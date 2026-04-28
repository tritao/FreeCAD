# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2025 Furgo                                              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Shared helpers for BIM Plan Edit GUI workflow tests."""

import Arch
import ArchSpace
import ArchWindow
import Draft
import FreeCAD
import FreeCADGui
import math
import Part
import Sketcher
from bimcommands import BimPlanSession
from bimplan import document_visuals as plan_document_visuals
from bimplan.selection import edit_nodes as plan_edit_nodes
from bimplan.providers import (
    PlanActionSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditProvider,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlaySpec,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanProviderTargetSpec,
    PlanToolSpec,
    PlanToolInteraction,
)
from bimplan.providers import get_plan_edit_registry
from bimtests.ArchWallGuiTestUtils import (
    ArchWallGuiTestCase,
    MockTracker,
    current_arch_wall_class,
)
from unittest.mock import patch


class _TestPlanProvider(PlanEditProvider):
    provider_id = "test-plan-provider"
    display_name = "Test Plan Provider"

    def __init__(self):
        self.executed_actions = []
        self.context_panel_calls = 0
        self.issue_calls = 0
        self.section_calls = 0
        self.tool_calls = 0
        self.overlay_calls = 0

    def get_issues(self, context):
        del context
        self.issue_calls += 1
        return (
            PlanIssueSpec(
                key="provider-review",
                title="Provider needs review",
                message="A test provider contribution should appear in the Plan Edit dock.",
                severity=PlanIssueSeverity.WARNING,
                actions=(
                    PlanActionSpec(
                        key="apply-provider-fix",
                        label="Apply Test Fix",
                    ),
                ),
            ),
        )

    def get_context_panels(self, context):
        self.context_panel_calls += 1
        primary_target = context.get_primary_target()
        target_label = getattr(primary_target, "label", "") if primary_target else ""
        if not target_label:
            target_label = "Nothing selected"
        return (
            PlanContextPanelSpec(
                key="provider-context",
                title=target_label,
                subtitle="Test Selection",
                state=PlanContextPanelState.SINGLE_OBJECT,
                subject_kind=PlanContextSubjectKind.ENDPOINT,
                summary_rows=(
                    PlanContextRowSpec(label="State", value="Ready"),
                    PlanContextRowSpec(label="Owner", value="Test Plan Provider"),
                ),
                message="Context panel content should appear in the Plan Edit dock.",
            ),
        )

    def get_inspector_sections(self, context):
        self.section_calls += 1
        primary_target = context.get_primary_target()
        target_label = getattr(primary_target, "label", "") if primary_target else ""
        if not target_label:
            target_label = "Nothing selected"
        return (
            PlanInspectorSection(
                key="provider-summary",
                title="Integration Summary",
                body=f"Primary target: {target_label}",
            ),
        )

    def get_tools(self, context):
        del context
        self.tool_calls += 1
        return (
            PlanToolSpec(
                key="run-provider-tool",
                label="Run Test Tool",
                tooltip="Run a provider-owned Plan Edit tool.",
            ),
        )

    def get_overlays(self, context):
        del context
        self.overlay_calls += 1
        return (
            PlanOverlaySpec(
                key="provider-preview",
                label="Provider Preview",
                points=((100.0, 200.0, 0.0),),
                color=(0.1, 0.2, 0.3),
            ),
            PlanOverlaySpec(
                key="electrical-preview",
                label="Electrical Preview",
                points=((160.0, 260.0, 0.0),),
                color=(0.9, 0.6, 0.1),
                category="electrical",
            ),
        )

    def execute_action(self, action_key, context, session):
        del session
        primary_target = context.get_primary_target()
        target_name = getattr(primary_target, "object_name", "") if primary_target else ""
        self.executed_actions.append((str(action_key or ""), str(target_name or "")))
        return True


class _DeletedDocument:
    def __getattribute__(self, name):
        if name == "Name":
            raise ReferenceError("Cannot access attribute 'Name' of deleted object")
        return object.__getattribute__(self, name)


class BimPlanEditGuiBase(ArchWallGuiTestCase):
    def _assert_selected_plan_target(self, session, kind, obj):
        self.assertEqual(session.selection.state.get_selected_plan_target(), (kind, obj))

    def _assert_no_selected_plan_target(self, session):
        self._assert_selected_plan_target(session, None, None)

    def _undo_document(self):
        undo = getattr(self.document, "undo", None)
        if callable(undo):
            undo()
        else:
            FreeCADGui.runCommand("Std_Undo", 0)
        self.pump_gui_events(timeout_ms=500)

    def _redo_document(self):
        redo = getattr(self.document, "redo", None)
        if callable(redo):
            redo()
        else:
            FreeCADGui.runCommand("Std_Redo", 0)
        self.pump_gui_events(timeout_ms=500)

    def _get_wall_endpoints(self, wall):
        start, end = wall.Proxy.calc_endpoints(wall)
        return (FreeCAD.Vector(start), FreeCAD.Vector(end))

    def _get_hosted_opening_center_u(self, opening):
        proxy = opening.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        center = proxy.get_plan_center_point()
        self.assertIsNotNone(center)
        return (
            FreeCAD.Vector(center).sub(context["origin"]).dot(context["axis_u"]),
            float(context["opening_half_width_u"]),
        )

    def _assert_wall_grips_match_wall(self, session, wall):
        endpoints = self._get_wall_endpoints(wall)
        midpoint = (endpoints[0] + endpoints[1]) * 0.5
        self.assertEqual(len(session._grip_trackers), 3)
        expected_points = (endpoints[0], endpoints[1], midpoint)
        for tracker, expected in zip(session._grip_trackers, expected_points):
            self.assertLess(tracker.get().distanceToPoint(expected), 1e-6)

    def _assert_selected_wall_visuals(self, session, wall):
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), wall)
        self.assertGreater(len(session._wall_overlay_trackers), 0)
        self._assert_wall_grips_match_wall(session, wall)

    def _assert_no_wall_edit_preview_visuals(self, session):
        self.assertEqual(len(session._preview_grip_trackers), 0)
        self.assertEqual(len(session._wall_edit_readout_trackers), 0)
        self.assertEqual(len(session._wall_edit_opening_preview_trackers), 0)

    def _assert_wall_selection_visual_consistency(self, session):
        selected_wall = session.selection.state.get_selected_target_for_kind("wall")
        if selected_wall is None:
            self.assertEqual(len(session._wall_overlay_trackers), 0)
            self.assertEqual(len(session._grip_trackers), 0)
            return
        self.assertGreater(len(session._wall_overlay_trackers), 0)
        if session.wall_edit.is_selected_wall_endpoint_editable():
            self._assert_wall_grips_match_wall(session, selected_wall)
        else:
            self.assertEqual(len(session._grip_trackers), 0)

    def _assert_selected_opening_visuals(self, session, opening):
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), opening)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def _assert_no_opening_move_preview_visuals(self, session):
        self.assertEqual(len(session._opening_move_preview_trackers), 0)
        self.assertIsNone(session._edit_opening)
        self.assertIsNone(session._edit_opening_handle_index)

    def _assert_opening_selection_visual_consistency(self, session):
        selected_opening = session.selection.state.get_selected_target_for_kind("opening")
        if selected_opening is None:
            self.assertEqual(len(session._opening_overlay_trackers), 0)
            self.assertEqual(len(session._opening_handle_trackers), 0)
            return
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def _get_space_overlap_volume(self, first_space, second_space):
        try:
            overlap = first_space.Shape.common(second_space.Shape)
        except Exception:
            return float("inf")
        try:
            return float(getattr(overlap, "Volume", 0.0) or 0.0)
        except Exception:
            return float("inf")

    def _assert_spaces_stay_distinct(self, spaces):
        self.assertEqual(len(spaces), 2)
        sorted_spaces = sorted(spaces, key=lambda item: float(item.Shape.CenterOfMass.x))
        left_space, right_space = sorted_spaces
        self.assertLess(float(left_space.Shape.CenterOfMass.x), 3000.0)
        self.assertGreater(float(right_space.Shape.CenterOfMass.x), 3000.0)
        self.assertLess(self._get_space_overlap_volume(left_space, right_space), 1e-3)
        for space in sorted_spaces:
            self.assertGreater(space.Proxy.getArea(space), 1_000_000.0)
            self.assertEqual(space.Proxy.getLastBoundaryError(space), "")
        return sorted_spaces

    def _create_adjacent_wall_linked_spaces(self, session):
        level, walls = self._make_split_plan_room_walls()
        divider_wall = next(wall for wall in walls if wall.Label == "Divider Wall")
        left_reference = FreeCAD.Vector(1500.0, 2000.0, 1000.0)
        right_reference = FreeCAD.Vector(4500.0, 2000.0, 1000.0)
        center_reference = FreeCAD.Vector(3000.0, 2000.0, 1000.0)

        left_divider_face = ArchSpace.getBoundaryFaceNamesForObject(
            divider_wall,
            reference_point=left_reference,
        )[0]
        right_divider_face = ArchSpace.getBoundaryFaceNamesForObject(
            divider_wall,
            reference_point=right_reference,
        )[0]

        boundaries = []
        for wall in walls:
            if wall is divider_wall:
                face_names = tuple(dict.fromkeys((left_divider_face, right_divider_face)))
            else:
                face_names = ArchSpace.getBoundaryFaceNamesForObject(
                    wall,
                    reference_point=center_reference,
                )
            boundaries.append((wall, face_names))
        self.assertEqual(len(boundaries), 5)

        report = session.spaces.build_space_region_candidate_report(boundaries, label="Two Rooms")
        major_candidates = [
            candidate
            for candidate in report.get("candidates", [])
            if candidate["area"] > 1_000_000.0
        ]
        self.assertEqual(len(major_candidates), 2)
        major_candidates.sort(key=lambda item: float(item["sample_point"].x))

        created_spaces = []
        for candidate in major_candidates:
            space = session.spaces.create_space_from_region_candidate(
                candidate,
                boundaries=boundaries,
                keep_boundaries=True,
            )
            self.assertIsNotNone(space)
            if hasattr(space, "BoundaryWalls"):
                space.BoundaryWalls = []
            space.Boundaries = list(boundaries)
            created_spaces.append(space)
        self.document.recompute()
        self.pump_gui_events()

        for space in created_spaces:
            self.assertTrue(str(getattr(space, "BoundaryRegionHint", "") or "").strip())
            self.assertEqual(len(session.spaces.get_space_boundary_entries(space)), 5)

        return level, walls, divider_wall, boundaries, created_spaces

    def _get_scenegraph_named_switches(self, session, switch_name):
        view = getattr(session, "view", None)
        scene_graph = view.getSceneGraph() if view else None
        if scene_graph is None:
            return []

        nodes = []

        def walk(node):
            if node is None:
                return
            try:
                name = str(node.getName().getString())
            except Exception:
                try:
                    name = str(node.getName())
                except Exception:
                    name = ""
            if name == switch_name:
                nodes.append(node)
            try:
                child_count = int(node.getNumChildren())
            except Exception:
                child_count = 0
            for index in range(child_count):
                try:
                    child = node.getChild(index)
                except Exception:
                    continue
                walk(child)

        walk(scene_graph)
        return nodes

    def _count_scenegraph_named_switches(self, session, switch_name):
        return len(self._get_scenegraph_named_switches(session, switch_name))

    def _get_scenegraph_edit_nodes(self, session):
        view = getattr(session, "view", None)
        scene_graph = view.getSceneGraph() if view else None
        if scene_graph is None:
            return []

        nodes = []

        def walk(node):
            if node is None:
                return
            try:
                type_name = node.getTypeId().getName().getString()
            except Exception:
                type_name = ""
            if type_name == "SoFCSelection":
                try:
                    object_name = str(node.objectName.getValue())
                    subelement_name = str(node.subElementName.getValue())
                except Exception:
                    object_name = ""
                    subelement_name = ""
                if subelement_name.startswith("EditNode"):
                    nodes.append((object_name, subelement_name))
            try:
                child_count = int(node.getNumChildren())
            except Exception:
                child_count = 0
            for index in range(child_count):
                try:
                    child = node.getChild(index)
                except Exception:
                    continue
                walk(child)

        walk(scene_graph)
        return nodes

    def _make_fake_left_mouse_press(self, x=250, y=250):
        return self._make_fake_left_mouse_button_event(x, y, down=True)

    def _make_fake_left_mouse_release(self, x=250, y=250):
        return self._make_fake_left_mouse_button_event(x, y, down=False)

    def _make_fake_mouse_move_event(self, x=250, y=250):
        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getPosition(self):
                return self._position

        return self._FakeEventCallback(_FakeMouseEvent(x, y))

    def _make_fake_mouse_wheel_event(self):
        class _FakeTypeId:
            def getName(self):
                return "SoMouseWheelEvent"

        class _FakeWheelEvent:
            def getTypeId(self):
                return _FakeTypeId()

        return self._FakeEventCallback(_FakeWheelEvent())

    def _make_fake_selection_node(self, document_name, object_name, sub_element_name):
        class _Field:
            def __init__(self, value):
                self._value = value

            def getValue(self):
                return self._value

        return type(
            "FakeSelectionNode",
            (),
            {
                "documentName": _Field(document_name),
                "objectName": _Field(object_name),
                "subElementName": _Field(sub_element_name),
            },
        )()

    def _make_fake_left_mouse_button_event(self, x=250, y=250, down=True):
        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                if down:
                    return coin.SoMouseButtonEvent.DOWN
                return coin.SoMouseButtonEvent.UP

            def getPosition(self):
                return self._position

        return self._FakeEventCallback(_FakeMouseEvent(x, y))

    def _make_plan_symbol_link(self, anchor=None, facing=None):
        level = Arch.makeFloor(name="Level 0")
        box = self.document.addObject("Part::Box", "PlanSymbolBox")
        box.Length = 1400
        box.Width = 1950
        box.Height = 600
        equipment = Arch.makeEquipment(box)
        if anchor is not None:
            equipment.PlanAnchor = FreeCAD.Vector(anchor)
        if facing is not None:
            equipment.PlanFacing = FreeCAD.Vector(facing)

        plan = self.document.addObject("Part::Feature", "PlanSymbol2D")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1400, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 0, 0), FreeCAD.Vector(1400, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 1950, 0), FreeCAD.Vector(0, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(0, 1950, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        equipment.PlanSymbols = [plan]

        link = self.document.addObject("App::Link", "PlanSymbolLink")
        link.setLink(equipment)
        if hasattr(link, "LinkTransform"):
            link.LinkTransform = True
        link.Label = "Double Bed 001"
        link.Placement.Base = FreeCAD.Vector(1000, 800, 0)
        level.addObject(link)

        self.document.recompute()
        self.pump_gui_events()
        return level, equipment, link

    def _make_direct_plan_symbol_equipment(self, anchor=None, facing=None):
        level = Arch.makeFloor(name="Level 0")
        box = self.document.addObject("Part::Box", "DirectPlanSymbolBox")
        box.Length = 1400
        box.Width = 1950
        box.Height = 600
        equipment = Arch.makeEquipment(box)
        if anchor is not None:
            equipment.PlanAnchor = FreeCAD.Vector(anchor)
        if facing is not None:
            equipment.PlanFacing = FreeCAD.Vector(facing)

        plan = self.document.addObject("Part::Feature", "DirectPlanSymbol2D")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1400, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 0, 0), FreeCAD.Vector(1400, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 1950, 0), FreeCAD.Vector(0, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(0, 1950, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        equipment.PlanSymbols = [plan]
        equipment.Label = "Bed 001"
        equipment.Placement.Base = FreeCAD.Vector(1000, 800, 0)
        level.addObject(equipment)

        self.document.recompute()
        self.pump_gui_events()
        return level, equipment

    def _make_linked_symbolic_equipment(self):
        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Feature", "LinkedPlanEquipmentSymbol")
        base.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(600, 0, 0)),
                Part.makeLine(FreeCAD.Vector(600, 0, 0), FreeCAD.Vector(600, 400, 0)),
                Part.makeLine(FreeCAD.Vector(600, 400, 0), FreeCAD.Vector(0, 400, 0)),
                Part.makeLine(FreeCAD.Vector(0, 400, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        equipment = Arch.makeEquipment(base)

        link = self.document.addObject("App::Link", "LinkedPlanEquipmentLink")
        link.setLink(equipment)
        if hasattr(link, "LinkTransform"):
            link.LinkTransform = True
        link.Label = "Nightstand 001"
        link.Placement.Base = FreeCAD.Vector(1000, 800, 0)
        level.addObject(link)

        self.document.recompute()
        self.pump_gui_events()
        return level, equipment, link

    def _make_plan_room_walls(self, size=4000, width=200, height=2500):
        level = Arch.makeFloor(name="Level 0")
        walls = []
        half = size * 0.5
        placements = (
            (FreeCAD.Vector(half, 0, 0), 0),
            (FreeCAD.Vector(size, half, 0), 90),
            (FreeCAD.Vector(half, size, 0), 180),
            (FreeCAD.Vector(0, half, 0), -90),
        )
        for index, (base, angle) in enumerate(placements, start=1):
            wall = Arch.makeWall(length=size, width=width, height=height, align="Left")
            wall.Label = f"Room Wall {index}"
            wall.Placement.Base = base
            wall.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), angle)
            level.addObject(wall)
            walls.append(wall)

        self.document.recompute()
        self.pump_gui_events()
        return level, walls

    def _make_split_plan_room_walls(self, width=200, height=2500):
        level = Arch.makeFloor(name="Level 0")
        walls = []
        placements = (
            ("South Wall", 6000, FreeCAD.Vector(3000, 0, 0), 0),
            ("East Wall", 4000, FreeCAD.Vector(6000, 2000, 0), 90),
            ("North Wall", 6000, FreeCAD.Vector(3000, 4000, 0), 180),
            ("West Wall", 4000, FreeCAD.Vector(0, 2000, 0), -90),
            ("Divider Wall", 4000, FreeCAD.Vector(3000, 2000, 0), 90),
        )
        for label, length, base, angle in placements:
            wall = Arch.makeWall(length=length, width=width, height=height, align="Left")
            wall.Label = label
            wall.Placement.Base = base
            wall.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), angle)
            level.addObject(wall)
            walls.append(wall)

        self.document.recompute()
        self.pump_gui_events()
        return level, walls

    def _make_plan_space_separator(
        self,
        level,
        start=FreeCAD.Vector(3000, 0, 0),
        end=FreeCAD.Vector(3000, 4000, 0),
        height=2500,
        label="Room Divider",
    ):
        separator = Arch.makeSpaceSeparator(start=start, end=end, height=height, name=label)
        level.addObject(separator)
        self.document.recompute()
        self.pump_gui_events()
        return separator

    def _make_plan_region(
        self,
        level,
        points=None,
        parent_space=None,
        label="Kitchen Zone",
    ):
        if points is None:
            points = [
                FreeCAD.Vector(900, 900, 0),
                FreeCAD.Vector(2900, 900, 0),
                FreeCAD.Vector(2900, 2100, 0),
                FreeCAD.Vector(900, 2100, 0),
            ]
        region = Arch.makePlanRegion(
            points=points,
            parent_space=parent_space,
            name=label,
        )
        level.addObject(region)
        self.document.recompute()
        self.pump_gui_events()
        return region

    def _make_windowed_plan_wall(self, length=3000, width=200, height=2500):
        level = Arch.makeFloor(name="Level 0")
        wall_base = Draft.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(length, 0, 0))
        wall = Arch.makeWall(wall_base, width=width, height=height, name="WindowedWall")
        level.addObject(wall)

        sketch = self.document.addObject("Sketcher::SketchObject", "WindowSketch")
        sketch.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90)
        sketch.addGeometry(
            Part.LineSegment(FreeCAD.Vector(900, 700, 0), FreeCAD.Vector(1700, 700, 0))
        )
        sketch.addGeometry(
            Part.LineSegment(FreeCAD.Vector(1700, 700, 0), FreeCAD.Vector(1700, 1900, 0))
        )
        sketch.addGeometry(
            Part.LineSegment(FreeCAD.Vector(1700, 1900, 0), FreeCAD.Vector(900, 1900, 0))
        )
        sketch.addGeometry(
            Part.LineSegment(FreeCAD.Vector(900, 1900, 0), FreeCAD.Vector(900, 700, 0))
        )
        sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", 1, 2, 2, 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", 2, 2, 3, 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", 3, 2, 0, 1))
        self.document.recompute()

        window = Arch.makeWindow(sketch)
        Arch.addComponents(window, wall)

        self.document.recompute()
        self.pump_gui_events()
        return level, wall, window

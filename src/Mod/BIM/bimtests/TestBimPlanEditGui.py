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

"""GUI tests for BIM Plan Edit wall and opening workflows."""

import Arch
import ArchSpace
import Draft
import FreeCAD
import FreeCADGui
import math
import Part
import Sketcher
from bimcommands import BimPlanSession
from bimplan.providers import (
    PlanActionSpec,
    PlanEditProvider,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanToolSpec,
)
from bimplan.registry import get_plan_edit_registry
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
                severity="warning",
                actions=(
                    PlanActionSpec(
                        key="apply-provider-fix",
                        label="Apply Test Fix",
                    ),
                ),
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
        )

    def execute_action(self, action_key, context, session):
        del session
        primary_target = context.get_primary_target()
        target_name = getattr(primary_target, "object_name", "") if primary_target else ""
        self.executed_actions.append((str(action_key or ""), str(target_name or "")))
        return True


class TestBimPlanEditGui(ArchWallGuiTestCase):
    def _assert_selected_plan_target(self, session, kind, obj):
        self.assertEqual(session._get_selected_plan_target(), (kind, obj))

    def _assert_no_selected_plan_target(self, session):
        self._assert_selected_plan_target(session, None, None)

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
        segments = (
            ("South Wall", FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(6000, 0, 0)),
            ("East Wall", FreeCAD.Vector(6000, 0, 0), FreeCAD.Vector(6000, 4000, 0)),
            ("North Wall", FreeCAD.Vector(6000, 4000, 0), FreeCAD.Vector(0, 4000, 0)),
            ("West Wall", FreeCAD.Vector(0, 4000, 0), FreeCAD.Vector(0, 0, 0)),
            ("Divider Wall", FreeCAD.Vector(3000, 0, 0), FreeCAD.Vector(3000, 4000, 0)),
        )
        for label, start, end in segments:
            base = Draft.makeLine(start, end)
            wall = Arch.makeWall(base, width=width, height=height, name=label.replace(" ", ""))
            wall.Label = label
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

    def test_plan_edit_renders_registered_provider_contributions(self):
        from PySide import QtGui

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        panel = session.task_panel
        self.assertIsNotNone(panel, "Plan Edit task panel should be attached.")
        panel.refresh_from_session()
        self.pump_gui_events()

        self.assertFalse(panel.integration_panel.isHidden())
        self.assertTrue(panel.integration_panel.isVisibleTo(panel.form))
        labels = [
            str(widget.text()) for widget in panel.integration_panel.findChildren(QtGui.QLabel)
        ]
        self.assertTrue(any("Provider needs review" in text for text in labels))
        self.assertTrue(any("Integration Summary" in text for text in labels))
        self.assertTrue(any("Overlays" in text for text in labels))

        overlay_checkboxes = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QCheckBox)
            if "Provider Preview" in str(widget.text())
        ]
        self.assertEqual(1, len(overlay_checkboxes))
        overlay_key = session.get_plan_provider_overlay_visibility_key(
            "test-plan-provider",
            "provider-preview",
        )
        self.assertTrue(overlay_checkboxes[0].isChecked())
        self.assertNotIn(overlay_key, session._provider_overlay_visibility)
        overlay_checkboxes[0].setChecked(False)
        self.pump_gui_events()
        self.assertFalse(session._provider_overlay_visibility[overlay_key])
        overlay_checkboxes[0].setChecked(True)
        self.pump_gui_events()
        self.assertNotIn(overlay_key, session._provider_overlay_visibility)

        buttons = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QPushButton)
            if str(widget.text()) == "Apply Test Fix"
        ]
        self.assertEqual(1, len(buttons))

        buttons[0].click()
        self.pump_gui_events()
        self.assertEqual([("apply-provider-fix", "")], provider.executed_actions)

        tool_buttons = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QPushButton)
            if str(widget.text()) == "Run Test Tool"
        ]
        self.assertEqual(1, len(tool_buttons))

        tool_buttons[0].click()
        self.pump_gui_events()
        self.assertEqual(
            [("apply-provider-fix", ""), ("run-provider-tool", "")],
            provider.executed_actions,
        )
        self.assertGreater(provider.tool_calls, 0)
        self.assertGreater(provider.overlay_calls, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_can_disable_provider_integrations_for_perf(self):
        """A temporary perf switch should bypass providers and hide the integration panel."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        with patch.dict("os.environ", {"FC_BIM_PLAN_EDIT_DISABLE_INTEGRATIONS": "1"}):
            session = BimPlanSession.start_session()
            self.assertIsNotNone(session)
            self.pump_gui_events()

            panel = session.task_panel
            self.assertIsNotNone(panel)
            panel.refresh_from_session()
            self.pump_gui_events(timeout_ms=500)

            self.assertEqual(0, provider.issue_calls)
            self.assertEqual(0, provider.section_calls)
            self.assertEqual(0, provider.tool_calls)
            self.assertEqual(0, provider.overlay_calls)
            self.assertTrue(panel.integration_panel.isHidden())
            self.assertFalse(
                session.execute_plan_provider_action("test-plan-provider", "apply-provider-fix")
            )
            self.assertEqual([], provider.executed_actions)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()

    def test_plan_edit_provider_point_tool_dispatches_plan_point(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            tooltip="Click in plan to place a test marker.",
            transaction_label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction="point",
            prompt="Click a plan point to place a test marker.",
        )
        captured = []

        def _capture_action(provider_id, action_key, transaction_label="", payload=None):
            captured.append((provider_id, action_key, transaction_label, payload))
            return True

        snap_info = {
            "Object": wall.Name,
            "Component": "Edge1",
            "SubName": "Edge1",
        }
        selected_target = ("wall", wall)
        selected_targets = ("selected-wall-target",)
        hovered_target = ("wall", wall)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint") as get_point,
            patch.object(
                FreeCADGui.Snapper,
                "snapInfo",
                snap_info,
                create=True,
            ),
            patch.object(
                session,
                "execute_plan_provider_action",
                side_effect=_capture_action,
            ),
            patch.object(
                session,
                "_get_selected_plan_target",
                return_value=selected_target,
            ),
            patch.object(
                session,
                "_get_selected_plan_targets",
                return_value=selected_targets,
            ),
            patch.object(
                session,
                "_get_hovered_plan_target",
                return_value=hovered_target,
            ),
        ):
            self.assertTrue(session.start_plan_provider_point_tool(tool))
            self.assertEqual("Provider Point", session.current_tool)
            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            session._handle_provider_point_tool_point(raw_point, wall)
            self.assertEqual("Provider Point", session.current_tool)
            self.assertGreaterEqual(get_point.call_count, 2)
            self.assertTrue(session._cancel_provider_point_tool())

        self.assertEqual(1, len(captured))
        provider_id, action_key, transaction_label, payload = captured[0]
        self.assertEqual("test-plan-provider", provider_id)
        self.assertEqual("place-test-marker", action_key)
        self.assertEqual("Place Test Marker", transaction_label)
        self.assertIs(tool, payload["tool"])
        self.assertEqual(120.0, payload["point"].x)
        self.assertEqual(340.0, payload["point"].y)
        self.assertEqual(("wall", wall), payload["host_target"])
        self.assertEqual("selected", payload["host_source"])
        expected_placement = session._project_provider_point_to_host(payload["point"], wall)
        self.assertIsNotNone(expected_placement)
        self.assertAlmostEqual(expected_placement.x, payload["placement_point"].x)
        self.assertAlmostEqual(expected_placement.y, payload["placement_point"].y)
        self.assertEqual(999.0, payload["raw_point"].z)
        self.assertEqual(snap_info, payload["snap_info"])
        self.assertIs(wall, payload["snap_object"])
        self.assertEqual(("wall", wall), payload["snap_target"])
        self.assertEqual(self.document.Name, payload["snap_document_name"])
        self.assertEqual(wall.Name, payload["snap_object_name"])
        self.assertEqual("Edge1", payload["snap_component"])
        self.assertEqual("Edge1", payload["snap_subname"])
        self.assertEqual(selected_target, payload["selected_target"])
        self.assertEqual(selected_targets, payload["selected_targets"])
        self.assertEqual(hovered_target, payload["hovered_target"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_uses_selected_wall_host_context(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction="point",
        )
        captured = []

        def _capture_action(provider_id, action_key, transaction_label="", payload=None):
            captured.append((provider_id, action_key, transaction_label, payload))
            return True

        with (
            patch.object(FreeCADGui.Snapper, "getPoint"),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
            patch.object(session, "execute_plan_provider_action", side_effect=_capture_action),
        ):
            self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
            self.assertTrue(session.start_plan_provider_point_tool(tool))
            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            session._handle_provider_point_tool_point(raw_point, None)
            self.assertTrue(session._cancel_provider_point_tool())

        self.assertEqual(1, len(captured))
        payload = captured[0][3]
        self.assertEqual(("wall", wall), payload["host_target"])
        self.assertEqual("selected", payload["host_source"])
        expected_placement = session._project_provider_point_to_host(payload["point"], wall)
        self.assertIsNotNone(expected_placement)
        self.assertAlmostEqual(expected_placement.x, payload["placement_point"].x)
        self.assertAlmostEqual(expected_placement.y, payload["placement_point"].y)
        self.assertEqual((None, None), payload["snap_target"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_previews_selected_wall_host(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction="point",
        )
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
        ):
            self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
            self.assertTrue(session.start_plan_provider_point_tool(tool))
            self.assertIn("movecallback", captured)

            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            captured["movecallback"](raw_point, None)

            plan_point = session._project_plan_point(raw_point)
            expected_placement = session._project_provider_point_to_host(plan_point, wall)
            self.assertIsNotNone(expected_placement)
            self.assertEqual(("wall", wall), session._provider_point_preview_host_target)
            self.assertEqual("selected", session._provider_point_preview_host_source)
            self.assertAlmostEqual(expected_placement.x, session._provider_point_preview_point.x)
            self.assertAlmostEqual(expected_placement.y, session._provider_point_preview_point.y)
            self.assertGreater(len(session._provider_point_preview_trackers), 2)

            self.assertTrue(session._cancel_provider_point_tool())

        self.assertIsNone(session._provider_point_preview_point)
        self.assertEqual([], session._provider_point_preview_trackers)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_previews_unhosted_point(self):
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction="point",
        )
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
            patch.object(session, "_get_selected_plan_target", return_value=(None, None)),
            patch.object(session, "_get_selected_plan_targets", return_value=()),
            patch.object(session, "_get_hovered_plan_target", return_value=(None, None)),
        ):
            self.assertTrue(session.start_plan_provider_point_tool(tool))
            self.assertIn("movecallback", captured)

            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            captured["movecallback"](raw_point, None)

            plan_point = session._project_plan_point(raw_point)
            self.assertEqual((None, None), session._provider_point_preview_host_target)
            self.assertEqual("", session._provider_point_preview_host_source)
            self.assertAlmostEqual(plan_point.x, session._provider_point_preview_point.x)
            self.assertAlmostEqual(plan_point.y, session._provider_point_preview_point.y)
            self.assertEqual(2, len(session._provider_point_preview_trackers))

            self.assertTrue(session._cancel_provider_point_tool())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_selection_defers_provider_refresh(self):
        """Wall selection should not synchronously run provider integrations."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        panel = session.task_panel
        self.assertIsNotNone(panel)
        panel.refresh_from_session()
        self.pump_gui_events()
        provider.issue_calls = 0
        provider.section_calls = 0
        provider.tool_calls = 0
        provider.overlay_calls = 0

        session._set_hovered_wall(wall)
        with patch.object(session, "_get_edit_node", return_value=None):
            press = self._make_fake_left_mouse_press(250, 250)
            session._on_mouse_pressed(press)

        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(0, provider.issue_calls)
        self.assertEqual(0, provider.section_calls)
        self.assertEqual(0, provider.tool_calls)
        self.assertEqual(0, provider.overlay_calls)

        self.pump_gui_events(timeout_ms=500)
        self.assertGreater(provider.issue_calls, 0)
        self.assertGreater(provider.section_calls, 0)
        self.assertGreater(provider.tool_calls, 0)
        self.assertGreater(provider.overlay_calls, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_overlay_point_selects_target_object(self):
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        node = self._make_fake_selection_node(
            self.document.Name,
            marker.Name,
            "ProviderOverlayPoint:object:0",
        )
        event = self._make_fake_left_mouse_press()

        self.assertTrue(
            session._activate_provider_overlay_target_node(
                ("provider_overlay_point", node),
                event,
            )
        )
        self.assertTrue(event._handled)
        self.assertIn(marker, FreeCADGui.Selection.getSelection())
        self._assert_no_selected_plan_target(session)
        self.assertIn("Object: Electrical Marker", session.task_panel.status.text())
        self.assertIn("integration details", session.task_panel.status.text())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_additive_provider_overlay_point_keeps_wall_selection(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
        self.pump_gui_events()
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual([wall], FreeCADGui.Selection.getSelection())

        node = self._make_fake_selection_node(
            self.document.Name,
            marker.Name,
            "ProviderOverlayPoint:object:0",
        )
        event = self._make_fake_left_mouse_press()

        with (
            patch.object(session, "_get_edit_node", return_value=("provider_overlay_point", node)),
            patch.object(
                session,
                "_toggle_raw_plan_object_selection",
                wraps=session._toggle_raw_plan_object_selection,
            ) as toggle_raw_selection,
        ):
            self.assertTrue(session._toggle_plan_target_selection_at_position((250, 250), event))

        toggle_raw_selection.assert_called_once_with(marker, event)
        self.assertTrue(event._handled)
        selection = FreeCADGui.Selection.getSelection()
        self.assertIn(wall, selection)
        self.assertIn(marker, session._provider_selected_objects)
        self.assertIn(marker, session.get_selected_objects())
        self._assert_selected_plan_target(session, "wall", wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_embedded_wall_uses_sane_top_plane(self):
        """Embedded wall creation in Plan Edit should start from a clean top plane."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.activate_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Wall")
        self.assertIsNotNone(session._embedded_tool, "Wall tool should be embedded in Plan Edit.")
        self.assertIsInstance(session._embedded_tool, current_arch_wall_class())

        self.assertPlaneIsSaneTop(session.get_interaction_plane())
        self.assertPlaneIsSaneTop(session._embedded_tool._plane)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_embedded_wall_first_update_stays_sane(self):
        """The first embedded wall preview update in Plan Edit should stay bounded."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.activate_wall_tool()
        self.pump_gui_events()

        cmd = session._embedded_tool
        self.assertIsInstance(cmd, current_arch_wall_class())

        cmd.tracker = MockTracker()
        first = FreeCAD.Vector(1000, 1000, 0)
        second = FreeCAD.Vector(3000, 1000, 0)

        cmd.getPoint(first)
        self.assertEqual(len(cmd.points), 1)

        self.assertTrue(
            FreeCADGui.Control.activeDialog(),
            "Embedded wall point picking should open a live Draft dialog.",
        )
        cmd.update(second, None)

        self.assertPlaneIsSaneTop(cmd._plane)
        self.assertIsNotNone(cmd.tracker.last_points, "Expected a preview update on the tracker.")
        self.assertEqual(len(cmd.tracker.last_points), 2)
        for point in cmd.tracker.last_points:
            self.assertLess(abs(point.x), 1e6)
            self.assertLess(abs(point.y), 1e6)
            self.assertLess(abs(point.z), 1e6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_creates_four_walls(self):
        """Plan Edit should create a rectangular run as four baseless walls."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        session.activate_rect_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Rect Wall")

        session._handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
        session._handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
        self.assertEqual(len(walls), 4, "Expected exactly four walls from a rectangular run.")
        for wall in walls:
            self.assertIn(level, wall.InListRecursive)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_autojoins_closed_run(self):
        """Rectangular wall runs should autojoin as one closed addition host when enabled."""

        arch_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch")
        original_autojoin = arch_params.GetBool("autoJoinWalls", False)

        try:
            arch_params.SetBool("autoJoinWalls", True)
            level = Arch.makeFloor(name="Level 0")
            self.document.recompute()

            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(level)

            session = BimPlanSession.start_session()
            self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
            self.pump_gui_events()

            before = {obj.Name for obj in self.document.Objects}
            session.activate_rect_wall_tool()
            self.pump_gui_events()

            session._handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
            session._handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
            self.pump_gui_events()

            created = [obj for obj in self.document.Objects if obj.Name not in before]
            walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
            self.assertEqual(len(walls), 4)
            self.assertEqual(sum(len(wall.Additions) for wall in walls), 3)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()
        finally:
            arch_params.SetBool("autoJoinWalls", original_autojoin)

    def test_plan_edit_does_not_open_dedicated_dock_pane(self):
        """Plan Edit should rely on the contextual task panel, not a separate dock widget."""

        from PySide import QtGui

        FreeCADGui.activateWorkbench("BIMWorkbench")
        workbench = FreeCADGui.activeWorkbench()
        if hasattr(workbench, "setTaskWatchers"):
            FreeCADGui.Control.clearTaskWatcher()
            workbench.setTaskWatchers()
        FreeCADGui.Control.showTaskView()
        self.pump_gui_events(timeout_ms=400)

        main_window = FreeCADGui.getMainWindow()
        self.assertIsNone(main_window.findChild(QtGui.QDockWidget, "BIMPlanEditDock"))

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events(timeout_ms=400)

        self.assertIsNone(main_window.findChild(QtGui.QDockWidget, "BIMPlanEditDock"))
        context_controls = main_window.findChild(QtGui.QWidget, "BIMPlanEditContextControls")
        self.assertIsNotNone(context_controls)
        self.assertIs(session.task_panel.form, context_controls)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_exposes_contextual_session_controls(self):
        """Plan Edit should expose the reusable session controls in the contextual task panel."""

        from PySide import QtGui

        FreeCADGui.activateWorkbench("BIMWorkbench")
        workbench = FreeCADGui.activeWorkbench()
        if hasattr(workbench, "setTaskWatchers"):
            FreeCADGui.Control.clearTaskWatcher()
            workbench.setTaskWatchers()
        FreeCADGui.Control.showTaskView()
        self.pump_gui_events(timeout_ms=400)

        main_window = FreeCADGui.getMainWindow()
        self.assertIsNone(main_window.findChild(QtGui.QWidget, "BIMPlanEditContextControls"))

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events(timeout_ms=400)

        context_controls = main_window.findChild(QtGui.QWidget, "BIMPlanEditContextControls")
        self.assertIsNotNone(context_controls)
        self.assertTrue(context_controls.isVisible())

        session.shutdown(close_dialog=False)
        self.pump_gui_events(timeout_ms=400)

        self.assertIsNone(main_window.findChild(QtGui.QWidget, "BIMPlanEditContextControls"))

    def test_plan_edit_disables_external_command_actions(self):
        """External commands should not stay available while Plan Edit owns interaction."""

        from PySide import QtGui
        from bimplan import command_gate

        main_window = FreeCADGui.getMainWindow()
        action = QtGui.QAction(main_window)
        action.setObjectName("Arch_Window")
        action.setEnabled(True)
        main_window.addAction(action)
        command_action = QtGui.QAction()
        command_action.setObjectName("Arch_Wall")
        command_action.setEnabled(True)
        original_command = FreeCADGui.Command

        class _FakeCommand:
            def getAction(self):
                return [command_action]

        class _CommandNamespace:
            def get(self, command_name):
                if command_name == "Arch_Wall":
                    return _FakeCommand()
                return original_command.get(command_name)

        session = None

        try:
            with patch.object(command_gate.FreeCADGui, "Command", _CommandNamespace()):
                session = BimPlanSession.start_session()
                self.assertIsNotNone(session)
                self.pump_gui_events()

                self.assertTrue(command_gate.is_command_blocked("Arch_Window"))
                self.assertFalse(action.isEnabled())
                self.assertFalse(command_action.isEnabled())

                action.setEnabled(True)
                command_action.setEnabled(True)
                self.pump_gui_events()
                self.assertFalse(action.isEnabled())
                self.assertFalse(command_action.isEnabled())

                session.shutdown(close_dialog=False)
                session = None
                self.pump_gui_events()

            self.assertFalse(command_gate.is_command_blocked("Arch_Window"))
            self.assertTrue(action.isEnabled())
            self.assertTrue(command_action.isEnabled())
        finally:
            if session is not None:
                session.shutdown(close_dialog=False, teardown=True)
            command_gate.uninstall()
            main_window.removeAction(action)
            action.deleteLater()
            command_action.deleteLater()

    def test_plan_edit_hides_joined_wall_additions(self):
        """Joined child walls should stay hidden so their footprints do not overdraw the host."""

        host = Arch.makeWall(length=3000, width=200, height=2500)
        child = Arch.makeWall(length=3000, width=200, height=2500)
        Arch.addComponents(child, host)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(host.ViewObject.Visibility)
        self.assertFalse(
            child.ViewObject.Visibility,
            "Joined child walls should stay hidden in Plan Edit to avoid double rendering.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_slabs_visible_but_not_selectable(self):
        """Active-storey slabs should not block wall picking in Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        rect = Draft.makeRectangle(6000, 6000)
        slab = Arch.makeStructure(rect, height=200, name="TestSlab")
        slab.IfcType = "Slab"

        level.addObject(wall)
        level.addObject(slab)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Selectable)
        self.assertTrue(slab.ViewObject.Visibility)
        self.assertFalse(
            slab.ViewObject.Selectable,
            "Slabs should stay visible as background context but not intercept selection.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_global_mode_keeps_slabs_not_selectable(self):
        """Global plan mode should still treat slabs as non-selectable background."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)

        rect = Draft.makeRectangle(6000, 6000)
        slab = Arch.makeStructure(rect, height=200, name="TestSlab")
        slab.IfcType = "Slab"

        self.document.recompute()

        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertIsNone(session.active_storey)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertTrue(slab.ViewObject.Visibility)
        self.assertFalse(
            slab.ViewObject.Selectable,
            "Slabs should stay unselectable even when Plan Edit is in Global XY mode.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_equipment_visible_but_not_selectable(self):
        """Equipment should appear in plan as passive context without stealing picks."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "PlanEquipmentBox")
        box.Length = 800
        box.Width = 600
        box.Height = 900
        equipment = Arch.makeEquipment(box)

        level.addObject(wall)
        level.addObject(equipment)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertTrue(equipment.ViewObject.Visibility)
        self.assertFalse(
            equipment.ViewObject.Selectable,
            "Equipment should stay visible as context but not intercept wall editing picks.",
        )
        self.assertIn("Footprint", equipment.ViewObject.listDisplayModes())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_symbolic_equipment_visible_but_not_selectable(self):
        """Symbolic edge-only equipment should also appear as passive plan context."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        base = self.document.addObject("Part::Feature", "PlanEquipmentSymbol")
        base.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(600, 0, 0)),
                Part.makeLine(FreeCAD.Vector(600, 0, 0), FreeCAD.Vector(600, 400, 0)),
                Part.makeLine(FreeCAD.Vector(600, 400, 0), FreeCAD.Vector(0, 400, 0)),
                Part.makeLine(FreeCAD.Vector(0, 400, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        equipment = Arch.makeEquipment(base)

        level.addObject(wall)
        level.addObject(equipment)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(equipment.ViewObject.Visibility)
        self.assertFalse(equipment.ViewObject.Selectable)
        self.assertGreater(equipment.ViewObject.Proxy.lcoords.point.getNum(), 0)
        self.assertGreater(equipment.ViewObject.Proxy.lset.numVertices.getNum(), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_linked_symbol_instances_are_selectable_with_handles(self):
        """Linked equipment instances should be editable plan targets, not passive context."""

        level, _equipment, link = self._make_plan_symbol_link()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        self.assertTrue(link.ViewObject.Visibility)
        self.assertTrue(link.ViewObject.Selectable)
        self.assertTrue(session._is_plan_symbol_instance(link))

        self.assertTrue(session._select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        self.assertIs(link, session.selected_symbol)
        self.assertEqual(
            {"move", "rotate"},
            {role for role, _point, _marker in session._get_selected_symbol_handle_specs(link)},
        )
        self.assertEqual(2, len(session._symbol_handle_trackers))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_linked_symbol_child_picks_prefer_link_instance(self):
        """Picking linked symbol children should resolve to the placed link instance."""

        level, equipment, link = self._make_plan_symbol_link()
        plan_symbol = equipment.PlanSymbols[0]
        base = equipment.Base

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        original_view = session.view
        original_pick_opening = session._pick_plan_opening_target_from_overlays
        opening_pick_calls = []

        class FakeView:
            def __init__(self, infos):
                self._infos = infos

            def getObjectsInfo(self, _mouse_pos):
                return self._infos

        def fail_if_opening_overlay_pick_runs(*_args, **_kwargs):
            opening_pick_calls.append(True)
            return None

        try:
            session._pick_plan_opening_target_from_overlays = fail_if_opening_overlay_pick_runs
            session.view = FakeView(
                [{"Document": self.document.Name, "Object": plan_symbol.Name, "ParentObject": link}]
            )
            self.assertEqual(("symbol", link), session._get_plan_target_at_position((100, 100)))

            session.view = FakeView(
                [{"Document": self.document.Name, "Object": base.Name, "ParentObject": link}]
            )
            self.assertEqual(("symbol", link), session._get_plan_target_at_position((100, 100)))
            self.assertEqual([], opening_pick_calls)
        finally:
            session._pick_plan_opening_target_from_overlays = original_pick_opening
            session.view = original_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_linked_symbol_overlay_fallback_picks_symbol_when_view_pick_misses(self):
        """Plan Edit should fall back to overlay geometry when footprint picking misses."""

        level, _equipment, link = self._make_linked_symbolic_equipment()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        segments = session._get_symbol_overlay_segments(link)
        self.assertTrue(segments, "Expected linked symbolic equipment to expose overlay segments.")
        start, end = segments[0]
        mid = FreeCAD.Vector(
            (start.x + end.x) * 0.5, (start.y + end.y) * 0.5, (start.z + end.z) * 0.5
        )

        real_view = session.view
        screen_pos = real_view.getPointOnScreen(mid)

        class FakeView:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def getObjectsInfo(self, _mouse_pos):
                return None

            def getPointOnScreen(self, point):
                return self._wrapped.getPointOnScreen(point)

        try:
            session.view = FakeView(real_view)
            mouse_pos = (int(screen_pos[0]), int(screen_pos[1]))
            self.assertEqual(("symbol", link), session._get_plan_target_at_position(mouse_pos))
        finally:
            session.view = real_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_direct_symbol_instances_are_selectable_with_handles(self):
        """Direct equipment with authored plan symbols should also be editable plan targets."""

        level, equipment = self._make_direct_plan_symbol_equipment()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(equipment)
        self.pump_gui_events()

        self.assertTrue(equipment.ViewObject.Visibility)
        self.assertTrue(equipment.ViewObject.Selectable)
        self.assertTrue(session._is_plan_symbol_instance(equipment))
        self.assertEqual("symbol", session._get_plan_target_kind_for_object(equipment))

        self.assertTrue(session._select_symbol_for_plan_edit(equipment))
        self.pump_gui_events()

        self.assertIs(equipment, session.selected_symbol)
        self.assertEqual(
            {"move", "rotate"},
            {
                role
                for role, _point, _marker in session._get_selected_symbol_handle_specs(equipment)
            },
        )
        self.assertEqual(2, len(session._symbol_handle_trackers))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_direct_symbol_dependencies_resolve_to_symbol_owner(self):
        """Plan Edit should keep direct symbol dependencies pickable and mapped to their owner."""

        level, equipment = self._make_direct_plan_symbol_equipment()
        plan_symbol = equipment.PlanSymbols[0]
        base = equipment.Base

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(equipment)
        self.pump_gui_events()

        self.assertIs(session._get_plan_semantic_object(plan_symbol), equipment)
        self.assertIs(session._get_plan_semantic_object(base), equipment)
        self.assertTrue(plan_symbol.ViewObject.Visibility)
        self.assertTrue(plan_symbol.ViewObject.Selectable)

        original_view = session.view

        class FakeView:
            def __init__(self, infos):
                self._infos = infos

            def getObjectsInfo(self, _mouse_pos):
                return self._infos

        try:
            session.view = FakeView(
                [
                    {
                        "Document": self.document.Name,
                        "Object": plan_symbol.Name,
                        "ParentObject": equipment,
                    }
                ]
            )
            self.assertEqual(
                ("symbol", equipment), session._get_plan_target_at_position((100, 100))
            )

            session.view = FakeView(
                [{"Document": self.document.Name, "Object": base.Name, "ParentObject": equipment}]
            )
            self.assertEqual(
                ("symbol", equipment), session._get_plan_target_at_position((100, 100))
            )
        finally:
            session.view = original_view

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(plan_symbol)
        self.pump_gui_events()
        self.assertIs(equipment, session.selected_symbol)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(base)
        self.pump_gui_events()
        self.assertIs(equipment, session.selected_symbol)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_symbol_handles_commit_link_placement(self):
        """Move/rotate symbol handles should update only the instance placement."""

        level, equipment, link = self._make_plan_symbol_link()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.assertTrue(session._select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }

        session.current_tool = "Move Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "move"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["move"]
        session._finish_symbol_handle_point_pick(FreeCAD.Vector(2400, 1600, 0))
        self.pump_gui_events()

        self.assertAlmostEqual(2400.0, link.Placement.Base.x, delta=1e-6)
        self.assertAlmostEqual(1600.0, link.Placement.Base.y, delta=1e-6)
        self.assertIs(session.selected_symbol, link)

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }
        anchor = FreeCAD.Vector(link.Placement.Base)

        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        session._finish_symbol_handle_point_pick(FreeCAD.Vector(anchor.x, anchor.y + 1000, 0))
        self.pump_gui_events()

        axis = link.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        self.assertAlmostEqual(0.0, axis.x, delta=1e-3)
        self.assertGreater(axis.y, 0.99)
        self.assertIs(session.selected_symbol, link)
        self.assertIs(equipment, link.LinkedObject)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_symbol_handles_honor_authored_anchor_and_facing(self):
        """Symbol handle positions and edits should use authored local plan metadata."""

        level, equipment, link = self._make_plan_symbol_link(
            anchor=FreeCAD.Vector(700, 975, 0),
            facing=FreeCAD.Vector(0, 1, 0),
        )

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.assertTrue(session._select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }
        expected_anchor = link.Placement.multVec(equipment.PlanAnchor)
        self.assertAlmostEqual(expected_anchor.x, handle_points["move"].x, delta=1e-6)
        self.assertAlmostEqual(expected_anchor.y, handle_points["move"].y, delta=1e-6)

        rotate_offset = handle_points["rotate"].sub(handle_points["move"])
        rotate_offset.z = 0
        rotate_offset.normalize()
        self.assertAlmostEqual(0.0, rotate_offset.x, delta=1e-3)
        self.assertGreater(rotate_offset.y, 0.99)

        target_anchor = FreeCAD.Vector(3200, 2400, 0)
        session.current_tool = "Move Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "move"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["move"]
        session._finish_symbol_handle_point_pick(target_anchor)
        self.pump_gui_events()

        self.assertAlmostEqual(2500.0, link.Placement.Base.x, delta=1e-6)
        self.assertAlmostEqual(1425.0, link.Placement.Base.y, delta=1e-6)
        moved_anchor = link.Placement.multVec(equipment.PlanAnchor)
        self.assertAlmostEqual(target_anchor.x, moved_anchor.x, delta=1e-6)
        self.assertAlmostEqual(target_anchor.y, moved_anchor.y, delta=1e-6)

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }
        anchor = link.Placement.multVec(equipment.PlanAnchor)
        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        session._finish_symbol_handle_point_pick(FreeCAD.Vector(anchor.x + 1000, anchor.y, 0))
        self.pump_gui_events()

        rotated_anchor = link.Placement.multVec(equipment.PlanAnchor)
        self.assertAlmostEqual(anchor.x, rotated_anchor.x, delta=1e-6)
        self.assertAlmostEqual(anchor.y, rotated_anchor.y, delta=1e-6)
        facing = link.Placement.Rotation.multVec(equipment.PlanFacing)
        facing.z = 0
        facing.normalize()
        self.assertGreater(facing.x, 0.99)
        self.assertAlmostEqual(0.0, facing.y, delta=1e-3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_symbol_rotation_snaps_to_angle_increment(self):
        """Symbol rotation should snap to the configured angular increment by default."""

        level, equipment, link = self._make_plan_symbol_link()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.assertTrue(session._select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }
        anchor = session._get_symbol_anchor_point(link)
        target_angle = math.radians(10.0)
        raw_point = FreeCAD.Vector(
            anchor.x + 1000.0 * math.cos(target_angle),
            anchor.y + 1000.0 * math.sin(target_angle),
            anchor.z,
        )

        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        with (
            patch.object(session, "_symbol_rotation_snap_enabled", return_value=True),
            patch.object(session, "_get_symbol_rotation_snap_increment_degrees", return_value=15.0),
            patch.object(
                session, "_symbol_rotation_free_angle_override_active", return_value=False
            ),
        ):
            session._finish_symbol_handle_point_pick(raw_point)
        self.pump_gui_events()

        facing = link.Placement.Rotation.multVec(equipment.PlanFacing)
        angle = math.degrees(math.atan2(facing.y, facing.x))
        self.assertAlmostEqual(15.0, angle, delta=1e-3)
        rotated_anchor = session._get_symbol_anchor_point(link)
        self.assertAlmostEqual(anchor.x, rotated_anchor.x, delta=1e-6)
        self.assertAlmostEqual(anchor.y, rotated_anchor.y, delta=1e-6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_symbol_rotation_shift_override_skips_snap(self):
        """Holding the free-angle override should bypass symbol rotation snapping."""

        level, equipment, link = self._make_plan_symbol_link()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session._refresh_plan_object_footprint_display(link)
        self.assertTrue(session._select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point for role, point, _marker in session._get_selected_symbol_handle_specs(link)
        }
        anchor = session._get_symbol_anchor_point(link)
        target_angle = math.radians(10.0)
        raw_point = FreeCAD.Vector(
            anchor.x + 1000.0 * math.cos(target_angle),
            anchor.y + 1000.0 * math.sin(target_angle),
            anchor.z,
        )

        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        with (
            patch.object(session, "_symbol_rotation_snap_enabled", return_value=True),
            patch.object(session, "_get_symbol_rotation_snap_increment_degrees", return_value=15.0),
            patch.object(session, "_symbol_rotation_free_angle_override_active", return_value=True),
        ):
            session._finish_symbol_handle_point_pick(raw_point)
        self.pump_gui_events()

        facing = link.Placement.Rotation.multVec(equipment.PlanFacing)
        angle = math.degrees(math.atan2(facing.y, facing.x))
        self.assertAlmostEqual(10.0, angle, delta=1e-3)
        rotated_anchor = session._get_symbol_anchor_point(link)
        self.assertAlmostEqual(anchor.x, rotated_anchor.x, delta=1e-6)
        self.assertAlmostEqual(anchor.y, rotated_anchor.y, delta=1e-6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_global_mode_hides_unsupported_objects(self):
        """Global plan mode should hide unsupported objects instead of restoring them as-is."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        self.document.recompute()

        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertIsNone(session.active_storey)
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(box.ViewObject.Visibility)
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hides_unsupported_active_storey_objects(self):
        """Unsupported active-storey objects should not clutter Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        level.addObject(wall)
        level.addObject(box)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(
            box.ViewObject.Visibility,
            "Unsupported active-storey objects should be hidden in Plan Edit.",
        )
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hides_unsupported_objects_outside_active_storey(self):
        """Unsupported objects with no storey ancestry should also be hidden."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(
            box.ViewObject.Visibility,
            "Unsupported objects outside the active storey should be hidden in Plan Edit.",
        )
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_building_visible_but_not_selectable(self):
        """Building containers should stay visible as context, but not intercept selection."""

        building = Arch.makeBuilding(name="TestBuilding")
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        building.addObject(level)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(building.ViewObject.Visibility)
        self.assertFalse(building.ViewObject.Selectable)
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_plain_groups_visible_but_not_selectable(self):
        """Generic group containers should stay visible as context in Plan Edit."""

        group = self.document.addObject("App::DocumentObjectGroup", "TestGroup")
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        group.addObject(level)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(group.ViewObject.Visibility)
        self.assertFalse(getattr(group.ViewObject, "Selectable", False))
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_forces_hosted_doors_visible(self):
        """Hosted doors should become visible in Plan Edit even if the regular 3D view keeps them hidden."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall)
        door.ViewObject.Visibility = False

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Visibility)
        self.assertTrue(door.ViewObject.Selectable)
        self.assertTrue(hasattr(door.ViewObject.Proxy, "lcoords"))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hosted_door_populates_footprint_lines(self):
        """Hosted doors should have committed footprint line data while Plan Edit is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="PlanDoor")
        door.ViewObject.Visibility = False

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = door.ViewObject.Proxy
        self.assertTrue(door.ViewObject.Visibility)
        self.assertTrue(door.ViewObject.Selectable)
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_plan_edit_selecting_hosted_door_does_not_enable_wall_grips(self):
        """Hosted opening selection should not re-enter wall endpoint edit mode."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="SelectableDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Selectable)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)

        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_window_tool_creates_hosted_window_on_selected_wall(self):
        """The Plan Edit Window tool should create a real hosted Arch Window."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        captured = {}
        prehost_window_shapes = []

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_add_components = Arch.addComponents

        def record_add_components(objects, host):
            window = objects[0] if isinstance(objects, list) else objects
            prehost_window_shapes.append(
                bool(
                    getattr(window, "Shape", None)
                    and not window.Shape.isNull()
                    and window.Shape.Solids
                )
            )
            return original_add_components(objects, host)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(Arch, "addComponents", side_effect=record_add_components),
        ):
            self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
            self.assertTrue(session.can_place_plan_window())

            before = {obj.Name for obj in self.document.Objects}
            self.assertTrue(session.activate_window_tool())
            self.assertEqual(session.current_tool, "Window")
            self.assertIs(session._window_host_wall, wall)
            self.assertIn("callback", captured)
            self.assertIn("movecallback", captured)

            point = FreeCAD.Vector(1200, 100, 0)
            captured["movecallback"](point, None)
            self.assertEqual(4, len(session._window_preview_trackers))

            captured["callback"](point, None)

        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        windows = [
            obj
            for obj in created
            if getattr(obj, "IfcType", "") == "Window" and session._is_hosted_opening_object(obj)
        ]
        self.assertEqual(1, len(windows))

        window = windows[0]
        self.assertEqual([True], prehost_window_shapes)
        self.assertIn(wall, window.Hosts)
        self.assertIn(level, window.InListRecursive)
        self.assertAlmostEqual(float(getattr(window.Width, "Value", window.Width)), 900.0)
        self.assertAlmostEqual(float(getattr(window.Height, "Value", window.Height)), 1200.0)
        self.assertAlmostEqual(window.Base.Placement.Base.z, 900.0, delta=1e-6)
        self.assertAlmostEqual(window.Shape.BoundBox.ZMin, 900.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "opening", window)

    def test_plan_edit_window_tool_uses_current_snap_wall_for_host(self):
        """Window placement should follow the wall under the cursor, not stale selection."""

        level = Arch.makeFloor(name="Level 0")
        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        base_b = Draft.makeLine(FreeCAD.Vector(2000, 0, 0), FreeCAD.Vector(2000, 3000, 0))
        wall_b = Arch.makeWall(base_b, width=200, height=2500, name="SnapWall")
        level.addObject(wall_a)
        level.addObject(wall_b)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        captured = {}
        snap_info = {
            "Document": self.document.Name,
            "Object": wall_b.Name,
            "Component": "Face1",
            "SubName": "Face1",
        }

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", snap_info, create=True),
        ):
            self.assertTrue(session._select_wall_for_plan_edit(wall_a, sync_gui_selection=True))
            self.assertTrue(session.activate_window_tool())
            self.assertIs(session._window_host_wall, wall_a)

            before = {obj.Name for obj in self.document.Objects}
            point = FreeCAD.Vector(2100, 1200, 0)
            captured["movecallback"](point, None)
            self.assertIs(session._window_host_wall, wall_b)

            captured["callback"](point, None)

        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        windows = [
            obj
            for obj in created
            if getattr(obj, "IfcType", "") == "Window" and session._is_hosted_opening_object(obj)
        ]
        self.assertEqual(1, len(windows))

        window = windows[0]
        self.assertIn(wall_b, window.Hosts)
        self.assertNotIn(wall_a, window.Hosts)
        self.assertAlmostEqual(window.Base.Placement.Base.x, 2000.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.Placement.Base.y, 1200.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.Placement.Base.z, 900.0, delta=1e-6)

        sketch_x_axis = window.Base.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        self.assertAlmostEqual(abs(sketch_x_axis.x), 0.0, delta=1e-6)
        self.assertAlmostEqual(abs(sketch_x_axis.y), 1.0, delta=1e-6)

    def test_plan_edit_selected_window_status_uses_window_label(self):
        """Hosted windows should be labelled as windows, not generic openings."""

        level, wall, window = self._make_windowed_plan_wall()
        del wall

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, window.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "opening", window)
        self.assertTrue(
            session._format_plan_target_selection_state("opening", window).startswith("Window:")
        )
        self.assertIn("selected window", session._format_opening_selection_help(window))

    def test_plan_edit_ctrl_click_adds_wall_to_selection_without_replacing_primary_target(self):
        """Ctrl-click should build a wall selection set while keeping the current primary wall."""

        from PySide import QtCore

        level = Arch.makeFloor(name="Level 0")
        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        level.addObject(wall_a)
        level.addObject(wall_b)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", wall_a),
            ),
        ):
            session._on_mouse_pressed(self._make_fake_left_mouse_press())

        self._assert_selected_plan_target(session, "wall", wall_a)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall_a.Name])

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session,
                "_get_edit_node",
                return_value=None,
            ),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", wall_b),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self._assert_selected_plan_target(session, "wall", wall_a)
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [wall_a.Name, wall_b.Name],
        )
        self.assertEqual(session._get_selected_plan_target(), ("wall", wall_a))
        self.assertEqual(session._get_secondary_selected_plan_targets(), [("wall", wall_b)])
        self.assertGreater(len(session._secondary_selection_trackers), 0)
        self.assertIn("Selection set: 2 walls", session.task_panel.status.text())

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session,
                "_get_edit_node",
                return_value=None,
            ),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", wall_a),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self._assert_selected_plan_target(session, "wall", wall_b)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall_b.Name])
        self.assertEqual(session._get_selected_plan_target(), ("wall", wall_b))
        self.assertEqual(session._get_secondary_selected_plan_targets(), [])
        self.assertEqual(len(session._secondary_selection_trackers), 0)
        self.assertNotIn("Selection set:", session.task_panel.status.text())

        session.shutdown(close_dialog=False)

        self.pump_gui_events()

    def test_plan_edit_hovered_hosted_door_shows_preselection_overlay(self):
        """Hosted openings should get a hover overlay independent of global preselection."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("opening", door),
        ):
            session._update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session._opening_hover_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

    def test_plan_edit_clicking_hovered_hosted_door_selects_it(self):
        """Clicking a hovered hosted opening should promote it to selected opening state."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClickHoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("opening", door),
        ):
            activated = session._activate_opening_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_real_view_picking_hover_and_click_hosted_door(self):
        """Real view-based hover and click should pick a hosted opening."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="RealPickDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = getattr(door.ViewObject, "Proxy", None)
        self.assertIsNotNone(proxy)
        polylines = list(proxy.get_plan_overlay_polylines() or [])
        self.assertTrue(polylines)
        self.assertGreaterEqual(len(polylines[0]), 2)

        start = polylines[0][0]
        end = polylines[0][1]
        mid = FreeCAD.Vector(
            (start.x + end.x) * 0.5,
            (start.y + end.y) * 0.5,
            (start.z + end.z) * 0.5,
        )
        screen_pos = session.view.getPointOnScreen(mid)
        mouse_pos = (int(screen_pos[0]), int(screen_pos[1]))

        move = self._make_fake_mouse_move_event(*mouse_pos)
        session._on_mouse_moved(move)
        self.pump_gui_events()

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session._opening_hover_trackers), 0)

        move_again = self._make_fake_mouse_move_event(*mouse_pos)
        session._on_mouse_moved(move_again)
        self.pump_gui_events()

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session._opening_hover_trackers), 0)

        press = self._make_fake_left_mouse_press(*mouse_pos)
        session._on_mouse_pressed(press)
        self.pump_gui_events()

        release = self._make_fake_left_mouse_release(*mouse_pos)
        session._on_mouse_pressed(release)
        self.pump_gui_events()

        self.assertTrue(press._handled)
        self.assertTrue(release._handled)
        self.assertFalse(session._consume_left_button_release)
        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_real_view_hovered_wall_shows_preselection_overlay(self):
        """Real view-based hover should pick a wall and keep the warm path cheap."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        faces = list(
            getattr(getattr(wall, "Proxy", None), "getFootprint", lambda _obj: [])(wall) or []
        )
        self.assertTrue(faces)
        face = faces[0]
        point = FreeCAD.Vector(face.CenterOfMass)
        screen_pos = session.view.getPointOnScreen(point)
        mouse_pos = (int(screen_pos[0]), int(screen_pos[1]))

        move = self._make_fake_mouse_move_event(*mouse_pos)
        session._on_mouse_moved(move)
        self.pump_gui_events()

        self.assertIs(session.hovered_wall, wall)
        self.assertGreater(len(session._wall_hover_trackers), 0)

        move_again = self._make_fake_mouse_move_event(*mouse_pos)
        session._on_mouse_moved(move_again)
        self.pump_gui_events()

        self.assertIs(session.hovered_wall, wall)
        self.assertGreater(len(session._wall_hover_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_empty_canvas_click_clears_selected_opening(self):
        """Empty canvas clicks should clear an internally selected opening."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClearRestoreDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with (
            patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("opening", door),
            ),
        ):
            activated = session._activate_opening_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "opening", door)
        restore_calls = [call for call in calls if getattr(call[1], "__name__", "") == "<lambda>"]
        self.assertEqual(len(restore_calls), 1)
        self.assertEqual(restore_calls[0][0], 0)
        self.assertEqual(session._pending_selected_plan_target, ("opening", door))

        restore_calls[0][1]()
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events()

        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_selected_plan_target(session, "opening", door)
        self.assertIsNone(session._pending_selected_plan_target)

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=(None, None),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        self._assert_no_selected_plan_target(session)
        self.assertIsNone(session._pending_selected_plan_target)
        self.assertEqual(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

    def test_plan_edit_empty_canvas_click_clears_selected_wall(self):
        """Transient empty GUI selection should not immediately deselect a clicked wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session._activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(session._pending_selected_plan_target, ("wall", wall))

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events()

        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertIsNone(session._pending_selected_plan_target)

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=(None, None),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        self._assert_no_selected_plan_target(session)
        self.assertIsNone(session._pending_selected_plan_target)
        self.assertEqual(len(session._grip_trackers), 0)

    def test_plan_edit_empty_canvas_click_clears_lingering_storey_gui_selection(self):
        """Select-mode empty clicks should clear the initial storey GUI selection."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [level.Name])

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=(None, None),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_no_selected_plan_target(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_opening_move_uses_reduced_snap_profile(self):
        """Opening move should use a constrained snap profile while point-picking."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="MoveDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        handle = session._get_selected_opening_edit_handles(door)[0]
        captured = {}
        pushed_modes = []
        popped = []

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(
                FreeCADGui.Snapper,
                "push_snap_modes",
                side_effect=lambda modes: pushed_modes.append(set(modes)),
            ),
            patch.object(
                FreeCADGui.Snapper, "pop_snap_modes", side_effect=lambda: popped.append(True)
            ),
        ):
            session._start_opening_handle_point_pick(door, 0, handle)

            self.assertEqual(pushed_modes, [set(BimPlanSession._OPENING_MOVE_SNAP_SET)])
            self.assertEqual(session.current_tool, "Move Opening")
            self.assertIn("callback", captured)
            self.assertIn("movecallback", captured)
            self.assertIn("last", captured)
            self.assertTrue(captured.get("noTracker"))

            captured["callback"](handle.point, None)

        self.assertEqual(len(popped), 1)
        self.assertEqual(session.current_tool, "Select")

    def test_plan_edit_opening_move_clamps_to_host_span(self):
        """Opening move projection should stay within the valid host wall span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClampedDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        far_before = origin.add(FreeCAD.Vector(axis_u).multiply(-100000))
        far_after = origin.add(FreeCAD.Vector(axis_u).multiply(100000))

        projected_before = proxy.project_point_to_host_axis(far_before)
        projected_after = proxy.project_point_to_host_axis(far_after)

        before_u = projected_before.sub(origin).dot(axis_u)
        after_u = projected_after.sub(origin).dot(axis_u)

        self.assertAlmostEqual(before_u, context["move_u_min"], delta=1e-6)
        self.assertAlmostEqual(after_u, context["move_u_max"], delta=1e-6)

    def test_plan_edit_opening_move_anchor_offsets_center_from_edge_alignment(self):
        """Opening move anchors should offset the center from left/right jamb picks."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="AnchoredDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        center_u = (context["move_u_min"] + context["move_u_max"]) * 0.5
        half_width = context["opening_half_width_u"]

        left_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u - half_width))
        right_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u + half_width))

        projected_left = proxy.project_point_to_host_axis(left_edge_point, anchor="left")
        projected_right = proxy.project_point_to_host_axis(right_edge_point, anchor="right")

        projected_left_u = projected_left.sub(origin).dot(axis_u)
        projected_right_u = projected_right.sub(origin).dot(axis_u)

        self.assertAlmostEqual(projected_left_u, center_u, delta=1e-6)
        self.assertAlmostEqual(projected_right_u, center_u, delta=1e-6)

    def test_plan_edit_opening_overlay_stays_within_wall_span_at_limit(self):
        """Hosted opening overlay should stay inside the host wall span at the move limit."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="BoundedSymbolDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        left_limit = context["origin"].add(
            FreeCAD.Vector(context["axis_u"]).multiply(context["move_u_min"])
        )
        left_limit.z = context["base_z"]
        proxy.move_along_host(left_limit)
        self.document.recompute()

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        wall_length = wall_axis_u.Length
        self.assertGreater(wall_length, 0.0)
        wall_axis_u.normalize()

        overlay_us = []
        for polyline in proxy.get_plan_overlay_polylines():
            for point in polyline:
                overlay_us.append(FreeCAD.Vector(point).sub(wall_start).dot(wall_axis_u))

        self.assertTrue(overlay_us)
        self.assertGreaterEqual(min(overlay_us), -1e-6)
        self.assertLessEqual(max(overlay_us), wall_length + 1e-6)

    def test_plan_edit_opening_move_a_cycles_anchor(self):
        """A should cycle opening move anchors while the point-pick is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="TabDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        handle = session._get_selected_opening_edit_handles(door)[0]

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(
                session, "_refresh_opening_move_preview_from_raw_point", return_value=None
            ) as refresh_preview,
        ):
            session._start_opening_handle_point_pick(door, 0, handle)

            from pivy import coin

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session._edit_opening_move_anchor, "left")

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session._edit_opening_move_anchor, "right")

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session._edit_opening_move_anchor, "center")

            self.assertEqual(refresh_preview.call_count, 3)

            session._cancel_opening_handle_point_pick()

    def test_plan_edit_opening_move_updates_input_hints(self):
        """Active opening move should publish placement/cancel/anchor hints."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HintDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        handle = session._get_selected_opening_edit_handles(door)[0]

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.HintManager, "show") as show_hints,
        ):
            session._start_opening_handle_point_pick(door, 0, handle)

        self.assertTrue(show_hints.called)
        hints = show_hints.call_args.args
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0].message, "%1 place opening")
        self.assertEqual(hints[1].message, "%1 cycle move anchor")
        self.assertEqual(hints[2].message, "%1 cancel")

    def test_plan_edit_opening_move_preview_offsets_readout_outside_host_wall(self):
        """Opening move preview readout should sit outside the host wall footprint."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        door = self._make_hosted_door(wall, name="OpeningPreviewOffsetDoor")
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = door.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        preview_point = context["origin"].add(
            FreeCAD.Vector(context["axis_u"]).multiply(context["move_u_max"])
        )
        preview_point.z = context["base_z"]

        session.current_tool = "Move Opening"
        session._edit_opening_move_anchor = "center"
        session._sync_opening_move_preview(door, preview_point)

        dim_trackers = [
            tracker
            for tracker in session._opening_move_preview_trackers
            if hasattr(tracker, "dimnode") and hasattr(tracker, "offset")
        ]
        self.assertEqual(len(dim_trackers), 1)
        self.assertGreater(dim_trackers[0].offset, wall.Width.Value / 2.0)

    def test_plan_edit_hovered_wall_shows_preselection_overlay(self):
        """Walls should get a lightweight hover overlay before actual selection."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            session._update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_wall, wall)
        self.assertIsNone(session.hovered_opening)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 0)

    def test_plan_edit_hovered_wall_shows_hosted_opening_context(self):
        """Hovering a wall should passively highlight its hosted openings."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        self._make_hosted_door(wall, name="HoverWallContextDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            session._update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_wall, wall)
        self._assert_no_selected_plan_target(session)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertGreater(len(session._hovered_wall_opening_context_trackers), 0)
        self.assertEqual(len(session._opening_hover_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

    def test_plan_edit_clicking_hovered_wall_selects_it(self):
        """Clicking a hovered wall should promote it to selected wall state."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session._activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_selected_wall_shows_hosted_opening_context(self):
        """Selecting a wall should highlight hosted openings without selecting them."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="WallContextDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session._activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertGreater(len(session._selected_wall_opening_context_trackers), 0)
        self.assertEqual(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

        session._select_opening_for_plan_edit(door)

        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session._selected_wall_opening_context_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_join_mode_hover_tracks_candidate_wall(self):
        """Join mode should keep a hovered candidate wall visible for joining."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        session.activate_join_tool()

        self.assertEqual(session.current_tool, "Join")
        self._assert_selected_plan_target(session, "wall", source_wall)
        self.assertEqual(len(session._grip_trackers), 0)

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", target_wall),
        ):
            session._update_hovered_plan_target((100, 100))
            session._refresh_plan_overlay_visuals()

        self.assertIs(session.hovered_wall, target_wall)
        self.assertIsNone(session.hovered_opening)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._hovered_wall_opening_context_trackers), 0)

    def test_plan_edit_join_mode_cancel_restores_selected_wall_grips(self):
        """Canceling join mode should return to Select with the source wall active."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        self.assertEqual(len(session._grip_trackers), 3)

        session.activate_join_tool()
        self.assertEqual(session.current_tool, "Join")
        self.assertEqual(len(session._grip_trackers), 0)

        session._cancel_join_tool()

        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", source_wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_join_mode_cycles_join_type_with_tab(self):
        """Join mode should cycle the active join type and reflect it in the UI."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        session.activate_join_tool()

        self.assertEqual(session.get_plan_join_type(), "Miter")
        self.assertEqual(
            session.task_panel.join_type_combo.currentIndex(),
            session.task_panel.join_type_combo.findData("Miter"),
        )

        from pivy import coin

        event_callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
        session._on_key_pressed(event_callback)

        self.assertEqual(session.get_plan_join_type(), "Butt")
        self.assertEqual(
            session.task_panel.join_type_combo.currentIndex(),
            session.task_panel.join_type_combo.findData("Butt"),
        )
        self.assertTrue(event_callback._handled)
        _title, body = session._get_status_chip_text()
        self.assertIn("butt joint", body.lower())
        self.assertIn("Join type: Butt", session.task_panel.status.text())

    def test_plan_edit_join_mode_creates_wall_joint_from_clicked_candidate(self):
        """Join mode should create a BIM wall joint from the selected and clicked walls."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        session.activate_join_tool()

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")
        self.assertEqual(joint.Status, "OK")
        self.assertEqual({joint.WallA, joint.WallB}, {source_wall, target_wall})

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, source_wall)
        self.assertIsNone(session.selected_opening)
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertEqual(len(session._wall_hover_trackers), 0)

    def test_plan_edit_join_mode_uses_selected_join_type_from_dock(self):
        """Join mode should create the join type currently selected in the dock."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        butt_index = session.task_panel.join_type_combo.findData("Butt")
        self.assertGreaterEqual(butt_index, 0)
        session.task_panel.join_type_combo.setCurrentIndex(butt_index)
        self.pump_gui_events()

        self.assertEqual(session.get_plan_join_type(), "Butt")

        session._select_wall_for_plan_edit(source_wall)
        session.activate_join_tool()

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Butt")
        trimmed_wall = joint.WallA if joint.ButtTrimmed == "WallA" else joint.WallB
        self.assertIs(trimmed_wall, target_wall)
        self.assertEqual(joint.Status, "OK")

    def test_plan_edit_join_mode_updates_existing_joint_for_hovered_pair(self):
        """Join mode should surface and update an existing wall joint for the hovered pair."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        session.set_plan_join_type("Butt")
        session.activate_join_tool()
        session._set_hovered_wall(target_wall)

        self.assertTrue(session.task_panel.unjoin_button.isEnabled())
        _title, body = session._get_status_chip_text()
        self.assertIn("Existing joint", body)
        self.assertIn("change it to a butt joint", body.lower())
        self.assertIn("Existing joint", session.task_panel.status.text())

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        self.assertIs(joints[0], joint)
        self.assertEqual(joint.JointType, "Butt")
        self.assertEqual(session.current_tool, "Select")

    def test_plan_edit_join_mode_unjoins_hovered_pair(self):
        """Join mode should remove the existing joint for the hovered wall pair."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        session.activate_join_tool()
        session._set_hovered_wall(target_wall)

        self.assertTrue(session.task_panel.unjoin_button.isEnabled())
        self.assertTrue(session._unjoin_current_plan_wall_pair())
        self.pump_gui_events()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(session.current_tool, "Join")
        self.assertIs(session.selected_wall, source_wall)
        self.assertIs(session.hovered_wall, target_wall)
        self.assertFalse(session.task_panel.unjoin_button.isEnabled())
        _title, body = session._get_status_chip_text()
        self.assertIn("Candidate wall", body)
        self.assertIn("create a miter joint", body.lower())

    def test_plan_edit_selected_wall_shows_junction_node_overlay(self):
        """Selecting a wall in a wall junction should show the junction node overlay."""

        carrier_wall = Arch.makeWall(length=3000, width=200, height=2500)
        carrier_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1500, 0, 0), FreeCAD.Rotation())
        branch_up = Arch.makeWall(length=1500, width=200, height=2500)
        branch_up.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        branch_down = Arch.makeWall(length=1500, width=200, height=2500)
        branch_down.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        junction = Arch.makeWallJunction([carrier_wall, branch_up, branch_down])
        self.document.recompute()
        self.assertEqual(junction.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(carrier_wall)

        self.assertGreater(len(session._junction_node_trackers), 0)

    def test_plan_edit_join_promotes_wall_pair_to_junction(self):
        """Joining a third compatible wall should promote the cluster to a wall junction."""

        carrier_wall = Arch.makeWall(length=3000, width=200, height=2500)
        carrier_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1500, 0, 0), FreeCAD.Rotation())
        branch_up = Arch.makeWall(length=1500, width=200, height=2500)
        branch_up.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        branch_down = Arch.makeWall(length=1500, width=200, height=2500)
        branch_down.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Tee

        joint = Arch.makeWallJoint(branch_up, carrier_wall, "Tee")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Tee()._configure_joint(joint, branch_up, carrier_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(carrier_wall)
        session.activate_join_tool()

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
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", branch_down),
            ),
        ):
            session._on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        junctions = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJunction"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(len(junctions), 1)
        junction = junctions[0]
        self.assertEqual(junction.Status, "OK")
        self.assertEqual(
            {wall.Name for wall in junction.Walls},
            {carrier_wall.Name, branch_up.Name, branch_down.Name},
        )
        self.assertIs(session.selected_wall, carrier_wall)
        self.assertGreater(len(session._junction_node_trackers), 0)

    def test_plan_edit_wall_resize_keeps_relation_status_clear_when_join_stays_resolvable(
        self,
    ):
        """Wall resize should keep relation status clear when the committed join remains valid."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(3000, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        original_endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        new_points = [
            original_endpoints[0],
            original_endpoints[0].add(FreeCAD.Vector(1000, 0, 0)),
        ]

        session._commit_wall_edit_points(source_wall, "End", source_wall.Proxy, new_points)
        self.pump_gui_events()
        self.pump_gui_events()

        self.assertEqual(joint.Status, "OK")
        self.assertIsNone(session._plan_relation_status_message)
        _title, body = session._get_status_chip_text()
        self.assertNotIn("Relation warning", body)
        self.assertNotIn("Relation warning", session.task_panel.status.text())

    def test_plan_edit_joined_wall_preview_uses_trimmed_footprint(self):
        """Wall stretch preview should clip the footprint using active wall joins."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._edit_wall = source_wall
        endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        plain = session._get_preview_footprint(endpoints)
        polylines, warnings = session._get_preview_footprint_polylines(endpoints)

        self.assertEqual(warnings, [])
        self.assertEqual(len(polylines), 1)
        closed_plain = [FreeCAD.Vector(point) for point in plain]
        closed_plain.append(FreeCAD.Vector(plain[0]))
        preview = polylines[0]
        self.assertNotEqual(len(preview), 0)
        self.assertFalse(
            len(preview) == len(closed_plain)
            and all(
                preview_point.distanceToPoint(plain_point) < 1e-6
                for preview_point, plain_point in zip(preview, closed_plain)
            )
        )

    def test_plan_edit_joined_wall_preview_drops_trim_when_span_no_longer_reaches_join(self):
        """Wall stretch preview should fall back to the plain footprint when the edited span no longer reaches the join."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._select_wall_for_plan_edit(source_wall)
        original_endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        session._wall_edit_modal_active = True
        session._edit_wall = source_wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"

        invalid_points = [
            original_endpoints[0],
            original_endpoints[0].add(FreeCAD.Vector(1000, 0, 0)),
        ]
        session._sync_wall_edit_preview(invalid_points)
        self.pump_gui_events()

        self.assertIsNone(session._plan_relation_status_message)
        plain = session._get_preview_footprint(invalid_points)
        polylines, warnings = session._get_preview_footprint_polylines(invalid_points)
        self.assertEqual(warnings, [])
        self.assertEqual(len(polylines), 1)
        closed_plain = [FreeCAD.Vector(point) for point in plain]
        closed_plain.append(FreeCAD.Vector(plain[0]))
        self.assertEqual(len(polylines[0]), len(closed_plain))
        self.assertTrue(
            all(
                preview_point.distanceToPoint(plain_point) < 1e-6
                for preview_point, plain_point in zip(polylines[0], closed_plain)
            )
        )

    def test_plan_edit_wall_grip_move_uses_point_pick_commit(self):
        """Wall grips should use click-move-click editing instead of hold-drag."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(2)

        self.assertEqual(session.current_tool, "Move Wall")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)
        self.assertIn("last", captured)
        self.assertTrue(captured.get("noTracker"))

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)
        self.assertIsNotNone(session._preview_points)
        self.assertNotEqual(session._preview_points, list(original_endpoints))

        captured["callback"](new_midpoint, None)
        self.pump_gui_events()

        moved_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(
            moved_endpoints[0].x - original_endpoints[0].x,
            1000.0,
            delta=1e-6,
        )
        self.assertAlmostEqual(
            moved_endpoints[1].x - original_endpoints[1].x,
            1000.0,
            delta=1e-6,
        )
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_move_escape_cancels_and_keeps_selection(self):
        """Esc should cancel an active wall point-pick edit and restore wall grips."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(2)

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)

        from pivy import coin

        session._on_key_pressed(
            self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.ESCAPE))
        )
        self.pump_gui_events()

        canceled_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(canceled_endpoints[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(canceled_endpoints[1].x, original_endpoints[1].x, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_activation_is_deferred(self):
        """Wall grip activation should defer point-pick start until after the click event unwinds."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session._activate_wall_grip(2)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(session.current_tool, "Select")

        # Late selection clears from the click should not break the deferred grip activation.
        session._set_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            calls[0][1]()

        self.assertEqual(session.current_tool, "Move Wall")
        self._assert_selected_plan_target(session, "wall", wall)

    def test_plan_edit_opening_handle_activation_is_deferred(self):
        """Deferred opening handle activation should survive late selection clears."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="DeferredDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        handle = session._get_selected_opening_edit_handles(door)[0]
        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session._activate_opening_handle(door, 0)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)
        session._set_selected_plan_target()

        if handle.interaction == "point_pick":
            captured = {}

            def fake_get_point(**kwargs):
                captured.update(kwargs)

            with (
                patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
                patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            ):
                calls[0][1]()

            self.assertEqual(session.current_tool, "Move Opening")
            self._assert_selected_plan_target(session, "opening", door)
            self.assertIs(session._edit_opening, door)
            self.assertIn("callback", captured)
        else:
            original_parts = list(door.WindowParts)
            calls[0][1]()
            self._assert_selected_plan_target(session, "opening", door)
            self.assertNotEqual(original_parts, list(door.WindowParts))

    def test_plan_edit_wall_move_preview_shows_delta_readouts(self):
        """Moving a wall should show horizontal and vertical temporary readouts."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints

        moved_points = [
            original_endpoints[0].add(FreeCAD.Vector(500, 250, 0)),
            original_endpoints[1].add(FreeCAD.Vector(500, 250, 0)),
        ]

        session._sync_wall_edit_preview(moved_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 2)
        self.assertTrue(
            all(hasattr(tracker, "dimnode") for tracker in session._wall_edit_readout_trackers)
        )
        self.assertEqual(
            sorted(
                int(tracker.dimnode.datumtype.getValue())
                for tracker in session._wall_edit_readout_trackers
            ),
            [2, 3],
        )
        self.assertTrue(
            all(
                tracker.offset == session._get_wall_edit_readout_offset(tracker.mode)
                for tracker in session._wall_edit_readout_trackers
            )
        )
        self.assertTrue(
            all(tracker.offset >= 100.0 for tracker in session._wall_edit_readout_trackers)
        )

    def test_plan_edit_wall_stretch_preview_shows_length_readout(self):
        """Stretching a wall endpoint should show one aligned temporary length readout."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"

        stretched_points = [
            original_endpoints[0],
            original_endpoints[1].add(FreeCAD.Vector(800, 0, 0)),
        ]

        session._sync_wall_edit_preview(stretched_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 1)
        tracker = session._wall_edit_readout_trackers[0]
        self.assertTrue(hasattr(tracker, "label"))
        self.assertTrue(hasattr(tracker, "startEdit"))
        self.assertEqual(tracker.mode, 1)
        self.assertGreater(tracker.offset, wall.Width.Value / 2.0)

    def test_plan_edit_readout_offset_grows_when_zoomed_out(self):
        """Aligned readout offsets should grow when the same wall is viewed farther out."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(session, "_get_plan_view_units_per_pixel", return_value=1.0):
            close_offset = session._get_aligned_readout_offset_for_wall(wall)

        with patch.object(session, "_get_plan_view_units_per_pixel", return_value=40.0):
            far_offset = session._get_aligned_readout_offset_for_wall(wall)

        self.assertGreater(far_offset, close_offset)

    def test_plan_edit_disables_locked_view_actions(self):
        """Plan Edit should disable and later restore standard view orientation actions."""

        from PySide import QtGui

        session = BimPlanSession.PlanEditSession()
        main_window = QtGui.QWidget()

        initially_enabled = QtGui.QAction(main_window)
        initially_enabled.setObjectName("Std_ViewFront")
        initially_enabled.setEnabled(True)

        initially_disabled = QtGui.QAction(main_window)
        initially_disabled.setObjectName("Std_PerspectiveCamera")
        initially_disabled.setEnabled(False)

        with patch.object(FreeCADGui, "getMainWindow", return_value=main_window):
            session._apply_locked_view_actions()
            self.assertFalse(initially_enabled.isEnabled())
            self.assertFalse(initially_disabled.isEnabled())

            session._restore_locked_view_actions()
            self.assertTrue(initially_enabled.isEnabled())
            self.assertFalse(initially_disabled.isEnabled())

    def test_plan_edit_applies_orientation_lock_to_navigation_style(self):
        """Plan Edit should lock and later restore view orientation at the navigation layer."""

        class FakeNavigationStyle:
            def __init__(self):
                self.rotation_enabled = True
                self.orientation_locked = False

            def isRotationEnabled(self):
                return self.rotation_enabled

            def setRotationEnabled(self, enabled):
                self.rotation_enabled = enabled

            def isOrientationLocked(self):
                return self.orientation_locked

            def setOrientationLocked(self, enabled):
                self.orientation_locked = enabled

        class FakeViewer:
            def __init__(self):
                self.navicube_enabled = True
                self.navicube_override = None

            def isEnabledNaviCube(self):
                return self.navicube_enabled

            def setEnabledNaviCube(self, enabled):
                self.navicube_enabled = enabled

            def setNaviCubeEnabledOverride(self, enabled):
                self.navicube_override = enabled

            def clearNaviCubeEnabledOverride(self):
                self.navicube_override = None

        class FakeView:
            def __init__(self):
                self.corner_cross_visible = True

            def isCornerCrossVisible(self):
                return self.corner_cross_visible

            def setCornerCrossVisible(self, enabled):
                self.corner_cross_visible = enabled

        session = BimPlanSession.PlanEditSession()
        nav_style = FakeNavigationStyle()
        viewer = FakeViewer()
        view = FakeView()
        session.viewer = viewer
        session.view = view

        with patch.object(session, "_get_navigation_style", return_value=nav_style):
            session._apply_plan_navigation_profile()
            self.assertFalse(nav_style.rotation_enabled)
            self.assertTrue(nav_style.orientation_locked)
            self.assertFalse(viewer.navicube_override)
            self.assertFalse(view.corner_cross_visible)

            session._restore_navigation_state()
            self.assertTrue(nav_style.rotation_enabled)
            self.assertFalse(nav_style.orientation_locked)
            self.assertIsNone(viewer.navicube_override)
            self.assertTrue(view.corner_cross_visible)

    def test_plan_edit_ignores_deleted_view_wrappers_in_overlay_scaling(self):
        """Overlay scaling should fall back cleanly when the underlying Qt view was deleted."""

        class DeletedView:
            def __getattribute__(self, name):
                if name in ("getCameraNode", "getSize", "redraw"):
                    raise RuntimeError(f"Cannot access attribute '{name}' of deleted object")
                return object.__getattribute__(self, name)

        session = BimPlanSession.PlanEditSession()
        session.view = DeletedView()
        session.viewer = object()

        self.assertIsNone(session._get_plan_view_height())
        self.assertIsNone(session.view)
        self.assertIsNone(session.viewer)
        self.assertEqual(session._scaled_line_width(3), 3.0)

    def test_plan_edit_uses_viewer_background_override_api(self):
        """Plan Edit should use the viewer override API for its paper background."""

        class FakeViewer:
            def __init__(self):
                self.calls = []

            def setBackgroundAppearanceOverride(self, mode, background, from_color, to_color):
                self.calls.append(("set", mode, background, from_color, to_color))

            def clearBackgroundAppearanceOverride(self):
                self.calls.append(("clear",))

        session = BimPlanSession.PlanEditSession()
        session.viewer = FakeViewer()

        session._apply_plan_background_override()
        self.assertEqual(
            session.viewer.calls[0],
            (
                "set",
                "NONE",
                BimPlanSession._PLAN_PAPER_RGB,
                BimPlanSession._PLAN_PAPER_RGB,
                BimPlanSession._PLAN_PAPER_RGB,
            ),
        )

        session._clear_plan_background_override()
        self.assertEqual(session.viewer.calls[1], ("clear",))

    def test_plan_edit_session_hides_navicube_and_restores_it_on_exit(self):
        """Plan Edit should hide the live viewer NaviCube and restore it on exit."""

        view = FreeCADGui.ActiveDocument.ActiveView
        viewer = view.getViewer()

        original_navicube = viewer.isEnabledNaviCube()
        original_corner_cross = view.isCornerCrossVisible()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertFalse(viewer.isEnabledNaviCube())
        self.assertFalse(view.isCornerCrossVisible())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

        self.assertEqual(viewer.isEnabledNaviCube(), original_navicube)
        self.assertEqual(view.isCornerCrossVisible(), original_corner_cross)

    def test_plan_edit_keeps_paper_background_when_view_preferences_change(self):
        """Plan Edit should keep its paper override while view preferences change."""

        def _pack_rgb(r, g, b):
            return (r << 24) | (g << 16) | (b << 8) | 0xFF

        def _rgb_tuple(color):
            return tuple(round(component, 6) for component in color)

        view = FreeCADGui.ActiveDocument.ActiveView
        viewer = view.getViewer()
        view_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")

        original_show_navicube = view_params.GetBool("ShowNaviCube", True)
        original_background = view_params.GetUnsigned("BackgroundColor", 3940932863)

        updated_show_navicube = not original_show_navicube
        updated_background = _pack_rgb(12, 34, 56)
        updated_background_rgb = _rgb_tuple((12 / 255.0, 34 / 255.0, 56 / 255.0))

        session = None
        try:
            session = BimPlanSession.start_session()
            self.assertIsNotNone(session)
            self.pump_gui_events()

            self.assertEqual(viewer.getGradientBackground(), "NONE")
            self.assertEqual(
                _rgb_tuple(viewer.getBackgroundColor()), _rgb_tuple(BimPlanSession._PLAN_PAPER_RGB)
            )
            self.assertFalse(viewer.isEnabledNaviCube())

            view_params.SetBool("ShowNaviCube", updated_show_navicube)
            view_params.SetUnsigned("BackgroundColor", updated_background)
            self.pump_gui_events()

            self.assertEqual(viewer.getGradientBackground(), "NONE")
            self.assertEqual(
                _rgb_tuple(viewer.getBackgroundColor()), _rgb_tuple(BimPlanSession._PLAN_PAPER_RGB)
            )
            self.assertFalse(viewer.isEnabledNaviCube())

            session.shutdown(close_dialog=False)
            session = None
            self.pump_gui_events()

            self.assertEqual(viewer.isEnabledNaviCube(), updated_show_navicube)
            self.assertEqual(_rgb_tuple(viewer.getBackgroundColor()), updated_background_rgb)
        finally:
            if session is not None:
                session.shutdown(close_dialog=False)
                self.pump_gui_events()
            view_params.SetBool("ShowNaviCube", original_show_navicube)
            view_params.SetUnsigned("BackgroundColor", original_background)
            self.pump_gui_events()

    def test_plan_edit_wall_stretch_enter_starts_length_edit(self):
        """Enter should activate in-view length editing for a wall stretch preview."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(1)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.RETURN))
        session._on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_move_enter_starts_offset_edit(self):
        """Enter should activate in-view offset editing for a wall move preview."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(2)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.RETURN))
        session._on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertEqual(len(session._wall_edit_readout_trackers), 2)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertEqual(session._wall_edit_active_readout_tracker.mode, 2)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_move_tab_cycles_active_offset_axis(self):
        """Tab should cycle the active in-view move offset between X and Y."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(2)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
        session._on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertEqual(session._wall_edit_active_readout_tracker.mode, 3)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_stretch_length_edit_updates_preview(self):
        """Numeric wall stretch edits should drive the preview without rebuilding the label."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"
        session._sync_wall_edit_preview(list(original_endpoints))

        tracker = session._wall_edit_active_readout_tracker
        self.assertIsNotNone(tracker)

        session._on_wall_stretch_length_changed(4200.0)

        self.assertIs(session._wall_edit_active_readout_tracker, tracker)
        self.assertAlmostEqual(session._preview_points[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(
            session._preview_points[1].x, original_endpoints[0].x + 4200.0, delta=1e-6
        )

    def test_plan_edit_wall_move_offset_edit_updates_preview(self):
        """Numeric wall move edits should drive the preview without rebuilding the labels."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Move Wall"
        session._sync_wall_edit_preview(list(original_endpoints))

        tracker = session._wall_edit_active_readout_tracker
        self.assertIsNotNone(tracker)
        self.assertEqual(tracker.mode, 2)

        session._on_wall_move_delta_changed(2, 500.0)

        self.assertIs(session._wall_edit_active_readout_tracker, tracker)
        self.assertAlmostEqual(
            session._preview_points[0].x, original_endpoints[0].x + 500.0, delta=1e-6
        )
        self.assertAlmostEqual(
            session._preview_points[1].x, original_endpoints[1].x + 500.0, delta=1e-6
        )

    def test_plan_edit_wall_move_offset_edit_commits_wall(self):
        """Accepting a typed wall move offset should commit the translated wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Move Wall"
        session._sync_wall_edit_preview(list(original_endpoints))

        session._on_wall_move_delta_finished(2, 500.0)
        self.pump_gui_events()

        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(endpoints[0].x, original_endpoints[0].x + 500.0, delta=1e-6)
        self.assertAlmostEqual(endpoints[1].x, original_endpoints[1].x + 500.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, wall)

    def test_plan_edit_wall_stretch_length_edit_commits_wall(self):
        """Accepting a typed wall stretch length should commit the resized wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(1)

        session._on_wall_stretch_length_finished(4200.0)
        self.pump_gui_events()

        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(endpoints[1].sub(endpoints[0]).Length, 4200.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, wall)

    def test_plan_edit_wall_edit_refreshes_hosted_opening_footprints(self):
        """Wall edits should refresh footprints for openings hosted by that wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="WallEditDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(session, "_refresh_opening_footprint_display") as refresh_opening,
        ):
            session._start_wall_grip_edit(2)
            new_midpoint = captured["last"].add(FreeCAD.Vector(400, 0, 0))
            captured["callback"](new_midpoint, None)

        refresh_opening.assert_any_call(door)

    def test_plan_edit_wall_stretch_clamps_hosted_opening_inside_wall(self):
        """Shortening a wall should move hosted openings back inside the valid span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="ClampAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        updated_context = door_proxy.get_plan_move_context()
        current_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(current_center)
        current_center_u = (
            FreeCAD.Vector(current_center)
            .sub(updated_context["origin"])
            .dot(updated_context["axis_u"])
        )
        self.assertAlmostEqual(current_center_u, updated_context["move_u_max"], delta=1e-6)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)

    def test_plan_edit_wall_stretch_preview_shows_repositioned_opening_overlay(self):
        """Stretch preview should show hosted openings in their predicted post-resize position."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="PreviewStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(rightmost))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session._wall_edit_opening_clearances = session._snapshot_wall_hosted_opening_clearances(
            wall, original_endpoints
        )
        session.current_tool = "Stretch End"

        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_points = [
            original_endpoints[0],
            original_endpoints[0].add(axis.multiply(1600.0)),
        ]

        layout = session._compute_wall_hosted_opening_layout(wall, shortened_points)
        self.assertIsNotNone(layout)
        item = next(candidate for candidate in layout if candidate["opening"] is door)
        delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
        self.assertGreater(delta.Length, 1e-6)

        original_polylines = session._get_opening_overlay_polylines(door)
        self.assertTrue(original_polylines)
        first_polyline = next(polyline for polyline in original_polylines if len(polyline) >= 2)

        session._sync_wall_edit_preview(shortened_points)

        expected_segment_count = sum(
            max(len(polyline) - 1, 0) for polyline in original_polylines if len(polyline) >= 2
        )
        self.assertEqual(
            len(session._wall_edit_opening_preview_trackers),
            expected_segment_count,
        )

        tracker = session._wall_edit_opening_preview_trackers[0]
        expected_start = FreeCAD.Vector(first_polyline[0]).add(delta)
        expected_end = FreeCAD.Vector(first_polyline[1]).add(delta)
        self.assertLess(tracker.p1().distanceToPoint(expected_start), 1e-6)
        self.assertLess(tracker.p2().distanceToPoint(expected_end), 1e-6)

    def test_plan_edit_wall_stretch_preserves_opening_edge_clearance(self):
        """Stretching a wall endpoint should preserve existing opening edge clearance when possible."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="PreserveEdgeClearanceDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        target_center_u = 750.0
        target_point = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(target_center_u)
        )
        target_point.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(target_point))
        self.document.recompute()

        initial_context = door_proxy.get_plan_move_context()
        initial_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(initial_center)
        initial_center_u = (
            FreeCAD.Vector(initial_center)
            .sub(initial_context["origin"])
            .dot(initial_context["axis_u"])
        )
        initial_left_clearance = initial_center_u - initial_context["opening_half_width_u"]
        self.assertAlmostEqual(initial_left_clearance, 300.0, delta=1e-6)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        new_start = FreeCAD.Vector(original_endpoints[0]).add(FreeCAD.Vector(200.0, 0.0, 0.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(0)
            captured["callback"](new_start, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_axis_u = FreeCAD.Vector(wall_end).sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        updated_context = door_proxy.get_plan_move_context()
        updated_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(updated_center)
        updated_center_u = FreeCAD.Vector(updated_center).sub(wall_start).dot(wall_axis_u)
        updated_left_clearance = updated_center_u - updated_context["opening_half_width_u"]
        self.assertAlmostEqual(updated_left_clearance, initial_left_clearance, delta=1e-6)

    def test_plan_edit_wall_stretch_keeps_opening_symbol_centered_on_slot(self):
        """Hosted opening symbols should stay centered on the actual slot after wall resize."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="CenteredAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session._start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        actual_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(actual_center)
        actual_center_u = FreeCAD.Vector(actual_center).sub(wall_start).dot(wall_axis_u)
        actual_context = door_proxy.get_plan_move_context()
        self.assertIsNotNone(actual_context)

        overlay_polylines = door_proxy.get_plan_overlay_polylines()
        self.assertTrue(overlay_polylines)
        centerline = overlay_polylines[-1]
        self.assertEqual(len(centerline), 2)
        symbol_center = FreeCAD.Vector(centerline[0]).add(centerline[1]).multiply(0.5)
        symbol_center_u = symbol_center.sub(wall_start).dot(wall_axis_u)

        self.assertAlmostEqual(symbol_center_u, actual_center_u, delta=1e-6)

        wall_faces = wall.Proxy.getFootprint(wall)
        self.assertTrue(wall_faces)

        def get_u_bounds(face):
            u_values = []
            for wire in face.Wires:
                for vertex in wire.Vertexes:
                    u_values.append(vertex.Point.sub(wall_start).dot(wall_axis_u))
            return min(u_values), max(u_values)

        wall_bounds = sorted((get_u_bounds(face) for face in wall_faces), key=lambda item: item[0])
        left_jamb_u = actual_center_u - actual_context["opening_half_width_u"]
        right_jamb_u = actual_center_u + actual_context["opening_half_width_u"]

        if len(wall_bounds) == 2:
            gap_center_u = (wall_bounds[0][1] + wall_bounds[1][0]) * 0.5
            gap_width = wall_bounds[1][0] - wall_bounds[0][1]
            self.assertAlmostEqual(gap_center_u, actual_center_u, delta=1e-6)
            self.assertAlmostEqual(
                gap_width, actual_context["opening_half_width_u"] * 2.0, delta=1e-6
            )
            return

        self.assertEqual(len(wall_bounds), 1)
        single_min_u, single_max_u = wall_bounds[0]
        flush_start = (
            abs(single_min_u - right_jamb_u) < 1e-6 and abs(single_max_u - wall_length) < 1e-6
        )
        flush_end = abs(single_min_u) < 1e-6 and abs(single_max_u - left_jamb_u) < 1e-6
        self.assertTrue(flush_start or flush_end)

    def test_plan_edit_can_flip_selected_door_hinge(self):
        """Selected door handles should expose hinge flipping in Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="FlipDoor")
        original_parts = list(door.WindowParts)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        session._activate_opening_handle(door, 1)
        self.pump_gui_events()

        self.assertNotEqual(original_parts, list(door.WindowParts))

    def test_plan_edit_selects_existing_space(self):
        """Plan Edit should treat Arch Spaces as first-class selectable targets."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "PlanEditSpaceBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, space.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "space", space)
        self.assertGreater(len(session._space_overlay_trackers), 0)
        self.assertIn("Space: Bedroom", session.task_panel.status.text())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selects_existing_region(self):
        """Plan Edit should treat plan regions as first-class selectable targets."""

        level = Arch.makeFloor(name="Level 0")
        region = self._make_plan_region(level)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, region.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "region", region)
        self.assertGreater(len(session._region_overlay_trackers), 0)
        self.assertIn("Region: Kitchen Zone", session.task_panel.status.text())
        self.assertIs(session.view.getActiveObject("Arch"), region)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_spaces_and_regions_are_custom_pick_only(self):
        """Spaces and plan regions should use session-owned picking, not native 3D selection."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "CustomPickSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        region = self._make_plan_region(level, parent_space=space, label="Kitchen Area")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(space.ViewObject.Visibility)
        self.assertFalse(
            space.ViewObject.Selectable,
            "Spaces should be selected through Plan Edit, not native face picking.",
        )
        self.assertTrue(region.ViewObject.Visibility)
        self.assertFalse(
            region.ViewObject.Selectable,
            "Plan regions should be selected through Plan Edit, not native face picking.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

        self.assertTrue(space.ViewObject.Selectable)
        self.assertTrue(region.ViewObject.Selectable)

    def test_plan_edit_primary_selection_state_tracks_compat_properties(self):
        """Legacy selected_* properties should mirror one primary plan target state."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "SelectionCompatSpaceBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        region = self._make_plan_region(level)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selected_region = region
        self.assertEqual(session._get_selected_plan_target(), ("region", region))
        self.assertEqual(session._get_selected_plan_target_state(), ("region", region))
        self.assertIs(session.selected_region, region)
        self.assertIsNone(session.selected_space)
        self.assertIsNone(session.selected_wall)

        session.selected_space = space
        self.assertEqual(session._get_selected_plan_target(), ("space", space))
        self.assertEqual(session._get_selected_plan_target_state(), ("space", space))
        self.assertIs(session.selected_space, space)
        self.assertIsNone(session.selected_region)

        session.selected_region = None
        self.assertEqual(session._get_selected_plan_target(), ("space", space))
        self.assertIs(session.selected_space, space)

        session.selected_space = None
        self.assertEqual(session._get_selected_plan_target(), (None, None))
        self.assertEqual(session._get_selected_plan_target_state(), (None, None))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_region_populates_selection_ex(self):
        """Clicked region selection should create a real SelectionEx entry for property view."""

        level = Arch.makeFloor(name="Level 0")
        region = self._make_plan_region(level)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("region", region),
        ):
            activated = session._activate_region_target((100, 100))

        self.assertTrue(activated)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [region.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, region.Name)
        self.assertIs(session.view.getActiveObject("Arch"), region)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_space_resolves_target_once_per_press(self):
        """A semantic click should resolve the plan target once, then reuse that result."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "SingleResolveSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("space", space),
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session._on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 1)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "space", space)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [space.Name])
        self.assertIs(session.view.getActiveObject("Arch"), space)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_hovered_wall_reuses_hover_target_without_repick(self):
        """A hovered wall click should promote the hovered target without another pick pass."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._set_hovered_wall(wall)
        self.assertIs(session.hovered_wall, wall)

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session._on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 0)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self.pump_gui_events()
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall.Name])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_click_after_skipped_hover_repicks_target(self):
        """A throttled hover must not let a stale hovered wall steal the click."""

        stale_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 1000, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._set_hovered_wall(stale_wall)
        session._hover_pick_dirty = True

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", target_wall),
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session._on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 1)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", target_wall)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self.pump_gui_events()
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [target_wall.Name],
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_mouse_wheel_queues_view_scale_refresh(self):
        """Zoom events should queue the dedicated debounced view-scale refresh path."""

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "_queue_plan_overlay_view_scale_refresh",
                wraps=session._queue_plan_overlay_view_scale_refresh,
            ) as queue_scale,
            patch.object(
                session,
                "_queue_plan_overlay_visual_refresh",
                wraps=session._queue_plan_overlay_visual_refresh,
            ) as queue_visual,
        ):
            session._on_mouse_wheel(self._make_fake_mouse_wheel_event())

        self.assertEqual(queue_scale.call_count, 1)
        self.assertEqual(queue_visual.call_count, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selecting_wall_uses_lightweight_task_panel_refresh(self):
        """Wall selection should update the task panel without a full widget rebuild."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session.task_panel,
                "refresh_from_session",
                wraps=session.task_panel.refresh_from_session,
            ) as refresh_full,
            patch.object(
                session.task_panel,
                "refresh_selection_from_session",
                wraps=session.task_panel.refresh_selection_from_session,
            ) as refresh_selection,
        ):
            self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))

        self.assertEqual(refresh_full.call_count, 0)
        self.assertEqual(refresh_selection.call_count, 1)
        self._assert_selected_plan_target(session, "wall", wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_zoom_refresh_keeps_selected_space_overlay_geometry_cache(self):
        """Zoom-style view-scale refreshes should reuse cached selected-space geometry."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "ZoomSpaceOverlayBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="ZoomSpace")
        level.addObject(space)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session._select_space_for_plan_edit(space, sync_gui_selection=True))
        with patch.object(
            session,
            "_get_plan_view_height",
            return_value=5000.0,
        ):
            session._sync_selected_space_overlay()
        self.assertFalse(session._selected_space_overlay_dirty)

        with (
            patch.object(
                session,
                "_get_space_overlay_segments",
                wraps=session._get_space_overlay_segments,
            ) as get_segments,
            patch.object(
                session,
                "_get_plan_view_height",
                return_value=20000.0,
            ),
        ):
            session._refresh_plan_overlay_visuals({BimPlanSession._PLAN_VISUAL_VIEW_SCALE})

        self.assertEqual(get_segments.call_count, 0)
        self.assertFalse(session._selected_space_overlay_dirty)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_switching_selected_walls_reuses_grip_trackers(self):
        """Switching walls should retarget the existing grip trackers instead of recreating them."""

        level, walls = self._make_plan_room_walls()
        wall_a, wall_b = walls[:2]
        self.assertIsNotNone(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session._select_wall_for_plan_edit(wall_a, sync_gui_selection=True))
        original_trackers = tuple(session._grip_trackers)
        self.assertEqual(len(original_trackers), 3)

        self.assertTrue(session._select_wall_for_plan_edit(wall_b, sync_gui_selection=True))
        self.assertEqual(len(session._grip_trackers), 3)
        for current, original in zip(session._grip_trackers, original_trackers):
            self.assertIs(current, original)
            self.assertEqual(str(current.selnode.objectName.getValue()), wall_b.Name)

        self._assert_selected_plan_target(session, "wall", wall_b)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_mouse_move_resyncs_selected_wall_grips(self):
        """Mouse moves should resync the active wall grips instead of leaving stale overlays."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
        self.assertEqual(len(session._grip_trackers), 3)

        expected_positions = tuple(
            (
                round(float(position.x), 6),
                round(float(position.y), 6),
                round(float(position.z), 6),
            )
            for position in wall.Proxy.calc_edit_grip_positions(wall)
        )

        bogus_positions = (
            FreeCAD.Vector(1111, 2222, 0),
            FreeCAD.Vector(3333, 4444, 0),
            FreeCAD.Vector(5555, 6666, 0),
        )
        for tracker, bogus in zip(session._grip_trackers, bogus_positions):
            tracker.set(bogus)

        current_positions = tuple(
            (
                round(float(tracker.position.x), 6),
                round(float(tracker.position.y), 6),
                round(float(tracker.position.z), 6),
            )
            for tracker in session._grip_trackers
        )
        self.assertNotEqual(current_positions, expected_positions)

        with patch.object(session, "_get_plan_target_at_position", return_value=(None, None)):
            session._on_mouse_moved(self._make_fake_mouse_move_event(10, 10))
        self.pump_gui_events()

        refreshed_positions = tuple(
            (
                round(float(tracker.position.x), 6),
                round(float(tracker.position.y), 6),
                round(float(tracker.position.z), 6),
            )
            for tracker in session._grip_trackers
        )
        self.assertEqual(refreshed_positions, expected_positions)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clearing_wall_grips_removes_edit_trackers_from_scenegraph(self):
        """Clearing a selected wall should remove the live editTracker nodes from the scenegraph."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        baseline = self._count_scenegraph_named_switches(session, "editTracker")

        self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))
        self.pump_gui_events()

        self.assertEqual(len(session._grip_trackers), 3)
        self.assertEqual(
            self._count_scenegraph_named_switches(session, "editTracker"),
            baseline + 3,
        )

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        self.pump_gui_events(timeout_ms=400)

        self.assertEqual(len(session._grip_trackers), 0)
        self._assert_no_selected_plan_target(session)
        self.assertEqual(
            self._count_scenegraph_named_switches(session, "editTracker"),
            baseline,
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_edit_tracker_finalized_before_insert_does_not_leak_scenegraph_node(self):
        """Finalizing an edit tracker before the delayed insert runs must not leak an orphan node."""

        import draftguitools.gui_trackers as DraftTrackers

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        baseline = self._count_scenegraph_named_switches(session, "editTracker")

        tracker = DraftTrackers.editTracker(
            pos=FreeCAD.Vector(1000, 1000, 0),
            name=wall.Name,
            idx=0,
        )
        tracker.finalize()
        self.pump_gui_events(timeout_ms=400)

        self.assertEqual(
            self._count_scenegraph_named_switches(session, "editTracker"),
            baseline,
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selecting_space_refreshes_only_changed_selected_overlays(self):
        """Switching semantic selection to a space should avoid unrelated selected-overlay refreshes."""

        level, walls = self._make_plan_room_walls()
        wall = walls[0]
        base = self.document.addObject("Part::Box", "SemanticSelectSpaceBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session._select_wall_for_plan_edit(wall, sync_gui_selection=True))

        with (
            patch.object(
                session,
                "_sync_selected_opening_overlay",
                wraps=session._sync_selected_opening_overlay,
            ) as sync_opening,
            patch.object(
                session,
                "_sync_selected_symbol_overlay",
                wraps=session._sync_selected_symbol_overlay,
            ) as sync_symbol,
            patch.object(
                session,
                "_sync_selected_region_overlay",
                wraps=session._sync_selected_region_overlay,
            ) as sync_region,
            patch.object(
                session,
                "_sync_selected_space_overlay",
                wraps=session._sync_selected_space_overlay,
            ) as sync_space,
            patch.object(
                session,
                "_sync_secondary_selected_overlays",
                wraps=session._sync_secondary_selected_overlays,
            ) as sync_secondary,
            patch.object(
                session,
                "_refresh_task_panel_status",
                wraps=session._refresh_task_panel_status,
            ) as refresh_panel,
        ):
            self.assertTrue(session._select_space_for_plan_edit(space, sync_gui_selection=True))

        self.assertEqual(sync_opening.call_count, 0)
        self.assertEqual(sync_symbol.call_count, 0)
        self.assertEqual(sync_region.call_count, 0)
        self.assertEqual(sync_space.call_count, 1)
        self.assertEqual(sync_secondary.call_count, 1)
        self.assertEqual(refresh_panel.call_count, 1)
        self._assert_selected_plan_target(session, "space", space)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [space.Name])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_editor_refresh_skips_unchanged_rebuilds(self):
        """Repeated panel refreshes should not rebuild unchanged space editor controls."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "CachedSpaceEditorBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, space.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        panel = session.task_panel
        self.assertIsNotNone(panel)
        panel._space_editor_label_state = None
        panel._space_editor_combo_state = None
        panel._space_editor_boundary_state = None

        with (
            patch.object(
                panel,
                "_set_space_type_combo_options",
                wraps=panel._set_space_type_combo_options,
            ) as set_options,
            patch.object(
                session,
                "_get_space_boundary_entries",
                wraps=session._get_space_boundary_entries,
            ) as get_boundary_entries,
        ):
            panel.refresh_from_session()
            panel.refresh_from_session()

        self.assertEqual(set_options.call_count, 1)
        self.assertEqual(get_boundary_entries.call_count, 1)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_space_overlay_sync_skips_unchanged_rebuilds(self):
        """Repeated selected-space overlay syncs should reuse cached state until invalidated."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "CachedSpaceOverlayBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._set_selected_plan_target_state("space", space)
        session._clear_selected_space_overlay()

        with patch.object(
            session,
            "_get_space_overlay_segments",
            wraps=session._get_space_overlay_segments,
        ) as get_segments:
            session._sync_selected_space_overlay()
            session._sync_selected_space_overlay()
            session._invalidate_selected_space_overlay_cache()
            session._sync_selected_space_overlay()

        self.assertEqual(get_segments.call_count, 2)
        self.assertGreater(len(session._space_overlay_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_opening_overlay_sync_skips_unchanged_rebuilds(self):
        """Repeated selected-opening overlay syncs should reuse cached state until invalidated."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="CachedOpeningOverlayDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        session._clear_selected_opening_overlay()

        with patch.object(
            session,
            "_get_opening_overlay_segments",
            wraps=session._get_opening_overlay_segments,
        ) as get_segments:
            session._sync_selected_opening_overlay()
            session._sync_selected_opening_overlay()
            session._invalidate_plan_overlay_geometry_cache(door)
            session._sync_selected_opening_overlay()

        self.assertEqual(get_segments.call_count, 2)
        self.assertGreater(len(session._opening_overlay_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_opening_handle_sync_skips_unchanged_rebuilds(self):
        """Repeated selected-opening handle syncs should keep the existing trackers."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="CachedOpeningHandleDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        session._clear_selected_opening_handles()

        session._sync_selected_opening_handles()
        original_trackers = tuple(session._opening_handle_trackers)
        self.assertGreater(len(original_trackers), 0)

        session._sync_selected_opening_handles()
        for current, original in zip(session._opening_handle_trackers, original_trackers):
            self.assertIs(current, original)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_overlay_geometry_cache_reuses_footprint_until_invalidated(self):
        """Space overlay geometry should reuse cached footprint data until invalidated."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "CachedSpaceGeometryBase")
        base.Length = 3200
        base.Width = 2400
        base.Height = 2500
        space = Arch.makeSpace(base, name="Bedroom")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_footprint_overlay_polylines",
            wraps=session._get_footprint_overlay_polylines,
        ) as get_polylines:
            first = tuple(session._get_space_overlay_segments(space))
            second = tuple(session._get_space_overlay_segments(space))
            session._invalidate_plan_overlay_geometry_cache(space)
            third = tuple(session._get_space_overlay_segments(space))

        self.assertEqual(get_polylines.call_count, 2)
        self.assertEqual(first, second)
        self.assertEqual(second, third)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_click_cycle_keeps_region_selected_over_parent_space(self):
        """Region click handling should keep the region as the semantic target across press/release."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "ClickCycleParentSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        region = self._make_plan_region(level, parent_space=space, label="Kitchen Area")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertFalse(space.ViewObject.Selectable)
        self.assertFalse(region.ViewObject.Selectable)

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("region", region),
            ),
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session._on_mouse_pressed(press)
            release = self._make_fake_left_mouse_release(250, 250)
            session._on_mouse_pressed(release)

        self.assertTrue(press._handled)
        self.assertTrue(release._handled)
        self.assertFalse(session._consume_left_button_release)
        self._assert_selected_plan_target(session, "region", region)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [region.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, region.Name)
        self.assertIs(session.view.getActiveObject("Arch"), region)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_opening_populates_selection_ex(self):
        """Clicked opening selection should create a real SelectionEx entry for property view."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="SelectionDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("opening", door),
        ):
            activated = session._activate_opening_target((100, 100))

        self.assertTrue(activated)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_opening_handle_populates_selection_ex(self):
        """Opening handle clicks should also create a real SelectionEx entry."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="HandleSelectionDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "_get_edit_node",
                return_value=("opening_handle", door, 0),
            ),
            patch.object(session, "_activate_opening_handle") as activate_handle,
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        activate_handle.assert_called_once_with(door, 0)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_opening_edit_node_populates_selection_ex(self):
        """Opening edit-node hits should populate property-view selection before handle activation."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="EditNodeSelectionDoor")

        class _FakeField:
            def __init__(self, value):
                self._value = value

            def getValue(self):
                return self._value

        class _FakePickedPoint:
            def __init__(self, document_name, object_name, sub_element_name):
                self.documentName = _FakeField(document_name)
                self.objectName = _FakeField(object_name)
                self.subElementName = _FakeField(sub_element_name)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        picked_point = _FakePickedPoint(self.document.Name, door.Name, "EditNode0")
        with (
            patch.object(
                session,
                "_get_edit_node",
                return_value=("edit_node", picked_point),
            ),
            patch.object(session, "_activate_opening_handle") as activate_handle,
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        activate_handle.assert_called_once_with(door, 0)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_face_pick_survives_storey_object_hits(self):
        """Region face picks should still resolve when native picking only reports the storey."""

        level = Arch.makeFloor(name="Level 0")
        region = self._make_plan_region(level)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        original_view = session.view

        class FakeView:
            def getObjectsInfo(self, _mouse_pos):
                return [{"Document": self.document_name, "Object": self.object_name}]

            def __init__(self, document_name, object_name):
                self.document_name = document_name
                self.object_name = object_name

        try:
            session.view = FakeView(self.document.Name, level.Name)
            with patch.object(
                session,
                "_get_plan_point_from_mouse_pos",
                return_value=FreeCAD.Vector(1500, 1200, 0),
            ):
                self.assertEqual(
                    ("region", region), session._get_plan_target_at_position((100, 100))
                )
        finally:
            session.view = original_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_pick_beats_parent_space_hit_context(self):
        """Direct region hits should not be remapped to the enclosing parent space."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "ParentSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        region = self._make_plan_region(level, parent_space=space, label="Kitchen Area")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        original_view = session.view

        class FakeView:
            def __init__(self, document_name, object_name, parent_object):
                self.document_name = document_name
                self.object_name = object_name
                self.parent_object = parent_object

            def getObjectsInfo(self, _mouse_pos):
                return [
                    {
                        "Document": self.document_name,
                        "Object": self.object_name,
                        "ParentObject": self.parent_object,
                    }
                ]

        try:
            session.view = FakeView(self.document.Name, region.Name, space)
            self.assertEqual(("region", region), session._get_plan_target_at_position((100, 100)))
        finally:
            session.view = original_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_pick_uses_region_points_when_footprint_faces_are_unavailable(self):
        """Saved plan regions should remain pickable from their polygon points."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "FallbackParentSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        region = self._make_plan_region(level, parent_space=space, label="Kitchen Area")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        original_view = session.view

        class FakeView:
            def __init__(self, document_name, object_name, parent_object):
                self.document_name = document_name
                self.object_name = object_name
                self.parent_object = parent_object

            def getObjectsInfo(self, _mouse_pos):
                return [
                    {
                        "Document": self.document_name,
                        "Object": self.object_name,
                        "ParentObject": self.parent_object,
                    }
                ]

        try:
            session.view = FakeView(self.document.Name, space.Name, level)
            with (
                patch.object(session, "_get_region_footprint_faces", return_value=[]),
                patch.object(
                    session,
                    "_get_plan_point_from_mouse_pos",
                    return_value=FreeCAD.Vector(1500, 1200, 0),
                ),
            ):
                self.assertEqual(
                    ("region", region), session._get_plan_target_at_position((100, 100))
                )
        finally:
            session.view = original_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_editor_updates_region_metadata(self):
        """Region metadata should be editable from the Plan Edit task panel."""

        level = Arch.makeFloor(name="Level 0")

        living_base = self.document.addObject("Part::Box", "LivingRoomBase")
        living_base.Length = 6000
        living_base.Width = 4000
        living_base.Height = 2500
        living_space = Arch.makeSpace(living_base, name="Living Room")

        dining_base = self.document.addObject("Part::Box", "DiningRoomBase")
        dining_base.Length = 2800
        dining_base.Width = 2400
        dining_base.Height = 2500
        dining_base.Placement.Base = FreeCAD.Vector(6500, 0, 0)
        dining_space = Arch.makeSpace(dining_base, name="Dining Room")

        level.addObject(living_space)
        level.addObject(dining_space)
        region = self._make_plan_region(level, parent_space=living_space)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, region.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self.assertIs(session.selected_region, region)
        self.assertFalse(session.task_panel.region_editor.isHidden())
        self.assertTrue(session.task_panel.space_editor.isHidden())

        session.task_panel.region_label_edit.setText("Prep Zone")
        session.task_panel.on_region_label_edited()
        self.pump_gui_events()
        self.assertEqual(region.Label, "Prep Zone")

        session.task_panel.region_scheme_edit.setText("Operations")
        session.task_panel.on_region_scheme_edited()
        self.pump_gui_events()
        self.assertEqual(region.Scheme, "Operations")

        session.task_panel.region_type_edit.setText("Kitchen Support")
        session.task_panel.on_region_type_edited()
        self.pump_gui_events()
        self.assertEqual(region.RegionType, "Kitchen Support")

        combo_items = session.task_panel._region_parent_space_items
        target_index = next(
            index
            for index, item in enumerate(combo_items)
            if getattr(item, "Name", None) == dining_space.Name
        )
        session.task_panel.region_parent_space_combo.setCurrentIndex(target_index)
        session.task_panel.on_region_parent_space_changed(target_index)
        self.pump_gui_events()
        self.assertIs(region.ParentSpace, dining_space)

        session.task_panel.region_parent_space_combo.setCurrentIndex(0)
        session.task_panel.on_region_parent_space_changed(0)
        self.pump_gui_events()
        self.assertIsNone(region.ParentSpace)
        self.assertIn("Region: Prep Zone", session.task_panel.status.text())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_drops_deleted_selected_region_reference(self):
        """Deleted region targets should not crash selection/overlay refresh paths."""

        level = Arch.makeFloor(name="Level 0")
        region = self._make_plan_region(level)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, region.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        self.assertIs(session.selected_region, region)

        stale_region = region
        self.document.removeObject(region.Name)
        self.document.recompute()
        self.pump_gui_events()

        session.selected_region = stale_region
        self.assertEqual(session._get_selected_plan_target(), (None, None))
        self.assertIsNone(session.selected_region)

        session.slotChangedObject(level, "Placement")
        self.pump_gui_events()

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_overlay_follows_wire_edges_when_vertex_order_is_scrambled(self):
        """Space overlays should follow wire edge order, not OCC vertex storage order."""

        class _FakeSpaceProxy:
            Type = "Space"

            def __init__(self, faces):
                self._faces = list(faces or [])

            def getFootprint(self, _obj):
                return list(self._faces)

        class _FakeSpace:
            IfcType = "Space"
            InList = []
            InListRecursive = []
            Name = "OverlaySpace"
            TypeId = "App::FeaturePython"

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        face_shape = Part.makeFace(
            [
                Part.makeLine(FreeCAD.Vector(200, 200, 0), FreeCAD.Vector(6200, 200, 0)),
                Part.makeLine(FreeCAD.Vector(200, 5630, 0), FreeCAD.Vector(200, 200, 0)),
                Part.makeLine(FreeCAD.Vector(6200, 5630, 0), FreeCAD.Vector(200, 5630, 0)),
                Part.makeLine(FreeCAD.Vector(6200, 200, 0), FreeCAD.Vector(6200, 5630, 0)),
            ],
            "Part::FaceMakerBuildFace",
        )
        self.assertEqual(len(face_shape.Faces), 1)

        space = _FakeSpace()
        space.Proxy = _FakeSpaceProxy(face_shape.Faces)

        polylines = session._get_space_overlay_polylines(space)
        self.assertEqual(len(polylines), 1)

        polyline = polylines[0]
        self.assertGreaterEqual(len(polyline), 5)
        self.assertLess(polyline[0].distanceToPoint(polyline[-1]), 1e-6)
        for start, end in zip(polyline, polyline[1:]):
            dx = abs(start.x - end.x)
            dy = abs(start.y - end.y)
            self.assertTrue(dx < 1e-6 or dy < 1e-6)

        x_values = [round(point.x, 6) for point in polyline[:-1]]
        y_values = [round(point.y, 6) for point in polyline[:-1]]
        self.assertEqual(min(x_values), 200.0)
        self.assertEqual(max(x_values), 6200.0)
        self.assertEqual(min(y_values), 200.0)
        self.assertEqual(max(y_values), 5630.0)
        for point in polyline[:-1]:
            self.assertTrue(
                abs(point.x - 200.0) < 1e-6
                or abs(point.x - 6200.0) < 1e-6
                or abs(point.y - 200.0) < 1e-6
                or abs(point.y - 5630.0) < 1e-6
            )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_button_creates_space_from_selected_walls(self):
        """The Space action should create and select a real Arch Space from selected walls."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        FreeCADGui.Selection.clearSelection()
        for wall in walls:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self.assertTrue(session.activate_space_tool())
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        space = created_spaces[0]

        self.assertEqual(Draft.getType(space), "Space")
        self.assertEqual(space.IfcType, "Space")
        self.assertIn(level, space.InListRecursive)
        self.assertIs(session.selected_space, space)
        self.assertEqual(len(session._get_space_boundary_entries(space)), 4)
        self.assertGreater(space.Area.getValueAs("m^2").Value, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_region_button_creates_plan_region_with_parent_space(self):
        """The Region action should create and select a polygonal plan region."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "LivingRoomBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        session._set_pending_selected_plan_target("space", space)
        session._set_gui_selection([space])
        session._refresh_primary_selected_plan_target()
        self.assertIs(session.selected_space, space)

        with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None):
            session.activate_plan_region_tool()
            self.assertEqual(session.current_tool, "Region")
            for point in (
                FreeCAD.Vector(1200, 1200, 0),
                FreeCAD.Vector(3200, 1200, 0),
                FreeCAD.Vector(3200, 2400, 0),
                FreeCAD.Vector(1200, 2400, 0),
            ):
                session._handle_plan_region_point(point)
            self.assertTrue(session._finalize_plan_region())
        self.pump_gui_events()

        created_regions = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "PlanRegion"
        ]
        self.assertEqual(len(created_regions), 1)
        region = created_regions[0]

        self.assertIs(region.ParentSpace, space)
        self.assertIn(level, region.InListRecursive)
        self.assertGreater(len(region.Shape.Faces), 0)
        self.assertIs(session.selected_region, region)
        self.assertEqual(session.current_tool, "Select")

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_separator_tool_creates_space_separator_in_active_storey(self):
        """The Separator action should create a real space-separator object on the storey."""

        level = Arch.makeFloor(name="Level 0")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}

        session.activate_space_separator_tool()
        self.assertEqual(session.current_tool, "Separator")

        session._handle_space_separator_point(FreeCAD.Vector(1000, 500, 0))
        session._handle_space_separator_point(FreeCAD.Vector(1000, 3500, 0))
        self.pump_gui_events()

        created = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "SpaceSeparator"
        ]
        self.assertEqual(len(created), 1)
        separator = created[0]

        self.assertIn(level, separator.InListRecursive)
        expected_area = 3000.0 * float(separator.Height.Value)
        self.assertAlmostEqual(separator.Shape.Area, expected_area, places=3)
        self.assertEqual(session.current_tool, "Select")

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_uses_selected_separator_boundary(self):
        """Wall-based space creation should include selected separators as explicit boundaries."""

        level, walls = self._make_plan_room_walls(size=6000)
        separator = self._make_plan_space_separator(
            level,
            start=FreeCAD.Vector(3000, 0, 0),
            end=FreeCAD.Vector(3000, 6000, 0),
        )

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        for obj in list(walls) + [separator]:
            FreeCADGui.Selection.addSelection(self.document.Name, obj.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        request = session._get_space_creation_request()
        self.assertIsNotNone(request)
        self.assertIn(separator, [obj for obj, _subnames in request["boundaries"]])

        self.assertTrue(session.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session._space_region_candidates), 2)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_can_pick_regions_from_selected_space_and_separator(self):
        """A selected space plus separator should split the space into region candidates."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "SeedSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Living Room")
        level.addObject(space)
        separator = self._make_plan_space_separator(level)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}

        session._set_pending_selected_plan_target("space", space)
        session._set_gui_selection([space, separator])
        session._refresh_primary_selected_plan_target()

        self.assertIs(session.selected_space, space)
        request = session._get_space_creation_request()
        self.assertIsNotNone(request)
        self.assertIs(request["region_seed_space"], space)
        self.assertIn(separator, [obj for obj, _subnames in request["boundaries"]])

        self.assertTrue(session.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session._space_region_candidates), 2)

        candidate = min(session._space_region_candidates, key=lambda item: item["area"])
        self.assertTrue(session._activate_space_region_candidate(candidate))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        self.assertAlmostEqual(
            created_spaces[0].Proxy.getArea(created_spaces[0]), candidate["area"]
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_picker_prefers_primary_wall_face_over_opening_reveals(self):
        """Auto-picked wall boundaries should prefer the room-side wall face, not opening reveals."""

        level, wall, _window = self._make_windowed_plan_wall()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        face_names = ArchSpace.getBoundaryFaceNamesForObject(
            wall,
            reference_point=FreeCAD.Vector(1500, 1500, 1000),
        )
        self.assertEqual(len(face_names), 1)

        face = wall.Shape.Faces[int(face_names[0][4:]) - 1]
        normal = FreeCAD.Vector(face.normalAt(0, 0))
        normal.normalize()

        self.assertGreater(face.Area, 5_000_000.0)
        self.assertGreater(abs(normal.y), 0.8)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_picker_skips_walls_outside_reference_height(self):
        """Auto-picked space boundaries should ignore walls that do not span the room height."""

        level, walls = self._make_plan_room_walls()
        walls[0].Placement.Base.z = 3000
        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        for wall in walls:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        boundaries = session._get_selected_space_boundary_links()
        self.assertEqual(len(boundaries), 3)
        self.assertNotIn(walls[0].Name, [obj.Name for obj, _subnames in boundaries])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_preflight_reports_valid_wall_selection(self):
        """Selecting enclosing walls should show a valid-space preflight in the task panel."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        for wall in walls:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        status_text = session.task_panel.status.text()
        self.assertIn("Selection set: 4 walls", status_text)
        self.assertIn("Space preflight: Valid space", status_text)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_single_wall_selection_skips_space_preflight(self):
        """Selecting one wall should not run boundary preflight on every panel refresh."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch(
            "ArchSpace.analyzeBoundaryLinks",
            wraps=ArchSpace.analyzeBoundaryLinks,
        ) as analyze_boundaries:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(self.document.Name, walls[0].Name)
            self.pump_gui_events()
            session._refresh_primary_selected_plan_target()

            status_text = session.task_panel.status.text()
            self.assertNotIn("Space preflight:", status_text)
            analyze_boundaries.assert_not_called()

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_preflight_reports_open_loop(self):
        """Selecting an open wall set should show the preflight failure before creating a space."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        for wall in walls[:3]:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        status_text = session.task_panel.status.text()
        self.assertIn("Selection set: 3 walls", status_text)
        self.assertIn("Space preflight: Open loop", status_text)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_can_pick_a_region_from_multiple_enclosed_rooms(self):
        """Plan Edit should let the user choose one enclosed region when many are detected."""

        level = Arch.makeFloor(name="Level 0")
        height = 2500.0

        def make_boundary_face(name, points):
            face_object = self.document.addObject("Part::Feature", name)
            face_object.Shape = Part.Face(Part.makePolygon(points + [points[0]]))
            return face_object

        boundaries = [
            (
                make_boundary_face(
                    "OuterSouth",
                    [
                        FreeCAD.Vector(0.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 0.0, height),
                        FreeCAD.Vector(0.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterEast",
                    [
                        FreeCAD.Vector(6000.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 4000.0, 0.0),
                        FreeCAD.Vector(6000.0, 4000.0, height),
                        FreeCAD.Vector(6000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterNorth",
                    [
                        FreeCAD.Vector(6000.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 4000.0, height),
                        FreeCAD.Vector(6000.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterWest",
                    [
                        FreeCAD.Vector(0.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 0.0, 0.0),
                        FreeCAD.Vector(0.0, 0.0, height),
                        FreeCAD.Vector(0.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "Divider",
                    [
                        FreeCAD.Vector(3000.0, 0.0, 0.0),
                        FreeCAD.Vector(3000.0, 4000.0, 0.0),
                        FreeCAD.Vector(3000.0, 4000.0, height),
                        FreeCAD.Vector(3000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
        ]

        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}

        self.assertTrue(session._begin_space_region_pick(boundaries, label="Two Rooms"))
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session._space_region_candidates), 2)
        self.assertIn("pick region", session.task_panel.status.text().lower())

        candidate = session._space_region_candidates[0]
        screen_pos = session.view.getPointOnScreen(candidate["sample_point"])
        self.assertIs(session._pick_space_region_candidate(screen_pos), candidate)

        session._on_mouse_pressed(self._make_fake_left_mouse_press(*screen_pos))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_space, space)
        self.assertEqual(len(session._get_space_boundary_entries(space)), len(boundaries))
        self.assertAlmostEqual(space.Proxy.getArea(space), candidate["area"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_can_pick_regions_from_selected_space_and_wall(self):
        """A selected space plus boundary wall should become a region-pick candidate set."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "RegionSeedSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Seed Space")
        wall_base = Draft.makeLine(FreeCAD.Vector(2000, 0, 0), FreeCAD.Vector(2000, 4000, 0))
        wall = Arch.makeWall(wall_base, width=200, height=2500, name="RegionDivider")
        wall.Label = "Region Divider"
        level.addObject(space)
        level.addObject(wall)
        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}

        session._set_pending_selected_plan_target("space", space)
        session._set_gui_selection([space, wall])
        session._refresh_primary_selected_plan_target()

        self.assertIs(session.selected_space, space)
        self.assertIsNone(session.selected_wall)
        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())

        self.assertTrue(session.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session._space_region_candidates), 2)

        candidate = min(session._space_region_candidates, key=lambda item: item["area"])
        self.assertTrue(session._activate_space_region_candidate(candidate))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        created_space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_space, created_space)
        self.assertEqual(session._get_space_boundary_entries(created_space), [])
        self.assertAlmostEqual(created_space.Proxy.getArea(created_space), candidate["area"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_accepts_space_selected_after_wall(self):
        """Space seeding should work even when the wall is the primary selected target."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "RegionSeedSpaceBase")
        base.Length = 6000
        base.Width = 4000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Seed Space")
        wall_base = Draft.makeLine(FreeCAD.Vector(2000, 0, 0), FreeCAD.Vector(2000, 4000, 0))
        wall = Arch.makeWall(wall_base, width=200, height=2500, name="RegionDivider")
        wall.Label = "Region Divider"
        level.addObject(space)
        level.addObject(wall)
        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._set_pending_selected_plan_target("wall", wall)
        session._set_gui_selection([wall, space])
        session._refresh_primary_selected_plan_target()

        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())
        self.assertTrue(session.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session._space_region_candidates), 2)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_tool_skips_regions_with_existing_spaces(self):
        """Wall-only space creation should ignore enclosed regions already covered by a space."""

        level = Arch.makeFloor(name="Level 0")
        height = 2500.0

        def make_boundary_face(name, points):
            face_object = self.document.addObject("Part::Feature", name)
            face_object.Shape = Part.Face(Part.makePolygon(points + [points[0]]))
            return face_object

        boundaries = [
            (
                make_boundary_face(
                    "OuterSouth",
                    [
                        FreeCAD.Vector(0.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 0.0, height),
                        FreeCAD.Vector(0.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterEast",
                    [
                        FreeCAD.Vector(6000.0, 0.0, 0.0),
                        FreeCAD.Vector(6000.0, 4000.0, 0.0),
                        FreeCAD.Vector(6000.0, 4000.0, height),
                        FreeCAD.Vector(6000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterNorth",
                    [
                        FreeCAD.Vector(6000.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 4000.0, height),
                        FreeCAD.Vector(6000.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterWest",
                    [
                        FreeCAD.Vector(0.0, 4000.0, 0.0),
                        FreeCAD.Vector(0.0, 0.0, 0.0),
                        FreeCAD.Vector(0.0, 0.0, height),
                        FreeCAD.Vector(0.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "Divider",
                    [
                        FreeCAD.Vector(3000.0, 0.0, 0.0),
                        FreeCAD.Vector(3000.0, 4000.0, 0.0),
                        FreeCAD.Vector(3000.0, 4000.0, height),
                        FreeCAD.Vector(3000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
        ]

        base = self.document.addObject("Part::Box", "ExistingBathroomBase")
        # Mimic a saved space footprint that is slightly stale versus the live wall region.
        base.Length = 2800
        base.Width = 4000
        base.Height = 2500
        base.Placement.Base = FreeCAD.Vector(3000, 0, 0)
        existing_bathroom = Arch.makeSpace(base, name="Existing Bathroom")
        level.addObject(existing_bathroom)
        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}

        self.assertTrue(session._begin_space_region_pick(boundaries, label="Two Rooms"))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        created_space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_space, created_space)
        self.assertEqual(len(session._space_region_candidates), 0)
        self.assertAlmostEqual(created_space.Area.getValueAs("m^2").Value, 12.0, places=3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_button_rejects_open_boundary_selection(self):
        """Open wall selections should fail cleanly and leave no orphan space object behind."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        FreeCADGui.Selection.clearSelection()
        for wall in walls[:3]:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        with (
            patch("FreeCAD.Console.PrintError") as print_error,
            patch("FreeCAD.Console.PrintWarning") as print_warning,
        ):
            self.assertFalse(session.activate_space_tool())
            self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(created_spaces, [])
        error_output = "".join(call.args[0] for call in print_error.call_args_list)
        warning_output = "".join(call.args[0] for call in print_warning.call_args_list)
        self.assertIn("closed room loop", error_output)
        self.assertIn("kept no new space object", warning_output)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_editor_can_add_and_remove_wall_boundaries(self):
        """Space boundary editing should stay session-owned inside Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "EditableSpaceBase")
        base.Length = 3000
        base.Width = 2000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Editable Space")
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        wall.Label = "Boundary Wall"
        level.addObject(space)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, space.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        self.assertIs(session.selected_space, space)

        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()
        self.assertIs(session.selected_space, space)

        self.assertTrue(session._add_boundaries_to_selected_space())
        boundaries = session._get_space_boundary_entries(space)
        self.assertEqual(len(boundaries), 1)
        self.assertIs(boundaries[0][0], wall)

        self.assertTrue(session._remove_selected_space_boundaries())
        self.assertEqual(session._get_space_boundary_entries(space), [])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_editor_uses_searchable_compact_type_combo(self):
        """Space type selection should stay compact and searchable inside Plan Edit."""

        from PySide import QtCore, QtGui

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "SearchableSpaceBase")
        base.Length = 3000
        base.Width = 2000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Searchable Space")
        level.addObject(space)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, space.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        combo = session.task_panel.space_type_combo
        self.assertIsNotNone(combo)
        self.assertTrue(combo.isEditable())
        self.assertEqual(combo.insertPolicy(), QtGui.QComboBox.NoInsert)
        self.assertEqual(combo.maxVisibleItems(), 12)
        self.assertIsNotNone(combo.completer())
        self.assertEqual(combo.completer().completionMode(), QtGui.QCompleter.PopupCompletion)
        self.assertEqual(combo.completer().caseSensitivity(), QtCore.Qt.CaseInsensitive)
        if hasattr(combo.completer(), "filterMode"):
            self.assertEqual(combo.completer().filterMode(), QtCore.Qt.MatchContains)

        expected_prefix = [
            "Undefined",
            "Room",
            "Office",
            "Restrooms",
            "Corridor / Transition",
            "Lobby",
            "Dining Area",
            "Exterior",
            "Active Storage",
            "Electrical / Mechanical",
        ]
        actual_prefix = [combo.itemText(index) for index in range(len(expected_prefix))]
        self.assertEqual(actual_prefix, expected_prefix)

        line_edit = combo.lineEdit()
        self.assertIsNotNone(line_edit)
        if hasattr(line_edit, "placeholderText"):
            self.assertEqual(line_edit.placeholderText(), "Search space types")

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_ctrl_click_wall_keeps_selected_space_primary_for_boundary_editing(self):
        """Ctrl-click should add boundary walls without replacing the selected space editor target."""

        from PySide import QtCore

        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "CtrlClickSpaceBase")
        base.Length = 3000
        base.Width = 2000
        base.Height = 2500
        space = Arch.makeSpace(base, name="Ctrl Space")
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        wall.Label = "Ctrl Boundary Wall"
        level.addObject(space)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session, "_get_edit_node", return_value=None),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("space", space),
            ),
        ):
            session._on_mouse_pressed(self._make_fake_left_mouse_press())

        self.assertIs(session.selected_space, space)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [space.Name])

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session,
                "_get_edit_node",
                return_value=None,
            ),
            patch.object(
                session,
                "_get_plan_target_at_position",
                return_value=("wall", wall),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session._on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self.assertIs(session.selected_space, space)
        self.assertIsNone(session.selected_wall)
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [space.Name, wall.Name],
        )
        self.assertEqual(session._get_selected_plan_target(), ("space", space))
        self.assertEqual(session._get_secondary_selected_plan_targets(), [("wall", wall)])
        self.assertGreater(len(session._secondary_selection_trackers), 0)
        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())

        self.assertTrue(session._add_boundaries_to_selected_space())
        self.pump_gui_events()
        boundaries = session._get_space_boundary_entries(space)
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0][0], wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_defers_document_visual_refresh_until_scope_exit(self):
        """Document changes inside a deferred scope should produce one visual refresh."""

        session = BimPlanSession.PlanEditSession()
        with (
            patch.object(
                session,
                "_invalidate_document_dependent_plan_visuals",
            ) as invalidate_visuals,
            patch.object(
                session,
                "_refresh_primary_selected_plan_target",
            ) as refresh_selection,
            patch.object(
                session,
                "_refresh_task_panel_status",
            ) as refresh_status,
        ):
            with session.defer_document_visual_updates():
                session.slotChangedObject(object(), "Placement")
                session.slotRecomputedDocument(self.document)
                invalidate_visuals.assert_not_called()
                refresh_selection.assert_not_called()
                refresh_status.assert_not_called()

            invalidate_visuals.assert_called_once_with()
            refresh_selection.assert_called_once_with()
            refresh_status.assert_called_once_with(selection_only=True)

    def test_plan_edit_defers_created_object_registration_until_scope_exit(self):
        """Objects created inside a deferred scope should be registered after the scope exits."""

        session = BimPlanSession.PlanEditSession()
        obj = self.document.addObject("App::FeaturePython", "DeferredPlanObject")
        with (
            patch.object(
                session,
                "_should_register_created_plan_object",
                return_value=True,
            ),
            patch.object(session, "_register_plan_object") as register_object,
            patch.object(
                session,
                "_invalidate_document_dependent_plan_visuals",
            ) as invalidate_visuals,
            patch.object(
                session,
                "_refresh_primary_selected_plan_target",
            ) as refresh_selection,
            patch.object(
                session,
                "_refresh_task_panel_status",
            ) as refresh_status,
        ):
            register_object.side_effect = lambda registered: session.slotChangedObject(
                registered,
                "Group",
            )
            with session.defer_document_visual_updates():
                session.slotCreatedObject(obj)
                self.assertIn(obj.Name, session._pending_created_plan_objects)
                session._flush_created_plan_objects()
                register_object.assert_not_called()

            register_object.assert_called_once_with(obj)
            invalidate_visuals.assert_called_once_with()
            refresh_selection.assert_called_once_with()
            refresh_status.assert_called_once_with(selection_only=True)
            self.assertFalse(session._pending_created_plan_objects)

    def test_plan_edit_invalidates_selected_opening_overlay_when_base_changes(self):
        """Selected opening overlays should be invalidated when the opening base changes."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="UndoDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        with patch.object(session, "_queue_plan_overlay_visual_refresh") as queue_refresh:
            session.slotChangedObject(door.Base, "Placement")

        queue_refresh.assert_called_once_with(
            BimPlanSession._PLAN_VISUAL_SELECTED_OPENING,
            BimPlanSession._PLAN_VISUAL_HOVERED_OPENING,
        )

    def test_plan_edit_invalidates_selected_opening_overlay_on_undo_document(self):
        """Selected opening overlays should be invalidated on document-level undo notifications."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="UndoNotifyDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        with (
            patch.object(session, "_queue_hard_refresh_selected_opening_visuals") as hard_refresh,
            patch.object(session, "_queue_recompute_opening_hosts") as recompute_hosts,
            patch.object(session, "_queue_plan_overlay_visual_refresh") as queue_refresh,
        ):
            session.slotUndoDocument(self.document)

        hard_refresh.assert_called_once_with()
        recompute_hosts.assert_called_once_with(door, None)
        queue_refresh.assert_called_once_with(
            BimPlanSession._PLAN_VISUAL_SELECTED_SYMBOL,
            BimPlanSession._PLAN_VISUAL_HOVERED_SYMBOL,
            BimPlanSession._PLAN_VISUAL_HOVERED_OPENING,
            BimPlanSession._PLAN_VISUAL_HOVERED_WALL,
            BimPlanSession._PLAN_VISUAL_WALL_GRIPS,
            BimPlanSession._PLAN_VISUAL_SELECTED_OPENING,
        )

    def test_plan_edit_shows_grips_for_straight_base_wall(self):
        """Straight base-driven walls should get the same grip overlays as baseless walls."""

        base = Draft.make_line(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(3000, 0, 0))
        wall = Arch.makeWall(base, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_primary_selected_plan_target()

        self.assertTrue(session.is_selected_wall_endpoint_editable())
        self.assertEqual(len(session._grip_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clears_selected_wall_when_host_shape_changes(self):
        """Selected wall grips should be cleared if a hosted opening changes the wall shape."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        self.pump_gui_events()
        self.assertIs(session.selected_wall, wall)
        self.assertGreater(len(session._grip_trackers), 0)

        self._make_hosted_door(wall, name="ResetDoor")
        self.pump_gui_events()

        self.assertIsNone(session.selected_wall)
        self.assertEqual(len(session._grip_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

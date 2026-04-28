# SPDX-License-Identifier: LGPL-2.1-or-later

"""Symbol and passive-context GUI tests."""

from .TestBimPlanEditGuiBase import *  # noqa: F401,F403
from .TestBimPlanEditGuiBase import BimPlanEditGuiBase


class BimPlanEditGuiSymbolsMixin:
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        self.assertTrue(link.ViewObject.Visibility)
        self.assertTrue(link.ViewObject.Selectable)
        self.assertTrue(session.visibility.is_plan_symbol_instance(link))

        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        self.assertIs(link, session.selection.state.get_selected_target_for_kind("symbol"))
        self.assertEqual(
            {"move", "rotate"},
            {
                role
                for role, _point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                    link
                )
            },
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        original_view = session.view
        original_pick_opening = session.picking.pick_plan_opening_target_from_overlays
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
            session.picking.pick_plan_opening_target_from_overlays = (
                fail_if_opening_overlay_pick_runs
            )
            session.view = FakeView(
                [{"Document": self.document.Name, "Object": plan_symbol.Name, "ParentObject": link}]
            )
            self.assertEqual(
                ("symbol", link), session.picking.get_plan_target_at_position((100, 100))
            )

            session.view = FakeView(
                [{"Document": self.document.Name, "Object": base.Name, "ParentObject": link}]
            )
            self.assertEqual(
                ("symbol", link), session.picking.get_plan_target_at_position((100, 100))
            )
            self.assertEqual([], opening_pick_calls)
        finally:
            session.picking.pick_plan_opening_target_from_overlays = original_pick_opening
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.pump_gui_events()

        segments = session.overlays.symbols.get_symbol_overlay_segments(link)
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
            self.assertEqual(
                ("symbol", link), session.picking.get_plan_target_at_position(mouse_pos)
            )
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

        session.document_visuals.refresh_plan_object_footprint_display(equipment)
        self.pump_gui_events()

        self.assertTrue(equipment.ViewObject.Visibility)
        self.assertTrue(equipment.ViewObject.Selectable)
        self.assertTrue(session.visibility.is_plan_symbol_instance(equipment))
        self.assertEqual(
            "symbol", session.selection.targets.get_plan_target_kind_for_object(equipment)
        )

        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(equipment))
        self.pump_gui_events()

        self.assertIs(equipment, session.selection.state.get_selected_target_for_kind("symbol"))
        self.assertEqual(
            {"move", "rotate"},
            {
                role
                for role, _point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                    equipment
                )
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

        session.document_visuals.refresh_plan_object_footprint_display(equipment)
        self.pump_gui_events()

        self.assertIs(session.visibility.get_plan_semantic_object(plan_symbol), equipment)
        self.assertIs(session.visibility.get_plan_semantic_object(base), equipment)
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
                ("symbol", equipment), session.picking.get_plan_target_at_position((100, 100))
            )

            session.view = FakeView(
                [{"Document": self.document.Name, "Object": base.Name, "ParentObject": equipment}]
            )
            self.assertEqual(
                ("symbol", equipment), session.picking.get_plan_target_at_position((100, 100))
            )
        finally:
            session.view = original_view

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(plan_symbol)
        self.pump_gui_events()
        self.assertIs(equipment, session.selection.state.get_selected_target_for_kind("symbol"))

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(base)
        self.pump_gui_events()
        self.assertIs(equipment, session.selection.state.get_selected_target_for_kind("symbol"))

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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
        }

        session.current_tool = "Move Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "move"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["move"]
        session.symbols.finish_symbol_handle_point_pick(FreeCAD.Vector(2400, 1600, 0))
        self.pump_gui_events()

        self.assertAlmostEqual(2400.0, link.Placement.Base.x, delta=1e-6)
        self.assertAlmostEqual(1600.0, link.Placement.Base.y, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("symbol"), link)

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
        }
        anchor = FreeCAD.Vector(link.Placement.Base)

        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        session.symbols.finish_symbol_handle_point_pick(
            FreeCAD.Vector(anchor.x, anchor.y + 1000, 0)
        )
        self.pump_gui_events()

        axis = link.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        self.assertAlmostEqual(0.0, axis.x, delta=1e-3)
        self.assertGreater(axis.y, 0.99)
        self.assertIs(session.selection.state.get_selected_target_for_kind("symbol"), link)
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
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
        session.symbols.finish_symbol_handle_point_pick(target_anchor)
        self.pump_gui_events()

        self.assertAlmostEqual(2500.0, link.Placement.Base.x, delta=1e-6)
        self.assertAlmostEqual(1425.0, link.Placement.Base.y, delta=1e-6)
        moved_anchor = link.Placement.multVec(equipment.PlanAnchor)
        self.assertAlmostEqual(target_anchor.x, moved_anchor.x, delta=1e-6)
        self.assertAlmostEqual(target_anchor.y, moved_anchor.y, delta=1e-6)

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
        }
        anchor = link.Placement.multVec(equipment.PlanAnchor)
        session.current_tool = "Rotate Symbol"
        session._edit_symbol = link
        session._edit_symbol_handle_role = "rotate"
        session._edit_symbol_start_placement = link.Placement.copy()
        session._edit_symbol_reference_point = handle_points["rotate"]
        session.symbols.finish_symbol_handle_point_pick(
            FreeCAD.Vector(anchor.x + 1000, anchor.y, 0)
        )
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
        }
        anchor = session.symbols.get_symbol_anchor_point(link)
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
            patch.object(session.symbols, "symbol_rotation_snap_enabled", return_value=True),
            patch.object(
                session.overlays.symbols,
                "get_symbol_rotation_snap_increment_degrees",
                return_value=15.0,
            ),
            patch.object(
                session.overlays.symbols,
                "symbol_rotation_free_angle_override_active",
                return_value=False,
            ),
        ):
            session.symbols.finish_symbol_handle_point_pick(raw_point)
        self.pump_gui_events()

        facing = link.Placement.Rotation.multVec(equipment.PlanFacing)
        angle = math.degrees(math.atan2(facing.y, facing.x))
        self.assertAlmostEqual(15.0, angle, delta=1e-3)
        rotated_anchor = session.symbols.get_symbol_anchor_point(link)
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

        session.document_visuals.refresh_plan_object_footprint_display(link)
        self.assertTrue(session.selection.activation.select_symbol_for_plan_edit(link))
        self.pump_gui_events()

        handle_points = {
            role: point
            for role, point, _marker in session.overlays.symbols.get_selected_symbol_handle_specs(
                link
            )
        }
        anchor = session.symbols.get_symbol_anchor_point(link)
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
            patch.object(session.symbols, "symbol_rotation_snap_enabled", return_value=True),
            patch.object(
                session.overlays.symbols,
                "get_symbol_rotation_snap_increment_degrees",
                return_value=15.0,
            ),
            patch.object(
                session.overlays.symbols,
                "symbol_rotation_free_angle_override_active",
                return_value=True,
            ),
        ):
            session.symbols.finish_symbol_handle_point_pick(raw_point)
        self.pump_gui_events()

        facing = link.Placement.Rotation.multVec(equipment.PlanFacing)
        angle = math.degrees(math.atan2(facing.y, facing.x))
        self.assertAlmostEqual(10.0, angle, delta=1e-3)
        rotated_anchor = session.symbols.get_symbol_anchor_point(link)
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


class TestBimPlanEditGuiSymbols(BimPlanEditGuiSymbolsMixin, BimPlanEditGuiBase):
    """Symbol and passive-context Plan Edit GUI suite."""

    pass

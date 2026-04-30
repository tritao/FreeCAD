# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space and region GUI tests."""

from .TestBimPlanEditGuiBase import *  # noqa: F401,F403
from .TestBimPlanEditGuiBase import BimPlanEditGuiBase


class BimPlanEditGuiSpacesMixin:
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "space", space)
        self.assertGreater(len(session.overlay_tracker_state.space_overlay_trackers), 0)
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "region", region)
        self.assertGreater(len(session.overlay_tracker_state.region_overlay_trackers), 0)
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

        session.selection.state.set_selected_target_for_kind("region", region)
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("region", region))
        self.assertEqual(
            session.selection.state.get_selected_plan_target_state(), ("region", region)
        )
        self.assertIs(session.selection.state.get_selected_target_for_kind("region"), region)
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("space"))
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("wall"))

        session.selection.state.set_selected_target_for_kind("space", space)
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("space", space))
        self.assertEqual(session.selection.state.get_selected_plan_target_state(), ("space", space))
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("region"))

        session.selection.state.set_selected_target_for_kind("region", None)
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("space", space))
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)

        session.selection.state.set_selected_target_for_kind("space", None)
        self.assertEqual(session.selection.state.get_selected_plan_target(), (None, None))
        self.assertEqual(session.selection.state.get_selected_plan_target_state(), (None, None))

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
            session.picking,
            "pick",
            return_value=("region", region),
        ):
            activated = session.selection.activation.activate_region_target((100, 100))

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
            patch.object(session.picking, "pick_edit_node", return_value=None),
            patch.object(
                session.picking,
                "pick",
                return_value=("space", space),
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 1)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "space", space)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [space.Name])
        self.assertIs(session.view.getActiveObject("Arch"), space)

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
            patch.object(session.picking, "pick_edit_node", return_value=None),
            patch.object(
                session.picking,
                "pick",
                return_value=("region", region),
            ),
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)
            release = self._make_fake_left_mouse_release(250, 250)
            session.input.on_mouse_pressed(release)

        self.assertTrue(press._handled)
        self.assertTrue(release._handled)
        self.assertFalse(session.input_event_state.consume_left_button_release)
        self._assert_selected_plan_target(session, "region", region)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [region.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, region.Name)
        self.assertIs(session.view.getActiveObject("Arch"), region)

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
                session.viewport,
                "get_plan_point_from_mouse_pos",
                return_value=FreeCAD.Vector(1500, 1200, 0),
            ):
                self.assertEqual(
                    ("region", region),
                    session.picking.pick((100, 100)),
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
            self.assertEqual(
                ("region", region),
                session.picking.pick((100, 100)),
            )
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
                patch(
                    "bimplan.overlays.geometry.get_region_footprint_faces",
                    return_value=[],
                ),
                patch.object(
                    session.viewport,
                    "get_plan_point_from_mouse_pos",
                    return_value=FreeCAD.Vector(1500, 1200, 0),
                ),
            ):
                self.assertEqual(
                    ("region", region),
                    session.picking.pick((100, 100)),
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        self.assertIs(session.selection.state.get_selected_target_for_kind("region"), region)
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
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.assertIs(session.selection.state.get_selected_target_for_kind("region"), region)

        stale_region = region
        self.document.removeObject(region.Name)
        self.document.recompute()
        self.pump_gui_events()

        session.selection.state.set_selected_target_for_kind("region", stale_region)
        self.assertEqual(session.selection.state.get_selected_plan_target(), (None, None))
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("region"))

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

        polylines = session.overlays.geometry.get_space_overlay_polylines(space)
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        self.assertTrue(session.spaces.activate_space_tool())
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
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        self.assertEqual(len(session.spaces.get_space_boundary_entries(space)), 4)
        self.assertGreater(space.Area.getValueAs("m^2").Value, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_backed_space_survives_hosted_opening_face_split(self):
        """A space created from selected walls should stay valid after a hosted door changes one wall."""

        level, walls = self._make_plan_room_walls()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()
        selection = getattr(session, "selection", None)
        selection_refresh = getattr(selection, "refresh", selection)

        FreeCADGui.Selection.clearSelection()
        for wall in walls:
            FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        selection_refresh.refresh_primary_selected_plan_target()

        self.assertTrue(session.spaces.activate_space_tool())
        self.pump_gui_events()

        created_spaces = [obj for obj in self.document.Objects if Draft.getType(obj) == "Space"]
        self.assertEqual(len(created_spaces), 1)
        space = created_spaces[0]

        initial_area = float(space.Proxy.getArea(space))
        self.assertGreater(initial_area, 1_000_000.0)
        self.assertEqual(space.Proxy.getLastBoundaryError(space), "")
        self.assertTrue(getattr(space, "BoundarySideHints", []))
        self.assertEqual(len(session.spaces.get_space_boundary_entries(space)), 4)

        self._make_hosted_door(walls[1], name="RoomBoundaryDoor")
        self.document.recompute()
        self.pump_gui_events()

        self.assertAlmostEqual(float(space.Proxy.getArea(space)), initial_area)
        self.assertEqual(space.Proxy.getLastBoundaryError(space), "")
        self.assertTrue(getattr(space, "BoundarySideHints", []))
        self.assertEqual(len(session.spaces.get_space_boundary_entries(space)), 4)

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
        session.selection.state.set_pending_selected_plan_target("space", space)
        session.selection.sync.set_gui_selection([space])
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)

        with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None):
            session.spaces.activate_plan_region_tool()
            self.assertEqual(session.current_tool, "Region")
            for point in (
                FreeCAD.Vector(1200, 1200, 0),
                FreeCAD.Vector(3200, 1200, 0),
                FreeCAD.Vector(3200, 2400, 0),
                FreeCAD.Vector(1200, 2400, 0),
            ):
                session.spaces.handle_plan_region_point(point)
            self.assertTrue(session.spaces.finalize_plan_region())
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
        self.assertIs(session.selection.state.get_selected_target_for_kind("region"), region)
        self.assertEqual(session.current_tool, "Select")

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_shutdown_cancels_active_region_tool(self):
        level = Arch.makeFloor(name="Level 0")
        base = self.document.addObject("Part::Box", "ShutdownRegionBase")
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

        try:
            session.selection.state.set_pending_selected_plan_target("space", space)
            session.selection.sync.set_gui_selection([space])
            session.selection.refresh.refresh_primary_selected_plan_target()

            with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None):
                session.spaces.activate_plan_region_tool()

            self.assertEqual("Region", session.current_tool)
            self.assertIs(session.plan_region_tool_state.parent_space, space)

            self.assertTrue(session.shutdown(close_dialog=False))
            self.pump_gui_events()

            self.assertEqual("Select", session.current_tool)
            self.assertEqual([], session.plan_region_tool_state.points)
            self.assertIsNone(session.plan_region_tool_state.parent_space)
            self.assertIsNone(session.doc)
            self.assertIsNone(BimPlanSession.get_active_session())
        finally:
            if BimPlanSession.get_active_session() is session:
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

        session.spaces.activate_space_separator_tool()
        self.assertEqual(session.current_tool, "Separator")

        session.spaces.handle_space_separator_point(FreeCAD.Vector(1000, 500, 0))
        session.spaces.handle_space_separator_point(FreeCAD.Vector(1000, 3500, 0))
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        request = session.spaces.build_space_creation_request()
        self.assertIsNotNone(request)
        self.assertIn(separator, [obj for obj, _subnames in request["boundaries"]])

        self.assertTrue(session.spaces.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)

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

        session.selection.state.set_pending_selected_plan_target("space", space)
        session.selection.sync.set_gui_selection([space, separator])
        session.selection.refresh.refresh_primary_selected_plan_target()

        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        request = session.spaces.build_space_creation_request()
        self.assertIsNotNone(request)
        self.assertIs(request["region_seed_space"], space)
        self.assertIn(separator, [obj for obj, _subnames in request["boundaries"]])

        self.assertTrue(session.spaces.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)

        candidate = min(session.space_region_pick_state.candidates, key=lambda item: item["area"])
        self.assertTrue(session.spaces.activate_space_region_candidate(candidate))
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        boundaries = session.spaces.get_selected_space_boundary_links()
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
        session.selection.refresh.refresh_primary_selected_plan_target()

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
            session.selection.refresh.refresh_primary_selected_plan_target()

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
        session.selection.refresh.refresh_primary_selected_plan_target()

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

        self.assertTrue(session.spaces.start_space_region_pick(boundaries, label="Two Rooms"))
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)
        self.assertIn("pick region", session.task_panel.status.text().lower())

        candidate = session.space_region_pick_state.candidates[0]
        screen_pos = session.view.getPointOnScreen(candidate["sample_point"])
        self.assertIs(session.spaces.pick_space_region_candidate(screen_pos), candidate)

        session.input.on_mouse_pressed(self._make_fake_left_mouse_press(*screen_pos))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        self.assertEqual(len(session.spaces.get_space_boundary_entries(space)), len(boundaries))
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
        selection = getattr(session, "selection", None)
        selection_state = getattr(selection, "state", selection)
        selection_sync = getattr(selection, "sync", selection)
        selection_refresh = getattr(selection, "refresh", selection)

        before = {obj.Name for obj in self.document.Objects}

        selection_state.set_pending_selected_plan_target("space", space)
        selection_sync.set_gui_selection([space, wall])
        selection_refresh.refresh_primary_selected_plan_target()

        self.assertIs(selection_state.get_selected_target_for_kind("space"), space)
        self.assertIsNone(selection_state.get_selected_target_for_kind("wall"))
        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())

        self.assertTrue(session.spaces.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)

        candidate = min(session.space_region_pick_state.candidates, key=lambda item: item["area"])
        self.assertTrue(session.spaces.activate_space_region_candidate(candidate))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        created_space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(selection_state.get_selected_target_for_kind("space"), created_space)
        self.assertEqual(session.spaces.get_space_boundary_entries(created_space), [])
        self.assertAlmostEqual(created_space.Proxy.getArea(created_space), candidate["area"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_space_boundary_conflict_issue_can_reassign_selected_space(self):
        """A conflicted selected space should expose a re-pick action that updates the same space."""

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

        report = ArchSpace.getBoundaryRegionCandidates(boundaries, label="Two Rooms Preview")
        self.assertEqual(report["candidate_count"], 2)
        left_candidate = min(report["candidates"], key=lambda item: float(item["sample_point"].x))

        base = self.document.addObject("Part::Feature", "ConflictRegionBase")
        base.Shape = left_candidate["shape"].copy()
        space = Arch.makeSpace(base, name="Conflicted Room")
        ArchSpace.setBoundaryRegionReferencePoint(space, left_candidate["sample_point"])
        ArchSpace.setBoundaryLinks(space, boundaries)
        self.document.recompute()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        initial_space_names = sorted(
            obj.Name for obj in self.document.Objects if Draft.getType(obj) == "Space"
        )

        ArchSpace.setBoundaryRegionReferencePoint(space, FreeCAD.Vector(7000.0, 2000.0, 1000.0))
        space.touch()
        self.document.recompute()
        self.pump_gui_events()

        self.assertEqual(getattr(space, "BoundaryStatus", ""), "Conflict")

        selection = getattr(session, "selection", None)
        selection_state = getattr(selection, "state", selection)
        selection_sync = getattr(selection, "sync", selection)
        selection_refresh = getattr(selection, "refresh", selection)
        selection_state.set_pending_selected_plan_target("space", space)
        selection_sync.set_gui_selection([space])
        selection_refresh.refresh_primary_selected_plan_target()
        self.assertIs(selection_state.get_selected_target_for_kind("space"), space)

        snapshot = session.providers.runtime.get_plan_provider_snapshot()
        conflict_issues = [
            issue
            for issue in tuple(getattr(snapshot, "issues", ()) or ())
            if str(getattr(issue, "provider_id", "") or "") == "bim-space"
        ]
        self.assertEqual(len(conflict_issues), 1)
        issue = conflict_issues[0]
        self.assertEqual(issue.title, "Space boundary conflict")
        self.assertEqual(len(issue.actions), 1)
        self.assertEqual(issue.actions[0].label, "Re-pick room region")

        self.assertTrue(
            session.providers.runtime.execute_plan_provider_action(
                issue.provider_id,
                issue.actions[0].key,
                transaction_label=getattr(issue.actions[0], "transaction_label", ""),
            )
        )
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertIs(session.space_region_pick_state.edit_space, space)
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)

        candidate = min(
            session.space_region_pick_state.candidates,
            key=lambda item: float(item["sample_point"].x),
        )
        self.assertTrue(session.spaces.activate_space_region_candidate(candidate))
        self.pump_gui_events()

        current_space_names = sorted(
            obj.Name for obj in self.document.Objects if Draft.getType(obj) == "Space"
        )
        self.assertEqual(current_space_names, initial_space_names)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(selection_state.get_selected_target_for_kind("space"), space)
        self.assertEqual(getattr(space, "BoundaryStatus", ""), "OK")
        self.assertAlmostEqual(space.Proxy.getArea(space), candidate["area"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_stretch_undo_keeps_adjacent_wall_linked_spaces_distinct(self):
        """Stretch undo should not collapse sibling wall-linked spaces onto the same region."""

        FreeCADGui.Selection.clearSelection()
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        level, walls, divider_wall, _boundaries, created_spaces = (
            self._create_adjacent_wall_linked_spaces(session)
        )
        sorted_spaces = self._assert_spaces_stay_distinct(created_spaces)
        initial_centers = [float(space.Shape.CenterOfMass.x) for space in sorted_spaces]
        initial_areas = [float(space.Proxy.getArea(space)) for space in sorted_spaces]

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, divider_wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        divider_start, divider_end = self._get_wall_endpoints(divider_wall)
        new_start = FreeCAD.Vector(divider_start).add(FreeCAD.Vector(400.0, 0.0, 0.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(0)
            captured["callback"](new_start, None)

        self._assert_no_wall_edit_preview_visuals(session)
        self._assert_spaces_stay_distinct(created_spaces)

        self._undo_document()
        self._assert_no_wall_edit_preview_visuals(session)

        restored_spaces = self._assert_spaces_stay_distinct(created_spaces)
        restored_centers = [float(space.Shape.CenterOfMass.x) for space in restored_spaces]
        restored_areas = [float(space.Proxy.getArea(space)) for space in restored_spaces]
        for initial_center, restored_center in zip(initial_centers, restored_centers):
            self.assertAlmostEqual(restored_center, initial_center, delta=1e-6)
        for initial_area, restored_area in zip(initial_areas, restored_areas):
            self.assertAlmostEqual(restored_area, initial_area, delta=1e-6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_move_undo_keeps_adjacent_wall_linked_spaces_distinct(self):
        """Wall move undo should not collapse sibling wall-linked spaces onto the same region."""

        FreeCADGui.Selection.clearSelection()
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        level, walls, divider_wall, _boundaries, created_spaces = (
            self._create_adjacent_wall_linked_spaces(session)
        )
        sorted_spaces = self._assert_spaces_stay_distinct(created_spaces)
        initial_centers = [float(space.Shape.CenterOfMass.x) for space in sorted_spaces]
        initial_areas = [float(space.Proxy.getArea(space)) for space in sorted_spaces]

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, divider_wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)
            moved_midpoint = FreeCAD.Vector(captured["last"]).add(FreeCAD.Vector(300.0, 0.0, 0.0))
            captured["callback"](moved_midpoint, None)

        self._assert_no_wall_edit_preview_visuals(session)
        self._assert_spaces_stay_distinct(created_spaces)

        self._undo_document()
        self._assert_no_wall_edit_preview_visuals(session)

        restored_spaces = self._assert_spaces_stay_distinct(created_spaces)
        restored_centers = [float(space.Shape.CenterOfMass.x) for space in restored_spaces]
        restored_areas = [float(space.Proxy.getArea(space)) for space in restored_spaces]
        for initial_center, restored_center in zip(initial_centers, restored_centers):
            self.assertAlmostEqual(restored_center, initial_center, delta=1e-6)
        for initial_area, restored_area in zip(initial_areas, restored_areas):
            self.assertAlmostEqual(restored_area, initial_area, delta=1e-6)

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

        session.selection.state.set_pending_selected_plan_target("wall", wall)
        session.selection.sync.set_gui_selection([wall, space])
        session.selection.refresh.refresh_primary_selected_plan_target()

        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())
        self.assertTrue(session.spaces.activate_space_tool())
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Pick Space Region")
        self.assertEqual(len(session.space_region_pick_state.candidates), 2)

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

        self.assertTrue(session.spaces.start_space_region_pick(boundaries, label="Two Rooms"))
        self.pump_gui_events()

        created_spaces = [
            obj
            for obj in self.document.Objects
            if obj.Name not in before and Draft.getType(obj) == "Space"
        ]
        self.assertEqual(len(created_spaces), 1)
        created_space = created_spaces[0]

        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), created_space)
        self.assertEqual(len(session.space_region_pick_state.candidates), 0)
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
        session.selection.refresh.refresh_primary_selected_plan_target()

        with (
            patch("FreeCAD.Console.PrintError") as print_error,
            patch("FreeCAD.Console.PrintWarning") as print_warning,
        ):
            self.assertFalse(session.spaces.activate_space_tool())
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
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)

        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)

        self.assertTrue(session.spaces.add_boundaries_to_selected_space())
        boundaries = session.spaces.get_space_boundary_entries(space)
        self.assertEqual(len(boundaries), 1)
        self.assertIs(boundaries[0][0], wall)

        self.assertTrue(session.spaces.remove_selected_space_boundaries())
        self.assertEqual(session.spaces.get_space_boundary_entries(space), [])

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
        session.selection.refresh.refresh_primary_selected_plan_target()

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
            patch.object(session.picking, "pick_edit_node", return_value=None),
            patch.object(
                session.picking,
                "pick",
                return_value=("space", space),
            ),
        ):
            session.input.on_mouse_pressed(self._make_fake_left_mouse_press())

        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [space.Name])

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session.picking,
                "pick_edit_node",
                return_value=None,
            ),
            patch.object(
                session.picking,
                "pick",
                return_value=("wall", wall),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self.assertIs(session.selection.state.get_selected_target_for_kind("space"), space)
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("wall"))
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [space.Name, wall.Name],
        )
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("space", space))
        self.assertEqual(
            session.selection.state.get_secondary_selected_plan_targets(), [("wall", wall)]
        )
        self.assertGreater(len(session.overlay_tracker_state.secondary_selection_trackers), 0)
        self.assertIn("Boundary candidates: 1 wall", session.task_panel.status.text())

        self.assertTrue(session.spaces.add_boundaries_to_selected_space())
        self.pump_gui_events()
        boundaries = session.spaces.get_space_boundary_entries(space)
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0][0], wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()


class TestBimPlanEditGuiSpaces(BimPlanEditGuiSpacesMixin, BimPlanEditGuiBase):
    """Space and region Plan Edit GUI suite."""

    pass

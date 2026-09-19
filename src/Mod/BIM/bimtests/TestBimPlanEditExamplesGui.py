# SPDX-License-Identifier: LGPL-2.1-or-later

"""End-to-end GUI checks for the generated BIM Plan Edit examples."""

import os
import tempfile
from unittest.mock import patch

import ArchRepresentation
import FreeCAD
import FreeCADGui
import Part
from pivy import coin
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession


class TestBimPlanEditExamplesGui(TestArchBaseGui):
    """Treat installed example documents as executable integration fixtures."""

    def _example_path(self, filename):
        candidates = []
        source_dir = os.environ.get("FREECAD_SOURCE_DIR")
        if source_dir:
            candidates.append(os.path.join(source_dir, "data", "examples", filename))
        candidates.append(os.path.join(FreeCAD.getResourceDir(), "examples", filename))
        path = next((item for item in candidates if os.path.isfile(item)), candidates[-1])
        self.assertTrue(os.path.isfile(path), f"Plan Edit example is missing: {path}")
        return path

    def _open_example(self, filename, keep_startup_activity=False):
        FreeCAD.closeDocument(self.document.Name)
        self.document = FreeCAD.openDocument(self._example_path(filename))
        FreeCAD.setActiveDocument(self.document.Name)
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.document.Name)
        self.document.UndoMode = 1
        self.pump_gui_events()
        if not keep_startup_activity:
            from bimplan.runtime.session import get_active_session

            session = get_active_session()
            if session is not None:
                session.shutdown(close_dialog=False)
                self.pump_gui_events()
        return self.document

    @staticmethod
    def _objects_with_ifc_type(document, ifc_type):
        return [obj for obj in document.Objects if getattr(obj, "IfcType", "") == ifc_type]

    def _enter_plan_edit(self, storey):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(storey)
        session = PlanEditSession()
        self.assertTrue(session.enter())
        self.assertIs(session.active_storey, storey)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.pump_gui_events()
        return session

    def test_basic_example_restores_document_startup_context(self):
        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        gui_startup = document.settings("Gui.Startup")
        bim_startup = document.settings("BIM.Startup")
        self.assertEqual(1, gui_startup.getInt("SchemaVersion", 0))
        self.assertEqual("BIMWorkbench", gui_startup.getString("Workbench", ""))
        self.assertEqual(1, bim_startup.getInt("SchemaVersion", 0))
        self.assertEqual("PlanEdit", bim_startup.getString("Activity", ""))
        self.assertEqual("BIMWorkbench", FreeCADGui.activeWorkbench().name())

        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.assertIsNone(session.task_panel)
        context = document.getObject(bim_startup.getString("ContextObject", ""))
        definition = document.getObject(bim_startup.getString("ViewObject", ""))
        self.assertIs(session.active_storey, context)
        self.assertTrue(definition.isDerivedFrom("App::ViewDefinition"))
        self.assertTrue(definition.BIMIsActiveView)
        self.addCleanup(session.shutdown, close_dialog=False)

    def test_basic_example_populates_plan_session_after_presentation_reveal(self):
        from bimplan.runtime.session import BIMEditingSession

        main_window = FreeCADGui.getMainWindow()
        phase_gate_states = []
        original_prepare = BIMEditingSession.prepare
        original_populate = BIMEditingSession.populate

        def record_prepare(session):
            phase_gate_states.append(("prepare", main_window.isPresentationFrozen()))
            return original_prepare(session)

        def record_populate(session, *args, **kwargs):
            phase_gate_states.append(("populate", main_window.isPresentationFrozen()))
            return original_populate(session, *args, **kwargs)

        with patch.object(BIMEditingSession, "prepare", record_prepare), patch.object(
            BIMEditingSession, "populate", record_populate
        ):
            self._open_example("BIMPlanEditBasic.FCStd", keep_startup_activity=True)

        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.assertIn(("prepare", True), phase_gate_states)
        self.assertIn(("populate", False), phase_gate_states)
        self.assertLess(
            phase_gate_states.index(("prepare", True)),
            phase_gate_states.index(("populate", False)),
        )

    def test_basic_example_startup_builds_every_wall_pick_target(self):
        """GUI restore completion must build the complete semantic wall layer."""

        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.pump_gui_events(250)
        self.assertTrue(session.contextual_rendering.is_ready)

        renderer = session.contextual_rendering.renderer
        walls = self._objects_with_ifc_type(document, "Wall")
        self.assertEqual(set(walls), set(walls).intersection(renderer.sources))
        for wall in walls:
            resolved = set()
            representation = renderer._representations[wall]
            for geometry in representation.cut_geometry:
                mesh = representation.face_mesh_for(geometry)
                if mesh is None:
                    continue
                for triangle in mesh.triangles:
                    point = sum(
                        (FreeCAD.Vector(mesh.vertices[index]) for index in triangle),
                        FreeCAD.Vector(),
                    ) / 3.0
                    screen = session.view.getPointOnScreen(point)
                    target = session.picking.pick(screen)
                    if target is not None:
                        resolved.add(target.obj)
            self.assertIn(wall, resolved, wall.Name)

    def test_basic_example_plan_view_hides_section_plane_markers(self):
        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        markers = [
            obj
            for obj in document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", "") == "SectionPlane"
        ]
        self.assertTrue(markers)
        for marker in markers:
            self.assertEqual("Hidden", session.view.getViewVisibility(marker), marker.Name)
            self.assertTrue(marker.ViewObject.Visibility, marker.Name)

        view = session.view
        session.shutdown(close_dialog=False)
        for marker in markers:
            self.assertEqual("Inherit", view.getViewVisibility(marker), marker.Name)
            self.assertTrue(marker.ViewObject.Visibility, marker.Name)

    def test_basic_example_door_uses_semantic_plan_symbol(self):
        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.pump_gui_events(100)
        door = next(obj for obj in document.Objects if getattr(obj, "IfcType", "") == "Door")
        host = door.Hosts[0]
        wall_representation = session.contextual_rendering.renderer._representations[host]
        representation = session.overlays.geometry.get_opening_representation(door)
        self.assertIn(
            "OpeningSymbol",
            {mapping.role for mapping in representation.source_mappings},
        )
        self.assertEqual("Hidden", session.view.getViewVisibility(host))
        self.assertEqual("Hidden", session.view.getViewVisibility(door))
        self.assertTrue(host.ViewObject.Visibility)
        self.assertTrue(door.ViewObject.Visibility)

        model = wall_representation.analytic_model
        self.assertIsNotNone(model)
        self.assertEqual(1, len(model.opening_intervals))
        lower, upper = model.opening_intervals[0]
        axis = model.recipe.axis_end.sub(model.recipe.axis_start)
        axis.normalize()
        section = model.recipe.section
        doorway = model.recipe.axis_start.add(axis * ((lower + upper) * 0.5))
        doorway = doorway.add(
            model.recipe.lateral * ((section.y_min + section.y_max) * 0.5)
        )
        doorway.z = model.target_z
        self.assertFalse(
            any(face.isInside(doorway, 1e-7, True) for face in wall_representation.cut_geometry)
        )

    def test_basic_example_hover_resolves_last_coin_mouse_move(self):
        """A throttled final Coin move must still hover each vertical wall."""

        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.pump_gui_events(250)

        walls = self._objects_with_ifc_type(document, "Wall")
        y_oriented_walls = sorted(
            (
                wall
                for wall in walls
                if wall.Shape.BoundBox.YLength > wall.Shape.BoundBox.XLength
            ),
            key=lambda wall: wall.Shape.BoundBox.Center.x,
        )
        vertical_walls = (y_oriented_walls[0], y_oriented_walls[-1])
        horizontal_wall = next(
            wall
            for wall in walls
            if wall.Shape.BoundBox.XLength > wall.Shape.BoundBox.YLength
        )
        self.assertGreaterEqual(len(y_oriented_walls), 2)

        def event_pixel_for(wall):
            representation = session.contextual_rendering.renderer._representations[wall]
            for geometry in representation.cut_geometry:
                mesh = representation.face_mesh_for(geometry)
                if mesh is None:
                    continue
                for triangle in mesh.triangles:
                    point = sum(
                        (FreeCAD.Vector(mesh.vertices[index]) for index in triangle),
                        FreeCAD.Vector(),
                    ) / 3.0
                    screen = session.view.getPointOnScreen(point)
                    target = session.picking.pick(screen)
                    if target is not None and target.obj is wall:
                        return screen
            self.fail(f"No visible semantic pick point for {wall.Name}")

        event_manager = session.view.getViewer().getSoEventManager()

        def send_move(pixel):
            event = coin.SoLocation2Event()
            event.setPosition(coin.SbVec2s(round(pixel[0]), round(pixel[1])))
            event_manager.processEvent(event)

        lead_in = event_pixel_for(horizontal_wall)
        for wall in vertical_walls:
            session.hover_pick_state.last_time = 0.0
            send_move(lead_in)
            send_move(event_pixel_for(wall))
            self.assertTrue(
                self.pump_gui_events_until(
                    lambda: session.selection.hover.get_hovered_plan_target().obj is wall,
                )
            )

    def test_basic_example_loads_and_renders_semantically(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        walls = self._objects_with_ifc_type(document, "Wall")
        doors = self._objects_with_ifc_type(document, "Door")
        windows = self._objects_with_ifc_type(document, "Window")
        spaces = self._objects_with_ifc_type(document, "Space")
        storeys = self._objects_with_ifc_type(document, "Building Storey")
        joints = [
            obj
            for obj in document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(5, len(walls))
        self.assertEqual(1, len(doors))
        self.assertEqual(1, len(windows))
        self.assertEqual(100, doors[0].Opening)
        self.assertEqual(1, len(spaces))
        self.assertEqual(1, len(storeys))
        self.assertEqual(6, len(joints))
        definitions = [
            obj for obj in document.Objects if obj.isDerivedFrom("App::ViewDefinition")
        ]
        from bimsheets import BIMSheetService

        sheets = [obj for obj in document.Objects if BIMSheetService.is_sheet(obj)]
        self.assertEqual(1, len(sheets))
        self.assertEqual("G-001", sheets[0].SheetNumber)
        self.assertEqual("Ground Floor Plan", sheets[0].SheetTitle)
        drawing_views = [
            obj
            for obj in sheets[0].Views
            if obj.isDerivedFrom("TechDraw::DrawViewArch")
        ]
        self.assertEqual(1, len(drawing_views))
        self.assertEqual(
            "Plan",
            drawing_views[0].BIMViewDefinition.Purpose,
        )
        self.assertIn('stroke-linecap="butt"', drawing_views[0].Symbol)
        self.assertNotIn('stroke-linecap="square"', drawing_views[0].Symbol)
        from bimviews.navigator_model import BIMNavigatorModel

        project_nodes = BIMNavigatorModel(document).project_nodes()
        building_node = next(node for node in project_nodes if node.kind == "Building")
        self.assertEqual(
            (storeys[0],), tuple(node.object for node in building_node.children)
        )
        pending_nodes = list(project_nodes)
        section_nodes = []
        while pending_nodes:
            node = pending_nodes.pop(0)
            pending_nodes.extend(node.children)
            if node.kind == "SectionPlane":
                section_nodes.append(node)
        self.assertEqual(
            ("Editable Section",),
            tuple(node.object.Label for node in section_nodes),
        )
        self.assertEqual(
            {"Model", "Plan", "Section", "Elevation"},
            {definition.Purpose for definition in definitions},
        )
        section_view = next(item for item in definitions if item.Purpose == "Section")
        section_plane = section_view.BIMContextSource
        self.assertEqual("Section", section_plane.Purpose)
        self.assertEqual("Editable Section", section_plane.Label)
        self.assertEqual(section_plane.Placement, section_view.ReferenceFrame)
        self.assertEqual(
            set(walls + doors + windows),
            set(section_plane.Objects),
        )
        elevation_view = next(item for item in definitions if item.Purpose == "Elevation")
        elevation_plane = elevation_view.BIMContextSource
        self.assertEqual("Elevation", elevation_plane.Purpose)
        self.assertEqual("South Elevation Marker", elevation_plane.Label)
        self.assertGreater(elevation_plane.Depth.Value, 0.0)
        self.assertEqual(
            set(walls + doors + windows + spaces),
            set(elevation_plane.Objects),
        )

        from bimviews.service import BIMViewService

        plan_view = next(item for item in definitions if item.Purpose == "Plan")
        scope = BIMViewService(document).scope_for(plan_view)
        categories = {category.key: category for category in scope.categories}
        self.assertEqual(5, len(categories["Walls"].objects))
        self.assertEqual(1, len(categories["Doors"].objects))
        self.assertEqual(1, len(categories["Windows"].objects))
        self.assertEqual(1, len(categories["Spaces"].objects))
        self.assertEqual(4, sum(joint.JointType == "Miter" for joint in joints))
        self.assertEqual(2, sum(joint.JointType == "Tee" for joint in joints))
        self.assertTrue(
            all(joint.Status == "OK" for joint in joints),
            [(joint.Label, joint.Status, joint.StatusMessage) for joint in joints],
        )
        for wall in walls:
            self.assertIsInstance(wall.Proxy._resolved_geometry_signatures, dict)
            self.assertFalse(wall.Proxy._invalidating_wall_relations)
            wall.touch()
        document.recompute()
        self.assertTrue(all(not wall.Shape.isNull() for wall in walls))
        for opening in doors + windows:
            self.assertTrue(opening.WindowParts)
            self.assertGreater(len(opening.Shape.Solids), 1)
            self.assertEqual(len(opening.Hosts), 1)
            host = opening.Hosts[0]
            subvolume = opening.Proxy.getSubVolume(opening, host=host)
            self.assertIsNotNone(subvolume)
            self.assertAlmostEqual(
                host.Shape.common(subvolume, noElementMap=True).Volume, 0.0, delta=1e-6
            )
        space_bounds = spaces[0].Shape.BoundBox
        self.assertAlmostEqual(walls[3].Shape.BoundBox.XMax, space_bounds.XMin)
        self.assertAlmostEqual(walls[4].Shape.BoundBox.XMin, space_bounds.XMax)
        self.assertAlmostEqual(walls[2].Shape.BoundBox.YMax, space_bounds.YMin)
        self.assertAlmostEqual(walls[0].Shape.BoundBox.YMin, space_bounds.YMax)

        session = self._enter_plan_edit(storeys[0])
        self.assertTrue(
            all(wall in session.contextual_rendering.renderer.sources for wall in walls)
        )
        self.assertTrue(
            all(
                session.contextual_rendering.renderer._representations[wall].analytic_model
                is not None
                for wall in walls
            )
        )
        self.assertGreater(session.contextual_rendering.renderer.root.getNumChildren(), 0)

    def test_basic_example_elevation_lifecycle_survives_edit_and_reopen(self):
        """Saved elevations remain editable, cacheable, and sheet-compatible."""

        document = self._open_example("BIMPlanEditBasic.FCStd")
        definitions = [
            obj for obj in document.Objects if obj.isDerivedFrom("App::ViewDefinition")
        ]
        model_view = next(item for item in definitions if item.Purpose == "Model")
        plan_view = next(item for item in definitions if item.Purpose == "Plan")
        elevation_view = next(item for item in definitions if item.Purpose == "Elevation")

        from bimcommands.BimViews import _apply_representation_request
        from bimcontextual.session import active_session as active_contextual_session
        from bimviews.service import BIMViewService

        view = FreeCADGui.ActiveDocument.ActiveView
        service = BIMViewService(
            document,
            view=view,
            representation_applier=_apply_representation_request,
        )
        service.activate_view(plan_view)
        self.pump_gui_events(40)
        from bimplan.runtime.session import get_active_session

        self.assertIsNotNone(get_active_session())

        service.activate_view(elevation_view)
        self.pump_gui_events(80)
        elevation_session = active_contextual_session()
        self.assertIsNotNone(elevation_session)
        self.assertEqual(
            ArchRepresentation.RepresentationPurpose.ELEVATION,
            elevation_session.request.purpose,
        )
        self.assertTrue(elevation_session.renderer.render_representation)
        self.assertTrue(elevation_session.renderer.replace_source)
        walls = self._objects_with_ifc_type(document, "Wall")
        self.assertTrue(all(wall in elevation_session.renderer._representations for wall in walls))
        self.assertTrue(
            any(
                elevation_session.renderer._representations[wall].projected_geometry
                for wall in walls
            )
        )

        wall = walls[0]
        old_height = wall.Height.Value
        wall.Height = old_height + 25.0
        document.recompute()
        service.activate_view(elevation_view)
        self.pump_gui_events(40)
        self.assertAlmostEqual(old_height + 25.0, wall.Height.Value)
        elevation_session = active_contextual_session()
        self.assertTrue(
            elevation_session.renderer._representations[wall].projected_geometry
        )

        marker = elevation_view.BIMContextSource
        original_depth = marker.Depth.Value
        marker.Depth = original_depth + 250.0
        marker_placement = FreeCAD.Placement(marker.Placement)
        marker_placement.Base.x += 100.0
        marker.Placement = marker_placement
        marker.ShowSilhouettes = False
        marker.VisibleLineWidth = 1.8
        marker.SilhouetteLineWidth = 2.4
        document.recompute()
        service.activate_view(elevation_view)
        self.pump_gui_events(50)
        refreshed = active_contextual_session()
        self.assertEqual(
            (-marker.Depth.Value, 0.0), refreshed.request.projection_range
        )
        self.assertFalse(refreshed.request.presentation_profile["show_silhouettes"])
        self.assertEqual(1.8, refreshed.request.presentation_profile["visible_line_width"])
        self.assertEqual(2.4, refreshed.request.presentation_profile["silhouette_line_width"])

        with tempfile.TemporaryDirectory(prefix="freecad-elevation-") as directory:
            path = os.path.join(directory, "lifecycle.FCStd")
            document.saveAs(path)
            saved_name = document.Name
            FreeCAD.closeDocument(saved_name)
            reopened = FreeCAD.openDocument(path)
            self.document = reopened
            FreeCAD.setActiveDocument(reopened.Name)
            FreeCADGui.ActiveDocument = FreeCADGui.getDocument(reopened.Name)
            reopened_view = FreeCADGui.activeDocument().activeView()
            if not hasattr(reopened_view, "applyViewDefinition"):
                reopened_view = FreeCADGui.activeDocument().createView(
                    "Gui::View3DInventor"
                )
            self.assertTrue(hasattr(reopened_view, "applyViewDefinition"))
            reopened_service = BIMViewService(
                reopened,
                view=reopened_view,
                representation_applier=_apply_representation_request,
            )
            reopened_elevation = next(
                item
                for item in reopened.Objects
                if item.isDerivedFrom("App::ViewDefinition") and item.Purpose == "Elevation"
            )
            self.assertTrue(reopened_service.activate_view(reopened_elevation))
            self.pump_gui_events(100)
            reopened_session = active_contextual_session()
            self.assertIsNotNone(reopened_session)
            self.assertEqual(
                ArchRepresentation.RepresentationPurpose.ELEVATION,
                reopened_session.request.purpose,
            )
            self.assertFalse(
                reopened_session.request.presentation_profile["show_silhouettes"]
            )
            self.assertEqual(
                1.8,
                reopened_session.request.presentation_profile["visible_line_width"],
            )
            self.assertEqual(
                2.4,
                reopened_session.request.presentation_profile["silhouette_line_width"],
            )
            self.assertTrue(reopened_session.renderer._representations)

            page = reopened.addObject("TechDraw::DrawPage", "LifecycleElevationPage")
            template = reopened.addObject(
                "TechDraw::DrawSVGTemplate", "LifecycleElevationTemplate"
            )
            template.Template = (
                FreeCAD.getResourceDir()
                + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
            )
            page.Template = template
            drawing_view = reopened_service.place_on_sheet(reopened_elevation, page)
            self.assertIs(reopened_elevation, drawing_view.BIMViewDefinition)
            self.assertIn(drawing_view, page.Views)
            self.addCleanup(reopened_session.close)

    def test_basic_example_saved_section_activates_contextual_runtime(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        section_view = next(
            item
            for item in document.Objects
            if item.isDerivedFrom("App::ViewDefinition") and item.Purpose == "Section"
        )

        from bimcommands.BimViews import _apply_representation_request
        from bimcontextual.session import active_session as active_contextual_session
        from bimviews.service import BIMViewService

        service = BIMViewService(
            document,
            view=FreeCADGui.ActiveDocument.ActiveView,
            representation_applier=_apply_representation_request,
        )

        self.assertTrue(service.activate_view(section_view))
        self.pump_gui_events(80)
        session = active_contextual_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.close)
        self.assertEqual(
            ArchRepresentation.RepresentationPurpose.SECTION,
            session.request.purpose,
        )
        self.assertEqual(section_view.ReferenceFrame, session.request.reference_frame)
        self.assertTrue(session.renderer._representations)

    def test_basic_example_reuses_saved_plan_until_model_changes(self):
        """Saved Model/Plan switching retains valid viewport representations."""

        document = self._open_example("BIMPlanEditBasic.FCStd")
        definitions = [
            obj for obj in document.Objects if obj.isDerivedFrom("App::ViewDefinition")
        ]
        model_view = next(item for item in definitions if item.Purpose == "Model")
        plan_view = next(item for item in definitions if item.Purpose == "Plan")
        wall = self._objects_with_ifc_type(document, "Wall")[0]

        from bimcommands.BimViews import _apply_representation_request
        from bimplan.runtime.session import get_active_session
        from bimviews.service import BIMViewService

        view = FreeCADGui.ActiveDocument.ActiveView
        service = BIMViewService(
            document,
            view=view,
            representation_applier=_apply_representation_request,
        )
        alternate_plan = service.duplicate_view(plan_view, "Alternate Plan")
        alternate_frame = FreeCAD.Placement(plan_view.ReferenceFrame)
        alternate_frame.Base.z += 250
        alternate_plan.ReferenceFrame = alternate_frame

        service.activate_view(plan_view)
        first_session = get_active_session()
        first_renderer = first_session.contextual_rendering.renderer
        first_representation = first_renderer._representations[wall]
        first_node = first_renderer._object_nodes[wall]

        service.activate_view(model_view)
        self.pump_gui_events()
        service.activate_view(plan_view)
        second_session = get_active_session()
        second_renderer = second_session.contextual_rendering.renderer
        self.assertIs(first_renderer, second_renderer)
        self.assertIs(first_representation, second_renderer._representations[wall])
        self.assertIs(first_node, second_renderer._object_nodes[wall])

        service.activate_view(alternate_plan)
        alternate_session = get_active_session()
        alternate_renderer = alternate_session.contextual_rendering.renderer
        self.assertIsNot(first_renderer, alternate_renderer)
        self.assertEqual(
            alternate_frame,
            alternate_session.representation_request.request.reference_frame,
        )

        service.activate_view(plan_view)
        restored_session = get_active_session()
        self.assertIs(first_renderer, restored_session.contextual_rendering.renderer)

        service.activate_view(model_view)
        self.pump_gui_events()
        wall.Width = wall.Width.Value + 50
        document.recompute()
        service.activate_view(plan_view)
        changed_session = get_active_session()
        changed_renderer = changed_session.contextual_rendering.renderer
        self.assertIsNot(first_renderer, changed_renderer)
        wall_after_edit = changed_renderer._representations[wall]
        self.assertIsNot(first_representation, wall_after_edit)

        service.activate_view(model_view)
        self.pump_gui_events()
        opening = self._objects_with_ifc_type(document, "Window")[0]
        opening.Width = opening.Width.Value + 50
        document.recompute()
        service.activate_view(plan_view)
        opening_session = get_active_session()
        wall_after_opening = opening_session.contextual_rendering.renderer._representations[wall]
        self.assertIsNot(wall_after_edit, wall_after_opening)

        service.activate_view(model_view)
        self.pump_gui_events()
        joint = next(
            obj
            for obj in document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
            and wall in (obj.WallA, obj.WallB)
        )
        joint.Enabled = False
        document.recompute()
        service.activate_view(plan_view)
        joint_session = get_active_session()
        wall_after_joint = joint_session.contextual_rendering.renderer._representations[wall]
        self.assertIsNot(wall_after_opening, wall_after_joint)
        self.addCleanup(joint_session.shutdown, close_dialog=False)

    def test_basic_example_refreshes_active_plan_geometry_and_picking(self):
        """A recompute keeps the active Plan layer and semantic picking in sync."""

        document = self._open_example(
            "BIMPlanEditBasic.FCStd", keep_startup_activity=True
        )
        from bimplan.runtime.session import get_active_session

        session = get_active_session()
        self.assertIsNotNone(session)
        self.addCleanup(session.shutdown, close_dialog=False)
        wall = self._objects_with_ifc_type(document, "Wall")[-1]
        renderer = session.contextual_rendering.renderer
        original = renderer._representations[wall]
        original_bounds = tuple(
            (geometry.BoundBox.XLength, geometry.BoundBox.YLength)
            for geometry in original.cut_geometry
            if getattr(geometry, "ShapeType", "") == "Face"
        )
        wall.Width = wall.Width.Value + 50
        document.recompute()
        self.pump_gui_events()

        refreshed = renderer._representations[wall]
        face = next(
            geometry
            for geometry in refreshed.cut_geometry
            if getattr(geometry, "ShapeType", "") == "Face"
        )
        refreshed_bounds = tuple(
            (geometry.BoundBox.XLength, geometry.BoundBox.YLength)
            for geometry in refreshed.cut_geometry
            if getattr(geometry, "ShapeType", "") == "Face"
        )
        self.assertNotEqual(original_bounds, refreshed_bounds)
        mesh = refreshed.face_mesh_for(face)
        vertices, triangles = mesh.vertices, mesh.triangles
        self.assertAlmostEqual(face.BoundBox.XMin, min(point.x for point in vertices))
        self.assertAlmostEqual(face.BoundBox.XMax, max(point.x for point in vertices))
        self.assertAlmostEqual(face.BoundBox.YMin, min(point.y for point in vertices))
        self.assertAlmostEqual(face.BoundBox.YMax, max(point.y for point in vertices))
        session.view.fitAll()
        self.pump_gui_events()
        mappings = []
        for triangle in triangles:
            pick_point = sum(
                (FreeCAD.Vector(vertices[index]) for index in triangle),
                FreeCAD.Vector(),
            ) / 3.0
            screen_point = session.view.getPointOnScreen(pick_point)
            mappings.append(session.contextual_rendering.pick_mapping(screen_point))
        self.assertIn(wall, {mapping.source for mapping in mappings if mapping is not None})

        # Coin events, native ray picks, and getPointOnScreen all use the same
        # viewport/device-pixel contract. Exercise it for every wall, including
        # the narrow clipped exterior walls that expose small coordinate shifts.

        for candidate in self._objects_with_ifc_type(document, "Wall"):
            candidate_representation = renderer._representations[candidate]
            candidate_hits = []
            for geometry in candidate_representation.cut_geometry:
                candidate_mesh = candidate_representation.face_mesh_for(geometry)
                if candidate_mesh is None:
                    continue
                for triangle in candidate_mesh.triangles:
                    point = sum(
                        (
                            FreeCAD.Vector(candidate_mesh.vertices[index])
                            for index in triangle
                        ),
                        FreeCAD.Vector(),
                    ) / 3.0
                    screen = session.view.getPointOnScreen(point)
                    candidate_hits.append(
                        session.contextual_rendering.pick_mapping(screen)
                    )
            self.assertIn(
                candidate,
                {mapping.source for mapping in candidate_hits if mapping is not None},
                candidate.Name,
            )

    def test_basic_example_analytic_wall_plans_match_brep_sections(self):
        """Analytic joins and opening intervals preserve the legacy Plan result."""

        document = self._open_example("BIMPlanEditBasic.FCStd")
        plan_view = next(
            obj
            for obj in document.Objects
            if obj.isDerivedFrom("App::ViewDefinition") and obj.Purpose == "Plan"
        )
        from bimplan.representation_request import representation_request_from_storey
        from bimviews.service import BIMViewService

        service = BIMViewService(document)
        request = representation_request_from_storey(service.context_source(plan_view))
        for wall in self._objects_with_ifc_type(document, "Wall"):
            representation = wall.Proxy.getRepresentation(wall, request)
            self.assertIsNotNone(representation.analytic_model, wall.Name)
            analytic_faces = tuple(representation.cut_geometry)
            analytic_boundaries = representation.analytic_model.boundaries
            self.assertEqual(len(analytic_boundaries), len(analytic_faces), wall.Name)
            for face, boundary in zip(analytic_faces, analytic_boundaries):
                mesh = representation.face_mesh_for(face)
                self.assertIsNotNone(mesh, wall.Name)
                self.assertEqual(len(boundary), len(mesh.vertices), wall.Name)
                self.assertEqual(len(boundary) - 2, len(mesh.triangles), wall.Name)
                self.assertTrue(
                    all(
                        expected.isEqual(actual, 1e-7)
                        for expected, actual in zip(boundary, mesh.vertices)
                    ),
                    wall.Name,
                )
            brep_faces = tuple(wall.Proxy._getCutRepresentation(wall, request))
            self.assertAlmostEqual(
                sum(face.Area for face in brep_faces),
                sum(face.Area for face in analytic_faces),
                delta=1e-3,
                msg=wall.Name,
            )
            analytic_bounds = Part.makeCompound(analytic_faces).BoundBox
            brep_bounds = Part.makeCompound(brep_faces).BoundBox
            for analytic_value, brep_value in zip(
                (
                    analytic_bounds.XMin,
                    analytic_bounds.XMax,
                    analytic_bounds.YMin,
                    analytic_bounds.YMax,
                ),
                (brep_bounds.XMin, brep_bounds.XMax, brep_bounds.YMin, brep_bounds.YMax),
            ):
                self.assertAlmostEqual(brep_value, analytic_value, delta=1e-4, msg=wall.Name)

    def test_basic_example_wall_edit_roundtrips(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        wall = self._objects_with_ifc_type(document, "Wall")[0]
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._enter_plan_edit(storey)
        handle = next(
            item
            for item in session.contextual_rendering.edit_handles_for(wall)
            if item.role == "WallWidth"
        )
        width = wall.Width.Value
        session.contextual_editing.begin(handle)
        result = session.contextual_editing.commit(handle.point + handle.direction * 50)
        self.assertTrue(result.success)
        self.assertAlmostEqual(width + 50, wall.Width.Value)
        document.undo()
        self.assertAlmostEqual(width, wall.Width.Value)

    def test_basic_example_coin_drag_survives_refresh_undo_and_reentry(self):
        """Exercise the real Coin/Draft drag lifecycle on the installed fixture."""

        import DraftGui
        from bimplan.selection import edit_nodes as plan_edit_nodes
        from draftguitools import gui_snapper

        document = self._open_example("BIMPlanEditBasic.FCStd")
        wall = self._objects_with_ifc_type(document, "Wall")[0]
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        original_width = wall.Width.Value
        created_toolbar = not hasattr(FreeCADGui, "draftToolBar")
        if created_toolbar:
            FreeCADGui.draftToolBar = DraftGui.DraftToolBar()
        created_snapper = not hasattr(FreeCADGui, "Snapper")
        if created_snapper:
            FreeCADGui.Snapper = gui_snapper.Snapper()

        session = self._enter_plan_edit(storey)
        try:
            event_manager = session.viewer.getSoEventManager()

            def send_move(point):
                event = coin.SoLocation2Event()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event_manager.processEvent(event)

            def send_button(point, state):
                event = coin.SoMouseButtonEvent()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event.setButton(coin.SoMouseButtonEvent.BUTTON1)
                event.setState(state)
                event_manager.processEvent(event)

            for offset in (35.0, 55.0, 40.0):
                session.selection.state.set_selected_plan_target_state("wall", wall)
                session.contextual_rendering.sync_visible_handles()
                session.viewport.flush_scene_graph_mutations()
                session.view.fitAll()
                self.pump_gui_events()
                handle = next(
                    item
                    for item in session.contextual_rendering.edit_handles_for(wall)
                    if item.subelement == "Width.PositiveFace"
                )
                start = session.view.getPointOnScreen(handle.point)
                target = session.view.getPointOnScreen(handle.point + handle.direction * offset)
                self.assertIs(handle, session.contextual_rendering.pick_edit_handle(start))

                edit_node = handle
                send_move(start)
                self.pump_gui_events(20)
                with patch.object(session.picking, "pick_edit_node", return_value=edit_node):
                    send_button(start, coin.SoButtonEvent.DOWN)
                send_button(start, coin.SoButtonEvent.UP)
                self.pump_gui_events(20)
                self.assertIsNotNone(session.contextual_editing.editor)

                world_target = handle.point + handle.direction * offset
                with patch.object(FreeCADGui.Snapper, "snap", return_value=world_target):
                    send_move(target)
                self.pump_gui_events(20)
                send_button(target, coin.SoButtonEvent.DOWN)
                send_button(target, coin.SoButtonEvent.UP)
                self.pump_gui_events(50)
                self.assertIsNone(session.contextual_editing.editor)
                self.assertAlmostEqual(original_width + offset, wall.Width.Value)

                document.undo()
                document.recompute()
                self.pump_gui_events(30)
                self.assertAlmostEqual(original_width, wall.Width.Value)

            session.shutdown(close_dialog=False)
            self.pump_gui_events(50)
            session = self._enter_plan_edit(storey)
            self.assertIn(wall, session.contextual_rendering.renderer.sources)
            session.selection.state.set_selected_plan_target_state("wall", wall)
            session.contextual_rendering.sync_visible_handles()
            session.viewport.flush_scene_graph_mutations()
            self.assertTrue(session.contextual_rendering.edit_handles_for(wall))
        finally:
            session.shutdown(close_dialog=False)
            if created_snapper:
                del FreeCADGui.Snapper
            if created_toolbar:
                del FreeCADGui.draftToolBar

    def test_basic_example_opening_handles_drive_real_coin_edits(self):
        """Move, resize and flip a hosted door through its semantic Coin handles."""

        import ArchWindow
        import ArchRepresentation
        import DraftGui
        from bimplan.selection import edit_nodes as plan_edit_nodes
        from draftguitools import gui_snapper

        document = self._open_example("BIMPlanEditBasic.FCStd")
        door = self._objects_with_ifc_type(document, "Door")[0]
        space = self._objects_with_ifc_type(document, "Space")[0]
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        host = door.Hosts[0]
        created_toolbar = not hasattr(FreeCADGui, "draftToolBar")
        if created_toolbar:
            FreeCADGui.draftToolBar = DraftGui.DraftToolBar()
        created_snapper = not hasattr(FreeCADGui, "Snapper")
        if created_snapper:
            FreeCADGui.Snapper = gui_snapper.Snapper()

        session = self._enter_plan_edit(storey)
        try:
            event_manager = session.viewer.getSoEventManager()

            def send_move(point):
                event = coin.SoLocation2Event()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event_manager.processEvent(event)

            def send_button(point, state):
                event = coin.SoMouseButtonEvent()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event.setButton(coin.SoMouseButtonEvent.BUTTON1)
                event.setState(state)
                event_manager.processEvent(event)

            def select_and_sync():
                session.selection.state.set_selected_plan_target_state("opening", door)
                session.contextual_rendering.sync_visible_handles()
                session.viewport.flush_scene_graph_mutations()
                session.view.fitAll()
                self.pump_gui_events(30)
                return session.contextual_rendering.edit_handles_for(door)

            handles = select_and_sync()
            self.assertEqual(
                {
                    "OpeningPosition",
                    "OpeningLeftJamb",
                    "OpeningRightJamb",
                    "OpeningFlipHinge",
                    "OpeningFlipDirection",
                },
                {handle.role for handle in handles},
            )
            action_icons = {
                "OpeningFlipHinge": "BIM_OpeningFlipHinge",
                "OpeningFlipDirection": "BIM_OpeningFlipDirection",
            }
            for handle in handles:
                if handle.role in action_icons:
                    self.assertEqual("Icon", handle.glyph)
                    self.assertEqual(18, handle.glyph_size)
                    self.assertEqual(action_icons[handle.role], handle.icon_name)
            handle_switch = session.contextual_rendering.renderer._handle_switches[door]
            icon_nodes = []
            self.assertEqual(len(handles), handle_switch.getNumChildren())
            for index, handle in enumerate(handles):
                node = handle_switch.getChild(index)
                if handle.role in action_icons:
                    self.assertEqual(action_icons[handle.role], node.iconName.getValue())
                    search = coin.SoSearchAction()
                    search.setType(coin.SoImage.getClassTypeId())
                    search.apply(node)
                    self.assertIsNotNone(search.getPath())
                    image = search.getPath().getTail()
                    self.assertFalse(image.image.isDefault())
                    icon_nodes.append(node)
            self.assertEqual(2, len(icon_nodes))

            session.selection.state.set_selected_plan_target_state("wall", host)
            session.contextual_rendering.sync_visible_handles()
            session.viewport.flush_scene_graph_mutations()
            wall_width_handle = next(
                handle
                for handle in session.contextual_rendering.edit_handles_for(host)
                if handle.subelement == "Width.PositiveFace"
            )
            original_host_width = host.Width.Value
            semantic_state = wall_width_handle.operation.get_preview(
                host,
                original_host_width + 25.0,
                session.representation_request.request,
            )
            ArchRepresentation.expand_preview_dependents(
                semantic_state, session.representation_request.request
            )
            space_representation = semantic_state.representation_for(space)
            self.assertIsNotNone(space_representation)
            original_space_area = sum(face.Area for face in space.Proxy.getFootprint(space))
            proposed_space_area = sum(face.Area for face in space_representation.cut_geometry)
            self.assertGreater(abs(proposed_space_area - original_space_area), 1.0)
            self.assertAlmostEqual(original_space_area, space.Area.Value)
            session.contextual_editing.begin(wall_width_handle)
            wall_preview = session.contextual_editing.preview(
                wall_width_handle.point + wall_width_handle.direction * 25.0
            )
            session.viewport.flush_scene_graph_mutations()
            renderer = session.contextual_rendering.renderer
            self.assertTrue(wall_preview.validation.allowed)
            self.assertTrue({host, door}.issubset(renderer._preview_nodes))
            self.assertTrue({host, door}.issubset(renderer._preview_replaced_sources))
            self.assertIn(space, renderer._preview_nodes)
            self.assertNotIn(space, renderer._preview_replaced_sources)
            space_preview_node = renderer._preview_nodes[space]
            self.assertGreater(space_preview_node.getNumChildren(), 0)
            self.assertAlmostEqual(original_host_width, host.Width.Value)
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(host, renderer._preview_nodes)
            self.assertNotIn(door, renderer._preview_nodes)
            self.assertNotIn(space, renderer._preview_nodes)
            self.assertAlmostEqual(original_host_width, host.Width.Value)

            session.contextual_editing.begin(wall_width_handle)
            wall_commit = session.contextual_editing.commit(
                wall_width_handle.point + wall_width_handle.direction * 25.0
            )
            session.viewport.flush_scene_graph_mutations()
            self.assertTrue(wall_commit.success, wall_commit.reason)
            self.assertAlmostEqual(original_host_width + 25.0, host.Width.Value)
            self.assertNotIn(host, renderer._preview_nodes)
            self.assertNotIn(door, renderer._preview_nodes)
            document.undo()
            document.recompute()
            self.pump_gui_events(30)
            self.assertAlmostEqual(original_host_width, host.Width.Value)

            handles = select_and_sync()
            preview_handle = next(handle for handle in handles if handle.role == "OpeningRightJamb")
            preview_width = ArchWindow.getWindowWidthMm(door)
            renderer = session.contextual_rendering.renderer
            self.assertTrue(renderer.set_edit_label(door, "Width: 900 mm", preview_handle.point))
            renderer.clear_edit_label(door)
            session.contextual_editing.begin(preview_handle)
            preview = session.contextual_editing.preview(
                preview_handle.point + preview_handle.direction * 25.0
            )
            session.viewport.flush_scene_graph_mutations()
            self.assertTrue(preview.validation.allowed)
            self.assertEqual(preview_width, ArchWindow.getWindowWidthMm(door))
            self.assertIn(door, session.contextual_rendering.renderer._preview_nodes)
            self.assertIn(host, session.contextual_rendering.renderer._preview_nodes)
            self.assertIn(space, session.contextual_rendering.renderer._preview_nodes)
            self.assertIn(host, session.contextual_rendering.renderer._preview_replaced_sources)
            self.assertNotIn(space, session.contextual_rendering.renderer._preview_replaced_sources)
            label_node = session.contextual_rendering.renderer._preview_label_nodes[door]
            search = coin.SoSearchAction()
            search.setType(coin.SoType.fromName("SoFrameLabel"))
            search.apply(label_node)
            self.assertIsNotNone(search.getPath())
            frame_label = search.getPath().getTail()
            self.assertIn("Width", frame_label.string.getValues()[0])
            self.assertGreater(
                session.contextual_rendering.renderer._preview_nodes[door].getNumChildren(),
                0,
            )
            first_wall_preview = session.contextual_rendering.renderer._preview_nodes[host]
            session.contextual_editing.preview(
                preview_handle.point + preview_handle.direction * 50.0
            )
            session.viewport.flush_scene_graph_mutations()
            self.assertIsNot(
                first_wall_preview,
                session.contextual_rendering.renderer._preview_nodes[host],
            )
            self.assertEqual(preview_width, ArchWindow.getWindowWidthMm(door))
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(door, session.contextual_rendering.renderer._preview_nodes)
            self.assertNotIn(host, session.contextual_rendering.renderer._preview_nodes)
            self.assertNotIn(space, session.contextual_rendering.renderer._preview_nodes)
            self.assertNotIn(host, session.contextual_rendering.renderer._preview_replaced_sources)
            self.assertEqual(
                coin.SO_SWITCH_ALL,
                session.contextual_rendering.renderer._object_nodes[host].whichChild.getValue(),
            )
            self.assertNotIn(door, session.contextual_rendering.renderer._preview_label_nodes)

            session.contextual_editing.begin(preview_handle)
            invalid_distance = (
                preview_handle.operation.maximum - preview_handle.operation.get_value(door) + 100.0
            )
            invalid_preview = session.contextual_editing.preview(
                preview_handle.point + preview_handle.direction * invalid_distance
            )
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(invalid_preview.validation.allowed)
            self.assertIn(door, session.contextual_rendering.renderer._preview_nodes)
            self.assertIn(host, session.contextual_rendering.renderer._preview_nodes)
            self.assertNotIn(host, session.contextual_rendering.renderer._preview_replaced_sources)
            self.assertEqual(
                coin.SO_SWITCH_ALL,
                session.contextual_rendering.renderer._object_nodes[host].whichChild.getValue(),
            )
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(door, session.contextual_rendering.renderer._preview_nodes)
            self.assertNotIn(host, session.contextual_rendering.renderer._preview_nodes)

            handles = select_and_sync()
            position_handle = next(handle for handle in handles if handle.role == "OpeningPosition")
            original_position = position_handle.operation.get_value(door)
            proposed_position = original_position + 50.0
            preview_state = position_handle.operation.get_preview(
                door,
                proposed_position,
                session.representation_request.request,
            )
            ArchRepresentation.expand_preview_dependents(
                preview_state, session.representation_request.request
            )
            expected_host_area = sum(
                face.Area for face in preview_state.representation_for(host).cut_geometry
            )
            expected_space_area = sum(
                face.Area for face in preview_state.representation_for(space).cut_geometry
            )
            original_host_area = sum(
                face.Area
                for face in host.Proxy.getRepresentation(
                    host, session.representation_request.request
                ).cut_geometry
            )
            original_space_area = sum(face.Area for face in space.Proxy.getFootprint(space))

            self.assertTrue(session.contextual_editing.begin(position_handle))
            committed_preview = session.contextual_editing.preview(
                position_handle.point + position_handle.direction * 50.0
            )
            session.viewport.flush_scene_graph_mutations()
            self.assertTrue(committed_preview.validation.allowed)
            self.assertTrue(
                {door, host, space}.issubset(session.contextual_rendering.renderer._preview_nodes)
            )
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(
                {door, host, space}.intersection(
                    session.contextual_rendering.renderer._preview_nodes
                )
            )
            self.assertAlmostEqual(original_position, position_handle.operation.get_value(door))

            self.assertTrue(session.contextual_editing.begin(position_handle))
            opening_commit = session.contextual_editing.commit(
                position_handle.point + position_handle.direction * 50.0
            )
            session.viewport.flush_scene_graph_mutations()
            document.recompute()
            self.pump_gui_events(30)
            self.assertTrue(opening_commit.success, opening_commit.reason)
            committed_host_area = sum(
                face.Area
                for face in host.Proxy.getRepresentation(
                    host, session.representation_request.request
                ).cut_geometry
            )
            committed_space_area = sum(face.Area for face in space.Proxy.getFootprint(space))
            self.assertAlmostEqual(expected_host_area, committed_host_area, delta=1e-6)
            self.assertAlmostEqual(expected_space_area, committed_space_area, delta=1e-6)
            self.assertAlmostEqual(original_space_area, space.Area.Value, delta=1e-6)

            document.undo()
            document.recompute()
            self.pump_gui_events(30)
            restored_host_area = sum(
                face.Area
                for face in host.Proxy.getRepresentation(
                    host, session.representation_request.request
                ).cut_geometry
            )
            restored_space_area = sum(face.Area for face in space.Proxy.getFootprint(space))
            self.assertAlmostEqual(original_position, position_handle.operation.get_value(door))
            self.assertAlmostEqual(original_host_area, restored_host_area, delta=1e-6)
            self.assertAlmostEqual(original_space_area, restored_space_area, delta=1e-6)
            self.assertAlmostEqual(original_space_area, space.Area.Value, delta=1e-6)

            for role, offset in (("OpeningPosition", 75.0), ("OpeningRightJamb", 50.0)):
                handles = select_and_sync()
                handle = next(item for item in handles if item.role == role)
                original_value = handle.operation.get_value(door)
                original_width = ArchWindow.getWindowWidthMm(door)
                start = session.view.getPointOnScreen(handle.point)
                world_target = handle.point + handle.direction * offset
                target = session.view.getPointOnScreen(world_target)
                self.assertIs(handle, session.contextual_rendering.pick_edit_handle(start))
                edit_node = handle
                send_move(start)
                self.pump_gui_events(20)
                with patch.object(session.picking, "pick_edit_node", return_value=edit_node):
                    send_button(start, coin.SoButtonEvent.DOWN)
                self.pump_gui_events(20)
                self.assertIsNotNone(session.contextual_editing.editor)
                with patch.object(FreeCADGui.Snapper, "snap", return_value=world_target):
                    send_move(target)
                self.pump_gui_events(20)
                self.assertAlmostEqual(original_value, handle.operation.get_value(door))
                self.assertIn(door, session.contextual_rendering.renderer._preview_nodes)
                send_button(target, coin.SoButtonEvent.DOWN)
                send_button(target, coin.SoButtonEvent.UP)
                self.pump_gui_events(50)
                self.assertIsNone(session.contextual_editing.editor)
                self.assertAlmostEqual(original_value + offset, handle.operation.get_value(door))
                if role == "OpeningRightJamb":
                    self.assertAlmostEqual(
                        original_width + offset, ArchWindow.getWindowWidthMm(door)
                    )
                subvolume = door.Proxy.getSubVolume(door, host=host)
                self.assertIsNotNone(subvolume)
                self.assertAlmostEqual(
                    host.Shape.common(subvolume, noElementMap=True).Volume, 0.0, delta=1e-6
                )

                document.undo()
                document.recompute()
                self.pump_gui_events(30)
                self.assertAlmostEqual(original_value, handle.operation.get_value(door))
                self.assertAlmostEqual(original_width, ArchWindow.getWindowWidthMm(door))

            handles = select_and_sync()
            original_parts = tuple(door.WindowParts)
            flip_handle = next(
                handle for handle in handles if handle.role == "OpeningFlipDirection"
            )
            flip_screen = session.view.getPointOnScreen(flip_handle.point)
            with patch.object(
                session.picking,
                "pick_edit_node",
                return_value=flip_handle,
            ):
                send_button(flip_screen, coin.SoButtonEvent.DOWN)
            self.pump_gui_events(40)
            self.assertNotEqual(original_parts, tuple(door.WindowParts))
            document.undo()
            document.recompute()
            self.pump_gui_events(30)
            self.assertEqual(original_parts, tuple(door.WindowParts))

            session.shutdown(close_dialog=False)
            self.pump_gui_events(50)
            session = self._enter_plan_edit(storey)
            handles = select_and_sync()
            self.assertIn("OpeningPosition", {handle.role for handle in handles})
            self.assertIn(door, session.contextual_rendering.renderer.sources)
        finally:
            session.shutdown(close_dialog=False)
            if created_snapper:
                del FreeCADGui.Snapper
            if created_toolbar:
                del FreeCADGui.draftToolBar

    def test_path_ownership_example_exposes_owner_specific_handles(self):
        document = self._open_example("BIMPlanEditPathOwnership.FCStd")
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._enter_plan_edit(storey)
        expected = {
            "Wall": ("WallPathStart", "WallPathEnd"),
            "Wall001": ("WallPathVertex1", "WallPathVertex2"),
            "Wall002": ("WallPathVertex1", "WallPathVertex2", "WallPathVertex3"),
            "Wall003": ("WallPathG0P1", "WallPathG0P2_G1P1", "WallPathG1P2"),
            "Wall004": (),
            "Wall005": (),
        }
        actual = {
            wall.Name: tuple(
                handle.role
                for handle in session.contextual_rendering.edit_handles_for(wall)
                if handle.role.startswith("WallPath")
            )
            for wall in self._objects_with_ifc_type(document, "Wall")
        }
        self.assertEqual(expected, actual)
        line_wall = document.getObject("Wall001")
        line_handles = session.contextual_rendering.edit_handles_for(line_wall)
        self.assertEqual(
            {"WallStretchStart", "WallStretchEnd", "WallMove"},
            {
                handle.operation.interaction_intent
                for handle in line_handles
                if handle.operation.interaction_intent
            },
        )

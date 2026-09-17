# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI-facing tests for the BIM Navigator service seam."""

from types import SimpleNamespace
from unittest.mock import patch

import ArchRepresentation
import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

from bimcommands.BimViews import (
    _apply_representation_request,
    _findModelDock,
    placeInComboView,
    restoreComboViewTitle,
)
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimviews.model import BIMViewManagerModel
from bimviews.navigator_model import BIMNavigatorModel
from bimviews.navigator_qt import BIMNavigatorQtModel
from bimviews.ruler_model import RulerTransform, engineering_interval, format_metric, tick_values
from bimviews.service import BIMViewService
from bimviews.viewport_ruler import ViewportRulerOverlay, _ViewportEventFilter


class _RecordingView:
    def __init__(self, calls):
        self.calls = calls

    def captureViewDefinition(self, definition):
        self.calls.append(("capture", definition))
        definition.CameraCodec = "CoinCamera"
        definition.CameraVersion = 1
        definition.CameraPayload = "camera"
        return True

    def applyViewDefinition(self, definition):
        self.calls.append(("apply", definition))
        return True

    def setCameraType(self, camera_type):
        self.calls.append(("camera-type", camera_type))

    def setCameraOrientation(self, orientation):
        self.calls.append(("camera-orientation", orientation))

    def viewTop(self):
        self.calls.append(("view-top", None))

    def fitAll(self):
        self.calls.append(("fit", None))


class TestBimViewsServiceGui(TestArchBaseGui):
    def test_plan_saved_view_activation_starts_shared_editing_runtime(self):
        source = SimpleNamespace()
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            source=source,
        )
        calls = []
        representation = SimpleNamespace(
            set_source=lambda value, fit=False: calls.append(("source", value, fit))
        )
        fake_session = SimpleNamespace(representation_request=representation)

        with patch("bimplan.runtime.session.get_active_session", return_value=None):
            with patch(
                "bimplan.runtime.session.start_editing_session",
                return_value=fake_session,
            ) as start:
                self.assertIs(fake_session, _apply_representation_request(request))

        start.assert_called_once_with(show_task_panel=False)
        self.assertEqual([("source", source, False)], calls)

    def test_navigator_tabs_with_model_and_restores_combo_title(self):
        main_window = FreeCADGui.getMainWindow()
        combo = _findModelDock(main_window)
        self.assertIsNotNone(combo)
        original_title = combo.windowTitle()
        navigator = QtGui.QDockWidget()
        navigator.setObjectName("BIM Navigator Test")
        main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, navigator)
        try:
            placeInComboView(navigator)

            self.assertEqual("BIM Navigator", navigator.windowTitle())
            self.assertEqual("Model", combo.windowTitle())
            self.assertIn(navigator, main_window.tabifiedDockWidgets(combo))
        finally:
            restoreComboViewTitle()
            main_window.removeDockWidget(navigator)
            navigator.deleteLater()
        self.assertEqual(original_title, combo.windowTitle())

    def test_ruler_uses_engineering_intervals(self):
        self.assertEqual(100.0, engineering_interval(0.8))
        self.assertEqual(200.0, engineering_interval(1.1))
        self.assertEqual(500.0, engineering_interval(3.0))
        self.assertEqual(1000.0, engineering_interval(8.0))

    def test_ruler_transform_supports_directed_view_axes(self):
        transform = RulerTransform(
            -1000.0, 4000.0, 3000.0, -2000.0, 500.0, 500.0, 10.0
        )

        self.assertEqual(1000.0, transform.major_interval)
        self.assertAlmostEqual(1500.0, transform.x_at_pixel(250.0))
        self.assertAlmostEqual(500.0, transform.y_at_pixel(250.0))
        self.assertAlmostEqual(100.0, transform.pixel_for_x(0.0))
        self.assertEqual((-1000.0, 0.0, 1000.0), tick_values(-1100.0, 1100.0, 1000.0))
        self.assertEqual("3.482 m", format_metric(3482.0, cursor=True))
        self.assertEqual("100 mm", format_metric(100.0, 100.0))
        self.assertEqual("0 mm", format_metric(0.0, 100.0))

    def test_ruler_overlay_paints_ticks_and_cursor(self):
        host = QtGui.QWidget()
        host.resize(640, 480)
        transform = RulerTransform(0.0, 5000.0, 4000.0, 0.0, 640.0, 480.0, 8.0)
        overlay = ViewportRulerOverlay(host, lambda: transform)
        try:
            overlay.refresh_transform()
            overlay.set_cursor_position((320, 240))
            image = QtGui.QImage(640, 480, QtGui.QImage.Format_ARGB32)
            image.fill(0)

            overlay.render(image)

            self.assertFalse(image.isNull())
            self.assertEqual(
                QtGui.QColor(*ViewportRulerOverlay.BAND_COLOR), image.pixelColor(100, 10)
            )
        finally:
            overlay.close()

    def test_left_cursor_measure_fits_long_values(self):
        host = QtGui.QWidget()
        host.resize(640, 480)
        transform = RulerTransform(
            0.0, 5000.0, 12000.0, -12000.0, 640.0, 480.0, 50.0
        )
        overlay = ViewportRulerOverlay(host, lambda: transform)
        image = QtGui.QImage(640, 480, QtGui.QImage.Format_ARGB32)
        painter = QtGui.QPainter(image)
        try:
            overlay.set_cursor_position((320, 479))
            rect = overlay._vertical_cursor_rect(painter, transform, 479)
            label = overlay._cursor_label(transform.y_at_pixel(479))
            required_width = painter.fontMetrics().horizontalAdvance(label) + 10

            self.assertGreaterEqual(rect.width(), required_width)
            self.assertLessEqual(rect.bottom(), overlay.height())
        finally:
            painter.end()
            overlay.close()

    def test_ruler_maps_sibling_viewport_without_parent_warning(self):
        host = QtGui.QWidget()
        host.resize(640, 480)
        viewport = QtGui.QWidget(host)
        viewport.setGeometry(46, 28, 594, 452)
        transform = RulerTransform(
            0.0, 5000.0, 4000.0, 0.0, 594.0, 452.0, 8.0
        )
        overlay = ViewportRulerOverlay(host, lambda: transform, viewport)
        try:
            self.assertEqual((46, 28), overlay._content_origin())
        finally:
            overlay.close()

    def test_ruler_ignores_parent_mouse_coordinates(self):
        graphics_view = QtGui.QWidget()
        viewport = QtGui.QWidget(graphics_view)
        overlay = ViewportRulerOverlay(graphics_view, lambda: None, viewport)
        controller = SimpleNamespace(
            overlay=overlay,
            host_widget=viewport,
        )
        event_filter = _ViewportEventFilter(controller)
        try:
            event_filter.eventFilter(
                graphics_view, QtCore.QEvent(QtCore.QEvent.MouseMove)
            )
            self.assertIsNone(overlay.cursor_position)
        finally:
            overlay.close()

    def test_saved_views_are_grouped_separately_from_project_context(self):
        model_view = self.document.addObject("App::ViewDefinition", "ModelView")
        model_view.Label = "Default 3D"
        model_view.Purpose = "Model"
        plan_view = self.document.addObject("App::ViewDefinition", "PlanView")
        plan_view.Label = "Ground Floor"
        plan_view.Purpose = "Plan"

        groups = BIMViewManagerModel(self.document).saved_view_groups()

        self.assertEqual(("Plan", "Model"), tuple(group.key for group in groups))
        self.assertEqual((plan_view,), groups[0].views)
        self.assertEqual((model_view,), groups[1].views)

    def test_navigator_exposes_stable_virtual_sections(self):
        sections = BIMNavigatorModel(self.document).sections()

        self.assertEqual(
            ("Project", "Views", "CurrentView", "Sheets"),
            tuple(section.key for section in sections),
        )

    def test_navigator_builds_project_context_without_qt_items(self):
        building = self.document.addObject("App::Part", "Building")
        upper = self.document.addObject("App::Part", "UpperStorey")
        upper.Placement.Base.z = 3000.0
        ground = self.document.addObject("App::Part", "GroundStorey")
        ground.Placement.Base.z = 0.0
        proxy = self.document.addObject("App::FeaturePython", "GroundWorkingPlane")
        ground.addObject(proxy)
        building.addObject(upper)
        building.addObject(ground)
        kinds = {
            building.Name: "Building",
            upper.Name: "Building Storey",
            ground.Name: "Building Storey",
            proxy.Name: "WorkingPlaneProxy",
        }

        nodes = BIMNavigatorModel(
            self.document,
            type_resolver=lambda obj: kinds.get(obj.Name, ""),
        ).project_nodes()

        self.assertEqual((building,), tuple(node.object for node in nodes))
        self.assertEqual((ground, upper), tuple(node.object for node in nodes[0].children))
        self.assertEqual((proxy,), tuple(node.object for node in nodes[0].children[0].children))

    def test_qt_navigator_presents_one_tree_with_semantic_scope(self):
        storey = self.document.addObject("App::Part", "NavigatorStorey")
        wall = self.document.addObject("PartDesign::Feature", "NavigatorWall")
        wall.addProperty("App::PropertyString", "IfcType")
        wall.IfcType = "Wall"
        wall.ViewObject.Visibility = False
        storey.addObject(wall)
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Navigator Plan", "Plan", storey)
        service.activate_view(definition)
        navigator = BIMNavigatorModel(
            self.document,
            type_resolver=lambda obj: (
                "Building Storey" if obj is storey else ""
            ),
        )

        model = BIMNavigatorQtModel(navigator)

        self.assertEqual(4, model.rowCount())
        self.assertEqual(
            ("Project", "Views", "Current View", "Sheets"),
            tuple(model.index(row, 0).data() for row in range(4)),
        )
        current = model.index(2, 0)
        walls = model.index(0, 0, current)
        hidden_wall = model.index(0, 0, walls)
        self.assertEqual("1", model.index(0, 1, current).data())
        self.assertIs(wall, model.object_for_index(hidden_wall))
        self.assertIsNotNone(hidden_wall.data(QtCore.Qt.ForegroundRole))
        self.document.removeObject(wall.Name)
        self.assertTrue(model.flags(hidden_wall) & QtCore.Qt.ItemIsEnabled)

    def test_view_scope_keeps_hidden_storey_objects_in_context(self):
        storey = self.document.addObject("App::Part", "ScopeStorey")
        visible = self.document.addObject("PartDesign::Feature", "VisibleWall")
        hidden = self.document.addObject("PartDesign::Feature", "HiddenWall")
        storey.addObject(visible)
        storey.addObject(hidden)
        hidden.ViewObject.Visibility = False
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Scope Plan", "Plan", storey)

        scope = service.scope_for(definition)

        self.assertEqual((visible, hidden), scope.context_objects)
        self.assertEqual((visible,), scope.visible_objects)
        self.assertEqual((hidden,), scope.hidden_objects)

    def test_view_scope_groups_semantic_objects_and_preserves_hidden_members(self):
        storey = self.document.addObject("App::Part", "CategorizedStorey")
        wall = self.document.addObject("PartDesign::Feature", "CategorizedWall")
        wall.addProperty("App::PropertyString", "IfcType")
        wall.IfcType = "Wall"
        door = self.document.addObject("PartDesign::Feature", "CategorizedDoor")
        door.addProperty("App::PropertyString", "IfcType")
        door.IfcType = "Door"
        door.ViewObject.Visibility = False
        storey.addObject(wall)
        storey.addObject(door)
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Categorized Plan", "Plan", storey)

        scope = service.scope_for(definition)

        self.assertEqual(("Walls", "Doors"), tuple(item.key for item in scope.categories))
        self.assertEqual((wall,), scope.categories[0].visible_objects)
        self.assertEqual((door,), scope.categories[1].hidden_objects)

    def test_service_creates_captures_and_activates_a_plan_view(self):
        calls = []
        storey = self.document.addObject("App::FeaturePython", "GroundFloor")
        storey.addProperty("App::PropertyString", "IfcType")
        storey.addProperty("App::PropertyPlacement", "Placement")
        storey.IfcType = "Building Storey"
        storey.Placement.Base.z = 3000.0
        view = _RecordingView(calls)
        service = BIMViewService(
            self.document,
            view=view,
            representation_applier=lambda request: calls.append(("request", request)),
        )

        definition = service.create_view("Ground Floor Plan", "Plan", storey)
        context = service.context_for(definition)

        self.assertEqual("Plan", definition.Purpose)
        self.assertIs(storey, context.source)
        self.assertEqual(ArchRepresentation.RepresentationPurpose.PLAN, context.request.purpose)
        self.assertTrue(service.activate_view(definition))
        self.assertIs(definition, service.active_view)
        self.assertIs(storey, service.active_storey)
        self.assertEqual(("capture", "request", "apply"), tuple(call[0] for call in calls))

    def test_duplicate_preserves_persistent_view_state(self):
        service = BIMViewService(self.document, view=_RecordingView([]))
        original = service.create_view("Default 3D", "Model")
        original.ForcedHidden = [self.document.addObject("App::FeaturePython", "HiddenObject")]

        duplicate = service.duplicate_view(original)

        self.assertEqual("Default 3D Copy", duplicate.Label)
        self.assertEqual(original.CameraPayload, duplicate.CameraPayload)
        self.assertEqual(original.ForcedHidden, duplicate.ForcedHidden)
        self.assertFalse(duplicate.BIMIsActiveView)

    def test_active_saved_view_is_persistent_and_restorable(self):
        calls = []
        view = _RecordingView(calls)
        service = BIMViewService(self.document, view=view)
        first = service.create_model_view("Default 3D")
        second = service.create_model_view("Context 3D")

        restored_service = BIMViewService(self.document, view=view)

        self.assertFalse(first.BIMIsActiveView)
        self.assertTrue(second.BIMIsActiveView)
        self.assertIs(second, restored_service.active_view)
        self.assertTrue(restored_service.restore_active_view())
        self.assertIs(second, restored_service.active_view)

    def test_plan_creation_orients_and_captures_the_view(self):
        calls = []
        storey = self.document.addObject("App::FeaturePython", "FirstFloor")
        storey.addProperty("App::PropertyPlacement", "Placement")
        storey.Placement.Base = FreeCAD.Vector(1000, 2000, 3000)
        service = BIMViewService(self.document, view=_RecordingView(calls))

        definition = service.create_plan_view("First Floor Plan", storey)

        call_names = tuple(call[0] for call in calls)
        self.assertEqual(
            ("camera-type", "camera-orientation", "fit", "capture"), call_names
        )
        self.assertEqual("Plan", definition.Purpose)
        self.assertIs(storey, definition.BIMContextSource)
        self.assertTrue(definition.BIMIsActiveView)

    def test_saved_view_activation_configures_originating_snap_context(self):
        """Saved PLAN and MODEL views keep independent Snapper inputs."""

        calls = []
        snapper = SimpleNamespace(
            configure_view=lambda view, **kwargs: calls.append((view, kwargs)),
            remove_context=lambda view: calls.append((view, "removed")),
        )
        storey = self.document.addObject("App::FeaturePython", "SnapStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        storey.Placement.Base = FreeCAD.Vector(1000, 2000, 3000)
        view = _RecordingView([])
        service = BIMViewService(self.document, view=view)
        plan = service.create_view("Snap Plan", "Plan", storey, capture=False)
        section = service.create_view("Snap Section", "Section", storey, capture=False)
        model = service.create_view("Snap Model", "Model", capture=False)

        with patch.object(FreeCADGui, "Snapper", snapper, create=True):
            self.assertTrue(service.activate_view(plan))
            plan_view, plan_kwargs = calls[-1]
            self.assertIs(view, plan_view)
            self.assertIn("Grid", plan_kwargs["modes"])
            self.assertIsNotNone(plan_kwargs["interaction_plane"])
            self.assertIsNotNone(plan_kwargs["grid_provider"])
            self.assertEqual(
                FreeCAD.Vector(1000, 2000, 3000),
                plan_kwargs["grid_provider"].nearest_node(FreeCAD.Vector(1049, 2049, 3000)),
            )

            self.assertTrue(service.activate_view(section))
            section_view, section_kwargs = calls[-1]
            self.assertIs(view, section_view)
            self.assertIn("Midpoint", section_kwargs["modes"])
            self.assertIsNotNone(section_kwargs["interaction_plane"])
            self.assertIsNotNone(section_kwargs["grid_provider"])

            self.assertTrue(service.activate_view(model))
            model_view, model_kwargs = calls[-1]
            self.assertIs(view, model_view)
            self.assertIsNone(model_kwargs["modes"])
            self.assertIsNone(model_kwargs["interaction_plane"])
            self.assertIsNone(model_kwargs["grid_provider"])

            service.clear_snap_context(view)
            self.assertEqual((view, "removed"), calls[-1])

    def test_sourced_plan_view_can_be_linked_to_a_sheet(self):
        storey = self.document.addObject("App::FeaturePython", "SheetStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Sheet Plan", "Plan", storey)
        page = self.document.addObject("TechDraw::DrawPage", "Page")
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "Template")
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template

        drawing_view = service.place_on_sheet(definition, page)

        self.assertIs(definition, drawing_view.BIMViewDefinition)
        self.assertIs(storey, drawing_view.Source)
        self.assertIn(drawing_view, page.Views)

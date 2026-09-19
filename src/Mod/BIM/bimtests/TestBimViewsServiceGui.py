# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI-facing tests for the BIM Navigator service seam."""

from types import SimpleNamespace
from unittest.mock import patch

import ArchRepresentation
import FreeCAD
import FreeCADGui
import Part
from PySide import QtCore, QtGui
from pivy import coin

from bimcommands.BimViews import (
    _SectionViewPlacement,
    _apply_representation_request,
    _findModelDock,
    placeInComboView,
    restoreComboViewTitle,
)
from draftutils.grid import GridLattice, adaptive_lattice_interval
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimviews.grid_settings import get_grid_settings
from bimviews.viewport_grid import ViewportGridController
from bimviews.model import BIMViewManagerModel
from bimviews.navigator_model import BIMNavigatorModel
from bimviews.navigator_qt import BIMNavigatorQtModel, configure_navigator_columns
from bimviews.ruler_model import (
    RulerTransform,
    engineering_interval,
    format_length,
    format_metric,
    preferred_length_unit,
    tick_values,
)
from bimviews.framing import planar_view_bounds
from bimviews.service import BIMViewService
from bimviews.viewport_ruler import (
    ViewportRulerController,
    ViewportRulerOverlay,
    _ViewportEventFilter,
)
from bimplan.runtime.session import activate_representation_request
from bimsheets import BIMSheetMetadata, BIMSheetService


class _RecordingView:
    def __init__(self, calls):
        self.calls = calls

    def captureViewDefinition(self, definition):
        self.calls.append(("capture", definition))
        definition.CameraType = "Perspective"
        definition.CameraFocalDistance = 250.0
        definition.CameraHeightAngle = 0.75
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


class _AnimatedRecordingView(_RecordingView):
    def __init__(self, calls):
        super().__init__(calls)
        self.animation_enabled = True

    def stopAnimating(self):
        self.calls.append(("stop-animation", None))

    def isAnimationEnabled(self):
        self.calls.append(("get-animation", None))
        return self.animation_enabled

    def setAnimationEnabled(self, enabled):
        self.animation_enabled = bool(enabled)
        self.calls.append(("set-animation", self.animation_enabled))


class _FramingRecordingView(_RecordingView):
    def __init__(self, calls, size=(1000, 500)):
        super().__init__(calls)
        self.camera = coin.SoOrthographicCamera()
        self.camera.position.setValue(0.0, 0.0, 10.0)
        self.size = size

    def getCameraNode(self):
        return self.camera

    def getSize(self):
        return self.size


class TestBimViewsServiceGui(TestArchBaseGui):
    def test_sheet_service_creates_page_with_stable_metadata_contract(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        service = BIMSheetService(self.document)
        metadata = BIMSheetMetadata(
            number="A-101",
            title="Ground Floor Plan",
            discipline="Architectural",
            revision="P01",
            issue="Planning",
            issue_date="2026-09-19",
            status="Shared",
            template_identity="Default_Template_A4_Landscape.svg",
            order=101,
        )

        page = service.create_sheet(template_path, metadata)

        self.assertTrue(service.is_sheet(page))
        self.assertEqual("Ground Floor Plan", page.Label)
        self.assertEqual("Default_Template_A4_Landscape.svg", page.TemplateIdentity)
        self.assertEqual(metadata, service.metadata_for(page))
        self.assertIsNotNone(page.Template)

    def test_sheet_metadata_initialization_is_idempotent(self):
        page = self.document.addObject("TechDraw::DrawPage", "ExistingPage")
        service = BIMSheetService(self.document)
        service.ensure_metadata(
            page,
            BIMSheetMetadata(number="A-001", title="Cover", order=1),
        )

        service.ensure_metadata(page)

        self.assertEqual("A-001", page.SheetNumber)
        self.assertEqual("Cover", page.SheetTitle)
        self.assertEqual(1, page.SheetOrder)
        self.assertEqual(1, page.BIMSheetSchemaVersion)

    def test_sheet_service_rejects_non_page_objects(self):
        obj = self.document.addObject("App::FeaturePython", "NotAPage")

        with self.assertRaises(TypeError):
            BIMSheetService(self.document).ensure_metadata(obj)

    def test_section_placement_collects_line_and_side_then_cleans_up(self):
        requests = []
        finishes = []
        snapper = SimpleNamespace(
            getPoint=lambda **kwargs: requests.append(kwargs),
            cancelPointRequest=lambda: requests.append("cancelled"),
            off=lambda: requests.append("off"),
        )
        owner = SimpleNamespace(
            viewService=SimpleNamespace(_snap_plane_for=lambda _request: "plane"),
            _finishSectionPlacement=lambda *args: finishes.append(args),
            _sectionPlacement=None,
        )
        source = SimpleNamespace()
        frame = FreeCAD.Placement()
        placement = _SectionViewPlacement(owner, source, frame, "view")
        owner._sectionPlacement = placement

        with patch.object(FreeCADGui, "Snapper", snapper):
            placement.start()
            requests[-1]["callback"](FreeCAD.Vector(0, 0, 0))
            requests[-1]["callback"](FreeCAD.Vector(1000, 0, 0))
            requests[-1]["callback"](FreeCAD.Vector(500, -500, 0))

        self.assertEqual(
            (
                source,
                frame,
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(1000, 0, 0),
                FreeCAD.Vector(500, -500, 0),
            ),
            finishes[0],
        )
        self.assertIn("cancelled", requests)
        self.assertIn("off", requests)
        self.assertIsNone(owner._sectionPlacement)
        self.assertIsNone(FreeCAD.activeDraftCommand)

    def test_section_placement_cancel_creates_nothing(self):
        requests = []
        finishes = []
        snapper = SimpleNamespace(
            getPoint=lambda **kwargs: requests.append(kwargs),
            cancelPointRequest=lambda: requests.append("cancelled"),
            off=lambda: requests.append("off"),
        )
        owner = SimpleNamespace(
            viewService=SimpleNamespace(_snap_plane_for=lambda _request: "plane"),
            _finishSectionPlacement=lambda *args: finishes.append(args),
            _sectionPlacement=None,
        )
        placement = _SectionViewPlacement(
            owner, SimpleNamespace(), FreeCAD.Placement(), "view"
        )
        owner._sectionPlacement = placement

        with patch.object(FreeCADGui, "Snapper", snapper):
            placement.start()
            requests[-1]["callback"](None)

        self.assertFalse(finishes)
        self.assertIsNone(owner._sectionPlacement)
        self.assertIsNone(FreeCAD.activeDraftCommand)

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

        start.assert_called_once_with(
            show_task_panel=True,
            initial_request=request,
            prepare_only=False,
        )
        self.assertEqual([], calls)

    def test_plan_startup_preparation_keeps_task_panel_detached(self):
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            source=SimpleNamespace(),
        )
        fake_session = SimpleNamespace()

        with patch("bimplan.runtime.session.get_active_session", return_value=None):
            with patch(
                "bimplan.runtime.session.start_editing_session",
                return_value=fake_session,
            ) as start:
                self.assertIs(
                    fake_session,
                    activate_representation_request(request, prepare_only=True),
                )

        start.assert_called_once_with(
            show_task_panel=False,
            initial_request=request,
            prepare_only=True,
        )

    def test_plan_saved_view_activation_attaches_panel_to_existing_runtime(self):
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            source=SimpleNamespace(),
        )
        calls = []
        fake_session = SimpleNamespace(
            representation_request=SimpleNamespace(
                set_request=lambda value, fit=False: calls.append(
                    ("request", value, fit)
                )
            ),
            ensure_task_panel=lambda: calls.append(("panel",)),
        )

        with patch(
            "bimplan.runtime.session.get_active_session", return_value=fake_session
        ), patch("bimcontextual.session.active_session", return_value=None), patch(
            "bimplan.runtime.session._refresh_contextual_task_watchers"
        ):
            self.assertIs(fake_session, activate_representation_request(request))

        self.assertEqual(("request", request, False), calls[0])
        self.assertEqual(("panel",), calls[1])

    def test_elevation_saved_view_starts_contextual_editing_runtime(self):
        source = SimpleNamespace(Objects=("wall", "window"))
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
            source=source,
        )
        contextual = SimpleNamespace()

        with patch("bimplan.runtime.session.get_active_session", return_value=None):
            with patch("bimcontextual.session.active_session", return_value=None):
                with patch(
                    "bimcontextual.session.start_session", return_value=contextual
                ) as start:
                    self.assertIs(contextual, activate_representation_request(request))

        kwargs = start.call_args.kwargs
        self.assertIs(request, kwargs["request"])
        self.assertEqual(("wall", "window"), kwargs["sources"])
        self.assertFalse(kwargs["orient_to_request"])
        self.assertTrue(kwargs["providers"])

    def test_section_saved_view_starts_contextual_editing_runtime(self):
        source = SimpleNamespace(Objects=("wall", "door"))
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.SECTION,
            source=source,
        )
        contextual = SimpleNamespace()

        with patch("bimplan.runtime.session.get_active_session", return_value=None):
            with patch("bimcontextual.session.active_session", return_value=None):
                with patch(
                    "bimcontextual.session.start_session", return_value=contextual
                ) as start:
                    self.assertIs(contextual, activate_representation_request(request))

        kwargs = start.call_args.kwargs
        self.assertIs(request, kwargs["request"])
        self.assertEqual(("wall", "door"), kwargs["sources"])
        self.assertFalse(kwargs["orient_to_request"])
        self.assertTrue(kwargs["providers"])

    def test_saved_view_activation_suppresses_camera_animation(self):
        calls = []
        view = _AnimatedRecordingView(calls)
        service = BIMViewService(self.document, view=view)
        definition = service.create_view("Instant Plan", "Plan", capture=False)

        with patch.object(service, "configure_snap_context"):
            self.assertTrue(service.activate_view(definition))

        self.assertEqual(
            [
                ("stop-animation", None),
                ("get-animation", None),
                ("set-animation", False),
                ("apply", definition),
                ("set-animation", True),
            ],
            calls,
        )
        self.assertTrue(view.animation_enabled)

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
            FreeCADGui.deleteLater(navigator)
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
        self.assertEqual(format_length(3482.0, cursor=True), format_metric(3482.0, cursor=True))
        self.assertIn(preferred_length_unit(), format_length(100.0, 100.0))
        self.assertIn(preferred_length_unit(), format_length(0.0, 100.0))

    def test_grid_settings_parse_common_length_units(self):
        expected = (
            ("100 mm", 100.0),
            ("10 cm", 100.0),
            ("4 in", 101.6),
            ("1 ft", 304.8),
            ("1/8 in", 3.175),
        )
        for raw_spacing, expected_spacing in expected:
            preferences = SimpleNamespace(
                GetString=lambda _name, _default, value=raw_spacing: value,
                GetInt=lambda _name, default: default,
            )
            settings = get_grid_settings(preferences)
            self.assertAlmostEqual(expected_spacing, settings.spacing, places=9)
            self.assertEqual(10, settings.major_every)

    def test_grid_settings_validate_invalid_preferences(self):
        preferences = SimpleNamespace(
            GetString=lambda _name, _default: "0 mm",
            GetInt=lambda _name, _default: -2,
        )
        settings = get_grid_settings(preferences)
        self.assertEqual(100.0, settings.spacing)
        self.assertEqual(10, settings.major_every)

    def test_grid_nodes_are_schema_independent(self):
        preferences = SimpleNamespace(
            GetString=lambda _name, _default: "10 cm",
            GetInt=lambda _name, default: default,
        )
        settings = get_grid_settings(preferences)
        lattice = GridLattice(spacing=settings.spacing)
        expected = lattice.nearest_node(FreeCAD.Vector(149.0, 51.0, 0.0))
        original_schema = FreeCAD.Units.getSchema()
        try:
            schemas = FreeCAD.Units.listSchemas()
            for schema_name in ("Internal", "MeterDecimal"):
                if schema_name not in schemas:
                    continue
                FreeCAD.Units.setSchema(schemas.index(schema_name))
                self.assertEqual(expected, lattice.nearest_node(FreeCAD.Vector(149.0, 51.0, 0.0)))
        finally:
            FreeCAD.Units.setSchema(original_schema)

    def test_ruler_labels_follow_active_unit_schema(self):
        original_schema = FreeCAD.Units.getSchema()
        try:
            schemas = FreeCAD.Units.listSchemas()
            for schema_name, expected_unit in (("Internal", "mm"), ("MeterDecimal", "m")):
                if schema_name not in schemas:
                    continue
                FreeCAD.Units.setSchema(schemas.index(schema_name))
                self.assertIn(expected_unit, preferred_length_unit())
                self.assertIn(expected_unit, format_length(1000.0, 1000.0))
        finally:
            FreeCAD.Units.setSchema(original_schema)

    def test_adaptive_grid_display_interval_is_a_snap_multiple(self):
        spacing = 100.0
        for units_per_pixel in (0.01, 0.2, 1.0, 7.0, 100.0):
            display_spacing = adaptive_lattice_interval(spacing, units_per_pixel)
            multiplier = display_spacing / spacing
            self.assertIn(round(multiplier), (2, 5, 10, 20))
            self.assertAlmostEqual(round(multiplier), multiplier)

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

    def test_ruler_uses_native_decoration_slots_without_viewport_margins(self):
        view = FreeCADGui.activeDocument().activeView()
        graphics_view = view.graphicsView()
        initial_margins = graphics_view.viewportMargins()
        request = SimpleNamespace(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            reference_frame=None,
            source=None,
        )
        viewport = SimpleNamespace(
            get_plan_view_widget=lambda: graphics_view,
            get_plan_point_from_mouse_pos=lambda pos: FreeCAD.Vector(pos[0], pos[1], 0),
            get_plan_view_units_per_pixel=lambda: 1.0,
            get_plan_projection_cache_key=lambda: None,
        )
        controller = ViewportRulerController(
            SimpleNamespace(view=view, viewport=viewport), request
        )
        try:
            self.assertTrue(controller.attach())
            self.assertEqual(initial_margins, graphics_view.viewportMargins())
            self.assertEqual(
                [
                    "View3DViewportTopDecoration",
                    "View3DViewportLeftDecoration",
                    "View3DViewportCornerDecoration",
                ],
                [host.objectName() for host in controller.decoration_hosts],
            )
            self.assertIs(controller.host_widget, graphics_view.viewport())
        finally:
            controller.close()

    def test_viewport_controllers_ignore_deleted_graphics_view_wrappers(self):
        graphics_view = QtGui.QGraphicsView()
        from shiboken6 import Shiboken

        Shiboken.delete(graphics_view)
        viewport = SimpleNamespace(get_plan_view_widget=lambda: graphics_view)
        request = SimpleNamespace(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            reference_frame=None,
            source=None,
        )
        session = SimpleNamespace(view=None, viewport=viewport)
        ruler = ViewportRulerController(session, request)
        grid = ViewportGridController(session, request)

        with patch("bimviews.viewport_ruler.rulers_enabled", return_value=True), patch(
            "bimviews.viewport_grid.grid_enabled", return_value=True
        ):
            self.assertFalse(ruler.attach())
            self.assertFalse(grid.attach())
            ruler.close()
            grid.close()
            ruler.close()
            grid.close()

    def test_grid_controller_clears_widgets_destroyed_after_attach(self):
        graphics_view = QtGui.QGraphicsView()
        graphics_view.resize(640, 480)
        viewport = SimpleNamespace(
            get_plan_view_widget=lambda: graphics_view,
            get_plan_point_from_mouse_pos=lambda pos: FreeCAD.Vector(pos[0], pos[1], 0),
            get_plan_view_units_per_pixel=lambda: 1.0,
            get_plan_projection_cache_key=lambda: None,
        )
        request = SimpleNamespace(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            reference_frame=None,
            source=None,
        )
        controller = ViewportGridController(
            SimpleNamespace(view=None, viewport=viewport), request
        )

        with patch("bimviews.viewport_grid.grid_enabled", return_value=True):
            self.assertTrue(controller.attach())
        from shiboken6 import Shiboken

        Shiboken.delete(graphics_view)
        self.assertIsNone(controller.graphics_view)
        self.assertIsNone(controller.host_widget)
        controller.close()
        controller.close()

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

    def test_navigator_columns_keep_element_labels_in_available_space(self):
        tree = QtGui.QTreeView()
        tree.setModel(QtGui.QStandardItemModel(0, 3, tree))
        configure_navigator_columns(tree)
        header = tree.header()

        self.assertFalse(header.stretchLastSection())
        self.assertEqual(QtGui.QHeaderView.Stretch, header.sectionResizeMode(0))
        self.assertEqual(QtGui.QHeaderView.ResizeToContents, header.sectionResizeMode(1))
        self.assertEqual(QtGui.QHeaderView.ResizeToContents, header.sectionResizeMode(2))

    def test_navigator_builds_project_context_without_qt_items(self):
        building = self.document.addObject("App::Part", "Building")
        upper = self.document.addObject("App::Part", "UpperStorey")
        upper.Placement.Base.z = 3000.0
        ground = self.document.addObject("App::Part", "GroundStorey")
        ground.Placement.Base.z = 0.0
        proxy = self.document.addObject("App::FeaturePython", "GroundWorkingPlane")
        section = __import__("Arch").makeSectionPlane(name="GroundSection")
        ground.addObject(proxy)
        ground.addObject(section)
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
        self.assertEqual(
            (proxy, section),
            tuple(node.object for node in nodes[0].children[0].children),
        )

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
        self.assertEqual(original.CameraType, duplicate.CameraType)
        self.assertEqual(original.CameraHeightAngle, duplicate.CameraHeightAngle)
        self.assertEqual(original.CameraPlacement, duplicate.CameraPlacement)
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

    def test_elevation_creation_builds_marker_and_saved_view(self):
        calls = []
        storey = self.document.addObject("App::Part", "ElevationStorey")
        facade = self.document.addObject("PartDesign::Feature", "ElevationFacade")
        facade.Shape = Part.makeBox(4000, 200, 3000)
        storey.addObject(facade)
        service = BIMViewService(self.document, view=_RecordingView(calls))

        definition = service.create_elevation_view(
            "South Elevation", storey, direction="South"
        )
        plane = definition.BIMContextSource

        self.assertEqual("Elevation", definition.Purpose)
        self.assertEqual("Elevation", plane.Purpose)
        self.assertEqual([facade], list(plane.Objects))
        self.assertGreater(plane.Depth.Value, 200.0)
        self.assertEqual(plane.Placement, definition.ReferenceFrame)
        self.assertEqual(
            ("camera-type", "camera-orientation", "fit", "capture"),
            tuple(call[0] for call in calls),
        )
        request = service.request_for(definition)
        self.assertEqual(
            ArchRepresentation.RepresentationPurpose.ELEVATION,
            request.purpose,
        )
        self.assertEqual((-plane.Depth.Value, 0.0), request.projection_range)

    def test_section_creation_builds_saved_view_from_existing_plane(self):
        calls = []
        wall = self.document.addObject("PartDesign::Feature", "SectionWall")
        wall.Shape = Part.makeBox(4000, 200, 3000)
        plane = __import__("Arch").makeSectionPlane([wall], name="BuildingSection")
        plane.Placement = FreeCAD.Placement(
            FreeCAD.Vector(2000, 100, 1500),
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
        )
        service = BIMViewService(self.document, view=_RecordingView(calls))

        definition = service.create_section_view("Building Section", plane)

        self.assertEqual("Section", definition.Purpose)
        self.assertIs(plane, definition.BIMContextSource)
        self.assertEqual(plane.Placement, definition.ReferenceFrame)
        self.assertTrue(definition.BIMIsActiveView)
        self.assertEqual(
            ("camera-type", "camera-orientation", "fit", "capture"),
            tuple(call[0] for call in calls),
        )
        request = service.request_for(definition)
        self.assertEqual(
            ArchRepresentation.RepresentationPurpose.SECTION,
            request.purpose,
        )
        self.assertEqual((wall,), service.scope_for(definition).context_objects)

    def test_section_creation_rejects_elevation_plane(self):
        facade = self.document.addObject("PartDesign::Feature", "NotASectionFacade")
        facade.Shape = Part.makeBox(1000, 200, 1000)
        plane = __import__("Arch").makeSectionPlane([facade], name="ElevationOnly")
        plane.Purpose = "Elevation"
        service = BIMViewService(self.document, view=_RecordingView([]))

        with self.assertRaisesRegex(ValueError, "section-purpose"):
            service.create_section_view("Invalid Section", plane)

    def test_section_line_creation_sets_scope_direction_and_extents(self):
        storey = self.document.addObject("App::Part", "SectionLineStorey")
        wall = self.document.addObject("PartDesign::Feature", "SectionLineWall")
        wall.Shape = Part.makeBox(1000, 200, 3000)
        storey.addObject(wall)
        service = BIMViewService(self.document, view=_RecordingView([]))

        definition = service.create_section_view_from_line(
            "Cross Section",
            storey,
            FreeCAD.Vector(0, 100, 0),
            FreeCAD.Vector(1000, 100, 0),
            FreeCAD.Vector(500, -100, 0),
        )
        plane = definition.BIMContextSource

        self.assertEqual("Section", definition.Purpose)
        self.assertEqual("Section", plane.Purpose)
        self.assertEqual((wall,), tuple(plane.Objects))
        self.assertAlmostEqual(1000.0, plane.ViewObject.DisplayLength.Value)
        self.assertGreater(plane.ViewObject.DisplayHeight.Value, 3000.0)
        self.assertGreater(plane.Depth.Value, 100.0)
        normal = plane.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        self.assertAlmostEqual(-1.0, normal.y)
        self.assertEqual(plane.Placement, definition.ReferenceFrame)

    def test_section_line_viewing_side_reverses_normal(self):
        storey = self.document.addObject("App::Part", "ReverseSectionStorey")
        wall = self.document.addObject("PartDesign::Feature", "ReverseSectionWall")
        wall.Shape = Part.makeBox(1000, 200, 3000)
        storey.addObject(wall)
        service = BIMViewService(self.document, view=_RecordingView([]))

        definition = service.create_section_view_from_line(
            "Reverse Section",
            storey,
            FreeCAD.Vector(0, 100, 0),
            FreeCAD.Vector(1000, 100, 0),
            FreeCAD.Vector(500, 300, 0),
        )

        normal = definition.BIMContextSource.Placement.Rotation.multVec(
            FreeCAD.Vector(0, 0, 1)
        )
        self.assertAlmostEqual(1.0, normal.y)

    def test_section_line_rejects_degenerate_picks_without_creating_objects(self):
        storey = self.document.addObject("App::Part", "InvalidSectionStorey")
        wall = self.document.addObject("PartDesign::Feature", "InvalidSectionWall")
        wall.Shape = Part.makeBox(1000, 200, 3000)
        storey.addObject(wall)
        service = BIMViewService(self.document, view=_RecordingView([]))

        with self.assertRaisesRegex(ValueError, "distinct plan points"):
            service.create_section_view_from_line(
                "Invalid Section",
                storey,
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(0, 0, 1000),
                FreeCAD.Vector(100, 0, 0),
            )

        self.assertFalse(
            any(obj.isDerivedFrom("App::ViewDefinition") for obj in self.document.Objects)
        )

    def test_section_line_creation_is_one_undoable_transaction(self):
        storey = self.document.addObject("App::Part", "UndoSectionStorey")
        wall = self.document.addObject("PartDesign::Feature", "UndoSectionWall")
        wall.Shape = Part.makeBox(1000, 200, 3000)
        storey.addObject(wall)
        service = BIMViewService(self.document, view=_RecordingView([]))
        self.document.recompute()

        self.document.openTransaction("Create BIM section")
        definition = service.create_section_view_from_line(
            "Undo Section",
            storey,
            FreeCAD.Vector(0, 100, 0),
            FreeCAD.Vector(1000, 100, 0),
            FreeCAD.Vector(500, -100, 0),
        )
        plane_name = definition.BIMContextSource.Name
        definition_name = definition.Name
        self.document.commitTransaction()
        self.document.recompute()

        self.document.undo()

        self.assertIsNone(self.document.getObject(plane_name))
        self.assertIsNone(self.document.getObject(definition_name))

    def test_elevation_scope_uses_section_plane_objects(self):
        storey = self.document.addObject("App::Part", "ScopedElevationStorey")
        facade = self.document.addObject("PartDesign::Feature", "ScopedFacade")
        facade.Shape = Part.makeBox(1000, 200, 1000)
        storey.addObject(facade)
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_elevation_view("West Elevation", storey, direction="West")

        scope = service.scope_for(definition)

        self.assertEqual((facade,), scope.context_objects)

    def test_plan_creation_frames_visible_scope_geometry_not_the_coin_scene(self):
        calls = []
        storey = self.document.addObject("App::Part", "FramedStorey")
        visible = self.document.addObject("PartDesign::Feature", "VisiblePlanGeometry")
        visible.Shape = Part.makeBox(100, 50, 20)
        hidden = self.document.addObject("PartDesign::Feature", "HiddenOutlier")
        hidden.Shape = Part.makeBox(10000, 10000, 20)
        hidden.ViewObject.Visibility = False
        storey.addObject(visible)
        storey.addObject(hidden)
        view = _FramingRecordingView(calls)

        definition = BIMViewService(self.document, view=view).create_plan_view(
            "Framed Plan", storey
        )

        self.assertEqual(
            ("camera-type", "camera-orientation", "capture"),
            tuple(call[0] for call in calls),
        )
        self.assertAlmostEqual(57.5, view.camera.height.getValue())
        position = view.camera.position.getValue()
        self.assertAlmostEqual(50.0, position[0])
        self.assertAlmostEqual(25.0, position[1])
        self.assertTrue(definition.BIMIsActiveView)

    def test_planar_view_bounds_uses_the_view_reference_frame(self):
        feature = self.document.addObject("PartDesign::Feature", "OffsetGeometry")
        feature.Shape = Part.makeBox(40, 20, 10, FreeCAD.Vector(100, 200, 30))
        frame = FreeCAD.Placement(FreeCAD.Vector(100, 200, 30), FreeCAD.Rotation())

        bounds = planar_view_bounds((feature,), frame)

        self.assertEqual((0.0, 40.0), (bounds.x_min, bounds.x_max))
        self.assertEqual((0.0, 20.0), (bounds.y_min, bounds.y_max))
        self.assertEqual((0.0, 10.0), (bounds.z_min, bounds.z_max))

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

    def test_sourced_elevation_view_can_be_linked_to_a_sheet(self):
        facade = self.document.addObject("PartDesign::Feature", "SheetElevationFacade")
        facade.Shape = Part.makeBox(1000, 200, 1000)
        plane = __import__("Arch").makeSectionPlane([facade], name="SheetElevation")
        plane.Purpose = "Elevation"
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Sheet Elevation", "Elevation", plane, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "ElevationPage")
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "ElevationTemplate")
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template

        drawing_view = service.place_on_sheet(definition, page)

        self.assertIs(plane, drawing_view.Source)
        self.assertIs(definition, drawing_view.BIMViewDefinition)
        self.assertIn(drawing_view, page.Views)

    def test_sourced_section_view_can_be_linked_to_a_sheet(self):
        wall = self.document.addObject("PartDesign::Feature", "SheetSectionWall")
        wall.Shape = Part.makeBox(1000, 200, 1000)
        plane = __import__("Arch").makeSectionPlane([wall], name="SheetSection")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Sheet Section", "Section", plane, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "SectionPage")
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "SectionTemplate")
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template

        drawing_view = service.place_on_sheet(definition, page)

        self.assertIs(plane, drawing_view.Source)
        self.assertIs(definition, drawing_view.BIMViewDefinition)
        self.assertIn(drawing_view, page.Views)

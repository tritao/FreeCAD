# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI-facing tests for the BIM Views Manager service seam."""

import ArchRepresentation
import FreeCAD
from PySide import QtGui

from bimtests.TestArchBaseGui import TestArchBaseGui
from bimviews.model import BIMViewManagerModel
from bimviews.ruler_model import RulerTransform, engineering_interval, format_metric, tick_values
from bimviews.service import BIMViewService
from bimviews.viewport_ruler import ViewportRulerOverlay


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

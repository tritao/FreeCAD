# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI-facing tests for the BIM Navigator service seam."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import ArchRepresentation
import FreeCAD
import FreeCADGui
import Part
from PySide import QtCore, QtGui
from pivy import coin

from bimcommands.BimViews import (
    BIM_Views,
    _SectionViewPlacement,
    _apply_representation_request,
    _findModelDock,
    _preferred_sheet,
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
from bimviews.representation import apply_view_visibility, resolve_drawing_context
from bimviews.service import BIMViewService
from bimviews.viewport_ruler import (
    ViewportRulerController,
    ViewportRulerOverlay,
    _ViewportEventFilter,
)
from bimplan.runtime.session import activate_representation_request
from bimsheets import (
    BIMSheetFootprintProvider,
    BIMSheetIdentityService,
    BIMSheetLayout,
    BIMSheetIssueService,
    BIMSheetMetadata,
    BIMSheetPublishingService,
    BIMSheetService,
    BIMSheetViewTitleService,
    BIMTitleBlockService,
    SheetPublicationError,
    SheetIssueError,
    SheetLayoutError,
    PlacementFootprint,
    SheetRect,
    format_scale,
)
from bimsheets.gui import (
    BIMSheetInspectorPanel,
    BIMSheetPlacementPropertiesWidget,
    BIMSheetPropertiesDialog,
    create_sheet_interactive,
    hide_sheet_inspector,
    show_sheet_inspector,
)
from bimsheets.layout import svg_footprint


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
    def test_sheet_layout_places_views_without_overlap(self):
        layout = BIMSheetLayout(200, 120, gap=5)
        first = layout.place((50, 40))
        second = layout.place((50, 40), (first,))

        self.assertEqual(SheetRect(35, 90, 50, 40), first)
        self.assertEqual(SheetRect(90, 90, 50, 40), second)
        self.assertFalse(first.intersects(second, layout.gap))

    def test_sheet_layout_validates_overrides_and_full_sheets(self):
        layout = BIMSheetLayout(100, 80, gap=5)

        explicit = layout.place((20, 10), position=(50, 40))

        self.assertEqual(SheetRect(50, 40, 20, 10), explicit)
        with self.assertRaisesRegex(SheetLayoutError, "outside printable"):
            layout.place((20, 10), position=(5, 5))
        with self.assertRaisesRegex(SheetLayoutError, "no printable sheet space"):
            layout.place((70, 50), (SheetRect(50, 40, 70, 50),))

        with self.assertRaisesRegex(SheetLayoutError, "overlaps"):
            layout.place(
                (20, 10),
                (SheetRect(50, 40, 20, 10),),
                position=(50, 40),
            )

    def test_sheet_layout_preserves_anchor_for_offset_footprints(self):
        footprint = PlacementFootprint(-10, -20, 10, 5)

        placement = BIMSheetLayout(100, 80).place(footprint)

        self.assertEqual(SheetRect(20, 57.5, 20, 25), placement)

    def test_svg_footprint_uses_rendered_geometry_and_scale(self):
        svg = '<svg><path d="M -10 5 L 90 5 L 90 55 L -10 55" /></svg>'

        self.assertEqual((25.0, 12.5), svg_footprint(svg, scale=0.25))
        self.assertEqual((16.0, 16.0), svg_footprint("", scale=0.25))

    def test_sheet_footprint_includes_owned_title_offset(self):
        drawing_view = SimpleNamespace(
            Symbol='<svg><path d="M 0 0 L 10 0 L 10 10 L 0 10" /></svg>',
            ViewNumber="1",
            ViewTitle="Plan",
            Label="Plan",
            getScale=lambda: 1.0,
        )
        annotation = SimpleNamespace(
            Owner=drawing_view,
            OwnerOffsetX=0.0,
            OwnerOffsetY=-20.0,
            TextSize=4.0,
            isDerivedFrom=lambda type_name: type_name
            == "TechDraw::DrawViewAnnotation",
        )
        drawing_view.Document = SimpleNamespace(Objects=(annotation,))

        footprint = BIMSheetFootprintProvider().for_view(drawing_view)
        edited = BIMSheetFootprintProvider().for_view(
            drawing_view, view_title="A much longer contextual title"
        )

        self.assertLess(footprint.bottom, -5.0)
        self.assertEqual(5.0, footprint.top)
        self.assertGreater(edited.width, footprint.width)

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
            margin_left=12,
            margin_top=8,
            margin_right=15,
            margin_bottom=20,
        )

        page = service.create_sheet(template_path, metadata)

        self.assertTrue(service.is_sheet(page))
        self.assertEqual("A-101 — Ground Floor Plan", page.Label)
        self.assertEqual("Default_Template_A4_Landscape.svg", page.TemplateIdentity)
        self.assertEqual(metadata, service.metadata_for(page))
        self.assertEqual(
            SheetRect(37, page.PageHeight - 28, 50, 40),
            BIMSheetLayout(
                page.PageWidth,
                page.PageHeight,
                service.margins_for(page),
            ).place((50, 40)),
        )
        self.assertIsNotNone(page.Template)

    def test_sheet_identity_allocates_discipline_numbers_and_fills_gaps(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        service = BIMSheetService(self.document)
        first = service.create_sheet(template_path)
        second = service.create_sheet(template_path)
        service.create_sheet(
            template_path,
            BIMSheetMetadata(
                number="A-001", title="Architectural Plans", discipline="Architectural"
            ),
        )
        identity = BIMSheetIdentityService(self.document, service.is_sheet)

        self.assertEqual("G-001", first.SheetNumber)
        self.assertEqual("G-002", second.SheetNumber)
        self.assertEqual("G-001 — Untitled Sheet", first.Label)
        self.assertEqual("A-002", identity.next_number("Architectural"))

        self.document.removeObject(first.Name)
        self.assertEqual("G-001", identity.next_number("General"))

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
        self.assertEqual(service.SCHEMA_VERSION, page.BIMSheetSchemaVersion)

    def test_sheet_properties_dialog_edits_visible_metadata_only(self):
        metadata = BIMSheetMetadata(
            number="A-101",
            title="Floor Plan",
            discipline="Architectural",
            revision="P01",
            issue="Tender",
            issue_date="2026-09-19",
            status="Shared",
            template_identity="A1.svg",
            order=10,
        )
        dialog = BIMSheetPropertiesDialog(metadata)
        try:
            dialog.number.setText(" A-102 ")
            dialog.title.setText(" Reflected Ceiling Plan ")
            dialog.revision.setText(" P02 ")
            dialog.status.setCurrentText("Published")
            dialog.order.setValue(20)
            edited = dialog.metadata()
        finally:
            dialog.close()
            FreeCADGui.deleteLater(dialog)

        self.assertEqual("A-102", edited.number)
        self.assertEqual("Reflected Ceiling Plan", edited.title)
        self.assertEqual("P02", edited.revision)
        self.assertEqual("Published", edited.status)
        self.assertEqual(20, edited.order)
        self.assertEqual("Tender", edited.issue)
        self.assertEqual("2026-09-19", edited.issue_date)
        self.assertEqual("A1.svg", edited.template_identity)

    def test_sheet_placement_prefers_active_page_then_selected_or_only_sheet(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        service = BIMSheetService(self.document)
        first = service.create_sheet(
            template_path, BIMSheetMetadata(number="A-101", title="Plans")
        )
        second = service.create_sheet(
            template_path, BIMSheetMetadata(number="A-201", title="Elevations")
        )
        active_view = SimpleNamespace(getPage=lambda: second)
        gui_document = SimpleNamespace(activeView=lambda: active_view)

        with patch(
            "bimcommands.BimViews.FreeCADGui.activeDocument",
            return_value=gui_document,
        ):
            self.assertIs(second, _preferred_sheet(self.document, (first,)))

        gui_document = SimpleNamespace(activeView=lambda: SimpleNamespace())
        with patch(
            "bimcommands.BimViews.FreeCADGui.activeDocument",
            return_value=gui_document,
        ):
            self.assertIs(first, _preferred_sheet(self.document, (first,)))
            self.assertIsNone(_preferred_sheet(self.document))

        self.document.removeObject(second.Name)
        with patch(
            "bimcommands.BimViews.FreeCADGui.activeDocument",
            return_value=gui_document,
        ):
            self.assertIs(first, _preferred_sheet(self.document))

    def test_interactive_sheet_creation_uses_shared_service_path(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        saved_directories = []
        bim_parameters = SimpleNamespace(
            GetString=lambda _name, _default: "",
            GetFloat=lambda _name, _default: 0.02,
            SetString=lambda name, value: saved_directories.append((name, value)),
        )
        techdraw_directory = os.path.dirname(template_path)
        techdraw_parameters = SimpleNamespace(
            GetString=lambda _name, _default: techdraw_directory,
        )
        with patch(
            "bimsheets.gui.FreeCAD.ParamGet",
            side_effect=(bim_parameters, techdraw_parameters),
        ), patch(
            "bimsheets.gui.QtGui.QFileDialog.getOpenFileName",
            return_value=(template_path, "SVG file (*.svg)"),
        ) as chooser:
            page = create_sheet_interactive(self.document)

        self.assertTrue(BIMSheetService.is_sheet(page))
        self.assertEqual("G-001", page.SheetNumber)
        self.assertEqual("Untitled Sheet", page.SheetTitle)
        self.assertEqual("G-001 — Untitled Sheet", page.Label)
        self.assertEqual("Default_Template_A4_Landscape.svg", page.TemplateIdentity)
        self.assertEqual(techdraw_directory, chooser.call_args.args[2])
        self.assertEqual([("TDTemplateDir", techdraw_directory)], saved_directories)

    def test_sheet_inspector_applies_metadata_without_a_modal_dialog(self):
        page = BIMSheetService(self.document).create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg",
            BIMSheetMetadata(number="A-101", title="Plan", order=1),
        )
        panel = BIMSheetInspectorPanel()
        panel.set_context(page, "sheet")
        panel.editor.number.setText("A-201")
        panel.editor.title.setText("Floor Plans")
        panel.editor.revision.setText("P02")
        panel.apply()

        self.assertEqual("A-201", page.SheetNumber)
        self.assertEqual("Floor Plans", page.SheetTitle)
        self.assertEqual("A-201 — Floor Plans", page.Label)
        self.assertEqual("P02", page.Revision)
        self.assertEqual("A-201", page.Template.EditableTexts["drawing_number"])

    def test_placement_inspector_applies_generic_techdraw_properties(self):
        source = self.document.addObject("App::FeaturePython", "InspectorSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Plan", "Plan", source, capture=False)
        page = BIMSheetService(self.document).create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        drawing_view = service.place_on_sheet(definition, page)
        editor = BIMSheetPlacementPropertiesWidget(drawing_view)
        try:
            editor.number.setText("D1")
            editor.title.setText("Lobby Detail")
            editor.scale.setValue(0.02)
            editor.x.setValue(80)
            editor.y.setValue(60)
            editor.title_offset.setValue(10)
            editor.title_size.setValue(4)
            editor.show_hidden.setChecked(True)
            with patch("ArchSectionPlane.getSVG", return_value=""):
                editor.apply()
        finally:
            editor.close()
            FreeCADGui.deleteLater(editor)

        annotation = BIMSheetViewTitleService.annotation_for(drawing_view)
        self.assertEqual("D1", drawing_view.ViewNumber)
        self.assertEqual("Lobby Detail", drawing_view.ViewTitle)
        self.assertAlmostEqual(0.02, drawing_view.Scale)
        self.assertAlmostEqual(80, drawing_view.X.Value)
        self.assertAlmostEqual(60, drawing_view.Y.Value)
        self.assertAlmostEqual(10, annotation.BIMTitleGap.Value)
        self.assertLess(annotation.OwnerOffsetY.Value, -10)
        self.assertAlmostEqual(4, annotation.TextSize.Value)
        self.assertTrue(drawing_view.ShowHidden)

    def test_placement_inspector_suggests_layout_without_mutating_document(self):
        source = self.document.addObject("App::FeaturePython", "SuggestionSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        view_service = BIMViewService(self.document, view=_RecordingView([]))
        definition = view_service.create_view(
            "Suggested Plan", "Plan", source, capture=False
        )
        page = BIMSheetService(self.document).create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        drawing_view = view_service.place_on_sheet(definition, page)
        original = (
            drawing_view.Scale,
            drawing_view.X.Value,
            drawing_view.Y.Value,
        )
        editor = BIMSheetPlacementPropertiesWidget(drawing_view)
        try:
            editor.scale.setValue(100.0)
            editor.fit_to_available_space()

            self.assertLess(editor.scale.value(), 100.0)
            self.assertIn("Apply", editor.suggestion_status.text())
            self.assertEqual(original[0], drawing_view.Scale)
            self.assertEqual(original[1], drawing_view.X.Value)
            self.assertEqual(original[2], drawing_view.Y.Value)

            editor.find_free_position()
            self.assertIn("Apply", editor.suggestion_status.text())
            self.assertEqual(original[1], drawing_view.X.Value)
            self.assertEqual(original[2], drawing_view.Y.Value)
        finally:
            editor.close()
            FreeCADGui.deleteLater(editor)

    def test_sheet_inspector_uses_standard_contextual_task_view(self):
        page = BIMSheetService(self.document).create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        try:
            panel = show_sheet_inspector(page, "sheet")
            self.assertIsNotNone(panel)
            self.assertEqual("Sheet Inspector", panel.form.windowTitle())
            self.assertIsNotNone(FreeCADGui.Control.activeDialog(FreeCADGui.activeDocument()))
        finally:
            hide_sheet_inspector()

    def test_sheet_metadata_synchronizes_mapped_title_block_fields(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        metadata = BIMSheetMetadata(
            number="A-301",
            title="Floor Plans",
            revision="P03",
            issue_date="2026-09-19",
        )
        page = BIMSheetService(self.document).create_sheet(template_path, metadata)
        title_blocks = BIMTitleBlockService(self.document)
        texts = dict(page.Template.EditableTexts)
        creator = texts["creator"]

        self.assertEqual("A-301", texts["drawing_number"])
        self.assertEqual("Floor Plans", texts["title"])
        self.assertEqual("P03", texts["revision_index"])
        self.assertEqual("2026-09-19", texts["date_of_issue"])
        self.assertEqual(creator, texts["creator"])
        self.assertEqual("drawing_number", title_blocks.mapping_for(page)["number"])
        self.assertIn("discipline", page.MissingTitleBlockFields)

        page.SheetNumber = "A-302"
        page.SheetTitle = "Updated Plans"
        self.assertEqual("A-302", page.Template.EditableTexts["drawing_number"])
        self.assertEqual("Updated Plans", page.Template.EditableTexts["title"])
        self.assertEqual(creator, page.Template.EditableTexts["creator"])

    def test_title_block_mapping_survives_save_reopen_and_is_undoable(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path,
            BIMSheetMetadata(number="S-001", title="Sections"),
            name="PersistentTitleBlockPage",
        )
        self.document.openTransaction("Change sheet number")
        page.SheetNumber = "S-002"
        self.document.commitTransaction()
        self.assertEqual("S-002", page.Template.EditableTexts["drawing_number"])
        self.document.undo()
        self.assertEqual("S-001", page.SheetNumber)
        self.assertEqual("S-001", page.Template.EditableTexts["drawing_number"])

        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/title-block.FCStd"
            self.document.saveAs(path)
            FreeCAD.closeDocument(self.document.Name)
            self.document = FreeCAD.openDocument(path)
            page = self.document.getObject("PersistentTitleBlockPage")
            self.assertEqual(
                "drawing_number", page.EditableTextBindings["SheetNumber"]
            )
            page.Revision = "C01"
            self.assertEqual("C01", page.Template.EditableTexts["revision_index"])

    def test_title_block_rejects_unknown_explicit_template_fields(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(template_path)

        with self.assertRaisesRegex(ValueError, "template fields not found"):
            BIMTitleBlockService(self.document).synchronize(
                page, {"number": "does_not_exist"}
            )

    def test_sheet_set_publication_is_ordered_and_records_output(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        sheets = BIMSheetService(self.document)
        second = sheets.create_sheet(
            template_path,
            BIMSheetMetadata(number="A-202", title="Upper Plan", revision="P02", order=202),
            name="SecondPublishedSheet",
        )
        first = sheets.create_sheet(
            template_path,
            BIMSheetMetadata(number="A-101", title="Ground/Plan", revision="P01", order=101),
            name="FirstPublishedSheet",
        )
        calls = []

        def exporter(page, path, format):
            calls.append((page, path.name, format))
            path.write_text("{}:{}".format(format, page.SheetNumber), encoding="utf-8")

        instant = datetime(2026, 9, 19, 12, 30, tzinfo=timezone.utc)
        publisher = BIMSheetPublishingService(
            self.document, exporter=exporter, clock=lambda: instant
        )
        with tempfile.TemporaryDirectory() as directory:
            result = publisher.publish_set(directory, "pdf")

            self.assertEqual([first, second], [item.page for item in result.sheets])
            self.assertEqual(
                ["A-101 - Ground-Plan.pdf", "A-202 - Upper Plan.pdf"],
                [item.path.name for item in result.sheets],
            )
            self.assertEqual([first, second], [call[0] for call in calls])
            self.assertTrue(all(item.path.is_file() for item in result.sheets))
            self.assertEqual("Published", str(first.SheetStatus))
            self.assertEqual("P01", first.LastPublishedRevision)
            self.assertEqual("pdf", first.LastPublishedFormat)
            self.assertEqual(instant.isoformat(), first.LastPublishedAt)
            self.assertEqual(64, len(first.LastPublishedSHA256))

            path = directory + "/published.FCStd"
            self.document.saveAs(path)
            FreeCAD.closeDocument(self.document.Name)
            self.document = FreeCAD.openDocument(path)
            reopened = self.document.getObject("FirstPublishedSheet")
            self.assertEqual("P01", reopened.LastPublishedRevision)
            self.assertEqual("pdf", reopened.LastPublishedFormat)

    def test_sheet_publication_requires_explicit_overwrite(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path, BIMSheetMetadata(number="A-001", title="Cover")
        )
        calls = []

        def exporter(_page, path, _format):
            calls.append(path)
            path.write_text("new", encoding="utf-8")

        publisher = BIMSheetPublishingService(self.document, exporter=exporter)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / publisher.filename_for(page, "svg")
            target.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(SheetPublicationError, "overwrite"):
                publisher.publish_sheet(page, directory, "svg")
            self.assertEqual([], calls)
            self.assertEqual("existing", target.read_text(encoding="utf-8"))

            publisher.publish_sheet(page, directory, "svg", overwrite=True)
            self.assertEqual("new", target.read_text(encoding="utf-8"))

    def test_sheet_publication_rejects_invalid_format_and_unlinked_views(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path, BIMSheetMetadata(number="A-010", title="Invalid")
        )
        publisher = BIMSheetPublishingService(self.document)
        with self.assertRaisesRegex(ValueError, "unsupported publication format"):
            publisher.filename_for(page, "dwg")

        unlinked = self.document.addObject("TechDraw::DrawViewArch", "UnlinkedView")
        page.addView(unlinked)
        self.document.recompute()
        with self.assertRaisesRegex(SheetPublicationError, "no saved BIM view"):
            publisher.validate(page)

    def test_sheet_set_publication_cleans_staged_files_after_failure(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        sheets = BIMSheetService(self.document)
        sheets.create_sheet(
            template_path, BIMSheetMetadata(number="A-001", title="First", order=1)
        )
        sheets.create_sheet(
            template_path, BIMSheetMetadata(number="A-002", title="Second", order=2)
        )
        count = 0

        def exporter(_page, path, _format):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("export failed")
            path.write_text("staged", encoding="utf-8")

        publisher = BIMSheetPublishingService(self.document, exporter=exporter)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "export failed"):
                publisher.publish_set(directory, "pdf")
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_sheet_issue_manifest_is_immutable_exportable_and_persistent(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path,
            BIMSheetMetadata(
                number="A-101", title="Plan", revision="P01", issue="ISSUE-1"
            ),
        )

        def exporter(sheet, path, format):
            path.write_text(
                "{}:{}:{}".format(format, sheet.SheetNumber, sheet.Revision),
                encoding="utf-8",
            )

        instant = datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            BIMSheetPublishingService(
                self.document, exporter=exporter, clock=lambda: instant
            ).publish_sheet(page, directory)
            issues = BIMSheetIssueService(self.document, clock=lambda: instant)
            self.document.openTransaction("Create issue")
            issue = issues.create_issue("ISSUE-1", "Planning Issue")
            self.document.commitTransaction()
            issue_name = issue.Name
            self.document.undo()
            self.assertIsNone(self.document.getObject(issue_name))
            self.document.redo()
            issue = self.document.getObject(issue_name)
            manifest_path = issues.export_manifest(
                issue, Path(directory) / "ISSUE-1.json"
            )

            self.assertEqual("ISSUE-1", issue.IssueIdentifier)
            self.assertEqual(1, issue.IssueOrder)
            self.assertEqual(64, len(issue.ManifestSHA256))
            self.assertEqual(issue.ManifestJSON + "\n", manifest_path.read_text("utf-8"))
            self.assertEqual("A-101", issues.manifest_for(issue)["sheets"][0]["number"])
            with self.assertRaises(Exception):
                issue.ManifestJSON = "{}"

            manifest_digest = issue.ManifestSHA256
            document_path = directory + "/issued.FCStd"
            self.document.saveAs(document_path)
            FreeCAD.closeDocument(self.document.Name)
            self.document = FreeCAD.openDocument(document_path)
            reopened = BIMSheetIssueService(self.document).issues()[0]
            self.assertEqual("ISSUE-1", reopened.IssueIdentifier)
            self.assertEqual(manifest_digest, reopened.ManifestSHA256)

    def test_sheet_issue_comparison_detects_added_removed_and_changed_sheets(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        sheets = BIMSheetService(self.document)
        first = sheets.create_sheet(
            template_path,
            BIMSheetMetadata(number="A-101", title="Plan", revision="P01", issue="I1", order=1),
        )
        removed = sheets.create_sheet(
            template_path,
            BIMSheetMetadata(number="A-201", title="Section", revision="P01", issue="I1", order=2),
        )

        def exporter(sheet, path, _format):
            path.write_text(
                "{}:{}".format(sheet.SheetNumber, sheet.Revision), encoding="utf-8"
            )

        with tempfile.TemporaryDirectory() as directory:
            publisher = BIMSheetPublishingService(self.document, exporter=exporter)
            publisher.publish_set(directory)
            service = BIMSheetIssueService(self.document)
            issue_one = service.create_issue("I1")

            first.Issue = "I2"
            first.Revision = "P02"
            first.SheetTitle = "Updated Plan"
            added = sheets.create_sheet(
                template_path,
                BIMSheetMetadata(number="A-301", title="Elevation", revision="P01", issue="I2", order=3),
            )
            publisher.publish_sheet(first, directory, overwrite=True)
            publisher.publish_sheet(added, directory)
            issue_two = service.create_issue("I2", pages=(first, added))
            comparison = service.compare(issue_two)

            self.assertIs(issue_one, issue_two.PreviousIssue)
            self.assertEqual(("A-301",), comparison.added)
            self.assertEqual(("A-201",), comparison.removed)
            self.assertEqual(
                (("A-101", ("revision", "metadata", "output")),),
                comparison.changed,
            )

    def test_sheet_issue_rejects_incomplete_or_inconsistent_publications(self):
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/ISO/A4_Landscape_ISO5457_minimal.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path,
            BIMSheetMetadata(number="A-001", title="Cover", revision="P01", issue="I1"),
        )
        service = BIMSheetIssueService(self.document)
        with self.assertRaisesRegex(SheetIssueError, "has not been published"):
            service.create_issue("I1")
        with self.assertRaisesRegex(SheetIssueError, "does not match"):
            service.create_issue("I2")

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
            ("Project", "Views", "CurrentView", "Sheets", "Issues"),
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

        self.assertEqual(5, model.rowCount())
        self.assertEqual(
            ("Project", "Views", "Current View", "Sheets", "Issues"),
            tuple(model.index(row, 0).data() for row in range(5)),
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
        self.assertIn("BIMViewDefinition", drawing_view.PropertiesList)
        self.assertNotIn("BIMSheetScale", definition.PropertiesList)
        self.assertNotIn("BIMRenderMode", definition.PropertiesList)

    def test_first_sheet_view_fits_and_centers_in_printable_area(self):
        source = self.document.addObject("App::FeaturePython", "CenteredPlanSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        view_service = BIMViewService(self.document, view=_RecordingView([]))
        definition = view_service.create_view(
            "Centered Plan", "Plan", source, capture=False
        )
        sheet_service = BIMSheetService(self.document)
        page = sheet_service.create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Scale = 0.01

        drawing_view = view_service.place_on_sheet(definition, page)
        self.document.recompute()

        footprint = BIMSheetFootprintProvider().for_view(drawing_view)
        bounds = footprint.at(drawing_view.X.Value, drawing_view.Y.Value)
        annotation = BIMSheetViewTitleService.annotation_for(drawing_view)
        margins = sheet_service.margins_for(page)
        self.assertGreater(drawing_view.Scale, page.Scale)
        self.assertAlmostEqual(
            (margins.left + page.PageWidth - margins.right) / 2.0,
            bounds.x,
        )
        self.assertAlmostEqual(
            (margins.bottom + page.PageHeight - margins.top) / 2.0,
            bounds.y,
        )
        self.assertAlmostEqual(drawing_view.X.Value, annotation.X.Value)
        self.assertAlmostEqual(
            drawing_view.Y.Value + annotation.OwnerOffsetY.Value,
            annotation.Y.Value,
        )
        geometry_height = svg_footprint(
            drawing_view.Symbol, drawing_view.Scale
        )[1]
        title_height = len(annotation.Text) * annotation.TextSize.Value * 1.25
        self.assertLessEqual(
            annotation.OwnerOffsetY.Value + title_height / 2.0,
            -geometry_height / 2.0 - annotation.BIMTitleGap.Value,
        )

    def test_create_sheet_from_view_uses_shared_creation_and_placement(self):
        source = self.document.addObject("App::FeaturePython", "SheetShortcutSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Ground Floor Plan", "Plan", source, capture=False
        )
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )

        page, drawing_view = service.create_sheet_from_view(
            definition, template_path, page_scale=0.01
        )

        self.assertTrue(BIMSheetService.is_sheet(page))
        self.assertEqual("Ground Floor Plan", page.SheetTitle)
        self.assertEqual("G-001 — Ground Floor Plan", page.Label)
        self.assertIs(definition, drawing_view.BIMViewDefinition)
        self.assertIn(drawing_view, page.Views)
        self.assertGreater(drawing_view.Scale, page.Scale)

    def test_sheet_placement_uses_first_free_position_and_explicit_override(self):
        storey = self.document.addObject("App::FeaturePython", "LayoutStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        first_definition = service.create_view(
            "First Layout Plan", "Plan", storey, capture=False
        )
        second_definition = service.create_view(
            "Second Layout Plan", "Plan", storey, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "LayoutPage")
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "LayoutTemplate")
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template

        first = service.place_on_sheet(first_definition, page)
        second = service.place_on_sheet(second_definition, page)
        with self.assertRaisesRegex(SheetLayoutError, "overlaps"):
            BIMSheetService(self.document).validate_view_layout(
                page,
                second,
                position=(first.X.Value, first.Y.Value),
            )
        explicit = service.place_on_sheet(
            first_definition,
            page,
            position=(page.PageWidth - 42, page.PageHeight - 42),
            allow_duplicate=True,
        )

        self.assertNotEqual((first.X, first.Y), (second.X, second.Y))
        self.assertEqual(page.PageWidth - 42, explicit.X.Value)
        self.assertEqual(page.PageHeight - 42, explicit.Y.Value)

    def test_sheet_placement_rejects_duplicates_and_removes_only_placement(self):
        storey = self.document.addObject("App::FeaturePython", "DuplicateStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Duplicate Plan", "Plan", storey, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "DuplicatePage")
        template = self.document.addObject(
            "TechDraw::DrawSVGTemplate", "DuplicateTemplate"
        )
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template
        first = service.place_on_sheet(definition, page)

        with self.assertRaisesRegex(ValueError, "already placed"):
            service.place_on_sheet(definition, page)
        second = service.place_on_sheet(definition, page, allow_duplicate=True)
        self.assertEqual((first, second), service.placements_for(definition, page))

        service.remove_sheet_placement(first)

        self.assertIsNotNone(self.document.getObject(definition.Name))
        self.assertEqual((second,), service.placements_for(definition, page))

    def test_navigator_locates_and_undoably_removes_sheet_placement(self):
        storey = self.document.addObject("App::FeaturePython", "ActionStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Action Plan", "Plan", storey, capture=False)
        page = self.document.addObject("TechDraw::DrawPage", "ActionPage")
        template = self.document.addObject("TechDraw::DrawSVGTemplate", "ActionTemplate")
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template
        drawing_view = service.place_on_sheet(definition, page)
        drawing_name = drawing_view.Name
        command = BIM_Views()
        command.contextObject = drawing_view

        command.locatePlacement()
        self.assertEqual([drawing_view], FreeCADGui.Selection.getSelection())
        command.removeFromSheet()
        self.assertIsNone(self.document.getObject(drawing_name))
        self.assertIsNotNone(self.document.getObject(definition.Name))

        self.document.undo()
        restored = self.document.getObject(drawing_name)
        self.assertIsNotNone(restored)
        self.assertIs(definition, restored.BIMViewDefinition)
        self.assertIn(restored, page.Views)

    def test_navigator_lists_sheet_metadata_and_linked_placements(self):
        storey = self.document.addObject("App::FeaturePython", "NavigatorSheetStorey")
        storey.addProperty("App::PropertyPlacement", "Placement")
        view_service = BIMViewService(self.document, view=_RecordingView([]))
        definition = view_service.create_view(
            "Navigator Sheet Plan", "Plan", storey, capture=False
        )
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page = BIMSheetService(self.document).create_sheet(
            template_path,
            BIMSheetMetadata(
                number="A-201",
                title="Plans",
                discipline="Architectural",
                revision="P02",
                status="Shared",
                order=201,
            ),
            name="NavigatorSheet",
        )
        drawing_view = view_service.place_on_sheet(definition, page)
        navigator = BIMNavigatorModel(self.document)

        sheet = navigator.sheet_nodes()[0]
        self.assertIs(page, sheet.page)
        self.assertEqual((drawing_view,), tuple(p.drawing_view for p in sheet.placements))

        model = BIMNavigatorQtModel(navigator)
        sheets = model.index(3, 0)
        sheet_index = model.index(0, 0, sheets)
        placement_index = model.index(0, 0, sheet_index)
        self.assertEqual("A-201 — Plans", sheet_index.data())
        self.assertEqual("Architectural", model.index(0, 1, sheets).data())
        self.assertEqual("P02 · Shared", model.index(0, 2, sheets).data())
        self.assertEqual("sheet-placement", model.kind_for_index(placement_index))
        self.assertIs(drawing_view, model.object_for_index(placement_index))
        self.assertEqual(2, len(model.indexes_for_object(definition)))

    def test_sheet_placement_has_persistent_numbered_title(self):
        source = self.document.addObject("App::FeaturePython", "TitledSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view("Ground Floor", "Plan", source, capture=False)
        template_path = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page = BIMSheetService(self.document).create_sheet(template_path)
        drawing_view = service.place_on_sheet(definition, page)
        annotation = BIMSheetViewTitleService.annotation_for(drawing_view)

        import ArchSectionPlane

        with patch.object(ArchSectionPlane, "getSVG", return_value=""):
            drawing_view.Scale = 0.01
            self.document.recompute()
            self.assertEqual("1", drawing_view.ViewNumber)
            self.assertEqual(["1  Ground Floor", "1:100"], annotation.Text)
            self.assertIs(drawing_view, annotation.Owner)
            self.assertIn(annotation, page.Views)

            drawing_view.Scale = 0.02
            definition.Label = "Level 00"
            self.document.recompute()
            self.assertEqual(["1  Level 00", "1:50"], annotation.Text)

            drawing_view.ViewTitle = "Entrance Plan"
            drawing_view.X = 90
            drawing_view.Y = 70
            self.document.recompute()
            self.assertEqual(["1  Entrance Plan", "1:50"], annotation.Text)
            self.assertEqual(90, annotation.X.Value)
            self.assertEqual(70 + annotation.OwnerOffsetY.Value, annotation.Y.Value)

    def test_sheet_view_numbers_are_unique_and_fill_gaps(self):
        page = BIMSheetService(self.document).create_sheet(
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg",
            name="NumberedPage",
        )
        title_service = BIMSheetViewTitleService(self.document)
        first = self.document.addObject("TechDraw::DrawViewArch", "FirstNumbered")
        second = self.document.addObject("TechDraw::DrawViewArch", "SecondNumbered")
        page.addView(first)
        page.addView(second)

        title_service.create(page, first, "2")
        with self.assertRaisesRegex(ValueError, "unique"):
            title_service.create(page, second, "2")
        self.assertEqual("1", title_service.next_number(page))
        self.assertEqual("1:20", format_scale(0.05))

    def test_techdraw_title_binding_is_generic(self):
        owner = self.document.addObject("TechDraw::DrawViewSymbol", "GenericView")
        owner.ViewNumber = "A"
        owner.ViewTitle = "Detail"
        owner.Scale = 0.25
        owner.X = 40
        owner.Y = 30
        annotation = self.document.addObject(
            "TechDraw::DrawViewAnnotation", "GenericViewTitle"
        )
        annotation.Owner = owner
        annotation.TextTemplate = ["{ViewNumber}  {ViewTitle|Label}", "{Scale}"]
        annotation.FollowOwnerPosition = True
        annotation.OwnerOffsetX = 2
        annotation.OwnerOffsetY = -5

        self.document.recompute()

        self.assertEqual(["A  Detail", "1:4"], annotation.Text)
        self.assertEqual(42, annotation.X.Value)
        self.assertEqual(25, annotation.Y.Value)

        owner.ViewTitle = ""
        owner.Label = "Fallback"
        self.document.recompute()
        self.assertEqual(["A  Fallback", "1:4"], annotation.Text)

    def test_saved_view_visibility_is_applied_within_sheet_source_scope(self):
        normally_visible = self.document.addObject("PartDesign::Feature", "Visible")
        forced_visible = self.document.addObject("PartDesign::Feature", "ForcedVisible")
        forced_hidden = self.document.addObject("PartDesign::Feature", "ForcedHidden")
        outside_scope = self.document.addObject("PartDesign::Feature", "OutsideScope")
        definition = self.document.addObject("App::ViewDefinition", "VisibilityView")
        definition.ForcedVisible = [forced_visible, outside_scope]
        definition.ForcedHidden = [forced_hidden]

        visible = apply_view_visibility(
            (normally_visible, forced_visible, forced_hidden),
            definition,
            (normally_visible, forced_hidden),
        )

        self.assertEqual([normally_visible, forced_visible], visible)

    def test_saved_view_changes_recompute_linked_sheet_view(self):
        import Arch
        import ArchSectionPlane

        wall = self.document.addObject("PartDesign::Feature", "RecomputeWall")
        wall.Shape = Part.makeBox(1000, 200, 1000)
        original = Arch.makeSectionPlane([wall], name="OriginalSection")
        replacement = Arch.makeSectionPlane([wall], name="ReplacementSection")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Recomputing Section", "Section", original, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "RecomputePage")
        template = self.document.addObject(
            "TechDraw::DrawSVGTemplate", "RecomputeTemplate"
        )
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template
        drawing_view = service.place_on_sheet(definition, page)

        with patch.object(ArchSectionPlane, "getSVG", return_value="") as get_svg:
            self.document.recompute()
            get_svg.reset_mock()
            drawing_view.FontSize = 10.0
            drawing_view.LineSpacing = 1.2
            self.document.recompute()
            get_svg.assert_called_once()
            self.assertAlmostEqual(6.0, get_svg.call_args.kwargs["linespacing"])

            get_svg.reset_mock()
            definition.BIMContextSource = replacement
            self.document.recompute()
            get_svg.assert_called_once()
            args, kwargs = get_svg.call_args
            self.assertIs(replacement, args[0])
            self.assertIs(definition, kwargs["viewDefinition"])

            get_svg.reset_mock()
            definition.ReferenceFrame = FreeCAD.Placement(
                FreeCAD.Vector(25, 50, 75), FreeCAD.Rotation()
            )
            self.document.recompute()
            get_svg.assert_called_once()

            get_svg.reset_mock()
            definition.ForcedHidden = [wall]
            self.document.recompute()
            get_svg.assert_called_once()

        self.assertIs(original, drawing_view.Source)
        request = service.request_for(definition)
        self.assertEqual(definition.ReferenceFrame, request.reference_frame)

    def test_sheet_view_link_and_instance_style_survive_save_reopen(self):
        source = self.document.addObject("App::FeaturePython", "PersistentSource")
        source.addProperty("App::PropertyPlacement", "Placement")
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Persistent Plan", "Plan", source, capture=False
        )
        drawing_view = self.document.addObject(
            "TechDraw::DrawViewArch", "PersistentDrawingView"
        )
        drawing_view.Source = source
        drawing_view.BIMViewDefinition = definition
        drawing_view.ShowHidden = True
        drawing_view.Scale = 0.02
        drawing_view.X = 123
        drawing_view.Y = 77

        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/sheet-view.FCStd"
            self.document.saveAs(path)
            FreeCAD.closeDocument(self.document.Name)
            self.document = FreeCAD.openDocument(path)

            reopened_view = self.document.getObject("PersistentDrawingView")
            reopened_definition = self.document.getObject("BIMView")
            self.assertIs(reopened_definition, reopened_view.BIMViewDefinition)
            self.assertTrue(reopened_view.ShowHidden)
            self.assertAlmostEqual(0.02, reopened_view.Scale)
            self.assertAlmostEqual(123, reopened_view.X.Value)
            self.assertAlmostEqual(77, reopened_view.Y.Value)
            self.assertNotIn("BIMShowHidden", reopened_definition.PropertiesList)

    def test_plan_section_and_elevation_placements_render_svg(self):
        import Arch
        import ArchSectionPlane

        plan_wall = Arch.makeWall(length=3000, width=200, height=3000)
        storey = Arch.makeFloor(name="RenderedStorey")
        storey.addObject(plan_wall)

        section_wall = Arch.makeWall(length=3000, width=200, height=3000)
        section = Arch.makeSectionPlane([section_wall], name="RenderedSection")
        section.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )

        elevation_box = self.document.addObject(
            "PartDesign::Feature", "RenderedElevationBox"
        )
        elevation_box.Shape = Part.makeBox(1000, 200, 1200)
        elevation = Arch.makeSectionPlane([elevation_box], name="RenderedElevation")
        elevation.Purpose = "Elevation"
        elevation.Depth = 2000
        self.document.recompute()

        service = BIMViewService(self.document, view=_RecordingView([]))
        definitions = (
            service.create_view("Rendered Plan", "Plan", storey, capture=False),
            service.create_view(
                "Rendered Section", "Section", section, capture=False
            ),
            service.create_view(
                "Rendered Elevation", "Elevation", elevation, capture=False
            ),
        )
        page = self.document.addObject("TechDraw::DrawPage", "RenderedPage")
        template = self.document.addObject(
            "TechDraw::DrawSVGTemplate", "RenderedTemplate"
        )
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template

        for index, definition in enumerate(definitions, start=1):
            source = definition.BIMContextSource
            svg = ArchSectionPlane.getSVG(
                source,
                techdraw=True,
                renderMode="Wireframe",
                viewDefinition=definition,
            )
            self.assertTrue(svg, definition.Purpose)
            drawing_view = service.place_on_sheet(definition, page)
            drawing_view.Scale = 0.01 * index
            drawing_view.ShowFill = index == 2

        self.document.recompute()
        drawing_views = [
            view
            for view in page.Views
            if view.isDerivedFrom("TechDraw::DrawViewArch")
        ]
        self.assertEqual(3, len(drawing_views))
        for index, drawing_view in enumerate(drawing_views, start=1):
            self.assertIn("<svg", drawing_view.Symbol)
            self.assertGreater(len(drawing_view.Symbol), 100)
            self.assertAlmostEqual(0.01 * index, drawing_view.Scale)
            self.assertEqual(index == 2, drawing_view.ShowFill)

    def test_get_svg_compatibility_wrapper_matches_context_renderer(self):
        import Arch
        import ArchSectionPlane
        import Draft

        wall = Arch.makeWall(length=3000, width=200, height=3000)
        section = Arch.makeSectionPlane([wall], name="ContextSection")
        section.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Context Section", "Section", section, capture=False
        )
        self.document.recompute()

        wrapped = ArchSectionPlane.getSVG(
            section, techdraw=True, viewDefinition=definition
        )
        objects, cutplane, only_solids, clip, direction = (
            ArchSectionPlane.getSectionData(section)
        )
        context = resolve_drawing_context(
            section,
            objects,
            view_definition=definition,
            normally_visible=Draft.removeHidden(objects),
            cutplane=cutplane,
            only_solids=only_solids,
            clip=clip,
            direction=direction,
        )
        contextual = ArchSectionPlane.render_drawing_context(
            context, techdraw=True
        )

        self.assertTrue(wrapped)
        self.assertEqual(wrapped, contextual)

    def test_saved_view_visibility_changes_rendered_svg(self):
        import Arch
        import ArchSectionPlane

        first = Arch.makeWall(length=1000, width=200, height=1000)
        second = Arch.makeWall(length=1000, width=200, height=1000)
        second.Placement.Base.y = 500
        section = Arch.makeSectionPlane([first, second], name="VisibilitySection")
        section.Placement = FreeCAD.Placement(
            FreeCAD.Vector(500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Visibility Section", "Section", section, capture=False
        )
        self.document.recompute()

        complete = ArchSectionPlane.getSVG(
            section, techdraw=True, viewDefinition=definition
        )
        definition.ForcedHidden = [second]
        hidden = ArchSectionPlane.getSVG(
            section, techdraw=True, viewDefinition=definition
        )
        second.ViewObject.Visibility = False
        definition.ForcedHidden = []
        definition.ForcedVisible = [second]
        restored = ArchSectionPlane.getSVG(
            section, techdraw=True, viewDefinition=definition
        )

        self.assertTrue(complete)
        self.assertTrue(hidden)
        self.assertNotEqual(complete, hidden)
        self.assertEqual(complete, restored)

    def test_rendered_sheet_view_reopens_and_tracks_reference_frame(self):
        import Arch

        wall = Arch.makeWall(length=3000, width=200, height=3000)
        section = Arch.makeSectionPlane([wall], name="PersistentRenderedSection")
        section.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        service = BIMViewService(self.document, view=_RecordingView([]))
        definition = service.create_view(
            "Persistent Render", "Section", section, capture=False
        )
        page = self.document.addObject("TechDraw::DrawPage", "PersistentRenderPage")
        template = self.document.addObject(
            "TechDraw::DrawSVGTemplate", "PersistentRenderTemplate"
        )
        template.Template = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Templates/Default_Template_A4_Landscape.svg"
        )
        page.Template = template
        drawing_view = service.place_on_sheet(definition, page)
        self.document.recompute()
        original_svg = drawing_view.Symbol
        self.assertGreater(len(original_svg), 100)

        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/rendered-sheet-view.FCStd"
            self.document.saveAs(path)
            FreeCAD.closeDocument(self.document.Name)
            self.document = FreeCAD.openDocument(path)
            reopened_view = self.document.getObject("BIMSavedView")
            reopened_definition = self.document.getObject("BIMView")
            self.assertEqual(original_svg, reopened_view.Symbol)

            frame = FreeCAD.Placement(reopened_definition.ReferenceFrame)
            frame.Rotation = frame.Rotation.multiply(
                FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 30)
            )
            reopened_definition.ReferenceFrame = frame
            self.document.recompute()

            self.assertNotEqual(original_svg, reopened_view.Symbol)
            self.assertGreater(len(reopened_view.Symbol), 100)

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

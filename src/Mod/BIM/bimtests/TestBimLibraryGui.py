# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
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

"""GUI tests for BIM Library semantic definition handling."""

import Arch
import ArchEquipment
import BimLibrarySources
import FreeCAD
import json
import os
import Part
import tempfile
from bimcommands import BimLibrary, BimPlanSession
from bimtests.TestArchBaseGui import TestArchBaseGui
from unittest.mock import patch


class TestBimLibraryGui(TestArchBaseGui):
    def _write_library_root_metadata(self, root, label):
        with open(os.path.join(root, "library.json"), "w", encoding="utf-8") as handle:
            json.dump({"label": label}, handle)

    def _write_library_asset(self, root, folder_name, label, asset_id):
        asset_dir = os.path.join(root, folder_name)
        os.makedirs(asset_dir, exist_ok=True)
        manifest_path = os.path.join(asset_dir, "asset.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "id": asset_id,
                    "label": label,
                    "kind": "equipment",
                    "representations": {
                        "model3d": {"file": folder_name.lower() + ".fcstd"},
                    },
                },
                handle,
            )
        return manifest_path

    def _write_preview_asset_bundle(
        self, root, label="Preview Bed", asset_id="furniture.bed.preview"
    ):
        model_path = os.path.join(root, "bed.fcstd")
        plan_path = os.path.join(root, "bed-plan.fcstd")
        manifest_path = os.path.join(root, "asset.json")

        model_doc = FreeCAD.newDocument("PreviewModel")
        model = model_doc.addObject("Part::Box", "DoubleBed")
        model.Length = 1400
        model.Width = 1950
        model.Height = 600
        model_doc.recompute()
        model_doc.saveAs(model_path)
        FreeCAD.closeDocument(model_doc.Name)

        plan_doc = FreeCAD.newDocument("PreviewPlan")
        plan = plan_doc.addObject("Part::Feature", "BedPlan")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1400, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 0, 0), FreeCAD.Vector(1400, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 1950, 0), FreeCAD.Vector(0, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(0, 1950, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        plan.Placement.Base = FreeCAD.Vector(125.0, 958.85, 0)
        plan_doc.recompute()
        plan_doc.saveAs(plan_path)
        FreeCAD.closeDocument(plan_doc.Name)

        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "id": asset_id,
                    "label": label,
                    "kind": "equipment",
                    "representations": {
                        "model3d": {"file": "bed.fcstd", "root": "DoubleBed"},
                        "plan2d": {"file": "bed-plan.fcstd", "root": "BedPlan"},
                    },
                },
                handle,
            )

        return manifest_path

    def _count_coin_nodes(self, node, coin_class):
        if not node:
            return 0

        count = 0
        stack = [node]
        class_type = coin_class.getClassTypeId()

        while stack:
            current = stack.pop()
            if not current:
                continue
            if current.isOfType(class_type):
                count += 1
            if hasattr(current, "getNumChildren"):
                for index in range(current.getNumChildren()):
                    stack.append(current.getChild(index))

        return count

    def test_equipment_library_definitions_normalize_to_semantic_equipment_roots(self):
        """Library equipment definitions should expose equipment semantics to Plan Edit."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)
        source_path = "library://furniture/bed/double"
        descriptor = {
            "label": "Double Bed",
            "kind": "equipment",
        }

        asset_group = self.document.addObject("App::DocumentObjectGroup", "SymbolAsset")
        panel._ensure_library_metadata(asset_group, source_path, role="asset")

        base = self.document.addObject("Part::Box", "DoubleBedShape")
        base.Length = 1400
        base.Width = 1950
        base.Height = 600
        panel._ensure_library_metadata(base, source_path, role="instance")
        asset_group.addObject(base)
        stale_link = self.document.addObject("App::Link", "LegacyBedLink")
        stale_link.setLink(base)

        plan = self.document.addObject("Part::Feature", "DoubleBedPlan")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1400, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 0, 0), FreeCAD.Vector(1400, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(1400, 1950, 0), FreeCAD.Vector(0, 1950, 0)),
                Part.makeLine(FreeCAD.Vector(0, 1950, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        panel._ensure_library_metadata(plan, source_path, role="plan2d")
        asset_group.addObject(plan)

        normalized_roots = panel._normalize_definition_roots(
            self.document,
            asset_group,
            descriptor,
            [base],
        )
        panel._attach_plan_symbol_roots(normalized_roots, [plan])
        self.document.recompute()
        self.pump_gui_events()

        self.assertEqual(1, len(normalized_roots))
        equipment = normalized_roots[0]
        self.assertEqual("Equipment", getattr(getattr(equipment, "Proxy", None), "Type", None))
        self.assertIs(equipment.Base, base)
        self.assertEqual("source", base.LibraryDefinitionRole)
        self.assertEqual([plan], list(equipment.PlanSymbols))
        self.assertEqual([equipment], panel._get_symbol_definition_roots(asset_group))
        self.assertIs(stale_link.LinkedObject, equipment)
        self.assertIn("Footprint", equipment.ViewObject.listDisplayModes())
        self.assertGreater(equipment.ViewObject.Proxy.lcoords.point.getNum(), 0)
        self.assertGreater(equipment.ViewObject.Proxy.lset.numVertices.getNum(), 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertIs(session._get_plan_semantic_object(stale_link), equipment)
        self.assertTrue(session.visibility.is_plan_equipment_object(stale_link))
        self.assertTrue(session.visibility.is_supported_plan_object(stale_link))

        live_link = panel._create_symbol_link(self.document, equipment)
        self.assertFalse(session.document_visuals.is_hidden_library_definition_object(live_link))
        self.assertTrue(session.document_visuals.should_register_created_plan_object(live_link))
        self.document.recompute()
        self.pump_gui_events()
        session.document_visuals.flush_created_plan_objects()
        session.document_visuals.refresh_plan_object_footprint_display(live_link)
        self.pump_gui_events()

        from pivy import coin

        self.assertGreater(
            self._count_coin_nodes(live_link.ViewObject.RootNode, coin.SoLineSet),
            0,
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_asset_descriptor_reads_plan_anchor_and_facing(self):
        """Manifest-backed assets should expose authored plan insertion metadata."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "asset.json")
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "id": "furniture.bed.double",
                        "label": "Double Bed",
                        "kind": "equipment",
                        "representations": {
                            "model3d": {"file": "bed.fcstd", "root": "DoubleBed"},
                            "plan2d": {
                                "file": "bed-plan.fcstd",
                                "root": "BedPlan",
                                "anchor": [700, 975, 0],
                                "facing": [0, 1, 0],
                            },
                        },
                    },
                    handle,
                )

            descriptor = panel._build_asset_descriptor(manifest_path)

        self.assertEqual("Double Bed", descriptor["label"])
        self.assertIsNotNone(descriptor["plan_anchor"])
        self.assertIsNotNone(descriptor["plan_facing"])
        self.assertAlmostEqual(700.0, descriptor["plan_anchor"].x, delta=1e-6)
        self.assertAlmostEqual(975.0, descriptor["plan_anchor"].y, delta=1e-6)
        self.assertAlmostEqual(0.0, descriptor["plan_facing"].x, delta=1e-6)
        self.assertAlmostEqual(1.0, descriptor["plan_facing"].y, delta=1e-6)

    def test_library_insert_delta_uses_authored_plan_anchor(self):
        """Default library insertion should align the authored plan anchor with the picked point."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)
        panel.shape = Part.makeBox(1400, 1950, 1)

        equipment = Arch.makeEquipment()
        equipment.Shape = panel.shape.copy()
        equipment.PlanAnchor = FreeCAD.Vector(700, 975, 0)
        panel.instance_definition_roots = [equipment]

        class _Combo:
            def currentIndex(self):
                return 0

        class _Origin:
            comboOrigin = _Combo()

        panel.origin = _Origin()

        delta = panel.getDelta()

        self.assertAlmostEqual(-700.0, delta.x, delta=1e-6)
        self.assertAlmostEqual(-975.0, delta.y, delta=1e-6)
        self.assertAlmostEqual(0.0, delta.z, delta=1e-6)

    def test_plan_symbol_preview_matches_imported_plan_symbol_geometry(self):
        """Preview ghost geometry should match the imported plan-symbol placement semantics."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)
        panel.mainDocName = self.document.Name
        self.document.recompute()
        FreeCAD.setActiveDocument(self.document.Name)
        if FreeCAD.GuiUp:
            from FreeCAD import Gui as FreeCADGuiModule

            FreeCADGuiModule.ActiveDocument = FreeCADGuiModule.getDocument(self.document.Name)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "bed.fcstd")
            plan_path = os.path.join(tmpdir, "bed-plan.fcstd")
            manifest_path = os.path.join(tmpdir, "asset.json")

            model_doc = FreeCAD.newDocument("PreviewModel")
            model = model_doc.addObject("Part::Box", "DoubleBed")
            model.Length = 1400
            model.Width = 1950
            model.Height = 600
            model_doc.recompute()
            model_doc.saveAs(model_path)
            FreeCAD.closeDocument(model_doc.Name)

            plan_doc = FreeCAD.newDocument("PreviewPlan")
            plan = plan_doc.addObject("Part::Feature", "BedPlan")
            plan.Shape = Part.makeCompound(
                [
                    Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1400, 0, 0)),
                    Part.makeLine(FreeCAD.Vector(1400, 0, 0), FreeCAD.Vector(1400, 1950, 0)),
                    Part.makeLine(FreeCAD.Vector(1400, 1950, 0), FreeCAD.Vector(0, 1950, 0)),
                    Part.makeLine(FreeCAD.Vector(0, 1950, 0), FreeCAD.Vector(0, 0, 0)),
                ]
            )
            plan.Placement.Base = FreeCAD.Vector(125.0, 958.85, 0)
            plan_doc.recompute()
            plan_doc.saveAs(plan_path)
            FreeCAD.closeDocument(plan_doc.Name)

            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "id": "furniture.bed.preview",
                        "label": "Preview Bed",
                        "kind": "equipment",
                        "representations": {
                            "model3d": {"file": "bed.fcstd", "root": "DoubleBed"},
                            "plan2d": {"file": "bed-plan.fcstd", "root": "BedPlan"},
                        },
                    },
                    handle,
                )

            FreeCAD.setActiveDocument(self.document.Name)
            if FreeCAD.GuiUp:
                from FreeCAD import Gui as FreeCADGuiModule

                FreeCADGuiModule.ActiveDocument = FreeCADGuiModule.getDocument(self.document.Name)

            roots = panel._ensure_symbol_definition_roots(self.document, manifest_path)
            self.document.recompute()

        equipment = roots[0]
        expected_shapes = list(ArchEquipment.get_plan_representation_shapes(equipment))
        self.assertEqual(1, len(expected_shapes))
        expected_bb = expected_shapes[0].BoundBox

        with patch.object(panel, "_should_prefer_plan_symbol_preview", return_value=True):
            preview_shape = panel._build_definition_preview_shape(roots)

        self.assertIsNotNone(preview_shape)
        self.assertAlmostEqual(expected_bb.XMin, preview_shape.BoundBox.XMin, delta=1e-6)
        self.assertAlmostEqual(expected_bb.YMin, preview_shape.BoundBox.YMin, delta=1e-6)
        self.assertAlmostEqual(expected_bb.XMax, preview_shape.BoundBox.XMax, delta=1e-6)
        self.assertAlmostEqual(expected_bb.YMax, preview_shape.BoundBox.YMax, delta=1e-6)

    def test_generated_preview_fallback_supports_distinct_2d_and_3d_modes(self):
        """Generated local previews should produce distinct cached 2D and 3D images."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = self._write_preview_asset_bundle(tmpdir)

            preview_2d = panel._get_generated_preview_path(
                manifest_path, BimLibrary.PREVIEW_MODE_2D
            )
            preview_3d = panel._get_generated_preview_path(
                manifest_path, BimLibrary.PREVIEW_MODE_3D
            )

            self.assertTrue(preview_2d)
            self.assertTrue(preview_3d)
            self.assertTrue(os.path.isfile(preview_2d))
            self.assertTrue(os.path.isfile(preview_3d))
            self.assertNotEqual(preview_2d, preview_3d)

            with open(preview_2d, "rb") as handle:
                image_2d = handle.read()
            with open(preview_3d, "rb") as handle:
                image_3d = handle.read()

            self.assertNotEqual(image_2d, image_3d)

    def test_auto_preview_mode_switches_with_plan_edit_session(self):
        """Auto preview mode should prefer 2D previews while Plan Edit is active."""

        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = self._write_preview_asset_bundle(tmpdir)

            with patch.object(
                panel,
                "_get_selected_preview_mode",
                return_value=BimLibrary.PREVIEW_MODE_AUTO,
            ), patch("bimcommands.BimPlanSession.get_active_session", return_value=None):
                preview_3d = panel.getThumbnail(manifest_path)
                self.assertTrue(preview_3d)
                self.assertTrue(os.path.isfile(preview_3d))
                self.assertEqual(BimLibrary.PREVIEW_MODE_3D, panel._get_effective_preview_mode())

            class _ActivePlanSession:
                _tearing_down = False

            with patch.object(
                panel,
                "_get_selected_preview_mode",
                return_value=BimLibrary.PREVIEW_MODE_AUTO,
            ), patch(
                "bimcommands.BimPlanSession.get_active_session",
                return_value=_ActivePlanSession(),
            ):
                preview_2d = panel.getThumbnail(manifest_path)
                self.assertTrue(preview_2d)
                self.assertTrue(os.path.isfile(preview_2d))
                self.assertEqual(BimLibrary.PREVIEW_MODE_2D, panel._get_effective_preview_mode())
                self.assertNotEqual(preview_3d, preview_2d)

    def test_configured_library_roots_migrate_legacy_destination(self):
        """Legacy single-root settings should migrate to the multi-root preference."""

        params = FreeCAD.ParamGet("User parameter:Plugins/parts_library")
        previous_destination = params.GetString("destination", "")
        previous_destinations = params.GetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "")
        previous_entries = params.GetString(
            BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY,
            "",
        )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                params.SetString("destination", tmpdir)
                params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "")
                params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, "")

                roots = BimLibrarySources.get_configured_library_roots()
                resolved_roots = BimLibrarySources.resolve_library_roots()

                self.assertEqual([tmpdir.replace("\\", "/")], roots)
                self.assertEqual(tmpdir.replace("\\", "/"), resolved_roots[0].path)
                self.assertEqual(
                    BimLibrarySources.LIBRARY_SOURCE_CONFIGURED,
                    resolved_roots[0].source,
                )
                self.assertEqual(tmpdir.replace("\\", "/"), params.GetString("destination", ""))
                self.assertEqual(
                    [tmpdir.replace("\\", "/")],
                    json.loads(
                        params.GetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "[]")
                    ),
                )
        finally:
            params.SetString("destination", previous_destination)
            params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, previous_destinations)
            params.SetString(
                BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, previous_entries
            )

    def test_configured_library_root_entries_preserve_order_and_enabled_state(self):
        """Configured root settings should preserve order and disabled entries."""

        params = FreeCAD.ParamGet("User parameter:Plugins/parts_library")
        previous_destination = params.GetString("destination", "")
        previous_destinations = params.GetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "")
        previous_entries = params.GetString(
            BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY,
            "",
        )

        try:
            with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
                normalized_a = root_a.replace("\\", "/")
                normalized_b = root_b.replace("\\", "/")

                BimLibrarySources.set_configured_library_root_entries(
                    [
                        BimLibrarySources.ConfiguredLibraryRoot(root_a, False),
                        BimLibrarySources.ConfiguredLibraryRoot(root_b, True),
                    ]
                )

                self.assertEqual(
                    [
                        {"path": normalized_a, "enabled": False},
                        {"path": normalized_b, "enabled": True},
                    ],
                    json.loads(
                        params.GetString(
                            BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, "[]"
                        )
                    ),
                )

                configured_entries = BimLibrarySources.get_configured_library_root_entries()
                self.assertEqual(
                    [normalized_a, normalized_b],
                    [entry.path for entry in configured_entries],
                )
                self.assertEqual(
                    [False, True],
                    [entry.enabled for entry in configured_entries],
                )
                self.assertEqual([normalized_b], BimLibrarySources.get_configured_library_roots())

                resolved_roots = BimLibrarySources.resolve_library_roots()
                self.assertEqual(normalized_b, resolved_roots[0].path)
                self.assertNotIn(normalized_a, [root.path for root in resolved_roots])
                self.assertEqual(normalized_b, params.GetString("destination", ""))
                self.assertEqual(
                    [normalized_b],
                    json.loads(
                        params.GetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "[]")
                    ),
                )
        finally:
            params.SetString("destination", previous_destination)
            params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, previous_destinations)
            params.SetString(
                BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, previous_entries
            )

    def test_manage_libraries_dialog_reorders_and_toggles_entries(self):
        """The manager dialog should preserve order changes and enabled state toggles."""

        from PySide import QtCore

        with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            self._write_library_root_metadata(root_a, "Parts Library")
            self._write_library_root_metadata(root_b, "Team Library")

            dialog = BimLibrary.BIM_LibraryRootManagerDialog(
                configured_roots=[
                    BimLibrarySources.ConfiguredLibraryRoot(root_a, True),
                    BimLibrarySources.ConfiguredLibraryRoot(root_b, False),
                ]
            )

            try:
                dialog.listWidget.setCurrentRow(1)
                dialog._move_current_item(-1)
                dialog.listWidget.item(0).setCheckState(QtCore.Qt.Checked)
                dialog.listWidget.item(1).setCheckState(QtCore.Qt.Unchecked)

                configured_entries = dialog.getConfiguredRoots()

                self.assertEqual(
                    [root_b.replace("\\", "/"), root_a.replace("\\", "/")],
                    [entry.path for entry in configured_entries],
                )
                self.assertEqual([True, False], [entry.enabled for entry in configured_entries])
                self.assertEqual("Team Library", configured_entries[0].label)
                self.assertEqual("Parts Library", configured_entries[1].label)
            finally:
                dialog.dialog.close()

    def test_local_library_panel_combines_tree_and_search_across_multiple_roots(self):
        """Multiple configured roots should appear together in the local tree and search index."""

        with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            self._write_library_root_metadata(root_a, "Parts Library")
            self._write_library_root_metadata(root_b, "Team Library")
            chair_manifest = self._write_library_asset(
                root_a,
                "ChairAsset",
                "Chair Asset",
                "furniture.chair.asset",
            )
            lamp_manifest = self._write_library_asset(
                root_b,
                "LampAsset",
                "Lamp Asset",
                "lighting.lamp.asset",
            )

            panel = BimLibrary.BIM_Library_TaskPanel(
                libraryroots=[
                    BimLibrarySources.LibraryRoot(
                        root_a, BimLibrarySources.LIBRARY_SOURCE_CONFIGURED
                    ),
                    BimLibrarySources.LibraryRoot(root_b, BimLibrarySources.LIBRARY_SOURCE_MODULE),
                ],
                target_doc_name=self.document.Name,
            )
            self.pump_gui_events()

            try:
                self.assertEqual(2, panel.filemodel.rowCount())
                self.assertEqual(root_a.replace("\\", "/"), panel.filemodel.item(0).toolTip())
                self.assertEqual(root_b.replace("\\", "/"), panel.filemodel.item(1).toolTip())
                self.assertEqual("Parts Library · 1", panel.filemodel.item(0).text())
                self.assertEqual("Team Library · 1", panel.filemodel.item(1).text())
                self.assertEqual("Online", panel.form.checkOnline.text())
                self.assertIn("2 local libraries", panel.form.labelLibraryRootStatus.text())
                self.assertTrue(panel.form.labelLibraryRootSummary.isHidden())
                self.assertTrue(panel.form.labelLibraryRootSources.isHidden())
                self.assertEqual("", panel.form.labelLibraryRootSources.text())
                self.assertNotIn(
                    root_a.replace("\\", "/"), panel.form.labelLibraryRootStatus.text()
                )
                self.assertNotIn(
                    root_b.replace("\\", "/"), panel.form.labelLibraryRootStatus.text()
                )
                self.assertEqual("Parts Library", panel.libraryroots[0].label)
                self.assertEqual("Team Library", panel.libraryroots[1].label)
                self.assertTrue(panel.form.tree.isExpanded(panel.filemodel.index(0, 0)))
                self.assertTrue(panel.form.tree.isExpanded(panel.filemodel.index(1, 0)))
                self.assertEqual(
                    "Select an asset to preview and insert",
                    panel.form.framePreview.text(),
                )

                search_entries = panel._get_local_search_index()
                self.assertEqual(
                    {chair_manifest.replace("\\", "/"), lamp_manifest.replace("\\", "/")},
                    {entry["path"].replace("\\", "/") for entry in search_entries},
                )
                self.assertEqual(
                    {"Chair Asset (Parts Library)", "Lamp Asset (Team Library)"},
                    {entry["display_label"] for entry in search_entries},
                )

                panel.setSearchModel("lamp asset")
                self.pump_gui_events()

                self.assertEqual(1, panel.filemodel.rowCount())
                self.assertEqual(
                    lamp_manifest.replace("\\", "/"), panel.filemodel.item(0).toolTip()
                )
                self.assertEqual("Lamp Asset (Team Library)", panel.filemodel.item(0).text())

                cleaned_path = panel.cleanPath(lamp_manifest)
                self.assertTrue(cleaned_path.endswith("LampAsset/lampasset.fcstd"))
                self.assertNotIn(root_b.replace("\\", "/"), cleaned_path)
            finally:
                panel.reject()

    def test_local_library_panel_restores_root_expansion_after_search(self):
        """The local tree should default-expand library roots and preserve collapsed roots."""

        with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)
            panel.libraryroots = [
                BimLibrarySources.LibraryRoot(root_a, BimLibrarySources.LIBRARY_SOURCE_CONFIGURED),
                BimLibrarySources.LibraryRoot(root_b, BimLibrarySources.LIBRARY_SOURCE_MODULE),
            ]
            panel._expanded_tree_paths = set()

            self.assertEqual(
                {root_a.replace("\\", "/"), root_b.replace("\\", "/")},
                panel._get_tree_expansion_restore_paths(),
            )

            panel._remember_tree_expansion_state(root_a, True)
            panel._remember_tree_expansion_state(root_b, True)
            panel._remember_tree_expansion_state(root_a, False)

            self.assertEqual(
                {root_b.replace("\\", "/")},
                panel._get_tree_expansion_restore_paths(),
            )

    def test_library_panel_refreshes_after_configured_root_changes(self):
        """Saving configured root changes should refresh the active panel immediately."""

        params = FreeCAD.ParamGet("User parameter:Plugins/parts_library")
        previous_destination = params.GetString("destination", "")
        previous_destinations = params.GetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "")
        previous_entries = params.GetString(
            BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY,
            "",
        )
        previous_mode_chosen = BimLibrary.PARAMS.GetBool("LibraryModeChosen", False)
        previous_online = BimLibrary.PARAMS.GetBool("LibraryOnline", False)

        try:
            with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
                self._write_library_root_metadata(root_a, "Parts Library")
                self._write_library_root_metadata(root_b, "Team Library")
                chair_manifest = self._write_library_asset(
                    root_a,
                    "ChairAsset",
                    "Chair Asset",
                    "furniture.chair.asset",
                )
                lamp_manifest = self._write_library_asset(
                    root_b,
                    "LampAsset",
                    "Lamp Asset",
                    "lighting.lamp.asset",
                )

                BimLibrarySources.set_configured_library_root_entries(
                    [
                        BimLibrarySources.ConfiguredLibraryRoot(root_a, True),
                        BimLibrarySources.ConfiguredLibraryRoot(root_b, False),
                    ]
                )
                BimLibrary.PARAMS.SetBool("LibraryModeChosen", True)
                BimLibrary.PARAMS.SetBool("LibraryOnline", False)

                panel = BimLibrary.BIM_Library_TaskPanel(target_doc_name=self.document.Name)
                self.pump_gui_events()

                try:
                    self.assertEqual(root_a.replace("\\", "/"), panel.librarypath)
                    self.assertEqual(
                        {chair_manifest.replace("\\", "/")},
                        {
                            entry["path"].replace("\\", "/")
                            for entry in panel._get_local_search_index()
                        },
                    )

                    panel._apply_configured_library_root_entries(
                        [
                            BimLibrarySources.ConfiguredLibraryRoot(root_b, True),
                            BimLibrarySources.ConfiguredLibraryRoot(root_a, False),
                        ],
                        online_mode=False,
                    )
                    self.pump_gui_events()

                    self.assertEqual(root_b.replace("\\", "/"), panel.librarypath)
                    self.assertEqual(root_b.replace("\\", "/"), panel.librarypaths[0])
                    self.assertNotIn(root_a.replace("\\", "/"), panel.librarypaths)
                    self.assertTrue(panel.form.labelLibraryRootSources.isHidden())
                    self.assertIn(
                        "Team Library · Configured",
                        panel.form.labelLibraryRootStatus.toolTip(),
                    )
                    search_paths = {
                        entry["path"].replace("\\", "/")
                        for entry in panel._get_local_search_index()
                    }
                    self.assertIn(lamp_manifest.replace("\\", "/"), search_paths)
                    self.assertNotIn(chair_manifest.replace("\\", "/"), search_paths)
                finally:
                    panel.reject()
        finally:
            params.SetString("destination", previous_destination)
            params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, previous_destinations)
            params.SetString(
                BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, previous_entries
            )
            BimLibrary.PARAMS.SetBool("LibraryModeChosen", previous_mode_chosen)
            BimLibrary.PARAMS.SetBool("LibraryOnline", previous_online)

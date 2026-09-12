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

"""GUI tests for BIM Library browsing and preview generation."""

import BimLibrarySources
import FreeCAD
import importlib.util
import json
import os
import Part
import sys
import tempfile
from bimtests.TestArchBaseGui import TestArchBaseGui


_library_module_name = "_BimLibraryBrowserTestModule"
_library_module_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "bimcommands",
    "BimLibrary.py",
)
_library_spec = importlib.util.spec_from_file_location(_library_module_name, _library_module_path)
BimLibrary = importlib.util.module_from_spec(_library_spec)
sys.modules[_library_module_name] = BimLibrary
_library_spec.loader.exec_module(BimLibrary)


class TestBimLibraryBrowserGui(TestArchBaseGui):
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

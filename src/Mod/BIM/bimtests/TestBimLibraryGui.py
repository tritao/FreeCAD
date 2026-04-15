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
import FreeCAD
import json
import os
import Part
import tempfile
from bimcommands import BimLibrary, BimPlanSession
from bimtests.TestArchBaseGui import TestArchBaseGui
from unittest.mock import patch


class TestBimLibraryGui(TestArchBaseGui):
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
        self.assertTrue(session._is_plan_equipment_object(stale_link))
        self.assertTrue(session._is_supported_plan_object(stale_link))

        live_link = panel._create_symbol_link(self.document, equipment)
        self.assertFalse(session._is_hidden_library_definition_object(live_link))
        self.assertTrue(session._should_register_created_plan_object(live_link))
        self.document.recompute()
        self.pump_gui_events()
        session._flush_created_plan_objects()
        session._refresh_plan_object_footprint_display(live_link)
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

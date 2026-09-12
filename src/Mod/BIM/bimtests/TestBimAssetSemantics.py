# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import tempfile
import unittest

import FreeCAD

import BimAssetSemantics


class TestBimAssetSemantics(unittest.TestCase):
    def test_asset_kind_normalizes_equipment_aliases(self):
        self.assertEqual(BimAssetSemantics.normalize_asset_kind("Furniture"), "equipment")
        self.assertEqual(BimAssetSemantics.normalize_asset_kind("FurnishingElement"), "equipment")
        self.assertEqual(
            BimAssetSemantics.get_asset_kind({"category": "furniture/seating"}),
            "equipment",
        )

    def test_descriptor_resolves_model_and_plan_representations(self):
        with tempfile.TemporaryDirectory() as root:
            asset_dir = os.path.join(root, "Chair")
            os.makedirs(asset_dir)
            manifest_path = os.path.join(asset_dir, "asset.json")
            with open(manifest_path, "w", encoding="utf-8") as manifest_file:
                manifest_file.write("{}")

            asset_path = os.path.join(asset_dir, "preview.svg")
            manifest = {
                "id": "furniture.chair",
                "name": "Chair",
                "kind": "furniture",
                "representations": {
                    "model3d": {"file": "chair.FCStd", "root": "Chair"},
                    "plan2d": {
                        "file": "chair-plan.FCStd",
                        "root": "ChairPlan",
                        "anchor": [12, 24, 0],
                        "facing": "0, 1, 0",
                    },
                },
            }

            descriptor = BimAssetSemantics.build_asset_descriptor(
                asset_path,
                lambda value: value,
                lambda _path: manifest,
                lambda _path: "Chair",
            )

        self.assertEqual(descriptor["asset_id"], "furniture.chair")
        self.assertEqual(descriptor["kind"], "equipment")
        self.assertEqual(descriptor["model_path"], os.path.join(asset_dir, "chair.FCStd"))
        self.assertEqual(descriptor["model_root"], "Chair")
        self.assertEqual(descriptor["plan_path"], os.path.join(asset_dir, "chair-plan.FCStd"))
        self.assertEqual(descriptor["plan_root"], "ChairPlan")
        self.assertEqual(descriptor["plan_anchor"], FreeCAD.Vector(12, 24, 0))
        self.assertEqual(descriptor["plan_facing"], FreeCAD.Vector(0, 1, 0))

    def test_descriptor_falls_back_to_a_static_file_without_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "desk.step")
            descriptor = BimAssetSemantics.build_asset_descriptor(
                path,
                lambda value: value,
                lambda _path: self.fail("manifest loader must not be called"),
                lambda _path: self.fail("asset label callback must not be called"),
            )

        self.assertEqual(descriptor["label"], "desk")
        self.assertEqual(descriptor["model_path"], path)
        self.assertEqual(descriptor["kind"], "")
        self.assertEqual(descriptor["provider_key"], "static")


if __name__ == "__main__":
    unittest.main()

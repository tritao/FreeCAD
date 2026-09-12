# SPDX-License-Identifier: LGPL-2.1-or-later

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import BimLibrarySources


class TestBimLibrarySources(unittest.TestCase):
    def setUp(self):
        self.params = BimLibrarySources._get_parts_library_params()
        self.saved_preferences = {
            key: self.params.GetString(key, "")
            for key in (
                BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY,
                BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY,
                BimLibrarySources.LEGACY_LIBRARY_ROOT_KEY,
            )
        }

    def tearDown(self):
        for key, value in self.saved_preferences.items():
            self.params.SetString(key, value)

    def test_root_label_comes_from_library_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "library.json"), "w", encoding="utf-8") as handle:
                json.dump({"library": {"title": "Office Furniture"}}, handle)

            entry = BimLibrarySources.ConfiguredLibraryRoot(root)

        self.assertEqual(entry.label, "Office Furniture")
        self.assertEqual(entry.metadata_path, os.path.join(root, "library.json"))

    def test_configuration_preserves_order_and_disabled_entries(self):
        with tempfile.TemporaryDirectory() as root:
            root_a = os.path.join(root, "library-a")
            root_b = os.path.join(root, "library-b")
            os.makedirs(root_a)
            os.makedirs(root_b)

            entries = BimLibrarySources.set_configured_library_root_entries(
                [
                    BimLibrarySources.ConfiguredLibraryRoot(root_a, True, "Primary"),
                    BimLibrarySources.ConfiguredLibraryRoot(root_b, False, "Disabled"),
                ]
            )
            restored = BimLibrarySources.get_configured_library_root_entries()
            enabled = BimLibrarySources.get_configured_library_roots()

        self.assertEqual([entry.path for entry in entries], [root_a, root_b])
        self.assertEqual(
            [(entry.path, entry.enabled) for entry in restored],
            [(root_a, True), (root_b, False)],
        )
        self.assertEqual(enabled, [root_a])

    def test_legacy_destination_migrates_to_managed_source_state(self):
        with tempfile.TemporaryDirectory() as root:
            self.params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOTS_KEY, "")
            self.params.SetString(BimLibrarySources.CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, "")
            self.params.SetString(BimLibrarySources.LEGACY_LIBRARY_ROOT_KEY, root)

            entries = BimLibrarySources.get_configured_library_root_entries()

            self.assertEqual([(entry.path, entry.enabled) for entry in entries], [(root, True)])
            self.assertEqual(
                BimLibrarySources.get_configured_library_roots(),
                [root],
            )

    def test_resolver_orders_configured_module_and_legacy_roots(self):
        with tempfile.TemporaryDirectory() as root:
            configured = os.path.join(root, "configured")
            module = os.path.join(root, "BIMAddon")
            marked_library = os.path.join(module, "Library")
            user_data = os.path.join(root, "user-data")
            legacy = os.path.join(user_data, "Mod", BimLibrarySources.LEGACY_LIBRARY_ADDON_NAME)
            for path in (configured, module, marked_library, legacy):
                os.makedirs(path, exist_ok=True)

            with open(os.path.join(marked_library, ".freecad-library"), "w", encoding="utf-8"):
                pass
            BimLibrarySources.set_configured_library_root_entries(
                [BimLibrarySources.ConfiguredLibraryRoot(configured)]
            )

            with patch.object(BimLibrarySources, "_iter_module_search_roots", return_value=[module]):
                with patch.object(
                    BimLibrarySources.FreeCAD,
                    "getUserAppDataDir",
                    return_value=user_data,
                ):
                    roots = BimLibrarySources.resolve_library_roots()

        self.assertEqual(
            [(entry.path, entry.source) for entry in roots],
            [
                (configured, BimLibrarySources.LIBRARY_SOURCE_CONFIGURED),
                (marked_library, BimLibrarySources.LIBRARY_SOURCE_MODULE),
                (legacy, BimLibrarySources.LIBRARY_SOURCE_LEGACY),
            ],
        )


if __name__ == "__main__":
    unittest.main()

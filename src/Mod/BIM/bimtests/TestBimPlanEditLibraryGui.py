# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for Plan Edit-aware BIM Library preview selection."""

import importlib.util
import os
import sys
import types
import unittest.mock


_module_name = "_BimPlanEditLibraryTestModule"
_module_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "bimcommands",
    "BimLibrary.py",
)
_module_spec = importlib.util.spec_from_file_location(_module_name, _module_path)
BimLibrary = importlib.util.module_from_spec(_module_spec)
sys.modules[_module_name] = BimLibrary
_module_spec.loader.exec_module(BimLibrary)


class TestBimPlanEditLibraryGui(unittest.TestCase):
    def test_auto_preview_uses_plan_symbols_only_during_an_active_session(self):
        panel = BimLibrary.BIM_Library_TaskPanel.__new__(BimLibrary.BIM_Library_TaskPanel)
        panel._get_selected_preview_mode = lambda: BimLibrary.PREVIEW_MODE_AUTO

        with unittest.mock.patch(
            "bimplan.runtime.session.get_active_session",
            return_value=types.SimpleNamespace(_finishing=False, _finished=False),
        ):
            self.assertEqual(BimLibrary.PREVIEW_MODE_2D, panel._get_effective_preview_mode())

        with unittest.mock.patch(
            "bimplan.runtime.session.get_active_session",
            return_value=types.SimpleNamespace(_finishing=True, _finished=False),
        ):
            self.assertEqual(BimLibrary.PREVIEW_MODE_3D, panel._get_effective_preview_mode())

        panel._get_selected_preview_mode = lambda: BimLibrary.PREVIEW_MODE_3D
        with unittest.mock.patch(
            "bimplan.runtime.session.get_active_session",
            return_value=types.SimpleNamespace(_finishing=False, _finished=False),
        ):
            self.assertEqual(BimLibrary.PREVIEW_MODE_3D, panel._get_effective_preview_mode())

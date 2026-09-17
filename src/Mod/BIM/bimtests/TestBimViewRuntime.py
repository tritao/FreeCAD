# SPDX-License-Identifier: LGPL-2.1-or-later

"""Unit tests for the representation-owned BIM viewport runtime."""

import unittest
from types import SimpleNamespace

from ArchRepresentation import RepresentationPurpose
from bimviews.runtime import BIMViewRuntime


class TestBimViewRuntime(unittest.TestCase):
    def test_plan_runtime_exposes_planar_capabilities(self):
        view = object()
        request = SimpleNamespace(purpose=RepresentationPurpose.PLAN)
        runtime = BIMViewRuntime(view, request)

        self.assertTrue(runtime.is_planar)
        self.assertTrue(runtime.supports("planar_editing"))
        self.assertTrue(runtime.supports("grid"))
        self.assertTrue(runtime.accepts_view(view))
        self.assertFalse(runtime.accepts_view(object()))

    def test_model_runtime_does_not_expose_planar_capabilities(self):
        runtime = BIMViewRuntime(
            object(), SimpleNamespace(purpose=RepresentationPurpose.MODEL)
        )

        self.assertFalse(runtime.is_planar)
        self.assertTrue(runtime.supports("model_editing"))
        self.assertFalse(runtime.supports("rulers"))

    def test_close_releases_view_and_capabilities(self):
        runtime = BIMViewRuntime(
            object(), SimpleNamespace(purpose=RepresentationPurpose.PLAN)
        )

        self.assertTrue(runtime.close())
        self.assertFalse(runtime.close())
        self.assertTrue(runtime.closed)
        self.assertIsNone(runtime.view)
        self.assertFalse(runtime.capabilities)
        self.assertFalse(runtime.set_request(SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()

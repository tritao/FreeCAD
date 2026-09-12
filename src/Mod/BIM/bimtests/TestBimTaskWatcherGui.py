# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for BIM selection-context classification used by task watchers."""

from types import SimpleNamespace

import FreeCADGui
from bimtests.TestArchBaseGui import TestArchBaseGui


class TestBimTaskWatcherGui(TestArchBaseGui):
    def test_semantic_selection_types_are_classified_for_contextual_actions(self):
        workbench = FreeCADGui.getWorkbench("BIMWorkbench")

        storey = SimpleNamespace(TypeId="App::DocumentObjectGroup", IfcType="Building Storey")
        wall = SimpleNamespace(TypeId="Part::FeaturePython", IfcType="Wall")
        sketch = SimpleNamespace(TypeId="Sketcher::SketchObject")
        model = SimpleNamespace(TypeId="PartDesign::Feature", Shape=object())

        self.assertTrue(workbench._is_project_container(storey))
        self.assertTrue(workbench._is_wall_like(wall))
        self.assertTrue(workbench._is_2d_like(sketch))
        self.assertTrue(workbench._is_model_object(model))
        self.assertFalse(workbench._is_model_object(storey))
        self.assertFalse(workbench._is_model_object(sketch))

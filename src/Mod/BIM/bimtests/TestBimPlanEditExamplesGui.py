# SPDX-License-Identifier: LGPL-2.1-or-later

"""End-to-end GUI checks for the generated BIM Plan Edit examples."""

import os

import FreeCAD
import FreeCADGui
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession


class TestBimPlanEditExamplesGui(TestArchBaseGui):
    """Treat installed example documents as executable integration fixtures."""

    def _example_path(self, filename):
        candidates = []
        source_dir = os.environ.get("FREECAD_SOURCE_DIR")
        if source_dir:
            candidates.append(os.path.join(source_dir, "data", "examples", filename))
        candidates.append(os.path.join(FreeCAD.getResourceDir(), "examples", filename))
        path = next((item for item in candidates if os.path.isfile(item)), candidates[-1])
        self.assertTrue(os.path.isfile(path), f"Plan Edit example is missing: {path}")
        return path

    def _open_example(self, filename):
        FreeCAD.closeDocument(self.document.Name)
        self.document = FreeCAD.openDocument(self._example_path(filename))
        FreeCAD.setActiveDocument(self.document.Name)
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.document.Name)
        self.document.UndoMode = 1
        self.pump_gui_events()
        return self.document

    @staticmethod
    def _objects_with_ifc_type(document, ifc_type):
        return [obj for obj in document.Objects if getattr(obj, "IfcType", "") == ifc_type]

    def _enter_plan_edit(self, storey):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(storey)
        session = PlanEditSession()
        self.assertTrue(session.enter())
        self.assertIs(session.active_storey, storey)
        self.addCleanup(session.shutdown, close_dialog=False)
        self.pump_gui_events()
        return session

    def test_basic_example_loads_and_renders_semantically(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        walls = self._objects_with_ifc_type(document, "Wall")
        storeys = self._objects_with_ifc_type(document, "Building Storey")
        self.assertEqual(5, len(walls))
        self.assertEqual(1, len(storeys))
        for wall in walls:
            self.assertIsInstance(wall.Proxy._resolved_geometry_signatures, dict)
            self.assertFalse(wall.Proxy._invalidating_wall_relations)
            wall.touch()
        document.recompute()
        self.assertTrue(all(not wall.Shape.isNull() for wall in walls))

        session = self._enter_plan_edit(storeys[0])
        self.assertTrue(all(wall in session.contextual_rendering.renderer.sources for wall in walls))
        self.assertGreater(session.contextual_rendering.renderer.root.getNumChildren(), 0)

    def test_basic_example_wall_edit_roundtrips(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        wall = self._objects_with_ifc_type(document, "Wall")[0]
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._enter_plan_edit(storey)
        handle = next(
            item
            for item in session.contextual_rendering.edit_handles_for(wall)
            if item.role == "WallWidth"
        )
        width = wall.Width.Value
        session.contextual_editing.begin(handle)
        result = session.contextual_editing.commit(handle.point + handle.direction * 50)
        self.assertTrue(result.success)
        self.assertAlmostEqual(width + 100, wall.Width.Value)
        document.undo()
        self.assertAlmostEqual(width, wall.Width.Value)

    def test_path_ownership_example_exposes_owner_specific_handles(self):
        document = self._open_example("BIMPlanEditPathOwnership.FCStd")
        storey = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._enter_plan_edit(storey)
        expected = {
            "Wall": ("WallPathStart", "WallPathEnd"),
            "Wall001": ("WallPathVertex1", "WallPathVertex2"),
            "Wall002": ("WallPathVertex1", "WallPathVertex2", "WallPathVertex3"),
            "Wall003": ("WallPathG0P1", "WallPathG0P2_G1P1", "WallPathG1P2"),
            "Wall004": (),
            "Wall005": (),
        }
        actual = {
            wall.Name: tuple(
                handle.role
                for handle in session.contextual_rendering.edit_handles_for(wall)
                if handle.role.startswith("WallPath")
            )
            for wall in self._objects_with_ifc_type(document, "Wall")
        }
        self.assertEqual(expected, actual)

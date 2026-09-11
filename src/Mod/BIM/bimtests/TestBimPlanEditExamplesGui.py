# SPDX-License-Identifier: LGPL-2.1-or-later

"""End-to-end GUI checks for the generated BIM Plan Edit examples."""

import os
import tempfile

import FreeCAD
import FreeCADGui
from bimcommands import BimPlanSession

from .TestBimPlanEditGuiBase import BimPlanEditGuiBase


class TestBimPlanEditExamplesGui(BimPlanEditGuiBase):
    """Treat installed example documents as executable integration fixtures."""

    def _open_example(self, filename):
        path = os.path.join(FreeCAD.getResourceDir(), "examples", filename)
        self.assertTrue(os.path.isfile(path), f"Installed example is missing: {path}")
        FreeCAD.closeDocument(self.document.Name)
        self.document = FreeCAD.openDocument(path)
        FreeCAD.setActiveDocument(self.document.Name)
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.document.Name)
        self.document.UndoMode = 1
        self.pump_gui_events(timeout_ms=500)
        return self.document

    def _start_for(self, source):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(source)
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events(timeout_ms=500)
        return session

    @staticmethod
    def _objects_with_ifc_type(document, ifc_type):
        return [obj for obj in document.Objects if getattr(obj, "IfcType", "") == ifc_type]

    @staticmethod
    def _handle(session, obj, role):
        return next(
            handle
            for handle in session.contextual_rendering.edit_handles_for(obj)
            if handle.role == role
        )

    def test_basic_example_restores_runtime_wall_state_and_recomputes(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        walls = self._objects_with_ifc_type(document, "Wall")
        self.assertEqual(len(walls), 5)

        for wall in walls:
            self.assertIsInstance(wall.Proxy._resolved_geometry_signatures, dict)
            self.assertFalse(wall.Proxy._invalidating_wall_relations)
            wall.touch()
        document.recompute()

        for wall in walls:
            self.assertFalse(wall.Shape.isNull())

    def test_basic_example_plan_edits_roundtrip_and_render_semantically(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        level = self._objects_with_ifc_type(document, "Building Storey")[0]
        wall = self._objects_with_ifc_type(document, "Wall")[0]
        opening = self._objects_with_ifc_type(document, "Door")[0]
        session = self._start_for(level)

        self.assertIs(session.active_storey, level)
        self.assertIn(wall, session.contextual_rendering.renderer.sources)
        self.assertIn(opening, session.contextual_rendering.renderer.sources)
        self.assertGreater(session.contextual_rendering.renderer.root.getNumChildren(), 0)

        start_before, end_before = wall.Proxy.calc_endpoints(wall)
        endpoint = self._handle(session, wall, "WallPathEnd")
        session.contextual_editing.begin(endpoint)
        result = session.contextual_editing.commit(endpoint.point + FreeCAD.Vector(240, 160, 50))
        self.assertTrue(result.success)
        self.assertTrue(
            wall.Proxy.calc_endpoints(wall)[1].isEqual(
                end_before + FreeCAD.Vector(240, 160, 0), 1e-7
            )
        )
        self._undo_document()
        self.assertTrue(wall.Proxy.calc_endpoints(wall)[0].isEqual(start_before, 1e-7))
        self.assertTrue(wall.Proxy.calc_endpoints(wall)[1].isEqual(end_before, 1e-7))
        self._redo_document()
        self.assertTrue(
            wall.Proxy.calc_endpoints(wall)[1].isEqual(
                end_before + FreeCAD.Vector(240, 160, 0), 1e-7
            )
        )

        self.assertTrue(session.selection.activation.select_opening_for_plan_edit(opening))
        self.pump_gui_events(timeout_ms=250)
        self._assert_selected_opening_visuals(session, opening)
        center_before = opening.Proxy.get_plan_center_point()
        position = self._handle(session, opening, "OpeningPosition")
        session.contextual_editing.begin(position)
        result = session.contextual_editing.commit(position.point + position.direction * 100)
        self.assertTrue(result.success)
        self.assertGreater(opening.Proxy.get_plan_center_point().distanceToPoint(center_before), 99)
        self._undo_document()
        self.assertTrue(opening.Proxy.get_plan_center_point().isEqual(center_before, 1e-7))

    def test_basic_example_save_reopen_has_no_transient_plan_objects(self):
        document = self._open_example("BIMPlanEditBasic.FCStd")
        level = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._start_for(level)
        original_names = tuple(obj.Name for obj in document.Objects)

        handle = tempfile.NamedTemporaryFile(suffix=".FCStd", delete=False)
        handle.close()
        os.unlink(handle.name)
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        document.saveAs(handle.name)
        session.shutdown(close_dialog=False)
        self.pump_gui_events(timeout_ms=250)
        FreeCAD.closeDocument(document.Name)

        self.document = FreeCAD.openDocument(handle.name)
        self.assertEqual(tuple(obj.Name for obj in self.document.Objects), original_names)
        self.assertFalse(any("PlanEdit" in obj.Name for obj in self.document.Objects))

    def test_path_ownership_example_edits_only_semantic_owners(self):
        document = self._open_example("BIMPlanEditPathOwnership.FCStd")
        level = self._objects_with_ifc_type(document, "Building Storey")[0]
        session = self._start_for(level)
        expected = {
            "Wall": ["WallPathStart", "WallPathEnd"],
            "Wall001": ["WallPathVertex1", "WallPathVertex2"],
            "Wall002": ["WallPathVertex1", "WallPathVertex2", "WallPathVertex3"],
            "Wall003": ["WallPathG0P1", "WallPathG0P2_G1P1", "WallPathG1P2"],
            "Wall004": [],
            "Wall005": [],
        }
        actual = {}
        for wall in self._objects_with_ifc_type(document, "Wall"):
            actual[wall.Name] = [
                handle.role
                for handle in session.contextual_rendering.edit_handles_for(wall)
                if handle.role.startswith("WallPath")
            ]
        self.assertEqual(actual, expected)

        draft_wall = document.getObject("Wall002")
        draft_path = draft_wall.Base
        point_before = FreeCAD.Vector(draft_path.Points[1])
        vertex = self._handle(session, draft_wall, "WallPathVertex2")
        session.contextual_editing.begin(vertex)
        result = session.contextual_editing.commit(vertex.point + FreeCAD.Vector(120, 80, 30))
        self.assertTrue(result.success)
        self.assertTrue(
            FreeCAD.Vector(draft_path.Points[1]).isEqual(
                point_before + FreeCAD.Vector(120, 80, 0), 1e-7
            )
        )
        self._undo_document()
        self.assertTrue(FreeCAD.Vector(draft_path.Points[1]).isEqual(point_before, 1e-7))

        sketch_wall = document.getObject("Wall003")
        sketch = sketch_wall.Base
        joined = self._handle(session, sketch_wall, "WallPathG0P2_G1P1")
        session.contextual_editing.begin(joined)
        result = session.contextual_editing.commit(joined.point + FreeCAD.Vector(90, 70, 25))
        self.assertTrue(result.success)
        self.assertTrue(sketch.getPoint(0, 2).isEqual(sketch.getPoint(1, 1), 1e-7))

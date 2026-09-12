# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for the viewer-local BIM Plan Edit session."""

from unittest.mock import patch

import FreeCAD
import FreeCADGui
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession


class TestBimPlanEditSessionGui(TestArchBaseGui):
    def test_storey_entry_helper_selects_source_and_runs_shared_command(self):
        from bimcommands.BimPlanEdit import start_plan_edit_for

        storey, _contained = self._make_storey("Plan Storey", 0)
        with patch.object(FreeCADGui, "runCommand") as run_command:
            start_plan_edit_for(storey)

        self.assertEqual([storey], FreeCADGui.Selection.getSelection())
        run_command.assert_called_once_with("BIM_PlanEdit")

    def _make_storey(self, label, elevation):
        storey = self.document.addObject("App::DocumentObjectGroup", "Storey")
        storey.Label = label
        storey.addProperty("App::PropertyString", "IfcType", "BIM")
        storey.addProperty("App::PropertyPlacement", "Placement", "Base")
        storey.IfcType = "Building Storey"
        storey.Placement = FreeCAD.Placement(
            FreeCAD.Vector(0, 0, elevation), FreeCAD.Rotation()
        )
        contained = self.document.addObject("App::DocumentObjectGroup", "ContainedObject")
        storey.addObject(contained)
        self.document.recompute()
        return storey, contained

    def test_session_visibility_and_camera_are_reversible(self):
        lower_storey, lower_wall = self._make_storey("Lower Storey", 0)
        upper_storey, upper_wall = self._make_storey("Upper Storey", 3000)

        gui_document = FreeCADGui.ActiveDocument
        view = gui_document.ActiveView
        original_camera = view.getCamera()
        original_camera_type = view.getCameraType()
        original_visibility = {
            obj.Name: obj.ViewObject.Visibility
            for obj in (lower_storey, lower_wall, upper_storey, upper_wall)
        }

        session = PlanEditSession(self.document, gui_document)
        try:
            self.assertTrue(session.enter(show_panel=False))
            self.assertEqual(session.active_storey.Name, lower_storey.Name)
            self.assertEqual(view.getCameraType(), "Orthographic")
            self.assertEqual(view.getViewVisibility(lower_storey), "Visible")
            self.assertEqual(view.getViewVisibility(lower_wall), "Visible")
            self.assertEqual(view.getViewVisibility(upper_storey), "Hidden")
            self.assertEqual(view.getViewVisibility(upper_wall), "Hidden")

            session.set_active_storey(upper_storey)
            self.assertEqual(view.getViewVisibility(lower_storey), "Hidden")
            self.assertEqual(view.getViewVisibility(lower_wall), "Hidden")
            self.assertEqual(view.getViewVisibility(upper_storey), "Visible")
            self.assertEqual(view.getViewVisibility(upper_wall), "Visible")
            self.assertEqual(
                {
                    obj.Name: obj.ViewObject.Visibility
                    for obj in (lower_storey, lower_wall, upper_storey, upper_wall)
                },
                original_visibility,
            )
        finally:
            session.finish(close_dialog=False)

        self.assertEqual(view.getCameraType(), original_camera_type)
        self.assertEqual(view.getCamera(), original_camera)
        for obj in (lower_storey, lower_wall, upper_storey, upper_wall):
            self.assertEqual(view.getViewVisibility(obj), "Inherit")
            self.assertEqual(obj.ViewObject.Visibility, original_visibility[obj.Name])

    def test_task_panel_exit_finishes_the_session(self):
        gui_document = FreeCADGui.ActiveDocument
        session = PlanEditSession(self.document, gui_document)

        self.assertTrue(session.enter(show_panel=True))
        self.assertIsNotNone(session.task_panel)
        session.task_panel.exit_button.click()

        self.assertFalse(session._entered)
        self.assertIsNone(session.context_layer)

# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for the viewer-local BIM Plan Edit session."""

from unittest.mock import patch

import Arch
import FreeCAD
import FreeCADGui
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession
from bimplan.providers import PlanEditProvider, PlanEditRegistry


class _TestProvider(PlanEditProvider):
    def __init__(self, provider_id):
        self.provider_id = provider_id

    def get_provider_id(self):
        return self.provider_id


class TestBimPlanEditSessionGui(TestArchBaseGui):
    def test_storey_entry_helper_selects_source_and_runs_shared_command(self):
        from bimcommands.BimPlanEdit import start_plan_edit_for

        storey, _contained = self._make_storey("Plan Storey", 0)
        with patch.object(FreeCADGui, "runCommand") as run_command:
            start_plan_edit_for(storey)

        self.assertEqual([storey], FreeCADGui.Selection.getSelection())
        run_command.assert_called_once_with("BIM_PlanEdit")

    def test_rectangular_wall_run_uses_command_owned_creation_api(self):
        from bimcommands import BimWall

        points = [
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1000, 0, 0),
            FreeCAD.Vector(1000, 800, 0),
            FreeCAD.Vector(0, 800, 0),
        ]
        walls = BimWall.create_wall_run_from_points(
            points,
            width=200,
            height=2500,
            closed=True,
            auto_group=False,
        )
        self.assertEqual(4, len(walls))
        self.assertTrue(all(wall.Base is None for wall in walls))

    def test_provider_rehost_api_preserves_pose(self):
        from bimplan.tools import hosted_openings

        host = self.document.addObject("Part::Feature", "Host")
        opening = self.document.addObject("Part::FeaturePython", "Opening")
        opening.addProperty("App::PropertyLinkList", "Hosts")
        opening.Placement.Base = FreeCAD.Vector(120, 80, 40)
        before = FreeCAD.Placement(opening.Placement)

        self.assertTrue(
            hosted_openings.rehost_object(opening, host, preserve_world_position=True)
        )
        self.assertEqual([host], list(opening.Hosts))
        self.assertTrue(opening.Placement.Base.isEqual(before.Base, 1e-7))

    def test_provider_registry_preserves_order_and_replaces_by_identity(self):
        registry = PlanEditRegistry()
        first = _TestProvider("first")
        second = _TestProvider("second")
        replacement = _TestProvider("first")

        registry.register_provider(first)
        registry.register_provider(second)
        registry.register_provider(replacement)

        self.assertEqual(("first", "second"), registry.provider_ids())
        self.assertEqual((replacement, second), registry.iter_providers())
        self.assertIs(replacement, registry.get_provider("first"))
        self.assertIs(second, registry.unregister_provider(second))
        self.assertEqual(("first",), registry.provider_ids())

    def test_provider_registry_rejects_missing_identity(self):
        registry = PlanEditRegistry()

        with self.assertRaises(ValueError):
            registry.register_provider(_TestProvider(""))

    def _make_storey(self, label, elevation):
        storey = Arch.makeBuildingPart(name=label)
        storey.Label = label
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

        session = PlanEditSession()
        try:
            self.assertTrue(session.enter())
            self.assertEqual(session.active_storey.Name, lower_storey.Name)
            self.assertEqual(view.getCameraType(), "Orthographic")
            self.assertEqual(view.getViewVisibility(lower_storey), "Visible")
            self.assertEqual(view.getViewVisibility(lower_wall), "Visible")
            self.assertEqual(view.getViewVisibility(upper_storey), "Hidden")
            self.assertEqual(view.getViewVisibility(upper_wall), "Hidden")

            session.storey.set_active_storey(upper_storey)
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
        session = PlanEditSession()

        self.assertTrue(session.enter())
        self.assertIsNotNone(session.task_panel)
        session.task_panel.exit_button.click()

        self.assertIsNone(session.task_panel)
        self.assertIsNone(session.viewport_state.view_context_layer)

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

"""GUI tests for BIM Project Manager IFC dependency handling."""

import FreeCAD
from bimcommands import BimProjectManager
from bimtests.TestArchBaseGui import TestArchBaseGui
from unittest.mock import patch


class TestBimProjectManagerGui(TestArchBaseGui):
    def _cleanup_command(self, command):
        if not hasattr(command, "form"):
            return
        try:
            command.reject()
        except Exception:
            pass

    def _close_documents(self, names):
        for name in names:
            try:
                FreeCAD.closeDocument(name)
            except Exception:
                pass

    def test_project_manager_disables_native_ifc_creation_when_ifcopenshell_is_unavailable(self):
        """The IFC creation options should be disabled when ifcopenshell is unavailable."""

        command = BimProjectManager.BIM_ProjectManager()
        self.addCleanup(self._cleanup_command, command)

        with patch.object(command, "_native_ifc_available", return_value=False):
            command.Activated()

        self.assertTrue(command.form.radioNative1.isChecked())
        self.assertFalse(command.form.radioNative2.isEnabled())
        self.assertFalse(command.form.radioNative3.isEnabled())
        self.assertIn("IfcOpenShell", command.form.radioNative2.toolTip())
        self.assertIn("IfcOpenShell", command.form.radioNative3.toolTip())

    def test_project_manager_creates_non_ifc_project_without_native_ifc_tools(self):
        """The plain FreeCAD project path should not import nativeifc helpers."""

        command = BimProjectManager.BIM_ProjectManager()
        self.addCleanup(self._cleanup_command, command)
        initial_docs = set(FreeCAD.listDocuments().keys())

        with patch.object(command, "_native_ifc_available", return_value=False):
            command.Activated()

        command.form.radioNative1.setChecked(True)
        command.form.projectName.setText("Plain Project")
        command.form.groupSite.setChecked(False)
        command.form.groupBuilding.setChecked(False)

        with patch.object(
            command,
            "_get_ifc_tools",
            side_effect=AssertionError("native IFC helpers should not be used"),
        ):
            result = command.accept()

        self.assertTrue(result)

        created_docs = [
            doc for name, doc in FreeCAD.listDocuments().items() if name not in initial_docs
        ]
        self.assertEqual(1, len(created_docs))

        try:
            doc = created_docs[0]
            self.assertEqual("Plain Project", doc.Label)
            self.assertFalse(hasattr(getattr(doc, "Proxy", None), "ifcfile"))
        finally:
            self._close_documents([doc.Name for doc in created_docs])

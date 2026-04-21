# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026                                                    *
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

import BimSelect
import FreeCAD
import FreeCADGui
from bimtests.TestArchBaseGui import TestArchBaseGui
from unittest.mock import patch


class _DeletedSelectionObject:
    def __init__(self, document_name, object_name, subelement_names):
        self.DocumentName = document_name
        self.ObjectName = object_name
        self.SubElementNames = tuple(subelement_names)

    @property
    def Object(self):
        raise RuntimeError("Object already deleted")


class TestBimSelectGui(TestArchBaseGui):
    def tearDown(self):
        if hasattr(FreeCAD, "CyclicSelectionObserver"):
            del FreeCAD.CyclicSelectionObserver
        super().tearDown()

    def test_cyclic_selection_uses_stored_names_when_preselection_object_was_deleted(self):
        box = self.document.addObject("Part::Box", "Box")
        self.document.recompute()

        observer = BimSelect.CyclicSelectionObserver()
        FreeCAD.CyclicSelectionObserver = observer
        preselection = _DeletedSelectionObject(self.document.Name, box.Name, ("Face1",))

        selection_calls = {}

        class _FakeSelection:
            @staticmethod
            def removeSelection(*args):
                selection_calls["removeSelection"] = args

            @staticmethod
            def removeObserver(*args):
                selection_calls["removeObserver"] = args

            @staticmethod
            def getPreselection():
                return preselection

            @staticmethod
            def addSelection(*args):
                selection_calls["addSelection"] = args

        with patch.object(FreeCADGui, "Selection", _FakeSelection()):
            observer.addSelection(self.document.Name, box.Name, "", None)

        self.assertEqual(selection_calls["removeSelection"], (self.document.Name, box.Name, ""))
        self.assertEqual(selection_calls["removeObserver"], (observer,))
        self.assertEqual(selection_calls["addSelection"], (self.document.Name, box.Name, "Face1"))
        self.assertFalse(hasattr(FreeCAD, "CyclicSelectionObserver"))

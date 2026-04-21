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


class TestBimSelectGui(TestArchBaseGui):
    def tearDown(self):
        if hasattr(FreeCAD, "CyclicSelectionObserver"):
            del FreeCAD.CyclicSelectionObserver
        super().tearDown()

    def test_cyclic_selection_uses_observer_target_without_reading_preselection(self):
        box = self.document.addObject("Part::Box", "Box")
        self.document.recompute()

        observer = BimSelect.CyclicSelectionObserver(self.document.Name, box.Name, "Face1")
        FreeCAD.CyclicSelectionObserver = observer

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
                raise AssertionError("getPreselection() should not be used here")

            @staticmethod
            def addSelection(*args):
                selection_calls["addSelection"] = args

        with patch.object(FreeCADGui, "Selection", _FakeSelection()):
            observer.addSelection(self.document.Name, "Clicked", "Face2", None)

        self.assertEqual(
            selection_calls["removeSelection"], (self.document.Name, "Clicked", "Face2")
        )
        self.assertEqual(selection_calls["removeObserver"], (observer,))
        self.assertEqual(selection_calls["addSelection"], (self.document.Name, box.Name, "Face1"))
        self.assertFalse(hasattr(FreeCAD, "CyclicSelectionObserver"))

    def test_cyclic_selection_leaves_clicked_selection_when_target_is_missing(self):
        observer = BimSelect.CyclicSelectionObserver(self.document.Name, "Missing", "Face1")
        FreeCAD.CyclicSelectionObserver = observer

        selection_calls = {}

        class _FakeSelection:
            @staticmethod
            def removeSelection(*args):
                selection_calls["removeSelection"] = args

            @staticmethod
            def removeObserver(*args):
                selection_calls["removeObserver"] = args

            @staticmethod
            def addSelection(*args):
                selection_calls["addSelection"] = args

        with patch.object(FreeCADGui, "Selection", _FakeSelection()):
            observer.addSelection(self.document.Name, "Clicked", "Face2", None)

        self.assertNotIn("removeSelection", selection_calls)
        self.assertNotIn("addSelection", selection_calls)
        self.assertEqual(selection_calls["removeObserver"], (observer,))
        self.assertFalse(hasattr(FreeCAD, "CyclicSelectionObserver"))

    def test_select_object_registers_observer_for_current_cycle_target(self):
        from pivy import coin

        box = self.document.addObject("Part::Box", "Box")
        self.document.recompute()

        selector = BimSelect.CyclicObjectSelector()
        selector.selectableObjects = [
            {"Object": box.Name, "Component": "Face1"},
            {"Object": box.Name, "Component": "Face2"},
        ]
        selector.objectIndex = 1

        selection_calls = {}

        class _FakeSelection:
            @staticmethod
            def addObserver(*args):
                selection_calls["addObserver"] = args

        class _FakeActiveView:
            @staticmethod
            def getObjectsInfo(_pos):
                return [{}]

        class _FakeGuiDocument:
            ActiveView = _FakeActiveView()

        class _FakeMousePosition:
            @staticmethod
            def getValue():
                return (10, 20)

        class _FakeMouseEvent:
            @staticmethod
            def getState():
                return coin.SoMouseButtonEvent.DOWN

            @staticmethod
            def getPosition():
                return _FakeMousePosition()

        class _FakeEventCallback:
            @staticmethod
            def getEvent():
                return _FakeMouseEvent()

        with (
            patch.object(FreeCADGui, "Selection", _FakeSelection()),
            patch.object(FreeCADGui, "ActiveDocument", _FakeGuiDocument()),
        ):
            selector.selectObject(_FakeEventCallback())

        observer = FreeCAD.CyclicSelectionObserver
        self.assertEqual(observer.document_name, self.document.Name)
        self.assertEqual(observer.object_name, box.Name)
        self.assertEqual(observer.subelement_name, "Face2")
        self.assertEqual(selection_calls["addObserver"], (observer,))

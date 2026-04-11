# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2024 Yorik van Havre <yorik@uncreated.net>              *
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

import FreeCAD


class CyclicSelectionObserver:
    def addSelection(self, document, object, element, position):
        import FreeCADGui

        if not FreeCAD.ActiveDocument:
            return
        if not hasattr(FreeCAD, "CyclicSelectionObserver"):
            return
        FreeCADGui.Selection.removeSelection(FreeCAD.ActiveDocument.getObject(object))
        FreeCADGui.Selection.removeObserver(FreeCAD.CyclicSelectionObserver)
        del FreeCAD.CyclicSelectionObserver
        preselection = FreeCADGui.Selection.getPreselection()
        FreeCADGui.Selection.addSelection(
            FreeCAD.ActiveDocument.getObject(preselection.Object.Name),
            preselection.SubElementNames[0],
        )
        FreeCAD.ActiveDocument.recompute()


class CyclicObjectSelector:
    def __init__(self):
        self.selectableObjects = []
        self.objectIndex = 0

    def selectObject(self, event_callback):
        import FreeCADGui
        from pivy import coin

        if not FreeCAD.ActiveDocument:
            return
        event = event_callback.getEvent()

        if event.getState() != coin.SoMouseButtonEvent.DOWN or not self.selectableObjects:
            return

        pos = event.getPosition().getValue()
        element_list = FreeCADGui.ActiveDocument.ActiveView.getObjectsInfo(
            (int(pos[0]), int(pos[1]))
        )

        if not element_list:
            self.selectableObjects = []
            if hasattr(FreeCAD, "CyclicSelectionObserver"):
                FreeCADGui.Selection.removeObserver(FreeCAD.CyclicSelectionObserver)
                del FreeCAD.CyclicSelectionObserver
            return

        FreeCAD.CyclicSelectionObserver = CyclicSelectionObserver()
        FreeCADGui.Selection.addObserver(FreeCAD.CyclicSelectionObserver)

    def cycleSelectableObjects(self, event_callback):
        import FreeCADGui

        if not FreeCAD.ActiveDocument:
            return
        event = event_callback.getEvent()

        if not event.isKeyPressEvent(event, event.TAB):
            return

        pos = event.getPosition().getValue()
        selectableObjects = FreeCADGui.ActiveDocument.ActiveView.getObjectsInfo(
            (int(pos[0]), int(pos[1]))
        )

        if not selectableObjects:
            return

        if self.selectableObjects != selectableObjects:
            self.selectableObjects = selectableObjects
            self.objectIndex = 0
        elif self.objectIndex < len(self.selectableObjects) - 1:
            self.objectIndex += 1
        else:
            self.objectIndex = 0
        object_name = self.selectableObjects[self.objectIndex]["Object"]
        subelement_name = self.selectableObjects[self.objectIndex]["Component"]
        FreeCADGui.getMainWindow().showMessage(
            "Cycle preselected (TAB): {} - {}".format(object_name, subelement_name), 0
        )
        FreeCADGui.Selection.setPreselection(
            FreeCAD.ActiveDocument.getObject(object_name), subelement_name
        )


class Setup:
    def __init__(self):
        self.callbacks = {}

    def _document_name(self, doc):
        document = getattr(doc, "Document", doc)
        return getattr(document, "Name", None)

    def _remove_callbacks(self, key):
        from pivy import coin

        callback_data = self.callbacks.pop(key, None)
        if not callback_data:
            return

        view = callback_data["view"]
        try:
            view.removeEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(), callback_data["mouse"]
            )
            view.removeEventCallbackPivy(
                coin.SoKeyboardEvent.getClassTypeId(), callback_data["keyboard"]
            )
        except RuntimeError:
            # the view has been deleted already
            pass

    def slotActivateDocument(self, doc):
        from pivy import coin

        key = self._document_name(doc)
        view = getattr(doc, "ActiveView", None)
        if not key:
            return
        callback_data = self.callbacks.get(key)
        if callback_data and callback_data["view"] is view:
            return
        if callback_data:
            self._remove_callbacks(key)

        cos = CyclicObjectSelector()
        if doc and view and hasattr(view, "getSceneGraph"):
            mouse_callback = view.addEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(), cos.selectObject
            )
            keyboard_callback = view.addEventCallbackPivy(
                coin.SoKeyboardEvent.getClassTypeId(), cos.cycleSelectableObjects
            )
            self.callbacks[key] = {
                "view": view,
                "selector": cos,
                "mouse": mouse_callback,
                "keyboard": keyboard_callback,
            }

    def slotDeletedDocument(self, doc):
        key = self._document_name(doc)
        if key:
            self._remove_callbacks(key)

    def cleanup(self):
        for key in list(self.callbacks):
            self._remove_callbacks(key)

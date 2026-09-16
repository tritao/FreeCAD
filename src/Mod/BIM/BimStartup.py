# SPDX-License-Identifier: LGPL-2.1-or-later

"""Restore BIM-owned startup activities embedded in a document."""

import FreeCAD
import FreeCADGui
from PySide import QtCore


GUI_SCHEMA_VERSION = 1
BIM_SCHEMA_VERSION = 1


def apply_document_startup(document):
    """Apply the supported BIM startup activity once the GUI is idle."""

    if document is None or FreeCAD.ActiveDocument is not document:
        return False

    gui_settings = document.settings("Gui.Startup")
    if gui_settings.getInt("SchemaVersion", 0) != GUI_SCHEMA_VERSION:
        return False
    if gui_settings.getString("Workbench", "") != "BIMWorkbench":
        return False

    bim_settings = document.settings("BIM.Startup")
    if bim_settings.getInt("SchemaVersion", 0) != BIM_SCHEMA_VERSION:
        return False
    if bim_settings.getString("Activity", "") != "PlanEdit":
        return False

    context = document.getObject(bim_settings.getString("ContextObject", ""))
    if context is None:
        FreeCAD.Console.PrintWarning("BIM startup context object was not found\n")
        return False

    view_name = bim_settings.getString("ViewObject", "")
    definition = document.getObject(view_name) if view_name else None
    if definition is not None:
        try:
            from bimcommands.BimViews import _apply_representation_request
            from bimviews.service import BIMViewService

            BIMViewService(
                document,
                representation_applier=_apply_representation_request,
            ).activate_view(definition)
        except Exception as exc:
            FreeCAD.Console.PrintWarning(
                "Could not restore BIM startup view: {}\n".format(exc)
            )

    from bimcommands.BimPlanEdit import start_plan_edit_for

    start_plan_edit_for(context)
    return True


class _BIMStartupObserver:
    def __init__(self):
        self._scheduled = set()

    def slotActivateDocument(self, document):
        if document.Name in self._scheduled:
            return
        self._scheduled.add(document.Name)
        QtCore.QTimer.singleShot(0, lambda name=document.Name: self._apply(name))

    def slotDeletedDocument(self, document):
        self._scheduled.discard(document.Name)

    def _apply(self, document_name):
        try:
            document = FreeCAD.getDocument(document_name)
        except NameError:
            document = None
        if document is not None:
            apply_document_startup(document)


_observer = None


def install_observer():
    global _observer
    if _observer is None:
        _observer = _BIMStartupObserver()
        FreeCAD.addDocumentObserver(_observer)

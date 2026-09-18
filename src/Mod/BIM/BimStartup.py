# SPDX-License-Identifier: LGPL-2.1-or-later

"""Restore BIM-owned startup activities embedded in a document."""

import FreeCAD
import FreeCADGui


GUI_SCHEMA_VERSION = 1
BIM_SCHEMA_VERSION = 1


def apply_document_startup(document):
    """Apply the supported BIM startup activity after GUI restoration."""

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
    activated = False
    if definition is not None:
        try:
            from bimplan.runtime.session import activate_representation_request
            from bimviews.service import BIMViewService

            activated = BIMViewService(
                document,
                representation_applier=lambda request: activate_representation_request(
                    request, defer_population=True
                ),
            ).activate_view(definition)
        except Exception as exc:
            FreeCAD.Console.PrintWarning(
                "Could not restore BIM startup view: {}\n".format(exc)
            )

    if not activated:
        # Older documents may only persist a startup context.  Resolve that
        # context through the same Navigator/runtime seam without invoking the
        # deprecated Plan Edit command or opening its task panel.
        try:
            from bimplan.representation_request import representation_request_from_storey
            from bimplan.runtime.session import activate_representation_request

            activate_representation_request(
                representation_request_from_storey(context), defer_population=True
            )
            activated = True
        except Exception as exc:
            FreeCAD.Console.PrintWarning(
                "Could not restore BIM startup context: {}\n".format(exc)
            )

    return activated


class _BIMStartupObserver:
    def __init__(self):
        self._restored = set()
        self._applied = set()

    def slotFinishRestoreDocument(self, gui_document):
        document = gui_document.Document
        self._restored.add(document.Name)
        self._apply(document)

    def slotActivateDocument(self, gui_document):
        document = gui_document.Document
        if document.Name in self._restored or not document.Restoring:
            self._apply(document)

    def slotDeletedDocument(self, gui_document):
        name = gui_document.Document.Name
        self._restored.discard(name)
        self._applied.discard(name)

    def _apply(self, document):
        if document.Name in self._applied:
            return
        if apply_document_startup(document):
            self._applied.add(document.Name)


_observer = None


def install_observer():
    global _observer
    if _observer is None:
        _observer = _BIMStartupObserver()
        FreeCADGui.addDocumentObserver(_observer)
        # Workbench initialization can happen after an already-open document
        # completed restoration, so apply that one known-ready document now.
        if FreeCAD.ActiveDocument is not None and not FreeCAD.ActiveDocument.Restoring:
            _observer._restored.add(FreeCAD.ActiveDocument.Name)
            _observer._apply(FreeCAD.ActiveDocument)

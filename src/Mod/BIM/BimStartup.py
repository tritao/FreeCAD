# SPDX-License-Identifier: LGPL-2.1-or-later

"""Restore BIM-owned startup activities embedded in a document."""

import FreeCAD
import FreeCADGui


GUI_SCHEMA_VERSION = 1
BIM_SCHEMA_VERSION = 1


def prepare_document_startup(document):
    """Prepare the supported BIM startup activity before document reveal."""

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
                    request, prepare_only=True
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
                representation_request_from_storey(context), prepare_only=True
            )
            activated = True
        except Exception as exc:
            FreeCAD.Console.PrintWarning(
                "Could not restore BIM startup context: {}\n".format(exc)
            )

    return activated


def populate_document_startup(document):
    """Populate the prepared BIM activity after presentation is released."""

    from bimplan.runtime.session import get_active_session

    session = get_active_session()
    if session is None or session.doc is not document:
        return False
    try:
        return session.populate(attach_task_panel=False)
    except Exception as exc:
        FreeCAD.Console.PrintError(
            "Could not finish BIM Plan Edit startup: {}\n".format(exc)
        )
        session.shutdown(close_dialog=False)
        return False


def register_startup_activity():
    """Register BIM's versioned startup lifecycle with GUI core."""

    FreeCADGui.registerStartupActivity(
        "BIMWorkbench",
        "PlanEdit",
        GUI_SCHEMA_VERSION,
        prepare_document_startup,
        populate_document_startup,
    )

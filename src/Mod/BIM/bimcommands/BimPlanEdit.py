# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command for entering the reversible BIM Plan Edit view session."""

import FreeCAD
import FreeCADGui


def start_plan_edit_for(obj):
    """Select a storey-like object and enter the shared Plan Edit command."""

    if obj is None:
        return
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(obj)
    FreeCADGui.runCommand("BIM_PlanEdit")


class BIM_PlanEdit:
    def GetResources(self):
        return {
            "Pixmap": "Arch_Floor",
            "MenuText": FreeCAD.Qt.QT_TRANSLATE_NOOP("BIM_PlanEdit", "Plan Edit"),
            "ToolTip": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_PlanEdit", "Enter a reversible, storey-scoped plan view"
            ),
        }

    def IsActive(self):
        gui_document = FreeCADGui.ActiveDocument
        view = getattr(gui_document, "ActiveView", None) if gui_document else None
        return FreeCAD.ActiveDocument is not None and callable(
            getattr(view, "getViewer", None)
        )

    def Activated(self):
        from bimplan.runtime.session import start_session

        start_session()


FreeCADGui.addCommand("BIM_PlanEdit", BIM_PlanEdit())

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command for semantic handle editing in the ordinary 3D model view."""

import FreeCAD
import FreeCADGui


class BIM_ContextualEdit3D:
    def GetResources(self):
        return {
            "Pixmap": "Arch_Wall",
            "MenuText": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_ContextualEdit3D", "3D Contextual Edit"
            ),
            "ToolTip": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_ContextualEdit3D",
                "Edit semantic BIM handles in the current 3D view",
            ),
        }

    def IsActive(self):
        gui_document = FreeCADGui.ActiveDocument
        view = getattr(gui_document, "ActiveView", None) if gui_document else None
        return FreeCAD.ActiveDocument is not None and callable(
            getattr(view, "getViewer", None)
        )

    def Activated(self):
        from bimplan.contextual_edit_3d import active_session, start_session

        session = active_session()
        if session is not None:
            session.close()
            return
        start_session()


FreeCADGui.addCommand("BIM_ContextualEdit3D", BIM_ContextualEdit3D())

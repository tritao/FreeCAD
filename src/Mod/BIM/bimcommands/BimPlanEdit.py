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

"""Command for BIM plan editing."""

import FreeCAD
import FreeCADGui

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


class BIM_PlanEdit:
    def GetResources(self):
        return {
            "Pixmap": "Arch_Floor",
            "MenuText": QT_TRANSLATE_NOOP("BIM_PlanEdit", "Plan Edit"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_PlanEdit",
                "Enters Plan Edit mode locked to a top orthographic BIM view",
            ),
        }

    def IsActive(self):
        return (
            FreeCAD.ActiveDocument is not None
            and hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        )

    def Activated(self):
        from bimcommands import BimPlanSession

        session = BimPlanSession.get_active_session()
        if session:
            panel = getattr(session, "task_panel", None)
            if panel and getattr(panel, "form", None) is not None and not getattr(panel, "_closed", False):
                try:
                    panel.show()
                    panel.raise_()
                    panel.activateWindow()
                    return
                except RuntimeError:
                    pass
            session.shutdown(close_dialog=False)
        BimPlanSession.start_session()


FreeCADGui.addCommand("BIM_PlanEdit", BIM_PlanEdit())

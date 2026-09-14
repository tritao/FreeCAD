# SPDX-License-Identifier: LGPL-2.1-or-later

"""Contextual elevation editing from an Arch SectionPlane frame."""

import FreeCAD
import FreeCADGui

import ArchRepresentation
from bimcommands.BimSectionEdit import _selected_request_source


class BIM_ElevationEdit:
    def GetResources(self):
        return {
            "Pixmap": "Arch_SectionPlane",
            "MenuText": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_ElevationEdit", "Elevation Edit"
            ),
            "ToolTip": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_ElevationEdit",
                "Edit semantic BIM handles in a selected elevation frame",
            ),
        }

    def IsActive(self):
        return (
            FreeCAD.ActiveDocument is not None
            and _selected_request_source(
                ArchRepresentation.RepresentationPurpose.ELEVATION
            )
            is not None
        )

    def Activated(self):
        from ArchContextualCreation import architectural_contextual_providers
        from bimcontextual.session import active_session, start_session

        session = active_session()
        if session is not None:
            session.close()
            return
        source = _selected_request_source(
            ArchRepresentation.RepresentationPurpose.ELEVATION
        )
        if source is None:
            return
        start_session(
            request=source.Proxy.getRepresentationRequest(source),
            sources=tuple(getattr(source, "Objects", ()) or ()),
            orient_to_request=True,
            providers=architectural_contextual_providers(),
        )


FreeCADGui.addCommand("BIM_ElevationEdit", BIM_ElevationEdit())

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Contextual elevation editing from an Arch SectionPlane frame."""

import FreeCAD
import FreeCADGui

import ArchRepresentation
from bimcommands.BimSectionEdit import _selected_section_plane


def _elevation_context(source):
    supplied = source.Proxy.getRepresentationContext(source)
    return ArchRepresentation.RepresentationContext(
        purpose=ArchRepresentation.RepresentationPurpose.ELEVATION,
        reference_frame=supplied.reference_frame,
        cut_range=supplied.cut_range,
        projection_range=supplied.projection_range,
        profile=supplied.profile,
        source=source,
        cut_offset=supplied.cut_offset,
        target_offset=supplied.target_offset,
    )


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
            and _selected_section_plane() is not None
        )

    def Activated(self):
        from bimplan.contextual_session import active_session, start_session

        session = active_session()
        if session is not None:
            session.close()
            return
        source = _selected_section_plane()
        if source is None:
            return
        start_session(
            context=_elevation_context(source),
            sources=tuple(getattr(source, "Objects", ()) or ()),
            orient_to_context=True,
        )


FreeCADGui.addCommand("BIM_ElevationEdit", BIM_ElevationEdit())

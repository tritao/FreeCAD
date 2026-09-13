# SPDX-License-Identifier: LGPL-2.1-or-later

"""Contextual editing in the view defined by an Arch SectionPlane."""

import FreeCAD
import FreeCADGui

import ArchRepresentation


def _selected_section_plane():
    selected = tuple(FreeCADGui.Selection.getSelection() or ())
    if (
        len(selected) != 1
        or getattr(getattr(selected[0], "Proxy", None), "Type", "") != "SectionPlane"
    ):
        return None
    return selected[0]


def _selected_context_source(purpose=None):
    source = _selected_section_plane()
    if source is None or purpose is None:
        return source
    context = source.Proxy.getRepresentationContext(source)
    return source if context.purpose == purpose else None


class BIM_SectionEdit:
    def GetResources(self):
        return {
            "Pixmap": "Arch_SectionPlane",
            "MenuText": FreeCAD.Qt.QT_TRANSLATE_NOOP("BIM_SectionEdit", "Section Edit"),
            "ToolTip": FreeCAD.Qt.QT_TRANSLATE_NOOP(
                "BIM_SectionEdit", "Edit semantic BIM handles in a selected section"
            ),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None and _selected_context_source(
            ArchRepresentation.RepresentationPurpose.SECTION
        ) is not None

    def Activated(self):
        from bimcontextual.session import active_session, start_session

        session = active_session()
        if session is not None:
            session.close()
            return
        section = _selected_context_source(
            ArchRepresentation.RepresentationPurpose.SECTION
        )
        if section is None:
            return
        context = section.Proxy.getRepresentationContext(section)
        start_session(
            context=context,
            sources=tuple(getattr(section, "Objects", ()) or ()),
            orient_to_context=True,
        )


FreeCADGui.addCommand("BIM_SectionEdit", BIM_SectionEdit())

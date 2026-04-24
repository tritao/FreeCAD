# SPDX-License-Identifier: LGPL-2.1-or-later

"""Storey selection helpers for BIM Plan Edit."""

from __future__ import annotations

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate


def collect_storeys(session):
    import Draft

    storeys = []
    for obj in session.doc.Objects:
        obj_type = Draft.getType(obj)
        if obj_type == "Floor":
            storeys.append(obj)
        elif obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
            storeys.append(obj)

    storeys.sort(key=lambda obj: get_storey_elevation(obj))
    return storeys


def find_initial_storey(session):
    import Draft

    for obj in FreeCADGui.Selection.getSelection():
        obj_type = Draft.getType(obj)
        if obj_type == "Floor":
            return obj
        if obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
            return obj
    if session.storeys:
        return session.storeys[0]
    return None


def get_storey_elevation(obj):
    try:
        placement = getattr(obj, "Placement", None)
    except Exception:
        return 0.0
    if placement is not None:
        try:
            return placement.Base.z
        except Exception:
            return 0.0
    return 0.0


def get_storey_label(obj):
    if obj is None:
        return translate("BIM_PlanEdit", "Global XY (Z=0)")
    elevation = FreeCAD.Units.Quantity(get_storey_elevation(obj), FreeCAD.Units.Length).UserString
    try:
        label = str(getattr(obj, "Label", "") or getattr(obj, "Name", "") or "")
    except Exception:
        return translate("BIM_PlanEdit", "Global XY (Z=0)")
    return f"{label} [{elevation}]"


def set_active_storey(session, storey):
    session.active_storey = storey
    session.viewport.apply_plan_view(fit=False)
    session.visibility.apply_storey_visibility()
    session.task_panels.refresh_task_panel_status()

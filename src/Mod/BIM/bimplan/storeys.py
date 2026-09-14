# SPDX-License-Identifier: LGPL-2.1-or-later

"""Storey selection helpers for BIM Plan Edit."""

from __future__ import annotations

import FreeCAD
import FreeCADGui
import ArchBuildingPart

translate = FreeCAD.Qt.translate


class PlanStoreysAPI:
    """Owned session surface for storey-related behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def collect_storeys(self):
        return collect_storeys(self.session)

    def find_initial_storey(self):
        return find_initial_storey(self.session)

    def get_storey_elevation(self, obj):
        return get_storey_elevation(obj)

    def get_storey_label(self, obj):
        return get_storey_label(obj)

    def set_active_storey(self, storey):
        return set_active_storey(self.session, storey)


def collect_storeys(session):
    storeys = list(ArchBuildingPart.iterBuildingStoreys(session.doc, includeLegacyFloors=True))
    storeys.sort(key=lambda obj: get_storey_elevation(obj))
    return storeys


def find_initial_storey(session):
    for obj in FreeCADGui.Selection.getSelection():
        if obj in session.storeys:
            return obj
    if session.storeys:
        return session.storeys[0]
    return None


def get_storey_elevation(obj):
    return ArchBuildingPart.getStoreyElevation(obj)


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

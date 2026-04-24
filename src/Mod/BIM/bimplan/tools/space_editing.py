# SPDX-License-Identifier: LGPL-2.1-or-later

"""Editing helpers for BIM Plan Edit spaces and regions."""

import FreeCAD

from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


def _apply_space_edit(session, title, apply_change):
    try:
        session.doc.openTransaction(title)
        apply_change()
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_space_label(session, label):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    label = str(label or "").strip()
    if not label or label == space.Label:
        return False
    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Rename Space"),
        lambda: setattr(space, "Label", label),
    )


def set_selected_space_type(session, space_type):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    space_type = str(space_type or "")
    if not space_type or space_type == getattr(space, "SpaceType", ""):
        return False
    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Change Space Type"),
        lambda: setattr(space, "SpaceType", space_type),
    )


def set_selected_region_label(session, label):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    label = str(label or "").strip()
    if not label or label == getattr(region, "Label", ""):
        return False
    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Rename Region"),
        lambda: setattr(region, "Label", label),
    )


def set_selected_region_scheme(session, scheme):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    scheme = str(scheme or "").strip()
    if scheme == str(getattr(region, "Scheme", "") or ""):
        return False
    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Change Region Scheme"),
        lambda: setattr(region, "Scheme", scheme),
    )


def set_selected_region_type(session, region_type):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    region_type = str(region_type or "").strip()
    if region_type == str(getattr(region, "RegionType", "") or ""):
        return False
    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Change Region Type"),
        lambda: setattr(region, "RegionType", region_type),
    )


def set_selected_region_parent_space(session, space):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    space = session.visibility.get_plan_semantic_object(space) if space else None
    if space is not None and not session.selection.is_plan_space_object(space):
        return False

    current_parent = getattr(region, "ParentSpace", None)
    current_parent = (
        session.visibility.get_plan_semantic_object(current_parent) if current_parent else None
    )
    if current_parent == space:
        return False

    return _apply_space_edit(
        session,
        translate("BIM_PlanEdit", "Change Region Parent Space"),
        lambda: setattr(region, "ParentSpace", space),
    )


def set_space_boundaries(session, space, boundaries):
    if not session.selection.is_plan_space_object(space):
        return False
    import ArchSpace

    boundaries = ArchSpace.normalizeBoundaryLinks(boundaries)
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Edit Space Boundaries"))
        space.Boundaries = boundaries
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.spaces.refresh_selected_space_visuals()
    session.task_panels.refresh_task_panel_status()
    return True


def add_boundaries_to_selected_space(session):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    existing = session.spaces.get_space_boundary_entries(space)
    additions = session.spaces.get_selected_space_boundary_links(fallback_space=space)
    if not additions:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces to add to the space.\n",
            )
        )
        return False
    merged = existing + additions
    return session.spaces.set_space_boundaries(space, merged)


def remove_selected_space_boundaries(session, row_indexes=None):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    existing = session.spaces.get_space_boundary_entries(space)
    if not existing:
        return False

    if row_indexes:
        row_indexes = set(int(index) for index in row_indexes if int(index) >= 0)
        remaining = [boundary for idx, boundary in enumerate(existing) if idx not in row_indexes]
        if len(remaining) == len(existing):
            return False
        return session.spaces.set_space_boundaries(space, remaining)

    removals = {
        session.spaces.space_boundary_key(boundary)
        for boundary in session.spaces.get_selected_space_boundary_links(fallback_space=space)
    }
    if not removals:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select boundary rows or room-bounding walls to remove from the space.\n",
            )
        )
        return False
    remaining = [
        boundary
        for boundary in existing
        if session.spaces.space_boundary_key(boundary) not in removals
    ]
    if len(remaining) == len(existing):
        return False
    return session.spaces.set_space_boundaries(space, remaining)


def refresh_selected_space_visuals(session):
    session.overlays.invalidate_selected_space_overlay_cache()
    session.overlays.sync_selected_space_overlay()
    session.viewport.request_view_redraw()


def refresh_selected_region_visuals(session):
    session.overlays.sync_selected_region_overlay()
    session.viewport.request_view_redraw()


def restore_selected_semantic_target(session, kind, obj, *, clear_edit_space=False):
    sync_method = {
        plan_target_kinds.PLAN_TARGET_REGION: session.overlays.sync_selected_region_overlay,
        plan_target_kinds.PLAN_TARGET_SPACE: session.overlays.sync_selected_space_overlay,
    }.get(kind)
    if sync_method is None:
        return
    session.current_tool = "Select"
    if clear_edit_space:
        session._edit_space = None
    if obj:
        session.selection.set_selected_plan_target(kind, obj, pending_restore=True)
        session.selection.set_gui_selection_object(obj)
    else:
        session.selection.set_selected_plan_target()
    sync_method()
    session.task_panels.refresh_task_panel_status()


def queue_restore_selected_semantic_target(session, kind, obj, *, clear_edit_space=False):
    try:
        from PySide import QtCore
    except ImportError:
        restore_selected_semantic_target(
            session,
            kind,
            obj,
            clear_edit_space=clear_edit_space,
        )
        return
    QtCore.QTimer.singleShot(
        0,
        lambda: restore_selected_semantic_target(
            session,
            kind,
            obj,
            clear_edit_space=clear_edit_space,
        ),
    )


def restore_selected_region(session, region):
    restore_selected_semantic_target(session, plan_target_kinds.PLAN_TARGET_REGION, region)


def queue_restore_selected_region(session, region):
    queue_restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_REGION,
        region,
    )


def restore_selected_space(session, space):
    restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
        space,
        clear_edit_space=True,
    )


def queue_restore_selected_space(session, space):
    queue_restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
        space,
        clear_edit_space=True,
    )

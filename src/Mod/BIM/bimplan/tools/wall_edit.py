# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan adapters for semantic wall editing and wall-related UI helpers."""

import FreeCAD

from bimplan.runtime import capabilities as runtime_capabilities
from ArchWallSemantic import MINIMUM_WALL_LENGTH, evaluate_hosted_openings


def _get_wall_endpoint_proxy(wall):
    proxy = getattr(wall, "Proxy", None)
    getter = runtime_capabilities.get_callable
    return proxy if getter(proxy, "calc_endpoints") and getter(proxy, "set_from_endpoints") else None


def _active_wall_editor(session):
    editor = getattr(session.contextual_editing, "editor", None)
    operation = getattr(getattr(editor, "handle", None), "operation", None)
    if getattr(operation, "interaction_intent", "") in (
        "WallStretchStart", "WallStretchEnd", "WallMove"
    ):
        return editor
    return None


def has_active_wall_edit(session):
    return bool(_active_wall_editor(session) or session.interaction_state.embedded_tool_name == "Wall")


def is_wall_edit_modal_active(session):
    return _active_wall_editor(session) is not None


def is_selected_wall_endpoint_editable(session):
    wall = session.selection.state.get_selected_plan_target_object("wall")
    if not wall or _get_wall_endpoint_proxy(wall) is None:
        return False
    base = getattr(wall, "Base", None)
    if not base:
        return True
    try:
        edges = tuple(getattr(getattr(base, "Shape", None), "Edges", ()) or ())
        if len(edges) == 1 and not bool(getattr(edges[0], "Closed", False)):
            return True
        import Draft
        return Draft.getType(base) in {"Line", "BezCurve"}
    except Exception:
        return False


def cancel_wall_edit(session, restore=True, refresh=True):
    del restore
    active = has_active_wall_edit(session)
    if session.interaction_state.embedded_tool_name == "Wall":
        session.embedded_tools.cancel("Wall")
    if _active_wall_editor(session):
        session.contextual_editing.cancel(refresh=False)
    if active:
        session.current_tool = "Select"
        session.wall_relations.restore_selected_wall_relation_status()
        session.contextual_rendering.sync_visible_handles()
        session.overlays.openings.sync_selected_wall_opening_context_overlay()
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return active


def reset_pending_edit_state(session, *, restore_wall_visibility=True):
    del restore_wall_visibility
    session.contextual_editing.cancel(refresh=False)


def discard_runtime_references(session):
    session.contextual_editing.cancel(refresh=False)


def get_preview_footprint(session, points, width=None, align=None):
    del session
    if not points or len(points) != 2 or width is None or float(width) <= 0:
        return None
    start, end = (FreeCAD.Vector(point) for point in points)
    axis = end.sub(start)
    if axis.Length < MINIMUM_WALL_LENGTH:
        return None
    axis.normalize()
    perpendicular = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis).multVec(
        FreeCAD.Vector(0, 1, 0)
    )
    width = float(width)
    if align == "Left":
        low, high = -width, 0.0
    elif align == "Right":
        low, high = 0.0, width
    else:
        low, high = -width * 0.5, width * 0.5
    return [start + perpendicular * low, end + perpendicular * low,
            end + perpendicular * high, start + perpendicular * high]


def get_readout_base_gap(session):
    from draftutils import params
    units = session.viewport.get_plan_view_units_per_pixel() or 0.0
    marker = float(params.get_param_view("MarkerSize") or 0.0)
    return max(100.0, marker * 2.0 * 96.0 / 72.0 * units * 1.25)


def get_aligned_readout_offset_for_wall(session, wall):
    width = float(getattr(getattr(wall, "Width", None), "Value", 0.0) or 0.0)
    gap = max(width * 0.25, get_readout_base_gap(session))
    align = str(getattr(wall, "Align", "Center")) if wall else "Center"
    return -gap if align == "Right" else gap if align == "Left" or width <= 0 else width * 0.5 + gap


def get_opening_move_readout_offset(session, opening):
    host = next(iter(getattr(opening, "Hosts", ()) or ()), None) if opening else None
    return get_aligned_readout_offset_for_wall(session, host)


def refresh_wall_hosted_opening_footprints(session, wall):
    for opening in session.openings.get_wall_hosted_openings(wall):
        session.openings.refresh_opening_footprint_display(opening)
        session.openings.refresh_opening_host_footprint_displays(opening)


def compute_wall_hosted_opening_layout(session, wall, endpoints):
    del session
    if not wall or not endpoints or len(endpoints) != 2:
        return []
    return evaluate_hosted_openings(wall, endpoints, endpoints, "Move")


def resolve_wall_hosted_opening_layout(session, wall):
    proxy = _get_wall_endpoint_proxy(wall)
    if proxy is None:
        return True
    layout = compute_wall_hosted_opening_layout(session, wall, proxy.calc_endpoints(wall))
    if layout is None:
        return False
    return all(item["proxy"].move_along_host(item["target_point"]) for item in layout)


class PlanWallEditAPI:
    def __init__(self, session):
        self.session = session

    def has_active_wall_edit(self):
        return has_active_wall_edit(self.session)

    def is_wall_edit_modal_active(self):
        return is_wall_edit_modal_active(self.session)

    def is_selected_wall_endpoint_editable(self):
        return is_selected_wall_endpoint_editable(self.session)

    def cancel_wall_edit(self, *args, **kwargs):
        return cancel_wall_edit(self.session, *args, **kwargs)

    def cancel_for_select(self):
        return self.cancel_wall_edit()

    def reset_pending_edit_state(self, *args, **kwargs):
        return reset_pending_edit_state(self.session, *args, **kwargs)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def get_preview_footprint(self, *args, **kwargs):
        return get_preview_footprint(self.session, *args, **kwargs)

    def get_opening_move_readout_offset(self, *args, **kwargs):
        return get_opening_move_readout_offset(self.session, *args, **kwargs)

    def refresh_wall_hosted_opening_footprints(self, *args, **kwargs):
        return refresh_wall_hosted_opening_footprints(self.session, *args, **kwargs)

    def compute_wall_hosted_opening_layout(self, *args, **kwargs):
        return compute_wall_hosted_opening_layout(self.session, *args, **kwargs)

    def resolve_wall_hosted_opening_layout(self, *args, **kwargs):
        return resolve_wall_hosted_opening_layout(self.session, *args, **kwargs)

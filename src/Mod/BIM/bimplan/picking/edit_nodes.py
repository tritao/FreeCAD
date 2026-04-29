# SPDX-License-Identifier: LGPL-2.1-or-later

"""Edit-node picking helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.picking import debug as plan_picking_debug
from bimplan.providers import picking as plan_provider_picking
from bimplan.selection import edit_nodes as plan_edit_nodes
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection import targets as plan_targets


def get_plan_target_from_edit_node(session, node):
    if not node:
        return plan_target_kinds.make_plan_target_ref()
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind in ("provider_overlay_point", "provider_overlay_target"):
        target_ref = plan_provider_picking.get_provider_overlay_target_from_edit_node(session, node)
        if session.selection.state.is_valid_plan_target(target_ref.kind, target_ref.obj):
            return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
        fallback_target_ref = plan_target_kinds.coerce_plan_target_ref(
            plan_targets.get_plan_target_for_object(session, target_ref.obj)
        )
        return plan_target_kinds.make_plan_target_ref(
            fallback_target_ref.kind, fallback_target_ref.obj
        )
    if node_kind == "opening_handle":
        opening, _index = plan_edit_nodes.get_edit_node_payload(node)
        if session.openings.is_hosted_opening_object(opening):
            return plan_target_kinds.make_plan_target_ref("opening", opening)
        return plan_target_kinds.make_plan_target_ref()
    if node_kind == "symbol_handle":
        symbol, _role = plan_edit_nodes.get_edit_node_payload(node)
        if session.visibility.is_plan_symbol_instance(symbol):
            return plan_target_kinds.make_plan_target_ref("symbol", symbol)
        return plan_target_kinds.make_plan_target_ref()
    try:
        (point,) = plan_edit_nodes.get_edit_node_payload(node)
        doc = FreeCAD.getDocument(str(point.documentName.getValue()))
        obj = doc.getObject(str(point.objectName.getValue()))
    except Exception:
        return plan_target_kinds.make_plan_target_ref()
    if session.openings.is_hosted_opening_object(obj):
        return plan_target_kinds.make_plan_target_ref("opening", obj)
    target_ref = plan_target_kinds.coerce_plan_target_ref(
        plan_targets.get_plan_target_for_object(session, obj)
    )
    return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)


def get_edit_node(session, mouse_pos):
    node = _get_selected_handle_edit_node(session, mouse_pos)
    if node is not None:
        return node
    node = _get_provider_overlay_edit_node(session, mouse_pos)
    if node is not None:
        return node
    return _get_ray_picked_edit_node(session, mouse_pos)


def _emit_get_edit_node_result(session, mouse_pos, source, result):
    plan_picking_debug.emit_pick_debug(
        session,
        "get_edit_node",
        mouse_pos=mouse_pos,
        source=source,
        result=result,
    )
    return result


def _get_selected_handle_edit_node(session, mouse_pos):
    symbol_handle_role = session.overlays.symbols.pick_selected_symbol_handle(mouse_pos)
    if symbol_handle_role is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_symbol_handle",
            plan_edit_nodes.SymbolHandleEditNode(
                session.selection.state.get_selected_plan_target_object("symbol"),
                symbol_handle_role,
            ),
        )
    opening_handle_index = pick_selected_opening_handle(session, mouse_pos)
    if opening_handle_index is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_opening_handle",
            plan_edit_nodes.OpeningHandleEditNode(
                session.selection.state.get_selected_plan_target_object("opening"),
                opening_handle_index,
            ),
        )
    provider_handle_index = session.overlays.providers.pick_selected_provider_handle(mouse_pos)
    if provider_handle_index is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_provider_handle",
            plan_edit_nodes.ProviderHandleEditNode(
                session.selection.state.get_selected_plan_target_object("provider"),
                provider_handle_index,
            ),
        )
    return None


def _get_provider_overlay_edit_node(session, mouse_pos):
    target_ref = plan_provider_picking.pick_provider_overlay_target_from_objects_info(
        session, mouse_pos
    )
    if target_ref.obj is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "provider_overlay_objects_info",
            plan_edit_nodes.ProviderOverlayTargetEditNode(target_ref.kind, target_ref.obj),
        )
    target_ref = plan_provider_picking.pick_provider_overlay_target_from_overlays(
        session, mouse_pos
    )
    if target_ref.obj is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "provider_overlay_overlays",
            plan_edit_nodes.ProviderOverlayTargetEditNode(target_ref.kind, target_ref.obj),
        )
    return None


def _get_ray_picked_edit_node(session, mouse_pos):
    render_manager = session.viewport_state.render_manager
    if not render_manager:
        return _emit_get_edit_node_result(session, mouse_pos, "no_render_manager", None)
    try:
        from pivy import coin
    except Exception:
        return _emit_get_edit_node_result(session, mouse_pos, "coin_import_failed", None)

    ray_pick = coin.SoRayPickAction(render_manager.getViewportRegion())
    ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
    ray_pick.setRadius(8)
    ray_pick.setPickAll(True)
    ray_pick.apply(render_manager.getSceneGraph())
    picked_points = ray_pick.getPickedPointList()
    if not picked_points:
        return _emit_get_edit_node_result(session, mouse_pos, "no_edit_node", None)
    return _get_edit_node_from_picked_points(session, mouse_pos, picked_points)


def _get_edit_node_from_picked_points(session, mouse_pos, picked_points):
    for picked_point in picked_points:
        path = picked_point.getPath()
        point = path.getNode(path.getLength() - 2)
        try:
            sub_element = str(point.subElementName.getValue())
        except Exception:
            continue
        if plan_provider_picking.is_provider_overlay_point_subname(sub_element):
            return _emit_get_edit_node_result(
                session,
                mouse_pos,
                "ray_pick_provider_overlay_point",
                plan_edit_nodes.ProviderOverlayPointEditNode(point),
            )
        if "EditNode" in sub_element:
            return _emit_get_edit_node_result(
                session,
                mouse_pos,
                "ray_pick_edit_node",
                plan_edit_nodes.RayEditNode(point),
            )
    return _emit_get_edit_node_result(session, mouse_pos, "no_edit_node", None)


def pick_selected_opening_handle(session, mouse_pos, radius_px=10):
    opening = session.selection.state.get_selected_plan_target_object("opening")
    if not session.openings.is_hosted_opening_object(opening) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_index = None
    best_distance_sq = None
    for idx, _role, point, _marker in session.overlays.openings.get_selected_opening_handle_specs(
        opening
    ):
        try:
            screen_x, screen_y = session.view.getPointOnScreen(point)
        except Exception:
            continue
        dx = float(screen_x) - float(cursor_x)
        dy = float(screen_y) - float(cursor_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq > radius_px * radius_px:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_index = idx
            best_distance_sq = distance_sq
    return best_index

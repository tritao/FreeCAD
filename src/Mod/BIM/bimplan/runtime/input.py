# SPDX-License-Identifier: LGPL-2.1-or-later

"""Input event routing for BIM Plan Edit."""

import FreeCAD

from bimplan import selection as plan_selection


def on_mouse_pressed(session, event_callback):
    if session._tearing_down:
        return
    try:
        from pivy import coin
    except Exception:
        return

    event = event_callback.getEvent()
    mouse_pos = None
    try:
        pos = event.getPosition().getValue()
        mouse_pos = (pos[0], pos[1])
    except Exception:
        mouse_pos = None
    selected_before = session.selection.get_selected_plan_target()
    with session.performance.plan_perf_trace_event(
        "mouse_pressed",
        button=str(event.getButton()),
        state=str(event.getState()),
        mouse_pos=mouse_pos,
        selected_before=session.performance.plan_perf_describe_target(
            selected_before[0], selected_before[1]
        ),
    ):
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        with session.performance.plan_pick_debug_scope(
            "mouse_pressed_pick",
            button=str(event.getButton()),
            state=str(event.getState()),
            mouse_pos=mouse_pos,
            selected_before=session.performance.plan_perf_describe_target(
                selected_before[0], selected_before[1]
            ),
        ):
            try:
                if event.getState() == coin.SoMouseButtonEvent.UP:
                    if session._consume_left_button_release:
                        session._consume_left_button_release = False
                        session._set_event_handled(event_callback)
                        return

                if event.getState() == coin.SoMouseButtonEvent.DOWN:
                    session._consume_left_button_release = False
                    if session.current_tool == "Join":
                        pos = event.getPosition().getValue()
                        target_kind, target_wall = session.selection.get_plan_target_at_position(
                            (pos[0], pos[1])
                        )
                        source_wall = plan_selection.get_selected_plan_target_object(
                            session, "wall"
                        )
                        if (
                            target_kind == "wall"
                            and session.selection.is_plan_selectable_wall(target_wall)
                            and target_wall != source_wall
                            and session.wall_relations.apply_plan_wall_join(
                                source_wall, target_wall
                            )
                        ):
                            session._claim_left_button_click(event_callback)
                        return
                    else:
                        if session.current_tool == "Pick Space Region":
                            pos = event.getPosition().getValue()
                            candidate = session.spaces.pick_space_region_candidate((pos[0], pos[1]))
                            if candidate:
                                session.spaces.activate_space_region_candidate(
                                    candidate,
                                    event_callback,
                                )
                            return
                        if session.current_tool != "Select":
                            return
                        pos = event.getPosition().getValue()
                        mouse_pos = (pos[0], pos[1])
                        if session._is_plan_additive_selection_active():
                            if not session.selection.toggle_plan_target_selection_at_position(
                                mouse_pos, event_callback
                            ):
                                session._claim_left_button_click(event_callback)
                            return
                        node = session.selection.get_edit_node(mouse_pos)
                        if not node:
                            if session.selection.activate_semantic_plan_target(
                                mouse_pos, event_callback
                            ):
                                return
                            session.selection.clear_plan_selection_state()
                            session._claim_left_button_click(event_callback)
                            return
                        node_kind = node[0]
                        if node_kind == "opening_handle":
                            _kind, obj, index = node
                            session.selection.select_opening_for_plan_edit(obj)
                            session.selection.set_gui_selection_object(obj)
                            session.openings.activate_opening_handle(obj, index)
                        elif node_kind == "provider_handle":
                            _kind, obj, index = node
                            session._set_selected_plan_target_state("provider", obj)
                            session.overlays.clear_wall_grips()
                            session.overlays.clear_selected_wall_overlay()
                            session.providers.activate_provider_handle(obj, index)
                        elif node_kind == "symbol_handle":
                            _kind, obj, role = node
                            session._set_selected_plan_target_state("symbol", obj)
                            session.overlays.clear_wall_grips()
                            session.overlays.clear_selected_wall_overlay()
                            session.symbols.activate_symbol_handle(obj, role)
                        elif node_kind in (
                            "provider_overlay_point",
                            "provider_overlay_target",
                        ):
                            if not session.selection.activate_provider_overlay_target_node(
                                node,
                                event_callback,
                            ):
                                return
                        else:
                            point = node[1]
                            try:
                                doc = FreeCAD.getDocument(str(point.documentName.getValue()))
                                obj = doc.getObject(str(point.objectName.getValue()))
                                index = int(str(point.subElementName.getValue())[8:])
                            except Exception:
                                return
                            if session.openings.is_hosted_opening_object(obj):
                                session.selection.select_opening_for_plan_edit(obj)
                                session.selection.set_gui_selection_object(obj)
                                session.openings.activate_opening_handle(obj, index)
                            else:
                                session._set_selected_plan_target_state("wall", obj)
                                session.wall_edit.activate_wall_grip(index, wall=obj)
                        session._claim_left_button_click(event_callback)
            finally:
                selected_after = session.selection.get_selected_plan_target()
                session.performance.plan_perf_set_fields(
                    handled=bool(getattr(event_callback, "_handled", False)),
                    selected_after=session.performance.plan_perf_describe_target(
                        selected_after[0], selected_after[1]
                    ),
                )


def on_mouse_moved(session, event_callback):
    if session._tearing_down:
        return
    event = event_callback.getEvent()
    try:
        pos = event.getPosition().getValue()
        mouse_pos = (pos[0], pos[1])
    except Exception:
        mouse_pos = None
    hovered_before = session.selection.get_hovered_plan_target()
    with session.performance.plan_perf_trace_event(
        "mouse_moved",
        mouse_pos=mouse_pos,
        hovered_before=session.performance.plan_perf_describe_target(
            hovered_before[0], hovered_before[1]
        ),
    ):
        if session.current_tool == "Pick Space Region":
            if mouse_pos is not None:
                session.spaces.set_hovered_space_region_candidate(
                    session.spaces.pick_space_region_candidate(mouse_pos)
                )
                session.overlays.refresh_plan_overlay_visuals()
            return
        if session.current_tool not in ("Select", "Join"):
            session._set_hovered_wall(None)
            session._set_hovered_opening(None)
            session._set_hovered_symbol(None)
            session._set_hovered_provider(None)
            session._set_hovered_space(None)
            session._set_hovered_region(None)
            return
        if mouse_pos is None:
            return
        if not session.selection.update_hovered_plan_target(mouse_pos):
            return
        if session._grip_trackers or session._is_selected_plan_target("wall"):
            session.overlays.sync_wall_grips()
        session.viewport.request_view_redraw()
        hovered_after = session.selection.get_hovered_plan_target()
        session.performance.plan_perf_set_fields(
            hovered_after=session.performance.plan_perf_describe_target(
                hovered_after[0], hovered_after[1]
            ),
        )


def on_mouse_wheel(session, event_callback):
    if session._tearing_down:
        return
    event = event_callback.getEvent()
    try:
        event_type_name = str(event.getTypeId().getName())
    except Exception:
        event_type_name = ""
    if event_type_name != "SoMouseWheelEvent":
        return
    with session.performance.plan_perf_trace_event("mouse_wheel", event_type=event_type_name):
        session.overlays.queue_plan_overlay_view_scale_refresh()


def on_key_pressed(session, event_callback):
    if session._tearing_down:
        return
    try:
        from pivy import coin
    except Exception:
        return
    event = event_callback.getEvent()
    key = event.getKey()
    if session.current_tool == "Move Opening" and key == coin.SoKeyboardEvent.A:
        if session.openings.cycle_opening_move_anchor():
            session.openings.refresh_opening_move_preview_from_raw_point()
            session.task_panels.refresh_task_panel_status()
        return
    if (
        session.current_tool in ("Move Symbol", "Rotate Symbol")
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.symbols.cancel_symbol_handle_point_pick()
        return
    if session.current_tool == "Join" and key == coin.SoKeyboardEvent.TAB:
        if session.wall_relations.cycle_plan_join_type() and hasattr(event_callback, "setHandled"):
            event_callback.setHandled()
        return
    if session.current_tool == "Join" and key in (
        getattr(coin.SoKeyboardEvent, "DELETE", None),
        getattr(coin.SoKeyboardEvent, "BACKSPACE", None),
    ):
        if session.wall_relations.unjoin_current_plan_wall_pair() and hasattr(
            event_callback, "setHandled"
        ):
            event_callback.setHandled()
        return
    if session.current_tool == "Join" and key == coin.SoKeyboardEvent.ESCAPE:
        session.wall_relations.cancel_join_tool()
        return
    if session.current_tool == "Pick Space Region" and key == coin.SoKeyboardEvent.ESCAPE:
        session.spaces.cancel_space_region_pick()
        return
    if session.current_tool == "Region" and key in (
        coin.SoKeyboardEvent.RETURN,
        coin.SoKeyboardEvent.ENTER,
    ):
        if session.spaces.finalize_plan_region():
            if hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
        return
    if session.current_tool == "Region" and key == coin.SoKeyboardEvent.ESCAPE:
        session.spaces.cancel_plan_region_tool()
        return
    if session.current_tool == "Provider Point" and key == coin.SoKeyboardEvent.ESCAPE:
        session.providers.cancel_provider_point_tool()
        return
    if session.current_tool == "Move Provider" and key == coin.SoKeyboardEvent.ESCAPE:
        session.providers.cancel_provider_handle_point_pick()
        return
    if session.current_tool == "Window" and key == coin.SoKeyboardEvent.ESCAPE:
        session.windows.cancel_window_tool()
        return
    if session.wall_edit.is_wall_move_edit_active() and key == coin.SoKeyboardEvent.TAB:
        if session.wall_edit.start_wall_readout_edit(cycle=True):
            if hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
        return
    if session.wall_edit.is_wall_readout_edit_active() and key in (
        coin.SoKeyboardEvent.RETURN,
        coin.SoKeyboardEvent.ENTER,
    ):
        if session.wall_edit.start_wall_readout_edit():
            if hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
        return
    if session.wall_edit.is_wall_stretch_edit_active() and key == coin.SoKeyboardEvent.TAB:
        if session.wall_edit.start_wall_readout_edit():
            if hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
        return
    if key != coin.SoKeyboardEvent.ESCAPE:
        return
    if session._edit_wall and session.current_tool != "Select":
        session.wall_edit.cancel_wall_edit_point_pick()
        return
    if session.current_tool == "Move Opening":
        session.openings.cancel_opening_handle_point_pick()
        return
    if session.current_tool == "Move Provider":
        session.providers.cancel_provider_handle_point_pick()
        return
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session.symbols.cancel_symbol_handle_point_pick()
        return
    if session.current_tool == "Set Space Text":
        session.spaces.cancel_space_text_position_pick()
        return
    if session.providers.has_active_provider_point_tool():
        session.providers.cancel_provider_point_tool()
        return
    if session.windows.has_active_window_tool():
        session.windows.cancel_window_tool()
        return
    if session.wall_create.has_active_rect_wall_tool():
        session.wall_create.cancel_rect_wall_tool()
        return
    if session.spaces.has_active_plan_region_tool():
        session.spaces.cancel_plan_region_tool()
        return
    if session.spaces.has_active_space_separator_tool():
        session.spaces.cancel_space_separator_tool()

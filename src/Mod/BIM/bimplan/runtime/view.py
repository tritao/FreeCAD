# SPDX-License-Identifier: LGPL-2.1-or-later

"""View and viewport helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

_VIEW_PREFERENCES_PATH = "User parameter:BaseApp/Preferences/View"
_ENABLE_PRESELECTION_PARAM = "EnablePreselection"


class PlanViewportAPI:
    """Owned session surface for Plan Edit view and viewport behavior."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def capture_view_action_state(self):
        return capture_view_action_state(
            self.session,
            self.session.viewport_state.plan_view_locked_actions,
        )

    def apply_locked_view_actions(self):
        return apply_locked_view_actions(
            self.session,
            self.session.viewport_state.plan_view_locked_actions,
        )

    def apply_plan_background_override(self):
        return apply_plan_background_override(
            self.session,
            self.session.viewport_state.plan_paper_rgb,
        )

    def apply_plan_navigation_profile(self):
        return apply_plan_navigation_profile(
            self.session,
            self.session.viewport_state.plan_view_locked_actions,
        )

    def ensure_viewport_status_chip(self):
        from bimplan.ui.task_panel import _PlanEditViewportStatusChip

        return ensure_viewport_status_chip(
            self.session,
            _PlanEditViewportStatusChip,
        )

    def refresh_viewport_status_chip(self):
        from bimplan.ui.task_panel import _PlanEditViewportStatusChip

        return refresh_viewport_status_chip(
            self.session,
            _PlanEditViewportStatusChip,
        )

    def schedule_viewport_status_chip_refresh(self):
        from bimplan.ui.task_panel import _PlanEditViewportStatusChip

        return schedule_viewport_status_chip_refresh(
            self.session,
            _PlanEditViewportStatusChip,
        )

    def discard_stale_runtime_object(self, obj):
        return discard_stale_runtime_object(self.session, obj)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def get_runtime_attr(self, obj, attr_name):
        return get_runtime_attr(self.session, obj, attr_name)

    def get_navigation_style(self):
        return get_navigation_style(self.session)

    def get_main_window(self):
        return get_main_window(self.session)

    def find_main_window_action(self, command_name):
        return find_main_window_action(self.session, command_name)

    def capture_navigation_flag(self, target, getter_name, state_key):
        return capture_navigation_flag(self.session, target, getter_name, state_key)

    def apply_navigation_flag(self, target, setter_name, state_key, enabled):
        return apply_navigation_flag(self.session, target, setter_name, state_key, enabled)

    def capture_navigation_state(self):
        return capture_navigation_state(self.session)

    def clear_plan_background_override(self):
        return clear_plan_background_override(self.session)

    def restore_navigation_state(self):
        return restore_navigation_state(self.session)

    def force_plan_preselection(self):
        return force_plan_preselection(self.session)

    def restore_preselection_state(self):
        return restore_preselection_state(self.session)

    def apply_plan_view(self, fit=True):
        return apply_plan_view(self.session, fit=fit)

    def restore_state(self):
        return restore_state(self.session)

    def capture_state(self):
        return capture_state(self.session)

    def get_interaction_plane(self):
        return get_interaction_plane(self.session)

    def project_plan_point(self, point):
        return project_plan_point(self.session, point)

    def get_plan_view_height(self):
        return get_plan_view_height(self.session)

    def get_plan_overlay_scale(self):
        return get_plan_overlay_scale(self.session)

    def scaled_line_width(self, base_width):
        return scaled_line_width(self.session, base_width)

    def scaled_marker_size(self, base_size):
        return scaled_marker_size(self.session, base_size)

    def get_plan_view_units_per_pixel(self):
        return get_plan_view_units_per_pixel(self.session)

    def get_plan_projection_cache_key(self):
        return get_plan_projection_cache_key(self.session)

    def get_plan_point_from_mouse_pos(self, mouse_pos):
        return get_plan_point_from_mouse_pos(self.session, mouse_pos)

    def set_active_object(self, obj):
        return set_active_object(self.session, obj)

    def sync_active_plan_target_object(self):
        return sync_active_plan_target_object(self.session)

    def register_edit_callbacks(self):
        return register_edit_callbacks(self.session)

    def unregister_edit_callbacks(self):
        return unregister_edit_callbacks(self.session)

    def focus_plan_view(self):
        return focus_plan_view(self.session)

    def queue_focus_plan_view(self):
        return queue_focus_plan_view(self.session)

    def get_plan_view_widget(self):
        return get_plan_view_widget(self.session)

    def clear_viewport_status_chip(self):
        return clear_viewport_status_chip(self.session)

    def request_view_redraw(self):
        return request_view_redraw(self.session)


def _copy_plane(plane):
    import WorkingPlane

    if plane is None:
        return None

    def _copy_vec(vec):
        return FreeCAD.Vector(vec.x, vec.y, vec.z)

    return WorkingPlane.PlaneBase(
        _copy_vec(plane.u),
        _copy_vec(plane.v),
        _copy_vec(plane.axis),
        _copy_vec(plane.position),
    )


def discard_stale_runtime_object(session, obj):
    if obj is session.view:
        session.view = None
        session.viewer = None
    elif obj is session.viewer:
        session.viewer = None


def discard_runtime_references(session):
    viewport_state = session.viewport_state
    session.viewport.clear_viewport_status_chip()
    session.viewport.restore_preselection_state()
    session.doc = None
    session.gui_doc = None
    session.view = None
    session.viewer = None
    viewport_state.saved_navigation_style = None
    viewport_state.saved_navigation_state = {}
    viewport_state.saved_view_action_state = {}
    viewport_state.saved_preselection_state = None
    viewport_state.plan_preselection_forced = False
    viewport_state.saved_camera = None
    viewport_state.saved_camera_type = None
    viewport_state.working_plane = None
    viewport_state.interaction_plane = None


def get_runtime_attr(session, obj, attr_name):
    if obj is None:
        return None
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return None
    except (ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(obj)
        return None


def get_navigation_style(session):
    viewer = session.viewer
    get_navigation_style_attr = session.viewport.get_runtime_attr(viewer, "getNavigationStyle")
    if get_navigation_style_attr is None:
        return None
    try:
        return get_navigation_style_attr()
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(viewer)
        return None


def get_main_window(_session):
    try:
        return FreeCADGui.getMainWindow()
    except Exception:
        return None


def find_main_window_action(session, command_name):
    from PySide import QtGui

    main_window = get_main_window(session)
    if not main_window:
        return None
    try:
        return main_window.findChild(QtGui.QAction, command_name)
    except Exception:
        return None


def capture_view_action_state(session, locked_actions):
    viewport_state = session.viewport_state
    for command_name in locked_actions:
        if command_name in viewport_state.saved_view_action_state:
            continue
        action = find_main_window_action(session, command_name)
        if action is None:
            continue
        try:
            viewport_state.saved_view_action_state[command_name] = bool(action.isEnabled())
        except Exception:
            pass


def apply_locked_view_actions(session, locked_actions):
    capture_view_action_state(session, locked_actions)
    for command_name in locked_actions:
        action = find_main_window_action(session, command_name)
        if action is None:
            continue
        try:
            action.setEnabled(False)
        except Exception:
            pass


def restore_locked_view_actions(session):
    for command_name, enabled in session.viewport_state.saved_view_action_state.items():
        action = find_main_window_action(session, command_name)
        if action is None:
            continue
        try:
            action.setEnabled(bool(enabled))
        except Exception:
            pass


def capture_navigation_flag(session, target, getter_name, state_key):
    viewport_state = session.viewport_state
    if state_key in viewport_state.saved_navigation_state:
        return
    getter = session.viewport.get_runtime_attr(target, getter_name)
    if getter is None:
        return
    try:
        viewport_state.saved_navigation_state[state_key] = bool(getter())
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(target)


def apply_navigation_flag(session, target, setter_name, state_key, enabled):
    if state_key not in session.viewport_state.saved_navigation_state:
        return
    setter = session.viewport.get_runtime_attr(target, setter_name)
    if setter is None:
        return
    try:
        setter(enabled)
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(target)


def capture_navigation_state(session):
    viewport_state = session.viewport_state
    nav_style = get_navigation_style(session)
    if nav_style:
        viewport_state.saved_navigation_style = nav_style
    capture_navigation_flag(session, nav_style, "isRotationEnabled", "rotation_enabled")
    capture_navigation_flag(session, nav_style, "isOrientationLocked", "orientation_locked")
    if session.viewport.get_runtime_attr(session.viewer, "setNaviCubeEnabledOverride") is None:
        capture_navigation_flag(
            session,
            session.viewer,
            "isEnabledNaviCube",
            "navicube_enabled",
        )
    capture_navigation_flag(
        session,
        session.view,
        "isCornerCrossVisible",
        "corner_cross_visible",
    )


def apply_plan_background_override(session, paper_rgb):
    viewer = session.viewer
    set_background_override = session.viewport.get_runtime_attr(
        viewer, "setBackgroundAppearanceOverride"
    )
    if set_background_override is None:
        return
    try:
        set_background_override("NONE", paper_rgb, paper_rgb, paper_rgb)
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(viewer)


def clear_plan_background_override(session):
    viewer = session.viewer
    clear_background_override = session.viewport.get_runtime_attr(
        viewer, "clearBackgroundAppearanceOverride"
    )
    if clear_background_override is None:
        return
    try:
        clear_background_override()
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(viewer)


def apply_plan_navigation_profile(session, locked_actions):
    capture_navigation_state(session)
    nav_style = session.viewport_state.saved_navigation_style or get_navigation_style(session)
    apply_navigation_flag(
        session,
        nav_style,
        "setRotationEnabled",
        "rotation_enabled",
        False,
    )
    apply_navigation_flag(
        session,
        nav_style,
        "setOrientationLocked",
        "orientation_locked",
        True,
    )
    set_navicube_override = session.viewport.get_runtime_attr(
        session.viewer, "setNaviCubeEnabledOverride"
    )
    if set_navicube_override is not None:
        try:
            set_navicube_override(False)
        except (AttributeError, ReferenceError, RuntimeError):
            session.viewport.discard_stale_runtime_object(session.viewer)
    else:
        apply_navigation_flag(
            session, session.viewer, "setEnabledNaviCube", "navicube_enabled", False
        )
    apply_navigation_flag(
        session, session.view, "setCornerCrossVisible", "corner_cross_visible", False
    )
    apply_locked_view_actions(session, locked_actions)


def restore_navigation_state(session):
    viewport_state = session.viewport_state
    nav_style = viewport_state.saved_navigation_style or get_navigation_style(session)
    apply_navigation_flag(
        session,
        nav_style,
        "setRotationEnabled",
        "rotation_enabled",
        viewport_state.saved_navigation_state.get("rotation_enabled"),
    )
    apply_navigation_flag(
        session,
        nav_style,
        "setOrientationLocked",
        "orientation_locked",
        viewport_state.saved_navigation_state.get("orientation_locked"),
    )
    clear_navicube_override = session.viewport.get_runtime_attr(
        session.viewer, "clearNaviCubeEnabledOverride"
    )
    if clear_navicube_override is not None:
        try:
            clear_navicube_override()
        except (AttributeError, ReferenceError, RuntimeError):
            session.viewport.discard_stale_runtime_object(session.viewer)
    else:
        apply_navigation_flag(
            session,
            session.viewer,
            "setEnabledNaviCube",
            "navicube_enabled",
            viewport_state.saved_navigation_state.get("navicube_enabled"),
        )
    apply_navigation_flag(
        session,
        session.view,
        "setCornerCrossVisible",
        "corner_cross_visible",
        viewport_state.saved_navigation_state.get("corner_cross_visible"),
    )
    restore_locked_view_actions(session)


def _get_view_preferences():
    return FreeCAD.ParamGet(_VIEW_PREFERENCES_PATH)


def capture_preselection_state(session):
    if session.viewport_state.saved_preselection_state is not None:
        return
    params = _get_view_preferences()
    try:
        has_preselection_param = _ENABLE_PRESELECTION_PARAM in params.GetBools()
    except Exception:
        has_preselection_param = True
    try:
        enabled = bool(params.GetBool(_ENABLE_PRESELECTION_PARAM, True))
    except Exception:
        enabled = True
    session.viewport_state.saved_preselection_state = (has_preselection_param, enabled)


def force_plan_preselection(session):
    capture_preselection_state(session)
    params = _get_view_preferences()
    try:
        if bool(params.GetBool(_ENABLE_PRESELECTION_PARAM, True)):
            return
        params.SetBool(_ENABLE_PRESELECTION_PARAM, True)
        session.viewport_state.plan_preselection_forced = True
    except Exception:
        pass


def restore_preselection_state(session):
    viewport_state = session.viewport_state
    state = viewport_state.saved_preselection_state
    if state is None:
        return
    viewport_state.saved_preselection_state = None
    viewport_state.plan_preselection_forced = False
    had_preselection_param, enabled = state
    params = _get_view_preferences()
    try:
        if had_preselection_param:
            params.SetBool(_ENABLE_PRESELECTION_PARAM, bool(enabled))
        else:
            params.RemBool(_ENABLE_PRESELECTION_PARAM)
    except Exception:
        pass


def apply_plan_view(session, fit=True):
    import WorkingPlane

    if session.view:
        with session.performance.plan_perf_trace_span("apply_plan_view_camera_top"):
            try:
                session.view.setCameraType("Orthographic")
                session.view.viewTop()
            except RuntimeError:
                session.view = None

    if session.viewer:
        with session.performance.plan_perf_trace_span("apply_plan_view_footprint_override"):
            try:
                session.viewer.setOverrideMode("Footprint")
                apply_plan_background_override(session, session.viewport_state.plan_paper_rgb)
            except RuntimeError:
                session.viewer = None

    with session.performance.plan_perf_trace_span("apply_plan_view_working_plane"):
        wp = WorkingPlane.get_working_plane(update=False)
        offset = (
            session.storey.get_storey_elevation(session.active_storey)
            if session.active_storey
            else 0.0
        )
        wp.set_to_top(offset=offset)
        _update_working_plane(wp)

        session.viewport_state.interaction_plane = WorkingPlane.PlaneBase()
        session.viewport_state.interaction_plane.set_to_top(offset=offset)

    if session.active_storey:
        with session.performance.plan_perf_trace_span("apply_plan_view_set_active_object"):
            session.viewport.set_active_object(session.active_storey)

    with session.performance.plan_perf_trace_span("apply_plan_view_navigation_profile"):
        apply_plan_navigation_profile(session, session.viewport_state.plan_view_locked_actions)

    if fit and session.view:
        with session.performance.plan_perf_trace_span("apply_plan_view_fit_all"):
            try:
                session.view.fitAll()
            except RuntimeError:
                session.view = None


def restore_state(session):
    import WorkingPlane

    restore_preselection_state(session)
    session.visibility.restore_object_view_state()
    session.snap.restore_snap_profile()
    session.viewport_state.interaction_plane = None

    if session.viewer:
        try:
            session.viewer.setOverrideMode("As Is")
            clear_plan_background_override(session)
        except RuntimeError:
            session.viewer = None

    viewport_state = session.viewport_state
    if session.view and viewport_state.saved_camera_type:
        try:
            session.view.setCameraType(viewport_state.saved_camera_type)
        except RuntimeError:
            session.view = None
    if session.view and viewport_state.saved_camera:
        try:
            session.view.setCamera(viewport_state.saved_camera)
        except RuntimeError:
            session.view = None

    wp = viewport_state.working_plane or WorkingPlane.get_working_plane(update=False)
    restore = getattr(wp, "restore", None)
    if callable(restore):
        try:
            restore()
            _update_working_plane(wp)
        except RuntimeError:
            pass

    restore_navigation_state(session)


def capture_state(session):
    import WorkingPlane

    get_camera = session.viewport.get_runtime_attr(session.view, "getCamera")
    if get_camera is not None:
        try:
            session.viewport_state.saved_camera = get_camera()
        except (AttributeError, ReferenceError, RuntimeError):
            session.viewport.discard_stale_runtime_object(session.view)
    get_camera_type = session.viewport.get_runtime_attr(session.view, "getCameraType")
    if get_camera_type is not None:
        try:
            session.viewport_state.saved_camera_type = get_camera_type()
        except (AttributeError, ReferenceError, RuntimeError):
            session.viewport.discard_stale_runtime_object(session.view)

    session.viewport_state.working_plane = WorkingPlane.get_working_plane(update=False)
    save = getattr(session.viewport_state.working_plane, "save", None)
    if callable(save):
        save()


def get_interaction_plane(session):
    import WorkingPlane

    if session.viewport_state.interaction_plane is not None:
        return _copy_plane(session.viewport_state.interaction_plane)
    return WorkingPlane.get_working_plane(update=False)


def project_plan_point(session, point):
    plane = get_interaction_plane(session)
    project_point = getattr(plane, "project_point", None) if plane else None
    if callable(project_point):
        try:
            return project_point(point)
        except Exception:
            pass
    return point


def get_plan_view_height(session):
    if (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not session.view
    ):
        return None
    get_camera_node = session.viewport.get_runtime_attr(session.view, "getCameraNode")
    if get_camera_node is None:
        return None
    try:
        camera = get_camera_node()
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(session.view)
        return None
    try:
        height_prop = getattr(camera, "height")
    except (AttributeError, ReferenceError, RuntimeError):
        return None
    try:
        return float(height_prop.getValue())
    except Exception:
        return None


def get_plan_overlay_scale(session):
    height = get_plan_view_height(session)
    if not height or height <= 0:
        return 1.0
    if height <= 5000.0:
        return 1.0
    if height >= 30000.0:
        return 0.35
    scale = 5000.0 / height
    return max(0.35, min(1.0, scale * 2.0))


def _update_working_plane(wp):
    update_all = getattr(wp, "_update_all", None)
    if not callable(update_all):
        return
    update_all(_hist_add=False)


def scaled_line_width(session, base_width):
    return max(1.0, base_width * get_plan_overlay_scale(session))


def scaled_marker_size(session, base_size):
    return max(4, int(round(base_size * get_plan_overlay_scale(session))))


def get_plan_view_units_per_pixel(session):
    height = get_plan_view_height(session)
    get_size = session.viewport.get_runtime_attr(session.view, "getSize")
    if not height or height <= 0 or get_size is None:
        return None
    try:
        view_height = float(get_size()[1])
    except Exception:
        return None
    if view_height <= 0:
        return None
    return height / view_height


def get_plan_projection_cache_key(session):
    if (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not session.view
    ):
        return None
    get_camera_node = session.viewport.get_runtime_attr(session.view, "getCameraNode")
    get_size = session.viewport.get_runtime_attr(session.view, "getSize")
    if get_camera_node is None or get_size is None:
        return None
    try:
        camera = get_camera_node()
    except Exception:
        return None
    try:
        size = get_size()
        size_key = (int(size[0]), int(size[1]))
    except Exception:
        return None
    try:
        position = getattr(camera, "position").getValue()
        position_key = (
            round(float(position[0]), 6),
            round(float(position[1]), 6),
            round(float(position[2]), 6),
        )
    except Exception:
        position_key = (None, None, None)
    height = get_plan_view_height(session)
    if height is None:
        return None
    return size_key + (round(float(height), 6),) + position_key


def get_plan_point_from_mouse_pos(session, mouse_pos):
    if not session.view or not mouse_pos:
        return None
    get_point = session.viewport.get_runtime_attr(session.view, "getPoint")
    if get_point is None:
        return None
    try:
        point = get_point(int(mouse_pos[0]), int(mouse_pos[1]))
    except TypeError:
        try:
            point = get_point((int(mouse_pos[0]), int(mouse_pos[1])))
        except Exception:
            return None
    except Exception:
        return None
    return session.viewport.project_plan_point(point)


def set_active_object(session, obj):
    try:
        session.view.setActiveObject("Arch", None)
    except Exception:
        pass
    try:
        session.view.setActiveObject("NativeIFC", None)
    except Exception:
        pass
    if obj is None:
        return
    context = "Arch"
    if getattr(obj, "IfcType", "") == "Building Storey":
        context = "NativeIFC"
    try:
        session.view.setActiveObject(context, obj)
    except Exception:
        pass


def sync_active_plan_target_object(session):
    if not session.view:
        return
    target_kind, target_obj = session.selection.state.get_selected_plan_target()
    del target_kind
    if target_obj is not None:
        session.viewport.set_active_object(target_obj)
        return
    if session.active_storey is not None:
        session.viewport.set_active_object(session.active_storey)
        return
    session.viewport.set_active_object(None)


def register_edit_callbacks(session):
    try:
        from pivy import coin
    except Exception:
        return

    add_event_callback = session.viewport.get_runtime_attr(session.view, "addEventCallbackPivy")
    if add_event_callback is None:
        return

    try:
        viewer = session.viewer
        if viewer is None:
            get_viewer = session.viewport.get_runtime_attr(session.view, "getViewer")
            if get_viewer is None:
                return
            viewer = get_viewer()
            session.viewer = viewer
        get_render_manager = session.viewport.get_runtime_attr(viewer, "getSoRenderManager")
        session.viewport_state.render_manager = (
            get_render_manager() if get_render_manager is not None else None
        )
        input_event_state = session.input_event_state
        if input_event_state.key_pressed_cb is None:
            input_event_state.key_pressed_cb = add_event_callback(
                coin.SoKeyboardEvent.getClassTypeId(), session.input.on_key_pressed
            )
        if input_event_state.mouse_moved_cb is None:
            input_event_state.mouse_moved_cb = add_event_callback(
                coin.SoLocation2Event.getClassTypeId(), session.input.on_mouse_moved
            )
        if input_event_state.mouse_wheel_cb is None:
            event_type = getattr(coin, "SoMouseWheelEvent", None)
            if event_type is not None:
                input_event_state.mouse_wheel_event_type = event_type.getClassTypeId()
            else:
                input_event_state.mouse_wheel_event_type = coin.SoEvent.getClassTypeId()
            input_event_state.mouse_wheel_cb = add_event_callback(
                input_event_state.mouse_wheel_event_type, session.input.on_mouse_wheel
            )
        if input_event_state.mouse_pressed_cb is None:
            input_event_state.mouse_pressed_cb = add_event_callback(
                coin.SoMouseButtonEvent.getClassTypeId(), session.input.on_mouse_pressed
            )
    except (AttributeError, ReferenceError, RuntimeError):
        session.viewport.discard_stale_runtime_object(session.view)
        session.viewport_state.render_manager = None


def _clear_edit_callbacks(session):
    input_event_state = session.input_event_state
    input_event_state.key_pressed_cb = None
    input_event_state.mouse_moved_cb = None
    input_event_state.mouse_wheel_cb = None
    input_event_state.mouse_wheel_event_type = None
    input_event_state.mouse_pressed_cb = None
    session.viewport_state.render_manager = None


def unregister_edit_callbacks(session):
    try:
        from pivy import coin
    except Exception:
        _clear_edit_callbacks(session)
        return

    if not session.view:
        _clear_edit_callbacks(session)
        return

    try:
        input_event_state = session.input_event_state
        if input_event_state.key_pressed_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoKeyboardEvent.getClassTypeId(), input_event_state.key_pressed_cb
            )
        if input_event_state.mouse_moved_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoLocation2Event.getClassTypeId(), input_event_state.mouse_moved_cb
            )
        if input_event_state.mouse_wheel_cb and input_event_state.mouse_wheel_event_type:
            session.view.removeEventCallbackSWIG(
                input_event_state.mouse_wheel_event_type, input_event_state.mouse_wheel_cb
            )
        if input_event_state.mouse_pressed_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoMouseButtonEvent.getClassTypeId(), input_event_state.mouse_pressed_cb
            )
    except RuntimeError:
        pass

    _clear_edit_callbacks(session)


def focus_plan_view(session):
    if session.lifecycle_state.tearing_down or not session.view:
        return
    try:
        widget = session.view.graphicsView()
    except Exception:
        widget = None
    if widget is not None:
        try:
            widget.activateWindow()
        except Exception:
            pass
        try:
            widget.setFocus()
        except Exception:
            pass
        return
    try:
        session.view.setFocus()
    except Exception:
        pass


def queue_focus_plan_view(session):
    try:
        from PySide import QtCore
    except Exception:
        focus_plan_view(session)
        return
    QtCore.QTimer.singleShot(0, lambda: focus_plan_view(session))


def get_plan_view_widget(session):
    if session.lifecycle_state.tearing_down or not session.view:
        return None
    try:
        return session.view.graphicsView()
    except Exception:
        return None


def ensure_viewport_status_chip(session, chip_factory):
    widget = get_plan_view_widget(session)
    if widget is None:
        clear_viewport_status_chip(session)
        return None
    viewport_state = session.viewport_state
    chip = viewport_state.status_chip
    if chip is not None and getattr(chip, "host_widget", None) is widget:
        return chip
    clear_viewport_status_chip(session)
    try:
        chip = chip_factory(session, widget)
    except Exception:
        return None
    viewport_state.status_chip = chip
    return chip


def refresh_viewport_status_chip(session, chip_factory):
    session.viewport_state.status_chip_refresh_queued = False
    if session.lifecycle_state.tearing_down:
        return
    chip = ensure_viewport_status_chip(session, chip_factory)
    if chip is None:
        return
    title, body = session.status_text.get_status_chip_text()
    try:
        chip.set_texts(title, body)
    except Exception:
        clear_viewport_status_chip(session)


def clear_viewport_status_chip(session):
    viewport_state = session.viewport_state
    viewport_state.status_chip_refresh_queued = False
    chip = viewport_state.status_chip
    viewport_state.status_chip = None
    if chip is None:
        return
    try:
        chip.close_chip()
    except Exception:
        pass


def schedule_viewport_status_chip_refresh(session, chip_factory):
    viewport_state = session.viewport_state
    if viewport_state.status_chip_refresh_queued or session.lifecycle_state.tearing_down:
        return
    try:
        from PySide import QtCore
    except ImportError:
        refresh_viewport_status_chip(session, chip_factory)
        return
    viewport_state.status_chip_refresh_queued = True
    QtCore.QTimer.singleShot(0, lambda: refresh_viewport_status_chip(session, chip_factory))


def request_view_redraw(session):
    if session.lifecycle_state.tearing_down:
        return
    redraw = session.viewport.get_runtime_attr(session.view, "redraw")
    if redraw is not None:
        try:
            redraw()
            return
        except Exception:
            session.viewport.discard_stale_runtime_object(session.view)

# SPDX-License-Identifier: LGPL-2.1-or-later

"""View and viewport helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

_VIEW_PREFERENCES_PATH = "User parameter:BaseApp/Preferences/View"
_ENABLE_PRESELECTION_PARAM = "EnablePreselection"


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


def get_navigation_style(session):
    viewer = session.viewer
    get_navigation_style_attr = session._get_runtime_attr(viewer, "getNavigationStyle")
    if get_navigation_style_attr is None:
        return None
    try:
        return get_navigation_style_attr()
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(viewer)
        return None


def get_main_window(_session):
    try:
        return FreeCADGui.getMainWindow()
    except Exception:
        return None


def find_main_window_action(session, command_name):
    from PySide import QtGui

    main_window = session._get_main_window()
    if not main_window:
        return None
    try:
        return main_window.findChild(QtGui.QAction, command_name)
    except Exception:
        return None


def capture_view_action_state(session, locked_actions):
    for command_name in locked_actions:
        if command_name in session._saved_view_action_state:
            continue
        action = session._find_main_window_action(command_name)
        if action is None:
            continue
        try:
            session._saved_view_action_state[command_name] = bool(action.isEnabled())
        except Exception:
            pass


def apply_locked_view_actions(session, locked_actions):
    session._capture_view_action_state()
    for command_name in locked_actions:
        action = session._find_main_window_action(command_name)
        if action is None:
            continue
        try:
            action.setEnabled(False)
        except Exception:
            pass


def restore_locked_view_actions(session):
    for command_name, enabled in session._saved_view_action_state.items():
        action = session._find_main_window_action(command_name)
        if action is None:
            continue
        try:
            action.setEnabled(bool(enabled))
        except Exception:
            pass


def capture_navigation_flag(session, target, getter_name, state_key):
    if state_key in session._saved_navigation_state:
        return
    getter = session._get_runtime_attr(target, getter_name)
    if getter is None:
        return
    try:
        session._saved_navigation_state[state_key] = bool(getter())
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(target)


def apply_navigation_flag(session, target, setter_name, state_key, enabled):
    if state_key not in session._saved_navigation_state:
        return
    setter = session._get_runtime_attr(target, setter_name)
    if setter is None:
        return
    try:
        setter(enabled)
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(target)


def capture_navigation_state(session):
    nav_style = session._get_navigation_style()
    if nav_style:
        session._saved_navigation_style = nav_style
    session._capture_navigation_flag(nav_style, "isRotationEnabled", "rotation_enabled")
    session._capture_navigation_flag(nav_style, "isOrientationLocked", "orientation_locked")
    if session._get_runtime_attr(session.viewer, "setNaviCubeEnabledOverride") is None:
        session._capture_navigation_flag(session.viewer, "isEnabledNaviCube", "navicube_enabled")
    session._capture_navigation_flag(session.view, "isCornerCrossVisible", "corner_cross_visible")


def apply_plan_background_override(session, paper_rgb):
    viewer = session.viewer
    set_background_override = session._get_runtime_attr(viewer, "setBackgroundAppearanceOverride")
    if set_background_override is None:
        return
    try:
        set_background_override("NONE", paper_rgb, paper_rgb, paper_rgb)
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(viewer)


def clear_plan_background_override(session):
    viewer = session.viewer
    clear_background_override = session._get_runtime_attr(
        viewer, "clearBackgroundAppearanceOverride"
    )
    if clear_background_override is None:
        return
    try:
        clear_background_override()
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(viewer)


def apply_plan_navigation_profile(session, locked_actions):
    session._capture_navigation_state()
    nav_style = session._saved_navigation_style or session._get_navigation_style()
    session._apply_navigation_flag(nav_style, "setRotationEnabled", "rotation_enabled", False)
    session._apply_navigation_flag(nav_style, "setOrientationLocked", "orientation_locked", True)
    set_navicube_override = session._get_runtime_attr(session.viewer, "setNaviCubeEnabledOverride")
    if set_navicube_override is not None:
        try:
            set_navicube_override(False)
        except (AttributeError, ReferenceError, RuntimeError):
            session._discard_stale_runtime_object(session.viewer)
    else:
        session._apply_navigation_flag(
            session.viewer, "setEnabledNaviCube", "navicube_enabled", False
        )
    session._apply_navigation_flag(
        session.view, "setCornerCrossVisible", "corner_cross_visible", False
    )
    session._apply_locked_view_actions()


def restore_navigation_state(session):
    nav_style = session._saved_navigation_style or session._get_navigation_style()
    session._apply_navigation_flag(
        nav_style,
        "setRotationEnabled",
        "rotation_enabled",
        session._saved_navigation_state.get("rotation_enabled"),
    )
    session._apply_navigation_flag(
        nav_style,
        "setOrientationLocked",
        "orientation_locked",
        session._saved_navigation_state.get("orientation_locked"),
    )
    clear_navicube_override = session._get_runtime_attr(
        session.viewer, "clearNaviCubeEnabledOverride"
    )
    if clear_navicube_override is not None:
        try:
            clear_navicube_override()
        except (AttributeError, ReferenceError, RuntimeError):
            session._discard_stale_runtime_object(session.viewer)
    else:
        session._apply_navigation_flag(
            session.viewer,
            "setEnabledNaviCube",
            "navicube_enabled",
            session._saved_navigation_state.get("navicube_enabled"),
        )
    session._apply_navigation_flag(
        session.view,
        "setCornerCrossVisible",
        "corner_cross_visible",
        session._saved_navigation_state.get("corner_cross_visible"),
    )
    session._restore_locked_view_actions()


def _get_view_preferences():
    return FreeCAD.ParamGet(_VIEW_PREFERENCES_PATH)


def capture_preselection_state(session):
    if getattr(session, "_saved_preselection_state", None) is not None:
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
    session._saved_preselection_state = (has_preselection_param, enabled)


def force_plan_preselection(session):
    capture_preselection_state(session)
    params = _get_view_preferences()
    try:
        if bool(params.GetBool(_ENABLE_PRESELECTION_PARAM, True)):
            return
        params.SetBool(_ENABLE_PRESELECTION_PARAM, True)
        session._plan_preselection_forced = True
    except Exception:
        pass


def restore_preselection_state(session):
    state = getattr(session, "_saved_preselection_state", None)
    if state is None:
        return
    session._saved_preselection_state = None
    session._plan_preselection_forced = False
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
        with session._plan_perf_trace_span("apply_plan_view_camera_top"):
            try:
                session.view.setCameraType("Orthographic")
                session.view.viewTop()
            except RuntimeError:
                session.view = None

    if session.viewer:
        with session._plan_perf_trace_span("apply_plan_view_footprint_override"):
            try:
                session.viewer.setOverrideMode("Footprint")
                session._apply_plan_background_override()
            except RuntimeError:
                session.viewer = None

    with session._plan_perf_trace_span("apply_plan_view_working_plane"):
        wp = WorkingPlane.get_working_plane(update=False)
        offset = (
            session.get_storey_elevation(session.active_storey) if session.active_storey else 0.0
        )
        wp.set_to_top(offset=offset)
        if hasattr(wp, "_update_all"):
            wp._update_all(_hist_add=False)

        session._interaction_plane = WorkingPlane.PlaneBase()
        session._interaction_plane.set_to_top(offset=offset)

    if session.active_storey:
        with session._plan_perf_trace_span("apply_plan_view_set_active_object"):
            session._set_active_object(session.active_storey)

    with session._plan_perf_trace_span("apply_plan_view_navigation_profile"):
        session._apply_plan_navigation_profile()

    if fit and session.view:
        with session._plan_perf_trace_span("apply_plan_view_fit_all"):
            try:
                session.view.fitAll()
            except RuntimeError:
                session.view = None


def restore_state(session):
    import WorkingPlane

    session._restore_preselection_state()
    session._restore_object_view_state()
    session._restore_snap_profile()
    session._interaction_plane = None

    if session.viewer:
        try:
            session.viewer.setOverrideMode("As Is")
            session._clear_plan_background_override()
        except RuntimeError:
            session.viewer = None

    if session.view and session._saved_camera_type:
        try:
            session.view.setCameraType(session._saved_camera_type)
        except RuntimeError:
            session.view = None
    if session.view and session._saved_camera:
        try:
            session.view.setCamera(session._saved_camera)
        except RuntimeError:
            session.view = None

    wp = session._working_plane or WorkingPlane.get_working_plane(update=False)
    if hasattr(wp, "restore"):
        try:
            wp.restore()
            wp._update_all(_hist_add=False)
        except RuntimeError:
            pass

    session._restore_navigation_state()


def capture_state(session):
    import WorkingPlane

    get_camera = session._get_runtime_attr(session.view, "getCamera")
    if get_camera is not None:
        try:
            session._saved_camera = get_camera()
        except (AttributeError, ReferenceError, RuntimeError):
            session._discard_stale_runtime_object(session.view)
    get_camera_type = session._get_runtime_attr(session.view, "getCameraType")
    if get_camera_type is not None:
        try:
            session._saved_camera_type = get_camera_type()
        except (AttributeError, ReferenceError, RuntimeError):
            session._discard_stale_runtime_object(session.view)

    session._working_plane = WorkingPlane.get_working_plane(update=False)
    if hasattr(session._working_plane, "save"):
        session._working_plane.save()


def get_interaction_plane(session):
    import WorkingPlane

    if session._interaction_plane is not None:
        return _copy_plane(session._interaction_plane)
    return WorkingPlane.get_working_plane(update=False)


def project_plan_point(session, point):
    plane = session.get_interaction_plane()
    if plane and hasattr(plane, "project_point"):
        try:
            return plane.project_point(point)
        except Exception:
            pass
    return point


def get_plan_view_height(session):
    if session._tearing_down or getattr(session, "_finishing", False) or not session.view:
        return None
    get_camera_node = session._get_runtime_attr(session.view, "getCameraNode")
    if get_camera_node is None:
        return None
    try:
        camera = get_camera_node()
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(session.view)
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
    height = session._get_plan_view_height()
    if not height or height <= 0:
        return 1.0
    if height <= 5000.0:
        return 1.0
    if height >= 30000.0:
        return 0.35
    scale = 5000.0 / height
    return max(0.35, min(1.0, scale * 2.0))


def scaled_line_width(session, base_width):
    return max(1.0, base_width * session._get_plan_overlay_scale())


def scaled_marker_size(session, base_size):
    return max(4, int(round(base_size * session._get_plan_overlay_scale())))


def get_plan_view_units_per_pixel(session):
    height = session._get_plan_view_height()
    get_size = session._get_runtime_attr(session.view, "getSize")
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
    if session._tearing_down or getattr(session, "_finishing", False) or not session.view:
        return None
    get_camera_node = session._get_runtime_attr(session.view, "getCameraNode")
    get_size = session._get_runtime_attr(session.view, "getSize")
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
    height = session._get_plan_view_height()
    if height is None:
        return None
    return size_key + (round(float(height), 6),) + position_key


def register_edit_callbacks(session):
    try:
        from pivy import coin
    except Exception:
        return

    add_event_callback = session._get_runtime_attr(session.view, "addEventCallbackPivy")
    if add_event_callback is None:
        return

    try:
        viewer = session.viewer
        if viewer is None:
            get_viewer = session._get_runtime_attr(session.view, "getViewer")
            if get_viewer is None:
                return
            viewer = get_viewer()
            session.viewer = viewer
        get_render_manager = session._get_runtime_attr(viewer, "getSoRenderManager")
        session._render_manager = get_render_manager() if get_render_manager is not None else None
        if session._key_pressed_cb is None:
            session._key_pressed_cb = add_event_callback(
                coin.SoKeyboardEvent.getClassTypeId(), session._on_key_pressed
            )
        if session._mouse_moved_cb is None:
            session._mouse_moved_cb = add_event_callback(
                coin.SoLocation2Event.getClassTypeId(), session._on_mouse_moved
            )
        if session._mouse_wheel_cb is None:
            event_type = getattr(coin, "SoMouseWheelEvent", None)
            if event_type is not None:
                session._mouse_wheel_event_type = event_type.getClassTypeId()
            else:
                session._mouse_wheel_event_type = coin.SoEvent.getClassTypeId()
            session._mouse_wheel_cb = add_event_callback(
                session._mouse_wheel_event_type, session._on_mouse_wheel
            )
        if session._mouse_pressed_cb is None:
            session._mouse_pressed_cb = add_event_callback(
                coin.SoMouseButtonEvent.getClassTypeId(), session._on_mouse_pressed
            )
    except (AttributeError, ReferenceError, RuntimeError):
        session._discard_stale_runtime_object(session.view)
        session._render_manager = None


def _clear_edit_callbacks(session):
    session._key_pressed_cb = None
    session._mouse_moved_cb = None
    session._mouse_wheel_cb = None
    session._mouse_wheel_event_type = None
    session._mouse_pressed_cb = None
    session._render_manager = None


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
        if session._key_pressed_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoKeyboardEvent.getClassTypeId(), session._key_pressed_cb
            )
        if session._mouse_moved_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoLocation2Event.getClassTypeId(), session._mouse_moved_cb
            )
        if session._mouse_wheel_cb and session._mouse_wheel_event_type:
            session.view.removeEventCallbackSWIG(
                session._mouse_wheel_event_type, session._mouse_wheel_cb
            )
        if session._mouse_pressed_cb:
            session.view.removeEventCallbackSWIG(
                coin.SoMouseButtonEvent.getClassTypeId(), session._mouse_pressed_cb
            )
    except RuntimeError:
        pass

    _clear_edit_callbacks(session)


def focus_plan_view(session):
    if session._tearing_down or not session.view:
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
    QtCore.QTimer.singleShot(0, session._focus_plan_view)


def get_plan_view_widget(session):
    if session._tearing_down or not session.view:
        return None
    try:
        return session.view.graphicsView()
    except Exception:
        return None


def ensure_viewport_status_chip(session, chip_factory):
    widget = session._get_plan_view_widget()
    if widget is None:
        session._clear_viewport_status_chip()
        return None
    chip = session._viewport_status_chip
    if chip is not None and getattr(chip, "host_widget", None) is widget:
        return chip
    session._clear_viewport_status_chip()
    try:
        chip = chip_factory(session, widget)
    except Exception:
        return None
    session._viewport_status_chip = chip
    return chip


def refresh_viewport_status_chip(session, chip_factory):
    if session._tearing_down:
        return
    chip = session._ensure_viewport_status_chip()
    if chip is None:
        return
    title, body = session._get_status_chip_text()
    try:
        chip.set_texts(title, body)
    except Exception:
        session._clear_viewport_status_chip()


def clear_viewport_status_chip(session):
    chip = session._viewport_status_chip
    session._viewport_status_chip = None
    if chip is None:
        return
    try:
        chip.close_chip()
    except Exception:
        pass


def request_view_redraw(session):
    if session._tearing_down:
        return
    redraw = session._get_runtime_attr(session.view, "redraw")
    if redraw is not None:
        try:
            redraw()
            return
        except Exception:
            session._discard_stale_runtime_object(session.view)

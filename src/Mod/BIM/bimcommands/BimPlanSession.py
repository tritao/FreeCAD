# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Session controller for BIM plan editing."""

import FreeCAD
import FreeCADGui
from draftguitools import gui_base

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
_DEFAULT_DOCK_AREA = 2
_MIN_WALL_LENGTH = 10.0
_PLAN_EDIT_SNAP_SET = {
    "Lock",
    "Near",
    "Extension",
    "Endpoint",
    "Midpoint",
    "Perpendicular",
    "Ortho",
    "Intersection",
    "WorkingPlane",
}
# Opening move is already constrained onto the host axis, so keep its snap
# profile minimal. This avoids unrelated object snaps dragging the returned
# point far away from the hovered location during Draft snap winner selection.
_OPENING_MOVE_SNAP_SET = {
    "Lock",
    "WorkingPlane",
}
_OPENING_MOVE_ANCHORS = ("center", "left", "right")
_OPENING_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "Hosts",
    "WindowParts",
    "IfcType",
}
_WALL_VISUAL_PROPERTIES = {"Shape", "Additions", "Subtractions", "Hosts"}
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_WALL_GRIPS = "wall_grips"
_PLAN_VISUAL_WALL_EDIT_PREVIEW = "wall_edit_preview"
_PLAN_VISUAL_ALL = "all"
_PLAN_VIEW_LOCKED_ACTIONS = (
    "Std_ViewFront",
    "Std_ViewTop",
    "Std_ViewRight",
    "Std_ViewRear",
    "Std_ViewBottom",
    "Std_ViewLeft",
    "Std_ViewIsometric",
    "Std_ViewDimetric",
    "Std_ViewTrimetric",
    "Std_ViewRotateLeft",
    "Std_ViewRotateRight",
    "Std_PerspectiveCamera",
    "Std_ViewHome",
    "Std_ViewRestoreCamera",
)

_active_session = None


def _view_param_group():
    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")


def _unsigned_to_rgb(color):
    return (
        ((color >> 24) & 0xFF) / 255.0,
        ((color >> 16) & 0xFF) / 255.0,
        ((color >> 8) & 0xFF) / 255.0,
    )


def _apply_viewer_background(viewer, state):
    if not viewer or not state:
        return

    gradient_mode = "NONE"
    if state.get("radial_gradient", False):
        gradient_mode = "RADIAL"
    elif state.get("gradient", False):
        gradient_mode = "LINEAR"

    viewer.setGradientBackground(gradient_mode)
    viewer.setBackgroundColor(*state["background"])

    if state.get("use_mid", False):
        viewer.setGradientBackgroundColor(
            state["background2"],
            state["background3"],
            state["background4"],
        )
    else:
        viewer.setGradientBackgroundColor(state["background2"], state["background3"])


def _make_plan_background_state(state):
    if not state:
        return None

    return {
        "gradient": False,
        "radial_gradient": False,
        "use_mid": False,
        "background": _PLAN_PAPER_RGB,
        "background2": _PLAN_PAPER_RGB,
        "background3": _PLAN_PAPER_RGB,
        "background4": _PLAN_PAPER_RGB,
    }


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


def get_active_session():
    return _active_session


def start_session():
    global _active_session

    if _active_session:
        return _active_session

    session = PlanEditSession()
    if session.enter():
        _active_session = session
        return session
    return None


class _PlanEditWallHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for wall creation inside Plan Edit.

    This host overrides the generic interaction policy hooks from
    `DraftInteractionHost` so plan wall creation can:
    - avoid task widgets
    - keep ortho on by default
    - use `Shift` as a temporary free-angle override
    - continue chained wall runs from the last endpoint
    """

    def __init__(self, session, command=None):
        super().__init__(command)
        self.session = session

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started("Wall", command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished("Wall", command or self.command)

    def get_working_plane(self):
        return self.session.get_interaction_plane()

    def get_interaction_plane(self):
        return self.session.get_interaction_plane()

    def request_point(
        self,
        callback,
        move_callback=None,
        last=None,
        title=None,
        mode=None,
        extra_widget=None,
        hints=None,
        modifier_resolver=None,
    ):
        del extra_widget
        super().request_point(
            callback=callback,
            move_callback=move_callback,
            last=last,
            title=title,
            mode=mode,
            extra_widget=None,
            hints=hints,
            modifier_resolver=modifier_resolver,
        )

    def clear_ui_state(self):
        return

    def reset_edit(self):
        return

    def show_continue(self):
        return

    def continue_mode_enabled(self):
        return False

    def continue_wall_chain_enabled(self):
        return True

    def supports_extra_widget(self):
        return False

    def resolve_point_request_modifiers(self, ctrl, shift, alt):
        del alt
        return ctrl, False

    def default_ortho_enabled(self):
        return True

    def free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def on_created_object(self, obj):
        self.session._register_plan_object(obj)


class _PlanEditCommandHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for modifiers used inside Plan Edit."""

    def __init__(self, session, tool_name, command=None):
        super().__init__(command)
        self.session = session
        self.tool_name = tool_name

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started(self.tool_name, command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished(self.tool_name, command or self.command)

    def continue_mode_enabled(self):
        return False


class PlanEditSession:
    """Owns the viewer state and control dock for Plan Edit mode."""

    def __init__(self):
        from PySide import QtCore, QtGui

        self.doc = FreeCAD.ActiveDocument
        self.gui_doc = FreeCADGui.ActiveDocument
        self.view = None
        self.viewer = None
        self.task_panel = None
        self.current_tool = "Select"
        self.storeys = []
        self.active_storey = None
        self.selected_wall = None
        self.selected_opening = None
        self.hovered_wall = None
        self.hovered_opening = None
        self._pending_selected_opening_intent = None
        self._grip_trackers = []
        self._wall_hover_trackers = []
        self._opening_hover_trackers = []
        self._opening_overlay_trackers = []
        self._opening_handle_trackers = []
        self._selected_opening_hard_refresh_queued = False
        self._opening_host_recompute_queued = False
        self._opening_host_recompute_running = False
        self._opening_move_preview_trackers = []
        self._opening_move_snap_profile_pushed = False
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self._selection_observer_added = False
        self._document_observer_added = False
        self._pending_selected_wall_reset = False
        self._wall_edit_modal_active = False
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._preview_points = None
        self._preview_line_tracker = None
        self._preview_rect_tracker = None
        self._preview_grip_trackers = []
        self._wall_edit_readout_trackers = []
        self._wall_edit_opening_preview_trackers = []
        self._wall_edit_active_readout_tracker = None
        self._wall_edit_active_readout_mode = None
        self._wall_edit_length_edit_queued = False
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._edit_wall_visibility = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._ignore_selection_changes = False
        self._mouse_moved_cb = None
        self._mouse_wheel_cb = None
        self._mouse_wheel_event_type = None
        self._mouse_pressed_cb = None
        self._key_pressed_cb = None
        self._overlay_refresh_queued = False
        self._dirty_plan_visuals = set()
        self._render_manager = None
        self._saved_camera = None
        self._saved_camera_type = None
        self._saved_background = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self._saved_object_view_state = {}
        self._working_plane = None
        self._interaction_plane = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._finishing = False
        self._tearing_down = False
        app = QtGui.QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.begin_teardown)

    def enter(self):
        if not self.doc or not self.gui_doc:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
            )
            return False

        self.view = self.gui_doc.ActiveView
        if not self.view or not hasattr(self.view, "getViewer"):
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False

        self.viewer = self.view.getViewer()
        self._capture_state()

        self.storeys = self.collect_storeys()
        self.active_storey = self.find_initial_storey()
        self._capture_object_view_state()
        self.apply_plan_view()
        self._apply_plan_snap_profile()
        self._apply_storey_visibility()
        self._attach_selection_observer()
        self._attach_document_observer()
        self._register_edit_callbacks()
        self._refresh_selected_wall()

        panel = PlanEditDockWidget(self)
        self.attach_task_panel(panel)
        panel.refresh()
        panel.show()
        panel.raise_()
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Entered BIM Plan Edit mode.\n"))
        return True

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
            return True
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
            return True
        if self._has_active_wall_edit():
            self._cancel_wall_edit()
            return True
        return self.shutdown(close_dialog=close_dialog)

    def begin_teardown(self):
        if self._tearing_down:
            return
        self._tearing_down = True
        self._clear_input_hints()
        self._cancel_embedded_tool()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        self._clear_hovered_wall_overlay()
        self._clear_wall_grips()
        self._clear_hovered_opening_overlay()
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._clear_opening_move_preview()
        self._detach_selection_observer()
        self._detach_document_observer()
        self._unregister_edit_callbacks()

    def _document_is_alive(self):
        doc = self.doc
        if not doc:
            return False
        try:
            _ = doc.Name
            return True
        except Exception:
            self.doc = None
            return False

    def _discard_runtime_references(self):
        self.doc = None
        self.gui_doc = None
        self.view = None
        self.viewer = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self.selected_wall = None
        self.selected_opening = None
        self.hovered_wall = None
        self.hovered_opening = None
        self._pending_selected_opening_intent = None
        self._edit_wall = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._preview_rect_tracker = None
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._edit_wall_visibility = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None

    def _get_navigation_style(self):
        viewer = self.viewer
        if not viewer or not hasattr(viewer, "getNavigationStyle"):
            return None
        try:
            return viewer.getNavigationStyle()
        except (AttributeError, ReferenceError, RuntimeError):
            return None

    def _get_main_window(self):
        try:
            return FreeCADGui.getMainWindow()
        except Exception:
            return None

    def _find_main_window_action(self, command_name):
        from PySide import QtGui

        main_window = self._get_main_window()
        if not main_window:
            return None
        try:
            return main_window.findChild(QtGui.QAction, command_name)
        except Exception:
            return None

    def _capture_view_action_state(self):
        for command_name in _PLAN_VIEW_LOCKED_ACTIONS:
            if command_name in self._saved_view_action_state:
                continue
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                self._saved_view_action_state[command_name] = bool(action.isEnabled())
            except Exception:
                pass

    def _apply_locked_view_actions(self):
        self._capture_view_action_state()
        for command_name in _PLAN_VIEW_LOCKED_ACTIONS:
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                action.setEnabled(False)
            except Exception:
                pass

    def _restore_locked_view_actions(self):
        for command_name, enabled in self._saved_view_action_state.items():
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                action.setEnabled(bool(enabled))
            except Exception:
                pass

    def _capture_navigation_flag(self, target, getter_name, state_key):
        if state_key in self._saved_navigation_state:
            return
        if not target or not hasattr(target, getter_name):
            return
        try:
            self._saved_navigation_state[state_key] = bool(getattr(target, getter_name)())
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    def _apply_navigation_flag(self, target, setter_name, state_key, enabled):
        if state_key not in self._saved_navigation_state:
            return
        if not target or not hasattr(target, setter_name):
            return
        try:
            getattr(target, setter_name)(enabled)
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    def _capture_navigation_state(self):
        nav_style = self._get_navigation_style()
        if nav_style:
            self._saved_navigation_style = nav_style
        self._capture_navigation_flag(nav_style, "isRotationEnabled", "rotation_enabled")
        self._capture_navigation_flag(nav_style, "isOrientationLocked", "orientation_locked")
        self._capture_navigation_flag(self.viewer, "isEnabledNaviCube", "navicube_enabled")
        self._capture_navigation_flag(self.view, "isCornerCrossVisible", "corner_cross_visible")

    def _apply_plan_navigation_profile(self):
        self._capture_navigation_state()
        nav_style = self._saved_navigation_style or self._get_navigation_style()
        self._apply_navigation_flag(nav_style, "setRotationEnabled", "rotation_enabled", False)
        self._apply_navigation_flag(nav_style, "setOrientationLocked", "orientation_locked", True)
        self._apply_navigation_flag(self.viewer, "setEnabledNaviCube", "navicube_enabled", False)
        self._apply_navigation_flag(
            self.view, "setCornerCrossVisible", "corner_cross_visible", False
        )
        self._apply_locked_view_actions()

    def _restore_navigation_state(self):
        nav_style = self._saved_navigation_style or self._get_navigation_style()
        self._apply_navigation_flag(
            nav_style,
            "setRotationEnabled",
            "rotation_enabled",
            self._saved_navigation_state.get("rotation_enabled"),
        )
        self._apply_navigation_flag(
            nav_style,
            "setOrientationLocked",
            "orientation_locked",
            self._saved_navigation_state.get("orientation_locked"),
        )
        self._apply_navigation_flag(
            self.viewer,
            "setEnabledNaviCube",
            "navicube_enabled",
            self._saved_navigation_state.get("navicube_enabled"),
        )
        self._apply_navigation_flag(
            self.view,
            "setCornerCrossVisible",
            "corner_cross_visible",
            self._saved_navigation_state.get("corner_cross_visible"),
        )
        self._restore_locked_view_actions()

    def shutdown(self, close_dialog=True, teardown=False):
        global _active_session

        if self._finishing:
            return True
        self._finishing = True

        try:
            if not self._document_is_alive():
                self.begin_teardown()
            teardown = teardown or self._tearing_down
            panel = self.task_panel
            self.task_panel = None
            self._cancel_embedded_tool()
            self._cancel_rect_wall_tool(refresh=False)
            self._cancel_wall_edit(restore=not teardown, refresh=False)
            self._cancel_pending_edit()
            self._clear_input_hints()
            self._clear_hovered_wall_overlay()
            self._clear_wall_grips()
            self._clear_hovered_opening_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_opening_handles()
            self._clear_opening_move_preview()
            self._detach_selection_observer()
            self._detach_document_observer()
            self._unregister_edit_callbacks()
            if panel:
                panel.mark_closed()
                if close_dialog and not teardown:
                    panel.close()
                else:
                    panel.detach()
            if teardown:
                self._discard_runtime_references()
            else:
                self.restore_state()
                if self.doc:
                    try:
                        self.doc.recompute()
                    except ReferenceError:
                        self.doc = None
                    except RuntimeError:
                        self.doc = None
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "Exited BIM Plan Edit mode.\n")
                )
        finally:
            _active_session = None
            self._finishing = False
        return True

    def collect_storeys(self):
        import Draft

        storeys = []
        for obj in self.doc.Objects:
            obj_type = Draft.getType(obj)
            if obj_type == "Floor":
                storeys.append(obj)
            elif obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
                storeys.append(obj)

        storeys.sort(key=lambda obj: self.get_storey_elevation(obj))
        return storeys

    def find_initial_storey(self):
        import Draft

        for obj in FreeCADGui.Selection.getSelection():
            obj_type = Draft.getType(obj)
            if obj_type == "Floor":
                return obj
            if obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
                return obj
        if self.storeys:
            return self.storeys[0]
        return None

    def get_storey_elevation(self, obj):
        if hasattr(obj, "Placement"):
            return obj.Placement.Base.z
        return 0.0

    def get_storey_label(self, obj):
        if not obj:
            return translate("BIM_PlanEdit", "Global XY (Z=0)")
        elevation = FreeCAD.Units.Quantity(
            self.get_storey_elevation(obj), FreeCAD.Units.Length
        ).UserString
        return f"{obj.Label} [{elevation}]"

    def set_active_storey(self, storey):
        self.active_storey = storey
        self.apply_plan_view(fit=False)
        self._apply_storey_visibility()
        self._refresh_task_panel_status()

    def _on_embedded_command_started(self, tool_name, command=None):
        if self._tearing_down:
            return
        self._embedded_tool_name = tool_name
        if command is not None:
            self._embedded_tool = command
        self.current_tool = tool_name
        self._refresh_task_panel_status()

    def _on_embedded_command_finished(self, tool_name, command=None):
        if self._tearing_down:
            return
        if command is None or self._embedded_tool is command:
            self._embedded_host = None
            self._embedded_tool = None
            self._embedded_tool_name = None
        if self.current_tool == tool_name:
            self.current_tool = "Select"
            self._refresh_task_panel_status()

    def activate_select_tool(self):
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        self._cancel_wall_edit()

    def activate_wall_tool(self):
        from bimcommands import BimWall

        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self.selected_wall = None
        self._clear_wall_grips()
        try:
            FreeCADGui.Selection.clearSelection()
        except (ReferenceError, RuntimeError):
            pass
        self._start_embedded_tool("Wall", BimWall.Arch_Wall(), host_class=_PlanEditWallHost)

    def activate_rect_wall_tool(self):
        self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self.selected_wall = None
        self._clear_wall_grips()
        self._clear_rect_wall_preview()
        self._rect_wall_start = None
        self._rect_wall_params = self._get_wall_defaults()
        self.current_tool = "Rect Wall"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_rect_wall_point,
            title=translate("BIM_PlanEdit", "First rectangle corner"),
        )
        self._refresh_task_panel_status()

    def activate_move_tool(self):
        from draftguitools import gui_move

        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_wall_grips()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        import Draft

        self._cancel_rect_wall_tool(refresh=False)
        selection = []
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            selection = []

        if not selection:
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Select objects to join before using Join.\n")
            )
            return

        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_wall_grips()

        if all(Draft.getType(obj) == "Wall" for obj in selection):
            from bimcommands import BimArchUtils

            self.current_tool = "Join"
            self._refresh_task_panel_status()
            BimArchUtils.Arch_MergeWalls().Activated()
            self.current_tool = "Select"
            self._refresh_selected_wall()
            return

        from draftguitools import gui_join

        self._start_embedded_tool("Join", gui_join.Join())

    def stretch_selected_wall(self, endpoint):
        self._start_wall_edit(endpoint)

    def move_selected_wall(self):
        self._start_wall_edit("Move")

    def is_selected_wall_endpoint_editable(self):
        wall = self.selected_wall
        if not wall:
            return False
        proxy = getattr(wall, "Proxy", None)
        if not (hasattr(proxy, "calc_endpoints") and hasattr(proxy, "set_from_endpoints")):
            return False
        if not getattr(wall, "Base", None):
            return True
        try:
            import Arch

            return Arch.is_debasable(wall)
        except Exception:
            return False

    def is_selected_wall_baseless(self):
        wall = self.selected_wall
        if not wall:
            return False
        return not getattr(wall, "Base", None) and self.is_selected_wall_endpoint_editable()

    def apply_plan_view(self, fit=True):
        import WorkingPlane

        if self.view:
            try:
                self.view.setCameraType("Orthographic")
                self.view.viewTop()
            except RuntimeError:
                self.view = None

        if self.viewer:
            try:
                self.viewer.setOverrideMode("Footprint")
                if self._saved_background:
                    _apply_viewer_background(
                        self.viewer,
                        _make_plan_background_state(self._saved_background),
                    )
            except RuntimeError:
                self.viewer = None

        wp = WorkingPlane.get_working_plane(update=False)
        offset = self.get_storey_elevation(self.active_storey) if self.active_storey else 0.0
        wp.set_to_top(offset=offset)
        if hasattr(wp, "_update_all"):
            wp._update_all(_hist_add=False)
        # Keep a dedicated immutable-like plan plane for embedded tools instead
        # of reusing Draft's live PlaneGui state, which can be mutated by other
        # Draft UI paths during interaction.
        self._interaction_plane = WorkingPlane.PlaneBase()
        self._interaction_plane.set_to_top(offset=offset)

        if self.active_storey:
            self._set_active_object(self.active_storey)

        if fit and self.view:
            try:
                self.view.fitAll()
            except RuntimeError:
                self.view = None

    def restore_state(self):
        import WorkingPlane

        self._restore_object_view_state()
        self._restore_snap_profile()
        self._interaction_plane = None

        if self.viewer:
            try:
                self.viewer.setOverrideMode("As Is")
                if self._saved_background:
                    _apply_viewer_background(self.viewer, self._saved_background)
            except RuntimeError:
                self.viewer = None

        if self.view and self._saved_camera_type:
            try:
                self.view.setCameraType(self._saved_camera_type)
            except RuntimeError:
                self.view = None
        if self.view and self._saved_camera:
            try:
                self.view.setCamera(self._saved_camera)
            except RuntimeError:
                self.view = None

        wp = self._working_plane or WorkingPlane.get_working_plane(update=False)
        if hasattr(wp, "restore"):
            try:
                wp.restore()
                wp._update_all(_hist_add=False)
            except RuntimeError:
                pass

    def _capture_state(self):
        import WorkingPlane

        if self.view and hasattr(self.view, "getCamera"):
            self._saved_camera = self.view.getCamera()
        if self.view and hasattr(self.view, "getCameraType"):
            self._saved_camera_type = self.view.getCameraType()
        self._saved_background = self._capture_background_state()

        self._working_plane = WorkingPlane.get_working_plane(update=False)
        if hasattr(self._working_plane, "save"):
            self._working_plane.save()

    def get_interaction_plane(self):
        import WorkingPlane

        if self._interaction_plane is not None:
            return _copy_plane(self._interaction_plane)
        return WorkingPlane.get_working_plane(update=False)

    def _project_plan_point(self, point):
        plane = self.get_interaction_plane()
        if plane and hasattr(plane, "project_point"):
            try:
                return plane.project_point(point)
            except Exception:
                pass
        return point

    def _get_wall_defaults(self):
        from draftutils import params

        return {
            "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
            "width": params.get_param_arch("WallWidth"),
            "height": params.get_param_arch("WallHeight"),
            "offset": params.get_param_arch("WallOffset"),
        }

    def _get_plan_view_height(self):
        if not self.view or not hasattr(self.view, "getCameraNode"):
            return None
        try:
            camera = self.view.getCameraNode()
        except (AttributeError, ReferenceError, RuntimeError):
            return None
        if camera is None or not hasattr(camera, "height"):
            return None
        try:
            return float(camera.height.getValue())
        except Exception:
            return None

    def _get_plan_overlay_scale(self):
        height = self._get_plan_view_height()
        if not height or height <= 0:
            return 1.0
        if height <= 5000.0:
            return 1.0
        if height >= 30000.0:
            return 0.35
        scale = 5000.0 / height
        return max(0.35, min(1.0, scale * 2.0))

    def _scaled_line_width(self, base_width):
        return max(1.0, base_width * self._get_plan_overlay_scale())

    def _scaled_marker_size(self, base_size):
        return max(4, int(round(base_size * self._get_plan_overlay_scale())))

    def _get_plan_view_units_per_pixel(self):
        height = self._get_plan_view_height()
        if not height or height <= 0 or not self.view or not hasattr(self.view, "getSize"):
            return None
        try:
            view_height = float(self.view.getSize()[1])
        except Exception:
            return None
        if view_height <= 0:
            return None
        return height / view_height

    def _capture_background_state(self):
        params = _view_param_group()
        return {
            "gradient": params.GetBool("Gradient", True),
            "radial_gradient": params.GetBool("RadialGradient", False),
            "use_mid": params.GetBool("UseBackgroundColorMid", False),
            "background": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor", 3940932863)),
            "background2": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor2", 859006463)),
            "background3": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor3", 2880160255)),
            "background4": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor4", 1869583359)),
        }

    def _apply_plan_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper or not hasattr(snapper, "push_snap_modes"):
            return
        try:
            snapper.push_snap_modes(_PLAN_EDIT_SNAP_SET)
        except Exception:
            pass

    def _restore_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper or not hasattr(snapper, "pop_snap_modes"):
            return
        try:
            snapper.pop_snap_modes()
        except Exception:
            pass

    def _push_opening_move_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if (
            self._opening_move_snap_profile_pushed
            or not snapper
            or not hasattr(snapper, "push_snap_modes")
        ):
            return
        try:
            snapper.push_snap_modes(_OPENING_MOVE_SNAP_SET)
            self._opening_move_snap_profile_pushed = True
        except Exception:
            pass

    def _pop_opening_move_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if (
            not self._opening_move_snap_profile_pushed
            or not snapper
            or not hasattr(snapper, "pop_snap_modes")
        ):
            return
        try:
            snapper.pop_snap_modes()
        except Exception:
            pass
        self._opening_move_snap_profile_pushed = False

    def _capture_object_view_state(self):
        self._saved_object_view_state = {}
        if not self.doc:
            return
        for obj in self.doc.Objects:
            self._register_object_view_state(obj)

    def _register_object_view_state(self, obj):
        if not obj:
            return
        view_object = getattr(obj, "ViewObject", None)
        if not view_object:
            return
        state = {}
        for prop in ("Visibility", "Transparency", "Selectable"):
            if hasattr(view_object, prop):
                try:
                    state[prop] = getattr(view_object, prop)
                except Exception:
                    pass
        if state:
            self._saved_object_view_state[obj.Name] = state

    def _add_object_to_active_storey(self, obj):
        storey = self.active_storey
        if not storey or not obj:
            return False
        if obj is storey or obj in getattr(storey, "InListRecursive", []):
            return True
        try:
            if hasattr(storey, "addObject"):
                storey.addObject(obj)
                return True
        except Exception:
            pass
        group = getattr(storey, "Group", None)
        if group is None:
            return False
        try:
            if obj not in group:
                storey.Group = list(group) + [obj]
            return True
        except Exception:
            return False

    def _register_plan_object(self, obj):
        if not obj:
            return
        self._add_object_to_active_storey(obj)
        self._register_object_view_state(obj)
        self._apply_storey_visibility()

    def _restore_object_view_state(self):
        if not self.doc or not self._saved_object_view_state:
            return
        try:
            doc = self.doc
            _ = doc.Name
        except Exception:
            self.doc = None
            return
        for obj_name, state in self._saved_object_view_state.items():
            try:
                obj = doc.getObject(obj_name)
            except Exception:
                self.doc = None
                return
            if not obj:
                continue
            view_object = getattr(obj, "ViewObject", None)
            if not view_object:
                continue
            for prop, value in state.items():
                if hasattr(view_object, prop):
                    try:
                        setattr(view_object, prop, value)
                    except Exception:
                        pass

    def _is_storey_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") == "Building Storey":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Floor"
        except Exception:
            return False

    def _is_plan_container_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") in {"Site", "Building", "Building Storey"}:
            return True
        if hasattr(obj, "isDerivedFrom") and obj.isDerivedFrom("App::DocumentObjectGroup"):
            return True
        if hasattr(obj, "hasExtension") and obj.hasExtension("App::GroupExtension"):
            return True
        try:
            import Draft

            return Draft.getType(obj) in {
                "Site",
                "Building",
                "Floor",
                "BuildingPart",
                "Group",
            }
        except Exception:
            return False

    def _is_plan_background_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") == "Slab":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
        except Exception:
            return False

    def _is_component_addition_object(self, obj):
        if not obj:
            return False
        for parent in getattr(obj, "InList", []) or []:
            try:
                if obj in getattr(parent, "Additions", []):
                    return True
            except Exception:
                pass
        return False

    def _is_supported_plan_object(self, obj):
        if not obj:
            return False
        if self._is_plan_container_object(obj) or self._is_plan_background_object(obj):
            return True
        try:
            import Draft

            obj_type = Draft.getType(obj)
        except Exception:
            obj_type = ""

        if obj_type in {"Wall", "Window", "Space", "Axis", "AxisSystem"}:
            return True

        if getattr(obj, "IfcType", "") in {
            "Wall",
            "Window",
            "Door",
            "Space",
            "Column",
            "Grid",
            "Stair",
            "Curtain Wall",
        }:
            return True

        return False

    def _is_hosted_opening_object(self, obj):
        if not obj:
            return False
        if not getattr(obj, "Hosts", None):
            return False

        if getattr(obj, "IfcType", "") in {"Window", "Door"}:
            return True

        try:
            import Draft

            return Draft.getType(obj) == "Window"
        except Exception:
            return False

    def _get_supported_plan_visibility(self, obj, state):
        if self._is_component_addition_object(obj):
            return False
        visibility = state.get("Visibility", True)
        # Hosted openings are commonly hidden in the regular 3D workflow while
        # their wall cuts carry the main visual meaning. In Plan Edit we want
        # their committed footprint symbols to be visible whenever they are a
        # supported plan object.
        if self._is_hosted_opening_object(obj):
            return True
        return visibility

    def _apply_background_object_selectability(self, obj, view_object):
        if not view_object or not hasattr(view_object, "Selectable"):
            return
        if not (self._is_plan_background_object(obj) or self._is_plan_container_object(obj)):
            return
        try:
            view_object.Selectable = False
        except Exception:
            pass

    def _apply_hidden_object_state(self, view_object):
        if not view_object:
            return
        if hasattr(view_object, "Visibility"):
            try:
                view_object.Visibility = False
            except Exception:
                pass
        if hasattr(view_object, "Selectable"):
            try:
                view_object.Selectable = False
            except Exception:
                pass

    def _get_object_storeys(self, obj):
        if not obj:
            return []
        storeys = []
        seen = set()
        parents = list(getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []))
        if self._is_storey_object(obj):
            parents.insert(0, obj)
        for parent in parents:
            if not parent or parent.Name in seen:
                continue
            seen.add(parent.Name)
            if self._is_storey_object(parent):
                storeys.append(parent)
        return storeys

    def _apply_storey_visibility(self):
        if not self.doc or not self._saved_object_view_state:
            return

        active_storey_name = getattr(self.active_storey, "Name", None)

        if active_storey_name is None:
            self._restore_object_view_state()
            for obj in self.doc.Objects:
                view_object = getattr(obj, "ViewObject", None)
                state = self._saved_object_view_state.get(obj.Name, {})
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                if view_object and hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_background_object_selectability(obj, view_object)
            return

        for obj in self.doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            state = self._saved_object_view_state.get(obj.Name)
            if not view_object or not state:
                continue

            storeys = self._get_object_storeys(obj)
            if not storeys:
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_background_object_selectability(obj, view_object)
                continue

            belongs_to_active = any(parent.Name == active_storey_name for parent in storeys)
            if belongs_to_active:
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_background_object_selectability(obj, view_object)
                continue

            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                except Exception:
                    pass
            if hasattr(view_object, "Transparency"):
                try:
                    view_object.Transparency = max(int(state.get("Transparency", 0)), 85)
                except Exception:
                    pass
            if hasattr(view_object, "Selectable"):
                try:
                    view_object.Selectable = False
                except Exception:
                    pass

    def _set_active_object(self, obj):
        context = "Arch"
        if getattr(obj, "IfcType", "") == "Building Storey":
            context = "NativeIFC"
        try:
            self.view.setActiveObject(context, obj)
        except Exception:
            pass

    def _attach_selection_observer(self):
        if not self._selection_observer_added:
            FreeCADGui.Selection.addObserver(self)
            self._selection_observer_added = True

    def _detach_selection_observer(self):
        if self._selection_observer_added:
            FreeCADGui.Selection.removeObserver(self)
            self._selection_observer_added = False

    def _attach_document_observer(self):
        if not self._document_observer_added:
            FreeCAD.addDocumentObserver(self)
            self._document_observer_added = True

    def _detach_document_observer(self):
        if self._document_observer_added:
            try:
                FreeCAD.removeDocumentObserver(self)
            except Exception:
                pass
            self._document_observer_added = False

    def _schedule_selected_wall_reset(self, reason, obj):
        if self._pending_selected_wall_reset or self._tearing_down:
            return
        self._pending_selected_wall_reset = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._reset_selected_wall_after_change)
        except Exception:
            self._reset_selected_wall_after_change()

    def _reset_selected_wall_after_change(self):
        self._pending_selected_wall_reset = False
        if self._tearing_down or self.current_tool != "Select":
            return
        wall = self.selected_wall
        if not wall:
            return
        self._clear_wall_grips()
        self.selected_wall = None
        try:
            self._ignore_selection_changes = True
            FreeCADGui.Selection.clearSelection()
        except Exception:
            pass
        finally:
            self._ignore_selection_changes = False
        self._refresh_task_panel_status()

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        """Drop current selected-wall UI state before another tool mutates the host wall."""

        if self._tearing_down:
            return
        if wall is None:
            wall = self.selected_wall
        if wall is None:
            return
        if self.selected_wall != wall:
            return
        self._pending_selected_wall_reset = False
        self._clear_wall_grips()
        self.selected_wall = None
        if clear_gui_selection:
            try:
                self._ignore_selection_changes = True
                FreeCADGui.Selection.clearSelection()
            except Exception:
                pass
            finally:
                self._ignore_selection_changes = False
        self._refresh_task_panel_status()

    def _register_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            return

        if not self.view or not hasattr(self.view, "addEventCallbackPivy"):
            return

        try:
            self._render_manager = self.view.getViewer().getSoRenderManager()
            if self._key_pressed_cb is None:
                self._key_pressed_cb = self.view.addEventCallbackPivy(
                    coin.SoKeyboardEvent.getClassTypeId(), self._on_key_pressed
                )
            if self._mouse_moved_cb is None:
                self._mouse_moved_cb = self.view.addEventCallbackPivy(
                    coin.SoLocation2Event.getClassTypeId(), self._on_mouse_moved
                )
            if self._mouse_wheel_cb is None:
                event_type = getattr(coin, "SoMouseWheelEvent", None)
                if event_type is not None:
                    self._mouse_wheel_event_type = event_type.getClassTypeId()
                else:
                    self._mouse_wheel_event_type = coin.SoEvent.getClassTypeId()
                self._mouse_wheel_cb = self.view.addEventCallbackPivy(
                    self._mouse_wheel_event_type, self._on_mouse_wheel
                )
            if self._mouse_pressed_cb is None:
                self._mouse_pressed_cb = self.view.addEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_pressed
                )
        except RuntimeError:
            self._render_manager = None

    def _unregister_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_wheel_cb = None
            self._mouse_wheel_event_type = None
            self._mouse_pressed_cb = None
            self._render_manager = None
            return

        if not self.view:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_wheel_cb = None
            self._mouse_wheel_event_type = None
            self._mouse_pressed_cb = None
            self._render_manager = None
            return

        try:
            if self._key_pressed_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoKeyboardEvent.getClassTypeId(), self._key_pressed_cb
                )
            if self._mouse_moved_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoLocation2Event.getClassTypeId(), self._mouse_moved_cb
                )
            if self._mouse_wheel_cb and self._mouse_wheel_event_type:
                self.view.removeEventCallbackSWIG(
                    self._mouse_wheel_event_type, self._mouse_wheel_cb
                )
            if self._mouse_pressed_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._mouse_pressed_cb
                )
        except RuntimeError:
            pass

        self._key_pressed_cb = None
        self._mouse_moved_cb = None
        self._mouse_wheel_cb = None
        self._mouse_wheel_event_type = None
        self._mouse_pressed_cb = None
        self._render_manager = None

    def _refresh_selected_wall(self):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        import Draft

        previous_wall = self.selected_wall
        previous_opening = self.selected_opening
        if self._is_wall_edit_modal_active():
            self.selected_wall = self._edit_wall
            self.selected_opening = None
            if previous_wall != self.selected_wall:
                self._sync_wall_grips()
            self._sync_hovered_wall_overlay()
            if previous_opening is not None or self.current_tool != "Select":
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            self._sync_hovered_opening_overlay()
            self._refresh_task_panel_status()
            return
        self.selected_wall = None
        self.selected_opening = None
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            return
        if self.current_tool == "Select" and len(selection) == 1:
            selected = selection[0]
            if Draft.getType(selected) == "Wall":
                self.selected_wall = selected
                self._pending_selected_opening_intent = None
            elif self._is_hosted_opening_object(selected):
                self.selected_opening = selected
                self._pending_selected_opening_intent = None
            else:
                self._pending_selected_opening_intent = None
        elif (
            self.current_tool == "Select"
            and not selection
            and self._is_hosted_opening_object(self._pending_selected_opening_intent)
        ):
            self.selected_opening = self._pending_selected_opening_intent
            self._pending_selected_opening_intent = None
        if previous_wall != self.selected_wall:
            self._sync_wall_grips()
        self._sync_hovered_wall_overlay()
        if previous_opening != self.selected_opening or self.current_tool != "Select":
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
        self._sync_hovered_opening_overlay()
        self._refresh_task_panel_status()

    def _start_embedded_tool(self, tool_name, command, host_class=_PlanEditCommandHost):
        self.current_tool = tool_name
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._refresh_task_panel_status()
        self._embedded_tool = command
        self._embedded_tool_name = tool_name
        if host_class is _PlanEditWallHost:
            self._embedded_host = host_class(self, command)
        else:
            self._embedded_host = host_class(self, tool_name, command)
        command.Activated(host=self._embedded_host)

    def _cancel_pending_edit(self):
        if self._tearing_down:
            self._wall_edit_modal_active = False
            self._restore_edit_wall_visibility()
            self._clear_wall_edit_preview()
            self._edit_wall = None
            self._edit_endpoint = None
            self._edit_endpoints = None
            self._wall_edit_opening_clearances = {}
            self._preview_points = None
            self._wall_edit_length_edit_queued = False
            self._ignore_selection_changes = False
            self._embedded_host = None
            self._embedded_tool = None
            self._embedded_tool_name = None
            self._edit_opening_move_anchor = "center"
            self._edit_opening_move_raw_point = None
            return
        self._stop_snapper()
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._wall_edit_modal_active = False
        self._restore_edit_wall_visibility()
        self._clear_wall_edit_preview()
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._preview_points = None
        self._wall_edit_length_edit_queued = False
        self._ignore_selection_changes = False
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self._sync_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()

    def _stop_snapper(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper:
            return
        toolbar = getattr(FreeCADGui, "draftToolBar", None)
        if toolbar and hasattr(toolbar, "setPointFocusSuppressed"):
            try:
                toolbar.setPointFocusSuppressed(False)
            except Exception:
                pass
        elif toolbar and hasattr(toolbar, "suppress_point_focus"):
            try:
                toolbar.suppress_point_focus = False
            except Exception:
                pass
        try:
            snapper.getPoint()
            snapper.off()
        except Exception:
            pass

    def _set_draft_point_focus_suppressed(self, suppressed):
        toolbar = getattr(FreeCADGui, "draftToolBar", None)
        if not toolbar:
            return
        if hasattr(toolbar, "setPointFocusSuppressed"):
            try:
                toolbar.setPointFocusSuppressed(bool(suppressed))
            except Exception:
                pass
            return
        if hasattr(toolbar, "suppress_point_focus"):
            try:
                toolbar.suppress_point_focus = bool(suppressed)
            except Exception:
                pass

    def _has_active_rect_wall_tool(self):
        return self._rect_wall_start is not None or self.current_tool == "Rect Wall"

    def _clear_rect_wall_preview(self):
        for tracker in self._rect_wall_preview_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._rect_wall_preview_trackers = []

    def _cancel_rect_wall_tool(self, refresh=True):
        if not self._has_active_rect_wall_tool():
            return False
        self._stop_snapper()
        self._clear_rect_wall_preview()
        self._rect_wall_start = None
        self._rect_wall_params = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        return True

    def _get_rect_wall_corners(self, point):
        start = self._rect_wall_start
        if start is None or point is None:
            return None
        end = self._project_plan_point(point)
        if end is None:
            return None
        x1, y1 = start.x, start.y
        x2, y2 = end.x, end.y
        z = start.z
        if abs(x2 - x1) < _MIN_WALL_LENGTH or abs(y2 - y1) < _MIN_WALL_LENGTH:
            return None
        return [
            FreeCAD.Vector(x1, y1, z),
            FreeCAD.Vector(x2, y1, z),
            FreeCAD.Vector(x2, y2, z),
            FreeCAD.Vector(x1, y2, z),
        ]

    def _update_rect_wall_preview(self, point, info):
        del info
        corners = self._get_rect_wall_corners(point)
        if not corners:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        segments = list(zip(corners, corners[1:] + corners[:1]))
        if not self._rect_wall_preview_trackers:
            for start, end in segments:
                tracker = DraftTrackers.rectangleTracker(face=True)
                self._rect_wall_preview_trackers.append(tracker)
        for tracker, (start, end) in zip(self._rect_wall_preview_trackers, segments):
            footprint = self._get_preview_footprint(
                [start, end],
                width=self._rect_wall_params["width"],
                align=self._rect_wall_params["align"],
            )
            if not footprint:
                continue
            axis = end.sub(start)
            if axis.Length < _MIN_WALL_LENGTH:
                continue
            axis.normalize()
            rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
            perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))
            tracker.setPlane(axis, perp)
            tracker.setorigin(footprint[0])
            tracker.update(footprint[2])
            tracker.on()

    def _create_rect_wall_run(self, corners):
        from bimcommands import BimWall

        walls = []
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Rectangular Wall Run"))
        try:
            walls = BimWall.create_wall_run_from_points(
                corners,
                width=self._rect_wall_params["width"],
                height=self._rect_wall_params["height"],
                align=self._rect_wall_params["align"],
                offset=self._rect_wall_params["offset"],
                closed=True,
                on_created=self._register_plan_object,
            )
            BimWall.autojoin_wall_run(walls, closed=True)
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return walls

    def _handle_rect_wall_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_rect_wall_tool()
            return

        point = self._project_plan_point(point)
        if self._rect_wall_start is None:
            self._rect_wall_start = point
            FreeCADGui.Snapper.getPoint(
                callback=self._handle_rect_wall_point,
                movecallback=self._update_rect_wall_preview,
                last=point,
                title=translate("BIM_PlanEdit", "Opposite rectangle corner"),
                mode="line",
            )
            return

        corners = self._get_rect_wall_corners(point)
        if not corners:
            self._cancel_rect_wall_tool()
            return

        try:
            walls = self._create_rect_wall_run(corners)
        except Exception:
            self._cancel_rect_wall_tool()
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the rectangular wall run.\n")
            )
            return

        try:
            FreeCADGui.Selection.clearSelection()
            for wall in walls:
                FreeCADGui.Selection.addSelection(wall)
        except (ReferenceError, RuntimeError):
            pass

        self._cancel_rect_wall_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_selected_wall()
        self._refresh_task_panel_status()

    def _has_active_wall_edit(self):
        return self._is_wall_edit_modal_active() or self._embedded_tool_name == "Wall"

    def _is_wall_edit_modal_active(self):
        return bool(self._wall_edit_modal_active and self._edit_wall)

    def _has_active_embedded_tool(self):
        return self._embedded_tool is not None

    def _cancel_embedded_tool(self, tool_name=None):
        if self._tearing_down or self._embedded_tool is None:
            return
        if tool_name is not None and self._embedded_tool_name != tool_name:
            return
        tool = self._embedded_tool
        if hasattr(tool, "cancel_interactive"):
            try:
                tool.cancel_interactive()
                return
            except Exception:
                pass
        if hasattr(tool, "finish"):
            try:
                tool.finish(cont=False)
            except Exception:
                pass

    def _cancel_wall_edit(self, restore=True, refresh=True):
        if not self._has_active_wall_edit():
            if refresh:
                self.current_tool = "Select"
                self._refresh_task_panel_status()
            return False

        self._cancel_wall_subtool()

        self.current_tool = "Select"
        self._cancel_pending_edit()
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _cancel_wall_subtool(self):
        self._cancel_embedded_tool("Wall")

    def _start_wall_edit(self, mode):
        if not self.is_selected_wall_endpoint_editable():
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "Select a straight wall before using wall grips.\n",
                )
            )
            return

        wall = self.selected_wall
        proxy = getattr(wall, "Proxy", None)
        if (
            not proxy
            or not hasattr(proxy, "calc_endpoints")
            or not hasattr(proxy, "set_from_endpoints")
        ):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        self.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self.selected_wall = wall
        self.selected_opening = None
        self._wall_edit_modal_active = True
        self._edit_wall = wall
        self._edit_endpoint = mode
        self._edit_endpoints = endpoints
        self._wall_edit_opening_clearances = self._snapshot_wall_hosted_opening_clearances(
            wall, endpoints
        )
        self._preview_points = list(endpoints)
        self._edit_wall_visibility = None
        try:
            self._edit_wall_visibility = wall.ViewObject.Visibility
            wall.ViewObject.Visibility = False
        except Exception:
            self._edit_wall_visibility = None
        self._clear_wall_grips()
        self._sync_wall_edit_preview(self._preview_points)
        self._refresh_task_panel_status()
        self._resume_wall_edit_point_pick()

    def _resume_wall_edit_point_pick(self):
        if not self._is_wall_edit_modal_active():
            return
        mode = self._edit_endpoint
        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))
        last = self._get_wall_edit_reference_point()

        FreeCAD.activeDraftCommand = self
        if getattr(FreeCADGui, "Snapper", None):
            try:
                FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            callback=self._finish_wall_edit,
            movecallback=self._update_wall_edit_point_pick,
            last=last,
            title=title,
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _snapshot_wall_hosted_opening_clearances(self, wall, endpoints):
        if not wall or not endpoints or len(endpoints) != 2:
            return {}

        wall_origin = FreeCAD.Vector(endpoints[0])
        wall_axis_u = FreeCAD.Vector(endpoints[1]).sub(wall_origin)
        wall_length = wall_axis_u.Length
        if wall_length < 1e-9:
            return {}
        wall_axis_u.normalize()

        snapshot = {}
        for opening in self._get_wall_hosted_openings(wall):
            proxy = self._get_opening_plan_proxy(
                opening, "get_plan_move_context", "get_plan_center_point"
            )
            if not proxy:
                continue
            context = proxy.get_plan_move_context()
            center = proxy.get_plan_center_point()
            if not context or center is None:
                continue
            half_width = float(context.get("opening_half_width_u") or 0.0)
            center_u = FreeCAD.Vector(center).sub(wall_origin).dot(wall_axis_u)
            snapshot[getattr(opening, "Name", "")] = {
                "center_u": center_u,
                "left_clearance": max(0.0, center_u - half_width),
                "right_clearance": max(0.0, wall_length - (center_u + half_width)),
            }
        return snapshot

    def _finish_wall_edit(self, point=None, obj=None):
        del obj

        wall = self._edit_wall
        endpoint = self._edit_endpoint
        new_points = self._compute_wall_edit_points(point)

        if point is None or not wall or not endpoint or not new_points:
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        proxy = getattr(wall, "Proxy", None)
        if (
            not proxy
            or not hasattr(proxy, "calc_endpoints")
            or not hasattr(proxy, "set_from_endpoints")
        ):
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _commit_wall_edit_points(self, wall, endpoint, proxy, new_points):
        if not wall or not endpoint or not proxy or not new_points:
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        transaction_name = (
            translate("BIM_PlanEdit", "Move Wall")
            if endpoint == "Move"
            else translate("BIM_PlanEdit", "Stretch Wall Endpoint")
        )
        openings_fit = True

        try:
            self.doc.openTransaction(transaction_name)
            proxy.set_from_endpoints(wall, new_points)
            self.doc.recompute()
            openings_fit = self._resolve_wall_hosted_opening_layout(wall)
            if not openings_fit:
                raise RuntimeError("Hosted openings no longer fit within resized wall")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not openings_fit:
                FreeCAD.Console.PrintError(
                    translate(
                        "BIM_PlanEdit",
                        "The resized wall cannot contain its hosted openings.\n",
                    )
                )
            self.current_tool = "Select"
            self._cancel_pending_edit()
            return

        self._refresh_wall_hosted_opening_footprints(wall)
        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(wall)
        except (ReferenceError, RuntimeError):
            pass
        self.current_tool = "Select"
        self._cancel_pending_edit()
        self.selected_wall = wall
        self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _start_wall_grip_edit(self, grip_index):
        if grip_index not in (0, 1, 2) or not self.is_selected_wall_endpoint_editable():
            return
        self._start_wall_edit({0: "Start", 1: "End", 2: "Move"}[grip_index])

    def _activate_wall_grip(self, grip_index):
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_wall_grip_now(grip_index)
            return

        QtCore.QTimer.singleShot(0, lambda: self._activate_wall_grip_now(grip_index))

    def _activate_wall_grip_now(self, grip_index):
        if self._tearing_down or self.current_tool != "Select":
            return
        self._start_wall_grip_edit(grip_index)

    def _get_wall_edit_reference_point(self):
        if not self._edit_endpoints or len(self._edit_endpoints) != 2:
            return None
        if self._edit_endpoint == "Move":
            return (self._edit_endpoints[0] + self._edit_endpoints[1]) * 0.5
        if self._edit_endpoint == "Start":
            return self._edit_endpoints[0]
        if self._edit_endpoint == "End":
            return self._edit_endpoints[1]
        return None

    def _compute_wall_edit_points(self, point):
        endpoint = self._edit_endpoint
        original_endpoints = self._edit_endpoints
        if point is None or not endpoint or not original_endpoints:
            return None

        if endpoint == "Start":
            axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
            projected = axis.dot(point.sub(original_endpoints[1]))
            if projected > -_MIN_WALL_LENGTH:
                return None
            return [original_endpoints[1].add(axis.multiply(projected)), original_endpoints[1]]
        elif endpoint == "End":
            axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
            projected = axis.dot(point.sub(original_endpoints[0]))
            if projected < _MIN_WALL_LENGTH:
                return None
            return [original_endpoints[0], original_endpoints[0].add(axis.multiply(projected))]

        original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
        delta = point.sub(original_midpoint)
        return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]

    def _compute_wall_edit_points_from_length(self, length):
        endpoint = self._edit_endpoint
        original_endpoints = self._edit_endpoints
        if endpoint not in ("Start", "End") or not original_endpoints:
            return None

        length = max(float(length), _MIN_WALL_LENGTH)
        axis = original_endpoints[1].sub(original_endpoints[0])
        if axis.Length < _MIN_WALL_LENGTH:
            return None
        axis.normalize()

        if endpoint == "Start":
            end = original_endpoints[1]
            return [end.sub(FreeCAD.Vector(axis).multiply(length)), end]

        start = original_endpoints[0]
        return [start, start.add(FreeCAD.Vector(axis).multiply(length))]

    def _get_preview_footprint(self, points, width=None, align=None):
        wall = self._edit_wall
        if not points or len(points) != 2:
            return None

        if width is None and wall:
            width = getattr(getattr(wall, "Width", None), "Value", 0.0) or 0.0
        if width <= 0:
            return None

        axis = points[1].sub(points[0])
        if axis.Length < _MIN_WALL_LENGTH:
            return None
        axis.normalize()
        rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
        perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))

        if align is None:
            align = getattr(wall, "Align", "Center") if wall else "Center"
        if align == "Center":
            y_min = -width / 2
            y_max = width / 2
        elif align == "Left":
            y_min = -width
            y_max = 0.0
        else:
            y_min = 0.0
            y_max = width

        return [
            points[0].add(FreeCAD.Vector(perp).multiply(y_min)),
            points[1].add(FreeCAD.Vector(perp).multiply(y_min)),
            points[1].add(FreeCAD.Vector(perp).multiply(y_max)),
            points[0].add(FreeCAD.Vector(perp).multiply(y_max)),
        ]

    def _get_readout_base_gap(self):
        from draftutils import params

        units_per_pixel = self._get_plan_view_units_per_pixel() or 0.0
        text_height_pixels = float(params.get_param_view("MarkerSize") or 0.0) * 2.0 * 96.0 / 72.0
        return max(100.0, text_height_pixels * units_per_pixel * 1.25)

    def _get_aligned_readout_offset_for_wall(self, wall):
        width = getattr(getattr(wall, "Width", None), "Value", 0.0) if wall else 0.0
        width = float(width or 0.0)
        base_gap = max(width * 0.25, self._get_readout_base_gap())
        if width <= 0:
            return base_gap
        align = getattr(wall, "Align", "Center") if wall else "Center"
        if align == "Left":
            return base_gap
        if align == "Right":
            return -(base_gap)
        return width * 0.5 + base_gap

    def _get_wall_edit_readout_offset(self, mode):
        if mode in (2, 3):
            return self._get_readout_base_gap()
        if mode != 1:
            return None
        return self._get_aligned_readout_offset_for_wall(self._edit_wall)

    def _get_opening_move_readout_offset(self, opening):
        host = next(iter(getattr(opening, "Hosts", None) or []), None) if opening else None
        return self._get_aligned_readout_offset_for_wall(host)

    def _update_wall_edit_preview_geometry(self, points):
        if not points or len(points) != 2:
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        if self._preview_line_tracker is None:
            self._preview_line_tracker = DraftTrackers.lineTracker(
                swidth=self._scaled_line_width(2), ontop=True
            )
            self._preview_line_tracker.on()
        self._preview_line_tracker.p1(points[0])
        self._preview_line_tracker.p2(points[1])

        footprint = self._get_preview_footprint(points)
        if footprint:
            if self._preview_rect_tracker is None:
                self._preview_rect_tracker = DraftTrackers.rectangleTracker()
                self._preview_rect_tracker.on()
            axis = points[1].sub(points[0]).normalize()
            rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
            perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))
            self._preview_rect_tracker.setPlane(axis, perp)
            self._preview_rect_tracker.setorigin(footprint[0])
            self._preview_rect_tracker.update(footprint[2])
            self._preview_rect_tracker.on()

        midpoint = (points[0] + points[1]) * 0.5
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)

        grip_specs = (
            (points[0], 0, None),
            (points[1], 1, None),
            (midpoint, 2, midpoint_marker),
        )
        if not self._preview_grip_trackers:
            for position, idx, marker in grip_specs:
                tracker = DraftTrackers.editTracker(
                    pos=position,
                    idx=idx,
                    marker=marker,
                    inactive=True,
                )
                tracker.on()
                self._preview_grip_trackers.append(tracker)
            return

        for tracker, (position, _idx, _marker) in zip(self._preview_grip_trackers, grip_specs):
            tracker.set(position)
            tracker.on()

    def _sync_wall_edit_preview(self, points):
        self._update_wall_edit_preview_geometry(points)
        self._sync_wall_edit_readout(points)
        self._sync_wall_hosted_opening_preview(points)

    def _is_wall_move_edit_active(self):
        return bool(
            self._edit_wall and self._edit_endpoint == "Move" and self.current_tool == "Move Wall"
        )

    def _is_wall_stretch_edit_active(self):
        return bool(
            self._edit_wall
            and self._edit_endpoint in ("Start", "End")
            and self.current_tool in ("Stretch Start", "Stretch End")
        )

    def _is_wall_readout_edit_active(self):
        return bool(self._is_wall_move_edit_active() or self._is_wall_stretch_edit_active())

    def _clear_wall_edit_preview(self):
        if self._preview_line_tracker:
            try:
                self._preview_line_tracker.finalize()
            except Exception:
                pass
        self._preview_line_tracker = None

        if self._preview_rect_tracker:
            try:
                self._preview_rect_tracker.finalize()
            except Exception:
                pass
        self._preview_rect_tracker = None

        for tracker in self._preview_grip_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._preview_grip_trackers = []
        self._clear_wall_edit_readout()
        self._clear_wall_hosted_opening_preview()

    def _get_wall_hosted_opening_preview_segments(self, wall, points):
        if not wall or not points or len(points) != 2:
            return []
        if self._edit_endpoint not in ("Start", "End"):
            return []

        layout = self._compute_wall_hosted_opening_layout(wall, points)
        if layout is None:
            return []

        segments = []
        for item in layout:
            delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
            if delta.Length < 1e-6:
                continue
            for polyline in self._get_opening_overlay_polylines(item["opening"]):
                if len(polyline) < 2:
                    continue
                translated = [FreeCAD.Vector(point).add(delta) for point in polyline]
                segments.extend(zip(translated, translated[1:]))
        return segments

    def _sync_wall_hosted_opening_preview(self, points):
        wall = self._edit_wall
        if self.current_tool not in ("Stretch Start", "Stretch End") or not wall:
            self._clear_wall_hosted_opening_preview()
            return

        segments = self._get_wall_hosted_opening_preview_segments(wall, points)
        if not segments:
            self._clear_wall_hosted_opening_preview()
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_wall_hosted_opening_preview()
            return

        color = (0.12, 0.38, 0.95)
        width = self._scaled_line_width(2)
        if len(self._wall_edit_opening_preview_trackers) != len(segments):
            self._clear_wall_hosted_opening_preview()
            for _start, _end in segments:
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                self._wall_edit_opening_preview_trackers.append(tracker)

        for tracker, (start, end) in zip(self._wall_edit_opening_preview_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_wall_hosted_opening_preview(self):
        self._finalize_trackers(self._wall_edit_opening_preview_trackers)
        self._wall_edit_opening_preview_trackers = []

    def _get_wall_edit_readout_specs(self, points):
        if not points or len(points) != 2 or not self._edit_endpoints:
            return []

        original_points = self._edit_endpoints
        if self._edit_endpoint == "Move":
            original_midpoint = (original_points[0] + original_points[1]) * 0.5
            new_midpoint = (points[0] + points[1]) * 0.5
            return [
                (2, original_midpoint, new_midpoint),
                (3, original_midpoint, new_midpoint),
            ]

        return [(1, points[0], points[1])]

    def _get_default_wall_edit_readout_mode(self, specs):
        modes = [mode for mode, _start, _end in specs]
        if not modes:
            return None
        if self._is_wall_move_edit_active():
            if self._wall_edit_active_readout_mode in modes:
                return self._wall_edit_active_readout_mode
            if 2 in modes:
                return 2
        if 1 in modes:
            return 1
        return modes[0]

    def _bind_wall_edit_readout_callbacks(self, dim, mode):
        if mode == 1:
            dim.setValueChangedCallback(self._on_wall_stretch_length_changed)
            dim.setEditingFinishedCallback(self._on_wall_stretch_length_finished)
            if hasattr(dim, "setEditingCanceledCallback"):
                dim.setEditingCanceledCallback(self._on_wall_stretch_length_canceled)
            return

        dim.setValueChangedCallback(
            lambda value, delta_mode=mode: self._on_wall_move_delta_changed(delta_mode, value)
        )
        dim.setEditingFinishedCallback(
            lambda value, delta_mode=mode: self._on_wall_move_delta_finished(delta_mode, value)
        )
        if hasattr(dim, "setEditingCanceledCallback"):
            dim.setEditingCanceledCallback(
                lambda value, delta_mode=mode: self._on_wall_move_delta_canceled(delta_mode, value)
            )

    def _update_wall_edit_readouts_in_place(self, points, active_mode=None):
        specs = {
            mode: (start, end) for mode, start, end in self._get_wall_edit_readout_specs(points)
        }
        for tracker in self._wall_edit_readout_trackers:
            mode = getattr(tracker, "mode", None)
            if mode not in specs:
                continue
            start, end = specs[mode]
            if hasattr(tracker, "updatePoints"):
                tracker.updatePoints(start, end, sync_spinbox=(mode != active_mode))
            else:
                tracker.p1(start)
                tracker.p2(end)
            tracker.on()

    def _sync_wall_edit_readout(self, points):
        self._clear_wall_edit_readout()
        if not points or len(points) != 2 or not self._edit_endpoints:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        readout_color = (0.12, 0.38, 0.95)
        dims = self._get_wall_edit_readout_specs(points)
        active_mode = self._get_default_wall_edit_readout_mode(dims)
        self._wall_edit_active_readout_mode = active_mode

        for mode, start, end in dims:
            try:
                if self._is_wall_readout_edit_active():
                    dim = DraftTrackers.editableArchDimTracker(mode=mode)
                else:
                    dim = DraftTrackers.archDimTracker(mode=mode)
            except Exception:
                continue
            try:
                if hasattr(dim, "dimnode"):
                    dim.dimnode.textColor.setValue(readout_color)
                else:
                    dim.setColor(readout_color)
            except Exception:
                pass
            offset = self._get_wall_edit_readout_offset(mode)
            if offset is not None:
                dim.offset = offset
            dim.p1(start)
            dim.p2(end)
            dim.on()
            if self._is_wall_readout_edit_active() and hasattr(dim, "setValueChangedCallback"):
                self._bind_wall_edit_readout_callbacks(dim, mode)
                if mode == active_mode:
                    self._wall_edit_active_readout_mode = mode
                    self._wall_edit_active_readout_tracker = dim
            if self._wall_edit_active_readout_tracker is None:
                self._wall_edit_active_readout_tracker = dim
            self._wall_edit_readout_trackers.append(dim)

    def _clear_wall_edit_readout(self):
        self._finalize_trackers(self._wall_edit_readout_trackers)
        self._wall_edit_readout_trackers = []
        self._wall_edit_active_readout_tracker = None
        self._wall_edit_active_readout_mode = None
        self._wall_edit_length_edit_queued = False

    def _get_wall_edit_readout_tracker(self, mode):
        for tracker in self._wall_edit_readout_trackers:
            if getattr(tracker, "mode", None) == mode:
                return tracker
        return None

    def _cycle_wall_move_readout_mode(self):
        if not self._is_wall_move_edit_active():
            return False
        modes = [
            getattr(tracker, "mode", None)
            for tracker in self._wall_edit_readout_trackers
            if getattr(tracker, "mode", None) in (2, 3)
        ]
        modes = [mode for mode in modes if mode is not None]
        if not modes:
            return False
        current_mode = (
            self._wall_edit_active_readout_mode
            if self._wall_edit_active_readout_mode in modes
            else modes[0]
        )
        next_mode = modes[(modes.index(current_mode) + 1) % len(modes)]
        self._wall_edit_active_readout_mode = next_mode
        tracker = self._get_wall_edit_readout_tracker(next_mode)
        if tracker is not None:
            self._wall_edit_active_readout_tracker = tracker
        return True

    def _start_wall_readout_edit(self, cycle=False):
        tracker = self._wall_edit_active_readout_tracker
        if not self._is_wall_readout_edit_active():
            return False
        if cycle and self._is_wall_move_edit_active():
            if (
                tracker is not None
                and hasattr(tracker, "isInEdit")
                and tracker.isInEdit()
                and hasattr(tracker, "stopEdit")
            ):
                tracker.stopEdit()
            if not self._cycle_wall_move_readout_mode():
                return False
            tracker = self._wall_edit_active_readout_tracker
        if tracker is None:
            return False
        if not hasattr(tracker, "startEdit"):
            return False
        if hasattr(tracker, "isInEdit") and tracker.isInEdit():
            if hasattr(tracker, "label"):
                tracker.label.setFocusToSpinbox()
            return True
        if self._wall_edit_length_edit_queued:
            return True
        self._wall_edit_length_edit_queued = True
        self._stop_snapper()
        try:
            from PySide import QtCore
        except ImportError:
            self._wall_edit_length_edit_queued = False
            tracker.startEdit(tracker.Distance)
            return True
        QtCore.QTimer.singleShot(
            0, lambda: self._start_wall_readout_edit_now(tracker, tracker.Distance)
        )
        return True

    def _start_wall_stretch_length_edit(self):
        return self._start_wall_readout_edit(cycle=False)

    def _start_wall_readout_edit_now(self, tracker, value):
        self._wall_edit_length_edit_queued = False
        if not self._is_wall_readout_edit_active():
            return
        if tracker is None or tracker is not self._wall_edit_active_readout_tracker:
            return
        if not hasattr(tracker, "startEdit"):
            return
        if hasattr(tracker, "isInEdit") and tracker.isInEdit():
            if hasattr(tracker, "label"):
                tracker.label.setFocusToSpinbox()
            return
        try:
            tracker.startEdit(value)
        except Exception:
            return

    def _on_wall_stretch_length_changed(self, value):
        if not self._is_wall_stretch_edit_active():
            return
        new_points = self._compute_wall_edit_points_from_length(value)
        tracker = self._wall_edit_active_readout_tracker
        if not new_points or tracker is None:
            return
        self._preview_points = new_points
        self._update_wall_edit_preview_geometry(new_points)
        self._update_wall_edit_readouts_in_place(new_points, active_mode=1)
        self._sync_wall_hosted_opening_preview(new_points)

    def _on_wall_stretch_length_finished(self, value):
        if not self._is_wall_stretch_edit_active():
            return
        wall = self._edit_wall
        endpoint = self._edit_endpoint
        proxy = getattr(wall, "Proxy", None)
        new_points = self._compute_wall_edit_points_from_length(value)
        if not new_points or not proxy:
            return
        self._preview_points = new_points
        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _on_wall_stretch_length_canceled(self, value):
        del value
        if not self._is_wall_stretch_edit_active():
            return
        self._schedule_wall_edit_readout_cancel()

    def _compute_wall_edit_points_from_move_delta(self, mode, value):
        if not self._is_wall_move_edit_active() or not self._edit_endpoints:
            return None
        original_endpoints = self._edit_endpoints
        original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
        preview_points = self._preview_points if self._preview_points else original_endpoints
        current_midpoint = (preview_points[0] + preview_points[1]) * 0.5
        target_midpoint = FreeCAD.Vector(current_midpoint)
        if mode == 2:
            target_midpoint.x = original_midpoint.x + float(value)
        elif mode == 3:
            target_midpoint.y = original_midpoint.y + float(value)
        else:
            return None
        delta = target_midpoint.sub(original_midpoint)
        return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]

    def _on_wall_move_delta_changed(self, mode, value):
        if not self._is_wall_move_edit_active():
            return
        new_points = self._compute_wall_edit_points_from_move_delta(mode, value)
        if not new_points:
            return
        self._preview_points = new_points
        self._update_wall_edit_preview_geometry(new_points)
        self._update_wall_edit_readouts_in_place(new_points, active_mode=mode)
        self._sync_wall_hosted_opening_preview(new_points)

    def _on_wall_move_delta_finished(self, mode, value):
        if not self._is_wall_move_edit_active():
            return
        wall = self._edit_wall
        endpoint = self._edit_endpoint
        proxy = getattr(wall, "Proxy", None)
        new_points = self._compute_wall_edit_points_from_move_delta(mode, value)
        if not new_points or not proxy:
            return
        self._preview_points = new_points
        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _on_wall_move_delta_canceled(self, mode, value):
        del mode, value
        if not self._is_wall_move_edit_active():
            return
        self._schedule_wall_edit_readout_cancel()

    def _schedule_wall_edit_readout_cancel(self):
        preview_points = None
        if self._preview_points:
            preview_points = [FreeCAD.Vector(point) for point in self._preview_points]
        elif self._edit_endpoints:
            preview_points = [FreeCAD.Vector(point) for point in self._edit_endpoints]
        try:
            from PySide import QtCore
        except ImportError:
            self._finish_wall_edit_readout_canceled(preview_points)
            return
        QtCore.QTimer.singleShot(
            0, lambda pts=preview_points: self._finish_wall_edit_readout_canceled(pts)
        )

    def _finish_wall_edit_readout_canceled(self, preview_points):
        if not self._is_wall_readout_edit_active():
            return
        if preview_points:
            self._sync_wall_edit_preview(preview_points)
        self._resume_wall_edit_point_pick()

    def _restore_edit_wall_visibility(self):
        wall = self._edit_wall
        if wall is not None and self._edit_wall_visibility is not None:
            try:
                wall.ViewObject.Visibility = self._edit_wall_visibility
            except Exception:
                pass
        self._edit_wall_visibility = None

    def _update_wall_edit_preview(self, point):
        new_points = self._compute_wall_edit_points(point)
        if not new_points:
            return
        self._preview_points = new_points
        self._sync_wall_edit_preview(new_points)

    def _update_wall_edit_point_pick(self, point=None, snap_info=None):
        del snap_info
        if self._wall_edit_active_readout_tracker and hasattr(
            self._wall_edit_active_readout_tracker, "isInEdit"
        ):
            if self._wall_edit_active_readout_tracker.isInEdit():
                return
        self._update_wall_edit_preview(point)

    def _cancel_wall_edit_point_pick(self):
        self.current_tool = "Select"
        self._cancel_pending_edit()
        self._refresh_task_panel_status()

    def _get_edit_node(self, mouse_pos):
        opening_handle_index = self._pick_selected_opening_handle(mouse_pos)
        if opening_handle_index is not None:
            return ("opening_handle", self.selected_opening, opening_handle_index)
        if not self._render_manager:
            return None
        try:
            from pivy import coin
        except Exception:
            return None

        ray_pick = coin.SoRayPickAction(self._render_manager.getViewportRegion())
        ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
        ray_pick.setRadius(8)
        ray_pick.setPickAll(True)
        ray_pick.apply(self._render_manager.getSceneGraph())
        picked_points = ray_pick.getPickedPointList()
        if not picked_points:
            return None

        for picked_point in picked_points:
            path = picked_point.getPath()
            point = path.getNode(path.getLength() - 2)
            if hasattr(point, "subElementName") and "EditNode" in str(
                point.subElementName.getValue()
            ):
                return ("edit_node", point)
        return None

    def _pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        opening = self.selected_opening
        if not self._is_hosted_opening_object(opening) or not self.view:
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_index = None
        best_distance_sq = None
        for idx, point, _marker in self._get_selected_opening_handle_specs(opening):
            try:
                screen_x, screen_y = self.view.getPointOnScreen(point)
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

    def _on_mouse_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return

        event = event_callback.getEvent()
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return

        if event.getState() == coin.SoMouseButtonEvent.DOWN:
            if self.current_tool != "Select":
                return
            pos = event.getPosition().getValue()
            node = self._get_edit_node((pos[0], pos[1]))
            if not node:
                if self._activate_opening_target((pos[0], pos[1]), event_callback):
                    return
                if self._activate_wall_target((pos[0], pos[1]), event_callback):
                    return
                return
            node_kind = node[0]
            if node_kind == "opening_handle":
                _kind, obj, index = node
                self.selected_opening = obj
                self.selected_wall = None
                self._clear_wall_grips()
                self._activate_opening_handle(obj, index)
            else:
                point = node[1]
                try:
                    doc = FreeCAD.getDocument(str(point.documentName.getValue()))
                    obj = doc.getObject(str(point.objectName.getValue()))
                    index = int(str(point.subElementName.getValue())[8:])
                except Exception:
                    return
                if self._is_hosted_opening_object(obj):
                    self.selected_opening = obj
                    self.selected_wall = None
                    self._clear_wall_grips()
                    self._activate_opening_handle(obj, index)
                else:
                    if obj != self.selected_wall:
                        self.selected_wall = obj
                    self._activate_wall_grip(index)
            if hasattr(event_callback, "setHandled"):
                try:
                    event_callback.setHandled()
                except Exception:
                    pass

    def _on_mouse_moved(self, event_callback):
        if self._tearing_down:
            return
        if self.current_tool != "Select":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            return
        event = event_callback.getEvent()
        pos = event.getPosition().getValue()
        self._update_hovered_plan_target((pos[0], pos[1]))
        self._refresh_plan_overlay_visuals()

    def _on_mouse_wheel(self, event_callback):
        if self._tearing_down:
            return
        event = event_callback.getEvent()
        try:
            event_type_name = str(event.getTypeId().getName())
        except Exception:
            event_type_name = ""
        if event_type_name != "SoMouseWheelEvent":
            return
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)

    def _queue_plan_overlay_visual_refresh(self, *visuals):
        if self._tearing_down:
            return
        dirty = set(visuals) if visuals else {_PLAN_VISUAL_ALL}
        self._dirty_plan_visuals.update(dirty)
        if self._overlay_refresh_queued:
            return
        try:
            from PySide import QtCore
        except ImportError:
            dirty = self._consume_dirty_plan_visuals()
            self._refresh_plan_overlay_visuals(dirty)
            return
        self._overlay_refresh_queued = True
        QtCore.QTimer.singleShot(0, self._flush_plan_overlay_visual_refresh)

    def _consume_dirty_plan_visuals(self):
        dirty = set(self._dirty_plan_visuals)
        self._dirty_plan_visuals.clear()
        return dirty or {_PLAN_VISUAL_ALL}

    def _flush_plan_overlay_visual_refresh(self):
        self._overlay_refresh_queued = False
        dirty = self._consume_dirty_plan_visuals()
        self._refresh_plan_overlay_visuals(dirty)

    def _refresh_plan_overlay_visuals(self, dirty=None):
        if self._tearing_down:
            return
        dirty = set(dirty or {_PLAN_VISUAL_ALL})
        refresh_all = _PLAN_VISUAL_ALL in dirty
        if self.current_tool == "Select":
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_OPENING in dirty:
                self._sync_hovered_opening_overlay()
            if self.selected_wall and (refresh_all or _PLAN_VISUAL_WALL_GRIPS in dirty):
                self._sync_wall_grips()
            if self.selected_opening and (refresh_all or _PLAN_VISUAL_SELECTED_OPENING in dirty):
                self._refresh_selected_opening_visuals()
            return
        if (
            self._edit_wall
            and self._preview_points
            and (refresh_all or _PLAN_VISUAL_WALL_EDIT_PREVIEW in dirty)
        ):
            self._sync_wall_edit_preview(self._preview_points)

    def _on_key_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return
        event = event_callback.getEvent()
        key = event.getKey()
        if self.current_tool == "Move Opening" and key == coin.SoKeyboardEvent.A:
            if self._cycle_opening_move_anchor():
                self._refresh_opening_move_preview_from_raw_point()
                self._refresh_task_panel_status()
            return
        if self._is_wall_move_edit_active() and key == coin.SoKeyboardEvent.TAB:
            if self._start_wall_readout_edit(cycle=True):
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self._is_wall_readout_edit_active() and key in (
            coin.SoKeyboardEvent.RETURN,
            coin.SoKeyboardEvent.ENTER,
        ):
            if self._start_wall_readout_edit():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self._is_wall_stretch_edit_active() and key == coin.SoKeyboardEvent.TAB:
            if self._start_wall_readout_edit():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if key != coin.SoKeyboardEvent.ESCAPE:
            return
        if self._edit_wall and self.current_tool != "Select":
            self._cancel_wall_edit_point_pick()
            return
        if self.current_tool == "Move Opening":
            self._cancel_opening_handle_point_pick()
            return
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()

    # Selection observer interface

    def addSelection(self, doc, obj, sub, point):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        if sub in ("EditNode0", "EditNode1", "EditNode2"):
            return
        del doc, obj, sub, point
        self._refresh_selected_wall()

    def removeSelection(self, doc, obj, sub):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc, obj, sub
        self._refresh_selected_wall()

    def setSelection(self, doc):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc
        self._refresh_selected_wall()

    def clearSelection(self, doc):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc
        self._refresh_selected_wall()

    # Document observer interface

    def _is_opening_visual_dependency(self, opening, obj):
        if not opening or not obj:
            return False
        if obj == opening:
            return True
        if obj == getattr(opening, "Base", None):
            return True
        return obj in (getattr(opening, "Hosts", None) or [])

    def _refresh_selected_opening_visuals(self):
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._request_view_redraw()

    def _refresh_opening_footprint_display(self, opening):
        if not self._is_hosted_opening_object(opening):
            return
        view_object = getattr(opening, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            return
        try:
            if hasattr(proxy, "ensureFootprintGroup"):
                proxy.ensureFootprintGroup(view_object)
            if hasattr(proxy, "updateFootprint"):
                proxy.updateFootprint()
            if hasattr(view_object, "update"):
                view_object.update()
        except Exception:
            return
        self._request_view_redraw()

    def _refresh_wall_footprint_display(self, wall):
        if not wall:
            return
        view_object = getattr(wall, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            return
        try:
            if hasattr(proxy, "ensureFootprintGroup"):
                proxy.ensureFootprintGroup(view_object)
            if hasattr(proxy, "updateFootprint"):
                proxy.updateFootprint()
            if hasattr(view_object, "update"):
                view_object.update()
        except Exception:
            return
        self._request_view_redraw()

    def _get_wall_hosted_openings(self, wall):
        if not wall or not self.doc:
            return []
        openings = []
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_hosted_opening_object(obj):
                continue
            if wall in (getattr(obj, "Hosts", None) or []):
                openings.append(obj)
        return openings

    def _refresh_wall_hosted_opening_footprints(self, wall):
        for opening in self._get_wall_hosted_openings(wall):
            self._refresh_opening_footprint_display(opening)

    def _compute_wall_hosted_opening_layout(self, wall, endpoints):
        if not wall:
            return []
        if not endpoints or len(endpoints) != 2:
            return []
        wall_origin = FreeCAD.Vector(endpoints[0])
        wall_end = FreeCAD.Vector(endpoints[1])
        wall_axis_u = wall_end.sub(wall_origin)
        wall_length = wall_axis_u.Length
        if wall_length < 1e-9:
            return None
        wall_axis_u.normalize()

        openings = []
        for opening in self._get_wall_hosted_openings(wall):
            proxy = self._get_opening_plan_proxy(
                opening, "get_plan_move_context", "move_along_host", "get_plan_center_point"
            )
            if not proxy:
                continue
            context = proxy.get_plan_move_context()
            if not context:
                continue
            current_center = proxy.get_plan_center_point()
            if current_center is None:
                continue
            current = FreeCAD.Vector(current_center)
            delta = current.sub(wall_origin)
            half_width = float(context.get("opening_half_width_u") or 0.0)
            desired_u = delta.dot(wall_axis_u)
            clearance_seed = self._wall_edit_opening_clearances.get(getattr(opening, "Name", ""))
            if clearance_seed:
                if self._edit_endpoint == "Start":
                    desired_u = max(
                        desired_u,
                        half_width + float(clearance_seed.get("left_clearance") or 0.0),
                    )
                elif self._edit_endpoint == "End":
                    desired_u = min(
                        desired_u,
                        wall_length
                        - half_width
                        - float(clearance_seed.get("right_clearance") or 0.0),
                    )
            low = half_width
            high = wall_length - half_width
            if low > high:
                midpoint = wall_length * 0.5
                low = midpoint
                high = midpoint
            item = {
                "opening": opening,
                "proxy": proxy,
                "current": current,
                "desired_u": desired_u,
                "low": low,
                "high": high,
                "half_width": half_width,
                "clearance_seed": clearance_seed,
            }
            openings.append(item)

        if not openings:
            return []

        openings.sort(key=lambda item: (item["desired_u"], getattr(item["opening"], "Name", "")))

        left = []
        for index, item in enumerate(openings):
            minimum = item["low"]
            if index > 0:
                minimum = max(
                    minimum,
                    left[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
                )
            if minimum > item["high"] + 1e-6:
                return None
            left.append(minimum)

        right = [0.0] * len(openings)
        for index in range(len(openings) - 1, -1, -1):
            maximum = openings[index]["high"]
            if index < len(openings) - 1:
                maximum = min(
                    maximum,
                    right[index + 1]
                    - openings[index]["half_width"]
                    - openings[index + 1]["half_width"],
                )
            if maximum < openings[index]["low"] - 1e-6:
                return None
            right[index] = maximum

        resolved = []
        for index, item in enumerate(openings):
            center_u = min(max(item["desired_u"], left[index]), right[index])
            if index > 0:
                center_u = max(
                    center_u,
                    resolved[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
                )
            if center_u > right[index] + 1e-6:
                return None
            resolved.append(center_u)

        layout = []
        for item, center_u in zip(openings, resolved):
            target_point = wall_origin.add(FreeCAD.Vector(wall_axis_u).multiply(center_u))
            target_point.z = item["current"].z
            layout.append(
                {
                    **item,
                    "target_center_u": center_u,
                    "target_point": target_point,
                }
            )

        return layout

    def _resolve_wall_hosted_opening_layout(self, wall):
        wall_proxy = getattr(wall, "Proxy", None)
        if not wall_proxy or not hasattr(wall_proxy, "calc_endpoints"):
            return True
        try:
            endpoints = wall_proxy.calc_endpoints(wall)
        except Exception:
            return True
        layout = self._compute_wall_hosted_opening_layout(wall, endpoints)
        if layout is None:
            return False
        for item in layout:
            if not item["proxy"].move_along_host(item["target_point"]):
                return False

        return True

    def _refresh_opening_host_footprint_displays(self, opening):
        if not self._is_hosted_opening_object(opening):
            return
        for host in getattr(opening, "Hosts", None) or []:
            self._refresh_wall_footprint_display(host)

    def _queue_recompute_opening_hosts(self, *openings):
        if (
            self._tearing_down
            or self._opening_host_recompute_queued
            or self._opening_host_recompute_running
        ):
            return
        hosts = []
        for opening in openings:
            if not self._is_hosted_opening_object(opening):
                continue
            hosts.extend(getattr(opening, "Hosts", None) or [])
        hosts = [host for host in dict.fromkeys(hosts) if host]
        if not hosts:
            return
        self._opening_host_recompute_queued = True
        self._flush_recompute_opening_hosts(hosts)

    def _flush_recompute_opening_hosts(self, hosts):
        self._opening_host_recompute_queued = False
        if self._tearing_down or self._opening_host_recompute_running or not self.doc:
            return
        self._opening_host_recompute_running = True
        try:
            for host in hosts:
                try:
                    host.touch()
                except Exception:
                    continue
            self.doc.recompute()
        finally:
            self._opening_host_recompute_running = False

    def _queue_hard_refresh_selected_opening_visuals(self):
        if self._tearing_down or self._selected_opening_hard_refresh_queued:
            return
        self._selected_opening_hard_refresh_queued = True
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._request_view_redraw()
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._flush_hard_refresh_selected_opening_visuals)
        except Exception:
            self._flush_hard_refresh_selected_opening_visuals()

    def _flush_hard_refresh_selected_opening_visuals(self):
        self._selected_opening_hard_refresh_queued = False
        if self._tearing_down or self.current_tool != "Select":
            return
        if not self._is_hosted_opening_object(self.selected_opening):
            return
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._request_view_redraw()

    def slotChangedObject(self, obj, prop):
        if self._tearing_down:
            return
        if self.current_tool != "Select":
            return
        if (
            self._is_opening_visual_dependency(self.selected_opening, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(self.selected_opening)
            self._refresh_opening_host_footprint_displays(self.selected_opening)
            self._queue_plan_overlay_visual_refresh(
                _PLAN_VISUAL_SELECTED_OPENING,
                _PLAN_VISUAL_HOVERED_OPENING,
            )
            return
        if (
            self._is_opening_visual_dependency(self.hovered_opening, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(self.hovered_opening)
            self._refresh_opening_host_footprint_displays(self.hovered_opening)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_OPENING)
            return
        if obj == self.hovered_wall and prop in _WALL_VISUAL_PROPERTIES:
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
            return
        if obj != self.selected_wall:
            return
        if prop not in _WALL_VISUAL_PROPERTIES:
            return
        self._refresh_wall_hosted_opening_footprints(obj)
        self._schedule_selected_wall_reset(prop, obj)

    def slotDeletedObject(self, obj):
        if self._tearing_down:
            return
        if obj == self.hovered_wall:
            self.hovered_wall = None
            self._clear_hovered_wall_overlay()
        if obj == self.hovered_opening:
            self.hovered_opening = None
            self._clear_hovered_opening_overlay()
        if obj == self.selected_opening:
            self.selected_opening = None
            self._refresh_selected_opening_visuals()
            return
        if obj != self.selected_wall:
            return
        self._schedule_selected_wall_reset("Deleted", obj)

    def _invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        if self.selected_opening:
            self._refresh_opening_footprint_display(self.selected_opening)
            self._refresh_opening_host_footprint_displays(self.selected_opening)
            self._queue_hard_refresh_selected_opening_visuals()
        if self.hovered_opening and self.hovered_opening != self.selected_opening:
            self._refresh_opening_footprint_display(self.hovered_opening)
            self._refresh_opening_host_footprint_displays(self.hovered_opening)
        if recompute_opening_hosts:
            self._queue_recompute_opening_hosts(self.selected_opening, self.hovered_opening)
        self._queue_plan_overlay_visual_refresh(
            _PLAN_VISUAL_HOVERED_OPENING,
            _PLAN_VISUAL_HOVERED_WALL,
            _PLAN_VISUAL_WALL_GRIPS,
        )

    def slotUndoDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)

    def slotRedoDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)

    def slotRecomputedDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals()

    def attach_task_panel(self, panel):
        if self.task_panel is panel:
            return
        self.task_panel = panel

    def detach_task_panel(self):
        panel = self.task_panel
        self.task_panel = None
        if panel:
            panel.mark_closed()
            panel.detach()
        return panel

    def on_panel_closed(self, panel):
        if self.task_panel is panel:
            self.task_panel = None
            if not self._finishing:
                self.shutdown(close_dialog=False, teardown=self._tearing_down)
            return
        panel.mark_closed()
        panel.detach()

    def _refresh_task_panel_status(self):
        if self._tearing_down:
            return
        self._update_input_hints()
        panel = self.task_panel
        if not panel:
            return
        try:
            panel.refresh_from_session()
        except (AttributeError, RuntimeError):
            self.on_panel_closed(panel)

    def _is_modal_plan_interaction_active(self):
        return bool(self._is_wall_edit_modal_active() or self.current_tool == "Move Opening")

    def _focus_plan_view(self):
        if self._tearing_down or not self.view:
            return
        try:
            widget = self.view.graphicsView()
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
            self.view.setFocus()
        except Exception:
            pass

    def _queue_focus_plan_view(self):
        try:
            from PySide import QtCore
        except Exception:
            self._focus_plan_view()
            return
        QtCore.QTimer.singleShot(0, self._focus_plan_view)

    def _clear_input_hints(self):
        hint_manager = getattr(FreeCADGui, "HintManager", None)
        if not hint_manager or not hasattr(hint_manager, "hide"):
            return
        try:
            hint_manager.hide()
        except Exception:
            pass

    def _request_view_redraw(self):
        if self._tearing_down:
            return
        if self.view and hasattr(self.view, "redraw"):
            try:
                self.view.redraw()
                return
            except Exception:
                pass

    def _make_input_hint(self, message, *sequences):
        if not hasattr(FreeCADGui, "InputHint"):
            return None
        try:
            return FreeCADGui.InputHint(message, *sequences)
        except Exception:
            return None

    def _get_input_hint_specs(self):
        ui = FreeCADGui.UserInput

        if self.current_tool == "Select":
            if self.selected_opening:
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick opening handle"),
                        ui.MouseLeft,
                    ),
                )
            if self.selected_wall:
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick wall grip"),
                        ui.MouseLeft,
                    ),
                )
            return (
                (
                    translate("BIM_PlanEdit", "%1 select wall or opening"),
                    ui.MouseLeft,
                ),
            )

        if self.current_tool.startswith("Stretch "):
            return (
                (
                    translate("BIM_PlanEdit", "%1 place endpoint"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 edit length"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            )

        return {
            "Move Opening": (
                (
                    translate("BIM_PlanEdit", "%1 place opening"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle move anchor"),
                    ui.KeyA,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Move Wall": (
                (
                    translate("BIM_PlanEdit", "%1 place wall"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 edit current offset"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle X/Y offset"),
                    ui.KeyTab,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
        }.get(self.current_tool, ())

    def _get_input_hints(self):
        return [
            self._make_input_hint(message, *sequences)
            for message, *sequences in self._get_input_hint_specs()
        ]

    def _update_input_hints(self):
        hint_manager = getattr(FreeCADGui, "HintManager", None)
        if not hint_manager or not hasattr(hint_manager, "show"):
            return
        hints = [hint for hint in self._get_input_hints() if hint is not None]
        if not hints:
            self._clear_input_hints()
            return
        try:
            hint_manager.show(*hints)
        except Exception:
            pass

    def _sync_wall_grips(self):
        self._clear_wall_grips()
        if not self.is_selected_wall_endpoint_editable():
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        wall = self.selected_wall
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "calc_endpoints"):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        if hasattr(proxy, "calc_edit_grip_positions"):
            grip_positions = proxy.calc_edit_grip_positions(wall)
        else:
            grip_positions = endpoints + [(endpoints[0] + endpoints[1]) * 0.5]
        if len(grip_positions) != 3:
            return
        grip_start, grip_end, midpoint = grip_positions
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)

        self._grip_trackers = [
            DraftTrackers.editTracker(pos=grip_start, name=wall.Name, idx=0),
            DraftTrackers.editTracker(pos=grip_end, name=wall.Name, idx=1),
            DraftTrackers.editTracker(
                pos=midpoint,
                name=wall.Name,
                idx=2,
                marker=midpoint_marker,
            ),
        ]

    def _clear_wall_grips(self):
        self._finalize_trackers(self._grip_trackers)
        self._grip_trackers = []

    def _get_wall_overlay_polylines(self, wall):
        if not wall:
            return []
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "getFootprint"):
            return []
        try:
            faces = proxy.getFootprint(wall) or []
        except Exception:
            return []

        polylines = []
        for face in faces:
            for wire in face.Wires:
                points = [vertex.Point for vertex in wire.Vertexes]
                if len(points) < 2:
                    continue
                if points[0].distanceToPoint(points[-1]) > 0.001:
                    points.append(points[0])
                polylines.append(points)
        return polylines

    def _get_opening_overlay_polylines(self, opening):
        if not opening:
            return []
        view_object = getattr(opening, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None)
        if not proxy:
            return []
        if not hasattr(proxy, "get_plan_overlay_polylines"):
            return []
        try:
            return list(proxy.get_plan_overlay_polylines() or [])
        except Exception:
            return []

    def _finalize_trackers(self, trackers):
        for tracker in trackers:
            try:
                if hasattr(tracker, "off"):
                    tracker.off()
            except Exception:
                pass
            try:
                tracker.finalize()
            except Exception:
                pass

    def _get_plan_target_at_position(self, mouse_pos):
        if not self.view or not mouse_pos:
            return (None, None)
        try:
            infos = self.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
        except (AttributeError, ReferenceError, RuntimeError):
            return (None, None)
        if not infos:
            return (None, None)

        wall_candidate = None
        for info in infos:
            if not info:
                continue
            doc_name = info.get("Document")
            obj_name = info.get("Object")
            if not doc_name or not obj_name:
                continue
            try:
                doc = FreeCAD.getDocument(str(doc_name))
            except Exception:
                doc = None
            if not doc:
                continue
            obj = doc.getObject(str(obj_name))
            if self._is_hosted_opening_object(obj):
                return ("opening", obj)
            try:
                import Draft

                if wall_candidate is None and Draft.getType(obj) == "Wall":
                    wall_candidate = obj
            except Exception:
                pass
        if wall_candidate is not None:
            return ("wall", wall_candidate)
        return (None, None)

    def _update_hovered_plan_target(self, mouse_pos):
        if self.current_tool != "Select":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            return
        target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if target_kind == "opening":
            self._set_hovered_wall(None)
            self._set_hovered_opening(target_obj)
        elif target_kind == "wall":
            self._set_hovered_opening(None)
            self._set_hovered_wall(target_obj)
        else:
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)

    def _set_hovered_wall(self, wall):
        if wall == self.selected_wall:
            wall = None
        if self.hovered_wall == wall:
            return
        self.hovered_wall = wall
        self._sync_hovered_wall_overlay()

    def _set_hovered_opening(self, opening):
        if opening == self.selected_opening:
            opening = None
        if self.hovered_opening == opening:
            return
        self.hovered_opening = opening
        self._sync_hovered_opening_overlay()

    def _select_opening_for_plan_edit(self, opening, queue_restore=False):
        if not self._is_hosted_opening_object(opening):
            return False
        self.current_tool = "Select"
        self.selected_wall = None
        self.selected_opening = opening
        self._pending_selected_opening_intent = opening if queue_restore else None
        self._clear_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()
        if queue_restore:
            self._queue_restore_selected_opening(opening)
        return True

    def _select_wall_for_plan_edit(self, wall):
        if not wall:
            return False
        try:
            import Draft

            if Draft.getType(wall) != "Wall":
                return False
        except Exception:
            return False

        self.current_tool = "Select"
        self.selected_opening = None
        self.hovered_opening = None
        self.selected_wall = wall
        self._pending_selected_opening_intent = None
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_wall_grips()
        self._refresh_task_panel_status()
        return True

    def _activate_opening_target(self, mouse_pos, event_callback=None):
        target_kind, opening = self._get_plan_target_at_position(mouse_pos)
        if target_kind != "opening":
            opening = None
        if not self._is_hosted_opening_object(opening):
            return False
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._select_opening_for_plan_edit(opening, queue_restore=True)
        if event_callback and hasattr(event_callback, "setHandled"):
            try:
                event_callback.setHandled()
            except Exception:
                pass
        return True

    def _activate_wall_target(self, mouse_pos, event_callback=None):
        target_kind, wall = self._get_plan_target_at_position(mouse_pos)
        if target_kind != "wall":
            wall = None
        if not self._select_wall_for_plan_edit(wall):
            return False
        self._set_hovered_wall(None)
        previous_ignore = self._ignore_selection_changes
        self._ignore_selection_changes = True
        try:
            try:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(wall)
            except Exception:
                pass
        finally:
            self._ignore_selection_changes = previous_ignore
        if event_callback and hasattr(event_callback, "setHandled"):
            try:
                event_callback.setHandled()
            except Exception:
                pass
        return True

    def _sync_hovered_wall_overlay(self):
        self._clear_hovered_wall_overlay()
        if self.current_tool != "Select":
            return
        if not self.hovered_wall or self.hovered_wall == self.selected_wall:
            return
        self._create_wall_overlay_trackers(
            self.hovered_wall,
            color=(0.42, 0.62, 0.9),
            width=self._scaled_line_width(2),
            tracker_store=self._wall_hover_trackers,
        )

    def _clear_hovered_wall_overlay(self):
        self._finalize_trackers(self._wall_hover_trackers)
        self._wall_hover_trackers = []

    def _create_wall_overlay_trackers(self, wall, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_wall_overlay_polylines(wall):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _sync_hovered_opening_overlay(self):
        self._clear_hovered_opening_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_hosted_opening_object(self.hovered_opening):
            return
        if self.hovered_opening == self.selected_opening:
            return
        self._create_opening_overlay_trackers(
            self.hovered_opening,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._opening_hover_trackers,
        )

    def _clear_hovered_opening_overlay(self):
        self._finalize_trackers(self._opening_hover_trackers)
        self._opening_hover_trackers = []

    def _create_opening_overlay_trackers(self, opening, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_opening_overlay_polylines(opening):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _get_opening_overlay_segments(self, opening):
        segments = []
        for polyline in self._get_opening_overlay_polylines(opening):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _sync_selected_opening_overlay(self):
        if self.current_tool != "Select" or not self._is_hosted_opening_object(
            self.selected_opening
        ):
            self._clear_selected_opening_overlay()
            return
        width = self._scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_selected_opening_overlay()
            return
        segments = self._get_opening_overlay_segments(self.selected_opening)
        color = (0.12, 0.38, 0.95)
        if len(self._opening_overlay_trackers) != len(segments):
            self._clear_selected_opening_overlay()
            for _start, _end in segments:
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                self._opening_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(self._opening_overlay_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_selected_opening_overlay(self):
        self._finalize_trackers(self._opening_overlay_trackers)
        self._opening_overlay_trackers = []

    def _get_selected_opening_edit_handles(self, opening):
        proxy = self._get_opening_view_proxy(opening, "get_plan_edit_handles")
        if not proxy:
            return []
        return list(proxy.get_plan_edit_handles() or [])

    def _get_opening_plan_proxy(self, opening, *attrs):
        if not opening:
            return None
        proxy = getattr(opening, "Proxy", None)
        if proxy and all(hasattr(proxy, attr) for attr in attrs):
            return proxy
        return self._get_opening_view_proxy(opening, *attrs)

    def _get_opening_view_proxy(self, opening, *attrs):
        if not opening:
            return None
        view_object = getattr(opening, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None)
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _project_opening_handle_point(self, opening, handle, point):
        if point is None or not opening or getattr(handle, "role", None) != "move":
            return point
        proxy = self._get_opening_plan_proxy(opening, "project_point_to_host_axis")
        if not proxy:
            return point
        return proxy.project_point_to_host_axis(point, anchor=self._edit_opening_move_anchor)

    def _get_opening_move_anchor_modes(self, opening):
        proxy = self._get_opening_plan_proxy(opening, "get_plan_move_anchor_modes")
        if not proxy:
            return _OPENING_MOVE_ANCHORS
        modes = tuple(proxy.get_plan_move_anchor_modes() or ())
        return modes or _OPENING_MOVE_ANCHORS

    def _execute_opening_handle(self, opening, handle_index, point=None):
        proxy = self._get_opening_view_proxy(opening, "execute_plan_edit_handle")
        if not proxy:
            return False
        return bool(
            proxy.execute_plan_edit_handle(
                handle_index,
                point,
                anchor=self._edit_opening_move_anchor,
            )
        )

    def _get_selected_opening_handle_specs(self, opening):
        from draftutils import params

        handle_specs = []
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        markers = {
            "move": FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
            "flip_hinge": FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
            "flip_opening": FreeCADGui.getMarkerIndex("CROSS", marker_size),
        }
        for idx, handle in enumerate(self._get_selected_opening_edit_handles(opening)):
            if handle.role not in markers or handle.point is None:
                continue
            handle_specs.append((idx, handle.point, markers[handle.role]))
        return handle_specs

    def _sync_selected_opening_handles(self):
        if self.current_tool != "Select":
            self._clear_selected_opening_handles()
            return
        if not self._is_hosted_opening_object(self.selected_opening):
            self._clear_selected_opening_handles()
            return
        self._clear_selected_opening_handles()
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        for idx, point, marker in self._get_selected_opening_handle_specs(self.selected_opening):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            self._opening_handle_trackers.append(tracker)

    def _clear_selected_opening_handles(self):
        self._finalize_trackers(self._opening_handle_trackers)
        self._opening_handle_trackers = []

    def _get_opening_move_preview_state(self, opening, point):
        if not opening or point is None:
            return None
        proxy = self._get_opening_view_proxy(opening, "get_plan_move_preview_state")
        if not proxy:
            return None
        return proxy.get_plan_move_preview_state(point, anchor=self._edit_opening_move_anchor)

    def _sync_opening_move_preview(self, opening, point):
        self._clear_opening_move_preview()
        if self.current_tool != "Move Opening" or not opening or point is None:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        preview_state = self._get_opening_move_preview_state(opening, point)
        if not preview_state:
            return

        preview_color = (0.12, 0.38, 0.95)
        for polyline in preview_state.get("polylines", []):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = DraftTrackers.lineTracker(
                    scolor=preview_color,
                    swidth=self._scaled_line_width(3),
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                self._opening_move_preview_trackers.append(tracker)

        guide_start = preview_state.get("guide_start")
        guide_end = preview_state.get("guide_end")
        if guide_start is None or guide_end is None:
            return

        guide = DraftTrackers.lineTracker(
            dotted=True,
            scolor=preview_color,
            swidth=self._scaled_line_width(1),
            ontop=True,
        )
        guide.p1(guide_start)
        guide.p2(guide_end)
        guide.on()
        self._opening_move_preview_trackers.append(guide)

        try:
            dim = DraftTrackers.archDimTracker(mode=1)
        except Exception:
            return
        dim.dimnode.textColor.setValue(preview_color)
        dim.offset = self._get_opening_move_readout_offset(opening)
        dim.p1(guide_start)
        dim.p2(guide_end)
        dim.on()
        self._opening_move_preview_trackers.append(dim)

    def _clear_opening_move_preview(self):
        self._finalize_trackers(self._opening_move_preview_trackers)
        self._opening_move_preview_trackers = []

    def _cycle_opening_move_anchor(self):
        if self.current_tool != "Move Opening":
            return False
        anchor_modes = self._get_opening_move_anchor_modes(self._edit_opening)
        try:
            current_index = anchor_modes.index(self._edit_opening_move_anchor)
        except ValueError:
            current_index = 0
        self._edit_opening_move_anchor = anchor_modes[(current_index + 1) % len(anchor_modes)]
        return True

    def _refresh_opening_move_preview_from_raw_point(self):
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        if not opening or handle_index is None:
            return
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        raw_point = self._edit_opening_move_raw_point
        if raw_point is None:
            raw_point = handle.point
        point = self._project_opening_handle_point(opening, handle, raw_point)
        self._sync_opening_move_preview(opening, point)

    def _activate_opening_handle(self, opening, handle_index):
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_opening_handle_now(opening, handle_index)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda: self._activate_opening_handle_now(opening, handle_index),
        )

    def _activate_opening_handle_now(self, opening, handle_index):
        if self._tearing_down or not opening:
            return
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        if handle.interaction == "point_pick":
            self._start_opening_handle_point_pick(opening, handle_index, handle)
        else:
            self._execute_selected_opening_handle(opening, handle_index, handle)

    def _start_opening_handle_point_pick(self, opening, handle_index, handle):
        if not opening:
            return
        self.current_tool = "Move Opening"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._edit_opening = opening
        self._edit_opening_handle_index = handle_index
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = FreeCAD.Vector(handle.point)
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._sync_opening_move_preview(opening, handle.point)
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._push_opening_move_snap_profile()
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            last=handle.point,
            callback=self._finish_opening_handle_point_pick,
            movecallback=self._update_opening_handle_point_pick,
            title=handle.title or translate("BIM_PlanEdit", "Pick new opening position"),
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _update_opening_handle_point_pick(self, point=None, snap_info=None):
        del snap_info
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        if not opening or handle_index is None:
            self._clear_opening_move_preview()
            return
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            self._clear_opening_move_preview()
            return
        handle = handles[handle_index]
        self._edit_opening_move_raw_point = FreeCAD.Vector(point) if point is not None else None
        point = self._project_opening_handle_point(opening, handle, point)
        self._sync_opening_move_preview(opening, point)

    def _finish_opening_handle_point_pick(self, point=None, obj=None):
        del obj
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._clear_opening_move_preview()
        self._edit_opening_move_raw_point = None

        if point is None or not opening:
            self.current_tool = "Select"
            self._edit_opening_move_anchor = "center"
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._refresh_task_panel_status()
            return

        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index is None or handle_index < 0 or handle_index >= len(handles):
            self.current_tool = "Select"
            self._edit_opening_move_anchor = "center"
            self._refresh_task_panel_status()
            return
        handle = handles[handle_index]
        point = self._project_opening_handle_point(opening, handle, point)

        try:
            self.doc.openTransaction(
                handle.transaction or translate("BIM_PlanEdit", "Edit Opening")
            )
            moved = self._execute_opening_handle(opening, handle_index, point)
            if not moved:
                raise RuntimeError("Unable to execute opening handle")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self._edit_opening_move_anchor = "center"
            self._restore_selected_opening(opening)
            return

        self._edit_opening_move_anchor = "center"
        self._queue_restore_selected_opening(opening)

    def _cancel_opening_handle_point_pick(self):
        opening = self._edit_opening
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._stop_snapper()
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._clear_opening_move_preview()
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self.current_tool = "Select"
        if opening:
            self.selected_opening = opening
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()

    def _restore_selected_opening(self, opening):
        self.current_tool = "Select"
        self.selected_opening = opening
        if not opening:
            self._pending_selected_opening_intent = None
        if not opening:
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._refresh_task_panel_status()
            return
        previous_ignore = self._ignore_selection_changes
        self._ignore_selection_changes = True
        try:
            try:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(opening)
            except Exception:
                pass
        finally:
            self._ignore_selection_changes = previous_ignore
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()

    def _queue_restore_selected_opening(self, opening):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_opening(opening)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_opening(opening))

    def _execute_selected_opening_handle(self, opening, handle_index, handle):
        try:
            self.doc.openTransaction(
                handle.transaction or translate("BIM_PlanEdit", "Edit Opening")
            )
            executed = self._execute_opening_handle(opening, handle_index)
            if not executed:
                raise RuntimeError("Unable to execute opening handle")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return
        self.selected_opening = opening
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()


class PlanEditDockWidget:
    """Compact modeless dock for Plan Edit mode."""

    def __init__(self, session):
        from PySide import QtCore, QtGui

        self.session = session
        self._storey_items = []
        self._closed = False
        self._params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit")
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._dock = _PlanEditDock(self)

        self.form = self._dock
        self._configure_form(QtCore, QtGui)
        container = self._build_form_contents(QtGui)
        self._install_form(container, QtCore)

    def _configure_form(self, QtCore, QtGui):
        self.form.setWindowTitle(translate("BIM_PlanEdit", "Plan Edit"))
        self.form.setObjectName("BIMPlanEditDock")
        self.form.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.form.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.form.setFeatures(
            QtGui.QDockWidget.DockWidgetClosable
            | QtGui.QDockWidget.DockWidgetMovable
            | QtGui.QDockWidget.DockWidgetFloatable
        )

    def _build_form_contents(self, QtGui):
        container = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        container.setMinimumWidth(280)
        container.setMaximumWidth(360)

        layout.addWidget(self._build_intro_label(QtGui))
        layout.addLayout(self._build_storey_row(QtGui))
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("select_button", "Select", self.on_select_clicked),
                    ("wall_button", "Wall", self.on_wall_clicked),
                    ("rect_wall_button", "Rect Wall", self.on_rect_wall_clicked),
                    ("move_button", "Move", self.on_move_clicked),
                    ("join_button", "Join", self.on_join_clicked),
                    ("reapply_button", "Reapply View", self.on_reapply_clicked),
                ),
            )
        )
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("stretch_start_button", "Stretch Start", self.on_stretch_start_clicked),
                    ("stretch_end_button", "Stretch End", self.on_stretch_end_clicked),
                ),
            )
        )

        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.exit_button = self._make_button(QtGui, "Exit Plan Edit", self.on_exit_clicked)
        self.exit_button.setMinimumHeight(32)
        layout.addWidget(self.exit_button)

        self._modal_focus_widgets = [
            self.storey_combo,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
            self.stretch_start_button,
            self.stretch_end_button,
            self.exit_button,
        ]
        self._capture_focus_policies()

        container.setLayout(layout)
        return container

    def _build_intro_label(self, QtGui):
        intro = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan authoring mode for the active storey.",
            )
        )
        intro.setWordWrap(True)
        return intro

    def _make_button(self, QtGui, label, handler):
        button = QtGui.QPushButton(translate("BIM_PlanEdit", label))
        button.clicked.connect(handler)
        return button

    def _build_storey_row(self, QtGui):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        storey_label = QtGui.QLabel(translate("BIM_PlanEdit", "Storey"))
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        row.addWidget(storey_label)
        row.addWidget(self.storey_combo, 1)
        return row

    def _build_button_row(self, QtGui, specs):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        for attr, label, handler in specs:
            button = self._make_button(QtGui, label, handler)
            setattr(self, attr, button)
            row.addWidget(button)
        return row

    def _capture_focus_policies(self):
        for widget in self._modal_focus_widgets:
            try:
                self._saved_focus_policies[widget] = widget.focusPolicy()
            except Exception:
                pass

    def _install_form(self, container, QtCore):
        self.form.setWidget(container)
        self.form.install_plan_key_filter(
            self.form,
            container,
            *self._modal_focus_widgets,
        )
        FreeCADGui.getMainWindow().addDockWidget(QtCore.Qt.RightDockWidgetArea, self.form)
        self._apply_initial_placement(QtCore)
        QtCore.QMetaObject.connectSlotsByName(container)

    def show(self):
        if self._closed or self.form is None:
            return
        self.form.show()

    def raise_(self):
        if self._closed or self.form is None:
            return
        self.form.raise_()

    def activateWindow(self):
        if self._closed or self.form is None:
            return
        self.form.activateWindow()

    def mark_closed(self):
        self._closed = True

    def save_state(self):
        if self.form is None:
            return
        try:
            geometry = self.form.geometry()
            self._params.SetBool("DockPlacementSaved", True)
            self._params.SetBool("DockFloating", self.form.isFloating())
            self._params.SetInt("DockX", geometry.x())
            self._params.SetInt("DockY", geometry.y())
            self._params.SetInt("DockWidth", geometry.width())
            self._params.SetInt("DockHeight", geometry.height())
            area = FreeCADGui.getMainWindow().dockWidgetArea(self.form)
            self._params.SetInt("DockArea", getattr(area, "value", _DEFAULT_DOCK_AREA))
        except RuntimeError:
            pass
        except Exception:
            pass

    def _apply_initial_placement(self, QtCore):
        width = max(self._params.GetInt("DockWidth", 300), 280)
        height = max(self._params.GetInt("DockHeight", 240), 220)

        if self._params.GetBool("DockPlacementSaved", False):
            area = self._params.GetInt("DockArea", _DEFAULT_DOCK_AREA)
            try:
                dock_area = getattr(QtCore.Qt, "DockWidgetArea", None)
                if dock_area:
                    dock_area = dock_area(area)
                else:
                    dock_area = QtCore.Qt.RightDockWidgetArea
                FreeCADGui.getMainWindow().addDockWidget(dock_area, self.form)
            except Exception:
                pass
            self.form.resize(width, height)
            floating = self._params.GetBool("DockFloating", True)
            self.form.setFloating(floating)
            if floating:
                self.form.move(
                    self._params.GetInt("DockX", 0),
                    self._params.GetInt("DockY", 0),
                )
            return

        main_window = FreeCADGui.getMainWindow()
        frame = main_window.frameGeometry()
        margin = 32
        self.form.resize(300, 240)
        self.form.setFloating(True)
        self.form.move(
            frame.x() + max(frame.width() - 300 - margin, margin),
            frame.y() + margin,
        )

    def detach(self):
        form = self.form
        self.form = None
        self._dock = None
        self.status = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.move_button = None
        self.join_button = None
        self.reapply_button = None
        self.stretch_start_button = None
        self.stretch_end_button = None
        self.exit_button = None
        if form:
            try:
                form.setWidget(None)
            except RuntimeError:
                pass

    def close(self):
        if self.form is None:
            return
        self.mark_closed()
        self.form.close()

    def refresh(self):
        if self._closed or self.form is None or self.storey_combo is None:
            return
        try:
            self.storey_combo.blockSignals(True)
            self.storey_combo.clear()
            self._storey_items = [None] + list(self.session.storeys)
            self.storey_combo.addItem(translate("BIM_PlanEdit", "Global XY (Z=0)"))
            for storey in self.session.storeys:
                self.storey_combo.addItem(self.session.get_storey_label(storey))

            current = self.session.active_storey
            try:
                index = self._storey_items.index(current)
            except ValueError:
                index = 0
            self.storey_combo.setCurrentIndex(index)
            self.storey_combo.blockSignals(False)
            self.refresh_from_session()
        except (AttributeError, RuntimeError):
            self.mark_closed()
            self.detach()

    def refresh_from_session(self):
        if (
            self._closed
            or self.form is None
            or self.status is None
            or self.stretch_start_button is None
            or self.stretch_end_button is None
            or self.exit_button is None
        ):
            return
        try:
            storey_text = self.session.get_storey_label(self.session.active_storey)
            tool = self.session.current_tool
            selected = self.session.selected_wall
            modal_active = self.session._is_modal_plan_interaction_active()
            if selected:
                wall_state = translate("BIM_PlanEdit", "Selected wall: {label}").format(
                    label=selected.Label
                )
                if self.session.is_selected_wall_endpoint_editable():
                    if self.session.is_selected_wall_baseless():
                        wall_state += "\n" + translate("BIM_PlanEdit", "Wall mode: baseless")
                    else:
                        wall_state += "\n" + translate(
                            "BIM_PlanEdit", "Wall mode: base-driven straight line"
                        )
                    wall_state += "\n" + translate(
                        "BIM_PlanEdit",
                        "Grip editing: drag square grips to stretch, diamond grip to move",
                    )
                else:
                    wall_state += "\n" + translate("BIM_PlanEdit", "Wall mode: base-driven")
            else:
                wall_state = translate("BIM_PlanEdit", "Selected wall: none")
            self.status.setText(
                translate(
                    "BIM_PlanEdit",
                    "Current tool: {tool}\nWorking plane: {storey}\nDisplay override: Footprint\n{wall_state}",
                ).format(tool=tool, storey=storey_text, wall_state=wall_state)
            )
            stretch_enabled = self.session.is_selected_wall_endpoint_editable()
            self._apply_modal_interaction_state(modal_active)
            if not modal_active:
                self.stretch_start_button.setEnabled(stretch_enabled)
                self.stretch_end_button.setEnabled(stretch_enabled)
        except (AttributeError, RuntimeError):
            self.mark_closed()
            self.detach()

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        for widget in self._modal_focus_widgets:
            if widget is None:
                continue
            try:
                widget.setFocusPolicy(
                    QtCore.Qt.NoFocus
                    if modal_active
                    else self._saved_focus_policies.get(widget, QtCore.Qt.StrongFocus)
                )
            except Exception:
                pass

        for widget in (
            self.storey_combo,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
            self.stretch_start_button,
            self.stretch_end_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(not modal_active)
            except Exception:
                pass

    def on_storey_changed(self, index):
        if 0 <= index < len(self._storey_items):
            self.session.set_active_storey(self._storey_items[index])

    def on_select_clicked(self):
        self.session.activate_select_tool()

    def on_wall_clicked(self):
        self.session.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.activate_rect_wall_tool()

    def on_move_clicked(self):
        self.session.activate_move_tool()

    def on_join_clicked(self):
        self.session.activate_join_tool()

    def on_reapply_clicked(self):
        self.session.apply_plan_view(fit=False)
        self.refresh_from_session()

    def on_stretch_start_clicked(self):
        self.session.stretch_selected_wall("Start")

    def on_stretch_end_clicked(self):
        self.session.stretch_selected_wall("End")

    def on_exit_clicked(self):
        self.session.shutdown()


class _PlanEditDock:
    def __new__(cls, owner):
        from PySide import QtCore, QtGui

        class _DockWidget(QtGui.QDockWidget):
            def __init__(self, dock_owner):
                super().__init__(FreeCADGui.getMainWindow())
                self._plan_owner = dock_owner
                self._key_filtered_widgets = []

            def closeEvent(self, event):
                owner = self._plan_owner
                if owner and not owner._closed:
                    if owner.session and not owner.session._tearing_down:
                        owner.save_state()
                    owner.mark_closed()
                    if owner.session:
                        owner.session.on_panel_closed(owner)
                super().closeEvent(event)
                self._plan_owner = None

            def eventFilter(self, watched, event):
                owner = self._plan_owner
                if (
                    owner
                    and owner.session
                    and event.type() == QtCore.QEvent.KeyPress
                    and owner.session._is_wall_readout_edit_active()
                ):
                    key = event.key()
                    if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                        if owner.session._start_wall_readout_edit():
                            event.accept()
                            return True
                    if key == QtCore.Qt.Key_Tab:
                        if owner.session._start_wall_readout_edit(
                            cycle=owner.session._is_wall_move_edit_active()
                        ):
                            event.accept()
                            return True
                return super().eventFilter(watched, event)

            def install_plan_key_filter(self, *widgets):
                for widget in widgets:
                    if widget is None:
                        continue
                    try:
                        widget.installEventFilter(self)
                        self._key_filtered_widgets.append(widget)
                    except Exception:
                        pass

        return _DockWidget(owner)

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

import math

import FreeCAD
import FreeCADGui
from draftguitools import gui_base

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
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
_PLAN_JOIN_TYPES = ("Miter", "Butt", "Tee")
_OPENING_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "Hosts",
    "WindowParts",
    "IfcType",
}
_WALL_VISUAL_PROPERTIES = {"Shape", "Additions", "Subtractions", "Hosts"}
_SYMBOL_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "PlanSymbols",
    "LinkedObject",
}
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
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


def _refresh_contextual_task_watchers():
    task_view = None
    try:
        task_view = FreeCADGui.Control.taskPanel()
    except Exception:
        task_view = None

    if task_view is not None:
        try:
            update = getattr(task_view, "updateWatcher", None)
            if callable(update):
                update()
                return
        except Exception:
            pass

    try:
        workbench = FreeCADGui.activeWorkbench()
    except Exception:
        workbench = None
    if not workbench or workbench.name() != "BIMWorkbench":
        return
    try:
        if hasattr(workbench, "setTaskWatchers"):
            FreeCADGui.Control.clearTaskWatcher()
            workbench.setTaskWatchers()
    except Exception:
        pass


def start_session():
    global _active_session

    if _active_session:
        return _active_session

    session = PlanEditSession()
    if session.enter():
        _active_session = session
        try:
            FreeCADGui.Control.showTaskView()
        except Exception:
            pass
        _refresh_contextual_task_watchers()
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
        self._aux_task_panels = []
        self._viewport_status_chip = None
        self.current_tool = "Select"
        self._plan_join_type = "Miter"
        self._plan_relation_status_message = None
        self.storeys = []
        self.active_storey = None
        self.selected_wall = None
        self.selected_opening = None
        self.selected_symbol = None
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self._pending_selected_plan_target = None
        self._grip_trackers = []
        self._wall_hover_trackers = []
        self._junction_node_trackers = []
        self._hovered_wall_opening_context_trackers = []
        self._opening_hover_trackers = []
        self._symbol_hover_trackers = []
        self._opening_overlay_trackers = []
        self._symbol_overlay_trackers = []
        self._selected_wall_opening_context_trackers = []
        self._opening_handle_trackers = []
        self._symbol_handle_trackers = []
        self._selected_opening_hard_refresh_queued = False
        self._opening_host_recompute_queued = False
        self._opening_host_recompute_running = False
        self._opening_move_preview_trackers = []
        self._symbol_edit_preview_trackers = []
        self._opening_move_snap_profile_pushed = False
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self._selection_observer_added = False
        self._document_observer_added = False
        self._pending_created_plan_objects = {}
        self._created_plan_objects_flush_queued = False
        self._pending_selected_wall_reset = False
        self._wall_edit_modal_active = False
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._preview_points = None
        self._preview_line_tracker = None
        self._preview_footprint_trackers = []
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
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
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
        self._plan_edit_params = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
        )
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

        panel = PlanEditControlsWidget(self)
        self.attach_task_panel(panel)
        panel.refresh()
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Entered BIM Plan Edit mode.\n"))
        return True

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return True
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
        self._clear_viewport_status_chip()
        self._clear_input_hints()
        self._cancel_embedded_tool()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
        self._clear_hovered_wall_overlay()
        self._clear_junction_node_overlays()
        self._clear_hovered_wall_opening_context_overlay()
        self._clear_wall_grips()
        self._clear_hovered_opening_overlay()
        self._clear_hovered_symbol_overlay()
        self._clear_selected_opening_overlay()
        self._clear_selected_symbol_overlay()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_opening_handles()
        self._clear_selected_symbol_handles()
        self._clear_opening_move_preview()
        self._clear_symbol_edit_preview()
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
        self._clear_viewport_status_chip()
        self.doc = None
        self.gui_doc = None
        self.view = None
        self.viewer = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self.selected_wall = None
        self.selected_opening = None
        self.selected_symbol = None
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self._pending_selected_plan_target = None
        self._edit_wall = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._junction_node_trackers = []
        self._preview_footprint_trackers = []
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
        if not (self.viewer and hasattr(self.viewer, "setNaviCubeEnabledOverride")):
            self._capture_navigation_flag(self.viewer, "isEnabledNaviCube", "navicube_enabled")
        self._capture_navigation_flag(self.view, "isCornerCrossVisible", "corner_cross_visible")

    def _apply_plan_background_override(self):
        viewer = self.viewer
        if not viewer or not hasattr(viewer, "setBackgroundAppearanceOverride"):
            return
        try:
            viewer.setBackgroundAppearanceOverride(
                "NONE",
                _PLAN_PAPER_RGB,
                _PLAN_PAPER_RGB,
                _PLAN_PAPER_RGB,
            )
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    def _clear_plan_background_override(self):
        viewer = self.viewer
        if not viewer or not hasattr(viewer, "clearBackgroundAppearanceOverride"):
            return
        try:
            viewer.clearBackgroundAppearanceOverride()
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    def _apply_plan_navigation_profile(self):
        self._capture_navigation_state()
        nav_style = self._saved_navigation_style or self._get_navigation_style()
        self._apply_navigation_flag(nav_style, "setRotationEnabled", "rotation_enabled", False)
        self._apply_navigation_flag(nav_style, "setOrientationLocked", "orientation_locked", True)
        if self.viewer and hasattr(self.viewer, "setNaviCubeEnabledOverride"):
            try:
                self.viewer.setNaviCubeEnabledOverride(False)
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        else:
            self._apply_navigation_flag(
                self.viewer, "setEnabledNaviCube", "navicube_enabled", False
            )
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
        if self.viewer and hasattr(self.viewer, "clearNaviCubeEnabledOverride"):
            try:
                self.viewer.clearNaviCubeEnabledOverride()
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        else:
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
            if self.current_tool in ("Move Symbol", "Rotate Symbol"):
                self._cancel_symbol_handle_point_pick()
            self._clear_viewport_status_chip()
            self._clear_input_hints()
            self._clear_hovered_wall_overlay()
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_opening_move_preview()
            self._clear_symbol_edit_preview()
            self._detach_selection_observer()
            self._detach_document_observer()
            self._unregister_edit_callbacks()
            if panel:
                try:
                    mark_closed = getattr(panel, "mark_closed", None)
                    if callable(mark_closed):
                        mark_closed()
                except Exception:
                    pass
                if close_dialog and not teardown:
                    try:
                        close = getattr(panel, "close", None)
                        if callable(close):
                            close()
                    except Exception:
                        pass
                else:
                    try:
                        detach = getattr(panel, "detach", None)
                        if callable(detach):
                            detach()
                    except Exception:
                        pass
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
            self._aux_task_panels = []
            _active_session = None
            self._finishing = False
            _refresh_contextual_task_watchers()
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
        self._sync_selected_wall_opening_context_overlay()
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
            self._sync_selected_wall_opening_context_overlay()
            self._refresh_task_panel_status()

    def activate_select_tool(self):
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        self._cancel_wall_edit()
        self._cancel_join_tool()

    def activate_wall_tool(self):
        from bimcommands import BimWall

        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self.selected_wall = None
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        try:
            FreeCADGui.Selection.clearSelection()
        except (ReferenceError, RuntimeError):
            pass
        self._start_embedded_tool("Wall", BimWall.Arch_Wall(), host_class=_PlanEditWallHost)

    def activate_rect_wall_tool(self):
        self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self.selected_wall = None
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
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
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        self._cancel_rect_wall_tool(refresh=False)

        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._set_hovered_opening(None)
        self._set_hovered_wall(None)

        wall = self.selected_wall
        if not self._is_plan_selectable_wall(wall):
            selection = []
            try:
                selection = FreeCADGui.Selection.getSelection()
            except (ReferenceError, RuntimeError):
                selection = []
            if len(selection) == 1 and self._is_plan_selectable_wall(selection[0]):
                wall = selection[0]

        if not self._is_plan_selectable_wall(wall):
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Select a wall before using Join.\n")
            )
            return

        self.current_tool = "Join"
        self._set_selected_plan_target("wall", wall)
        self._restore_gui_selection(wall)
        self._refresh_task_panel_status()

    def get_plan_join_type(self):
        return self._plan_join_type

    def get_plan_join_types(self):
        return _PLAN_JOIN_TYPES

    def _normalize_plan_join_type(self, join_type):
        if join_type in _PLAN_JOIN_TYPES:
            return join_type
        try:
            join_type = str(join_type)
        except Exception:
            return "Miter"
        if join_type in _PLAN_JOIN_TYPES:
            return join_type
        return "Miter"

    def get_plan_join_type_label(self, join_type=None):
        join_type = self._normalize_plan_join_type(join_type or self._plan_join_type)
        return {
            "Miter": translate("BIM_PlanEdit", "Miter"),
            "Butt": translate("BIM_PlanEdit", "Butt"),
            "Tee": translate("BIM_PlanEdit", "Tee"),
        }[join_type]

    def _get_plan_join_type_phrase(self, join_type=None):
        join_type = self._normalize_plan_join_type(join_type or self._plan_join_type)
        return {
            "Miter": translate("BIM_PlanEdit", "miter"),
            "Butt": translate("BIM_PlanEdit", "butt"),
            "Tee": translate("BIM_PlanEdit", "tee"),
        }[join_type]

    def _get_plan_join_action_text(self, join_type=None):
        return translate(
            "BIM_PlanEdit", "Click another wall to create a {joint_type} joint"
        ).format(joint_type=self._get_plan_join_type_phrase(join_type))

    def set_plan_join_type(self, join_type, refresh=True):
        join_type = self._normalize_plan_join_type(join_type)
        if self._plan_join_type == join_type:
            if refresh:
                self._refresh_task_panel_status()
            return False
        self._plan_join_type = join_type
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _cycle_plan_join_type(self):
        try:
            current_index = _PLAN_JOIN_TYPES.index(self._plan_join_type)
        except ValueError:
            current_index = 0
        next_join_type = _PLAN_JOIN_TYPES[(current_index + 1) % len(_PLAN_JOIN_TYPES)]
        self.set_plan_join_type(next_join_type)
        return True

    def _get_plan_join_command(self):
        from bimcommands.BimJoin import BIM_Join_Butt, BIM_Join_Miter, BIM_Join_Tee

        return {
            "Miter": BIM_Join_Miter,
            "Butt": BIM_Join_Butt,
            "Tee": BIM_Join_Tee,
        }.get(self._normalize_plan_join_type(self._plan_join_type), BIM_Join_Miter)()

    def _get_plan_join_candidate_wall(self):
        if self.current_tool != "Join":
            return None
        wall = self.hovered_wall
        if not self._is_plan_selectable_wall(wall) or wall == self.selected_wall:
            return None
        return wall

    def _get_plan_candidate_joint(self, target_wall=None):
        import ArchWallJoinUtils

        source_wall = self.selected_wall
        target_wall = target_wall or self._get_plan_join_candidate_wall()
        if not self._is_plan_selectable_wall(source_wall):
            return None
        if not self._is_plan_selectable_wall(target_wall):
            return None
        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return None
        return ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)

    def _get_plan_join_candidate_state(self):
        target_wall = self._get_plan_join_candidate_wall()
        if not target_wall:
            return None, None, ""

        joint = self._get_plan_candidate_joint(target_wall)
        if not joint:
            return (
                target_wall,
                None,
                translate("BIM_PlanEdit", "Candidate wall: {label}").format(
                    label=target_wall.Label
                ),
            )

        summary = translate("BIM_PlanEdit", "Existing joint with {label}: {joint_type}").format(
            label=target_wall.Label,
            joint_type=self.get_plan_join_type_label(getattr(joint, "JointType", "Miter")),
        )
        status = getattr(joint, "Status", "")
        if status not in ("", "OK"):
            summary = translate("BIM_PlanEdit", "{summary} ({status})").format(
                summary=summary,
                status=status,
            )
        return target_wall, joint, summary

    def _get_plan_join_mode_action_text(self, target_wall=None, joint=None):
        target_wall = target_wall or self._get_plan_join_candidate_wall()
        joint = joint or self._get_plan_candidate_joint(target_wall)
        if joint:
            current_type = self._normalize_plan_join_type(getattr(joint, "JointType", "Miter"))
            if current_type == self._plan_join_type:
                return translate(
                    "BIM_PlanEdit",
                    "Press Delete to unjoin this pair, or Tab to choose a different joint type",
                )
            return translate(
                "BIM_PlanEdit",
                "Click wall to change it to a {joint_type} joint",
            ).format(joint_type=self._get_plan_join_type_phrase())
        if target_wall:
            return self._get_plan_join_action_text()
        return translate(
            "BIM_PlanEdit",
            "Hover another wall, then click to create a {joint_type} joint",
        ).format(joint_type=self._get_plan_join_type_phrase())

    def _unjoin_plan_wall_pair(self, source_wall, target_wall):
        import ArchWallJoinUtils

        if not self._is_plan_selectable_wall(source_wall):
            return False
        if not self._is_plan_selectable_wall(target_wall):
            return False

        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return False
        joint = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
        if not joint:
            return False

        doc.openTransaction(translate("BIM_PlanEdit", "Unjoin walls"))
        try:
            doc.removeObject(joint.Name)
            doc.commitTransaction()
            doc.recompute()
        except Exception:
            try:
                doc.abortTransaction()
            except Exception:
                pass
            return False

        self._clear_plan_relation_status()
        self._refresh_task_panel_status()
        return True

    def _unjoin_current_plan_wall_pair(self):
        source_wall = self.selected_wall
        target_wall = self._get_plan_join_candidate_wall()
        if not self._unjoin_plan_wall_pair(source_wall, target_wall):
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Hover a joined wall pair before using Unjoin.\n")
            )
            return False
        return True

    @staticmethod
    def _iter_unique_wall_sets(source_wall, target_wall, extra_walls):
        import itertools

        base = [source_wall, target_wall]
        extras = sorted(
            [wall for wall in extra_walls if wall not in base],
            key=lambda wall: getattr(wall, "Name", ""),
        )
        seen = set()
        for size in range(len(extras), 0, -1):
            for combo in itertools.combinations(extras, size):
                walls = base + list(combo)
                signature = tuple(sorted(getattr(wall, "Name", "") for wall in walls if wall))
                if signature in seen:
                    continue
                seen.add(signature)
                yield walls

    def _find_plan_junction_promotion(self, source_wall, target_wall):
        import ArchWallJoinUtils
        import ArchWallJunctionUtils

        if not self._is_plan_selectable_wall(source_wall):
            return None
        if not self._is_plan_selectable_wall(target_wall):
            return None

        candidate_walls = {
            getattr(source_wall, "Name", ""): source_wall,
            getattr(target_wall, "Name", ""): target_wall,
        }
        candidate_relations = []
        seen_relations = set()
        for wall in (source_wall, target_wall):
            for relation in ArchWallJoinUtils.iter_wall_relations(wall):
                relation_name = getattr(relation, "Name", None)
                if not relation_name or relation_name in seen_relations:
                    continue
                seen_relations.add(relation_name)
                candidate_relations.append(relation)
                for linked_wall in ArchWallJoinUtils.get_relation_walls(relation):
                    if self._is_plan_selectable_wall(linked_wall):
                        candidate_walls[getattr(linked_wall, "Name", "")] = linked_wall

        if len(candidate_walls) < 3:
            return None

        extra_walls = [
            wall
            for name, wall in candidate_walls.items()
            if wall not in (source_wall, target_wall) and name
        ]
        for walls in self._iter_unique_wall_sets(source_wall, target_wall, extra_walls):
            solution = ArchWallJunctionUtils.solve_wall_junction_inputs(walls)
            if solution.is_ok():
                return walls, solution, candidate_relations
        return None

    @staticmethod
    def _find_reusable_plan_junction(candidate_relations, walls):
        wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
        best_relation = None
        best_overlap = 0
        for relation in candidate_relations:
            if getattr(getattr(relation, "Proxy", None), "Type", None) != "WallJunction":
                continue
            relation_names = {
                getattr(wall, "Name", "")
                for wall in list(getattr(relation, "Walls", []) or [])
                if wall
            }
            overlap = len(wall_names.intersection(relation_names))
            if overlap > best_overlap:
                best_relation = relation
                best_overlap = overlap
        return best_relation if best_overlap >= 2 else None

    def _apply_plan_wall_junction_promotion(self, doc, source_wall, target_wall):
        import Arch
        import ArchWallJoinUtils

        promotion = self._find_plan_junction_promotion(source_wall, target_wall)
        if not promotion:
            return None

        walls, solution, candidate_relations = promotion
        wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
        junction = self._find_reusable_plan_junction(candidate_relations, walls)

        for relation in candidate_relations:
            if not ArchWallJoinUtils.is_wall_joint(relation):
                continue
            relation_walls = {
                getattr(wall, "Name", "")
                for wall in ArchWallJoinUtils.get_relation_walls(relation)
                if wall
            }
            if relation_walls and relation_walls.issubset(wall_names):
                doc.removeObject(relation.Name)

        if junction:
            junction.Walls = list(walls)
            junction.CarrierMode = "Explicit"
            junction.CarrierWall = solution.carrier_wall
            junction.Enabled = True
            return junction

        return Arch.makeWallJunction(list(walls), carrier_wall=solution.carrier_wall)

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
                self._apply_plan_background_override()
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

        # Keep the live view decorations and navigation model constrained every
        # time the session reapplies the plan view, not just in helper tests.
        self._apply_plan_navigation_profile()

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
                self._clear_plan_background_override()
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

        # Restore the viewer/navigation decorations after the plan override is
        # fully unwound so the normal 3D state comes back coherently.
        self._restore_navigation_state()

    def _capture_state(self):
        import WorkingPlane

        if self.view and hasattr(self.view, "getCamera"):
            self._saved_camera = self.view.getCamera()
        if self.view and hasattr(self.view, "getCameraType"):
            self._saved_camera_type = self.view.getCameraType()

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
        self._refresh_plan_object_footprint_display(obj)
        self._request_view_redraw()

    def _get_plan_semantic_object(self, obj):
        current = obj
        seen = set()
        while current:
            name = getattr(current, "Name", None)
            if name in seen:
                break
            if name:
                seen.add(name)
            if getattr(current, "TypeId", "") != "App::Link":
                break
            linked = getattr(current, "LinkedObject", None)
            if linked is None and hasattr(current, "getLinkedObject"):
                try:
                    linked = current.getLinkedObject(True)
                except TypeError:
                    try:
                        linked = current.getLinkedObject()
                    except Exception:
                        linked = None
                except Exception:
                    linked = None
            if not linked or linked == current:
                break
            current = linked
        return current or obj

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
        obj = self._get_plan_semantic_object(obj)
        if getattr(obj, "IfcType", "") == "Slab":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
        except Exception:
            return False

    def _is_plan_equipment_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            if Draft.getType(obj) == "Equipment":
                return True
        except Exception:
            pass
        proxy = getattr(obj, "Proxy", None)
        return getattr(proxy, "Type", None) == "Equipment"

    def _is_plan_symbol_instance(self, obj):
        if not obj:
            return False
        if getattr(obj, "TypeId", "") != "App::Link":
            return False
        if self._is_hidden_library_definition_object(obj):
            return False
        return self._is_plan_equipment_object(obj)

    def _is_plan_context_only_object(self, obj):
        if not obj:
            return False
        if self._is_plan_symbol_instance(obj):
            return False
        return (
            self._is_plan_container_object(obj)
            or self._is_plan_background_object(obj)
            or self._is_plan_equipment_object(obj)
        )

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
        if self._is_plan_symbol_instance(obj):
            return True
        if self._is_plan_context_only_object(obj):
            return True
        semantic_obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            obj_type = Draft.getType(semantic_obj)
        except Exception:
            obj_type = ""

        if obj_type in {"Wall", "Window", "Space", "Axis", "AxisSystem"}:
            return True

        if getattr(semantic_obj, "IfcType", "") in {
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
        semantic_obj = self._get_plan_semantic_object(obj)
        if not getattr(semantic_obj, "Hosts", None):
            return False

        if getattr(semantic_obj, "IfcType", "") in {"Window", "Door"}:
            return True

        try:
            import Draft

            return Draft.getType(semantic_obj) == "Window"
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

    def _apply_context_object_selectability(self, obj, view_object):
        if not view_object or not hasattr(view_object, "Selectable"):
            return
        if not self._is_plan_context_only_object(obj):
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
                self._apply_context_object_selectability(obj, view_object)
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
                self._apply_context_object_selectability(obj, view_object)
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
                self._apply_context_object_selectability(obj, view_object)
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

    def _is_plan_selectable_wall(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            return Draft.getType(obj) == "Wall"
        except Exception:
            return False

    def _get_plan_target_kind_for_object(self, obj):
        if self._is_hosted_opening_object(obj):
            return "opening"
        if self._is_plan_symbol_instance(obj):
            return "symbol"
        if self._is_plan_selectable_wall(obj):
            return "wall"
        return None

    def _has_direct_true_property(self, obj, prop_name):
        if not obj:
            return False
        try:
            if prop_name not in (getattr(obj, "PropertiesList", []) or []):
                return False
            return bool(getattr(obj, prop_name))
        except Exception:
            return False

    def _is_hidden_library_definition_object(self, obj):
        if not obj:
            return False
        if self._has_direct_true_property(obj, "IsLibraryDefinition"):
            return True
        for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
            if self._has_direct_true_property(parent, "IsLibraryDefinition"):
                return True
        return False

    def _should_register_created_plan_object(self, obj):
        if self._tearing_down or not obj or not self.doc:
            return False
        try:
            if getattr(obj, "Document", None) != self.doc:
                return False
            if self._is_hidden_library_definition_object(obj):
                return False
            return self._is_supported_plan_object(obj)
        except ReferenceError:
            return False

    def _queue_created_plan_object(self, obj):
        if not obj or not getattr(obj, "Name", None):
            return
        self._pending_created_plan_objects[obj.Name] = obj
        if self._created_plan_objects_flush_queued:
            return
        self._created_plan_objects_flush_queued = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._flush_created_plan_objects)
        except Exception:
            self._flush_created_plan_objects()

    def _flush_created_plan_objects(self):
        self._created_plan_objects_flush_queued = False
        pending = list(self._pending_created_plan_objects.values())
        self._pending_created_plan_objects.clear()
        for obj in pending:
            if not self._should_register_created_plan_object(obj):
                continue
            self._register_plan_object(obj)

    def _set_pending_selected_plan_target(self, kind=None, obj=None):
        if kind == "opening" and self._is_hosted_opening_object(obj):
            self._pending_selected_plan_target = ("opening", obj)
            return
        if kind == "symbol" and self._is_plan_symbol_instance(obj):
            self._pending_selected_plan_target = ("symbol", obj)
            return
        if kind == "wall" and self._is_plan_selectable_wall(obj):
            self._pending_selected_plan_target = ("wall", obj)
            return
        self._pending_selected_plan_target = None

    def _consume_pending_selected_plan_target(self):
        pending_target = self._pending_selected_plan_target
        self._pending_selected_plan_target = None
        if not pending_target:
            return (None, None)
        kind, obj = pending_target
        if kind == "opening" and self._is_hosted_opening_object(obj):
            return (kind, obj)
        if kind == "symbol" and self._is_plan_symbol_instance(obj):
            return (kind, obj)
        if kind == "wall" and self._is_plan_selectable_wall(obj):
            return (kind, obj)
        return (None, None)

    def _clear_plan_relation_status(self):
        self._plan_relation_status_message = None

    def _collect_wall_relation_warnings(self, wall):
        if not wall:
            return []
        import ArchWallJoinUtils

        warnings = []
        seen = set()
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            if not relation or relation.Name in seen or not getattr(relation, "Enabled", True):
                continue
            seen.add(relation.Name)
            status = getattr(relation, "Status", "")
            if status in ("", "OK", "Disabled"):
                continue
            label = getattr(relation, "Label", getattr(relation, "Name", ""))
            detail = str(getattr(relation, "StatusMessage", "") or status).strip()
            warnings.append((relation, label, status, detail))
        return warnings

    def _update_wall_relation_status(self, wall):
        warnings = self._collect_wall_relation_warnings(wall)
        if not warnings:
            self._clear_plan_relation_status()
            return

        if len(warnings) == 1:
            _relation, label, status, _detail = warnings[0]
            summary = translate("BIM_PlanEdit", "Relation warning: {label} ({status})").format(
                label=label,
                status=status,
            )
        else:
            summary = translate(
                "BIM_PlanEdit", "Relation warnings: {count} relations need attention"
            ).format(count=len(warnings))

        self._plan_relation_status_message = summary
        FreeCAD.Console.PrintWarning(summary + "\n")
        for _relation, label, _status, detail in warnings:
            FreeCAD.Console.PrintWarning(f"  - {label}: {detail}\n")

    def _set_selected_plan_target(self, kind=None, obj=None, pending_restore=False):
        if kind == "opening" and self._is_hosted_opening_object(obj):
            self.selected_wall = None
            self.selected_opening = obj
            self.selected_symbol = None
        elif kind == "symbol" and self._is_plan_symbol_instance(obj):
            self.selected_wall = None
            self.selected_opening = None
            self.selected_symbol = obj
        elif kind == "wall" and self._is_plan_selectable_wall(obj):
            self.selected_wall = obj
            self.selected_opening = None
            self.selected_symbol = None
        else:
            self.selected_wall = None
            self.selected_opening = None
            self.selected_symbol = None
            kind = None
            obj = None
        self._clear_plan_relation_status()
        if pending_restore:
            self._set_pending_selected_plan_target(kind, obj)
        else:
            self._set_pending_selected_plan_target()
        if not self._tearing_down:
            self._sync_junction_node_overlays()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            self._sync_hovered_symbol_overlay()

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

    def _refresh_selected_plan_target(self):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return

        previous_wall = self.selected_wall
        previous_opening = self.selected_opening
        previous_symbol = self.selected_symbol
        if self._is_wall_edit_modal_active():
            self.selected_wall = self._edit_wall
            self.selected_opening = None
            self.selected_symbol = None
            if previous_wall != self.selected_wall:
                self._sync_wall_grips()
            self._sync_hovered_wall_overlay()
            if previous_opening is not None or self.current_tool != "Select":
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if previous_symbol is not None or self.current_tool != "Select":
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_opening_overlay()
            self._refresh_task_panel_status()
            return
        if self.current_tool == "Join":
            self.selected_opening = None
            self.selected_symbol = None
            if not self._is_plan_selectable_wall(self.selected_wall):
                self.current_tool = "Select"
                self.selected_wall = None
            self._clear_wall_grips()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            if previous_opening is not None:
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if previous_symbol is not None:
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_opening_overlay()
            self._refresh_task_panel_status()
            return
        self.selected_wall = None
        self.selected_opening = None
        self.selected_symbol = None
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            return
        if self.current_tool == "Select" and selection:
            selected_targets = []
            for selected in selection:
                target_kind = self._get_plan_target_kind_for_object(selected)
                if target_kind:
                    selected_targets.append((target_kind, selected))

            matched_target = None
            pending_kind, pending_target = self._pending_selected_plan_target or (None, None)
            if pending_target is not None:
                for target_kind, selected in selected_targets:
                    if selected == pending_target and target_kind == pending_kind:
                        matched_target = (target_kind, selected)
                        break
            if matched_target is None:
                for preferred_kind in ("opening", "symbol", "wall"):
                    matched_target = next(
                        (
                            (target_kind, selected)
                            for target_kind, selected in selected_targets
                            if target_kind == preferred_kind
                        ),
                        None,
                    )
                    if matched_target is not None:
                        break

            if matched_target is not None:
                target_kind, selected = matched_target
                if target_kind == "wall":
                    self.selected_wall = selected
                elif target_kind == "opening":
                    self.selected_opening = selected
                elif target_kind == "symbol":
                    self.selected_symbol = selected
                if len(selection) == 1:
                    self._set_pending_selected_plan_target()
                else:
                    self._set_pending_selected_plan_target(target_kind, selected)
            else:
                self._set_pending_selected_plan_target()
        elif self.current_tool == "Select" and not selection:
            pending_kind, pending_target = self._consume_pending_selected_plan_target()
            if pending_kind == "opening":
                self.selected_opening = pending_target
            elif pending_kind == "symbol":
                self.selected_symbol = pending_target
            elif pending_kind == "wall":
                self.selected_wall = pending_target
        else:
            self._set_pending_selected_plan_target()
        if previous_wall != self.selected_wall:
            self._sync_wall_grips()
        self._sync_selected_wall_opening_context_overlay()
        self._sync_hovered_wall_overlay()
        self._sync_hovered_wall_opening_context_overlay()
        if previous_opening != self.selected_opening or self.current_tool != "Select":
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
        if previous_symbol != self.selected_symbol or self.current_tool != "Select":
            self._sync_selected_symbol_overlay()
            self._sync_selected_symbol_handles()
        self._sync_hovered_symbol_overlay()
        self._sync_hovered_opening_overlay()
        self._refresh_task_panel_status()

    def _refresh_selected_wall(self):
        self._refresh_selected_plan_target()

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
            self._clear_plan_relation_status()
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
        self._clear_plan_relation_status()
        self._sync_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()

    def _cancel_join_tool(self, refresh=True):
        if self.current_tool != "Join":
            return False
        selected_wall = (
            self.selected_wall if self._is_plan_selectable_wall(self.selected_wall) else None
        )
        self.current_tool = "Select"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        if selected_wall:
            self._select_wall_for_plan_edit(selected_wall)
            return True
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _restore_gui_selection(self, obj):
        if not obj:
            return
        previous_ignore = self._ignore_selection_changes
        self._ignore_selection_changes = True
        try:
            try:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(obj)
            except Exception:
                pass
        finally:
            self._ignore_selection_changes = previous_ignore

    def _apply_plan_wall_join(self, source_wall, target_wall):
        if not self._is_plan_selectable_wall(source_wall):
            return False
        if not self._is_plan_selectable_wall(target_wall):
            return False
        if source_wall == target_wall:
            return False

        import Arch
        import ArchWallJoinUtils

        join_command = self._get_plan_join_command()
        created = False
        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return False

        doc.openTransaction(translate("BIM_PlanEdit", "Join walls"))
        try:
            relation = self._apply_plan_wall_junction_promotion(doc, source_wall, target_wall)
            if relation is None:
                relation = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
                if not relation:
                    relation = Arch.makeWallJoint(source_wall, target_wall, join_command.JointType)
                    created = True
                if not relation:
                    raise RuntimeError("Unable to create wall joint")
                if not join_command._configure_joint(relation, source_wall, target_wall):
                    raise RuntimeError("Unable to configure wall joint")
            doc.commitTransaction()
            doc.recompute()
        except Exception:
            try:
                doc.abortTransaction()
            except Exception:
                pass
            return False

        if getattr(getattr(relation, "Proxy", None), "Type", None) == "WallJoint":
            if created or getattr(relation, "Status", "OK") != "OK":
                join_command._report_joint_status(relation)
        elif getattr(relation, "Status", "OK") != "OK":
            message = str(getattr(relation, "StatusMessage", "") or getattr(relation, "Status", ""))
            if message:
                FreeCAD.Console.PrintWarning(message + "\n")
        self.current_tool = "Select"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._select_wall_for_plan_edit(source_wall)
        self._restore_gui_selection(source_wall)
        return True

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
        self._sync_selected_wall_opening_context_overlay()
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

        self._clear_plan_relation_status()
        self.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_selected_plan_target("wall", wall)
        self._clear_selected_wall_opening_context_overlay()
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
        self._set_selected_plan_target("wall", wall, pending_restore=True)
        self._update_wall_relation_status(wall)
        self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _start_wall_grip_edit(self, grip_index):
        if grip_index not in (0, 1, 2) or not self.is_selected_wall_endpoint_editable():
            return
        self._start_wall_edit({0: "Start", 1: "End", 2: "Move"}[grip_index])

    def _activate_wall_grip(self, grip_index, wall=None):
        if wall is None:
            wall = self.selected_wall
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_wall_grip_now(grip_index, wall)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda wall=wall, grip_index=grip_index: self._activate_wall_grip_now(grip_index, wall),
        )

    def _activate_wall_grip_now(self, grip_index, wall=None):
        if self._tearing_down or self.current_tool != "Select" or not wall:
            return
        self._set_selected_plan_target("wall", wall)
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

    def _make_preview_wall_adapter(self, wall, endpoints):
        if not wall or not endpoints or len(endpoints) != 2:
            return None

        real_proxy = getattr(wall, "Proxy", None)
        preview_points = [FreeCAD.Vector(point) for point in endpoints]

        class _PreviewWallProxy:
            def __init__(self, wrapped_proxy):
                self._wrapped_proxy = wrapped_proxy
                self.Type = getattr(wrapped_proxy, "Type", None)

            def calc_endpoints(self, _obj):
                return [FreeCAD.Vector(point) for point in preview_points]

            def get_width(self, _obj, widths=False):
                if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_width"):
                    return self._wrapped_proxy.get_width(wall, widths=widths)
                width = getattr(getattr(wall, "Width", None), "Value", getattr(wall, "Width", None))
                return width

            def get_layers(self, _obj):
                if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_layers"):
                    return self._wrapped_proxy.get_layers(wall)
                return None

        class _PreviewWall:
            def __init__(self):
                self._wall = wall
                self.Proxy = _PreviewWallProxy(real_proxy)
                self.Label = getattr(wall, "Label", getattr(wall, "Name", ""))
                self.Name = getattr(wall, "Name", "")
                self.Document = getattr(wall, "Document", None)
                self.InList = getattr(wall, "InList", [])
                # Force solver helpers to read the transient preview endpoints
                # instead of the original baseline object.
                self.Base = None
                self.Width = getattr(wall, "Width", None)
                self.Align = getattr(wall, "Align", "Center")

            def __getattr__(self, attr):
                return getattr(self._wall, attr)

        return _PreviewWall()

    def _solve_preview_wall_relation(self, relation, wall, preview_wall):
        if not relation or not wall or not preview_wall:
            return None

        import ArchWallJoinUtils
        import ArchWallJunctionUtils

        if ArchWallJoinUtils.is_wall_joint(relation):
            wall_a = preview_wall if getattr(relation, "WallA", None) == wall else relation.WallA
            wall_b = preview_wall if getattr(relation, "WallB", None) == wall else relation.WallB
            return ArchWallJoinUtils.solve_wall_joint_inputs(
                wall_a,
                wall_b,
                getattr(relation, "JointType", "Miter"),
                getattr(relation, "ButtTrimmed", "Auto"),
                getattr(relation, "TeeStem", "Auto"),
                getattr(relation, "EndA", "Auto"),
                getattr(relation, "EndB", "Auto"),
            )

        if ArchWallJoinUtils.is_wall_junction(relation):
            walls = [
                preview_wall if linked_wall == wall else linked_wall
                for linked_wall in list(getattr(relation, "Walls", []) or [])
            ]
            carrier_wall = (
                preview_wall
                if getattr(relation, "CarrierWall", None) == wall
                else relation.CarrierWall
            )
            return ArchWallJunctionUtils.solve_wall_junction_inputs(
                walls,
                getattr(relation, "CarrierMode", "Auto"),
                carrier_wall,
            )

        return None

    def _collect_preview_wall_relation_data(self, wall, points):
        if not wall or not points or len(points) != 2:
            return {"Start": None, "End": None, "Conflicts": set()}, []

        preview_wall = self._make_preview_wall_adapter(wall, points)
        if not preview_wall:
            return {"Start": None, "End": None, "Conflicts": set()}, []

        import ArchWallJoinUtils

        claims = {"Start": [], "End": []}
        warnings = []
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            solution = self._solve_preview_wall_relation(relation, wall, preview_wall)
            if not solution:
                continue
            if not solution.is_ok():
                warnings.append(
                    (
                        getattr(relation, "Label", getattr(relation, "Name", "")),
                        getattr(solution, "status", "SolverError"),
                        str(getattr(solution, "status_message", "") or "").strip(),
                    )
                )
                continue
            end_name, plane = ArchWallJoinUtils.get_trim_for_wall(solution, preview_wall)
            if end_name and plane:
                claims[end_name].append((relation, plane))

        result = {"Start": None, "End": None, "Conflicts": set()}
        for end_name, entries in claims.items():
            if len(entries) == 1:
                result[end_name] = entries[0][1]
            elif len(entries) > 1:
                result["Conflicts"].add(end_name)
                warnings.append(
                    (
                        translate("BIM_PlanEdit", "{end_name} preview trims").format(
                            end_name=end_name
                        ),
                        "Conflict",
                        translate(
                            "BIM_PlanEdit",
                            "Multiple wall relations trim the same wall end in preview.",
                        ),
                    )
                )
        return result, warnings

    @staticmethod
    def _clip_preview_polygon_to_plane(polygon, plane_placement, ref_point, tol=1e-7):
        if not polygon or len(polygon) < 3 or plane_placement is None or ref_point is None:
            return polygon

        plane_origin = FreeCAD.Vector(plane_placement.Base)
        plane_normal = plane_placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        if plane_normal.Length <= tol:
            return polygon
        plane_normal.normalize()

        ref_distance = plane_normal.dot(FreeCAD.Vector(ref_point).sub(plane_origin))

        def signed_distance(point):
            return plane_normal.dot(FreeCAD.Vector(point).sub(plane_origin))

        def is_inside(distance):
            if ref_distance >= 0:
                return distance >= -tol
            return distance <= tol

        def intersect(prev_point, curr_point, prev_distance, curr_distance):
            denom = prev_distance - curr_distance
            if abs(denom) <= tol:
                return FreeCAD.Vector(curr_point)
            factor = prev_distance / denom
            segment = FreeCAD.Vector(curr_point).sub(prev_point)
            return FreeCAD.Vector(prev_point).add(segment.multiply(factor))

        result = []
        prev_point = FreeCAD.Vector(polygon[-1])
        prev_distance = signed_distance(prev_point)
        prev_inside = is_inside(prev_distance)
        for current_point in polygon:
            current_point = FreeCAD.Vector(current_point)
            current_distance = signed_distance(current_point)
            current_inside = is_inside(current_distance)
            if current_inside:
                if not prev_inside:
                    result.append(
                        intersect(prev_point, current_point, prev_distance, current_distance)
                    )
                result.append(current_point)
            elif prev_inside:
                result.append(intersect(prev_point, current_point, prev_distance, current_distance))
            prev_point = current_point
            prev_distance = current_distance
            prev_inside = current_inside
        return result

    def _get_preview_footprint_polylines(self, points):
        footprint = self._get_preview_footprint(points)
        if not footprint or len(footprint) < 3:
            return [], []

        relation_endings, warnings = self._collect_preview_wall_relation_data(
            self._edit_wall, points
        )
        polygon = [FreeCAD.Vector(point) for point in footprint]
        for end_name in ("Start", "End"):
            plane = relation_endings.get(end_name)
            if plane is None or end_name in relation_endings.get("Conflicts", set()):
                continue
            ref_point = points[1] if end_name == "Start" else points[0]
            polygon = self._clip_preview_polygon_to_plane(polygon, plane, ref_point)
            if not polygon or len(polygon) < 3:
                break

        if not polygon or len(polygon) < 3:
            return [], warnings

        closed = list(polygon)
        closed.append(FreeCAD.Vector(closed[0]))
        return [closed], warnings

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

        previous_relation_status = self._plan_relation_status_message
        polylines, relation_warnings = self._get_preview_footprint_polylines(points)
        if relation_warnings:
            label, status, _detail = relation_warnings[0]
            self._plan_relation_status_message = translate(
                "BIM_PlanEdit", "Preview warning: {label} ({status})"
            ).format(label=label, status=status)
        elif self._is_wall_edit_modal_active():
            self._clear_plan_relation_status()

        segments = []
        for polyline in polylines:
            if len(polyline) < 2:
                continue
            segments.extend(zip(polyline, polyline[1:]))

        color = (0.22, 0.53, 0.98)
        width = self._scaled_line_width(2)
        if len(self._preview_footprint_trackers) != len(segments):
            self._finalize_trackers(self._preview_footprint_trackers)
            self._preview_footprint_trackers = []
            for _start, _end in segments:
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                self._preview_footprint_trackers.append(tracker)

        for tracker, (start, end) in zip(self._preview_footprint_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

        if previous_relation_status != self._plan_relation_status_message:
            self._refresh_task_panel_status()

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

        self._finalize_trackers(self._preview_footprint_trackers)
        self._preview_footprint_trackers = []

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
        symbol_handle_role = self._pick_selected_symbol_handle(mouse_pos)
        if symbol_handle_role is not None:
            return ("symbol_handle", self.selected_symbol, symbol_handle_role)
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
            if self.current_tool == "Join":
                pos = event.getPosition().getValue()
                target_kind, target_wall = self._get_plan_target_at_position((pos[0], pos[1]))
                if (
                    target_kind == "wall"
                    and self._is_plan_selectable_wall(target_wall)
                    and target_wall != self.selected_wall
                    and self._apply_plan_wall_join(self.selected_wall, target_wall)
                ):
                    if hasattr(event_callback, "setHandled"):
                        try:
                            event_callback.setHandled()
                        except Exception:
                            pass
                return
            if self.current_tool != "Select":
                return
            pos = event.getPosition().getValue()
            node = self._get_edit_node((pos[0], pos[1]))
            if not node:
                if self._activate_opening_target((pos[0], pos[1]), event_callback):
                    return
                if self._activate_symbol_target((pos[0], pos[1]), event_callback):
                    return
                if self._activate_wall_target((pos[0], pos[1]), event_callback):
                    return
                if (
                    self.selected_opening is not None
                    or self.selected_symbol is not None
                    or self.selected_wall is not None
                ):
                    self._clear_plan_selection_state()
                return
            node_kind = node[0]
            if node_kind == "opening_handle":
                _kind, obj, index = node
                self.selected_opening = obj
                self.selected_wall = None
                self.selected_symbol = None
                self._clear_wall_grips()
                self._activate_opening_handle(obj, index)
            elif node_kind == "symbol_handle":
                _kind, obj, role = node
                self.selected_symbol = obj
                self.selected_wall = None
                self.selected_opening = None
                self._clear_wall_grips()
                self._activate_symbol_handle(obj, role)
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
                    self.selected_symbol = None
                    self._clear_wall_grips()
                    self._activate_opening_handle(obj, index)
                else:
                    if obj != self.selected_wall:
                        self.selected_wall = obj
                    self.selected_opening = None
                    self.selected_symbol = None
                    self._activate_wall_grip(index, wall=obj)
            if hasattr(event_callback, "setHandled"):
                try:
                    event_callback.setHandled()
                except Exception:
                    pass

    def _on_mouse_moved(self, event_callback):
        if self._tearing_down:
            return
        if self.current_tool not in ("Select", "Join"):
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
        if self.current_tool == "Join":
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            self._sync_junction_node_overlays()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            return
        if self.current_tool == "Select":
            self._sync_junction_node_overlays()
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
                self._sync_hovered_wall_opening_context_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_OPENING in dirty:
                self._sync_hovered_opening_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_SYMBOL in dirty:
                self._sync_hovered_symbol_overlay()
            if refresh_all or _PLAN_VISUAL_WALL_GRIPS in dirty:
                if self.selected_wall:
                    self._sync_wall_grips()
                self._sync_selected_wall_opening_context_overlay()
            if self.selected_opening and (refresh_all or _PLAN_VISUAL_SELECTED_OPENING in dirty):
                self._refresh_selected_opening_visuals()
            if self.selected_symbol and (refresh_all or _PLAN_VISUAL_SELECTED_SYMBOL in dirty):
                self._refresh_selected_symbol_visuals()
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
        if (
            self.current_tool in ("Move Symbol", "Rotate Symbol")
            and key == coin.SoKeyboardEvent.ESCAPE
        ):
            self._cancel_symbol_handle_point_pick()
            return
        if self.current_tool == "Join" and key == coin.SoKeyboardEvent.TAB:
            if self._cycle_plan_join_type() and hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
            return
        if self.current_tool == "Join" and key in (
            getattr(coin.SoKeyboardEvent, "DELETE", None),
            getattr(coin.SoKeyboardEvent, "BACKSPACE", None),
        ):
            if self._unjoin_current_plan_wall_pair() and hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
            return
        if self.current_tool == "Join" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_join_tool()
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
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
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
        self._sync_selected_wall_opening_context_overlay()
        self._request_view_redraw()

    def _is_symbol_visual_dependency(self, symbol, obj):
        if not self._is_plan_symbol_instance(symbol) or not obj:
            return False
        if obj == symbol:
            return True
        semantic_obj = self._get_plan_semantic_object(symbol)
        if obj == semantic_obj:
            return True
        if obj == getattr(semantic_obj, "Base", None):
            return True
        return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])

    def _refresh_plan_object_footprint_display(self, obj):
        if not self._is_supported_plan_object(obj):
            return
        semantic_obj = self._get_plan_semantic_object(obj)
        refresh_targets = []
        for candidate in (semantic_obj, obj):
            if not candidate:
                continue
            name = getattr(candidate, "Name", None)
            if not name or any(getattr(target, "Name", None) == name for target in refresh_targets):
                continue
            refresh_targets.append(candidate)

        refreshed = False
        for candidate in refresh_targets:
            view_object = getattr(candidate, "ViewObject", None)
            proxy = getattr(view_object, "Proxy", None) if view_object else None
            if not proxy:
                continue
            if not hasattr(proxy, "ensureFootprintGroup") and not hasattr(proxy, "updateFootprint"):
                continue
            try:
                if hasattr(proxy, "ensureFootprintGroup"):
                    proxy.ensureFootprintGroup(view_object)
                if hasattr(proxy, "updateFootprint"):
                    proxy.updateFootprint()
                if hasattr(view_object, "update"):
                    view_object.update()
                refreshed = True
            except Exception:
                continue

        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "update"):
            try:
                view_object.update()
            except Exception:
                pass
        if not refreshed:
            return
        self._request_view_redraw()

    def _refresh_opening_footprint_display(self, opening):
        if not self._is_hosted_opening_object(opening):
            return
        self._refresh_plan_object_footprint_display(opening)

    def _refresh_wall_footprint_display(self, wall):
        if not wall:
            return
        self._refresh_plan_object_footprint_display(wall)

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

    def slotCreatedObject(self, obj):
        if self._tearing_down:
            return
        self._queue_created_plan_object(obj)

    def slotChangedObject(self, obj, prop):
        if self._tearing_down:
            return
        if self.current_tool != "Select":
            return
        if (
            self._is_symbol_visual_dependency(self.selected_symbol, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.selected_symbol)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SYMBOL)
            return
        if (
            self._is_symbol_visual_dependency(self.hovered_symbol, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_symbol)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SYMBOL)
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
        if (
            self.hovered_wall
            and obj in self._get_wall_hosted_openings(self.hovered_wall)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(obj)
            self._refresh_opening_host_footprint_displays(obj)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
            return
        if (
            self.selected_wall
            and obj in self._get_wall_hosted_openings(self.selected_wall)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(obj)
            self._refresh_opening_host_footprint_displays(obj)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_WALL_GRIPS)
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
        if obj == self.hovered_symbol:
            self.hovered_symbol = None
            self._clear_hovered_symbol_overlay()
        if obj == self.selected_opening:
            self.selected_opening = None
            self._refresh_selected_opening_visuals()
            return
        if obj == self.selected_symbol:
            self.selected_symbol = None
            self._refresh_selected_symbol_visuals()
            return
        if obj != self.selected_wall:
            return
        self._schedule_selected_wall_reset("Deleted", obj)

    def _invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        if self.selected_symbol:
            self._refresh_plan_object_footprint_display(self.selected_symbol)
        if self.hovered_symbol and self.hovered_symbol != self.selected_symbol:
            self._refresh_plan_object_footprint_display(self.hovered_symbol)
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
            _PLAN_VISUAL_SELECTED_SYMBOL,
            _PLAN_VISUAL_HOVERED_SYMBOL,
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

    def attach_aux_task_panel(self, panel):
        if panel is None or panel in self._aux_task_panels:
            return
        self._aux_task_panels.append(panel)
        try:
            panel.refresh()
        except (AttributeError, RuntimeError):
            self.detach_aux_task_panel(panel)

    def detach_aux_task_panel(self, panel):
        if panel is None:
            return
        self._aux_task_panels = [item for item in self._aux_task_panels if item is not panel]

    def detach_task_panel(self):
        panel = self.task_panel
        self.task_panel = None
        if panel:
            try:
                mark_closed = getattr(panel, "mark_closed", None)
                if callable(mark_closed):
                    mark_closed()
            except Exception:
                pass
            try:
                detach = getattr(panel, "detach", None)
                if callable(detach):
                    detach()
                else:
                    dispose = getattr(panel, "dispose", None)
                    if callable(dispose):
                        dispose()
            except Exception:
                pass
        return panel

    def on_panel_closed(self, panel):
        if self.task_panel is panel:
            self.task_panel = None
            if not self._finishing:
                self.shutdown(close_dialog=False, teardown=self._tearing_down)
            return
        try:
            mark_closed = getattr(panel, "mark_closed", None)
            if callable(mark_closed):
                mark_closed()
        except Exception:
            pass
        try:
            detach = getattr(panel, "detach", None)
            if callable(detach):
                detach()
            else:
                dispose = getattr(panel, "dispose", None)
                if callable(dispose):
                    dispose()
        except Exception:
            pass

    def _refresh_task_panel_status(self):
        if self._tearing_down:
            return
        self._update_input_hints()
        self._refresh_viewport_status_chip()
        panel = self.task_panel
        if panel:
            try:
                panel.refresh_from_session()
            except (AttributeError, RuntimeError):
                self.on_panel_closed(panel)
        stale_panels = []
        for extra_panel in list(self._aux_task_panels):
            if extra_panel is panel:
                continue
            try:
                extra_panel.refresh_from_session()
            except (AttributeError, RuntimeError):
                stale_panels.append(extra_panel)
        for extra_panel in stale_panels:
            self.detach_aux_task_panel(extra_panel)

    def _is_modal_plan_interaction_active(self):
        return bool(
            self._is_wall_edit_modal_active()
            or self.current_tool in ("Move Opening", "Move Symbol", "Rotate Symbol")
        )

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

    def _get_plan_view_widget(self):
        if self._tearing_down or not self.view:
            return None
        try:
            return self.view.graphicsView()
        except Exception:
            return None

    def _format_status_chip_action(self, message):
        if not message:
            return ""
        text = str(message)
        if text.startswith("%1 "):
            text = text[3:]
        elif text.startswith("%1"):
            text = text[2:]
        text = text.strip()
        if not text:
            return ""
        return text[0].upper() + text[1:]

    def _get_status_chip_text(self):
        title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(tool=self.current_tool)

        if self.current_tool == "Move Opening":
            context = (
                translate("BIM_PlanEdit", "Opening: {label}").format(
                    label=self.selected_opening.Label
                )
                if self.selected_opening
                else translate("BIM_PlanEdit", "Opening move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Move Symbol":
            context = (
                translate("BIM_PlanEdit", "Symbol: {label}").format(
                    label=self.selected_symbol.Label
                )
                if self.selected_symbol
                else translate("BIM_PlanEdit", "Symbol move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Rotate Symbol":
            context = (
                translate("BIM_PlanEdit", "Symbol: {label}").format(
                    label=self.selected_symbol.Label
                )
                if self.selected_symbol
                else translate("BIM_PlanEdit", "Symbol rotation")
            )
            if self._symbol_rotation_snap_enabled():
                action = translate(
                    "BIM_PlanEdit", "Click target angle ({snap} snap, Shift = free)"
                ).format(snap=self._format_symbol_rotation_snap_label())
            else:
                action = translate("BIM_PlanEdit", "Click target angle")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Move Wall":
            context = (
                translate("BIM_PlanEdit", "Wall: {label}").format(label=self.selected_wall.Label)
                if self.selected_wall
                else translate("BIM_PlanEdit", "Wall move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Join":
            target_wall, joint, detail = self._get_plan_join_candidate_state()
            context = (
                translate("BIM_PlanEdit", "Source wall: {label}").format(
                    label=self.selected_wall.Label
                )
                if self.selected_wall
                else translate("BIM_PlanEdit", "Wall join")
            )
            action = self._get_plan_join_mode_action_text(target_wall, joint)
            if detail:
                return title, "{}\n{}\n{}".format(context, detail, action)
            return title, "{}\n{}".format(context, action)

        if self.current_tool.startswith("Stretch "):
            context = (
                translate("BIM_PlanEdit", "Wall: {label}").format(label=self.selected_wall.Label)
                if self.selected_wall
                else translate("BIM_PlanEdit", "Wall stretch")
            )
            action = translate("BIM_PlanEdit", "Click endpoint or press Enter to type a value")
            return title, "{}\n{}".format(context, action)

        if self.selected_opening:
            context = translate("BIM_PlanEdit", "Opening: {label}").format(
                label=self.selected_opening.Label
            )
        elif self.selected_symbol:
            context = translate("BIM_PlanEdit", "Symbol: {label}").format(
                label=self.selected_symbol.Label
            )
        elif self.selected_wall:
            context = translate("BIM_PlanEdit", "Wall: {label}").format(
                label=self.selected_wall.Label
            )
        else:
            context = translate("BIM_PlanEdit", "Storey: {label}").format(
                label=self.get_storey_label(self.active_storey)
            )

        hints = self._get_input_hint_specs()
        action = self._format_status_chip_action(hints[0][0]) if hints else ""
        if self._plan_relation_status_message:
            action = self._plan_relation_status_message
        if not action:
            action = translate("BIM_PlanEdit", "Work directly in the viewport")
        return title, "{}\n{}".format(context, action)

    def _ensure_viewport_status_chip(self):
        widget = self._get_plan_view_widget()
        if widget is None:
            self._clear_viewport_status_chip()
            return None
        chip = self._viewport_status_chip
        if chip is not None and getattr(chip, "host_widget", None) is widget:
            return chip
        self._clear_viewport_status_chip()
        try:
            chip = _PlanEditViewportStatusChip(self, widget)
        except Exception:
            return None
        self._viewport_status_chip = chip
        return chip

    def _refresh_viewport_status_chip(self):
        if self._tearing_down:
            return
        chip = self._ensure_viewport_status_chip()
        if chip is None:
            return
        title, body = self._get_status_chip_text()
        try:
            chip.set_texts(title, body)
        except Exception:
            self._clear_viewport_status_chip()

    def _clear_viewport_status_chip(self):
        chip = self._viewport_status_chip
        self._viewport_status_chip = None
        if chip is None:
            return
        try:
            chip.close_chip()
        except Exception:
            pass

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
        if message is None:
            return None
        raw_message = str(message)
        if not raw_message.strip():
            return None
        try:
            return FreeCADGui.InputHint(raw_message, *sequences)
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
            if self.selected_symbol:
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick symbol handle"),
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
                    translate("BIM_PlanEdit", "%1 select wall, opening, or symbol"),
                    ui.MouseLeft,
                ),
            )

        if self.current_tool == "Join":
            hints = [
                (
                    translate("BIM_PlanEdit", "%1 pick wall to join"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle join type ({joint_type})").format(
                        joint_type=self.get_plan_join_type_label()
                    ),
                    ui.KeyTab,
                ),
            ]
            if self._get_plan_candidate_joint() is not None:
                hints.append(
                    (
                        translate("BIM_PlanEdit", "%1 unjoin pair"),
                        ui.KeyDelete,
                    )
                )
            hints.append(
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                )
            )
            return tuple(hints)

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
            "Move Symbol": (
                (
                    translate("BIM_PlanEdit", "%1 place symbol"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Rotate Symbol": (
                (
                    translate("BIM_PlanEdit", "%1 place rotation"),
                    ui.MouseLeft,
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
        symbol_candidate = None
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
            target_kind = self._get_plan_target_kind_for_object(obj)
            if target_kind == "opening":
                return ("opening", obj)
            if target_kind == "symbol" and symbol_candidate is None:
                symbol_candidate = obj
            elif target_kind == "wall" and wall_candidate is None:
                wall_candidate = obj
        if symbol_candidate is not None:
            return ("symbol", symbol_candidate)
        if wall_candidate is not None:
            return ("wall", wall_candidate)
        return (None, None)

    def _update_hovered_plan_target(self, mouse_pos):
        if self.current_tool == "Join":
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
            if target_kind == "wall" and target_obj != self.selected_wall:
                self._set_hovered_wall(target_obj)
            else:
                self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            return
        if self.current_tool != "Select":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            return
        target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if target_kind == "opening":
            self._set_hovered_wall(None)
            self._set_hovered_opening(target_obj)
            self._set_hovered_symbol(None)
        elif target_kind == "symbol":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(target_obj)
        elif target_kind == "wall":
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_wall(target_obj)
        else:
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)

    def _set_hovered_wall(self, wall):
        if wall == self.selected_wall:
            wall = None
        if self.hovered_wall == wall:
            return
        self.hovered_wall = wall
        self._sync_junction_node_overlays()
        self._sync_hovered_wall_overlay()
        self._sync_hovered_wall_opening_context_overlay()
        if self.current_tool == "Join":
            self._refresh_task_panel_status()

    def _set_hovered_opening(self, opening):
        if opening == self.selected_opening:
            opening = None
        if self.hovered_opening == opening:
            return
        self.hovered_opening = opening
        self._sync_hovered_opening_overlay()

    def _set_hovered_symbol(self, symbol):
        if symbol == self.selected_symbol:
            symbol = None
        if self.hovered_symbol == symbol:
            return
        self.hovered_symbol = symbol
        self._sync_hovered_symbol_overlay()

    def _select_opening_for_plan_edit(self, opening, queue_restore=False):
        if not self._is_hosted_opening_object(opening):
            return False
        self.current_tool = "Select"
        self._set_selected_plan_target("opening", opening, pending_restore=queue_restore)
        self._clear_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()
        if queue_restore:
            self._queue_restore_selected_opening(opening)
        return True

    def _select_symbol_for_plan_edit(self, symbol, queue_restore=False):
        if not self._is_plan_symbol_instance(symbol):
            return False
        self.current_tool = "Select"
        self._set_selected_plan_target("symbol", symbol, pending_restore=queue_restore)
        self._clear_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()
        if queue_restore:
            self._queue_restore_selected_symbol(symbol)
        return True

    def _select_wall_for_plan_edit(self, wall, queue_restore=False):
        if not self._is_plan_selectable_wall(wall):
            return False

        self.current_tool = "Select"
        self.hovered_opening = None
        self.hovered_symbol = None
        self._set_selected_plan_target("wall", wall, pending_restore=queue_restore)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
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
        self._set_hovered_symbol(None)
        self._select_opening_for_plan_edit(opening, queue_restore=True)
        if event_callback and hasattr(event_callback, "setHandled"):
            try:
                event_callback.setHandled()
            except Exception:
                pass
        return True

    def _activate_symbol_target(self, mouse_pos, event_callback=None):
        target_kind, symbol = self._get_plan_target_at_position(mouse_pos)
        if target_kind != "symbol":
            symbol = None
        if not self._select_symbol_for_plan_edit(symbol, queue_restore=True):
            return False
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
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
        if not self._select_wall_for_plan_edit(wall, queue_restore=True):
            return False
        self._set_hovered_wall(None)
        self._set_hovered_symbol(None)
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
        if self.current_tool not in ("Select", "Join"):
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

    def _get_plan_context_junctions(self):
        if self.current_tool not in ("Select", "Join"):
            return []

        import ArchWallJoinUtils

        junctions = []
        seen = set()
        for wall in (self.selected_wall, self.hovered_wall):
            if not self._is_plan_selectable_wall(wall):
                continue
            for relation in ArchWallJoinUtils.iter_wall_relations(wall):
                if not ArchWallJoinUtils.is_wall_junction(relation):
                    continue
                relation_name = getattr(relation, "Name", None)
                if not relation_name or relation_name in seen:
                    continue
                seen.add(relation_name)
                if getattr(relation, "Status", "") not in ("OK", "Conflict"):
                    continue
                junctions.append(relation)
        return junctions

    def _create_junction_node_trackers(self, junction, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        intersection = getattr(junction, "Intersection", None)
        if intersection is None:
            return
        units_per_pixel = self._get_plan_view_units_per_pixel() or 1.0
        half_size = max(units_per_pixel * 8.0, 20.0)
        center = FreeCAD.Vector(intersection)
        offsets = (
            (FreeCAD.Vector(-half_size, -half_size, 0), FreeCAD.Vector(half_size, half_size, 0)),
            (FreeCAD.Vector(-half_size, half_size, 0), FreeCAD.Vector(half_size, -half_size, 0)),
        )
        for start_offset, end_offset in offsets:
            tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
            tracker.p1(center.add(start_offset))
            tracker.p2(center.add(end_offset))
            tracker.on()
            tracker_store.append(tracker)

    def _sync_junction_node_overlays(self):
        self._clear_junction_node_overlays()
        for junction in self._get_plan_context_junctions():
            if self.selected_wall and self.selected_wall in (
                getattr(junction, "Walls", None) or []
            ):
                color = (0.92, 0.58, 0.12)
                width = self._scaled_line_width(2)
            else:
                color = (0.82, 0.70, 0.32)
                width = self._scaled_line_width(1)
            self._create_junction_node_trackers(
                junction,
                color=color,
                width=width,
                tracker_store=self._junction_node_trackers,
            )

    def _clear_junction_node_overlays(self):
        self._finalize_trackers(self._junction_node_trackers)
        self._junction_node_trackers = []

    def _sync_hovered_wall_opening_context_overlay(self):
        self._clear_hovered_wall_opening_context_overlay()
        if self.current_tool != "Select":
            return
        if not self.hovered_wall or self.hovered_wall == self.selected_wall:
            return
        if self.selected_wall or self.selected_opening:
            return
        color = (0.64, 0.70, 0.84)
        width = self._scaled_line_width(1)
        for opening in self._get_wall_hosted_openings(self.hovered_wall):
            self._create_opening_overlay_trackers(
                opening,
                color=color,
                width=width,
                tracker_store=self._hovered_wall_opening_context_trackers,
            )

    def _clear_hovered_wall_opening_context_overlay(self):
        self._finalize_trackers(self._hovered_wall_opening_context_trackers)
        self._hovered_wall_opening_context_trackers = []

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

    def _sync_selected_wall_opening_context_overlay(self):
        self._clear_selected_wall_opening_context_overlay()
        if self.current_tool != "Select" or not self.selected_wall or self.selected_opening:
            return
        color = (0.46, 0.58, 0.82)
        width = self._scaled_line_width(2)
        for opening in self._get_wall_hosted_openings(self.selected_wall):
            self._create_opening_overlay_trackers(
                opening,
                color=color,
                width=width,
                tracker_store=self._selected_wall_opening_context_trackers,
            )

    def _clear_selected_wall_opening_context_overlay(self):
        self._finalize_trackers(self._selected_wall_opening_context_trackers)
        self._selected_wall_opening_context_trackers = []

    def _copy_placement(self, placement):
        if placement is None:
            return FreeCAD.Placement()
        try:
            return placement.copy()
        except Exception:
            return FreeCAD.Placement(placement)

    def _get_plan_object_global_placement(self, obj):
        if not obj:
            return FreeCAD.Placement()
        if hasattr(obj, "getGlobalPlacement"):
            try:
                placement = obj.getGlobalPlacement()
                if placement is not None:
                    return placement
            except Exception:
                pass
        return getattr(obj, "Placement", FreeCAD.Placement())

    def _get_symbol_global_placement(self, symbol, placement=None):
        current_global = self._get_plan_object_global_placement(symbol)
        if placement is None:
            return current_global
        current_local = getattr(symbol, "Placement", None)
        if current_local is None:
            return placement
        try:
            parent_global = current_global.multiply(current_local.inverse())
            return parent_global.multiply(placement)
        except Exception:
            return placement

    def _get_symbol_parent_global_placement(self, symbol, placement=None):
        placement = placement or getattr(symbol, "Placement", None)
        current_global = self._get_plan_object_global_placement(symbol)
        if placement is None:
            return current_global
        try:
            return current_global.multiply(placement.inverse())
        except Exception:
            return FreeCAD.Placement()

    def _get_symbol_plan_proxy(self, symbol, *attrs):
        semantic_obj = self._get_plan_semantic_object(symbol)
        view_object = getattr(semantic_obj, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _get_symbol_semantic_proxy(self, symbol, *attrs):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = getattr(semantic_obj, "Proxy", None)
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _get_symbol_overlay_polylines(self, symbol, placement=None):
        if not self._is_plan_symbol_instance(symbol):
            return []
        proxy = self._get_symbol_plan_proxy(symbol, "_collect_local_footprint_polylines")
        if not proxy:
            return []
        try:
            local_polylines = list(proxy._collect_local_footprint_polylines() or [])
        except Exception:
            return []

        placement = self._get_symbol_global_placement(symbol, placement=placement)
        polylines = []
        for polyline in local_polylines:
            points = []
            for point in polyline:
                if isinstance(point, FreeCAD.Vector):
                    local_point = FreeCAD.Vector(point)
                else:
                    try:
                        z_value = point[2] if len(point) > 2 else 0.0
                        local_point = FreeCAD.Vector(point[0], point[1], z_value)
                    except Exception:
                        continue
                try:
                    points.append(placement.multVec(local_point))
                except Exception:
                    continue
            if len(points) >= 2:
                polylines.append(points)
        return polylines

    def _get_symbol_overlay_segments(self, symbol, placement=None):
        segments = []
        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _refresh_selected_symbol_visuals(self):
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._request_view_redraw()

    def _create_symbol_overlay_trackers(self, symbol, color, width, tracker_store, placement=None):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _sync_hovered_symbol_overlay(self):
        self._clear_hovered_symbol_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_plan_symbol_instance(self.hovered_symbol):
            return
        if self.hovered_symbol == self.selected_symbol:
            return
        self._create_symbol_overlay_trackers(
            self.hovered_symbol,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._symbol_hover_trackers,
        )

    def _clear_hovered_symbol_overlay(self):
        self._finalize_trackers(self._symbol_hover_trackers)
        self._symbol_hover_trackers = []

    def _sync_selected_symbol_overlay(self):
        if self.current_tool != "Select" or not self._is_plan_symbol_instance(self.selected_symbol):
            self._clear_selected_symbol_overlay()
            return
        width = self._scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_selected_symbol_overlay()
            return
        segments = self._get_symbol_overlay_segments(self.selected_symbol)
        color = (0.12, 0.38, 0.95)
        if len(self._symbol_overlay_trackers) != len(segments):
            self._clear_selected_symbol_overlay()
            for _start, _end in segments:
                tracker = DraftTrackers.lineTracker(scolor=color, swidth=width, ontop=True)
                self._symbol_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(self._symbol_overlay_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_selected_symbol_overlay(self):
        self._finalize_trackers(self._symbol_overlay_trackers)
        self._symbol_overlay_trackers = []

    def _get_symbol_local_anchor(self, symbol):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = self._get_symbol_semantic_proxy(symbol, "get_plan_anchor")
        if proxy:
            try:
                return FreeCAD.Vector(proxy.get_plan_anchor(semantic_obj))
            except Exception:
                pass
        try:
            import ArchEquipment

            return ArchEquipment.get_plan_anchor(semantic_obj)
        except Exception:
            return FreeCAD.Vector()

    def _get_symbol_local_facing(self, symbol):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = self._get_symbol_semantic_proxy(symbol, "get_plan_facing")
        if proxy:
            try:
                facing = FreeCAD.Vector(proxy.get_plan_facing(semantic_obj))
            except Exception:
                facing = None
        else:
            facing = None
        if facing is None:
            try:
                import ArchEquipment

                facing = ArchEquipment.get_plan_facing(semantic_obj)
            except Exception:
                facing = FreeCAD.Vector(1, 0, 0)
        facing = FreeCAD.Vector(facing.x, facing.y, 0)
        if facing.Length < 0.001:
            return FreeCAD.Vector(1, 0, 0)
        facing.normalize()
        return facing

    def _get_symbol_anchor_point(self, symbol, placement=None):
        placement = self._get_symbol_global_placement(symbol, placement=placement)
        anchor = self._get_symbol_local_anchor(symbol)
        try:
            return placement.multVec(anchor)
        except Exception:
            base = getattr(placement, "Base", None)
            if base is None:
                return FreeCAD.Vector()
            return FreeCAD.Vector(base.x, base.y, base.z)

    def _get_symbol_facing_vector(self, symbol, placement=None):
        placement = self._get_symbol_global_placement(symbol, placement=placement)
        facing = self._get_symbol_local_facing(symbol)
        try:
            facing = placement.Rotation.multVec(facing)
        except Exception:
            pass
        facing = FreeCAD.Vector(facing.x, facing.y, 0)
        if facing.Length < 0.001:
            return FreeCAD.Vector()
        facing.normalize()
        return facing

    def _symbol_rotation_snap_enabled(self):
        params = getattr(self, "_plan_edit_params", None)
        if not params:
            return True
        try:
            return params.GetBool("SymbolRotateAngleSnap", True)
        except Exception:
            return True

    def _get_symbol_rotation_snap_increment_degrees(self):
        params = getattr(self, "_plan_edit_params", None)
        if not params:
            return 15.0
        try:
            increment = float(params.GetFloat("SymbolRotateAngleIncrement", 15.0))
        except Exception:
            increment = 15.0
        if increment <= 0.001:
            return 15.0
        return min(increment, 180.0)

    def _get_symbol_rotation_snap_step_radians(self):
        return math.radians(self._get_symbol_rotation_snap_increment_degrees())

    def _format_symbol_rotation_snap_label(self):
        increment = self._get_symbol_rotation_snap_increment_degrees()
        rounded = round(increment)
        if abs(increment - rounded) < 1e-9:
            return "{}°".format(int(rounded))
        return "{}°".format(("{:.3f}".format(increment)).rstrip("0").rstrip("."))

    def _symbol_rotation_free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def _resolve_symbol_handle_target_point(self, symbol, handle_role, point, placement=None):
        if point is None:
            return None
        if isinstance(point, FreeCAD.Vector):
            target_point = FreeCAD.Vector(point.x, point.y, point.z)
        else:
            try:
                z_value = point[2] if len(point) > 2 else 0.0
                target_point = FreeCAD.Vector(point[0], point[1], z_value)
            except Exception:
                return None
        if handle_role != "rotate":
            return target_point
        if not self._symbol_rotation_snap_enabled():
            return target_point
        if self._symbol_rotation_free_angle_override_active():
            return target_point

        snap_step = self._get_symbol_rotation_snap_step_radians()
        if snap_step <= 1e-9:
            return target_point

        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        vector = FreeCAD.Vector(target_point.x - anchor.x, target_point.y - anchor.y, 0)
        radius = math.hypot(vector.x, vector.y)
        if radius < 0.001:
            return target_point

        snapped_angle = round(math.atan2(vector.y, vector.x) / snap_step) * snap_step
        return FreeCAD.Vector(
            anchor.x + radius * math.cos(snapped_angle),
            anchor.y + radius * math.sin(snapped_angle),
            anchor.z,
        )

    def _get_symbol_handle_radius(self, symbol, placement=None):
        placement = placement or self._get_plan_object_global_placement(symbol)
        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        radius = 0.0
        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            for point in polyline:
                radius = max(
                    radius,
                    math.hypot(float(point.x) - float(anchor.x), float(point.y) - float(anchor.y)),
                )
        units_per_pixel = self._get_plan_view_units_per_pixel() or 10.0
        return max(radius * 1.2, 28.0 * units_per_pixel, 300.0)

    def _get_selected_symbol_handle_specs(self, symbol):
        from draftutils import params

        if not self._is_plan_symbol_instance(symbol):
            return []

        placement = self._get_plan_object_global_placement(symbol)
        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        radius = self._get_symbol_handle_radius(symbol, placement=placement)
        rotate_direction = self._get_symbol_facing_vector(symbol, placement=placement)
        if rotate_direction.Length < 0.001:
            rotate_direction = FreeCAD.Vector(1, 0, 0)
        rotate_offset = rotate_direction.multiply(radius)
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        return [
            (
                "move",
                anchor,
                FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
            ),
            (
                "rotate",
                anchor.add(rotate_offset),
                FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
            ),
        ]

    def _sync_selected_symbol_handles(self):
        if self.current_tool != "Select":
            self._clear_selected_symbol_handles()
            return
        if not self._is_plan_symbol_instance(self.selected_symbol):
            self._clear_selected_symbol_handles()
            return
        self._clear_selected_symbol_handles()
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        for idx, (_role, point, marker) in enumerate(
            self._get_selected_symbol_handle_specs(self.selected_symbol)
        ):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            self._symbol_handle_trackers.append(tracker)

    def _clear_selected_symbol_handles(self):
        self._finalize_trackers(self._symbol_handle_trackers)
        self._symbol_handle_trackers = []

    def _pick_selected_symbol_handle(self, mouse_pos, radius_px=10):
        symbol = self.selected_symbol
        if not self._is_plan_symbol_instance(symbol) or not self.view:
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_role = None
        best_distance_sq = None
        for role, point, _marker in self._get_selected_symbol_handle_specs(symbol):
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
                best_role = role
                best_distance_sq = distance_sq
        return best_role

    def _sync_symbol_edit_preview(self, symbol, placement, guide_start=None, guide_end=None):
        self._clear_symbol_edit_preview()
        if self.current_tool not in ("Move Symbol", "Rotate Symbol"):
            return
        if not self._is_plan_symbol_instance(symbol) or placement is None:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        preview_color = (0.12, 0.38, 0.95)
        self._create_symbol_overlay_trackers(
            symbol,
            color=preview_color,
            width=self._scaled_line_width(3),
            tracker_store=self._symbol_edit_preview_trackers,
            placement=placement,
        )
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
        self._symbol_edit_preview_trackers.append(guide)

    def _clear_symbol_edit_preview(self):
        self._finalize_trackers(self._symbol_edit_preview_trackers)
        self._symbol_edit_preview_trackers = []

    def _get_symbol_handle_placement(self, symbol, handle_role, point):
        if not self._is_plan_symbol_instance(symbol) or point is None or not handle_role:
            return None
        start_placement = self._edit_symbol_start_placement
        if start_placement is None:
            start_placement = self._copy_placement(getattr(symbol, "Placement", None))
        point = self._resolve_symbol_handle_target_point(
            symbol, handle_role, point, placement=start_placement
        )
        if point is None:
            return None
        placement = self._copy_placement(start_placement)
        parent_global = self._get_symbol_parent_global_placement(symbol, placement=start_placement)
        anchor_global = self._get_symbol_anchor_point(symbol, placement=start_placement)
        local_anchor = self._get_symbol_local_anchor(symbol)
        if handle_role == "move":
            point_global = FreeCAD.Vector(point.x, point.y, anchor_global.z)
            try:
                anchor_parent = parent_global.inverse().multVec(point_global)
                placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
            except Exception:
                placement.Base = FreeCAD.Vector(
                    point.x - local_anchor.x,
                    point.y - local_anchor.y,
                    start_placement.Base.z,
                )
            return placement
        if handle_role != "rotate":
            return None

        anchor = FreeCAD.Vector(anchor_global.x, anchor_global.y, anchor_global.z)
        reference_point = self._edit_symbol_reference_point
        if reference_point is None:
            specs = dict(
                (role, handle_point)
                for role, handle_point, _marker in self._get_selected_symbol_handle_specs(symbol)
            )
            reference_point = specs.get("rotate")
        if reference_point is None:
            return None

        reference_vector = FreeCAD.Vector(
            reference_point.x - anchor.x,
            reference_point.y - anchor.y,
            0,
        )
        new_vector = FreeCAD.Vector(point.x - anchor.x, point.y - anchor.y, 0)
        if reference_vector.Length < 0.001 or new_vector.Length < 0.001:
            return None

        reference_angle = math.atan2(reference_vector.y, reference_vector.x)
        target_angle = math.atan2(new_vector.y, new_vector.x)
        delta_rotation = FreeCAD.Rotation(
            FreeCAD.Vector(0, 0, 1), math.degrees(target_angle - reference_angle)
        )
        current_global = self._get_symbol_global_placement(symbol, placement=start_placement)
        try:
            global_rotation = delta_rotation.multiply(current_global.Rotation)
            placement.Rotation = parent_global.Rotation.inverse().multiply(global_rotation)
        except Exception:
            placement.Rotation = delta_rotation.multiply(start_placement.Rotation)
        try:
            anchor_parent = parent_global.inverse().multVec(anchor)
            placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
        except Exception:
            placement.Base = FreeCAD.Vector(
                anchor.x - local_anchor.x,
                anchor.y - local_anchor.y,
                start_placement.Base.z,
            )
        return placement

    def _activate_symbol_handle(self, symbol, handle_role):
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_symbol_handle_now(symbol, handle_role)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda: self._activate_symbol_handle_now(symbol, handle_role),
        )

    def _activate_symbol_handle_now(self, symbol, handle_role):
        if self._tearing_down or not self._is_plan_symbol_instance(symbol):
            return
        if handle_role not in {"move", "rotate"}:
            return
        self._set_selected_plan_target("symbol", symbol)
        self._clear_wall_grips()
        self._start_symbol_handle_point_pick(symbol, handle_role)

    def _start_symbol_handle_point_pick(self, symbol, handle_role):
        if not self._is_plan_symbol_instance(symbol):
            return
        handle_points = {
            role: point for role, point, _marker in self._get_selected_symbol_handle_specs(symbol)
        }
        start_point = handle_points.get(handle_role)
        if start_point is None:
            return
        self.current_tool = "Move Symbol" if handle_role == "move" else "Rotate Symbol"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._edit_symbol = symbol
        self._edit_symbol_handle_role = handle_role
        self._edit_symbol_start_placement = self._copy_placement(getattr(symbol, "Placement", None))
        self._edit_symbol_reference_point = FreeCAD.Vector(start_point)
        self._clear_selected_symbol_overlay()
        self._clear_selected_symbol_handles()
        anchor = self._get_symbol_anchor_point(symbol, placement=self._edit_symbol_start_placement)
        self._sync_symbol_edit_preview(
            symbol,
            self._edit_symbol_start_placement,
            guide_start=anchor,
            guide_end=start_point,
        )
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            last=start_point,
            callback=self._finish_symbol_handle_point_pick,
            movecallback=self._update_symbol_handle_point_pick,
            title=(
                translate("BIM_PlanEdit", "Pick new symbol position")
                if handle_role == "move"
                else translate("BIM_PlanEdit", "Pick new symbol rotation")
            ),
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _update_symbol_handle_point_pick(self, point=None, snap_info=None):
        del snap_info
        symbol = self._edit_symbol
        handle_role = self._edit_symbol_handle_role
        if not symbol or not handle_role:
            self._clear_symbol_edit_preview()
            return
        target_point = self._resolve_symbol_handle_target_point(
            symbol, handle_role, point, placement=self._edit_symbol_start_placement
        )
        if target_point is None:
            self._clear_symbol_edit_preview()
            return
        placement = self._get_symbol_handle_placement(symbol, handle_role, point)
        if placement is None:
            self._clear_symbol_edit_preview()
            return
        guide_start = self._get_symbol_anchor_point(
            symbol, placement=self._edit_symbol_start_placement
        )
        guide_end = (
            self._get_symbol_anchor_point(symbol, placement=placement)
            if handle_role == "move"
            else target_point
        )
        self._sync_symbol_edit_preview(
            symbol, placement, guide_start=guide_start, guide_end=guide_end
        )

    def _finish_symbol_handle_point_pick(self, point=None, obj=None):
        del obj
        symbol = self._edit_symbol
        handle_role = self._edit_symbol_handle_role
        start_placement = self._edit_symbol_start_placement
        reference_point = self._edit_symbol_reference_point
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        FreeCAD.activeDraftCommand = None
        self._clear_symbol_edit_preview()

        if point is None or not symbol or not handle_role:
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        self._edit_symbol_start_placement = start_placement
        self._edit_symbol_reference_point = reference_point
        placement = self._get_symbol_handle_placement(symbol, handle_role, point)
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        if placement is None:
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        try:
            self.doc.openTransaction(
                translate(
                    "BIM_PlanEdit",
                    "Move Symbol" if handle_role == "move" else "Rotate Symbol",
                )
            )
            symbol.Placement = placement
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        self.current_tool = "Select"
        self._queue_restore_selected_symbol(symbol)

    def _cancel_symbol_handle_point_pick(self):
        symbol = self._edit_symbol
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._stop_snapper()
        FreeCAD.activeDraftCommand = None
        self._clear_symbol_edit_preview()
        self.current_tool = "Select"
        if symbol:
            self._set_selected_plan_target("symbol", symbol, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()

    def _restore_selected_symbol(self, symbol):
        self.current_tool = "Select"
        if symbol:
            self._set_selected_plan_target("symbol", symbol, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not symbol:
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._sync_selected_symbol_overlay()
            self._sync_selected_symbol_handles()
            self._refresh_task_panel_status()
            return
        previous_ignore = self._ignore_selection_changes
        self._ignore_selection_changes = True
        try:
            try:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(symbol)
            except Exception:
                pass
        finally:
            self._ignore_selection_changes = previous_ignore
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()

    def _queue_restore_selected_symbol(self, symbol):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_symbol(symbol)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_symbol(symbol))

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
        self._set_selected_plan_target("opening", opening)
        self._clear_wall_grips()
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
        self.current_tool = "Select"
        self._refresh_task_panel_status()
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
            self._set_selected_plan_target("opening", opening, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()

    def _restore_selected_opening(self, opening):
        self.current_tool = "Select"
        if opening:
            self._set_selected_plan_target("opening", opening, pending_restore=True)
        else:
            self._set_selected_plan_target()
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

    def _clear_plan_selection_state(self):
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._clear_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()

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
        self._set_selected_plan_target("opening", opening, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()


class PlanEditControlsWidget:
    """Reusable session controls widget for Plan Edit mode."""

    def __init__(self, session):
        from PySide import QtGui

        self.session = session
        self._storey_items = []
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self.form = self._build_form(QtGui)
        try:
            self.form.setObjectName("BIMPlanEditContextControls")
        except Exception:
            pass

    @property
    def modal_focus_widgets(self):
        return tuple(self._modal_focus_widgets)

    def _build_form(self, QtGui):
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
        layout.addLayout(self._build_join_type_row(QtGui))

        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.exit_button = self._make_button(QtGui, "Exit Plan Edit", self.on_exit_clicked)
        self.exit_button.setMinimumHeight(32)
        layout.addWidget(self.exit_button)

        self._modal_focus_widgets = [
            self.storey_combo,
            self.join_type_combo,
            self.unjoin_button,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
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

    def _build_join_type_row(self, QtGui):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        join_type_label = QtGui.QLabel(translate("BIM_PlanEdit", "Join Type"))
        self.join_type_combo = QtGui.QComboBox()
        for join_type in self.session.get_plan_join_types():
            self.join_type_combo.addItem(
                self.session.get_plan_join_type_label(join_type), join_type
            )
        self.join_type_combo.currentIndexChanged.connect(self.on_join_type_changed)
        self.unjoin_button = self._make_button(QtGui, "Unjoin", self.on_unjoin_clicked)
        row.addWidget(join_type_label)
        row.addWidget(self.join_type_combo, 1)
        row.addWidget(self.unjoin_button)
        return row

    def _capture_focus_policies(self):
        for widget in self._modal_focus_widgets:
            try:
                self._saved_focus_policies[widget] = widget.focusPolicy()
            except Exception:
                pass

    def dispose(self):
        form = self.form
        if form is not None:
            try:
                parent = form.parentWidget()
                if parent is not None and hasattr(parent, "layout"):
                    layout = parent.layout()
                    if layout is not None:
                        layout.removeWidget(form)
            except Exception:
                pass
            try:
                form.hide()
            except Exception:
                pass
            try:
                form.setParent(None)
            except Exception:
                pass
            try:
                form.deleteLater()
            except Exception:
                pass
        self.form = None
        self.status = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.move_button = None
        self.join_button = None
        self.join_type_combo = None
        self.unjoin_button = None
        self.reapply_button = None
        self.exit_button = None
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._storey_items = []

    def refresh(self):
        if self.form is None or self.storey_combo is None:
            return
        self.storey_combo.blockSignals(True)
        try:
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
        finally:
            try:
                self.storey_combo.blockSignals(False)
            except Exception:
                pass
        self.refresh_from_session()

    def refresh_from_session(self):
        if self.form is None or self.status is None or self.exit_button is None:
            return

        if self.join_type_combo is not None:
            self.join_type_combo.blockSignals(True)
            try:
                join_type_index = self.join_type_combo.findData(self.session.get_plan_join_type())
                if join_type_index >= 0:
                    self.join_type_combo.setCurrentIndex(join_type_index)
            finally:
                try:
                    self.join_type_combo.blockSignals(False)
                except Exception:
                    pass

        storey_text = self.session.get_storey_label(self.session.active_storey)
        tool = self.session.current_tool
        modal_active = self.session._is_modal_plan_interaction_active()
        if tool == "Join" and self.session.selected_wall:
            target_wall, joint, detail = self.session._get_plan_join_candidate_state()
            selection_state = translate("BIM_PlanEdit", "Source wall: {label}").format(
                label=self.session.selected_wall.Label
            )
            selection_help = translate(
                "BIM_PlanEdit",
                "Join type: {joint_type}\n{pair_state}\n{action}",
            ).format(
                joint_type=self.session.get_plan_join_type_label(),
                pair_state=detail or translate("BIM_PlanEdit", "Candidate wall: none"),
                action=self.session._get_plan_join_mode_action_text(target_wall, joint),
            )
        elif self.session.selected_opening:
            selection_state = translate("BIM_PlanEdit", "Opening: {label}").format(
                label=self.session.selected_opening.Label
            )
            selection_help = translate(
                "BIM_PlanEdit",
                "Use in-view handles to move or flip the selected opening.",
            )
        elif self.session.selected_symbol:
            selection_state = translate("BIM_PlanEdit", "Symbol: {label}").format(
                label=self.session.selected_symbol.Label
            )
            if self.session.current_tool == "Rotate Symbol":
                if self.session._symbol_rotation_snap_enabled():
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use in-view handles to rotate the selected symbol instance. Rotation snaps to {snap} by default; hold Shift for free angle.",
                    ).format(snap=self.session._format_symbol_rotation_snap_label())
                else:
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use in-view handles to rotate the selected symbol instance.",
                    )
            else:
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use in-view handles to move or rotate the selected symbol instance.",
                )
        elif self.session.selected_wall:
            selection_state = translate("BIM_PlanEdit", "Wall: {label}").format(
                label=self.session.selected_wall.Label
            )
            if self.session.is_selected_wall_endpoint_editable():
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use wall grips in the viewport to stretch or move the selected wall.",
                )
            else:
                selection_help = translate(
                    "BIM_PlanEdit",
                    "This wall can be reviewed in plan, but grip editing is unavailable.",
                )
        else:
            selection_state = translate("BIM_PlanEdit", "Selection: none")
            selection_help = translate(
                "BIM_PlanEdit",
                "Select a wall, hosted opening, or symbol instance in the viewport to edit it.",
            )
        if self.session._plan_relation_status_message:
            selection_help = "{}\n{}".format(
                selection_help,
                self.session._plan_relation_status_message,
            )
        self.status.setText(
            translate(
                "BIM_PlanEdit",
                "Mode: {tool}\nStorey: {storey}\nDisplay: Footprint\n{selection_state}\n{selection_help}",
            ).format(
                tool=tool,
                storey=storey_text,
                selection_state=selection_state,
                selection_help=selection_help,
            )
        )
        self._apply_modal_interaction_state(modal_active)

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
            self.join_type_combo,
            self.unjoin_button,
            self.reapply_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(not modal_active)
            except Exception:
                pass
        if self.unjoin_button is not None:
            try:
                self.unjoin_button.setEnabled(
                    not modal_active
                    and self.session.current_tool == "Join"
                    and self.session._get_plan_candidate_joint() is not None
                )
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

    def on_join_type_changed(self, index):
        if self.join_type_combo is None or index < 0:
            return
        join_type = self.join_type_combo.itemData(index) or self.join_type_combo.itemText(index)
        self.session.set_plan_join_type(join_type)

    def on_unjoin_clicked(self):
        self.session._unjoin_current_plan_wall_pair()

    def on_reapply_clicked(self):
        self.session.apply_plan_view(fit=False)
        self.refresh_from_session()

    def on_exit_clicked(self):
        self.session.shutdown()


class _PlanEditViewportStatusChip:
    def __new__(cls, session, host_widget):
        from PySide import QtCore, QtGui

        class _Chip(QtGui.QFrame):
            def __init__(self, plan_session, parent_widget):
                super().__init__(parent_widget)
                self.session = plan_session
                self.host_widget = parent_widget
                self.setObjectName("BIMPlanEditViewportStatusChip")
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                self.setFocusPolicy(QtCore.Qt.NoFocus)
                self.setFrameShape(QtGui.QFrame.NoFrame)
                self.setStyleSheet("""
                    QFrame#BIMPlanEditViewportStatusChip {
                        background: rgba(250, 250, 248, 230);
                        border: 1px solid rgba(24, 40, 56, 60);
                        border-radius: 10px;
                    }
                    QLabel#BIMPlanEditViewportStatusTitle {
                        color: rgb(25, 32, 38);
                        font-weight: 600;
                    }
                    QLabel#BIMPlanEditViewportStatusBody {
                        color: rgb(60, 68, 76);
                    }
                    """)

                layout = QtGui.QVBoxLayout(self)
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(2)

                self.title_label = QtGui.QLabel(self)
                self.title_label.setObjectName("BIMPlanEditViewportStatusTitle")
                self.body_label = QtGui.QLabel(self)
                self.body_label.setObjectName("BIMPlanEditViewportStatusBody")
                self.body_label.setWordWrap(True)
                self.body_label.setMaximumWidth(300)

                layout.addWidget(self.title_label)
                layout.addWidget(self.body_label)

                try:
                    self.host_widget.installEventFilter(self)
                except Exception:
                    pass

            def set_texts(self, title, body):
                self.title_label.setText(title)
                self.body_label.setText(body)
                self.adjustSize()
                self._reposition()
                self.show()
                self.raise_()

            def _reposition(self):
                host = self.host_widget
                if host is None:
                    return
                margin = 14
                max_width = max(180, host.width() - (margin * 2))
                self.setMaximumWidth(max_width)
                self.body_label.setMaximumWidth(max_width - 24)
                self.adjustSize()
                self.move(margin, margin)

            def eventFilter(self, watched, event):
                if watched is self.host_widget and event.type() in (
                    QtCore.QEvent.Resize,
                    QtCore.QEvent.Move,
                    QtCore.QEvent.Show,
                ):
                    self._reposition()
                return QtGui.QFrame.eventFilter(self, watched, event)

            def close_chip(self):
                host = self.host_widget
                if host is not None:
                    try:
                        host.removeEventFilter(self)
                    except Exception:
                        pass
                self.host_widget = None
                self.hide()
                self.deleteLater()

        return _Chip(session, host_widget)

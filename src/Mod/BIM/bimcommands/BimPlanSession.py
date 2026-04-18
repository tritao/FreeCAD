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

from contextlib import contextmanager
import math

import FreeCAD
import FreeCADGui
from bimplan import picking as plan_picking
from bimplan import performance as plan_performance
from bimplan import provider_runtime as plan_provider_runtime
from bimplan import selection as plan_selection
from bimplan import snap as plan_snap
from bimplan import symbol_edit as plan_symbol_edit
from bimplan import opening_edit as plan_opening_edit
from bimplan import targets as plan_targets
from bimplan import view as plan_view
from bimplan.context import PlanEditContext
from bimplan.hosts import _PlanEditCommandHost, _PlanEditWallHost
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays
from bimplan.registry import get_plan_edit_registry
from bimplan.ui.controls import PlanEditControlsWidget
from bimplan.ui.status_chip import _PlanEditViewportStatusChip

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
_PRIMARY_PLAN_TARGET_KINDS = ("wall", "opening", "symbol", "region", "space")
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
_SPACE_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Boundaries",
}
_REGION_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Points",
    "Scheme",
    "RegionType",
    "ParentSpace",
}
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
_PLAN_VISUAL_HOVERED_SPACE = "hovered_space"
_PLAN_VISUAL_HOVERED_REGION = "hovered_region"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
_PLAN_VISUAL_SELECTED_SPACE = "selected_space"
_PLAN_VISUAL_SELECTED_REGION = "selected_region"
_PLAN_VISUAL_SECONDARY_SELECTION = "secondary_selection"
_PLAN_VISUAL_SPACE_REGION_PICK = "space_region_pick"
_PLAN_VISUAL_WALL_GRIPS = "wall_grips"
_PLAN_VISUAL_WALL_EDIT_PREVIEW = "wall_edit_preview"
_PLAN_VISUAL_VIEW_SCALE = "view_scale"
_PLAN_VISUAL_ALL = "all"
_PLAN_VIEW_SCALE_REFRESH_DELAY_MS = 40
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
        self._selected_plan_target_kind = None
        self._selected_plan_target_obj = None
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self.hovered_space = None
        self.hovered_region = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._secondary_selected_plan_targets_state = []
        self._grip_trackers = []
        self._wall_grip_state = None
        self._wall_hover_trackers = []
        self._junction_node_trackers = []
        self._hovered_wall_opening_context_trackers = []
        self._opening_hover_trackers = []
        self._symbol_hover_trackers = []
        self._space_hover_trackers = []
        self._region_hover_trackers = []
        self._plan_overlay_geometry_cache = {
            "opening": {},
            "space": {},
            "region": {},
        }
        self._opening_overlay_screen_cache = {}
        self._opening_overlay_screen_cache_projection_key = None
        self._opening_overlay_trackers = []
        self._hovered_opening_overlay_dirty = False
        self._hovered_opening_overlay_render_state = None
        self._selected_opening_overlay_dirty = False
        self._selected_opening_overlay_render_state = None
        self._symbol_overlay_trackers = []
        self._space_overlay_trackers = []
        self._selected_space_overlay_dirty = True
        self._selected_space_overlay_geometry_key = None
        self._selected_space_overlay_segments = ()
        self._selected_space_overlay_render_state = None
        self._region_overlay_trackers = []
        self._secondary_selection_trackers = []
        self._space_region_pick_trackers = []
        self._selected_wall_opening_context_trackers = []
        self._opening_handle_trackers = []
        self._opening_handle_tracker_pool = []
        self._opening_handle_tracker_pool_queued = False
        self._selected_opening_handle_render_state = None
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
        self._space_separator_start = None
        self._space_separator_height = None
        self._space_separator_preview_trackers = []
        self._plan_region_points = []
        self._plan_region_parent_space = None
        self._plan_region_preview_trackers = []
        self._edit_wall_visibility = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._edit_space = None
        self._ignore_selection_changes = False
        self._mouse_moved_cb = None
        self._mouse_wheel_cb = None
        self._mouse_wheel_event_type = None
        self._mouse_pressed_cb = None
        self._consume_left_button_release = False
        self._key_pressed_cb = None
        self._overlay_refresh_queued = False
        self._view_scale_overlay_refresh_queued = False
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
        self._plan_perf_log_path = self._resolve_plan_perf_log_path()
        self._plan_perf_current_event = None
        self._plan_perf_sequence = 0
        app = QtGui.QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.begin_teardown)

    def _get_selected_target_for_kind(self, kind):
        return plan_selection.get_selected_target_for_kind(self, kind)

    def _set_selected_target_for_kind(self, kind, obj):
        return plan_selection.set_selected_target_for_kind(self, kind, obj)

    def _get_selected_plan_target_state(self):
        return plan_selection.get_selected_plan_target_state(
            self,
            _PRIMARY_PLAN_TARGET_KINDS,
        )

    def _set_selected_plan_target_state(self, kind=None, obj=None):
        return plan_selection.set_selected_plan_target_state(
            self,
            _PRIMARY_PLAN_TARGET_KINDS,
            kind=kind,
            obj=obj,
        )

    def _get_selected_plan_target_object(self, kind=None):
        return plan_selection.get_selected_plan_target_object(self, kind=kind)

    def _is_selected_plan_target(self, kind, obj=None):
        return plan_selection.is_selected_plan_target(self, kind, obj=obj)

    def _clear_selected_plan_target_if_matches(self, kind, obj):
        return plan_selection.clear_selected_plan_target_if_matches(self, kind, obj)

    def _get_plan_target_object_from_state(self, state_kind, state_obj, kind):
        if state_kind == kind:
            return state_obj
        return None

    def _selected_plan_target_changed(self, previous_kind, previous_obj, kind=None):
        current_kind, current_obj = self._get_selected_plan_target()
        if kind is None:
            return previous_kind != current_kind or previous_obj != current_obj
        previous_target = self._get_plan_target_object_from_state(previous_kind, previous_obj, kind)
        current_target = self._get_plan_target_object_from_state(current_kind, current_obj, kind)
        return previous_target != current_target

    @property
    def selected_wall(self):
        return self._get_selected_target_for_kind("wall")

    @selected_wall.setter
    def selected_wall(self, wall):
        self._set_selected_target_for_kind("wall", wall)

    @property
    def selected_opening(self):
        return self._get_selected_target_for_kind("opening")

    @selected_opening.setter
    def selected_opening(self, opening):
        self._set_selected_target_for_kind("opening", opening)

    @property
    def selected_symbol(self):
        return self._get_selected_target_for_kind("symbol")

    @selected_symbol.setter
    def selected_symbol(self, symbol):
        self._set_selected_target_for_kind("symbol", symbol)

    @property
    def selected_region(self):
        return self._get_selected_target_for_kind("region")

    @selected_region.setter
    def selected_region(self, region):
        self._set_selected_target_for_kind("region", region)

    @property
    def selected_space(self):
        return self._get_selected_target_for_kind("space")

    @selected_space.setter
    def selected_space(self, space):
        self._set_selected_target_for_kind("space", space)

    def _discard_stale_runtime_object(self, obj):
        if obj is self.view:
            self.view = None
            self.viewer = None
        elif obj is self.viewer:
            self.viewer = None

    def _get_runtime_attr(self, obj, attr_name):
        if obj is None:
            return None
        try:
            return getattr(obj, attr_name)
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(obj)
            return None

    def _is_live_document_object(self, obj):
        if obj is None:
            return False
        try:
            _ = obj.Name
            return True
        except (AttributeError, ReferenceError, RuntimeError):
            return False

    def _get_document_object_key(self, obj):
        if obj is None:
            return None
        try:
            return (
                getattr(getattr(obj, "Document", None), "Name", None),
                getattr(obj, "Name", None),
            )
        except Exception:
            return None

    def _get_plan_overlay_geometry_kinds_for_object(self, obj):
        return overlay_geometry.get_plan_overlay_geometry_kinds_for_object(self, obj)

    def _get_plan_overlay_geometry_cache_entry(self, kind, obj, create=False):
        return overlay_geometry.get_plan_overlay_geometry_cache_entry(
            self,
            kind,
            obj,
            create=create,
        )

    def _invalidate_plan_overlay_geometry_cache(self, obj=None, kinds=None):
        return overlay_geometry.invalidate_plan_overlay_geometry_cache(
            self,
            obj=obj,
            kinds=kinds,
        )

    def _get_cached_plan_overlay_geometry(self, kind, obj, field_name, compute):
        return overlay_geometry.get_cached_plan_overlay_geometry(
            self,
            kind,
            obj,
            field_name,
            compute,
        )

    def _sanitize_plan_target_references(self):
        changed = False
        for attr in (
            "selected_wall",
            "selected_opening",
            "selected_symbol",
            "selected_region",
            "selected_space",
            "hovered_wall",
            "hovered_opening",
            "hovered_symbol",
            "hovered_region",
            "hovered_space",
        ):
            obj = getattr(self, attr, None)
            if obj is None or self._is_live_document_object(obj):
                continue
            setattr(self, attr, None)
            changed = True
        normalized_secondary = self._normalize_plan_target_list(
            getattr(self, "_secondary_selected_plan_targets_state", [])
        )
        if normalized_secondary != getattr(self, "_secondary_selected_plan_targets_state", []):
            self._secondary_selected_plan_targets_state = normalized_secondary
            changed = True
        return changed

    def _resolve_plan_perf_log_path(self):
        return plan_performance.resolve_plan_perf_log_path(self)

    def _is_plan_perf_trace_enabled(self):
        return plan_performance.is_plan_perf_trace_enabled(self)

    def _plan_perf_describe_object(self, obj):
        return plan_performance.plan_perf_describe_object(self, obj)

    def _plan_perf_describe_target(self, kind, obj):
        return plan_performance.plan_perf_describe_target(self, kind, obj)

    def _plan_perf_coerce_value(self, value):
        return plan_performance.plan_perf_coerce_value(self, value)

    def _plan_perf_set_fields(self, **fields):
        return plan_performance.plan_perf_set_fields(self, **fields)

    def _plan_perf_count(self, name, delta=1):
        return plan_performance.plan_perf_count(self, name, delta=delta)

    def _plan_perf_note_error(self, scope, exc):
        return plan_performance.plan_perf_note_error(self, scope, exc)

    def _plan_perf_finalize_event(self, event, total_ms):
        return plan_performance.plan_perf_finalize_event(self, event, total_ms)

    def _plan_perf_write_event(self, event, total_ms):
        return plan_performance.plan_perf_write_event(self, event, total_ms)

    def _plan_perf_trace_event(self, name, **fields):
        return plan_performance.plan_perf_trace_event(self, name, **fields)

    def _plan_perf_trace_span(self, name, **fields):
        return plan_performance.plan_perf_trace_span(self, name, **fields)

    def enter(self):
        if not self.doc or not self.gui_doc:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
            )
            return False

        self.view = self.gui_doc.ActiveView
        get_viewer = self._get_runtime_attr(self.view, "getViewer")
        if self.view is None or get_viewer is None:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False

        try:
            self.viewer = get_viewer()
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(self.view)
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False
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
        self._refresh_primary_selected_plan_target()

        panel = PlanEditControlsWidget(self)
        self.attach_task_panel(panel)
        panel.refresh()
        self._queue_prime_opening_handle_tracker_pool()
        if self._is_plan_perf_trace_enabled():
            FreeCAD.Console.PrintMessage(
                translate("BIM_PlanEdit", "BIM Plan Edit perf trace: {path}\n").format(
                    path=self._plan_perf_log_path
                )
            )
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Entered BIM Plan Edit mode.\n"))
        return True

    @property
    def _plan_paper_rgb(self):
        return _PLAN_PAPER_RGB

    @property
    def _plan_view_locked_actions(self):
        return _PLAN_VIEW_LOCKED_ACTIONS

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return True
        if self.current_tool == "Pick Space Region":
            self._cancel_space_region_pick()
            return True
        if self.current_tool == "Region":
            self._cancel_plan_region_tool()
            return True
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
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
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
        if self.current_tool == "Set Space Text":
            self._edit_space = None
        if self.current_tool == "Pick Space Region":
            self._space_region_pick_boundaries = []
            self._space_region_candidates = []
            self._hovered_space_region_candidate = None
            self._space_region_pick_seed_space = None
        self._clear_hovered_wall_overlay()
        self._clear_junction_node_overlays()
        self._clear_hovered_wall_opening_context_overlay()
        self._clear_wall_grips()
        self._clear_hovered_opening_overlay()
        self._clear_hovered_symbol_overlay()
        self._clear_hovered_space_overlay()
        self._clear_hovered_region_overlay()
        self._clear_selected_opening_overlay()
        self._clear_selected_symbol_overlay()
        self._clear_selected_space_overlay()
        self._clear_selected_region_overlay()
        self._clear_space_region_pick_overlays()
        self._clear_secondary_selected_overlays()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_opening_handles()
        self._discard_opening_handle_tracker_pool()
        self._clear_selected_symbol_handles()
        self._clear_opening_move_preview()
        self._clear_symbol_edit_preview()
        self._clear_plan_region_preview()
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
        self._set_selected_plan_target_state()
        self._secondary_selected_plan_targets_state = []
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self.hovered_space = None
        self.hovered_region = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._edit_wall = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._plan_region_points = []
        self._plan_region_parent_space = None
        self._edit_space = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._junction_node_trackers = []
        self._preview_footprint_trackers = []
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._space_region_pick_trackers = []
        self._edit_wall_visibility = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None

    def _get_navigation_style(self):
        return plan_view.get_navigation_style(self)

    def _get_main_window(self):
        return plan_view.get_main_window(self)

    def _find_main_window_action(self, command_name):
        return plan_view.find_main_window_action(self, command_name)

    def _capture_view_action_state(self):
        return plan_view.capture_view_action_state(self, _PLAN_VIEW_LOCKED_ACTIONS)

    def _apply_locked_view_actions(self):
        return plan_view.apply_locked_view_actions(self, _PLAN_VIEW_LOCKED_ACTIONS)

    def _restore_locked_view_actions(self):
        return plan_view.restore_locked_view_actions(self)

    def _capture_navigation_flag(self, target, getter_name, state_key):
        return plan_view.capture_navigation_flag(self, target, getter_name, state_key)

    def _apply_navigation_flag(self, target, setter_name, state_key, enabled):
        return plan_view.apply_navigation_flag(self, target, setter_name, state_key, enabled)

    def _capture_navigation_state(self):
        return plan_view.capture_navigation_state(self)

    def _apply_plan_background_override(self):
        return plan_view.apply_plan_background_override(self, _PLAN_PAPER_RGB)

    def _clear_plan_background_override(self):
        return plan_view.clear_plan_background_override(self)

    def _apply_plan_navigation_profile(self):
        return plan_view.apply_plan_navigation_profile(self, _PLAN_VIEW_LOCKED_ACTIONS)

    def _restore_navigation_state(self):
        return plan_view.restore_navigation_state(self)

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
            self._cancel_space_separator_tool(refresh=False)
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
            self._discard_opening_handle_tracker_pool()
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

    def get_plan_provider_registry(self):
        return get_plan_edit_registry()

    def get_plan_provider_display_name(self, provider_id):
        return plan_provider_runtime.get_plan_provider_display_name(self, provider_id)

    def get_plan_edit_context(self):
        active_storey = self.active_storey
        return PlanEditContext(
            session=self,
            document_name=str(getattr(self.doc, "Name", "") or ""),
            active_storey_name=str(getattr(active_storey, "Name", "") or ""),
            active_storey_label=str(self.get_storey_label(active_storey) or ""),
            current_tool=str(self.current_tool or ""),
        )

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
        if self.current_tool == "Pick Space Region":
            self._cancel_space_region_pick()
            return
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        if self._has_active_plan_region_tool():
            self._cancel_plan_region_tool()
        if self._has_active_space_separator_tool():
            self._cancel_space_separator_tool()
        self._cancel_wall_edit()
        self._cancel_join_tool()

    def activate_wall_tool(self):
        from bimcommands import BimWall

        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._set_gui_selection([])
        self._start_embedded_tool("Wall", BimWall.Arch_Wall(), host_class=_PlanEditWallHost)

    def activate_rect_wall_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
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

    def activate_plan_region_tool(self):
        parent_space = self._get_selected_plan_target_object("space")
        self._cancel_space_region_pick(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_region_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._clear_plan_region_preview()
        self._plan_region_points = []
        self._plan_region_parent_space = parent_space
        self.current_tool = "Region"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_plan_region_point,
            movecallback=self._update_plan_region_preview,
            title=translate("BIM_PlanEdit", "First region point"),
        )
        self._refresh_task_panel_status()

    def activate_space_separator_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._clear_space_separator_preview()
        self._space_separator_start = None
        self._space_separator_height = self._get_wall_defaults()["height"]
        self.current_tool = "Separator"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_space_separator_point,
            title=translate("BIM_PlanEdit", "Separator start point"),
        )
        self._refresh_task_panel_status()

    def activate_space_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit(refresh=False)
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        return self._create_space_from_current_selection()

    def activate_move_tool(self):
        from draftguitools import gui_move

        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)

        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._set_hovered_opening(None)
        self._set_hovered_wall(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)

        wall = self._get_selected_plan_target_object("wall")
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
        self._sync_secondary_selected_overlays()
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
        if not self._is_plan_selectable_wall(wall) or self._is_selected_plan_target("wall", wall):
            return None
        return wall

    def _get_plan_candidate_joint(self, target_wall=None):
        import ArchWallJoinUtils

        source_wall = self._get_selected_plan_target_object("wall")
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
        source_wall = self._get_selected_plan_target_object("wall")
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
        wall = self._get_selected_plan_target_object("wall")
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
        wall = self._get_selected_plan_target_object("wall")
        if not wall:
            return False
        return not getattr(wall, "Base", None) and self.is_selected_wall_endpoint_editable()

    def apply_plan_view(self, fit=True):
        return plan_view.apply_plan_view(self, fit=fit)

    def restore_state(self):
        return plan_view.restore_state(self)

    def _capture_state(self):
        return plan_view.capture_state(self)

    def get_interaction_plane(self):
        return plan_view.get_interaction_plane(self)

    def _project_plan_point(self, point):
        return plan_view.project_plan_point(self, point)

    def _get_wall_defaults(self):
        from draftutils import params

        return {
            "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
            "width": params.get_param_arch("WallWidth"),
            "height": params.get_param_arch("WallHeight"),
            "offset": params.get_param_arch("WallOffset"),
        }

    def _get_plan_view_height(self):
        return plan_view.get_plan_view_height(self)

    def _get_plan_overlay_scale(self):
        return plan_view.get_plan_overlay_scale(self)

    def _scaled_line_width(self, base_width):
        return plan_view.scaled_line_width(self, base_width)

    def _scaled_marker_size(self, base_size):
        return plan_view.scaled_marker_size(self, base_size)

    def _get_plan_view_units_per_pixel(self):
        return plan_view.get_plan_view_units_per_pixel(self)

    def _get_plan_projection_cache_key(self):
        return plan_view.get_plan_projection_cache_key(self)

    def _invalidate_opening_overlay_screen_cache(self):
        return overlay_geometry.invalidate_opening_overlay_screen_cache(self)

    def _apply_plan_snap_profile(self):
        return plan_snap.apply_plan_snap_profile(_PLAN_EDIT_SNAP_SET)

    def _restore_snap_profile(self):
        return plan_snap.restore_snap_profile()

    def _push_opening_move_snap_profile(self):
        return plan_snap.push_opening_move_snap_profile(self, _OPENING_MOVE_SNAP_SET)

    def _pop_opening_move_snap_profile(self):
        return plan_snap.pop_opening_move_snap_profile(self)

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

    def _is_direct_plan_equipment_object(self, obj):
        if not obj:
            return False
        try:
            import Draft

            if Draft.getType(obj) == "Equipment":
                return True
        except Exception:
            pass
        proxy = getattr(obj, "Proxy", None)
        return getattr(proxy, "Type", None) == "Equipment"

    def _get_direct_plan_symbol_owner(self, obj):
        if not obj:
            return None
        for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
            if not self._is_direct_plan_equipment_object(parent):
                continue
            if obj == getattr(parent, "Base", None):
                return parent
            if obj in (getattr(parent, "PlanSymbols", None) or []):
                return parent
        return None

    def _get_plan_semantic_object(self, obj):
        current = obj
        seen = set()
        while current:
            if not self._is_live_document_object(current):
                current = None
                break
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
        owner = self._get_direct_plan_symbol_owner(current)
        return owner or current or obj

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
        return self._is_direct_plan_equipment_object(self._get_plan_semantic_object(obj))

    def _has_direct_plan_symbols(self, obj):
        if not obj:
            return False
        try:
            if "PlanSymbols" not in (getattr(obj, "PropertiesList", []) or []):
                return False
            return any(symbol is not None for symbol in (getattr(obj, "PlanSymbols", []) or []))
        except Exception:
            return False

    def _is_plan_symbol_instance(self, obj):
        if not obj:
            return False
        if self._is_hidden_library_definition_object(obj):
            return False
        if not self._is_plan_equipment_object(obj):
            return False
        if getattr(obj, "TypeId", "") == "App::Link":
            return True
        semantic_obj = self._get_plan_semantic_object(obj)
        return obj == semantic_obj and self._has_direct_plan_symbols(semantic_obj)

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
        if self._is_plan_region_object(obj):
            return True
        if self._is_plan_space_separator_object(obj):
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
        semantic_obj = self._get_plan_semantic_object(obj)
        if semantic_obj is not None and self._is_symbol_visual_dependency(semantic_obj, obj):
            try:
                view_object.Selectable = True
            except Exception:
                pass
            return
        # Spaces and plan regions are selected through Plan Edit's semantic
        # picking paths. Leaving their native 3D view objects selectable lets
        # the viewer replace the intended target with enclosing face hits on
        # button release, especially for nested region-in-space cases.
        if self._is_plan_custom_pick_only_object(semantic_obj or obj):
            try:
                view_object.Selectable = False
            except Exception:
                pass
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
        try:
            self.view.setActiveObject("Arch", None)
        except Exception:
            pass
        try:
            self.view.setActiveObject("NativeIFC", None)
        except Exception:
            pass
        if obj is None:
            return
        context = "Arch"
        if getattr(obj, "IfcType", "") == "Building Storey":
            context = "NativeIFC"
        try:
            self.view.setActiveObject(context, obj)
        except Exception:
            pass

    def _sync_active_plan_target_object(self):
        if not self.view:
            return
        target_kind, target_obj = self._get_selected_plan_target()
        del target_kind
        if target_obj is not None:
            self._set_active_object(target_obj)
            return
        if self.active_storey is not None:
            self._set_active_object(self.active_storey)
            return
        self._set_active_object(None)

    def _attach_selection_observer(self):
        return plan_selection.attach_selection_observer(self)

    def _detach_selection_observer(self):
        return plan_selection.detach_selection_observer(self)

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
        return plan_targets.is_plan_selectable_wall(self, obj)

    def _is_plan_space_object(self, obj):
        return plan_targets.is_plan_space_object(self, obj)

    def _is_plan_custom_pick_only_object(self, obj):
        return plan_targets.is_plan_custom_pick_only_object(self, obj)

    def _is_plan_space_separator_object(self, obj):
        return plan_targets.is_plan_space_separator_object(self, obj)

    def _is_plan_region_object(self, obj):
        return plan_targets.is_plan_region_object(self, obj)

    def _get_gui_selection_ex(self):
        return plan_selection.get_gui_selection_ex()

    def _get_gui_selection(self):
        return plan_selection.get_gui_selection()

    def _get_space_reference_point(self, space):
        if not self._is_plan_space_object(space):
            return None
        shape = getattr(space, "Shape", None)
        if shape and hasattr(shape, "CenterOfMass"):
            try:
                return self._project_plan_point(shape.CenterOfMass)
            except Exception:
                pass
        placement = getattr(space, "Placement", None)
        if placement is not None:
            try:
                return self._project_plan_point(placement.Base)
            except Exception:
                pass
        return None

    def _get_space_boundary_reference_point(self, selection_ex, fallback_space=None):
        points = []
        for selection in selection_ex or []:
            obj = getattr(selection, "Object", None)
            if not obj or obj == fallback_space:
                continue
            subobjects = list(getattr(selection, "SubObjects", []) or [])
            added_subobject_center = False
            for subobject in subobjects:
                center = getattr(subobject, "CenterOfMass", None)
                if center is None:
                    continue
                try:
                    points.append(FreeCAD.Vector(center.x, center.y, center.z))
                    added_subobject_center = True
                except Exception:
                    continue
            if added_subobject_center:
                continue
            shape = getattr(obj, "Shape", None)
            bound_box = getattr(shape, "BoundBox", None)
            center = getattr(bound_box, "Center", None) if bound_box is not None else None
            if center is None:
                continue
            try:
                points.append(FreeCAD.Vector(center.x, center.y, center.z))
            except Exception:
                continue
        if points:
            total = FreeCAD.Vector()
            for point in points:
                total = total.add(point)
            return total.multiply(1.0 / float(len(points)))
        return self._get_space_reference_point(fallback_space)

    def _get_space_boundary_entries(self, space):
        if not self._is_plan_space_object(space):
            return []
        import ArchSpace

        entries = []
        for boundary in getattr(space, "Boundaries", []) or []:
            try:
                obj = boundary[0]
                subnames = boundary[1]
            except Exception:
                continue
            entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
        return ArchSpace.normalizeBoundaryLinks(entries)

    def _space_boundary_key(self, boundary):
        import ArchSpace

        obj, subnames = boundary
        return (
            getattr(obj, "Name", None),
            tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
        )

    def _get_selected_space_boundary_links(self, fallback_space=None):
        import ArchSpace

        selection_ex = self._get_gui_selection_ex()
        reference_point = (
            self._get_space_reference_point(fallback_space)
            if fallback_space is not None
            else self._get_space_boundary_reference_point(selection_ex)
        )
        entries = []
        for selection in selection_ex:
            obj = self._get_plan_semantic_object(getattr(selection, "Object", None))
            if not obj:
                continue
            entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
        return ArchSpace.resolveBoundaryLinks(
            entries,
            reference_point=reference_point,
            exclude_objects=(fallback_space,) if fallback_space is not None else None,
        )

    def _get_space_region_seed_targets(self, targets=None):
        targets = list(targets if targets is not None else self._get_selected_plan_targets())
        if not targets:
            return (None, [])

        space_targets = [
            target_obj for target_kind, target_obj in targets if target_kind == "space"
        ]
        if len(space_targets) != 1:
            return (None, [])

        if len(targets) == 1:
            boundary_links = self._get_selected_space_boundary_links(
                fallback_space=space_targets[0]
            )
            if boundary_links:
                return (space_targets[0], [])
            return (None, [])

        wall_targets = [
            (target_kind, target_obj)
            for target_kind, target_obj in targets
            if target_kind == "wall"
        ]
        if len(wall_targets) != len(targets) - 1:
            return (None, [])

        return (space_targets[0], wall_targets)

    def _get_selected_space_region_seed(self, targets=None):
        region_seed_space, _wall_targets = self._get_space_region_seed_targets(targets)
        return region_seed_space

    def _copy_shape_without_element_map(self, shape):
        if shape is None:
            return None
        try:
            return shape.copy(noElementMap=True)
        except TypeError:
            try:
                clean_shape = shape.copy()
                if getattr(clean_shape, "ElementMapSize", 0):
                    clean_shape.clearElementMap()
                return clean_shape
            except Exception:
                return shape
        except Exception:
            return shape

    def _get_space_creation_request(self, targets=None):
        targets = targets if targets is not None else self._get_selected_plan_targets()
        if not targets:
            return None

        label = None
        region_seed_space = self._get_selected_space_region_seed(targets)
        if region_seed_space is not None:
            boundaries = self._get_selected_space_boundary_links(fallback_space=region_seed_space)
            label = getattr(region_seed_space, "Label", None)
        elif all(target_kind == "wall" for target_kind, _target_obj in targets):
            boundaries = self._get_selected_space_boundary_links()
        else:
            return None

        return {
            "targets": targets,
            "label": label,
            "region_seed_space": region_seed_space,
            "boundaries": boundaries,
        }

    def _get_existing_space_region_filter_spaces(self, exclude=None):
        if not self.doc:
            return []
        active_storey_name = getattr(self.active_storey, "Name", None)
        exclude_space = self._get_plan_semantic_object(exclude) if exclude else None
        exclude_name = getattr(exclude_space, "Name", None)

        spaces = []
        seen = set()
        for obj in self.doc.Objects:
            semantic_obj = self._get_plan_semantic_object(obj)
            name = getattr(semantic_obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            if name == exclude_name or not self._is_plan_space_object(semantic_obj):
                continue
            if active_storey_name is not None:
                storeys = self._get_object_storeys(semantic_obj)
                if storeys and not any(parent.Name == active_storey_name for parent in storeys):
                    continue
            spaces.append(semantic_obj)
        return spaces

    def _get_xy_bound_box_iou(self, first_shape, second_shape):
        first_bb = getattr(first_shape, "BoundBox", None)
        second_bb = getattr(second_shape, "BoundBox", None)
        if first_bb is None or second_bb is None:
            return 0.0

        x_overlap = min(float(first_bb.XMax), float(second_bb.XMax)) - max(
            float(first_bb.XMin), float(second_bb.XMin)
        )
        y_overlap = min(float(first_bb.YMax), float(second_bb.YMax)) - max(
            float(first_bb.YMin), float(second_bb.YMin)
        )
        if x_overlap <= 0.000001 or y_overlap <= 0.000001:
            return 0.0

        intersection_area = x_overlap * y_overlap
        first_area = max(
            0.0,
            (float(first_bb.XMax) - float(first_bb.XMin))
            * (float(first_bb.YMax) - float(first_bb.YMin)),
        )
        second_area = max(
            0.0,
            (float(second_bb.XMax) - float(second_bb.XMin))
            * (float(second_bb.YMax) - float(second_bb.YMin)),
        )
        union_area = first_area + second_area - intersection_area
        if union_area <= 0.000001:
            return 0.0
        return intersection_area / union_area

    def _is_space_region_candidate_claimed(self, candidate, spaces, overlap_iou_tolerance=0.9):
        if not isinstance(candidate, dict):
            return False
        candidate_face = candidate.get("face")
        sample_point = candidate.get("sample_point")
        if candidate_face is None or sample_point is None:
            return False

        for space in spaces or []:
            footprint_faces = self._get_space_footprint_faces(space)
            if not footprint_faces:
                continue
            for footprint_face in footprint_faces:
                try:
                    test_point = FreeCAD.Vector(
                        sample_point.x,
                        sample_point.y,
                        float(footprint_face.BoundBox.ZMin),
                    )
                    if not footprint_face.isInside(test_point, 0.001, True):
                        continue
                except Exception:
                    continue
                if self._get_xy_bound_box_iou(
                    candidate_face,
                    footprint_face,
                ) >= float(overlap_iou_tolerance):
                    return True
        return False

    def _filter_claimed_space_region_candidates(self, candidates, exclude_space=None):
        candidates = list(candidates or [])
        if not candidates:
            return candidates, 0

        spaces = self._get_existing_space_region_filter_spaces(exclude=exclude_space)
        if not spaces:
            return candidates, 0

        filtered = []
        skipped = 0
        for candidate in candidates:
            if self._is_space_region_candidate_claimed(candidate, spaces):
                skipped += 1
                continue
            filtered.append(candidate)
        return filtered, skipped

    def _get_space_region_candidate_report(
        self,
        boundaries,
        label=None,
        seed_space=None,
    ):
        import ArchSpace

        report = ArchSpace.getBoundaryRegionCandidates(
            boundaries,
            label=label,
            seed_space=seed_space,
        )
        report = dict(report or {})
        candidates = list(report.get("candidates", []) or [])
        skipped_claimed = 0
        if seed_space is None:
            candidates, skipped_claimed = self._filter_claimed_space_region_candidates(candidates)
        report["candidates"] = candidates
        report["candidate_count"] = len(candidates)
        report["skipped_claimed_candidate_count"] = skipped_claimed
        return report

    def _report_space_region_candidate_failure(self, report):
        skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
        if skipped_claimed and not int(report.get("candidate_count", 0) or 0):
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "All enclosed regions are already covered by existing spaces.\n",
                )
            )
            return

        message = str(report.get("message") or "").strip()
        details = [
            str(detail).strip() for detail in report.get("details", []) if str(detail).strip()
        ]
        if message:
            FreeCAD.Console.PrintError(message + "\n")
            for detail in details:
                FreeCAD.Console.PrintError(f"  - {detail}\n")
            return

        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Failed to derive enclosed space regions from the current selection.\n",
            )
        )

    def _get_plan_target_kind_for_object(self, obj):
        return plan_targets.get_plan_target_kind_for_object(self, obj)

    def _get_plan_target_for_object(self, obj, parent_obj=None):
        return plan_targets.get_plan_target_for_object(self, obj, parent_obj=parent_obj)

    def _get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        return plan_picking.get_screen_distance_sq_to_segment(self, mouse_pos, start, end)

    def _get_screen_distance_sq_to_projected_segment(self, cursor_xy, start_xy, end_xy):
        return plan_picking.get_screen_distance_sq_to_projected_segment(
            cursor_xy,
            start_xy,
            end_xy,
        )

    def _pick_plan_symbol_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_picking.pick_plan_symbol_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _pick_plan_opening_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_picking.pick_plan_opening_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _pick_plan_space_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_picking.pick_plan_space_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _pick_plan_region_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_picking.pick_plan_region_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _get_region_pick_polylines(self, region):
        return plan_picking.get_region_pick_polylines(self, region)

    def _xy_polygon_area(self, polyline):
        return plan_picking.xy_polygon_area(polyline)

    def _xy_point_in_polygon(self, point, polyline, tolerance=1e-9):
        return plan_picking.xy_point_in_polygon(point, polyline, tolerance=tolerance)

    def _pick_plan_region_target_from_polylines(self, mouse_pos):
        return plan_picking.pick_plan_region_target_from_polylines(self, mouse_pos)

    def _pick_plan_target_from_footprint_faces(
        self, mouse_pos, is_target, get_faces, target_label="target"
    ):
        return plan_picking.pick_plan_target_from_footprint_faces(
            self,
            mouse_pos,
            is_target,
            get_faces,
            target_label=target_label,
        )

    def _pick_plan_space_target_from_footprints(self, mouse_pos):
        return plan_picking.pick_plan_space_target_from_footprints(self, mouse_pos)

    def _pick_plan_region_target_from_footprints(self, mouse_pos):
        return plan_picking.pick_plan_region_target_from_footprints(self, mouse_pos)

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
        return plan_selection.set_pending_selected_plan_target(self, kind=kind, obj=obj)

    def _consume_pending_selected_plan_target(self):
        return plan_selection.consume_pending_selected_plan_target(self)

    def _get_selected_plan_target(self):
        return plan_selection.get_selected_plan_target(self)

    def _get_first_plan_target_from_selection(self, selection):
        return plan_selection.get_first_plan_target_from_selection(self, selection)

    def _is_valid_plan_target(self, kind, obj):
        return plan_selection.is_valid_plan_target(self, kind, obj)

    def _get_plan_target_state_key(self, kind, obj):
        return plan_selection.get_plan_target_state_key(kind, obj)

    def _normalize_plan_target_list(self, targets):
        return plan_selection.normalize_plan_target_list(self, targets)

    def _normalize_plan_targets_from_selection(self, selection):
        return plan_selection.normalize_plan_targets_from_selection(self, selection)

    def _set_secondary_selected_plan_targets(self, targets, primary_kind=None, primary_obj=None):
        return plan_selection.set_secondary_selected_plan_targets(
            self,
            targets,
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def _sync_secondary_selected_plan_targets_from_selection(
        self, selection, primary_kind=None, primary_obj=None
    ):
        return plan_selection.sync_secondary_selected_plan_targets_from_selection(
            self,
            selection,
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def _sync_secondary_selected_plan_targets_from_gui_selection(
        self, primary_kind=None, primary_obj=None
    ):
        return plan_selection.sync_secondary_selected_plan_targets_from_gui_selection(
            self,
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    @contextmanager
    def _selection_changes_suppressed(self):
        with plan_selection.selection_changes_suppressed(self):
            yield

    def _set_gui_selection(self, selection):
        return plan_selection.set_gui_selection(self, selection)

    def _set_gui_selection_object(self, obj):
        return plan_selection.set_gui_selection_object(self, obj)

    def _add_gui_selection_object(self, obj):
        return plan_selection.add_gui_selection_object(obj)

    def _get_secondary_selected_plan_targets(self):
        return plan_selection.get_secondary_selected_plan_targets(self)

    def _format_plan_target_count_label(self, kind, count):
        labels = {
            "wall": (translate("BIM_PlanEdit", "wall"), translate("BIM_PlanEdit", "walls")),
            "opening": (
                translate("BIM_PlanEdit", "opening"),
                translate("BIM_PlanEdit", "openings"),
            ),
            "symbol": (translate("BIM_PlanEdit", "symbol"), translate("BIM_PlanEdit", "symbols")),
            "region": (translate("BIM_PlanEdit", "region"), translate("BIM_PlanEdit", "regions")),
            "space": (translate("BIM_PlanEdit", "space"), translate("BIM_PlanEdit", "spaces")),
        }
        singular, plural = labels.get(
            kind,
            (translate("BIM_PlanEdit", "item"), translate("BIM_PlanEdit", "items")),
        )
        return "{} {}".format(count, singular if count == 1 else plural)

    def _format_space_region_candidate_area(self, candidate):
        area = float((candidate or {}).get("area", 0.0) or 0.0)
        if area <= 0.0:
            return ""
        try:
            quantity = FreeCAD.Units.Quantity(area, "mm^2")
            return quantity.UserString
        except Exception:
            return "{:.3f} m^2".format(area / 1000000.0)

    def _summarize_plan_targets(self, targets):
        counts = {}
        for target_kind, _target_obj in targets or []:
            counts[target_kind] = counts.get(target_kind, 0) + 1
        parts = [
            self._format_plan_target_count_label(kind, counts[kind])
            for kind in ("wall", "opening", "symbol", "region", "space")
            if counts.get(kind)
        ]
        return ", ".join(parts)

    def _get_selected_plan_targets(self):
        return plan_selection.get_selected_plan_targets(self)

    def _get_plan_text_property(self, obj, property_names, default=""):
        return plan_targets.get_plan_text_property(obj, property_names, default=default)

    def _get_plan_float_property(self, obj, property_names):
        return plan_targets.get_plan_float_property(obj, property_names)

    def _normalize_plan_requirement_tags(self, value):
        return plan_targets.normalize_plan_requirement_tags(value)

    def _get_plan_host_ref(self, obj):
        return plan_targets.get_plan_host_ref(self, obj)

    def _make_plan_target_record(self, kind, obj, selected_keys=None, primary_key=None):
        return plan_targets.make_plan_target_record(
            self,
            kind,
            obj,
            selected_keys=selected_keys,
            primary_key=primary_key,
        )

    def get_plan_targets(self, selected_only=False):
        return plan_targets.get_plan_targets(self, selected_only=selected_only)

    def resolve_plan_target_object(self, target):
        return plan_targets.resolve_plan_target_object(self, target)

    def resolve_plan_semantic_object(self, target):
        return plan_targets.resolve_plan_semantic_object(self, target)

    def _build_plan_semantic_record(self, target_kind, target_obj):
        return plan_provider_runtime.build_plan_semantic_record(
            self,
            target_kind,
            target_obj,
        )

    def get_plan_semantic_records(self, targets=None):
        return plan_provider_runtime.get_plan_semantic_records(self, targets=targets)

    def _get_plan_provider_id(self, provider):
        return plan_provider_runtime.get_plan_provider_id(provider)

    def _coerce_plan_provider_results(self, result):
        return plan_provider_runtime.coerce_plan_provider_results(result)

    def _normalize_plan_provider_action(self, provider_id, action):
        return plan_provider_runtime.normalize_plan_provider_action(provider_id, action)

    def _normalize_plan_provider_issue(self, provider_id, issue):
        return plan_provider_runtime.normalize_plan_provider_issue(self, provider_id, issue)

    def _normalize_plan_provider_suggestion(self, provider_id, suggestion):
        return plan_provider_runtime.normalize_plan_provider_suggestion(
            self,
            provider_id,
            suggestion,
        )

    def _normalize_plan_provider_section(self, provider_id, section):
        return plan_provider_runtime.normalize_plan_provider_section(
            self,
            provider_id,
            section,
        )

    def _normalize_plan_provider_overlay(self, provider_id, overlay):
        return plan_provider_runtime.normalize_plan_provider_overlay(provider_id, overlay)

    def _collect_plan_provider_contributions(self, method_name, normalizer):
        return plan_provider_runtime.collect_plan_provider_contributions(
            self,
            method_name,
            normalizer,
        )

    def get_plan_provider_issues(self):
        return self._collect_plan_provider_contributions(
            "get_issues",
            self._normalize_plan_provider_issue,
        )

    def get_plan_provider_suggestions(self):
        return self._collect_plan_provider_contributions(
            "get_suggestions",
            self._normalize_plan_provider_suggestion,
        )

    def get_plan_provider_inspector_sections(self):
        return self._collect_plan_provider_contributions(
            "get_inspector_sections",
            self._normalize_plan_provider_section,
        )

    def get_plan_provider_overlays(self):
        return self._collect_plan_provider_contributions(
            "get_overlays",
            self._normalize_plan_provider_overlay,
        )

    def execute_plan_provider_action(self, provider_id, action_key, transaction_label=""):
        return plan_provider_runtime.execute_plan_provider_action(
            self,
            provider_id,
            action_key,
            transaction_label=transaction_label,
        )

    def _get_space_preflight_report(self, targets=None):
        if self.current_tool != "Select":
            return None

        request = self._get_space_creation_request(targets=targets)
        if not request:
            return None

        import ArchSpace

        return ArchSpace.analyzeBoundaryLinks(
            request["boundaries"],
            label=request["label"],
            seed_space=request["region_seed_space"],
        )

    def _format_space_preflight_text(self, report):
        if not report:
            return ""

        if report.get("valid"):
            inner_void_count = int(report.get("inner_void_count", 0) or 0)
            if inner_void_count <= 0:
                return translate("BIM_PlanEdit", "Space preflight: Valid space")
            if inner_void_count == 1:
                return translate("BIM_PlanEdit", "Space preflight: Valid space with 1 inner void")
            return translate(
                "BIM_PlanEdit", "Space preflight: Valid space with {count} inner voids"
            ).format(count=inner_void_count)

        code = report.get("code")
        status_map = {
            "empty": translate(
                "BIM_PlanEdit", "Space preflight: Select room-bounding walls or faces"
            ),
            "unusable_boundaries": translate(
                "BIM_PlanEdit", "Space preflight: No usable boundary faces"
            ),
            "no_height": translate("BIM_PlanEdit", "Space preflight: Boundaries have no height"),
            "no_intersection": translate(
                "BIM_PlanEdit", "Space preflight: Boundaries miss the plan cut"
            ),
            "open_loop": translate("BIM_PlanEdit", "Space preflight: Open loop"),
            "multiple_regions": translate(
                "BIM_PlanEdit", "Space preflight: Multiple enclosed regions"
            ),
            "nested_islands": translate(
                "BIM_PlanEdit", "Space preflight: Nested islands are not supported"
            ),
            "invalid_solid": translate(
                "BIM_PlanEdit", "Space preflight: Selection cannot become one space"
            ),
        }
        status = status_map.get(
            code,
            translate("BIM_PlanEdit", "Space preflight: Selection cannot become one space"),
        )
        details = [
            str(detail).strip() for detail in report.get("details", []) if str(detail).strip()
        ]
        if details:
            return "{}\n{}".format(status, details[0])
        return status

    def _get_plan_selection_summary_text(self):
        if self.current_tool != "Select":
            return ""
        targets = self._get_selected_plan_targets()
        preflight_text = self._format_space_preflight_text(
            self._get_space_preflight_report(targets)
        )
        if len(targets) <= 1:
            return preflight_text
        region_seed_space, wall_targets = self._get_space_region_seed_targets(targets)
        if region_seed_space is not None and wall_targets:
            summary = translate("BIM_PlanEdit", "Boundary candidates: {summary}").format(
                summary=self._summarize_plan_targets(wall_targets)
            )
        else:
            summary = translate("BIM_PlanEdit", "Selection set: {summary}").format(
                summary=self._summarize_plan_targets(targets)
            )
        if preflight_text:
            return "{}\n{}".format(summary, preflight_text)
        return summary

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
        if self._is_valid_plan_target(kind, obj):
            self._set_selected_plan_target_state(kind, obj)
        else:
            self._set_selected_plan_target_state()
            kind = None
            obj = None
        self._sync_secondary_selected_plan_targets_from_gui_selection(
            primary_kind=kind,
            primary_obj=obj,
        )
        self._clear_plan_relation_status()
        self._sync_active_plan_target_object()
        if pending_restore:
            self._set_pending_selected_plan_target(kind, obj)
        else:
            self._set_pending_selected_plan_target()
        if not self._tearing_down:
            self._sync_junction_node_overlays()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_space_overlay()
            self._sync_hovered_region_overlay()

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
        wall = self._get_selected_plan_target_object("wall")
        if not wall:
            return
        self._clear_wall_grips()
        self._clear_selected_plan_target_if_matches("wall", wall)
        self._set_gui_selection([])
        self._refresh_task_panel_status()

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        """Drop current selected-wall UI state before another tool mutates the host wall."""

        if self._tearing_down:
            return
        if wall is None:
            wall = self._get_selected_plan_target_object("wall")
        if wall is None:
            return
        if not self._is_selected_plan_target("wall", wall):
            return
        self._pending_selected_wall_reset = False
        self._clear_wall_grips()
        self._clear_selected_plan_target_if_matches("wall", wall)
        if clear_gui_selection:
            self._set_gui_selection([])
        self._refresh_task_panel_status()

    def _register_edit_callbacks(self):
        return plan_view.register_edit_callbacks(self)

    def _unregister_edit_callbacks(self):
        return plan_view.unregister_edit_callbacks(self)

    def _sync_primary_selected_plan_target_visuals(self, previous_kind=None, previous_obj=None):
        with self._plan_perf_trace_span("sync_primary_selected_plan_target_visuals"):
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "opening"
            ):
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "symbol"
            ):
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "region"
            ):
                self._sync_selected_region_overlay()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "space"
            ):
                self._sync_selected_space_overlay()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_opening_overlay()
            self._sync_hovered_space_overlay()
            self._sync_hovered_region_overlay()
            self._sync_secondary_selected_overlays()
            self._sync_active_plan_target_object()
            self._refresh_task_panel_status()

    def _refresh_selected_plan_target(self):
        return plan_selection.refresh_selected_plan_target(self)

    def _refresh_primary_selected_plan_target(self):
        self._refresh_selected_plan_target()

    def _refresh_selected_wall(self):
        # Compatibility wrapper for older tests and callers.
        self._refresh_primary_selected_plan_target()

    def _start_embedded_tool(self, tool_name, command, host_class=_PlanEditCommandHost):
        self.current_tool = tool_name
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_region(None)
        self._sync_secondary_selected_overlays()
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
        self._sync_selected_space_overlay()

    def _cancel_join_tool(self, refresh=True):
        if self.current_tool != "Join":
            return False
        selected_wall = self._get_selected_plan_target_object("wall")
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
        self._set_gui_selection_object(obj)

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
        self._sync_selected_space_overlay()
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
            self._set_gui_selection(walls)
        except Exception:
            pass

        self._cancel_rect_wall_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_primary_selected_plan_target()
        self._refresh_task_panel_status()

    def _has_active_space_separator_tool(self):
        return self._space_separator_start is not None or self.current_tool == "Separator"

    def _has_active_plan_region_tool(self):
        return bool(self._plan_region_points) or self.current_tool == "Region"

    def _clear_plan_region_preview(self):
        self._finalize_trackers(self._plan_region_preview_trackers)
        self._plan_region_preview_trackers = []

    def _cancel_plan_region_tool(self, refresh=True):
        if not self._has_active_plan_region_tool():
            return False
        self._stop_snapper()
        self._clear_plan_region_preview()
        self._plan_region_points = []
        self._plan_region_parent_space = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._sync_selected_region_overlay()
        self._sync_selected_space_overlay()
        return True

    def _get_plan_region_close_tolerance(self):
        units_per_pixel = self._get_plan_view_units_per_pixel()
        if units_per_pixel is None:
            return 120.0
        return max(120.0, float(units_per_pixel) * 12.0)

    def _get_plan_region_preview_segments(self, point=None):
        points = [FreeCAD.Vector(item) for item in (self._plan_region_points or [])]
        if point is not None:
            point = self._project_plan_point(point)
            if point is not None and (not points or point.distanceToPoint(points[-1]) > 0.000001):
                points.append(point)
        segments = []
        for start, end in zip(points, points[1:]):
            if start.distanceToPoint(end) <= 0.000001:
                continue
            segments.append((start, end, False))
        if len(points) >= 3 and points[-1].distanceToPoint(points[0]) > 0.000001:
            segments.append((points[-1], points[0], True))
        return segments

    def _update_plan_region_preview(self, point, info):
        del info
        segments = self._get_plan_region_preview_segments(point)
        self._clear_plan_region_preview()
        if not segments:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        color = (0.86, 0.48, 0.12)
        width = self._scaled_line_width(2)
        for index, (start, end, dotted) in enumerate(segments):
            tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "plan_region_preview:{}".format(index),
                dotted=dotted,
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            self._plan_region_preview_trackers.append(tracker)

    def _create_plan_region(self, points):
        import Arch

        region = None
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Plan Region"))
        try:
            region = Arch.makePlanRegion(
                points=points,
                parent_space=self._plan_region_parent_space,
            )
            if not region:
                raise RuntimeError("Unable to create plan region")
            self._add_object_to_active_storey(region)
            self.doc.recompute()
            if not self._get_region_footprint_faces(region):
                raise RuntimeError("Plan region has no valid footprint")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return region

    def _finalize_plan_region(self):
        if len(self._plan_region_points) < 3:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Place at least three points before finishing the region.\n",
                )
            )
            return False
        try:
            region = self._create_plan_region(self._plan_region_points)
        except Exception:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the plan region.\n")
            )
            return False

        self._register_plan_object(region)
        self._cancel_plan_region_tool(refresh=False)
        self._restore_selected_region(region)
        return True

    def _handle_plan_region_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_plan_region_tool()
            return

        point = self._project_plan_point(point)
        if point is None:
            self._cancel_plan_region_tool()
            return

        if self._plan_region_points:
            if point.distanceToPoint(self._plan_region_points[-1]) <= 0.000001:
                FreeCADGui.Snapper.getPoint(
                    callback=self._handle_plan_region_point,
                    movecallback=self._update_plan_region_preview,
                    last=self._plan_region_points[-1],
                    title=translate("BIM_PlanEdit", "Next region point"),
                    mode="line",
                )
                return
            if (
                len(self._plan_region_points) >= 3
                and point.distanceToPoint(self._plan_region_points[0])
                <= self._get_plan_region_close_tolerance()
            ):
                self._finalize_plan_region()
                return

        self._plan_region_points.append(point)
        self._update_plan_region_preview(None, None)
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_plan_region_point,
            movecallback=self._update_plan_region_preview,
            last=point,
            title=translate("BIM_PlanEdit", "Next region point"),
            mode="line",
        )

    def _clear_space_separator_preview(self):
        self._finalize_trackers(self._space_separator_preview_trackers)
        self._space_separator_preview_trackers = []

    def _cancel_space_separator_tool(self, refresh=True):
        if not self._has_active_space_separator_tool():
            return False
        self._stop_snapper()
        self._clear_space_separator_preview()
        self._space_separator_start = None
        self._space_separator_height = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_space_overlay()
        return True

    def _update_space_separator_preview(self, point, info):
        del info
        start = self._space_separator_start
        if start is None or point is None:
            return
        end = self._project_plan_point(point)
        if end is None or end.sub(start).Length < _MIN_WALL_LENGTH:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        if not self._space_separator_preview_trackers:
            tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "space_separator_preview",
                dotted=True,
                ontop=True,
            )
            self._space_separator_preview_trackers.append(tracker)
        tracker = self._space_separator_preview_trackers[0]
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()

    def _create_space_separator(self, start, end):
        import Arch

        separator = None
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space Separator"))
        try:
            separator = Arch.makeSpaceSeparator(
                start=start,
                end=end,
                height=self._space_separator_height,
            )
            if not separator:
                raise RuntimeError("Unable to create space separator")
            self._add_object_to_active_storey(separator)
            self.doc.recompute()
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return separator

    def _handle_space_separator_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_space_separator_tool()
            return

        point = self._project_plan_point(point)
        if self._space_separator_start is None:
            self._space_separator_start = point
            FreeCADGui.Snapper.getPoint(
                callback=self._handle_space_separator_point,
                movecallback=self._update_space_separator_preview,
                last=point,
                title=translate("BIM_PlanEdit", "Separator end point"),
                mode="line",
            )
            return

        if point.sub(self._space_separator_start).Length < _MIN_WALL_LENGTH:
            self._cancel_space_separator_tool()
            return

        try:
            separator = self._create_space_separator(self._space_separator_start, point)
        except Exception:
            self._cancel_space_separator_tool()
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the space separator.\n")
            )
            return

        self._register_plan_object(separator)
        self._cancel_space_separator_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_primary_selected_plan_target()
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

        wall = self._get_selected_plan_target_object("wall")
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
        self._set_gui_selection_object(wall)
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
            wall = self._get_selected_plan_target_object("wall")
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
            self._preview_line_tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-preview-axis",
                swidth=self._scaled_line_width(2),
                ontop=True,
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
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "wall-edit-preview-footprint",
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
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
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "wall-edit-opening-preview",
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
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
            return (
                "symbol_handle",
                self._get_selected_plan_target_object("symbol"),
                symbol_handle_role,
            )
        opening_handle_index = self._pick_selected_opening_handle(mouse_pos)
        if opening_handle_index is not None:
            return (
                "opening_handle",
                self._get_selected_plan_target_object("opening"),
                opening_handle_index,
            )
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
        opening = self._get_selected_plan_target_object("opening")
        if not self._is_hosted_opening_object(opening) or not self.view:
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_index = None
        best_distance_sq = None
        for idx, _role, point, _marker in self._get_selected_opening_handle_specs(opening):
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
        mouse_pos = None
        try:
            pos = event.getPosition().getValue()
            mouse_pos = (pos[0], pos[1])
        except Exception:
            mouse_pos = None
        selected_before = self._get_selected_plan_target()
        with self._plan_perf_trace_event(
            "mouse_pressed",
            button=str(event.getButton()),
            state=str(event.getState()),
            mouse_pos=mouse_pos,
            selected_before=self._plan_perf_describe_target(selected_before[0], selected_before[1]),
        ):
            if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
                return
            try:
                if event.getState() == coin.SoMouseButtonEvent.UP:
                    if self._consume_left_button_release:
                        self._consume_left_button_release = False
                        self._set_event_handled(event_callback)
                    return

                if event.getState() == coin.SoMouseButtonEvent.DOWN:
                    self._consume_left_button_release = False
                    if self.current_tool == "Join":
                        pos = event.getPosition().getValue()
                        target_kind, target_wall = self._get_plan_target_at_position(
                            (pos[0], pos[1])
                        )
                        source_wall = self._get_selected_plan_target_object("wall")
                        if (
                            target_kind == "wall"
                            and self._is_plan_selectable_wall(target_wall)
                            and target_wall != source_wall
                            and self._apply_plan_wall_join(source_wall, target_wall)
                        ):
                            self._claim_left_button_click(event_callback)
                        return
                    if self.current_tool == "Pick Space Region":
                        pos = event.getPosition().getValue()
                        candidate = self._pick_space_region_candidate((pos[0], pos[1]))
                        if candidate:
                            self._activate_space_region_candidate(candidate, event_callback)
                        return
                    if self.current_tool != "Select":
                        return
                    pos = event.getPosition().getValue()
                    mouse_pos = (pos[0], pos[1])
                    if self._is_plan_additive_selection_active():
                        if not self._toggle_plan_target_selection_at_position(
                            mouse_pos, event_callback
                        ):
                            self._claim_left_button_click(event_callback)
                        return
                    node = self._get_edit_node(mouse_pos)
                    if not node:
                        if self._activate_semantic_plan_target(mouse_pos, event_callback):
                            return
                        self._clear_plan_selection_state()
                        self._claim_left_button_click(event_callback)
                        return
                    node_kind = node[0]
                    if node_kind == "opening_handle":
                        _kind, obj, index = node
                        self._select_opening_for_plan_edit(obj)
                        self._set_gui_selection_object(obj)
                        self._activate_opening_handle(obj, index)
                    elif node_kind == "symbol_handle":
                        _kind, obj, role = node
                        self._set_selected_plan_target_state("symbol", obj)
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
                            self._select_opening_for_plan_edit(obj)
                            self._set_gui_selection_object(obj)
                            self._activate_opening_handle(obj, index)
                        else:
                            self._set_selected_plan_target_state("wall", obj)
                            self._activate_wall_grip(index, wall=obj)
                    self._claim_left_button_click(event_callback)
            finally:
                selected_after = self._get_selected_plan_target()
                self._plan_perf_set_fields(
                    handled=bool(getattr(event_callback, "_handled", False)),
                    selected_after=self._plan_perf_describe_target(
                        selected_after[0], selected_after[1]
                    ),
                )

    def _on_mouse_moved(self, event_callback):
        if self._tearing_down:
            return
        event = event_callback.getEvent()
        try:
            pos = event.getPosition().getValue()
            mouse_pos = (pos[0], pos[1])
        except Exception:
            mouse_pos = None
        hovered_before = self._get_hovered_plan_target()
        with self._plan_perf_trace_event(
            "mouse_moved",
            mouse_pos=mouse_pos,
            hovered_before=self._plan_perf_describe_target(hovered_before[0], hovered_before[1]),
        ):
            if self.current_tool == "Pick Space Region":
                if mouse_pos is not None:
                    self._set_hovered_space_region_candidate(
                        self._pick_space_region_candidate(mouse_pos)
                    )
                    self._refresh_plan_overlay_visuals()
                return
            if self.current_tool not in ("Select", "Join"):
                self._set_hovered_wall(None)
                self._set_hovered_opening(None)
                self._set_hovered_symbol(None)
                self._set_hovered_space(None)
                self._set_hovered_region(None)
                return
            if mouse_pos is None:
                return
            self._update_hovered_plan_target(mouse_pos)
            if self._grip_trackers or self._is_selected_plan_target("wall"):
                self._sync_wall_grips()
            self._request_view_redraw()
            hovered_after = self._get_hovered_plan_target()
            self._plan_perf_set_fields(
                hovered_after=self._plan_perf_describe_target(hovered_after[0], hovered_after[1])
            )

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
        with self._plan_perf_trace_event("mouse_wheel", event_type=event_type_name):
            self._queue_plan_overlay_view_scale_refresh()

    def _queue_plan_overlay_visual_refresh(self, *visuals):
        return overlay_manager.queue_plan_overlay_visual_refresh(
            self,
            visuals,
            _PLAN_VISUAL_ALL,
            _PLAN_VISUAL_SELECTED_SPACE,
        )

    def _queue_plan_overlay_view_scale_refresh(self, delay_ms=_PLAN_VIEW_SCALE_REFRESH_DELAY_MS):
        return overlay_manager.queue_plan_overlay_view_scale_refresh(
            self,
            _PLAN_VISUAL_VIEW_SCALE,
            delay_ms,
        )

    def _consume_dirty_plan_visuals(self, default_all=True):
        return overlay_manager.consume_dirty_plan_visuals(
            self,
            _PLAN_VISUAL_ALL,
            default_all=default_all,
        )

    def _flush_plan_overlay_visual_refresh(self):
        return overlay_manager.flush_plan_overlay_visual_refresh(self)

    def _flush_view_scale_overlay_refresh(self):
        return overlay_manager.flush_view_scale_overlay_refresh(self)

    def _refresh_plan_overlay_view_scale(self):
        with self._plan_perf_trace_span("refresh_plan_overlay_view_scale"):
            if self.current_tool == "Join":
                self._sync_junction_node_overlays()
                if self.hovered_wall:
                    self._sync_hovered_wall_overlay()
                return
            if self.current_tool == "Set Space Text":
                if self._is_selected_plan_target("space"):
                    self._sync_selected_space_overlay()
                return
            if self.current_tool == "Pick Space Region":
                if self._space_region_candidates:
                    self._sync_space_region_pick_overlays()
                if self._get_selected_plan_targets():
                    self._sync_secondary_selected_overlays()
                return
            if self.current_tool != "Select":
                return
            if self.hovered_wall or self._is_selected_plan_target("wall"):
                self._sync_junction_node_overlays()
            if self.hovered_wall:
                self._sync_hovered_wall_overlay()
                self._sync_hovered_wall_opening_context_overlay()
            if self._is_selected_plan_target("wall"):
                self._sync_selected_wall_opening_context_overlay()
                self._sync_wall_grips()
            if self.hovered_opening:
                self._sync_hovered_opening_overlay()
            if self._is_selected_plan_target("opening"):
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if self.hovered_symbol:
                self._sync_hovered_symbol_overlay()
            if self._is_selected_plan_target("symbol"):
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            if self.hovered_space:
                self._sync_hovered_space_overlay()
            if self._is_selected_plan_target("space"):
                self._sync_selected_space_overlay()
            if self.hovered_region:
                self._sync_hovered_region_overlay()
            if self._is_selected_plan_target("region"):
                self._sync_selected_region_overlay()
            if self._get_secondary_selected_plan_targets():
                self._sync_secondary_selected_overlays()

    def _refresh_plan_overlay_visuals(self, dirty=None):
        if self._tearing_down:
            return
        dirty = set(dirty or {_PLAN_VISUAL_ALL})
        refresh_all = _PLAN_VISUAL_ALL in dirty
        if not refresh_all and _PLAN_VISUAL_VIEW_SCALE in dirty:
            self._refresh_plan_overlay_view_scale()
            dirty.discard(_PLAN_VISUAL_VIEW_SCALE)
            if not dirty:
                return
        if self.current_tool == "Join":
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            self._sync_junction_node_overlays()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            return
        if self.current_tool == "Region":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            return
        if self.current_tool == "Set Space Text":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            if self._is_selected_plan_target("space") and (
                refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty
            ):
                self._refresh_selected_space_visuals()
            return
        if self.current_tool == "Pick Space Region":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            if (
                refresh_all
                or _PLAN_VISUAL_SECONDARY_SELECTION in dirty
                or _PLAN_VISUAL_SPACE_REGION_PICK in dirty
            ):
                self._sync_secondary_selected_overlays()
                self._sync_space_region_pick_overlays()
            return
        if self.current_tool == "Select":
            self._clear_space_region_pick_overlays()
            self._sync_junction_node_overlays()
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_OPENING in dirty:
                self._sync_hovered_opening_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_SYMBOL in dirty:
                self._sync_hovered_symbol_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_SPACE in dirty:
                self._sync_hovered_space_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_REGION in dirty:
                self._sync_hovered_region_overlay()
            if refresh_all or _PLAN_VISUAL_SELECTED_OPENING in dirty:
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if refresh_all or _PLAN_VISUAL_SELECTED_SYMBOL in dirty:
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            if refresh_all or _PLAN_VISUAL_SELECTED_REGION in dirty:
                self._sync_selected_region_overlay()
            if refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty:
                self._sync_selected_space_overlay()
            if refresh_all or _PLAN_VISUAL_SECONDARY_SELECTION in dirty:
                self._sync_secondary_selected_overlays()
            if refresh_all or _PLAN_VISUAL_SPACE_REGION_PICK in dirty:
                self._clear_space_region_pick_overlays()
            if refresh_all or _PLAN_VISUAL_WALL_GRIPS in dirty:
                self._sync_wall_grips()
            return

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
        if self.current_tool == "Pick Space Region" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_space_region_pick()
            return
        if self.current_tool == "Region" and key in (
            coin.SoKeyboardEvent.RETURN,
            coin.SoKeyboardEvent.ENTER,
        ):
            if self._finalize_plan_region():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self.current_tool == "Region" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_plan_region_tool()
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
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
            return
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
            return
        if self._has_active_plan_region_tool():
            self._cancel_plan_region_tool()
            return
        if self._has_active_space_separator_tool():
            self._cancel_space_separator_tool()

    # Selection observer interface

    def addSelection(self, doc, obj, sub, point):
        return plan_selection.selection_observer_add(self, doc, obj, sub, point)

    def removeSelection(self, doc, obj, sub):
        return plan_selection.selection_observer_remove(self, doc, obj, sub)

    def setSelection(self, doc):
        return plan_selection.selection_observer_set(self, doc)

    def clearSelection(self, doc):
        return plan_selection.selection_observer_clear(self, doc)

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
        self._invalidate_plan_overlay_geometry_cache(obj)
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
        opening = self._get_selected_plan_target_object("opening")
        if not self._is_hosted_opening_object(opening):
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
        self._sanitize_plan_target_references()
        selected_wall = self._get_selected_plan_target_object("wall")
        selected_opening = self._get_selected_plan_target_object("opening")
        selected_symbol = self._get_selected_plan_target_object("symbol")
        selected_region = self._get_selected_plan_target_object("region")
        selected_space = self._get_selected_plan_target_object("space")
        if selected_region and obj == selected_region and prop in _REGION_VISUAL_PROPERTIES:
            self._refresh_plan_object_footprint_display(selected_region)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_REGION)
            self._refresh_task_panel_status()
            return
        if (
            self.hovered_region
            and not self._is_selected_plan_target("region", self.hovered_region)
            and obj == self.hovered_region
            and prop in _REGION_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_region)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_REGION)
            return
        if selected_space and obj == selected_space and prop in _SPACE_VISUAL_PROPERTIES:
            self._refresh_plan_object_footprint_display(selected_space)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SPACE)
            self._refresh_task_panel_status()
            return
        if (
            self.hovered_space
            and not self._is_selected_plan_target("space", self.hovered_space)
            and obj == self.hovered_space
            and prop in _SPACE_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_space)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SPACE)
            return
        secondary_overlay_refresh = False
        for target_kind, target_obj in self._get_secondary_selected_plan_targets():
            if target_kind == "region" and obj == target_obj and prop in _REGION_VISUAL_PROPERTIES:
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif target_kind == "space" and obj == target_obj and prop in _SPACE_VISUAL_PROPERTIES:
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif (
                target_kind == "symbol"
                and self._is_symbol_visual_dependency(target_obj, obj)
                and prop in _SYMBOL_VISUAL_PROPERTIES
            ):
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif (
                target_kind == "opening"
                and self._is_opening_visual_dependency(target_obj, obj)
                and prop in _OPENING_VISUAL_PROPERTIES
            ):
                self._refresh_opening_footprint_display(target_obj)
                self._refresh_opening_host_footprint_displays(target_obj)
                secondary_overlay_refresh = True
            elif target_kind == "wall" and obj == target_obj and prop in _WALL_VISUAL_PROPERTIES:
                secondary_overlay_refresh = True
        if secondary_overlay_refresh:
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SECONDARY_SELECTION)
            return
        if (
            self._is_symbol_visual_dependency(selected_symbol, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(selected_symbol)
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
            self._is_opening_visual_dependency(selected_opening, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(selected_opening)
            self._refresh_opening_host_footprint_displays(selected_opening)
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
            selected_wall
            and obj in self._get_wall_hosted_openings(selected_wall)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(obj)
            self._refresh_opening_host_footprint_displays(obj)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_WALL_GRIPS)
            return
        if obj == self.hovered_wall and prop in _WALL_VISUAL_PROPERTIES:
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
            return
        if obj != selected_wall:
            return
        if prop not in _WALL_VISUAL_PROPERTIES:
            return
        self._refresh_wall_hosted_opening_footprints(obj)
        self._schedule_selected_wall_reset(prop, obj)

    def slotDeletedObject(self, obj):
        if self._tearing_down:
            return
        self._invalidate_plan_overlay_geometry_cache(obj)
        if obj == self.hovered_wall:
            self.hovered_wall = None
            self._clear_hovered_wall_overlay()
        if obj == self.hovered_opening:
            self.hovered_opening = None
            self._clear_hovered_opening_overlay()
        if obj == self.hovered_symbol:
            self.hovered_symbol = None
            self._clear_hovered_symbol_overlay()
        if obj == self.hovered_space:
            self.hovered_space = None
            self._clear_hovered_space_overlay()
        if obj == self.hovered_region:
            self.hovered_region = None
            self._clear_hovered_region_overlay()
        if self._clear_selected_plan_target_if_matches("opening", obj):
            self._refresh_selected_opening_visuals()
            return
        if self._clear_selected_plan_target_if_matches("symbol", obj):
            self._refresh_selected_symbol_visuals()
            return
        if self._clear_selected_plan_target_if_matches("region", obj):
            self._refresh_selected_region_visuals()
            self._refresh_task_panel_status()
            return
        if self._clear_selected_plan_target_if_matches("space", obj):
            self._refresh_selected_space_visuals()
            self._refresh_task_panel_status()
            return
        if not self._is_selected_plan_target("wall", obj):
            return
        self._schedule_selected_wall_reset("Deleted", obj)

    def _invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        self._invalidate_plan_overlay_geometry_cache()
        self._sanitize_plan_target_references()
        selected_symbol = self._get_selected_plan_target_object("symbol")
        selected_region = self._get_selected_plan_target_object("region")
        selected_space = self._get_selected_plan_target_object("space")
        selected_opening = self._get_selected_plan_target_object("opening")
        if selected_symbol:
            self._refresh_plan_object_footprint_display(selected_symbol)
        if self.hovered_symbol and not self._is_selected_plan_target("symbol", self.hovered_symbol):
            self._refresh_plan_object_footprint_display(self.hovered_symbol)
        if selected_region:
            self._refresh_plan_object_footprint_display(selected_region)
        if self.hovered_region and not self._is_selected_plan_target("region", self.hovered_region):
            self._refresh_plan_object_footprint_display(self.hovered_region)
        if selected_space:
            self._refresh_plan_object_footprint_display(selected_space)
        if self.hovered_space and not self._is_selected_plan_target("space", self.hovered_space):
            self._refresh_plan_object_footprint_display(self.hovered_space)
        secondary_targets = self._get_secondary_selected_plan_targets()
        for target_kind, target_obj in secondary_targets:
            if target_kind in ("symbol", "region", "space"):
                self._refresh_plan_object_footprint_display(target_obj)
            elif target_kind == "opening":
                self._refresh_opening_footprint_display(target_obj)
                self._refresh_opening_host_footprint_displays(target_obj)
        if selected_opening:
            self._refresh_opening_footprint_display(selected_opening)
            self._refresh_opening_host_footprint_displays(selected_opening)
            self._queue_hard_refresh_selected_opening_visuals()
        if self.hovered_opening and not self._is_selected_plan_target(
            "opening", self.hovered_opening
        ):
            self._refresh_opening_footprint_display(self.hovered_opening)
            self._refresh_opening_host_footprint_displays(self.hovered_opening)
        if recompute_opening_hosts:
            self._queue_recompute_opening_hosts(selected_opening, self.hovered_opening)
        visual_args = [
            _PLAN_VISUAL_SELECTED_SYMBOL,
            _PLAN_VISUAL_HOVERED_SYMBOL,
            _PLAN_VISUAL_HOVERED_OPENING,
            _PLAN_VISUAL_HOVERED_WALL,
            _PLAN_VISUAL_WALL_GRIPS,
        ]
        if selected_region:
            visual_args.append(_PLAN_VISUAL_SELECTED_REGION)
        if self.hovered_region and not self._is_selected_plan_target("region", self.hovered_region):
            visual_args.append(_PLAN_VISUAL_HOVERED_REGION)
        if selected_space:
            visual_args.append(_PLAN_VISUAL_SELECTED_SPACE)
        if self.hovered_space and not self._is_selected_plan_target("space", self.hovered_space):
            visual_args.append(_PLAN_VISUAL_HOVERED_SPACE)
        if selected_opening:
            visual_args.append(_PLAN_VISUAL_SELECTED_OPENING)
        if secondary_targets:
            visual_args.append(_PLAN_VISUAL_SECONDARY_SELECTION)
        self._queue_plan_overlay_visual_refresh(*visual_args)

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

    def _refresh_task_panel_status(self, selection_only=False):
        with self._plan_perf_trace_span(
            "refresh_task_panel_status",
            selection_only=bool(selection_only),
        ):
            if self._tearing_down:
                return
            self._sanitize_plan_target_references()
            self._update_input_hints()
            self._refresh_viewport_status_chip()
            panel = self.task_panel
            if panel:
                try:
                    refresh = None
                    if selection_only:
                        refresh = getattr(panel, "refresh_selection_from_session", None)
                    if not callable(refresh):
                        refresh = getattr(panel, "refresh_from_session", None)
                    if callable(refresh):
                        refresh()
                except (AttributeError, RuntimeError):
                    self.on_panel_closed(panel)
            stale_panels = []
            for extra_panel in list(self._aux_task_panels):
                if extra_panel is panel:
                    continue
                try:
                    refresh = None
                    if selection_only:
                        refresh = getattr(extra_panel, "refresh_selection_from_session", None)
                    if not callable(refresh):
                        refresh = getattr(extra_panel, "refresh_from_session", None)
                    if callable(refresh):
                        refresh()
                except (AttributeError, RuntimeError):
                    stale_panels.append(extra_panel)
            for extra_panel in stale_panels:
                self.detach_aux_task_panel(extra_panel)

    def _is_modal_plan_interaction_active(self):
        return bool(
            self._is_wall_edit_modal_active()
            or self.current_tool
            in ("Move Opening", "Move Symbol", "Rotate Symbol", "Set Space Text")
        )

    def _focus_plan_view(self):
        return plan_view.focus_plan_view(self)

    def _queue_focus_plan_view(self):
        return plan_view.queue_focus_plan_view(self)

    def _get_plan_view_widget(self):
        return plan_view.get_plan_view_widget(self)

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

    def _get_plan_target_display_label(self, obj):
        return getattr(obj, "Label", getattr(obj, "Name", ""))

    def _format_plan_target_selection_state(self, kind, obj):
        if not kind or not obj:
            return ""
        templates = {
            "opening": translate("BIM_PlanEdit", "Opening: {label}"),
            "symbol": translate("BIM_PlanEdit", "Symbol: {label}"),
            "region": translate("BIM_PlanEdit", "Region: {label}"),
            "space": translate("BIM_PlanEdit", "Space: {label}"),
            "wall": translate("BIM_PlanEdit", "Wall: {label}"),
        }
        template = templates.get(kind)
        if not template:
            return ""
        return template.format(label=self._get_plan_target_display_label(obj))

    def _get_status_chip_text(self):
        title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(tool=self.current_tool)
        selected_kind, selected_obj = self._get_selected_plan_target()
        selected_context = self._format_plan_target_selection_state(selected_kind, selected_obj)

        if self.current_tool == "Move Opening":
            context = (
                selected_context
                if selected_kind == "opening" and selected_obj is not None
                else translate("BIM_PlanEdit", "Opening move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Move Symbol":
            context = (
                selected_context
                if selected_kind == "symbol" and selected_obj is not None
                else translate("BIM_PlanEdit", "Symbol move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Rotate Symbol":
            context = (
                selected_context
                if selected_kind == "symbol" and selected_obj is not None
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
                selected_context
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Join":
            target_wall, joint, detail = self._get_plan_join_candidate_state()
            context = (
                translate("BIM_PlanEdit", "Source wall: {label}").format(
                    label=self._get_plan_target_display_label(selected_obj)
                )
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall join")
            )
            action = self._get_plan_join_mode_action_text(target_wall, joint)
            if detail:
                return title, "{}\n{}\n{}".format(context, detail, action)
            return title, "{}\n{}".format(context, action)

        if self.current_tool.startswith("Stretch "):
            context = (
                selected_context
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall stretch")
            )
            action = translate("BIM_PlanEdit", "Click endpoint or press Enter to type a value")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Region":
            context = (
                translate("BIM_PlanEdit", "Parent space: {label}").format(
                    label=self._plan_region_parent_space.Label
                )
                if self._is_plan_space_object(self._plan_region_parent_space)
                else translate("BIM_PlanEdit", "Plan region")
            )
            action = translate(
                "BIM_PlanEdit",
                "Click polygon points, press Enter to finish, or click near the first point to close",
            )
            return title, "{}\n{}".format(context, action)

        if selected_context:
            context = selected_context
        else:
            context = translate("BIM_PlanEdit", "Storey: {label}").format(
                label=self.get_storey_label(self.active_storey)
            )

        selection_summary = self._get_plan_selection_summary_text()
        if selection_summary:
            context = "{}\n{}".format(context, selection_summary)

        hints = self._get_input_hint_specs()
        action = self._format_status_chip_action(hints[0][0]) if hints else ""
        if selected_kind == "region" and self.current_tool == "Select":
            action = translate(
                "BIM_PlanEdit",
                "Edit label, scheme, type, and parent space in the task panel",
            )
        if self._plan_relation_status_message:
            action = self._plan_relation_status_message
        if not action:
            action = translate("BIM_PlanEdit", "Work directly in the viewport")
        return title, "{}\n{}".format(context, action)

    def _ensure_viewport_status_chip(self):
        return plan_view.ensure_viewport_status_chip(self, _PlanEditViewportStatusChip)

    def _refresh_viewport_status_chip(self):
        return plan_view.refresh_viewport_status_chip(self, _PlanEditViewportStatusChip)

    def _clear_viewport_status_chip(self):
        return plan_view.clear_viewport_status_chip(self)

    def _clear_input_hints(self):
        hint_manager = getattr(FreeCADGui, "HintManager", None)
        if not hint_manager or not hasattr(hint_manager, "hide"):
            return
        try:
            hint_manager.hide()
        except Exception:
            pass

    def _request_view_redraw(self):
        return plan_view.request_view_redraw(self)

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
        selected_kind, _selected_obj = self._get_selected_plan_target()

        if self.current_tool == "Select":
            additive_hint = (
                translate("BIM_PlanEdit", "%1 add or remove from selection"),
                (ui.KeyControl, ui.MouseLeft),
            )
            if selected_kind == "opening":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick opening handle"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "symbol":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick symbol handle"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "wall":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick wall grip"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "region":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 select another target"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "space":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 select space boundary target"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            return (
                (
                    translate(
                        "BIM_PlanEdit",
                        "%1 select wall, opening, symbol, region, or space",
                    ),
                    ui.MouseLeft,
                ),
                additive_hint,
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
            "Set Space Text": (
                (
                    translate("BIM_PlanEdit", "%1 place text"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Region": (
                (
                    translate("BIM_PlanEdit", "%1 place region point"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 finish region"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Separator": (
                (
                    translate("BIM_PlanEdit", "%1 place separator"),
                    ui.MouseLeft,
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

    def _retarget_edit_tracker(self, tracker, obj, index):
        return wall_overlays.retarget_edit_tracker(tracker, obj, index)

    def _sync_wall_grips(self):
        return wall_overlays.sync_wall_grips(self)

    def _clear_wall_grips(self):
        return wall_overlays.clear_wall_grips(self)

    def _get_footprint_overlay_polylines(self, faces):
        return overlay_geometry.get_footprint_overlay_polylines(faces)

    def _build_overlay_segments_from_polylines(self, polylines):
        return overlay_geometry.build_overlay_segments_from_polylines(polylines)

    def _get_wall_overlay_polylines(self, wall):
        return overlay_geometry.get_wall_overlay_polylines(self, wall)

    def _get_space_footprint_faces(self, space):
        return overlay_geometry.get_space_footprint_faces(self, space)

    def _get_space_overlay_polylines(self, space):
        return overlay_geometry.get_space_overlay_polylines(self, space)

    def _get_region_footprint_faces(self, region):
        return overlay_geometry.get_region_footprint_faces(self, region)

    def _get_region_overlay_polylines(self, region):
        return overlay_geometry.get_region_overlay_polylines(self, region)

    def _get_opening_overlay_polylines(self, opening):
        return overlay_geometry.get_opening_overlay_polylines(self, opening)

    def _get_opening_overlay_screen_polylines(self, opening):
        return overlay_geometry.get_opening_overlay_screen_polylines(self, opening)

    def _finalize_trackers(self, trackers):
        return overlay_manager.finalize_trackers(trackers)

    def _make_plan_line_tracker(self, DraftTrackers, label, **kwargs):
        return overlay_manager.make_plan_line_tracker(DraftTrackers, label, **kwargs)

    def _set_plan_line_tracker_width(self, tracker, width):
        return overlay_manager.set_plan_line_tracker_width(tracker, width)

    def _get_opening_handle_markers(self, marker_size=None):
        return opening_overlays.get_opening_handle_markers(self, marker_size=marker_size)

    def _set_opening_handle_tracker_marker(self, tracker, marker):
        return opening_overlays.set_opening_handle_tracker_marker(tracker, marker)

    def _discard_opening_handle_tracker_pool(self):
        return opening_overlays.discard_opening_handle_tracker_pool(self)

    def _queue_prime_opening_handle_tracker_pool(self):
        return opening_overlays.queue_prime_opening_handle_tracker_pool(self)

    def _prime_opening_handle_tracker_pool(self):
        return opening_overlays.prime_opening_handle_tracker_pool(self)

    def _get_plan_target_at_position(self, mouse_pos):
        return plan_picking.get_plan_target_at_position(self, mouse_pos)

    def _update_hovered_plan_target(self, mouse_pos):
        if self.current_tool == "Join":
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
            if target_kind == "wall" and not self._is_selected_plan_target("wall", target_obj):
                self._set_hovered_wall(target_obj)
            else:
                self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            return
        if self.current_tool != "Select":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            return
        target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if target_kind == "opening":
            self._set_hovered_wall(None)
            self._set_hovered_opening(target_obj)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
        elif target_kind == "symbol":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(target_obj)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
        elif target_kind == "wall":
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            self._set_hovered_wall(target_obj)
        elif target_kind == "region":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(target_obj)
        elif target_kind == "space":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_region(None)
            self._set_hovered_space(target_obj)
        else:
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)

    def _is_plan_additive_selection_active(self):
        if self.current_tool != "Select":
            return False
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ControlModifier)
        except Exception:
            return False

    def _get_plan_target_from_edit_node(self, node):
        return plan_picking.get_plan_target_from_edit_node(self, node)

    def _toggle_plan_target_selection_at_position(self, mouse_pos, event_callback=None):
        node = self._get_edit_node(mouse_pos)
        target_kind, target_obj = self._get_plan_target_from_edit_node(node)
        if target_kind is None:
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if not target_kind or not target_obj:
            return False

        primary_kind, primary_obj = self._get_selected_plan_target()
        selection = self._get_gui_selection()
        if primary_obj is not None and primary_obj not in selection:
            selection = [primary_obj] + selection

        normalized_selection = []
        seen = set()
        for selected in selection:
            if not selected:
                continue
            key = (
                getattr(getattr(selected, "Document", None), "Name", None),
                getattr(selected, "Name", None),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized_selection.append(selected)
        selection = normalized_selection

        was_selected = target_obj in selection
        if was_selected:
            new_selection = [selected for selected in selection if selected != target_obj]
            if primary_obj == target_obj:
                next_kind, next_obj = self._get_first_plan_target_from_selection(new_selection)
            elif primary_obj is not None and primary_obj in new_selection:
                next_kind, next_obj = primary_kind, primary_obj
            else:
                next_kind, next_obj = self._get_first_plan_target_from_selection(new_selection)
        else:
            new_selection = list(selection)
            new_selection.append(target_obj)
            if (
                primary_obj is not None
                and primary_obj in new_selection
                and primary_obj != target_obj
            ):
                next_kind, next_obj = primary_kind, primary_obj
            else:
                next_kind, next_obj = target_kind, target_obj

        self._set_pending_selected_plan_target(next_kind, next_obj)
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._set_gui_selection(new_selection)
        self._refresh_primary_selected_plan_target()
        self._claim_left_button_click(event_callback)
        return True

    def _clear_hovered_plan_targets(self, kinds=None):
        clearers = {
            "wall": self._set_hovered_wall,
            "opening": self._set_hovered_opening,
            "symbol": self._set_hovered_symbol,
            "space": self._set_hovered_space,
            "region": self._set_hovered_region,
        }
        for kind in kinds or ("wall", "opening", "symbol", "space", "region"):
            clear_hovered = clearers.get(kind)
            if clear_hovered is not None:
                clear_hovered(None)

    def _get_hovered_plan_target(self):
        return plan_picking.get_hovered_plan_target(self)

    def _set_event_handled(self, event_callback):
        if event_callback and hasattr(event_callback, "setHandled"):
            try:
                event_callback.setHandled()
            except Exception:
                pass

    def _claim_left_button_click(self, event_callback):
        # Plan Edit owns overlay-driven picks, so also swallow the matching
        # button release to prevent the base 3D view selection pass from
        # clearing or replacing the GUI selection afterwards.
        self._consume_left_button_release = True
        self._set_event_handled(event_callback)

    def _set_hovered_wall(self, wall):
        if self._is_selected_plan_target("wall", wall):
            wall = None
        if self.hovered_wall == wall:
            return
        self.hovered_wall = wall
        self._sync_junction_node_overlays()
        self._sync_hovered_wall_overlay()
        self._sync_hovered_wall_opening_context_overlay()
        if self.current_tool == "Join":
            self._refresh_task_panel_status(
                selection_only=self.current_tool == "Select"
                and self._is_selected_plan_target("wall")
            )

    def _set_hovered_opening(self, opening):
        if self._is_selected_plan_target("opening", opening):
            opening = None
        if self.hovered_opening == opening:
            return
        self.hovered_opening = opening
        self._sync_hovered_opening_overlay()

    def _set_hovered_symbol(self, symbol):
        if self._is_selected_plan_target("symbol", symbol):
            symbol = None
        if self.hovered_symbol == symbol:
            return
        self.hovered_symbol = symbol
        self._sync_hovered_symbol_overlay()

    def _set_hovered_space(self, space):
        if self._is_selected_plan_target("space", space):
            space = None
        if self.hovered_space == space:
            return
        self.hovered_space = space
        self._sync_hovered_space_overlay()

    def _set_hovered_region(self, region):
        if self._is_selected_plan_target("region", region):
            region = None
        if self.hovered_region == region:
            return
        self.hovered_region = region
        self._sync_hovered_region_overlay()

    def _queue_restore_selected_plan_target(self, kind, obj):
        if not obj:
            return
        queue_restore = {
            "opening": self._queue_restore_selected_opening,
            "symbol": self._queue_restore_selected_symbol,
            "region": self._queue_restore_selected_region,
            "space": self._queue_restore_selected_space,
        }.get(kind)
        if queue_restore is not None:
            queue_restore(obj)

    def _select_plan_target_for_plan_edit(
        self, kind, obj, queue_restore=False, sync_gui_selection=False
    ):
        validators = {
            "opening": self._is_hosted_opening_object,
            "symbol": self._is_plan_symbol_instance,
            "region": self._is_plan_region_object,
            "space": self._is_plan_space_object,
            "wall": self._is_plan_selectable_wall,
        }
        validator = validators.get(kind)
        if validator is None or not validator(obj):
            return False
        previous_kind, previous_obj = self._get_selected_plan_target()
        self.current_tool = "Select"
        self._set_selected_plan_target(kind, obj, pending_restore=queue_restore)
        if sync_gui_selection:
            self._set_gui_selection_object(obj)
        if kind == "wall":
            self._sync_wall_grips()
        else:
            self._clear_wall_grips()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "opening"):
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "symbol"):
            self._sync_selected_symbol_overlay()
            self._sync_selected_symbol_handles()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "region"):
            self._sync_selected_region_overlay()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "space"):
            self._sync_selected_space_overlay()
        self._sync_secondary_selected_overlays()
        self._refresh_task_panel_status(
            selection_only=self.current_tool == "Select" and self._is_selected_plan_target("wall")
        )
        if queue_restore:
            self._queue_restore_selected_plan_target(kind, obj)
        return True

    def _select_opening_for_plan_edit(self, opening, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "opening",
            opening,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_symbol_for_plan_edit(self, symbol, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "symbol",
            symbol,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_region_for_plan_edit(self, region, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "region",
            region,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_space_for_plan_edit(self, space, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "space",
            space,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_wall_for_plan_edit(self, wall, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "wall",
            wall,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _activate_plan_target(
        self,
        kind,
        mouse_pos,
        event_callback=None,
        sync_gui_selection=False,
        clear_hovered_kinds=None,
        resolved_target=None,
    ):
        if resolved_target is None:
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        else:
            target_kind, target_obj = resolved_target
        with self._plan_perf_trace_span(
            f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
        ):
            self._plan_perf_count(f"activate_plan_target_attempts_{kind}")
            self._plan_perf_set_fields(
                resolved_target=self._plan_perf_describe_target(target_kind, target_obj)
            )
            if target_kind != kind:
                target_obj = None
            select_target = {
                "opening": self._select_opening_for_plan_edit,
                "symbol": self._select_symbol_for_plan_edit,
                "region": self._select_region_for_plan_edit,
                "space": self._select_space_for_plan_edit,
                "wall": self._select_wall_for_plan_edit,
            }.get(kind)
            if select_target is None or not select_target(
                target_obj,
                queue_restore=True,
                sync_gui_selection=sync_gui_selection,
            ):
                self._plan_perf_set_fields(activate_plan_target_result=False)
                return False
            self._clear_hovered_plan_targets(clear_hovered_kinds)
            self._claim_left_button_click(event_callback)
            self._plan_perf_set_fields(
                activate_plan_target_result=True,
                activated_target=self._plan_perf_describe_target(kind, target_obj),
            )
            return True

    def _activate_semantic_plan_target(self, mouse_pos, event_callback=None):
        target_kind, target_obj = self._get_hovered_plan_target()
        if target_obj is None:
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
            self._plan_perf_set_fields(semantic_target_source="picked")
        else:
            self._plan_perf_set_fields(
                semantic_target_source="hovered",
                hovered_target=self._plan_perf_describe_target(target_kind, target_obj),
            )
        activate_target = {
            "opening": self._activate_opening_target,
            "symbol": self._activate_symbol_target,
            "region": self._activate_region_target,
            "space": self._activate_space_target,
            "wall": self._activate_wall_target,
        }.get(target_kind)
        if activate_target is None:
            return False
        return activate_target(
            mouse_pos,
            event_callback=event_callback,
            resolved_target=(target_kind, target_obj),
        )

    def _activate_opening_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "opening",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_symbol_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "symbol",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_region_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "region",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_space_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "space",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "region"),
            resolved_target=resolved_target,
        )

    def _activate_wall_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "wall",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _get_plan_point_from_mouse_pos(self, mouse_pos):
        if not self.view or not mouse_pos:
            return None
        get_point = self._get_runtime_attr(self.view, "getPoint")
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
        return self._project_plan_point(point)

    def _get_space_region_candidate_polylines(self, candidate):
        face = candidate.get("face") if isinstance(candidate, dict) else None
        if not face:
            return []
        return self._get_footprint_overlay_polylines([face])

    def _get_space_region_candidate_segments(self, candidate):
        segments = []
        for polyline in self._get_space_region_candidate_polylines(candidate):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _pick_space_region_candidate(self, mouse_pos, radius_px=10):
        if self.current_tool != "Pick Space Region" or not self._space_region_candidates:
            return None

        point = self._get_plan_point_from_mouse_pos(mouse_pos)
        if point is not None:
            for candidate in self._space_region_candidates:
                face = candidate.get("face")
                if not face:
                    continue
                bound_box = getattr(face, "BoundBox", None)
                if bound_box is None:
                    continue
                test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
                try:
                    if face.isInside(test_point, 0.001, True):
                        return candidate
                except Exception:
                    continue

        radius_sq = float(radius_px) * float(radius_px)
        best_candidate = None
        best_distance_sq = None
        for candidate in self._space_region_candidates:
            for start, end in self._get_space_region_candidate_segments(candidate):
                distance_sq = self._get_screen_distance_sq_to_segment(mouse_pos, start, end)
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_candidate = candidate
                    best_distance_sq = distance_sq
        return best_candidate

    def _set_hovered_space_region_candidate(self, candidate):
        if self._hovered_space_region_candidate is candidate:
            return
        self._hovered_space_region_candidate = candidate
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SPACE_REGION_PICK)
        self._refresh_task_panel_status()

    def _create_space_region_base_object(self, candidate):
        shape = candidate.get("shape") if isinstance(candidate, dict) else None
        if not shape:
            return None
        try:
            base = self.doc.addObject("Part::Feature", "SpaceRegionBase")
        except Exception:
            return None
        try:
            base.Shape = self._copy_shape_without_element_map(shape)
        except Exception:
            return None

        view_object = getattr(base, "ViewObject", None)
        if view_object:
            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = False
                except Exception:
                    pass
            if hasattr(view_object, "ShowInTree"):
                try:
                    view_object.ShowInTree = False
                except Exception:
                    pass
            if hasattr(view_object, "Selectable"):
                try:
                    view_object.Selectable = False
                except Exception:
                    pass
        return base

    def _begin_space_region_pick(self, boundaries, label=None, seed_space=None, report=None):
        if report is None:
            report = self._get_space_region_candidate_report(
                boundaries,
                label=label,
                seed_space=seed_space,
            )
        candidates = list(report.get("candidates", []) or [])
        if not candidates:
            self._report_space_region_candidate_failure(report)
            return False

        skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
        if skipped_claimed:
            FreeCAD.Console.PrintMessage(
                translate(
                    "BIM_PlanEdit",
                    "Ignoring {count} enclosed region(s) already covered by existing spaces.\n",
                ).format(count=skipped_claimed)
            )
        if skipped_claimed and len(candidates) == 1:
            space = self._create_space_from_region_candidate(
                candidates[0],
                boundaries=boundaries,
                keep_boundaries=seed_space is None,
            )
            if not space:
                return False
            self._register_plan_object(space)
            self._restore_selected_space(space)
            return True

        self.current_tool = "Pick Space Region"
        self._space_region_pick_boundaries = list(boundaries)
        self._space_region_candidates = candidates
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = seed_space
        self._clear_wall_grips()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._refresh_primary_selected_plan_target()
        FreeCAD.Console.PrintMessage(
            translate(
                "BIM_PlanEdit",
                "Multiple enclosed regions found. Hover a dashed region and click to create that space.\n",
            )
        )
        return True

    def _cancel_space_region_pick(self, refresh=True):
        was_active = self.current_tool == "Pick Space Region" or bool(self._space_region_candidates)
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._clear_space_region_pick_overlays()
        if self.current_tool == "Pick Space Region":
            self.current_tool = "Select"
        if was_active:
            self._refresh_primary_selected_plan_target()
        elif refresh:
            self._refresh_task_panel_status()
        return was_active

    def _create_space_from_region_candidate(self, candidate, boundaries=None, keep_boundaries=True):
        import Arch

        if not isinstance(candidate, dict):
            return None
        boundaries = list(boundaries or [])

        space = None
        reported_failure = False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
            base = self._create_space_region_base_object(candidate)
            if not base:
                raise RuntimeError("Unable to create space base")
            space = Arch.makeSpace(base)
            if not space:
                raise RuntimeError("Unable to create space")
            if keep_boundaries and boundaries:
                space.Boundaries = boundaries
            self._add_object_to_active_storey(space)
            self.doc.recompute()
            if not self._space_has_valid_geometry(space):
                reported_failure = self._report_space_creation_failure(space)
                raise RuntimeError("Unable to create space")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not reported_failure:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "Failed to create the selected space.\n")
                )
            return None

        return space

    def _activate_space_region_candidate(self, candidate, event_callback=None):
        if self.current_tool != "Pick Space Region" or not isinstance(candidate, dict):
            return False

        boundaries = list(self._space_region_pick_boundaries or [])
        if not boundaries and self._space_region_pick_seed_space is None:
            return False

        space = self._create_space_from_region_candidate(
            candidate,
            boundaries=boundaries,
            keep_boundaries=self._space_region_pick_seed_space is None,
        )
        if not space:
            return False

        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._clear_space_region_pick_overlays()
        self._register_plan_object(space)
        self._restore_selected_space(space)
        self._claim_left_button_click(event_callback)
        return True

    def _create_space_from_current_selection(self):
        import ArchSpace

        request = self._get_space_creation_request()
        if not request:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces before using Space.\n",
                )
            )
            return False

        boundaries = list(request["boundaries"] or [])
        region_seed_space = request["region_seed_space"]
        if not boundaries:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces before using Space.\n",
                )
            )
            return False

        if region_seed_space is not None:
            report = self._get_space_region_candidate_report(
                boundaries,
                label=request["label"],
                seed_space=region_seed_space,
            )
            candidate_count = int(report.get("candidate_count", 0) or 0)
            if candidate_count > 1:
                return self._begin_space_region_pick(
                    boundaries,
                    label=report.get("label"),
                    seed_space=region_seed_space,
                    report=report,
                )
            if candidate_count == 1:
                space = self._create_space_from_region_candidate(
                    report["candidates"][0],
                    boundaries=boundaries,
                    keep_boundaries=False,
                )
                if not space:
                    return False
                self._register_plan_object(space)
                self._restore_selected_space(space)
                return True
            self._report_space_region_candidate_failure(report)
            return False

        report = ArchSpace.analyzeBoundaryLinks(boundaries)
        if report.get("code") == "multiple_regions":
            region_report = self._get_space_region_candidate_report(
                boundaries,
                label=report.get("label"),
            )
            candidate_count = int(region_report.get("candidate_count", 0) or 0)
            if candidate_count > 1:
                return self._begin_space_region_pick(
                    boundaries,
                    label=report.get("label"),
                    report=region_report,
                )
            if candidate_count == 1:
                space = self._create_space_from_region_candidate(
                    region_report["candidates"][0],
                    boundaries=boundaries,
                    keep_boundaries=True,
                )
                if not space:
                    return False
                self._register_plan_object(space)
                self._restore_selected_space(space)
                return True
            self._report_space_region_candidate_failure(region_report)
            return False

        import Arch

        space = None
        reported_failure = False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
            space = Arch.makeSpace(boundaries)
            if not space:
                raise RuntimeError("Unable to create space")
            self._add_object_to_active_storey(space)
            self.doc.recompute()
            if not self._space_has_valid_geometry(space):
                reported_failure = self._report_space_creation_failure(space)
                raise RuntimeError("Unable to create space")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not reported_failure:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "Failed to create the selected space.\n")
                )
            return False

        self._register_plan_object(space)
        self._restore_selected_space(space)
        return True

    def _space_has_valid_geometry(self, space):
        if not self._is_plan_space_object(space):
            return False
        try:
            shape = getattr(space, "Shape", None)
        except Exception:
            return False
        if not shape:
            return False
        try:
            if shape.isNull():
                return False
        except Exception:
            pass
        return bool(getattr(shape, "Solids", None))

    def _report_space_creation_failure(self, space):
        proxy = getattr(space, "Proxy", None)
        if not proxy:
            return False

        message = ""
        if hasattr(proxy, "getLastBoundaryError"):
            try:
                message = str(proxy.getLastBoundaryError(space) or "").strip()
            except Exception:
                message = ""

        if not message:
            return False

        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Plan Edit kept no new space object because the selection could not be turned into a valid Arch Space.\n",
            )
        )
        return True

    def _set_selected_space_label(self, label):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        label = str(label or "").strip()
        if not label or label == space.Label:
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Rename Space"))
            space.Label = label
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_space_type(self, space_type):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        space_type = str(space_type or "")
        if not space_type or space_type == getattr(space, "SpaceType", ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Space Type"))
            space.SpaceType = space_type
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_label(self, label):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        label = str(label or "").strip()
        if not label or label == getattr(region, "Label", ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Rename Region"))
            region.Label = label
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_scheme(self, scheme):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        scheme = str(scheme or "").strip()
        if scheme == str(getattr(region, "Scheme", "") or ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Scheme"))
            region.Scheme = scheme
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_type(self, region_type):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        region_type = str(region_type or "").strip()
        if region_type == str(getattr(region, "RegionType", "") or ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Type"))
            region.RegionType = region_type
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_parent_space(self, space):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        space = self._get_plan_semantic_object(space) if space else None
        if space is not None and not self._is_plan_space_object(space):
            return False

        current_parent = getattr(region, "ParentSpace", None)
        current_parent = self._get_plan_semantic_object(current_parent) if current_parent else None
        if current_parent == space:
            return False

        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Parent Space"))
            region.ParentSpace = space
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_space_boundaries(self, space, boundaries):
        if not self._is_plan_space_object(space):
            return False
        import ArchSpace

        boundaries = ArchSpace.normalizeBoundaryLinks(boundaries)
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Edit Space Boundaries"))
            space.Boundaries = boundaries
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_selected_space_visuals()
        self._refresh_task_panel_status()
        return True

    def _add_boundaries_to_selected_space(self):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        existing = self._get_space_boundary_entries(space)
        additions = self._get_selected_space_boundary_links(fallback_space=space)
        if not additions:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces to add to the space.\n",
                )
            )
            return False
        merged = existing + additions
        return self._set_space_boundaries(space, merged)

    def _remove_selected_space_boundaries(self, row_indexes=None):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        existing = self._get_space_boundary_entries(space)
        if not existing:
            return False

        if row_indexes:
            row_indexes = set(int(index) for index in row_indexes if int(index) >= 0)
            remaining = [
                boundary for idx, boundary in enumerate(existing) if idx not in row_indexes
            ]
            if len(remaining) == len(existing):
                return False
            return self._set_space_boundaries(space, remaining)

        removals = {
            self._space_boundary_key(boundary)
            for boundary in self._get_selected_space_boundary_links(fallback_space=space)
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
            boundary for boundary in existing if self._space_boundary_key(boundary) not in removals
        ]
        if len(remaining) == len(existing):
            return False
        return self._set_space_boundaries(space, remaining)

    def _start_space_text_position_pick(self):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        self.current_tool = "Set Space Text"
        self._edit_space = space
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._sync_secondary_selected_overlays()
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            callback=self._finish_space_text_position_pick,
            last=self._get_space_reference_point(space),
            title=translate("BIM_PlanEdit", "Pick space text position"),
            noTracker=True,
        )
        self._queue_focus_plan_view()
        return True

    def _finish_space_text_position_pick(self, point=None, obj=None):
        del obj
        space = self._edit_space
        self._edit_space = None
        FreeCAD.activeDraftCommand = None
        self._set_draft_point_focus_suppressed(False)

        if point is None or not self._is_plan_space_object(space):
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        point = self._project_plan_point(point)
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Set Space Text Position"))
            space.ViewObject.TextPosition = space.Placement.inverse().multVec(point)
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self._restore_selected_space(space)
            return

        self.current_tool = "Select"
        self._queue_restore_selected_space(space)

    def _cancel_space_text_position_pick(self):
        space = self._edit_space or self._get_selected_plan_target_object("space")
        self._edit_space = None
        self._stop_snapper()
        FreeCAD.activeDraftCommand = None
        self._set_draft_point_focus_suppressed(False)
        self.current_tool = "Select"
        if space:
            self._set_selected_plan_target("space", space, pending_restore=True)
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _refresh_selected_space_visuals(self):
        self._invalidate_selected_space_overlay_cache()
        self._sync_selected_space_overlay()
        self._request_view_redraw()

    def _refresh_selected_region_visuals(self):
        self._sync_selected_region_overlay()
        self._request_view_redraw()

    def _restore_selected_region(self, region):
        self.current_tool = "Select"
        if region:
            self._set_selected_plan_target("region", region, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not region:
            self._sync_selected_region_overlay()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(region)
        self._sync_selected_region_overlay()
        self._refresh_task_panel_status()

    def _queue_restore_selected_region(self, region):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_region(region)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_region(region))

    def _restore_selected_space(self, space):
        self.current_tool = "Select"
        self._edit_space = None
        if space:
            self._set_selected_plan_target("space", space, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not space:
            self._sync_selected_space_overlay()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(space)
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _queue_restore_selected_space(self, space):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_space(space)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_space(space))

    def _sync_secondary_selected_overlays(self):
        return space_overlays.sync_secondary_selected_overlays(self)

    def _clear_secondary_selected_overlays(self):
        return space_overlays.clear_secondary_selected_overlays(self)

    def _sync_space_region_pick_overlays(self):
        return space_overlays.sync_space_region_pick_overlays(self)

    def _clear_space_region_pick_overlays(self):
        return space_overlays.clear_space_region_pick_overlays(self)

    def _sync_hovered_wall_overlay(self):
        return wall_overlays.sync_hovered_wall_overlay(self)

    def _clear_hovered_wall_overlay(self):
        return wall_overlays.clear_hovered_wall_overlay(self)

    def _get_plan_context_junctions(self):
        return wall_overlays.get_plan_context_junctions(self)

    def _create_junction_node_trackers(self, junction, color, width, tracker_store):
        return wall_overlays.create_junction_node_trackers(
            self,
            junction,
            color=color,
            width=width,
            tracker_store=tracker_store,
        )

    def _sync_junction_node_overlays(self):
        return wall_overlays.sync_junction_node_overlays(self)

    def _clear_junction_node_overlays(self):
        return wall_overlays.clear_junction_node_overlays(self)

    def _sync_hovered_wall_opening_context_overlay(self):
        return wall_overlays.sync_hovered_wall_opening_context_overlay(self)

    def _clear_hovered_wall_opening_context_overlay(self):
        return wall_overlays.clear_hovered_wall_opening_context_overlay(self)

    def _create_wall_overlay_trackers(self, wall, color, width, tracker_store):
        return wall_overlays.create_wall_overlay_trackers(
            self,
            wall,
            color=color,
            width=width,
            tracker_store=tracker_store,
        )

    def _create_space_overlay_trackers(self, space, color, width, tracker_store):
        return space_overlays.create_space_overlay_trackers(
            self,
            space,
            color=color,
            width=width,
            tracker_store=tracker_store,
        )

    def _create_region_overlay_trackers(self, region, color, width, tracker_store):
        return space_overlays.create_region_overlay_trackers(
            self,
            region,
            color=color,
            width=width,
            tracker_store=tracker_store,
        )

    def _get_region_overlay_segments(self, region):
        return overlay_geometry.get_region_overlay_segments(self, region)

    def _get_space_overlay_segments(self, space):
        return overlay_geometry.get_space_overlay_segments(self, space)

    def _sync_hovered_space_overlay(self):
        return space_overlays.sync_hovered_space_overlay(self)

    def _clear_hovered_space_overlay(self):
        return space_overlays.clear_hovered_space_overlay(self)

    def _sync_hovered_region_overlay(self):
        return space_overlays.sync_hovered_region_overlay(self)

    def _clear_hovered_region_overlay(self):
        return space_overlays.clear_hovered_region_overlay(self)

    def _invalidate_selected_space_overlay_cache(self):
        return space_overlays.invalidate_selected_space_overlay_cache(self)

    def _sync_selected_space_overlay(self):
        return space_overlays.sync_selected_space_overlay(self)

    def _clear_selected_space_overlay(self):
        return space_overlays.clear_selected_space_overlay(self)

    def _sync_selected_region_overlay(self):
        return space_overlays.sync_selected_region_overlay(self)

    def _clear_selected_region_overlay(self):
        return space_overlays.clear_selected_region_overlay(self)

    def _sync_hovered_opening_overlay(self):
        return opening_overlays.sync_hovered_opening_overlay(self)

    def _clear_hovered_opening_overlay(self):
        return opening_overlays.clear_hovered_opening_overlay(self)

    def _invalidate_hovered_opening_overlay_cache(self):
        return opening_overlays.invalidate_hovered_opening_overlay_cache(self)

    def _create_opening_overlay_trackers(self, opening, color, width, tracker_store):
        return opening_overlays.create_opening_overlay_trackers(
            self,
            opening,
            color=color,
            width=width,
            tracker_store=tracker_store,
        )

    def _get_opening_overlay_segments(self, opening):
        return overlay_geometry.get_opening_overlay_segments(self, opening)

    def _sync_selected_opening_overlay(self):
        return opening_overlays.sync_selected_opening_overlay(self)

    def _clear_selected_opening_overlay(self):
        return opening_overlays.clear_selected_opening_overlay(self)

    def _invalidate_selected_opening_overlay_cache(self):
        return opening_overlays.invalidate_selected_opening_overlay_cache(self)

    def _sync_selected_wall_opening_context_overlay(self):
        return opening_overlays.sync_selected_wall_opening_context_overlay(self)

    def _clear_selected_wall_opening_context_overlay(self):
        return opening_overlays.clear_selected_wall_opening_context_overlay(self)

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
        return symbol_overlays.get_symbol_global_placement(self, symbol, placement=placement)

    def _get_symbol_parent_global_placement(self, symbol, placement=None):
        return symbol_overlays.get_symbol_parent_global_placement(self, symbol, placement=placement)

    def _get_symbol_plan_proxy(self, symbol, *attrs):
        return symbol_overlays.get_symbol_plan_proxy(self, symbol, *attrs)

    def _get_symbol_semantic_proxy(self, symbol, *attrs):
        return symbol_overlays.get_symbol_semantic_proxy(self, symbol, *attrs)

    def _get_symbol_overlay_polylines(self, symbol, placement=None):
        return symbol_overlays.get_symbol_overlay_polylines(self, symbol, placement=placement)

    def _get_symbol_overlay_segments(self, symbol, placement=None):
        return symbol_overlays.get_symbol_overlay_segments(self, symbol, placement=placement)

    def _refresh_selected_symbol_visuals(self):
        return symbol_overlays.refresh_selected_symbol_visuals(self)

    def _create_symbol_overlay_trackers(self, symbol, color, width, tracker_store, placement=None):
        return symbol_overlays.create_symbol_overlay_trackers(
            self,
            symbol,
            color=color,
            width=width,
            tracker_store=tracker_store,
            placement=placement,
        )

    def _sync_hovered_symbol_overlay(self):
        return symbol_overlays.sync_hovered_symbol_overlay(self)

    def _clear_hovered_symbol_overlay(self):
        return symbol_overlays.clear_hovered_symbol_overlay(self)

    def _sync_selected_symbol_overlay(self):
        return symbol_overlays.sync_selected_symbol_overlay(self)

    def _clear_selected_symbol_overlay(self):
        return symbol_overlays.clear_selected_symbol_overlay(self)

    def _get_symbol_local_anchor(self, symbol):
        return symbol_overlays.get_symbol_local_anchor(self, symbol)

    def _get_symbol_local_facing(self, symbol):
        return symbol_overlays.get_symbol_local_facing(self, symbol)

    def _get_symbol_anchor_point(self, symbol, placement=None):
        return symbol_overlays.get_symbol_anchor_point(self, symbol, placement=placement)

    def _get_symbol_facing_vector(self, symbol, placement=None):
        return symbol_overlays.get_symbol_facing_vector(self, symbol, placement=placement)

    def _symbol_rotation_snap_enabled(self):
        return symbol_overlays.symbol_rotation_snap_enabled(self)

    def _get_symbol_rotation_snap_increment_degrees(self):
        return symbol_overlays.get_symbol_rotation_snap_increment_degrees(self)

    def _get_symbol_rotation_snap_step_radians(self):
        return symbol_overlays.get_symbol_rotation_snap_step_radians(self)

    def _format_symbol_rotation_snap_label(self):
        return symbol_overlays.format_symbol_rotation_snap_label(self)

    def _symbol_rotation_free_angle_override_active(self):
        return symbol_overlays.symbol_rotation_free_angle_override_active(self)

    def _resolve_symbol_handle_target_point(self, symbol, handle_role, point, placement=None):
        return symbol_overlays.resolve_symbol_handle_target_point(
            self,
            symbol,
            handle_role,
            point,
            placement=placement,
        )

    def _get_symbol_handle_radius(self, symbol, placement=None):
        return symbol_overlays.get_symbol_handle_radius(self, symbol, placement=placement)

    def _get_selected_symbol_handle_specs(self, symbol):
        return symbol_overlays.get_selected_symbol_handle_specs(self, symbol)

    def _sync_selected_symbol_handles(self):
        return symbol_overlays.sync_selected_symbol_handles(self)

    def _clear_selected_symbol_handles(self):
        return symbol_overlays.clear_selected_symbol_handles(self)

    def _pick_selected_symbol_handle(self, mouse_pos, radius_px=10):
        return symbol_overlays.pick_selected_symbol_handle(self, mouse_pos, radius_px=radius_px)

    def _sync_symbol_edit_preview(self, symbol, placement, guide_start=None, guide_end=None):
        return symbol_overlays.sync_symbol_edit_preview(
            self,
            symbol,
            placement,
            guide_start=guide_start,
            guide_end=guide_end,
        )

    def _clear_symbol_edit_preview(self):
        return symbol_overlays.clear_symbol_edit_preview(self)

    def _get_symbol_handle_placement(self, symbol, handle_role, point):
        return plan_symbol_edit.get_symbol_handle_placement(self, symbol, handle_role, point)

    def _activate_symbol_handle(self, symbol, handle_role):
        return plan_symbol_edit.activate_symbol_handle(self, symbol, handle_role)

    def _activate_symbol_handle_now(self, symbol, handle_role):
        return plan_symbol_edit.activate_symbol_handle_now(self, symbol, handle_role)

    def _start_symbol_handle_point_pick(self, symbol, handle_role):
        return plan_symbol_edit.start_symbol_handle_point_pick(self, symbol, handle_role)

    def _update_symbol_handle_point_pick(self, point=None, snap_info=None):
        return plan_symbol_edit.update_symbol_handle_point_pick(
            self, point=point, snap_info=snap_info
        )

    def _finish_symbol_handle_point_pick(self, point=None, obj=None):
        return plan_symbol_edit.finish_symbol_handle_point_pick(self, point=point, obj=obj)

    def _cancel_symbol_handle_point_pick(self):
        return plan_symbol_edit.cancel_symbol_handle_point_pick(self)

    def _restore_selected_symbol(self, symbol):
        return plan_symbol_edit.restore_selected_symbol(self, symbol)

    def _queue_restore_selected_symbol(self, symbol):
        return plan_symbol_edit.queue_restore_selected_symbol(self, symbol)

    def _get_selected_opening_edit_handles(self, opening):
        return plan_opening_edit.get_selected_opening_edit_handles(self, opening)

    def _get_opening_plan_proxy(self, opening, *attrs):
        return plan_opening_edit.get_opening_plan_proxy(self, opening, *attrs)

    def _get_opening_view_proxy(self, opening, *attrs):
        return plan_opening_edit.get_opening_view_proxy(self, opening, *attrs)

    def _project_opening_handle_point(self, opening, handle, point):
        return plan_opening_edit.project_opening_handle_point(self, opening, handle, point)

    def _get_opening_move_anchor_modes(self, opening):
        return plan_opening_edit.get_opening_move_anchor_modes(self, opening)

    def _execute_opening_handle(self, opening, handle_index, point=None):
        return plan_opening_edit.execute_opening_handle(self, opening, handle_index, point=point)

    def _get_selected_opening_handle_specs(self, opening):
        return opening_overlays.get_selected_opening_handle_specs(self, opening)

    def _sync_selected_opening_handles(self):
        return opening_overlays.sync_selected_opening_handles(self)

    def _clear_selected_opening_handles(self):
        return opening_overlays.clear_selected_opening_handles(self)

    def _get_opening_move_preview_state(self, opening, point):
        return plan_opening_edit.get_opening_move_preview_state(self, opening, point)

    def _sync_opening_move_preview(self, opening, point):
        return plan_opening_edit.sync_opening_move_preview(self, opening, point)

    def _clear_opening_move_preview(self):
        return plan_opening_edit.clear_opening_move_preview(self)

    def _cycle_opening_move_anchor(self):
        return plan_opening_edit.cycle_opening_move_anchor(self)

    def _refresh_opening_move_preview_from_raw_point(self):
        return plan_opening_edit.refresh_opening_move_preview_from_raw_point(self)

    def _activate_opening_handle(self, opening, handle_index):
        return plan_opening_edit.activate_opening_handle(self, opening, handle_index)

    def _activate_opening_handle_now(self, opening, handle_index):
        return plan_opening_edit.activate_opening_handle_now(self, opening, handle_index)

    def _start_opening_handle_point_pick(self, opening, handle_index, handle):
        return plan_opening_edit.start_opening_handle_point_pick(
            self, opening, handle_index, handle
        )

    def _update_opening_handle_point_pick(self, point=None, snap_info=None):
        return plan_opening_edit.update_opening_handle_point_pick(
            self, point=point, snap_info=snap_info
        )

    def _finish_opening_handle_point_pick(self, point=None, obj=None):
        return plan_opening_edit.finish_opening_handle_point_pick(self, point=point, obj=obj)

    def _cancel_opening_handle_point_pick(self):
        return plan_opening_edit.cancel_opening_handle_point_pick(self)

    def _restore_selected_opening(self, opening):
        return plan_opening_edit.restore_selected_opening(self, opening)

    def _queue_restore_selected_opening(self, opening):
        return plan_opening_edit.queue_restore_selected_opening(self, opening)

    def _clear_plan_selection_state(self):
        self._set_gui_selection([])
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._sync_secondary_selected_overlays()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._sync_selected_region_overlay()
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _execute_selected_opening_handle(self, opening, handle_index, handle):
        return plan_opening_edit.execute_selected_opening_handle(
            self, opening, handle_index, handle
        )

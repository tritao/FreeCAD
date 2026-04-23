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
import os

import FreeCAD
import FreeCADGui
from bimplan import picking as plan_picking
from bimplan import command_gate as plan_command_gate
from bimplan import document_visuals as plan_document_visuals
from bimplan import hosted_openings as plan_hosted_openings
from bimplan import input as plan_input
from bimplan import performance as plan_performance
from bimplan import provider_runtime as plan_provider_runtime
from bimplan import provider_targets as plan_provider_targets
from bimplan import selection as plan_selection
from bimplan import snap as plan_snap
from bimplan import spaces as plan_spaces
from bimplan import task_panel as plan_task_panel
from bimplan import symbol_edit as plan_symbol_edit
from bimplan import opening_edit as plan_opening_edit
from bimplan import provider_edit as plan_provider_edit
from bimplan import targets as plan_targets
from bimplan import view as plan_view
from bimplan import wall_create as plan_wall_create
from bimplan import wall_edit as plan_wall_edit
from bimplan import wall_relations as plan_wall_relations
from bimplan import window_create as plan_window_create
from bimplan import window_edit as plan_window_edit
from bimplan.context import PlanEditContext
from bimplan.hosts import _PlanEditCommandHost, _PlanEditWallHost
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
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
_PRIMARY_PLAN_TARGET_KINDS = ("wall", "opening", "symbol", "provider", "region", "space")
_OPENING_VISUAL_PROPERTIES = plan_document_visuals.OPENING_VISUAL_PROPERTIES
_WALL_VISUAL_PROPERTIES = plan_document_visuals.WALL_VISUAL_PROPERTIES
_SYMBOL_VISUAL_PROPERTIES = plan_document_visuals.SYMBOL_VISUAL_PROPERTIES
_SPACE_VISUAL_PROPERTIES = plan_document_visuals.SPACE_VISUAL_PROPERTIES
_REGION_VISUAL_PROPERTIES = plan_document_visuals.REGION_VISUAL_PROPERTIES
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
_PLAN_VISUAL_HOVERED_PROVIDER = "hovered_provider"
_PLAN_VISUAL_HOVERED_SPACE = "hovered_space"
_PLAN_VISUAL_HOVERED_REGION = "hovered_region"
_PLAN_VISUAL_SELECTED_PROVIDER = "selected_provider"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
_PLAN_VISUAL_SELECTED_SPACE = "selected_space"
_PLAN_VISUAL_SELECTED_REGION = "selected_region"
_PLAN_VISUAL_SECONDARY_SELECTION = "secondary_selection"
_PLAN_VISUAL_SPACE_REGION_PICK = "space_region_pick"
_PLAN_VISUAL_WALL_GRIPS = "wall_grips"
_PLAN_VISUAL_WALL_EDIT_PREVIEW = "wall_edit_preview"
_PLAN_VISUAL_PROVIDER_OVERLAYS = "provider_overlays"
_PLAN_VISUAL_VIEW_SCALE = "view_scale"
_PLAN_VISUAL_ALL = "all"
_PLAN_PROVIDER_OVERLAY_MODE_ALL = "all"
_PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE = "architecture"
_PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL = "electrical"
_PLAN_PROVIDER_OVERLAY_MODE_PLUMBING = "plumbing"
_PLAN_GUI_SELECTION_SYNC_DELAY_MS = 80
_PLAN_WALL_GRIP_REFRESH_DELAY_MS = 120
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


def _register_builtin_plan_edit_integrations():
    try:
        from bimplan.window_provider import register_plan_edit_providers

        register_plan_edit_providers()
    except Exception as exc:
        try:
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "BIM Plan Edit window provider registration failed: {error}\n",
                ).format(error=exc)
            )
        except Exception:
            pass


def start_session():
    global _active_session

    if _active_session:
        return _active_session

    _register_builtin_plan_edit_integrations()
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
        self.hovered_provider = None
        self.hovered_space = None
        self.hovered_region = None
        self._hover_pick_dirty = False
        self._hover_pick_last_time = 0.0
        self._hover_pick_last_mouse_pos = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._secondary_selected_plan_targets_state = []
        self._grip_trackers = []
        self._wall_grip_state = None
        self._wall_grip_sync_queued = False
        self._wall_grip_sync_generation = 0
        self._wall_hover_trackers = []
        self._wall_overlay_trackers = []
        self._junction_node_trackers = []
        self._hovered_wall_opening_context_trackers = []
        self._opening_hover_trackers = []
        self._symbol_hover_trackers = []
        self._provider_hover_trackers = []
        self._provider_selected_trackers = []
        self._space_hover_trackers = []
        self._region_hover_trackers = []
        self._plan_overlay_geometry_cache = {
            "opening": {},
            "space": {},
            "region": {},
        }
        self._plan_semantic_object_cache = {}
        self._plan_object_storeys_cache = {}
        self._plan_symbol_instances_cache = None
        self._plan_space_instances_cache = None
        self._plan_region_instances_cache = None
        self._plan_opening_instances_cache = None
        self._wall_hosted_openings_cache = None
        self._wall_hosted_openings_cache_queued = False
        self._plan_hover_pick_cache_queued = False
        self._opening_overlay_screen_cache = {}
        self._opening_overlay_screen_cache_projection_key = None
        self._symbol_overlay_screen_cache = {}
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
        self._provider_overlay_trackers = []
        self._provider_overlay_state = None
        self._selected_provider_overlay_render_state = None
        self._provider_handle_trackers = []
        self._selected_provider_handle_render_state = None
        self._provider_overlay_visibility = {}
        self._provider_overlay_mode = _PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE
        self._provider_selected_objects = []
        self._provider_point_host_target = None
        self._provider_point_host_source = ""
        self._provider_point_preview_trackers = []
        self._provider_point_preview_render_state = None
        self._provider_point_preview_style_state = None
        self._provider_point_preview_source_point = None
        self._provider_point_preview_point = None
        self._provider_point_preview_host_target = None
        self._provider_point_preview_host_source = ""
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
        self._selection_refresh_queued = False
        self._gui_selection_sync_queued = False
        self._gui_selection_sync_generation = 0
        self._queued_gui_selection_object = None
        self._document_observer_added = False
        self._pending_created_plan_objects = {}
        self._created_plan_objects_flush_queued = False
        self._created_plan_objects_flush_deferred = False
        self._document_visual_update_defer_depth = 0
        self._document_visual_refresh_deferred = False
        self._pending_selected_wall_reset = False
        self._wall_edit_modal_active = False
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._wall_edit_opening_clearances_queued = False
        self._wall_edit_task_panel_refresh_queued = False
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
        self._window_host_wall = None
        self._window_preview_trackers = []
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
        self._edit_provider = None
        self._edit_provider_handle_index = None
        self._edit_provider_handle = None
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
        self._saved_preselection_state = None
        self._plan_preselection_forced = False
        self._saved_object_view_state = {}
        self._working_plane = None
        self._interaction_plane = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._provider_point_tool = None
        self._finishing = False
        self._tearing_down = False
        self._teardown_signal_sources = []
        self._plan_edit_params = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
        )
        self._plan_perf_log_path = self._resolve_plan_perf_log_path()
        self._plan_pick_debug_log_path = self._resolve_plan_pick_debug_log_path()
        self._plan_perf_current_event = None
        self._plan_perf_sequence = 0
        self._plan_pick_debug_sequence = 0
        self._plan_pick_debug_scope_depth = 0
        self._plan_pick_debug_scope_name = ""
        self._plan_provider_refresh_cache = None
        self._plan_provider_document_cache = {}
        self._plan_provider_target_collection_depth = 0
        self._connect_teardown_signals(QtGui)

    def _connect_teardown_signal(self, signal):
        try:
            signal.connect(self.begin_teardown)
        except Exception:
            return
        self._teardown_signal_sources.append(signal)

    def _connect_teardown_signals(self, QtGui):
        app = QtGui.QApplication.instance()
        if app:
            self._connect_teardown_signal(app.aboutToQuit)
        main_window = self._get_main_window()
        if main_window:
            try:
                signal = main_window.mainWindowClosed
            except AttributeError:
                signal = None
            if signal is not None:
                self._connect_teardown_signal(signal)

    def _disconnect_teardown_signals(self):
        for signal in self._teardown_signal_sources:
            try:
                signal.disconnect(self.begin_teardown)
            except Exception:
                pass
        self._teardown_signal_sources = []

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
        return plan_selection.get_plan_target_object_from_state(state_kind, state_obj, kind)

    def _selected_plan_target_changed(self, previous_kind, previous_obj, kind=None):
        return plan_selection.selected_plan_target_changed(
            self,
            previous_kind,
            previous_obj,
            kind=kind,
        )

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

    def _invalidate_plan_classification_cache(self):
        self._plan_semantic_object_cache.clear()
        self._plan_object_storeys_cache.clear()
        self._plan_symbol_instances_cache = None
        self._plan_space_instances_cache = None
        self._plan_region_instances_cache = None
        self._symbol_overlay_screen_cache.clear()

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
            "hovered_provider",
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

    def _resolve_plan_pick_debug_log_path(self):
        return plan_performance.resolve_plan_pick_debug_log_path(self)

    def _is_plan_perf_trace_enabled(self):
        return plan_performance.is_plan_perf_trace_enabled(self)

    def _is_plan_pick_debug_enabled(self):
        return plan_performance.is_plan_pick_debug_enabled(self)

    def _is_plan_pick_debug_active(self):
        return bool(getattr(self, "_plan_pick_debug_scope_depth", 0))

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

    def _plan_pick_debug_event(self, name, **fields):
        return plan_performance.plan_pick_debug_event(self, name, **fields)

    @contextmanager
    def _plan_pick_debug_scope(self, name, **fields):
        if not self._is_plan_pick_debug_enabled():
            yield None
            return
        previous_name = str(getattr(self, "_plan_pick_debug_scope_name", "") or "")
        previous_depth = int(getattr(self, "_plan_pick_debug_scope_depth", 0) or 0)
        self._plan_pick_debug_scope_name = str(name or "").strip()
        self._plan_pick_debug_scope_depth = previous_depth + 1
        self._plan_pick_debug_event(f"{name}_start", **fields)
        try:
            yield None
        finally:
            selected_after = self._get_selected_plan_target()
            self._plan_pick_debug_event(
                f"{name}_end",
                selected_after=self._plan_perf_describe_target(
                    selected_after[0],
                    selected_after[1],
                ),
                provider_selected_objects=[
                    self._plan_perf_describe_object(obj)
                    for obj in tuple(getattr(self, "_provider_selected_objects", ()) or ())
                ],
            )
            self._plan_pick_debug_scope_depth = previous_depth
            self._plan_pick_debug_scope_name = previous_name

    def enter(self):
        with self._plan_perf_trace_event("enter_plan_edit"):
            self._plan_perf_count("document_objects", len(getattr(self.doc, "Objects", []) or []))
            if not self.doc or not self.gui_doc:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
                )
                return False

            with self._plan_perf_trace_span("enter_acquire_view"):
                self.view = self.gui_doc.ActiveView
                get_viewer = self._get_runtime_attr(self.view, "getViewer")
                if self.view is None or get_viewer is None:
                    FreeCAD.Console.PrintError(
                        translate(
                            "BIM_PlanEdit",
                            "Plan Edit requires an active 3D Inventor view.\n",
                        )
                    )
                    return False

                try:
                    self.viewer = get_viewer()
                except (AttributeError, ReferenceError, RuntimeError):
                    self._discard_stale_runtime_object(self.view)
                    FreeCAD.Console.PrintError(
                        translate(
                            "BIM_PlanEdit",
                            "Plan Edit requires an active 3D Inventor view.\n",
                        )
                    )
                    return False

            with self._plan_perf_trace_span("capture_plan_edit_state"):
                self._capture_state()
            with self._plan_perf_trace_span("force_plan_preselection"):
                self._force_plan_preselection()

            with self._plan_perf_trace_span("collect_storeys"):
                self.storeys = self.collect_storeys()
                self._plan_perf_count("storeys_found", len(self.storeys))
            with self._plan_perf_trace_span("find_initial_storey"):
                self.active_storey = self.find_initial_storey()
                self._plan_perf_set_fields(
                    active_storey=self._plan_perf_describe_object(self.active_storey)
                )
            with self._plan_perf_trace_span("capture_object_view_state"):
                self._capture_object_view_state()
            with self._plan_perf_trace_span("apply_plan_view"):
                self.apply_plan_view(fit=False)
            with self._plan_perf_trace_span("apply_plan_snap_profile"):
                self._apply_plan_snap_profile()
            self._apply_storey_visibility()
            with self._plan_perf_trace_span("attach_selection_observer"):
                self._attach_selection_observer()
            with self._plan_perf_trace_span("attach_document_observer"):
                self._attach_document_observer()
            with self._plan_perf_trace_span("register_edit_callbacks"):
                self._register_edit_callbacks()
            with self._plan_perf_trace_span("refresh_primary_selected_plan_target_on_enter"):
                self._refresh_primary_selected_plan_target()

            with self._plan_perf_trace_span("build_task_panel"):
                panel = PlanEditControlsWidget(self)
            with self._plan_perf_trace_span("attach_task_panel"):
                self.attach_task_panel(panel)
            with self._plan_perf_trace_span("task_panel_initial_refresh"):
                panel.refresh(refresh_integrations=False)
            with self._plan_perf_trace_span("queue_prime_opening_handle_tracker_pool"):
                self._queue_prime_opening_handle_tracker_pool()
            with self._plan_perf_trace_span("queue_prime_wall_hosted_openings_cache"):
                self._queue_prime_wall_hosted_openings_cache()
            with self._plan_perf_trace_span("queue_prime_hover_pick_caches"):
                self._queue_prime_hover_pick_caches()
            with self._plan_perf_trace_span("install_command_gate"):
                plan_command_gate.install(self)
            if self._is_plan_perf_trace_enabled():
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "BIM Plan Edit perf trace: {path}\n").format(
                        path=self._plan_perf_log_path
                    )
                )
            if self._is_plan_pick_debug_enabled():
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "BIM Plan Edit pick debug: {path}\n").format(
                        path=self._plan_pick_debug_log_path
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
        if self.current_tool == "Move Provider":
            self._cancel_provider_handle_point_pick()
            return True
        if self.current_tool == "Move Opening":
            self._cancel_opening_handle_point_pick()
            return True
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
        if self.current_tool == "Window":
            self._cancel_window_tool()
            return True
        if self._has_active_provider_point_tool():
            self._cancel_provider_point_tool()
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
        plan_command_gate.uninstall(self)
        self._clear_viewport_status_chip()
        self._clear_input_hints()
        self._cancel_embedded_tool()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_window_tool(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        if self.current_tool == "Move Provider":
            self._cancel_provider_handle_point_pick()
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
        self._clear_selected_wall_overlay()
        self._clear_hovered_opening_overlay()
        self._clear_hovered_symbol_overlay()
        self._clear_hovered_provider_overlay()
        self._clear_hovered_space_overlay()
        self._clear_hovered_region_overlay()
        self._clear_selected_provider_overlay()
        self._clear_selected_provider_handles()
        self._clear_selected_opening_overlay()
        self._clear_selected_symbol_overlay()
        self._clear_selected_space_overlay()
        self._clear_selected_region_overlay()
        self._clear_provider_overlays()
        self._clear_provider_point_preview()
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
        if doc is None:
            return False
        try:
            _ = doc.Name
            return True
        except Exception:
            self.doc = None
            return False

    def _discard_runtime_references(self):
        self._clear_viewport_status_chip()
        self._restore_preselection_state()
        self.doc = None
        self.gui_doc = None
        self.view = None
        self.viewer = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self._saved_preselection_state = None
        self._plan_preselection_forced = False
        self._set_selected_plan_target_state()
        self._provider_selected_objects = []
        self._provider_point_host_target = None
        self._provider_point_host_source = ""
        self._provider_point_preview_render_state = None
        self._provider_point_preview_style_state = None
        self._provider_point_preview_source_point = None
        self._provider_point_preview_point = None
        self._provider_point_preview_host_target = None
        self._provider_point_preview_host_source = ""
        self._secondary_selected_plan_targets_state = []
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self.hovered_provider = None
        self.hovered_space = None
        self.hovered_region = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._plan_provider_target_collection_depth = 0
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

    def _force_plan_preselection(self):
        return plan_view.force_plan_preselection(self)

    def _restore_preselection_state(self):
        return plan_view.restore_preselection_state(self)

    def shutdown(self, close_dialog=True, teardown=False):
        global _active_session

        if self._finishing:
            return True
        self._finishing = True

        try:
            plan_command_gate.uninstall(self)
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
            self._clear_selected_wall_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_provider_overlay()
            self._clear_selected_provider_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
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
            self._disconnect_teardown_signals()
            self._tearing_down = True
            self._discard_runtime_references()
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
        try:
            placement = getattr(obj, "Placement", None)
        except Exception:
            return 0.0
        if placement is not None:
            try:
                return placement.Base.z
            except Exception:
                return 0.0
        return 0.0

    def get_storey_label(self, obj):
        if obj is None:
            return translate("BIM_PlanEdit", "Global XY (Z=0)")
        elevation = FreeCAD.Units.Quantity(
            self.get_storey_elevation(obj), FreeCAD.Units.Length
        ).UserString
        try:
            label = str(getattr(obj, "Label", "") or getattr(obj, "Name", "") or "")
        except Exception:
            return translate("BIM_PlanEdit", "Global XY (Z=0)")
        return f"{label} [{elevation}]"

    def set_active_storey(self, storey):
        self.active_storey = storey
        self.apply_plan_view(fit=False)
        self._apply_storey_visibility()
        self._refresh_task_panel_status()

    def get_plan_provider_registry(self):
        return get_plan_edit_registry()

    @contextmanager
    def _plan_provider_refresh_cache_scope(self):
        previous_cache = self._plan_provider_refresh_cache
        self._plan_provider_refresh_cache = {}
        try:
            yield self._plan_provider_refresh_cache
        finally:
            self._plan_provider_refresh_cache = previous_cache

    def _invalidate_plan_provider_document_cache(self):
        self._plan_provider_document_cache = {}

    def _plan_provider_integrations_disabled(self):
        env_value = str(os.environ.get("FC_BIM_PLAN_EDIT_DISABLE_INTEGRATIONS", "") or "").strip()
        if env_value:
            return env_value not in {"0", "false", "False", "no", "off"}
        try:
            return bool(self._plan_edit_params.GetBool("DisableIntegrations", False))
        except Exception:
            return False

    def get_plan_provider_display_name(self, provider_id):
        return plan_provider_runtime.get_plan_provider_display_name(self, provider_id)

    def _safe_plan_object_name(self, obj):
        if obj is None:
            return ""
        try:
            return str(getattr(obj, "Name", "") or "")
        except Exception:
            return ""

    def get_plan_edit_context(self):
        doc = self.doc if self._document_is_alive() else None
        active_storey = self.active_storey
        active_storey_name = self._safe_plan_object_name(active_storey)
        if active_storey is not None and not active_storey_name:
            active_storey = None
            self.active_storey = None
        return PlanEditContext(
            session=self,
            document_name=self._safe_plan_object_name(doc),
            active_storey_name=active_storey_name,
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
        if self._has_active_provider_point_tool():
            self._cancel_provider_point_tool()
            return
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        if self._has_active_window_tool():
            self._cancel_window_tool()
        if self._has_active_plan_region_tool():
            self._cancel_plan_region_tool()
        if self._has_active_space_separator_tool():
            self._cancel_space_separator_tool()
        self._cancel_wall_edit()
        self._cancel_join_tool()

    def activate_wall_tool(self):
        return plan_wall_create.activate_wall_tool(self)

    def activate_rect_wall_tool(self):
        return plan_wall_create.activate_rect_wall_tool(self)

    def can_place_plan_window(self):
        return plan_window_create.can_place_window(self)

    def activate_window_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._clear_selected_wall_overlay()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._clear_selected_symbol_overlay()
        self._clear_selected_space_overlay()
        self._clear_selected_region_overlay()
        self._clear_secondary_selected_overlays()
        self._clear_window_preview()
        return plan_window_create.activate_window_tool(self)

    def activate_plan_region_tool(self):
        parent_space = self._get_selected_plan_target_object("space")
        self._cancel_space_region_pick(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_window_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_provider(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._clear_selected_wall_overlay()
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
        self._cancel_window_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_overlay()
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
        self._cancel_window_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
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
        self._cancel_window_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_provider_point_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._clear_selected_wall_overlay()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        return plan_wall_relations.activate_join_tool(self)

    def get_plan_join_type(self):
        return plan_wall_relations.get_plan_join_type(self)

    def get_plan_join_types(self):
        return plan_wall_relations.get_plan_join_types(self)

    def _normalize_plan_join_type(self, join_type):
        return plan_wall_relations.normalize_plan_join_type(self, join_type)

    def get_plan_join_type_label(self, join_type=None):
        return plan_wall_relations.get_plan_join_type_label(self, join_type=join_type)

    def _get_plan_join_type_phrase(self, join_type=None):
        return plan_wall_relations.get_plan_join_type_phrase(self, join_type=join_type)

    def _get_plan_join_action_text(self, join_type=None):
        return plan_wall_relations.get_plan_join_action_text(self, join_type=join_type)

    def set_plan_join_type(self, join_type, refresh=True):
        return plan_wall_relations.set_plan_join_type(self, join_type, refresh=refresh)

    def _cycle_plan_join_type(self):
        return plan_wall_relations.cycle_plan_join_type(self)

    def _get_plan_join_command(self):
        return plan_wall_relations.get_plan_join_command(self)

    def _get_plan_join_candidate_wall(self):
        return plan_wall_relations.get_plan_join_candidate_wall(self)

    def _get_plan_candidate_joint(self, target_wall=None):
        return plan_wall_relations.get_plan_candidate_joint(self, target_wall=target_wall)

    def _get_plan_join_candidate_state(self):
        return plan_wall_relations.get_plan_join_candidate_state(self)

    def _get_plan_join_mode_action_text(self, target_wall=None, joint=None):
        return plan_wall_relations.get_plan_join_mode_action_text(
            self,
            target_wall=target_wall,
            joint=joint,
        )

    def _unjoin_plan_wall_pair(self, source_wall, target_wall):
        return plan_wall_relations.unjoin_plan_wall_pair(self, source_wall, target_wall)

    def _unjoin_current_plan_wall_pair(self):
        return plan_wall_relations.unjoin_current_plan_wall_pair(self)

    @staticmethod
    def _iter_unique_wall_sets(source_wall, target_wall, extra_walls):
        return plan_wall_relations.iter_unique_wall_sets(source_wall, target_wall, extra_walls)

    def _find_plan_junction_promotion(self, source_wall, target_wall):
        return plan_wall_relations.find_plan_junction_promotion(self, source_wall, target_wall)

    @staticmethod
    def _find_reusable_plan_junction(candidate_relations, walls):
        return plan_wall_relations.find_reusable_plan_junction(candidate_relations, walls)

    def _apply_plan_wall_junction_promotion(self, doc, source_wall, target_wall):
        return plan_wall_relations.apply_plan_wall_junction_promotion(
            self,
            doc,
            source_wall,
            target_wall,
        )

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
        return plan_wall_create.get_wall_defaults(self)

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
        with self._plan_perf_trace_span("capture_object_view_state_objects"):
            for obj in self.doc.Objects:
                self._plan_perf_count("capture_view_state_objects_scanned")
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
        self._register_plan_objects((obj,))

    def _register_plan_objects(self, objects):
        registered = []
        seen_names = set()
        for obj in tuple(objects or ()):
            if not obj:
                continue
            name = getattr(obj, "Name", None)
            if name and name in seen_names:
                continue
            if name:
                seen_names.add(name)
            self._add_object_to_active_storey(obj)
            self._register_object_view_state(obj)
            registered.append(obj)
        if not registered:
            return
        self._apply_storey_visibility()
        for obj in registered:
            self._refresh_plan_object_footprint_display(obj, request_redraw=False)
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
        key = self._get_document_object_key(obj)
        if key is not None and key in self._plan_semantic_object_cache:
            self._plan_perf_count("semantic_object_cache_hits")
            return self._plan_semantic_object_cache[key]

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
        result = owner or current or obj
        if key is not None:
            self._plan_semantic_object_cache[key] = result
        return result

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

    def _is_cabinetry_plan_context_object(self, obj):
        if not obj:
            return False
        proxy_type = str(getattr(getattr(obj, "Proxy", None), "Type", "") or "")
        return proxy_type in {
            "CabinetryApplianceTower",
            "CabinetryBaseCabinet",
            "CabinetryBlindCornerBaseCabinet",
            "CabinetryFridgeSurround",
            "CabinetryProject",
            "CabinetryRunAccessories",
            "CabinetryRunApplianceRepresentation",
            "CabinetryRunGuide",
            "CabinetryRunProfileRepresentation",
            "CabinetryRunReservation",
            "CabinetryRunReservationRepresentation",
            "CabinetryTallCabinet",
            "CabinetryVanityBase",
            "CabinetryWallCabinet",
            "CabinetZone",
            "CabinetRun",
            "CabinetRunJunction",
        }

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
            or self._is_cabinetry_plan_context_object(obj)
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
        return plan_hosted_openings.is_hosted_opening_object(self, obj)

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
        # Openings, spaces, and plan regions are selected through Plan Edit's
        # semantic picking paths. Leaving their native 3D view objects
        # selectable lets the viewer replace the intended target with
        # overlapping native hits on button release.
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
        key = self._get_document_object_key(obj)
        if key is not None and key in self._plan_object_storeys_cache:
            self._plan_perf_count("object_storeys_cache_hits")
            return list(self._plan_object_storeys_cache[key])

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
        if key is not None:
            self._plan_object_storeys_cache[key] = tuple(storeys)
        return storeys

    def _apply_storey_visibility(self):
        with self._plan_perf_trace_span(
            "apply_storey_visibility",
            active_storey=self._plan_perf_describe_object(self.active_storey),
        ):
            if not self.doc or not self._saved_object_view_state:
                return

            active_storey_name = getattr(self.active_storey, "Name", None)

            if active_storey_name is None:
                with self._plan_perf_trace_span("restore_object_view_state_for_global_plan"):
                    self._restore_object_view_state()
                for obj in self.doc.Objects:
                    self._plan_perf_count("storey_visibility_objects_scanned")
                    view_object = getattr(obj, "ViewObject", None)
                    state = self._saved_object_view_state.get(obj.Name, {})
                    if not self._is_supported_plan_object(obj):
                        self._plan_perf_count("storey_visibility_hidden_unsupported")
                        self._apply_hidden_object_state(view_object)
                        continue
                    self._plan_perf_count("storey_visibility_supported")
                    if view_object and hasattr(view_object, "Visibility"):
                        try:
                            view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                        except Exception:
                            pass
                    self._apply_context_object_selectability(obj, view_object)
                return

            for obj in self.doc.Objects:
                self._plan_perf_count("storey_visibility_objects_scanned")
                view_object = getattr(obj, "ViewObject", None)
                state = self._saved_object_view_state.get(obj.Name)
                if not view_object or not state:
                    self._plan_perf_count("storey_visibility_objects_skipped_no_view_state")
                    continue

                storeys = self._get_object_storeys(obj)
                if not storeys:
                    self._plan_perf_count("storey_visibility_global_objects")
                    if not self._is_supported_plan_object(obj):
                        self._plan_perf_count("storey_visibility_hidden_unsupported")
                        self._apply_hidden_object_state(view_object)
                        continue
                    self._plan_perf_count("storey_visibility_supported")
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
                    self._plan_perf_count("storey_visibility_active_storey_objects")
                    for prop, value in state.items():
                        if hasattr(view_object, prop):
                            try:
                                setattr(view_object, prop, value)
                            except Exception:
                                pass
                    if not self._is_supported_plan_object(obj):
                        self._plan_perf_count("storey_visibility_hidden_unsupported")
                        self._apply_hidden_object_state(view_object)
                        continue
                    self._plan_perf_count("storey_visibility_supported")
                    if hasattr(view_object, "Visibility"):
                        try:
                            view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                        except Exception:
                            pass
                    self._apply_context_object_selectability(obj, view_object)
                    continue

                self._plan_perf_count("storey_visibility_other_storey_objects")
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

    def _schedule_selection_refresh(self):
        return plan_selection.schedule_selection_refresh(self)

    def _run_scheduled_selection_refresh(self):
        return plan_selection.run_scheduled_selection_refresh(self)

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
        return plan_spaces.get_space_reference_point(self, space)

    def _get_space_boundary_reference_point(self, selection_ex, fallback_space=None):
        return plan_spaces.get_space_boundary_reference_point(
            self,
            selection_ex,
            fallback_space=fallback_space,
        )

    def _get_space_boundary_entries(self, space):
        return plan_spaces.get_space_boundary_entries(self, space)

    def _space_boundary_key(self, boundary):
        return plan_spaces.space_boundary_key(boundary)

    def _get_selected_space_boundary_links(self, fallback_space=None):
        return plan_spaces.get_selected_space_boundary_links(
            self,
            fallback_space=fallback_space,
        )

    def _get_space_region_seed_targets(self, targets=None):
        return plan_spaces.get_space_region_seed_targets(self, targets=targets)

    def _get_selected_space_region_seed(self, targets=None):
        return plan_spaces.get_selected_space_region_seed(self, targets=targets)

    def _copy_shape_without_element_map(self, shape):
        return plan_spaces.copy_shape_without_element_map(shape)

    def _get_space_creation_request(self, targets=None):
        return plan_spaces.get_space_creation_request(self, targets=targets)

    def _get_existing_space_region_filter_spaces(self, exclude=None):
        return plan_spaces.get_existing_space_region_filter_spaces(self, exclude=exclude)

    def _get_xy_bound_box_iou(self, first_shape, second_shape):
        return plan_spaces.get_xy_bound_box_iou(first_shape, second_shape)

    def _is_space_region_candidate_claimed(self, candidate, spaces, overlap_iou_tolerance=0.9):
        return plan_spaces.is_space_region_candidate_claimed(
            self,
            candidate,
            spaces,
            overlap_iou_tolerance=overlap_iou_tolerance,
        )

    def _filter_claimed_space_region_candidates(self, candidates, exclude_space=None):
        return plan_spaces.filter_claimed_space_region_candidates(
            self,
            candidates,
            exclude_space=exclude_space,
        )

    def _get_space_region_candidate_report(
        self,
        boundaries,
        label=None,
        seed_space=None,
    ):
        return plan_spaces.get_space_region_candidate_report(
            self,
            boundaries,
            label=label,
            seed_space=seed_space,
        )

    def _report_space_region_candidate_failure(self, report):
        return plan_spaces.report_space_region_candidate_failure(report)

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

    def _pick_plan_opening_target_from_overlays(self, mouse_pos, radius_px=10, candidates=None):
        return plan_picking.pick_plan_opening_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
            candidates=candidates,
        )

    def _pick_provider_overlay_target_from_overlays(self, mouse_pos, radius_px=12):
        return plan_picking.pick_provider_overlay_target_from_overlays(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _pick_provider_overlay_target_from_objects_info(self, mouse_pos):
        return plan_picking.pick_provider_overlay_target_from_objects_info(self, mouse_pos)

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
        return plan_document_visuals.has_direct_true_property(obj, prop_name)

    def _is_hidden_library_definition_object(self, obj):
        return plan_document_visuals.is_hidden_library_definition_object(obj)

    def _should_register_created_plan_object(self, obj):
        return plan_document_visuals.should_register_created_plan_object(self, obj)

    def _queue_created_plan_object(self, obj):
        return plan_document_visuals.queue_created_plan_object(self, obj)

    def _flush_created_plan_objects(self, force=False):
        return plan_document_visuals.flush_created_plan_objects(self, force=force)

    def _are_document_visual_updates_deferred(self):
        return plan_document_visuals.are_document_visual_updates_deferred(self)

    def _defer_document_visual_refresh(self):
        return plan_document_visuals.defer_document_visual_refresh(self)

    def defer_document_visual_updates(self):
        return plan_document_visuals.defer_document_visual_updates(self)

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

    def _schedule_gui_selection_object(self, obj, delay_ms=_PLAN_GUI_SELECTION_SYNC_DELAY_MS):
        return plan_selection.schedule_gui_selection_object(self, obj, delay_ms=delay_ms)

    def _run_scheduled_gui_selection_sync(self, generation=None):
        return plan_selection.run_scheduled_gui_selection_sync(self, generation=generation)

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

    def get_selected_objects(self):
        return tuple(
            self._normalize_gui_object_selection(
                tuple(self._get_gui_selection()) + tuple(self._provider_selected_objects)
            )
        )

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

    def _normalize_plan_provider_tool(self, provider_id, tool):
        return plan_provider_runtime.normalize_plan_provider_tool(provider_id, tool)

    def _normalize_plan_provider_edit_handle(self, provider_id, handle):
        return plan_provider_runtime.normalize_plan_provider_edit_handle(provider_id, handle)

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

    def _normalize_plan_provider_context_panel(self, provider_id, panel):
        return plan_provider_runtime.normalize_plan_provider_context_panel(
            self,
            provider_id,
            panel,
        )

    def _normalize_plan_provider_overlay(self, provider_id, overlay):
        return plan_provider_runtime.normalize_plan_provider_overlay(provider_id, overlay)

    def _normalize_plan_provider_target(self, provider_id, target):
        return plan_provider_targets.normalize_plan_provider_target(provider_id, target)

    def _collect_plan_provider_contributions(self, method_name, normalizer):
        if self._tearing_down or self._finishing or not self._document_is_alive():
            self._plan_perf_count("plan_provider_inactive_session")
            return ()
        if self._plan_provider_integrations_disabled():
            self._plan_perf_count("plan_provider_integrations_disabled")
            return ()
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

    def get_plan_provider_tools(self):
        return self._collect_plan_provider_contributions(
            "get_tools",
            self._normalize_plan_provider_tool,
        )

    def get_plan_provider_edit_handles(self):
        return plan_provider_runtime.get_plan_provider_edit_handles(self)

    def get_plan_provider_inspector_sections(self):
        return self._collect_plan_provider_contributions(
            "get_inspector_sections",
            self._normalize_plan_provider_section,
        )

    def get_plan_provider_context_panels(self):
        return self._collect_plan_provider_contributions(
            "get_context_panels",
            self._normalize_plan_provider_context_panel,
        )

    def get_plan_provider_overlays(self):
        return self._collect_plan_provider_contributions(
            "get_overlays",
            self._normalize_plan_provider_overlay,
        )

    def get_plan_provider_targets(self):
        return plan_provider_targets.get_plan_provider_targets(self)

    def _get_plan_provider_target_for_object(self, obj):
        return plan_provider_targets.get_plan_provider_target_for_object(self, obj)

    def _is_plan_provider_target_object(self, obj):
        return plan_provider_targets.is_plan_provider_target_object(self, obj)

    def get_plan_provider_overlay_visibility_key(self, provider_id, overlay_key):
        provider_id = str(provider_id or "").strip()
        overlay_key = str(overlay_key or "").strip()
        if not provider_id or not overlay_key:
            return None
        return (provider_id, overlay_key)

    def _normalize_plan_provider_overlay_mode(self, mode):
        normalized = str(mode or "").strip().lower()
        if normalized == _PLAN_PROVIDER_OVERLAY_MODE_ALL:
            return _PLAN_PROVIDER_OVERLAY_MODE_ALL
        if normalized == _PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
            return _PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
        if normalized == _PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
            return _PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
        return _PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE

    def get_plan_provider_overlay_mode(self):
        return self._normalize_plan_provider_overlay_mode(
            getattr(self, "_provider_overlay_mode", _PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE)
        )

    def set_plan_provider_overlay_mode(self, mode):
        normalized = self._normalize_plan_provider_overlay_mode(mode)
        if normalized == self.get_plan_provider_overlay_mode():
            return False
        self._provider_overlay_mode = normalized
        self._provider_overlay_state = None
        plan_selection.clear_hidden_provider_preselection(self)
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)
        self._refresh_provider_overlay_mode_panels()
        return True

    def get_plan_provider_overlay_category(self, overlay):
        category = str(getattr(overlay, "category", "") or "").strip().lower()
        if category == _PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
            return _PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
        if category == _PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
            return _PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
        return _PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE

    def is_plan_provider_overlay_enabled(self, overlay):
        key = self.get_plan_provider_overlay_visibility_key(
            getattr(overlay, "provider_id", ""),
            getattr(overlay, "key", ""),
        )
        if key is None:
            return True
        return self._provider_overlay_visibility.get(key, True)

    def is_plan_provider_overlay_visible_for_mode(self, overlay, mode=None):
        overlay_mode = self._normalize_plan_provider_overlay_mode(
            self.get_plan_provider_overlay_mode() if mode is None else mode
        )
        if overlay_mode == _PLAN_PROVIDER_OVERLAY_MODE_ALL:
            return True
        return self.get_plan_provider_overlay_category(overlay) == overlay_mode

    def is_plan_provider_overlay_visible(self, overlay):
        if not bool(getattr(overlay, "visible", True)):
            return False
        if not self.is_plan_provider_overlay_enabled(overlay):
            return False
        return self.is_plan_provider_overlay_visible_for_mode(overlay)

    def set_plan_provider_overlay_visible(self, provider_id, overlay_key, visible):
        key = self.get_plan_provider_overlay_visibility_key(provider_id, overlay_key)
        if key is None:
            return
        visible = bool(visible)
        if visible:
            self._provider_overlay_visibility.pop(key, None)
        else:
            self._provider_overlay_visibility[key] = False
        self._provider_overlay_state = None
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)

    def queue_plan_provider_overlay_refresh(self):
        self._provider_overlay_state = None
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)

    def queue_plan_provider_overlay_sync(self):
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)

    def execute_plan_provider_action(
        self,
        provider_id,
        action_key,
        transaction_label="",
        payload=None,
    ):
        if self._tearing_down or self._finishing or not self._document_is_alive():
            return False
        if self._plan_provider_integrations_disabled():
            return False
        return plan_provider_runtime.execute_plan_provider_action(
            self,
            provider_id,
            action_key,
            transaction_label=transaction_label,
            payload=payload,
        )

    def _has_active_provider_point_tool(self):
        return self.current_tool == "Provider Point" and self._provider_point_tool is not None

    def _get_provider_point_tool_label(self):
        tool = self._provider_point_tool
        if tool is None:
            return translate("BIM_PlanEdit", "Provider Point")
        label = str(getattr(tool, "label", "") or "").strip()
        if label:
            return label
        return str(getattr(tool, "key", "") or "").strip() or translate(
            "BIM_PlanEdit",
            "Provider Point",
        )

    def _get_provider_point_tool_prompt(self):
        tool = self._provider_point_tool
        if tool is None:
            return translate("BIM_PlanEdit", "Click a plan point")
        prompt = str(getattr(tool, "prompt", "") or "").strip()
        if prompt:
            return prompt
        return translate("BIM_PlanEdit", "Click a plan point for {tool}").format(
            tool=self._get_provider_point_tool_label()
        )

    def _arm_provider_point_tool(self):
        if not self._has_active_provider_point_tool():
            return False
        snapper = getattr(FreeCADGui, "Snapper", None)
        if snapper is None:
            return False
        FreeCAD.activeDraftCommand = self
        try:
            snapper.setSelectMode(False)
        except Exception:
            pass
        self._set_draft_point_focus_suppressed(True)
        try:
            snapper.getPoint(
                callback=self._handle_provider_point_tool_point,
                movecallback=self._update_provider_point_tool_preview,
                title=self._get_provider_point_tool_prompt(),
                noTracker=True,
            )
        except Exception:
            self._set_draft_point_focus_suppressed(False)
            return False
        self._queue_focus_plan_view()
        return True

    def _cancel_provider_point_tool(self, refresh=True):
        if not self._has_active_provider_point_tool():
            self._clear_provider_point_preview()
            return False
        self._stop_snapper()
        self._provider_point_tool = None
        self._provider_point_host_target = None
        self._provider_point_host_source = ""
        self._clear_provider_point_preview()
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)
        return True

    def start_plan_provider_point_tool(self, tool):
        if tool is None:
            return False
        if self._plan_provider_integrations_disabled():
            return False
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit(refresh=False)
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_provider(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._clear_selected_wall_overlay()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_opening_handles()
        self._clear_selected_symbol_handles()
        self._clear_provider_point_preview()
        host_kind, host_obj, host_source = self._get_provider_point_context_host_state()
        if host_obj is None:
            host_kind, host_obj = self._normalize_provider_point_host_target(
                getattr(tool, "default_host_target", ())
            )
            if host_obj is not None:
                host_source = "tool"
        self._provider_point_host_target = (host_kind, host_obj)
        self._provider_point_host_source = host_source
        self._provider_point_tool = tool
        self.current_tool = "Provider Point"
        self._refresh_task_panel_status()
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)
        if self._arm_provider_point_tool():
            return True
        self._provider_point_tool = None
        self._provider_point_host_target = None
        self._provider_point_host_source = ""
        self.current_tool = "Select"
        self._refresh_task_panel_status()
        return False

    def _handle_provider_point_tool_point(self, point=None, obj=None):
        if not self._has_active_provider_point_tool():
            return
        if point is None:
            self._cancel_provider_point_tool()
            return
        plan_point = self._project_plan_point(point)
        if plan_point is None:
            self._clear_provider_point_preview()
            self._arm_provider_point_tool()
            return
        tool = self._provider_point_tool
        snap_info = self._get_provider_point_snap_info()
        snap_object = self._resolve_provider_point_snap_object(obj, snap_info)
        payload = self._build_provider_point_tool_payload(
            tool,
            raw_point=point,
            plan_point=plan_point,
            snap_object=snap_object,
            snap_info=snap_info,
        )
        self.execute_plan_provider_action(
            getattr(tool, "provider_id", ""),
            getattr(tool, "key", ""),
            transaction_label=getattr(tool, "transaction_label", ""),
            payload=payload,
        )
        self._clear_provider_point_preview()
        if self._has_active_provider_point_tool():
            self._arm_provider_point_tool()

    def _update_provider_point_tool_preview(self, point=None, obj=None):
        if not self._has_active_provider_point_tool():
            self._clear_provider_point_preview()
            return
        if point is None:
            self._clear_provider_point_preview()
            return
        plan_point = self._project_plan_point(point)
        if plan_point is None:
            self._clear_provider_point_preview()
            return
        snap_info = self._get_provider_point_snap_info()
        snap_object = self._resolve_provider_point_snap_object(obj, snap_info)
        snap_target = (None, None)
        if snap_object is not None:
            snap_target = self._get_plan_target_for_object(snap_object)
        host_kind, host_obj, host_source = self._get_provider_point_payload_host_target(
            snap_target=snap_target,
            selected_target=self._get_selected_plan_target(),
            selected_targets=self._get_selected_plan_targets(),
            hovered_target=self._get_hovered_plan_target(),
        )
        placement_point = (
            self._project_provider_point_to_host(plan_point, host_obj)
            if host_kind == "wall"
            else None
        )
        if placement_point is None:
            placement_point = plan_point
        self._provider_point_preview_source_point = plan_point
        self._provider_point_preview_point = placement_point
        self._provider_point_preview_host_target = (host_kind, host_obj)
        self._provider_point_preview_host_source = host_source
        self._sync_provider_point_preview()

    def _get_provider_point_snap_info(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if snapper is None:
            return {}
        snap_info = getattr(snapper, "snapInfo", None)
        if isinstance(snap_info, dict):
            return dict(snap_info)
        return {}

    def _resolve_provider_point_snap_object(self, snap_object, snap_info):
        if snap_object is not None:
            return snap_object
        object_name = str(snap_info.get("Object", "") or "").strip()
        if not object_name:
            return None
        doc = self.doc
        document_name = str(snap_info.get("Document", "") or "").strip()
        if document_name:
            try:
                doc = FreeCAD.getDocument(document_name)
            except Exception:
                doc = self.doc
        if doc is None:
            return None
        try:
            return doc.getObject(object_name)
        except Exception:
            return None

    def _normalize_provider_point_host_target(self, target):
        if not target:
            return (None, None)
        try:
            target_kind, target_obj = target
        except Exception:
            return (None, None)
        if target_kind == "wall" and self._is_plan_selectable_wall(target_obj):
            return ("wall", target_obj)
        return (None, None)

    def _get_provider_point_context_host_state(self):
        selected_kind, selected_obj = self._normalize_provider_point_host_target(
            self._get_selected_plan_target()
        )
        if selected_obj is not None:
            return selected_kind, selected_obj, "selected"
        hovered_kind, hovered_obj = self._normalize_provider_point_host_target(
            self._get_hovered_plan_target()
        )
        if hovered_obj is not None:
            return hovered_kind, hovered_obj, "hovered"
        return None, None, ""

    def _get_provider_point_payload_host_target(
        self,
        *,
        snap_target,
        selected_target,
        selected_targets,
        hovered_target,
    ):
        selected_kind, selected_obj = self._normalize_provider_point_host_target(selected_target)
        if selected_obj is not None:
            return selected_kind, selected_obj, "selected"
        selected_walls = []
        for target in selected_targets or ():
            target_kind, target_obj = self._normalize_provider_point_host_target(target)
            if target_obj is not None and target_obj not in selected_walls:
                selected_walls.append(target_obj)
        if len(selected_walls) == 1:
            return "wall", selected_walls[0], "selected"
        snap_kind, snap_obj = self._normalize_provider_point_host_target(snap_target)
        if snap_obj is not None:
            return snap_kind, snap_obj, "snap"
        stored_kind, stored_obj = self._normalize_provider_point_host_target(
            self._provider_point_host_target
        )
        if stored_obj is not None:
            return stored_kind, stored_obj, self._provider_point_host_source or "stored"
        hovered_kind, hovered_obj = self._normalize_provider_point_host_target(hovered_target)
        if hovered_obj is not None:
            return hovered_kind, hovered_obj, "hovered"
        return None, None, ""

    def _project_provider_point_to_host(self, point, host_wall):
        if point is None or host_wall is None:
            return None
        proxy = getattr(host_wall, "Proxy", None)
        if proxy is None or not hasattr(proxy, "calc_endpoints"):
            return None
        try:
            endpoints = proxy.calc_endpoints(host_wall)
            start = FreeCAD.Vector(endpoints[0])
            end = FreeCAD.Vector(endpoints[1])
            source = FreeCAD.Vector(point)
        except Exception:
            return None
        axis = end.sub(start)
        axis.z = 0.0
        length_sq = axis.dot(axis)
        if length_sq <= 1e-9:
            return None
        offset = source.sub(start)
        offset.z = 0.0
        factor = max(0.0, min(1.0, offset.dot(axis) / length_sq))
        projected = start.add(axis.multiply(factor))
        projected.z = getattr(source, "z", 0.0)
        return projected

    def _build_provider_point_tool_payload(
        self,
        tool,
        *,
        raw_point,
        plan_point,
        snap_object,
        snap_info,
    ):
        snap_target = (None, None)
        if snap_object is not None:
            snap_target = self._get_plan_target_for_object(snap_object)
        snap_component = str(snap_info.get("Component", "") or "").strip()
        snap_subname = str(snap_info.get("SubName", "") or snap_component).strip()
        snap_document_name = str(snap_info.get("Document", "") or "").strip()
        if not snap_document_name and snap_object is not None:
            snap_document_name = str(
                getattr(getattr(snap_object, "Document", None), "Name", "") or ""
            )
        snap_object_name = str(snap_info.get("Object", "") or "").strip()
        if not snap_object_name and snap_object is not None:
            snap_object_name = str(getattr(snap_object, "Name", "") or "")
        selected_target = self._get_selected_plan_target()
        selected_targets = self._get_selected_plan_targets()
        hovered_target = self._get_hovered_plan_target()
        host_kind, host_obj, host_source = self._get_provider_point_payload_host_target(
            snap_target=snap_target,
            selected_target=selected_target,
            selected_targets=selected_targets,
            hovered_target=hovered_target,
        )
        placement_point = (
            self._project_provider_point_to_host(plan_point, host_obj)
            if host_kind == "wall"
            else None
        )
        if placement_point is None:
            placement_point = plan_point
        return {
            "tool": tool,
            "point": plan_point,
            "placement_point": placement_point,
            "raw_point": raw_point,
            "snap_info": snap_info,
            "snap_object": snap_object,
            "snap_target": snap_target,
            "snap_document_name": snap_document_name,
            "snap_object_name": snap_object_name,
            "snap_component": snap_component,
            "snap_subname": snap_subname,
            "selected_target": selected_target,
            "selected_targets": selected_targets,
            "hovered_target": hovered_target,
            "host_target": (host_kind, host_obj),
            "host_source": host_source,
        }

    def _get_space_preflight_report(self, targets=None):
        return plan_spaces.get_space_preflight_report(self, targets=targets)

    def _format_space_preflight_text(self, report):
        return plan_spaces.format_space_preflight_text(report)

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
        return plan_wall_relations.clear_plan_relation_status(self)

    def _collect_wall_relation_warnings(self, wall):
        return plan_wall_relations.collect_wall_relation_warnings(self, wall)

    def _update_wall_relation_status(self, wall):
        return plan_wall_relations.update_wall_relation_status(self, wall)

    def _set_selected_plan_target(
        self,
        kind=None,
        obj=None,
        pending_restore=False,
        preserve_hovered_symbol_overlay=False,
    ):
        return plan_selection.set_selected_plan_target(
            self,
            kind=kind,
            obj=obj,
            pending_restore=pending_restore,
            preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
        )

    def _schedule_selected_wall_reset(self, reason, obj):
        return plan_selection.schedule_selected_wall_reset(self, reason, obj)

    def _reset_selected_wall_after_change(self):
        return plan_selection.reset_selected_wall_after_change(self)

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        return plan_selection.suspend_selected_wall_state(
            self,
            wall=wall,
            clear_gui_selection=clear_gui_selection,
        )

    def _register_edit_callbacks(self):
        return plan_view.register_edit_callbacks(self)

    def _unregister_edit_callbacks(self):
        return plan_view.unregister_edit_callbacks(self)

    def _sync_primary_selected_plan_target_visuals(self, previous_kind=None, previous_obj=None):
        return plan_selection.sync_primary_selected_plan_target_visuals(
            self,
            previous_kind=previous_kind,
            previous_obj=previous_obj,
        )

    def _refresh_selected_plan_target(self):
        return plan_selection.refresh_selected_plan_target(self)

    def _refresh_primary_selected_plan_target(self):
        return plan_selection.refresh_primary_selected_plan_target(self)

    def _refresh_selected_wall(self):
        # Compatibility wrapper for older tests and callers.
        return self._refresh_primary_selected_plan_target()

    def _start_embedded_tool(self, tool_name, command, host_class=_PlanEditCommandHost):
        self.current_tool = tool_name
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_provider(None)
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
            self._wall_edit_opening_clearances_queued = False
            self._wall_edit_task_panel_refresh_queued = False
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
        self._wall_edit_opening_clearances_queued = False
        self._wall_edit_task_panel_refresh_queued = False
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
        self._sync_selected_provider_overlay()
        self._sync_selected_provider_handles()

    def _cancel_join_tool(self, refresh=True):
        return plan_wall_relations.cancel_join_tool(self, refresh=refresh)

    def _restore_gui_selection(self, obj):
        if not obj:
            return
        self._set_gui_selection_object(obj)

    def _apply_plan_wall_join(self, source_wall, target_wall):
        return plan_wall_relations.apply_plan_wall_join(self, source_wall, target_wall)

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
        return plan_wall_create.has_active_rect_wall_tool(self)

    def _clear_rect_wall_preview(self):
        return plan_wall_create.clear_rect_wall_preview(self)

    def _cancel_rect_wall_tool(self, refresh=True):
        return plan_wall_create.cancel_rect_wall_tool(self, refresh=refresh)

    def _get_rect_wall_corners(self, point):
        return plan_wall_create.get_rect_wall_corners(self, point)

    def _update_rect_wall_preview(self, point, info):
        return plan_wall_create.update_rect_wall_preview(self, point, info)

    def _create_rect_wall_run(self, corners):
        return plan_wall_create.create_rect_wall_run(self, corners)

    def _handle_rect_wall_point(self, point=None, obj=None):
        return plan_wall_create.handle_rect_wall_point(self, point=point, obj=obj)

    def _has_active_window_tool(self):
        return plan_window_create.has_active_window_tool(self)

    def _clear_window_preview(self):
        return plan_window_create.clear_window_preview(self)

    def _cancel_window_tool(self, refresh=True):
        return plan_window_create.cancel_window_tool(self, refresh=refresh)

    def _project_window_point_to_host(self, point, wall=None):
        return plan_window_create.project_window_point_to_host(self, point, wall=wall)

    def _update_window_tool_preview(self, point=None, info=None):
        return plan_window_create.update_window_tool_preview(self, point=point, info=info)

    def _handle_window_tool_point(self, point=None, obj=None):
        return plan_window_create.handle_window_tool_point(self, point=point, obj=obj)

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
        self._sync_selected_provider_overlay()
        self._sync_selected_provider_handles()
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
        self._sync_selected_provider_overlay()
        self._sync_selected_provider_handles()
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
        return plan_wall_edit.has_active_wall_edit(self)

    def _is_wall_edit_modal_active(self):
        return plan_wall_edit.is_wall_edit_modal_active(self)

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
        return plan_wall_edit.cancel_wall_edit(self, restore=restore, refresh=refresh)

    def _cancel_wall_subtool(self):
        return plan_wall_edit.cancel_wall_subtool(self)

    def _start_wall_edit(self, mode):
        return plan_wall_edit.start_wall_edit(self, mode)

    def _resume_wall_edit_point_pick(self):
        return plan_wall_edit.resume_wall_edit_point_pick(self)

    def _snapshot_wall_hosted_opening_clearances(self, wall, endpoints):
        return plan_wall_edit.snapshot_wall_hosted_opening_clearances(self, wall, endpoints)

    def _queue_wall_edit_opening_clearances(self):
        return plan_wall_edit.queue_wall_edit_opening_clearances(self)

    def _prime_wall_edit_opening_clearances(self):
        return plan_wall_edit.prime_wall_edit_opening_clearances(self)

    def _ensure_wall_edit_opening_clearances(self, wall, endpoints):
        return plan_wall_edit.ensure_wall_edit_opening_clearances(self, wall, endpoints)

    def _queue_wall_edit_task_panel_refresh(self):
        return plan_wall_edit.queue_wall_edit_task_panel_refresh(self)

    def _flush_wall_edit_task_panel_refresh(self):
        return plan_wall_edit.flush_wall_edit_task_panel_refresh(self)

    def _finish_wall_edit(self, point=None, obj=None):
        return plan_wall_edit.finish_wall_edit(self, point=point, obj=obj)

    def _commit_wall_edit_points(self, wall, endpoint, proxy, new_points):
        return plan_wall_edit.commit_wall_edit_points(self, wall, endpoint, proxy, new_points)

    def _start_wall_grip_edit(self, grip_index):
        return plan_wall_edit.start_wall_grip_edit(self, grip_index)

    def _activate_wall_grip(self, grip_index, wall=None):
        return plan_wall_edit.activate_wall_grip(self, grip_index, wall=wall)

    def _activate_wall_grip_now(self, grip_index, wall=None):
        return plan_wall_edit.activate_wall_grip_now(self, grip_index, wall=wall)

    def _get_wall_edit_reference_point(self):
        return plan_wall_edit.get_wall_edit_reference_point(self)

    def _compute_wall_edit_points(self, point):
        return plan_wall_edit.compute_wall_edit_points(self, point)

    def _compute_wall_edit_points_from_length(self, length):
        return plan_wall_edit.compute_wall_edit_points_from_length(self, length)

    def _get_preview_footprint(self, points, width=None, align=None):
        return plan_wall_edit.get_preview_footprint(self, points, width=width, align=align)

    def _make_preview_wall_adapter(self, wall, endpoints):
        return plan_wall_edit.make_preview_wall_adapter(self, wall, endpoints)

    def _solve_preview_wall_relation(self, relation, wall, preview_wall):
        return plan_wall_edit.solve_preview_wall_relation(self, relation, wall, preview_wall)

    def _collect_preview_wall_relation_data(self, wall, points):
        return plan_wall_edit.collect_preview_wall_relation_data(self, wall, points)

    @staticmethod
    def _clip_preview_polygon_to_plane(polygon, plane_placement, ref_point, tol=1e-7):
        return plan_wall_edit.clip_preview_polygon_to_plane(
            polygon,
            plane_placement,
            ref_point,
            tol=tol,
        )

    def _get_preview_footprint_polylines(self, points):
        return plan_wall_edit.get_preview_footprint_polylines(self, points)

    def _get_readout_base_gap(self):
        return plan_wall_edit.get_readout_base_gap(self)

    def _get_aligned_readout_offset_for_wall(self, wall):
        return plan_wall_edit.get_aligned_readout_offset_for_wall(self, wall)

    def _get_wall_edit_readout_offset(self, mode):
        return plan_wall_edit.get_wall_edit_readout_offset(self, mode)

    def _get_opening_move_readout_offset(self, opening):
        return plan_wall_edit.get_opening_move_readout_offset(self, opening)

    def _update_wall_edit_preview_geometry(self, points):
        return plan_wall_edit.update_wall_edit_preview_geometry(self, points)

    def _sync_wall_edit_preview(self, points, include_opening_preview=True):
        return plan_wall_edit.sync_wall_edit_preview(
            self,
            points,
            include_opening_preview=include_opening_preview,
        )

    def _is_wall_move_edit_active(self):
        return plan_wall_edit.is_wall_move_edit_active(self)

    def _is_wall_stretch_edit_active(self):
        return plan_wall_edit.is_wall_stretch_edit_active(self)

    def _is_wall_readout_edit_active(self):
        return plan_wall_edit.is_wall_readout_edit_active(self)

    def _clear_wall_edit_preview(self):
        return plan_wall_edit.clear_wall_edit_preview(self)

    def _get_wall_hosted_opening_preview_segments(self, wall, points):
        return plan_wall_edit.get_wall_hosted_opening_preview_segments(self, wall, points)

    def _sync_wall_hosted_opening_preview(self, points):
        return plan_wall_edit.sync_wall_hosted_opening_preview(self, points)

    def _clear_wall_hosted_opening_preview(self):
        return plan_wall_edit.clear_wall_hosted_opening_preview(self)

    def _get_wall_edit_readout_specs(self, points):
        return plan_wall_edit.get_wall_edit_readout_specs(self, points)

    def _get_default_wall_edit_readout_mode(self, specs):
        return plan_wall_edit.get_default_wall_edit_readout_mode(self, specs)

    def _bind_wall_edit_readout_callbacks(self, dim, mode):
        return plan_wall_edit.bind_wall_edit_readout_callbacks(self, dim, mode)

    def _update_wall_edit_readouts_in_place(self, points, active_mode=None):
        return plan_wall_edit.update_wall_edit_readouts_in_place(
            self,
            points,
            active_mode=active_mode,
        )

    def _sync_wall_edit_readout(self, points):
        return plan_wall_edit.sync_wall_edit_readout(self, points)

    def _clear_wall_edit_readout(self):
        return plan_wall_edit.clear_wall_edit_readout(self)

    def _get_wall_edit_readout_tracker(self, mode):
        return plan_wall_edit.get_wall_edit_readout_tracker(self, mode)

    def _cycle_wall_move_readout_mode(self):
        return plan_wall_edit.cycle_wall_move_readout_mode(self)

    def _start_wall_readout_edit(self, cycle=False):
        return plan_wall_edit.start_wall_readout_edit(self, cycle=cycle)

    def _start_wall_stretch_length_edit(self):
        return plan_wall_edit.start_wall_stretch_length_edit(self)

    def _start_wall_readout_edit_now(self, tracker, value):
        return plan_wall_edit.start_wall_readout_edit_now(self, tracker, value)

    def _on_wall_stretch_length_changed(self, value):
        return plan_wall_edit.on_wall_stretch_length_changed(self, value)

    def _on_wall_stretch_length_finished(self, value):
        return plan_wall_edit.on_wall_stretch_length_finished(self, value)

    def _on_wall_stretch_length_canceled(self, value):
        return plan_wall_edit.on_wall_stretch_length_canceled(self, value)

    def _compute_wall_edit_points_from_move_delta(self, mode, value):
        return plan_wall_edit.compute_wall_edit_points_from_move_delta(self, mode, value)

    def _on_wall_move_delta_changed(self, mode, value):
        return plan_wall_edit.on_wall_move_delta_changed(self, mode, value)

    def _on_wall_move_delta_finished(self, mode, value):
        return plan_wall_edit.on_wall_move_delta_finished(self, mode, value)

    def _on_wall_move_delta_canceled(self, mode, value):
        return plan_wall_edit.on_wall_move_delta_canceled(self, mode, value)

    def _schedule_wall_edit_readout_cancel(self):
        return plan_wall_edit.schedule_wall_edit_readout_cancel(self)

    def _finish_wall_edit_readout_canceled(self, preview_points):
        return plan_wall_edit.finish_wall_edit_readout_canceled(self, preview_points)

    def _restore_edit_wall_visibility(self):
        return plan_wall_edit.restore_edit_wall_visibility(self)

    def _update_wall_edit_preview(self, point):
        return plan_wall_edit.update_wall_edit_preview(self, point)

    def _update_wall_edit_point_pick(self, point=None, snap_info=None):
        return plan_wall_edit.update_wall_edit_point_pick(
            self,
            point=point,
            snap_info=snap_info,
        )

    def _cancel_wall_edit_point_pick(self):
        return plan_wall_edit.cancel_wall_edit_point_pick(self)

    def _get_edit_node(self, mouse_pos):
        symbol_handle_role = self._pick_selected_symbol_handle(mouse_pos)
        if symbol_handle_role is not None:
            node = (
                "symbol_handle",
                self._get_selected_plan_target_object("symbol"),
                symbol_handle_role,
            )
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="selected_symbol_handle",
                result=node,
            )
            return node
        opening_handle_index = self._pick_selected_opening_handle(mouse_pos)
        if opening_handle_index is not None:
            node = (
                "opening_handle",
                self._get_selected_plan_target_object("opening"),
                opening_handle_index,
            )
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="selected_opening_handle",
                result=node,
            )
            return node
        provider_handle_index = self._pick_selected_provider_handle(mouse_pos)
        if provider_handle_index is not None:
            node = (
                "provider_handle",
                self._get_selected_plan_target_object("provider"),
                provider_handle_index,
            )
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="selected_provider_handle",
                result=node,
            )
            return node
        target_kind, target_obj = self._pick_provider_overlay_target_from_objects_info(mouse_pos)
        if target_obj is not None:
            node = ("provider_overlay_target", target_kind, target_obj)
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="provider_overlay_objects_info",
                result=node,
            )
            return node
        target_kind, target_obj = self._pick_provider_overlay_target_from_overlays(mouse_pos)
        if target_obj is not None:
            node = ("provider_overlay_target", target_kind, target_obj)
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="provider_overlay_overlays",
                result=node,
            )
            return node
        if not self._render_manager:
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="no_render_manager",
                result=None,
            )
            return None
        try:
            from pivy import coin
        except Exception:
            self._plan_pick_debug_event(
                "get_edit_node",
                mouse_pos=mouse_pos,
                source="coin_import_failed",
                result=None,
            )
            return None

        ray_pick = coin.SoRayPickAction(self._render_manager.getViewportRegion())
        ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
        ray_pick.setRadius(8)
        ray_pick.setPickAll(True)
        ray_pick.apply(self._render_manager.getSceneGraph())
        picked_points = ray_pick.getPickedPointList()
        if picked_points:
            for picked_point in picked_points:
                path = picked_point.getPath()
                point = path.getNode(path.getLength() - 2)
                try:
                    sub_element = str(point.subElementName.getValue())
                except Exception:
                    continue
                if plan_picking.is_provider_overlay_point_subname(sub_element):
                    node = ("provider_overlay_point", point)
                    self._plan_pick_debug_event(
                        "get_edit_node",
                        mouse_pos=mouse_pos,
                        source="ray_pick_provider_overlay_point",
                        result=node,
                    )
                    return node
                if "EditNode" in sub_element:
                    node = ("edit_node", point)
                    self._plan_pick_debug_event(
                        "get_edit_node",
                        mouse_pos=mouse_pos,
                        source="ray_pick_edit_node",
                        result=node,
                    )
                    return node
        self._plan_pick_debug_event(
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="no_edit_node",
            result=None,
        )
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
        return plan_input.on_mouse_pressed(self, event_callback)

    def _on_mouse_moved(self, event_callback):
        return plan_input.on_mouse_moved(self, event_callback)

    def _on_mouse_wheel(self, event_callback):
        return plan_input.on_mouse_wheel(self, event_callback)

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
            if self.current_tool == "Provider Point":
                self._sync_provider_overlays()
                self._sync_provider_point_preview()
                return
            if self.current_tool != "Select":
                return
            if self.hovered_wall or self._is_selected_plan_target("wall"):
                self._sync_junction_node_overlays()
            if self.hovered_wall:
                self._sync_hovered_wall_overlay()
                self._sync_hovered_wall_opening_context_overlay()
            if self._is_selected_plan_target("wall"):
                self._sync_selected_wall_overlay()
                self._sync_selected_wall_opening_context_overlay()
                self._sync_wall_grips()
            if self.hovered_opening:
                self._sync_hovered_opening_overlay()
            if self._is_selected_plan_target("opening"):
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if self.hovered_symbol:
                self._sync_hovered_symbol_overlay()
            self._sync_provider_overlays()
            if self.hovered_provider:
                self._sync_hovered_provider_overlay()
            if self._is_selected_plan_target("provider") or self._get_provider_selected_objects():
                self._sync_selected_provider_overlay()
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
        if self._tearing_down or self._finishing or not self._document_is_alive():
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
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_provider_overlay()
            self._clear_selected_provider_handles()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
            return
        if self.current_tool == "Region":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_provider_overlay()
            self._clear_selected_provider_handles()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
            return
        if self.current_tool == "Set Space Text":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_provider_overlay()
            self._clear_selected_provider_handles()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
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
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_selected_provider_overlay()
            self._clear_selected_provider_handles()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
            if (
                refresh_all
                or _PLAN_VISUAL_SECONDARY_SELECTION in dirty
                or _PLAN_VISUAL_SPACE_REGION_PICK in dirty
            ):
                self._sync_secondary_selected_overlays()
                self._sync_space_region_pick_overlays()
            return
        if self.current_tool == "Provider Point":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_provider_overlay()
            self._clear_selected_provider_handles()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
            if refresh_all or _PLAN_VISUAL_PROVIDER_OVERLAYS in dirty:
                self._sync_provider_overlays()
            self._sync_provider_point_preview()
            return
        if self.current_tool == "Window":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_provider_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_provider_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_provider_overlays()
            self._clear_provider_point_preview()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_selected_wall_overlay()
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
            if refresh_all or _PLAN_VISUAL_HOVERED_PROVIDER in dirty:
                self._sync_hovered_provider_overlay()
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
                self._sync_selected_wall_overlay()
                self._sync_wall_grips()
            provider_overlays_dirty = refresh_all or _PLAN_VISUAL_PROVIDER_OVERLAYS in dirty
            if provider_overlays_dirty:
                self._sync_provider_overlays()
            if provider_overlays_dirty or refresh_all or _PLAN_VISUAL_SELECTED_PROVIDER in dirty:
                self._sync_selected_provider_overlay()
                self._sync_selected_provider_handles()
            self._clear_provider_point_preview()
            return

    def _on_key_pressed(self, event_callback):
        return plan_input.on_key_pressed(self, event_callback)

    # Selection observer interface

    def addSelection(self, doc, obj, sub, point):
        return plan_selection.selection_observer_add(self, doc, obj, sub, point)

    def removeSelection(self, doc, obj, sub):
        return plan_selection.selection_observer_remove(self, doc, obj, sub)

    def setSelection(self, doc):
        return plan_selection.selection_observer_set(self, doc)

    def clearSelection(self, doc):
        return plan_selection.selection_observer_clear(self, doc)

    def setPreselection(self, doc, obj, sub):
        return plan_selection.selection_observer_set_preselection(self, doc, obj, sub)

    def removePreselection(self, doc, obj, sub):
        return plan_selection.selection_observer_remove_preselection(self, doc, obj, sub)

    # Document observer interface

    def _is_opening_visual_dependency(self, opening, obj):
        return plan_document_visuals.is_opening_visual_dependency(opening, obj)

    def _refresh_selected_opening_visuals(self):
        return plan_document_visuals.refresh_selected_opening_visuals(self)

    def _is_symbol_visual_dependency(self, symbol, obj):
        return plan_document_visuals.is_symbol_visual_dependency(self, symbol, obj)

    def _refresh_plan_object_footprint_display(self, obj, *, request_redraw=True):
        return plan_document_visuals.refresh_plan_object_footprint_display(
            self,
            obj,
            request_redraw=request_redraw,
        )

    def _refresh_opening_footprint_display(self, opening):
        return plan_document_visuals.refresh_opening_footprint_display(self, opening)

    def _refresh_wall_footprint_display(self, wall):
        return plan_document_visuals.refresh_wall_footprint_display(self, wall)

    def _invalidate_wall_hosted_openings_cache(self):
        return plan_hosted_openings.invalidate_wall_hosted_openings_cache(self)

    def _queue_prime_wall_hosted_openings_cache(self):
        return plan_hosted_openings.queue_prime_wall_hosted_openings_cache(self)

    def _prime_wall_hosted_openings_cache(self):
        return plan_hosted_openings.prime_wall_hosted_openings_cache(self)

    def _queue_prime_hover_pick_caches(self):
        return plan_picking.queue_prime_hover_pick_caches(self)

    def _prime_hover_pick_caches(self):
        return plan_picking.prime_hover_pick_caches(self)

    def _build_wall_hosted_openings_cache(self):
        return plan_hosted_openings.build_wall_hosted_openings_cache(self)

    def _collect_opening_instances_from_host_cache(self, host_cache):
        return plan_hosted_openings.collect_opening_instances_from_host_cache(self, host_cache)

    def _get_plan_opening_instances(self):
        return plan_hosted_openings.get_plan_opening_instances(self)

    def _get_wall_hosted_openings(self, wall):
        return plan_hosted_openings.get_wall_hosted_openings(self, wall)

    def _refresh_wall_hosted_opening_footprints(self, wall):
        return plan_wall_edit.refresh_wall_hosted_opening_footprints(self, wall)

    def _compute_wall_hosted_opening_layout(self, wall, endpoints):
        return plan_wall_edit.compute_wall_hosted_opening_layout(self, wall, endpoints)

    def _resolve_wall_hosted_opening_layout(self, wall):
        return plan_wall_edit.resolve_wall_hosted_opening_layout(self, wall)

    def _refresh_opening_host_footprint_displays(self, opening):
        return plan_document_visuals.refresh_opening_host_footprint_displays(self, opening)

    def _queue_recompute_opening_hosts(self, *openings):
        return plan_document_visuals.queue_recompute_opening_hosts(self, *openings)

    def _flush_recompute_opening_hosts(self, hosts):
        return plan_document_visuals.flush_recompute_opening_hosts(self, hosts)

    def _queue_hard_refresh_selected_opening_visuals(self):
        return plan_document_visuals.queue_hard_refresh_selected_opening_visuals(self)

    def _flush_hard_refresh_selected_opening_visuals(self):
        return plan_document_visuals.flush_hard_refresh_selected_opening_visuals(self)

    def slotCreatedObject(self, obj):
        return plan_document_visuals.slot_created_object(self, obj)

    def slotChangedObject(self, obj, prop):
        return plan_document_visuals.slot_changed_object(self, obj, prop)

    def slotDeletedObject(self, obj):
        return plan_document_visuals.slot_deleted_object(self, obj)

    def _invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        return plan_document_visuals.invalidate_document_dependent_plan_visuals(
            self,
            recompute_opening_hosts=recompute_opening_hosts,
        )

    def slotUndoDocument(self, doc):
        return plan_document_visuals.slot_undo_document(self, doc)

    def slotRedoDocument(self, doc):
        return plan_document_visuals.slot_redo_document(self, doc)

    def slotRecomputedDocument(self, doc):
        return plan_document_visuals.slot_recomputed_document(self, doc)

    def slotDeletedDocument(self, doc):
        return plan_document_visuals.slot_deleted_document(self, doc)

    def attach_task_panel(self, panel):
        return plan_task_panel.attach_task_panel(self, panel)

    def attach_aux_task_panel(self, panel):
        return plan_task_panel.attach_aux_task_panel(self, panel)

    def detach_aux_task_panel(self, panel):
        return plan_task_panel.detach_aux_task_panel(self, panel)

    def detach_task_panel(self):
        return plan_task_panel.detach_task_panel(self)

    def on_panel_closed(self, panel):
        return plan_task_panel.on_panel_closed(self, panel)

    def _refresh_task_panel_status(self, selection_only=False):
        return plan_task_panel.refresh_task_panel_status(self, selection_only=selection_only)

    def _refresh_provider_overlay_mode_panels(self):
        return plan_task_panel.refresh_provider_overlay_mode_panels(self)

    def _is_modal_plan_interaction_active(self):
        return bool(
            self._is_wall_edit_modal_active()
            or self.current_tool
            in ("Move Opening", "Move Symbol", "Rotate Symbol", "Set Space Text", "Window")
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

    def _format_provider_target_role_label(self, obj):
        return plan_provider_targets.get_plan_provider_target_role_label(self, obj)

    def _format_provider_target_help(self, obj):
        return plan_provider_targets.format_plan_provider_target_help(self, obj)

    def _get_opening_display_kind_key(self, opening):
        if not opening:
            return "Opening"
        semantic_obj = self._get_plan_semantic_object(opening)
        ifc_type = getattr(semantic_obj, "IfcType", "") if semantic_obj else ""
        if ifc_type in {"Window", "Door"}:
            return ifc_type
        try:
            import Draft

            if Draft.getType(semantic_obj) == "Window":
                return "Window"
        except Exception:
            pass
        return "Opening"

    def _get_opening_display_kind(self, opening):
        return translate("BIM_PlanEdit", self._get_opening_display_kind_key(opening))

    def _format_opening_selection_help(self, opening):
        opening_kind = self._get_opening_display_kind_key(opening)
        if opening_kind == "Door":
            return translate(
                "BIM_PlanEdit",
                "Use in-view handles to move or flip the selected door.",
            )
        if opening_kind == "Window":
            help_text = translate(
                "BIM_PlanEdit",
                "Use the in-view handle to move the selected window along its host wall.",
            )
            can_edit_width = self._can_edit_window_width(opening)
            can_edit_height = self._can_edit_window_height(opening)
            can_apply_style = self._can_apply_window_style_preset(opening)
            if (can_edit_width or can_edit_height) and can_apply_style:
                help_text = "{} {}".format(
                    help_text,
                    translate(
                        "BIM_PlanEdit",
                        "Use the window controls below to change its width, height, or style.",
                    ),
                )
            elif can_edit_width and can_edit_height:
                help_text = "{} {}".format(
                    help_text,
                    translate(
                        "BIM_PlanEdit",
                        "Use the window controls below to change its width or height.",
                    ),
                )
            elif can_edit_width:
                help_text = "{} {}".format(
                    help_text,
                    translate(
                        "BIM_PlanEdit",
                        "Use the window controls below to change its width.",
                    ),
                )
            elif can_edit_height:
                help_text = "{} {}".format(
                    help_text,
                    translate(
                        "BIM_PlanEdit",
                        "Use the window controls below to change its height.",
                    ),
                )
            elif can_apply_style:
                help_text = "{} {}".format(
                    help_text,
                    translate(
                        "BIM_PlanEdit",
                        "Use the window controls below to change its style.",
                    ),
                )
            return help_text
        return translate(
            "BIM_PlanEdit",
            "Use in-view handles to move or flip the selected opening.",
        )

    def _format_plan_target_selection_state(self, kind, obj):
        if not kind or not obj:
            return ""
        if kind == "opening":
            return translate("BIM_PlanEdit", "{kind}: {label}").format(
                kind=self._get_opening_display_kind(obj),
                label=self._get_plan_target_display_label(obj),
            )
        templates = {
            "symbol": translate("BIM_PlanEdit", "Symbol: {label}"),
            "region": translate("BIM_PlanEdit", "Region: {label}"),
            "space": translate("BIM_PlanEdit", "Space: {label}"),
            "wall": translate("BIM_PlanEdit", "Wall: {label}"),
        }
        if kind == "provider":
            return translate("BIM_PlanEdit", "{kind}: {label}").format(
                kind=self._format_provider_target_role_label(obj),
                label=self._get_plan_target_display_label(obj),
            )
        template = templates.get(kind)
        if not template:
            return ""
        return template.format(label=self._get_plan_target_display_label(obj))

    def _get_provider_selected_objects(self):
        return tuple(self._normalize_gui_object_selection(self._provider_selected_objects))

    def _format_provider_selected_object_state(self):
        objects = self._get_provider_selected_objects()
        if not objects:
            return ""
        if len(objects) == 1:
            return translate("BIM_PlanEdit", "Object: {label}").format(
                label=self._get_plan_target_display_label(objects[0])
            )
        return translate("BIM_PlanEdit", "{count} integration objects selected").format(
            count=len(objects)
        )

    def _format_provider_selected_object_help(self):
        if not self._get_provider_selected_objects():
            return ""
        return translate(
            "BIM_PlanEdit",
            "Use the integration details and actions below for the selected object.",
        )

    def _get_status_chip_text(self):
        title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(tool=self.current_tool)
        selected_kind, selected_obj = self._get_selected_plan_target()
        selected_context = self._format_plan_target_selection_state(selected_kind, selected_obj)
        provider_context = self._format_provider_selected_object_state()
        provider_action = self._format_provider_selected_object_help()

        if self.current_tool == "Provider Point":
            title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(
                tool=self._get_provider_point_tool_label()
            )
            return title, self._get_provider_point_tool_prompt()

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

        if self.current_tool == "Move Provider":
            context = (
                selected_context
                if selected_kind == "provider" and selected_obj is not None
                else translate("BIM_PlanEdit", "Integration move")
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
        elif provider_context:
            context = provider_context
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
        if (selected_kind == "provider" or provider_context) and self.current_tool == "Select":
            if selected_kind == "provider":
                action = self._format_provider_target_help(selected_obj)
            else:
                action = provider_action
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
        return plan_task_panel.clear_input_hints()

    def _request_view_redraw(self):
        return plan_view.request_view_redraw(self)

    def _make_input_hint(self, message, *sequences):
        return plan_task_panel.make_input_hint(message, *sequences)

    def _get_input_hint_specs(self):
        return plan_task_panel.get_input_hint_specs(self)

    def _get_input_hints(self):
        return plan_task_panel.get_input_hints(self)

    def _update_input_hints(self):
        return plan_task_panel.update_input_hints(self)

    def _retarget_edit_tracker(self, tracker, obj, index):
        return wall_overlays.retarget_edit_tracker(tracker, obj, index)

    def _sync_wall_grips(self):
        return wall_overlays.sync_wall_grips(self)

    def _schedule_wall_grip_sync(self, delay_ms=_PLAN_WALL_GRIP_REFRESH_DELAY_MS):
        return wall_overlays.schedule_wall_grip_sync(self, delay_ms=delay_ms)

    def _run_scheduled_wall_grip_sync(self, generation=None):
        return wall_overlays.run_scheduled_wall_grip_sync(self, generation=generation)

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

    def _get_plan_target_at_position(self, mouse_pos, include_space_fallback=True):
        return plan_picking.get_plan_target_at_position(
            self,
            mouse_pos,
            include_space_fallback=include_space_fallback,
        )

    def _get_plan_space_instances(self):
        return plan_picking.get_plan_space_instances(self)

    def _get_plan_region_instances(self):
        return plan_picking.get_plan_region_instances(self)

    def _should_skip_hover_pick(self, mouse_pos, force=False):
        return plan_picking.should_skip_hover_pick(self, mouse_pos, force=force)

    def _update_hovered_plan_target(self, mouse_pos, force=False):
        return plan_picking.update_hovered_plan_target(self, mouse_pos, force=force)

    def _is_plan_additive_selection_active(self):
        return plan_selection.is_plan_additive_selection_active(self)

    def _get_plan_target_from_edit_node(self, node):
        return plan_picking.get_plan_target_from_edit_node(self, node)

    def _get_provider_overlay_target_from_edit_node(self, node):
        return plan_picking.get_provider_overlay_target_from_edit_node(self, node)

    def _activate_provider_overlay_target_node(self, node, event_callback=None):
        return plan_selection.activate_provider_overlay_target_node(
            self,
            node,
            event_callback=event_callback,
        )

    def _normalize_gui_object_selection(self, selection):
        return plan_selection.normalize_gui_object_selection(selection)

    def _toggle_raw_plan_object_selection(self, obj, event_callback=None):
        return plan_selection.toggle_raw_plan_object_selection(
            self,
            obj,
            event_callback=event_callback,
        )

    def _toggle_plan_target_selection_at_position(self, mouse_pos, event_callback=None):
        return plan_selection.toggle_plan_target_selection_at_position(
            self,
            mouse_pos,
            event_callback=event_callback,
        )

    def _clear_hovered_plan_targets(self, kinds=None):
        return plan_picking.clear_hovered_plan_targets(self, kinds=kinds)

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
        return plan_selection.set_hovered_wall(self, wall)

    def _set_hovered_opening(self, opening):
        return plan_selection.set_hovered_opening(self, opening)

    def _set_hovered_symbol(self, symbol):
        return plan_selection.set_hovered_symbol(self, symbol)

    def _set_hovered_provider(self, provider):
        return plan_selection.set_hovered_provider(self, provider)

    def _set_hovered_space(self, space):
        return plan_selection.set_hovered_space(self, space)

    def _set_hovered_region(self, region):
        return plan_selection.set_hovered_region(self, region)

    def _queue_restore_selected_plan_target(self, kind, obj):
        return plan_selection.queue_restore_selected_plan_target(self, kind, obj)

    def _select_plan_target_for_plan_edit(
        self,
        kind,
        obj,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_plan_target_for_plan_edit(
            self,
            kind,
            obj,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _select_opening_for_plan_edit(
        self,
        opening,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_opening_for_plan_edit(
            self,
            opening,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _select_symbol_for_plan_edit(
        self,
        symbol,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_symbol_for_plan_edit(
            self,
            symbol,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _select_region_for_plan_edit(
        self,
        region,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_region_for_plan_edit(
            self,
            region,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _select_space_for_plan_edit(
        self,
        space,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_space_for_plan_edit(
            self,
            space,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _select_wall_for_plan_edit(
        self,
        wall,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.select_wall_for_plan_edit(
            self,
            wall,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _activate_plan_target(
        self,
        kind,
        mouse_pos,
        event_callback=None,
        sync_gui_selection=False,
        clear_hovered_kinds=None,
        resolved_target=None,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.activate_plan_target(
            self,
            kind,
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=sync_gui_selection,
            clear_hovered_kinds=clear_hovered_kinds,
            resolved_target=resolved_target,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def _activate_semantic_plan_target(self, mouse_pos, event_callback=None):
        return plan_selection.activate_semantic_plan_target(
            self,
            mouse_pos,
            event_callback=event_callback,
        )

    def _activate_opening_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return plan_selection.activate_opening_target(
            self,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def _activate_symbol_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return plan_selection.activate_symbol_target(
            self,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def _activate_region_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return plan_selection.activate_region_target(
            self,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def _activate_space_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return plan_selection.activate_space_target(
            self,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def _activate_wall_target(
        self,
        mouse_pos,
        event_callback=None,
        resolved_target=None,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return plan_selection.activate_wall_target(
            self,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
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
        return plan_spaces.get_space_region_candidate_polylines(self, candidate)

    def _get_space_region_candidate_segments(self, candidate):
        return plan_spaces.get_space_region_candidate_segments(self, candidate)

    def _pick_space_region_candidate(self, mouse_pos, radius_px=10):
        return plan_spaces.pick_space_region_candidate(self, mouse_pos, radius_px=radius_px)

    def _set_hovered_space_region_candidate(self, candidate):
        return plan_spaces.set_hovered_space_region_candidate(
            self,
            candidate,
            _PLAN_VISUAL_SPACE_REGION_PICK,
        )

    def _create_space_region_base_object(self, candidate):
        return plan_spaces.create_space_region_base_object(self, candidate)

    def _begin_space_region_pick(self, boundaries, label=None, seed_space=None, report=None):
        return plan_spaces.begin_space_region_pick(
            self,
            boundaries,
            label=label,
            seed_space=seed_space,
            report=report,
        )

    def _cancel_space_region_pick(self, refresh=True):
        return plan_spaces.cancel_space_region_pick(self, refresh=refresh)

    def _create_space_from_region_candidate(self, candidate, boundaries=None, keep_boundaries=True):
        return plan_spaces.create_space_from_region_candidate(
            self,
            candidate,
            boundaries=boundaries,
            keep_boundaries=keep_boundaries,
        )

    def _activate_space_region_candidate(self, candidate, event_callback=None):
        return plan_spaces.activate_space_region_candidate(
            self,
            candidate,
            event_callback=event_callback,
        )

    def _create_space_from_current_selection(self):
        return plan_spaces.create_space_from_current_selection(self)

    def _space_has_valid_geometry(self, space):
        return plan_spaces.space_has_valid_geometry(self, space)

    def _report_space_creation_failure(self, space):
        return plan_spaces.report_space_creation_failure(space)

    def _set_selected_space_label(self, label):
        return plan_spaces.set_selected_space_label(self, label)

    def _set_selected_space_type(self, space_type):
        return plan_spaces.set_selected_space_type(self, space_type)

    def _get_window_style_preset_options(self):
        return plan_window_edit.get_window_style_preset_options()

    def _get_selected_window_style_preset(self):
        return plan_window_edit.get_selected_window_style_preset(self)

    def _get_selected_window_width_mm(self):
        return plan_window_edit.get_selected_window_width_mm(self)

    def _get_selected_window_width_text(self):
        return plan_window_edit.get_selected_window_width_text(self)

    def _get_selected_window_height_mm(self):
        return plan_window_edit.get_selected_window_height_mm(self)

    def _get_selected_window_height_text(self):
        return plan_window_edit.get_selected_window_height_text(self)

    def _can_apply_window_style_preset(self, window=None):
        if window is None:
            window = self._get_selected_plan_target_object("opening")
        return plan_window_edit.can_edit_window_style_preset(window)

    def _can_edit_window_width(self, window=None):
        if window is None:
            window = self._get_selected_plan_target_object("opening")
        return plan_window_edit.can_edit_window_width(window)

    def _can_edit_window_height(self, window=None):
        if window is None:
            window = self._get_selected_plan_target_object("opening")
        return plan_window_edit.can_edit_window_height(window)

    def _can_apply_selected_window_style_preset(self):
        return plan_window_edit.can_apply_selected_window_style_preset(self)

    def _can_apply_selected_window_width(self):
        return plan_window_edit.can_apply_selected_window_width(self)

    def _can_apply_selected_window_height(self):
        return plan_window_edit.can_apply_selected_window_height(self)

    def _can_apply_selected_window_size(self, width_value=None, height_value=None):
        return plan_window_edit.can_apply_selected_window_size(
            self,
            width_value=width_value,
            height_value=height_value,
        )

    def _apply_selected_window_style_preset(self, preset_name):
        return plan_window_edit.apply_selected_window_style_preset(self, preset_name)

    def _set_selected_window_width(self, value):
        return plan_window_edit.set_selected_window_width(self, value)

    def _set_selected_window_height(self, value):
        return plan_window_edit.set_selected_window_height(self, value)

    def _set_selected_window_size(self, width_value=None, height_value=None):
        return plan_window_edit.set_selected_window_size(
            self,
            width_value=width_value,
            height_value=height_value,
        )

    def _set_selected_region_label(self, label):
        return plan_spaces.set_selected_region_label(self, label)

    def _set_selected_region_scheme(self, scheme):
        return plan_spaces.set_selected_region_scheme(self, scheme)

    def _set_selected_region_type(self, region_type):
        return plan_spaces.set_selected_region_type(self, region_type)

    def _set_selected_region_parent_space(self, space):
        return plan_spaces.set_selected_region_parent_space(self, space)

    def _set_space_boundaries(self, space, boundaries):
        return plan_spaces.set_space_boundaries(self, space, boundaries)

    def _add_boundaries_to_selected_space(self):
        return plan_spaces.add_boundaries_to_selected_space(self)

    def _remove_selected_space_boundaries(self, row_indexes=None):
        return plan_spaces.remove_selected_space_boundaries(self, row_indexes=row_indexes)

    def _start_space_text_position_pick(self):
        return plan_spaces.start_space_text_position_pick(self)

    def _finish_space_text_position_pick(self, point=None, obj=None):
        return plan_spaces.finish_space_text_position_pick(self, point=point, obj=obj)

    def _cancel_space_text_position_pick(self):
        return plan_spaces.cancel_space_text_position_pick(self)

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

    def _sync_selected_wall_overlay(self):
        return wall_overlays.sync_selected_wall_overlay(self)

    def _clear_selected_wall_overlay(self):
        return wall_overlays.clear_selected_wall_overlay(self)

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

    def _sync_provider_overlays(self):
        return provider_overlays.sync_provider_overlays(self)

    def _clear_provider_overlays(self):
        return provider_overlays.clear_provider_overlays(self)

    def _sync_hovered_provider_overlay(self):
        return provider_overlays.sync_hovered_provider_overlay(self)

    def _clear_hovered_provider_overlay(self):
        return provider_overlays.clear_hovered_provider_overlay(self)

    def _sync_selected_provider_overlay(self):
        return provider_overlays.sync_selected_provider_overlay(self)

    def _clear_selected_provider_overlay(self):
        return provider_overlays.clear_selected_provider_overlay(self)

    def _get_selected_provider_handle_specs(self, provider_obj):
        return provider_overlays.get_selected_provider_handle_specs(self, provider_obj)

    def _sync_selected_provider_handles(self):
        return provider_overlays.sync_selected_provider_handles(self)

    def _clear_selected_provider_handles(self):
        return provider_overlays.clear_selected_provider_handles(self)

    def _pick_selected_provider_handle(self, mouse_pos, radius_px=10):
        return provider_overlays.pick_selected_provider_handle(
            self,
            mouse_pos,
            radius_px=radius_px,
        )

    def _sync_provider_point_preview(self):
        return provider_overlays.sync_provider_point_preview(self)

    def _clear_provider_point_preview(self):
        return provider_overlays.clear_provider_point_preview(self)

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

    def _get_plan_symbol_instances(self):
        return symbol_overlays.get_plan_symbol_instances(self)

    def _get_symbol_overlay_screen_polylines(self, symbol):
        return symbol_overlays.get_symbol_overlay_screen_polylines(self, symbol)

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

    def _get_selected_provider_edit_handles(self, provider_obj):
        return plan_provider_edit.get_selected_provider_edit_handles(self, provider_obj)

    def _can_move_provider_target_by_placement(self, provider_obj):
        return plan_provider_edit.can_move_provider_target_by_placement(self, provider_obj)

    def _activate_provider_handle(self, provider_obj, handle_index):
        return plan_provider_edit.activate_provider_handle(self, provider_obj, handle_index)

    def _activate_provider_handle_now(self, provider_obj, handle_index):
        return plan_provider_edit.activate_provider_handle_now(self, provider_obj, handle_index)

    def _start_provider_handle_point_pick(self, provider_obj, handle_index, handle):
        return plan_provider_edit.start_provider_handle_point_pick(
            self,
            provider_obj,
            handle_index,
            handle,
        )

    def _update_provider_handle_point_pick(self, point=None, snap_info=None):
        return plan_provider_edit.update_provider_handle_point_pick(
            self,
            point=point,
            snap_info=snap_info,
        )

    def _finish_provider_handle_point_pick(self, point=None, obj=None):
        return plan_provider_edit.finish_provider_handle_point_pick(self, point=point, obj=obj)

    def _cancel_provider_handle_point_pick(self):
        return plan_provider_edit.cancel_provider_handle_point_pick(self)

    def _restore_selected_provider(self, provider_obj):
        return plan_provider_edit.restore_selected_provider(self, provider_obj)

    def _queue_restore_selected_provider(self, provider_obj):
        return plan_provider_edit.queue_restore_selected_provider(self, provider_obj)

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
        return plan_selection.clear_plan_selection_state(self)

    def _execute_selected_opening_handle(self, opening, handle_index, handle):
        return plan_opening_edit.execute_selected_opening_handle(
            self, opening, handle_index, handle
        )

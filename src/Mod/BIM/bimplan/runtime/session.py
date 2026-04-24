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
from bimplan import selection as plan_selection
from bimplan.selection import picking as plan_picking
from bimplan.runtime import command_gate as plan_command_gate
from bimplan import document_visuals as plan_document_visuals
from bimplan.tools import hosted_openings as plan_hosted_openings
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.runtime import input as plan_input
from bimplan.runtime import lifecycle as plan_lifecycle
from bimplan import object_visibility as plan_object_visibility
from bimplan import performance as plan_performance
from bimplan.providers import point as plan_provider_point
from bimplan.providers import runtime as plan_provider_runtime
from bimplan import snap as plan_snap
from bimplan.runtime import session_state as plan_session_state
from bimplan.runtime.session_state import PlanInteractionAPI
from bimplan import storeys as plan_storeys
from bimplan import task_panel as plan_task_panel
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection.selection import PlanSelectionAPI
from bimplan.tools import symbol_edit as plan_symbol_edit
from bimplan.tools.symbol_edit import PlanSymbolsAPI
from bimplan.tools import opening_edit as plan_opening_edit
from bimplan.providers import edit as plan_provider_edit
from bimplan.providers.runtime import PlanProvidersAPI
from bimplan.selection import targets as plan_targets
from bimplan.tools import wall_create as plan_wall_create
from bimplan.tools import wall_relations as plan_wall_relations
from bimplan.tools.wall_relations import PlanWallRelationsAPI
from bimplan.tools.wall_edit import PlanWallEditAPI
from bimplan.tools import window_create as plan_window_create
from bimplan.tools.window_create import PlanWindowsAPI
from bimplan.tools.spaces import PlanSpacesAPI
from bimplan.providers import PlanEditContext
from bimplan.runtime.view import PlanViewportAPI
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays
from bimplan.providers import get_plan_edit_registry
from bimplan.status_text import PlanStatusTextAPI
from bimplan.ui.controls import PlanEditControlsWidget

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
_OPENING_VISUAL_PROPERTIES = plan_document_visuals.OPENING_VISUAL_PROPERTIES
_WALL_VISUAL_PROPERTIES = plan_document_visuals.WALL_VISUAL_PROPERTIES
_SYMBOL_VISUAL_PROPERTIES = plan_document_visuals.SYMBOL_VISUAL_PROPERTIES
_SPACE_VISUAL_PROPERTIES = plan_document_visuals.SPACE_VISUAL_PROPERTIES
_REGION_VISUAL_PROPERTIES = plan_document_visuals.REGION_VISUAL_PROPERTIES
_PLAN_VISUAL_HOVERED_WALL = plan_document_visuals.PLAN_VISUAL_HOVERED_WALL
_PLAN_VISUAL_HOVERED_OPENING = plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING
_PLAN_VISUAL_HOVERED_SYMBOL = plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL
_PLAN_VISUAL_HOVERED_PROVIDER = plan_document_visuals.PLAN_VISUAL_HOVERED_PROVIDER
_PLAN_VISUAL_HOVERED_SPACE = plan_document_visuals.PLAN_VISUAL_HOVERED_SPACE
_PLAN_VISUAL_HOVERED_REGION = plan_document_visuals.PLAN_VISUAL_HOVERED_REGION
_PLAN_VISUAL_SELECTED_PROVIDER = plan_document_visuals.PLAN_VISUAL_SELECTED_PROVIDER
_PLAN_VISUAL_SELECTED_OPENING = plan_document_visuals.PLAN_VISUAL_SELECTED_OPENING
_PLAN_VISUAL_SELECTED_SYMBOL = plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL
_PLAN_VISUAL_SELECTED_SPACE = plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE
_PLAN_VISUAL_SELECTED_REGION = plan_document_visuals.PLAN_VISUAL_SELECTED_REGION
_PLAN_VISUAL_SECONDARY_SELECTION = plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION
_PLAN_VISUAL_WALL_GRIPS = plan_document_visuals.PLAN_VISUAL_WALL_GRIPS
_PLAN_VISUAL_WALL_EDIT_PREVIEW = plan_document_visuals.PLAN_VISUAL_WALL_EDIT_PREVIEW
_PLAN_VISUAL_PROVIDER_OVERLAYS = plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
_PLAN_VISUAL_VIEW_SCALE = plan_document_visuals.PLAN_VISUAL_VIEW_SCALE
_PLAN_VISUAL_ALL = plan_document_visuals.PLAN_VISUAL_ALL
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


def _make_select_plan_target_method(kind):
    def _select_plan_target(
        self,
        obj,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return self._select_plan_target_for_plan_edit(
            kind,
            obj,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    return _select_plan_target


def _make_activate_plan_target_method(kind):
    def _activate_plan_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target_by_kind(
            kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    return _activate_plan_target


def _make_set_hovered_target_method(method_name):
    def _set_hovered_target(self, obj):
        return getattr(self.selection, method_name)(obj)

    return _set_hovered_target


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
        from bimplan.providers import register_plan_edit_providers

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

    def _ensure_task_panel_state(self):
        state = self.__dict__.get("task_panel_state")
        if state is None:
            state = plan_session_state.PlanTaskPanelState()
            self.__dict__["task_panel_state"] = state
        return state

    def _ensure_provider_overlay_read_state(self):
        state = self.__dict__.get("provider_overlay_read_state")
        if state is None:
            state = plan_session_state.PlanProviderOverlayReadState()
            self.__dict__["provider_overlay_read_state"] = state
        return state

    def _ensure_interaction_state(self):
        state = self.__dict__.get("interaction_state")
        if state is None:
            state = plan_session_state.PlanInteractionState()
            self.__dict__["interaction_state"] = state
        return state

    def _ensure_selection_state(self):
        state = self.__dict__.get("selection_state")
        if state is None:
            state = plan_session_state.PlanSelectionState()
            self.__dict__["selection_state"] = state
        return state

    def _ensure_wall_edit_state(self):
        state = self.__dict__.get("wall_edit_state")
        if state is None:
            state = plan_session_state.PlanWallEditState()
            self.__dict__["wall_edit_state"] = state
        return state

    def _ensure_hover_pick_state(self):
        state = self.__dict__.get("hover_pick_state")
        if state is None:
            state = plan_session_state.PlanHoverPickState()
            self.__dict__["hover_pick_state"] = state
        return state

    def _ensure_selection_sync_state(self):
        state = self.__dict__.get("selection_sync_state")
        if state is None:
            state = plan_session_state.PlanSelectionSyncState()
            self.__dict__["selection_sync_state"] = state
        return state

    def _ensure_input_event_state(self):
        state = self.__dict__.get("input_event_state")
        if state is None:
            state = plan_session_state.PlanInputEventState()
            self.__dict__["input_event_state"] = state
        return state

    def _ensure_overlay_refresh_state(self):
        state = self.__dict__.get("overlay_refresh_state")
        if state is None:
            state = plan_session_state.PlanOverlayRefreshState()
            self.__dict__["overlay_refresh_state"] = state
        return state

    @property
    def _plan_relation_status_message(self):
        return self._ensure_task_panel_state().relation_status_message

    @_plan_relation_status_message.setter
    def _plan_relation_status_message(self, value):
        self._ensure_task_panel_state().relation_status_message = value

    @property
    def _space_region_candidates(self):
        return self._ensure_task_panel_state().space_region_candidates

    @_space_region_candidates.setter
    def _space_region_candidates(self, value):
        self._ensure_task_panel_state().space_region_candidates = list(value or [])

    @property
    def _hovered_space_region_candidate(self):
        return self._ensure_task_panel_state().hovered_space_region_candidate

    @_hovered_space_region_candidate.setter
    def _hovered_space_region_candidate(self, value):
        self._ensure_task_panel_state().hovered_space_region_candidate = value

    @property
    def _plan_region_parent_space(self):
        return self._ensure_task_panel_state().plan_region_parent_space

    @_plan_region_parent_space.setter
    def _plan_region_parent_space(self, value):
        self._ensure_task_panel_state().plan_region_parent_space = value

    @property
    def _provider_overlay_mode(self):
        return self._ensure_provider_overlay_read_state().mode

    @_provider_overlay_mode.setter
    def _provider_overlay_mode(self, value):
        self._ensure_provider_overlay_read_state().mode = str(value or "architecture")

    @property
    def _provider_overlay_visibility(self):
        return self._ensure_provider_overlay_read_state().visibility

    @_provider_overlay_visibility.setter
    def _provider_overlay_visibility(self, value):
        self._ensure_provider_overlay_read_state().visibility = dict(value or {})

    @property
    def _provider_overlay_state(self):
        return self._ensure_provider_overlay_read_state().render_state

    @_provider_overlay_state.setter
    def _provider_overlay_state(self, value):
        self._ensure_provider_overlay_read_state().render_state = value

    @property
    def _selected_plan_target_kind(self):
        return self._ensure_selection_state().selected_plan_target_kind

    @_selected_plan_target_kind.setter
    def _selected_plan_target_kind(self, value):
        self._ensure_selection_state().selected_plan_target_kind = value

    @property
    def _selected_plan_target_obj(self):
        return self._ensure_selection_state().selected_plan_target_obj

    @_selected_plan_target_obj.setter
    def _selected_plan_target_obj(self, value):
        self._ensure_selection_state().selected_plan_target_obj = value

    @property
    def hovered_wall(self):
        return self._ensure_selection_state().hovered_wall

    @hovered_wall.setter
    def hovered_wall(self, value):
        self._ensure_selection_state().hovered_wall = value

    @property
    def hovered_opening(self):
        return self._ensure_selection_state().hovered_opening

    @hovered_opening.setter
    def hovered_opening(self, value):
        self._ensure_selection_state().hovered_opening = value

    @property
    def hovered_symbol(self):
        return self._ensure_selection_state().hovered_symbol

    @hovered_symbol.setter
    def hovered_symbol(self, value):
        self._ensure_selection_state().hovered_symbol = value

    @property
    def hovered_provider(self):
        return self._ensure_selection_state().hovered_provider

    @hovered_provider.setter
    def hovered_provider(self, value):
        self._ensure_selection_state().hovered_provider = value

    @property
    def hovered_space(self):
        return self._ensure_selection_state().hovered_space

    @hovered_space.setter
    def hovered_space(self, value):
        self._ensure_selection_state().hovered_space = value

    @property
    def hovered_region(self):
        return self._ensure_selection_state().hovered_region

    @hovered_region.setter
    def hovered_region(self, value):
        self._ensure_selection_state().hovered_region = value

    @property
    def _pending_selected_plan_target(self):
        return self._ensure_selection_state().pending_selected_plan_target

    @_pending_selected_plan_target.setter
    def _pending_selected_plan_target(self, value):
        self._ensure_selection_state().pending_selected_plan_target = value

    @property
    def _secondary_selected_plan_targets_state(self):
        return self._ensure_selection_state().secondary_selected_plan_targets_state

    @_secondary_selected_plan_targets_state.setter
    def _secondary_selected_plan_targets_state(self, value):
        self._ensure_selection_state().secondary_selected_plan_targets_state = list(value or [])

    @property
    def _wall_edit_modal_active(self):
        return self._ensure_wall_edit_state().wall_edit_modal_active

    @_wall_edit_modal_active.setter
    def _wall_edit_modal_active(self, value):
        self._ensure_wall_edit_state().wall_edit_modal_active = bool(value)

    @property
    def _edit_wall(self):
        return self._ensure_wall_edit_state().edit_wall

    @_edit_wall.setter
    def _edit_wall(self, value):
        self._ensure_wall_edit_state().edit_wall = value

    @property
    def _edit_endpoint(self):
        return self._ensure_wall_edit_state().edit_endpoint

    @_edit_endpoint.setter
    def _edit_endpoint(self, value):
        self._ensure_wall_edit_state().edit_endpoint = value

    @property
    def _edit_endpoints(self):
        return self._ensure_wall_edit_state().edit_endpoints

    @_edit_endpoints.setter
    def _edit_endpoints(self, value):
        self._ensure_wall_edit_state().edit_endpoints = value

    @property
    def _wall_edit_opening_clearances(self):
        return self._ensure_wall_edit_state().wall_edit_opening_clearances

    @_wall_edit_opening_clearances.setter
    def _wall_edit_opening_clearances(self, value):
        self._ensure_wall_edit_state().wall_edit_opening_clearances = dict(value or {})

    @property
    def _wall_edit_opening_clearances_queued(self):
        return self._ensure_wall_edit_state().wall_edit_opening_clearances_queued

    @_wall_edit_opening_clearances_queued.setter
    def _wall_edit_opening_clearances_queued(self, value):
        self._ensure_wall_edit_state().wall_edit_opening_clearances_queued = bool(value)

    @property
    def _wall_edit_task_panel_refresh_queued(self):
        return self._ensure_wall_edit_state().wall_edit_task_panel_refresh_queued

    @_wall_edit_task_panel_refresh_queued.setter
    def _wall_edit_task_panel_refresh_queued(self, value):
        self._ensure_wall_edit_state().wall_edit_task_panel_refresh_queued = bool(value)

    @property
    def _preview_points(self):
        return self._ensure_wall_edit_state().preview_points

    @_preview_points.setter
    def _preview_points(self, value):
        self._ensure_wall_edit_state().preview_points = value

    @property
    def _preview_line_tracker(self):
        return self._ensure_wall_edit_state().preview_line_tracker

    @_preview_line_tracker.setter
    def _preview_line_tracker(self, value):
        self._ensure_wall_edit_state().preview_line_tracker = value

    @property
    def _preview_footprint_trackers(self):
        return self._ensure_wall_edit_state().preview_footprint_trackers

    @_preview_footprint_trackers.setter
    def _preview_footprint_trackers(self, value):
        self._ensure_wall_edit_state().preview_footprint_trackers = list(value or [])

    @property
    def _preview_grip_trackers(self):
        return self._ensure_wall_edit_state().preview_grip_trackers

    @_preview_grip_trackers.setter
    def _preview_grip_trackers(self, value):
        self._ensure_wall_edit_state().preview_grip_trackers = list(value or [])

    @property
    def _wall_edit_readout_trackers(self):
        return self._ensure_wall_edit_state().wall_edit_readout_trackers

    @_wall_edit_readout_trackers.setter
    def _wall_edit_readout_trackers(self, value):
        self._ensure_wall_edit_state().wall_edit_readout_trackers = list(value or [])

    @property
    def _wall_edit_opening_preview_trackers(self):
        return self._ensure_wall_edit_state().wall_edit_opening_preview_trackers

    @_wall_edit_opening_preview_trackers.setter
    def _wall_edit_opening_preview_trackers(self, value):
        self._ensure_wall_edit_state().wall_edit_opening_preview_trackers = list(value or [])

    @property
    def _wall_edit_active_readout_tracker(self):
        return self._ensure_wall_edit_state().wall_edit_active_readout_tracker

    @_wall_edit_active_readout_tracker.setter
    def _wall_edit_active_readout_tracker(self, value):
        self._ensure_wall_edit_state().wall_edit_active_readout_tracker = value

    @property
    def _wall_edit_active_readout_mode(self):
        return self._ensure_wall_edit_state().wall_edit_active_readout_mode

    @_wall_edit_active_readout_mode.setter
    def _wall_edit_active_readout_mode(self, value):
        self._ensure_wall_edit_state().wall_edit_active_readout_mode = value

    @property
    def _wall_edit_length_edit_queued(self):
        return self._ensure_wall_edit_state().wall_edit_length_edit_queued

    @_wall_edit_length_edit_queued.setter
    def _wall_edit_length_edit_queued(self, value):
        self._ensure_wall_edit_state().wall_edit_length_edit_queued = bool(value)

    @property
    def _edit_wall_visibility(self):
        return self._ensure_wall_edit_state().edit_wall_visibility

    @_edit_wall_visibility.setter
    def _edit_wall_visibility(self, value):
        self._ensure_wall_edit_state().edit_wall_visibility = value

    @property
    def _embedded_host(self):
        return self._ensure_interaction_state().embedded_host

    @_embedded_host.setter
    def _embedded_host(self, value):
        self._ensure_interaction_state().embedded_host = value

    @property
    def _embedded_tool(self):
        return self._ensure_interaction_state().embedded_tool

    @_embedded_tool.setter
    def _embedded_tool(self, value):
        self._ensure_interaction_state().embedded_tool = value

    @property
    def _embedded_tool_name(self):
        return self._ensure_interaction_state().embedded_tool_name

    @_embedded_tool_name.setter
    def _embedded_tool_name(self, value):
        self._ensure_interaction_state().embedded_tool_name = str(value or "") or None

    @property
    def _provider_point_tool(self):
        return self._ensure_interaction_state().provider_point_tool

    @_provider_point_tool.setter
    def _provider_point_tool(self, value):
        self._ensure_interaction_state().provider_point_tool = value

    @property
    def _edit_opening(self):
        return self._ensure_interaction_state().edit_opening

    @_edit_opening.setter
    def _edit_opening(self, value):
        self._ensure_interaction_state().edit_opening = value

    @property
    def _edit_opening_handle_index(self):
        return self._ensure_interaction_state().edit_opening_handle_index

    @_edit_opening_handle_index.setter
    def _edit_opening_handle_index(self, value):
        self._ensure_interaction_state().edit_opening_handle_index = value

    @property
    def _edit_symbol(self):
        return self._ensure_interaction_state().edit_symbol

    @_edit_symbol.setter
    def _edit_symbol(self, value):
        self._ensure_interaction_state().edit_symbol = value

    @property
    def _edit_symbol_handle_role(self):
        return self._ensure_interaction_state().edit_symbol_handle_role

    @_edit_symbol_handle_role.setter
    def _edit_symbol_handle_role(self, value):
        self._ensure_interaction_state().edit_symbol_handle_role = value

    @property
    def _edit_provider(self):
        return self._ensure_interaction_state().edit_provider

    @_edit_provider.setter
    def _edit_provider(self, value):
        self._ensure_interaction_state().edit_provider = value

    @property
    def _edit_provider_handle_index(self):
        return self._ensure_interaction_state().edit_provider_handle_index

    @_edit_provider_handle_index.setter
    def _edit_provider_handle_index(self, value):
        self._ensure_interaction_state().edit_provider_handle_index = value

    @property
    def _edit_provider_handle(self):
        return self._ensure_interaction_state().edit_provider_handle

    @_edit_provider_handle.setter
    def _edit_provider_handle(self, value):
        self._ensure_interaction_state().edit_provider_handle = value

    @property
    def _edit_space(self):
        return self._ensure_interaction_state().edit_space

    @_edit_space.setter
    def _edit_space(self, value):
        self._ensure_interaction_state().edit_space = value

    @property
    def _hover_pick_dirty(self):
        return self._ensure_hover_pick_state().dirty

    @_hover_pick_dirty.setter
    def _hover_pick_dirty(self, value):
        self._ensure_hover_pick_state().dirty = bool(value)

    @property
    def _hover_pick_last_time(self):
        return self._ensure_hover_pick_state().last_time

    @_hover_pick_last_time.setter
    def _hover_pick_last_time(self, value):
        self._ensure_hover_pick_state().last_time = float(value or 0.0)

    @property
    def _hover_pick_last_mouse_pos(self):
        return self._ensure_hover_pick_state().last_mouse_pos

    @_hover_pick_last_mouse_pos.setter
    def _hover_pick_last_mouse_pos(self, value):
        self._ensure_hover_pick_state().last_mouse_pos = value

    @property
    def _plan_hover_pick_cache_queued(self):
        return self._ensure_hover_pick_state().cache_queued

    @_plan_hover_pick_cache_queued.setter
    def _plan_hover_pick_cache_queued(self, value):
        self._ensure_hover_pick_state().cache_queued = bool(value)

    @property
    def _selection_refresh_queued(self):
        return self._ensure_selection_sync_state().selection_refresh_queued

    @_selection_refresh_queued.setter
    def _selection_refresh_queued(self, value):
        self._ensure_selection_sync_state().selection_refresh_queued = bool(value)

    @property
    def _gui_selection_sync_queued(self):
        return self._ensure_selection_sync_state().gui_selection_sync_queued

    @_gui_selection_sync_queued.setter
    def _gui_selection_sync_queued(self, value):
        self._ensure_selection_sync_state().gui_selection_sync_queued = bool(value)

    @property
    def _gui_selection_sync_generation(self):
        return self._ensure_selection_sync_state().gui_selection_sync_generation

    @_gui_selection_sync_generation.setter
    def _gui_selection_sync_generation(self, value):
        self._ensure_selection_sync_state().gui_selection_sync_generation = int(value or 0)

    @property
    def _queued_gui_selection_object(self):
        return self._ensure_selection_sync_state().queued_gui_selection_object

    @_queued_gui_selection_object.setter
    def _queued_gui_selection_object(self, value):
        self._ensure_selection_sync_state().queued_gui_selection_object = value

    @property
    def _mouse_moved_cb(self):
        return self._ensure_input_event_state().mouse_moved_cb

    @_mouse_moved_cb.setter
    def _mouse_moved_cb(self, value):
        self._ensure_input_event_state().mouse_moved_cb = value

    @property
    def _mouse_wheel_cb(self):
        return self._ensure_input_event_state().mouse_wheel_cb

    @_mouse_wheel_cb.setter
    def _mouse_wheel_cb(self, value):
        self._ensure_input_event_state().mouse_wheel_cb = value

    @property
    def _mouse_wheel_event_type(self):
        return self._ensure_input_event_state().mouse_wheel_event_type

    @_mouse_wheel_event_type.setter
    def _mouse_wheel_event_type(self, value):
        self._ensure_input_event_state().mouse_wheel_event_type = value

    @property
    def _mouse_pressed_cb(self):
        return self._ensure_input_event_state().mouse_pressed_cb

    @_mouse_pressed_cb.setter
    def _mouse_pressed_cb(self, value):
        self._ensure_input_event_state().mouse_pressed_cb = value

    @property
    def _key_pressed_cb(self):
        return self._ensure_input_event_state().key_pressed_cb

    @_key_pressed_cb.setter
    def _key_pressed_cb(self, value):
        self._ensure_input_event_state().key_pressed_cb = value

    @property
    def _consume_left_button_release(self):
        return self._ensure_input_event_state().consume_left_button_release

    @_consume_left_button_release.setter
    def _consume_left_button_release(self, value):
        self._ensure_input_event_state().consume_left_button_release = bool(value)

    @property
    def _overlay_refresh_queued(self):
        return self._ensure_overlay_refresh_state().overlay_refresh_queued

    @_overlay_refresh_queued.setter
    def _overlay_refresh_queued(self, value):
        self._ensure_overlay_refresh_state().overlay_refresh_queued = bool(value)

    @property
    def _view_scale_overlay_refresh_queued(self):
        return self._ensure_overlay_refresh_state().view_scale_overlay_refresh_queued

    @_view_scale_overlay_refresh_queued.setter
    def _view_scale_overlay_refresh_queued(self, value):
        self._ensure_overlay_refresh_state().view_scale_overlay_refresh_queued = bool(value)

    @property
    def _dirty_plan_visuals(self):
        return self._ensure_overlay_refresh_state().dirty_plan_visuals

    @_dirty_plan_visuals.setter
    def _dirty_plan_visuals(self, value):
        self._ensure_overlay_refresh_state().dirty_plan_visuals = set(value or ())

    def __init__(self):
        self.selection = PlanSelectionAPI(self)
        self.spaces = PlanSpacesAPI(self)
        self.wall_relations = PlanWallRelationsAPI(self)
        self.interaction = PlanInteractionAPI(self)
        self.symbols = PlanSymbolsAPI(self)
        self.windows = PlanWindowsAPI(self)
        self.viewport = PlanViewportAPI(self)
        self.wall_edit = PlanWallEditAPI(self)
        self.providers = PlanProvidersAPI(self)
        self.status_text = PlanStatusTextAPI(self)
        plan_session_state.initialize_session_state(self)

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
        main_window = self.viewport.get_main_window()
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

    def _set_selected_target_for_kind(self, kind, obj):
        return self.selection.set_selected_target_for_kind(kind, obj)

    def _get_selected_plan_target_state(self):
        return self.selection.get_selected_plan_target_state()

    def _set_selected_plan_target_state(self, kind=None, obj=None):
        return self.selection.set_selected_plan_target_state(kind=kind, obj=obj)

    def _is_selected_plan_target(self, kind, obj=None):
        return self.selection.is_selected_plan_target(kind, obj=obj)

    def _clear_selected_plan_target_if_matches(self, kind, obj):
        return self.selection.clear_selected_plan_target_if_matches(kind, obj)

    def _get_plan_target_object_from_state(self, state_kind, state_obj, kind):
        return self.selection.get_plan_target_object_from_state(state_kind, state_obj, kind)

    def _selected_plan_target_changed(self, previous_kind, previous_obj, kind=None):
        return self.selection.selected_plan_target_changed(
            previous_kind,
            previous_obj,
            kind=kind,
        )

    @property
    def selected_wall(self):
        return self.selection.get_selected_target_for_kind("wall")

    @selected_wall.setter
    def selected_wall(self, wall):
        self._set_selected_target_for_kind("wall", wall)

    @property
    def selected_opening(self):
        return self.selection.get_selected_target_for_kind("opening")

    @selected_opening.setter
    def selected_opening(self, opening):
        self._set_selected_target_for_kind("opening", opening)

    @property
    def selected_symbol(self):
        return self.selection.get_selected_target_for_kind("symbol")

    @selected_symbol.setter
    def selected_symbol(self, symbol):
        self._set_selected_target_for_kind("symbol", symbol)

    @property
    def selected_region(self):
        return self.selection.get_selected_target_for_kind("region")

    @selected_region.setter
    def selected_region(self, region):
        self._set_selected_target_for_kind("region", region)

    @property
    def selected_space(self):
        return self.selection.get_selected_target_for_kind("space")

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
            selected_after = self.selection.get_selected_plan_target()
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
                self.viewport.capture_state()
            with self._plan_perf_trace_span("force_plan_preselection"):
                self.viewport.force_plan_preselection()

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
                self.viewport.apply_plan_view(fit=False)
            with self._plan_perf_trace_span("apply_plan_snap_profile"):
                self._apply_plan_snap_profile()
            self._apply_storey_visibility()
            with self._plan_perf_trace_span("attach_selection_observer"):
                self._attach_selection_observer()
            with self._plan_perf_trace_span("attach_document_observer"):
                self._attach_document_observer()
            with self._plan_perf_trace_span("register_edit_callbacks"):
                self.viewport.register_edit_callbacks()
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
        return plan_lifecycle.finish(self, close_dialog=close_dialog)

    def begin_teardown(self):
        return plan_lifecycle.begin_teardown(self)

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
        self.viewport.clear_viewport_status_chip()
        self.viewport.restore_preselection_state()
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

    def shutdown(self, close_dialog=True, teardown=False):
        global _active_session

        if self._finishing:
            return True
        self._finishing = True

        try:
            plan_lifecycle.shutdown(self, close_dialog=close_dialog, teardown=teardown)
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
        return plan_storeys.collect_storeys(self)

    def find_initial_storey(self):
        return plan_storeys.find_initial_storey(self)

    def get_storey_elevation(self, obj):
        return plan_storeys.get_storey_elevation(obj)

    def get_storey_label(self, obj):
        return plan_storeys.get_storey_label(obj)

    def set_active_storey(self, storey):
        return plan_storeys.set_active_storey(self, storey)

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
        return self.providers.get_plan_provider_display_name(provider_id)

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

    def get_plan_provider_action_context(self, payload=None):
        doc = self.doc if self._document_is_alive() else None
        return PlanEditContext.make_action_context(
            self,
            payload=payload,
            document_name=self._safe_plan_object_name(doc),
            current_tool=str(self.current_tool or ""),
        )

    def _on_embedded_command_started(self, tool_name, command=None):
        return plan_lifecycle.on_embedded_command_started(
            self,
            tool_name,
            command=command,
        )

    def _on_embedded_command_finished(self, tool_name, command=None):
        return plan_lifecycle.on_embedded_command_finished(
            self,
            tool_name,
            command=command,
        )

    def activate_select_tool(self):
        return plan_lifecycle.activate_select_tool(self)

    def activate_wall_tool(self):
        return plan_wall_create.activate_wall_tool(self)

    def activate_rect_wall_tool(self):
        return plan_wall_create.activate_rect_wall_tool(self)

    def can_place_plan_window(self):
        return self.windows.can_place_window()

    def activate_window_tool(self):
        return plan_lifecycle.activate_window_tool(self)

    def activate_plan_region_tool(self):
        return plan_lifecycle.activate_plan_region_tool(self)

    def activate_space_separator_tool(self):
        return plan_lifecycle.activate_space_separator_tool(self)

    def activate_space_tool(self):
        return plan_lifecycle.activate_space_tool(self)

    def activate_move_tool(self):
        return plan_lifecycle.activate_move_tool(self)

    def activate_join_tool(self):
        return plan_wall_relations.activate_join_tool(self)

    def get_plan_join_type(self):
        return plan_wall_relations.get_plan_join_type(self)

    def get_plan_join_types(self):
        return plan_wall_relations.get_plan_join_types(self)

    def _normalize_plan_join_type(self, join_type):
        return plan_wall_relations.normalize_plan_join_type(self, join_type)

    def get_plan_join_type_label(self, join_type=None):
        return self.wall_relations.get_plan_join_type_label(join_type=join_type)

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
        return self.wall_relations.get_plan_candidate_joint(target_wall=target_wall)

    def _get_plan_join_candidate_state(self):
        return self.wall_relations.get_plan_join_candidate_state()

    def _get_plan_join_mode_action_text(self, target_wall=None, joint=None):
        return self.wall_relations.get_plan_join_mode_action_text(
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
        return self.wall_edit.is_selected_wall_endpoint_editable()

    def is_selected_wall_baseless(self):
        wall = self.selection.get_selected_plan_target_object("wall")
        if not wall:
            return False
        return not getattr(wall, "Base", None) and self.is_selected_wall_endpoint_editable()

    def _get_wall_defaults(self):
        return plan_wall_create.get_wall_defaults(self)

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
        return plan_object_visibility.capture_object_view_state(self)

    def _register_object_view_state(self, obj):
        return plan_object_visibility.register_object_view_state(self, obj)

    def _add_object_to_active_storey(self, obj):
        return plan_object_visibility.add_object_to_active_storey(self, obj)

    def _register_plan_object(self, obj):
        return plan_object_visibility.register_plan_object(self, obj)

    def _register_plan_objects(self, objects):
        return plan_object_visibility.register_plan_objects(self, objects)

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
        return plan_object_visibility.restore_object_view_state(self)

    def _is_storey_object(self, obj):
        return plan_object_visibility.is_storey_object(obj)

    def _is_plan_container_object(self, obj):
        return plan_object_visibility.is_plan_container_object(obj)

    def _is_plan_background_object(self, obj):
        return plan_object_visibility.is_plan_background_object(self, obj)

    def _is_plan_equipment_object(self, obj):
        return plan_object_visibility.is_plan_equipment_object(self, obj)

    def _is_cabinetry_plan_context_object(self, obj):
        return plan_object_visibility.is_cabinetry_plan_context_object(obj)

    def _has_direct_plan_symbols(self, obj):
        return plan_object_visibility.has_direct_plan_symbols(obj)

    def _is_plan_symbol_instance(self, obj):
        return plan_object_visibility.is_plan_symbol_instance(self, obj)

    def _is_plan_context_only_object(self, obj):
        return plan_object_visibility.is_plan_context_only_object(self, obj)

    def _is_component_addition_object(self, obj):
        return plan_object_visibility.is_component_addition_object(obj)

    def _is_supported_plan_object(self, obj):
        return plan_object_visibility.is_supported_plan_object(self, obj)

    def _is_hosted_opening_object(self, obj):
        return plan_hosted_openings.is_hosted_opening_object(self, obj)

    def _get_supported_plan_visibility(self, obj, state):
        return plan_object_visibility.get_supported_plan_visibility(self, obj, state)

    def _apply_context_object_selectability(self, obj, view_object):
        return plan_object_visibility.apply_context_object_selectability(
            self,
            obj,
            view_object,
        )

    def _apply_hidden_object_state(self, view_object):
        return plan_object_visibility.apply_hidden_object_state(view_object)

    def _get_object_storeys(self, obj):
        return plan_object_visibility.get_object_storeys(self, obj)

    def _apply_storey_visibility(self):
        return plan_object_visibility.apply_storey_visibility(self)

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
        target_kind, target_obj = self.selection.get_selected_plan_target()
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
        return self.spaces.is_plan_space_object(obj)

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
        return self.spaces.get_space_reference_point(space)

    def _get_space_boundary_reference_point(self, selection_ex, fallback_space=None):
        return self.spaces.get_space_boundary_reference_point(
            selection_ex,
            fallback_space=fallback_space,
        )

    def _get_space_boundary_entries(self, space):
        return self.spaces.get_space_boundary_entries(space)

    def _space_boundary_key(self, boundary):
        return self.spaces.space_boundary_key(boundary)

    def _get_selected_space_boundary_links(self, fallback_space=None):
        return self.spaces.get_selected_space_boundary_links(
            fallback_space=fallback_space,
        )

    def _get_space_region_seed_targets(self, targets=None):
        return self.spaces.get_space_region_seed_targets(targets=targets)

    def _get_selected_space_region_seed(self, targets=None):
        return self.spaces.get_selected_space_region_seed(targets=targets)

    def _copy_shape_without_element_map(self, shape):
        return self.spaces.copy_shape_without_element_map(shape)

    def _get_space_creation_request(self, targets=None):
        return self.spaces.get_space_creation_request(targets=targets)

    def _get_existing_space_region_filter_spaces(self, exclude=None):
        return self.spaces.get_existing_space_region_filter_spaces(exclude=exclude)

    def _get_xy_bound_box_iou(self, first_shape, second_shape):
        return self.spaces.get_xy_bound_box_iou(first_shape, second_shape)

    def _is_space_region_candidate_claimed(self, candidate, spaces, overlap_iou_tolerance=0.9):
        return self.spaces.is_space_region_candidate_claimed(
            candidate,
            spaces,
            overlap_iou_tolerance=overlap_iou_tolerance,
        )

    def _filter_claimed_space_region_candidates(self, candidates, exclude_space=None):
        return self.spaces.filter_claimed_space_region_candidates(
            candidates,
            exclude_space=exclude_space,
        )

    def _get_space_region_candidate_report(
        self,
        boundaries,
        label=None,
        seed_space=None,
    ):
        return self.spaces.get_space_region_candidate_report(
            boundaries,
            label=label,
            seed_space=seed_space,
        )

    def _report_space_region_candidate_failure(self, report):
        return self.spaces.report_space_region_candidate_failure(report)

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
        return self.selection.set_pending_selected_plan_target(kind=kind, obj=obj)

    def _consume_pending_selected_plan_target(self):
        return self.selection.consume_pending_selected_plan_target()

    def _get_first_plan_target_from_selection(self, selection):
        return self.selection.get_first_plan_target_from_selection(selection)

    def _is_valid_plan_target(self, kind, obj):
        return self.selection.is_valid_plan_target(kind, obj)

    def _get_plan_target_state_key(self, kind, obj):
        return self.selection.get_plan_target_state_key(kind, obj)

    def _normalize_plan_target_list(self, targets):
        return self.selection.normalize_plan_target_list(targets)

    def _normalize_plan_targets_from_selection(self, selection):
        return self.selection.normalize_plan_targets_from_selection(selection)

    def _set_secondary_selected_plan_targets(self, targets, primary_kind=None, primary_obj=None):
        return self.selection.set_secondary_selected_plan_targets(
            targets,
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def _sync_secondary_selected_plan_targets_from_selection(
        self, selection, primary_kind=None, primary_obj=None
    ):
        return self.selection.sync_secondary_selected_plan_targets_from_selection(
            selection,
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def _sync_secondary_selected_plan_targets_from_gui_selection(
        self, primary_kind=None, primary_obj=None
    ):
        return self.selection.sync_secondary_selected_plan_targets_from_gui_selection(
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

    def _format_plan_target_count_label(self, kind, count):
        return self.status_text.format_plan_target_count_label(kind, count)

    def _format_space_region_candidate_area(self, candidate):
        return self.spaces.format_space_region_candidate_area(candidate)

    def _summarize_plan_targets(self, targets):
        return self.status_text.summarize_plan_targets(targets)

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
        return plan_provider_runtime.normalize_plan_provider_target(provider_id, target)

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

    def get_plan_provider_snapshot(self):
        if self._tearing_down or self._finishing or not self._document_is_alive():
            self._plan_perf_count("plan_provider_inactive_session")
            return plan_provider_runtime.PlanProviderSnapshot()
        if self._plan_provider_integrations_disabled():
            self._plan_perf_count("plan_provider_integrations_disabled")
            return plan_provider_runtime.PlanProviderSnapshot()
        return plan_provider_runtime.collect_plan_provider_snapshot(self)

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
        return plan_provider_runtime.get_plan_provider_targets(self)

    def _get_plan_provider_target_for_object(self, obj):
        return plan_provider_runtime.get_plan_provider_target_for_object(self, obj)

    def _is_plan_provider_target_object(self, obj):
        return plan_provider_runtime.is_plan_provider_target_object(self, obj)

    def get_plan_provider_overlay_visibility_key(self, provider_id, overlay_key):
        return plan_provider_runtime.get_plan_provider_overlay_visibility_key(
            provider_id,
            overlay_key,
        )

    def _normalize_plan_provider_overlay_mode(self, mode):
        return plan_provider_runtime.normalize_plan_provider_overlay_mode(mode)

    def get_plan_provider_overlay_mode(self):
        return self.providers.get_plan_provider_overlay_mode()

    def set_plan_provider_overlay_mode(self, mode):
        return plan_provider_runtime.set_plan_provider_overlay_mode(self, mode)

    def get_plan_provider_overlay_category(self, overlay):
        return self.providers.get_plan_provider_overlay_category(overlay)

    def is_plan_provider_overlay_enabled(self, overlay):
        return self.providers.is_plan_provider_overlay_enabled(overlay)

    def is_plan_provider_overlay_visible_for_mode(self, overlay, mode=None):
        return plan_provider_runtime.is_plan_provider_overlay_visible_for_mode(
            self,
            overlay,
            mode=mode,
        )

    def is_plan_provider_overlay_visible(self, overlay):
        return plan_provider_runtime.is_plan_provider_overlay_visible(self, overlay)

    def set_plan_provider_overlay_visible(self, provider_id, overlay_key, visible):
        return plan_provider_runtime.set_plan_provider_overlay_visible(
            self,
            provider_id,
            overlay_key,
            visible,
        )

    def queue_plan_provider_overlay_refresh(self):
        return plan_provider_runtime.queue_plan_provider_overlay_refresh(self)

    def queue_plan_provider_overlay_sync(self):
        return plan_provider_runtime.queue_plan_provider_overlay_sync(self)

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
        return plan_provider_point.has_active_provider_point_tool(self)

    def _get_provider_point_tool_label(self):
        return self.providers.get_provider_point_tool_label()

    def _get_provider_point_tool_prompt(self):
        return self.providers.get_provider_point_tool_prompt()

    def _arm_provider_point_tool(self):
        return plan_provider_point.arm_provider_point_tool(self)

    def _cancel_provider_point_tool(self, refresh=True):
        return plan_provider_point.cancel_provider_point_tool(self, refresh=refresh)

    def start_plan_provider_point_tool(self, tool):
        return plan_provider_point.start_plan_provider_point_tool(self, tool)

    def _handle_provider_point_tool_point(self, point=None, obj=None):
        return plan_provider_point.handle_provider_point_tool_point(self, point=point, obj=obj)

    def _update_provider_point_tool_preview(self, point=None, obj=None):
        return plan_provider_point.update_provider_point_tool_preview(
            self,
            point=point,
            obj=obj,
        )

    def _get_provider_point_snap_info(self):
        return plan_provider_point.get_provider_point_snap_info()

    def _resolve_provider_point_snap_object(self, snap_object, snap_info):
        return plan_provider_point.resolve_provider_point_snap_object(
            self,
            snap_object,
            snap_info,
        )

    def _normalize_provider_point_host_target(self, target):
        return plan_provider_point.normalize_provider_point_host_target(self, target)

    def _get_provider_point_context_host_state(self):
        return plan_provider_point.get_provider_point_context_host_state(self)

    def _get_provider_point_payload_host_target(
        self,
        *,
        snap_target,
        selected_target,
        selected_targets,
        hovered_target,
    ):
        return plan_provider_point.get_provider_point_payload_host_target(
            self,
            snap_target=snap_target,
            selected_target=selected_target,
            selected_targets=selected_targets,
            hovered_target=hovered_target,
        )

    def _project_provider_point_to_host(self, point, host_wall):
        return plan_provider_point.project_provider_point_to_host(point, host_wall)

    def _build_provider_point_tool_payload(
        self,
        tool,
        *,
        raw_point,
        plan_point,
        snap_object,
        snap_info,
    ):
        return plan_provider_point.build_provider_point_tool_payload(
            self,
            tool,
            raw_point=raw_point,
            plan_point=plan_point,
            snap_object=snap_object,
            snap_info=snap_info,
        )

    def _format_space_preflight_text(self, report):
        return self.spaces.format_space_preflight_text(report)

    def _get_plan_selection_summary_text(self):
        return self.status_text.get_plan_selection_summary_text()

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
        return self.selection.set_selected_plan_target(
            kind=kind,
            obj=obj,
            pending_restore=pending_restore,
            preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
        )

    def _schedule_selected_wall_reset(self, reason, obj):
        return self.selection.schedule_selected_wall_reset(reason, obj)

    def _reset_selected_wall_after_change(self):
        return self.selection.reset_selected_wall_after_change()

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        return self.selection.suspend_selected_wall_state(
            wall=wall,
            clear_gui_selection=clear_gui_selection,
        )

    def _sync_primary_selected_plan_target_visuals(self, previous_kind=None, previous_obj=None):
        return self.selection.sync_primary_selected_plan_target_visuals(
            previous_kind=previous_kind,
            previous_obj=previous_obj,
        )

    def _refresh_selected_plan_target(self):
        return self.selection.refresh_selected_plan_target()

    def _refresh_primary_selected_plan_target(self):
        return self.selection.refresh_primary_selected_plan_target()

    def _refresh_selected_wall(self):
        # Compatibility wrapper for older tests and callers.
        return self._refresh_primary_selected_plan_target()

    def _start_embedded_tool(self, tool_name, command, host_class=None):
        return plan_lifecycle.start_embedded_tool(
            self,
            tool_name,
            command,
            host_class=host_class,
        )

    def _cancel_pending_edit(self):
        return plan_lifecycle.cancel_pending_edit(self)

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
        return self.spaces.has_active_space_separator_tool()

    def _has_active_plan_region_tool(self):
        return self.spaces.has_active_plan_region_tool()

    def _clear_plan_region_preview(self):
        return self.spaces.clear_plan_region_preview()

    def _cancel_plan_region_tool(self, refresh=True):
        return self.spaces.cancel_plan_region_tool(refresh=refresh)

    def _get_plan_region_close_tolerance(self):
        return self.spaces.get_plan_region_close_tolerance()

    def _get_plan_region_preview_segments(self, point=None):
        return self.spaces.get_plan_region_preview_segments(point=point)

    def _update_plan_region_preview(self, point, info):
        return self.spaces.update_plan_region_preview(point, info)

    def _create_plan_region(self, points):
        return self.spaces.create_plan_region(points)

    def _finalize_plan_region(self):
        return self.spaces.finalize_plan_region()

    def _handle_plan_region_point(self, point=None, obj=None):
        return self.spaces.handle_plan_region_point(point=point, obj=obj)

    def _clear_space_separator_preview(self):
        return self.spaces.clear_space_separator_preview()

    def _cancel_space_separator_tool(self, refresh=True):
        return self.spaces.cancel_space_separator_tool(refresh=refresh)

    def _update_space_separator_preview(self, point, info):
        return self.spaces.update_space_separator_preview(point, info)

    def _create_space_separator(self, start, end):
        return self.spaces.create_space_separator(start, end)

    def _handle_space_separator_point(self, point=None, obj=None):
        return self.spaces.handle_space_separator_point(point=point, obj=obj)

    def _has_active_embedded_tool(self):
        return self._embedded_tool is not None

    def _cancel_embedded_tool(self, tool_name=None):
        return plan_lifecycle.cancel_embedded_tool(self, tool_name=tool_name)

    def _cancel_wall_edit(self, restore=True, refresh=True):
        return self.wall_edit.cancel_wall_edit(restore=restore, refresh=refresh)

    def _cancel_wall_subtool(self):
        return self.wall_edit.cancel_wall_subtool()

    def _start_wall_edit(self, mode):
        return self.wall_edit.start_wall_edit(mode)

    def _resume_wall_edit_point_pick(self):
        return self.wall_edit.resume_wall_edit_point_pick()

    def _snapshot_wall_hosted_opening_clearances(self, wall, endpoints):
        return self.wall_edit.snapshot_wall_hosted_opening_clearances(wall, endpoints)

    def _queue_wall_edit_opening_clearances(self):
        return self.wall_edit.queue_wall_edit_opening_clearances()

    def _prime_wall_edit_opening_clearances(self):
        return self.wall_edit.prime_wall_edit_opening_clearances()

    def _ensure_wall_edit_opening_clearances(self, wall, endpoints):
        return self.wall_edit.ensure_wall_edit_opening_clearances(wall, endpoints)

    def _queue_wall_edit_task_panel_refresh(self):
        return self.wall_edit.queue_wall_edit_task_panel_refresh()

    def _flush_wall_edit_task_panel_refresh(self):
        return self.wall_edit.flush_wall_edit_task_panel_refresh()

    def _finish_wall_edit(self, point=None, obj=None):
        return self.wall_edit.finish_wall_edit(point=point, obj=obj)

    def _commit_wall_edit_points(self, wall, endpoint, proxy, new_points):
        return self.wall_edit.commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _start_wall_grip_edit(self, grip_index):
        return self.wall_edit.start_wall_grip_edit(grip_index)

    def _activate_wall_grip(self, grip_index, wall=None):
        return self.wall_edit.activate_wall_grip(grip_index, wall=wall)

    def _activate_wall_grip_now(self, grip_index, wall=None):
        return self.wall_edit.activate_wall_grip_now(grip_index, wall=wall)

    def _get_wall_edit_reference_point(self):
        return self.wall_edit.get_wall_edit_reference_point()

    def _compute_wall_edit_points(self, point):
        return self.wall_edit.compute_wall_edit_points(point)

    def _compute_wall_edit_points_from_length(self, length):
        return self.wall_edit.compute_wall_edit_points_from_length(length)

    def _get_preview_footprint(self, points, width=None, align=None):
        return self.wall_edit.get_preview_footprint(points, width=width, align=align)

    def _make_preview_wall_adapter(self, wall, endpoints):
        return self.wall_edit.make_preview_wall_adapter(wall, endpoints)

    def _solve_preview_wall_relation(self, relation, wall, preview_wall):
        return self.wall_edit.solve_preview_wall_relation(relation, wall, preview_wall)

    def _collect_preview_wall_relation_data(self, wall, points):
        return self.wall_edit.collect_preview_wall_relation_data(wall, points)

    @staticmethod
    def _clip_preview_polygon_to_plane(polygon, plane_placement, ref_point, tol=1e-7):
        return PlanWallEditAPI.clip_preview_polygon_to_plane(
            polygon,
            plane_placement,
            ref_point,
            tol=tol,
        )

    def _get_preview_footprint_polylines(self, points):
        return self.wall_edit.get_preview_footprint_polylines(points)

    def _get_readout_base_gap(self):
        return self.wall_edit.get_readout_base_gap()

    def _get_aligned_readout_offset_for_wall(self, wall):
        return self.wall_edit.get_aligned_readout_offset_for_wall(wall)

    def _get_wall_edit_readout_offset(self, mode):
        return self.wall_edit.get_wall_edit_readout_offset(mode)

    def _get_opening_move_readout_offset(self, opening):
        return self.wall_edit.get_opening_move_readout_offset(opening)

    def _update_wall_edit_preview_geometry(self, points):
        return self.wall_edit.update_wall_edit_preview_geometry(points)

    def _sync_wall_edit_preview(self, points, include_opening_preview=True):
        return self.wall_edit.sync_wall_edit_preview(
            points,
            include_opening_preview=include_opening_preview,
        )

    def _is_wall_move_edit_active(self):
        return self.wall_edit.is_wall_move_edit_active()

    def _is_wall_stretch_edit_active(self):
        return self.wall_edit.is_wall_stretch_edit_active()

    def _is_wall_readout_edit_active(self):
        return self.wall_edit.is_wall_readout_edit_active()

    def _clear_wall_edit_preview(self):
        return self.wall_edit.clear_wall_edit_preview()

    def _get_wall_hosted_opening_preview_segments(self, wall, points):
        return self.wall_edit.get_wall_hosted_opening_preview_segments(wall, points)

    def _sync_wall_hosted_opening_preview(self, points):
        return self.wall_edit.sync_wall_hosted_opening_preview(points)

    def _clear_wall_hosted_opening_preview(self):
        return self.wall_edit.clear_wall_hosted_opening_preview()

    def _get_wall_edit_readout_specs(self, points):
        return self.wall_edit.get_wall_edit_readout_specs(points)

    def _get_default_wall_edit_readout_mode(self, specs):
        return self.wall_edit.get_default_wall_edit_readout_mode(specs)

    def _bind_wall_edit_readout_callbacks(self, dim, mode):
        return self.wall_edit.bind_wall_edit_readout_callbacks(dim, mode)

    def _update_wall_edit_readouts_in_place(self, points, active_mode=None):
        return self.wall_edit.update_wall_edit_readouts_in_place(
            points,
            active_mode=active_mode,
        )

    def _sync_wall_edit_readout(self, points):
        return self.wall_edit.sync_wall_edit_readout(points)

    def _clear_wall_edit_readout(self):
        return self.wall_edit.clear_wall_edit_readout()

    def _get_wall_edit_readout_tracker(self, mode):
        return self.wall_edit.get_wall_edit_readout_tracker(mode)

    def _cycle_wall_move_readout_mode(self):
        return self.wall_edit.cycle_wall_move_readout_mode()

    def _start_wall_readout_edit(self, cycle=False):
        return self.wall_edit.start_wall_readout_edit(cycle=cycle)

    def _start_wall_stretch_length_edit(self):
        return self.wall_edit.start_wall_stretch_length_edit()

    def _start_wall_readout_edit_now(self, tracker, value):
        return self.wall_edit.start_wall_readout_edit_now(tracker, value)

    def _on_wall_stretch_length_changed(self, value):
        return self.wall_edit.on_wall_stretch_length_changed(value)

    def _on_wall_stretch_length_finished(self, value):
        return self.wall_edit.on_wall_stretch_length_finished(value)

    def _on_wall_stretch_length_canceled(self, value):
        return self.wall_edit.on_wall_stretch_length_canceled(value)

    def _compute_wall_edit_points_from_move_delta(self, mode, value):
        return self.wall_edit.compute_wall_edit_points_from_move_delta(mode, value)

    def _on_wall_move_delta_changed(self, mode, value):
        return self.wall_edit.on_wall_move_delta_changed(mode, value)

    def _on_wall_move_delta_finished(self, mode, value):
        return self.wall_edit.on_wall_move_delta_finished(mode, value)

    def _on_wall_move_delta_canceled(self, mode, value):
        return self.wall_edit.on_wall_move_delta_canceled(mode, value)

    def _schedule_wall_edit_readout_cancel(self):
        return self.wall_edit.schedule_wall_edit_readout_cancel()

    def _finish_wall_edit_readout_canceled(self, preview_points):
        return self.wall_edit.finish_wall_edit_readout_canceled(preview_points)

    def _restore_edit_wall_visibility(self):
        return self.wall_edit.restore_edit_wall_visibility()

    def _update_wall_edit_preview(self, point):
        return self.wall_edit.update_wall_edit_preview(point)

    def _update_wall_edit_point_pick(self, point=None, snap_info=None):
        return self.wall_edit.update_wall_edit_point_pick(
            point=point,
            snap_info=snap_info,
        )

    def _cancel_wall_edit_point_pick(self):
        return self.wall_edit.cancel_wall_edit_point_pick()

    def _get_edit_node(self, mouse_pos):
        return plan_picking.get_edit_node(self, mouse_pos)

    def _pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        return plan_picking.pick_selected_opening_handle(self, mouse_pos, radius_px=radius_px)

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
        return overlay_manager.refresh_plan_overlay_view_scale(self)

    def _refresh_plan_overlay_visuals(self, dirty=None):
        return overlay_manager.refresh_plan_overlay_visuals(self, dirty=dirty)

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
        return plan_hover_picking.queue_prime_hover_pick_caches(self)

    def _prime_hover_pick_caches(self):
        return plan_hover_picking.prime_hover_pick_caches(self)

    def _build_wall_hosted_openings_cache(self):
        return plan_hosted_openings.build_wall_hosted_openings_cache(self)

    def _collect_opening_instances_from_host_cache(self, host_cache):
        return plan_hosted_openings.collect_opening_instances_from_host_cache(self, host_cache)

    def _get_plan_opening_instances(self):
        return plan_hosted_openings.get_plan_opening_instances(self)

    def _get_wall_hosted_openings(self, wall):
        return plan_hosted_openings.get_wall_hosted_openings(self, wall)

    def _refresh_wall_hosted_opening_footprints(self, wall):
        return self.wall_edit.refresh_wall_hosted_opening_footprints(wall)

    def _compute_wall_hosted_opening_layout(self, wall, endpoints):
        return self.wall_edit.compute_wall_hosted_opening_layout(wall, endpoints)

    def _resolve_wall_hosted_opening_layout(self, wall):
        return self.wall_edit.resolve_wall_hosted_opening_layout(wall)

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
        return self.interaction.is_modal_plan_interaction_active()

    def _get_plan_target_display_label(self, obj):
        return self.status_text.get_plan_target_display_label(obj)

    def _format_provider_target_role_label(self, obj):
        return self.status_text.format_provider_target_role_label(obj)

    def _format_provider_target_help(self, obj):
        return self.status_text.format_provider_target_help(obj)

    def _get_opening_display_kind_key(self, opening):
        return self.status_text.get_opening_display_kind_key(opening)

    def _get_opening_display_kind(self, opening):
        return self.status_text.get_opening_display_kind(opening)

    def _format_opening_selection_help(self, opening):
        return self.status_text.format_opening_selection_help(opening)

    def _format_plan_target_selection_state(self, kind, obj):
        return self.status_text.format_plan_target_selection_state(kind, obj)

    def _get_provider_selected_objects(self):
        return self.status_text.get_provider_selected_objects()

    def _format_provider_selected_object_state(self):
        return self.status_text.format_provider_selected_object_state()

    def _format_provider_selected_object_help(self):
        return self.status_text.format_provider_selected_object_help()

    def _clear_input_hints(self):
        return self.status_text.clear_input_hints()

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
        return plan_hover_picking.should_skip_hover_pick(self, mouse_pos, force=force)

    def _update_hovered_plan_target(self, mouse_pos, force=False):
        return plan_hover_picking.update_hovered_plan_target(self, mouse_pos, force=force)

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
        return plan_selection.normalize_gui_object_selection(self, selection)

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
        return plan_hover_picking.clear_hovered_plan_targets(self, kinds=kinds)

    def _get_hovered_plan_target(self):
        return plan_hover_picking.get_hovered_plan_target(self)

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

    _set_hovered_wall = _make_set_hovered_target_method("set_hovered_wall")

    _set_hovered_opening = _make_set_hovered_target_method("set_hovered_opening")

    _set_hovered_symbol = _make_set_hovered_target_method("set_hovered_symbol")

    _set_hovered_provider = _make_set_hovered_target_method("set_hovered_provider")

    _set_hovered_space = _make_set_hovered_target_method("set_hovered_space")

    _set_hovered_region = _make_set_hovered_target_method("set_hovered_region")

    def _queue_restore_selected_plan_target(self, kind, obj):
        return self.selection.queue_restore_selected_plan_target(kind, obj)

    def _select_plan_target_for_plan_edit(
        self,
        kind,
        obj,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return self.selection.select_plan_target_for_plan_edit(
            kind,
            obj,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    _select_opening_for_plan_edit = _make_select_plan_target_method(
        plan_target_kinds.PLAN_TARGET_OPENING
    )

    _select_symbol_for_plan_edit = _make_select_plan_target_method(
        plan_target_kinds.PLAN_TARGET_SYMBOL
    )

    _select_region_for_plan_edit = _make_select_plan_target_method(
        plan_target_kinds.PLAN_TARGET_REGION
    )

    _select_space_for_plan_edit = _make_select_plan_target_method(
        plan_target_kinds.PLAN_TARGET_SPACE
    )

    _select_wall_for_plan_edit = _make_select_plan_target_method(plan_target_kinds.PLAN_TARGET_WALL)

    def _activate_plan_target_by_kind(
        self,
        kind,
        mouse_pos,
        *,
        event_callback=None,
        resolved_target=None,
        defer_gui_selection=None,
        defer_wall_grips=None,
    ):
        return self.selection.activate_plan_target_for_kind(
            kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
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
        return self.selection.activate_plan_target(
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
        return self.selection.activate_semantic_plan_target(
            mouse_pos,
            event_callback=event_callback,
        )

    _activate_opening_target = _make_activate_plan_target_method(
        plan_target_kinds.PLAN_TARGET_OPENING
    )

    _activate_symbol_target = _make_activate_plan_target_method(
        plan_target_kinds.PLAN_TARGET_SYMBOL
    )

    _activate_region_target = _make_activate_plan_target_method(
        plan_target_kinds.PLAN_TARGET_REGION
    )

    _activate_space_target = _make_activate_plan_target_method(plan_target_kinds.PLAN_TARGET_SPACE)

    def _activate_wall_target(
        self,
        mouse_pos,
        event_callback=None,
        resolved_target=None,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return self._activate_plan_target_by_kind(
            plan_target_kinds.PLAN_TARGET_WALL,
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
        return self.viewport.project_plan_point(point)

    def _get_space_region_candidate_polylines(self, candidate):
        return self.spaces.get_space_region_candidate_polylines(candidate)

    def _get_space_region_candidate_segments(self, candidate):
        return self.spaces.get_space_region_candidate_segments(candidate)

    def _pick_space_region_candidate(self, mouse_pos, radius_px=10):
        return self.spaces.pick_space_region_candidate(mouse_pos, radius_px=radius_px)

    def _set_hovered_space_region_candidate(self, candidate):
        return self.spaces.set_hovered_space_region_candidate(candidate)

    def _create_space_region_base_object(self, candidate):
        return self.spaces.create_space_region_base_object(candidate)

    def _begin_space_region_pick(self, boundaries, label=None, seed_space=None, report=None):
        return self.spaces.begin_space_region_pick(
            boundaries,
            label=label,
            seed_space=seed_space,
            report=report,
        )

    def _cancel_space_region_pick(self, refresh=True):
        return self.spaces.cancel_space_region_pick(refresh=refresh)

    def _create_space_from_region_candidate(self, candidate, boundaries=None, keep_boundaries=True):
        return self.spaces.create_space_from_region_candidate(
            candidate,
            boundaries=boundaries,
            keep_boundaries=keep_boundaries,
        )

    def _activate_space_region_candidate(self, candidate, event_callback=None):
        return self.spaces.activate_space_region_candidate(
            candidate,
            event_callback=event_callback,
        )

    def _create_space_from_current_selection(self):
        return self.spaces.create_space_from_current_selection()

    def _space_has_valid_geometry(self, space):
        return self.spaces.space_has_valid_geometry(space)

    def _report_space_creation_failure(self, space):
        return self.spaces.report_space_creation_failure(space)

    def _set_selected_space_label(self, label):
        return self.spaces.set_selected_space_label(label)

    def _set_selected_space_type(self, space_type):
        return self.spaces.set_selected_space_type(space_type)

    def _get_window_style_preset_options(self):
        return self.windows.get_window_style_preset_options()

    def _get_selected_window_style_preset(self):
        return self.windows.get_selected_window_style_preset()

    def _get_selected_window_width_mm(self):
        return plan_window_create.get_selected_window_width_mm(self)

    def _get_selected_window_width_text(self):
        return self.windows.get_selected_window_width_text()

    def _get_selected_window_height_mm(self):
        return plan_window_create.get_selected_window_height_mm(self)

    def _get_selected_window_height_text(self):
        return self.windows.get_selected_window_height_text()

    def _can_apply_window_style_preset(self, window=None):
        return self.windows.can_apply_window_style_preset(window)

    def _can_edit_window_width(self, window=None):
        return self.windows.can_edit_window_width(window)

    def _can_edit_window_height(self, window=None):
        return self.windows.can_edit_window_height(window)

    def _can_apply_selected_window_style_preset(self):
        return plan_window_create.can_apply_selected_window_style_preset(self)

    def _can_apply_selected_window_width(self):
        return plan_window_create.can_apply_selected_window_width(self)

    def _can_apply_selected_window_height(self):
        return plan_window_create.can_apply_selected_window_height(self)

    def _can_apply_selected_window_size(self, width_value=None, height_value=None):
        return plan_window_create.can_apply_selected_window_size(
            self,
            width_value=width_value,
            height_value=height_value,
        )

    def _apply_selected_window_style_preset(self, preset_name):
        return plan_window_create.apply_selected_window_style_preset(self, preset_name)

    def _set_selected_window_width(self, value):
        return plan_window_create.set_selected_window_width(self, value)

    def _set_selected_window_height(self, value):
        return plan_window_create.set_selected_window_height(self, value)

    def _set_selected_window_size(self, width_value=None, height_value=None):
        return plan_window_create.set_selected_window_size(
            self,
            width_value=width_value,
            height_value=height_value,
        )

    def _set_selected_region_label(self, label):
        return self.spaces.set_selected_region_label(label)

    def _set_selected_region_scheme(self, scheme):
        return self.spaces.set_selected_region_scheme(scheme)

    def _set_selected_region_type(self, region_type):
        return self.spaces.set_selected_region_type(region_type)

    def _set_selected_region_parent_space(self, space):
        return self.spaces.set_selected_region_parent_space(space)

    def _set_space_boundaries(self, space, boundaries):
        return self.spaces.set_space_boundaries(space, boundaries)

    def _add_boundaries_to_selected_space(self):
        return self.spaces.add_boundaries_to_selected_space()

    def _remove_selected_space_boundaries(self, row_indexes=None):
        return self.spaces.remove_selected_space_boundaries(row_indexes=row_indexes)

    def _start_space_text_position_pick(self):
        return self.spaces.start_space_text_position_pick()

    def _finish_space_text_position_pick(self, point=None, obj=None):
        return self.spaces.finish_space_text_position_pick(point=point, obj=obj)

    def _cancel_space_text_position_pick(self):
        return self.spaces.cancel_space_text_position_pick()

    def _refresh_selected_space_visuals(self):
        self._invalidate_selected_space_overlay_cache()
        self._sync_selected_space_overlay()
        self.viewport.request_view_redraw()

    def _refresh_selected_region_visuals(self):
        self._sync_selected_region_overlay()
        self.viewport.request_view_redraw()

    def _restore_selected_semantic_target(self, kind, obj, *, clear_edit_space=False):
        sync_method = {
            plan_target_kinds.PLAN_TARGET_REGION: self._sync_selected_region_overlay,
            plan_target_kinds.PLAN_TARGET_SPACE: self._sync_selected_space_overlay,
        }.get(kind)
        if sync_method is None:
            return
        self.current_tool = "Select"
        if clear_edit_space:
            self._edit_space = None
        if obj:
            self._set_selected_plan_target(kind, obj, pending_restore=True)
            self._set_gui_selection_object(obj)
        else:
            self._set_selected_plan_target()
        sync_method()
        self._refresh_task_panel_status()

    def _queue_restore_selected_semantic_target(self, kind, obj, *, clear_edit_space=False):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_semantic_target(
                kind,
                obj,
                clear_edit_space=clear_edit_space,
            )
            return
        QtCore.QTimer.singleShot(
            0,
            lambda: self._restore_selected_semantic_target(
                kind,
                obj,
                clear_edit_space=clear_edit_space,
            ),
        )

    def _restore_selected_region(self, region):
        self._restore_selected_semantic_target(plan_target_kinds.PLAN_TARGET_REGION, region)

    def _queue_restore_selected_region(self, region):
        self._queue_restore_selected_semantic_target(plan_target_kinds.PLAN_TARGET_REGION, region)

    def _restore_selected_space(self, space):
        self._restore_selected_semantic_target(
            plan_target_kinds.PLAN_TARGET_SPACE,
            space,
            clear_edit_space=True,
        )

    def _queue_restore_selected_space(self, space):
        self._queue_restore_selected_semantic_target(
            plan_target_kinds.PLAN_TARGET_SPACE,
            space,
            clear_edit_space=True,
        )

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
        return self.symbols.symbol_rotation_snap_enabled()

    def _get_symbol_rotation_snap_increment_degrees(self):
        return symbol_overlays.get_symbol_rotation_snap_increment_degrees(self)

    def _get_symbol_rotation_snap_step_radians(self):
        return symbol_overlays.get_symbol_rotation_snap_step_radians(self)

    def _format_symbol_rotation_snap_label(self):
        return self.symbols.format_symbol_rotation_snap_label()

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
        return self.selection.clear_plan_selection_state()

    def _execute_selected_opening_handle(self, opening, handle_index, handle):
        return plan_opening_edit.execute_selected_opening_handle(
            self, opening, handle_index, handle
        )

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
from bimplan import selection as plan_selection
from bimplan.selection import picking as plan_picking
from bimplan.runtime import command_gate as plan_command_gate
from bimplan import document_visuals as plan_document_visuals
from bimplan.document_visuals import PlanDocumentVisualsAPI
from bimplan.tools import hosted_openings as plan_hosted_openings
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.runtime import input as plan_input
from bimplan.runtime import lifecycle as plan_lifecycle
from bimplan.object_visibility import PlanVisibilityAPI
from bimplan import performance as plan_performance
from bimplan.performance import PlanPerformanceAPI
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
from bimplan.tools.opening_edit import PlanOpeningsAPI
from bimplan.providers.runtime import PlanProvidersAPI
from bimplan.tools.wall_create import PlanWallCreateAPI
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
from bimplan.overlays.runtime import PlanOverlaysAPI
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

    # State-backed compatibility properties are bound after class definition.

    def __init__(self):
        self.selection = PlanSelectionAPI(self)
        self.spaces = PlanSpacesAPI(self)
        self.openings = PlanOpeningsAPI(self)
        self.wall_relations = PlanWallRelationsAPI(self)
        self.wall_create = PlanWallCreateAPI(self)
        self.interaction = PlanInteractionAPI(self)
        self.lifecycle = plan_lifecycle.PlanLifecycleAPI(self)
        self.symbols = PlanSymbolsAPI(self)
        self.windows = PlanWindowsAPI(self)
        self.viewport = PlanViewportAPI(self)
        self.overlays = PlanOverlaysAPI(self)
        self.wall_edit = PlanWallEditAPI(self)
        self.visibility = PlanVisibilityAPI(self)
        self.providers = PlanProvidersAPI(self)
        self.performance = PlanPerformanceAPI(self)
        self.document_visuals = PlanDocumentVisualsAPI(self)
        self.status_text = PlanStatusTextAPI(self)
        self.task_panels = plan_task_panel.PlanTaskPanelsAPI(self)
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
        normalized_secondary = self.selection.normalize_plan_target_list(
            getattr(self, "_secondary_selected_plan_targets_state", [])
        )
        if normalized_secondary != getattr(self, "_secondary_selected_plan_targets_state", []):
            self._secondary_selected_plan_targets_state = normalized_secondary
            changed = True
        return changed

    def enter(self):
        with self.performance.plan_perf_trace_event("enter_plan_edit"):
            self.performance.plan_perf_count(
                "document_objects", len(getattr(self.doc, "Objects", []) or [])
            )
            if not self.doc or not self.gui_doc:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
                )
                return False

            with self.performance.plan_perf_trace_span("enter_acquire_view"):
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

            with self.performance.plan_perf_trace_span("capture_plan_edit_state"):
                self.viewport.capture_state()
            with self.performance.plan_perf_trace_span("force_plan_preselection"):
                self.viewport.force_plan_preselection()

            with self.performance.plan_perf_trace_span("collect_storeys"):
                self.storeys = self.collect_storeys()
                self.performance.plan_perf_count("storeys_found", len(self.storeys))
            with self.performance.plan_perf_trace_span("find_initial_storey"):
                self.active_storey = self.find_initial_storey()
                self.performance.plan_perf_set_fields(
                    active_storey=self.performance.plan_perf_describe_object(self.active_storey)
                )
            with self.performance.plan_perf_trace_span("capture_object_view_state"):
                self.visibility.capture_object_view_state()
            with self.performance.plan_perf_trace_span("apply_plan_view"):
                self.viewport.apply_plan_view(fit=False)
            with self.performance.plan_perf_trace_span("apply_plan_snap_profile"):
                self._apply_plan_snap_profile()
            self.visibility.apply_storey_visibility()
            with self.performance.plan_perf_trace_span("attach_selection_observer"):
                self.selection.attach_selection_observer()
            with self.performance.plan_perf_trace_span("attach_document_observer"):
                self._attach_document_observer()
            with self.performance.plan_perf_trace_span("register_edit_callbacks"):
                self.viewport.register_edit_callbacks()
            with self.performance.plan_perf_trace_span(
                "refresh_primary_selected_plan_target_on_enter"
            ):
                self._refresh_primary_selected_plan_target()

            with self.performance.plan_perf_trace_span("build_task_panel"):
                panel = PlanEditControlsWidget(self)
            with self.performance.plan_perf_trace_span("attach_task_panel"):
                self.task_panels.attach_task_panel(panel)
            with self.performance.plan_perf_trace_span("task_panel_initial_refresh"):
                panel.refresh(refresh_integrations=False)
            with self.performance.plan_perf_trace_span("queue_prime_opening_handle_tracker_pool"):
                self.overlays.queue_prime_opening_handle_tracker_pool()
            with self.performance.plan_perf_trace_span("queue_prime_wall_hosted_openings_cache"):
                self.openings.queue_prime_wall_hosted_openings_cache()
            with self.performance.plan_perf_trace_span("queue_prime_hover_pick_caches"):
                self.selection.queue_prime_hover_pick_caches()
            with self.performance.plan_perf_trace_span("install_command_gate"):
                plan_command_gate.install(self)
            if self.performance.is_plan_perf_trace_enabled():
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "BIM Plan Edit perf trace: {path}\n").format(
                        path=self._plan_perf_log_path
                    )
                )
            if self.performance.is_plan_pick_debug_enabled():
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

    def can_place_plan_window(self):
        return self.windows.can_place_window()

    def stretch_selected_wall(self, endpoint):
        self.wall_edit.start_wall_edit(endpoint)

    def move_selected_wall(self):
        self.wall_edit.start_wall_edit("Move")

    def is_selected_wall_endpoint_editable(self):
        return self.wall_edit.is_selected_wall_endpoint_editable()

    def is_selected_wall_baseless(self):
        wall = self.selection.get_selected_plan_target_object("wall")
        if not wall:
            return False
        return not getattr(wall, "Base", None) and self.is_selected_wall_endpoint_editable()

    def _apply_plan_snap_profile(self):
        return plan_snap.apply_plan_snap_profile(_PLAN_EDIT_SNAP_SET)

    def _restore_snap_profile(self):
        return plan_snap.restore_snap_profile()

    def _push_opening_move_snap_profile(self):
        return plan_snap.push_opening_move_snap_profile(self, _OPENING_MOVE_SNAP_SET)

    def _pop_opening_move_snap_profile(self):
        return plan_snap.pop_opening_move_snap_profile(self)

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

    def _get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        return plan_picking.get_screen_distance_sq_to_segment(self, mouse_pos, start, end)

    def _get_screen_distance_sq_to_projected_segment(self, cursor_xy, start_xy, end_xy):
        return plan_picking.get_screen_distance_sq_to_projected_segment(
            cursor_xy,
            start_xy,
            end_xy,
        )

    def defer_document_visual_updates(self):
        return plan_document_visuals.defer_document_visual_updates(self)

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

    def _restore_gui_selection(self, obj):
        if not obj:
            return
        self.selection.set_gui_selection_object(obj)

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

    def slotCreatedObject(self, obj):
        return plan_document_visuals.slot_created_object(self, obj)

    def slotChangedObject(self, obj, prop):
        return plan_document_visuals.slot_changed_object(self, obj, prop)

    def slotDeletedObject(self, obj):
        return plan_document_visuals.slot_deleted_object(self, obj)

    def slotUndoDocument(self, doc):
        return plan_document_visuals.slot_undo_document(self, doc)

    def slotRedoDocument(self, doc):
        return plan_document_visuals.slot_redo_document(self, doc)

    def slotRecomputedDocument(self, doc):
        return plan_document_visuals.slot_recomputed_document(self, doc)

    def slotDeletedDocument(self, doc):
        return plan_document_visuals.slot_deleted_document(self, doc)

    def _is_modal_plan_interaction_active(self):
        return self.interaction.is_modal_plan_interaction_active()

    def _clear_input_hints(self):
        return self.status_text.clear_input_hints()

    def _retarget_edit_tracker(self, tracker, obj, index):
        return wall_overlays.retarget_edit_tracker(tracker, obj, index)

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

    def _is_plan_additive_selection_active(self):
        return plan_selection.is_plan_additive_selection_active(self)

    def _clear_hovered_plan_targets(self, kinds=None):
        return plan_hover_picking.clear_hovered_plan_targets(self, kinds=kinds)

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

    def _pick_space_region_candidate(self, mouse_pos, radius_px=10):
        return self.spaces.pick_space_region_candidate(mouse_pos, radius_px=radius_px)

    def _set_hovered_space_region_candidate(self, candidate):
        return self.spaces.set_hovered_space_region_candidate(candidate)

    def _create_space_region_base_object(self, candidate):
        return self.spaces.create_space_region_base_object(candidate)

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

    def _clear_plan_selection_state(self):
        return self.selection.clear_plan_selection_state()


plan_session_state.bind_session_state_accessors(PlanEditSession)

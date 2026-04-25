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
from bimplan.runtime import command_gate as plan_command_gate
from bimplan import document_visuals as plan_document_visuals
from bimplan.document_visuals import PlanDocumentVisualsAPI
from bimplan.runtime import input as plan_input
from bimplan.runtime import lifecycle as plan_lifecycle
from bimplan.object_visibility import PlanVisibilityAPI
from bimplan.performance import PlanPerformanceAPI
from bimplan import snap as plan_snap
from bimplan.runtime import session_state as plan_session_state
from bimplan.runtime.session_state import PlanInteractionAPI
from bimplan.storeys import PlanStoreysAPI
from bimplan import task_panel as plan_task_panel
from bimplan.selection.selection import PlanSelectionAPI
from bimplan.tools.symbol_edit import PlanSymbolsAPI
from bimplan.tools.opening_edit import PlanOpeningsAPI
from bimplan.providers.runtime import PlanProvidersAPI
from bimplan.tools.wall_create import PlanWallCreateAPI
from bimplan.tools.wall_relations import PlanWallRelationsAPI
from bimplan.tools.wall_edit import PlanWallEditAPI
from bimplan.tools.window_create import PlanWindowsAPI
from bimplan.tools.spaces import PlanSpacesAPI
from bimplan.runtime.view import PlanViewportAPI
from bimplan.overlays.runtime import PlanOverlaysAPI
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
_PLAN_VISUAL_SELECTED_REGION = plan_document_visuals.PLAN_VISUAL_SELECTED_REGION
_PLAN_VISUAL_SECONDARY_SELECTION = plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION
_PLAN_VISUAL_WALL_GRIPS = plan_document_visuals.PLAN_VISUAL_WALL_GRIPS
_PLAN_VISUAL_WALL_EDIT_PREVIEW = plan_document_visuals.PLAN_VISUAL_WALL_EDIT_PREVIEW
_PLAN_VISUAL_PROVIDER_OVERLAYS = plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
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


def _make_selection_observer_delegate(method_name):
    def _selection_observer_method(self, *args):
        return getattr(self.selection, method_name)(*args)

    return _selection_observer_method


def _make_document_visuals_delegate(method_name):
    def _document_visuals_method(self, *args):
        return getattr(self.document_visuals, method_name)(*args)

    return _document_visuals_method


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
        self.input = plan_input.PlanInputAPI(self)
        self.lifecycle = plan_lifecycle.PlanLifecycleAPI(self)
        self.symbols = PlanSymbolsAPI(self)
        self.windows = PlanWindowsAPI(self)
        self.viewport = PlanViewportAPI(self)
        self.overlays = PlanOverlaysAPI(self)
        self.wall_edit = PlanWallEditAPI(self)
        self.visibility = PlanVisibilityAPI(self)
        self.providers = PlanProvidersAPI(self)
        self.storey = PlanStoreysAPI(self)
        self.snap = plan_snap.PlanSnapAPI(self, _PLAN_EDIT_SNAP_SET, _OPENING_MOVE_SNAP_SET)
        self.performance = PlanPerformanceAPI(self)
        self.document_visuals = PlanDocumentVisualsAPI(self)
        self.status_text = PlanStatusTextAPI(self)
        self.task_panels = plan_task_panel.PlanTaskPanelsAPI(self)
        plan_session_state.initialize_session_state(self)

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
                get_viewer = self.viewport.get_runtime_attr(self.view, "getViewer")
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
                    self.viewport.discard_stale_runtime_object(self.view)
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
                self.storeys = self.storey.collect_storeys()
                self.performance.plan_perf_count("storeys_found", len(self.storeys))
            with self.performance.plan_perf_trace_span("find_initial_storey"):
                self.active_storey = self.storey.find_initial_storey()
                self.performance.plan_perf_set_fields(
                    active_storey=self.performance.plan_perf_describe_object(self.active_storey)
                )
            with self.performance.plan_perf_trace_span("capture_object_view_state"):
                self.visibility.capture_object_view_state()
            with self.performance.plan_perf_trace_span("apply_plan_view"):
                self.viewport.apply_plan_view(fit=False)
            with self.performance.plan_perf_trace_span("apply_plan_snap_profile"):
                self.snap.apply_plan_snap_profile()
            self.visibility.apply_storey_visibility()
            with self.performance.plan_perf_trace_span("attach_selection_observer"):
                self.selection.attach_selection_observer()
            with self.performance.plan_perf_trace_span("attach_document_observer"):
                self.document_visuals.attach_document_observer()
            with self.performance.plan_perf_trace_span("register_edit_callbacks"):
                self.viewport.register_edit_callbacks()
            with self.performance.plan_perf_trace_span(
                "refresh_primary_selected_plan_target_on_enter"
            ):
                self.selection.refresh_primary_selected_plan_target()

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

    def shutdown(self, close_dialog=True, teardown=False):
        global _active_session

        if self._finishing:
            return True
        self._finishing = True

        try:
            plan_lifecycle.shutdown(self, close_dialog=close_dialog, teardown=teardown)
        finally:
            self.lifecycle.disconnect_teardown_signals()
            self._tearing_down = True
            self.lifecycle.discard_runtime_references()
            self._aux_task_panels = []
            _active_session = None
            self._finishing = False
            _refresh_contextual_task_watchers()
        return True

    def get_plan_provider_registry(self):
        return get_plan_edit_registry()

    def defer_document_visual_updates(self):
        return plan_document_visuals.defer_document_visual_updates(self)

    addSelection = _make_selection_observer_delegate("addSelection")

    removeSelection = _make_selection_observer_delegate("removeSelection")

    setSelection = _make_selection_observer_delegate("setSelection")

    clearSelection = _make_selection_observer_delegate("clearSelection")

    setPreselection = _make_selection_observer_delegate("setPreselection")

    removePreselection = _make_selection_observer_delegate("removePreselection")

    _is_opening_visual_dependency = _make_document_visuals_delegate("is_opening_visual_dependency")

    _refresh_selected_opening_visuals = _make_document_visuals_delegate(
        "refresh_selected_opening_visuals"
    )

    slotCreatedObject = _make_document_visuals_delegate("slot_created_object")

    slotChangedObject = _make_document_visuals_delegate("slot_changed_object")

    slotDeletedObject = _make_document_visuals_delegate("slot_deleted_object")

    slotUndoDocument = _make_document_visuals_delegate("slot_undo_document")

    slotRedoDocument = _make_document_visuals_delegate("slot_redo_document")

    slotRecomputedDocument = _make_document_visuals_delegate("slot_recomputed_document")

    slotDeletedDocument = _make_document_visuals_delegate("slot_deleted_document")


plan_session_state.bind_session_state_accessors(PlanEditSession)

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
from bimplan.document_visuals import PlanDocumentVisualsAPI
from bimplan.runtime.embedded_commands import PlanEmbeddedToolsAPI
from bimplan.runtime import input as plan_input
from bimplan.runtime import lifecycle as plan_lifecycle
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.object_visibility import PlanVisibilityAPI
from bimplan.performance import PlanPerformanceAPI
from bimplan.picking import PlanPickingAPI
from bimplan import snap as plan_snap
from bimplan.runtime import session_state as plan_session_state
from bimplan.runtime.session_state import PlanInteractionAPI
from bimplan.storeys import PlanStoreysAPI
from bimplan.ui import task_panel as plan_task_panel
from bimplan.selection.selection import PlanSelectionAPI
from bimplan.tools.symbol_edit import PlanSymbolsAPI
from bimplan.tools.opening_edit import PlanOpeningsAPI
from bimplan.tools.move import PlanMoveAPI
from bimplan.providers.runtime import PlanProvidersAPI
from bimplan.tools.wall_create import PlanWallCreateAPI
from bimplan.tools.wall_relations import PlanWallRelationsAPI
from bimplan.tools.wall_edit import PlanWallEditAPI
from bimplan.tools.window_create import PlanHostedOpeningsAPI
from bimplan.tools.spaces import PlanSpacesAPI
from bimplan.runtime.view import PlanViewportAPI
from bimplan.overlays.runtime import PlanOverlaysAPI
from bimplan.ui.status_text import PlanStatusTextAPI
from bimplan.ui.controls import PlanEditControlsWidget
from bimplan.contextual_rendering import PlanContextualRenderingAPI
from bimplan.representation_request import PlanRepresentationRequestAPI
from bimplan.contextual_editing import PlanContextualEditingAPI
from bimplan.contextual_datums import PlanContextualDatumService
from bimviews.runtime import BIMViewRuntime
from bimviews.viewport_grid import ViewportGridController
from bimviews.projection import ViewportProjectionCoordinator
from bimviews.viewport_ruler import ViewportRulerController

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
_PLAN_EDIT_SNAP_SET = {
    "Lock",
    "Near",
    "Extension",
    "Grid",
    "Endpoint",
    "Midpoint",
    "Perpendicular",
    "Ortho",
    "Intersection",
    "WorkingPlane",
}
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
    set_task_watchers = getattr(workbench, "setTaskWatchers", None)
    if not callable(set_task_watchers):
        return
    try:
        FreeCADGui.Control.clearTaskWatcher()
        set_task_watchers()
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


def start_editing_session(
    *, show_task_panel=False, initial_request=None, prepare_only=False
):
    """Start the representation editing runtime for the active PLAN view.

    Navigator activation uses the runtime without opening the legacy Plan Edit
    task panel.  The explicit ``BIM_PlanEdit`` compatibility command passes
    ``show_task_panel=True`` so existing command-driven workflows retain their
    controls.  ``initial_request`` lets saved-view activation initialize the
    runtime from its target representation during preparation.
    """

    global _active_session

    if _active_session:
        if show_task_panel:
            _active_session.ensure_task_panel()
            try:
                FreeCADGui.Control.showTaskView()
            except Exception:
                pass
            _refresh_contextual_task_watchers()
        return _active_session

    _register_builtin_plan_edit_integrations()
    session = BIMEditingSession()
    session._initial_representation_request = initial_request
    if session.prepare():
        _active_session = session
        if not prepare_only and not session.populate(attach_task_panel=show_task_panel):
            _active_session = None
            session.shutdown(close_dialog=False)
            return None
        if show_task_panel:
            try:
                FreeCADGui.Control.showTaskView()
            except Exception:
                pass
            _refresh_contextual_task_watchers()
        return session
    return None


def start_session():
    """Compatibility entry point for the former Plan Edit session."""

    return start_editing_session(show_task_panel=True)


def activate_representation_request(request, *, prepare_only=False):
    """Apply a saved BIM request through its compatible editing runtime.

    Saved views are the user-facing editing context.  Opening a PLAN view from
    the BIM Navigator initializes the runtime and exposes its contextual task
    panel without requiring the former Plan Edit command.  Startup preparation
    remains panel-free until presentation has been released.  SECTION and
    ELEVATION use the shared object-agnostic contextual session; MODEL leaves
    document interaction to the standard viewport.
    """

    if request is None:
        return None

    import ArchRepresentation

    purpose = getattr(request, "purpose", None)
    if purpose != ArchRepresentation.RepresentationPurpose.PLAN:
        # The Plan runtime must not keep intercepting input after switching
        # to another representation.
        session = get_active_session()
        if session is not None:
            session.deactivate_for_view_transition()
        from bimcontextual.session import active_session as active_contextual_session

        contextual = active_contextual_session()
        if purpose not in (
            ArchRepresentation.RepresentationPurpose.SECTION,
            ArchRepresentation.RepresentationPurpose.ELEVATION,
        ):
            if contextual is not None:
                contextual.close()
            return None
        if contextual is not None:
            if contextual.request is request:
                return contextual
            contextual.close()
        from ArchContextualCreation import architectural_contextual_providers
        from bimcontextual.session import start_session as start_contextual_session

        source = getattr(request, "source", None)
        return start_contextual_session(
            request=request,
            sources=tuple(getattr(source, "Objects", ()) or ()),
            orient_to_request=False,
            providers=architectural_contextual_providers(),
        )

    from bimcontextual.session import active_session as active_contextual_session

    contextual = active_contextual_session()
    if contextual is not None:
        contextual.close()

    session = get_active_session()
    created = False
    if session is None:
        session = start_editing_session(
            show_task_panel=not prepare_only,
            initial_request=request,
            prepare_only=prepare_only,
        )
        created = session is not None
    if session is None:
        return None

    # A newly-created session was initialized from this exact request and has
    # already applied it during enter().  Avoid applying the same camera,
    # working plane and representation a second time.
    if created:
        return session

    source = getattr(request, "source", None)
    if source is not None:
        session.representation_request.set_request(request, fit=False)
    else:
        # A request without a source is still meaningful (it represents the
        # document-level PLAN context).  Keep all live consumers synchronized
        # when switching from a sourced view so no stale storey/grid/runtime
        # state is retained.
        session.representation_request.set_request(request, fit=False)

    if not prepare_only:
        session.ensure_task_panel()
        try:
            FreeCADGui.Control.showTaskView()
        except Exception:
            pass
        _refresh_contextual_task_watchers()
    return session


class BIMEditingSession:
    """Own the BIM editing session and its active viewport runtime.

    The public ``PlanEditSession`` name remains as a compatibility alias while
    the implementation moves toward a representation-driven BIM session.
    """

    # State-backed compatibility properties are bound after class definition.

    def __init__(self):
        self._prepared = False
        self._populated = False
        self.view_runtime = None
        # Keyed by ``id(view)`` so transient GUI view wrappers do not need to
        # be hashable.  The registry is the migration seam for simultaneous
        # PLAN/MODEL/SECTION viewports; the legacy Plan Edit command still
        # drives only the active runtime for now.
        self.view_runtimes = {}
        self.picking = PlanPickingAPI(self)
        self.selection = PlanSelectionAPI(self)
        self.spaces = PlanSpacesAPI(self)
        self.openings = PlanOpeningsAPI(self)
        self.wall_relations = PlanWallRelationsAPI(self)
        self.wall_create = PlanWallCreateAPI(self)
        self.move_tool = PlanMoveAPI(self)
        self.interaction = PlanInteractionAPI(self)
        self.embedded_tools = PlanEmbeddedToolsAPI(self)
        self.input = plan_input.PlanInputAPI(self)
        self.lifecycle = plan_lifecycle.PlanLifecycleAPI(self)
        self.symbols = PlanSymbolsAPI(self)
        self.hosted_openings = PlanHostedOpeningsAPI(self)
        self.viewport = PlanViewportAPI(self)
        self.overlays = PlanOverlaysAPI(self)
        self.wall_edit = PlanWallEditAPI(self)
        self.visibility = PlanVisibilityAPI(self)
        self.providers = PlanProvidersAPI(self)
        self.storey = PlanStoreysAPI(self)
        self.snap = plan_snap.PlanSnapAPI(self, _PLAN_EDIT_SNAP_SET)
        self.performance = PlanPerformanceAPI(self)
        self.document_visuals = PlanDocumentVisualsAPI(self)
        self.contextual_rendering = PlanContextualRenderingAPI(self)
        self.representation_request = PlanRepresentationRequestAPI(self)
        self.contextual_editing = PlanContextualEditingAPI(self)
        self.contextual_datums = PlanContextualDatumService(self)
        self.status_text = PlanStatusTextAPI(self)
        self.task_panels = plan_task_panel.PlanTaskPanelsAPI(self)
        self.projection = ViewportProjectionCoordinator(self)
        self.view_grid = ViewportGridController(self)
        self.view_rulers = ViewportRulerController(self)
        plan_session_state.initialize_session_state(self)
        self.viewport_state.plan_paper_rgb = _PLAN_PAPER_RGB
        self.viewport_state.plan_view_locked_actions = _PLAN_VIEW_LOCKED_ACTIONS

    @property
    def current_tool(self):
        return self._current_tool

    @current_tool.setter
    def current_tool(self, value):
        tool = plan_runtime_tools.coerce_plan_tool(value)
        if tool not in (None, plan_runtime_tools.PlanTool.SELECT):
            runtime = getattr(self, "view_runtime", None)
            if runtime is not None and not runtime.supports("planar_editing"):
                return
        self._current_tool = tool

    @property
    def hovered_wall(self):
        return self.selection_state.hovered_wall

    @hovered_wall.setter
    def hovered_wall(self, value):
        self.selection_state.hovered_wall = value

    @property
    def hovered_opening(self):
        return self.selection_state.hovered_opening

    @hovered_opening.setter
    def hovered_opening(self, value):
        self.selection_state.hovered_opening = value

    @property
    def hovered_symbol(self):
        return self.selection_state.hovered_symbol

    @hovered_symbol.setter
    def hovered_symbol(self, value):
        self.selection_state.hovered_symbol = value

    @property
    def hovered_provider(self):
        return self.selection_state.hovered_provider

    @hovered_provider.setter
    def hovered_provider(self, value):
        self.selection_state.hovered_provider = value

    @property
    def hovered_space(self):
        return self.selection_state.hovered_space

    @hovered_space.setter
    def hovered_space(self, value):
        self.selection_state.hovered_space = value

    @property
    def hovered_region(self):
        return self.selection_state.hovered_region

    @hovered_region.setter
    def hovered_region(self, value):
        self.selection_state.hovered_region = value

    def enter(self, *, attach_task_panel=True):
        """Prepare and fully populate a session synchronously.

        Direct callers retain the historical ``enter()`` contract.  Document
        startup uses the two phases separately so the prepared view can be
        revealed before semantic geometry and pick caches are built.
        """

        with self.performance.plan_perf_trace_event("enter_plan_edit"):
            return self.prepare() and self.populate(attach_task_panel=attach_task_panel)

    def prepare(self):
        """Apply the view intent required for the session's first frame."""

        if self._prepared:
            return True
        with self.performance.plan_perf_trace_event("prepare_plan_edit"):
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
                self.view_runtime = self.runtime_for(self.view)

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
            initial_request = getattr(self, "_initial_representation_request", None)
            initial_source = getattr(initial_request, "source", None)
            if initial_request is None:
                self.representation_request.set_source(
                    self.representation_request.find_initial_source(), refresh=False
                )
            else:
                self.representation_request.source = initial_source
                self.representation_request.request = initial_request
                if initial_source is not None:
                    try:
                        import Draft

                        is_storey = Draft.getType(initial_source) == "Floor" or getattr(
                            initial_source, "IfcType", ""
                        ) == "Building Storey"
                    except Exception:
                        is_storey = getattr(initial_source, "IfcType", "") == "Building Storey"
                    if is_storey:
                        self.active_storey = initial_source
            with self.performance.plan_perf_trace_span("capture_object_view_state"):
                self.visibility.capture_object_view_state()
            self.visibility.begin_view_context()
            with self.performance.plan_perf_trace_span("apply_plan_view"):
                self.viewport.apply_representation_request(
                    self.representation_request.request, fit=False
                )
            with self.performance.plan_perf_trace_span("apply_plan_snap_profile"):
                self.snap.apply_plan_snap_profile()
            with self.performance.plan_perf_trace_span("apply_plan_grid"):
                self.snap.apply_plan_grid()
            self.visibility.apply_storey_visibility()
            with self.performance.plan_perf_trace_span("attach_view_rulers"):
                self.view_rulers.set_request(self.representation_request.request)
            with self.performance.plan_perf_trace_span("attach_view_grid"):
                self.view_grid.set_request(self.representation_request.request)
            # Teardown must already be observable during the prepare/populate
            # gap so closing a document cancels a prepared session cleanly.
            with self.performance.plan_perf_trace_span("attach_document_observer"):
                self.document_visuals.attach_document_observer()
            self._prepared = True
            return True

    def populate(self, *, attach_task_panel=True):
        """Build semantic rendering and interaction state after presentation."""

        if self._populated:
            if attach_task_panel:
                self.ensure_task_panel()
            return True
        if not self._prepared and not self.prepare():
            return False
        with self.performance.plan_perf_trace_event("populate_plan_edit"):
            with self.performance.plan_perf_trace_span("start_contextual_rendering"):
                self.contextual_rendering.start()
            with self.performance.plan_perf_trace_span("attach_selection_observer"):
                self.selection.sync.attach_selection_observer()
            with self.performance.plan_perf_trace_span("register_edit_callbacks"):
                self.viewport.register_edit_callbacks()
            with self.performance.plan_perf_trace_span(
                "refresh_primary_selected_plan_target_on_enter"
            ):
                self.selection.refresh.refresh_primary_selected_plan_target()

            if attach_task_panel:
                with self.performance.plan_perf_trace_span("build_task_panel"):
                    self.ensure_task_panel()
            with self.performance.plan_perf_trace_span("queue_prime_wall_hosted_openings_cache"):
                self.openings.queue_prime_wall_hosted_openings_cache()
            with self.performance.plan_perf_trace_span("queue_warm_exact_compilations"):
                self.openings.queue_warm_exact_compilations()
            with self.performance.plan_perf_trace_span("queue_prime_hover_pick_caches"):
                self.selection.hover.queue_prime_hover_pick_caches()
            with self.performance.plan_perf_trace_span("install_command_gate"):
                plan_command_gate.install(self)
            self._populated = True
            if self.performance.is_plan_perf_trace_enabled():
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "BIM Plan Edit perf trace: {path}\n").format(
                        path=self.performance_state.plan_perf_log_path
                    )
                )
            if self.performance.is_plan_pick_debug_enabled():
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "BIM Plan Edit pick debug: {path}\n").format(
                        path=self.performance_state.plan_pick_debug_log_path
                    )
                )
            return True

    def ensure_task_panel(self):
        """Create the legacy controls only when an explicit command asks for them."""

        if self.task_panel is not None:
            return self.task_panel
        runtime = getattr(self, "view_runtime", None)
        if runtime is not None and not runtime.supports("planar_editing"):
            return None
        panel = PlanEditControlsWidget(self)
        self.task_panels.attach_task_panel(panel)
        panel.refresh(refresh_integrations=False)
        return panel

    def supports_capability(self, capability, view=None):
        """Resolve a capability from the runtime owning the input viewport."""

        runtime = self.runtime_for(view, create=False)
        if runtime is None:
            return False
        return runtime.supports(capability)

    def supports_tool(self, tool, view=None):
        """Return whether a Plan tool is valid for the active view runtime."""

        runtime = self.runtime_for(view, create=False)
        if runtime is None:
            return False
        supports_tool = getattr(runtime, "supports_tool", None)
        if callable(supports_tool):
            return bool(supports_tool(tool))
        normalized = plan_runtime_tools.coerce_plan_tool(tool)
        if normalized in (None, plan_runtime_tools.PlanTool.SELECT):
            return self.supports_capability("planar_editing", view=view) or self.supports_capability(
                "model_editing", view=view
            )
        return self.supports_capability("planar_editing", view=view)

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        return plan_lifecycle.finish(self, close_dialog=close_dialog)

    def runtime_for(self, view=None, *, create=True):
        """Return the BIM runtime associated with a viewport.

        ``view=None`` means the active viewport owned by this editing
        session.  Existing Plan Edit code continues to use ``view_runtime``;
        new view-aware tools can ask for the runtime belonging to the view
        that generated an input event.
        """

        target = view if view is not None else self.view
        if target is None:
            return None
        key = id(target)
        runtime = self.view_runtimes.get(key)
        if runtime is None or runtime.closed:
            if not create:
                return None
            runtime = BIMViewRuntime(target, session=self)
            self.view_runtimes[key] = runtime
        if target is self.view:
            self.view_runtime = runtime
        return runtime

    def remove_view_runtime(self, view=None):
        """Close and forget one viewport runtime."""

        target = view if view is not None else self.view
        if target is None:
            return False
        runtime = self.view_runtimes.pop(id(target), None)
        if runtime is None:
            return False
        runtime.close()
        if runtime is self.view_runtime:
            self.view_runtime = None
        return True

    def begin_teardown(self):
        return plan_lifecycle.begin_teardown(self)

    def _finish_session(self, operation):
        global _active_session

        lifecycle_state = self.lifecycle_state
        if lifecycle_state.finishing:
            return True
        lifecycle_state.finishing = True

        try:
            self.viewport.discard_queued_view_updates()
            operation()
        finally:
            self.lifecycle.disconnect_teardown_signals()
            lifecycle_state.tearing_down = True
            self.lifecycle.discard_runtime_references()
            self.task_panel_state.aux_task_panels = []
            _active_session = None
            lifecycle_state.finishing = False
            _refresh_contextual_task_watchers()
        return True

    def deactivate_for_view_transition(self):
        return self._finish_session(
            lambda: self.lifecycle.deactivate_for_view_transition(close_dialog=False)
        )

    def shutdown(self, close_dialog=True, teardown=False):
        return self._finish_session(
            lambda: plan_lifecycle.shutdown(
                self, close_dialog=close_dialog, teardown=teardown
            )
        )

    def addSelection(self, *args):
        return self.selection.addSelection(*args)

    def removeSelection(self, *args):
        return self.selection.removeSelection(*args)

    def setSelection(self, *args):
        return self.selection.setSelection(*args)

    def clearSelection(self, *args):
        return self.selection.clearSelection(*args)

    def setPreselection(self, *args):
        return self.selection.setPreselection(*args)

    def removePreselection(self, *args):
        return self.selection.removePreselection(*args)

    def slotCreatedObject(self, *args):
        return self.document_visuals.slot_created_object(*args)

    def slotChangedObject(self, *args):
        return self.document_visuals.slot_changed_object(*args)

    def slotDeletedObject(self, *args):
        return self.document_visuals.slot_deleted_object(*args)

    def slotUndoDocument(self, *args):
        return self.document_visuals.slot_undo_document(*args)

    def slotRedoDocument(self, *args):
        return self.document_visuals.slot_redo_document(*args)

    def slotRecomputedDocument(self, *args):
        return self.document_visuals.slot_recomputed_document(*args)

    def representationCacheObjectInvalidated(self, obj):
        return self.document_visuals.queue_contextual_representation_refresh(obj)

    def slotDeletedDocument(self, *args):
        return self.document_visuals.slot_deleted_document(*args)


# Compatibility for commands, addons and tests that still construct the old
# modal session directly.  New code should use BIMEditingSession and inspect
# ``session.view_runtime`` for representation capabilities.
PlanEditSession = BIMEditingSession

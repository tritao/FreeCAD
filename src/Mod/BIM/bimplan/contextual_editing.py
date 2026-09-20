# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan-specific adapters for the shared BIM contextual editing engine."""

from contextlib import ExitStack, nullcontext

import FreeCAD
from draftguitools.gui_base import DraftInteractionHost

from bimcontextual.editing import ContextualEditController


class _PlanContextualInputAdapter:
    def __init__(self, session):
        self.session = session
        self.host = None

    def start_point_pick(self, point, callback, move_callback, title):
        import FreeCADGui
        self.session.snap.set_active_draft_command()
        try:
            FreeCADGui.Snapper.getPoint(
                last=point, callback=callback, movecallback=move_callback,
                title=title, noTracker=True,
                interaction_plane=self.session.viewport.get_interaction_plane(),
                view=self.session.view,
            )
        except Exception:
            self.clear()
            raise

    def defer(self, key, callback):
        return self.session.viewport.queue_scene_graph_mutation(key, callback)

    def clear(self):
        self.session.snap.clear_active_draft_command()

    def set_value_input(self, **kwargs):
        if self.host is None:
            self.host = DraftInteractionHost(view=self.session.view)
        return self.host.set_value_input(**kwargs)

    def clear_value_input(self):
        if self.host is not None:
            return self.host.clear_value_input()
        return False


class PlanContextualEditingAPI:
    """Plan Edit adapter around the viewer-independent contextual controller."""

    def __init__(self, session):
        self.session = session
        self.controller = None
        self.input_adapter = _PlanContextualInputAdapter(session)

    @property
    def editor(self):
        return self.controller.editor if self.controller is not None else None

    def _new_controller(self):
        return ContextualEditController(
            self.session.view, self.session.representation_request,
            self.session.contextual_rendering, self.input_adapter,
            refresh_callback=self.session.contextual_rendering.refresh_edit_dependencies,
            refresh_failure_callback=self.session.contextual_rendering.refresh_object,
            feedback_callback=self._set_feedback,
            clear_feedback_callback=self._clear_feedback,
            commit_scope=self._commit_scope,
            trace_scope=getattr(
                self.session.performance, "plan_perf_trace_span", None
            ),
        )

    def _commit_scope(self, impact):
        if impact is not None:
            plan = getattr(impact, "recompute", None)
            set_fields = getattr(
                self.session.performance, "plan_perf_set_fields", None
            )
            if callable(set_fields):
                set_fields(
                    recompute_roots=tuple(getattr(plan, "roots", ()) or ()),
                    representation_sources=tuple(
                        getattr(impact, "representation_sources", ()) or ()
                    ),
                )
        stack = ExitStack()
        if impact is not None:
            from bimviews import representation_cache

            derived_sources = (
                impact.derived_value_sources
                if impact.derived_value_sources is not None
                else impact.representation_sources
            )
            stack.enter_context(
                representation_cache.scoped_derived_invalidation(
                    derived_sources
                )
            )
        stack.enter_context(
            self.session.document_visuals.defer_contextual_edit_updates(impact)
        )
        return stack

    def begin(self, handle):
        self.controller = self._new_controller()
        return self.controller.begin(handle)

    def preview(self, pointer):
        if self.controller is None:
            raise RuntimeError("No BIM edit handle is active")
        return self.controller.preview(pointer)

    def preview_value(self, value):
        if self.controller is None:
            raise RuntimeError("No BIM edit handle is active")
        return self.controller.preview_value(value)

    def commit(self, pointer):
        if self.controller is None:
            raise RuntimeError("No BIM edit handle is active")
        with self._commit_trace("pointer"):
            return self.controller.commit(pointer)

    def cancel(self, *, refresh=True):
        if self.controller is not None:
            self.controller.cancel(refresh=refresh)
        self.input_adapter.clear()
        self.input_adapter.clear_value_input()

    def activate(self, handle):
        self.cancel()
        self.controller = self._new_controller()
        if handle.interaction == "Immediate":
            with self._commit_trace("immediate", handle=handle):
                activated = self.controller.activate(handle)
        else:
            activated = self.controller.activate(handle)
        if not activated:
            return False
        if handle.operation.value_kind == "Scalar":
            self.input_adapter.set_value_input(
                label=handle.operation.label, unit="Length",
                value=handle.operation.get_value(handle.source),
                callback=self.commit_value,
            )
        return True

    def commit_value(self, value):
        if self.controller is None or self.controller.editor is None:
            return False
        with self._commit_trace("value"):
            result = self.controller.commit_value(value)
        if result.success:
            self.input_adapter.clear_value_input()
        return result.success

    def _commit_trace(self, interaction, handle=None):
        if handle is None:
            handle = self.controller.active_edit if self.controller is not None else None
        operation = getattr(handle, "operation", None)
        trace_event = getattr(
            self.session.performance, "plan_perf_trace_event", None
        )
        if not callable(trace_event):
            return nullcontext()
        return trace_event(
            "contextual_edit_commit",
            interaction=interaction,
            operation=getattr(operation, "name", None),
            source=getattr(handle, "source", None),
        )

    def _set_feedback(self, message):
        self.session.status_text.set_integration_feedback_message(message)
        FreeCAD.Console.PrintWarning("BIM Plan Edit: {}\n".format(message))
        self.session.task_panels.refresh_task_panel_status()

    def _clear_feedback(self):
        self.session.status_text.clear_integration_feedback_message()

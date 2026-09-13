# SPDX-License-Identifier: LGPL-2.1-or-later

"""Context-projected editing of semantic handles from BIM representations."""

from contextlib import nullcontext
from dataclasses import dataclass

import FreeCAD
from ArchRepresentation import BIMEditTransaction, project_to_representation_plane



def _handle_value(handle):
    return handle.operation.get_value(handle.source)


@dataclass(frozen=True)
class BIMEditPreview:
    """Non-persistent result of projecting a pointer onto a semantic handle."""

    handle: object
    value: object
    point: object
    validation: object = None


@dataclass(frozen=True)
class BIMEditResult:
    """Structured outcome of a semantic edit commit."""

    success: bool
    preview: object = None
    reason: str = ""

    @property
    def value(self):
        return getattr(self.preview, "value", None)

    @property
    def point(self):
        return getattr(self.preview, "point", None)


class BIMContextualHandleEditor:
    """One active semantic-handle drag, independent of Coin and Qt."""

    def __init__(self, context, refresh=None):
        self.context = context
        self.refresh = refresh
        self.handle = None
        self.start_value = None

    def begin(self, handle):
        if handle is None or handle.interaction not in {"Linear", "Planar"}:
            raise ValueError("Unsupported BIM edit handle")
        validation = handle.operation.validate(handle.source)
        if not validation.allowed:
            raise ValueError(validation.reason)
        if handle.interaction == "Linear" and handle.direction.Length <= 1e-9:
            raise ValueError("BIM edit handle has no direction")
        self.handle = handle
        self.start_value = _handle_value(handle)
        return self.preview(handle.point)

    def preview(self, pointer):
        if self.handle is None:
            raise RuntimeError("No BIM edit handle is active")
        projected = project_to_representation_plane(pointer, self.context)
        if self.handle.interaction == "Planar":
            value = self.start_value + projected - self.handle.point
            validation = self.handle.operation.validate(self.handle.source, value)
            return BIMEditPreview(self.handle, value, projected, validation)
        delta = (projected - self.handle.point).dot(self.handle.direction)
        value = self.start_value + delta * self.handle.operation.sensitivity
        point = self.handle.point + self.handle.direction * delta
        validation = self.handle.operation.validate(self.handle.source, value)
        return BIMEditPreview(self.handle, value, point, validation)

    def cancel(self):
        self.handle = None
        self.start_value = None

    def commit(self, pointer):
        preview = self.preview(pointer)
        handle = preview.handle
        try:
            self._commit_value(handle, preview.value)
            if callable(self.refresh):
                self.refresh(handle.source)
        finally:
            self.cancel()
        return BIMEditResult(True, preview=preview)

    @staticmethod
    def _commit_value(handle, value):
        obj = handle.source
        doc = getattr(obj, "Document", None) or FreeCAD.ActiveDocument
        operation = handle.operation
        if operation.manages_transaction:
            operation.apply(obj, value)
            return
        with BIMEditTransaction(doc, operation.label):
            operation.apply(obj, value)
            if doc is not None:
                doc.recompute()


class ContextualEditController:
    """Coordinate one contextual edit using injected view and input services.

    The controller owns handle state and preview/commit/cancel behavior. It
    deliberately knows nothing about Plan Edit sessions, selection, Draft, or
    a particular renderer implementation.
    """

    def __init__(
        self,
        view,
        representation_context,
        renderer,
        input_adapter=None,
        *,
        refresh_callback=None,
        refresh_failure_callback=None,
        feedback_callback=None,
        clear_feedback_callback=None,
        commit_scope=None,
    ):
        self.view = view
        self.context = getattr(representation_context, "context", representation_context)
        self.renderer = renderer
        self.input_adapter = input_adapter
        self.refresh_callback = refresh_callback
        self.refresh_failure_callback = refresh_failure_callback
        self.feedback_callback = feedback_callback
        self.clear_feedback_callback = clear_feedback_callback
        self.commit_scope = commit_scope or nullcontext
        self.editor = None

    @property
    def active_edit(self):
        return self.editor.handle if self.editor is not None else None

    def begin(self, handle):
        self.editor = BIMContextualHandleEditor(
            self.context,
            refresh=self.refresh_callback,
        )
        try:
            preview = self.editor.begin(handle)
        except Exception as exc:
            self.editor = None
            self._set_feedback(exc)
            return BIMEditResult(False, reason=str(exc))
        self._clear_feedback()
        self._call_renderer("set_handle_state", handle, "active")
        return preview

    def preview(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        preview = self.editor.preview(pointer)
        self._call_renderer("preview_handle", preview.handle, preview.point)
        state = "active" if preview.validation.allowed else "invalid"
        self._call_renderer("set_handle_state", preview.handle, state)
        representation = preview.handle.operation.get_preview_representation(
            preview.handle.source,
            preview.value,
            self.editor.context,
        )
        shape = preview.handle.operation.get_preview_shape(
            preview.handle.source,
            preview.value,
            self.editor.context,
        )
        source = preview.handle.source
        if representation is not None:
            self._call_renderer(
                "set_preview_representation",
                source,
                representation,
                preview.validation.allowed,
            )
        elif shape is None or not preview.validation.allowed:
            self._call_renderer("clear_preview", source)
        else:
            self._call_renderer("set_preview_shape", source, shape)
        return preview

    def commit(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        handle = self.editor.handle
        editor = self.editor
        try:
            with self.commit_scope():
                result = editor.commit(pointer)
            self._clear_feedback()
            return result
        except Exception as exc:
            self._set_feedback(exc)
            if callable(self.refresh_failure_callback):
                self.refresh_failure_callback(handle.source)
            return BIMEditResult(False, reason=str(exc))
        finally:
            self._call_renderer("clear_preview", handle.source)
            self.editor = None

    def cancel(self, *, refresh=True):
        editor = self.editor
        handle = editor.handle if editor is not None else None
        if editor is not None:
            editor.cancel()
        self.editor = None
        if handle is not None:
            self._call_renderer("clear_preview", handle.source)
            if refresh and callable(self.refresh_failure_callback):
                self.refresh_failure_callback(handle.source)

    def activate(self, handle):
        """Start an immediate edit or delegate pointer input to the adapter."""

        self.cancel()
        if handle.interaction == "Immediate":
            validation = handle.operation.validate(handle.source)
            if not validation.allowed:
                self._set_feedback(validation.reason)
                return False
            try:
                BIMContextualHandleEditor._commit_value(
                    handle, handle.operation.get_value(handle.source)
                )
                if callable(self.refresh_callback):
                    self.refresh_callback(handle.source)
                self._call_renderer("sync_visible_handles")
                self._clear_feedback()
                return True
            except Exception as exc:
                self._set_feedback(exc)
                return False
        if self.input_adapter is None:
            self._set_feedback("No input adapter is available for this BIM edit.")
            return False
        started = self.begin(handle)
        if isinstance(started, BIMEditResult) and not started.success:
            return False
        try:
            self.input_adapter.start_point_pick(
                handle.point,
                self._finish_point_pick,
                self._preview_point_pick,
                "Edit {}".format(handle.role),
            )
        except Exception:
            self.cancel()
            raise
        return True

    def _preview_point_pick(self, point=None, input_info=None):
        del input_info
        if point is not None and self.editor is not None:
            self.preview(point)

    def _finish_point_pick(self, point=None, input_info=None):
        del input_info
        editor = self.editor
        target = None if point is None else FreeCAD.Vector(point)

        def finish_after_event():
            try:
                if self.editor is not editor:
                    return
                if target is None:
                    self.cancel()
                else:
                    self.commit(target)
            finally:
                self.input_adapter.clear()

        if not self.input_adapter.defer(("finish-contextual-handle", id(editor)), finish_after_event):
            self.cancel()
            self.input_adapter.clear()

    def _call_renderer(self, method, *args):
        callback = getattr(self.renderer, method, None)
        if callable(callback):
            return callback(*args)
        return None

    def _set_feedback(self, error):
        message = str(error or "").strip() or "BIM contextual edit failed."
        if callable(self.feedback_callback):
            self.feedback_callback(message)

    def _clear_feedback(self):
        if callable(self.clear_feedback_callback):
            self.clear_feedback_callback()


class _PlanContextualInputAdapter:
    """Bridge the generic controller to Plan Edit's Draft point acquisition."""

    def __init__(self, session):
        self.session = session

    def start_point_pick(self, point, callback, move_callback, title):
        import FreeCADGui

        self.session.snap.set_active_draft_command()
        try:
            FreeCADGui.Snapper.getPoint(
                last=point,
                callback=callback,
                movecallback=move_callback,
                title=title,
                noTracker=True,
            )
        except Exception:
            self.clear()
            raise

    def defer(self, key, callback):
        return self.session.viewport.queue_scene_graph_mutation(key, callback)

    def clear(self):
        self.session.snap.clear_active_draft_command()


class PlanContextualEditingAPI:
    """Plan Edit adapter around the viewer-independent contextual controller."""

    def __init__(self, session):
        self.session = session
        self.controller = None

    @property
    def editor(self):
        return self.controller.editor if self.controller is not None else None

    def _new_controller(self):
        return ContextualEditController(
            self.session.view,
            self.session.representation_context,
            self.session.contextual_rendering,
            _PlanContextualInputAdapter(self.session),
            refresh_callback=self.session.contextual_rendering.refresh_edit_dependencies,
            refresh_failure_callback=self.session.contextual_rendering.refresh_object,
            feedback_callback=self._set_feedback,
            clear_feedback_callback=self._clear_feedback,
            commit_scope=self._commit_scope,
        )

    def _commit_scope(self):
        session = self.session

        class CommitScope:
            def __enter__(self):
                session.document_visual_state.contextual_edit_recompute_depth += 1

            def __exit__(self, exc_type, exc_value, traceback):
                del exc_type, exc_value, traceback
                visual_state = session.document_visual_state
                visual_state.contextual_edit_recompute_depth = max(
                    0, visual_state.contextual_edit_recompute_depth - 1
                )
                return False

        return CommitScope()

    def begin(self, handle):
        self.controller = self._new_controller()
        return self.controller.begin(handle)

    def preview(self, pointer):
        if self.controller is None:
            raise RuntimeError("No BIM edit handle is active")
        return self.controller.preview(pointer)

    def commit(self, pointer):
        if self.controller is None:
            raise RuntimeError("No BIM edit handle is active")
        return self.controller.commit(pointer)

    def cancel(self, *, refresh=True):
        if self.controller is not None:
            self.controller.cancel(refresh=refresh)

    def activate(self, handle):
        self.cancel()
        intent = getattr(handle.operation, "interaction_intent", "")
        wall_modes = {
            "WallStretchStart": "Start",
            "WallStretchEnd": "End",
            "WallMove": "Move",
        }
        if intent in wall_modes:
            self.session.selection.state.set_selected_plan_target("wall", handle.source)
            self.session.wall_edit.start_wall_edit(wall_modes[intent])
            self.session.contextual_rendering.sync_visible_handles()
            return self.session.wall_edit.has_active_wall_edit()
        self.controller = self._new_controller()
        return self.controller.activate(handle)

    def _set_feedback(self, message):
        self.session.status_text.set_integration_feedback_message(message)
        FreeCAD.Console.PrintWarning("BIM Plan Edit: {}\n".format(message))
        self.session.task_panels.refresh_task_panel_status()

    def _clear_feedback(self):
        self.session.status_text.clear_integration_feedback_message()

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Context-projected editing of semantic handles from BIM representations."""

from dataclasses import dataclass

import FreeCAD
from ArchRepresentation import project_to_representation_plane

from bimplan.transactions import PlanEditTransaction


def _handle_value(handle):
    return handle.operation.get_value(handle.source)


@dataclass(frozen=True)
class BIMEditPreview:
    """Non-persistent result of projecting a pointer onto a semantic handle."""

    handle: object
    value: float
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
        if handle is None or handle.interaction != "Linear":
            raise ValueError("Unsupported BIM edit handle")
        validation = handle.operation.validate(handle.source)
        if not validation.allowed:
            raise ValueError(validation.reason)
        if handle.direction.Length <= 1e-9:
            raise ValueError("BIM edit handle has no direction")
        self.handle = handle
        self.start_value = _handle_value(handle)
        return self.preview(handle.point)

    def preview(self, pointer):
        if self.handle is None:
            raise RuntimeError("No BIM edit handle is active")
        projected = project_to_representation_plane(pointer, self.context)
        delta = (projected - self.handle.point).dot(self.handle.direction)
        value = self.start_value + delta
        point = self.handle.point + self.handle.direction * (value - self.start_value)
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
        with PlanEditTransaction(doc, operation.label):
            operation.apply(obj, value)
            if doc is not None:
                doc.recompute()


class PlanContextualEditingAPI:
    """Session facade that edits handles in the currently active context."""

    def __init__(self, session):
        self.session = session
        self.editor = None

    def begin(self, handle):
        self.editor = BIMContextualHandleEditor(
            self.session.representation_context.context,
            refresh=self.session.contextual_rendering.refresh_object,
        )
        try:
            preview = self.editor.begin(handle)
        except Exception as exc:
            self.editor = None
            self._set_feedback(exc)
            return BIMEditResult(False, reason=str(exc))
        self._clear_feedback()
        self.session.contextual_rendering.set_handle_state(handle, "active")
        return preview

    def preview(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        preview = self.editor.preview(pointer)
        self.session.contextual_rendering.preview_handle(preview.handle, preview.point)
        state = "active" if preview.validation.allowed else "invalid"
        self.session.contextual_rendering.set_handle_state(preview.handle, state)
        return preview

    def commit(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        handle = self.editor.handle
        try:
            result = self.editor.commit(pointer)
            self._clear_feedback()
            return result
        except Exception as exc:
            self._set_feedback(exc)
            self.session.contextual_rendering.refresh_object(handle.source)
            return BIMEditResult(False, reason=str(exc))
        finally:
            self.editor = None

    def cancel(self, *, refresh=True):
        handle = self.editor.handle if self.editor is not None else None
        if self.editor is not None:
            self.editor.cancel()
        self.editor = None
        if handle is not None and refresh:
            self.session.contextual_rendering.refresh_object(handle.source)

    def activate(self, handle):
        """Begin a viewer interaction using Draft's point acquisition."""

        import FreeCADGui

        self.cancel()
        started = self.begin(handle)
        if isinstance(started, BIMEditResult) and not started.success:
            return False
        self.session.snap.set_active_draft_command()
        try:
            FreeCADGui.Snapper.getPoint(
                last=handle.point,
                callback=self._finish_point_pick,
                movecallback=self._preview_point_pick,
                title="Edit {}".format(handle.role),
                noTracker=True,
            )
        except Exception:
            self.session.snap.clear_active_draft_command()
            self.cancel()
            raise
        return True

    def _preview_point_pick(self, point=None, snap_info=None):
        del snap_info
        if point is not None and self.editor is not None:
            self.preview(point)

    def _finish_point_pick(self, point=None, obj=None):
        del obj
        try:
            if point is None:
                self.cancel()
                return
            self.commit(point)
        finally:
            self.session.snap.clear_active_draft_command()

    def _set_feedback(self, error):
        message = str(error or "").strip() or "BIM contextual edit failed."
        self.session.status_text.set_integration_feedback_message(message)
        FreeCAD.Console.PrintWarning("BIM Plan Edit: {}\n".format(message))
        self.session.task_panels.refresh_task_panel_status()

    def _clear_feedback(self):
        self.session.status_text.clear_integration_feedback_message()

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic contextual editing in architectural view contexts."""

import FreeCAD
import FreeCADGui
from PySide import QtCore

import ArchRepresentation
import BimContextualRendering
from bimplan.contextual_editing import ContextualEditController
from draftguitools.gui_base import DraftInteractionHost


_active_session = None


class BIMContextualEditingSession:
    """Show and edit semantic handles while leaving document geometry visible."""

    def __init__(self, view=None, context=None, sources=None, orient_to_context=False):
        gui_document = FreeCADGui.ActiveDocument
        self.gui_document = gui_document
        self.document = FreeCAD.ActiveDocument
        self.view = view or getattr(gui_document, "ActiveView", None)
        if self.document is None or self.view is None:
            raise RuntimeError("A document and active 3D view are required")

        self.context = context or ArchRepresentation.RepresentationContext(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
        self._context_sources = None if sources is None else tuple(sources)
        self._restore_camera = None
        if orient_to_context:
            self._orient_view_to_context()
        self.renderer = BimContextualRendering.ContextualInteractionRenderer(self.view)
        self.controller = ContextualEditController(
            self.view,
            self.context,
            self.renderer,
            refresh_callback=self.refresh_source,
            refresh_failure_callback=self.refresh_source,
            feedback_callback=self._show_feedback,
            clear_feedback_callback=self._clear_feedback,
        )
        self._sources = set()
        self._closed = False
        self._selection_refresh_pending = False
        self.host = DraftInteractionHost(view=self.view)

        try:
            FreeCADGui.Selection.addObserver(self)
            self._request_interaction()
        except Exception:
            self.close()
            raise
        self._queue_selection_refresh()

    @property
    def active_edit(self):
        return self.controller.active_edit

    def begin_handle_edit(self, handle):
        """Begin editing a displayed handle; exposed for UI adapters and tests."""

        if (
            self._closed
            or handle is None
            or handle not in self.renderer.edit_handles_for(handle.source)
        ):
            return False
        result = self.controller.begin(handle)
        if getattr(result, "success", True) is False:
            return False
        if handle.operation.value_kind == "Scalar":
            self.host.set_value_input(
                label=handle.operation.label,
                unit="Length",
                value=handle.operation.get_value(handle.source),
                callback=self._commit_value,
            )
        return True

    def preview_pointer(self, pointer):
        if self.active_edit is None:
            return None
        return self.controller.preview(pointer)

    def commit_pointer(self, pointer):
        if self.active_edit is None:
            return None
        result = self.controller.commit(pointer)
        if getattr(result, "success", False):
            self.host.clear_value_input()
        return result

    def cancel_edit(self):
        if self.active_edit is None:
            return False
        self.controller.cancel()
        self.host.clear_value_input()
        self._clear_feedback()
        return True

    def refresh_source(self, _source=None):
        """Refresh capabilities after commit or a failed semantic operation."""

        self._queue_selection_refresh()

    def addSelection(self, *_args):
        self._queue_selection_refresh()

    def removeSelection(self, *_args):
        self._queue_selection_refresh()

    def setSelection(self, *_args):
        self._queue_selection_refresh()

    def clearSelection(self, *_args):
        self._queue_selection_refresh()

    def close(self):
        global _active_session

        if self._closed:
            return False
        self._closed = True
        try:
            FreeCADGui.Selection.removeObserver(self)
        except Exception:
            pass
        try:
            self.controller.cancel(refresh=False)
            self.host.stop_request()
            try:
                self.renderer.close()
            except (RuntimeError, ReferenceError):
                pass
            self._restore_context_view()
            self._sources.clear()
        finally:
            if _active_session is self:
                _active_session = None
        return True

    def _request_interaction(self):
        self.host.request_drag(
            self._pick_handle,
            self.begin_handle_edit,
            self._preview_from_view,
            self._commit_from_view,
            self._cancel_interaction,
        )

    def _pick_handle(self, position):
        if self._closed or self.active_edit is not None:
            return None
        return self.renderer.pick_edit_handle(
            position,
            self.view.getPointOnScreen,
            radius_px=8,
        )

    def _cancel_interaction(self):
        if self.active_edit is not None:
            self.cancel_edit()
        else:
            self.close()

    def _preview_from_view(self, position):
        if self._closed or self.active_edit is None or position is None:
            return
        try:
            self.preview_pointer(BimContextualRendering.ray_from_view(self.view, position))
        except Exception as exc:
            self._show_feedback(exc)

    def _commit_from_view(self, position):
        if self._closed or self.active_edit is None:
            return
        try:
            self.commit_pointer(BimContextualRendering.ray_from_view(self.view, position))
        except Exception as exc:
            self._show_feedback(exc)

    def _commit_value(self, value):
        if self._closed or self.active_edit is None:
            return
        try:
            result = self.controller.commit_value(value)
        except Exception as exc:
            self._show_feedback(exc)
            return
        if result.success:
            self.host.clear_value_input()
            self._clear_feedback()
            return
        self._show_feedback(result.reason)

    def _queue_selection_refresh(self):
        if self._closed or self._selection_refresh_pending:
            return
        self._selection_refresh_pending = True
        QtCore.QTimer.singleShot(0, self._refresh_selection)

    def _refresh_selection(self):
        self._selection_refresh_pending = False
        if self._closed:
            return
        selected = self._context_sources
        if selected is None:
            selected = tuple(FreeCADGui.Selection.getSelection() or ())
            selected = tuple(
                obj for obj in selected if getattr(obj, "Document", None) == self.document
            )
        selected_sources = set(selected)
        if self.active_edit is not None and self.active_edit.source not in selected_sources:
            self.controller.cancel()

        current_sources = set()
        for obj in selected:
            try:
                capabilities = ArchRepresentation.edit_capabilities_for(obj, self.context)
            except ArchRepresentation.RepresentationUnavailable:
                continue
            except Exception as exc:
                FreeCAD.Console.PrintError(
                    "Could not query contextual edits for {}: {}\n".format(
                        getattr(obj, "Label", getattr(obj, "Name", "object")), exc
                    )
                )
                continue
            if not capabilities.edit_handles:
                continue
            self.renderer.set_representation(capabilities)
            current_sources.add(obj)

        for source in self._sources - current_sources:
            self.renderer.remove_representation(source)
        self._sources = current_sources
        self.renderer.set_visible_handle_sources(current_sources)
        self.view.redraw()

    def _orient_view_to_context(self):
        frame = getattr(self.context, "reference_frame", None)
        if frame is None:
            return
        animation_enabled = self.view.isAnimationEnabled()
        self._restore_camera = (
            self.view.getCameraType(),
            self.view.getCamera(),
            animation_enabled,
        )
        self.view.stopAnimating()
        self.view.setAnimationEnabled(False)
        vx = frame.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        vy = frame.Rotation.multVec(FreeCAD.Vector(0, 1, 0))
        vz = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        rotation = FreeCAD.Rotation(vx, vy, vz, "ZXY")
        self.view.setCameraType("Orthographic")
        self.view.setCameraOrientation(rotation.Q)
        self.view.fitAll()

    def _restore_context_view(self):
        if self._restore_camera is None:
            return
        camera_type, camera, animation_enabled = self._restore_camera
        self._restore_camera = None
        self.view.stopAnimating()
        self.view.setCameraType(camera_type)
        self.view.setCamera(camera)
        self.view.setAnimationEnabled(animation_enabled)

    def _defer(self, callback):
        if self._closed:
            return
        QtCore.QTimer.singleShot(0, lambda: None if self._closed else callback())

    @staticmethod
    def _show_feedback(message):
        try:
            FreeCADGui.getMainWindow().statusBar().showMessage(str(message), 5000)
        except Exception:
            FreeCAD.Console.PrintError(str(message) + "\n")

    @staticmethod
    def _clear_feedback():
        try:
            FreeCADGui.getMainWindow().statusBar().clearMessage()
        except Exception:
            pass


def active_session():
    return _active_session


def start_session(view=None, **kwargs):
    """Start the ordinary 3D contextual editing mode."""

    global _active_session

    if _active_session is not None:
        _active_session.close()
    _active_session = BIMContextualEditingSession(view, **kwargs)
    return _active_session

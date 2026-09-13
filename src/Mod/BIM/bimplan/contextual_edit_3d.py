# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic contextual editing over the ordinary FreeCAD 3D model view."""

import FreeCAD
import FreeCADGui
from PySide import QtCore
from pivy import coin

import ArchRepresentation
import BimContextualRendering
from bimplan.contextual_editing import ContextualEditController


_active_session = None


class BIM3DContextualEditingSession:
    """Show and edit semantic handles while leaving document geometry visible."""

    def __init__(self, view=None):
        gui_document = FreeCADGui.ActiveDocument
        self.gui_document = gui_document
        self.document = FreeCAD.ActiveDocument
        self.view = view or getattr(gui_document, "ActiveView", None)
        if self.document is None or self.view is None:
            raise RuntimeError("A document and active 3D view are required")

        self.context = ArchRepresentation.RepresentationContext(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
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
        self._preview_pending = False
        self._pending_mouse_position = None
        self._callbacks = []

        try:
            FreeCADGui.Selection.addObserver(self)
            self._register_event_callbacks()
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
        return True

    def preview_pointer(self, pointer):
        if self.active_edit is None:
            return None
        return self.controller.preview(pointer)

    def commit_pointer(self, pointer):
        if self.active_edit is None:
            return None
        return self.controller.commit(pointer)

    def cancel_edit(self):
        if self.active_edit is None:
            return False
        self.controller.cancel()
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
            for event_type, callback in self._callbacks:
                try:
                    self.view.removeEventCallbackPivy(event_type, callback)
                except (RuntimeError, ReferenceError):
                    pass
            self._callbacks.clear()
            try:
                self.renderer.close()
            except (RuntimeError, ReferenceError):
                pass
            self._sources.clear()
        finally:
            if _active_session is self:
                _active_session = None
        return True

    def _register_event_callbacks(self):
        callback_types = (
            (coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_button),
            (coin.SoLocation2Event.getClassTypeId(), self._on_mouse_move),
            (coin.SoKeyboardEvent.getClassTypeId(), self._on_key),
        )
        for event_type, callback in callback_types:
            registered = self.view.addEventCallbackPivy(event_type, callback)
            self._callbacks.append((event_type, registered))

    def _on_mouse_button(self, event_callback):
        if self._closed:
            return
        event = event_callback.getEvent()
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        position = event.getPosition().getValue()
        position = int(position[0]), int(position[1])

        if self.active_edit is not None:
            if event.getState() == coin.SoMouseButtonEvent.UP:
                event_callback.setHandled()
                self._defer(lambda p=position: self._commit_from_view(p))
            else:
                event_callback.setHandled()
            return

        if event.getState() != coin.SoMouseButtonEvent.DOWN:
            return
        handle = self.renderer.pick_edit_handle(
            position,
            self.view.getPointOnScreen,
            radius_px=8,
        )
        if handle is None:
            return
        event_callback.setHandled()
        self._defer(lambda target=handle: self.begin_handle_edit(target))

    def _on_mouse_move(self, event_callback):
        if self._closed or self.active_edit is None:
            return
        event_callback.setHandled()
        position = event_callback.getEvent().getPosition().getValue()
        self._pending_mouse_position = int(position[0]), int(position[1])
        if self._preview_pending:
            return
        self._preview_pending = True
        self._defer(self._preview_from_latest_position)

    def _on_key(self, event_callback):
        if self._closed:
            return
        event = event_callback.getEvent()
        if event.getState() != coin.SoKeyboardEvent.DOWN:
            return
        if event.getKey() != coin.SoKeyboardEvent.ESCAPE:
            return
        event_callback.setHandled()
        if self.active_edit is not None:
            self._defer(self.cancel_edit)
        else:
            self._defer(self.close)

    def _preview_from_latest_position(self):
        self._preview_pending = False
        position = self._pending_mouse_position
        self._pending_mouse_position = None
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

    def _queue_selection_refresh(self):
        if self._closed or self._selection_refresh_pending:
            return
        self._selection_refresh_pending = True
        QtCore.QTimer.singleShot(0, self._refresh_selection)

    def _refresh_selection(self):
        self._selection_refresh_pending = False
        if self._closed:
            return
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


def start_session(view=None):
    """Start the ordinary 3D contextual editing mode."""

    global _active_session

    if _active_session is not None:
        _active_session.close()
    _active_session = BIM3DContextualEditingSession(view)
    return _active_session

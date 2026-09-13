# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic contextual editing in architectural view contexts."""

import FreeCAD
import FreeCADGui
from PySide import QtCore

import ArchRepresentation
import ArchOpeningConstruction
import BimContextualRendering
from bimplan.contextual_action_ui import ContextualActionPanel
from bimplan.contextual_actions import (
    ContextualProviderContext,
    HostedOpeningCreationProvider,
    SemanticEditProvider,
    WallCreationProvider,
)
from bimplan.contextual_editing import ContextualEditController
from draftguitools.gui_base import DraftInteractionHost


_active_session = None


class BIMContextualEditingSession:
    """Show and edit semantic handles while leaving document geometry visible."""

    def __init__(
        self,
        view=None,
        context=None,
        sources=None,
        orient_to_context=False,
        providers=None,
    ):
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
        self._capabilities = ()
        self.contextual_actions = ()
        self.inspector_sections = ()
        self._pending_action_handle = None
        self.providers = tuple(
            providers or (
                SemanticEditProvider(), HostedOpeningCreationProvider(), WallCreationProvider()
            )
        )
        self._provider_context = None
        self._creation_preview_source = object()
        self._wall_start = None
        self._wall_direction = None
        self.action_panel = ContextualActionPanel()
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

    def begin_hosted_opening_creation(self, kind, wall):
        """Acquire one point and construct an opening using semantic BIM policy."""

        if self._closed or wall is None:
            return False
        spec = ArchOpeningConstruction.HostedOpeningSpec(kind=kind)
        self.host.request_point(
            lambda point, _obj=None: self._finish_hosted_opening_creation(
                wall, point, spec
            ),
            title="{} location".format(spec.validated().kind),
            move_callback=lambda point, _info=None: self._preview_hosted_opening(
                wall, point, spec
            ),
        )
        return True

    def begin_wall_creation(self):
        self._wall_start = None
        self.host.request_point(self._accept_wall_point, title="Wall start")
        return True

    def _accept_wall_point(self, point, _obj=None):
        if point is None:
            self._wall_start = None
            self._wall_direction = None
            self.renderer.clear_preview(self._creation_preview_source)
            self.host.clear_value_input()
            self._request_interaction()
            return None
        if self._wall_start is None:
            self._wall_start = FreeCAD.Vector(point)
            self.host.request_point(
                self._accept_wall_point,
                move_callback=self._preview_wall,
                title="Wall end",
            )
            return None
        import ArchWallConstruction
        walls = ArchWallConstruction.construct_wall_run(
            self.document, (self._wall_start, point),
            ArchWallConstruction.WallConstructionSpec(200, 2500),
            transaction_name="Create Wall", auto_join=False,
        )
        self._wall_start = None
        self.renderer.clear_preview(self._creation_preview_source)
        self._request_interaction()
        return walls[0]

    def _preview_wall(self, point, _info=None):
        if self._wall_start is None or point is None:
            return
        import Part
        vector = FreeCAD.Vector(point).sub(self._wall_start)
        if vector.Length < 10:
            self.renderer.clear_preview(self._creation_preview_source)
            return
        shape = Part.makeBox(vector.Length, 200, 2500)
        shape.Placement = FreeCAD.Placement(
            self._wall_start,
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), vector),
        )
        self._show_creation_shape(shape, "WallPreview")
        self._wall_direction = FreeCAD.Vector(vector).normalize()
        self.host.set_value_input(
            label="Wall length",
            unit="Length",
            value=vector.Length,
            callback=self._commit_wall_length,
        )

    def _commit_wall_length(self, value):
        if self._wall_start is None or self._wall_direction is None:
            return
        end = self._wall_start.add(
            FreeCAD.Vector(self._wall_direction).multiply(float(value))
        )
        self._accept_wall_point(end)

    def _preview_hosted_opening(self, wall, point, spec):
        if point is None:
            return
        import Part
        value = spec.validated()
        shape = Part.makeBox(value.width, 200, value.height)
        shape.Placement = ArchOpeningConstruction.hosted_opening_placement(
            wall, point, value
        )
        self._show_creation_shape(shape, "OpeningPreview")

    def _show_creation_shape(self, shape, role):
        representation = ArchRepresentation.BIMRepresentation(
            source=self._creation_preview_source, context=self.context
        )
        for index, face in enumerate(shape.Faces, start=1):
            representation.add_geometry(
                "cut_geometry", face, role, "Face{}".format(index)
            )
        self.renderer.set_preview_representation(
            self._creation_preview_source, representation
        )

    def _finish_hosted_opening_creation(self, wall, point, spec):
        if self._closed:
            return None
        try:
            opening = ArchOpeningConstruction.construct_hosted_opening(
                self.document,
                wall,
                point,
                spec,
                transaction_name="Create {}".format(spec.validated().kind),
            )
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(opening)
            return opening
        except Exception as exc:
            self._show_feedback(exc)
            return None
        finally:
            self.renderer.clear_preview(self._creation_preview_source)
            if not self._closed:
                self._request_interaction()

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
            self.host.clear_value_input()
            self.renderer.clear_preview(self._creation_preview_source)
            self.action_panel.close()
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
        if self._pending_action_handle is not None:
            handle = self._pending_action_handle
            self._pending_action_handle = None
            return handle
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
        current_capabilities = []
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
            current_capabilities.append(capabilities)

        for source in self._sources - current_sources:
            self.renderer.remove_representation(source)
        self._sources = current_sources
        self._capabilities = tuple(current_capabilities)
        self._pending_action_handle = None
        self.renderer.set_visible_handle_sources(current_sources)
        self._refresh_contextual_actions(tuple(selected))
        self.view.redraw()

    def _refresh_contextual_actions(self, selected):
        context = ContextualProviderContext(
            representation_context=self.context,
            selected_sources=tuple(selected),
            view=self.view,
            capabilities=self._capabilities,
        )
        self._provider_context = context
        actions = []
        sections = []
        for provider in self.providers:
            actions.extend(provider.get_actions(context) or ())
            sections.extend(provider.get_inspector_sections(context) or ())
        self.contextual_actions = tuple(actions)
        self.inspector_sections = tuple(sections)
        self.action_panel.update(
            self.contextual_actions,
            self.inspector_sections,
            self.activate_action,
        )

    def activate_action(self, action):
        """Activate a provider action without embedding object-specific policy."""

        if self._closed or not getattr(action, "enabled", False):
            return False
        handle = next(
            (
                candidate
                for capability in self._capabilities
                for candidate in tuple(capability.edit_handles or ())
                if candidate.source is action.source
                and candidate.operation.key == action.handle_key
                and candidate.subelement == action.handle_subelement
            ),
            None,
        )
        if handle is None:
            provider = next(
                (
                    item
                    for item in self.providers
                    if item.get_provider_id() == action.provider_id
                ),
                None,
            )
            if provider is None or self._provider_context is None:
                return False
            return bool(
                provider.execute_action(
                    action.key, self._provider_context, commands=self
                )
            )
        if handle.operation.value_kind == "Scalar":
            return self.begin_handle_edit(handle)
        if handle.interaction == "Immediate":
            return self.controller.activate(handle)
        self._pending_action_handle = handle
        self._show_feedback("Click and drag to {}".format(action.label.lower()))
        return True

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

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Semantic contextual editing in architectural view contexts."""

import FreeCAD
import FreeCADGui
from PySide import QtCore

import ArchRepresentation
import BimContextualRendering
from .ui import ContextualActionPanel
from .actions import (
    ContextualProviderContext,
)
from .editing import ContextualEditController
from .interaction import ContextualInteractionHost


_active_session = None


class ContextualSession:
    """Show and edit semantic handles while leaving document geometry visible."""

    def __init__(
        self,
        view=None,
        request=None,
        sources=None,
        orient_to_request=False,
        providers=None,
    ):
        gui_document = FreeCADGui.ActiveDocument
        self.gui_document = gui_document
        self.document = FreeCAD.ActiveDocument
        self.view = view or getattr(gui_document, "ActiveView", None)
        if self.document is None or self.view is None:
            raise RuntimeError("A document and active 3D view are required")

        self.request = request or ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
        self._context_sources = None if sources is None else tuple(sources)
        self._restore_camera = None
        if orient_to_request:
            self._orient_view_to_request()
        self._projected_elevation = (
            self.request.purpose == ArchRepresentation.RepresentationPurpose.ELEVATION
        )
        if self._projected_elevation:
            self.renderer = BimContextualRendering.ContextualRepresentationRenderer(
                self.view,
                replace_source=True,
                render_representation=True,
            )
        else:
            self.renderer = BimContextualRendering.ContextualInteractionRenderer(self.view)
        self._hidden_context_marker = None
        marker = getattr(self.request, "source", None)
        if self._should_hide_own_context_marker(marker):
            try:
                self.view.setViewVisibility(self.renderer.layer, marker, "Hidden")
                self._hidden_context_marker = marker
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        self.controller = ContextualEditController(
            self.view,
            self.request,
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
        self._last_projection_error = None
        self.contextual_actions = ()
        self.contextual_tools = ()
        self.inspector_sections = ()
        self._pending_action_handle = None
        if providers is None:
            from .actions import SemanticEditProvider

            providers = (SemanticEditProvider(),)
        self.providers = tuple(providers)
        self._provider_context = None
        self.action_panel = ContextualActionPanel(close_callback=self.close)
        self.host = ContextualInteractionHost(self.request, view=self.view)

        try:
            FreeCADGui.Selection.addObserver(self)
            self._request_interaction()
        except Exception:
            self.close()
            raise
        self._queue_selection_refresh()

    def _should_hide_own_context_marker(self, marker):
        """Keep a planar view's defining plane out of its own rendered content.

        The marker remains a normal document object in model views.  Hiding it
        through the renderer's view-context layer avoids changing persistent
        visibility while preventing its large face from obscuring or winning
        picks against the section/elevation content it defines.
        """

        if marker is None:
            return False
        if self.request.purpose not in (
            ArchRepresentation.RepresentationPurpose.SECTION,
            ArchRepresentation.RepresentationPurpose.ELEVATION,
        ):
            return False
        return getattr(getattr(marker, "Proxy", None), "Type", "") == "SectionPlane"

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

    def request_point(self, callback, **kwargs):
        """Expose request-aware point acquisition to an active provider workflow."""

        if self._closed:
            return False
        request_result = self.host.request_point(callback, **kwargs)
        return True if request_result is None else request_result

    def set_value_input(self, **kwargs):
        if self._closed:
            return False
        return self.host.set_value_input(**kwargs)

    def clear_value_input(self):
        return self.host.clear_value_input()

    def present_preview(self, representation):
        if self._closed:
            return False
        return self.renderer.set_preview_state(
            ArchRepresentation.preview_state_from_representation(representation)
        )

    def clear_preview(self, source=None):
        return self.renderer.clear_preview(source)

    def select_source(self, source):
        if self._closed or source is None:
            return False
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(source)
        return True

    def resume_interaction(self):
        if self._closed:
            return False
        self._request_interaction()
        return True

    def show_feedback(self, message):
        self._show_feedback(message)

    def refresh_source(self, _source=None, _impact=None):
        """Refresh capabilities after commit or a failed semantic operation."""

        self._queue_selection_refresh()

    def refresh_request_from_source(self, source=None):
        """Refresh a saved planar request after its defining object changes.

        Section-plane presentation settings are document properties, while a
        contextual session owns an immutable request snapshot.  Rebuilding the
        request here keeps an active elevation in sync without forcing the user
        to leave and re-enter edit mode.
        """

        if self._closed:
            return False
        source = source or getattr(self.request, "source", None)
        provider = getattr(getattr(source, "Proxy", None), "getRepresentationRequest", None)
        if not callable(provider):
            return False
        request = provider(source)
        if request is None or request.purpose != self.request.purpose:
            return False
        if self.active_edit is not None:
            self.controller.cancel(refresh=False)
        self.request = request
        self.controller.request = request
        if self.controller.editor is not None:
            self.controller.editor.request = request
        self.host.request = request
        self._queue_selection_refresh()
        return True

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
            self.action_panel.close()
            if self._hidden_context_marker is not None:
                try:
                    self.view.setViewVisibility(
                        self.renderer.layer, self._hidden_context_marker, "Inherit"
                    )
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                self._hidden_context_marker = None
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
        FreeCADGui.invokeLater(self._refresh_selection)

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
        elevation_representations = {}
        projection_failed = False
        if self._projected_elevation:
            import ArchSectionProjection

            try:
                elevation_representations = ArchSectionProjection.project_elevation_scope(
                    selected, self.request
                )
            except (ArchRepresentation.RepresentationUnavailable, RuntimeError):
                projection_failed = True
                elevation_representations = {
                    obj: self.renderer._representations.get(obj)
                    for obj in selected
                    if self.renderer._representations.get(obj) is not None
                }
                self._last_projection_error = (
                    "Elevation projection refresh failed; showing the last valid view"
                )
                self._show_feedback(self._last_projection_error)
            else:
                self._last_projection_error = None
        for obj in selected:
            try:
                capabilities = ArchRepresentation.edit_capabilities_for(obj, self.request)
            except ArchRepresentation.RepresentationUnavailable:
                if not self._projected_elevation:
                    continue
                capabilities = ArchRepresentation.BIMEditCapabilities(
                    source=obj, request=self.request
                )
            except Exception as exc:
                FreeCAD.Console.PrintError(
                    "Could not query contextual edits for {}: {}\n".format(
                        getattr(obj, "Label", getattr(obj, "Name", "object")), exc
                    )
                )
                if not self._projected_elevation:
                    continue
                capabilities = ArchRepresentation.BIMEditCapabilities(
                    source=obj, request=self.request
                )
            display = capabilities
            if self._projected_elevation:
                display = elevation_representations.get(obj)
                if display is None:
                    display = ArchRepresentation.ViewportRepresentation(
                        source=obj, request=self.request
                    )
                if not projection_failed:
                    for handle in capabilities.edit_handles:
                        display.add_edit_handle(handle)
                elif display is not None:
                    display.edit_handles = list(capabilities.edit_handles)
            if (
                not self._projected_elevation
                and not capabilities.edit_handles
                and not getattr(display, "projected_geometry", ())
            ):
                continue
            self.renderer.set_representation(display)
            current_sources.add(obj)
            if capabilities.edit_handles:
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
            representation_request=self.request,
            selected_sources=tuple(selected),
            view=self.view,
            capabilities=self._capabilities,
        )
        self._provider_context = context
        actions = []
        tools = []
        sections = []
        for provider in self.providers:
            actions.extend(provider.get_actions(context) or ())
            tools.extend(provider.get_tools(context) or ())
            sections.extend(provider.get_inspector_sections(context) or ())
        self.contextual_actions = tuple(actions)
        self.contextual_tools = tuple(tools)
        self.inspector_sections = tuple(sections)
        self.action_panel.update(
            self.contextual_actions,
            self.contextual_tools,
            self.inspector_sections,
            self.activate_action,
            self.activate_tool,
        )

    def activate_tool(self, tool):
        if self._closed or tool is None or not tool.enabled:
            return False
        for provider in self.providers:
            if provider.get_provider_id() != tool.provider_id:
                continue
            return bool(
                provider.execute_tool(
                    tool.key, self._provider_context, commands=self
                )
            )
        return False

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

    def _orient_view_to_request(self):
        frame = getattr(self.request, "reference_frame", None)
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
        FreeCADGui.invokeLater(lambda: None if self._closed else callback())

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
    _active_session = ContextualSession(view, **kwargs)
    return _active_session

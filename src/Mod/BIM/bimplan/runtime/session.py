# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local Plan Edit session lifecycle."""

import FreeCAD
import FreeCADGui
import WorkingPlane
from PySide import QtGui

from bimplan.ui.session_panel import PlanEditSessionPanel


_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
_LOCKED_VIEW_ACTIONS = (
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
    """Return the active Plan Edit session, if one exists."""

    return _active_session


def start_session():
    """Start one Plan Edit session for the current document and view."""

    global _active_session
    if _active_session is not None:
        _active_session.show_task_panel()
        return _active_session

    session = PlanEditSession()
    if session.enter():
        _active_session = session
        return session
    return None


class PlanEditSession:
    """Own reversible Plan Edit state for one document view."""

    def __init__(self, document=None, gui_document=None):
        self.doc = document if document is not None else FreeCAD.ActiveDocument
        self.gui_doc = gui_document if gui_document is not None else FreeCADGui.ActiveDocument
        self.view = None
        self.viewer = None
        self.storeys = []
        self.active_storey = None
        self.context_layer = None
        self.working_plane = None
        self.task_panel = None
        self._saved_camera = None
        self._saved_camera_type = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self._finishing = False
        self._finished = False
        self._entered = False
        self._task_panel_open = False
        self._background_override_applied = False
        self._navicube_override_applied = False

    def enter(self, show_panel=True):
        """Capture the current view, apply the plan profile and show controls."""

        if self._finished:
            raise RuntimeError("a finished Plan Edit session cannot be entered again")
        if self.doc is None or self.gui_doc is None:
            FreeCAD.Console.PrintError("Plan Edit requires an active document and 3D view.\n")
            return False

        try:
            self.view = self.gui_doc.ActiveView
            if self.view is None or not hasattr(self.view, "getViewer"):
                FreeCAD.Console.PrintError("Plan Edit requires an active 3D view.\n")
                return False
            self.viewer = self.view.getViewer()
            if self.viewer is None:
                return False

            self._capture_state()
            self.storeys = self.collect_storeys()
            self.active_storey = self.find_initial_storey()
            self.context_layer = self.view.pushViewContextLayer()
            self._apply_storey_visibility()
            self._apply_plan_view()
            self._apply_navigation_profile()
            self._entered = True

            if show_panel:
                self.show_task_panel()
            FreeCAD.Console.PrintMessage("Entered BIM Plan Edit mode.\n")
            return True
        except Exception as exc:
            FreeCAD.Console.PrintError("Could not enter Plan Edit: {}\n".format(exc))
            self.finish(close_dialog=False)
            return False

    def collect_storeys(self):
        """Return semantic Building Storeys in vertical order.

        Legacy Arch Floors carry the same IFC type, so they use the same
        context path without a separate Draft type check.
        """
        storeys = []
        for obj in self.doc.Objects:
            if getattr(obj, "IfcType", "") == "Building Storey":
                storeys.append(obj)
        storeys.sort(key=self.get_storey_elevation)
        return storeys

    def find_initial_storey(self):
        """Use a selected storey, otherwise the lowest storey in the document."""

        storeys_by_name = {storey.Name: storey for storey in self.storeys}
        for obj in FreeCADGui.Selection.getSelection():
            storey = storeys_by_name.get(getattr(obj, "Name", None))
            if storey is not None:
                return storey
        return self.storeys[0] if self.storeys else None

    @staticmethod
    def get_storey_elevation(storey):
        placement = getattr(storey, "Placement", None)
        return placement.Base.z if placement else 0.0

    def get_storey_label(self, storey):
        if storey is None:
            return FreeCAD.Qt.translate("BIM_PlanEdit", "All model geometry")
        elevation = FreeCAD.Units.Quantity(
            self.get_storey_elevation(storey), FreeCAD.Units.Length
        ).UserString
        return "{} [{}]".format(storey.Label, elevation)

    def set_active_storey(self, storey):
        """Change the visibility context without touching document visibility."""

        if storey is not None and storey not in self.storeys:
            raise ValueError("storey does not belong to this Plan Edit session")
        self.active_storey = storey
        self._apply_storey_visibility()
        self._set_working_plane()
        if self.view and hasattr(self.view, "fitAll"):
            self.view.fitAll()

    def _storey_objects(self, storey):
        """Return the storey and all nested BIM contents without duplicates."""

        names = set()
        pending = [storey]
        while pending:
            obj = pending.pop()
            name = getattr(obj, "Name", None) if obj is not None else None
            if not name or name in names:
                continue
            names.add(name)
            pending.extend(getattr(obj, "Group", []) or [])
            pending.extend(getattr(obj, "Additions", []) or [])
        return names

    def _apply_storey_visibility(self):
        if self.context_layer is None or self.view is None:
            return
        visible_objects = self._storey_objects(self.active_storey) if self.active_storey else None
        for obj in self.doc.Objects:
            try:
                state = "Inherit"
                if visible_objects is not None:
                    if obj.Name in visible_objects:
                        view_object = getattr(obj, "ViewObject", None)
                        state = "Visible" if view_object and view_object.Visibility else "Inherit"
                    else:
                        state = "Hidden"
                self.view.setViewVisibility(self.context_layer, obj, state)
            except (AttributeError, ReferenceError, RuntimeError):
                continue

    def _capture_state(self):
        if hasattr(self.view, "getCamera"):
            self._saved_camera = self.view.getCamera()
        if hasattr(self.view, "getCameraType"):
            self._saved_camera_type = self.view.getCameraType()
        self.working_plane = WorkingPlane.get_working_plane(update=False)
        if hasattr(self.working_plane, "save"):
            self.working_plane.save()

        self._saved_navigation_style = self.viewer.getNavigationStyle()
        for name, getter in (
            ("rotation_enabled", "isRotationEnabled"),
            ("orientation_locked", "isOrientationLocked"),
        ):
            if hasattr(self._saved_navigation_style, getter):
                self._saved_navigation_state[name] = bool(
                    getattr(self._saved_navigation_style, getter)()
                )
        for name, getter in (("corner_cross_visible", "isCornerCrossVisible"),):
            if hasattr(self.view, getter):
                self._saved_navigation_state[name] = bool(getattr(self.view, getter)())

        main_window = FreeCADGui.getMainWindow()
        for command_name in _LOCKED_VIEW_ACTIONS:
            try:
                action = main_window.findChild(QtGui.QAction, command_name)
                if action is not None:
                    self._saved_view_action_state[command_name] = action.isEnabled()
            except Exception:
                continue

    def _apply_plan_view(self):
        if self.view is None:
            return
        self._set_working_plane()
        self.view.setCameraType("Orthographic")
        self.view.viewTop()
        self.view.waitForCameraAnimation()
        self.viewer.setBackgroundAppearanceOverride(
            "NONE", _PLAN_PAPER_RGB, _PLAN_PAPER_RGB, _PLAN_PAPER_RGB
        )
        self._background_override_applied = True
        self.viewer.setNaviCubeEnabledOverride(False)
        self._navicube_override_applied = True
        if hasattr(self.view, "fitAll"):
            self.view.fitAll()

    def _set_working_plane(self):
        if self.working_plane is None:
            return
        offset = self.get_storey_elevation(self.active_storey) if self.active_storey else 0.0
        self.working_plane.set_to_top(offset=offset)
        if hasattr(self.working_plane, "_update_all"):
            self.working_plane._update_all(_hist_add=False)

    def _apply_navigation_profile(self):
        style = self._saved_navigation_style
        if style is not None:
            style.setRotationEnabled(False)
            style.setOrientationLocked(True)
        try:
            self.view.setCornerCrossVisible(False)
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        main_window = FreeCADGui.getMainWindow()
        for command_name in _LOCKED_VIEW_ACTIONS:
            try:
                action = main_window.findChild(QtGui.QAction, command_name)
                if action is not None:
                    action.setEnabled(False)
            except Exception:
                continue

    def _restore_navigation_profile(self):
        style = self._saved_navigation_style
        if style is not None:
            try:
                if "rotation_enabled" in self._saved_navigation_state:
                    style.setRotationEnabled(self._saved_navigation_state["rotation_enabled"])
                if "orientation_locked" in self._saved_navigation_state:
                    style.setOrientationLocked(self._saved_navigation_state["orientation_locked"])
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        if "corner_cross_visible" in self._saved_navigation_state:
            try:
                self.view.setCornerCrossVisible(
                    self._saved_navigation_state["corner_cross_visible"]
                )
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        main_window = FreeCADGui.getMainWindow()
        for command_name, enabled in self._saved_view_action_state.items():
            try:
                action = main_window.findChild(QtGui.QAction, command_name)
                if action is not None:
                    action.setEnabled(bool(enabled))
            except Exception:
                continue

    def show_task_panel(self):
        if self.task_panel is None:
            self.task_panel = PlanEditSessionPanel(self)
        if self._task_panel_open:
            self.task_panel.form.show()
            self.task_panel.form.raise_()
            return
        FreeCADGui.Control.showDialog(self.task_panel, self.gui_doc)
        self._task_panel_open = True

    def finish(self, close_dialog=True):
        """Remove transient overrides and restore the original view exactly once."""

        global _active_session
        if self._finishing or self._finished:
            return True
        self._finishing = True
        try:
            if self.context_layer is not None and self.view is not None:
                try:
                    self.view.removeViewContextLayer(self.context_layer)
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                self.context_layer = None
            if self.viewer is not None and self._background_override_applied:
                try:
                    self.viewer.clearBackgroundAppearanceOverride()
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                self._background_override_applied = False
            if self.viewer is not None and self._navicube_override_applied:
                try:
                    self.viewer.clearNaviCubeEnabledOverride()
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                self._navicube_override_applied = False
            if self.view is not None:
                try:
                    if self._saved_camera_type is not None:
                        self.view.setCameraType(self._saved_camera_type)
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                try:
                    if self._saved_camera is not None:
                        self.view.setCamera(self._saved_camera)
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
            if self.working_plane is not None:
                try:
                    self.working_plane.restore()
                    self.working_plane._update_all(_hist_add=False)
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
            self._restore_navigation_profile()
            if close_dialog and self._task_panel_open:
                try:
                    FreeCADGui.Control.closeDialog()
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
                self._task_panel_open = False
        finally:
            self._entered = False
            self._finishing = False
            self._finished = True
            if _active_session is self:
                _active_session = None
        return True

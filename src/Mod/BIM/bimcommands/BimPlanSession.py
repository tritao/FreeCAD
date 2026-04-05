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
from draftguitools import gui_base

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
_DEFAULT_DOCK_AREA = 2
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

_active_session = None


def _view_param_group():
    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")


def _unsigned_to_rgb(color):
    return (
        ((color >> 24) & 0xFF) / 255.0,
        ((color >> 16) & 0xFF) / 255.0,
        ((color >> 8) & 0xFF) / 255.0,
    )


def _apply_viewer_background(viewer, state):
    if not viewer or not state:
        return

    gradient_mode = "NONE"
    if state.get("radial_gradient", False):
        gradient_mode = "RADIAL"
    elif state.get("gradient", False):
        gradient_mode = "LINEAR"

    viewer.setGradientBackground(gradient_mode)
    viewer.setBackgroundColor(*state["background"])

    if state.get("use_mid", False):
        viewer.setGradientBackgroundColor(
            state["background2"],
            state["background3"],
            state["background4"],
        )
    else:
        viewer.setGradientBackgroundColor(state["background2"], state["background3"])


def _make_plan_background_state(state):
    if not state:
        return None

    return {
        "gradient": False,
        "radial_gradient": False,
        "use_mid": False,
        "background": _PLAN_PAPER_RGB,
        "background2": _PLAN_PAPER_RGB,
        "background3": _PLAN_PAPER_RGB,
        "background4": _PLAN_PAPER_RGB,
    }


def _copy_plane(plane):
    import WorkingPlane

    if plane is None:
        return None

    def _copy_vec(vec):
        return FreeCAD.Vector(vec.x, vec.y, vec.z)

    return WorkingPlane.PlaneBase(
        _copy_vec(plane.u),
        _copy_vec(plane.v),
        _copy_vec(plane.axis),
        _copy_vec(plane.position),
    )


def get_active_session():
    return _active_session


def start_session():
    global _active_session

    if _active_session:
        return _active_session

    session = PlanEditSession()
    if session.enter():
        _active_session = session
        return session
    return None


class _PlanEditWallHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for wall creation inside Plan Edit.

    This host overrides the generic interaction policy hooks from
    `DraftInteractionHost` so plan wall creation can:
    - avoid task widgets
    - keep ortho on by default
    - use `Shift` as a temporary free-angle override
    - continue chained wall runs from the last endpoint
    """

    def __init__(self, session, command=None):
        super().__init__(command)
        self.session = session

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started("Wall", command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished("Wall", command or self.command)

    def get_working_plane(self):
        return self.session.get_interaction_plane()

    def get_interaction_plane(self):
        return self.session.get_interaction_plane()

    def request_point(
        self,
        callback,
        move_callback=None,
        last=None,
        title=None,
        mode=None,
        extra_widget=None,
        hints=None,
        modifier_resolver=None,
    ):
        del extra_widget
        super().request_point(
            callback=callback,
            move_callback=move_callback,
            last=last,
            title=title,
            mode=mode,
            extra_widget=None,
            hints=hints,
            modifier_resolver=modifier_resolver,
        )

    def clear_ui_state(self):
        return

    def reset_edit(self):
        return

    def show_continue(self):
        return

    def continue_mode_enabled(self):
        return False

    def continue_wall_chain_enabled(self):
        return True

    def supports_extra_widget(self):
        return False

    def resolve_point_request_modifiers(self, ctrl, shift, alt):
        del alt
        return ctrl, False

    def default_ortho_enabled(self):
        return True

    def free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def on_created_object(self, obj):
        self.session._register_plan_object(obj)


class _PlanEditCommandHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for modifiers used inside Plan Edit."""

    def __init__(self, session, tool_name, command=None):
        super().__init__(command)
        self.session = session
        self.tool_name = tool_name

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started(self.tool_name, command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished(self.tool_name, command or self.command)

    def continue_mode_enabled(self):
        return False


class PlanEditSession:
    """Owns the viewer state and control dock for Plan Edit mode."""

    def __init__(self):
        from PySide import QtCore, QtGui

        self.doc = FreeCAD.ActiveDocument
        self.gui_doc = FreeCADGui.ActiveDocument
        self.view = None
        self.viewer = None
        self.task_panel = None
        self.current_tool = "Select"
        self.storeys = []
        self.active_storey = None
        self.selected_wall = None
        self._grip_trackers = []
        self._selection_observer_added = False
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._preview_line_tracker = None
        self._preview_rect_tracker = None
        self._preview_grip_trackers = []
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._edit_wall_visibility = None
        self._dragging_grip = False
        self._ignore_selection_changes = False
        self._mouse_moved_cb = None
        self._mouse_pressed_cb = None
        self._key_pressed_cb = None
        self._render_manager = None
        self._saved_camera = None
        self._saved_camera_type = None
        self._saved_background = None
        self._saved_object_view_state = {}
        self._working_plane = None
        self._interaction_plane = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._finishing = False
        self._tearing_down = False
        app = QtGui.QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.begin_teardown)

    def enter(self):
        if not self.doc or not self.gui_doc:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
            )
            return False

        self.view = self.gui_doc.ActiveView
        if not self.view or not hasattr(self.view, "getViewer"):
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False

        self.viewer = self.view.getViewer()
        self._capture_state()

        self.storeys = self.collect_storeys()
        self.active_storey = self.find_initial_storey()
        self._capture_object_view_state()
        self.apply_plan_view()
        self._apply_plan_snap_profile()
        self._apply_storey_visibility()
        self._attach_selection_observer()
        self._register_edit_callbacks()
        self._refresh_selected_wall()

        panel = PlanEditDockWidget(self)
        self.attach_task_panel(panel)
        panel.refresh()
        panel.show()
        panel.raise_()
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Entered BIM Plan Edit mode.\n"))
        return True

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
            return True
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
            return True
        if self._has_active_wall_edit():
            self._cancel_wall_edit()
            return True
        return self.shutdown(close_dialog=close_dialog)

    def begin_teardown(self):
        if self._tearing_down:
            return
        self._tearing_down = True
        self._cancel_embedded_tool()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        self._clear_wall_grips()
        self._detach_selection_observer()
        self._unregister_edit_callbacks()

    def _document_is_alive(self):
        doc = self.doc
        if not doc:
            return False
        try:
            _ = doc.Name
            return True
        except Exception:
            self.doc = None
            return False

    def _discard_runtime_references(self):
        self.doc = None
        self.gui_doc = None
        self.view = None
        self.viewer = None
        self.selected_wall = None
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._preview_rect_tracker = None
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._edit_wall_visibility = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None

    def shutdown(self, close_dialog=True, teardown=False):
        global _active_session

        if self._finishing:
            return True
        self._finishing = True

        try:
            if not self._document_is_alive():
                self.begin_teardown()
            teardown = teardown or self._tearing_down
            panel = self.task_panel
            self.task_panel = None
            self._cancel_embedded_tool()
            self._cancel_rect_wall_tool(refresh=False)
            self._cancel_wall_edit(restore=not teardown, refresh=False)
            self._cancel_pending_edit()
            self._clear_wall_grips()
            self._detach_selection_observer()
            self._unregister_edit_callbacks()
            if panel:
                panel.mark_closed()
                if close_dialog and not teardown:
                    panel.close()
                else:
                    panel.detach()
            if teardown:
                self._discard_runtime_references()
            else:
                self.restore_state()
                if self.doc:
                    try:
                        self.doc.recompute()
                    except ReferenceError:
                        self.doc = None
                    except RuntimeError:
                        self.doc = None
                FreeCAD.Console.PrintMessage(
                    translate("BIM_PlanEdit", "Exited BIM Plan Edit mode.\n")
                )
        finally:
            _active_session = None
            self._finishing = False
        return True

    def collect_storeys(self):
        import Draft

        storeys = []
        for obj in self.doc.Objects:
            obj_type = Draft.getType(obj)
            if obj_type == "Floor":
                storeys.append(obj)
            elif obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
                storeys.append(obj)

        storeys.sort(key=lambda obj: self.get_storey_elevation(obj))
        return storeys

    def find_initial_storey(self):
        import Draft

        for obj in FreeCADGui.Selection.getSelection():
            obj_type = Draft.getType(obj)
            if obj_type == "Floor":
                return obj
            if obj_type == "BuildingPart" and getattr(obj, "IfcType", "") == "Building Storey":
                return obj
        if self.storeys:
            return self.storeys[0]
        return None

    def get_storey_elevation(self, obj):
        if hasattr(obj, "Placement"):
            return obj.Placement.Base.z
        return 0.0

    def get_storey_label(self, obj):
        if not obj:
            return translate("BIM_PlanEdit", "Global XY (Z=0)")
        elevation = FreeCAD.Units.Quantity(
            self.get_storey_elevation(obj), FreeCAD.Units.Length
        ).UserString
        return f"{obj.Label} [{elevation}]"

    def set_active_storey(self, storey):
        self.active_storey = storey
        self.apply_plan_view(fit=False)
        self._apply_storey_visibility()
        self._refresh_task_panel_status()

    def _on_embedded_command_started(self, tool_name, command=None):
        if self._tearing_down:
            return
        self._embedded_tool_name = tool_name
        if command is not None:
            self._embedded_tool = command
        self.current_tool = tool_name
        self._refresh_task_panel_status()

    def _on_embedded_command_finished(self, tool_name, command=None):
        if self._tearing_down:
            return
        if command is None or self._embedded_tool is command:
            self._embedded_host = None
            self._embedded_tool = None
            self._embedded_tool_name = None
        if self.current_tool == tool_name:
            self.current_tool = "Select"
            self._refresh_task_panel_status()

    def activate_select_tool(self):
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        self._cancel_wall_edit()

    def activate_wall_tool(self):
        from bimcommands import BimWall

        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self.selected_wall = None
        self._clear_wall_grips()
        try:
            FreeCADGui.Selection.clearSelection()
        except (ReferenceError, RuntimeError):
            pass
        self._start_embedded_tool("Wall", BimWall.Arch_Wall(), host_class=_PlanEditWallHost)

    def activate_rect_wall_tool(self):
        self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self.selected_wall = None
        self._clear_wall_grips()
        self._clear_rect_wall_preview()
        self._rect_wall_start = None
        self._rect_wall_params = self._get_wall_defaults()
        self.current_tool = "Rect Wall"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_rect_wall_point,
            title=translate("BIM_PlanEdit", "First rectangle corner"),
        )
        self._refresh_task_panel_status()

    def activate_move_tool(self):
        from draftguitools import gui_move

        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_wall_grips()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        import Draft

        self._cancel_rect_wall_tool(refresh=False)
        selection = []
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            selection = []

        if not selection:
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Select objects to join before using Join.\n")
            )
            return

        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_wall_grips()

        if all(Draft.getType(obj) == "Wall" for obj in selection):
            from bimcommands import BimArchUtils

            self.current_tool = "Join"
            self._refresh_task_panel_status()
            BimArchUtils.Arch_MergeWalls().Activated()
            self.current_tool = "Select"
            self._refresh_selected_wall()
            return

        from draftguitools import gui_join

        self._start_embedded_tool("Join", gui_join.Join())

    def stretch_selected_wall(self, endpoint):
        self._start_wall_edit(endpoint)

    def move_selected_wall(self):
        self._start_wall_edit("Move")

    def is_selected_wall_baseless(self):
        wall = self.selected_wall
        if not wall:
            return False
        if getattr(wall, "Base", None):
            return False
        proxy = getattr(wall, "Proxy", None)
        return hasattr(proxy, "calc_endpoints") and hasattr(proxy, "set_from_endpoints")

    def apply_plan_view(self, fit=True):
        import WorkingPlane

        if self.view:
            try:
                self.view.setCameraType("Orthographic")
                self.view.viewTop()
            except RuntimeError:
                self.view = None

        if self.viewer:
            try:
                self.viewer.setOverrideMode("Footprint")
                if self._saved_background:
                    _apply_viewer_background(
                        self.viewer,
                        _make_plan_background_state(self._saved_background),
                    )
            except RuntimeError:
                self.viewer = None

        wp = WorkingPlane.get_working_plane(update=False)
        offset = self.get_storey_elevation(self.active_storey) if self.active_storey else 0.0
        wp.set_to_top(offset=offset)
        if hasattr(wp, "_update_all"):
            wp._update_all(_hist_add=False)
        # Keep a dedicated immutable-like plan plane for embedded tools instead
        # of reusing Draft's live PlaneGui state, which can be mutated by other
        # Draft UI paths during interaction.
        self._interaction_plane = WorkingPlane.PlaneBase()
        self._interaction_plane.set_to_top(offset=offset)

        if self.active_storey:
            self._set_active_object(self.active_storey)

        if fit and self.view:
            try:
                self.view.fitAll()
            except RuntimeError:
                self.view = None

    def restore_state(self):
        import WorkingPlane

        self._restore_object_view_state()
        self._restore_snap_profile()
        self._interaction_plane = None

        if self.viewer:
            try:
                self.viewer.setOverrideMode("As Is")
                if self._saved_background:
                    _apply_viewer_background(self.viewer, self._saved_background)
            except RuntimeError:
                self.viewer = None

        if self.view and self._saved_camera_type:
            try:
                self.view.setCameraType(self._saved_camera_type)
            except RuntimeError:
                self.view = None
        if self.view and self._saved_camera:
            try:
                self.view.setCamera(self._saved_camera)
            except RuntimeError:
                self.view = None

        wp = self._working_plane or WorkingPlane.get_working_plane(update=False)
        if hasattr(wp, "restore"):
            try:
                wp.restore()
                wp._update_all(_hist_add=False)
            except RuntimeError:
                pass

    def _capture_state(self):
        import WorkingPlane

        if self.view and hasattr(self.view, "getCamera"):
            self._saved_camera = self.view.getCamera()
        if self.view and hasattr(self.view, "getCameraType"):
            self._saved_camera_type = self.view.getCameraType()
        self._saved_background = self._capture_background_state()

        self._working_plane = WorkingPlane.get_working_plane(update=False)
        if hasattr(self._working_plane, "save"):
            self._working_plane.save()

    def get_interaction_plane(self):
        import WorkingPlane

        if self._interaction_plane is not None:
            return _copy_plane(self._interaction_plane)
        return WorkingPlane.get_working_plane(update=False)

    def _project_plan_point(self, point):
        plane = self.get_interaction_plane()
        if plane and hasattr(plane, "project_point"):
            try:
                return plane.project_point(point)
            except Exception:
                pass
        return point

    def _get_wall_defaults(self):
        from draftutils import params

        return {
            "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
            "width": params.get_param_arch("WallWidth"),
            "height": params.get_param_arch("WallHeight"),
            "offset": params.get_param_arch("WallOffset"),
        }

    def _capture_background_state(self):
        params = _view_param_group()
        return {
            "gradient": params.GetBool("Gradient", True),
            "radial_gradient": params.GetBool("RadialGradient", False),
            "use_mid": params.GetBool("UseBackgroundColorMid", False),
            "background": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor", 3940932863)),
            "background2": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor2", 859006463)),
            "background3": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor3", 2880160255)),
            "background4": _unsigned_to_rgb(params.GetUnsigned("BackgroundColor4", 1869583359)),
        }

    def _apply_plan_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper or not hasattr(snapper, "push_snap_modes"):
            return
        try:
            snapper.push_snap_modes(_PLAN_EDIT_SNAP_SET)
        except Exception:
            pass

    def _restore_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper or not hasattr(snapper, "pop_snap_modes"):
            return
        try:
            snapper.pop_snap_modes()
        except Exception:
            pass

    def _capture_object_view_state(self):
        self._saved_object_view_state = {}
        if not self.doc:
            return
        for obj in self.doc.Objects:
            self._register_object_view_state(obj)

    def _register_object_view_state(self, obj):
        if not obj:
            return
        view_object = getattr(obj, "ViewObject", None)
        if not view_object:
            return
        state = {}
        for prop in ("Visibility", "Transparency", "Selectable"):
            if hasattr(view_object, prop):
                try:
                    state[prop] = getattr(view_object, prop)
                except Exception:
                    pass
        if state:
            self._saved_object_view_state[obj.Name] = state

    def _add_object_to_active_storey(self, obj):
        storey = self.active_storey
        if not storey or not obj:
            return False
        if obj is storey or obj in getattr(storey, "InListRecursive", []):
            return True
        try:
            if hasattr(storey, "addObject"):
                storey.addObject(obj)
                return True
        except Exception:
            pass
        group = getattr(storey, "Group", None)
        if group is None:
            return False
        try:
            if obj not in group:
                storey.Group = list(group) + [obj]
            return True
        except Exception:
            return False

    def _register_plan_object(self, obj):
        if not obj:
            return
        self._add_object_to_active_storey(obj)
        self._register_object_view_state(obj)
        self._apply_storey_visibility()

    def _restore_object_view_state(self):
        if not self.doc or not self._saved_object_view_state:
            return
        try:
            doc = self.doc
            _ = doc.Name
        except Exception:
            self.doc = None
            return
        for obj_name, state in self._saved_object_view_state.items():
            try:
                obj = doc.getObject(obj_name)
            except Exception:
                self.doc = None
                return
            if not obj:
                continue
            view_object = getattr(obj, "ViewObject", None)
            if not view_object:
                continue
            for prop, value in state.items():
                if hasattr(view_object, prop):
                    try:
                        setattr(view_object, prop, value)
                    except Exception:
                        pass

    def _is_storey_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") == "Building Storey":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Floor"
        except Exception:
            return False

    def _is_plan_background_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") == "Slab":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
        except Exception:
            return False

    def _get_object_storeys(self, obj):
        if not obj:
            return []
        storeys = []
        seen = set()
        parents = list(getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []))
        if self._is_storey_object(obj):
            parents.insert(0, obj)
        for parent in parents:
            if not parent or parent.Name in seen:
                continue
            seen.add(parent.Name)
            if self._is_storey_object(parent):
                storeys.append(parent)
        return storeys

    def _apply_storey_visibility(self):
        if not self.doc or not self._saved_object_view_state:
            return

        active_storey_name = getattr(self.active_storey, "Name", None)

        if active_storey_name is None:
            self._restore_object_view_state()
            return

        for obj in self.doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            state = self._saved_object_view_state.get(obj.Name)
            if not view_object or not state:
                continue

            storeys = self._get_object_storeys(obj)
            if not storeys:
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                continue

            belongs_to_active = any(parent.Name == active_storey_name for parent in storeys)
            if belongs_to_active:
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if self._is_plan_background_object(obj) and hasattr(view_object, "Selectable"):
                    try:
                        view_object.Selectable = False
                    except Exception:
                        pass
                continue

            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = state.get("Visibility", True)
                except Exception:
                    pass
            if hasattr(view_object, "Transparency"):
                try:
                    view_object.Transparency = max(int(state.get("Transparency", 0)), 85)
                except Exception:
                    pass
            if hasattr(view_object, "Selectable"):
                try:
                    view_object.Selectable = False
                except Exception:
                    pass

    def _set_active_object(self, obj):
        context = "Arch"
        if getattr(obj, "IfcType", "") == "Building Storey":
            context = "NativeIFC"
        try:
            self.view.setActiveObject(context, obj)
        except Exception:
            pass

    def _attach_selection_observer(self):
        if not self._selection_observer_added:
            FreeCADGui.Selection.addObserver(self)
            self._selection_observer_added = True

    def _detach_selection_observer(self):
        if self._selection_observer_added:
            FreeCADGui.Selection.removeObserver(self)
            self._selection_observer_added = False

    def _register_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            return

        if not self.view or not hasattr(self.view, "addEventCallbackPivy"):
            return

        try:
            self._render_manager = self.view.getViewer().getSoRenderManager()
            if self._key_pressed_cb is None:
                self._key_pressed_cb = self.view.addEventCallbackPivy(
                    coin.SoKeyboardEvent.getClassTypeId(), self._on_key_pressed
                )
            if self._mouse_moved_cb is None:
                self._mouse_moved_cb = self.view.addEventCallbackPivy(
                    coin.SoLocation2Event.getClassTypeId(), self._on_mouse_moved
                )
            if self._mouse_pressed_cb is None:
                self._mouse_pressed_cb = self.view.addEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_pressed
                )
        except RuntimeError:
            self._render_manager = None

    def _unregister_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_pressed_cb = None
            self._render_manager = None
            return

        if not self.view:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_pressed_cb = None
            self._render_manager = None
            return

        try:
            if self._key_pressed_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoKeyboardEvent.getClassTypeId(), self._key_pressed_cb
                )
            if self._mouse_moved_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoLocation2Event.getClassTypeId(), self._mouse_moved_cb
                )
            if self._mouse_pressed_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._mouse_pressed_cb
                )
        except RuntimeError:
            pass

        self._key_pressed_cb = None
        self._mouse_moved_cb = None
        self._mouse_pressed_cb = None
        self._render_manager = None

    def _refresh_selected_wall(self):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        import Draft

        previous_wall = self.selected_wall
        self.selected_wall = None
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            return
        if len(selection) == 1 and Draft.getType(selection[0]) == "Wall":
            self.selected_wall = selection[0]
        if previous_wall != self.selected_wall:
            self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _start_embedded_tool(self, tool_name, command, host_class=_PlanEditCommandHost):
        self.current_tool = tool_name
        self._refresh_task_panel_status()
        self._embedded_tool = command
        self._embedded_tool_name = tool_name
        if host_class is _PlanEditWallHost:
            self._embedded_host = host_class(self, command)
        else:
            self._embedded_host = host_class(self, tool_name, command)
        command.Activated(host=self._embedded_host)

    def _cancel_pending_edit(self):
        if self._tearing_down:
            self._restore_edit_wall_visibility()
            self._clear_drag_preview()
            self._edit_wall = None
            self._edit_endpoint = None
            self._edit_endpoints = None
            self._preview_points = None
            self._dragging_grip = False
            self._ignore_selection_changes = False
            self._embedded_host = None
            self._embedded_tool = None
            self._embedded_tool_name = None
            return
        self._stop_snapper()
        FreeCAD.activeDraftCommand = None
        self._restore_edit_wall_visibility()
        self._clear_drag_preview()
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._dragging_grip = False
        self._ignore_selection_changes = False
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._sync_wall_grips()

    def _stop_snapper(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper:
            return
        try:
            snapper.getPoint()
            snapper.off()
        except Exception:
            pass

    def _has_active_rect_wall_tool(self):
        return self._rect_wall_start is not None or self.current_tool == "Rect Wall"

    def _clear_rect_wall_preview(self):
        for tracker in self._rect_wall_preview_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._rect_wall_preview_trackers = []

    def _cancel_rect_wall_tool(self, refresh=True):
        if not self._has_active_rect_wall_tool():
            return False
        self._stop_snapper()
        self._clear_rect_wall_preview()
        self._rect_wall_start = None
        self._rect_wall_params = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _get_rect_wall_corners(self, point):
        start = self._rect_wall_start
        if start is None or point is None:
            return None
        end = self._project_plan_point(point)
        if end is None:
            return None
        x1, y1 = start.x, start.y
        x2, y2 = end.x, end.y
        z = start.z
        if abs(x2 - x1) < _MIN_WALL_LENGTH or abs(y2 - y1) < _MIN_WALL_LENGTH:
            return None
        return [
            FreeCAD.Vector(x1, y1, z),
            FreeCAD.Vector(x2, y1, z),
            FreeCAD.Vector(x2, y2, z),
            FreeCAD.Vector(x1, y2, z),
        ]

    def _update_rect_wall_preview(self, point, info):
        del info
        corners = self._get_rect_wall_corners(point)
        if not corners:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        segments = list(zip(corners, corners[1:] + corners[:1]))
        if not self._rect_wall_preview_trackers:
            for start, end in segments:
                tracker = DraftTrackers.rectangleTracker(face=True)
                self._rect_wall_preview_trackers.append(tracker)
        for tracker, (start, end) in zip(self._rect_wall_preview_trackers, segments):
            footprint = self._get_preview_footprint(
                [start, end],
                width=self._rect_wall_params["width"],
                align=self._rect_wall_params["align"],
            )
            if not footprint:
                continue
            axis = end.sub(start)
            if axis.Length < _MIN_WALL_LENGTH:
                continue
            axis.normalize()
            rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
            perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))
            tracker.setPlane(axis, perp)
            tracker.setorigin(footprint[0])
            tracker.update(footprint[2])
            tracker.on()

    def _create_rect_wall_run(self, corners):
        from bimcommands import BimWall

        walls = []
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Rectangular Wall Run"))
        try:
            walls = BimWall.create_wall_run_from_points(
                corners,
                width=self._rect_wall_params["width"],
                height=self._rect_wall_params["height"],
                align=self._rect_wall_params["align"],
                offset=self._rect_wall_params["offset"],
                closed=True,
                on_created=self._register_plan_object,
            )
            BimWall.autojoin_wall_run(walls, closed=True)
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return walls

    def _handle_rect_wall_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_rect_wall_tool()
            return

        point = self._project_plan_point(point)
        if self._rect_wall_start is None:
            self._rect_wall_start = point
            FreeCADGui.Snapper.getPoint(
                callback=self._handle_rect_wall_point,
                movecallback=self._update_rect_wall_preview,
                last=point,
                title=translate("BIM_PlanEdit", "Opposite rectangle corner"),
                mode="line",
            )
            return

        corners = self._get_rect_wall_corners(point)
        if not corners:
            self._cancel_rect_wall_tool()
            return

        try:
            walls = self._create_rect_wall_run(corners)
        except Exception:
            self._cancel_rect_wall_tool()
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the rectangular wall run.\n")
            )
            return

        try:
            FreeCADGui.Selection.clearSelection()
            for wall in walls:
                FreeCADGui.Selection.addSelection(wall)
        except (ReferenceError, RuntimeError):
            pass

        self._cancel_rect_wall_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_selected_wall()
        self._refresh_task_panel_status()

    def _has_active_wall_edit(self):
        return (
            self._edit_wall is not None or self._dragging_grip or self._embedded_tool_name == "Wall"
        )

    def _has_active_embedded_tool(self):
        return self._embedded_tool is not None

    def _cancel_embedded_tool(self, tool_name=None):
        if self._tearing_down or self._embedded_tool is None:
            return
        if tool_name is not None and self._embedded_tool_name != tool_name:
            return
        tool = self._embedded_tool
        if hasattr(tool, "cancel_interactive"):
            try:
                tool.cancel_interactive()
                return
            except Exception:
                pass
        if hasattr(tool, "finish"):
            try:
                tool.finish(cont=False)
            except Exception:
                pass

    def _cancel_wall_edit(self, restore=True, refresh=True):
        if not self._has_active_wall_edit():
            if refresh:
                self.current_tool = "Select"
                self._refresh_task_panel_status()
            return False

        self._cancel_wall_subtool()

        if restore and self._dragging_grip:
            self._cancel_drag_edit()
            return True

        self.current_tool = "Select"
        self._cancel_pending_edit()
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _cancel_wall_subtool(self):
        self._cancel_embedded_tool("Wall")

    def _start_wall_edit(self, mode):
        if not self.is_selected_wall_baseless():
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "Select a baseless wall before using wall grips.\n",
                )
            )
            return

        wall = self.selected_wall
        proxy = getattr(wall, "Proxy", None)
        if (
            not proxy
            or not hasattr(proxy, "calc_endpoints")
            or not hasattr(proxy, "set_from_endpoints")
        ):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        self.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
        self._edit_wall = wall
        self._edit_endpoint = mode
        self._edit_endpoints = endpoints
        self._clear_wall_grips()
        self._refresh_task_panel_status()

        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))

        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._finish_wall_edit,
            title=title,
        )

    def _finish_wall_edit(self, point=None, obj=None):
        del obj

        wall = self._edit_wall
        endpoint = self._edit_endpoint
        original_endpoints = self._edit_endpoints
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        FreeCAD.activeDraftCommand = None

        if point is None or not wall or not endpoint:
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        proxy = getattr(wall, "Proxy", None)
        if (
            not proxy
            or not hasattr(proxy, "calc_endpoints")
            or not hasattr(proxy, "set_from_endpoints")
        ):
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        if not original_endpoints or len(original_endpoints) != 2:
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        if endpoint == "Start":
            new_points = [point, original_endpoints[1]]
            transaction_name = translate("BIM_PlanEdit", "Stretch Wall Endpoint")
        elif endpoint == "End":
            new_points = [original_endpoints[0], point]
            transaction_name = translate("BIM_PlanEdit", "Stretch Wall Endpoint")
        else:
            original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
            delta = point.sub(original_midpoint)
            new_points = [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]
            transaction_name = translate("BIM_PlanEdit", "Move Wall")

        self.doc.openTransaction(transaction_name)
        proxy.set_from_endpoints(wall, new_points)
        self.doc.commitTransaction()
        try:
            self.doc.recompute()
        except (ReferenceError, RuntimeError):
            self.doc = None
            self.current_tool = "Select"
            return

        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(wall)
        except (ReferenceError, RuntimeError):
            pass
        self.current_tool = "Select"
        self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _begin_grip_drag(self, grip_index):
        if grip_index not in (0, 1, 2) or not self.is_selected_wall_baseless():
            return

        wall = self.selected_wall
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "calc_endpoints"):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        self._dragging_grip = True
        self._ignore_selection_changes = True
        self._edit_wall = wall
        self._edit_endpoint = {0: "Start", 1: "End", 2: "Move"}[grip_index]
        self._edit_endpoints = endpoints
        self._preview_points = list(endpoints)
        self.current_tool = "Move Wall" if grip_index == 2 else f"Stretch {self._edit_endpoint}"
        self._edit_wall_visibility = None
        try:
            self._edit_wall_visibility = wall.ViewObject.Visibility
            wall.ViewObject.Visibility = False
        except Exception:
            self._edit_wall_visibility = None
        self._clear_wall_grips()
        self._sync_drag_preview(self._preview_points)
        FreeCAD.activeDraftCommand = self
        if getattr(FreeCADGui, "Snapper", None):
            try:
                FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        self._refresh_task_panel_status()

    def _compute_drag_points(self, point):
        endpoint = self._edit_endpoint
        original_endpoints = self._edit_endpoints
        if point is None or not endpoint or not original_endpoints:
            return None

        if endpoint == "Start":
            axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
            projected = axis.dot(point.sub(original_endpoints[1]))
            if projected > -_MIN_WALL_LENGTH:
                return None
            return [original_endpoints[1].add(axis.multiply(projected)), original_endpoints[1]]
        elif endpoint == "End":
            axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
            projected = axis.dot(point.sub(original_endpoints[0]))
            if projected < _MIN_WALL_LENGTH:
                return None
            return [original_endpoints[0], original_endpoints[0].add(axis.multiply(projected))]

        original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
        delta = point.sub(original_midpoint)
        return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]

    def _get_preview_footprint(self, points, width=None, align=None):
        wall = self._edit_wall
        if not points or len(points) != 2:
            return None

        if width is None and wall:
            width = getattr(getattr(wall, "Width", None), "Value", 0.0) or 0.0
        if width <= 0:
            return None

        axis = points[1].sub(points[0])
        if axis.Length < _MIN_WALL_LENGTH:
            return None
        axis.normalize()
        rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
        perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))

        if align is None:
            align = getattr(wall, "Align", "Center") if wall else "Center"
        if align == "Center":
            y_min = -width / 2
            y_max = width / 2
        elif align == "Left":
            y_min = -width
            y_max = 0.0
        else:
            y_min = 0.0
            y_max = width

        return [
            points[0].add(FreeCAD.Vector(perp).multiply(y_min)),
            points[1].add(FreeCAD.Vector(perp).multiply(y_min)),
            points[1].add(FreeCAD.Vector(perp).multiply(y_max)),
            points[0].add(FreeCAD.Vector(perp).multiply(y_max)),
        ]

    def _sync_drag_preview(self, points):
        if not points or len(points) != 2:
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        if self._preview_line_tracker is None:
            self._preview_line_tracker = DraftTrackers.lineTracker(ontop=True)
            self._preview_line_tracker.on()
        self._preview_line_tracker.p1(points[0])
        self._preview_line_tracker.p2(points[1])

        footprint = self._get_preview_footprint(points)
        if footprint:
            if self._preview_rect_tracker is None:
                self._preview_rect_tracker = DraftTrackers.rectangleTracker()
                self._preview_rect_tracker.on()
            axis = points[1].sub(points[0]).normalize()
            rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
            perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))
            self._preview_rect_tracker.setPlane(axis, perp)
            self._preview_rect_tracker.setorigin(footprint[0])
            self._preview_rect_tracker.update(footprint[2])
            self._preview_rect_tracker.on()

        midpoint = (points[0] + points[1]) * 0.5
        midpoint_marker = FreeCADGui.getMarkerIndex(
            "DIAMOND_FILLED", params.get_param_view("MarkerSize")
        )

        grip_specs = (
            (points[0], 0, None),
            (points[1], 1, None),
            (midpoint, 2, midpoint_marker),
        )
        if not self._preview_grip_trackers:
            for position, idx, marker in grip_specs:
                tracker = DraftTrackers.editTracker(
                    pos=position,
                    idx=idx,
                    marker=marker,
                    inactive=True,
                )
                tracker.on()
                self._preview_grip_trackers.append(tracker)
            return

        for tracker, (position, _idx, _marker) in zip(self._preview_grip_trackers, grip_specs):
            tracker.set(position)
            tracker.on()

    def _clear_drag_preview(self):
        if self._preview_line_tracker:
            try:
                self._preview_line_tracker.finalize()
            except Exception:
                pass
        self._preview_line_tracker = None

        if self._preview_rect_tracker:
            try:
                self._preview_rect_tracker.finalize()
            except Exception:
                pass
        self._preview_rect_tracker = None

        for tracker in self._preview_grip_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._preview_grip_trackers = []

    def _restore_edit_wall_visibility(self):
        wall = self._edit_wall
        if wall is not None and self._edit_wall_visibility is not None:
            try:
                wall.ViewObject.Visibility = self._edit_wall_visibility
            except Exception:
                pass
        self._edit_wall_visibility = None

    def _update_dragged_wall(self, point):
        new_points = self._compute_drag_points(point)
        if not new_points:
            return
        self._preview_points = new_points
        self._sync_drag_preview(new_points)

    def _cancel_drag_edit(self):
        self.current_tool = "Select"
        self._cancel_pending_edit()
        self._refresh_task_panel_status()

    def _commit_drag_edit(self):
        wall = self._edit_wall
        endpoint = self._edit_endpoint
        preview_points = self._preview_points
        if not wall or not endpoint or not preview_points or len(preview_points) != 2:
            self._cancel_pending_edit()
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "set_from_endpoints"):
            self._cancel_pending_edit()
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        if self.doc:
            try:
                transaction_name = (
                    translate("BIM_PlanEdit", "Move Wall")
                    if endpoint == "Move"
                    else translate("BIM_PlanEdit", "Stretch Wall Endpoint")
                )
                self.doc.openTransaction(transaction_name)
                proxy.set_from_endpoints(wall, preview_points)
                self.doc.commitTransaction()
                self.doc.recompute()
            except Exception:
                try:
                    self.doc.abortTransaction()
                except Exception:
                    pass
                self._cancel_pending_edit()
                self.current_tool = "Select"
                self._refresh_task_panel_status()
                return

        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(wall)
        except (ReferenceError, RuntimeError):
            pass

        self.current_tool = "Select"
        self._cancel_pending_edit()
        self.selected_wall = wall
        self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _get_edit_node(self, mouse_pos):
        if not self._render_manager:
            return None
        try:
            from pivy import coin
        except Exception:
            return None

        ray_pick = coin.SoRayPickAction(self._render_manager.getViewportRegion())
        ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
        ray_pick.setRadius(8)
        ray_pick.setPickAll(True)
        ray_pick.apply(self._render_manager.getSceneGraph())
        picked_points = ray_pick.getPickedPointList()
        if not picked_points:
            return None

        for picked_point in picked_points:
            path = picked_point.getPath()
            point = path.getNode(path.getLength() - 2)
            if hasattr(point, "subElementName") and "EditNode" in str(
                point.subElementName.getValue()
            ):
                return point
        return None

    def _get_snapped_drag_point(self, event):
        if not getattr(FreeCADGui, "Snapper", None):
            return None

        pos = event.getPosition().getValue()
        constrain = bool(event.wasShiftDown())
        reference = None
        if self._edit_endpoints:
            if self._edit_endpoint == "Move":
                reference = (self._edit_endpoints[0] + self._edit_endpoints[1]) * 0.5
            elif self._edit_endpoint == "Start":
                reference = self._edit_endpoints[1]
            else:
                reference = self._edit_endpoints[0]
        try:
            return FreeCADGui.Snapper.snap((pos[0], pos[1]), reference, constrain=constrain)
        except Exception:
            return None

    def _on_mouse_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return

        event = event_callback.getEvent()
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return

        if event.getState() == coin.SoMouseButtonEvent.DOWN:
            if self._dragging_grip:
                return
            if self.current_tool != "Select":
                return
            pos = event.getPosition().getValue()
            node = self._get_edit_node((pos[0], pos[1]))
            if not node:
                return
            try:
                doc = FreeCAD.getDocument(str(node.documentName.getValue()))
                obj = doc.getObject(str(node.objectName.getValue()))
                index = int(str(node.subElementName.getValue())[8:])
            except Exception:
                return
            if obj != self.selected_wall:
                self.selected_wall = obj
            self._begin_grip_drag(index)
        elif event.getState() == coin.SoMouseButtonEvent.UP and self._dragging_grip:
            self._commit_drag_edit()

    def _on_mouse_moved(self, event_callback):
        if self._tearing_down or not self._dragging_grip:
            return
        event = event_callback.getEvent()
        snapped_point = self._get_snapped_drag_point(event)
        if snapped_point is None:
            return
        self._update_dragged_wall(snapped_point)

    def _on_key_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return
        event = event_callback.getEvent()
        if event.getKey() != coin.SoKeyboardEvent.ESCAPE:
            return
        if self._dragging_grip:
            self._cancel_drag_edit()
            return
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()

    # Selection observer interface

    def addSelection(self, doc, obj, sub, point):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        if sub in ("EditNode0", "EditNode1", "EditNode2"):
            self.selected_wall = FreeCAD.getDocument(doc).getObject(obj)
            self._clear_wall_grips()
            edit_mode = {
                "EditNode0": "Start",
                "EditNode1": "End",
                "EditNode2": "Move",
            }[sub]
            if edit_mode == "Move":
                self.move_selected_wall()
            else:
                self.stretch_selected_wall(edit_mode)
            return
        del doc, obj, sub, point
        self._refresh_selected_wall()

    def removeSelection(self, doc, obj, sub):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc, obj, sub
        self._refresh_selected_wall()

    def setSelection(self, doc):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc
        self._refresh_selected_wall()

    def clearSelection(self, doc):
        if self._tearing_down:
            return
        if self._ignore_selection_changes:
            return
        del doc
        self._refresh_selected_wall()

    def attach_task_panel(self, panel):
        if self.task_panel is panel:
            return
        self.task_panel = panel

    def detach_task_panel(self):
        panel = self.task_panel
        self.task_panel = None
        if panel:
            panel.mark_closed()
            panel.detach()
        return panel

    def on_panel_closed(self, panel):
        if self.task_panel is panel:
            self.task_panel = None
            if not self._finishing:
                self.shutdown(close_dialog=False, teardown=self._tearing_down)
            return
        panel.mark_closed()
        panel.detach()

    def _refresh_task_panel_status(self):
        if self._tearing_down:
            return
        panel = self.task_panel
        if not panel:
            return
        try:
            panel.refresh_from_session()
        except (AttributeError, RuntimeError):
            self.on_panel_closed(panel)

    def _sync_wall_grips(self):
        self._clear_wall_grips()
        if not self.is_selected_wall_baseless():
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        wall = self.selected_wall
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "calc_endpoints"):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        midpoint = (endpoints[0] + endpoints[1]) * 0.5
        midpoint_marker = FreeCADGui.getMarkerIndex(
            "DIAMOND_FILLED", params.get_param_view("MarkerSize")
        )

        self._grip_trackers = [
            DraftTrackers.editTracker(pos=endpoints[0], name=wall.Name, idx=0),
            DraftTrackers.editTracker(pos=endpoints[1], name=wall.Name, idx=1),
            DraftTrackers.editTracker(
                pos=midpoint,
                name=wall.Name,
                idx=2,
                marker=midpoint_marker,
            ),
        ]

    def _clear_wall_grips(self):
        for tracker in self._grip_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._grip_trackers = []


class PlanEditDockWidget:
    """Compact modeless dock for Plan Edit mode."""

    def __init__(self, session):
        from PySide import QtCore, QtGui

        self.session = session
        self._storey_items = []
        self._closed = False
        self._params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit")
        self._dock = _PlanEditDock(self)

        self.form = self._dock
        self.form.setWindowTitle(translate("BIM_PlanEdit", "Plan Edit"))
        self.form.setObjectName("BIMPlanEditDock")
        self.form.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.form.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.form.setFeatures(
            QtGui.QDockWidget.DockWidgetClosable
            | QtGui.QDockWidget.DockWidgetMovable
            | QtGui.QDockWidget.DockWidgetFloatable
        )

        container = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        container.setMinimumWidth(280)
        container.setMaximumWidth(360)

        intro = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan authoring mode for the active storey.",
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        storey_row = QtGui.QHBoxLayout()
        storey_row.setSpacing(6)
        storey_label = QtGui.QLabel(translate("BIM_PlanEdit", "Storey"))
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        storey_row.addWidget(storey_label)
        storey_row.addWidget(self.storey_combo, 1)
        layout.addLayout(storey_row)

        buttons = QtGui.QHBoxLayout()
        buttons.setSpacing(6)
        self.select_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Select"))
        self.wall_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Wall"))
        self.rect_wall_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Rect Wall"))
        self.move_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Move"))
        self.join_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Join"))
        self.reapply_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Reapply View"))
        self.select_button.clicked.connect(self.on_select_clicked)
        self.wall_button.clicked.connect(self.on_wall_clicked)
        self.rect_wall_button.clicked.connect(self.on_rect_wall_clicked)
        self.move_button.clicked.connect(self.on_move_clicked)
        self.join_button.clicked.connect(self.on_join_clicked)
        self.reapply_button.clicked.connect(self.on_reapply_clicked)
        buttons.addWidget(self.select_button)
        buttons.addWidget(self.wall_button)
        buttons.addWidget(self.rect_wall_button)
        buttons.addWidget(self.move_button)
        buttons.addWidget(self.join_button)
        buttons.addWidget(self.reapply_button)
        layout.addLayout(buttons)

        stretch_buttons = QtGui.QHBoxLayout()
        stretch_buttons.setSpacing(6)
        self.stretch_start_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Stretch Start"))
        self.stretch_end_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Stretch End"))
        self.stretch_start_button.clicked.connect(self.on_stretch_start_clicked)
        self.stretch_end_button.clicked.connect(self.on_stretch_end_clicked)
        stretch_buttons.addWidget(self.stretch_start_button)
        stretch_buttons.addWidget(self.stretch_end_button)
        layout.addLayout(stretch_buttons)

        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.exit_button = QtGui.QPushButton(translate("BIM_PlanEdit", "Exit Plan Edit"))
        self.exit_button.clicked.connect(self.on_exit_clicked)
        self.exit_button.setMinimumHeight(32)
        layout.addWidget(self.exit_button)

        container.setLayout(layout)
        self.form.setWidget(container)
        FreeCADGui.getMainWindow().addDockWidget(QtCore.Qt.RightDockWidgetArea, self.form)
        self._apply_initial_placement(QtCore)
        QtCore.QMetaObject.connectSlotsByName(container)

    def show(self):
        if self._closed or self.form is None:
            return
        self.form.show()

    def raise_(self):
        if self._closed or self.form is None:
            return
        self.form.raise_()

    def activateWindow(self):
        if self._closed or self.form is None:
            return
        self.form.activateWindow()

    def mark_closed(self):
        self._closed = True

    def save_state(self):
        if self.form is None:
            return
        try:
            geometry = self.form.geometry()
            self._params.SetBool("DockPlacementSaved", True)
            self._params.SetBool("DockFloating", self.form.isFloating())
            self._params.SetInt("DockX", geometry.x())
            self._params.SetInt("DockY", geometry.y())
            self._params.SetInt("DockWidth", geometry.width())
            self._params.SetInt("DockHeight", geometry.height())
            area = FreeCADGui.getMainWindow().dockWidgetArea(self.form)
            self._params.SetInt("DockArea", getattr(area, "value", _DEFAULT_DOCK_AREA))
        except RuntimeError:
            pass
        except Exception:
            pass

    def _apply_initial_placement(self, QtCore):
        width = max(self._params.GetInt("DockWidth", 300), 280)
        height = max(self._params.GetInt("DockHeight", 240), 220)

        if self._params.GetBool("DockPlacementSaved", False):
            area = self._params.GetInt("DockArea", _DEFAULT_DOCK_AREA)
            try:
                dock_area = getattr(QtCore.Qt, "DockWidgetArea", None)
                if dock_area:
                    dock_area = dock_area(area)
                else:
                    dock_area = QtCore.Qt.RightDockWidgetArea
                FreeCADGui.getMainWindow().addDockWidget(dock_area, self.form)
            except Exception:
                pass
            self.form.resize(width, height)
            floating = self._params.GetBool("DockFloating", True)
            self.form.setFloating(floating)
            if floating:
                self.form.move(
                    self._params.GetInt("DockX", 0),
                    self._params.GetInt("DockY", 0),
                )
            return

        main_window = FreeCADGui.getMainWindow()
        frame = main_window.frameGeometry()
        margin = 32
        self.form.resize(300, 240)
        self.form.setFloating(True)
        self.form.move(
            frame.x() + max(frame.width() - 300 - margin, margin),
            frame.y() + margin,
        )

    def detach(self):
        form = self.form
        self.form = None
        self._dock = None
        self.status = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.move_button = None
        self.join_button = None
        self.reapply_button = None
        self.stretch_start_button = None
        self.stretch_end_button = None
        self.exit_button = None
        if form:
            try:
                form.setWidget(None)
            except RuntimeError:
                pass

    def close(self):
        if self.form is None:
            return
        self.mark_closed()
        self.form.close()

    def refresh(self):
        if self._closed or self.form is None or self.storey_combo is None:
            return
        try:
            self.storey_combo.blockSignals(True)
            self.storey_combo.clear()
            self._storey_items = [None] + list(self.session.storeys)
            self.storey_combo.addItem(translate("BIM_PlanEdit", "Global XY (Z=0)"))
            for storey in self.session.storeys:
                self.storey_combo.addItem(self.session.get_storey_label(storey))

            current = self.session.active_storey
            try:
                index = self._storey_items.index(current)
            except ValueError:
                index = 0
            self.storey_combo.setCurrentIndex(index)
            self.storey_combo.blockSignals(False)
            self.refresh_from_session()
        except (AttributeError, RuntimeError):
            self.mark_closed()
            self.detach()

    def refresh_from_session(self):
        if (
            self._closed
            or self.form is None
            or self.status is None
            or self.stretch_start_button is None
            or self.stretch_end_button is None
            or self.exit_button is None
        ):
            return
        try:
            storey_text = self.session.get_storey_label(self.session.active_storey)
            tool = self.session.current_tool
            selected = self.session.selected_wall
            if selected:
                wall_state = translate("BIM_PlanEdit", "Selected wall: {label}").format(
                    label=selected.Label
                )
                if self.session.is_selected_wall_baseless():
                    wall_state += "\n" + translate("BIM_PlanEdit", "Wall mode: baseless")
                    wall_state += "\n" + translate(
                        "BIM_PlanEdit",
                        "Grip editing: drag square grips to stretch, diamond grip to move",
                    )
                else:
                    wall_state += "\n" + translate("BIM_PlanEdit", "Wall mode: base-driven")
            else:
                wall_state = translate("BIM_PlanEdit", "Selected wall: none")
            self.status.setText(
                translate(
                    "BIM_PlanEdit",
                    "Current tool: {tool}\nWorking plane: {storey}\nDisplay override: Footprint\n{wall_state}",
                ).format(tool=tool, storey=storey_text, wall_state=wall_state)
            )
            stretch_enabled = self.session.is_selected_wall_baseless()
            self.stretch_start_button.setEnabled(stretch_enabled)
            self.stretch_end_button.setEnabled(stretch_enabled)
        except (AttributeError, RuntimeError):
            self.mark_closed()
            self.detach()

    def on_storey_changed(self, index):
        if 0 <= index < len(self._storey_items):
            self.session.set_active_storey(self._storey_items[index])

    def on_select_clicked(self):
        self.session.activate_select_tool()

    def on_wall_clicked(self):
        self.session.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.activate_rect_wall_tool()

    def on_move_clicked(self):
        self.session.activate_move_tool()

    def on_join_clicked(self):
        self.session.activate_join_tool()

    def on_reapply_clicked(self):
        self.session.apply_plan_view(fit=False)
        self.refresh_from_session()

    def on_stretch_start_clicked(self):
        self.session.stretch_selected_wall("Start")

    def on_stretch_end_clicked(self):
        self.session.stretch_selected_wall("End")

    def on_exit_clicked(self):
        self.session.shutdown()


class _PlanEditDock:
    def __new__(cls, owner):
        from PySide import QtGui

        class _DockWidget(QtGui.QDockWidget):
            def __init__(self, dock_owner):
                super().__init__(FreeCADGui.getMainWindow())
                self._plan_owner = dock_owner

            def closeEvent(self, event):
                owner = self._plan_owner
                if owner and not owner._closed:
                    if owner.session and not owner.session._tearing_down:
                        owner.save_state()
                    owner.mark_closed()
                    if owner.session:
                        owner.session.on_panel_closed(owner)
                super().closeEvent(event)
                self._plan_owner = None

        return _DockWidget(owner)

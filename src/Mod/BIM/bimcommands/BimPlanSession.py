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

from contextlib import contextmanager
import json
import math
import os
import tempfile
import time

import ArchPlanGeometry
import FreeCAD
import FreeCADGui
from draftguitools import gui_base

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

_PLAN_PAPER_RGB = (1.0, 1.0, 1.0)
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
# Opening move is already constrained onto the host axis, so keep its snap
# profile minimal. This avoids unrelated object snaps dragging the returned
# point far away from the hovered location during Draft snap winner selection.
_OPENING_MOVE_SNAP_SET = {
    "Lock",
    "WorkingPlane",
}
_OPENING_MOVE_ANCHORS = ("center", "left", "right")
_PLAN_JOIN_TYPES = ("Miter", "Butt", "Tee")
_PRIMARY_PLAN_TARGET_KINDS = ("wall", "opening", "symbol", "region", "space")
_OPENING_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "Hosts",
    "WindowParts",
    "IfcType",
}
_WALL_VISUAL_PROPERTIES = {"Shape", "Additions", "Subtractions", "Hosts"}
_SYMBOL_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "PlanSymbols",
    "LinkedObject",
}
_SPACE_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Boundaries",
}
_REGION_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Points",
    "Scheme",
    "RegionType",
    "ParentSpace",
}
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
_PLAN_VISUAL_HOVERED_SPACE = "hovered_space"
_PLAN_VISUAL_HOVERED_REGION = "hovered_region"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
_PLAN_VISUAL_SELECTED_SPACE = "selected_space"
_PLAN_VISUAL_SELECTED_REGION = "selected_region"
_PLAN_VISUAL_SECONDARY_SELECTION = "secondary_selection"
_PLAN_VISUAL_SPACE_REGION_PICK = "space_region_pick"
_PLAN_VISUAL_WALL_GRIPS = "wall_grips"
_PLAN_VISUAL_WALL_EDIT_PREVIEW = "wall_edit_preview"
_PLAN_VISUAL_ALL = "all"
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
    try:
        if hasattr(workbench, "setTaskWatchers"):
            FreeCADGui.Control.clearTaskWatcher()
            workbench.setTaskWatchers()
    except Exception:
        pass


def start_session():
    global _active_session

    if _active_session:
        return _active_session

    session = PlanEditSession()
    if session.enter():
        _active_session = session
        try:
            FreeCADGui.Control.showTaskView()
        except Exception:
            pass
        _refresh_contextual_task_watchers()
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
        self._aux_task_panels = []
        self._viewport_status_chip = None
        self.current_tool = "Select"
        self._plan_join_type = "Miter"
        self._plan_relation_status_message = None
        self.storeys = []
        self.active_storey = None
        self._selected_plan_target_kind = None
        self._selected_plan_target_obj = None
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self.hovered_space = None
        self.hovered_region = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._secondary_selected_plan_targets_state = []
        self._grip_trackers = []
        self._wall_hover_trackers = []
        self._junction_node_trackers = []
        self._hovered_wall_opening_context_trackers = []
        self._opening_hover_trackers = []
        self._symbol_hover_trackers = []
        self._space_hover_trackers = []
        self._region_hover_trackers = []
        self._plan_overlay_geometry_cache = {
            "space": {},
            "region": {},
        }
        self._opening_overlay_trackers = []
        self._symbol_overlay_trackers = []
        self._space_overlay_trackers = []
        self._selected_space_overlay_dirty = True
        self._selected_space_overlay_geometry_key = None
        self._selected_space_overlay_segments = ()
        self._selected_space_overlay_render_state = None
        self._region_overlay_trackers = []
        self._secondary_selection_trackers = []
        self._space_region_pick_trackers = []
        self._selected_wall_opening_context_trackers = []
        self._opening_handle_trackers = []
        self._symbol_handle_trackers = []
        self._selected_opening_hard_refresh_queued = False
        self._opening_host_recompute_queued = False
        self._opening_host_recompute_running = False
        self._opening_move_preview_trackers = []
        self._symbol_edit_preview_trackers = []
        self._opening_move_snap_profile_pushed = False
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self._selection_observer_added = False
        self._document_observer_added = False
        self._pending_created_plan_objects = {}
        self._created_plan_objects_flush_queued = False
        self._pending_selected_wall_reset = False
        self._wall_edit_modal_active = False
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._preview_points = None
        self._preview_line_tracker = None
        self._preview_footprint_trackers = []
        self._preview_grip_trackers = []
        self._wall_edit_readout_trackers = []
        self._wall_edit_opening_preview_trackers = []
        self._wall_edit_active_readout_tracker = None
        self._wall_edit_active_readout_mode = None
        self._wall_edit_length_edit_queued = False
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._space_separator_start = None
        self._space_separator_height = None
        self._space_separator_preview_trackers = []
        self._plan_region_points = []
        self._plan_region_parent_space = None
        self._plan_region_preview_trackers = []
        self._edit_wall_visibility = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._edit_space = None
        self._ignore_selection_changes = False
        self._mouse_moved_cb = None
        self._mouse_wheel_cb = None
        self._mouse_wheel_event_type = None
        self._mouse_pressed_cb = None
        self._consume_left_button_release = False
        self._key_pressed_cb = None
        self._overlay_refresh_queued = False
        self._dirty_plan_visuals = set()
        self._render_manager = None
        self._saved_camera = None
        self._saved_camera_type = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self._saved_object_view_state = {}
        self._working_plane = None
        self._interaction_plane = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._finishing = False
        self._tearing_down = False
        self._plan_edit_params = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
        )
        self._plan_perf_log_path = self._resolve_plan_perf_log_path()
        self._plan_perf_current_event = None
        self._plan_perf_sequence = 0
        app = QtGui.QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.begin_teardown)

    def _get_selected_target_for_kind(self, kind):
        if getattr(self, "_selected_plan_target_kind", None) == kind:
            return getattr(self, "_selected_plan_target_obj", None)
        return None

    def _set_selected_target_for_kind(self, kind, obj):
        if obj is None:
            if getattr(self, "_selected_plan_target_kind", None) == kind:
                self._selected_plan_target_kind = None
                self._selected_plan_target_obj = None
            return
        self._selected_plan_target_kind = kind
        self._selected_plan_target_obj = obj

    def _get_selected_plan_target_state(self):
        kind = getattr(self, "_selected_plan_target_kind", None)
        obj = getattr(self, "_selected_plan_target_obj", None)
        if kind not in _PRIMARY_PLAN_TARGET_KINDS or obj is None:
            return (None, None)
        return (kind, obj)

    def _set_selected_plan_target_state(self, kind=None, obj=None):
        if kind not in _PRIMARY_PLAN_TARGET_KINDS or obj is None:
            kind = None
            obj = None
        self._selected_plan_target_kind = kind
        self._selected_plan_target_obj = obj

    def _get_selected_plan_target_object(self, kind=None):
        selected_kind, selected_obj = self._get_selected_plan_target()
        if kind is not None and selected_kind != kind:
            return None
        return selected_obj

    def _is_selected_plan_target(self, kind, obj=None):
        selected_kind, selected_obj = self._get_selected_plan_target()
        if selected_kind != kind:
            return False
        if obj is None:
            return selected_obj is not None
        return selected_obj == obj

    def _clear_selected_plan_target_if_matches(self, kind, obj):
        if not self._is_selected_plan_target(kind, obj):
            return False
        self._set_selected_plan_target_state()
        return True

    def _get_plan_target_object_from_state(self, state_kind, state_obj, kind):
        if state_kind == kind:
            return state_obj
        return None

    def _selected_plan_target_changed(self, previous_kind, previous_obj, kind=None):
        current_kind, current_obj = self._get_selected_plan_target()
        if kind is None:
            return previous_kind != current_kind or previous_obj != current_obj
        previous_target = self._get_plan_target_object_from_state(previous_kind, previous_obj, kind)
        current_target = self._get_plan_target_object_from_state(current_kind, current_obj, kind)
        return previous_target != current_target

    @property
    def selected_wall(self):
        return self._get_selected_target_for_kind("wall")

    @selected_wall.setter
    def selected_wall(self, wall):
        self._set_selected_target_for_kind("wall", wall)

    @property
    def selected_opening(self):
        return self._get_selected_target_for_kind("opening")

    @selected_opening.setter
    def selected_opening(self, opening):
        self._set_selected_target_for_kind("opening", opening)

    @property
    def selected_symbol(self):
        return self._get_selected_target_for_kind("symbol")

    @selected_symbol.setter
    def selected_symbol(self, symbol):
        self._set_selected_target_for_kind("symbol", symbol)

    @property
    def selected_region(self):
        return self._get_selected_target_for_kind("region")

    @selected_region.setter
    def selected_region(self, region):
        self._set_selected_target_for_kind("region", region)

    @property
    def selected_space(self):
        return self._get_selected_target_for_kind("space")

    @selected_space.setter
    def selected_space(self, space):
        self._set_selected_target_for_kind("space", space)

    def _discard_stale_runtime_object(self, obj):
        if obj is self.view:
            self.view = None
            self.viewer = None
        elif obj is self.viewer:
            self.viewer = None

    def _get_runtime_attr(self, obj, attr_name):
        if obj is None:
            return None
        try:
            return getattr(obj, attr_name)
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(obj)
            return None

    def _is_live_document_object(self, obj):
        if obj is None:
            return False
        try:
            _ = obj.Name
            return True
        except (AttributeError, ReferenceError, RuntimeError):
            return False

    def _get_document_object_key(self, obj):
        if obj is None:
            return None
        try:
            return (
                getattr(getattr(obj, "Document", None), "Name", None),
                getattr(obj, "Name", None),
            )
        except Exception:
            return None

    def _get_plan_overlay_geometry_kinds_for_object(self, obj):
        semantic_obj = self._get_plan_semantic_object(obj)
        if self._is_plan_space_object(semantic_obj):
            return ("space",)
        if self._is_plan_region_object(semantic_obj):
            return ("region",)
        return ()

    def _get_plan_overlay_geometry_cache_entry(self, kind, obj, create=False):
        cache = self._plan_overlay_geometry_cache.get(str(kind or ""))
        semantic_obj = self._get_plan_semantic_object(obj)
        if cache is None or semantic_obj is None:
            return (None, None, None)
        key = self._get_document_object_key(semantic_obj)
        if key is None:
            return (semantic_obj, None, None)
        entry = cache.get(key)
        if entry is None and create:
            entry = {}
            cache[key] = entry
        return (semantic_obj, key, entry)

    def _invalidate_plan_overlay_geometry_cache(self, obj=None, kinds=None):
        target_kinds = tuple(kinds or ())
        if not target_kinds:
            if obj is None:
                target_kinds = tuple(self._plan_overlay_geometry_cache.keys())
            else:
                target_kinds = self._get_plan_overlay_geometry_kinds_for_object(obj)
        if not target_kinds:
            return
        if obj is None:
            for kind in target_kinds:
                cache = self._plan_overlay_geometry_cache.get(kind)
                if cache is not None:
                    cache.clear()
            self._invalidate_selected_space_overlay_cache()
            return
        semantic_obj, key, _entry = self._get_plan_overlay_geometry_cache_entry(
            target_kinds[0], obj, create=False
        )
        if key is None:
            return
        for kind in target_kinds:
            cache = self._plan_overlay_geometry_cache.get(kind)
            if cache is not None:
                cache.pop(key, None)
        if self._is_selected_plan_target("space", semantic_obj):
            self._invalidate_selected_space_overlay_cache()

    def _get_cached_plan_overlay_geometry(self, kind, obj, field_name, compute):
        semantic_obj, _key, entry = self._get_plan_overlay_geometry_cache_entry(
            kind, obj, create=True
        )
        if semantic_obj is None or entry is None:
            return ()
        if field_name in entry:
            self._plan_perf_count(f"{kind}_{field_name}_cache_hits")
            return entry[field_name]
        value = compute(semantic_obj)
        if field_name == "footprint_faces":
            value = tuple(value or ())
        elif field_name == "overlay_polylines":
            value = tuple(tuple(polyline or ()) for polyline in (value or ()))
        elif field_name == "overlay_segments":
            value = tuple(value or ())
        entry[field_name] = value
        return value

    def _sanitize_plan_target_references(self):
        changed = False
        for attr in (
            "selected_wall",
            "selected_opening",
            "selected_symbol",
            "selected_region",
            "selected_space",
            "hovered_wall",
            "hovered_opening",
            "hovered_symbol",
            "hovered_region",
            "hovered_space",
        ):
            obj = getattr(self, attr, None)
            if obj is None or self._is_live_document_object(obj):
                continue
            setattr(self, attr, None)
            changed = True
        normalized_secondary = self._normalize_plan_target_list(
            getattr(self, "_secondary_selected_plan_targets_state", [])
        )
        if normalized_secondary != getattr(self, "_secondary_selected_plan_targets_state", []):
            self._secondary_selected_plan_targets_state = normalized_secondary
            changed = True
        return changed

    def _resolve_plan_perf_log_path(self):
        pref_enabled = False
        try:
            pref_enabled = bool(self._plan_edit_params.GetBool("PerfTrace", False))
        except Exception:
            pref_enabled = False

        env_value = str(os.environ.get("FC_BIM_PLAN_EDIT_PERF", "") or "").strip()
        env_log_path = str(os.environ.get("FC_BIM_PLAN_EDIT_PERF_LOG", "") or "").strip()
        false_values = {"0", "false", "False", "no", "off"}
        true_values = {"1", "true", "True", "yes", "on"}

        if env_value:
            if env_value in false_values:
                return None
            if env_value in true_values:
                return env_log_path or os.path.join(
                    tempfile.gettempdir(), f"bim_plan_edit_perf_{os.getpid()}.jsonl"
                )
            return env_value

        if env_log_path:
            return env_log_path
        if pref_enabled:
            return os.path.join(tempfile.gettempdir(), f"bim_plan_edit_perf_{os.getpid()}.jsonl")
        return None

    def _is_plan_perf_trace_enabled(self):
        return bool(self._plan_perf_log_path)

    def _plan_perf_describe_object(self, obj):
        if not obj:
            return None
        try:
            document = getattr(getattr(obj, "Document", None), "Name", None)
            name = getattr(obj, "Name", None)
            label = getattr(obj, "Label", None)
        except Exception:
            return repr(obj)
        result = {}
        if document:
            result["document"] = document
        if name:
            result["name"] = name
        if label and label != name:
            result["label"] = label
        return result or repr(obj)

    def _plan_perf_describe_target(self, kind, obj):
        if not kind or not obj:
            return None
        result = {"kind": kind}
        described = self._plan_perf_describe_object(obj)
        if isinstance(described, dict):
            result.update(described)
        elif described is not None:
            result["value"] = described
        return result

    def _plan_perf_coerce_value(self, value):
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._plan_perf_coerce_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._plan_perf_coerce_value(item) for key, item in value.items()}
        described = self._plan_perf_describe_object(value)
        if described is not None:
            return described
        return repr(value)

    def _plan_perf_set_fields(self, **fields):
        event = self._plan_perf_current_event
        if not event:
            return
        event_fields = event.setdefault("fields", {})
        for key, value in fields.items():
            if value is None:
                continue
            event_fields[str(key)] = self._plan_perf_coerce_value(value)

    def _plan_perf_count(self, name, delta=1):
        event = self._plan_perf_current_event
        if not event:
            return
        counts = event.setdefault("counts", {})
        counts[str(name)] = counts.get(str(name), 0) + delta

    def _plan_perf_note_error(self, scope, exc):
        event = self._plan_perf_current_event
        if not event:
            return
        errors = event.setdefault("errors", [])
        errors.append({"scope": str(scope), "message": repr(exc)})

    def _plan_perf_finalize_event(self, event, total_ms):
        output = {
            "event": event.get("event"),
            "seq": event.get("seq"),
            "pid": event.get("pid"),
            "ts_unix": round(float(event.get("ts_unix", 0.0)), 6),
            "total_ms": round(float(total_ms), 3),
            "tool": event.get("tool"),
            "fields": event.get("fields", {}),
            "counts": event.get("counts", {}),
            "spans": {
                name: {
                    "ms": round(float(data.get("ms", 0.0)), 3),
                    "count": int(data.get("count", 0)),
                }
                for name, data in event.get("spans", {}).items()
            },
        }
        if event.get("errors"):
            output["errors"] = list(event["errors"])
        return output

    def _plan_perf_write_event(self, event, total_ms):
        if not self._is_plan_perf_trace_enabled():
            return
        try:
            directory = os.path.dirname(self._plan_perf_log_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self._plan_perf_log_path, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(self._plan_perf_finalize_event(event, total_ms), sort_keys=True)
                )
                handle.write("\n")
        except Exception:
            pass

    @contextmanager
    def _plan_perf_trace_event(self, name, **fields):
        if not self._is_plan_perf_trace_enabled():
            yield None
            return
        if self._plan_perf_current_event is not None:
            with self._plan_perf_trace_span(name, **fields):
                yield self._plan_perf_current_event
            return
        self._plan_perf_sequence += 1
        event = {
            "event": str(name),
            "seq": self._plan_perf_sequence,
            "pid": os.getpid(),
            "ts_unix": time.time(),
            "tool": self.current_tool,
            "fields": {},
            "counts": {},
            "spans": {},
        }
        previous_event = self._plan_perf_current_event
        self._plan_perf_current_event = event
        self._plan_perf_set_fields(**fields)
        start_time = time.perf_counter()
        try:
            yield event
        except Exception as exc:
            self._plan_perf_note_error(name, exc)
            raise
        finally:
            total_ms = (time.perf_counter() - start_time) * 1000.0
            event["tool"] = self.current_tool
            self._plan_perf_write_event(event, total_ms)
            self._plan_perf_current_event = previous_event

    @contextmanager
    def _plan_perf_trace_span(self, name, **fields):
        event = self._plan_perf_current_event
        if event is None:
            yield None
            return
        self._plan_perf_set_fields(**fields)
        start_time = time.perf_counter()
        try:
            yield event
        except Exception as exc:
            self._plan_perf_note_error(name, exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            spans = event.setdefault("spans", {})
            span = spans.setdefault(str(name), {"ms": 0.0, "count": 0})
            span["ms"] += elapsed_ms
            span["count"] += 1

    def enter(self):
        if not self.doc or not self.gui_doc:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "An active document and 3D view are required.\n")
            )
            return False

        self.view = self.gui_doc.ActiveView
        get_viewer = self._get_runtime_attr(self.view, "getViewer")
        if self.view is None or get_viewer is None:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False

        try:
            self.viewer = get_viewer()
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(self.view)
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Plan Edit requires an active 3D Inventor view.\n")
            )
            return False
        self._capture_state()

        self.storeys = self.collect_storeys()
        self.active_storey = self.find_initial_storey()
        self._capture_object_view_state()
        self.apply_plan_view()
        self._apply_plan_snap_profile()
        self._apply_storey_visibility()
        self._attach_selection_observer()
        self._attach_document_observer()
        self._register_edit_callbacks()
        self._refresh_primary_selected_plan_target()

        panel = PlanEditControlsWidget(self)
        self.attach_task_panel(panel)
        panel.refresh()
        if self._is_plan_perf_trace_enabled():
            FreeCAD.Console.PrintMessage(
                translate("BIM_PlanEdit", "BIM Plan Edit perf trace: {path}\n").format(
                    path=self._plan_perf_log_path
                )
            )
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Entered BIM Plan Edit mode.\n"))
        return True

    def finish(self, cont=False, close_dialog=True, closed=False):
        del cont, closed
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return True
        if self.current_tool == "Pick Space Region":
            self._cancel_space_region_pick()
            return True
        if self.current_tool == "Region":
            self._cancel_plan_region_tool()
            return True
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
            return True
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
        self._clear_viewport_status_chip()
        self._clear_input_hints()
        self._cancel_embedded_tool()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_wall_edit(restore=False, refresh=False)
        self._cancel_pending_edit()
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
        if self.current_tool == "Set Space Text":
            self._edit_space = None
        if self.current_tool == "Pick Space Region":
            self._space_region_pick_boundaries = []
            self._space_region_candidates = []
            self._hovered_space_region_candidate = None
            self._space_region_pick_seed_space = None
        self._clear_hovered_wall_overlay()
        self._clear_junction_node_overlays()
        self._clear_hovered_wall_opening_context_overlay()
        self._clear_wall_grips()
        self._clear_hovered_opening_overlay()
        self._clear_hovered_symbol_overlay()
        self._clear_hovered_space_overlay()
        self._clear_hovered_region_overlay()
        self._clear_selected_opening_overlay()
        self._clear_selected_symbol_overlay()
        self._clear_selected_space_overlay()
        self._clear_selected_region_overlay()
        self._clear_space_region_pick_overlays()
        self._clear_secondary_selected_overlays()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_opening_handles()
        self._clear_selected_symbol_handles()
        self._clear_opening_move_preview()
        self._clear_symbol_edit_preview()
        self._clear_plan_region_preview()
        self._detach_selection_observer()
        self._detach_document_observer()
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
        self._clear_viewport_status_chip()
        self.doc = None
        self.gui_doc = None
        self.view = None
        self.viewer = None
        self._saved_navigation_style = None
        self._saved_navigation_state = {}
        self._saved_view_action_state = {}
        self._set_selected_plan_target_state()
        self._secondary_selected_plan_targets_state = []
        self.hovered_wall = None
        self.hovered_opening = None
        self.hovered_symbol = None
        self.hovered_space = None
        self.hovered_region = None
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._pending_selected_plan_target = None
        self._edit_wall = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._plan_region_points = []
        self._plan_region_parent_space = None
        self._edit_space = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._preview_points = None
        self._junction_node_trackers = []
        self._preview_footprint_trackers = []
        self._rect_wall_start = None
        self._rect_wall_params = None
        self._rect_wall_preview_trackers = []
        self._space_region_pick_trackers = []
        self._edit_wall_visibility = None
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None

    def _get_navigation_style(self):
        viewer = self.viewer
        get_navigation_style = self._get_runtime_attr(viewer, "getNavigationStyle")
        if get_navigation_style is None:
            return None
        try:
            return get_navigation_style()
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(viewer)
            return None

    def _get_main_window(self):
        try:
            return FreeCADGui.getMainWindow()
        except Exception:
            return None

    def _find_main_window_action(self, command_name):
        from PySide import QtGui

        main_window = self._get_main_window()
        if not main_window:
            return None
        try:
            return main_window.findChild(QtGui.QAction, command_name)
        except Exception:
            return None

    def _capture_view_action_state(self):
        for command_name in _PLAN_VIEW_LOCKED_ACTIONS:
            if command_name in self._saved_view_action_state:
                continue
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                self._saved_view_action_state[command_name] = bool(action.isEnabled())
            except Exception:
                pass

    def _apply_locked_view_actions(self):
        self._capture_view_action_state()
        for command_name in _PLAN_VIEW_LOCKED_ACTIONS:
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                action.setEnabled(False)
            except Exception:
                pass

    def _restore_locked_view_actions(self):
        for command_name, enabled in self._saved_view_action_state.items():
            action = self._find_main_window_action(command_name)
            if action is None:
                continue
            try:
                action.setEnabled(bool(enabled))
            except Exception:
                pass

    def _capture_navigation_flag(self, target, getter_name, state_key):
        if state_key in self._saved_navigation_state:
            return
        getter = self._get_runtime_attr(target, getter_name)
        if getter is None:
            return
        try:
            self._saved_navigation_state[state_key] = bool(getter())
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(target)
            pass

    def _apply_navigation_flag(self, target, setter_name, state_key, enabled):
        if state_key not in self._saved_navigation_state:
            return
        setter = self._get_runtime_attr(target, setter_name)
        if setter is None:
            return
        try:
            setter(enabled)
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(target)
            pass

    def _capture_navigation_state(self):
        nav_style = self._get_navigation_style()
        if nav_style:
            self._saved_navigation_style = nav_style
        self._capture_navigation_flag(nav_style, "isRotationEnabled", "rotation_enabled")
        self._capture_navigation_flag(nav_style, "isOrientationLocked", "orientation_locked")
        if self._get_runtime_attr(self.viewer, "setNaviCubeEnabledOverride") is None:
            self._capture_navigation_flag(self.viewer, "isEnabledNaviCube", "navicube_enabled")
        self._capture_navigation_flag(self.view, "isCornerCrossVisible", "corner_cross_visible")

    def _apply_plan_background_override(self):
        viewer = self.viewer
        set_background_override = self._get_runtime_attr(viewer, "setBackgroundAppearanceOverride")
        if set_background_override is None:
            return
        try:
            set_background_override(
                "NONE",
                _PLAN_PAPER_RGB,
                _PLAN_PAPER_RGB,
                _PLAN_PAPER_RGB,
            )
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(viewer)
            pass

    def _clear_plan_background_override(self):
        viewer = self.viewer
        clear_background_override = self._get_runtime_attr(
            viewer, "clearBackgroundAppearanceOverride"
        )
        if clear_background_override is None:
            return
        try:
            clear_background_override()
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(viewer)
            pass

    def _apply_plan_navigation_profile(self):
        self._capture_navigation_state()
        nav_style = self._saved_navigation_style or self._get_navigation_style()
        self._apply_navigation_flag(nav_style, "setRotationEnabled", "rotation_enabled", False)
        self._apply_navigation_flag(nav_style, "setOrientationLocked", "orientation_locked", True)
        set_navicube_override = self._get_runtime_attr(self.viewer, "setNaviCubeEnabledOverride")
        if set_navicube_override is not None:
            try:
                set_navicube_override(False)
            except (AttributeError, ReferenceError, RuntimeError):
                self._discard_stale_runtime_object(self.viewer)
                pass
        else:
            self._apply_navigation_flag(
                self.viewer, "setEnabledNaviCube", "navicube_enabled", False
            )
        self._apply_navigation_flag(
            self.view, "setCornerCrossVisible", "corner_cross_visible", False
        )
        self._apply_locked_view_actions()

    def _restore_navigation_state(self):
        nav_style = self._saved_navigation_style or self._get_navigation_style()
        self._apply_navigation_flag(
            nav_style,
            "setRotationEnabled",
            "rotation_enabled",
            self._saved_navigation_state.get("rotation_enabled"),
        )
        self._apply_navigation_flag(
            nav_style,
            "setOrientationLocked",
            "orientation_locked",
            self._saved_navigation_state.get("orientation_locked"),
        )
        clear_navicube_override = self._get_runtime_attr(
            self.viewer, "clearNaviCubeEnabledOverride"
        )
        if clear_navicube_override is not None:
            try:
                clear_navicube_override()
            except (AttributeError, ReferenceError, RuntimeError):
                self._discard_stale_runtime_object(self.viewer)
                pass
        else:
            self._apply_navigation_flag(
                self.viewer,
                "setEnabledNaviCube",
                "navicube_enabled",
                self._saved_navigation_state.get("navicube_enabled"),
            )
        self._apply_navigation_flag(
            self.view,
            "setCornerCrossVisible",
            "corner_cross_visible",
            self._saved_navigation_state.get("corner_cross_visible"),
        )
        self._restore_locked_view_actions()

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
            self._cancel_space_separator_tool(refresh=False)
            self._cancel_wall_edit(restore=not teardown, refresh=False)
            self._cancel_pending_edit()
            if self.current_tool in ("Move Symbol", "Rotate Symbol"):
                self._cancel_symbol_handle_point_pick()
            self._clear_viewport_status_chip()
            self._clear_input_hints()
            self._clear_hovered_wall_overlay()
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_wall_grips()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_opening_move_preview()
            self._clear_symbol_edit_preview()
            self._detach_selection_observer()
            self._detach_document_observer()
            self._unregister_edit_callbacks()
            if panel:
                try:
                    mark_closed = getattr(panel, "mark_closed", None)
                    if callable(mark_closed):
                        mark_closed()
                except Exception:
                    pass
                if close_dialog and not teardown:
                    try:
                        close = getattr(panel, "close", None)
                        if callable(close):
                            close()
                    except Exception:
                        pass
                else:
                    try:
                        detach = getattr(panel, "detach", None)
                        if callable(detach):
                            detach()
                    except Exception:
                        pass
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
            self._aux_task_panels = []
            _active_session = None
            self._finishing = False
            _refresh_contextual_task_watchers()
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
        self._sync_selected_wall_opening_context_overlay()
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
            self._sync_selected_wall_opening_context_overlay()
            self._refresh_task_panel_status()

    def activate_select_tool(self):
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return
        if self.current_tool == "Pick Space Region":
            self._cancel_space_region_pick()
            return
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
        if self._has_active_plan_region_tool():
            self._cancel_plan_region_tool()
        if self._has_active_space_separator_tool():
            self._cancel_space_separator_tool()
        self._cancel_wall_edit()
        self._cancel_join_tool()

    def activate_wall_tool(self):
        from bimcommands import BimWall

        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._set_gui_selection([])
        self._start_embedded_tool("Wall", BimWall.Arch_Wall(), host_class=_PlanEditWallHost)

    def activate_rect_wall_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
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

    def activate_plan_region_tool(self):
        parent_space = self._get_selected_plan_target_object("space")
        self._cancel_space_region_pick(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_region_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._clear_plan_region_preview()
        self._plan_region_points = []
        self._plan_region_parent_space = parent_space
        self.current_tool = "Region"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_plan_region_point,
            movecallback=self._update_plan_region_preview,
            title=translate("BIM_PlanEdit", "First region point"),
        )
        self._refresh_task_panel_status()

    def activate_space_separator_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._set_selected_plan_target()
        self._clear_wall_grips()
        self._clear_selected_wall_opening_context_overlay()
        self._clear_selected_space_overlay()
        self._clear_secondary_selected_overlays()
        self._clear_space_separator_preview()
        self._space_separator_start = None
        self._space_separator_height = self._get_wall_defaults()["height"]
        self.current_tool = "Separator"
        FreeCAD.activeDraftCommand = self
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_space_separator_point,
            title=translate("BIM_PlanEdit", "Separator start point"),
        )
        self._refresh_task_panel_status()

    def activate_space_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit(refresh=False)
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        return self._create_space_from_current_selection()

    def activate_move_tool(self):
        from draftguitools import gui_move

        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._start_embedded_tool("Move", gui_move.Move())

    def activate_join_tool(self):
        self._cancel_space_region_pick(refresh=False)
        self._cancel_plan_region_tool(refresh=False)
        self._cancel_rect_wall_tool(refresh=False)
        self._cancel_space_separator_tool(refresh=False)

        if self._has_active_embedded_tool():
            self._cancel_embedded_tool()
        self._cancel_wall_edit()
        self._cancel_pending_edit()
        self._clear_plan_relation_status()
        self._clear_wall_grips()
        self._set_hovered_opening(None)
        self._set_hovered_wall(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)

        wall = self._get_selected_plan_target_object("wall")
        if not self._is_plan_selectable_wall(wall):
            selection = []
            try:
                selection = FreeCADGui.Selection.getSelection()
            except (ReferenceError, RuntimeError):
                selection = []
            if len(selection) == 1 and self._is_plan_selectable_wall(selection[0]):
                wall = selection[0]

        if not self._is_plan_selectable_wall(wall):
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Select a wall before using Join.\n")
            )
            return

        self.current_tool = "Join"
        self._set_selected_plan_target("wall", wall)
        self._restore_gui_selection(wall)
        self._sync_secondary_selected_overlays()
        self._refresh_task_panel_status()

    def get_plan_join_type(self):
        return self._plan_join_type

    def get_plan_join_types(self):
        return _PLAN_JOIN_TYPES

    def _normalize_plan_join_type(self, join_type):
        if join_type in _PLAN_JOIN_TYPES:
            return join_type
        try:
            join_type = str(join_type)
        except Exception:
            return "Miter"
        if join_type in _PLAN_JOIN_TYPES:
            return join_type
        return "Miter"

    def get_plan_join_type_label(self, join_type=None):
        join_type = self._normalize_plan_join_type(join_type or self._plan_join_type)
        return {
            "Miter": translate("BIM_PlanEdit", "Miter"),
            "Butt": translate("BIM_PlanEdit", "Butt"),
            "Tee": translate("BIM_PlanEdit", "Tee"),
        }[join_type]

    def _get_plan_join_type_phrase(self, join_type=None):
        join_type = self._normalize_plan_join_type(join_type or self._plan_join_type)
        return {
            "Miter": translate("BIM_PlanEdit", "miter"),
            "Butt": translate("BIM_PlanEdit", "butt"),
            "Tee": translate("BIM_PlanEdit", "tee"),
        }[join_type]

    def _get_plan_join_action_text(self, join_type=None):
        return translate(
            "BIM_PlanEdit", "Click another wall to create a {joint_type} joint"
        ).format(joint_type=self._get_plan_join_type_phrase(join_type))

    def set_plan_join_type(self, join_type, refresh=True):
        join_type = self._normalize_plan_join_type(join_type)
        if self._plan_join_type == join_type:
            if refresh:
                self._refresh_task_panel_status()
            return False
        self._plan_join_type = join_type
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _cycle_plan_join_type(self):
        try:
            current_index = _PLAN_JOIN_TYPES.index(self._plan_join_type)
        except ValueError:
            current_index = 0
        next_join_type = _PLAN_JOIN_TYPES[(current_index + 1) % len(_PLAN_JOIN_TYPES)]
        self.set_plan_join_type(next_join_type)
        return True

    def _get_plan_join_command(self):
        from bimcommands.BimJoin import BIM_Join_Butt, BIM_Join_Miter, BIM_Join_Tee

        return {
            "Miter": BIM_Join_Miter,
            "Butt": BIM_Join_Butt,
            "Tee": BIM_Join_Tee,
        }.get(self._normalize_plan_join_type(self._plan_join_type), BIM_Join_Miter)()

    def _get_plan_join_candidate_wall(self):
        if self.current_tool != "Join":
            return None
        wall = self.hovered_wall
        if not self._is_plan_selectable_wall(wall) or self._is_selected_plan_target("wall", wall):
            return None
        return wall

    def _get_plan_candidate_joint(self, target_wall=None):
        import ArchWallJoinUtils

        source_wall = self._get_selected_plan_target_object("wall")
        target_wall = target_wall or self._get_plan_join_candidate_wall()
        if not self._is_plan_selectable_wall(source_wall):
            return None
        if not self._is_plan_selectable_wall(target_wall):
            return None
        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return None
        return ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)

    def _get_plan_join_candidate_state(self):
        target_wall = self._get_plan_join_candidate_wall()
        if not target_wall:
            return None, None, ""

        joint = self._get_plan_candidate_joint(target_wall)
        if not joint:
            return (
                target_wall,
                None,
                translate("BIM_PlanEdit", "Candidate wall: {label}").format(
                    label=target_wall.Label
                ),
            )

        summary = translate("BIM_PlanEdit", "Existing joint with {label}: {joint_type}").format(
            label=target_wall.Label,
            joint_type=self.get_plan_join_type_label(getattr(joint, "JointType", "Miter")),
        )
        status = getattr(joint, "Status", "")
        if status not in ("", "OK"):
            summary = translate("BIM_PlanEdit", "{summary} ({status})").format(
                summary=summary,
                status=status,
            )
        return target_wall, joint, summary

    def _get_plan_join_mode_action_text(self, target_wall=None, joint=None):
        target_wall = target_wall or self._get_plan_join_candidate_wall()
        joint = joint or self._get_plan_candidate_joint(target_wall)
        if joint:
            current_type = self._normalize_plan_join_type(getattr(joint, "JointType", "Miter"))
            if current_type == self._plan_join_type:
                return translate(
                    "BIM_PlanEdit",
                    "Press Delete to unjoin this pair, or Tab to choose a different joint type",
                )
            return translate(
                "BIM_PlanEdit",
                "Click wall to change it to a {joint_type} joint",
            ).format(joint_type=self._get_plan_join_type_phrase())
        if target_wall:
            return self._get_plan_join_action_text()
        return translate(
            "BIM_PlanEdit",
            "Hover another wall, then click to create a {joint_type} joint",
        ).format(joint_type=self._get_plan_join_type_phrase())

    def _unjoin_plan_wall_pair(self, source_wall, target_wall):
        import ArchWallJoinUtils

        if not self._is_plan_selectable_wall(source_wall):
            return False
        if not self._is_plan_selectable_wall(target_wall):
            return False

        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return False
        joint = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
        if not joint:
            return False

        doc.openTransaction(translate("BIM_PlanEdit", "Unjoin walls"))
        try:
            doc.removeObject(joint.Name)
            doc.commitTransaction()
            doc.recompute()
        except Exception:
            try:
                doc.abortTransaction()
            except Exception:
                pass
            return False

        self._clear_plan_relation_status()
        self._refresh_task_panel_status()
        return True

    def _unjoin_current_plan_wall_pair(self):
        source_wall = self._get_selected_plan_target_object("wall")
        target_wall = self._get_plan_join_candidate_wall()
        if not self._unjoin_plan_wall_pair(source_wall, target_wall):
            FreeCAD.Console.PrintWarning(
                translate("BIM_PlanEdit", "Hover a joined wall pair before using Unjoin.\n")
            )
            return False
        return True

    @staticmethod
    def _iter_unique_wall_sets(source_wall, target_wall, extra_walls):
        import itertools

        base = [source_wall, target_wall]
        extras = sorted(
            [wall for wall in extra_walls if wall not in base],
            key=lambda wall: getattr(wall, "Name", ""),
        )
        seen = set()
        for size in range(len(extras), 0, -1):
            for combo in itertools.combinations(extras, size):
                walls = base + list(combo)
                signature = tuple(sorted(getattr(wall, "Name", "") for wall in walls if wall))
                if signature in seen:
                    continue
                seen.add(signature)
                yield walls

    def _find_plan_junction_promotion(self, source_wall, target_wall):
        import ArchWallJoinUtils
        import ArchWallJunctionUtils

        if not self._is_plan_selectable_wall(source_wall):
            return None
        if not self._is_plan_selectable_wall(target_wall):
            return None

        candidate_walls = {
            getattr(source_wall, "Name", ""): source_wall,
            getattr(target_wall, "Name", ""): target_wall,
        }
        candidate_relations = []
        seen_relations = set()
        for wall in (source_wall, target_wall):
            for relation in ArchWallJoinUtils.iter_wall_relations(wall):
                relation_name = getattr(relation, "Name", None)
                if not relation_name or relation_name in seen_relations:
                    continue
                seen_relations.add(relation_name)
                candidate_relations.append(relation)
                for linked_wall in ArchWallJoinUtils.get_relation_walls(relation):
                    if self._is_plan_selectable_wall(linked_wall):
                        candidate_walls[getattr(linked_wall, "Name", "")] = linked_wall

        if len(candidate_walls) < 3:
            return None

        extra_walls = [
            wall
            for name, wall in candidate_walls.items()
            if wall not in (source_wall, target_wall) and name
        ]
        for walls in self._iter_unique_wall_sets(source_wall, target_wall, extra_walls):
            solution = ArchWallJunctionUtils.solve_wall_junction_inputs(walls)
            if solution.is_ok():
                return walls, solution, candidate_relations
        return None

    @staticmethod
    def _find_reusable_plan_junction(candidate_relations, walls):
        wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
        best_relation = None
        best_overlap = 0
        for relation in candidate_relations:
            if getattr(getattr(relation, "Proxy", None), "Type", None) != "WallJunction":
                continue
            relation_names = {
                getattr(wall, "Name", "")
                for wall in list(getattr(relation, "Walls", []) or [])
                if wall
            }
            overlap = len(wall_names.intersection(relation_names))
            if overlap > best_overlap:
                best_relation = relation
                best_overlap = overlap
        return best_relation if best_overlap >= 2 else None

    def _apply_plan_wall_junction_promotion(self, doc, source_wall, target_wall):
        import Arch
        import ArchWallJoinUtils

        promotion = self._find_plan_junction_promotion(source_wall, target_wall)
        if not promotion:
            return None

        walls, solution, candidate_relations = promotion
        wall_names = {getattr(wall, "Name", "") for wall in walls if wall}
        junction = self._find_reusable_plan_junction(candidate_relations, walls)

        for relation in candidate_relations:
            if not ArchWallJoinUtils.is_wall_joint(relation):
                continue
            relation_walls = {
                getattr(wall, "Name", "")
                for wall in ArchWallJoinUtils.get_relation_walls(relation)
                if wall
            }
            if relation_walls and relation_walls.issubset(wall_names):
                doc.removeObject(relation.Name)

        if junction:
            junction.Walls = list(walls)
            junction.CarrierMode = "Explicit"
            junction.CarrierWall = solution.carrier_wall
            junction.Enabled = True
            return junction

        return Arch.makeWallJunction(list(walls), carrier_wall=solution.carrier_wall)

    def stretch_selected_wall(self, endpoint):
        self._start_wall_edit(endpoint)

    def move_selected_wall(self):
        self._start_wall_edit("Move")

    def is_selected_wall_endpoint_editable(self):
        wall = self._get_selected_plan_target_object("wall")
        if not wall:
            return False
        proxy = getattr(wall, "Proxy", None)
        if not (hasattr(proxy, "calc_endpoints") and hasattr(proxy, "set_from_endpoints")):
            return False
        if not getattr(wall, "Base", None):
            return True
        try:
            import Arch

            return Arch.is_debasable(wall)
        except Exception:
            return False

    def is_selected_wall_baseless(self):
        wall = self._get_selected_plan_target_object("wall")
        if not wall:
            return False
        return not getattr(wall, "Base", None) and self.is_selected_wall_endpoint_editable()

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
                self._apply_plan_background_override()
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

        # Keep the live view decorations and navigation model constrained every
        # time the session reapplies the plan view, not just in helper tests.
        self._apply_plan_navigation_profile()

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
                self._clear_plan_background_override()
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

        # Restore the viewer/navigation decorations after the plan override is
        # fully unwound so the normal 3D state comes back coherently.
        self._restore_navigation_state()

    def _capture_state(self):
        import WorkingPlane

        get_camera = self._get_runtime_attr(self.view, "getCamera")
        if get_camera is not None:
            try:
                self._saved_camera = get_camera()
            except (AttributeError, ReferenceError, RuntimeError):
                self._discard_stale_runtime_object(self.view)
        get_camera_type = self._get_runtime_attr(self.view, "getCameraType")
        if get_camera_type is not None:
            try:
                self._saved_camera_type = get_camera_type()
            except (AttributeError, ReferenceError, RuntimeError):
                self._discard_stale_runtime_object(self.view)

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

    def _get_plan_view_height(self):
        get_camera_node = self._get_runtime_attr(self.view, "getCameraNode")
        if get_camera_node is None:
            return None
        try:
            camera = get_camera_node()
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(self.view)
            return None
        try:
            height_prop = getattr(camera, "height")
        except (AttributeError, ReferenceError, RuntimeError):
            return None
        try:
            return float(height_prop.getValue())
        except Exception:
            return None

    def _get_plan_overlay_scale(self):
        height = self._get_plan_view_height()
        if not height or height <= 0:
            return 1.0
        if height <= 5000.0:
            return 1.0
        if height >= 30000.0:
            return 0.35
        scale = 5000.0 / height
        return max(0.35, min(1.0, scale * 2.0))

    def _scaled_line_width(self, base_width):
        return max(1.0, base_width * self._get_plan_overlay_scale())

    def _scaled_marker_size(self, base_size):
        return max(4, int(round(base_size * self._get_plan_overlay_scale())))

    def _get_plan_view_units_per_pixel(self):
        height = self._get_plan_view_height()
        get_size = self._get_runtime_attr(self.view, "getSize")
        if not height or height <= 0 or get_size is None:
            return None
        try:
            view_height = float(get_size()[1])
        except Exception:
            return None
        if view_height <= 0:
            return None
        return height / view_height

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

    def _push_opening_move_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if (
            self._opening_move_snap_profile_pushed
            or not snapper
            or not hasattr(snapper, "push_snap_modes")
        ):
            return
        try:
            snapper.push_snap_modes(_OPENING_MOVE_SNAP_SET)
            self._opening_move_snap_profile_pushed = True
        except Exception:
            pass

    def _pop_opening_move_snap_profile(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if (
            not self._opening_move_snap_profile_pushed
            or not snapper
            or not hasattr(snapper, "pop_snap_modes")
        ):
            return
        try:
            snapper.pop_snap_modes()
        except Exception:
            pass
        self._opening_move_snap_profile_pushed = False

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
        self._refresh_plan_object_footprint_display(obj)
        self._request_view_redraw()

    def _is_direct_plan_equipment_object(self, obj):
        if not obj:
            return False
        try:
            import Draft

            if Draft.getType(obj) == "Equipment":
                return True
        except Exception:
            pass
        proxy = getattr(obj, "Proxy", None)
        return getattr(proxy, "Type", None) == "Equipment"

    def _get_direct_plan_symbol_owner(self, obj):
        if not obj:
            return None
        for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
            if not self._is_direct_plan_equipment_object(parent):
                continue
            if obj == getattr(parent, "Base", None):
                return parent
            if obj in (getattr(parent, "PlanSymbols", None) or []):
                return parent
        return None

    def _get_plan_semantic_object(self, obj):
        current = obj
        seen = set()
        while current:
            if not self._is_live_document_object(current):
                current = None
                break
            name = getattr(current, "Name", None)
            if name in seen:
                break
            if name:
                seen.add(name)
            if getattr(current, "TypeId", "") != "App::Link":
                break
            linked = getattr(current, "LinkedObject", None)
            if linked is None and hasattr(current, "getLinkedObject"):
                try:
                    linked = current.getLinkedObject(True)
                except TypeError:
                    try:
                        linked = current.getLinkedObject()
                    except Exception:
                        linked = None
                except Exception:
                    linked = None
            if not linked or linked == current:
                break
            current = linked
        owner = self._get_direct_plan_symbol_owner(current)
        return owner or current or obj

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

    def _is_plan_container_object(self, obj):
        if not obj:
            return False
        if getattr(obj, "IfcType", "") in {"Site", "Building", "Building Storey"}:
            return True
        if hasattr(obj, "isDerivedFrom") and obj.isDerivedFrom("App::DocumentObjectGroup"):
            return True
        if hasattr(obj, "hasExtension") and obj.hasExtension("App::GroupExtension"):
            return True
        try:
            import Draft

            return Draft.getType(obj) in {
                "Site",
                "Building",
                "Floor",
                "BuildingPart",
                "Group",
            }
        except Exception:
            return False

    def _is_plan_background_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        if getattr(obj, "IfcType", "") == "Slab":
            return True
        try:
            import Draft

            return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
        except Exception:
            return False

    def _is_plan_equipment_object(self, obj):
        if not obj:
            return False
        return self._is_direct_plan_equipment_object(self._get_plan_semantic_object(obj))

    def _has_direct_plan_symbols(self, obj):
        if not obj:
            return False
        try:
            if "PlanSymbols" not in (getattr(obj, "PropertiesList", []) or []):
                return False
            return any(symbol is not None for symbol in (getattr(obj, "PlanSymbols", []) or []))
        except Exception:
            return False

    def _is_plan_symbol_instance(self, obj):
        if not obj:
            return False
        if self._is_hidden_library_definition_object(obj):
            return False
        if not self._is_plan_equipment_object(obj):
            return False
        if getattr(obj, "TypeId", "") == "App::Link":
            return True
        semantic_obj = self._get_plan_semantic_object(obj)
        return obj == semantic_obj and self._has_direct_plan_symbols(semantic_obj)

    def _is_plan_context_only_object(self, obj):
        if not obj:
            return False
        if self._is_plan_symbol_instance(obj):
            return False
        return (
            self._is_plan_container_object(obj)
            or self._is_plan_background_object(obj)
            or self._is_plan_equipment_object(obj)
        )

    def _is_component_addition_object(self, obj):
        if not obj:
            return False
        for parent in getattr(obj, "InList", []) or []:
            try:
                if obj in getattr(parent, "Additions", []):
                    return True
            except Exception:
                pass
        return False

    def _is_supported_plan_object(self, obj):
        if not obj:
            return False
        if self._is_plan_symbol_instance(obj):
            return True
        if self._is_plan_region_object(obj):
            return True
        if self._is_plan_space_separator_object(obj):
            return True
        if self._is_plan_context_only_object(obj):
            return True
        semantic_obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            obj_type = Draft.getType(semantic_obj)
        except Exception:
            obj_type = ""

        if obj_type in {"Wall", "Window", "Space", "Axis", "AxisSystem"}:
            return True

        if getattr(semantic_obj, "IfcType", "") in {
            "Wall",
            "Window",
            "Door",
            "Space",
            "Column",
            "Grid",
            "Stair",
            "Curtain Wall",
        }:
            return True

        return False

    def _is_hosted_opening_object(self, obj):
        if not obj:
            return False
        semantic_obj = self._get_plan_semantic_object(obj)
        if not getattr(semantic_obj, "Hosts", None):
            return False

        if getattr(semantic_obj, "IfcType", "") in {"Window", "Door"}:
            return True

        try:
            import Draft

            return Draft.getType(semantic_obj) == "Window"
        except Exception:
            return False

    def _get_supported_plan_visibility(self, obj, state):
        if self._is_component_addition_object(obj):
            return False
        visibility = state.get("Visibility", True)
        # Hosted openings are commonly hidden in the regular 3D workflow while
        # their wall cuts carry the main visual meaning. In Plan Edit we want
        # their committed footprint symbols to be visible whenever they are a
        # supported plan object.
        if self._is_hosted_opening_object(obj):
            return True
        return visibility

    def _apply_context_object_selectability(self, obj, view_object):
        if not view_object or not hasattr(view_object, "Selectable"):
            return
        semantic_obj = self._get_plan_semantic_object(obj)
        if semantic_obj is not None and self._is_symbol_visual_dependency(semantic_obj, obj):
            try:
                view_object.Selectable = True
            except Exception:
                pass
            return
        # Spaces and plan regions are selected through Plan Edit's semantic
        # picking paths. Leaving their native 3D view objects selectable lets
        # the viewer replace the intended target with enclosing face hits on
        # button release, especially for nested region-in-space cases.
        if self._is_plan_custom_pick_only_object(semantic_obj or obj):
            try:
                view_object.Selectable = False
            except Exception:
                pass
            return
        if not self._is_plan_context_only_object(obj):
            return
        try:
            view_object.Selectable = False
        except Exception:
            pass

    def _apply_hidden_object_state(self, view_object):
        if not view_object:
            return
        if hasattr(view_object, "Visibility"):
            try:
                view_object.Visibility = False
            except Exception:
                pass
        if hasattr(view_object, "Selectable"):
            try:
                view_object.Selectable = False
            except Exception:
                pass

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
            for obj in self.doc.Objects:
                view_object = getattr(obj, "ViewObject", None)
                state = self._saved_object_view_state.get(obj.Name, {})
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                if view_object and hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_context_object_selectability(obj, view_object)
            return

        for obj in self.doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            state = self._saved_object_view_state.get(obj.Name)
            if not view_object or not state:
                continue

            storeys = self._get_object_storeys(obj)
            if not storeys:
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_context_object_selectability(obj, view_object)
                continue

            belongs_to_active = any(parent.Name == active_storey_name for parent in storeys)
            if belongs_to_active:
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if not self._is_supported_plan_object(obj):
                    self._apply_hidden_object_state(view_object)
                    continue
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = self._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                self._apply_context_object_selectability(obj, view_object)
                continue

            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = self._get_supported_plan_visibility(obj, state)
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
        try:
            self.view.setActiveObject("Arch", None)
        except Exception:
            pass
        try:
            self.view.setActiveObject("NativeIFC", None)
        except Exception:
            pass
        if obj is None:
            return
        context = "Arch"
        if getattr(obj, "IfcType", "") == "Building Storey":
            context = "NativeIFC"
        try:
            self.view.setActiveObject(context, obj)
        except Exception:
            pass

    def _sync_active_plan_target_object(self):
        if not self.view:
            return
        target_kind, target_obj = self._get_selected_plan_target()
        del target_kind
        if target_obj is not None:
            self._set_active_object(target_obj)
            return
        if self.active_storey is not None:
            self._set_active_object(self.active_storey)
            return
        self._set_active_object(None)

    def _attach_selection_observer(self):
        if not self._selection_observer_added:
            FreeCADGui.Selection.addObserver(self)
            self._selection_observer_added = True

    def _detach_selection_observer(self):
        if self._selection_observer_added:
            FreeCADGui.Selection.removeObserver(self)
            self._selection_observer_added = False

    def _attach_document_observer(self):
        if not self._document_observer_added:
            FreeCAD.addDocumentObserver(self)
            self._document_observer_added = True

    def _detach_document_observer(self):
        if self._document_observer_added:
            try:
                FreeCAD.removeDocumentObserver(self)
            except Exception:
                pass
            self._document_observer_added = False

    def _is_plan_selectable_wall(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            return Draft.getType(obj) == "Wall"
        except Exception:
            return False

    def _is_plan_space_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            if Draft.getType(obj) == "Space":
                return True
        except Exception:
            pass
        return getattr(obj, "IfcType", "") == "Space"

    def _is_plan_custom_pick_only_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        return self._is_plan_space_object(obj) or self._is_plan_region_object(obj)

    def _is_plan_space_separator_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            return Draft.getType(obj) == "SpaceSeparator"
        except Exception:
            return False

    def _is_plan_region_object(self, obj):
        if not obj:
            return False
        obj = self._get_plan_semantic_object(obj)
        try:
            import Draft

            return Draft.getType(obj) == "PlanRegion"
        except Exception:
            return False

    def _get_gui_selection_ex(self):
        try:
            return list(FreeCADGui.Selection.getSelectionEx() or [])
        except (ReferenceError, RuntimeError):
            return []

    def _get_gui_selection(self):
        try:
            return list(FreeCADGui.Selection.getSelection() or [])
        except (ReferenceError, RuntimeError):
            return []

    def _get_space_reference_point(self, space):
        if not self._is_plan_space_object(space):
            return None
        shape = getattr(space, "Shape", None)
        if shape and hasattr(shape, "CenterOfMass"):
            try:
                return self._project_plan_point(shape.CenterOfMass)
            except Exception:
                pass
        placement = getattr(space, "Placement", None)
        if placement is not None:
            try:
                return self._project_plan_point(placement.Base)
            except Exception:
                pass
        return None

    def _get_space_boundary_reference_point(self, selection_ex, fallback_space=None):
        points = []
        for selection in selection_ex or []:
            obj = getattr(selection, "Object", None)
            if not obj or obj == fallback_space:
                continue
            subobjects = list(getattr(selection, "SubObjects", []) or [])
            added_subobject_center = False
            for subobject in subobjects:
                center = getattr(subobject, "CenterOfMass", None)
                if center is None:
                    continue
                try:
                    points.append(FreeCAD.Vector(center.x, center.y, center.z))
                    added_subobject_center = True
                except Exception:
                    continue
            if added_subobject_center:
                continue
            shape = getattr(obj, "Shape", None)
            bound_box = getattr(shape, "BoundBox", None)
            center = getattr(bound_box, "Center", None) if bound_box is not None else None
            if center is None:
                continue
            try:
                points.append(FreeCAD.Vector(center.x, center.y, center.z))
            except Exception:
                continue
        if points:
            total = FreeCAD.Vector()
            for point in points:
                total = total.add(point)
            return total.multiply(1.0 / float(len(points)))
        return self._get_space_reference_point(fallback_space)

    def _get_space_boundary_entries(self, space):
        if not self._is_plan_space_object(space):
            return []
        import ArchSpace

        entries = []
        for boundary in getattr(space, "Boundaries", []) or []:
            try:
                obj = boundary[0]
                subnames = boundary[1]
            except Exception:
                continue
            entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
        return ArchSpace.normalizeBoundaryLinks(entries)

    def _space_boundary_key(self, boundary):
        import ArchSpace

        obj, subnames = boundary
        return (
            getattr(obj, "Name", None),
            tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
        )

    def _get_selected_space_boundary_links(self, fallback_space=None):
        import ArchSpace

        selection_ex = self._get_gui_selection_ex()
        reference_point = (
            self._get_space_reference_point(fallback_space)
            if fallback_space is not None
            else self._get_space_boundary_reference_point(selection_ex)
        )
        entries = []
        for selection in selection_ex:
            obj = self._get_plan_semantic_object(getattr(selection, "Object", None))
            if not obj:
                continue
            entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
        return ArchSpace.resolveBoundaryLinks(
            entries,
            reference_point=reference_point,
            exclude_objects=(fallback_space,) if fallback_space is not None else None,
        )

    def _get_space_region_seed_targets(self, targets=None):
        targets = list(targets if targets is not None else self._get_selected_plan_targets())
        if not targets:
            return (None, [])

        space_targets = [
            target_obj for target_kind, target_obj in targets if target_kind == "space"
        ]
        if len(space_targets) != 1:
            return (None, [])

        if len(targets) == 1:
            boundary_links = self._get_selected_space_boundary_links(
                fallback_space=space_targets[0]
            )
            if boundary_links:
                return (space_targets[0], [])
            return (None, [])

        wall_targets = [
            (target_kind, target_obj)
            for target_kind, target_obj in targets
            if target_kind == "wall"
        ]
        if len(wall_targets) != len(targets) - 1:
            return (None, [])

        return (space_targets[0], wall_targets)

    def _get_selected_space_region_seed(self, targets=None):
        region_seed_space, _wall_targets = self._get_space_region_seed_targets(targets)
        return region_seed_space

    def _copy_shape_without_element_map(self, shape):
        if shape is None:
            return None
        try:
            return shape.copy(noElementMap=True)
        except TypeError:
            try:
                clean_shape = shape.copy()
                if getattr(clean_shape, "ElementMapSize", 0):
                    clean_shape.clearElementMap()
                return clean_shape
            except Exception:
                return shape
        except Exception:
            return shape

    def _get_space_creation_request(self, targets=None):
        targets = targets if targets is not None else self._get_selected_plan_targets()
        if not targets:
            return None

        label = None
        region_seed_space = self._get_selected_space_region_seed(targets)
        if region_seed_space is not None:
            boundaries = self._get_selected_space_boundary_links(fallback_space=region_seed_space)
            label = getattr(region_seed_space, "Label", None)
        elif all(target_kind == "wall" for target_kind, _target_obj in targets):
            boundaries = self._get_selected_space_boundary_links()
        else:
            return None

        return {
            "targets": targets,
            "label": label,
            "region_seed_space": region_seed_space,
            "boundaries": boundaries,
        }

    def _get_existing_space_region_filter_spaces(self, exclude=None):
        if not self.doc:
            return []
        active_storey_name = getattr(self.active_storey, "Name", None)
        exclude_space = self._get_plan_semantic_object(exclude) if exclude else None
        exclude_name = getattr(exclude_space, "Name", None)

        spaces = []
        seen = set()
        for obj in self.doc.Objects:
            semantic_obj = self._get_plan_semantic_object(obj)
            name = getattr(semantic_obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            if name == exclude_name or not self._is_plan_space_object(semantic_obj):
                continue
            if active_storey_name is not None:
                storeys = self._get_object_storeys(semantic_obj)
                if storeys and not any(parent.Name == active_storey_name for parent in storeys):
                    continue
            spaces.append(semantic_obj)
        return spaces

    def _get_xy_bound_box_iou(self, first_shape, second_shape):
        first_bb = getattr(first_shape, "BoundBox", None)
        second_bb = getattr(second_shape, "BoundBox", None)
        if first_bb is None or second_bb is None:
            return 0.0

        x_overlap = min(float(first_bb.XMax), float(second_bb.XMax)) - max(
            float(first_bb.XMin), float(second_bb.XMin)
        )
        y_overlap = min(float(first_bb.YMax), float(second_bb.YMax)) - max(
            float(first_bb.YMin), float(second_bb.YMin)
        )
        if x_overlap <= 0.000001 or y_overlap <= 0.000001:
            return 0.0

        intersection_area = x_overlap * y_overlap
        first_area = max(
            0.0,
            (float(first_bb.XMax) - float(first_bb.XMin))
            * (float(first_bb.YMax) - float(first_bb.YMin)),
        )
        second_area = max(
            0.0,
            (float(second_bb.XMax) - float(second_bb.XMin))
            * (float(second_bb.YMax) - float(second_bb.YMin)),
        )
        union_area = first_area + second_area - intersection_area
        if union_area <= 0.000001:
            return 0.0
        return intersection_area / union_area

    def _is_space_region_candidate_claimed(self, candidate, spaces, overlap_iou_tolerance=0.9):
        if not isinstance(candidate, dict):
            return False
        candidate_face = candidate.get("face")
        sample_point = candidate.get("sample_point")
        if candidate_face is None or sample_point is None:
            return False

        for space in spaces or []:
            footprint_faces = self._get_space_footprint_faces(space)
            if not footprint_faces:
                continue
            for footprint_face in footprint_faces:
                try:
                    test_point = FreeCAD.Vector(
                        sample_point.x,
                        sample_point.y,
                        float(footprint_face.BoundBox.ZMin),
                    )
                    if not footprint_face.isInside(test_point, 0.001, True):
                        continue
                except Exception:
                    continue
                if self._get_xy_bound_box_iou(
                    candidate_face,
                    footprint_face,
                ) >= float(overlap_iou_tolerance):
                    return True
        return False

    def _filter_claimed_space_region_candidates(self, candidates, exclude_space=None):
        candidates = list(candidates or [])
        if not candidates:
            return candidates, 0

        spaces = self._get_existing_space_region_filter_spaces(exclude=exclude_space)
        if not spaces:
            return candidates, 0

        filtered = []
        skipped = 0
        for candidate in candidates:
            if self._is_space_region_candidate_claimed(candidate, spaces):
                skipped += 1
                continue
            filtered.append(candidate)
        return filtered, skipped

    def _get_space_region_candidate_report(
        self,
        boundaries,
        label=None,
        seed_space=None,
    ):
        import ArchSpace

        report = ArchSpace.getBoundaryRegionCandidates(
            boundaries,
            label=label,
            seed_space=seed_space,
        )
        report = dict(report or {})
        candidates = list(report.get("candidates", []) or [])
        skipped_claimed = 0
        if seed_space is None:
            candidates, skipped_claimed = self._filter_claimed_space_region_candidates(candidates)
        report["candidates"] = candidates
        report["candidate_count"] = len(candidates)
        report["skipped_claimed_candidate_count"] = skipped_claimed
        return report

    def _report_space_region_candidate_failure(self, report):
        skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
        if skipped_claimed and not int(report.get("candidate_count", 0) or 0):
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "All enclosed regions are already covered by existing spaces.\n",
                )
            )
            return

        message = str(report.get("message") or "").strip()
        details = [
            str(detail).strip() for detail in report.get("details", []) if str(detail).strip()
        ]
        if message:
            FreeCAD.Console.PrintError(message + "\n")
            for detail in details:
                FreeCAD.Console.PrintError(f"  - {detail}\n")
            return

        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Failed to derive enclosed space regions from the current selection.\n",
            )
        )

    def _get_plan_target_kind_for_object(self, obj):
        if self._is_hosted_opening_object(obj):
            return "opening"
        if self._is_plan_symbol_instance(obj):
            return "symbol"
        if self._is_plan_region_object(obj):
            return "region"
        if self._is_plan_selectable_wall(obj):
            return "wall"
        if self._is_plan_space_object(obj):
            return "space"
        return None

    def _get_plan_target_for_object(self, obj, parent_obj=None):
        seen = set()
        for candidate in (obj, parent_obj):
            if not candidate:
                continue
            name = getattr(candidate, "Name", None)
            if name and name in seen:
                continue
            if name:
                seen.add(name)
            target_kind = self._get_plan_target_kind_for_object(candidate)
            if target_kind:
                return (target_kind, candidate)

        semantic_obj = self._get_plan_semantic_object(obj)
        semantic_name = getattr(semantic_obj, "Name", None)
        if semantic_obj and semantic_name not in seen:
            target_kind = self._get_plan_target_kind_for_object(semantic_obj)
            if target_kind:
                return (target_kind, semantic_obj)

        return (None, None)

    def _get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        if not self.view or not mouse_pos:
            return None
        try:
            cursor_x = float(mouse_pos[0])
            cursor_y = float(mouse_pos[1])
            start_x, start_y = self.view.getPointOnScreen(start)
            end_x, end_y = self.view.getPointOnScreen(end)
        except Exception:
            return None

        start_x = float(start_x)
        start_y = float(start_y)
        end_x = float(end_x)
        end_y = float(end_y)
        dx = end_x - start_x
        dy = end_y - start_y
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            proj_x = start_x
            proj_y = start_y
        else:
            t = ((cursor_x - start_x) * dx + (cursor_y - start_y) * dy) / length_sq
            t = max(0.0, min(1.0, t))
            proj_x = start_x + t * dx
            proj_y = start_y + t * dy
        offset_x = proj_x - cursor_x
        offset_y = proj_y - cursor_y
        return offset_x * offset_x + offset_y * offset_y

    def _pick_plan_symbol_target_from_overlays(self, mouse_pos, radius_px=10):
        if not self.doc or not self.view or not mouse_pos:
            return None
        radius_sq = float(radius_px) * float(radius_px)
        best_symbol = None
        best_distance_sq = None
        seen = set()
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_plan_symbol_instance(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            for start, end in self._get_symbol_overlay_segments(obj):
                distance_sq = self._get_screen_distance_sq_to_segment(mouse_pos, start, end)
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_symbol = obj
                    best_distance_sq = distance_sq
        return best_symbol

    def _pick_plan_space_target_from_overlays(self, mouse_pos, radius_px=10):
        if not self.doc or not self.view or not mouse_pos:
            return None
        radius_sq = float(radius_px) * float(radius_px)
        best_space = None
        best_distance_sq = None
        seen = set()
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_plan_space_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            for start, end in self._get_space_overlay_segments(obj):
                distance_sq = self._get_screen_distance_sq_to_segment(mouse_pos, start, end)
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_space = obj
                    best_distance_sq = distance_sq
        return best_space

    def _pick_plan_region_target_from_overlays(self, mouse_pos, radius_px=10):
        if not self.doc or not self.view or not mouse_pos:
            return None
        radius_sq = float(radius_px) * float(radius_px)
        best_region = None
        best_distance_sq = None
        seen = set()
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_plan_region_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            for start, end in self._get_region_overlay_segments(obj):
                distance_sq = self._get_screen_distance_sq_to_segment(mouse_pos, start, end)
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_region = obj
                    best_distance_sq = distance_sq
        return best_region

    def _get_region_pick_polylines(self, region):
        if not self._is_plan_region_object(region):
            return []

        polylines = self._get_region_overlay_polylines(region)
        if polylines:
            return polylines

        proxy = getattr(region, "Proxy", None)
        points = []
        if proxy and hasattr(proxy, "_get_local_points"):
            try:
                points = list(proxy._get_local_points(region) or [])
            except Exception:
                points = []
        elif hasattr(region, "Points"):
            points = [FreeCAD.Vector(point) for point in (getattr(region, "Points", []) or [])]

        if len(points) < 3:
            return []

        placement = getattr(region, "Placement", None)
        if placement is not None:
            try:
                points = [placement.multVec(FreeCAD.Vector(point)) for point in points]
            except Exception:
                points = [FreeCAD.Vector(point) for point in points]
        return [points + [points[0]]]

    def _xy_polygon_area(self, polyline):
        if not polyline or len(polyline) < 4:
            return 0.0
        area = 0.0
        for start, end in zip(polyline, polyline[1:]):
            area += float(start.x) * float(end.y) - float(end.x) * float(start.y)
        return abs(area) * 0.5

    def _xy_point_in_polygon(self, point, polyline, tolerance=1e-9):
        if not point or not polyline or len(polyline) < 4:
            return False

        px = float(point.x)
        py = float(point.y)
        inside = False
        points = polyline
        if points[0].distanceToPoint(points[-1]) > tolerance:
            points = list(points) + [points[0]]

        for start, end in zip(points, points[1:]):
            x1 = float(start.x)
            y1 = float(start.y)
            x2 = float(end.x)
            y2 = float(end.y)
            if abs(y2 - y1) <= tolerance:
                continue
            intersects = (y1 > py) != (y2 > py)
            if not intersects:
                continue
            x_cross = x1 + ((py - y1) * (x2 - x1) / (y2 - y1))
            if x_cross >= px - tolerance:
                inside = not inside
        return inside

    def _pick_plan_region_target_from_polylines(self, mouse_pos):
        if not self.doc or not mouse_pos:
            return None

        point = self._get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_region = None
        best_area = None
        seen = set()
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_plan_region_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue

            containing_area = None
            for polyline in self._get_region_pick_polylines(obj):
                if not self._xy_point_in_polygon(point, polyline):
                    continue
                area = self._xy_polygon_area(polyline)
                if area <= 0.0:
                    continue
                if containing_area is None or area < containing_area:
                    containing_area = area

            if containing_area is None:
                continue
            if best_area is None or containing_area < best_area:
                best_region = obj
                best_area = containing_area

        return best_region

    def _pick_plan_target_from_footprint_faces(
        self, mouse_pos, is_target, get_faces, target_label="target"
    ):
        span_name = f"pick_{target_label}_target_from_footprints"
        with self._plan_perf_trace_span(span_name, mouse_pos=mouse_pos):
            if not self.doc or not mouse_pos:
                return None

            point = self._get_plan_point_from_mouse_pos(mouse_pos)
            if point is None:
                return None

            best_target = None
            best_area = None
            seen = set()
            for obj in getattr(self.doc, "Objects", []) or []:
                self._plan_perf_count(f"{target_label}_objects_scanned")
                if not is_target(obj):
                    continue
                name = getattr(obj, "Name", None)
                if not name or name in seen:
                    continue
                seen.add(name)
                view_object = getattr(obj, "ViewObject", None)
                if (
                    view_object
                    and hasattr(view_object, "Visibility")
                    and not view_object.Visibility
                ):
                    continue
                self._plan_perf_count(f"{target_label}_visible_candidates")

                containing_area = None
                faces = list(get_faces(obj) or [])
                self._plan_perf_count(f"{target_label}_footprint_faces_returned", len(faces))
                for face in faces:
                    self._plan_perf_count(f"{target_label}_footprint_faces_tested")
                    bound_box = getattr(face, "BoundBox", None)
                    if bound_box is None:
                        continue
                    test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
                    try:
                        if not face.isInside(test_point, 0.001, True):
                            continue
                    except Exception:
                        continue
                    area = float(getattr(face, "Area", 0.0) or 0.0)
                    if containing_area is None or area < containing_area:
                        containing_area = area

                if containing_area is None:
                    continue
                self._plan_perf_count(f"{target_label}_containing_candidates")
                if best_area is None or containing_area < best_area:
                    best_target = obj
                    best_area = containing_area

            self._plan_perf_set_fields(
                **{f"{target_label}_pick_result": self._plan_perf_describe_object(best_target)}
            )
            return best_target

    def _pick_plan_space_target_from_footprints(self, mouse_pos):
        return self._pick_plan_target_from_footprint_faces(
            mouse_pos,
            self._is_plan_space_object,
            self._get_space_footprint_faces,
            target_label="space",
        )

    def _pick_plan_region_target_from_footprints(self, mouse_pos):
        return self._pick_plan_target_from_footprint_faces(
            mouse_pos,
            self._is_plan_region_object,
            self._get_region_footprint_faces,
            target_label="region",
        )

    def _has_direct_true_property(self, obj, prop_name):
        if not obj:
            return False
        try:
            if prop_name not in (getattr(obj, "PropertiesList", []) or []):
                return False
            return bool(getattr(obj, prop_name))
        except Exception:
            return False

    def _is_hidden_library_definition_object(self, obj):
        if not obj:
            return False
        if self._has_direct_true_property(obj, "IsLibraryDefinition"):
            return True
        for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
            if self._has_direct_true_property(parent, "IsLibraryDefinition"):
                return True
        return False

    def _should_register_created_plan_object(self, obj):
        if self._tearing_down or not obj or not self.doc:
            return False
        try:
            if getattr(obj, "Document", None) != self.doc:
                return False
            if self._is_hidden_library_definition_object(obj):
                return False
            return self._is_supported_plan_object(obj)
        except ReferenceError:
            return False

    def _queue_created_plan_object(self, obj):
        if not obj or not getattr(obj, "Name", None):
            return
        self._pending_created_plan_objects[obj.Name] = obj
        if self._created_plan_objects_flush_queued:
            return
        self._created_plan_objects_flush_queued = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._flush_created_plan_objects)
        except Exception:
            self._flush_created_plan_objects()

    def _flush_created_plan_objects(self):
        self._created_plan_objects_flush_queued = False
        pending = list(self._pending_created_plan_objects.values())
        self._pending_created_plan_objects.clear()
        for obj in pending:
            if not self._should_register_created_plan_object(obj):
                continue
            self._register_plan_object(obj)

    def _set_pending_selected_plan_target(self, kind=None, obj=None):
        if kind == "opening" and self._is_hosted_opening_object(obj):
            self._pending_selected_plan_target = ("opening", obj)
            return
        if kind == "symbol" and self._is_plan_symbol_instance(obj):
            self._pending_selected_plan_target = ("symbol", obj)
            return
        if kind == "region" and self._is_plan_region_object(obj):
            self._pending_selected_plan_target = ("region", obj)
            return
        if kind == "space" and self._is_plan_space_object(obj):
            self._pending_selected_plan_target = ("space", obj)
            return
        if kind == "wall" and self._is_plan_selectable_wall(obj):
            self._pending_selected_plan_target = ("wall", obj)
            return
        self._pending_selected_plan_target = None

    def _consume_pending_selected_plan_target(self):
        pending_target = self._pending_selected_plan_target
        self._pending_selected_plan_target = None
        if not pending_target:
            return (None, None)
        kind, obj = pending_target
        if kind == "opening" and self._is_hosted_opening_object(obj):
            return (kind, obj)
        if kind == "symbol" and self._is_plan_symbol_instance(obj):
            return (kind, obj)
        if kind == "region" and self._is_plan_region_object(obj):
            return (kind, obj)
        if kind == "space" and self._is_plan_space_object(obj):
            return (kind, obj)
        if kind == "wall" and self._is_plan_selectable_wall(obj):
            return (kind, obj)
        return (None, None)

    def _get_selected_plan_target(self):
        self._sanitize_plan_target_references()
        kind, obj = self._get_selected_plan_target_state()
        if self._is_valid_plan_target(kind, obj):
            return (kind, obj)
        if kind is not None or obj is not None:
            self._set_selected_plan_target_state()
        return (None, None)

    def _get_first_plan_target_from_selection(self, selection):
        for selected in selection or []:
            target_kind, target_obj = self._get_plan_target_for_object(selected)
            if target_kind and target_obj:
                return (target_kind, target_obj)
        return (None, None)

    def _is_valid_plan_target(self, kind, obj):
        validators = {
            "opening": self._is_hosted_opening_object,
            "symbol": self._is_plan_symbol_instance,
            "region": self._is_plan_region_object,
            "space": self._is_plan_space_object,
            "wall": self._is_plan_selectable_wall,
        }
        validator = validators.get(kind)
        return bool(validator is not None and validator(obj))

    def _get_plan_target_state_key(self, kind, obj):
        if not kind or not obj:
            return None
        return (
            kind,
            getattr(getattr(obj, "Document", None), "Name", None),
            getattr(obj, "Name", None),
        )

    def _normalize_plan_target_list(self, targets):
        normalized = []
        seen = set()
        for target in targets or []:
            try:
                target_kind, target_obj = target
            except Exception:
                continue
            if not self._is_valid_plan_target(target_kind, target_obj):
                continue
            key = self._get_plan_target_state_key(target_kind, target_obj)
            if key is None or key in seen:
                continue
            seen.add(key)
            normalized.append((target_kind, target_obj))
        return normalized

    def _normalize_plan_targets_from_selection(self, selection):
        return self._normalize_plan_target_list(
            [
                (target_kind, target_obj)
                for target_kind, target_obj in (
                    self._get_plan_target_for_object(selected) for selected in (selection or [])
                )
                if target_kind and target_obj
            ]
        )

    def _set_secondary_selected_plan_targets(self, targets, primary_kind=None, primary_obj=None):
        if primary_kind is None and primary_obj is None:
            primary_kind, primary_obj = self._get_selected_plan_target()
        normalized = []
        for target_kind, target_obj in self._normalize_plan_target_list(targets):
            if target_kind == primary_kind and target_obj == primary_obj:
                continue
            normalized.append((target_kind, target_obj))
        self._secondary_selected_plan_targets_state = normalized

    def _sync_secondary_selected_plan_targets_from_selection(
        self, selection, primary_kind=None, primary_obj=None
    ):
        self._set_secondary_selected_plan_targets(
            self._normalize_plan_targets_from_selection(selection),
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def _sync_secondary_selected_plan_targets_from_gui_selection(
        self, primary_kind=None, primary_obj=None
    ):
        self._sync_secondary_selected_plan_targets_from_selection(
            self._get_gui_selection(),
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    @contextmanager
    def _selection_changes_suppressed(self):
        previous_ignore = self._ignore_selection_changes
        self._ignore_selection_changes = True
        try:
            yield
        finally:
            self._ignore_selection_changes = previous_ignore

    def _set_gui_selection(self, selection):
        with self._selection_changes_suppressed():
            try:
                FreeCADGui.Selection.clearSelection()
                seen = set()
                for obj in selection or []:
                    if not obj:
                        continue
                    key = (
                        getattr(getattr(obj, "Document", None), "Name", None),
                        getattr(obj, "Name", None),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    self._add_gui_selection_object(obj)
            except Exception:
                pass
        self._sync_secondary_selected_plan_targets_from_selection(selection)

    def _set_gui_selection_object(self, obj):
        if not obj:
            return
        self._set_gui_selection([obj])

    def _add_gui_selection_object(self, obj):
        if not obj:
            return
        doc_name = getattr(getattr(obj, "Document", None), "Name", None)
        obj_name = getattr(obj, "Name", None)
        try:
            if doc_name and obj_name:
                FreeCADGui.Selection.addSelection(doc_name, obj_name)
            else:
                FreeCADGui.Selection.addSelection(obj)
        except Exception:
            if doc_name and obj_name:
                try:
                    FreeCADGui.Selection.addSelection(obj)
                except Exception:
                    pass

    def _get_secondary_selected_plan_targets(self):
        self._sanitize_plan_target_references()
        primary_kind, primary_obj = self._get_selected_plan_target()
        self._set_secondary_selected_plan_targets(
            getattr(self, "_secondary_selected_plan_targets_state", []),
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )
        return list(getattr(self, "_secondary_selected_plan_targets_state", []))

    def _format_plan_target_count_label(self, kind, count):
        labels = {
            "wall": (translate("BIM_PlanEdit", "wall"), translate("BIM_PlanEdit", "walls")),
            "opening": (
                translate("BIM_PlanEdit", "opening"),
                translate("BIM_PlanEdit", "openings"),
            ),
            "symbol": (translate("BIM_PlanEdit", "symbol"), translate("BIM_PlanEdit", "symbols")),
            "region": (translate("BIM_PlanEdit", "region"), translate("BIM_PlanEdit", "regions")),
            "space": (translate("BIM_PlanEdit", "space"), translate("BIM_PlanEdit", "spaces")),
        }
        singular, plural = labels.get(
            kind,
            (translate("BIM_PlanEdit", "item"), translate("BIM_PlanEdit", "items")),
        )
        return "{} {}".format(count, singular if count == 1 else plural)

    def _format_space_region_candidate_area(self, candidate):
        area = float((candidate or {}).get("area", 0.0) or 0.0)
        if area <= 0.0:
            return ""
        try:
            quantity = FreeCAD.Units.Quantity(area, "mm^2")
            return quantity.UserString
        except Exception:
            return "{:.3f} m^2".format(area / 1000000.0)

    def _summarize_plan_targets(self, targets):
        counts = {}
        for target_kind, _target_obj in targets or []:
            counts[target_kind] = counts.get(target_kind, 0) + 1
        parts = [
            self._format_plan_target_count_label(kind, counts[kind])
            for kind in ("wall", "opening", "symbol", "region", "space")
            if counts.get(kind)
        ]
        return ", ".join(parts)

    def _get_selected_plan_targets(self):
        primary_kind, primary_obj = self._get_selected_plan_target()
        targets = []
        seen = set()
        if primary_kind and primary_obj:
            key = (
                primary_kind,
                getattr(getattr(primary_obj, "Document", None), "Name", None),
                getattr(primary_obj, "Name", None),
            )
            seen.add(key)
            targets.append((primary_kind, primary_obj))
        for target_kind, target_obj in self._get_secondary_selected_plan_targets():
            key = (
                target_kind,
                getattr(getattr(target_obj, "Document", None), "Name", None),
                getattr(target_obj, "Name", None),
            )
            if key in seen:
                continue
            seen.add(key)
            targets.append((target_kind, target_obj))
        return targets

    def _get_space_preflight_report(self, targets=None):
        if self.current_tool != "Select":
            return None

        request = self._get_space_creation_request(targets=targets)
        if not request:
            return None

        import ArchSpace

        return ArchSpace.analyzeBoundaryLinks(
            request["boundaries"],
            label=request["label"],
            seed_space=request["region_seed_space"],
        )

    def _format_space_preflight_text(self, report):
        if not report:
            return ""

        if report.get("valid"):
            inner_void_count = int(report.get("inner_void_count", 0) or 0)
            if inner_void_count <= 0:
                return translate("BIM_PlanEdit", "Space preflight: Valid space")
            if inner_void_count == 1:
                return translate("BIM_PlanEdit", "Space preflight: Valid space with 1 inner void")
            return translate(
                "BIM_PlanEdit", "Space preflight: Valid space with {count} inner voids"
            ).format(count=inner_void_count)

        code = report.get("code")
        status_map = {
            "empty": translate(
                "BIM_PlanEdit", "Space preflight: Select room-bounding walls or faces"
            ),
            "unusable_boundaries": translate(
                "BIM_PlanEdit", "Space preflight: No usable boundary faces"
            ),
            "no_height": translate("BIM_PlanEdit", "Space preflight: Boundaries have no height"),
            "no_intersection": translate(
                "BIM_PlanEdit", "Space preflight: Boundaries miss the plan cut"
            ),
            "open_loop": translate("BIM_PlanEdit", "Space preflight: Open loop"),
            "multiple_regions": translate(
                "BIM_PlanEdit", "Space preflight: Multiple enclosed regions"
            ),
            "nested_islands": translate(
                "BIM_PlanEdit", "Space preflight: Nested islands are not supported"
            ),
            "invalid_solid": translate(
                "BIM_PlanEdit", "Space preflight: Selection cannot become one space"
            ),
        }
        status = status_map.get(
            code,
            translate("BIM_PlanEdit", "Space preflight: Selection cannot become one space"),
        )
        details = [
            str(detail).strip() for detail in report.get("details", []) if str(detail).strip()
        ]
        if details:
            return "{}\n{}".format(status, details[0])
        return status

    def _get_plan_selection_summary_text(self):
        if self.current_tool != "Select":
            return ""
        targets = self._get_selected_plan_targets()
        preflight_text = self._format_space_preflight_text(
            self._get_space_preflight_report(targets)
        )
        if len(targets) <= 1:
            return preflight_text
        region_seed_space, wall_targets = self._get_space_region_seed_targets(targets)
        if region_seed_space is not None and wall_targets:
            summary = translate("BIM_PlanEdit", "Boundary candidates: {summary}").format(
                summary=self._summarize_plan_targets(wall_targets)
            )
        else:
            summary = translate("BIM_PlanEdit", "Selection set: {summary}").format(
                summary=self._summarize_plan_targets(targets)
            )
        if preflight_text:
            return "{}\n{}".format(summary, preflight_text)
        return summary

    def _clear_plan_relation_status(self):
        self._plan_relation_status_message = None

    def _collect_wall_relation_warnings(self, wall):
        if not wall:
            return []
        import ArchWallJoinUtils

        warnings = []
        seen = set()
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            if not relation or relation.Name in seen or not getattr(relation, "Enabled", True):
                continue
            seen.add(relation.Name)
            status = getattr(relation, "Status", "")
            if status in ("", "OK", "Disabled"):
                continue
            label = getattr(relation, "Label", getattr(relation, "Name", ""))
            detail = str(getattr(relation, "StatusMessage", "") or status).strip()
            warnings.append((relation, label, status, detail))
        return warnings

    def _update_wall_relation_status(self, wall):
        warnings = self._collect_wall_relation_warnings(wall)
        if not warnings:
            self._clear_plan_relation_status()
            return

        if len(warnings) == 1:
            _relation, label, status, _detail = warnings[0]
            summary = translate("BIM_PlanEdit", "Relation warning: {label} ({status})").format(
                label=label,
                status=status,
            )
        else:
            summary = translate(
                "BIM_PlanEdit", "Relation warnings: {count} relations need attention"
            ).format(count=len(warnings))

        self._plan_relation_status_message = summary
        FreeCAD.Console.PrintWarning(summary + "\n")
        for _relation, label, _status, detail in warnings:
            FreeCAD.Console.PrintWarning(f"  - {label}: {detail}\n")

    def _set_selected_plan_target(self, kind=None, obj=None, pending_restore=False):
        if self._is_valid_plan_target(kind, obj):
            self._set_selected_plan_target_state(kind, obj)
        else:
            self._set_selected_plan_target_state()
            kind = None
            obj = None
        self._sync_secondary_selected_plan_targets_from_gui_selection(
            primary_kind=kind,
            primary_obj=obj,
        )
        self._clear_plan_relation_status()
        self._sync_active_plan_target_object()
        if pending_restore:
            self._set_pending_selected_plan_target(kind, obj)
        else:
            self._set_pending_selected_plan_target()
        if not self._tearing_down:
            self._sync_junction_node_overlays()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_space_overlay()
            self._sync_hovered_region_overlay()

    def _schedule_selected_wall_reset(self, reason, obj):
        if self._pending_selected_wall_reset or self._tearing_down:
            return
        self._pending_selected_wall_reset = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._reset_selected_wall_after_change)
        except Exception:
            self._reset_selected_wall_after_change()

    def _reset_selected_wall_after_change(self):
        self._pending_selected_wall_reset = False
        if self._tearing_down or self.current_tool != "Select":
            return
        wall = self._get_selected_plan_target_object("wall")
        if not wall:
            return
        self._clear_wall_grips()
        self._clear_selected_plan_target_if_matches("wall", wall)
        self._set_gui_selection([])
        self._refresh_task_panel_status()

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        """Drop current selected-wall UI state before another tool mutates the host wall."""

        if self._tearing_down:
            return
        if wall is None:
            wall = self._get_selected_plan_target_object("wall")
        if wall is None:
            return
        if not self._is_selected_plan_target("wall", wall):
            return
        self._pending_selected_wall_reset = False
        self._clear_wall_grips()
        self._clear_selected_plan_target_if_matches("wall", wall)
        if clear_gui_selection:
            self._set_gui_selection([])
        self._refresh_task_panel_status()

    def _register_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            return

        add_event_callback = self._get_runtime_attr(self.view, "addEventCallbackPivy")
        if add_event_callback is None:
            return

        try:
            viewer = self.viewer
            if viewer is None:
                get_viewer = self._get_runtime_attr(self.view, "getViewer")
                if get_viewer is None:
                    return
                viewer = get_viewer()
                self.viewer = viewer
            get_render_manager = self._get_runtime_attr(viewer, "getSoRenderManager")
            self._render_manager = get_render_manager() if get_render_manager is not None else None
            if self._key_pressed_cb is None:
                self._key_pressed_cb = add_event_callback(
                    coin.SoKeyboardEvent.getClassTypeId(), self._on_key_pressed
                )
            if self._mouse_moved_cb is None:
                self._mouse_moved_cb = add_event_callback(
                    coin.SoLocation2Event.getClassTypeId(), self._on_mouse_moved
                )
            if self._mouse_wheel_cb is None:
                event_type = getattr(coin, "SoMouseWheelEvent", None)
                if event_type is not None:
                    self._mouse_wheel_event_type = event_type.getClassTypeId()
                else:
                    self._mouse_wheel_event_type = coin.SoEvent.getClassTypeId()
                self._mouse_wheel_cb = add_event_callback(
                    self._mouse_wheel_event_type, self._on_mouse_wheel
                )
            if self._mouse_pressed_cb is None:
                self._mouse_pressed_cb = add_event_callback(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_pressed
                )
        except (AttributeError, ReferenceError, RuntimeError):
            self._discard_stale_runtime_object(self.view)
            self._render_manager = None

    def _unregister_edit_callbacks(self):
        try:
            from pivy import coin
        except Exception:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_wheel_cb = None
            self._mouse_wheel_event_type = None
            self._mouse_pressed_cb = None
            self._render_manager = None
            return

        if not self.view:
            self._key_pressed_cb = None
            self._mouse_moved_cb = None
            self._mouse_wheel_cb = None
            self._mouse_wheel_event_type = None
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
            if self._mouse_wheel_cb and self._mouse_wheel_event_type:
                self.view.removeEventCallbackSWIG(
                    self._mouse_wheel_event_type, self._mouse_wheel_cb
                )
            if self._mouse_pressed_cb:
                self.view.removeEventCallbackSWIG(
                    coin.SoMouseButtonEvent.getClassTypeId(), self._mouse_pressed_cb
                )
        except RuntimeError:
            pass

        self._key_pressed_cb = None
        self._mouse_moved_cb = None
        self._mouse_wheel_cb = None
        self._mouse_wheel_event_type = None
        self._mouse_pressed_cb = None
        self._render_manager = None

    def _sync_primary_selected_plan_target_visuals(self, previous_kind=None, previous_obj=None):
        with self._plan_perf_trace_span("sync_primary_selected_plan_target_visuals"):
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "opening"
            ):
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "symbol"
            ):
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "region"
            ):
                self._sync_selected_region_overlay()
            if self.current_tool != "Select" or self._selected_plan_target_changed(
                previous_kind, previous_obj, "space"
            ):
                self._sync_selected_space_overlay()
            self._sync_hovered_symbol_overlay()
            self._sync_hovered_opening_overlay()
            self._sync_hovered_space_overlay()
            self._sync_hovered_region_overlay()
            self._sync_secondary_selected_overlays()
            self._sync_active_plan_target_object()
            self._refresh_task_panel_status()

    def _refresh_selected_plan_target(self):
        with self._plan_perf_trace_span("refresh_selected_plan_target"):
            self._plan_perf_count("selection_refreshes")
            if self._tearing_down:
                return
            if self._ignore_selection_changes:
                return

            previous_kind, previous_obj = self._get_selected_plan_target()
            self._plan_perf_set_fields(
                selected_before=self._plan_perf_describe_target(previous_kind, previous_obj)
            )
            previous_wall = self._get_plan_target_object_from_state(
                previous_kind, previous_obj, "wall"
            )
            if self._is_wall_edit_modal_active():
                self._set_selected_plan_target_state("wall", self._edit_wall)
                self._set_secondary_selected_plan_targets([])
                if self._selected_plan_target_changed(previous_kind, previous_obj, "wall"):
                    self._sync_wall_grips()
                self._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
                return
            if self.current_tool == "Set Space Text":
                self._set_selected_plan_target_state(
                    "space",
                    self._edit_space if self._is_plan_space_object(self._edit_space) else None,
                )
                self._set_secondary_selected_plan_targets([])
                self._clear_wall_grips()
                self._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
                return
            if self.current_tool == "Join":
                wall = previous_wall
                if not self._is_plan_selectable_wall(wall):
                    self.current_tool = "Select"
                    wall = None
                self._set_selected_plan_target_state("wall", wall)
                self._set_secondary_selected_plan_targets([])
                self._clear_wall_grips()
                self._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
                return
            self._set_selected_plan_target_state()
            try:
                selection = FreeCADGui.Selection.getSelection()
            except (ReferenceError, RuntimeError):
                return
            self._plan_perf_count("gui_selection_size", len(selection or []))
            if self.current_tool in ("Select", "Pick Space Region") and selection:
                selected_targets = []
                for selected in selection:
                    target_kind, target_obj = self._get_plan_target_for_object(selected)
                    if target_kind:
                        selected_targets.append((target_kind, target_obj))
                self._plan_perf_count("selected_targets_considered", len(selected_targets))

                matched_target = None
                pending_kind, pending_target = self._pending_selected_plan_target or (None, None)
                if pending_target is not None:
                    for target_kind, selected in selected_targets:
                        if selected == pending_target and target_kind == pending_kind:
                            matched_target = (target_kind, selected)
                            break
                if matched_target is None:
                    for preferred_kind in ("opening", "symbol", "wall", "region", "space"):
                        matched_target = next(
                            (
                                (target_kind, selected)
                                for target_kind, selected in selected_targets
                                if target_kind == preferred_kind
                            ),
                            None,
                        )
                        if matched_target is not None:
                            break

                if matched_target is not None:
                    target_kind, selected = matched_target
                    self._set_selected_plan_target_state(target_kind, selected)
                    self._set_secondary_selected_plan_targets(
                        selected_targets,
                        primary_kind=target_kind,
                        primary_obj=selected,
                    )
                    if len(selection) == 1 and target_kind not in ("space", "region"):
                        self._set_pending_selected_plan_target()
                    else:
                        self._set_pending_selected_plan_target(target_kind, selected)
                else:
                    self._set_secondary_selected_plan_targets([])
                    self._set_pending_selected_plan_target()
            elif self.current_tool in ("Select", "Pick Space Region") and not selection:
                pending_kind, pending_target = self._consume_pending_selected_plan_target()
                self._set_selected_plan_target_state(pending_kind, pending_target)
                self._set_secondary_selected_plan_targets([])
            else:
                self._set_secondary_selected_plan_targets([])
                self._set_pending_selected_plan_target()
            if self._selected_plan_target_changed(previous_kind, previous_obj, "wall"):
                self._sync_wall_grips()
            self._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
            selected_kind, selected_obj = self._get_selected_plan_target()
            self._plan_perf_set_fields(
                selected_after=self._plan_perf_describe_target(selected_kind, selected_obj)
            )

    def _refresh_primary_selected_plan_target(self):
        self._refresh_selected_plan_target()

    def _refresh_selected_wall(self):
        # Compatibility wrapper for older tests and callers.
        self._refresh_primary_selected_plan_target()

    def _start_embedded_tool(self, tool_name, command, host_class=_PlanEditCommandHost):
        self.current_tool = tool_name
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_region(None)
        self._sync_secondary_selected_overlays()
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
            self._wall_edit_modal_active = False
            self._restore_edit_wall_visibility()
            self._clear_wall_edit_preview()
            self._edit_wall = None
            self._edit_endpoint = None
            self._edit_endpoints = None
            self._wall_edit_opening_clearances = {}
            self._preview_points = None
            self._wall_edit_length_edit_queued = False
            self._ignore_selection_changes = False
            self._embedded_host = None
            self._embedded_tool = None
            self._embedded_tool_name = None
            self._edit_opening_move_anchor = "center"
            self._edit_opening_move_raw_point = None
            self._clear_plan_relation_status()
            return
        self._stop_snapper()
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._wall_edit_modal_active = False
        self._restore_edit_wall_visibility()
        self._clear_wall_edit_preview()
        self._edit_wall = None
        self._edit_endpoint = None
        self._edit_endpoints = None
        self._wall_edit_opening_clearances = {}
        self._preview_points = None
        self._wall_edit_length_edit_queued = False
        self._ignore_selection_changes = False
        self._embedded_host = None
        self._embedded_tool = None
        self._embedded_tool_name = None
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self._clear_plan_relation_status()
        self._sync_wall_grips()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_space_overlay()

    def _cancel_join_tool(self, refresh=True):
        if self.current_tool != "Join":
            return False
        selected_wall = self._get_selected_plan_target_object("wall")
        self.current_tool = "Select"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        if selected_wall:
            self._select_wall_for_plan_edit(selected_wall)
            return True
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _restore_gui_selection(self, obj):
        if not obj:
            return
        self._set_gui_selection_object(obj)

    def _apply_plan_wall_join(self, source_wall, target_wall):
        if not self._is_plan_selectable_wall(source_wall):
            return False
        if not self._is_plan_selectable_wall(target_wall):
            return False
        if source_wall == target_wall:
            return False

        import Arch
        import ArchWallJoinUtils

        join_command = self._get_plan_join_command()
        created = False
        doc = getattr(source_wall, "Document", None) or self.doc
        if doc is None:
            return False

        doc.openTransaction(translate("BIM_PlanEdit", "Join walls"))
        try:
            relation = self._apply_plan_wall_junction_promotion(doc, source_wall, target_wall)
            if relation is None:
                relation = ArchWallJoinUtils.find_existing_joint(doc, source_wall, target_wall)
                if not relation:
                    relation = Arch.makeWallJoint(source_wall, target_wall, join_command.JointType)
                    created = True
                if not relation:
                    raise RuntimeError("Unable to create wall joint")
                if not join_command._configure_joint(relation, source_wall, target_wall):
                    raise RuntimeError("Unable to configure wall joint")
            doc.commitTransaction()
            doc.recompute()
        except Exception:
            try:
                doc.abortTransaction()
            except Exception:
                pass
            return False

        if getattr(getattr(relation, "Proxy", None), "Type", None) == "WallJoint":
            if created or getattr(relation, "Status", "OK") != "OK":
                join_command._report_joint_status(relation)
        elif getattr(relation, "Status", "OK") != "OK":
            message = str(getattr(relation, "StatusMessage", "") or getattr(relation, "Status", ""))
            if message:
                FreeCAD.Console.PrintWarning(message + "\n")
        self.current_tool = "Select"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._select_wall_for_plan_edit(source_wall)
        self._restore_gui_selection(source_wall)
        return True

    def _stop_snapper(self):
        snapper = getattr(FreeCADGui, "Snapper", None)
        if not snapper:
            return
        toolbar = getattr(FreeCADGui, "draftToolBar", None)
        if toolbar and hasattr(toolbar, "setPointFocusSuppressed"):
            try:
                toolbar.setPointFocusSuppressed(False)
            except Exception:
                pass
        elif toolbar and hasattr(toolbar, "suppress_point_focus"):
            try:
                toolbar.suppress_point_focus = False
            except Exception:
                pass
        try:
            snapper.getPoint()
            snapper.off()
        except Exception:
            pass

    def _set_draft_point_focus_suppressed(self, suppressed):
        toolbar = getattr(FreeCADGui, "draftToolBar", None)
        if not toolbar:
            return
        if hasattr(toolbar, "setPointFocusSuppressed"):
            try:
                toolbar.setPointFocusSuppressed(bool(suppressed))
            except Exception:
                pass
            return
        if hasattr(toolbar, "suppress_point_focus"):
            try:
                toolbar.suppress_point_focus = bool(suppressed)
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
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_space_overlay()
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
            self._set_gui_selection(walls)
        except Exception:
            pass

        self._cancel_rect_wall_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_primary_selected_plan_target()
        self._refresh_task_panel_status()

    def _has_active_space_separator_tool(self):
        return self._space_separator_start is not None or self.current_tool == "Separator"

    def _has_active_plan_region_tool(self):
        return bool(self._plan_region_points) or self.current_tool == "Region"

    def _clear_plan_region_preview(self):
        self._finalize_trackers(self._plan_region_preview_trackers)
        self._plan_region_preview_trackers = []

    def _cancel_plan_region_tool(self, refresh=True):
        if not self._has_active_plan_region_tool():
            return False
        self._stop_snapper()
        self._clear_plan_region_preview()
        self._plan_region_points = []
        self._plan_region_parent_space = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._sync_selected_region_overlay()
        self._sync_selected_space_overlay()
        return True

    def _get_plan_region_close_tolerance(self):
        units_per_pixel = self._get_plan_view_units_per_pixel()
        if units_per_pixel is None:
            return 120.0
        return max(120.0, float(units_per_pixel) * 12.0)

    def _get_plan_region_preview_segments(self, point=None):
        points = [FreeCAD.Vector(item) for item in (self._plan_region_points or [])]
        if point is not None:
            point = self._project_plan_point(point)
            if point is not None and (not points or point.distanceToPoint(points[-1]) > 0.000001):
                points.append(point)
        segments = []
        for start, end in zip(points, points[1:]):
            if start.distanceToPoint(end) <= 0.000001:
                continue
            segments.append((start, end, False))
        if len(points) >= 3 and points[-1].distanceToPoint(points[0]) > 0.000001:
            segments.append((points[-1], points[0], True))
        return segments

    def _update_plan_region_preview(self, point, info):
        del info
        segments = self._get_plan_region_preview_segments(point)
        self._clear_plan_region_preview()
        if not segments:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        color = (0.86, 0.48, 0.12)
        width = self._scaled_line_width(2)
        for index, (start, end, dotted) in enumerate(segments):
            tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "plan_region_preview:{}".format(index),
                dotted=dotted,
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            self._plan_region_preview_trackers.append(tracker)

    def _create_plan_region(self, points):
        import Arch

        region = None
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Plan Region"))
        try:
            region = Arch.makePlanRegion(
                points=points,
                parent_space=self._plan_region_parent_space,
            )
            if not region:
                raise RuntimeError("Unable to create plan region")
            self._add_object_to_active_storey(region)
            self.doc.recompute()
            if not self._get_region_footprint_faces(region):
                raise RuntimeError("Plan region has no valid footprint")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return region

    def _finalize_plan_region(self):
        if len(self._plan_region_points) < 3:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Place at least three points before finishing the region.\n",
                )
            )
            return False
        try:
            region = self._create_plan_region(self._plan_region_points)
        except Exception:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the plan region.\n")
            )
            return False

        self._register_plan_object(region)
        self._cancel_plan_region_tool(refresh=False)
        self._restore_selected_region(region)
        return True

    def _handle_plan_region_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_plan_region_tool()
            return

        point = self._project_plan_point(point)
        if point is None:
            self._cancel_plan_region_tool()
            return

        if self._plan_region_points:
            if point.distanceToPoint(self._plan_region_points[-1]) <= 0.000001:
                FreeCADGui.Snapper.getPoint(
                    callback=self._handle_plan_region_point,
                    movecallback=self._update_plan_region_preview,
                    last=self._plan_region_points[-1],
                    title=translate("BIM_PlanEdit", "Next region point"),
                    mode="line",
                )
                return
            if (
                len(self._plan_region_points) >= 3
                and point.distanceToPoint(self._plan_region_points[0])
                <= self._get_plan_region_close_tolerance()
            ):
                self._finalize_plan_region()
                return

        self._plan_region_points.append(point)
        self._update_plan_region_preview(None, None)
        FreeCADGui.Snapper.getPoint(
            callback=self._handle_plan_region_point,
            movecallback=self._update_plan_region_preview,
            last=point,
            title=translate("BIM_PlanEdit", "Next region point"),
            mode="line",
        )

    def _clear_space_separator_preview(self):
        self._finalize_trackers(self._space_separator_preview_trackers)
        self._space_separator_preview_trackers = []

    def _cancel_space_separator_tool(self, refresh=True):
        if not self._has_active_space_separator_tool():
            return False
        self._stop_snapper()
        self._clear_space_separator_preview()
        self._space_separator_start = None
        self._space_separator_height = None
        FreeCAD.activeDraftCommand = None
        self.current_tool = "Select"
        if refresh:
            self._refresh_task_panel_status()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_space_overlay()
        return True

    def _update_space_separator_preview(self, point, info):
        del info
        start = self._space_separator_start
        if start is None or point is None:
            return
        end = self._project_plan_point(point)
        if end is None or end.sub(start).Length < _MIN_WALL_LENGTH:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        if not self._space_separator_preview_trackers:
            tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "space_separator_preview",
                dotted=True,
                ontop=True,
            )
            self._space_separator_preview_trackers.append(tracker)
        tracker = self._space_separator_preview_trackers[0]
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()

    def _create_space_separator(self, start, end):
        import Arch

        separator = None
        self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space Separator"))
        try:
            separator = Arch.makeSpaceSeparator(
                start=start,
                end=end,
                height=self._space_separator_height,
            )
            if not separator:
                raise RuntimeError("Unable to create space separator")
            self._add_object_to_active_storey(separator)
            self.doc.recompute()
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            raise
        return separator

    def _handle_space_separator_point(self, point=None, obj=None):
        del obj
        if point is None:
            self._cancel_space_separator_tool()
            return

        point = self._project_plan_point(point)
        if self._space_separator_start is None:
            self._space_separator_start = point
            FreeCADGui.Snapper.getPoint(
                callback=self._handle_space_separator_point,
                movecallback=self._update_space_separator_preview,
                last=point,
                title=translate("BIM_PlanEdit", "Separator end point"),
                mode="line",
            )
            return

        if point.sub(self._space_separator_start).Length < _MIN_WALL_LENGTH:
            self._cancel_space_separator_tool()
            return

        try:
            separator = self._create_space_separator(self._space_separator_start, point)
        except Exception:
            self._cancel_space_separator_tool()
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the space separator.\n")
            )
            return

        self._register_plan_object(separator)
        self._cancel_space_separator_tool(refresh=False)
        self.current_tool = "Select"
        self._refresh_primary_selected_plan_target()
        self._refresh_task_panel_status()

    def _has_active_wall_edit(self):
        return self._is_wall_edit_modal_active() or self._embedded_tool_name == "Wall"

    def _is_wall_edit_modal_active(self):
        return bool(self._wall_edit_modal_active and self._edit_wall)

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

        self.current_tool = "Select"
        self._cancel_pending_edit()
        self._sync_selected_wall_opening_context_overlay()
        if refresh:
            self._refresh_task_panel_status()
        return True

    def _cancel_wall_subtool(self):
        self._cancel_embedded_tool("Wall")

    def _start_wall_edit(self, mode):
        if not self.is_selected_wall_endpoint_editable():
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "Select a straight wall before using wall grips.\n",
                )
            )
            return

        wall = self._get_selected_plan_target_object("wall")
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

        self._clear_plan_relation_status()
        self.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_selected_plan_target("wall", wall)
        self._clear_selected_wall_opening_context_overlay()
        self._wall_edit_modal_active = True
        self._edit_wall = wall
        self._edit_endpoint = mode
        self._edit_endpoints = endpoints
        self._wall_edit_opening_clearances = self._snapshot_wall_hosted_opening_clearances(
            wall, endpoints
        )
        self._preview_points = list(endpoints)
        self._edit_wall_visibility = None
        try:
            self._edit_wall_visibility = wall.ViewObject.Visibility
            wall.ViewObject.Visibility = False
        except Exception:
            self._edit_wall_visibility = None
        self._clear_wall_grips()
        self._sync_wall_edit_preview(self._preview_points)
        self._refresh_task_panel_status()
        self._resume_wall_edit_point_pick()

    def _resume_wall_edit_point_pick(self):
        if not self._is_wall_edit_modal_active():
            return
        mode = self._edit_endpoint
        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))
        last = self._get_wall_edit_reference_point()

        FreeCAD.activeDraftCommand = self
        if getattr(FreeCADGui, "Snapper", None):
            try:
                FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            callback=self._finish_wall_edit,
            movecallback=self._update_wall_edit_point_pick,
            last=last,
            title=title,
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _snapshot_wall_hosted_opening_clearances(self, wall, endpoints):
        if not wall or not endpoints or len(endpoints) != 2:
            return {}

        wall_origin = FreeCAD.Vector(endpoints[0])
        wall_axis_u = FreeCAD.Vector(endpoints[1]).sub(wall_origin)
        wall_length = wall_axis_u.Length
        if wall_length < 1e-9:
            return {}
        wall_axis_u.normalize()

        snapshot = {}
        for opening in self._get_wall_hosted_openings(wall):
            proxy = self._get_opening_plan_proxy(
                opening, "get_plan_move_context", "get_plan_center_point"
            )
            if not proxy:
                continue
            context = proxy.get_plan_move_context()
            center = proxy.get_plan_center_point()
            if not context or center is None:
                continue
            half_width = float(context.get("opening_half_width_u") or 0.0)
            center_u = FreeCAD.Vector(center).sub(wall_origin).dot(wall_axis_u)
            snapshot[getattr(opening, "Name", "")] = {
                "center_u": center_u,
                "left_clearance": max(0.0, center_u - half_width),
                "right_clearance": max(0.0, wall_length - (center_u + half_width)),
            }
        return snapshot

    def _finish_wall_edit(self, point=None, obj=None):
        del obj

        wall = self._edit_wall
        endpoint = self._edit_endpoint
        new_points = self._compute_wall_edit_points(point)

        if point is None or not wall or not endpoint or not new_points:
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        proxy = getattr(wall, "Proxy", None)
        if (
            not proxy
            or not hasattr(proxy, "calc_endpoints")
            or not hasattr(proxy, "set_from_endpoints")
        ):
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _commit_wall_edit_points(self, wall, endpoint, proxy, new_points):
        if not wall or not endpoint or not proxy or not new_points:
            self.current_tool = "Select"
            self._cancel_pending_edit()
            self._refresh_task_panel_status()
            return

        transaction_name = (
            translate("BIM_PlanEdit", "Move Wall")
            if endpoint == "Move"
            else translate("BIM_PlanEdit", "Stretch Wall Endpoint")
        )
        openings_fit = True

        try:
            self.doc.openTransaction(transaction_name)
            proxy.set_from_endpoints(wall, new_points)
            self.doc.recompute()
            openings_fit = self._resolve_wall_hosted_opening_layout(wall)
            if not openings_fit:
                raise RuntimeError("Hosted openings no longer fit within resized wall")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not openings_fit:
                FreeCAD.Console.PrintError(
                    translate(
                        "BIM_PlanEdit",
                        "The resized wall cannot contain its hosted openings.\n",
                    )
                )
            self.current_tool = "Select"
            self._cancel_pending_edit()
            return
        self._refresh_wall_hosted_opening_footprints(wall)
        self._set_gui_selection_object(wall)
        self.current_tool = "Select"
        self._cancel_pending_edit()
        self._set_selected_plan_target("wall", wall, pending_restore=True)
        self._update_wall_relation_status(wall)
        self._sync_wall_grips()
        self._refresh_task_panel_status()

    def _start_wall_grip_edit(self, grip_index):
        if grip_index not in (0, 1, 2) or not self.is_selected_wall_endpoint_editable():
            return
        self._start_wall_edit({0: "Start", 1: "End", 2: "Move"}[grip_index])

    def _activate_wall_grip(self, grip_index, wall=None):
        if wall is None:
            wall = self._get_selected_plan_target_object("wall")
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_wall_grip_now(grip_index, wall)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda wall=wall, grip_index=grip_index: self._activate_wall_grip_now(grip_index, wall),
        )

    def _activate_wall_grip_now(self, grip_index, wall=None):
        if self._tearing_down or self.current_tool != "Select" or not wall:
            return
        self._set_selected_plan_target("wall", wall)
        self._start_wall_grip_edit(grip_index)

    def _get_wall_edit_reference_point(self):
        if not self._edit_endpoints or len(self._edit_endpoints) != 2:
            return None
        if self._edit_endpoint == "Move":
            return (self._edit_endpoints[0] + self._edit_endpoints[1]) * 0.5
        if self._edit_endpoint == "Start":
            return self._edit_endpoints[0]
        if self._edit_endpoint == "End":
            return self._edit_endpoints[1]
        return None

    def _compute_wall_edit_points(self, point):
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

    def _compute_wall_edit_points_from_length(self, length):
        endpoint = self._edit_endpoint
        original_endpoints = self._edit_endpoints
        if endpoint not in ("Start", "End") or not original_endpoints:
            return None

        length = max(float(length), _MIN_WALL_LENGTH)
        axis = original_endpoints[1].sub(original_endpoints[0])
        if axis.Length < _MIN_WALL_LENGTH:
            return None
        axis.normalize()

        if endpoint == "Start":
            end = original_endpoints[1]
            return [end.sub(FreeCAD.Vector(axis).multiply(length)), end]

        start = original_endpoints[0]
        return [start, start.add(FreeCAD.Vector(axis).multiply(length))]

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

    def _make_preview_wall_adapter(self, wall, endpoints):
        if not wall or not endpoints or len(endpoints) != 2:
            return None

        real_proxy = getattr(wall, "Proxy", None)
        preview_points = [FreeCAD.Vector(point) for point in endpoints]

        class _PreviewWallProxy:
            def __init__(self, wrapped_proxy):
                self._wrapped_proxy = wrapped_proxy
                self.Type = getattr(wrapped_proxy, "Type", None)

            def calc_endpoints(self, _obj):
                return [FreeCAD.Vector(point) for point in preview_points]

            def get_width(self, _obj, widths=False):
                if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_width"):
                    return self._wrapped_proxy.get_width(wall, widths=widths)
                width = getattr(getattr(wall, "Width", None), "Value", getattr(wall, "Width", None))
                return width

            def get_layers(self, _obj):
                if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_layers"):
                    return self._wrapped_proxy.get_layers(wall)
                return None

        class _PreviewWall:
            def __init__(self):
                self._wall = wall
                self.Proxy = _PreviewWallProxy(real_proxy)
                self.Label = getattr(wall, "Label", getattr(wall, "Name", ""))
                self.Name = getattr(wall, "Name", "")
                self.Document = getattr(wall, "Document", None)
                self.InList = getattr(wall, "InList", [])
                # Force solver helpers to read the transient preview endpoints
                # instead of the original baseline object.
                self.Base = None
                self.Width = getattr(wall, "Width", None)
                self.Align = getattr(wall, "Align", "Center")

            def __getattr__(self, attr):
                return getattr(self._wall, attr)

        return _PreviewWall()

    def _solve_preview_wall_relation(self, relation, wall, preview_wall):
        if not relation or not wall or not preview_wall:
            return None

        import ArchWallJoinUtils
        import ArchWallJunctionUtils

        if ArchWallJoinUtils.is_wall_joint(relation):
            wall_a = preview_wall if getattr(relation, "WallA", None) == wall else relation.WallA
            wall_b = preview_wall if getattr(relation, "WallB", None) == wall else relation.WallB
            return ArchWallJoinUtils.solve_wall_joint_inputs(
                wall_a,
                wall_b,
                getattr(relation, "JointType", "Miter"),
                getattr(relation, "ButtTrimmed", "Auto"),
                getattr(relation, "TeeStem", "Auto"),
                getattr(relation, "EndA", "Auto"),
                getattr(relation, "EndB", "Auto"),
            )

        if ArchWallJoinUtils.is_wall_junction(relation):
            walls = [
                preview_wall if linked_wall == wall else linked_wall
                for linked_wall in list(getattr(relation, "Walls", []) or [])
            ]
            carrier_wall = (
                preview_wall
                if getattr(relation, "CarrierWall", None) == wall
                else relation.CarrierWall
            )
            return ArchWallJunctionUtils.solve_wall_junction_inputs(
                walls,
                getattr(relation, "CarrierMode", "Auto"),
                carrier_wall,
            )

        return None

    def _collect_preview_wall_relation_data(self, wall, points):
        if not wall or not points or len(points) != 2:
            return {"Start": None, "End": None, "Conflicts": set()}, []

        preview_wall = self._make_preview_wall_adapter(wall, points)
        if not preview_wall:
            return {"Start": None, "End": None, "Conflicts": set()}, []

        import ArchWallJoinUtils

        claims = {"Start": [], "End": []}
        warnings = []
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            solution = self._solve_preview_wall_relation(relation, wall, preview_wall)
            if not solution:
                continue
            if not solution.is_ok():
                warnings.append(
                    (
                        getattr(relation, "Label", getattr(relation, "Name", "")),
                        getattr(solution, "status", "SolverError"),
                        str(getattr(solution, "status_message", "") or "").strip(),
                    )
                )
                continue
            end_name, plane = ArchWallJoinUtils.get_trim_for_wall(solution, preview_wall)
            if end_name and plane:
                claims[end_name].append((relation, plane))

        result = {"Start": None, "End": None, "Conflicts": set()}
        for end_name, entries in claims.items():
            if len(entries) == 1:
                result[end_name] = entries[0][1]
            elif len(entries) > 1:
                result["Conflicts"].add(end_name)
                warnings.append(
                    (
                        translate("BIM_PlanEdit", "{end_name} preview trims").format(
                            end_name=end_name
                        ),
                        "Conflict",
                        translate(
                            "BIM_PlanEdit",
                            "Multiple wall relations trim the same wall end in preview.",
                        ),
                    )
                )
        return result, warnings

    @staticmethod
    def _clip_preview_polygon_to_plane(polygon, plane_placement, ref_point, tol=1e-7):
        if not polygon or len(polygon) < 3 or plane_placement is None or ref_point is None:
            return polygon

        plane_origin = FreeCAD.Vector(plane_placement.Base)
        plane_normal = plane_placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        if plane_normal.Length <= tol:
            return polygon
        plane_normal.normalize()

        ref_distance = plane_normal.dot(FreeCAD.Vector(ref_point).sub(plane_origin))

        def signed_distance(point):
            return plane_normal.dot(FreeCAD.Vector(point).sub(plane_origin))

        def is_inside(distance):
            if ref_distance >= 0:
                return distance >= -tol
            return distance <= tol

        def intersect(prev_point, curr_point, prev_distance, curr_distance):
            denom = prev_distance - curr_distance
            if abs(denom) <= tol:
                return FreeCAD.Vector(curr_point)
            factor = prev_distance / denom
            segment = FreeCAD.Vector(curr_point).sub(prev_point)
            return FreeCAD.Vector(prev_point).add(segment.multiply(factor))

        result = []
        prev_point = FreeCAD.Vector(polygon[-1])
        prev_distance = signed_distance(prev_point)
        prev_inside = is_inside(prev_distance)
        for current_point in polygon:
            current_point = FreeCAD.Vector(current_point)
            current_distance = signed_distance(current_point)
            current_inside = is_inside(current_distance)
            if current_inside:
                if not prev_inside:
                    result.append(
                        intersect(prev_point, current_point, prev_distance, current_distance)
                    )
                result.append(current_point)
            elif prev_inside:
                result.append(intersect(prev_point, current_point, prev_distance, current_distance))
            prev_point = current_point
            prev_distance = current_distance
            prev_inside = current_inside
        return result

    def _get_preview_footprint_polylines(self, points):
        footprint = self._get_preview_footprint(points)
        if not footprint or len(footprint) < 3:
            return [], []

        relation_endings, warnings = self._collect_preview_wall_relation_data(
            self._edit_wall, points
        )
        polygon = [FreeCAD.Vector(point) for point in footprint]
        for end_name in ("Start", "End"):
            plane = relation_endings.get(end_name)
            if plane is None or end_name in relation_endings.get("Conflicts", set()):
                continue
            ref_point = points[1] if end_name == "Start" else points[0]
            polygon = self._clip_preview_polygon_to_plane(polygon, plane, ref_point)
            if not polygon or len(polygon) < 3:
                break

        if not polygon or len(polygon) < 3:
            return [], warnings

        closed = list(polygon)
        closed.append(FreeCAD.Vector(closed[0]))
        return [closed], warnings

    def _get_readout_base_gap(self):
        from draftutils import params

        units_per_pixel = self._get_plan_view_units_per_pixel() or 0.0
        text_height_pixels = float(params.get_param_view("MarkerSize") or 0.0) * 2.0 * 96.0 / 72.0
        return max(100.0, text_height_pixels * units_per_pixel * 1.25)

    def _get_aligned_readout_offset_for_wall(self, wall):
        width = getattr(getattr(wall, "Width", None), "Value", 0.0) if wall else 0.0
        width = float(width or 0.0)
        base_gap = max(width * 0.25, self._get_readout_base_gap())
        if width <= 0:
            return base_gap
        align = getattr(wall, "Align", "Center") if wall else "Center"
        if align == "Left":
            return base_gap
        if align == "Right":
            return -(base_gap)
        return width * 0.5 + base_gap

    def _get_wall_edit_readout_offset(self, mode):
        if mode in (2, 3):
            return self._get_readout_base_gap()
        if mode != 1:
            return None
        return self._get_aligned_readout_offset_for_wall(self._edit_wall)

    def _get_opening_move_readout_offset(self, opening):
        host = next(iter(getattr(opening, "Hosts", None) or []), None) if opening else None
        return self._get_aligned_readout_offset_for_wall(host)

    def _update_wall_edit_preview_geometry(self, points):
        if not points or len(points) != 2:
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        if self._preview_line_tracker is None:
            self._preview_line_tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-preview-axis",
                swidth=self._scaled_line_width(2),
                ontop=True,
            )
            self._preview_line_tracker.on()
        self._preview_line_tracker.p1(points[0])
        self._preview_line_tracker.p2(points[1])

        previous_relation_status = self._plan_relation_status_message
        polylines, relation_warnings = self._get_preview_footprint_polylines(points)
        if relation_warnings:
            label, status, _detail = relation_warnings[0]
            self._plan_relation_status_message = translate(
                "BIM_PlanEdit", "Preview warning: {label} ({status})"
            ).format(label=label, status=status)
        elif self._is_wall_edit_modal_active():
            self._clear_plan_relation_status()

        segments = []
        for polyline in polylines:
            if len(polyline) < 2:
                continue
            segments.extend(zip(polyline, polyline[1:]))

        color = (0.22, 0.53, 0.98)
        width = self._scaled_line_width(2)
        if len(self._preview_footprint_trackers) != len(segments):
            self._finalize_trackers(self._preview_footprint_trackers)
            self._preview_footprint_trackers = []
            for _start, _end in segments:
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "wall-edit-preview-footprint",
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                self._preview_footprint_trackers.append(tracker)

        for tracker, (start, end) in zip(self._preview_footprint_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

        if previous_relation_status != self._plan_relation_status_message:
            self._refresh_task_panel_status()

        midpoint = (points[0] + points[1]) * 0.5
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)

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

    def _sync_wall_edit_preview(self, points):
        self._update_wall_edit_preview_geometry(points)
        self._sync_wall_edit_readout(points)
        self._sync_wall_hosted_opening_preview(points)

    def _is_wall_move_edit_active(self):
        return bool(
            self._edit_wall and self._edit_endpoint == "Move" and self.current_tool == "Move Wall"
        )

    def _is_wall_stretch_edit_active(self):
        return bool(
            self._edit_wall
            and self._edit_endpoint in ("Start", "End")
            and self.current_tool in ("Stretch Start", "Stretch End")
        )

    def _is_wall_readout_edit_active(self):
        return bool(self._is_wall_move_edit_active() or self._is_wall_stretch_edit_active())

    def _clear_wall_edit_preview(self):
        if self._preview_line_tracker:
            try:
                self._preview_line_tracker.finalize()
            except Exception:
                pass
        self._preview_line_tracker = None

        self._finalize_trackers(self._preview_footprint_trackers)
        self._preview_footprint_trackers = []

        for tracker in self._preview_grip_trackers:
            try:
                tracker.finalize()
            except Exception:
                pass
        self._preview_grip_trackers = []
        self._clear_wall_edit_readout()
        self._clear_wall_hosted_opening_preview()

    def _get_wall_hosted_opening_preview_segments(self, wall, points):
        if not wall or not points or len(points) != 2:
            return []
        if self._edit_endpoint not in ("Start", "End"):
            return []

        layout = self._compute_wall_hosted_opening_layout(wall, points)
        if layout is None:
            return []

        segments = []
        for item in layout:
            delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
            if delta.Length < 1e-6:
                continue
            for polyline in self._get_opening_overlay_polylines(item["opening"]):
                if len(polyline) < 2:
                    continue
                translated = [FreeCAD.Vector(point).add(delta) for point in polyline]
                segments.extend(zip(translated, translated[1:]))
        return segments

    def _sync_wall_hosted_opening_preview(self, points):
        wall = self._edit_wall
        if self.current_tool not in ("Stretch Start", "Stretch End") or not wall:
            self._clear_wall_hosted_opening_preview()
            return

        segments = self._get_wall_hosted_opening_preview_segments(wall, points)
        if not segments:
            self._clear_wall_hosted_opening_preview()
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_wall_hosted_opening_preview()
            return

        color = (0.12, 0.38, 0.95)
        width = self._scaled_line_width(2)
        if len(self._wall_edit_opening_preview_trackers) != len(segments):
            self._clear_wall_hosted_opening_preview()
            for _start, _end in segments:
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "wall-edit-opening-preview",
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                self._wall_edit_opening_preview_trackers.append(tracker)

        for tracker, (start, end) in zip(self._wall_edit_opening_preview_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_wall_hosted_opening_preview(self):
        self._finalize_trackers(self._wall_edit_opening_preview_trackers)
        self._wall_edit_opening_preview_trackers = []

    def _get_wall_edit_readout_specs(self, points):
        if not points or len(points) != 2 or not self._edit_endpoints:
            return []

        original_points = self._edit_endpoints
        if self._edit_endpoint == "Move":
            original_midpoint = (original_points[0] + original_points[1]) * 0.5
            new_midpoint = (points[0] + points[1]) * 0.5
            return [
                (2, original_midpoint, new_midpoint),
                (3, original_midpoint, new_midpoint),
            ]

        return [(1, points[0], points[1])]

    def _get_default_wall_edit_readout_mode(self, specs):
        modes = [mode for mode, _start, _end in specs]
        if not modes:
            return None
        if self._is_wall_move_edit_active():
            if self._wall_edit_active_readout_mode in modes:
                return self._wall_edit_active_readout_mode
            if 2 in modes:
                return 2
        if 1 in modes:
            return 1
        return modes[0]

    def _bind_wall_edit_readout_callbacks(self, dim, mode):
        if mode == 1:
            dim.setValueChangedCallback(self._on_wall_stretch_length_changed)
            dim.setEditingFinishedCallback(self._on_wall_stretch_length_finished)
            if hasattr(dim, "setEditingCanceledCallback"):
                dim.setEditingCanceledCallback(self._on_wall_stretch_length_canceled)
            return

        dim.setValueChangedCallback(
            lambda value, delta_mode=mode: self._on_wall_move_delta_changed(delta_mode, value)
        )
        dim.setEditingFinishedCallback(
            lambda value, delta_mode=mode: self._on_wall_move_delta_finished(delta_mode, value)
        )
        if hasattr(dim, "setEditingCanceledCallback"):
            dim.setEditingCanceledCallback(
                lambda value, delta_mode=mode: self._on_wall_move_delta_canceled(delta_mode, value)
            )

    def _update_wall_edit_readouts_in_place(self, points, active_mode=None):
        specs = {
            mode: (start, end) for mode, start, end in self._get_wall_edit_readout_specs(points)
        }
        for tracker in self._wall_edit_readout_trackers:
            mode = getattr(tracker, "mode", None)
            if mode not in specs:
                continue
            start, end = specs[mode]
            if hasattr(tracker, "updatePoints"):
                tracker.updatePoints(start, end, sync_spinbox=(mode != active_mode))
            else:
                tracker.p1(start)
                tracker.p2(end)
            tracker.on()

    def _sync_wall_edit_readout(self, points):
        self._clear_wall_edit_readout()
        if not points or len(points) != 2 or not self._edit_endpoints:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except Exception:
            return

        readout_color = (0.12, 0.38, 0.95)
        dims = self._get_wall_edit_readout_specs(points)
        active_mode = self._get_default_wall_edit_readout_mode(dims)
        self._wall_edit_active_readout_mode = active_mode

        for mode, start, end in dims:
            try:
                if self._is_wall_readout_edit_active():
                    dim = DraftTrackers.editableArchDimTracker(mode=mode)
                else:
                    dim = DraftTrackers.archDimTracker(mode=mode)
            except Exception:
                continue
            try:
                if hasattr(dim, "dimnode"):
                    dim.dimnode.textColor.setValue(readout_color)
                else:
                    dim.setColor(readout_color)
            except Exception:
                pass
            offset = self._get_wall_edit_readout_offset(mode)
            if offset is not None:
                dim.offset = offset
            dim.p1(start)
            dim.p2(end)
            dim.on()
            if self._is_wall_readout_edit_active() and hasattr(dim, "setValueChangedCallback"):
                self._bind_wall_edit_readout_callbacks(dim, mode)
                if mode == active_mode:
                    self._wall_edit_active_readout_mode = mode
                    self._wall_edit_active_readout_tracker = dim
            if self._wall_edit_active_readout_tracker is None:
                self._wall_edit_active_readout_tracker = dim
            self._wall_edit_readout_trackers.append(dim)

    def _clear_wall_edit_readout(self):
        self._finalize_trackers(self._wall_edit_readout_trackers)
        self._wall_edit_readout_trackers = []
        self._wall_edit_active_readout_tracker = None
        self._wall_edit_active_readout_mode = None
        self._wall_edit_length_edit_queued = False

    def _get_wall_edit_readout_tracker(self, mode):
        for tracker in self._wall_edit_readout_trackers:
            if getattr(tracker, "mode", None) == mode:
                return tracker
        return None

    def _cycle_wall_move_readout_mode(self):
        if not self._is_wall_move_edit_active():
            return False
        modes = [
            getattr(tracker, "mode", None)
            for tracker in self._wall_edit_readout_trackers
            if getattr(tracker, "mode", None) in (2, 3)
        ]
        modes = [mode for mode in modes if mode is not None]
        if not modes:
            return False
        current_mode = (
            self._wall_edit_active_readout_mode
            if self._wall_edit_active_readout_mode in modes
            else modes[0]
        )
        next_mode = modes[(modes.index(current_mode) + 1) % len(modes)]
        self._wall_edit_active_readout_mode = next_mode
        tracker = self._get_wall_edit_readout_tracker(next_mode)
        if tracker is not None:
            self._wall_edit_active_readout_tracker = tracker
        return True

    def _start_wall_readout_edit(self, cycle=False):
        tracker = self._wall_edit_active_readout_tracker
        if not self._is_wall_readout_edit_active():
            return False
        if cycle and self._is_wall_move_edit_active():
            if (
                tracker is not None
                and hasattr(tracker, "isInEdit")
                and tracker.isInEdit()
                and hasattr(tracker, "stopEdit")
            ):
                tracker.stopEdit()
            if not self._cycle_wall_move_readout_mode():
                return False
            tracker = self._wall_edit_active_readout_tracker
        if tracker is None:
            return False
        if not hasattr(tracker, "startEdit"):
            return False
        if hasattr(tracker, "isInEdit") and tracker.isInEdit():
            if hasattr(tracker, "label"):
                tracker.label.setFocusToSpinbox()
            return True
        if self._wall_edit_length_edit_queued:
            return True
        self._wall_edit_length_edit_queued = True
        self._stop_snapper()
        try:
            from PySide import QtCore
        except ImportError:
            self._wall_edit_length_edit_queued = False
            tracker.startEdit(tracker.Distance)
            return True
        QtCore.QTimer.singleShot(
            0, lambda: self._start_wall_readout_edit_now(tracker, tracker.Distance)
        )
        return True

    def _start_wall_stretch_length_edit(self):
        return self._start_wall_readout_edit(cycle=False)

    def _start_wall_readout_edit_now(self, tracker, value):
        self._wall_edit_length_edit_queued = False
        if not self._is_wall_readout_edit_active():
            return
        if tracker is None or tracker is not self._wall_edit_active_readout_tracker:
            return
        if not hasattr(tracker, "startEdit"):
            return
        if hasattr(tracker, "isInEdit") and tracker.isInEdit():
            if hasattr(tracker, "label"):
                tracker.label.setFocusToSpinbox()
            return
        try:
            tracker.startEdit(value)
        except Exception:
            return

    def _on_wall_stretch_length_changed(self, value):
        if not self._is_wall_stretch_edit_active():
            return
        new_points = self._compute_wall_edit_points_from_length(value)
        tracker = self._wall_edit_active_readout_tracker
        if not new_points or tracker is None:
            return
        self._preview_points = new_points
        self._update_wall_edit_preview_geometry(new_points)
        self._update_wall_edit_readouts_in_place(new_points, active_mode=1)
        self._sync_wall_hosted_opening_preview(new_points)

    def _on_wall_stretch_length_finished(self, value):
        if not self._is_wall_stretch_edit_active():
            return
        wall = self._edit_wall
        endpoint = self._edit_endpoint
        proxy = getattr(wall, "Proxy", None)
        new_points = self._compute_wall_edit_points_from_length(value)
        if not new_points or not proxy:
            return
        self._preview_points = new_points
        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _on_wall_stretch_length_canceled(self, value):
        del value
        if not self._is_wall_stretch_edit_active():
            return
        self._schedule_wall_edit_readout_cancel()

    def _compute_wall_edit_points_from_move_delta(self, mode, value):
        if not self._is_wall_move_edit_active() or not self._edit_endpoints:
            return None
        original_endpoints = self._edit_endpoints
        original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
        preview_points = self._preview_points if self._preview_points else original_endpoints
        current_midpoint = (preview_points[0] + preview_points[1]) * 0.5
        target_midpoint = FreeCAD.Vector(current_midpoint)
        if mode == 2:
            target_midpoint.x = original_midpoint.x + float(value)
        elif mode == 3:
            target_midpoint.y = original_midpoint.y + float(value)
        else:
            return None
        delta = target_midpoint.sub(original_midpoint)
        return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]

    def _on_wall_move_delta_changed(self, mode, value):
        if not self._is_wall_move_edit_active():
            return
        new_points = self._compute_wall_edit_points_from_move_delta(mode, value)
        if not new_points:
            return
        self._preview_points = new_points
        self._update_wall_edit_preview_geometry(new_points)
        self._update_wall_edit_readouts_in_place(new_points, active_mode=mode)
        self._sync_wall_hosted_opening_preview(new_points)

    def _on_wall_move_delta_finished(self, mode, value):
        if not self._is_wall_move_edit_active():
            return
        wall = self._edit_wall
        endpoint = self._edit_endpoint
        proxy = getattr(wall, "Proxy", None)
        new_points = self._compute_wall_edit_points_from_move_delta(mode, value)
        if not new_points or not proxy:
            return
        self._preview_points = new_points
        self._commit_wall_edit_points(wall, endpoint, proxy, new_points)

    def _on_wall_move_delta_canceled(self, mode, value):
        del mode, value
        if not self._is_wall_move_edit_active():
            return
        self._schedule_wall_edit_readout_cancel()

    def _schedule_wall_edit_readout_cancel(self):
        preview_points = None
        if self._preview_points:
            preview_points = [FreeCAD.Vector(point) for point in self._preview_points]
        elif self._edit_endpoints:
            preview_points = [FreeCAD.Vector(point) for point in self._edit_endpoints]
        try:
            from PySide import QtCore
        except ImportError:
            self._finish_wall_edit_readout_canceled(preview_points)
            return
        QtCore.QTimer.singleShot(
            0, lambda pts=preview_points: self._finish_wall_edit_readout_canceled(pts)
        )

    def _finish_wall_edit_readout_canceled(self, preview_points):
        if not self._is_wall_readout_edit_active():
            return
        if preview_points:
            self._sync_wall_edit_preview(preview_points)
        self._resume_wall_edit_point_pick()

    def _restore_edit_wall_visibility(self):
        wall = self._edit_wall
        if wall is not None and self._edit_wall_visibility is not None:
            try:
                wall.ViewObject.Visibility = self._edit_wall_visibility
            except Exception:
                pass
        self._edit_wall_visibility = None

    def _update_wall_edit_preview(self, point):
        new_points = self._compute_wall_edit_points(point)
        if not new_points:
            return
        self._preview_points = new_points
        self._sync_wall_edit_preview(new_points)

    def _update_wall_edit_point_pick(self, point=None, snap_info=None):
        del snap_info
        if self._wall_edit_active_readout_tracker and hasattr(
            self._wall_edit_active_readout_tracker, "isInEdit"
        ):
            if self._wall_edit_active_readout_tracker.isInEdit():
                return
        self._update_wall_edit_preview(point)

    def _cancel_wall_edit_point_pick(self):
        self.current_tool = "Select"
        self._cancel_pending_edit()
        self._refresh_task_panel_status()

    def _get_edit_node(self, mouse_pos):
        symbol_handle_role = self._pick_selected_symbol_handle(mouse_pos)
        if symbol_handle_role is not None:
            return (
                "symbol_handle",
                self._get_selected_plan_target_object("symbol"),
                symbol_handle_role,
            )
        opening_handle_index = self._pick_selected_opening_handle(mouse_pos)
        if opening_handle_index is not None:
            return (
                "opening_handle",
                self._get_selected_plan_target_object("opening"),
                opening_handle_index,
            )
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
                return ("edit_node", point)
        return None

    def _pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        opening = self._get_selected_plan_target_object("opening")
        if not self._is_hosted_opening_object(opening) or not self.view:
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_index = None
        best_distance_sq = None
        for idx, point, _marker in self._get_selected_opening_handle_specs(opening):
            try:
                screen_x, screen_y = self.view.getPointOnScreen(point)
            except Exception:
                continue
            dx = float(screen_x) - float(cursor_x)
            dy = float(screen_y) - float(cursor_y)
            distance_sq = dx * dx + dy * dy
            if distance_sq > radius_px * radius_px:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_index = idx
                best_distance_sq = distance_sq
        return best_index

    def _on_mouse_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return

        event = event_callback.getEvent()
        mouse_pos = None
        try:
            pos = event.getPosition().getValue()
            mouse_pos = (pos[0], pos[1])
        except Exception:
            mouse_pos = None
        selected_before = self._get_selected_plan_target()
        with self._plan_perf_trace_event(
            "mouse_pressed",
            button=str(event.getButton()),
            state=str(event.getState()),
            mouse_pos=mouse_pos,
            selected_before=self._plan_perf_describe_target(selected_before[0], selected_before[1]),
        ):
            if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
                return
            try:
                if event.getState() == coin.SoMouseButtonEvent.UP:
                    if self._consume_left_button_release:
                        self._consume_left_button_release = False
                        self._set_event_handled(event_callback)
                    return

                if event.getState() == coin.SoMouseButtonEvent.DOWN:
                    self._consume_left_button_release = False
                    if self.current_tool == "Join":
                        pos = event.getPosition().getValue()
                        target_kind, target_wall = self._get_plan_target_at_position(
                            (pos[0], pos[1])
                        )
                        source_wall = self._get_selected_plan_target_object("wall")
                        if (
                            target_kind == "wall"
                            and self._is_plan_selectable_wall(target_wall)
                            and target_wall != source_wall
                            and self._apply_plan_wall_join(source_wall, target_wall)
                        ):
                            self._claim_left_button_click(event_callback)
                        return
                    if self.current_tool == "Pick Space Region":
                        pos = event.getPosition().getValue()
                        candidate = self._pick_space_region_candidate((pos[0], pos[1]))
                        if candidate:
                            self._activate_space_region_candidate(candidate, event_callback)
                        return
                    if self.current_tool != "Select":
                        return
                    pos = event.getPosition().getValue()
                    mouse_pos = (pos[0], pos[1])
                    if self._is_plan_additive_selection_active():
                        if not self._toggle_plan_target_selection_at_position(
                            mouse_pos, event_callback
                        ):
                            self._claim_left_button_click(event_callback)
                        return
                    node = self._get_edit_node(mouse_pos)
                    if not node:
                        if self._activate_semantic_plan_target(mouse_pos, event_callback):
                            return
                        self._clear_plan_selection_state()
                        self._claim_left_button_click(event_callback)
                        return
                    node_kind = node[0]
                    if node_kind == "opening_handle":
                        _kind, obj, index = node
                        self._select_opening_for_plan_edit(obj)
                        self._set_gui_selection_object(obj)
                        self._activate_opening_handle(obj, index)
                    elif node_kind == "symbol_handle":
                        _kind, obj, role = node
                        self._set_selected_plan_target_state("symbol", obj)
                        self._clear_wall_grips()
                        self._activate_symbol_handle(obj, role)
                    else:
                        point = node[1]
                        try:
                            doc = FreeCAD.getDocument(str(point.documentName.getValue()))
                            obj = doc.getObject(str(point.objectName.getValue()))
                            index = int(str(point.subElementName.getValue())[8:])
                        except Exception:
                            return
                        if self._is_hosted_opening_object(obj):
                            self._select_opening_for_plan_edit(obj)
                            self._set_gui_selection_object(obj)
                            self._activate_opening_handle(obj, index)
                        else:
                            self._set_selected_plan_target_state("wall", obj)
                            self._activate_wall_grip(index, wall=obj)
                    self._claim_left_button_click(event_callback)
            finally:
                selected_after = self._get_selected_plan_target()
                self._plan_perf_set_fields(
                    handled=bool(getattr(event_callback, "_handled", False)),
                    selected_after=self._plan_perf_describe_target(
                        selected_after[0], selected_after[1]
                    ),
                )

    def _on_mouse_moved(self, event_callback):
        if self._tearing_down:
            return
        if self.current_tool == "Pick Space Region":
            event = event_callback.getEvent()
            pos = event.getPosition().getValue()
            self._set_hovered_space_region_candidate(
                self._pick_space_region_candidate((pos[0], pos[1]))
            )
            self._refresh_plan_overlay_visuals()
            return
        if self.current_tool not in ("Select", "Join"):
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            return
        event = event_callback.getEvent()
        pos = event.getPosition().getValue()
        self._update_hovered_plan_target((pos[0], pos[1]))
        self._refresh_plan_overlay_visuals()

    def _on_mouse_wheel(self, event_callback):
        if self._tearing_down:
            return
        event = event_callback.getEvent()
        try:
            event_type_name = str(event.getTypeId().getName())
        except Exception:
            event_type_name = ""
        if event_type_name != "SoMouseWheelEvent":
            return
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)

    def _queue_plan_overlay_visual_refresh(self, *visuals):
        if self._tearing_down:
            return
        dirty = set(visuals) if visuals else {_PLAN_VISUAL_ALL}
        if _PLAN_VISUAL_ALL in dirty or _PLAN_VISUAL_SELECTED_SPACE in dirty:
            self._invalidate_selected_space_overlay_cache()
        self._dirty_plan_visuals.update(dirty)
        if self._overlay_refresh_queued:
            return
        try:
            from PySide import QtCore
        except ImportError:
            dirty = self._consume_dirty_plan_visuals()
            self._refresh_plan_overlay_visuals(dirty)
            return
        self._overlay_refresh_queued = True
        QtCore.QTimer.singleShot(0, self._flush_plan_overlay_visual_refresh)

    def _consume_dirty_plan_visuals(self):
        dirty = set(self._dirty_plan_visuals)
        self._dirty_plan_visuals.clear()
        return dirty or {_PLAN_VISUAL_ALL}

    def _flush_plan_overlay_visual_refresh(self):
        self._overlay_refresh_queued = False
        dirty = self._consume_dirty_plan_visuals()
        self._refresh_plan_overlay_visuals(dirty)

    def _refresh_plan_overlay_visuals(self, dirty=None):
        if self._tearing_down:
            return
        dirty = set(dirty or {_PLAN_VISUAL_ALL})
        refresh_all = _PLAN_VISUAL_ALL in dirty
        if self.current_tool == "Join":
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            self._sync_junction_node_overlays()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            return
        if self.current_tool == "Region":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            return
        if self.current_tool == "Set Space Text":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_space_region_pick_overlays()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_region_overlay()
            self._clear_secondary_selected_overlays()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            if self._is_selected_plan_target("space") and (
                refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty
            ):
                self._refresh_selected_space_visuals()
            return
        if self.current_tool == "Pick Space Region":
            self._clear_junction_node_overlays()
            self._clear_hovered_wall_overlay()
            self._clear_hovered_wall_opening_context_overlay()
            self._clear_hovered_opening_overlay()
            self._clear_hovered_symbol_overlay()
            self._clear_hovered_space_overlay()
            self._clear_hovered_region_overlay()
            self._clear_selected_opening_overlay()
            self._clear_selected_symbol_overlay()
            self._clear_selected_space_overlay()
            self._clear_selected_region_overlay()
            self._clear_selected_opening_handles()
            self._clear_selected_symbol_handles()
            self._clear_selected_wall_opening_context_overlay()
            self._clear_wall_grips()
            if (
                refresh_all
                or _PLAN_VISUAL_SECONDARY_SELECTION in dirty
                or _PLAN_VISUAL_SPACE_REGION_PICK in dirty
            ):
                self._sync_secondary_selected_overlays()
                self._sync_space_region_pick_overlays()
            return
        if self.current_tool == "Select":
            self._clear_space_region_pick_overlays()
            self._sync_junction_node_overlays()
            if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
                self._sync_hovered_wall_overlay()
            self._sync_selected_wall_opening_context_overlay()
            self._sync_hovered_wall_opening_context_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_OPENING in dirty:
                self._sync_hovered_opening_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_SYMBOL in dirty:
                self._sync_hovered_symbol_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_SPACE in dirty:
                self._sync_hovered_space_overlay()
            if refresh_all or _PLAN_VISUAL_HOVERED_REGION in dirty:
                self._sync_hovered_region_overlay()
            if refresh_all or _PLAN_VISUAL_SELECTED_OPENING in dirty:
                self._sync_selected_opening_overlay()
                self._sync_selected_opening_handles()
            if refresh_all or _PLAN_VISUAL_SELECTED_SYMBOL in dirty:
                self._sync_selected_symbol_overlay()
                self._sync_selected_symbol_handles()
            if refresh_all or _PLAN_VISUAL_SELECTED_REGION in dirty:
                self._sync_selected_region_overlay()
            if refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty:
                self._sync_selected_space_overlay()
            if refresh_all or _PLAN_VISUAL_SECONDARY_SELECTION in dirty:
                self._sync_secondary_selected_overlays()
            if refresh_all or _PLAN_VISUAL_SPACE_REGION_PICK in dirty:
                self._clear_space_region_pick_overlays()
            if refresh_all or _PLAN_VISUAL_WALL_GRIPS in dirty:
                self._sync_wall_grips()
            return

    def _on_key_pressed(self, event_callback):
        if self._tearing_down:
            return
        try:
            from pivy import coin
        except Exception:
            return
        event = event_callback.getEvent()
        key = event.getKey()
        if self.current_tool == "Move Opening" and key == coin.SoKeyboardEvent.A:
            if self._cycle_opening_move_anchor():
                self._refresh_opening_move_preview_from_raw_point()
                self._refresh_task_panel_status()
            return
        if (
            self.current_tool in ("Move Symbol", "Rotate Symbol")
            and key == coin.SoKeyboardEvent.ESCAPE
        ):
            self._cancel_symbol_handle_point_pick()
            return
        if self.current_tool == "Join" and key == coin.SoKeyboardEvent.TAB:
            if self._cycle_plan_join_type() and hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
            return
        if self.current_tool == "Join" and key in (
            getattr(coin.SoKeyboardEvent, "DELETE", None),
            getattr(coin.SoKeyboardEvent, "BACKSPACE", None),
        ):
            if self._unjoin_current_plan_wall_pair() and hasattr(event_callback, "setHandled"):
                event_callback.setHandled()
            return
        if self.current_tool == "Join" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_join_tool()
            return
        if self.current_tool == "Pick Space Region" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_space_region_pick()
            return
        if self.current_tool == "Region" and key in (
            coin.SoKeyboardEvent.RETURN,
            coin.SoKeyboardEvent.ENTER,
        ):
            if self._finalize_plan_region():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self.current_tool == "Region" and key == coin.SoKeyboardEvent.ESCAPE:
            self._cancel_plan_region_tool()
            return
        if self._is_wall_move_edit_active() and key == coin.SoKeyboardEvent.TAB:
            if self._start_wall_readout_edit(cycle=True):
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self._is_wall_readout_edit_active() and key in (
            coin.SoKeyboardEvent.RETURN,
            coin.SoKeyboardEvent.ENTER,
        ):
            if self._start_wall_readout_edit():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if self._is_wall_stretch_edit_active() and key == coin.SoKeyboardEvent.TAB:
            if self._start_wall_readout_edit():
                if hasattr(event_callback, "setHandled"):
                    event_callback.setHandled()
            return
        if key != coin.SoKeyboardEvent.ESCAPE:
            return
        if self._edit_wall and self.current_tool != "Select":
            self._cancel_wall_edit_point_pick()
            return
        if self.current_tool == "Move Opening":
            self._cancel_opening_handle_point_pick()
            return
        if self.current_tool in ("Move Symbol", "Rotate Symbol"):
            self._cancel_symbol_handle_point_pick()
            return
        if self.current_tool == "Set Space Text":
            self._cancel_space_text_position_pick()
            return
        if self._has_active_rect_wall_tool():
            self._cancel_rect_wall_tool()
            return
        if self._has_active_plan_region_tool():
            self._cancel_plan_region_tool()
            return
        if self._has_active_space_separator_tool():
            self._cancel_space_separator_tool()

    # Selection observer interface

    def addSelection(self, doc, obj, sub, point):
        with self._plan_perf_trace_event(
            "selection_observer_add",
            selection_document=doc,
            selection_object=obj,
            selection_subelement=sub,
        ):
            self._plan_perf_count("selection_observer_callbacks")
            if self._tearing_down:
                return
            if self._ignore_selection_changes:
                return
            if sub in ("EditNode0", "EditNode1", "EditNode2"):
                return
            del doc, obj, sub, point
            self._refresh_primary_selected_plan_target()

    def removeSelection(self, doc, obj, sub):
        with self._plan_perf_trace_event(
            "selection_observer_remove",
            selection_document=doc,
            selection_object=obj,
            selection_subelement=sub,
        ):
            self._plan_perf_count("selection_observer_callbacks")
            if self._tearing_down:
                return
            if self._ignore_selection_changes:
                return
            del doc, obj, sub
            self._refresh_primary_selected_plan_target()

    def setSelection(self, doc):
        with self._plan_perf_trace_event("selection_observer_set", selection_document=doc):
            self._plan_perf_count("selection_observer_callbacks")
            if self._tearing_down:
                return
            if self._ignore_selection_changes:
                return
            del doc
            self._refresh_primary_selected_plan_target()

    def clearSelection(self, doc):
        with self._plan_perf_trace_event("selection_observer_clear", selection_document=doc):
            self._plan_perf_count("selection_observer_callbacks")
            if self._tearing_down:
                return
            if self._ignore_selection_changes:
                return
            del doc
            self._refresh_primary_selected_plan_target()

    # Document observer interface

    def _is_opening_visual_dependency(self, opening, obj):
        if not opening or not obj:
            return False
        if obj == opening:
            return True
        if obj == getattr(opening, "Base", None):
            return True
        return obj in (getattr(opening, "Hosts", None) or [])

    def _refresh_selected_opening_visuals(self):
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_wall_opening_context_overlay()
        self._request_view_redraw()

    def _is_symbol_visual_dependency(self, symbol, obj):
        if not self._is_plan_symbol_instance(symbol) or not obj:
            return False
        if obj == symbol:
            return True
        semantic_obj = self._get_plan_semantic_object(symbol)
        if obj == semantic_obj:
            return True
        if obj == getattr(semantic_obj, "Base", None):
            return True
        return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])

    def _refresh_plan_object_footprint_display(self, obj):
        if not self._is_supported_plan_object(obj):
            return
        self._invalidate_plan_overlay_geometry_cache(obj)
        semantic_obj = self._get_plan_semantic_object(obj)
        refresh_targets = []
        for candidate in (semantic_obj, obj):
            if not candidate:
                continue
            name = getattr(candidate, "Name", None)
            if not name or any(getattr(target, "Name", None) == name for target in refresh_targets):
                continue
            refresh_targets.append(candidate)

        refreshed = False
        for candidate in refresh_targets:
            view_object = getattr(candidate, "ViewObject", None)
            proxy = getattr(view_object, "Proxy", None) if view_object else None
            if not proxy:
                continue
            if not hasattr(proxy, "ensureFootprintGroup") and not hasattr(proxy, "updateFootprint"):
                continue
            try:
                if hasattr(proxy, "ensureFootprintGroup"):
                    proxy.ensureFootprintGroup(view_object)
                if hasattr(proxy, "updateFootprint"):
                    proxy.updateFootprint()
                if hasattr(view_object, "update"):
                    view_object.update()
                refreshed = True
            except Exception:
                continue

        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "update"):
            try:
                view_object.update()
            except Exception:
                pass
        if not refreshed:
            return
        self._request_view_redraw()

    def _refresh_opening_footprint_display(self, opening):
        if not self._is_hosted_opening_object(opening):
            return
        self._refresh_plan_object_footprint_display(opening)

    def _refresh_wall_footprint_display(self, wall):
        if not wall:
            return
        self._refresh_plan_object_footprint_display(wall)

    def _get_wall_hosted_openings(self, wall):
        if not wall or not self.doc:
            return []
        openings = []
        for obj in getattr(self.doc, "Objects", []) or []:
            if not self._is_hosted_opening_object(obj):
                continue
            if wall in (getattr(obj, "Hosts", None) or []):
                openings.append(obj)
        return openings

    def _refresh_wall_hosted_opening_footprints(self, wall):
        for opening in self._get_wall_hosted_openings(wall):
            self._refresh_opening_footprint_display(opening)

    def _compute_wall_hosted_opening_layout(self, wall, endpoints):
        if not wall:
            return []
        if not endpoints or len(endpoints) != 2:
            return []
        wall_origin = FreeCAD.Vector(endpoints[0])
        wall_end = FreeCAD.Vector(endpoints[1])
        wall_axis_u = wall_end.sub(wall_origin)
        wall_length = wall_axis_u.Length
        if wall_length < 1e-9:
            return None
        wall_axis_u.normalize()

        openings = []
        for opening in self._get_wall_hosted_openings(wall):
            proxy = self._get_opening_plan_proxy(
                opening, "get_plan_move_context", "move_along_host", "get_plan_center_point"
            )
            if not proxy:
                continue
            context = proxy.get_plan_move_context()
            if not context:
                continue
            current_center = proxy.get_plan_center_point()
            if current_center is None:
                continue
            current = FreeCAD.Vector(current_center)
            delta = current.sub(wall_origin)
            half_width = float(context.get("opening_half_width_u") or 0.0)
            desired_u = delta.dot(wall_axis_u)
            clearance_seed = self._wall_edit_opening_clearances.get(getattr(opening, "Name", ""))
            if clearance_seed:
                if self._edit_endpoint == "Start":
                    desired_u = max(
                        desired_u,
                        half_width + float(clearance_seed.get("left_clearance") or 0.0),
                    )
                elif self._edit_endpoint == "End":
                    desired_u = min(
                        desired_u,
                        wall_length
                        - half_width
                        - float(clearance_seed.get("right_clearance") or 0.0),
                    )
            low = half_width
            high = wall_length - half_width
            if low > high:
                midpoint = wall_length * 0.5
                low = midpoint
                high = midpoint
            item = {
                "opening": opening,
                "proxy": proxy,
                "current": current,
                "desired_u": desired_u,
                "low": low,
                "high": high,
                "half_width": half_width,
                "clearance_seed": clearance_seed,
            }
            openings.append(item)

        if not openings:
            return []

        openings.sort(key=lambda item: (item["desired_u"], getattr(item["opening"], "Name", "")))

        left = []
        for index, item in enumerate(openings):
            minimum = item["low"]
            if index > 0:
                minimum = max(
                    minimum,
                    left[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
                )
            if minimum > item["high"] + 1e-6:
                return None
            left.append(minimum)

        right = [0.0] * len(openings)
        for index in range(len(openings) - 1, -1, -1):
            maximum = openings[index]["high"]
            if index < len(openings) - 1:
                maximum = min(
                    maximum,
                    right[index + 1]
                    - openings[index]["half_width"]
                    - openings[index + 1]["half_width"],
                )
            if maximum < openings[index]["low"] - 1e-6:
                return None
            right[index] = maximum

        resolved = []
        for index, item in enumerate(openings):
            center_u = min(max(item["desired_u"], left[index]), right[index])
            if index > 0:
                center_u = max(
                    center_u,
                    resolved[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
                )
            if center_u > right[index] + 1e-6:
                return None
            resolved.append(center_u)

        layout = []
        for item, center_u in zip(openings, resolved):
            target_point = wall_origin.add(FreeCAD.Vector(wall_axis_u).multiply(center_u))
            target_point.z = item["current"].z
            layout.append(
                {
                    **item,
                    "target_center_u": center_u,
                    "target_point": target_point,
                }
            )

        return layout

    def _resolve_wall_hosted_opening_layout(self, wall):
        wall_proxy = getattr(wall, "Proxy", None)
        if not wall_proxy or not hasattr(wall_proxy, "calc_endpoints"):
            return True
        try:
            endpoints = wall_proxy.calc_endpoints(wall)
        except Exception:
            return True
        layout = self._compute_wall_hosted_opening_layout(wall, endpoints)
        if layout is None:
            return False
        for item in layout:
            if not item["proxy"].move_along_host(item["target_point"]):
                return False

        return True

    def _refresh_opening_host_footprint_displays(self, opening):
        if not self._is_hosted_opening_object(opening):
            return
        for host in getattr(opening, "Hosts", None) or []:
            self._refresh_wall_footprint_display(host)

    def _queue_recompute_opening_hosts(self, *openings):
        if (
            self._tearing_down
            or self._opening_host_recompute_queued
            or self._opening_host_recompute_running
        ):
            return
        hosts = []
        for opening in openings:
            if not self._is_hosted_opening_object(opening):
                continue
            hosts.extend(getattr(opening, "Hosts", None) or [])
        hosts = [host for host in dict.fromkeys(hosts) if host]
        if not hosts:
            return
        self._opening_host_recompute_queued = True
        self._flush_recompute_opening_hosts(hosts)

    def _flush_recompute_opening_hosts(self, hosts):
        self._opening_host_recompute_queued = False
        if self._tearing_down or self._opening_host_recompute_running or not self.doc:
            return
        self._opening_host_recompute_running = True
        try:
            for host in hosts:
                try:
                    host.touch()
                except Exception:
                    continue
            self.doc.recompute()
        finally:
            self._opening_host_recompute_running = False

    def _queue_hard_refresh_selected_opening_visuals(self):
        if self._tearing_down or self._selected_opening_hard_refresh_queued:
            return
        self._selected_opening_hard_refresh_queued = True
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._request_view_redraw()
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, self._flush_hard_refresh_selected_opening_visuals)
        except Exception:
            self._flush_hard_refresh_selected_opening_visuals()

    def _flush_hard_refresh_selected_opening_visuals(self):
        self._selected_opening_hard_refresh_queued = False
        if self._tearing_down or self.current_tool != "Select":
            return
        opening = self._get_selected_plan_target_object("opening")
        if not self._is_hosted_opening_object(opening):
            return
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._request_view_redraw()

    def slotCreatedObject(self, obj):
        if self._tearing_down:
            return
        self._queue_created_plan_object(obj)

    def slotChangedObject(self, obj, prop):
        if self._tearing_down:
            return
        if self.current_tool != "Select":
            return
        self._sanitize_plan_target_references()
        selected_wall = self._get_selected_plan_target_object("wall")
        selected_opening = self._get_selected_plan_target_object("opening")
        selected_symbol = self._get_selected_plan_target_object("symbol")
        selected_region = self._get_selected_plan_target_object("region")
        selected_space = self._get_selected_plan_target_object("space")
        if selected_region and obj == selected_region and prop in _REGION_VISUAL_PROPERTIES:
            self._refresh_plan_object_footprint_display(selected_region)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_REGION)
            self._refresh_task_panel_status()
            return
        if (
            self.hovered_region
            and not self._is_selected_plan_target("region", self.hovered_region)
            and obj == self.hovered_region
            and prop in _REGION_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_region)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_REGION)
            return
        if selected_space and obj == selected_space and prop in _SPACE_VISUAL_PROPERTIES:
            self._refresh_plan_object_footprint_display(selected_space)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SPACE)
            self._refresh_task_panel_status()
            return
        if (
            self.hovered_space
            and not self._is_selected_plan_target("space", self.hovered_space)
            and obj == self.hovered_space
            and prop in _SPACE_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_space)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SPACE)
            return
        secondary_overlay_refresh = False
        for target_kind, target_obj in self._get_secondary_selected_plan_targets():
            if target_kind == "region" and obj == target_obj and prop in _REGION_VISUAL_PROPERTIES:
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif target_kind == "space" and obj == target_obj and prop in _SPACE_VISUAL_PROPERTIES:
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif (
                target_kind == "symbol"
                and self._is_symbol_visual_dependency(target_obj, obj)
                and prop in _SYMBOL_VISUAL_PROPERTIES
            ):
                self._refresh_plan_object_footprint_display(target_obj)
                secondary_overlay_refresh = True
            elif (
                target_kind == "opening"
                and self._is_opening_visual_dependency(target_obj, obj)
                and prop in _OPENING_VISUAL_PROPERTIES
            ):
                self._refresh_opening_footprint_display(target_obj)
                self._refresh_opening_host_footprint_displays(target_obj)
                secondary_overlay_refresh = True
            elif target_kind == "wall" and obj == target_obj and prop in _WALL_VISUAL_PROPERTIES:
                secondary_overlay_refresh = True
        if secondary_overlay_refresh:
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SECONDARY_SELECTION)
            return
        if (
            self._is_symbol_visual_dependency(selected_symbol, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(selected_symbol)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SYMBOL)
            return
        if (
            self._is_symbol_visual_dependency(self.hovered_symbol, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            self._refresh_plan_object_footprint_display(self.hovered_symbol)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SYMBOL)
            return
        if (
            self._is_opening_visual_dependency(selected_opening, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(selected_opening)
            self._refresh_opening_host_footprint_displays(selected_opening)
            self._queue_plan_overlay_visual_refresh(
                _PLAN_VISUAL_SELECTED_OPENING,
                _PLAN_VISUAL_HOVERED_OPENING,
            )
            return
        if (
            self._is_opening_visual_dependency(self.hovered_opening, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(self.hovered_opening)
            self._refresh_opening_host_footprint_displays(self.hovered_opening)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_OPENING)
            return
        if (
            self.hovered_wall
            and obj in self._get_wall_hosted_openings(self.hovered_wall)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(obj)
            self._refresh_opening_host_footprint_displays(obj)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
            return
        if (
            selected_wall
            and obj in self._get_wall_hosted_openings(selected_wall)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            self._refresh_opening_footprint_display(obj)
            self._refresh_opening_host_footprint_displays(obj)
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_WALL_GRIPS)
            return
        if obj == self.hovered_wall and prop in _WALL_VISUAL_PROPERTIES:
            self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
            return
        if obj != selected_wall:
            return
        if prop not in _WALL_VISUAL_PROPERTIES:
            return
        self._refresh_wall_hosted_opening_footprints(obj)
        self._schedule_selected_wall_reset(prop, obj)

    def slotDeletedObject(self, obj):
        if self._tearing_down:
            return
        self._invalidate_plan_overlay_geometry_cache(obj)
        if obj == self.hovered_wall:
            self.hovered_wall = None
            self._clear_hovered_wall_overlay()
        if obj == self.hovered_opening:
            self.hovered_opening = None
            self._clear_hovered_opening_overlay()
        if obj == self.hovered_symbol:
            self.hovered_symbol = None
            self._clear_hovered_symbol_overlay()
        if obj == self.hovered_space:
            self.hovered_space = None
            self._clear_hovered_space_overlay()
        if obj == self.hovered_region:
            self.hovered_region = None
            self._clear_hovered_region_overlay()
        if self._clear_selected_plan_target_if_matches("opening", obj):
            self._refresh_selected_opening_visuals()
            return
        if self._clear_selected_plan_target_if_matches("symbol", obj):
            self._refresh_selected_symbol_visuals()
            return
        if self._clear_selected_plan_target_if_matches("region", obj):
            self._refresh_selected_region_visuals()
            self._refresh_task_panel_status()
            return
        if self._clear_selected_plan_target_if_matches("space", obj):
            self._refresh_selected_space_visuals()
            self._refresh_task_panel_status()
            return
        if not self._is_selected_plan_target("wall", obj):
            return
        self._schedule_selected_wall_reset("Deleted", obj)

    def _invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        self._invalidate_plan_overlay_geometry_cache()
        self._sanitize_plan_target_references()
        selected_symbol = self._get_selected_plan_target_object("symbol")
        selected_region = self._get_selected_plan_target_object("region")
        selected_space = self._get_selected_plan_target_object("space")
        selected_opening = self._get_selected_plan_target_object("opening")
        if selected_symbol:
            self._refresh_plan_object_footprint_display(selected_symbol)
        if self.hovered_symbol and not self._is_selected_plan_target("symbol", self.hovered_symbol):
            self._refresh_plan_object_footprint_display(self.hovered_symbol)
        if selected_region:
            self._refresh_plan_object_footprint_display(selected_region)
        if self.hovered_region and not self._is_selected_plan_target("region", self.hovered_region):
            self._refresh_plan_object_footprint_display(self.hovered_region)
        if selected_space:
            self._refresh_plan_object_footprint_display(selected_space)
        if self.hovered_space and not self._is_selected_plan_target("space", self.hovered_space):
            self._refresh_plan_object_footprint_display(self.hovered_space)
        secondary_targets = self._get_secondary_selected_plan_targets()
        for target_kind, target_obj in secondary_targets:
            if target_kind in ("symbol", "region", "space"):
                self._refresh_plan_object_footprint_display(target_obj)
            elif target_kind == "opening":
                self._refresh_opening_footprint_display(target_obj)
                self._refresh_opening_host_footprint_displays(target_obj)
        if selected_opening:
            self._refresh_opening_footprint_display(selected_opening)
            self._refresh_opening_host_footprint_displays(selected_opening)
            self._queue_hard_refresh_selected_opening_visuals()
        if self.hovered_opening and not self._is_selected_plan_target(
            "opening", self.hovered_opening
        ):
            self._refresh_opening_footprint_display(self.hovered_opening)
            self._refresh_opening_host_footprint_displays(self.hovered_opening)
        if recompute_opening_hosts:
            self._queue_recompute_opening_hosts(selected_opening, self.hovered_opening)
        visual_args = [
            _PLAN_VISUAL_SELECTED_SYMBOL,
            _PLAN_VISUAL_HOVERED_SYMBOL,
            _PLAN_VISUAL_HOVERED_OPENING,
            _PLAN_VISUAL_HOVERED_WALL,
            _PLAN_VISUAL_WALL_GRIPS,
        ]
        if selected_region:
            visual_args.append(_PLAN_VISUAL_SELECTED_REGION)
        if self.hovered_region and not self._is_selected_plan_target("region", self.hovered_region):
            visual_args.append(_PLAN_VISUAL_HOVERED_REGION)
        if selected_space:
            visual_args.append(_PLAN_VISUAL_SELECTED_SPACE)
        if self.hovered_space and not self._is_selected_plan_target("space", self.hovered_space):
            visual_args.append(_PLAN_VISUAL_HOVERED_SPACE)
        if selected_opening:
            visual_args.append(_PLAN_VISUAL_SELECTED_OPENING)
        if secondary_targets:
            visual_args.append(_PLAN_VISUAL_SECONDARY_SELECTION)
        self._queue_plan_overlay_visual_refresh(*visual_args)

    def slotUndoDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)

    def slotRedoDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)

    def slotRecomputedDocument(self, doc):
        del doc
        self._invalidate_document_dependent_plan_visuals()

    def attach_task_panel(self, panel):
        if self.task_panel is panel:
            return
        self.task_panel = panel

    def attach_aux_task_panel(self, panel):
        if panel is None or panel in self._aux_task_panels:
            return
        self._aux_task_panels.append(panel)
        try:
            panel.refresh()
        except (AttributeError, RuntimeError):
            self.detach_aux_task_panel(panel)

    def detach_aux_task_panel(self, panel):
        if panel is None:
            return
        self._aux_task_panels = [item for item in self._aux_task_panels if item is not panel]

    def detach_task_panel(self):
        panel = self.task_panel
        self.task_panel = None
        if panel:
            try:
                mark_closed = getattr(panel, "mark_closed", None)
                if callable(mark_closed):
                    mark_closed()
            except Exception:
                pass
            try:
                detach = getattr(panel, "detach", None)
                if callable(detach):
                    detach()
                else:
                    dispose = getattr(panel, "dispose", None)
                    if callable(dispose):
                        dispose()
            except Exception:
                pass
        return panel

    def on_panel_closed(self, panel):
        if self.task_panel is panel:
            self.task_panel = None
            if not self._finishing:
                self.shutdown(close_dialog=False, teardown=self._tearing_down)
            return
        try:
            mark_closed = getattr(panel, "mark_closed", None)
            if callable(mark_closed):
                mark_closed()
        except Exception:
            pass
        try:
            detach = getattr(panel, "detach", None)
            if callable(detach):
                detach()
            else:
                dispose = getattr(panel, "dispose", None)
                if callable(dispose):
                    dispose()
        except Exception:
            pass

    def _refresh_task_panel_status(self):
        with self._plan_perf_trace_span("refresh_task_panel_status"):
            if self._tearing_down:
                return
            self._sanitize_plan_target_references()
            self._update_input_hints()
            self._refresh_viewport_status_chip()
            panel = self.task_panel
            if panel:
                try:
                    panel.refresh_from_session()
                except (AttributeError, RuntimeError):
                    self.on_panel_closed(panel)
            stale_panels = []
            for extra_panel in list(self._aux_task_panels):
                if extra_panel is panel:
                    continue
                try:
                    extra_panel.refresh_from_session()
                except (AttributeError, RuntimeError):
                    stale_panels.append(extra_panel)
            for extra_panel in stale_panels:
                self.detach_aux_task_panel(extra_panel)

    def _is_modal_plan_interaction_active(self):
        return bool(
            self._is_wall_edit_modal_active()
            or self.current_tool
            in ("Move Opening", "Move Symbol", "Rotate Symbol", "Set Space Text")
        )

    def _focus_plan_view(self):
        if self._tearing_down or not self.view:
            return
        try:
            widget = self.view.graphicsView()
        except Exception:
            widget = None
        if widget is not None:
            try:
                widget.activateWindow()
            except Exception:
                pass
            try:
                widget.setFocus()
            except Exception:
                pass
            return
        try:
            self.view.setFocus()
        except Exception:
            pass

    def _queue_focus_plan_view(self):
        try:
            from PySide import QtCore
        except Exception:
            self._focus_plan_view()
            return
        QtCore.QTimer.singleShot(0, self._focus_plan_view)

    def _get_plan_view_widget(self):
        if self._tearing_down or not self.view:
            return None
        try:
            return self.view.graphicsView()
        except Exception:
            return None

    def _format_status_chip_action(self, message):
        if not message:
            return ""
        text = str(message)
        if text.startswith("%1 "):
            text = text[3:]
        elif text.startswith("%1"):
            text = text[2:]
        text = text.strip()
        if not text:
            return ""
        return text[0].upper() + text[1:]

    def _get_plan_target_display_label(self, obj):
        return getattr(obj, "Label", getattr(obj, "Name", ""))

    def _format_plan_target_selection_state(self, kind, obj):
        if not kind or not obj:
            return ""
        templates = {
            "opening": translate("BIM_PlanEdit", "Opening: {label}"),
            "symbol": translate("BIM_PlanEdit", "Symbol: {label}"),
            "region": translate("BIM_PlanEdit", "Region: {label}"),
            "space": translate("BIM_PlanEdit", "Space: {label}"),
            "wall": translate("BIM_PlanEdit", "Wall: {label}"),
        }
        template = templates.get(kind)
        if not template:
            return ""
        return template.format(label=self._get_plan_target_display_label(obj))

    def _get_status_chip_text(self):
        title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(tool=self.current_tool)
        selected_kind, selected_obj = self._get_selected_plan_target()
        selected_context = self._format_plan_target_selection_state(selected_kind, selected_obj)

        if self.current_tool == "Move Opening":
            context = (
                selected_context
                if selected_kind == "opening" and selected_obj is not None
                else translate("BIM_PlanEdit", "Opening move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Move Symbol":
            context = (
                selected_context
                if selected_kind == "symbol" and selected_obj is not None
                else translate("BIM_PlanEdit", "Symbol move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Rotate Symbol":
            context = (
                selected_context
                if selected_kind == "symbol" and selected_obj is not None
                else translate("BIM_PlanEdit", "Symbol rotation")
            )
            if self._symbol_rotation_snap_enabled():
                action = translate(
                    "BIM_PlanEdit", "Click target angle ({snap} snap, Shift = free)"
                ).format(snap=self._format_symbol_rotation_snap_label())
            else:
                action = translate("BIM_PlanEdit", "Click target angle")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Move Wall":
            context = (
                selected_context
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall move")
            )
            action = translate("BIM_PlanEdit", "Click target point")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Join":
            target_wall, joint, detail = self._get_plan_join_candidate_state()
            context = (
                translate("BIM_PlanEdit", "Source wall: {label}").format(
                    label=self._get_plan_target_display_label(selected_obj)
                )
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall join")
            )
            action = self._get_plan_join_mode_action_text(target_wall, joint)
            if detail:
                return title, "{}\n{}\n{}".format(context, detail, action)
            return title, "{}\n{}".format(context, action)

        if self.current_tool.startswith("Stretch "):
            context = (
                selected_context
                if selected_kind == "wall" and selected_obj is not None
                else translate("BIM_PlanEdit", "Wall stretch")
            )
            action = translate("BIM_PlanEdit", "Click endpoint or press Enter to type a value")
            return title, "{}\n{}".format(context, action)

        if self.current_tool == "Region":
            context = (
                translate("BIM_PlanEdit", "Parent space: {label}").format(
                    label=self._plan_region_parent_space.Label
                )
                if self._is_plan_space_object(self._plan_region_parent_space)
                else translate("BIM_PlanEdit", "Plan region")
            )
            action = translate(
                "BIM_PlanEdit",
                "Click polygon points, press Enter to finish, or click near the first point to close",
            )
            return title, "{}\n{}".format(context, action)

        if selected_context:
            context = selected_context
        else:
            context = translate("BIM_PlanEdit", "Storey: {label}").format(
                label=self.get_storey_label(self.active_storey)
            )

        selection_summary = self._get_plan_selection_summary_text()
        if selection_summary:
            context = "{}\n{}".format(context, selection_summary)

        hints = self._get_input_hint_specs()
        action = self._format_status_chip_action(hints[0][0]) if hints else ""
        if selected_kind == "region" and self.current_tool == "Select":
            action = translate(
                "BIM_PlanEdit",
                "Edit label, scheme, type, and parent space in the task panel",
            )
        if self._plan_relation_status_message:
            action = self._plan_relation_status_message
        if not action:
            action = translate("BIM_PlanEdit", "Work directly in the viewport")
        return title, "{}\n{}".format(context, action)

    def _ensure_viewport_status_chip(self):
        widget = self._get_plan_view_widget()
        if widget is None:
            self._clear_viewport_status_chip()
            return None
        chip = self._viewport_status_chip
        if chip is not None and getattr(chip, "host_widget", None) is widget:
            return chip
        self._clear_viewport_status_chip()
        try:
            chip = _PlanEditViewportStatusChip(self, widget)
        except Exception:
            return None
        self._viewport_status_chip = chip
        return chip

    def _refresh_viewport_status_chip(self):
        if self._tearing_down:
            return
        chip = self._ensure_viewport_status_chip()
        if chip is None:
            return
        title, body = self._get_status_chip_text()
        try:
            chip.set_texts(title, body)
        except Exception:
            self._clear_viewport_status_chip()

    def _clear_viewport_status_chip(self):
        chip = self._viewport_status_chip
        self._viewport_status_chip = None
        if chip is None:
            return
        try:
            chip.close_chip()
        except Exception:
            pass

    def _clear_input_hints(self):
        hint_manager = getattr(FreeCADGui, "HintManager", None)
        if not hint_manager or not hasattr(hint_manager, "hide"):
            return
        try:
            hint_manager.hide()
        except Exception:
            pass

    def _request_view_redraw(self):
        if self._tearing_down:
            return
        redraw = self._get_runtime_attr(self.view, "redraw")
        if redraw is not None:
            try:
                redraw()
                return
            except Exception:
                self._discard_stale_runtime_object(self.view)
                pass

    def _make_input_hint(self, message, *sequences):
        if not hasattr(FreeCADGui, "InputHint"):
            return None
        if message is None:
            return None
        raw_message = str(message)
        if not raw_message.strip():
            return None
        try:
            return FreeCADGui.InputHint(raw_message, *sequences)
        except Exception:
            return None

    def _get_input_hint_specs(self):
        ui = FreeCADGui.UserInput
        selected_kind, _selected_obj = self._get_selected_plan_target()

        if self.current_tool == "Select":
            additive_hint = (
                translate("BIM_PlanEdit", "%1 add or remove from selection"),
                (ui.KeyControl, ui.MouseLeft),
            )
            if selected_kind == "opening":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick opening handle"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "symbol":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick symbol handle"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "wall":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 pick wall grip"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "region":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 select another target"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            if selected_kind == "space":
                return (
                    (
                        translate("BIM_PlanEdit", "%1 select space boundary target"),
                        ui.MouseLeft,
                    ),
                    additive_hint,
                )
            return (
                (
                    translate(
                        "BIM_PlanEdit",
                        "%1 select wall, opening, symbol, region, or space",
                    ),
                    ui.MouseLeft,
                ),
                additive_hint,
            )

        if self.current_tool == "Join":
            hints = [
                (
                    translate("BIM_PlanEdit", "%1 pick wall to join"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle join type ({joint_type})").format(
                        joint_type=self.get_plan_join_type_label()
                    ),
                    ui.KeyTab,
                ),
            ]
            if self._get_plan_candidate_joint() is not None:
                hints.append(
                    (
                        translate("BIM_PlanEdit", "%1 unjoin pair"),
                        ui.KeyDelete,
                    )
                )
            hints.append(
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                )
            )
            return tuple(hints)

        if self.current_tool.startswith("Stretch "):
            return (
                (
                    translate("BIM_PlanEdit", "%1 place endpoint"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 edit length"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            )

        return {
            "Move Opening": (
                (
                    translate("BIM_PlanEdit", "%1 place opening"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle move anchor"),
                    ui.KeyA,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Move Symbol": (
                (
                    translate("BIM_PlanEdit", "%1 place symbol"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Rotate Symbol": (
                (
                    translate("BIM_PlanEdit", "%1 place rotation"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Move Wall": (
                (
                    translate("BIM_PlanEdit", "%1 place wall"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 edit current offset"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cycle X/Y offset"),
                    ui.KeyTab,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Set Space Text": (
                (
                    translate("BIM_PlanEdit", "%1 place text"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Region": (
                (
                    translate("BIM_PlanEdit", "%1 place region point"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 finish region"),
                    ui.KeyReturn,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
            "Separator": (
                (
                    translate("BIM_PlanEdit", "%1 place separator"),
                    ui.MouseLeft,
                ),
                (
                    translate("BIM_PlanEdit", "%1 cancel"),
                    ui.KeyEscape,
                ),
            ),
        }.get(self.current_tool, ())

    def _get_input_hints(self):
        return [
            self._make_input_hint(message, *sequences)
            for message, *sequences in self._get_input_hint_specs()
        ]

    def _update_input_hints(self):
        hint_manager = getattr(FreeCADGui, "HintManager", None)
        if not hint_manager or not hasattr(hint_manager, "show"):
            return
        hints = [hint for hint in self._get_input_hints() if hint is not None]
        if not hints:
            self._clear_input_hints()
            return
        try:
            hint_manager.show(*hints)
        except Exception:
            pass

    def _sync_wall_grips(self):
        self._clear_wall_grips()
        if not self.is_selected_wall_endpoint_editable():
            return

        try:
            import draftguitools.gui_trackers as DraftTrackers
            from draftutils import params
        except Exception:
            return

        wall = self._get_selected_plan_target_object("wall")
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "calc_endpoints"):
            return

        endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            return

        if hasattr(proxy, "calc_edit_grip_positions"):
            grip_positions = proxy.calc_edit_grip_positions(wall)
        else:
            grip_positions = endpoints + [(endpoints[0] + endpoints[1]) * 0.5]
        if len(grip_positions) != 3:
            return
        grip_start, grip_end, midpoint = grip_positions
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)

        self._grip_trackers = [
            DraftTrackers.editTracker(pos=grip_start, name=wall.Name, idx=0),
            DraftTrackers.editTracker(pos=grip_end, name=wall.Name, idx=1),
            DraftTrackers.editTracker(
                pos=midpoint,
                name=wall.Name,
                idx=2,
                marker=midpoint_marker,
            ),
        ]

    def _clear_wall_grips(self):
        self._finalize_trackers(self._grip_trackers)
        self._grip_trackers = []

    def _get_footprint_overlay_polylines(self, faces):
        return ArchPlanGeometry.get_face_wire_polylines(faces)

    def _build_overlay_segments_from_polylines(self, polylines):
        segments = []
        for polyline in polylines or ():
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return tuple(segments)

    def _get_wall_overlay_polylines(self, wall):
        if not wall:
            return []
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "getFootprint"):
            return []
        try:
            faces = proxy.getFootprint(wall) or []
        except Exception:
            return []
        return self._get_footprint_overlay_polylines(faces)

    def _get_space_footprint_faces(self, space):
        if not self._is_plan_space_object(space):
            return ()

        def compute(space_obj):
            proxy = getattr(space_obj, "Proxy", None)
            if not proxy or not hasattr(proxy, "getFootprint"):
                return ()
            try:
                return proxy.getFootprint(space_obj) or ()
            except Exception:
                return ()

        return self._get_cached_plan_overlay_geometry(
            "space",
            space,
            "footprint_faces",
            compute,
        )

    def _get_space_overlay_polylines(self, space):
        if not self._is_plan_space_object(space):
            return ()
        return self._get_cached_plan_overlay_geometry(
            "space",
            space,
            "overlay_polylines",
            lambda space_obj: self._get_footprint_overlay_polylines(
                self._get_space_footprint_faces(space_obj)
            ),
        )

    def _get_region_footprint_faces(self, region):
        if not self._is_plan_region_object(region):
            return ()

        def compute(region_obj):
            proxy = getattr(region_obj, "Proxy", None)
            if not proxy or not hasattr(proxy, "getFootprint"):
                return ()
            try:
                return proxy.getFootprint(region_obj) or ()
            except Exception:
                return ()

        return self._get_cached_plan_overlay_geometry(
            "region",
            region,
            "footprint_faces",
            compute,
        )

    def _get_region_overlay_polylines(self, region):
        if not self._is_plan_region_object(region):
            return ()
        return self._get_cached_plan_overlay_geometry(
            "region",
            region,
            "overlay_polylines",
            lambda region_obj: self._get_footprint_overlay_polylines(
                self._get_region_footprint_faces(region_obj)
            ),
        )

    def _get_opening_overlay_polylines(self, opening):
        if not opening:
            return []
        view_object = getattr(opening, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None)
        if not proxy:
            return []
        if not hasattr(proxy, "get_plan_overlay_polylines"):
            return []
        try:
            return list(proxy.get_plan_overlay_polylines() or [])
        except Exception:
            return []

    def _finalize_trackers(self, trackers):
        for tracker in trackers:
            try:
                if hasattr(tracker, "off"):
                    tracker.off()
            except Exception:
                pass
            try:
                tracker.finalize()
            except Exception:
                pass

    def _make_plan_line_tracker(self, DraftTrackers, label, **kwargs):
        tracker = DraftTrackers.lineTracker(**kwargs)
        if hasattr(tracker, "setDebugLabel"):
            tracker.setDebugLabel("BimPlanSession:{}".format(label))
        return tracker

    def _get_plan_target_at_position(self, mouse_pos):
        with self._plan_perf_trace_span("get_plan_target_at_position", mouse_pos=mouse_pos):
            if not self.view or not mouse_pos:
                return (None, None)
            try:
                infos = self.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
            except (AttributeError, ReferenceError, RuntimeError):
                infos = None
            if not infos:
                infos = []
            self._plan_perf_count("objects_info_entries", len(infos))

            wall_candidate = None
            symbol_candidate = None
            region_candidate = None
            space_candidate = None
            result = (None, None)
            for info in infos:
                self._plan_perf_count("objects_info_scanned")
                if not info:
                    continue
                doc_name = info.get("Document")
                obj_name = info.get("Object")
                if not doc_name or not obj_name:
                    continue
                try:
                    doc = FreeCAD.getDocument(str(doc_name))
                except Exception:
                    doc = None
                if not doc:
                    continue
                obj = doc.getObject(str(obj_name))
                parent_obj = info.get("ParentObject")
                target_kind, target_obj = self._get_plan_target_for_object(
                    obj, parent_obj=parent_obj
                )
                if target_kind == "opening":
                    result = ("opening", target_obj)
                    break
                if target_kind == "symbol" and symbol_candidate is None:
                    symbol_candidate = target_obj
                elif target_kind == "region" and region_candidate is None:
                    region_candidate = target_obj
                elif target_kind == "wall" and wall_candidate is None:
                    wall_candidate = target_obj
                elif target_kind == "space" and space_candidate is None:
                    space_candidate = target_obj
            if result == (None, None):
                if symbol_candidate is None:
                    symbol_candidate = self._pick_plan_symbol_target_from_overlays(mouse_pos)
                if symbol_candidate is not None:
                    result = ("symbol", symbol_candidate)
                elif wall_candidate is not None:
                    result = ("wall", wall_candidate)
                else:
                    if region_candidate is None:
                        region_candidate = self._pick_plan_region_target_from_polylines(mouse_pos)
                    if region_candidate is None:
                        region_candidate = self._pick_plan_region_target_from_footprints(mouse_pos)
                    if region_candidate is None:
                        region_candidate = self._pick_plan_region_target_from_overlays(mouse_pos)
                    if region_candidate is not None:
                        result = ("region", region_candidate)
                    else:
                        if space_candidate is None:
                            space_candidate = self._pick_plan_space_target_from_footprints(
                                mouse_pos
                            )
                        if space_candidate is None:
                            space_candidate = self._pick_plan_space_target_from_overlays(mouse_pos)
                        if space_candidate is not None:
                            result = ("space", space_candidate)
            self._plan_perf_set_fields(
                picked_target=self._plan_perf_describe_target(result[0], result[1])
            )
            return result

    def _update_hovered_plan_target(self, mouse_pos):
        if self.current_tool == "Join":
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
            if target_kind == "wall" and not self._is_selected_plan_target("wall", target_obj):
                self._set_hovered_wall(target_obj)
            else:
                self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            return
        if self.current_tool != "Select":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            return
        target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if target_kind == "opening":
            self._set_hovered_wall(None)
            self._set_hovered_opening(target_obj)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
        elif target_kind == "symbol":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(target_obj)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
        elif target_kind == "wall":
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)
            self._set_hovered_wall(target_obj)
        elif target_kind == "region":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(target_obj)
        elif target_kind == "space":
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_region(None)
            self._set_hovered_space(target_obj)
        else:
            self._set_hovered_wall(None)
            self._set_hovered_opening(None)
            self._set_hovered_symbol(None)
            self._set_hovered_space(None)
            self._set_hovered_region(None)

    def _is_plan_additive_selection_active(self):
        if self.current_tool != "Select":
            return False
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ControlModifier)
        except Exception:
            return False

    def _get_plan_target_from_edit_node(self, node):
        if not node:
            return (None, None)
        node_kind = node[0]
        if node_kind == "opening_handle":
            opening = node[1]
            if self._is_hosted_opening_object(opening):
                return ("opening", opening)
            return (None, None)
        if node_kind == "symbol_handle":
            symbol = node[1]
            if self._is_plan_symbol_instance(symbol):
                return ("symbol", symbol)
            return (None, None)
        try:
            point = node[1]
            doc = FreeCAD.getDocument(str(point.documentName.getValue()))
            obj = doc.getObject(str(point.objectName.getValue()))
        except Exception:
            return (None, None)
        if self._is_hosted_opening_object(obj):
            return ("opening", obj)
        return self._get_plan_target_for_object(obj)

    def _toggle_plan_target_selection_at_position(self, mouse_pos, event_callback=None):
        node = self._get_edit_node(mouse_pos)
        target_kind, target_obj = self._get_plan_target_from_edit_node(node)
        if target_kind is None:
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        if not target_kind or not target_obj:
            return False

        primary_kind, primary_obj = self._get_selected_plan_target()
        selection = self._get_gui_selection()
        if primary_obj is not None and primary_obj not in selection:
            selection = [primary_obj] + selection

        normalized_selection = []
        seen = set()
        for selected in selection:
            if not selected:
                continue
            key = (
                getattr(getattr(selected, "Document", None), "Name", None),
                getattr(selected, "Name", None),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized_selection.append(selected)
        selection = normalized_selection

        was_selected = target_obj in selection
        if was_selected:
            new_selection = [selected for selected in selection if selected != target_obj]
            if primary_obj == target_obj:
                next_kind, next_obj = self._get_first_plan_target_from_selection(new_selection)
            elif primary_obj is not None and primary_obj in new_selection:
                next_kind, next_obj = primary_kind, primary_obj
            else:
                next_kind, next_obj = self._get_first_plan_target_from_selection(new_selection)
        else:
            new_selection = list(selection)
            new_selection.append(target_obj)
            if (
                primary_obj is not None
                and primary_obj in new_selection
                and primary_obj != target_obj
            ):
                next_kind, next_obj = primary_kind, primary_obj
            else:
                next_kind, next_obj = target_kind, target_obj

        self._set_pending_selected_plan_target(next_kind, next_obj)
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._set_gui_selection(new_selection)
        self._refresh_primary_selected_plan_target()
        self._claim_left_button_click(event_callback)
        return True

    def _clear_hovered_plan_targets(self, kinds=None):
        clearers = {
            "wall": self._set_hovered_wall,
            "opening": self._set_hovered_opening,
            "symbol": self._set_hovered_symbol,
            "space": self._set_hovered_space,
            "region": self._set_hovered_region,
        }
        for kind in kinds or ("wall", "opening", "symbol", "space", "region"):
            clear_hovered = clearers.get(kind)
            if clear_hovered is not None:
                clear_hovered(None)

    def _set_event_handled(self, event_callback):
        if event_callback and hasattr(event_callback, "setHandled"):
            try:
                event_callback.setHandled()
            except Exception:
                pass

    def _claim_left_button_click(self, event_callback):
        # Plan Edit owns overlay-driven picks, so also swallow the matching
        # button release to prevent the base 3D view selection pass from
        # clearing or replacing the GUI selection afterwards.
        self._consume_left_button_release = True
        self._set_event_handled(event_callback)

    def _set_hovered_wall(self, wall):
        if self._is_selected_plan_target("wall", wall):
            wall = None
        if self.hovered_wall == wall:
            return
        self.hovered_wall = wall
        self._sync_junction_node_overlays()
        self._sync_hovered_wall_overlay()
        self._sync_hovered_wall_opening_context_overlay()
        if self.current_tool == "Join":
            self._refresh_task_panel_status()

    def _set_hovered_opening(self, opening):
        if self._is_selected_plan_target("opening", opening):
            opening = None
        if self.hovered_opening == opening:
            return
        self.hovered_opening = opening
        self._sync_hovered_opening_overlay()

    def _set_hovered_symbol(self, symbol):
        if self._is_selected_plan_target("symbol", symbol):
            symbol = None
        if self.hovered_symbol == symbol:
            return
        self.hovered_symbol = symbol
        self._sync_hovered_symbol_overlay()

    def _set_hovered_space(self, space):
        if self._is_selected_plan_target("space", space):
            space = None
        if self.hovered_space == space:
            return
        self.hovered_space = space
        self._sync_hovered_space_overlay()

    def _set_hovered_region(self, region):
        if self._is_selected_plan_target("region", region):
            region = None
        if self.hovered_region == region:
            return
        self.hovered_region = region
        self._sync_hovered_region_overlay()

    def _queue_restore_selected_plan_target(self, kind, obj):
        if not obj:
            return
        queue_restore = {
            "opening": self._queue_restore_selected_opening,
            "symbol": self._queue_restore_selected_symbol,
            "region": self._queue_restore_selected_region,
            "space": self._queue_restore_selected_space,
        }.get(kind)
        if queue_restore is not None:
            queue_restore(obj)

    def _select_plan_target_for_plan_edit(
        self, kind, obj, queue_restore=False, sync_gui_selection=False
    ):
        validators = {
            "opening": self._is_hosted_opening_object,
            "symbol": self._is_plan_symbol_instance,
            "region": self._is_plan_region_object,
            "space": self._is_plan_space_object,
            "wall": self._is_plan_selectable_wall,
        }
        validator = validators.get(kind)
        if validator is None or not validator(obj):
            return False
        previous_kind, previous_obj = self._get_selected_plan_target()
        self.current_tool = "Select"
        self._set_selected_plan_target(kind, obj, pending_restore=queue_restore)
        if sync_gui_selection:
            self._set_gui_selection_object(obj)
        if kind == "wall":
            self._sync_wall_grips()
        else:
            self._clear_wall_grips()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "opening"):
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "symbol"):
            self._sync_selected_symbol_overlay()
            self._sync_selected_symbol_handles()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "region"):
            self._sync_selected_region_overlay()
        if self._selected_plan_target_changed(previous_kind, previous_obj, "space"):
            self._sync_selected_space_overlay()
        self._sync_secondary_selected_overlays()
        self._refresh_task_panel_status()
        if queue_restore:
            self._queue_restore_selected_plan_target(kind, obj)
        return True

    def _select_opening_for_plan_edit(self, opening, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "opening",
            opening,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_symbol_for_plan_edit(self, symbol, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "symbol",
            symbol,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_region_for_plan_edit(self, region, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "region",
            region,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_space_for_plan_edit(self, space, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "space",
            space,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _select_wall_for_plan_edit(self, wall, queue_restore=False, sync_gui_selection=False):
        return self._select_plan_target_for_plan_edit(
            "wall",
            wall,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
        )

    def _activate_plan_target(
        self,
        kind,
        mouse_pos,
        event_callback=None,
        sync_gui_selection=False,
        clear_hovered_kinds=None,
        resolved_target=None,
    ):
        if resolved_target is None:
            target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        else:
            target_kind, target_obj = resolved_target
        with self._plan_perf_trace_span(
            f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
        ):
            self._plan_perf_count(f"activate_plan_target_attempts_{kind}")
            self._plan_perf_set_fields(
                resolved_target=self._plan_perf_describe_target(target_kind, target_obj)
            )
            if target_kind != kind:
                target_obj = None
            select_target = {
                "opening": self._select_opening_for_plan_edit,
                "symbol": self._select_symbol_for_plan_edit,
                "region": self._select_region_for_plan_edit,
                "space": self._select_space_for_plan_edit,
                "wall": self._select_wall_for_plan_edit,
            }.get(kind)
            if select_target is None or not select_target(
                target_obj,
                queue_restore=True,
                sync_gui_selection=sync_gui_selection,
            ):
                self._plan_perf_set_fields(activate_plan_target_result=False)
                return False
            self._clear_hovered_plan_targets(clear_hovered_kinds)
            self._claim_left_button_click(event_callback)
            self._plan_perf_set_fields(
                activate_plan_target_result=True,
                activated_target=self._plan_perf_describe_target(kind, target_obj),
            )
            return True

    def _activate_semantic_plan_target(self, mouse_pos, event_callback=None):
        target_kind, target_obj = self._get_plan_target_at_position(mouse_pos)
        activate_target = {
            "opening": self._activate_opening_target,
            "symbol": self._activate_symbol_target,
            "region": self._activate_region_target,
            "space": self._activate_space_target,
            "wall": self._activate_wall_target,
        }.get(target_kind)
        if activate_target is None:
            return False
        return activate_target(
            mouse_pos,
            event_callback=event_callback,
            resolved_target=(target_kind, target_obj),
        )

    def _activate_opening_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "opening",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_symbol_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "symbol",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_region_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "region",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _activate_space_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "space",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "opening", "symbol", "region"),
            resolved_target=resolved_target,
        )

    def _activate_wall_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self._activate_plan_target(
            "wall",
            mouse_pos,
            event_callback=event_callback,
            sync_gui_selection=True,
            clear_hovered_kinds=("wall", "symbol", "space", "region"),
            resolved_target=resolved_target,
        )

    def _get_plan_point_from_mouse_pos(self, mouse_pos):
        if not self.view or not mouse_pos:
            return None
        get_point = self._get_runtime_attr(self.view, "getPoint")
        if get_point is None:
            return None
        try:
            point = get_point(int(mouse_pos[0]), int(mouse_pos[1]))
        except TypeError:
            try:
                point = get_point((int(mouse_pos[0]), int(mouse_pos[1])))
            except Exception:
                return None
        except Exception:
            return None
        return self._project_plan_point(point)

    def _get_space_region_candidate_polylines(self, candidate):
        face = candidate.get("face") if isinstance(candidate, dict) else None
        if not face:
            return []
        return self._get_footprint_overlay_polylines([face])

    def _get_space_region_candidate_segments(self, candidate):
        segments = []
        for polyline in self._get_space_region_candidate_polylines(candidate):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _pick_space_region_candidate(self, mouse_pos, radius_px=10):
        if self.current_tool != "Pick Space Region" or not self._space_region_candidates:
            return None

        point = self._get_plan_point_from_mouse_pos(mouse_pos)
        if point is not None:
            for candidate in self._space_region_candidates:
                face = candidate.get("face")
                if not face:
                    continue
                bound_box = getattr(face, "BoundBox", None)
                if bound_box is None:
                    continue
                test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
                try:
                    if face.isInside(test_point, 0.001, True):
                        return candidate
                except Exception:
                    continue

        radius_sq = float(radius_px) * float(radius_px)
        best_candidate = None
        best_distance_sq = None
        for candidate in self._space_region_candidates:
            for start, end in self._get_space_region_candidate_segments(candidate):
                distance_sq = self._get_screen_distance_sq_to_segment(mouse_pos, start, end)
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_candidate = candidate
                    best_distance_sq = distance_sq
        return best_candidate

    def _set_hovered_space_region_candidate(self, candidate):
        if self._hovered_space_region_candidate is candidate:
            return
        self._hovered_space_region_candidate = candidate
        self._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SPACE_REGION_PICK)
        self._refresh_task_panel_status()

    def _create_space_region_base_object(self, candidate):
        shape = candidate.get("shape") if isinstance(candidate, dict) else None
        if not shape:
            return None
        try:
            base = self.doc.addObject("Part::Feature", "SpaceRegionBase")
        except Exception:
            return None
        try:
            base.Shape = self._copy_shape_without_element_map(shape)
        except Exception:
            return None

        view_object = getattr(base, "ViewObject", None)
        if view_object:
            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = False
                except Exception:
                    pass
            if hasattr(view_object, "ShowInTree"):
                try:
                    view_object.ShowInTree = False
                except Exception:
                    pass
            if hasattr(view_object, "Selectable"):
                try:
                    view_object.Selectable = False
                except Exception:
                    pass
        return base

    def _begin_space_region_pick(self, boundaries, label=None, seed_space=None, report=None):
        if report is None:
            report = self._get_space_region_candidate_report(
                boundaries,
                label=label,
                seed_space=seed_space,
            )
        candidates = list(report.get("candidates", []) or [])
        if not candidates:
            self._report_space_region_candidate_failure(report)
            return False

        skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
        if skipped_claimed:
            FreeCAD.Console.PrintMessage(
                translate(
                    "BIM_PlanEdit",
                    "Ignoring {count} enclosed region(s) already covered by existing spaces.\n",
                ).format(count=skipped_claimed)
            )
        if skipped_claimed and len(candidates) == 1:
            space = self._create_space_from_region_candidate(
                candidates[0],
                boundaries=boundaries,
                keep_boundaries=seed_space is None,
            )
            if not space:
                return False
            self._register_plan_object(space)
            self._restore_selected_space(space)
            return True

        self.current_tool = "Pick Space Region"
        self._space_region_pick_boundaries = list(boundaries)
        self._space_region_candidates = candidates
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = seed_space
        self._clear_wall_grips()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._refresh_primary_selected_plan_target()
        FreeCAD.Console.PrintMessage(
            translate(
                "BIM_PlanEdit",
                "Multiple enclosed regions found. Hover a dashed region and click to create that space.\n",
            )
        )
        return True

    def _cancel_space_region_pick(self, refresh=True):
        was_active = self.current_tool == "Pick Space Region" or bool(self._space_region_candidates)
        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._clear_space_region_pick_overlays()
        if self.current_tool == "Pick Space Region":
            self.current_tool = "Select"
        if was_active:
            self._refresh_primary_selected_plan_target()
        elif refresh:
            self._refresh_task_panel_status()
        return was_active

    def _create_space_from_region_candidate(self, candidate, boundaries=None, keep_boundaries=True):
        import Arch

        if not isinstance(candidate, dict):
            return None
        boundaries = list(boundaries or [])

        space = None
        reported_failure = False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
            base = self._create_space_region_base_object(candidate)
            if not base:
                raise RuntimeError("Unable to create space base")
            space = Arch.makeSpace(base)
            if not space:
                raise RuntimeError("Unable to create space")
            if keep_boundaries and boundaries:
                space.Boundaries = boundaries
            self._add_object_to_active_storey(space)
            self.doc.recompute()
            if not self._space_has_valid_geometry(space):
                reported_failure = self._report_space_creation_failure(space)
                raise RuntimeError("Unable to create space")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not reported_failure:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "Failed to create the selected space.\n")
                )
            return None

        return space

    def _activate_space_region_candidate(self, candidate, event_callback=None):
        if self.current_tool != "Pick Space Region" or not isinstance(candidate, dict):
            return False

        boundaries = list(self._space_region_pick_boundaries or [])
        if not boundaries and self._space_region_pick_seed_space is None:
            return False

        space = self._create_space_from_region_candidate(
            candidate,
            boundaries=boundaries,
            keep_boundaries=self._space_region_pick_seed_space is None,
        )
        if not space:
            return False

        self._space_region_pick_boundaries = []
        self._space_region_candidates = []
        self._hovered_space_region_candidate = None
        self._space_region_pick_seed_space = None
        self._clear_space_region_pick_overlays()
        self._register_plan_object(space)
        self._restore_selected_space(space)
        self._claim_left_button_click(event_callback)
        return True

    def _create_space_from_current_selection(self):
        import ArchSpace

        request = self._get_space_creation_request()
        if not request:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces before using Space.\n",
                )
            )
            return False

        boundaries = list(request["boundaries"] or [])
        region_seed_space = request["region_seed_space"]
        if not boundaries:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces before using Space.\n",
                )
            )
            return False

        if region_seed_space is not None:
            report = self._get_space_region_candidate_report(
                boundaries,
                label=request["label"],
                seed_space=region_seed_space,
            )
            candidate_count = int(report.get("candidate_count", 0) or 0)
            if candidate_count > 1:
                return self._begin_space_region_pick(
                    boundaries,
                    label=report.get("label"),
                    seed_space=region_seed_space,
                    report=report,
                )
            if candidate_count == 1:
                space = self._create_space_from_region_candidate(
                    report["candidates"][0],
                    boundaries=boundaries,
                    keep_boundaries=False,
                )
                if not space:
                    return False
                self._register_plan_object(space)
                self._restore_selected_space(space)
                return True
            self._report_space_region_candidate_failure(report)
            return False

        report = ArchSpace.analyzeBoundaryLinks(boundaries)
        if report.get("code") == "multiple_regions":
            region_report = self._get_space_region_candidate_report(
                boundaries,
                label=report.get("label"),
            )
            candidate_count = int(region_report.get("candidate_count", 0) or 0)
            if candidate_count > 1:
                return self._begin_space_region_pick(
                    boundaries,
                    label=report.get("label"),
                    report=region_report,
                )
            if candidate_count == 1:
                space = self._create_space_from_region_candidate(
                    region_report["candidates"][0],
                    boundaries=boundaries,
                    keep_boundaries=True,
                )
                if not space:
                    return False
                self._register_plan_object(space)
                self._restore_selected_space(space)
                return True
            self._report_space_region_candidate_failure(region_report)
            return False

        import Arch

        space = None
        reported_failure = False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
            space = Arch.makeSpace(boundaries)
            if not space:
                raise RuntimeError("Unable to create space")
            self._add_object_to_active_storey(space)
            self.doc.recompute()
            if not self._space_has_valid_geometry(space):
                reported_failure = self._report_space_creation_failure(space)
                raise RuntimeError("Unable to create space")
            self.doc.commitTransaction()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            if not reported_failure:
                FreeCAD.Console.PrintError(
                    translate("BIM_PlanEdit", "Failed to create the selected space.\n")
                )
            return False

        self._register_plan_object(space)
        self._restore_selected_space(space)
        return True

    def _space_has_valid_geometry(self, space):
        if not self._is_plan_space_object(space):
            return False
        try:
            shape = getattr(space, "Shape", None)
        except Exception:
            return False
        if not shape:
            return False
        try:
            if shape.isNull():
                return False
        except Exception:
            pass
        return bool(getattr(shape, "Solids", None))

    def _report_space_creation_failure(self, space):
        proxy = getattr(space, "Proxy", None)
        if not proxy:
            return False

        message = ""
        if hasattr(proxy, "getLastBoundaryError"):
            try:
                message = str(proxy.getLastBoundaryError(space) or "").strip()
            except Exception:
                message = ""

        if not message:
            return False

        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Plan Edit kept no new space object because the selection could not be turned into a valid Arch Space.\n",
            )
        )
        return True

    def _set_selected_space_label(self, label):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        label = str(label or "").strip()
        if not label or label == space.Label:
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Rename Space"))
            space.Label = label
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_space_type(self, space_type):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        space_type = str(space_type or "")
        if not space_type or space_type == getattr(space, "SpaceType", ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Space Type"))
            space.SpaceType = space_type
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_label(self, label):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        label = str(label or "").strip()
        if not label or label == getattr(region, "Label", ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Rename Region"))
            region.Label = label
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_scheme(self, scheme):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        scheme = str(scheme or "").strip()
        if scheme == str(getattr(region, "Scheme", "") or ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Scheme"))
            region.Scheme = scheme
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_type(self, region_type):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        region_type = str(region_type or "").strip()
        if region_type == str(getattr(region, "RegionType", "") or ""):
            return False
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Type"))
            region.RegionType = region_type
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_selected_region_parent_space(self, space):
        region = self._get_selected_plan_target_object("region")
        if not self._is_plan_region_object(region):
            return False
        space = self._get_plan_semantic_object(space) if space else None
        if space is not None and not self._is_plan_space_object(space):
            return False

        current_parent = getattr(region, "ParentSpace", None)
        current_parent = self._get_plan_semantic_object(current_parent) if current_parent else None
        if current_parent == space:
            return False

        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Parent Space"))
            region.ParentSpace = space
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_task_panel_status()
        return True

    def _set_space_boundaries(self, space, boundaries):
        if not self._is_plan_space_object(space):
            return False
        import ArchSpace

        boundaries = ArchSpace.normalizeBoundaryLinks(boundaries)
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Edit Space Boundaries"))
            space.Boundaries = boundaries
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return False
        self._refresh_selected_space_visuals()
        self._refresh_task_panel_status()
        return True

    def _add_boundaries_to_selected_space(self):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        existing = self._get_space_boundary_entries(space)
        additions = self._get_selected_space_boundary_links(fallback_space=space)
        if not additions:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select room-bounding walls or explicit boundary faces to add to the space.\n",
                )
            )
            return False
        merged = existing + additions
        return self._set_space_boundaries(space, merged)

    def _remove_selected_space_boundaries(self, row_indexes=None):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        existing = self._get_space_boundary_entries(space)
        if not existing:
            return False

        if row_indexes:
            row_indexes = set(int(index) for index in row_indexes if int(index) >= 0)
            remaining = [
                boundary for idx, boundary in enumerate(existing) if idx not in row_indexes
            ]
            if len(remaining) == len(existing):
                return False
            return self._set_space_boundaries(space, remaining)

        removals = {
            self._space_boundary_key(boundary)
            for boundary in self._get_selected_space_boundary_links(fallback_space=space)
        }
        if not removals:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM_PlanEdit",
                    "Select boundary rows or room-bounding walls to remove from the space.\n",
                )
            )
            return False
        remaining = [
            boundary for boundary in existing if self._space_boundary_key(boundary) not in removals
        ]
        if len(remaining) == len(existing):
            return False
        return self._set_space_boundaries(space, remaining)

    def _start_space_text_position_pick(self):
        space = self._get_selected_plan_target_object("space")
        if not self._is_plan_space_object(space):
            return False
        self.current_tool = "Set Space Text"
        self._edit_space = space
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._sync_secondary_selected_overlays()
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            callback=self._finish_space_text_position_pick,
            last=self._get_space_reference_point(space),
            title=translate("BIM_PlanEdit", "Pick space text position"),
            noTracker=True,
        )
        self._queue_focus_plan_view()
        return True

    def _finish_space_text_position_pick(self, point=None, obj=None):
        del obj
        space = self._edit_space
        self._edit_space = None
        FreeCAD.activeDraftCommand = None
        self._set_draft_point_focus_suppressed(False)

        if point is None or not self._is_plan_space_object(space):
            self.current_tool = "Select"
            self._refresh_task_panel_status()
            return

        point = self._project_plan_point(point)
        try:
            self.doc.openTransaction(translate("BIM_PlanEdit", "Set Space Text Position"))
            space.ViewObject.TextPosition = space.Placement.inverse().multVec(point)
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self._restore_selected_space(space)
            return

        self.current_tool = "Select"
        self._queue_restore_selected_space(space)

    def _cancel_space_text_position_pick(self):
        space = self._edit_space or self._get_selected_plan_target_object("space")
        self._edit_space = None
        self._stop_snapper()
        FreeCAD.activeDraftCommand = None
        self._set_draft_point_focus_suppressed(False)
        self.current_tool = "Select"
        if space:
            self._set_selected_plan_target("space", space, pending_restore=True)
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _refresh_selected_space_visuals(self):
        self._invalidate_selected_space_overlay_cache()
        self._sync_selected_space_overlay()
        self._request_view_redraw()

    def _refresh_selected_region_visuals(self):
        self._sync_selected_region_overlay()
        self._request_view_redraw()

    def _restore_selected_region(self, region):
        self.current_tool = "Select"
        if region:
            self._set_selected_plan_target("region", region, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not region:
            self._sync_selected_region_overlay()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(region)
        self._sync_selected_region_overlay()
        self._refresh_task_panel_status()

    def _queue_restore_selected_region(self, region):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_region(region)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_region(region))

    def _restore_selected_space(self, space):
        self.current_tool = "Select"
        self._edit_space = None
        if space:
            self._set_selected_plan_target("space", space, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not space:
            self._sync_selected_space_overlay()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(space)
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _queue_restore_selected_space(self, space):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_space(space)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_space(space))

    def _sync_secondary_selected_overlays(self):
        self._clear_secondary_selected_overlays()
        if self.current_tool not in ("Select", "Pick Space Region"):
            return
        color = (0.12, 0.72, 0.68)
        width = self._scaled_line_width(2)
        selected_targets = (
            self._get_selected_plan_targets()
            if self.current_tool == "Pick Space Region"
            else self._get_secondary_selected_plan_targets()
        )
        for target_kind, target_obj in selected_targets:
            if target_kind == "wall":
                self._create_wall_overlay_trackers(
                    target_obj,
                    color=color,
                    width=width,
                    tracker_store=self._secondary_selection_trackers,
                )
            elif target_kind == "opening":
                self._create_opening_overlay_trackers(
                    target_obj,
                    color=color,
                    width=width,
                    tracker_store=self._secondary_selection_trackers,
                )
            elif target_kind == "symbol":
                self._create_symbol_overlay_trackers(
                    target_obj,
                    color=color,
                    width=width,
                    tracker_store=self._secondary_selection_trackers,
                )
            elif target_kind == "region":
                self._create_region_overlay_trackers(
                    target_obj,
                    color=color,
                    width=width,
                    tracker_store=self._secondary_selection_trackers,
                )
            elif target_kind == "space":
                self._create_space_overlay_trackers(
                    target_obj,
                    color=color,
                    width=width,
                    tracker_store=self._secondary_selection_trackers,
                )

    def _clear_secondary_selected_overlays(self):
        self._finalize_trackers(self._secondary_selection_trackers)
        self._secondary_selection_trackers = []

    def _sync_space_region_pick_overlays(self):
        self._clear_space_region_pick_overlays()
        if self.current_tool != "Pick Space Region":
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for candidate in self._space_region_candidates:
            hovered = candidate is self._hovered_space_region_candidate
            color = (0.90, 0.52, 0.10) if hovered else (0.22, 0.44, 0.88)
            width = self._scaled_line_width(3 if hovered else 2)
            dotted = not hovered
            for polyline in self._get_space_region_candidate_polylines(candidate):
                if len(polyline) < 2:
                    continue
                for start, end in zip(polyline, polyline[1:]):
                    tracker = self._make_plan_line_tracker(
                        DraftTrackers,
                        "space-region-pick:{}".format(candidate.get("index", "unknown")),
                        dotted=dotted,
                        scolor=color,
                        swidth=width,
                        ontop=True,
                    )
                    tracker.p1(start)
                    tracker.p2(end)
                    tracker.on()
                    self._space_region_pick_trackers.append(tracker)

    def _clear_space_region_pick_overlays(self):
        self._finalize_trackers(self._space_region_pick_trackers)
        self._space_region_pick_trackers = []

    def _sync_hovered_wall_overlay(self):
        self._clear_hovered_wall_overlay()
        if self.current_tool not in ("Select", "Join"):
            return
        if not self.hovered_wall or self._is_selected_plan_target("wall", self.hovered_wall):
            return
        self._create_wall_overlay_trackers(
            self.hovered_wall,
            color=(0.42, 0.62, 0.9),
            width=self._scaled_line_width(2),
            tracker_store=self._wall_hover_trackers,
        )

    def _clear_hovered_wall_overlay(self):
        self._finalize_trackers(self._wall_hover_trackers)
        self._wall_hover_trackers = []

    def _get_plan_context_junctions(self):
        if self.current_tool not in ("Select", "Join"):
            return []

        import ArchWallJoinUtils

        junctions = []
        seen = set()
        selected_wall = self._get_selected_plan_target_object("wall")
        for wall in (selected_wall, self.hovered_wall):
            if not self._is_plan_selectable_wall(wall):
                continue
            for relation in ArchWallJoinUtils.iter_wall_relations(wall):
                if not ArchWallJoinUtils.is_wall_junction(relation):
                    continue
                relation_name = getattr(relation, "Name", None)
                if not relation_name or relation_name in seen:
                    continue
                seen.add(relation_name)
                if getattr(relation, "Status", "") not in ("OK", "Conflict"):
                    continue
                junctions.append(relation)
        return junctions

    def _create_junction_node_trackers(self, junction, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        intersection = getattr(junction, "Intersection", None)
        if intersection is None:
            return
        units_per_pixel = self._get_plan_view_units_per_pixel() or 1.0
        half_size = max(units_per_pixel * 8.0, 20.0)
        center = FreeCAD.Vector(intersection)
        offsets = (
            (FreeCAD.Vector(-half_size, -half_size, 0), FreeCAD.Vector(half_size, half_size, 0)),
            (FreeCAD.Vector(-half_size, half_size, 0), FreeCAD.Vector(half_size, -half_size, 0)),
        )
        for start_offset, end_offset in offsets:
            tracker = self._make_plan_line_tracker(
                DraftTrackers,
                "junction-node:{}".format(getattr(junction, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(center.add(start_offset))
            tracker.p2(center.add(end_offset))
            tracker.on()
            tracker_store.append(tracker)

    def _sync_junction_node_overlays(self):
        self._clear_junction_node_overlays()
        selected_wall = self._get_selected_plan_target_object("wall")
        for junction in self._get_plan_context_junctions():
            if selected_wall and selected_wall in (getattr(junction, "Walls", None) or []):
                color = (0.92, 0.58, 0.12)
                width = self._scaled_line_width(2)
            else:
                color = (0.82, 0.70, 0.32)
                width = self._scaled_line_width(1)
            self._create_junction_node_trackers(
                junction,
                color=color,
                width=width,
                tracker_store=self._junction_node_trackers,
            )

    def _clear_junction_node_overlays(self):
        self._finalize_trackers(self._junction_node_trackers)
        self._junction_node_trackers = []

    def _sync_hovered_wall_opening_context_overlay(self):
        self._clear_hovered_wall_opening_context_overlay()
        if self.current_tool != "Select":
            return
        if not self.hovered_wall or self._is_selected_plan_target("wall", self.hovered_wall):
            return
        selected_kind, _selected_obj = self._get_selected_plan_target()
        if selected_kind in ("wall", "opening", "region", "space"):
            return
        color = (0.64, 0.70, 0.84)
        width = self._scaled_line_width(1)
        for opening in self._get_wall_hosted_openings(self.hovered_wall):
            self._create_opening_overlay_trackers(
                opening,
                color=color,
                width=width,
                tracker_store=self._hovered_wall_opening_context_trackers,
            )

    def _clear_hovered_wall_opening_context_overlay(self):
        self._finalize_trackers(self._hovered_wall_opening_context_trackers)
        self._hovered_wall_opening_context_trackers = []

    def _create_wall_overlay_trackers(self, wall, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_wall_overlay_polylines(wall):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "wall-overlay:{}".format(getattr(wall, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _create_space_overlay_trackers(self, space, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_space_overlay_polylines(space):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "space-overlay:{}".format(getattr(space, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _create_region_overlay_trackers(self, region, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_region_overlay_polylines(region):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "region-overlay:{}".format(getattr(region, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _get_region_overlay_segments(self, region):
        if not self._is_plan_region_object(region):
            return ()
        return self._get_cached_plan_overlay_geometry(
            "region",
            region,
            "overlay_segments",
            lambda region_obj: self._build_overlay_segments_from_polylines(
                self._get_region_overlay_polylines(region_obj)
            ),
        )

    def _get_space_overlay_segments(self, space):
        if not self._is_plan_space_object(space):
            return ()
        return self._get_cached_plan_overlay_geometry(
            "space",
            space,
            "overlay_segments",
            lambda space_obj: self._build_overlay_segments_from_polylines(
                self._get_space_overlay_polylines(space_obj)
            ),
        )

    def _sync_hovered_space_overlay(self):
        self._clear_hovered_space_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_plan_space_object(self.hovered_space):
            return
        if self._is_selected_plan_target("space", self.hovered_space):
            return
        self._create_space_overlay_trackers(
            self.hovered_space,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._space_hover_trackers,
        )

    def _clear_hovered_space_overlay(self):
        self._finalize_trackers(self._space_hover_trackers)
        self._space_hover_trackers = []

    def _sync_hovered_region_overlay(self):
        self._clear_hovered_region_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_plan_region_object(self.hovered_region):
            return
        if self._is_selected_plan_target("region", self.hovered_region):
            return
        self._create_region_overlay_trackers(
            self.hovered_region,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._region_hover_trackers,
        )

    def _clear_hovered_region_overlay(self):
        self._finalize_trackers(self._region_hover_trackers)
        self._region_hover_trackers = []

    def _invalidate_selected_space_overlay_cache(self):
        self._selected_space_overlay_dirty = True

    def _sync_selected_space_overlay(self):
        with self._plan_perf_trace_span("sync_selected_space_overlay"):
            space = self._get_selected_plan_target_object("space")
            if self.current_tool not in (
                "Select",
                "Set Space Text",
            ) or not self._is_plan_space_object(space):
                self._clear_selected_space_overlay()
                return
            width = self._scaled_line_width(3)
            try:
                import draftguitools.gui_trackers as DraftTrackers
            except ImportError:
                self._clear_selected_space_overlay()
                return
            color = (0.12, 0.38, 0.95)
            space_key = self._get_document_object_key(space)
            geometry_key = space_key
            render_state = (space_key, round(float(width), 3), color)
            if (
                not self._selected_space_overlay_dirty
                and self._selected_space_overlay_render_state == render_state
            ):
                self._plan_perf_count("selected_space_overlay_cache_hits")
                return
            if (
                not self._selected_space_overlay_dirty
                and self._selected_space_overlay_geometry_key == geometry_key
            ):
                segments = self._selected_space_overlay_segments
                self._plan_perf_count("selected_space_overlay_segment_cache_hits")
            else:
                segments = tuple(self._get_space_overlay_segments(space))
                self._selected_space_overlay_geometry_key = geometry_key
                self._selected_space_overlay_segments = segments
            self._plan_perf_count("selected_space_overlay_segments", len(segments))
            if self._selected_space_overlay_render_state != render_state or len(
                self._space_overlay_trackers
            ) != len(segments):
                self._clear_selected_space_overlay()
                for _start, _end in segments:
                    tracker = self._make_plan_line_tracker(
                        DraftTrackers,
                        "selected-space-overlay:{}".format(getattr(space, "Name", "unknown")),
                        scolor=color,
                        swidth=width,
                        ontop=True,
                    )
                    self._space_overlay_trackers.append(tracker)
                self._selected_space_overlay_geometry_key = geometry_key
                self._selected_space_overlay_segments = segments
            for tracker, (start, end) in zip(self._space_overlay_trackers, segments):
                tracker.setColor(color)
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
            self._selected_space_overlay_render_state = render_state
            self._selected_space_overlay_dirty = False

    def _clear_selected_space_overlay(self):
        self._finalize_trackers(self._space_overlay_trackers)
        self._space_overlay_trackers = []
        self._selected_space_overlay_dirty = False
        self._selected_space_overlay_geometry_key = None
        self._selected_space_overlay_segments = ()
        self._selected_space_overlay_render_state = None

    def _sync_selected_region_overlay(self):
        with self._plan_perf_trace_span("sync_selected_region_overlay"):
            region = self._get_selected_plan_target_object("region")
            if self.current_tool != "Select" or not self._is_plan_region_object(region):
                self._clear_selected_region_overlay()
                return
            width = self._scaled_line_width(3)
            try:
                import draftguitools.gui_trackers as DraftTrackers
            except ImportError:
                self._clear_selected_region_overlay()
                return
            segments = self._get_region_overlay_segments(region)
            self._plan_perf_count("selected_region_overlay_segments", len(segments))
            color = (0.12, 0.38, 0.95)
            if len(self._region_overlay_trackers) != len(segments):
                self._clear_selected_region_overlay()
                for _start, _end in segments:
                    tracker = self._make_plan_line_tracker(
                        DraftTrackers,
                        "selected-region-overlay:{}".format(getattr(region, "Name", "unknown")),
                        scolor=color,
                        swidth=width,
                        ontop=True,
                    )
                    self._region_overlay_trackers.append(tracker)
            for tracker, (start, end) in zip(self._region_overlay_trackers, segments):
                tracker.setColor(color)
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()

    def _clear_selected_region_overlay(self):
        self._finalize_trackers(self._region_overlay_trackers)
        self._region_overlay_trackers = []

    def _sync_hovered_opening_overlay(self):
        self._clear_hovered_opening_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_hosted_opening_object(self.hovered_opening):
            return
        if self._is_selected_plan_target("opening", self.hovered_opening):
            return
        self._create_opening_overlay_trackers(
            self.hovered_opening,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._opening_hover_trackers,
        )

    def _clear_hovered_opening_overlay(self):
        self._finalize_trackers(self._opening_hover_trackers)
        self._opening_hover_trackers = []

    def _create_opening_overlay_trackers(self, opening, color, width, tracker_store):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_opening_overlay_polylines(opening):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _get_opening_overlay_segments(self, opening):
        segments = []
        for polyline in self._get_opening_overlay_polylines(opening):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _sync_selected_opening_overlay(self):
        opening = self._get_selected_plan_target_object("opening")
        if self.current_tool != "Select" or not self._is_hosted_opening_object(opening):
            self._clear_selected_opening_overlay()
            return
        width = self._scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_selected_opening_overlay()
            return
        segments = self._get_opening_overlay_segments(opening)
        color = (0.12, 0.38, 0.95)
        if len(self._opening_overlay_trackers) != len(segments):
            self._clear_selected_opening_overlay()
            for _start, _end in segments:
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "selected-opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                self._opening_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(self._opening_overlay_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_selected_opening_overlay(self):
        self._finalize_trackers(self._opening_overlay_trackers)
        self._opening_overlay_trackers = []

    def _sync_selected_wall_opening_context_overlay(self):
        self._clear_selected_wall_opening_context_overlay()
        wall = self._get_selected_plan_target_object("wall")
        if self.current_tool != "Select" or not wall or self._is_selected_plan_target("opening"):
            return
        color = (0.46, 0.58, 0.82)
        width = self._scaled_line_width(2)
        for opening in self._get_wall_hosted_openings(wall):
            self._create_opening_overlay_trackers(
                opening,
                color=color,
                width=width,
                tracker_store=self._selected_wall_opening_context_trackers,
            )

    def _clear_selected_wall_opening_context_overlay(self):
        self._finalize_trackers(self._selected_wall_opening_context_trackers)
        self._selected_wall_opening_context_trackers = []

    def _copy_placement(self, placement):
        if placement is None:
            return FreeCAD.Placement()
        try:
            return placement.copy()
        except Exception:
            return FreeCAD.Placement(placement)

    def _get_plan_object_global_placement(self, obj):
        if not obj:
            return FreeCAD.Placement()
        if hasattr(obj, "getGlobalPlacement"):
            try:
                placement = obj.getGlobalPlacement()
                if placement is not None:
                    return placement
            except Exception:
                pass
        return getattr(obj, "Placement", FreeCAD.Placement())

    def _get_symbol_global_placement(self, symbol, placement=None):
        current_global = self._get_plan_object_global_placement(symbol)
        if placement is None:
            return current_global
        current_local = getattr(symbol, "Placement", None)
        if current_local is None:
            return placement
        try:
            parent_global = current_global.multiply(current_local.inverse())
            return parent_global.multiply(placement)
        except Exception:
            return placement

    def _get_symbol_parent_global_placement(self, symbol, placement=None):
        placement = placement or getattr(symbol, "Placement", None)
        current_global = self._get_plan_object_global_placement(symbol)
        if placement is None:
            return current_global
        try:
            return current_global.multiply(placement.inverse())
        except Exception:
            return FreeCAD.Placement()

    def _get_symbol_plan_proxy(self, symbol, *attrs):
        semantic_obj = self._get_plan_semantic_object(symbol)
        view_object = getattr(semantic_obj, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _get_symbol_semantic_proxy(self, symbol, *attrs):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = getattr(semantic_obj, "Proxy", None)
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _get_symbol_overlay_polylines(self, symbol, placement=None):
        if not self._is_plan_symbol_instance(symbol):
            return []
        proxy = self._get_symbol_plan_proxy(symbol, "_collect_local_footprint_polylines")
        if not proxy:
            return []
        try:
            local_polylines = list(proxy._collect_local_footprint_polylines() or [])
        except Exception:
            return []

        placement = self._get_symbol_global_placement(symbol, placement=placement)
        polylines = []
        for polyline in local_polylines:
            points = []
            for point in polyline:
                if isinstance(point, FreeCAD.Vector):
                    local_point = FreeCAD.Vector(point)
                else:
                    try:
                        z_value = point[2] if len(point) > 2 else 0.0
                        local_point = FreeCAD.Vector(point[0], point[1], z_value)
                    except Exception:
                        continue
                try:
                    points.append(placement.multVec(local_point))
                except Exception:
                    continue
            if len(points) >= 2:
                polylines.append(points)
        return polylines

    def _get_symbol_overlay_segments(self, symbol, placement=None):
        segments = []
        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                segments.append((start, end))
        return segments

    def _refresh_selected_symbol_visuals(self):
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._request_view_redraw()

    def _create_symbol_overlay_trackers(self, symbol, color, width, tracker_store, placement=None):
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "symbol-overlay:{}".format(getattr(symbol, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                tracker_store.append(tracker)

    def _sync_hovered_symbol_overlay(self):
        self._clear_hovered_symbol_overlay()
        if self.current_tool != "Select":
            return
        if not self._is_plan_symbol_instance(self.hovered_symbol):
            return
        if self._is_selected_plan_target("symbol", self.hovered_symbol):
            return
        self._create_symbol_overlay_trackers(
            self.hovered_symbol,
            color=(0.38, 0.62, 0.96),
            width=self._scaled_line_width(2),
            tracker_store=self._symbol_hover_trackers,
        )

    def _clear_hovered_symbol_overlay(self):
        self._finalize_trackers(self._symbol_hover_trackers)
        self._symbol_hover_trackers = []

    def _sync_selected_symbol_overlay(self):
        symbol = self._get_selected_plan_target_object("symbol")
        if self.current_tool != "Select" or not self._is_plan_symbol_instance(symbol):
            self._clear_selected_symbol_overlay()
            return
        width = self._scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            self._clear_selected_symbol_overlay()
            return
        segments = self._get_symbol_overlay_segments(symbol)
        color = (0.12, 0.38, 0.95)
        if len(self._symbol_overlay_trackers) != len(segments):
            self._clear_selected_symbol_overlay()
            for _start, _end in segments:
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "selected-symbol-overlay:{}".format(getattr(symbol, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                self._symbol_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(self._symbol_overlay_trackers, segments):
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()

    def _clear_selected_symbol_overlay(self):
        self._finalize_trackers(self._symbol_overlay_trackers)
        self._symbol_overlay_trackers = []

    def _get_symbol_local_anchor(self, symbol):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = self._get_symbol_semantic_proxy(symbol, "get_plan_anchor")
        if proxy:
            try:
                return FreeCAD.Vector(proxy.get_plan_anchor(semantic_obj))
            except Exception:
                pass
        try:
            import ArchEquipment

            return ArchEquipment.get_plan_anchor(semantic_obj)
        except Exception:
            return FreeCAD.Vector()

    def _get_symbol_local_facing(self, symbol):
        semantic_obj = self._get_plan_semantic_object(symbol)
        proxy = self._get_symbol_semantic_proxy(symbol, "get_plan_facing")
        if proxy:
            try:
                facing = FreeCAD.Vector(proxy.get_plan_facing(semantic_obj))
            except Exception:
                facing = None
        else:
            facing = None
        if facing is None:
            try:
                import ArchEquipment

                facing = ArchEquipment.get_plan_facing(semantic_obj)
            except Exception:
                facing = FreeCAD.Vector(1, 0, 0)
        facing = FreeCAD.Vector(facing.x, facing.y, 0)
        if facing.Length < 0.001:
            return FreeCAD.Vector(1, 0, 0)
        facing.normalize()
        return facing

    def _get_symbol_anchor_point(self, symbol, placement=None):
        placement = self._get_symbol_global_placement(symbol, placement=placement)
        anchor = self._get_symbol_local_anchor(symbol)
        try:
            return placement.multVec(anchor)
        except Exception:
            base = getattr(placement, "Base", None)
            if base is None:
                return FreeCAD.Vector()
            return FreeCAD.Vector(base.x, base.y, base.z)

    def _get_symbol_facing_vector(self, symbol, placement=None):
        placement = self._get_symbol_global_placement(symbol, placement=placement)
        facing = self._get_symbol_local_facing(symbol)
        try:
            facing = placement.Rotation.multVec(facing)
        except Exception:
            pass
        facing = FreeCAD.Vector(facing.x, facing.y, 0)
        if facing.Length < 0.001:
            return FreeCAD.Vector()
        facing.normalize()
        return facing

    def _symbol_rotation_snap_enabled(self):
        params = getattr(self, "_plan_edit_params", None)
        if not params:
            return True
        try:
            return params.GetBool("SymbolRotateAngleSnap", True)
        except Exception:
            return True

    def _get_symbol_rotation_snap_increment_degrees(self):
        params = getattr(self, "_plan_edit_params", None)
        if not params:
            return 15.0
        try:
            increment = float(params.GetFloat("SymbolRotateAngleIncrement", 15.0))
        except Exception:
            increment = 15.0
        if increment <= 0.001:
            return 15.0
        return min(increment, 180.0)

    def _get_symbol_rotation_snap_step_radians(self):
        return math.radians(self._get_symbol_rotation_snap_increment_degrees())

    def _format_symbol_rotation_snap_label(self):
        increment = self._get_symbol_rotation_snap_increment_degrees()
        rounded = round(increment)
        if abs(increment - rounded) < 1e-9:
            return "{}°".format(int(rounded))
        return "{}°".format(("{:.3f}".format(increment)).rstrip("0").rstrip("."))

    def _symbol_rotation_free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def _resolve_symbol_handle_target_point(self, symbol, handle_role, point, placement=None):
        if point is None:
            return None
        if isinstance(point, FreeCAD.Vector):
            target_point = FreeCAD.Vector(point.x, point.y, point.z)
        else:
            try:
                z_value = point[2] if len(point) > 2 else 0.0
                target_point = FreeCAD.Vector(point[0], point[1], z_value)
            except Exception:
                return None
        if handle_role != "rotate":
            return target_point
        if not self._symbol_rotation_snap_enabled():
            return target_point
        if self._symbol_rotation_free_angle_override_active():
            return target_point

        snap_step = self._get_symbol_rotation_snap_step_radians()
        if snap_step <= 1e-9:
            return target_point

        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        vector = FreeCAD.Vector(target_point.x - anchor.x, target_point.y - anchor.y, 0)
        radius = math.hypot(vector.x, vector.y)
        if radius < 0.001:
            return target_point

        snapped_angle = round(math.atan2(vector.y, vector.x) / snap_step) * snap_step
        return FreeCAD.Vector(
            anchor.x + radius * math.cos(snapped_angle),
            anchor.y + radius * math.sin(snapped_angle),
            anchor.z,
        )

    def _get_symbol_handle_radius(self, symbol, placement=None):
        placement = placement or self._get_plan_object_global_placement(symbol)
        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        radius = 0.0
        for polyline in self._get_symbol_overlay_polylines(symbol, placement=placement):
            for point in polyline:
                radius = max(
                    radius,
                    math.hypot(float(point.x) - float(anchor.x), float(point.y) - float(anchor.y)),
                )
        units_per_pixel = self._get_plan_view_units_per_pixel() or 10.0
        return max(radius * 1.2, 28.0 * units_per_pixel, 300.0)

    def _get_selected_symbol_handle_specs(self, symbol):
        from draftutils import params

        if not self._is_plan_symbol_instance(symbol):
            return []

        placement = self._get_plan_object_global_placement(symbol)
        anchor = self._get_symbol_anchor_point(symbol, placement=placement)
        radius = self._get_symbol_handle_radius(symbol, placement=placement)
        rotate_direction = self._get_symbol_facing_vector(symbol, placement=placement)
        if rotate_direction.Length < 0.001:
            rotate_direction = FreeCAD.Vector(1, 0, 0)
        rotate_offset = rotate_direction.multiply(radius)
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        return [
            (
                "move",
                anchor,
                FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
            ),
            (
                "rotate",
                anchor.add(rotate_offset),
                FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
            ),
        ]

    def _sync_selected_symbol_handles(self):
        symbol = self._get_selected_plan_target_object("symbol")
        if self.current_tool != "Select":
            self._clear_selected_symbol_handles()
            return
        if not self._is_plan_symbol_instance(symbol):
            self._clear_selected_symbol_handles()
            return
        self._clear_selected_symbol_handles()
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        for idx, (_role, point, marker) in enumerate(
            self._get_selected_symbol_handle_specs(symbol)
        ):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            self._symbol_handle_trackers.append(tracker)

    def _clear_selected_symbol_handles(self):
        self._finalize_trackers(self._symbol_handle_trackers)
        self._symbol_handle_trackers = []

    def _pick_selected_symbol_handle(self, mouse_pos, radius_px=10):
        symbol = self._get_selected_plan_target_object("symbol")
        if not self._is_plan_symbol_instance(symbol) or not self.view:
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_role = None
        best_distance_sq = None
        for role, point, _marker in self._get_selected_symbol_handle_specs(symbol):
            try:
                screen_x, screen_y = self.view.getPointOnScreen(point)
            except Exception:
                continue
            dx = float(screen_x) - float(cursor_x)
            dy = float(screen_y) - float(cursor_y)
            distance_sq = dx * dx + dy * dy
            if distance_sq > radius_px * radius_px:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_role = role
                best_distance_sq = distance_sq
        return best_role

    def _sync_symbol_edit_preview(self, symbol, placement, guide_start=None, guide_end=None):
        self._clear_symbol_edit_preview()
        if self.current_tool not in ("Move Symbol", "Rotate Symbol"):
            return
        if not self._is_plan_symbol_instance(symbol) or placement is None:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        preview_color = (0.12, 0.38, 0.95)
        self._create_symbol_overlay_trackers(
            symbol,
            color=preview_color,
            width=self._scaled_line_width(3),
            tracker_store=self._symbol_edit_preview_trackers,
            placement=placement,
        )
        if guide_start is None or guide_end is None:
            return
        guide = self._make_plan_line_tracker(
            DraftTrackers,
            "symbol-edit-guide:{}".format(getattr(symbol, "Name", "unknown")),
            dotted=True,
            scolor=preview_color,
            swidth=self._scaled_line_width(1),
            ontop=True,
        )
        guide.p1(guide_start)
        guide.p2(guide_end)
        guide.on()
        self._symbol_edit_preview_trackers.append(guide)

    def _clear_symbol_edit_preview(self):
        self._finalize_trackers(self._symbol_edit_preview_trackers)
        self._symbol_edit_preview_trackers = []

    def _get_symbol_handle_placement(self, symbol, handle_role, point):
        if not self._is_plan_symbol_instance(symbol) or point is None or not handle_role:
            return None
        start_placement = self._edit_symbol_start_placement
        if start_placement is None:
            start_placement = self._copy_placement(getattr(symbol, "Placement", None))
        point = self._resolve_symbol_handle_target_point(
            symbol, handle_role, point, placement=start_placement
        )
        if point is None:
            return None
        placement = self._copy_placement(start_placement)
        parent_global = self._get_symbol_parent_global_placement(symbol, placement=start_placement)
        anchor_global = self._get_symbol_anchor_point(symbol, placement=start_placement)
        local_anchor = self._get_symbol_local_anchor(symbol)
        if handle_role == "move":
            point_global = FreeCAD.Vector(point.x, point.y, anchor_global.z)
            try:
                anchor_parent = parent_global.inverse().multVec(point_global)
                placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
            except Exception:
                placement.Base = FreeCAD.Vector(
                    point.x - local_anchor.x,
                    point.y - local_anchor.y,
                    start_placement.Base.z,
                )
            return placement
        if handle_role != "rotate":
            return None

        anchor = FreeCAD.Vector(anchor_global.x, anchor_global.y, anchor_global.z)
        reference_point = self._edit_symbol_reference_point
        if reference_point is None:
            specs = dict(
                (role, handle_point)
                for role, handle_point, _marker in self._get_selected_symbol_handle_specs(symbol)
            )
            reference_point = specs.get("rotate")
        if reference_point is None:
            return None

        reference_vector = FreeCAD.Vector(
            reference_point.x - anchor.x,
            reference_point.y - anchor.y,
            0,
        )
        new_vector = FreeCAD.Vector(point.x - anchor.x, point.y - anchor.y, 0)
        if reference_vector.Length < 0.001 or new_vector.Length < 0.001:
            return None

        reference_angle = math.atan2(reference_vector.y, reference_vector.x)
        target_angle = math.atan2(new_vector.y, new_vector.x)
        delta_rotation = FreeCAD.Rotation(
            FreeCAD.Vector(0, 0, 1), math.degrees(target_angle - reference_angle)
        )
        current_global = self._get_symbol_global_placement(symbol, placement=start_placement)
        try:
            global_rotation = delta_rotation.multiply(current_global.Rotation)
            placement.Rotation = parent_global.Rotation.inverse().multiply(global_rotation)
        except Exception:
            placement.Rotation = delta_rotation.multiply(start_placement.Rotation)
        try:
            anchor_parent = parent_global.inverse().multVec(anchor)
            placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
        except Exception:
            placement.Base = FreeCAD.Vector(
                anchor.x - local_anchor.x,
                anchor.y - local_anchor.y,
                start_placement.Base.z,
            )
        return placement

    def _activate_symbol_handle(self, symbol, handle_role):
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_symbol_handle_now(symbol, handle_role)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda: self._activate_symbol_handle_now(symbol, handle_role),
        )

    def _activate_symbol_handle_now(self, symbol, handle_role):
        if self._tearing_down or not self._is_plan_symbol_instance(symbol):
            return
        if handle_role not in {"move", "rotate"}:
            return
        self._set_selected_plan_target("symbol", symbol)
        self._clear_wall_grips()
        self._start_symbol_handle_point_pick(symbol, handle_role)

    def _start_symbol_handle_point_pick(self, symbol, handle_role):
        if not self._is_plan_symbol_instance(symbol):
            return
        handle_points = {
            role: point for role, point, _marker in self._get_selected_symbol_handle_specs(symbol)
        }
        start_point = handle_points.get(handle_role)
        if start_point is None:
            return
        self.current_tool = "Move Symbol" if handle_role == "move" else "Rotate Symbol"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._sync_secondary_selected_overlays()
        self._edit_symbol = symbol
        self._edit_symbol_handle_role = handle_role
        self._edit_symbol_start_placement = self._copy_placement(getattr(symbol, "Placement", None))
        self._edit_symbol_reference_point = FreeCAD.Vector(start_point)
        self._clear_selected_symbol_overlay()
        self._clear_selected_symbol_handles()
        anchor = self._get_symbol_anchor_point(symbol, placement=self._edit_symbol_start_placement)
        self._sync_symbol_edit_preview(
            symbol,
            self._edit_symbol_start_placement,
            guide_start=anchor,
            guide_end=start_point,
        )
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            last=start_point,
            callback=self._finish_symbol_handle_point_pick,
            movecallback=self._update_symbol_handle_point_pick,
            title=(
                translate("BIM_PlanEdit", "Pick new symbol position")
                if handle_role == "move"
                else translate("BIM_PlanEdit", "Pick new symbol rotation")
            ),
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _update_symbol_handle_point_pick(self, point=None, snap_info=None):
        del snap_info
        symbol = self._edit_symbol
        handle_role = self._edit_symbol_handle_role
        if not symbol or not handle_role:
            self._clear_symbol_edit_preview()
            return
        target_point = self._resolve_symbol_handle_target_point(
            symbol, handle_role, point, placement=self._edit_symbol_start_placement
        )
        if target_point is None:
            self._clear_symbol_edit_preview()
            return
        placement = self._get_symbol_handle_placement(symbol, handle_role, point)
        if placement is None:
            self._clear_symbol_edit_preview()
            return
        guide_start = self._get_symbol_anchor_point(
            symbol, placement=self._edit_symbol_start_placement
        )
        guide_end = (
            self._get_symbol_anchor_point(symbol, placement=placement)
            if handle_role == "move"
            else target_point
        )
        self._sync_symbol_edit_preview(
            symbol, placement, guide_start=guide_start, guide_end=guide_end
        )

    def _finish_symbol_handle_point_pick(self, point=None, obj=None):
        del obj
        symbol = self._edit_symbol
        handle_role = self._edit_symbol_handle_role
        start_placement = self._edit_symbol_start_placement
        reference_point = self._edit_symbol_reference_point
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        FreeCAD.activeDraftCommand = None
        self._clear_symbol_edit_preview()

        if point is None or not symbol or not handle_role:
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        self._edit_symbol_start_placement = start_placement
        self._edit_symbol_reference_point = reference_point
        placement = self._get_symbol_handle_placement(symbol, handle_role, point)
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        if placement is None:
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        try:
            self.doc.openTransaction(
                translate(
                    "BIM_PlanEdit",
                    "Move Symbol" if handle_role == "move" else "Rotate Symbol",
                )
            )
            symbol.Placement = placement
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self.current_tool = "Select"
            self._restore_selected_symbol(symbol)
            return

        self.current_tool = "Select"
        self._queue_restore_selected_symbol(symbol)

    def _cancel_symbol_handle_point_pick(self):
        symbol = self._edit_symbol
        self._edit_symbol = None
        self._edit_symbol_handle_role = None
        self._edit_symbol_start_placement = None
        self._edit_symbol_reference_point = None
        self._stop_snapper()
        FreeCAD.activeDraftCommand = None
        self._clear_symbol_edit_preview()
        self.current_tool = "Select"
        if symbol:
            self._set_selected_plan_target("symbol", symbol, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()

    def _restore_selected_symbol(self, symbol):
        self.current_tool = "Select"
        if symbol:
            self._set_selected_plan_target("symbol", symbol, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not symbol:
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._sync_selected_symbol_overlay()
            self._sync_selected_symbol_handles()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(symbol)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._refresh_task_panel_status()

    def _queue_restore_selected_symbol(self, symbol):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_symbol(symbol)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_symbol(symbol))

    def _get_selected_opening_edit_handles(self, opening):
        proxy = self._get_opening_view_proxy(opening, "get_plan_edit_handles")
        if not proxy:
            return []
        return list(proxy.get_plan_edit_handles() or [])

    def _get_opening_plan_proxy(self, opening, *attrs):
        if not opening:
            return None
        proxy = getattr(opening, "Proxy", None)
        if proxy and all(hasattr(proxy, attr) for attr in attrs):
            return proxy
        return self._get_opening_view_proxy(opening, *attrs)

    def _get_opening_view_proxy(self, opening, *attrs):
        if not opening:
            return None
        view_object = getattr(opening, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None)
        if not proxy:
            return None
        for attr in attrs:
            if not hasattr(proxy, attr):
                return None
        return proxy

    def _project_opening_handle_point(self, opening, handle, point):
        if point is None or not opening or getattr(handle, "role", None) != "move":
            return point
        proxy = self._get_opening_plan_proxy(opening, "project_point_to_host_axis")
        if not proxy:
            return point
        return proxy.project_point_to_host_axis(point, anchor=self._edit_opening_move_anchor)

    def _get_opening_move_anchor_modes(self, opening):
        proxy = self._get_opening_plan_proxy(opening, "get_plan_move_anchor_modes")
        if not proxy:
            return _OPENING_MOVE_ANCHORS
        modes = tuple(proxy.get_plan_move_anchor_modes() or ())
        return modes or _OPENING_MOVE_ANCHORS

    def _execute_opening_handle(self, opening, handle_index, point=None):
        proxy = self._get_opening_view_proxy(opening, "execute_plan_edit_handle")
        if not proxy:
            return False
        return bool(
            proxy.execute_plan_edit_handle(
                handle_index,
                point,
                anchor=self._edit_opening_move_anchor,
            )
        )

    def _get_selected_opening_handle_specs(self, opening):
        from draftutils import params

        handle_specs = []
        marker_size = self._scaled_marker_size(params.get_param_view("MarkerSize"))
        markers = {
            "move": FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
            "flip_hinge": FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
            "flip_opening": FreeCADGui.getMarkerIndex("CROSS", marker_size),
        }
        for idx, handle in enumerate(self._get_selected_opening_edit_handles(opening)):
            if handle.role not in markers or handle.point is None:
                continue
            handle_specs.append((idx, handle.point, markers[handle.role]))
        return handle_specs

    def _sync_selected_opening_handles(self):
        opening = self._get_selected_plan_target_object("opening")
        if self.current_tool != "Select":
            self._clear_selected_opening_handles()
            return
        if not self._is_hosted_opening_object(opening):
            self._clear_selected_opening_handles()
            return
        self._clear_selected_opening_handles()
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        for idx, point, marker in self._get_selected_opening_handle_specs(opening):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            self._opening_handle_trackers.append(tracker)

    def _clear_selected_opening_handles(self):
        self._finalize_trackers(self._opening_handle_trackers)
        self._opening_handle_trackers = []

    def _get_opening_move_preview_state(self, opening, point):
        if not opening or point is None:
            return None
        proxy = self._get_opening_view_proxy(opening, "get_plan_move_preview_state")
        if not proxy:
            return None
        return proxy.get_plan_move_preview_state(point, anchor=self._edit_opening_move_anchor)

    def _sync_opening_move_preview(self, opening, point):
        self._clear_opening_move_preview()
        if self.current_tool != "Move Opening" or not opening or point is None:
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        preview_state = self._get_opening_move_preview_state(opening, point)
        if not preview_state:
            return

        preview_color = (0.12, 0.38, 0.95)
        for polyline in preview_state.get("polylines", []):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = self._make_plan_line_tracker(
                    DraftTrackers,
                    "opening-move-preview:{}".format(getattr(opening, "Name", "unknown")),
                    scolor=preview_color,
                    swidth=self._scaled_line_width(3),
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                self._opening_move_preview_trackers.append(tracker)

        guide_start = preview_state.get("guide_start")
        guide_end = preview_state.get("guide_end")
        if guide_start is None or guide_end is None:
            return

        guide = self._make_plan_line_tracker(
            DraftTrackers,
            "opening-move-guide:{}".format(getattr(opening, "Name", "unknown")),
            dotted=True,
            scolor=preview_color,
            swidth=self._scaled_line_width(1),
            ontop=True,
        )
        guide.p1(guide_start)
        guide.p2(guide_end)
        guide.on()
        self._opening_move_preview_trackers.append(guide)

        try:
            dim = DraftTrackers.archDimTracker(mode=1)
        except Exception:
            return
        dim.dimnode.textColor.setValue(preview_color)
        dim.offset = self._get_opening_move_readout_offset(opening)
        dim.p1(guide_start)
        dim.p2(guide_end)
        dim.on()
        self._opening_move_preview_trackers.append(dim)

    def _clear_opening_move_preview(self):
        self._finalize_trackers(self._opening_move_preview_trackers)
        self._opening_move_preview_trackers = []

    def _cycle_opening_move_anchor(self):
        if self.current_tool != "Move Opening":
            return False
        anchor_modes = self._get_opening_move_anchor_modes(self._edit_opening)
        try:
            current_index = anchor_modes.index(self._edit_opening_move_anchor)
        except ValueError:
            current_index = 0
        self._edit_opening_move_anchor = anchor_modes[(current_index + 1) % len(anchor_modes)]
        return True

    def _refresh_opening_move_preview_from_raw_point(self):
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        if not opening or handle_index is None:
            return
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        raw_point = self._edit_opening_move_raw_point
        if raw_point is None:
            raw_point = handle.point
        point = self._project_opening_handle_point(opening, handle, raw_point)
        self._sync_opening_move_preview(opening, point)

    def _activate_opening_handle(self, opening, handle_index):
        try:
            from PySide import QtCore
        except ImportError:
            self._activate_opening_handle_now(opening, handle_index)
            return

        QtCore.QTimer.singleShot(
            0,
            lambda: self._activate_opening_handle_now(opening, handle_index),
        )

    def _activate_opening_handle_now(self, opening, handle_index):
        if self._tearing_down or not opening:
            return
        self._set_selected_plan_target("opening", opening)
        self._clear_wall_grips()
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        if handle.interaction == "point_pick":
            self._start_opening_handle_point_pick(opening, handle_index, handle)
        else:
            self._execute_selected_opening_handle(opening, handle_index, handle)

    def _start_opening_handle_point_pick(self, opening, handle_index, handle):
        if not opening:
            return
        self.current_tool = "Move Opening"
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._sync_secondary_selected_overlays()
        self._edit_opening = opening
        self._edit_opening_handle_index = handle_index
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = FreeCAD.Vector(handle.point)
        self._clear_selected_opening_overlay()
        self._clear_selected_opening_handles()
        self._sync_opening_move_preview(opening, handle.point)
        self._refresh_task_panel_status()
        FreeCAD.activeDraftCommand = self
        self._push_opening_move_snap_profile()
        self._set_draft_point_focus_suppressed(True)
        FreeCADGui.Snapper.getPoint(
            last=handle.point,
            callback=self._finish_opening_handle_point_pick,
            movecallback=self._update_opening_handle_point_pick,
            title=handle.title or translate("BIM_PlanEdit", "Pick new opening position"),
            noTracker=True,
        )
        self._queue_focus_plan_view()

    def _update_opening_handle_point_pick(self, point=None, snap_info=None):
        del snap_info
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        if not opening or handle_index is None:
            self._clear_opening_move_preview()
            return
        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            self._clear_opening_move_preview()
            return
        handle = handles[handle_index]
        self._edit_opening_move_raw_point = FreeCAD.Vector(point) if point is not None else None
        point = self._project_opening_handle_point(opening, handle, point)
        self._sync_opening_move_preview(opening, point)

    def _finish_opening_handle_point_pick(self, point=None, obj=None):
        del obj
        opening = self._edit_opening
        handle_index = self._edit_opening_handle_index
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._clear_opening_move_preview()
        self._edit_opening_move_raw_point = None

        if point is None or not opening:
            self.current_tool = "Select"
            self._edit_opening_move_anchor = "center"
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._refresh_task_panel_status()
            return

        handles = self._get_selected_opening_edit_handles(opening)
        if handle_index is None or handle_index < 0 or handle_index >= len(handles):
            self.current_tool = "Select"
            self._edit_opening_move_anchor = "center"
            self._refresh_task_panel_status()
            return
        handle = handles[handle_index]
        point = self._project_opening_handle_point(opening, handle, point)

        try:
            self.doc.openTransaction(
                handle.transaction or translate("BIM_PlanEdit", "Edit Opening")
            )
            moved = self._execute_opening_handle(opening, handle_index, point)
            if not moved:
                raise RuntimeError("Unable to execute opening handle")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            self._edit_opening_move_anchor = "center"
            self._restore_selected_opening(opening)
            return

        self._edit_opening_move_anchor = "center"
        self.current_tool = "Select"
        self._refresh_task_panel_status()
        self._queue_restore_selected_opening(opening)

    def _cancel_opening_handle_point_pick(self):
        opening = self._edit_opening
        self._edit_opening = None
        self._edit_opening_handle_index = None
        self._stop_snapper()
        self._pop_opening_move_snap_profile()
        FreeCAD.activeDraftCommand = None
        self._clear_opening_move_preview()
        self._edit_opening_move_anchor = "center"
        self._edit_opening_move_raw_point = None
        self.current_tool = "Select"
        if opening:
            self._set_selected_plan_target("opening", opening, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()

    def _restore_selected_opening(self, opening):
        self.current_tool = "Select"
        if opening:
            self._set_selected_plan_target("opening", opening, pending_restore=True)
        else:
            self._set_selected_plan_target()
        if not opening:
            self._sync_selected_opening_overlay()
            self._sync_selected_opening_handles()
            self._refresh_task_panel_status()
            return
        self._set_gui_selection_object(opening)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._refresh_task_panel_status()

    def _queue_restore_selected_opening(self, opening):
        try:
            from PySide import QtCore
        except ImportError:
            self._restore_selected_opening(opening)
            return
        QtCore.QTimer.singleShot(0, lambda: self._restore_selected_opening(opening))

    def _clear_plan_selection_state(self):
        self._set_gui_selection([])
        self._set_selected_plan_target()
        self._set_hovered_wall(None)
        self._set_hovered_opening(None)
        self._set_hovered_symbol(None)
        self._set_hovered_space(None)
        self._set_hovered_region(None)
        self._clear_wall_grips()
        self._sync_secondary_selected_overlays()
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()
        self._sync_selected_symbol_overlay()
        self._sync_selected_symbol_handles()
        self._sync_selected_region_overlay()
        self._sync_selected_space_overlay()
        self._refresh_task_panel_status()

    def _execute_selected_opening_handle(self, opening, handle_index, handle):
        try:
            self.doc.openTransaction(
                handle.transaction or translate("BIM_PlanEdit", "Edit Opening")
            )
            executed = self._execute_opening_handle(opening, handle_index)
            if not executed:
                raise RuntimeError("Unable to execute opening handle")
            self.doc.commitTransaction()
            self.doc.recompute()
        except Exception:
            try:
                self.doc.abortTransaction()
            except Exception:
                pass
            return
        self._set_selected_plan_target("opening", opening, pending_restore=True)
        self._sync_selected_opening_overlay()
        self._sync_selected_opening_handles()


class PlanEditControlsWidget:
    """Reusable session controls widget for Plan Edit mode."""

    _COMMON_SPACE_TYPES = (
        "Undefined",
        "Room",
        "Office",
        "Restrooms",
        "Corridor / Transition",
        "Lobby",
        "Dining Area",
        "Exterior",
        "Active Storage",
        "Electrical / Mechanical",
    )

    def __init__(self, session):
        from PySide import QtGui

        self.session = session
        self._storey_items = []
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._refreshing_space_editor = False
        self._refreshing_region_editor = False
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self._region_parent_space_items = []
        self.form = self._build_form(QtGui)
        try:
            self.form.setObjectName("BIMPlanEditContextControls")
        except Exception:
            pass

    @property
    def modal_focus_widgets(self):
        return tuple(self._modal_focus_widgets)

    def _build_form(self, QtGui):
        container = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        container.setMinimumWidth(280)
        container.setMaximumWidth(360)

        layout.addWidget(self._build_intro_label(QtGui))
        layout.addLayout(self._build_storey_row(QtGui))
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("select_button", "Select", self.on_select_clicked),
                    ("wall_button", "Wall", self.on_wall_clicked),
                    ("rect_wall_button", "Rect Wall", self.on_rect_wall_clicked),
                ),
            )
        )
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("space_button", "Space", self.on_space_clicked),
                    ("region_button", "Region", self.on_region_clicked),
                    ("separator_button", "Separator", self.on_separator_clicked),
                    ("move_button", "Move", self.on_move_clicked),
                ),
            )
        )
        layout.addLayout(
            self._build_button_row(
                QtGui,
                (
                    ("join_button", "Join", self.on_join_clicked),
                    ("reapply_button", "Reapply View", self.on_reapply_clicked),
                ),
            )
        )
        layout.addLayout(self._build_join_type_row(QtGui))

        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.space_editor = self._build_space_editor(QtGui)
        layout.addWidget(self.space_editor)
        self.region_editor = self._build_region_editor(QtGui)
        layout.addWidget(self.region_editor)

        self.exit_button = self._make_button(QtGui, "Exit Plan Edit", self.on_exit_clicked)
        self.exit_button.setMinimumHeight(32)
        layout.addWidget(self.exit_button)

        self._modal_focus_widgets = [
            self.storey_combo,
            self.join_type_combo,
            self.unjoin_button,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.space_button,
            self.region_button,
            self.separator_button,
            self.move_button,
            self.join_button,
            self.reapply_button,
            self.space_label_edit,
            self.space_type_combo,
            self.space_boundary_list,
            self.space_add_button,
            self.space_remove_button,
            self.space_text_button,
            self.region_label_edit,
            self.region_scheme_edit,
            self.region_type_edit,
            self.region_parent_space_combo,
            self.exit_button,
        ]
        self._capture_focus_policies()

        container.setLayout(layout)
        return container

    def _build_intro_label(self, QtGui):
        intro = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan authoring mode for the active storey.",
            )
        )
        intro.setWordWrap(True)
        return intro

    def _make_button(self, QtGui, label, handler):
        button = QtGui.QPushButton(translate("BIM_PlanEdit", label))
        button.clicked.connect(handler)
        return button

    def _build_storey_row(self, QtGui):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        storey_label = QtGui.QLabel(translate("BIM_PlanEdit", "Storey"))
        self.storey_combo = QtGui.QComboBox()
        self.storey_combo.currentIndexChanged.connect(self.on_storey_changed)
        row.addWidget(storey_label)
        row.addWidget(self.storey_combo, 1)
        return row

    def _build_button_row(self, QtGui, specs):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        for attr, label, handler in specs:
            button = self._make_button(QtGui, label, handler)
            setattr(self, attr, button)
            row.addWidget(button)
        return row

    def _build_join_type_row(self, QtGui):
        row = QtGui.QHBoxLayout()
        row.setSpacing(6)
        join_type_label = QtGui.QLabel(translate("BIM_PlanEdit", "Join Type"))
        self.join_type_combo = QtGui.QComboBox()
        for join_type in self.session.get_plan_join_types():
            self.join_type_combo.addItem(
                self.session.get_plan_join_type_label(join_type), join_type
            )
        self.join_type_combo.currentIndexChanged.connect(self.on_join_type_changed)
        self.unjoin_button = self._make_button(QtGui, "Unjoin", self.on_unjoin_clicked)
        row.addWidget(join_type_label)
        row.addWidget(self.join_type_combo, 1)
        row.addWidget(self.unjoin_button)
        return row

    def _get_space_type_display_options(self, options):
        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)

        common = [option for option in self._COMMON_SPACE_TYPES if option in seen]
        remaining = [option for option in normalized if option not in common]
        if common and remaining:
            return common + [None] + remaining
        return common or remaining

    def _set_space_type_combo_options(self, options):
        from PySide import QtCore

        if self.space_type_combo is None:
            return

        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)

        self.space_type_combo.clear()
        for option in self._get_space_type_display_options(normalized):
            if option is None:
                try:
                    self.space_type_combo.insertSeparator(self.space_type_combo.count())
                except Exception:
                    pass
                continue
            self.space_type_combo.addItem(option, option)
            index = self.space_type_combo.count() - 1
            try:
                self.space_type_combo.setItemData(index, option, QtCore.Qt.ToolTipRole)
            except Exception:
                pass

        if self._space_type_option_model is not None:
            try:
                self._space_type_option_model.setStringList(normalized)
            except Exception:
                pass

    def _find_space_type_combo_index(self, value):
        value = str(value or "").strip().lower()
        if not value or self.space_type_combo is None:
            return -1
        for index in range(self.space_type_combo.count()):
            item_value = self.space_type_combo.itemData(index)
            if item_value is None:
                item_value = self.space_type_combo.itemText(index)
            if str(item_value or "").strip().lower() == value:
                return index
        return -1

    def _commit_space_type_combo_text(self, value):
        if self.space_type_combo is None:
            return False

        if hasattr(value, "data"):
            try:
                value = value.data()
            except Exception:
                pass

        index = self._find_space_type_combo_index(value)
        if index >= 0:
            self.space_type_combo.setCurrentIndex(index)
            line_edit = self.space_type_combo.lineEdit()
            if line_edit is not None:
                line_edit.setText(self.space_type_combo.itemText(index))
            return True

        line_edit = self.space_type_combo.lineEdit()
        current_index = self.space_type_combo.currentIndex()
        if line_edit is not None:
            if current_index >= 0:
                line_edit.setText(self.space_type_combo.itemText(current_index))
            else:
                line_edit.clear()
        return False

    def _format_region_parent_space_label(self, space):
        label = str(getattr(space, "Label", "") or "").strip()
        name = str(getattr(space, "Name", "") or "").strip()
        if label and name and label != name:
            return f"{label} ({name})"
        return label or name or translate("BIM_PlanEdit", "Unnamed Space")

    def _get_editor_object_key(self, obj):
        if obj is None:
            return None
        return (
            getattr(getattr(obj, "Document", None), "Name", None),
            getattr(obj, "Name", None),
        )

    def _normalize_space_type_options(self, options):
        normalized = []
        seen = set()
        for option in options or []:
            option = str(option or "").strip()
            if not option or option in seen:
                continue
            seen.add(option)
            normalized.append(option)
        return tuple(normalized)

    def _get_cached_space_type_options(self, space, current_type):
        if self._space_type_options_cache is None:
            options = []
            try:
                options = list(space.getEnumerationsOfProperty("SpaceType") or [])
            except Exception:
                options = []
            self._space_type_options_cache = self._normalize_space_type_options(options)
        normalized = list(self._space_type_options_cache or ())
        current_type = str(current_type or "").strip()
        if current_type and current_type not in normalized:
            normalized.append(current_type)
        return tuple(normalized)

    def _get_space_boundary_signature(self, space):
        signature = []
        for boundary in getattr(space, "Boundaries", []) or []:
            try:
                obj = boundary[0]
                subnames = boundary[1]
            except Exception:
                continue
            signature.append(
                (
                    self._get_editor_object_key(obj),
                    tuple(str(subname or "") for subname in (subnames or [])),
                )
            )
        return tuple(signature)

    def _get_region_parent_space_candidates(self, current_parent=None):
        candidates = []
        seen = set()
        active_storey = self.session.active_storey

        for obj in getattr(self.session.doc, "Objects", []) or []:
            semantic_obj = self.session._get_plan_semantic_object(obj)
            if not self.session._is_plan_space_object(semantic_obj):
                continue
            name = getattr(semantic_obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append(semantic_obj)

        current_parent = self.session._get_plan_semantic_object(current_parent)
        if self.session._is_plan_space_object(current_parent):
            current_name = getattr(current_parent, "Name", None)
            if current_name and current_name not in seen:
                candidates.append(current_parent)

        def sort_key(space):
            try:
                in_active_storey = bool(
                    active_storey and active_storey in (space.InListRecursive or [])
                )
            except Exception:
                in_active_storey = False
            label = str(getattr(space, "Label", "") or "").strip().lower()
            name = str(getattr(space, "Name", "") or "").strip().lower()
            return (0 if in_active_storey else 1, label or name, name)

        return sorted(candidates, key=sort_key)

    def _set_region_parent_space_combo_options(self, region):
        if self.region_parent_space_combo is None:
            return

        current_parent = self.session._get_plan_semantic_object(
            getattr(region, "ParentSpace", None)
        )
        candidates = self._get_region_parent_space_candidates(current_parent=current_parent)
        self._region_parent_space_items = [None] + candidates

        self.region_parent_space_combo.clear()
        self.region_parent_space_combo.addItem(translate("BIM_PlanEdit", "None"))
        for space in candidates:
            self.region_parent_space_combo.addItem(self._format_region_parent_space_label(space))

        current_name = getattr(current_parent, "Name", None) if current_parent else None
        current_index = 0
        if current_name:
            for index, space in enumerate(self._region_parent_space_items):
                if getattr(space, "Name", None) == current_name:
                    current_index = index
                    break
        self.region_parent_space_combo.setCurrentIndex(current_index)

    def _build_space_editor(self, QtGui):
        from PySide import QtCore

        editor = QtGui.QGroupBox(translate("BIM_PlanEdit", "Space"))
        editor.setVisible(False)
        layout = QtGui.QVBoxLayout(editor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QtGui.QFormLayout()
        form.setSpacing(6)

        self.space_label_edit = QtGui.QLineEdit(editor)
        self.space_label_edit.editingFinished.connect(self.on_space_label_edited)
        form.addRow(translate("BIM_PlanEdit", "Label"), self.space_label_edit)

        self.space_type_combo = QtGui.QComboBox(editor)
        self.space_type_combo.setEditable(True)
        self.space_type_combo.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.space_type_combo.setMaxVisibleItems(12)
        if hasattr(QtGui.QComboBox, "AdjustToMinimumContentsLengthWithIcon"):
            self.space_type_combo.setSizeAdjustPolicy(
                QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
        if hasattr(self.space_type_combo, "setMinimumContentsLength"):
            self.space_type_combo.setMinimumContentsLength(18)
        view = self.space_type_combo.view()
        if view is not None:
            if hasattr(view, "setTextElideMode"):
                view.setTextElideMode(QtCore.Qt.ElideRight)
            if hasattr(view, "setUniformItemSizes"):
                view.setUniformItemSizes(True)
        self._space_type_option_model = QtCore.QStringListModel([], self.space_type_combo)
        self._space_type_completer = QtGui.QCompleter(
            self._space_type_option_model,
            self.space_type_combo,
        )
        self._space_type_completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
        self._space_type_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        if hasattr(self._space_type_completer, "setFilterMode"):
            self._space_type_completer.setFilterMode(QtCore.Qt.MatchContains)
        self.space_type_combo.setCompleter(self._space_type_completer)
        try:
            self._space_type_completer.activated[str].connect(
                self.on_space_type_completion_activated
            )
        except Exception:
            self._space_type_completer.activated.connect(self.on_space_type_completion_activated)
        line_edit = self.space_type_combo.lineEdit()
        if line_edit is not None:
            if hasattr(line_edit, "setPlaceholderText"):
                line_edit.setPlaceholderText(translate("BIM_PlanEdit", "Search space types"))
            if hasattr(line_edit, "setClearButtonEnabled"):
                line_edit.setClearButtonEnabled(True)
            line_edit.editingFinished.connect(self.on_space_type_editing_finished)
        self.space_type_combo.currentIndexChanged.connect(self.on_space_type_changed)
        form.addRow(translate("BIM_PlanEdit", "Type"), self.space_type_combo)

        layout.addLayout(form)

        boundaries_label = QtGui.QLabel(translate("BIM_PlanEdit", "Boundaries"), editor)
        layout.addWidget(boundaries_label)

        self.space_boundary_list = QtGui.QListWidget(editor)
        self.space_boundary_list.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.space_boundary_list.setMinimumHeight(96)
        layout.addWidget(self.space_boundary_list)

        button_row = QtGui.QHBoxLayout()
        button_row.setSpacing(6)

        self.space_add_button = self._make_button(QtGui, "Add", self.on_space_add_clicked)
        self.space_remove_button = self._make_button(QtGui, "Remove", self.on_space_remove_clicked)
        self.space_text_button = self._make_button(
            QtGui,
            "Set Text Position",
            self.on_space_text_clicked,
        )

        button_row.addWidget(self.space_add_button)
        button_row.addWidget(self.space_remove_button)
        button_row.addWidget(self.space_text_button)
        layout.addLayout(button_row)

        return editor

    def _build_region_editor(self, QtGui):
        editor = QtGui.QGroupBox(translate("BIM_PlanEdit", "Region"))
        editor.setVisible(False)
        layout = QtGui.QVBoxLayout(editor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QtGui.QFormLayout()
        form.setSpacing(6)

        self.region_label_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_label_edit, "setClearButtonEnabled"):
            self.region_label_edit.setClearButtonEnabled(True)
        self.region_label_edit.editingFinished.connect(self.on_region_label_edited)
        form.addRow(translate("BIM_PlanEdit", "Label"), self.region_label_edit)

        self.region_scheme_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_scheme_edit, "setPlaceholderText"):
            self.region_scheme_edit.setPlaceholderText(translate("BIM_PlanEdit", "Program"))
        if hasattr(self.region_scheme_edit, "setClearButtonEnabled"):
            self.region_scheme_edit.setClearButtonEnabled(True)
        self.region_scheme_edit.editingFinished.connect(self.on_region_scheme_edited)
        form.addRow(translate("BIM_PlanEdit", "Scheme"), self.region_scheme_edit)

        self.region_type_edit = QtGui.QLineEdit(editor)
        if hasattr(self.region_type_edit, "setPlaceholderText"):
            self.region_type_edit.setPlaceholderText(translate("BIM_PlanEdit", "Zone"))
        if hasattr(self.region_type_edit, "setClearButtonEnabled"):
            self.region_type_edit.setClearButtonEnabled(True)
        self.region_type_edit.editingFinished.connect(self.on_region_type_edited)
        form.addRow(translate("BIM_PlanEdit", "Type"), self.region_type_edit)

        self.region_parent_space_combo = QtGui.QComboBox(editor)
        self.region_parent_space_combo.currentIndexChanged.connect(
            self.on_region_parent_space_changed
        )
        form.addRow(translate("BIM_PlanEdit", "Parent Space"), self.region_parent_space_combo)

        layout.addLayout(form)

        note = QtGui.QLabel(
            translate(
                "BIM_PlanEdit",
                "Plan regions store semantic zoning metadata and keep a polygonal footprint in plan.",
            ),
            editor,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        return editor

    def _capture_focus_policies(self):
        for widget in self._modal_focus_widgets:
            try:
                self._saved_focus_policies[widget] = widget.focusPolicy()
            except Exception:
                pass

    def dispose(self):
        form = self.form
        if form is not None:
            try:
                parent = form.parentWidget()
                if parent is not None and hasattr(parent, "layout"):
                    layout = parent.layout()
                    if layout is not None:
                        layout.removeWidget(form)
            except Exception:
                pass
            try:
                form.hide()
            except Exception:
                pass
            try:
                form.setParent(None)
            except Exception:
                pass
            try:
                form.deleteLater()
            except Exception:
                pass
        self.form = None
        self.status = None
        self.storey_combo = None
        self.select_button = None
        self.wall_button = None
        self.rect_wall_button = None
        self.space_button = None
        self.region_button = None
        self.separator_button = None
        self.move_button = None
        self.join_button = None
        self.join_type_combo = None
        self.unjoin_button = None
        self.reapply_button = None
        self.space_editor = None
        self.space_label_edit = None
        self.space_type_combo = None
        self.space_boundary_list = None
        self.space_add_button = None
        self.space_remove_button = None
        self.space_text_button = None
        self.region_editor = None
        self.region_label_edit = None
        self.region_scheme_edit = None
        self.region_type_edit = None
        self.region_parent_space_combo = None
        self._region_parent_space_items = []
        self._space_type_option_model = None
        self._space_type_completer = None
        self._space_type_options_cache = None
        self._space_editor_label_state = None
        self._space_editor_combo_state = None
        self._space_editor_boundary_state = None
        self.exit_button = None
        self._modal_focus_widgets = []
        self._saved_focus_policies = {}
        self._storey_items = []

    def refresh(self):
        if self.form is None or self.storey_combo is None:
            return
        self.storey_combo.blockSignals(True)
        try:
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
        finally:
            try:
                self.storey_combo.blockSignals(False)
            except Exception:
                pass
        self.refresh_from_session()

    def refresh_from_session(self):
        with self.session._plan_perf_trace_span("refresh_task_panel_widget"):
            if self.form is None or self.status is None or self.exit_button is None:
                return

            if self.join_type_combo is not None:
                self.join_type_combo.blockSignals(True)
                try:
                    join_type_index = self.join_type_combo.findData(
                        self.session.get_plan_join_type()
                    )
                    if join_type_index >= 0:
                        self.join_type_combo.setCurrentIndex(join_type_index)
                finally:
                    try:
                        self.join_type_combo.blockSignals(False)
                    except Exception:
                        pass

            storey_text = self.session.get_storey_label(self.session.active_storey)
            tool = self.session.current_tool
            modal_active = self.session._is_modal_plan_interaction_active()
            selected_kind, selected_obj = self.session._get_selected_plan_target()
            selected_state = self.session._format_plan_target_selection_state(
                selected_kind, selected_obj
            )
            if tool == "Join" and selected_kind == "wall" and selected_obj is not None:
                target_wall, joint, detail = self.session._get_plan_join_candidate_state()
                selection_state = translate("BIM_PlanEdit", "Source wall: {label}").format(
                    label=self.session._get_plan_target_display_label(selected_obj)
                )
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Join type: {joint_type}\n{pair_state}\n{action}",
                ).format(
                    joint_type=self.session.get_plan_join_type_label(),
                    pair_state=detail or translate("BIM_PlanEdit", "Candidate wall: none"),
                    action=self.session._get_plan_join_mode_action_text(target_wall, joint),
                )
            elif tool == "Pick Space Region":
                selection_state = translate("BIM_PlanEdit", "Space creation: pick region")
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Multiple enclosed regions were found. Hover a dashed outline, then click to create that space.",
                )
                targets = self.session._get_selected_plan_targets()
                if targets:
                    selection_help = "{}\n{}".format(
                        selection_help,
                        translate("BIM_PlanEdit", "Boundary candidates: {summary}").format(
                            summary=self.session._summarize_plan_targets(targets)
                        ),
                    )
                candidate_count = len(self.session._space_region_candidates)
                if candidate_count:
                    selection_help = "{}\n{}".format(
                        selection_help,
                        translate("BIM_PlanEdit", "{count} enclosed regions are available.").format(
                            count=candidate_count
                        ),
                    )
                hovered_candidate = self.session._hovered_space_region_candidate
                if hovered_candidate:
                    selection_help = "{}\n{}".format(
                        selection_help,
                        translate("BIM_PlanEdit", "Hovered region area: {area}").format(
                            area=self.session._format_space_region_candidate_area(hovered_candidate)
                        ),
                    )
            elif tool == "Region":
                selection_state = translate("BIM_PlanEdit", "Region: draw polygon")
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Click polygon points to define a semantic plan region. Press Enter to finish, or click near the first point to close.",
                )
                if self.session._is_plan_space_object(self.session._plan_region_parent_space):
                    selection_help = "{}\n{}".format(
                        selection_help,
                        translate("BIM_PlanEdit", "Parent space: {label}").format(
                            label=self.session._plan_region_parent_space.Label
                        ),
                    )
            elif tool == "Separator":
                selection_state = translate("BIM_PlanEdit", "Separator: place divider")
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Click two points to place a room divider that can split Arch Spaces.",
                )
            elif selected_kind == "opening" and selected_obj is not None:
                selection_state = selected_state
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use in-view handles to move or flip the selected opening.",
                )
            elif selected_kind == "symbol" and selected_obj is not None:
                selection_state = selected_state
                if self.session.current_tool == "Rotate Symbol":
                    if self.session._symbol_rotation_snap_enabled():
                        selection_help = translate(
                            "BIM_PlanEdit",
                            "Use in-view handles to rotate the selected symbol instance. Rotation snaps to {snap} by default; hold Shift for free angle.",
                        ).format(snap=self.session._format_symbol_rotation_snap_label())
                    else:
                        selection_help = translate(
                            "BIM_PlanEdit",
                            "Use in-view handles to rotate the selected symbol instance.",
                        )
                else:
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use in-view handles to move or rotate the selected symbol instance.",
                    )
            elif selected_kind == "region" and selected_obj is not None:
                selection_state = selected_state
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use the region controls below to edit label, scheme, type, and parent space.",
                )
            elif selected_kind == "space" and selected_obj is not None:
                selection_state = selected_state
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use the space controls below to edit label, type, boundaries, and text position.",
                )
            elif selected_kind == "wall" and selected_obj is not None:
                selection_state = selected_state
                if self.session.is_selected_wall_endpoint_editable():
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "Use wall grips in the viewport to stretch or move the selected wall.",
                    )
                else:
                    selection_help = translate(
                        "BIM_PlanEdit",
                        "This wall can be reviewed in plan, but grip editing is unavailable.",
                    )
            else:
                selection_state = translate("BIM_PlanEdit", "Selection: none")
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Select a wall, hosted opening, symbol instance, region, or space to edit it, or use walls and separators to define spaces.",
                )
            selection_summary = self.session._get_plan_selection_summary_text()
            if selection_summary:
                selection_help = "{}\n{}".format(selection_help, selection_summary)
            if self.session.current_tool == "Select":
                selection_help = "{}\n{}".format(
                    selection_help,
                    translate(
                        "BIM_PlanEdit",
                        "Ctrl-click adds or removes targets without replacing the current editor target.",
                    ),
                )
            if self.session._plan_relation_status_message:
                selection_help = "{}\n{}".format(
                    selection_help,
                    self.session._plan_relation_status_message,
                )
            self.status.setText(
                translate(
                    "BIM_PlanEdit",
                    "Mode: {tool}\nStorey: {storey}\nDisplay: Footprint\n{selection_state}\n{selection_help}",
                ).format(
                    tool=tool,
                    storey=storey_text,
                    selection_state=selection_state,
                    selection_help=selection_help,
                )
            )
            self._refresh_space_editor()
            self._refresh_region_editor()
            self._apply_modal_interaction_state(modal_active)

    def _refresh_space_editor(self):
        from PySide import QtGui

        with self.session._plan_perf_trace_span("refresh_space_editor"):
            if self.space_editor is None:
                return
            selected_kind, selected_obj = self.session._get_selected_plan_target()
            space = selected_obj if selected_kind == "space" else None
            show_editor = bool(space and self.session.current_tool in ("Select", "Set Space Text"))
            try:
                self.space_editor.setVisible(show_editor)
            except Exception:
                pass
            if not show_editor:
                return

            self._refreshing_space_editor = True
            try:
                space_key = self._get_editor_object_key(space)
                label = getattr(space, "Label", "")
                if self.space_label_edit is not None:
                    label_state = (space_key, label)
                    if label_state != self._space_editor_label_state:
                        self.space_label_edit.setText(label)
                        self._space_editor_label_state = label_state

                current_type = getattr(space, "SpaceType", "")
                options = self._get_cached_space_type_options(space, current_type)
                if self.space_type_combo is not None:
                    combo_state = (space_key, options, str(current_type or ""))
                    if combo_state != self._space_editor_combo_state:
                        self.session._plan_perf_count("space_type_options", len(options))
                        self.space_type_combo.blockSignals(True)
                        try:
                            self._set_space_type_combo_options(options)
                            current_index = self._find_space_type_combo_index(current_type)
                            if current_index >= 0:
                                self.space_type_combo.setCurrentIndex(current_index)
                            else:
                                line_edit = self.space_type_combo.lineEdit()
                                if line_edit is not None:
                                    line_edit.setText(current_type)
                        finally:
                            self.space_type_combo.blockSignals(False)
                        self._space_editor_combo_state = combo_state

                if self.space_boundary_list is not None:
                    boundary_state = (space_key, self._get_space_boundary_signature(space))
                    if boundary_state != self._space_editor_boundary_state:
                        boundary_entries = list(
                            self.session._get_space_boundary_entries(space) or []
                        )
                        self.session._plan_perf_count(
                            "space_boundary_entries", len(boundary_entries)
                        )
                        self.space_boundary_list.clear()
                        for obj, subnames in boundary_entries:
                            label = getattr(obj, "Label", getattr(obj, "Name", ""))
                            suffix = ", ".join(subnames)
                            text = f"{label}: {suffix}" if suffix else label
                            item = QtGui.QListWidgetItem(text)
                            item.setToolTip(getattr(obj, "Name", ""))
                            self.space_boundary_list.addItem(item)
                        self._space_editor_boundary_state = boundary_state
            finally:
                self._refreshing_space_editor = False

    def _refresh_region_editor(self):
        with self.session._plan_perf_trace_span("refresh_region_editor"):
            if self.region_editor is None:
                return
            selected_kind, selected_obj = self.session._get_selected_plan_target()
            region = selected_obj if selected_kind == "region" else None
            show_editor = bool(region and self.session.current_tool == "Select")
            try:
                self.region_editor.setVisible(show_editor)
            except Exception:
                pass
            if not show_editor:
                return

            self._refreshing_region_editor = True
            try:
                if self.region_label_edit is not None:
                    self.region_label_edit.setText(getattr(region, "Label", ""))
                if self.region_scheme_edit is not None:
                    self.region_scheme_edit.setText(getattr(region, "Scheme", ""))
                if self.region_type_edit is not None:
                    self.region_type_edit.setText(getattr(region, "RegionType", ""))
                if self.region_parent_space_combo is not None:
                    self.region_parent_space_combo.blockSignals(True)
                    try:
                        self._set_region_parent_space_combo_options(region)
                        self.session._plan_perf_count(
                            "region_parent_space_candidates",
                            max(0, len(self._region_parent_space_items) - 1),
                        )
                    finally:
                        self.region_parent_space_combo.blockSignals(False)
            finally:
                self._refreshing_region_editor = False

    def _apply_modal_interaction_state(self, modal_active):
        from PySide import QtCore

        for widget in self._modal_focus_widgets:
            if widget is None:
                continue
            try:
                widget.setFocusPolicy(
                    QtCore.Qt.NoFocus
                    if modal_active
                    else self._saved_focus_policies.get(widget, QtCore.Qt.StrongFocus)
                )
            except Exception:
                pass

        for widget in (
            self.storey_combo,
            self.select_button,
            self.wall_button,
            self.rect_wall_button,
            self.space_button,
            self.region_button,
            self.separator_button,
            self.move_button,
            self.join_button,
            self.join_type_combo,
            self.unjoin_button,
            self.reapply_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(not modal_active)
            except Exception:
                pass
        if self.unjoin_button is not None:
            try:
                self.unjoin_button.setEnabled(
                    not modal_active
                    and self.session.current_tool == "Join"
                    and self.session._get_plan_candidate_joint() is not None
                )
            except Exception:
                pass

        selected_kind, _selected_obj = self.session._get_selected_plan_target()
        has_space = selected_kind == "space"
        for widget in (
            self.space_label_edit,
            self.space_type_combo,
            self.space_boundary_list,
            self.space_add_button,
            self.space_remove_button,
            self.space_text_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(has_space and not modal_active))
            except Exception:
                pass

        has_region = selected_kind == "region"
        for widget in (
            self.region_label_edit,
            self.region_scheme_edit,
            self.region_type_edit,
            self.region_parent_space_combo,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(bool(has_region and not modal_active))
            except Exception:
                pass

    def on_storey_changed(self, index):
        if 0 <= index < len(self._storey_items):
            self.session.set_active_storey(self._storey_items[index])

    def on_select_clicked(self):
        self.session.activate_select_tool()

    def on_wall_clicked(self):
        self.session.activate_wall_tool()

    def on_rect_wall_clicked(self):
        self.session.activate_rect_wall_tool()

    def on_space_clicked(self):
        self.session.activate_space_tool()

    def on_region_clicked(self):
        self.session.activate_plan_region_tool()

    def on_separator_clicked(self):
        self.session.activate_space_separator_tool()

    def on_move_clicked(self):
        self.session.activate_move_tool()

    def on_join_clicked(self):
        self.session.activate_join_tool()

    def on_join_type_changed(self, index):
        if self.join_type_combo is None or index < 0:
            return
        join_type = self.join_type_combo.itemData(index) or self.join_type_combo.itemText(index)
        self.session.set_plan_join_type(join_type)

    def on_unjoin_clicked(self):
        self.session._unjoin_current_plan_wall_pair()

    def on_reapply_clicked(self):
        self.session.apply_plan_view(fit=False)
        self.refresh_from_session()

    def on_space_label_edited(self):
        if self._refreshing_space_editor or self.space_label_edit is None:
            return
        self.session._set_selected_space_label(self.space_label_edit.text())

    def on_space_type_changed(self, index):
        if self._refreshing_space_editor or self.space_type_combo is None or index < 0:
            return
        value = self.space_type_combo.itemData(index) or self.space_type_combo.itemText(index)
        self.session._set_selected_space_type(value)

    def on_space_type_completion_activated(self, value):
        if self._refreshing_space_editor or self.space_type_combo is None:
            return
        self._commit_space_type_combo_text(value)

    def on_space_type_editing_finished(self):
        if self._refreshing_space_editor or self.space_type_combo is None:
            return
        line_edit = self.space_type_combo.lineEdit()
        if line_edit is None:
            return
        self._commit_space_type_combo_text(line_edit.text())

    def on_space_add_clicked(self):
        self.session._add_boundaries_to_selected_space()

    def on_space_remove_clicked(self):
        if self.space_boundary_list is None:
            return
        rows = sorted({index.row() for index in self.space_boundary_list.selectedIndexes()})
        self.session._remove_selected_space_boundaries(rows)

    def on_space_text_clicked(self):
        self.session._start_space_text_position_pick()

    def on_region_label_edited(self):
        if self._refreshing_region_editor or self.region_label_edit is None:
            return
        self.session._set_selected_region_label(self.region_label_edit.text())

    def on_region_scheme_edited(self):
        if self._refreshing_region_editor or self.region_scheme_edit is None:
            return
        self.session._set_selected_region_scheme(self.region_scheme_edit.text())

    def on_region_type_edited(self):
        if self._refreshing_region_editor or self.region_type_edit is None:
            return
        self.session._set_selected_region_type(self.region_type_edit.text())

    def on_region_parent_space_changed(self, index):
        if self._refreshing_region_editor or self.region_parent_space_combo is None:
            return
        if index < 0 or index >= len(self._region_parent_space_items):
            return
        self.session._set_selected_region_parent_space(self._region_parent_space_items[index])

    def on_exit_clicked(self):
        self.session.shutdown()


class _PlanEditViewportStatusChip:
    def __new__(cls, session, host_widget):
        from PySide import QtCore, QtGui

        class _Chip(QtGui.QFrame):
            def __init__(self, plan_session, parent_widget):
                super().__init__(parent_widget)
                self.session = plan_session
                self.host_widget = parent_widget
                self.setObjectName("BIMPlanEditViewportStatusChip")
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                self.setFocusPolicy(QtCore.Qt.NoFocus)
                self.setFrameShape(QtGui.QFrame.NoFrame)
                self.setStyleSheet("""
                    QFrame#BIMPlanEditViewportStatusChip {
                        background: rgba(250, 250, 248, 230);
                        border: 1px solid rgba(24, 40, 56, 60);
                        border-radius: 10px;
                    }
                    QLabel#BIMPlanEditViewportStatusTitle {
                        color: rgb(25, 32, 38);
                        font-weight: 600;
                    }
                    QLabel#BIMPlanEditViewportStatusBody {
                        color: rgb(60, 68, 76);
                    }
                    """)

                layout = QtGui.QVBoxLayout(self)
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(2)

                self.title_label = QtGui.QLabel(self)
                self.title_label.setObjectName("BIMPlanEditViewportStatusTitle")
                self.body_label = QtGui.QLabel(self)
                self.body_label.setObjectName("BIMPlanEditViewportStatusBody")
                self.body_label.setWordWrap(True)
                self.body_label.setMaximumWidth(300)

                layout.addWidget(self.title_label)
                layout.addWidget(self.body_label)

                try:
                    self.host_widget.installEventFilter(self)
                except Exception:
                    pass

            def set_texts(self, title, body):
                self.title_label.setText(title)
                self.body_label.setText(body)
                self.adjustSize()
                self._reposition()
                self.show()
                self.raise_()

            def _reposition(self):
                host = self.host_widget
                if host is None:
                    return
                margin = 14
                max_width = max(180, host.width() - (margin * 2))
                self.setMaximumWidth(max_width)
                self.body_label.setMaximumWidth(max_width - 24)
                self.adjustSize()
                self.move(margin, margin)

            def eventFilter(self, watched, event):
                if watched is self.host_widget and event.type() in (
                    QtCore.QEvent.Resize,
                    QtCore.QEvent.Move,
                    QtCore.QEvent.Show,
                ):
                    self._reposition()
                return QtGui.QFrame.eventFilter(self, watched, event)

            def close_chip(self):
                host = self.host_widget
                if host is not None:
                    try:
                        host.removeEventFilter(self)
                    except Exception:
                        pass
                self.host_widget = None
                self.hide()
                self.deleteLater()

        return _Chip(session, host_widget)

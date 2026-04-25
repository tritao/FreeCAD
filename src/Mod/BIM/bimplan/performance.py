# SPDX-License-Identifier: LGPL-2.1-or-later

"""Performance tracing helpers for BIM Plan Edit."""

from contextlib import contextmanager
import json
import os
import tempfile
import time


def _performance_state(session):
    return session.performance_state


def resolve_plan_perf_log_path(session):
    pref_enabled = False
    try:
        pref_enabled = bool(
            _performance_state(session).plan_edit_params.GetBool("PerfTrace", False)
        )
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


def resolve_plan_pick_debug_log_path(session):
    del session
    env_value = str(os.environ.get("FC_BIM_PLAN_EDIT_PICK_DEBUG", "") or "").strip()
    env_log_path = str(os.environ.get("FC_BIM_PLAN_EDIT_PICK_DEBUG_LOG", "") or "").strip()
    false_values = {"0", "false", "False", "no", "off"}
    true_values = {"1", "true", "True", "yes", "on"}

    if env_value:
        if env_value in false_values:
            return None
        if env_value in true_values:
            return env_log_path or os.path.join(
                tempfile.gettempdir(),
                "bim_plan_edit_pick_debug.jsonl",
            )
        return env_value

    if env_log_path:
        return env_log_path
    return None


def is_plan_perf_trace_enabled(session):
    return bool(_performance_state(session).plan_perf_log_path)


def is_plan_pick_debug_enabled(session):
    return bool(_performance_state(session).plan_pick_debug_log_path)


def is_plan_pick_debug_active(session):
    return bool(_performance_state(session).plan_pick_debug_scope_depth)


def plan_perf_describe_object(_session, obj):
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


def plan_perf_describe_target(session, kind, obj):
    if not kind or not obj:
        return None
    result = {"kind": kind}
    described = plan_perf_describe_object(session, obj)
    if isinstance(described, dict):
        result.update(described)
    elif described is not None:
        result["value"] = described
    return result


def plan_perf_coerce_value(session, value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [plan_perf_coerce_value(session, item) for item in value]
    if isinstance(value, dict):
        return {str(key): plan_perf_coerce_value(session, item) for key, item in value.items()}
    described = plan_perf_describe_object(session, value)
    if described is not None:
        return described
    return repr(value)


def plan_perf_set_fields(session, **fields):
    event = _performance_state(session).plan_perf_current_event
    if not event:
        return
    event_fields = event.setdefault("fields", {})
    for key, value in fields.items():
        if value is None:
            continue
        event_fields[str(key)] = plan_perf_coerce_value(session, value)


def plan_perf_count(session, name, delta=1):
    event = _performance_state(session).plan_perf_current_event
    if not event:
        return
    counts = event.setdefault("counts", {})
    counts[str(name)] = counts.get(str(name), 0) + delta


def plan_perf_note_error(session, scope, exc):
    event = _performance_state(session).plan_perf_current_event
    if not event:
        return
    errors = event.setdefault("errors", [])
    errors.append({"scope": str(scope), "message": repr(exc)})


def plan_perf_finalize_event(_session, event, total_ms):
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


def plan_perf_write_event(session, event, total_ms):
    if not is_plan_perf_trace_enabled(session):
        return
    try:
        log_path = _performance_state(session).plan_perf_log_path
        directory = os.path.dirname(log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(plan_perf_finalize_event(session, event, total_ms), sort_keys=True)
            )
            handle.write("\n")
    except Exception:
        pass


def plan_pick_debug_event(session, name, **fields):
    if not is_plan_pick_debug_enabled(session):
        return
    state = _performance_state(session)
    try:
        state.plan_pick_debug_sequence = int(state.plan_pick_debug_sequence or 0) + 1
    except Exception:
        state.plan_pick_debug_sequence = 1

    output = {
        "event": str(name),
        "seq": state.plan_pick_debug_sequence,
        "pid": os.getpid(),
        "ts_unix": round(time.time(), 6),
        "tool": getattr(session, "current_tool", ""),
        "fields": {},
    }
    scope = str(state.plan_pick_debug_scope_name or "").strip()
    if scope:
        output["scope"] = scope
    try:
        output["overlay_mode"] = str(session.providers.get_plan_provider_overlay_mode() or "")
    except Exception:
        pass
    for key, value in fields.items():
        if value is None:
            continue
        output["fields"][str(key)] = plan_perf_coerce_value(session, value)

    try:
        log_path = state.plan_pick_debug_log_path
        directory = os.path.dirname(log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, sort_keys=True))
            handle.write("\n")
    except Exception:
        pass


@contextmanager
def plan_pick_debug_scope(session, name, **fields):
    if not is_plan_pick_debug_enabled(session):
        yield None
        return
    state = _performance_state(session)
    previous_name = str(state.plan_pick_debug_scope_name or "")
    previous_depth = int(state.plan_pick_debug_scope_depth or 0)
    state.plan_pick_debug_scope_name = str(name or "").strip()
    state.plan_pick_debug_scope_depth = previous_depth + 1
    plan_pick_debug_event(session, f"{name}_start", **fields)
    try:
        yield None
    finally:
        selected_after = session.selection.get_selected_plan_target()
        plan_pick_debug_event(
            session,
            f"{name}_end",
            selected_after=plan_perf_describe_target(
                session,
                selected_after[0],
                selected_after[1],
            ),
            provider_selected_objects=[
                plan_perf_describe_object(session, obj)
                for obj in tuple(session.provider_transient_state.provider_selected_objects or ())
            ],
        )
        state.plan_pick_debug_scope_depth = previous_depth
        state.plan_pick_debug_scope_name = previous_name


@contextmanager
def plan_perf_trace_event(session, name, **fields):
    if not is_plan_perf_trace_enabled(session):
        yield None
        return
    state = _performance_state(session)
    if state.plan_perf_current_event is not None:
        with plan_perf_trace_span(session, name, **fields):
            yield state.plan_perf_current_event
        return
    state.plan_perf_sequence += 1
    event = {
        "event": str(name),
        "seq": state.plan_perf_sequence,
        "pid": os.getpid(),
        "ts_unix": time.time(),
        "tool": session.current_tool,
        "fields": {},
        "counts": {},
        "spans": {},
    }
    previous_event = state.plan_perf_current_event
    state.plan_perf_current_event = event
    plan_perf_set_fields(session, **fields)
    start_time = time.perf_counter()
    try:
        yield event
    except Exception as exc:
        plan_perf_note_error(session, name, exc)
        raise
    finally:
        total_ms = (time.perf_counter() - start_time) * 1000.0
        event["tool"] = session.current_tool
        plan_perf_write_event(session, event, total_ms)
        state.plan_perf_current_event = previous_event


@contextmanager
def plan_perf_trace_span(session, name, **fields):
    event = _performance_state(session).plan_perf_current_event
    if event is None:
        yield None
        return
    plan_perf_set_fields(session, **fields)
    start_time = time.perf_counter()
    try:
        yield event
    except Exception as exc:
        plan_perf_note_error(session, name, exc)
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        spans = event.setdefault("spans", {})
        span = spans.setdefault(str(name), {"ms": 0.0, "count": 0})
        span["ms"] += elapsed_ms
        span["count"] += 1


class PlanPerformanceAPI:
    """Owned session surface for Plan Edit perf tracing and pick debug."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def resolve_plan_perf_log_path(self, *args, **kwargs):
        return resolve_plan_perf_log_path(self.session, *args, **kwargs)

    def resolve_plan_pick_debug_log_path(self, *args, **kwargs):
        return resolve_plan_pick_debug_log_path(self.session, *args, **kwargs)

    def is_plan_perf_trace_enabled(self, *args, **kwargs):
        return is_plan_perf_trace_enabled(self.session, *args, **kwargs)

    def is_plan_pick_debug_enabled(self, *args, **kwargs):
        return is_plan_pick_debug_enabled(self.session, *args, **kwargs)

    def is_plan_pick_debug_active(self, *args, **kwargs):
        return is_plan_pick_debug_active(self.session, *args, **kwargs)

    def plan_perf_describe_object(self, *args, **kwargs):
        return plan_perf_describe_object(self.session, *args, **kwargs)

    def plan_perf_describe_target(self, *args, **kwargs):
        return plan_perf_describe_target(self.session, *args, **kwargs)

    def plan_perf_coerce_value(self, *args, **kwargs):
        return plan_perf_coerce_value(self.session, *args, **kwargs)

    def plan_perf_set_fields(self, *args, **kwargs):
        return plan_perf_set_fields(self.session, *args, **kwargs)

    def plan_perf_count(self, *args, **kwargs):
        return plan_perf_count(self.session, *args, **kwargs)

    def plan_perf_note_error(self, *args, **kwargs):
        return plan_perf_note_error(self.session, *args, **kwargs)

    def plan_perf_finalize_event(self, *args, **kwargs):
        return plan_perf_finalize_event(self.session, *args, **kwargs)

    def plan_perf_write_event(self, *args, **kwargs):
        return plan_perf_write_event(self.session, *args, **kwargs)

    def plan_perf_trace_event(self, *args, **kwargs):
        return plan_perf_trace_event(self.session, *args, **kwargs)

    def plan_perf_trace_span(self, *args, **kwargs):
        return plan_perf_trace_span(self.session, *args, **kwargs)

    def plan_pick_debug_event(self, *args, **kwargs):
        return plan_pick_debug_event(self.session, *args, **kwargs)

    def plan_pick_debug_scope(self, name, **fields):
        return plan_pick_debug_scope(self.session, name, **fields)

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Performance tracing helpers for BIM Plan Edit."""

from contextlib import contextmanager
import json
import os
import tempfile
import time


def resolve_plan_perf_log_path(session):
    pref_enabled = False
    try:
        pref_enabled = bool(session._plan_edit_params.GetBool("PerfTrace", False))
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


def is_plan_perf_trace_enabled(session):
    return bool(session._plan_perf_log_path)


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
    described = session._plan_perf_describe_object(obj)
    if isinstance(described, dict):
        result.update(described)
    elif described is not None:
        result["value"] = described
    return result


def plan_perf_coerce_value(session, value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [session._plan_perf_coerce_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): session._plan_perf_coerce_value(item) for key, item in value.items()}
    described = session._plan_perf_describe_object(value)
    if described is not None:
        return described
    return repr(value)


def plan_perf_set_fields(session, **fields):
    event = session._plan_perf_current_event
    if not event:
        return
    event_fields = event.setdefault("fields", {})
    for key, value in fields.items():
        if value is None:
            continue
        event_fields[str(key)] = session._plan_perf_coerce_value(value)


def plan_perf_count(session, name, delta=1):
    event = session._plan_perf_current_event
    if not event:
        return
    counts = event.setdefault("counts", {})
    counts[str(name)] = counts.get(str(name), 0) + delta


def plan_perf_note_error(session, scope, exc):
    event = session._plan_perf_current_event
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
    if not session._is_plan_perf_trace_enabled():
        return
    try:
        directory = os.path.dirname(session._plan_perf_log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(session._plan_perf_log_path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(session._plan_perf_finalize_event(event, total_ms), sort_keys=True)
            )
            handle.write("\n")
    except Exception:
        pass


@contextmanager
def plan_perf_trace_event(session, name, **fields):
    if not session._is_plan_perf_trace_enabled():
        yield None
        return
    if session._plan_perf_current_event is not None:
        with session._plan_perf_trace_span(name, **fields):
            yield session._plan_perf_current_event
        return
    session._plan_perf_sequence += 1
    event = {
        "event": str(name),
        "seq": session._plan_perf_sequence,
        "pid": os.getpid(),
        "ts_unix": time.time(),
        "tool": session.current_tool,
        "fields": {},
        "counts": {},
        "spans": {},
    }
    previous_event = session._plan_perf_current_event
    session._plan_perf_current_event = event
    session._plan_perf_set_fields(**fields)
    start_time = time.perf_counter()
    try:
        yield event
    except Exception as exc:
        session._plan_perf_note_error(name, exc)
        raise
    finally:
        total_ms = (time.perf_counter() - start_time) * 1000.0
        event["tool"] = session.current_tool
        session._plan_perf_write_event(event, total_ms)
        session._plan_perf_current_event = previous_event


@contextmanager
def plan_perf_trace_span(session, name, **fields):
    event = session._plan_perf_current_event
    if event is None:
        yield None
        return
    session._plan_perf_set_fields(**fields)
    start_time = time.perf_counter()
    try:
        yield event
    except Exception as exc:
        session._plan_perf_note_error(name, exc)
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        spans = event.setdefault("spans", {})
        span = spans.setdefault(str(name), {"ms": 0.0, "count": 0})
        span["ms"] += elapsed_ms
        span["count"] += 1

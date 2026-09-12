# SPDX-License-Identifier: LGPL-2.1-or-later

"""Debug payload helpers for BIM Plan Edit picking."""

MAX_PICK_DEBUG_ITEMS = 40


def emit_pick_debug(session, name, **fields):
    if not session.performance.is_plan_pick_debug_active():
        return
    session.performance.plan_pick_debug_event(name, **fields)


def append_pick_debug_item(items, value, limit=MAX_PICK_DEBUG_ITEMS):
    if items is None or value is None or len(items) >= int(limit):
        return
    items.append(value)


def describe_pick_object(session, obj):
    try:
        return session.performance.plan_perf_describe_object(obj)
    except Exception:
        pass
    if obj is None:
        return None
    document_name = str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip()
    object_name = str(getattr(obj, "Name", "") or "").strip()
    label = str(getattr(obj, "Label", "") or "").strip()
    result = {}
    if document_name:
        result["document"] = document_name
    if object_name:
        result["name"] = object_name
    if label and label != object_name:
        result["label"] = label
    return result or repr(obj)


def describe_pick_target(session, kind, obj):
    try:
        return session.performance.plan_perf_describe_target(kind, obj)
    except Exception:
        pass
    if not kind or obj is None:
        return None
    result = {"kind": str(kind)}
    described = describe_pick_object(session, obj)
    if isinstance(described, dict):
        result.update(described)
    elif described is not None:
        result["value"] = described
    return result


def describe_pick_info_entry(info):
    if not info:
        return None
    result = {}
    for key in ("Document", "Object"):
        value = str(info.get(key) or "").strip()
        if value:
            result[key.lower()] = value
    parent_obj = info.get("ParentObject")
    if parent_obj is not None:
        result["parent_object"] = {
            "document": str(
                getattr(getattr(parent_obj, "Document", None), "Name", "") or ""
            ).strip(),
            "name": str(getattr(parent_obj, "Name", "") or "").strip(),
        }
    return result or None


def describe_pick_overlay_target(target):
    if target is None:
        return None
    target_kind = getattr(target, "target_kind", None)
    if target_kind is not None:
        target_kind = getattr(target_kind, "value", target_kind)
    result = {
        "document_name": str(getattr(target, "document_name", "") or "").strip(),
        "object_name": str(getattr(target, "object_name", "") or "").strip(),
        "target_kind": str(target_kind or "").strip(),
    }
    subname = str(getattr(target, "subname", "") or "").strip()
    if subname:
        result["subname"] = subname
    return result


def describe_pick_overlay(overlay):
    if overlay is None:
        return None
    marker_kind = getattr(overlay, "marker_kind", None)
    if marker_kind is not None:
        marker_kind = getattr(marker_kind, "value", marker_kind)
    return {
        "provider_id": str(getattr(overlay, "provider_id", "") or "").strip(),
        "key": str(getattr(overlay, "key", "") or "").strip(),
        "category": str(getattr(overlay, "category", "") or "").strip(),
        "marker_kind": str(marker_kind or "").strip(),
        "marker_size": float(getattr(overlay, "marker_size", 0.0) or 0.0),
        "point_count": len(tuple(getattr(overlay, "points", ()) or ())),
    }

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-overlay pick target helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.providers import runtime as plan_provider_runtime
from . import edit_nodes as plan_edit_nodes
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets

_PROVIDER_OVERLAY_POINT_PREFIX = "ProviderOverlayPoint"


def get_provider_overlay_target_from_edit_node(session, node):
    if not node:
        return (None, None)
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind == "provider_overlay_target":
        try:
            return plan_edit_nodes.get_edit_node_payload(node)
        except Exception:
            return (None, None)
    if node_kind != "provider_overlay_point":
        return (None, None)
    try:
        (point,) = plan_edit_nodes.get_edit_node_payload(node)
        document_name = str(point.documentName.getValue())
        object_name = str(point.objectName.getValue())
        subname = str(point.subElementName.getValue())
    except Exception:
        return (None, None)
    obj = resolve_document_object(session, document_name, object_name)
    if obj is None:
        return (None, None)
    target_kind = parse_provider_overlay_target_kind(subname)
    if target_kind and session.selection.state.is_valid_plan_target(target_kind, obj):
        return (target_kind, obj)
    inferred_kind, inferred_obj = plan_targets.get_plan_target_for_object(session, obj)
    if inferred_kind and inferred_obj:
        return (inferred_kind, inferred_obj)
    return (None, obj)


def is_provider_overlay_point_subname(subname):
    return str(subname or "").startswith(_PROVIDER_OVERLAY_POINT_PREFIX + ":")


def parse_provider_overlay_target_kind(subname):
    parts = str(subname or "").split(":")
    if len(parts) < 2 or parts[0] != _PROVIDER_OVERLAY_POINT_PREFIX:
        return ""
    return parts[1].strip()


def resolve_document_object(session, document_name, object_name):
    object_name = str(object_name or "").strip()
    if not object_name:
        return None
    document_name = str(document_name or "").strip()
    doc = None
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = None
    if doc is None:
        doc = getattr(session, "doc", None)
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def coerce_overlay_point_vector(point):
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        return FreeCAD.Vector(float(point[0]), float(point[1]), float(point[2]))
    except (TypeError, ValueError, IndexError):
        try:
            return FreeCAD.Vector(
                float(point.x),
                float(point.y),
                float(getattr(point, "z", 0.0) or 0.0),
            )
        except Exception:
            return None


def collect_visible_provider_overlay_targets(session):
    targets = {}
    for identity, target in iter_visible_provider_overlay_targets(session):
        if identity in targets:
            continue
        targets[identity] = target
    return targets


def iter_provider_overlay_targets_from_info(session, info, visible_targets):
    if not info or not visible_targets:
        return ()
    yielded = []
    for obj in get_objects_info_candidate_objects(session, info):
        identity = get_provider_overlay_object_identity(obj)
        if identity is None:
            continue
        target = visible_targets.get(identity)
        if target is None:
            continue
        yielded.append(
            plan_target_kinds.make_plan_target_ref(
                target.target_kind.value if target.target_kind is not None else "",
                obj,
            )
        )
    return tuple(yielded)


def iter_visible_provider_overlay_targets(session):
    yielded = []
    for overlay in tuple(plan_provider_runtime.get_plan_provider_overlays(session) or ()):
        if not bool(getattr(overlay, "visible", True)):
            continue
        if not plan_provider_runtime.is_plan_provider_overlay_visible(session, overlay):
            continue
        for target in tuple(getattr(overlay, "point_targets", ()) or ()):
            if not has_provider_overlay_target_identity(target):
                continue
            identity = get_provider_overlay_target_identity(session, target)
            if identity is None:
                continue
            yielded.append((identity, target))
    return tuple(yielded)


def get_provider_overlay_object_identity(obj):
    if obj is None:
        return None
    identity = (
        str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip(),
        str(getattr(obj, "Name", "") or "").strip(),
    )
    if not identity[1]:
        return None
    return identity


def get_objects_info_candidate_objects(session, info):
    if not info:
        return ()
    candidates = []
    doc_name = str(info.get("Document") or "").strip()
    obj_name = str(info.get("Object") or "").strip()
    if obj_name:
        resolved = resolve_document_object(session, doc_name, obj_name)
        if resolved is not None:
            candidates.append(resolved)
    parent_obj = info.get("ParentObject")
    if parent_obj is not None and parent_obj not in candidates:
        candidates.append(parent_obj)
    return tuple(candidates)


def get_provider_overlay_target_identity(session, target):
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not object_name:
        return None
    document_name = str(getattr(target, "document_name", "") or "").strip()
    if not document_name:
        document_name = str(getattr(getattr(session, "doc", None), "Name", "") or "")
    return (document_name, object_name)


def has_provider_overlay_target_identity(target):
    return bool(str(getattr(target, "object_name", "") or "").strip())

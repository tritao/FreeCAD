# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed edit-node payloads for BIM Plan Edit picking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolHandleEditNode:
    symbol: object
    role: object

    kind = "symbol_handle"


@dataclass(frozen=True, slots=True)
class OpeningHandleEditNode:
    opening: object
    index: int

    kind = "opening_handle"


@dataclass(frozen=True, slots=True)
class ProviderHandleEditNode:
    provider: object
    index: int

    kind = "provider_handle"


@dataclass(frozen=True, slots=True)
class ProviderOverlayTargetEditNode:
    target_kind: object
    target_obj: object

    kind = "provider_overlay_target"


@dataclass(frozen=True, slots=True)
class ProviderOverlayPointEditNode:
    point: object

    kind = "provider_overlay_point"


@dataclass(frozen=True, slots=True)
class RayEditNode:
    point: object

    kind = "edit_node"


def _get_node_attr(node, attr_name):
    return getattr(node, attr_name, None)


def _has_dataclass_payload(node, attr_name):
    return _get_node_attr(node, attr_name) is not None


def get_edit_node_kind(node):
    if node is None:
        return None
    kind = getattr(node, "kind", None)
    if kind is not None:
        return kind
    try:
        return node[0]
    except Exception:
        return None


def get_edit_node_payload(node):
    kind = get_edit_node_kind(node)
    if kind == "symbol_handle":
        if _has_dataclass_payload(node, "symbol"):
            return (_get_node_attr(node, "symbol"), _get_node_attr(node, "role"))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "opening_handle":
        if _has_dataclass_payload(node, "opening"):
            return (_get_node_attr(node, "opening"), _get_node_attr(node, "index"))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "provider_handle":
        if _has_dataclass_payload(node, "provider"):
            return (_get_node_attr(node, "provider"), _get_node_attr(node, "index"))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "provider_overlay_target":
        if _has_dataclass_payload(node, "target_kind"):
            return (_get_node_attr(node, "target_kind"), _get_node_attr(node, "target_obj"))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind in ("provider_overlay_point", "edit_node"):
        if _has_dataclass_payload(node, "point"):
            return (_get_node_attr(node, "point"),)
        try:
            return (node[1],)
        except Exception:
            return ()
    try:
        return tuple(node[1:])
    except Exception:
        return ()

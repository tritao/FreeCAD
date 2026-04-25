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
        if hasattr(node, "symbol"):
            return (getattr(node, "symbol", None), getattr(node, "role", None))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "opening_handle":
        if hasattr(node, "opening"):
            return (getattr(node, "opening", None), getattr(node, "index", None))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "provider_handle":
        if hasattr(node, "provider"):
            return (getattr(node, "provider", None), getattr(node, "index", None))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind == "provider_overlay_target":
        if hasattr(node, "target_kind"):
            return (getattr(node, "target_kind", None), getattr(node, "target_obj", None))
        try:
            return (node[1], node[2])
        except Exception:
            return ()
    if kind in ("provider_overlay_point", "edit_node"):
        if hasattr(node, "point"):
            return (getattr(node, "point", None),)
        try:
            return (node[1],)
        except Exception:
            return ()
    try:
        return tuple(node[1:])
    except Exception:
        return ()

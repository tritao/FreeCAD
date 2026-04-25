# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed provider action payloads for BIM Plan Edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Mapping


class _PayloadMapping(Mapping):
    _FIELDS: tuple[str, ...] = ()

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._FIELDS)

    def __len__(self) -> int:
        return len(self._FIELDS)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        value = getattr(self, key)
        return default if value is None and key not in self._FIELDS else value


@dataclass(frozen=True, slots=True)
class ProviderPointActionPayload(_PayloadMapping):
    tool: object
    point: object
    placement_point: object
    raw_point: object
    snap_info: object
    snap_object: object
    snap_target: object
    snap_document_name: str
    snap_object_name: str
    snap_component: str
    snap_subname: str
    selected_target: object
    selected_targets: object
    hovered_target: object
    host_target: object
    host_source: str

    _FIELDS = (
        "tool",
        "point",
        "placement_point",
        "raw_point",
        "snap_info",
        "snap_object",
        "snap_target",
        "snap_document_name",
        "snap_object_name",
        "snap_component",
        "snap_subname",
        "selected_target",
        "selected_targets",
        "hovered_target",
        "host_target",
        "host_source",
    )


@dataclass(frozen=True, slots=True)
class ProviderHandleActionPayload(_PayloadMapping):
    handle: object
    handle_key: str
    handle_role: str
    point: object
    placement_point: object
    raw_point: object
    snap_info: object
    snap_object: object
    snap_target: object
    snap_document_name: str
    snap_object_name: str
    snap_component: str
    snap_subname: str
    target_object: object
    provider_target: object
    target_key: str
    target_provider_id: str
    selected_target: object
    selected_targets: object
    hovered_target: object
    host_target: object
    host_source: str

    _FIELDS = (
        "handle",
        "handle_key",
        "handle_role",
        "point",
        "placement_point",
        "raw_point",
        "snap_info",
        "snap_object",
        "snap_target",
        "snap_document_name",
        "snap_object_name",
        "snap_component",
        "snap_subname",
        "target_object",
        "provider_target",
        "target_key",
        "target_provider_id",
        "selected_target",
        "selected_targets",
        "hovered_target",
        "host_target",
        "host_source",
    )

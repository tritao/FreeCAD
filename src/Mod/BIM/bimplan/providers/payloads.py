# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed provider action payloads for BIM Plan Edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Mapping


@dataclass(frozen=True, slots=True, eq=False)
class ProviderHostTargetRef:
    kind: object = None
    obj: object = None

    def __iter__(self):
        yield self.kind
        yield self.obj

    def __len__(self):
        return 2

    def __getitem__(self, index):
        return (self.kind, self.obj)[index]

    def __eq__(self, other):
        if isinstance(other, ProviderHostTargetRef):
            return self.kind == other.kind and self.obj == other.obj
        try:
            other_kind, other_obj = other
        except Exception:
            return False
        return self.kind == other_kind and self.obj == other_obj

    def __hash__(self):
        return hash((self.kind, self.obj))

    def as_tuple(self):
        return (self.kind, self.obj)


def make_provider_host_target_ref(kind=None, obj=None):
    return ProviderHostTargetRef(kind, obj)


def coerce_provider_host_target_ref(value):
    if isinstance(value, ProviderHostTargetRef):
        return value
    if value is None:
        return ProviderHostTargetRef()
    try:
        kind, obj = value
    except Exception:
        return ProviderHostTargetRef()
    return ProviderHostTargetRef(kind, obj)


def unpack_provider_host_target_ref(value):
    return coerce_provider_host_target_ref(value).as_tuple()


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

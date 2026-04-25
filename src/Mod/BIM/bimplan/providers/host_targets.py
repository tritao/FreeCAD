# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed provider host-target payloads for BIM Plan Edit."""

from dataclasses import dataclass


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

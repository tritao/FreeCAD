# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared target-kind strings for BIM Plan Edit."""

from dataclasses import dataclass
from enum import Enum


class PlanTargetKind(str, Enum):
    WALL = "wall"
    OPENING = "opening"
    SYMBOL = "symbol"
    PROVIDER = "provider"
    REGION = "region"
    SPACE = "space"


@dataclass(frozen=True, slots=True, eq=False)
class PlanTargetRef:
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
        if isinstance(other, PlanTargetRef):
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


def normalize_plan_target_kind(kind):
    return getattr(kind, "value", kind)


def make_plan_target_ref(kind=None, obj=None):
    return PlanTargetRef(normalize_plan_target_kind(kind), obj)


def coerce_plan_target_ref(value):
    if isinstance(value, PlanTargetRef):
        return value
    if value is None:
        return PlanTargetRef()
    try:
        kind, obj = value
    except Exception:
        return PlanTargetRef()
    return make_plan_target_ref(kind, obj)


def unpack_plan_target_ref(value):
    return coerce_plan_target_ref(value).as_tuple()


PLAN_TARGET_WALL = PlanTargetKind.WALL.value
PLAN_TARGET_OPENING = PlanTargetKind.OPENING.value
PLAN_TARGET_SYMBOL = PlanTargetKind.SYMBOL.value
PLAN_TARGET_PROVIDER = PlanTargetKind.PROVIDER.value
PLAN_TARGET_REGION = PlanTargetKind.REGION.value
PLAN_TARGET_SPACE = PlanTargetKind.SPACE.value

PRIMARY_PLAN_TARGET_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_PROVIDER,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
)

SUMMARY_PLAN_TARGET_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
)

FOOTPRINT_PLAN_TARGET_KINDS = (
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
)

HOVERED_PLAN_TARGET_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_PROVIDER,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_REGION,
)

PRIMARY_SELECTED_TARGET_PRIORITY_KINDS = (
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_WALL,
    PLAN_TARGET_PROVIDER,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
)

PRIMARY_SELECTED_VISUAL_SYNC_KINDS = (
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
)

CLEAR_PLAN_SELECTION_VISUAL_KINDS = (
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_PROVIDER,
)

PENDING_EDIT_VISUAL_SYNC_KINDS = (
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_PROVIDER,
)

SEMANTIC_TARGET_CLEAR_HOVERED_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_REGION,
)

SPACE_TARGET_CLEAR_HOVERED_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_REGION,
)

WALL_TARGET_CLEAR_HOVERED_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_REGION,
)

SPACE_EDIT_CLEAR_HOVERED_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_SPACE,
)

PLAN_REGION_CANCEL_VISUAL_KINDS = (
    PLAN_TARGET_REGION,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_PROVIDER,
)

SPACE_SEPARATOR_CANCEL_VISUAL_KINDS = (
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SPACE,
    PLAN_TARGET_PROVIDER,
)

EMBEDDED_TOOL_CLEAR_HOVERED_KINDS = (
    PLAN_TARGET_WALL,
    PLAN_TARGET_OPENING,
    PLAN_TARGET_SYMBOL,
    PLAN_TARGET_PROVIDER,
    PLAN_TARGET_REGION,
)

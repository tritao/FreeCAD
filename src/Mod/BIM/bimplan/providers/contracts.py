# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-facing contracts for BIM Plan Edit integrations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

from .commands import PlanProviderActionContext
from .context import PlanEditContext
from .registry import PlanEditRegistry, get_plan_edit_registry
from bimplan.contextual_actions import (
    ContextualActionSpec,
    ContextualInspectorSection,
    ContextualProvider,
    ContextualToolSpec,
)


PLAN_PROVIDER_OVERLAY_MODE_ALL = "all"
PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE = "architecture"
PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL = "electrical"
PLAN_PROVIDER_OVERLAY_MODE_PLUMBING = "plumbing"
FOCUSED_PROVIDER_OVERLAY_PICK_MODES = frozenset(
    (
        PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL,
        PLAN_PROVIDER_OVERLAY_MODE_PLUMBING,
    )
)


class _PlanContractEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class PlanToolInteraction(_PlanContractEnum):
    IMMEDIATE = "immediate"
    POINT = "point"


class PlanIssueSeverity(_PlanContractEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PlanContextPanelState(_PlanContractEnum):
    EMPTY = "empty"
    ACTIVE_TOOL = "active_tool"
    SINGLE_OBJECT = "single_object"
    MULTI_SELECTION = "multi_selection"
    GEOMETRY_REVIEW = "geometry_review"


class PlanContextSubjectKind(_PlanContractEnum):
    SCOPE = "scope"
    INTERACTION = "interaction"
    ENDPOINT = "endpoint"
    NETWORK = "network"
    DISTRIBUTION = "distribution"
    GEOMETRY = "geometry"


class PlanOverlayTargetKind(_PlanContractEnum):
    OBJECT = "object"
    OPENING = "opening"
    PROVIDER = "provider"
    REGION = "region"
    SPACE = "space"
    SYMBOL = "symbol"
    WALL = "wall"


class PlanOverlayMarkerKind(_PlanContractEnum):
    CIRCLE = "circle"
    CIRCLE_CROSS = "circle_cross"
    CROSS = "cross"
    DIAMOND = "diamond"
    HOURGLASS = "hourglass"
    SQUARE = "square"


@dataclass(frozen=True)
class PlanActionSpec(ContextualActionSpec):
    """Plan extension point for a generic contextual action."""


@dataclass(frozen=True)
class PlanToolSpec(ContextualToolSpec):
    """Plan tool with Plan's point/immediate interaction vocabulary."""

    interaction: PlanToolInteraction = PlanToolInteraction.IMMEDIATE


@dataclass(frozen=True)
class PlanEditHandleSpec:
    key: str
    point: tuple[float, float, float]
    label: str = ""
    tooltip: str = ""
    provider_id: str = ""
    target_key: str = ""
    action_key: str = ""
    transaction_label: str = ""
    prompt: str = ""
    role: str = ""
    interaction: PlanToolInteraction = PlanToolInteraction.POINT
    marker_kind: PlanOverlayMarkerKind = PlanOverlayMarkerKind.DIAMOND


@dataclass(frozen=True)
class PlanIssueSpec:
    key: str
    title: str
    message: str = ""
    severity: PlanIssueSeverity = PlanIssueSeverity.INFO
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    target_keys: Tuple[str, ...] = ()
    role: str = ""
    category: str = ""
    group_key: str = ""
    group_title: str = ""
    collapsed: bool = False
    summary: str = ""


@dataclass(frozen=True)
class PlanSuggestionSpec:
    key: str
    title: str
    message: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    target_keys: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanContextRowSpec:
    label: str
    value: str = ""


@dataclass(frozen=True)
class PlanContextDetailSpec:
    key: str
    title: str
    body: str = ""
    rows: Tuple[PlanContextRowSpec, ...] = ()
    collapsed: bool = True


@dataclass(frozen=True)
class PlanContextPanelSpec:
    key: str
    title: str
    subtitle: str = ""
    state: PlanContextPanelState = PlanContextPanelState.EMPTY
    subject_kind: PlanContextSubjectKind = PlanContextSubjectKind.SCOPE
    provider_id: str = ""
    summary_rows: Tuple[PlanContextRowSpec, ...] = ()
    message: str = ""
    primary_action: PlanActionSpec | None = None
    secondary_actions: Tuple[PlanActionSpec, ...] = ()
    details: Tuple[PlanContextDetailSpec, ...] = ()


@dataclass(frozen=True)
class PlanInspectorSection(ContextualInspectorSection):
    """Plan-compatible contextual inspector section."""

    actions: Tuple[PlanActionSpec, ...] = ()


@dataclass(frozen=True)
class PlanOverlayTargetSpec:
    document_name: str = ""
    object_name: str = ""
    target_kind: PlanOverlayTargetKind | None = None
    subname: str = ""


@dataclass(frozen=True)
class PlanProviderTargetSpec:
    key: str
    label: str = ""
    provider_id: str = ""
    document_name: str = ""
    object_name: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    category: str = ""
    role: str = ""


@dataclass(frozen=True)
class PlanOverlaySpec:
    key: str
    label: str = ""
    provider_id: str = ""
    target_keys: Tuple[str, ...] = ()
    points: Tuple[Tuple[float, float, float], ...] = ()
    point_targets: Tuple[PlanOverlayTargetSpec, ...] = ()
    polylines: Tuple[Tuple[Tuple[float, float, float], ...], ...] = ()
    color: Tuple[float, float, float] = (0.2, 0.55, 0.85)
    line_width: float = 2.0
    marker_size: float = 160.0
    marker_kind: PlanOverlayMarkerKind = PlanOverlayMarkerKind.CROSS
    dotted: bool = False
    visible: bool = True
    category: str = ""


class PlanEditProvider(ContextualProvider):
    """Plan-specific provider extension of the contextual provider contract."""

    def get_issues(self, context) -> Sequence[PlanIssueSpec]:
        del context
        return ()

    def get_suggestions(self, context) -> Sequence[PlanSuggestionSpec]:
        del context
        return ()

    def get_context_panels(self, context) -> Sequence[PlanContextPanelSpec]:
        del context
        return ()

    def get_inspector_sections(self, context) -> Sequence[PlanInspectorSection]:
        del context
        return ()

    def get_overlays(self, context) -> Sequence[PlanOverlaySpec]:
        del context
        return ()

    def get_targets(self, context) -> Sequence[PlanProviderTargetSpec]:
        del context
        return ()

    def get_tools(self, context) -> Sequence[PlanToolSpec]:
        del context
        return ()

    def get_edit_handles(self, context) -> Sequence[PlanEditHandleSpec]:
        del context
        return ()

    def execute_action(self, action_key, context, commands, payload=None):
        del action_key, context, commands, payload
        return False

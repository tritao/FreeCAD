# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-facing models for BIM Plan Edit integrations."""

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class PlanActionSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""


@dataclass(frozen=True)
class PlanToolSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""
    group: str = ""
    priority: int = 0
    interaction: str = ""
    prompt: str = ""
    default_host_target: tuple = ()


@dataclass(frozen=True)
class PlanIssueSpec:
    key: str
    title: str
    message: str = ""
    severity: str = "info"
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
class PlanInspectorSection:
    key: str
    title: str
    body: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    role: str = ""
    collapsed: bool = False


@dataclass(frozen=True)
class PlanOverlayTargetSpec:
    document_name: str = ""
    object_name: str = ""
    target_kind: str = ""
    subname: str = ""


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
    marker_kind: str = "cross"
    dotted: bool = False
    visible: bool = True
    category: str = ""


class PlanEditProvider:
    """Base class for add-ons extending BIM Plan Edit."""

    provider_id = ""
    display_name = ""

    def get_provider_id(self):
        provider_id = str(getattr(self, "provider_id", "") or "").strip()
        if provider_id:
            return provider_id
        return self.__class__.__name__

    def get_display_name(self):
        display_name = str(getattr(self, "display_name", "") or "").strip()
        if display_name:
            return display_name
        return self.get_provider_id()

    def get_issues(self, context) -> Sequence[PlanIssueSpec]:
        del context
        return ()

    def get_suggestions(self, context) -> Sequence[PlanSuggestionSpec]:
        del context
        return ()

    def get_inspector_sections(self, context) -> Sequence[PlanInspectorSection]:
        del context
        return ()

    def get_overlays(self, context) -> Sequence[PlanOverlaySpec]:
        del context
        return ()

    def get_tools(self, context) -> Sequence[PlanToolSpec]:
        del context
        return ()

    def execute_action(self, action_key, context, session):
        del action_key, context, session
        return False

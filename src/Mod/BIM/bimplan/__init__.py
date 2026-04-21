# SPDX-License-Identifier: LGPL-2.1-or-later

"""BIM-owned Plan Edit integration primitives."""

from .context import PlanEditContext
from .hosted_openings import create_hosted_opening, has_built_opening_shape
from .hosts import _PlanEditCommandHost, _PlanEditWallHost
from .providers import (
    PlanActionSpec,
    PlanContextDetailSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditProvider,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlaySpec,
    PlanOverlayMarkerKind,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanProviderTargetSpec,
    PlanSuggestionSpec,
    PlanToolSpec,
    PlanToolInteraction,
)
from .registry import PlanEditRegistry, get_plan_edit_registry
from .semantics import PlanSemanticRecord
from .targets import PlanTarget
from .transactions import PlanEditTransaction

__all__ = [
    "PlanActionSpec",
    "PlanContextDetailSpec",
    "PlanContextPanelSpec",
    "PlanContextPanelState",
    "PlanContextRowSpec",
    "PlanContextSubjectKind",
    "PlanEditContext",
    "PlanEditProvider",
    "PlanEditRegistry",
    "PlanEditTransaction",
    "create_hosted_opening",
    "has_built_opening_shape",
    "_PlanEditCommandHost",
    "_PlanEditWallHost",
    "PlanInspectorSection",
    "PlanIssueSpec",
    "PlanIssueSeverity",
    "PlanOverlaySpec",
    "PlanOverlayMarkerKind",
    "PlanOverlayTargetSpec",
    "PlanOverlayTargetKind",
    "PlanProviderTargetSpec",
    "PlanSemanticRecord",
    "PlanSuggestionSpec",
    "PlanTarget",
    "PlanToolSpec",
    "PlanToolInteraction",
    "get_plan_edit_registry",
]

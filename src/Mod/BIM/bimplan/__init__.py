# SPDX-License-Identifier: LGPL-2.1-or-later

"""BIM-owned Plan Edit integration primitives."""

from .context import PlanEditContext
from .hosted_openings import create_hosted_opening, has_built_opening_shape
from .hosts import _PlanEditCommandHost, _PlanEditWallHost
from .providers import (
    PlanActionSpec,
    PlanEditProvider,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanOverlayTargetSpec,
    PlanSuggestionSpec,
    PlanToolSpec,
)
from .registry import PlanEditRegistry, get_plan_edit_registry
from .semantics import PlanSemanticRecord
from .targets import PlanTarget
from .transactions import PlanEditTransaction

__all__ = [
    "PlanActionSpec",
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
    "PlanOverlaySpec",
    "PlanOverlayTargetSpec",
    "PlanSemanticRecord",
    "PlanSuggestionSpec",
    "PlanTarget",
    "PlanToolSpec",
    "get_plan_edit_registry",
]

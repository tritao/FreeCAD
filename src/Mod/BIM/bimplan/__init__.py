# SPDX-License-Identifier: LGPL-2.1-or-later

"""BIM-owned Plan Edit integration primitives."""

from .tools.hosted_openings import (
    _PlanEditCommandHost,
    _PlanEditWallHost,
    create_hosted_opening,
    has_built_opening_shape,
)
from .providers import (
    PlanActionSpec,
    PlanContextDetailSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditContext,
    PlanEditHandleSpec,
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
from .providers import PlanEditRegistry, get_plan_edit_registry
from .runtime import (
    command_gate,
    input,
    lifecycle,
    session,
    session_state,
    view,
)
from .selection import picking
from .semantics import PlanSemanticRecord
from .selection.targets import PlanTarget
from .transactions import PlanEditTransaction

__all__ = [
    "PlanActionSpec",
    "PlanContextDetailSpec",
    "PlanContextPanelSpec",
    "PlanContextPanelState",
    "PlanContextRowSpec",
    "PlanContextSubjectKind",
    "PlanEditHandleSpec",
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
    "command_gate",
    "get_plan_edit_registry",
    "input",
    "lifecycle",
    "picking",
    "session",
    "session_state",
    "view",
]

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared contextual editing architecture for BIM representation contexts."""

from .actions import (
    ContextualActionSpec, ContextualInspectorSection, ContextualProvider,
    ContextualProviderContext, ContextualToolSpec, SemanticEditProvider,
)
from .editing import (
    BIMContextualHandleEditor, BIMEditPreview, BIMEditResult, ContextualEditController,
)
from .editable_points import ContextualEditPoint, get_contextual_edit_points
from .interaction import ContextualInteractionHost
from .profiles import (
    ContextualProfile, ElevationProfile, ModelProfile, PlanProfile, SectionProfile,
    capabilities_for, profile_for, supports,
)
from .session import ContextualSession, active_session, start_session

__all__ = [name for name in globals() if not name.startswith("_")]

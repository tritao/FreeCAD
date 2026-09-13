# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft interaction adapter for architectural representation contexts."""

from draftguitools.gui_base import DraftInteractionHost


class ContextualInteractionHost(DraftInteractionHost):
    """Acquire Draft points on the plane declared by a BIM view context."""

    def __init__(self, context, profile=None, command=None, view=None):
        super().__init__(command=command, view=view)
        self.context = context
        if profile is None:
            from .profiles import profile_for
            profile = profile_for(context)
        self.profile = profile

    def get_interaction_plane(self):
        return self.profile.interaction_plane(self.context)

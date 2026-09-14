# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft interaction adapter for architectural representation contexts."""

from draftguitools.gui_base import DraftInteractionHost


class ContextualInteractionHost(DraftInteractionHost):
    """Acquire Draft points on the plane declared by a BIM view context."""

    def __init__(self, context, plane_resolver=None, command=None, view=None):
        super().__init__(command=command, view=view)
        self.context = context
        if plane_resolver is None:
            from .context_policy import interaction_plane_for

            plane_resolver = interaction_plane_for
        self._plane_resolver = plane_resolver

    def get_interaction_plane(self):
        return self._plane_resolver(self.context)

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft interaction adapter for BIM representation requests."""

from draftguitools.gui_base import DraftInteractionHost


class ContextualInteractionHost(DraftInteractionHost):
    """Acquire Draft points on the plane declared by a BIM view request."""

    def __init__(self, request, plane_resolver=None, command=None, view=None):
        super().__init__(command=command, view=view)
        self.request = request
        if plane_resolver is None:
            from .context_policy import interaction_plane_for

            plane_resolver = interaction_plane_for
        self._plane_resolver = plane_resolver

    def get_interaction_plane(self):
        return self._plane_resolver(self.request)

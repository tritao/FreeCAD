# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft interaction adapter for architectural representation contexts."""

import WorkingPlane

from draftguitools.gui_base import DraftInteractionHost


class ContextualInteractionHost(DraftInteractionHost):
    """Acquire Draft points on the plane declared by a BIM view context."""

    def __init__(self, context, command=None, view=None):
        super().__init__(command=command, view=view)
        self.context = context

    def get_interaction_plane(self):
        frame = getattr(self.context, "reference_frame", None)
        if frame is None:
            return super().get_interaction_plane()
        plane = WorkingPlane.PlaneBase()
        plane.align_to_placement(frame)
        return plane

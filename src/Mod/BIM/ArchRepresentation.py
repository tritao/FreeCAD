# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral inputs for architectural representation providers."""

from enum import Enum


class RepresentationPurpose(Enum):
    """Architectural intent of a representation request."""

    MODEL = "Model"
    PLAN = "Plan"
    SECTION = "Section"
    ELEVATION = "Elevation"


class RepresentationRequest:
    """GUI-independent inputs used to derive a BIM representation.

    ``reference_frame`` is supplied by the caller (normally an
    ``App.Placement``). Distances are measured along its local Z axis. A
    request contains no renderer state and can be passed to headless
    representation providers.
    """

    def __init__(
        self,
        purpose=RepresentationPurpose.MODEL,
        reference_frame=None,
        cut_range=None,
        projection_range=None,
        source=None,
        *,
        cut_offset=None,
        target_offset=None,
    ):
        if not isinstance(purpose, RepresentationPurpose):
            purpose = RepresentationPurpose(purpose)
        self.purpose = purpose
        self.reference_frame = reference_frame
        self.cut_range = cut_range
        self.projection_range = projection_range
        self.source = source
        self.cut_offset = cut_offset
        self.target_offset = target_offset

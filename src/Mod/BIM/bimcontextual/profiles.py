# SPDX-License-Identifier: LGPL-2.1-or-later

"""Profiles and capability policy for architectural editing contexts."""

import ArchRepresentation
import WorkingPlane


_CAPABILITIES = {
    ArchRepresentation.RepresentationPurpose.MODEL: frozenset((
        "wall-path", "wall-section", "wall-height", "create-wall", "insert-opening",
    )),
    ArchRepresentation.RepresentationPurpose.PLAN: frozenset((
        "wall-path", "wall-section", "create-wall", "insert-opening", "create-space",
    )),
    ArchRepresentation.RepresentationPurpose.SECTION: frozenset((
        "wall-height", "insert-opening",
    )),
    ArchRepresentation.RepresentationPurpose.ELEVATION: frozenset((
        "wall-height", "insert-opening",
    )),
}


def supports(context, capability):
    purpose = getattr(context, "purpose", context)
    return str(capability) in _CAPABILITIES.get(purpose, ())


def capabilities_for(context):
    purpose = getattr(context, "purpose", context)
    return _CAPABILITIES.get(purpose, frozenset())


def interaction_plane_for(context):
    """Return the Draft interaction plane declared by a representation context."""

    frame = getattr(context, "reference_frame", None)
    if frame is None:
        return WorkingPlane.get_working_plane()
    plane = WorkingPlane.PlaneBase()
    plane.align_to_placement(frame)
    return plane

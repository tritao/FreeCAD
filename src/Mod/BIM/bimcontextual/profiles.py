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


class ContextualProfile:
    """Declarative policy supplied to the shared contextual session."""

    purpose = ArchRepresentation.RepresentationPurpose.MODEL

    def interaction_plane(self, context):
        frame = getattr(context, "reference_frame", None)
        if frame is None:
            return WorkingPlane.get_working_plane()
        plane = WorkingPlane.PlaneBase()
        plane.align_to_placement(frame)
        return plane

    def providers(self, context):
        del context
        from .actions import (
            HostedOpeningCreationProvider,
            SemanticEditProvider,
            WallCreationProvider,
        )
        return (
            SemanticEditProvider(), HostedOpeningCreationProvider(), WallCreationProvider()
        )

    def supports(self, capability):
        return str(capability) in _CAPABILITIES.get(self.purpose, ())


class ModelProfile(ContextualProfile):
    purpose = ArchRepresentation.RepresentationPurpose.MODEL


class PlanProfile(ContextualProfile):
    purpose = ArchRepresentation.RepresentationPurpose.PLAN


class SectionProfile(ContextualProfile):
    purpose = ArchRepresentation.RepresentationPurpose.SECTION


class ElevationProfile(ContextualProfile):
    purpose = ArchRepresentation.RepresentationPurpose.ELEVATION


_PROFILE_TYPES = {
    profile.purpose: profile
    for profile in (ModelProfile, PlanProfile, SectionProfile, ElevationProfile)
}


def profile_for(context):
    purpose = getattr(context, "purpose", context)
    return _PROFILE_TYPES.get(purpose, ContextualProfile)()

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Product capability policy for architectural editing contexts."""

import ArchRepresentation


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

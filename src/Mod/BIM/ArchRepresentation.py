# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral contracts for architectural representation providers."""

from enum import Enum


class RepresentationPurpose(Enum):
    """Architectural intent of a representation request."""

    MODEL = "Model"
    PLAN = "Plan"
    SECTION = "Section"
    ELEVATION = "Elevation"


class RepresentationUnavailable(LookupError):
    """Raised when a provider cannot represent an object in a request."""


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


class RepresentationSource:
    """Semantic origin of one piece of transient representation geometry."""

    def __init__(self, geometry, source, role, subelement=None, related_sources=()):
        self.geometry = geometry
        self.source = source
        self.role = role
        self.subelement = subelement
        self.related_sources = tuple(related_sources or ())


class BIMRepresentation:
    """Renderer-neutral geometry and identity for one BIM object."""

    _COLLECTIONS = ("cut_geometry", "projected_geometry", "snap_geometry")

    def __init__(self, source=None, request=None):
        self.source = source
        self.request = request
        self.cut_geometry = []
        self.projected_geometry = []
        self.snap_geometry = []
        self.source_mappings = []

    def add_geometry(self, collection, geometry, role, subelement=None, *, related_sources=()):
        """Add geometry to a named collection and preserve semantic mapping."""
        if collection not in self._COLLECTIONS:
            raise ValueError("unknown representation collection: %s" % collection)
        getattr(self, collection).append(geometry)
        self.source_mappings.append(
            RepresentationSource(
                geometry,
                self.source,
                role,
                subelement=subelement,
                related_sources=related_sources,
            )
        )

    def mapping_for(self, geometry):
        """Return the mapping for an exact generated geometry object, if any."""
        return next(
            (mapping for mapping in self.source_mappings if mapping.geometry is geometry),
            None,
        )


def representation_for(obj, request):
    """Request a representation from the object's semantic provider.

    Provider lookup is capability-based: no BIM type names are inspected
    here. A Python proxy implementing ``getRepresentation(obj, request)``
    owns the representation policy for that object.
    """
    provider = getattr(getattr(obj, "Proxy", None), "getRepresentation", None)
    if not callable(provider):
        raise RepresentationUnavailable(
            "BIM object does not provide getRepresentation(obj, request)"
        )
    representation = provider(obj, request)
    if not isinstance(representation, BIMRepresentation):
        raise TypeError("getRepresentation(obj, request) must return BIMRepresentation")
    return representation

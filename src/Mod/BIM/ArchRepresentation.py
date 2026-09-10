# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral contextual BIM representations.

The classes in this module describe *what* an architectural object should
provide for a context.  They intentionally do not know about Coin, Qt or a
document view.  GUI and documentation consumers can therefore request the
same semantic geometry without creating converted document objects.
"""

from enum import Enum


class RepresentationPurpose(Enum):
    """Architectural intent of a representation request."""

    MODEL = "Model"
    PLAN = "Plan"
    SECTION = "Section"
    ELEVATION = "Elevation"


class RepresentationContext:
    """GUI-independent inputs used to derive a BIM representation.

    ``reference_frame`` is an arbitrary object supplied by the caller (in
    FreeCAD this is normally an ``App.Placement``).  Distances are measured
    on that frame's local Z axis.  The context contains no renderer state and
    is safe to pass to headless representation providers.
    """

    def __init__(
        self,
        purpose=RepresentationPurpose.MODEL,
        reference_frame=None,
        cut_range=None,
        projection_range=None,
        profile=None,
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
        self.profile = profile
        self.source = source
        self.cut_offset = cut_offset
        self.target_offset = target_offset


class PlanContext(RepresentationContext):
    """Compatibility context for a horizontal plan cut.

    New providers should prefer ``RepresentationContext`` with an explicit
    frame and offsets.  ``cut_z`` and ``target_z`` remain available while
    existing horizontal plan providers migrate to that contract.
    """

    def __init__(self, cut_z=None, target_z=None, source=None):
        super().__init__(
            purpose=RepresentationPurpose.PLAN,
            source=source,
            cut_offset=cut_z,
            target_offset=target_z,
        )
        self.cut_z = cut_z
        self.target_z = target_z


class RepresentationSource:
    """Semantic origin of one piece of transient representation geometry."""

    def __init__(self, geometry, source, role, subelement=None):
        self.geometry = geometry
        self.source = source
        self.role = role
        self.subelement = subelement


class BIMRepresentation:
    """Renderer-neutral geometry and identity for one BIM object."""

    _COLLECTIONS = ("cut_geometry", "projected_geometry", "snap_geometry")

    def __init__(self, source=None, context=None):
        self.source = source
        self.context = context
        self.cut_geometry = []
        self.projected_geometry = []
        self.snap_geometry = []
        self.source_mappings = []

    def add_geometry(self, collection, geometry, role, subelement=None):
        """Add geometry to a named collection and preserve semantic mapping."""
        if collection not in self._COLLECTIONS:
            raise ValueError("unknown representation collection: %s" % collection)
        getattr(self, collection).append(geometry)
        self.source_mappings.append(
            RepresentationSource(geometry, self.source, role, subelement=subelement)
        )

    def mapping_for(self, geometry):
        """Return the mapping for an exact generated geometry object, if any."""
        return next(
            (mapping for mapping in self.source_mappings if mapping.geometry is geometry),
            None,
        )


def representation_for(obj, context):
    """Request a representation from the object's semantic provider.

    Provider lookup is deliberately capability-based: no BIM type names are
    inspected here. A Python proxy implementing ``getRepresentation(obj,
    context)`` owns the representation policy for that object.
    """
    provider = getattr(getattr(obj, "Proxy", None), "getRepresentation", None)
    if not callable(provider):
        raise TypeError("BIM object does not provide getRepresentation(obj, context)")
    representation = provider(obj, context)
    if not isinstance(representation, BIMRepresentation):
        raise TypeError("getRepresentation(obj, context) must return BIMRepresentation")
    return representation

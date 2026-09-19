# SPDX-License-Identifier: LGPL-2.1-or-later

"""Representation semantics shared by saved BIM views and drawing views."""

import ArchRepresentation


def request_for_view_definition(definition):
    """Build the representation request persisted by a saved BIM view."""

    if definition is None or not definition.isDerivedFrom("App::ViewDefinition"):
        raise TypeError("definition must be an App::ViewDefinition")
    purpose = _purpose(definition.Purpose)
    source = getattr(definition, "BIMContextSource", None)
    if purpose == ArchRepresentation.RepresentationPurpose.PLAN:
        from bimplan.representation_request import representation_request_from_storey

        request = representation_request_from_storey(source)
        request.reference_frame = definition.ReferenceFrame
        return request
    provider = getattr(getattr(source, "Proxy", None), "getRepresentationRequest", None)
    if callable(provider):
        request = provider(source)
        if getattr(request, "purpose", None) == purpose:
            request.reference_frame = definition.ReferenceFrame
            return request
    return ArchRepresentation.RepresentationRequest(
        purpose=purpose,
        reference_frame=definition.ReferenceFrame,
        source=source,
    )


def apply_view_visibility(objects, definition, normally_visible):
    """Apply a definition's forced visibility to objects in its source scope."""

    objects = tuple(objects)
    visible = set(normally_visible)
    visible.update(getattr(definition, "ForcedVisible", ()) or ())
    visible.difference_update(getattr(definition, "ForcedHidden", ()) or ())
    return [obj for obj in objects if obj in visible]


def _purpose(value):
    key = str(value or "Model").strip().casefold()
    for purpose in ArchRepresentation.RepresentationPurpose:
        if purpose.value.casefold() == key:
            return purpose
    raise ValueError("Unsupported BIM view purpose: {}".format(value))

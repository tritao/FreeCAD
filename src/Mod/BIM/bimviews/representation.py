# SPDX-License-Identifier: LGPL-2.1-or-later

"""Representation semantics shared by saved BIM views and drawing views."""

from dataclasses import dataclass

import ArchRepresentation


@dataclass(frozen=True)
class BIMDrawingContext:
    """Resolved, immutable inputs for one BIM drawing render."""

    source: object
    objects: tuple
    request: object = None
    view_definition: object = None
    cutplane: object = None
    only_solids: bool = True
    clip: bool = False
    direction: object = None


def resolve_drawing_context(
    source,
    objects,
    *,
    view_definition=None,
    normally_visible=None,
    cutplane=None,
    only_solids=True,
    clip=False,
    direction=None,
    resolve_request=True,
):
    """Resolve persistent BIM state into render-ready drawing inputs."""

    objects = tuple(objects)
    if normally_visible is not None:
        if view_definition is not None:
            objects = tuple(
                apply_view_visibility(objects, view_definition, normally_visible)
            )
        else:
            visible = set(normally_visible)
            objects = tuple(obj for obj in objects if obj in visible)
    if not resolve_request:
        request = None
    elif view_definition is not None:
        request = request_for_view_definition(view_definition)
    else:
        provider = getattr(
            getattr(source, "Proxy", None), "getRepresentationRequest", None
        )
        request = provider(source) if callable(provider) else None
    return BIMDrawingContext(
        source=source,
        objects=objects,
        request=request,
        view_definition=view_definition,
        cutplane=cutplane,
        only_solids=only_solids,
        clip=clip,
        direction=direction,
    )


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

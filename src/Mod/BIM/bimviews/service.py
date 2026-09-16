# SPDX-License-Identifier: LGPL-2.1-or-later

"""Saved-view lifecycle and activation for the BIM Views Manager."""

from dataclasses import dataclass

import ArchRepresentation


_SUPPORTED_PURPOSES = {
    purpose.value.casefold(): purpose for purpose in ArchRepresentation.RepresentationPurpose
}


@dataclass(frozen=True)
class ViewActivationContext:
    """The persistent view and semantic BIM context activated together."""

    definition: object
    source: object
    request: object


class BIMViewService:
    """Create, capture and activate ``App::ViewDefinition`` objects.

    The service deliberately accepts its GUI view and representation applier as
    dependencies.  This keeps document traversal and view semantics testable
    without constructing the Views Manager dock.
    """

    CONTEXT_SOURCE_PROPERTY = "BIMContextSource"

    def __init__(self, document, view=None, representation_applier=None):
        self.document = document
        self.view = view
        self._representation_applier = representation_applier
        self.active_storey = None
        self.active_view = None

    @staticmethod
    def is_view_definition(obj):
        return bool(obj and obj.isDerivedFrom("App::ViewDefinition"))

    @staticmethod
    def normalize_purpose(purpose):
        if isinstance(purpose, ArchRepresentation.RepresentationPurpose):
            return purpose
        key = str(purpose or "Model").strip().casefold()
        try:
            return _SUPPORTED_PURPOSES[key]
        except KeyError as exc:
            raise ValueError("Unsupported BIM view purpose: {}".format(purpose)) from exc

    def create_view(self, label, purpose="Model", source=None, capture=True):
        purpose = self.normalize_purpose(purpose)
        definition = self.document.addObject("App::ViewDefinition", "BIMView")
        definition.Label = label
        definition.Purpose = purpose.value
        definition.addProperty(
            "App::PropertyLink",
            self.CONTEXT_SOURCE_PROPERTY,
            "BIM",
            "Project or storey context used by this saved view",
        )
        definition.BIMContextSource = source
        if source is not None and hasattr(source, "Placement"):
            definition.ReferenceFrame = source.Placement
        if capture:
            self.capture(definition)
        return definition

    def duplicate_view(self, definition, label=None):
        if not self.is_view_definition(definition):
            raise TypeError("definition must be an App::ViewDefinition")
        duplicate = self.create_view(
            label or "{} Copy".format(definition.Label),
            definition.Purpose,
            self.context_source(definition),
            capture=False,
        )
        for name in (
            "CameraCodec",
            "CameraVersion",
            "CameraPayload",
            "ReferenceFrame",
            "ForcedVisible",
            "ForcedHidden",
            "ClippingPlanes",
        ):
            setattr(duplicate, name, getattr(definition, name))
        return duplicate

    def capture(self, definition):
        if not self.is_view_definition(definition):
            raise TypeError("definition must be an App::ViewDefinition")
        view = self._view()
        if view is None or not hasattr(view, "captureViewDefinition"):
            raise RuntimeError("An active 3D view is required to capture a BIM view")
        return bool(view.captureViewDefinition(definition))

    def context_source(self, definition):
        return getattr(definition, self.CONTEXT_SOURCE_PROPERTY, None)

    def request_for(self, definition):
        if not self.is_view_definition(definition):
            raise TypeError("definition must be an App::ViewDefinition")
        purpose = self.normalize_purpose(definition.Purpose)
        source = self.context_source(definition)
        if purpose == ArchRepresentation.RepresentationPurpose.PLAN:
            from bimplan.representation_request import representation_request_from_storey

            request = representation_request_from_storey(source)
            request.reference_frame = definition.ReferenceFrame
            return request
        return ArchRepresentation.RepresentationRequest(
            purpose=purpose,
            reference_frame=definition.ReferenceFrame,
            source=source,
        )

    def context_for(self, definition):
        return ViewActivationContext(
            definition,
            self.context_source(definition),
            self.request_for(definition),
        )

    def activate_storey(self, storey):
        self.active_storey = storey

    def activate_view(self, definition):
        context = self.context_for(definition)
        if self._representation_applier is not None:
            self._representation_applier(context.request)
        view = self._view()
        if view is None or not hasattr(view, "applyViewDefinition"):
            raise RuntimeError("An active 3D view is required to activate a BIM view")
        applied = bool(view.applyViewDefinition(definition))
        if applied:
            self.active_view = definition
            if context.source is not None:
                self.active_storey = context.source
        return applied

    def _view(self):
        if self.view is not None:
            return self.view
        try:
            import FreeCADGui

            return FreeCADGui.ActiveDocument.ActiveView
        except (AttributeError, RuntimeError):
            return None

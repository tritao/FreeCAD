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
    ACTIVE_PROPERTY = "BIMIsActiveView"
    SHEET_VIEW_PROPERTY = "BIMViewDefinition"

    def __init__(self, document, view=None, representation_applier=None):
        self.document = document
        self.view = view
        self._representation_applier = representation_applier
        self.active_storey = None
        self.active_view = self._persisted_active_view()

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
        self._ensure_bim_properties(definition)
        definition.BIMContextSource = source
        if source is not None and hasattr(source, "Placement"):
            definition.ReferenceFrame = source.Placement
        if capture:
            self.capture(definition)
        return definition

    def create_plan_view(self, label, source=None):
        """Create and open an orthographic PLAN view for a project context."""

        definition = self.create_view(label, "Plan", source, capture=False)
        request = self.request_for(definition)
        if self._representation_applier is not None:
            self._representation_applier(request)
        self._orient_plan_view(request)
        self.capture(definition)
        self._mark_active(definition)
        return definition

    def create_model_view(self, label="Default 3D", source=None):
        definition = self.create_view(label, "Model", source, capture=True)
        self._mark_active(definition)
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

    def delete_view(self, definition):
        if not self.is_view_definition(definition):
            raise TypeError("definition must be an App::ViewDefinition")
        if self.active_view is definition:
            self.active_view = None
        self.document.removeObject(definition.Name)

    def can_place_on_sheet(self, definition):
        if not self.is_view_definition(definition):
            return False
        try:
            purpose = self.normalize_purpose(definition.Purpose)
        except ValueError:
            return False
        return (
            purpose == ArchRepresentation.RepresentationPurpose.PLAN
            and self.context_source(definition) is not None
        )

    def place_on_sheet(self, definition, page):
        """Create a linked TechDraw BIM view for a sourced PLAN definition."""

        if not self.can_place_on_sheet(definition):
            raise ValueError("Only PLAN views with a project context can be placed on a sheet")
        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            raise TypeError("page must be a TechDraw::DrawPage")
        drawing_view = self.document.addObject("TechDraw::DrawViewArch", "BIMSavedView")
        drawing_view.Label = definition.Label
        drawing_view.Source = self.context_source(definition)
        drawing_view.addProperty(
            "App::PropertyLink",
            self.SHEET_VIEW_PROPERTY,
            "BIM",
            "Saved BIM view represented by this drawing view",
        )
        drawing_view.BIMViewDefinition = definition
        page.addView(drawing_view)
        if getattr(page, "Scale", 0.0):
            drawing_view.Scale = page.Scale
        return drawing_view

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
            self._mark_active(definition)
            if context.source is not None:
                self.active_storey = context.source
        return applied

    def restore_active_view(self):
        definition = self._persisted_active_view()
        if definition is None:
            return False
        return self.activate_view(definition)

    def _ensure_bim_properties(self, definition):
        properties = getattr(definition, "PropertiesList", ())
        if self.CONTEXT_SOURCE_PROPERTY not in properties:
            definition.addProperty(
                "App::PropertyLink",
                self.CONTEXT_SOURCE_PROPERTY,
                "BIM",
                "Project or storey context used by this saved view",
            )
        if self.ACTIVE_PROPERTY not in properties:
            definition.addProperty(
                "App::PropertyBool",
                self.ACTIVE_PROPERTY,
                "BIM",
                "Whether this is the active saved BIM view",
            )

    def _persisted_active_view(self):
        for obj in getattr(self.document, "Objects", ()):
            if self.is_view_definition(obj) and bool(getattr(obj, self.ACTIVE_PROPERTY, False)):
                return obj
        return None

    def _mark_active(self, definition):
        for obj in getattr(self.document, "Objects", ()):
            if not self.is_view_definition(obj):
                continue
            self._ensure_bim_properties(obj)
            obj.BIMIsActiveView = obj is definition
        self.active_view = definition

    def _orient_plan_view(self, request):
        view = self._view()
        if view is None:
            raise RuntimeError("An active 3D view is required to create a floor plan")
        frame = getattr(request, "reference_frame", None)
        if frame is None:
            source = getattr(request, "source", None)
            frame = getattr(source, "Placement", None)
        try:
            view.setCameraType("Orthographic")
        except (AttributeError, RuntimeError):
            pass
        if frame is None:
            try:
                view.viewTop()
            except (AttributeError, RuntimeError):
                pass
        else:
            try:
                import FreeCAD

                vx = frame.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
                vy = frame.Rotation.multVec(FreeCAD.Vector(0, 1, 0))
                vz = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
                view.setCameraOrientation(FreeCAD.Rotation(vx, vy, vz, "ZXY").Q)
            except (AttributeError, RuntimeError):
                pass
        try:
            view.fitAll()
        except (AttributeError, RuntimeError):
            pass

    def _view(self):
        if self.view is not None:
            return self.view
        try:
            import FreeCADGui

            return FreeCADGui.ActiveDocument.ActiveView
        except (AttributeError, RuntimeError):
            return None

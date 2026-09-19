# SPDX-License-Identifier: LGPL-2.1-or-later

"""Saved-view lifecycle and activation for the BIM Navigator."""

from contextlib import contextmanager
from dataclasses import dataclass, replace

import ArchRepresentation
import FreeCAD

from .framing import frame_planar_view, planar_view_bounds
from .grid_settings import get_grid_settings


_SUPPORTED_PURPOSES = {
    purpose.value.casefold(): purpose for purpose in ArchRepresentation.RepresentationPurpose
}

_PLANAR_PURPOSES = frozenset(
    (
        ArchRepresentation.RepresentationPurpose.PLAN,
        ArchRepresentation.RepresentationPurpose.SECTION,
        ArchRepresentation.RepresentationPurpose.ELEVATION,
    )
)
_PLAN_SNAP_MODES = frozenset(
    (
        "Lock",
        "Near",
        "Extension",
        "Grid",
        "Endpoint",
        "Midpoint",
        "Perpendicular",
        "Ortho",
        "Intersection",
        "WorkingPlane",
    )
)
_SECTION_SNAP_MODES = frozenset(
    ("Lock", "Near", "Endpoint", "Midpoint", "Intersection", "Ortho", "Grid")
)

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
    without constructing the BIM Navigator dock.
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

    def create_view(self, label, purpose="Model", source=None, capture=True, view=None):
        purpose = self.normalize_purpose(purpose)
        definition = self.document.addObject("App::ViewDefinition", "BIMView")
        definition.Label = label
        definition.Purpose = purpose.value
        self._ensure_bim_properties(definition)
        definition.BIMContextSource = source
        if source is not None and hasattr(source, "Placement"):
            definition.ReferenceFrame = source.Placement
        if capture:
            self.capture(definition, view=view)
        return definition

    def create_plan_view(self, label, source=None, view=None):
        """Create and open an orthographic PLAN view for a project context."""

        definition = self.create_view(label, "Plan", source, capture=False, view=view)
        request = self.request_for(definition)
        target_view = self._view(view)
        if target_view is None:
            raise RuntimeError("An active 3D view is required to create a floor plan")
        with self._instant_view_transition(target_view):
            if self._representation_applier is not None:
                self._representation_applier(request)
            self._orient_plan_view(request, definition=definition, view=target_view)
            self.capture(definition, view=target_view)
        # Native capture persists the viewport context's previous reference
        # frame along with the camera.  The newly created planar view owns the
        # request frame, so establish it after capture.
        definition.ReferenceFrame = request.reference_frame
        self._mark_active(definition)
        self.configure_snap_context(definition, view=view)
        return definition

    def create_model_view(self, label="Default 3D", source=None, view=None):
        definition = self.create_view(label, "Model", source, capture=True, view=view)
        self._mark_active(definition)
        self.configure_snap_context(definition, view=view)
        return definition

    def create_section_view(self, label, plane, view=None):
        """Create and open a saved orthographic view for a section plane."""

        target_view = self._view(view)
        if target_view is None:
            raise RuntimeError("An active 3D view is required to create a section")
        request_provider = getattr(
            getattr(plane, "Proxy", None), "getRepresentationRequest", None
        )
        if not callable(request_provider):
            raise TypeError("Section views require an Arch section plane")
        request = request_provider(plane)
        if request.purpose != ArchRepresentation.RepresentationPurpose.SECTION:
            raise ValueError("Section views require a section-purpose plane")
        definition = self.create_view(
            label, "Section", plane, capture=False, view=target_view
        )
        definition.ReferenceFrame = request.reference_frame
        with self._instant_view_transition(target_view):
            if self._representation_applier is not None:
                self._representation_applier(request)
            self._orient_plan_view(request, definition=definition, view=target_view)
            self.capture(definition, view=target_view)
        definition.ReferenceFrame = request.reference_frame
        self._mark_active(definition)
        self.configure_snap_context(definition, view=target_view)
        return definition

    def create_section_view_from_line(
        self,
        label,
        source,
        start,
        end,
        side,
        *,
        reference_frame=None,
        view=None,
    ):
        """Create a section plane and saved view from a line drawn in a plan."""

        import Arch

        objects = self._shape_objects_in_scope(source)
        if not objects:
            raise ValueError("A section source must contain shape objects")
        frame = reference_frame or getattr(source, "Placement", FreeCAD.Placement())
        vertical = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        line = FreeCAD.Vector(end).sub(FreeCAD.Vector(start))
        line = line.sub(vertical * line.dot(vertical))
        if line.Length <= 1e-7:
            raise ValueError("A section line requires two distinct plan points")
        line_length = line.Length
        horizontal = line.normalize()
        normal = horizontal.cross(vertical)
        midpoint = (FreeCAD.Vector(start) + FreeCAD.Vector(end)) * 0.5
        side_vector = FreeCAD.Vector(side).sub(midpoint)
        side_vector = side_vector.sub(vertical * side_vector.dot(vertical))
        if side_vector.Length <= 1e-7:
            raise ValueError("The viewing side must not lie on the section line")
        if side_vector.dot(normal) < 0.0:
            horizontal = -horizontal
            normal = -normal
        rotation = FreeCAD.Rotation(horizontal, vertical, normal, "ZXY")
        initial_frame = FreeCAD.Placement(FreeCAD.Vector(), rotation)
        bounds = planar_view_bounds(objects, frame=initial_frame)
        if bounds is None:
            raise ValueError("The section source has no geometric bounds")
        local_midpoint = rotation.inverted().multVec(midpoint)
        local_origin = FreeCAD.Vector(
            local_midpoint.x,
            bounds.center.y,
            local_midpoint.z,
        )
        placement = FreeCAD.Placement(rotation.multVec(local_origin), rotation)
        local_bounds = planar_view_bounds(objects, frame=placement)
        margin = max(0.05 * max(bounds.width, bounds.height, bounds.depth), 1.0)
        depth = max((local_bounds.z_max if local_bounds else 0.0) + margin, margin)

        plane = Arch.makeSectionPlane(list(objects), name="Section")
        plane.Label = "{} Marker".format(label)
        plane.Purpose = "Section"
        plane.Placement = placement
        plane.Depth = depth
        if getattr(plane, "ViewObject", None) is not None:
            if hasattr(plane.ViewObject, "DisplayLength"):
                plane.ViewObject.DisplayLength = line_length
            if hasattr(plane.ViewObject, "DisplayHeight"):
                plane.ViewObject.DisplayHeight = bounds.height + 2.0 * margin
        return self.create_section_view(label, plane, view=view)

    def create_elevation_view(
        self,
        label,
        source=None,
        *,
        direction="South",
        plane=None,
        view=None,
    ):
        """Create an elevation marker and its saved orthographic view.

        ``source`` is normally a building or storey.  Passing an existing
        elevation ``plane`` preserves manual placement while still creating
        the saved-view contract around it.
        """

        target_view = self._view(view)
        if target_view is None:
            raise RuntimeError("An active 3D view is required to create an elevation")
        if plane is None:
            plane = self._create_elevation_plane(source, direction)
        request = plane.Proxy.getRepresentationRequest(plane)
        if request.purpose != ArchRepresentation.RepresentationPurpose.ELEVATION:
            raise ValueError("Elevation views require an elevation section plane")
        definition = self.create_view(
            label, "Elevation", plane, capture=False, view=target_view
        )
        definition.ReferenceFrame = request.reference_frame
        with self._instant_view_transition(target_view):
            if self._representation_applier is not None:
                self._representation_applier(request)
            self._orient_plan_view(request, definition=definition, view=target_view)
            self.capture(definition, view=target_view)
        definition.ReferenceFrame = request.reference_frame
        self._mark_active(definition)
        self.configure_snap_context(definition, view=target_view)
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
            "CameraType",
            "CameraPlacement",
            "CameraFocalDistance",
            "CameraHeightAngle",
            "CameraHeight",
            "CameraAspectRatio",
            "CameraNearDistance",
            "CameraFarDistance",
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
        return purpose in (
            ArchRepresentation.RepresentationPurpose.PLAN,
            ArchRepresentation.RepresentationPurpose.SECTION,
            ArchRepresentation.RepresentationPurpose.ELEVATION,
        ) and self.context_source(definition) is not None

    def placements_for(self, definition, page=None):
        """Return TechDraw placements linked to a saved view."""

        if not self.is_view_definition(definition):
            return ()
        return tuple(
            obj
            for obj in self.document.Objects
            if obj.isDerivedFrom("TechDraw::DrawViewArch")
            and getattr(obj, self.SHEET_VIEW_PROPERTY, None) is definition
            and (page is None or obj in getattr(page, "Views", ()))
        )

    def place_on_sheet(
        self, definition, page, position=None, *, allow_duplicate=False
    ):
        """Create a linked TechDraw BIM view for a sourced planar definition."""

        if not self.can_place_on_sheet(definition):
            raise ValueError(
                "Only PLAN, SECTION or ELEVATION views with a context can be placed on a sheet"
            )
        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            raise TypeError("page must be a TechDraw::DrawPage")
        if self.placements_for(definition, page) and not allow_duplicate:
            raise ValueError("This BIM view is already placed on the selected sheet")
        from bimsheets.service import BIMSheetService

        sheet_service = BIMSheetService(self.document)
        sheet_service.ensure_metadata(page)
        first_placement = not any(
            view.isDerivedFrom("TechDraw::DrawViewArch") for view in page.Views
        )
        drawing_view = self.document.addObject("TechDraw::DrawViewArch", "BIMSavedView")
        drawing_view.Label = definition.Label
        drawing_view.Source = self.context_source(definition)
        drawing_view.BIMViewDefinition = definition
        page.addView(drawing_view)
        if getattr(page, "Scale", 0.0):
            drawing_view.Scale = page.Scale
        try:
            from bimsheets import BIMSheetViewTitleService

            title_service = BIMSheetViewTitleService(self.document)
            annotation = title_service.create(page, drawing_view)
            self.document.recompute()
            title_service.position_below_view(drawing_view)
            if position is None:
                suggestion = sheet_service.fit_view_layout(
                    page,
                    drawing_view,
                    preferred_scale=drawing_view.Scale,
                    allow_larger=first_placement,
                    centered=first_placement,
                )
                drawing_view.Scale = suggestion.scale
                drawing_view.X = suggestion.x
                drawing_view.Y = suggestion.y
            else:
                sheet_service.layout_view(page, drawing_view, position=position)
            title_service.position_below_view(drawing_view)
        except Exception:
            from bimsheets import BIMSheetViewTitleService

            annotation = BIMSheetViewTitleService.annotation_for(drawing_view)
            if annotation is not None:
                page.removeView(annotation)
                self.document.removeObject(annotation.Name)
            page.removeView(drawing_view)
            self.document.removeObject(drawing_view.Name)
            raise
        return drawing_view

    def create_sheet_from_view(self, definition, template_path, *, page_scale=None):
        """Create a dedicated sheet and place one saved planar view on it."""

        if not self.can_place_on_sheet(definition):
            raise ValueError(
                "Only PLAN, SECTION or ELEVATION views with a context can create a sheet"
            )
        from bimsheets.service import BIMSheetService

        sheet_service = BIMSheetService(self.document)
        page = sheet_service.create_sheet(template_path)
        metadata = replace(
            sheet_service.metadata_for(page),
            title=definition.Label,
        )
        sheet_service.apply_metadata(page, metadata)
        if page_scale is not None and float(page_scale) > 0.0:
            page.Scale = float(page_scale)
        drawing_view = self.place_on_sheet(definition, page)
        return page, drawing_view

    def remove_sheet_placement(self, drawing_view):
        """Remove one placement without deleting its saved BIM view."""

        if drawing_view is None or not drawing_view.isDerivedFrom(
            "TechDraw::DrawViewArch"
        ):
            raise TypeError("drawing_view must be a TechDraw::DrawViewArch")
        if getattr(drawing_view, self.SHEET_VIEW_PROPERTY, None) is None:
            raise ValueError("drawing_view is not a saved BIM view placement")
        page = drawing_view.findParentPage()
        from bimsheets import BIMSheetViewTitleService

        BIMSheetViewTitleService(self.document).remove(drawing_view)
        if page is not None:
            page.removeView(drawing_view)
        self.document.removeObject(drawing_view.Name)

    def capture(self, definition, view=None):
        if not self.is_view_definition(definition):
            raise TypeError("definition must be an App::ViewDefinition")
        target_view = self._view(view)
        if target_view is None or not hasattr(target_view, "captureViewDefinition"):
            raise RuntimeError("An active 3D view is required to capture a BIM view")
        return bool(target_view.captureViewDefinition(definition))

    def context_source(self, definition):
        return getattr(definition, self.CONTEXT_SOURCE_PROPERTY, None)

    def request_for(self, definition):
        from .representation import request_for_view_definition

        return request_for_view_definition(definition)

    def _create_elevation_plane(self, source, direction):
        import Arch
        objects = self._shape_objects_in_scope(source)
        if not objects:
            raise ValueError("An elevation source must contain shape objects")
        rotation = self._elevation_rotation(direction)
        initial_frame = FreeCAD.Placement(FreeCAD.Vector(), rotation)
        bounds = planar_view_bounds(objects, frame=initial_frame)
        if bounds is None:
            raise ValueError("The elevation source has no geometric bounds")
        margin = max(0.05 * max(bounds.width, bounds.height, bounds.depth), 1.0)
        local_origin = FreeCAD.Vector(
            bounds.center.x,
            bounds.center.y,
            bounds.z_max + margin,
        )
        plane = Arch.makeSectionPlane(list(objects), name="Elevation")
        plane.Label = "{} Elevation Marker".format(str(direction).title())
        plane.Purpose = "Elevation"
        plane.Placement = FreeCAD.Placement(rotation.multVec(local_origin), rotation)
        plane.Depth = bounds.depth + 2.0 * margin
        if getattr(plane, "ViewObject", None) is not None:
            if hasattr(plane.ViewObject, "DisplayLength"):
                plane.ViewObject.DisplayLength = bounds.width + 2.0 * margin
            if hasattr(plane.ViewObject, "DisplayHeight"):
                plane.ViewObject.DisplayHeight = bounds.height + 2.0 * margin
        return plane

    @staticmethod
    def _shape_objects_in_scope(source):
        pending = list(getattr(source, "Group", ()) or ()) if source else []
        objects = []
        seen = set()
        while pending:
            obj = pending.pop(0)
            if obj in seen:
                continue
            seen.add(obj)
            pending.extend(getattr(obj, "Group", ()) or ())
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                objects.append(obj)
        return tuple(objects)

    @staticmethod
    def _elevation_rotation(direction):
        key = str(direction or "South").strip().casefold()
        normals = {
            "south": FreeCAD.Vector(0, -1, 0),
            "north": FreeCAD.Vector(0, 1, 0),
            "west": FreeCAD.Vector(-1, 0, 0),
            "east": FreeCAD.Vector(1, 0, 0),
        }
        try:
            normal = normals[key]
        except KeyError as exc:
            raise ValueError("Unsupported elevation direction: {}".format(direction)) from exc
        vertical = FreeCAD.Vector(0, 0, 1)
        horizontal = vertical.cross(normal)
        return FreeCAD.Rotation(horizontal, vertical, normal, "ZXY")

    def context_for(self, definition):
        return ViewActivationContext(
            definition,
            self.context_source(definition),
            self.request_for(definition),
        )

    def scope_for(self, definition=None):
        """Return the object scope for a saved view or the active saved view."""

        from .navigator_model import BIMNavigatorModel

        return BIMNavigatorModel(self.document).current_view_scope(
            definition or self.active_view
        )

    def activate_storey(self, storey):
        self.active_storey = storey

    def activate_view(self, definition, view=None):
        context = self.context_for(definition)
        target_view = self._view(view)
        if target_view is None or not hasattr(target_view, "applyViewDefinition"):
            raise RuntimeError("An active 3D view is required to activate a BIM view")
        # Saved-view activation is a state change, not a camera-navigation
        # gesture.  The representation bridge may orient the camera before
        # the persisted camera is applied; keep both operations synchronous so
        # switching PLAN/MODEL never waits for a navigation animation.
        with self._instant_view_transition(target_view):
            if self._representation_applier is not None:
                self._representation_applier(context.request)
            applied = bool(target_view.applyViewDefinition(definition))
        if applied:
            self.configure_snap_context(definition, view=target_view)
            self._mark_active(definition)
            if context.source is not None:
                self.active_storey = context.source
        return applied

    @staticmethod
    @contextmanager
    def _instant_view_transition(view):
        """Temporarily suppress navigation animation for a view switch.

        ``View3DInventor.setCameraOrientation`` animates whenever navigation
        animation is enabled, even for programmatic orientation changes with
        ``moveToCenter=False``.  BIM saved-view activation must apply a stored
        camera immediately while preserving the user's normal navigation
        preference after the operation.
        """

        stop = getattr(view, "stopAnimating", None)
        if callable(stop):
            try:
                stop()
            except (AttributeError, ReferenceError, RuntimeError):
                pass

        get_enabled = getattr(view, "isAnimationEnabled", None)
        set_enabled = getattr(view, "setAnimationEnabled", None)
        previous = None
        if callable(get_enabled):
            try:
                previous = bool(get_enabled())
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                previous = None
        if callable(set_enabled):
            try:
                set_enabled(False)
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                pass

        try:
            yield
        finally:
            if previous is not None and callable(set_enabled):
                try:
                    set_enabled(previous)
                except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                    pass

    def configure_snap_context(self, definition=None, view=None, semantic_providers=None):
        """Apply one saved view's snapping inputs to its originating viewport.

        MODEL views inherit the user's Draft snap modes and working plane.  A
        PLAN, SECTION or ELEVATION view gets a local planar working plane and
        a reference-frame grid.  Semantic providers are optional because live
        editing sessions own their provider lifecycle; callers with a saved
        representation query can supply them explicitly.
        """

        definition = definition or self.active_view
        if definition is None:
            return None
        target_view = self._view(view)
        if target_view is None:
            return None
        try:
            import FreeCADGui

            snapper = getattr(FreeCADGui, "Snapper", None)
            configure = getattr(snapper, "configure_view", None)
        except (ImportError, AttributeError, RuntimeError):
            return None
        if not callable(configure):
            return None

        request = self.request_for(definition)
        purpose = self.normalize_purpose(definition.Purpose)
        plane = self._snap_plane_for(request) if purpose in _PLANAR_PURPOSES else None
        grid = self._snap_grid_for(plane) if plane is not None else None
        if purpose == ArchRepresentation.RepresentationPurpose.PLAN:
            modes = _PLAN_SNAP_MODES
        elif purpose in (
            ArchRepresentation.RepresentationPurpose.SECTION,
            ArchRepresentation.RepresentationPurpose.ELEVATION,
        ):
            modes = _SECTION_SNAP_MODES
        else:
            modes = None
        kwargs = {
            "modes": modes,
            "interaction_plane": plane,
            "grid_provider": grid,
        }
        if semantic_providers is not None:
            kwargs["semantic_providers"] = semantic_providers
        try:
            return configure(target_view, **kwargs)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            return None

    def clear_snap_context(self, view=None):
        """Release the Snapper context associated with a closed viewport."""

        target_view = self._view(view)
        if target_view is None:
            return None
        try:
            import FreeCADGui

            snapper = getattr(FreeCADGui, "Snapper", None)
            remove = getattr(snapper, "remove_context", None)
        except (ImportError, AttributeError, RuntimeError):
            return None
        if not callable(remove):
            return None
        try:
            return remove(target_view)
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            return None

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

    def _orient_plan_view(self, request, definition=None, view=None):
        target_view = self._view(view)
        if target_view is None:
            raise RuntimeError("An active 3D view is required to create a floor plan")
        frame = getattr(request, "reference_frame", None)
        if frame is None:
            source = getattr(request, "source", None)
            frame = getattr(source, "Placement", None)
        try:
            target_view.setCameraType("Orthographic")
        except (AttributeError, RuntimeError):
            pass
        if frame is None:
            try:
                target_view.viewTop()
            except (AttributeError, RuntimeError):
                pass
        else:
            try:
                import FreeCAD

                vx = frame.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
                vy = frame.Rotation.multVec(FreeCAD.Vector(0, 1, 0))
                vz = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
                target_view.setCameraOrientation(FreeCAD.Rotation(vx, vy, vz, "ZXY").Q)
            except (AttributeError, RuntimeError):
                pass
        scope = self.scope_for(definition) if definition is not None else None
        bounds = planar_view_bounds(
            getattr(scope, "visible_objects", ()), frame=frame
        )
        if bounds is not None and frame_planar_view(target_view, bounds, frame):
            return
        # Empty contexts and lightweight/legacy views may have no semantic
        # shape bounds or writable camera.  Preserve scene fitting only as a
        # compatibility fallback for those cases.
        try:
            target_view.fitAll()
        except (AttributeError, RuntimeError):
            pass

    def _snap_plane_for(self, request):
        frame = getattr(request, "reference_frame", None)
        if frame is None:
            return None
        try:
            import WorkingPlane

            plane = WorkingPlane.PlaneBase()
            plane.align_to_placement(frame)
            return plane
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
            return None

    @staticmethod
    def _snap_grid_for(plane):
        if plane is None:
            return None
        try:
            from draftutils.grid import GridLattice

            settings = get_grid_settings()
            return GridLattice(
                plane.position,
                plane.u,
                plane.v,
                spacing=settings.spacing,
                major_every=settings.major_every,
            )
        except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
            return None

    def _view(self, view=None):
        if view is not None:
            return view
        if self.view is not None:
            return self.view
        try:
            import FreeCADGui

            return FreeCADGui.ActiveDocument.ActiveView
        except (AttributeError, RuntimeError):
            return None

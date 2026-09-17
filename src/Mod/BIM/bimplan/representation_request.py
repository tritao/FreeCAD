# SPDX-License-Identifier: LGPL-2.1-or-later

"""Architectural representation-request providers for BIM Plan Edit."""

import ArchComponent
import ArchRepresentation
import FreeCAD

def _quantity_value(value, default=0.0):
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)


def _proxy_representation_request(source):
    try:
        proxy = getattr(source, "Proxy", None)
        provider = getattr(proxy, "getRepresentationRequest", None)
    except (AttributeError, ReferenceError, RuntimeError):
        return None
    if not callable(provider):
        return None
    try:
        return provider(source)
    except Exception:
        return None


def _is_storey(source):
    if source is None:
        return False
    try:
        import Draft

        if Draft.getType(source) == "Floor":
            return True
    except Exception:
        pass
    return getattr(source, "IfcType", "") == "Building Storey"


def representation_request_from_storey(storey):
    elevation = 0.0
    cut_height = ArchComponent.DEFAULT_PLAN_CUT_HEIGHT
    if storey is not None:
        elevation = float(storey.Placement.Base.z) + _quantity_value(
            getattr(storey, "LevelOffset", 0.0)
        )
        configured_height = _quantity_value(getattr(storey, "PlanCutHeight", 0.0))
        if configured_height > 0.0:
            cut_height = configured_height
    return ArchRepresentation.RepresentationRequest(
        purpose=ArchRepresentation.RepresentationPurpose.PLAN,
        cut_offset=elevation + cut_height,
        target_offset=elevation,
        source=storey,
    )


def representation_request_from_source(source):
    provided = _proxy_representation_request(source)
    if provided is not None:
        return provided
    if _is_storey(source) or source is None:
        return representation_request_from_storey(source)
    return None


class PlanRepresentationRequestAPI:
    """Resolve and activate one BIM representation request for the session."""

    def __init__(self, session):
        self._session = session
        self.source = None
        self.request = representation_request_from_storey(None)

    def find_initial_source(self):
        try:
            import FreeCADGui

            selection = FreeCADGui.Selection.getSelection()
        except Exception:
            selection = ()
        for obj in selection:
            if representation_request_from_source(obj) is not None and not _is_storey(obj):
                return obj
        return self._session.active_storey

    def set_source(self, source, *, refresh=True, fit=False):
        request = representation_request_from_source(source)
        if request is None:
            raise ValueError("Object does not provide a BIM representation request")
        self.source = source
        self.request = request
        view_rulers = getattr(self._session, "view_rulers", None)
        if view_rulers is not None:
            view_rulers.set_request(request)
        view_grid = getattr(self._session, "view_grid", None)
        if view_grid is not None:
            view_grid.set_request(request)
        view_runtime = getattr(self._session, "view_runtime", None)
        if view_runtime is not None:
            view_runtime.set_request(request)
        if _is_storey(source):
            self._session.active_storey = source
        if not refresh:
            return request
        self._session.overlays.geometry.invalidate_plan_overlay_geometry_cache()
        self._session.viewport.apply_representation_request(request, fit=fit)
        self._session.visibility.apply_storey_visibility()
        self._session.contextual_rendering.refresh_all()
        return request

    def includes_object(self, obj):
        source_objects = getattr(self.source, "Objects", None)
        if source_objects:
            return obj in source_objects
        if _is_storey(self.source):
            return self._session.visibility.object_belongs_to_active_storey(obj)
        return True

    @property
    def purpose(self):
        return self.request.purpose

    def is_plan(self):
        return self.purpose == ArchRepresentation.RepresentationPurpose.PLAN

    def to_local(self, point):
        frame = getattr(self.request, "reference_frame", None)
        if frame is None:
            return FreeCAD.Vector(point)
        return frame.inverse().multVec(FreeCAD.Vector(point))

    def to_global(self, point):
        frame = getattr(self.request, "reference_frame", None)
        if frame is None:
            return FreeCAD.Vector(point)
        return frame.multVec(FreeCAD.Vector(point))

    def project_to_plane(self, point, offset=None):
        local = self.to_local(point)
        if offset is None:
            offset = getattr(self.request, "target_offset", None)
        local.z = float(offset or 0.0)
        return self.to_global(local)

    def refresh(self):
        if self.source is not None:
            updated = representation_request_from_source(self.source)
            if updated is not None:
                self.request = updated
        return self.request

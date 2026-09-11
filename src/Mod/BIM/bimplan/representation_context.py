# SPDX-License-Identifier: LGPL-2.1-or-later

"""Architectural representation-context providers for BIM Plan Edit."""

import ArchComponent
import ArchRepresentation


def _quantity_value(value, default=0.0):
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)


def _proxy_context(source):
    try:
        proxy = getattr(source, "Proxy", None)
        provider = getattr(proxy, "getRepresentationContext", None)
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


def context_from_storey(storey):
    elevation = 0.0
    cut_height = ArchComponent.DEFAULT_PLAN_CUT_HEIGHT
    if storey is not None:
        elevation = float(storey.Placement.Base.z) + _quantity_value(
            getattr(storey, "LevelOffset", 0.0)
        )
        configured_height = _quantity_value(getattr(storey, "PlanCutHeight", 0.0))
        if configured_height > 0.0:
            cut_height = configured_height
    return ArchRepresentation.RepresentationContext(
        purpose=ArchRepresentation.RepresentationPurpose.PLAN,
        cut_offset=elevation + cut_height,
        target_offset=elevation,
        source=storey,
    )


def context_from_source(source):
    provided = _proxy_context(source)
    if provided is not None:
        return provided
    if _is_storey(source) or source is None:
        return context_from_storey(source)
    return None


class PlanRepresentationContextAPI:
    """Resolve and activate one BIM representation context for the session."""

    def __init__(self, session):
        self._session = session
        self.source = None
        self.context = context_from_storey(None)

    def find_initial_source(self):
        try:
            import FreeCADGui

            selection = FreeCADGui.Selection.getSelection()
        except Exception:
            selection = ()
        for obj in selection:
            if context_from_source(obj) is not None and not _is_storey(obj):
                return obj
        return self._session.active_storey

    def set_source(self, source, *, refresh=True, fit=False):
        context = context_from_source(source)
        if context is None:
            raise ValueError("Object does not provide a BIM representation context")
        self.source = source
        self.context = context
        if _is_storey(source):
            self._session.active_storey = source
        if not refresh:
            return context
        self._session.overlays.geometry.invalidate_plan_overlay_geometry_cache()
        self._session.viewport.apply_representation_context(context, fit=fit)
        self._session.visibility.apply_storey_visibility()
        self._session.contextual_rendering.refresh_all()
        return context

    def includes_object(self, obj):
        source_objects = getattr(self.source, "Objects", None)
        if source_objects:
            return obj in source_objects
        if _is_storey(self.source):
            return self._session.visibility.object_belongs_to_active_storey(obj)
        return True

    def refresh(self):
        if self.source is not None:
            updated = context_from_source(self.source)
            if updated is not None:
                self.context = updated
        return self.context

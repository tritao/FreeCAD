# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local committed BIM representations used by Plan Edit."""

import BimContextualRendering


class PlanContextualRenderingAPI:
    """Own the committed wall and opening representation for one Plan Edit view."""

    def __init__(self, session):
        self._session = session
        self._renderer = None
        self._sources = set()

    @property
    def renderer(self):
        return self._renderer

    def start(self):
        if self._renderer is None:
            self._renderer = BimContextualRendering.ContextualRepresentationRenderer(
                self._session.view
            )
        self.refresh_all()

    def close(self):
        renderer = self._renderer
        self._renderer = None
        self._sources.clear()
        if renderer is not None:
            renderer.close()

    def mapping_for_node(self, node):
        if self._renderer is None:
            return None
        return self._renderer.mapping_for_node(node)

    def refresh_all(self):
        if self._renderer is None:
            return
        current = set()
        for obj in getattr(self._session.doc, "Objects", ()) or ():
            if not self._is_in_active_context(obj):
                continue
            representation = self._representation_for(obj)
            if representation is None:
                continue
            source = representation.source
            self._renderer.set_representation(representation)
            current.add(source)
        for source in self._sources - current:
            self._renderer.remove_representation(source)
        self._sources = current
        self._session.viewport.request_view_redraw()

    def refresh_object(self, obj):
        if self._renderer is None or obj is None:
            return
        semantic_obj = self._session.visibility.get_plan_semantic_object(obj)
        affected = {semantic_obj} if semantic_obj is not None else set()
        if self._session.selection.targets.is_plan_selectable_wall(semantic_obj):
            affected.update(self._session.openings.get_wall_hosted_openings(semantic_obj))
        for opening in self._session.openings.get_plan_opening_instances():
            if self._session.openings.is_opening_visual_dependency(opening, obj):
                affected.add(opening)
        for source in affected:
            self._refresh_source(source)
        self._session.viewport.request_view_redraw()

    def remove_object(self, obj):
        if self._renderer is None or obj is None:
            return
        semantic_obj = self._session.visibility.get_plan_semantic_object(obj)
        for source in (obj, semantic_obj):
            if source in self._sources:
                self._renderer.remove_representation(source)
                self._sources.discard(source)
        self._session.viewport.request_view_redraw()

    def _refresh_source(self, source):
        representation = None
        if self._is_in_active_context(source):
            representation = self._representation_for(source)
        if representation is None:
            if source in self._sources:
                self._renderer.remove_representation(source)
                self._sources.discard(source)
            return
        self._renderer.set_representation(representation)
        self._sources.add(representation.source)

    def _representation_for(self, obj):
        geometry = self._session.overlays.geometry
        if self._session.selection.targets.is_plan_selectable_wall(obj):
            return geometry.get_wall_representation(obj)
        if self._session.openings.is_hosted_opening_object(obj):
            return geometry.get_opening_representation(obj)
        return None

    def _is_in_active_context(self, obj):
        return self._session.representation_context.includes_object(obj)

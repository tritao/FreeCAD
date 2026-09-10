# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local committed BIM representations used by Plan Edit."""

import BimContextualRendering
import ArchWallRelation


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

    def edit_handles_for(self, source):
        if self._renderer is None:
            return ()
        return self._renderer.edit_handles_for(source)

    def preview_handle(self, handle, point):
        if self._renderer is None:
            return False
        changed = self._renderer.preview_handle(handle, point)
        if changed:
            self._session.viewport.request_view_redraw()
        return changed

    def set_handle_state(self, handle, state):
        if self._renderer is None:
            return False
        changed = self._renderer.set_handle_state(handle, state)
        if changed:
            self._session.viewport.request_view_redraw()
        return changed

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

    def refresh_edit_dependencies(self, obj):
        """Refresh the bounded semantic neighborhood affected by a BIM edit."""

        if self._renderer is None or obj is None:
            return
        session = self._session
        semantic_obj = session.visibility.get_plan_semantic_object(obj)
        walls = (
            {semantic_obj}
            if session.selection.targets.is_plan_selectable_wall(semantic_obj)
            else set()
        )
        for relation in ArchWallRelation.iter_wall_relations(semantic_obj):
            walls.update(
                wall for wall in ArchWallRelation.get_relation_walls(relation) if wall is not None
            )

        session.openings.invalidate_wall_hosted_openings_cache()
        for wall in walls:
            session.overlays.geometry.invalidate_plan_overlay_geometry_cache(wall)
            self.refresh_object(wall)
        space_visuals = tuple(session.spaces.refresh_document_dependent_visuals())
        session.selection.refresh.refresh_document_dependent_secondary_selection_visuals()
        visual_kinds = list(space_visuals)
        if session.selection.state.is_selected_plan_target("wall"):
            visual_kinds.extend(("selected_wall", "wall_grips"))
        if visual_kinds:
            session.overlays.runtime.queue_plan_overlay_visual_refresh(*visual_kinds)

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
        return self._session.overlays.geometry.get_contextual_representation(obj)

    def _is_in_active_context(self, obj):
        return self._session.representation_context.includes_object(obj)

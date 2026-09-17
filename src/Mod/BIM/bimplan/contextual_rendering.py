# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-local committed BIM representations used by Plan Edit."""

import ArchWallRelation
from bimviews import representation_layers


class PlanContextualRenderingAPI:
    """Own the committed wall and opening representation for one Plan Edit view."""

    def __init__(self, session):
        self._session = session
        self._renderer = None
        self._sources = set()
        self._generation = 0

    @property
    def renderer(self):
        return self._renderer

    def start(self):
        reused = self._renderer is not None
        if self._renderer is None:
            self._renderer, reused = representation_layers.acquire(
                self._session.view,
                self._session.representation_request.request,
                self._session.doc,
            )
            self._generation += 1
            if reused:
                self._sources = set(self._renderer.sources)
        if not reused:
            self.refresh_all()
        self._session.viewport.flush_scene_graph_mutations()
        self._session.snap.enable_semantic_snapping()

    def close(self, *, retain=False):
        self._session.snap.disable_semantic_snapping()
        renderer = self._renderer
        self._renderer = None
        self._sources.clear()
        self._generation += 1
        if renderer is not None:
            self._session.viewport.queue_scene_graph_mutation(
                ("contextual-renderer-close", id(renderer)),
                lambda: (
                    representation_layers.release(renderer)
                    if retain
                    else representation_layers.close_renderer(renderer)
                ),
                finalizer=True,
            )

    def _queue_renderer_mutation(self, key, callback):
        renderer = self._renderer
        generation = self._generation
        if renderer is None:
            return False

        def guarded_mutation():
            if self._renderer is not renderer or self._generation != generation:
                return False
            return callback(renderer)

        return self._session.viewport.queue_scene_graph_mutation(
            ("contextual-renderer", key), guarded_mutation
        )

    def mapping_for_node(self, node):
        if self._renderer is None:
            return None
        return self._renderer.mapping_for_node(node)

    def pick_mapping(self, mouse_pos, radius_px=4):
        if self._renderer is None:
            return None
        return self._renderer.pick_mapping(
            mouse_pos,
            self._session.view.getPointOnScreen,
            radius_px=radius_px,
        )

    def pick_edit_handle(self, mouse_pos, radius_px=8):
        if self._renderer is None:
            return None
        return self._renderer.pick_edit_handle(
            mouse_pos,
            self._session.view.getPointOnScreen,
            radius_px=radius_px,
        )

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
        return self._queue_renderer_mutation(
            ("handle-state", handle.source, handle.subelement),
            lambda renderer: renderer.set_handle_state(handle, state),
        )

    def set_preview_state(self, state, valid=True):
        renderer = self._renderer
        if renderer is None:
            return False
        source = state.primary_source
        return self._session.viewport.queue_scene_graph_mutation(
            ("contextual-preview-state", source),
            lambda: (
                renderer.set_preview_state(state, valid) if self._renderer is renderer else False
            ),
        )

    def clear_preview(self, source=None):
        renderer = self._renderer
        if renderer is None:
            return False
        return self._session.viewport.queue_scene_graph_mutation(
            ("contextual-preview", source),
            lambda: (renderer.clear_preview(source) if self._renderer is renderer else False),
        )

    def set_edit_label(self, source, text, point, valid=True):
        return self._queue_renderer_mutation(
            ("edit-label", source),
            lambda renderer: renderer.set_edit_label(source, text, point, valid),
        )

    def sync_visible_handles(self):
        """Keep semantic handles scoped to the primary Plan Edit selection."""

        if self._renderer is None:
            return False
        _kind, source = self._session.selection.state.get_selected_plan_target()
        if self._session.current_tool != "Select":
            source = None
        sources = (source,) if source else ()
        return self._queue_renderer_mutation(
            "visible-handle-sources",
            lambda renderer: renderer.set_visible_handle_sources(sources),
        )

    def set_source_visible(self, source, visible):
        return self._queue_renderer_mutation(
            ("source-visible", source),
            lambda renderer: renderer.set_source_visible(source, visible),
        )

    def refresh_all(self):
        if self._renderer is None:
            return
        self._session.performance.plan_perf_count("contextual_refresh_all")
        current = set()
        for obj in getattr(self._session.doc, "Objects", ()) or ():
            if not self._is_in_active_context(obj):
                continue
            with self._session.performance.plan_perf_trace_span(
                "contextual_representation_for_object"
            ):
                representation = self._representation_for(obj)
            if representation is None:
                continue
            self._session.performance.plan_perf_count("contextual_representations")
            source = representation.source
            self._queue_renderer_mutation(
                ("representation", source),
                lambda renderer, value=representation: renderer.set_representation(value),
            )
            current.add(source)
        for source in self._sources - current:
            self._queue_renderer_mutation(
                ("representation", source),
                lambda renderer, value=source: renderer.remove_representation(value),
            )
        self._sources = current
        self.sync_visible_handles()

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
            visual_kinds.append("selected_wall")
        if visual_kinds:
            session.overlays.queue_plan_overlay_visual_refresh(*visual_kinds)

    def remove_object(self, obj):
        if self._renderer is None or obj is None:
            return
        semantic_obj = self._session.visibility.get_plan_semantic_object(obj)
        for source in (obj, semantic_obj):
            if source in self._sources:
                self._queue_renderer_mutation(
                    ("representation", source),
                    lambda renderer, value=source: renderer.remove_representation(value),
                )
                self._sources.discard(source)

    def _refresh_source(self, source):
        representation = None
        if self._is_in_active_context(source):
            representation = self._representation_for(source)
        if representation is None:
            if source in self._sources:
                self._queue_renderer_mutation(
                    ("representation", source),
                    lambda renderer, value=source: renderer.remove_representation(value),
                )
                self._sources.discard(source)
            return
        self._queue_renderer_mutation(
            ("representation", source),
            lambda renderer: renderer.set_representation(representation),
        )
        self._sources.add(representation.source)

    def _representation_for(self, obj):
        return self._session.overlays.geometry.get_contextual_representation(obj)

    def _is_in_active_context(self, obj):
        return self._session.representation_request.includes_object(obj)

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays
from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds

_PLAN_VIEW_SCALE_REFRESH_DELAY_MS = 40


def _queue_plan_overlay_visual_refresh(session, *visuals):
    return overlay_manager.queue_plan_overlay_visual_refresh(
        session,
        visuals,
        plan_document_visuals.PLAN_VISUAL_ALL,
        plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE,
    )


def discard_runtime_references(session):
    session.overlays.walls.discard_runtime_references()
    session.overlays.spaces.discard_runtime_references()


def clear_begin_teardown_visuals(session):
    session.overlays.walls.clear_junction_node_overlays()
    session.overlays.walls.clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(session)
    session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_PROVIDER,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
    )
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.spaces.clear_secondary_selected_overlays()
    session.overlays.providers.clear_provider_overlays()
    session.overlays.providers.clear_provider_point_preview()
    session.overlays.spaces.clear_space_region_pick_overlays()
    session.overlays.openings.discard_opening_handle_tracker_pool()
    session.openings.clear_opening_move_preview()
    session.symbols.clear_symbol_edit_preview()
    session.spaces.clear_plan_region_preview()


def clear_shutdown_visuals(session):
    session.overlays.walls.clear_junction_node_overlays()
    session.overlays.walls.clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            plan_target_kinds.PLAN_TARGET_PROVIDER,
        ),
    )
    session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
    )
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.providers.clear_provider_overlays()
    session.overlays.providers.clear_provider_point_preview()
    session.overlays.openings.discard_opening_handle_tracker_pool()
    session.openings.clear_opening_move_preview()
    session.symbols.clear_symbol_edit_preview()


class PlanOverlaysAPI:
    """Owned session surface for BIM Plan Edit overlay behavior."""

    def __init__(self, session):
        self._session = session
        self.manager = overlay_manager.PlanOverlayManagerService(session)
        self.geometry = overlay_geometry.PlanOverlayGeometryService(session)
        self.spaces = space_overlays.PlanSpaceOverlayService(session)
        self.walls = wall_overlays.PlanWallOverlayService(session)
        self.providers = provider_overlays.PlanProviderOverlayService(session)
        self.openings = opening_overlays.PlanOpeningOverlayService(session)
        self.symbols = symbol_overlays.PlanSymbolOverlayService(session)

    @property
    def session(self):
        return self._session

    def queue_plan_overlay_visual_refresh(self, *visuals):
        return _queue_plan_overlay_visual_refresh(self.session, *visuals)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def clear_begin_teardown_visuals(self):
        return clear_begin_teardown_visuals(self.session)

    def clear_shutdown_visuals(self):
        return clear_shutdown_visuals(self.session)

    def queue_plan_overlay_view_scale_refresh(
        self,
        delay_ms=_PLAN_VIEW_SCALE_REFRESH_DELAY_MS,
    ):
        return overlay_manager.queue_plan_overlay_view_scale_refresh(
            self.session,
            plan_document_visuals.PLAN_VISUAL_VIEW_SCALE,
            delay_ms,
        )

    def consume_dirty_plan_visuals(self, default_all=True):
        return overlay_manager.consume_dirty_plan_visuals(
            self.session,
            plan_document_visuals.PLAN_VISUAL_ALL,
            default_all=default_all,
        )

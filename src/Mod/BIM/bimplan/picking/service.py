# SPDX-License-Identifier: LGPL-2.1-or-later

"""Session-owned Plan Edit picking API."""

from bimplan.selection import area_picking as plan_area_picking
from bimplan.selection import edit_node_picking as plan_edit_node_picking
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.selection import overlay_picking as plan_overlay_picking
from bimplan.selection import picking as plan_selection_picking
from bimplan.selection import picking_geometry as plan_picking_geometry
from bimplan.selection import provider_overlay_picking as plan_provider_overlay_picking


class PlanPickingAPI:
    """Owned picking surface for Plan Edit interaction code."""

    xy_polygon_area = staticmethod(plan_area_picking.xy_polygon_area)
    xy_point_in_polygon = staticmethod(plan_area_picking.xy_point_in_polygon)
    get_screen_distance_sq_to_projected_segment = staticmethod(
        plan_picking_geometry.get_screen_distance_sq_to_projected_segment
    )

    def __init__(self, session):
        self.session = session

    def pick(self, mouse_pos, *, mode="click", include_space_fallback=True):
        del mode
        return self.get_plan_target_at_position(
            mouse_pos,
            include_space_fallback=include_space_fallback,
        )

    def hover(self, mouse_pos, force=False):
        return plan_hover_picking.update_hovered_plan_target(
            self.session,
            mouse_pos,
            force=force,
        )

    def pick_edit_node(self, mouse_pos):
        return self.get_edit_node(mouse_pos)

    def get_plan_target_at_position(self, mouse_pos, *, include_space_fallback=True):
        return plan_selection_picking.get_plan_target_at_position(
            self.session,
            mouse_pos,
            include_space_fallback=include_space_fallback,
        )

    def get_edit_node(self, mouse_pos):
        return plan_edit_node_picking.get_edit_node(self.session, mouse_pos)

    def get_plan_target_from_edit_node(self, node):
        return plan_edit_node_picking.get_plan_target_from_edit_node(self.session, node)

    def get_provider_overlay_target_from_edit_node(self, node):
        return plan_provider_overlay_picking.get_provider_overlay_target_from_edit_node(
            self.session,
            node,
        )

    def get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        return plan_picking_geometry.get_screen_distance_sq_to_segment(
            self.session,
            mouse_pos,
            start,
            end,
        )

    def get_plan_space_instances(self):
        return plan_area_picking.get_plan_space_instances(self.session)

    def get_plan_region_instances(self):
        return plan_area_picking.get_plan_region_instances(self.session)

    def pick_plan_symbol_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_overlay_picking.pick_plan_symbol_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_plan_opening_target_from_overlays(
        self,
        mouse_pos,
        radius_px=10,
        candidates=None,
    ):
        return plan_overlay_picking.pick_plan_opening_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
            candidates=candidates,
        )

    def pick_provider_overlay_target_from_overlays(
        self,
        mouse_pos,
        radius_px=plan_provider_overlay_picking.PROVIDER_OVERLAY_PICK_RADIUS_PX,
    ):
        return plan_provider_overlay_picking.pick_provider_overlay_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_provider_overlay_target_from_objects_info(self, mouse_pos):
        return plan_provider_overlay_picking.pick_provider_overlay_target_from_objects_info(
            self.session,
            mouse_pos,
        )

    def pick_plan_space_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_area_picking.pick_plan_space_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_plan_region_target_from_overlays(self, mouse_pos, radius_px=10):
        return plan_area_picking.pick_plan_region_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def get_region_pick_polylines(self, region):
        return plan_area_picking.get_region_pick_polylines(self.session, region)

    def pick_plan_region_target_from_polylines(self, mouse_pos):
        return plan_area_picking.pick_plan_region_target_from_polylines(
            self.session,
            mouse_pos,
        )

    def pick_plan_target_from_footprint_faces(
        self,
        mouse_pos,
        is_target,
        get_faces,
        target_label="target",
    ):
        return plan_area_picking.pick_plan_target_from_footprint_faces(
            self.session,
            mouse_pos,
            is_target,
            get_faces,
            target_label=target_label,
        )

    def pick_plan_space_target_from_footprints(self, mouse_pos):
        return plan_area_picking.pick_plan_space_target_from_footprints(
            self.session,
            mouse_pos,
        )

    def pick_plan_region_target_from_footprints(self, mouse_pos):
        return plan_area_picking.pick_plan_region_target_from_footprints(
            self.session,
            mouse_pos,
        )

    def pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        return plan_edit_node_picking.pick_selected_opening_handle(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

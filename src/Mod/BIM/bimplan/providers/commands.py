# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider action command context for BIM Plan Edit."""

from __future__ import annotations

from dataclasses import dataclass

from . import payloads as plan_provider_payloads


@dataclass(frozen=True)
class PlanProviderActionContext:
    _session: object
    payload: object = None
    document_name: str = ""
    current_tool: str = ""

    @property
    def doc(self):
        return getattr(self._session, "doc", None)

    @property
    def action_payload(self):
        return self.payload

    def get_action_payload(self):
        return self.payload

    def get_action_payload_value(self, key, default=None):
        payload = self.payload
        if payload is None:
            return default
        getter = getattr(payload, "get", None)
        if callable(getter):
            return getter(key, default)
        return getattr(payload, key, default)

    def get_point(self):
        return self.get_action_payload_value("point")

    def get_placement_point(self):
        return self.get_action_payload_value("placement_point")

    def get_raw_point(self):
        return self.get_action_payload_value("raw_point")

    def get_snap_info(self):
        return self.get_action_payload_value("snap_info", {})

    def get_snap_object(self):
        return self.get_action_payload_value("snap_object")

    def get_host_source(self):
        return str(self.get_action_payload_value("host_source", "") or "")

    def get_selected_target(self):
        from bimplan.selection import kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("selected_target")
        )

    def get_selected_targets(self):
        from bimplan.selection import kinds as plan_target_kinds

        return tuple(
            plan_target_kinds.coerce_plan_target_ref(target)
            for target in (self.get_action_payload_value("selected_targets", ()) or ())
        )

    def get_hovered_target(self):
        from bimplan.selection import kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("hovered_target")
        )

    def get_snap_target(self):
        from bimplan.selection import kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("snap_target")
        )

    def get_host_target(self):
        return plan_provider_payloads.coerce_provider_host_target_ref(
            self.get_action_payload_value("host_target")
        )

    def select_wall_for_plan_edit(self, wall, sync_gui_selection=True):
        return bool(
            self._session.selection.activation.select_wall_for_plan_edit(
                wall,
                sync_gui_selection=sync_gui_selection,
            )
        )

    def queue_recompute_opening_hosts(self, opening):
        self._session.openings.queue_recompute_opening_hosts(opening)
        return True

    def recompute_document(self, doc=None):
        doc = doc if doc is not None else self.doc
        if doc is None:
            return False
        try:
            doc.recompute()
            return True
        except Exception:
            return False

    def refresh_opening_visuals(self, opening):
        self._session.openings.invalidate_wall_hosted_openings_cache()
        self._session.openings.refresh_opening_host_footprint_displays(opening)
        self._session.openings.refresh_opening_footprint_display(opening)

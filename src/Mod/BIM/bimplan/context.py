# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime context exposed to BIM Plan Edit providers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanEditContext:
    session: object
    document_name: str = ""
    active_storey_name: str = ""
    active_storey_label: str = ""
    current_tool: str = ""

    @classmethod
    def make_action_context(cls, session, payload=None, document_name="", current_tool=""):
        return PlanProviderActionContext(
            _session=session,
            payload=payload,
            document_name=str(document_name or ""),
            current_tool=str(current_tool or ""),
        )

    def get_selected_targets(self):
        getter = getattr(self.session, "get_plan_targets", None)
        if callable(getter):
            return tuple(getter(selected_only=True) or ())
        return ()

    def get_all_targets(self):
        getter = getattr(self.session, "get_plan_targets", None)
        if callable(getter):
            return tuple(getter(selected_only=False) or ())
        return ()

    def get_primary_target(self):
        targets = self.get_selected_targets()
        return targets[0] if targets else None

    def get_selected_objects(self):
        getter = getattr(self.session, "get_selected_objects", None)
        if callable(getter):
            return tuple(getter() or ())
        return ()

    def get_selected_semantic_records(self):
        getter = getattr(self.session, "get_plan_semantic_records", None)
        if callable(getter):
            return tuple(getter(targets=self.get_selected_targets()) or ())
        return ()

    def get_primary_semantic_record(self):
        records = self.get_selected_semantic_records()
        return records[0] if records else None

    def resolve_object(self, target):
        resolver = getattr(self.session, "resolve_plan_target_object", None)
        if callable(resolver):
            return resolver(target)
        return None

    def resolve_semantic_object(self, target):
        resolver = getattr(self.session, "resolve_plan_semantic_object", None)
        if callable(resolver):
            return resolver(target)
        return None

    def get_document(self):
        return getattr(self.session, "doc", None)

    def get_document_objects(self):
        return tuple(getattr(self.get_document(), "Objects", ()) or ())

    def is_selectable_wall(self, obj):
        checker = getattr(self.session, "_is_plan_selectable_wall", None)
        if callable(checker):
            try:
                return bool(checker(obj))
            except Exception:
                return False
        return False

    def get_wall_hosted_openings(self, wall):
        getter = getattr(self.session, "_get_wall_hosted_openings", None)
        if callable(getter):
            try:
                return tuple(getter(wall) or ())
            except Exception:
                return ()
        return ()

    def get_opening_plan_proxy(self, opening, *attrs):
        getter = getattr(self.session, "_get_opening_plan_proxy", None)
        if callable(getter):
            try:
                return getter(opening, *attrs)
            except Exception:
                return None
        return None


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

    def select_wall_for_plan_edit(self, wall, sync_gui_selection=True):
        selector = getattr(self._session, "_select_wall_for_plan_edit", None)
        if not callable(selector):
            return False
        return bool(selector(wall, sync_gui_selection=sync_gui_selection))

    def queue_recompute_opening_hosts(self, opening):
        recompute_hosts = getattr(self._session, "_queue_recompute_opening_hosts", None)
        if callable(recompute_hosts):
            recompute_hosts(opening)
            return True
        return False

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
        invalidate_cache = getattr(self._session, "_invalidate_wall_hosted_openings_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        refresh_hosts = getattr(self._session, "_refresh_opening_host_footprint_displays", None)
        if callable(refresh_hosts):
            refresh_hosts(opening)
        refresh_opening = getattr(self._session, "_refresh_opening_footprint_display", None)
        if callable(refresh_opening):
            refresh_opening(opening)

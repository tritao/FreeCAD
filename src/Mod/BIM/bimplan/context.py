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

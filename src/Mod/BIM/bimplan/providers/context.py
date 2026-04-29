# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider read context for BIM Plan Edit."""

from __future__ import annotations

from dataclasses import dataclass

from bimplan.runtime import capabilities as runtime_capabilities

from .commands import PlanProviderActionContext


def _call_component_method(session, component_name, method_name, *args, default=None, **kwargs):
    component = getattr(session, component_name, None)
    method = runtime_capabilities.get_callable(component, method_name)
    if method is None:
        method = runtime_capabilities.get_callable(session, method_name)
    if method is None:
        return default
    return method(*args, **kwargs)


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
        return tuple(self.session.selection.targets.get_plan_targets(selected_only=True) or ())

    def get_all_targets(self):
        return tuple(self.session.selection.targets.get_plan_targets(selected_only=False) or ())

    def get_primary_target(self):
        targets = self.get_selected_targets()
        return targets[0] if targets else None

    def get_selected_objects(self):
        return tuple(
            _call_component_method(
                self.session,
                "selection",
                "get_selected_objects",
                default=(),
            )
            or ()
        )

    def get_selected_semantic_records(self):
        getter = runtime_capabilities.get_callable(self.session, "get_plan_semantic_records")
        if getter is not None:
            return tuple(getter(targets=self.get_selected_targets()) or ())
        from . import runtime as plan_provider_runtime

        return tuple(
            plan_provider_runtime.get_plan_semantic_records(
                self.session,
                targets=self.get_selected_targets(),
            )
            or ()
        )

    def get_primary_semantic_record(self):
        records = self.get_selected_semantic_records()
        return records[0] if records else None

    def resolve_object(self, target):
        return self.session.selection.targets.resolve_plan_target_object(target)

    def resolve_semantic_object(self, target):
        return self.session.selection.targets.resolve_plan_semantic_object(target)

    def get_semantic_object(self, obj):
        semantic_obj = _call_component_method(
            self.session,
            "visibility",
            "get_plan_semantic_object",
            obj,
            default=None,
        )
        if semantic_obj is not None:
            return semantic_obj
        return obj

    def get_document(self):
        return getattr(self.session, "doc", None)

    def get_document_objects(self):
        return tuple(getattr(self.get_document(), "Objects", ()) or ())

    def is_selectable_wall(self, obj):
        return bool(self.session.selection.targets.is_plan_selectable_wall(obj))

    def get_wall_hosted_openings(self, wall):
        return tuple(
            _call_component_method(
                self.session,
                "openings",
                "get_wall_hosted_openings",
                wall,
                default=(),
            )
            or ()
        )

    def get_opening_plan_proxy(self, opening, *attrs):
        return _call_component_method(
            self.session,
            "openings",
            "get_opening_plan_proxy",
            opening,
            *attrs,
            default=None,
        )

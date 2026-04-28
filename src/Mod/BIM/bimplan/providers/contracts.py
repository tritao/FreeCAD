# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-facing contracts for BIM Plan Edit integrations."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

import FreeCAD

from . import host_targets as plan_host_targets
from bimplan.runtime import capabilities as runtime_capabilities


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
        from bimplan.selection import target_kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("selected_target")
        )

    def get_selected_targets(self):
        from bimplan.selection import target_kinds as plan_target_kinds

        return tuple(
            plan_target_kinds.coerce_plan_target_ref(target)
            for target in (self.get_action_payload_value("selected_targets", ()) or ())
        )

    def get_hovered_target(self):
        from bimplan.selection import target_kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("hovered_target")
        )

    def get_snap_target(self):
        from bimplan.selection import target_kinds as plan_target_kinds

        return plan_target_kinds.coerce_plan_target_ref(
            self.get_action_payload_value("snap_target")
        )

    def get_host_target(self):
        return plan_host_targets.coerce_provider_host_target_ref(
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
        self._session.document_visuals.queue_recompute_opening_hosts(opening)
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
        self._session.document_visuals.refresh_opening_host_footprint_displays(opening)
        self._session.document_visuals.refresh_opening_footprint_display(opening)


class PlanEditRegistry:
    def __init__(self):
        self._providers = OrderedDict()

    def __len__(self):
        return len(self._providers)

    def register_provider(self, provider):
        if provider is None:
            raise ValueError("A provider instance is required.")
        provider_id = str(provider.get_provider_id()).strip()
        if not provider_id:
            raise ValueError("Plan Edit providers must define a non-empty provider id.")
        self._providers[provider_id] = provider
        return provider

    def unregister_provider(self, provider_or_id):
        if provider_or_id is None:
            return None
        provider_id = provider_or_id
        if not isinstance(provider_or_id, str):
            provider_id = provider_or_id.get_provider_id()
        return self._providers.pop(str(provider_id).strip(), None)

    def clear(self):
        self._providers.clear()

    def get_provider(self, provider_id):
        return self._providers.get(str(provider_id or "").strip())

    def provider_ids(self):
        return tuple(self._providers.keys())

    def iter_providers(self):
        return tuple(self._providers.values())


_GLOBAL_PLAN_EDIT_REGISTRY = PlanEditRegistry()


def get_plan_edit_registry():
    return _GLOBAL_PLAN_EDIT_REGISTRY


class _PlanContractEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class PlanToolInteraction(_PlanContractEnum):
    IMMEDIATE = "immediate"
    POINT = "point"


class PlanIssueSeverity(_PlanContractEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PlanContextPanelState(_PlanContractEnum):
    EMPTY = "empty"
    ACTIVE_TOOL = "active_tool"
    SINGLE_OBJECT = "single_object"
    MULTI_SELECTION = "multi_selection"
    GEOMETRY_REVIEW = "geometry_review"


class PlanContextSubjectKind(_PlanContractEnum):
    SCOPE = "scope"
    INTERACTION = "interaction"
    ENDPOINT = "endpoint"
    NETWORK = "network"
    DISTRIBUTION = "distribution"
    GEOMETRY = "geometry"


class PlanOverlayTargetKind(_PlanContractEnum):
    OBJECT = "object"
    OPENING = "opening"
    PROVIDER = "provider"
    REGION = "region"
    SPACE = "space"
    SYMBOL = "symbol"
    WALL = "wall"


class PlanOverlayMarkerKind(_PlanContractEnum):
    CIRCLE = "circle"
    CIRCLE_CROSS = "circle_cross"
    CROSS = "cross"
    DIAMOND = "diamond"
    HOURGLASS = "hourglass"
    SQUARE = "square"


@dataclass(frozen=True)
class PlanActionSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""


@dataclass(frozen=True)
class PlanToolSpec:
    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""
    group: str = ""
    priority: int = 0
    interaction: PlanToolInteraction = PlanToolInteraction.IMMEDIATE
    prompt: str = ""
    default_host_target: tuple = ()


@dataclass(frozen=True)
class PlanEditHandleSpec:
    key: str
    point: tuple[float, float, float]
    label: str = ""
    tooltip: str = ""
    provider_id: str = ""
    target_key: str = ""
    action_key: str = ""
    transaction_label: str = ""
    prompt: str = ""
    role: str = ""
    interaction: PlanToolInteraction = PlanToolInteraction.POINT
    marker_kind: PlanOverlayMarkerKind = PlanOverlayMarkerKind.DIAMOND


@dataclass(frozen=True)
class PlanIssueSpec:
    key: str
    title: str
    message: str = ""
    severity: PlanIssueSeverity = PlanIssueSeverity.INFO
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    target_keys: Tuple[str, ...] = ()
    role: str = ""
    category: str = ""
    group_key: str = ""
    group_title: str = ""
    collapsed: bool = False
    summary: str = ""


@dataclass(frozen=True)
class PlanSuggestionSpec:
    key: str
    title: str
    message: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    target_keys: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanContextRowSpec:
    label: str
    value: str = ""


@dataclass(frozen=True)
class PlanContextDetailSpec:
    key: str
    title: str
    body: str = ""
    rows: Tuple[PlanContextRowSpec, ...] = ()
    collapsed: bool = True


@dataclass(frozen=True)
class PlanContextPanelSpec:
    key: str
    title: str
    subtitle: str = ""
    state: PlanContextPanelState = PlanContextPanelState.EMPTY
    subject_kind: PlanContextSubjectKind = PlanContextSubjectKind.SCOPE
    provider_id: str = ""
    summary_rows: Tuple[PlanContextRowSpec, ...] = ()
    message: str = ""
    primary_action: PlanActionSpec | None = None
    secondary_actions: Tuple[PlanActionSpec, ...] = ()
    details: Tuple[PlanContextDetailSpec, ...] = ()


@dataclass(frozen=True)
class PlanInspectorSection:
    key: str
    title: str
    body: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    role: str = ""
    collapsed: bool = False


@dataclass(frozen=True)
class PlanOverlayTargetSpec:
    document_name: str = ""
    object_name: str = ""
    target_kind: PlanOverlayTargetKind | None = None
    subname: str = ""


@dataclass(frozen=True)
class PlanProviderTargetSpec:
    key: str
    label: str = ""
    provider_id: str = ""
    document_name: str = ""
    object_name: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    category: str = ""
    role: str = ""


@dataclass(frozen=True)
class PlanOverlaySpec:
    key: str
    label: str = ""
    provider_id: str = ""
    target_keys: Tuple[str, ...] = ()
    points: Tuple[Tuple[float, float, float], ...] = ()
    point_targets: Tuple[PlanOverlayTargetSpec, ...] = ()
    polylines: Tuple[Tuple[Tuple[float, float, float], ...], ...] = ()
    color: Tuple[float, float, float] = (0.2, 0.55, 0.85)
    line_width: float = 2.0
    marker_size: float = 160.0
    marker_kind: PlanOverlayMarkerKind = PlanOverlayMarkerKind.CROSS
    dotted: bool = False
    visible: bool = True
    category: str = ""


class PlanEditProvider:
    provider_id = ""
    display_name = ""

    def get_provider_id(self):
        provider_id = str(getattr(self, "provider_id", "") or "").strip()
        if provider_id:
            return provider_id
        return self.__class__.__name__

    def get_display_name(self):
        display_name = str(getattr(self, "display_name", "") or "").strip()
        if display_name:
            return display_name
        return self.get_provider_id()

    def get_issues(self, context) -> Sequence[PlanIssueSpec]:
        del context
        return ()

    def get_suggestions(self, context) -> Sequence[PlanSuggestionSpec]:
        del context
        return ()

    def get_context_panels(self, context) -> Sequence[PlanContextPanelSpec]:
        del context
        return ()

    def get_inspector_sections(self, context) -> Sequence[PlanInspectorSection]:
        del context
        return ()

    def get_overlays(self, context) -> Sequence[PlanOverlaySpec]:
        del context
        return ()

    def get_targets(self, context) -> Sequence[PlanProviderTargetSpec]:
        del context
        return ()

    def get_tools(self, context) -> Sequence[PlanToolSpec]:
        del context
        return ()

    def get_edit_handles(self, context) -> Sequence[PlanEditHandleSpec]:
        del context
        return ()

    def execute_action(self, action_key, context, commands, payload=None):
        del action_key, context, commands, payload
        return False

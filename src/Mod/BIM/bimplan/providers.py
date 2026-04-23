# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-facing models for BIM Plan Edit integrations.

These dataclasses are the public contract used by BIM-owned and external
Plan Edit providers. Providers return declarative data here, while the core
session owns rendering, selection, and action execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple


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

    def get_semantic_object(self, obj):
        getter = getattr(self.session, "_get_plan_semantic_object", None)
        if callable(getter):
            try:
                semantic_obj = getter(obj)
                if semantic_obj is not None:
                    return semantic_obj
            except Exception:
                pass
        return obj

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


class _PlanContractEnum(str, Enum):
    """Shared base for closed-vocabulary provider contract values."""

    def __str__(self) -> str:
        return self.value


class PlanToolInteraction(_PlanContractEnum):
    """Plan Edit tool interaction modes exposed by providers."""

    IMMEDIATE = "immediate"
    POINT = "point"


class PlanIssueSeverity(_PlanContractEnum):
    """Supported provider issue severities."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PlanContextPanelState(_PlanContractEnum):
    """High-level contextual panel states resolved by the task panel."""

    EMPTY = "empty"
    ACTIVE_TOOL = "active_tool"
    SINGLE_OBJECT = "single_object"
    MULTI_SELECTION = "multi_selection"
    GEOMETRY_REVIEW = "geometry_review"


class PlanContextSubjectKind(_PlanContractEnum):
    """Shared subject kinds supported by the contextual MEP panel."""

    SCOPE = "scope"
    INTERACTION = "interaction"
    ENDPOINT = "endpoint"
    NETWORK = "network"
    DISTRIBUTION = "distribution"
    GEOMETRY = "geometry"


class PlanOverlayTargetKind(_PlanContractEnum):
    """Selectable target kinds available through provider overlay points."""

    OBJECT = "object"
    OPENING = "opening"
    PROVIDER = "provider"
    REGION = "region"
    SPACE = "space"
    SYMBOL = "symbol"
    WALL = "wall"


class PlanOverlayMarkerKind(_PlanContractEnum):
    """Supported provider point marker glyphs."""

    CIRCLE = "circle"
    CIRCLE_CROSS = "circle_cross"
    CROSS = "cross"
    DIAMOND = "diamond"
    HOURGLASS = "hourglass"
    SQUARE = "square"


@dataclass(frozen=True)
class PlanActionSpec:
    """Declarative action exposed by provider sections, issues, or suggestions."""

    key: str
    label: str
    tooltip: str = ""
    enabled: bool = True
    transaction_label: str = ""
    provider_id: str = ""


@dataclass(frozen=True)
class PlanToolSpec:
    """Declarative viewport tool exposed by a provider.

    `interaction`, `prompt`, and `default_host_target` are currently consumed by
    provider point tools that run inside the Plan Edit session.
    """

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
    """Direct-manipulation handle exposed by a provider for a selected target."""

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
    """Provider-reported problem shown in the Plan Guidance panel."""

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
    """Low-priority recommendation surfaced by a provider."""

    key: str
    title: str
    message: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    target_keys: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanContextRowSpec:
    """Compact key/value row rendered in the contextual panel summary."""

    label: str
    value: str = ""


@dataclass(frozen=True)
class PlanContextDetailSpec:
    """Collapsed advanced content exposed below the contextual panel summary."""

    key: str
    title: str
    body: str = ""
    rows: Tuple[PlanContextRowSpec, ...] = ()
    collapsed: bool = True


@dataclass(frozen=True)
class PlanContextPanelSpec:
    """Shared contextual-panel contract for MEP overlay modes.

    Providers may contribute one or more candidate panels. The task panel is
    expected to resolve these down to a single contextual state.
    """

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
    """Structured task-panel content contributed by a provider."""

    key: str
    title: str
    body: str = ""
    provider_id: str = ""
    actions: Tuple[PlanActionSpec, ...] = ()
    role: str = ""
    collapsed: bool = False


@dataclass(frozen=True)
class PlanOverlayTargetSpec:
    """Identity payload for an overlay point.

    When `point_targets` are supplied on a `PlanOverlaySpec`, they align by
    index with the `points` tuple and allow the rendered overlay marker to
    resolve back to a document object or Plan Edit target kind.
    """

    document_name: str = ""
    object_name: str = ""
    target_kind: PlanOverlayTargetKind | None = None
    subname: str = ""


@dataclass(frozen=True)
class PlanProviderTargetSpec:
    """First-class selectable Plan Edit target supplied by a provider.

    `document_name` and `object_name` identify the authored object selected in
    the document. `semantic_document_name` and `semantic_object_name` may point
    at a different semantic object when the provider target should inherit room,
    host, or storey semantics from another object.
    """

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
    """Lightweight plan-space visualization contributed by a provider.

    `target_keys` associate the overlay with provider-defined targets or issues.
    `point_targets` align by index with `points` and make point markers
    selectable. `category` is used for grouping and visibility controls in the
    Plan Guidance UI.
    """

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
    """Base class for add-ons extending BIM Plan Edit.

    Providers are expected to be mostly declarative:
    - report issues, suggestions, and inspector sections for the current context
    - optionally report contextual panel candidates for MEP-focused inspectors
    - expose overlays and optional first-class targets for in-view interaction
    - expose tools and handle action callbacks

    The session owns when these hooks are called, how results are normalized,
    and how provider targets participate in selection and task-panel state.
    """

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
        """Return first-class selectable targets for the current plan context."""

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

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-facing models for BIM Plan Edit integrations.

These dataclasses are the public contract used by BIM-owned and external
Plan Edit providers. Providers return declarative data here, while the core
session owns rendering, selection, and action execution.
"""

from __future__ import annotations

import FreeCAD
from collections import OrderedDict
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
        return tuple(self.session.selection.get_plan_targets(selected_only=True) or ())

    def get_all_targets(self):
        return tuple(self.session.selection.get_plan_targets(selected_only=False) or ())

    def get_primary_target(self):
        targets = self.get_selected_targets()
        return targets[0] if targets else None

    def get_selected_objects(self):
        return tuple(self.session.selection.get_selected_objects() or ())

    def get_selected_semantic_records(self):
        return tuple(
            self.session.providers.get_plan_semantic_records(targets=self.get_selected_targets())
            or ()
        )

    def get_primary_semantic_record(self):
        records = self.get_selected_semantic_records()
        return records[0] if records else None

    def resolve_object(self, target):
        return self.session.selection.resolve_plan_target_object(target)

    def resolve_semantic_object(self, target):
        return self.session.selection.resolve_plan_semantic_object(target)

    def get_semantic_object(self, obj):
        try:
            semantic_obj = self.session.visibility.get_plan_semantic_object(obj)
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
        try:
            return bool(self.session.selection.is_plan_selectable_wall(obj))
        except Exception:
            return False

    def get_wall_hosted_openings(self, wall):
        try:
            return tuple(self.session.openings.get_wall_hosted_openings(wall) or ())
        except Exception:
            return ()

    def get_opening_plan_proxy(self, opening, *attrs):
        try:
            return self.session.openings.get_opening_plan_proxy(opening, *attrs)
        except Exception:
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
        return bool(
            self._session.selection.select_wall_for_plan_edit(
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


_PROVIDER_ID = "bim-window"
_RECOMPUTE_HOST_ACTION_KEY = "bim_window_recompute_host"
_SELECT_HOST_ACTION_KEY = "bim_window_select_host"
_CENTER_ON_HOST_ACTION_KEY = "bim_window_center_on_host"
_WINDOW_OVERLAY_COLOR = (0.12, 0.38, 0.95)


class BIMWindowPlanEditProvider(PlanEditProvider):
    provider_id = _PROVIDER_ID
    display_name = "BIM Windows"

    def get_issues(self, context):
        window = _resolve_selected_window(context)
        if window is None:
            return ()

        host = _get_window_host_wall(context, window)
        issues = []
        if host is None:
            issues.append(
                PlanIssueSpec(
                    key=_object_key(window, "window-unhosted"),
                    title="Window has no host wall",
                    message=(
                        "This window is selected in Plan Edit, but it is not hosted by "
                        "a selectable wall."
                    ),
                    severity=PlanIssueSeverity.WARNING,
                    role="authoring",
                    category="windows",
                )
            )
        else:
            center = _get_window_center(context, window)
            if center is None:
                issues.append(
                    PlanIssueSpec(
                        key=_object_key(window, "window-center-unavailable"),
                        title="Window plan position cannot be read",
                        message=(
                            "Plan Edit cannot resolve the hosted window center. "
                            "Recomputing the host usually refreshes the window footprint."
                        ),
                        severity=PlanIssueSeverity.WARNING,
                        actions=(_recompute_host_action(),),
                        role="authoring",
                        category="windows",
                    )
                )
            elif not _window_fits_host_span(context, window, host, center):
                issues.append(
                    PlanIssueSpec(
                        key=_object_key(window, "window-outside-host"),
                        title="Window is outside the host wall span",
                        message=(
                            "The selected window center or width falls outside the "
                            "current host wall span."
                        ),
                        severity=PlanIssueSeverity.WARNING,
                        actions=(_center_on_host_action(), _recompute_host_action()),
                        role="authoring",
                        category="windows",
                    )
                )

        if not _has_valid_shape(window):
            issues.append(
                PlanIssueSpec(
                    key=_object_key(window, "window-shape-missing"),
                    title="Window shape is not built",
                    message=(
                        "The selected window has no usable shape. Recompute its host "
                        "and window footprint before continuing plan edits."
                    ),
                    severity=PlanIssueSeverity.WARNING,
                    actions=(_recompute_host_action(),),
                    role="authoring",
                    category="windows",
                )
            )
        return tuple(issues)

    def get_inspector_sections(self, context):
        window = _resolve_selected_window(context)
        if window is not None:
            host = _get_window_host_wall(context, window)
            return (
                PlanInspectorSection(
                    key=_object_key(window, "window-summary"),
                    title="Window",
                    body=_format_window_body(context, window, host),
                    actions=_window_actions(host),
                    role="details",
                    collapsed=False,
                ),
            )

        wall = _resolve_selected_wall(context)
        if wall is None:
            return ()
        windows = _get_wall_windows(context, wall)
        if not windows:
            return ()
        return (
            PlanInspectorSection(
                key=_object_key(wall, "wall-window-summary"),
                title="Windows on Wall",
                body=_format_wall_windows_body(context, wall, windows),
                actions=(),
                role="details",
                collapsed=False,
            ),
        )

    def get_overlays(self, context):
        wall = _resolve_selected_wall(context)
        if wall is None:
            return ()
        windows = _get_wall_windows(context, wall)
        if not windows:
            return ()

        points = []
        targets = []
        for window in windows:
            center = _get_window_center(context, window)
            if center is None:
                continue
            points.append(_point_tuple(center))
            targets.append(
                PlanOverlayTargetSpec(
                    document_name=str(getattr(getattr(window, "Document", None), "Name", "") or ""),
                    object_name=str(getattr(window, "Name", "") or ""),
                    target_kind=PlanOverlayTargetKind.OPENING,
                )
            )
        if not points:
            return ()
        return (
            PlanOverlaySpec(
                key=_object_key(wall, "wall-window-markers"),
                label="Hosted windows",
                points=tuple(points),
                point_targets=tuple(targets),
                color=_WINDOW_OVERLAY_COLOR,
                line_width=2.0,
                marker_size=120.0,
                category="windows",
            ),
        )

    def execute_action(self, action_key, context, commands, payload=None):
        del payload
        normalized_key = _normalize_text(action_key)
        window = _resolve_selected_window(context)
        if window is None:
            return False
        host = _get_window_host_wall(context, window)

        if normalized_key == _RECOMPUTE_HOST_ACTION_KEY:
            return _recompute_window_host(commands, window)
        if normalized_key == _SELECT_HOST_ACTION_KEY:
            return _select_window_host(commands, host)
        if normalized_key == _CENTER_ON_HOST_ACTION_KEY:
            return _center_window_on_host(context, commands, window, host)
        return False


def register_plan_edit_providers(registry=None):
    resolved_registry = registry if registry is not None else get_plan_edit_registry()
    existing = resolved_registry.get_provider(BIMWindowPlanEditProvider.provider_id)
    if isinstance(existing, BIMWindowPlanEditProvider):
        return existing
    provider = BIMWindowPlanEditProvider()
    resolved_registry.register_provider(provider)
    return provider


def _normalize_text(value):
    return str(value or "").strip()


def _object_label(obj):
    if obj is None:
        return ""
    label = str(getattr(obj, "Label", "") or "").strip()
    name = str(getattr(obj, "Name", "") or "").strip()
    if label and name and label != name:
        return f"{label} ({name})"
    return label or name


def _object_key(obj, suffix):
    doc_name = str(getattr(getattr(obj, "Document", None), "Name", "") or "")
    obj_name = str(getattr(obj, "Name", "") or "")
    identity = ":".join(part for part in (doc_name, obj_name, str(suffix or "")) if part)
    return identity or str(suffix or "")


def _get_semantic_object(context, obj):
    getter = getattr(context, "get_semantic_object", None)
    if callable(getter):
        return getter(obj)
    return obj


def _is_window_object(context, obj):
    if obj is None:
        return False
    obj = _get_semantic_object(context, obj)
    ifc_type = str(getattr(obj, "IfcType", "") or "").strip()
    if ifc_type == "Window":
        return True
    if ifc_type == "Door":
        return False
    try:
        import Draft

        return Draft.getType(obj) == "Window"
    except Exception:
        return False


def _resolve_target_object(context, target):
    for resolver_name in ("resolve_object", "resolve_semantic_object"):
        resolver = getattr(context, resolver_name, None)
        if not callable(resolver):
            continue
        try:
            obj = resolver(target)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def _resolve_selected_window(context):
    targets = []
    primary = getattr(context, "get_primary_target", lambda: None)()
    if primary is not None:
        targets.append(primary)
    targets.extend(
        target
        for target in tuple(getattr(context, "get_selected_targets", lambda: ())() or ())
        if target is not primary
    )

    for target in targets:
        if str(getattr(target, "kind", "") or "").strip() != "opening":
            continue
        obj = _resolve_target_object(context, target)
        if _is_window_object(context, obj):
            return _get_semantic_object(context, obj)

    for obj in tuple(getattr(context, "get_selected_objects", lambda: ())() or ()):
        if _is_window_object(context, obj):
            return _get_semantic_object(context, obj)
    return None


def _resolve_selected_wall(context):
    targets = []
    primary = getattr(context, "get_primary_target", lambda: None)()
    if primary is not None:
        targets.append(primary)
    targets.extend(
        target
        for target in tuple(getattr(context, "get_selected_targets", lambda: ())() or ())
        if target is not primary
    )
    for target in targets:
        if str(getattr(target, "kind", "") or "").strip() != "wall":
            continue
        obj = _resolve_target_object(context, target)
        if getattr(context, "is_selectable_wall", lambda _obj: False)(obj):
            return obj
        if _is_wall_object(obj):
            return obj
    return None


def _is_wall_object(obj):
    if obj is None:
        return False
    try:
        import Draft

        return Draft.getType(obj) == "Wall"
    except Exception:
        return False


def _get_window_host_wall(context, window):
    for host in tuple(getattr(window, "Hosts", None) or ()):
        if getattr(context, "is_selectable_wall", lambda _obj: False)(host):
            return host
        if _is_wall_object(host):
            return host
    return None


def _get_wall_windows(context, wall):
    if wall is None:
        return ()
    openings = tuple(getattr(context, "get_wall_hosted_openings", lambda _wall: ())(wall) or ())
    if not openings:
        openings = _scan_wall_windows_from_document(context, wall)
    return tuple(opening for opening in openings if _is_window_object(context, opening))


def _scan_wall_windows_from_document(context, wall):
    doc = getattr(wall, "Document", None)
    if doc is None:
        doc = getattr(context, "get_document", lambda: None)()
    windows = []
    for obj in tuple(getattr(doc, "Objects", ()) or ()):
        if wall in tuple(getattr(obj, "Hosts", None) or ()) and _is_window_object(context, obj):
            windows.append(obj)
    return tuple(windows)


def _has_valid_shape(obj):
    shape = getattr(obj, "Shape", None)
    if not shape:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return True


def _get_opening_plan_proxy(context, window, *attrs):
    getter = getattr(context, "get_opening_plan_proxy", None)
    if callable(getter):
        proxy = getter(window, *attrs)
        if proxy is not None:
            return proxy
    proxy = getattr(window, "Proxy", None)
    if proxy and all(hasattr(proxy, attr) for attr in attrs):
        return proxy
    return None


def _get_window_center(context, window):
    proxy = _get_opening_plan_proxy(context, window, "get_plan_center_point")
    if proxy is not None:
        try:
            center = proxy.get_plan_center_point()
            if center is not None:
                return FreeCAD.Vector(center)
        except Exception:
            pass

    shape = getattr(window, "Shape", None)
    bound_box = getattr(shape, "BoundBox", None)
    if bound_box is not None:
        try:
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                min(float(bound_box.ZMin), float(bound_box.ZMax)),
            )
        except Exception:
            pass

    base = getattr(window, "Base", None)
    placement = getattr(base, "Placement", None)
    if placement is not None:
        try:
            point = FreeCAD.Vector(placement.Base)
            point.z = 0.0
            return point
        except Exception:
            pass
    return None


def _get_wall_axis_context(wall):
    proxy = getattr(wall, "Proxy", None)
    if proxy is None or not hasattr(proxy, "calc_endpoints"):
        return None
    try:
        start, end = proxy.calc_endpoints(wall)
        start = FreeCAD.Vector(start)
        end = FreeCAD.Vector(end)
    except Exception:
        return None
    axis = end.sub(start)
    axis.z = 0.0
    length = axis.Length
    if length <= 1e-9:
        return None
    axis.normalize()
    return {
        "start": start,
        "end": end,
        "axis": axis,
        "length": length,
        "base_z": start.z,
    }


def _get_window_move_context(context, window):
    proxy = _get_opening_plan_proxy(context, window, "get_plan_move_context")
    if proxy is None:
        return {}
    try:
        return dict(proxy.get_plan_move_context() or {})
    except Exception:
        return {}


def _coerce_length_mm(value):
    try:
        value = value.Value
    except AttributeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_property_length_mm(obj, name):
    if obj is None or not hasattr(obj, name):
        return None
    try:
        return _coerce_length_mm(getattr(obj, name))
    except Exception:
        return None


def _format_length(value):
    value = _coerce_length_mm(value)
    if value is None:
        return "unknown"
    return f"{value:.0f} mm"


def _window_fits_host_span(context, window, host, center):
    wall_context = _get_wall_axis_context(host)
    if wall_context is None or center is None:
        return True
    move_context = _get_window_move_context(context, window)
    half_width = _coerce_length_mm(move_context.get("opening_half_width_u"))
    if half_width is None:
        width = _get_property_length_mm(window, "Width")
        half_width = max(0.0, (width or 0.0) * 0.5)
    center_u = FreeCAD.Vector(center).sub(wall_context["start"]).dot(wall_context["axis"])
    return center_u >= half_width - 1e-6 and center_u <= wall_context["length"] - half_width + 1e-6


def _get_window_offset_line(context, window, host):
    center = _get_window_center(context, window)
    wall_context = _get_wall_axis_context(host)
    if center is None or wall_context is None:
        return ""
    offset = FreeCAD.Vector(center).sub(wall_context["start"]).dot(wall_context["axis"])
    return f"Offset on host: {_format_length(offset)}"


def _get_window_sill_line(context, window, host):
    base = getattr(window, "Base", None)
    placement = getattr(base, "Placement", None)
    if placement is None:
        return ""
    wall_context = _get_wall_axis_context(host)
    try:
        sill = float(placement.Base.z)
    except Exception:
        return ""
    if wall_context is not None:
        sill -= float(wall_context["base_z"])
    return f"Sill height: {_format_length(sill)}"


def _format_window_body(context, window, host):
    lines = [
        f"Window: {_object_label(window)}",
        f"Host wall: {_object_label(host) if host is not None else 'not hosted'}",
    ]
    width = _get_property_length_mm(window, "Width")
    height = _get_property_length_mm(window, "Height")
    if width is not None:
        lines.append(f"Width: {_format_length(width)}")
    if height is not None:
        lines.append(f"Height: {_format_length(height)}")
    sill_line = _get_window_sill_line(context, window, host)
    if sill_line:
        lines.append(sill_line)
    offset_line = _get_window_offset_line(context, window, host)
    if offset_line:
        lines.append(offset_line)

    center = _get_window_center(context, window)
    if host is None:
        lines.append("Status: not hosted")
    elif center is None:
        lines.append("Status: plan center unavailable")
    elif not _window_fits_host_span(context, window, host, center):
        lines.append("Status: outside host span")
    elif not _has_valid_shape(window):
        lines.append("Status: shape missing")
    else:
        lines.append("Status: hosted")
    return "\n".join(lines)


def _format_wall_windows_body(context, wall, windows):
    lines = [
        f"Wall: {_object_label(wall)}",
        f"Hosted windows: {len(windows)}",
    ]
    for window in windows:
        details = [_object_label(window)]
        offset_line = _get_window_offset_line(context, window, wall)
        if offset_line:
            details.append(offset_line.replace("Offset on host: ", "offset "))
        lines.append("- " + ", ".join(details))
    return "\n".join(lines)


def _window_actions(host):
    actions = [_recompute_host_action()]
    if host is not None:
        actions.append(_select_host_action())
        actions.append(_center_on_host_action())
    return tuple(actions)


def _recompute_host_action():
    return PlanActionSpec(
        key=_RECOMPUTE_HOST_ACTION_KEY,
        label="Recompute host",
        tooltip="Touch and recompute the host wall, then refresh this window footprint.",
        transaction_label="Recompute window host",
    )


def _select_host_action():
    return PlanActionSpec(
        key=_SELECT_HOST_ACTION_KEY,
        label="Select host wall",
        tooltip="Select the wall hosting this window.",
    )


def _center_on_host_action():
    return PlanActionSpec(
        key=_CENTER_ON_HOST_ACTION_KEY,
        label="Center on host",
        tooltip="Move this window to the midpoint of its host wall.",
        transaction_label="Center window on host",
    )


def _recompute_window_host(commands, window):
    if window is None:
        return False
    if getattr(commands, "queue_recompute_opening_hosts", lambda _opening: False)(window):
        pass
    else:
        for host in tuple(getattr(window, "Hosts", None) or ()):
            try:
                host.touch()
            except Exception:
                pass
        doc = getattr(window, "Document", None) or getattr(commands, "doc", None)
        getattr(commands, "recompute_document", lambda _doc=None: False)(doc)
    _refresh_window_visuals(commands, window)
    return True


def _select_window_host(commands, host):
    if host is None:
        return False
    return bool(
        getattr(commands, "select_wall_for_plan_edit", lambda _host, **_kwargs: False)(
            host,
            sync_gui_selection=True,
        )
    )


def _center_window_on_host(context, commands, window, host):
    if window is None or host is None:
        return False
    wall_context = _get_wall_axis_context(host)
    if wall_context is None:
        return False
    proxy = _get_opening_plan_proxy(context, window, "move_along_host")
    if proxy is None:
        return False
    current = _get_window_center(context, window)
    target = wall_context["start"].add(
        FreeCAD.Vector(wall_context["axis"]).multiply(wall_context["length"] * 0.5)
    )
    target.z = current.z if current is not None else wall_context["base_z"]
    try:
        moved = bool(proxy.move_along_host(target))
    except Exception:
        moved = False
    if not moved:
        return False
    _refresh_window_visuals(commands, window)
    return True


def _refresh_window_visuals(commands, window):
    refresher = getattr(commands, "refresh_opening_visuals", None)
    if callable(refresher):
        refresher(window)


def _point_tuple(point):
    point = FreeCAD.Vector(point)
    return (float(point.x), float(point.y), float(point.z))

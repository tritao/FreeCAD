# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, replace

import FreeCAD

from bimplan import document_visuals as plan_document_visuals
from bimplan.providers import get_plan_edit_registry
from .contracts import (
    PlanActionSpec,
    PlanContextDetailSpec,
    PlanContextPanelSpec,
    PlanContextPanelState,
    PlanContextRowSpec,
    PlanContextSubjectKind,
    PlanEditHandleSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanIssueSeverity,
    PlanOverlaySpec,
    PlanOverlayMarkerKind,
    PlanOverlayTargetSpec,
    PlanOverlayTargetKind,
    PlanProviderTargetSpec,
    PlanSuggestionSpec,
    PlanToolSpec,
    PlanToolInteraction,
    PlanEditContext,
)
from bimplan.semantics import PlanSemanticRecord
from bimplan.transactions import PlanEditTransaction

translate = FreeCAD.Qt.translate

PLAN_PROVIDER_OVERLAY_MODE_ALL = "all"
PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE = "architecture"
PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL = "electrical"
PLAN_PROVIDER_OVERLAY_MODE_PLUMBING = "plumbing"
FOCUSED_PROVIDER_OVERLAY_PICK_MODES = frozenset(
    (
        PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL,
        PLAN_PROVIDER_OVERLAY_MODE_PLUMBING,
    )
)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _perf_count(session, name, delta=1):
    try:
        return session.performance.plan_perf_count(name, delta=delta)
    except TypeError:
        return session.performance.plan_perf_count(name)


def _get_instance_override(obj, method_name):
    obj_dict = getattr(obj, "__dict__", None)
    if not isinstance(obj_dict, dict) or method_name not in obj_dict:
        return None
    method = getattr(obj, method_name, None)
    if callable(method):
        return method
    return None


def _get_external_provider_api(session, method_name=None):
    providers = getattr(session, "providers", None)
    if isinstance(providers, PlanProvidersAPI):
        if method_name and _get_instance_override(providers, method_name) is not None:
            return providers
        return None
    return providers


def _call_provider_method(session, method_name, *args, default=None, **kwargs):
    providers = _get_external_provider_api(session, method_name)
    method = getattr(providers, method_name, None) if providers is not None else None
    if callable(method):
        return method(*args, **kwargs)
    return default


def _get_external_provider_refresh_cache_scope(session):
    return _call_provider_method(
        session,
        "plan_provider_refresh_cache_scope",
        default=None,
    )


def _get_external_provider_targets(session):
    direct_targets = _call_provider_method(session, "get_plan_provider_targets", default=_MISSING)
    if direct_targets is _MISSING:
        return _MISSING
    return tuple(direct_targets or ())


def _find_external_provider_target_for_object(session, object_key):
    external_targets = _get_external_provider_targets(session)
    if external_targets is _MISSING:
        return _MISSING
    default_document_name = _get_default_plan_provider_target_document_name(session)
    for target in external_targets:
        target_key = _make_plan_provider_target_object_key(
            getattr(target, "document_name", "") or default_document_name,
            getattr(target, "object_name", ""),
        )
        if target_key == object_key:
            return target
    return None


@dataclass
class _PlanProviderTargetDisplayFields:
    label: str = ""
    provider_id: str = ""
    target_key: str = ""
    category: str = ""
    role: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""


_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY = ("provider_snapshot", "panel")
_MISSING = object()


class PlanProvidersAPI:
    """Owned session surface for Plan Edit provider behavior."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_plan_provider_registry(self):
        del self
        return get_plan_edit_registry()

    def get_plan_provider_overlay_category(self, provider_id):
        del self
        return get_plan_provider_overlay_category(provider_id)

    def execute_plan_provider_action(
        self,
        provider_id,
        action_key,
        transaction_label="",
        payload=None,
    ):
        session = self.session
        if (
            session.lifecycle_state.tearing_down
            or session.lifecycle_state.finishing
            or not session.document_visuals.document_is_alive()
        ):
            return False
        if self.plan_provider_integrations_disabled():
            return False
        return execute_plan_provider_action(
            session,
            provider_id,
            action_key,
            transaction_label=transaction_label,
            payload=payload,
        )

    def get_provider_point_tool_label(self):
        from bimplan.providers import point

        return point.get_provider_point_tool_label(self.session)

    def get_provider_point_tool_prompt(self):
        from bimplan.providers import point

        return point.get_provider_point_tool_prompt(self.session)

    def has_active_provider_point_tool(self):
        from bimplan.providers import point

        return point.has_active_provider_point_tool(self.session)

    def arm_provider_point_tool(self):
        from bimplan.providers import point

        return point.arm_provider_point_tool(self.session)

    def cancel_provider_point_tool(self, refresh=True):
        from bimplan.providers import point

        return point.cancel_provider_point_tool(self.session, refresh=refresh)

    def start_plan_provider_point_tool(self, tool):
        from bimplan.providers import point

        return point.start_plan_provider_point_tool(self.session, tool)

    def handle_provider_point_tool_point(self, point=None, obj=None):
        from bimplan.providers import point as provider_point

        return provider_point.handle_provider_point_tool_point(
            self.session,
            point=point,
            obj=obj,
        )

    def update_provider_point_tool_preview(self, point=None, obj=None):
        from bimplan.providers import point

        return point.update_provider_point_tool_preview(
            self.session,
            point=point,
            obj=obj,
        )

    def get_provider_point_snap_info(self):
        del self
        from bimplan.providers import point

        return point.get_provider_point_snap_info()

    def resolve_provider_point_snap_object(self, snap_object, snap_info):
        from bimplan.providers import point

        return point.resolve_provider_point_snap_object(
            self.session,
            snap_object,
            snap_info,
        )

    def normalize_provider_point_host_target(self, target):
        from bimplan.providers import point

        return point.normalize_provider_point_host_target(self.session, target)

    def get_provider_point_context_host_state(self):
        from bimplan.providers import point

        return point.get_provider_point_context_host_state(self.session)

    def get_provider_point_payload_host_target(
        self,
        *,
        snap_target,
        selected_target,
        selected_targets,
        hovered_target,
    ):
        from bimplan.providers import point

        return point.get_provider_point_payload_host_target(
            self.session,
            snap_target=snap_target,
            selected_target=selected_target,
            selected_targets=selected_targets,
            hovered_target=hovered_target,
        )

    def project_provider_point_to_host(self, point, host_wall):
        del self
        from bimplan.providers import point as provider_point

        return provider_point.project_provider_point_to_host(point, host_wall)

    def build_provider_point_tool_payload(
        self,
        tool,
        *,
        raw_point,
        plan_point,
        snap_object,
        snap_info,
    ):
        from bimplan.providers import point

        return point.build_provider_point_tool_payload(
            self.session,
            tool,
            raw_point=raw_point,
            plan_point=plan_point,
            snap_object=snap_object,
            snap_info=snap_info,
        )

    def get_selected_provider_edit_handles(self, provider_obj):
        from bimplan.providers import edit

        return edit.get_selected_provider_edit_handles(self.session, provider_obj)

    def can_move_provider_target_by_placement(self, provider_obj):
        from bimplan.providers import edit

        return edit.can_move_provider_target_by_placement(self.session, provider_obj)

    def activate_provider_handle(self, provider_obj, handle_index):
        from bimplan.providers import edit

        return edit.activate_provider_handle(self.session, provider_obj, handle_index)

    def activate_provider_handle_now(self, provider_obj, handle_index):
        from bimplan.providers import edit

        return edit.activate_provider_handle_now(self.session, provider_obj, handle_index)

    def start_provider_handle_point_pick(self, provider_obj, handle_index, handle):
        from bimplan.providers import edit

        return edit.start_provider_handle_point_pick(
            self.session,
            provider_obj,
            handle_index,
            handle,
        )

    def update_provider_handle_point_pick(self, point=None, snap_info=None):
        from bimplan.providers import edit

        return edit.update_provider_handle_point_pick(
            self.session,
            point=point,
            snap_info=snap_info,
        )

    def finish_provider_handle_point_pick(self, point=None, obj=None):
        from bimplan.providers import edit

        return edit.finish_provider_handle_point_pick(
            self.session,
            point=point,
            obj=obj,
        )

    def cancel_provider_handle_point_pick(self):
        from bimplan.providers import edit

        return edit.cancel_provider_handle_point_pick(self.session)

    def restore_selected_provider(self, provider_obj):
        from bimplan.providers import edit

        return edit.restore_selected_provider(self.session, provider_obj)

    def queue_restore_selected_provider(self, provider_obj):
        from bimplan.providers import edit

        return edit.queue_restore_selected_provider(self.session, provider_obj)

    def plan_provider_integrations_disabled(self):
        return plan_provider_integrations_disabled(self.session)

    def get_plan_provider_id(self, provider):
        del self
        return get_plan_provider_id(provider)

    def coerce_plan_provider_results(self, result):
        del self
        return coerce_plan_provider_results(result)

    def normalize_plan_provider_action(self, provider_id, action):
        del self
        return normalize_plan_provider_action(provider_id, action)

    def normalize_plan_provider_tool(self, provider_id, tool):
        del self
        return normalize_plan_provider_tool(provider_id, tool)

    def normalize_plan_provider_edit_handle(self, provider_id, handle):
        del self
        return normalize_plan_provider_edit_handle(provider_id, handle)

    def normalize_plan_provider_issue(self, provider_id, issue):
        return normalize_plan_provider_issue(self.session, provider_id, issue)

    def normalize_plan_provider_suggestion(self, provider_id, suggestion):
        return normalize_plan_provider_suggestion(self.session, provider_id, suggestion)

    def normalize_plan_provider_section(self, provider_id, section):
        return normalize_plan_provider_section(self.session, provider_id, section)

    def normalize_plan_provider_context_panel(self, provider_id, panel):
        return normalize_plan_provider_context_panel(self.session, provider_id, panel)

    def normalize_plan_provider_overlay(self, provider_id, overlay):
        del self
        return normalize_plan_provider_overlay(provider_id, overlay)

    def normalize_plan_provider_target(self, provider_id, target):
        del self
        return normalize_plan_provider_target(provider_id, target)

    def collect_plan_provider_contributions(self, method_name, normalizer):
        return collect_plan_provider_contributions(self.session, method_name, normalizer)

    def get_plan_provider_display_name(self, provider_id):
        return get_plan_provider_display_name(self.session, provider_id)

    def get_plan_provider_issues(self):
        return get_plan_provider_issues(self.session)

    def get_plan_provider_suggestions(self):
        return get_plan_provider_suggestions(self.session)

    def get_plan_provider_tools(self):
        return get_plan_provider_tools(self.session)

    def get_plan_provider_snapshot(self):
        return get_plan_provider_snapshot(self.session)

    def get_plan_provider_edit_handles(self):
        return get_plan_provider_edit_handles(self.session)

    def get_plan_provider_inspector_sections(self):
        return get_plan_provider_inspector_sections(self.session)

    def get_plan_provider_context_panels(self):
        return get_plan_provider_context_panels(self.session)

    def get_plan_provider_overlays(self):
        return get_plan_provider_overlays(self.session)

    def get_plan_provider_overlay_mode(self):
        return get_plan_provider_overlay_mode(self.session)

    def set_plan_provider_overlay_mode(self, mode):
        return set_plan_provider_overlay_mode(self.session, mode)

    def get_plan_provider_targets(self):
        return get_plan_provider_targets(self.session)

    def get_plan_provider_target_for_object(self, obj):
        return get_plan_provider_target_for_object(self.session, obj)

    def is_plan_provider_target_object(self, obj):
        return is_plan_provider_target_object(self.session, obj)

    def is_plan_provider_overlay_enabled(self, overlay):
        return is_plan_provider_overlay_enabled(self.session, overlay)

    def is_plan_provider_overlay_visible_for_mode(self, overlay, mode=None):
        return is_plan_provider_overlay_visible_for_mode(
            self.session,
            overlay,
            mode=mode,
        )

    def is_plan_provider_overlay_visible(self, overlay):
        return is_plan_provider_overlay_visible(self.session, overlay)

    def set_plan_provider_overlay_visible(self, provider_id, overlay_key, visible):
        return set_plan_provider_overlay_visible(
            self.session,
            provider_id,
            overlay_key,
            visible,
        )

    def queue_plan_provider_overlay_refresh(self):
        return queue_plan_provider_overlay_refresh(self.session)

    def queue_plan_provider_overlay_sync(self):
        return queue_plan_provider_overlay_sync(self.session)

    def build_plan_semantic_record(self, target_kind, target_obj):
        return build_plan_semantic_record(self.session, target_kind, target_obj)

    def get_plan_semantic_records(self, targets=None):
        return get_plan_semantic_records(self.session, targets=targets)

    def get_plan_edit_context(self):
        return get_plan_edit_context(self.session)

    def get_plan_provider_action_context(self, payload=None):
        return get_plan_provider_action_context(self.session, payload=payload)

    def plan_provider_refresh_cache_scope(self):
        return plan_provider_refresh_cache_scope(self.session)

    def invalidate_plan_provider_document_cache(self):
        return invalidate_plan_provider_document_cache(self.session)


@dataclass(frozen=True)
class PlanProviderSnapshot:
    """Normalized provider read model for the task-panel integration surfaces."""

    tools: tuple[PlanToolSpec, ...] = ()
    overlays: tuple[PlanOverlaySpec, ...] = ()
    issues: tuple[PlanIssueSpec, ...] = ()
    context_panels: tuple[PlanContextPanelSpec, ...] = ()
    inspector_sections: tuple[PlanInspectorSection, ...] = ()

    def is_empty(self) -> bool:
        return not (
            self.tools
            or self.overlays
            or self.issues
            or self.context_panels
            or self.inspector_sections
        )


def _is_active_provider_session(session):
    return not (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not session.document_visuals.document_is_alive()
    )


def plan_provider_integrations_disabled(session):
    import os

    env_value = str(os.environ.get("FC_BIM_PLAN_EDIT_DISABLE_INTEGRATIONS", "") or "").strip()
    if env_value:
        return env_value not in {"0", "false", "False", "no", "off"}
    try:
        return bool(
            session.performance_state.plan_edit_params.GetBool("DisableIntegrations", False)
        )
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False


def _get_provider_runtime_state(session):
    return session.provider_runtime_state


def _get_provider_target_collection_depth(session):
    return int(_get_provider_runtime_state(session).target_collection_depth or 0)


def _set_provider_target_collection_depth(session, depth):
    _get_provider_runtime_state(session).target_collection_depth = int(depth or 0)


def invalidate_plan_provider_document_cache(session):
    _get_provider_runtime_state(session).document_cache = {}


@contextmanager
def plan_provider_refresh_cache_scope(session):
    external_scope = _get_external_provider_refresh_cache_scope(session)
    if external_scope is not None:
        with external_scope:
            yield external_scope
        return
    provider_runtime_state = _get_provider_runtime_state(session)
    previous_cache = provider_runtime_state.refresh_cache
    provider_runtime_state.refresh_cache = {}
    current_cache = provider_runtime_state.refresh_cache
    try:
        yield current_cache
    finally:
        provider_runtime_state.refresh_cache = previous_cache


def _get_provider_refresh_cache(session):
    refresh_cache = _get_provider_runtime_state(session).refresh_cache
    if isinstance(refresh_cache, dict):
        return refresh_cache
    return None


def _get_provider_document_cache(session):
    document_cache = _get_provider_runtime_state(session).document_cache
    if isinstance(document_cache, dict):
        return document_cache
    return None


def _get_provider_object_cache_key(obj):
    if obj is None:
        return ("", "")
    return (
        str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip(),
        str(getattr(obj, "Name", "") or "").strip(),
    )


def _get_provider_target_cache_key(target):
    return (
        str(getattr(target, "kind", "") or "").strip(),
        *_get_provider_object_cache_key(getattr(target, "obj", None)),
    )


def _get_selected_plan_target_cache_key(session):
    return tuple(
        _get_provider_target_cache_key(target)
        for target in tuple(session.selection.state.get_selected_plan_targets() or ())
    )


def _get_selected_provider_object_cache_key(session):
    return tuple(
        _get_provider_object_cache_key(obj)
        for obj in tuple(session.provider_transient_state.provider_selected_objects or ())
    )


def _make_provider_context_cache_key(session, context, method_name):
    return (
        str(method_name or "").strip(),
        str(getattr(context, "document_name", "") or "").strip(),
        str(getattr(context, "active_storey_name", "") or "").strip(),
        str(getattr(context, "current_tool", "") or "").strip(),
        normalize_plan_provider_overlay_mode(get_plan_provider_overlay_mode(session)),
        _get_selected_plan_target_cache_key(session),
        _get_selected_provider_object_cache_key(session),
    )


def _make_provider_target_context_cache_key(context):
    return (
        "get_targets",
        str(getattr(context, "document_name", "") or "").strip(),
        str(getattr(context, "active_storey_name", "") or "").strip(),
    )


def _make_provider_document_cache_key(session, context, method_name):
    if str(method_name or "").strip() == "get_targets":
        return ("provider_contributions",) + _make_provider_target_context_cache_key(context)
    return ("provider_contributions",) + _make_provider_context_cache_key(
        session,
        context,
        method_name,
    )


def _get_cached_provider_contributions(session, method_name):
    refresh_cache = _get_provider_refresh_cache(session)
    if refresh_cache is None:
        return None
    return refresh_cache.get(("provider_contributions", str(method_name or "")))


def _set_cached_provider_contributions(session, method_name, contributions):
    refresh_cache = _get_provider_refresh_cache(session)
    if refresh_cache is None:
        return
    refresh_cache[("provider_contributions", str(method_name or ""))] = contributions


def _get_document_cached_provider_contributions(session, context, method_name):
    document_cache = _get_provider_document_cache(session)
    if document_cache is None:
        return None
    return document_cache.get(_make_provider_document_cache_key(session, context, method_name))


def _set_document_cached_provider_contributions(session, context, method_name, contributions):
    document_cache = _get_provider_document_cache(session)
    if document_cache is None:
        return
    document_cache[_make_provider_document_cache_key(session, context, method_name)] = contributions


def _get_cached_provider_snapshot(session):
    refresh_cache = _get_provider_refresh_cache(session)
    if refresh_cache is None:
        return None
    cached_snapshot = refresh_cache.get(_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY)
    if isinstance(cached_snapshot, PlanProviderSnapshot):
        return cached_snapshot
    return None


def _set_cached_provider_snapshot(session, snapshot):
    refresh_cache = _get_provider_refresh_cache(session)
    if refresh_cache is None:
        return
    refresh_cache[_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY] = snapshot


def _get_document_cached_provider_snapshot(session, context):
    document_cache = _get_provider_document_cache(session)
    if document_cache is None:
        return None
    cached_snapshot = document_cache.get(
        ("provider_snapshot",) + _make_provider_context_cache_key(session, context, "snapshot")
    )
    if isinstance(cached_snapshot, PlanProviderSnapshot):
        return cached_snapshot
    return None


def _set_document_cached_provider_snapshot(session, context, snapshot):
    document_cache = _get_provider_document_cache(session)
    if document_cache is None:
        return
    document_cache[
        ("provider_snapshot",) + _make_provider_context_cache_key(session, context, "snapshot")
    ] = snapshot


def _get_plan_edit_context_or_none(session):
    context = _call_provider_method(session, "get_plan_edit_context", default=_MISSING)
    if context is not _MISSING:
        return context
    try:
        return get_plan_edit_context(session)
    except (ReferenceError, RuntimeError):
        return None


def _get_plan_provider_registry(session):
    providers = getattr(session, "providers", None)
    registry_getter = getattr(providers, "get_plan_provider_registry", None)
    if callable(registry_getter):
        return registry_getter()
    return get_plan_edit_registry()


def _get_document_visual_update_scope(session):
    document_visuals = getattr(session, "document_visuals", None)
    defer_updates = getattr(document_visuals, "defer_document_visual_updates", None)
    if callable(defer_updates):
        return defer_updates()
    return nullcontext()


def _iter_named_plan_providers(session):
    for provider in _get_plan_provider_registry(session).iter_providers():
        provider_id = get_plan_provider_id(provider)
        if provider_id:
            yield provider, provider_id


def _collect_provider_surface_contributions(
    session,
    provider,
    provider_id,
    context,
    method_name,
    normalizer,
):
    method = getattr(provider, method_name, None)
    if not callable(method):
        return ()

    span_name = "plan_provider_{}_{}".format(
        str(provider_id or "").replace(" ", "_"),
        method_name,
    )
    with _perf_trace_span(session, span_name):
        try:
            provided = method(context)
        except Exception as exc:
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "Plan Edit provider '{provider}' failed in {method}: {error}\n",
                ).format(provider=provider_id, method=method_name, error=exc)
            )
            return ()

    results = []
    for contribution in coerce_plan_provider_results(provided):
        normalized = _normalize_provider_surface_contribution(
            session,
            normalizer,
            provider_id,
            contribution,
        )
        if normalized is not None:
            results.append(normalized)

    _perf_count(
        session,
        "plan_provider_{}_{}_contributions".format(provider_id, method_name),
        len(results),
    )
    return tuple(results)


def _collect_plan_provider_contributions_for_method(session, context, method_name, normalizer):
    results = []
    for provider, provider_id in _iter_named_plan_providers(session):
        results.extend(
            _collect_provider_surface_contributions(
                session,
                provider,
                provider_id,
                context,
                method_name,
                normalizer,
            )
        )
    return tuple(results)


def _normalize_provider_surface_contribution(session, normalizer, provider_id, contribution):
    if normalizer in _SESSION_AWARE_PROVIDER_NORMALIZERS:
        return normalizer(session, provider_id, contribution)
    return normalizer(provider_id, contribution)


def _set_cached_provider_snapshot_contributions(session, snapshot):
    _set_cached_provider_contributions(session, "get_tools", snapshot.tools)
    _set_cached_provider_contributions(session, "get_overlays", snapshot.overlays)
    _set_cached_provider_contributions(session, "get_issues", snapshot.issues)
    _set_cached_provider_contributions(session, "get_context_panels", snapshot.context_panels)
    _set_cached_provider_contributions(
        session, "get_inspector_sections", snapshot.inspector_sections
    )


def _set_document_cached_provider_snapshot_contributions(session, context, snapshot):
    _set_document_cached_provider_contributions(session, context, "get_tools", snapshot.tools)
    _set_document_cached_provider_contributions(session, context, "get_overlays", snapshot.overlays)
    _set_document_cached_provider_contributions(session, context, "get_issues", snapshot.issues)
    _set_document_cached_provider_contributions(
        session, context, "get_context_panels", snapshot.context_panels
    )
    _set_document_cached_provider_contributions(
        session, context, "get_inspector_sections", snapshot.inspector_sections
    )


def _collect_plan_provider_snapshot_from_providers(session, context):
    return PlanProviderSnapshot(
        tools=_collect_plan_provider_contributions_for_method(
            session,
            context,
            "get_tools",
            normalize_plan_provider_tool,
        ),
        overlays=_collect_plan_provider_contributions_for_method(
            session,
            context,
            "get_overlays",
            normalize_plan_provider_overlay,
        ),
        issues=_collect_plan_provider_contributions_for_method(
            session,
            context,
            "get_issues",
            normalize_plan_provider_issue,
        ),
        context_panels=_collect_plan_provider_contributions_for_method(
            session,
            context,
            "get_context_panels",
            normalize_plan_provider_context_panel,
        ),
        inspector_sections=_collect_plan_provider_contributions_for_method(
            session,
            context,
            "get_inspector_sections",
            normalize_plan_provider_section,
        ),
    )


def collect_plan_provider_snapshot(session) -> PlanProviderSnapshot:
    with _perf_trace_span(session, "collect_plan_provider_snapshot"):
        if not session.document_visuals.document_is_alive():
            return PlanProviderSnapshot()

        cached_snapshot = _get_cached_provider_snapshot(session)
        if cached_snapshot is not None:
            return cached_snapshot

        context = _get_plan_edit_context_or_none(session)
        if context is None:
            return PlanProviderSnapshot()
        cached_snapshot = _get_document_cached_provider_snapshot(session, context)
        if cached_snapshot is not None:
            _set_cached_provider_snapshot(session, cached_snapshot)
            _set_cached_provider_snapshot_contributions(session, cached_snapshot)
            return cached_snapshot

        snapshot = _collect_plan_provider_snapshot_from_providers(session, context)
        _set_cached_provider_snapshot(session, snapshot)
        _set_document_cached_provider_snapshot(session, context, snapshot)
        _set_cached_provider_snapshot_contributions(session, snapshot)
        _set_document_cached_provider_snapshot_contributions(session, context, snapshot)
        return snapshot


def get_plan_provider_display_name(session, provider_id):
    provider = _get_plan_provider_registry(session).get_provider(provider_id)
    if provider is None:
        return str(provider_id or "").strip()
    display_name = str(getattr(provider, "display_name", "") or "").strip()
    if display_name:
        return display_name
    getter = getattr(provider, "get_display_name", None)
    if callable(getter):
        try:
            return str(getter() or "").strip()
        except Exception:
            pass
    provider_name = str(getattr(provider, "provider_id", "") or "").strip()
    return provider_name or str(provider_id or "").strip()


def get_plan_provider_overlay_visibility_key(provider_id, overlay_key):
    provider_id = str(provider_id or "").strip()
    overlay_key = str(overlay_key or "").strip()
    if not provider_id or not overlay_key:
        return None
    return (provider_id, overlay_key)


def normalize_plan_provider_overlay_mode(mode):
    normalized = str(mode or "").strip().lower()
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ALL:
        return PLAN_PROVIDER_OVERLAY_MODE_ALL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def _provider_overlay_read_state(session):
    return session.provider_overlay_read_state


def get_plan_provider_overlay_mode(session):
    external_mode = _call_provider_method(session, "get_plan_provider_overlay_mode", default=None)
    if external_mode is not None:
        return normalize_plan_provider_overlay_mode(external_mode)
    return normalize_plan_provider_overlay_mode(_provider_overlay_read_state(session).mode)


def is_focused_provider_overlay_pick_mode(mode):
    return normalize_plan_provider_overlay_mode(mode) in FOCUSED_PROVIDER_OVERLAY_PICK_MODES


def set_plan_provider_overlay_mode(session, mode):
    normalized = normalize_plan_provider_overlay_mode(mode)
    if normalized == get_plan_provider_overlay_mode(session):
        return False
    overlay_state = _provider_overlay_read_state(session)
    overlay_state.mode = normalized
    overlay_state.render_state = None
    invalidate_plan_provider_document_cache(session)
    session.selection.refresh.clear_hidden_provider_preselection()
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )
    session.task_panels.refresh_provider_overlay_mode_panels()
    return True


def get_plan_provider_overlay_category(overlay):
    category = str(getattr(overlay, "category", "") or "").strip().lower()
    if category == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if category == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def is_plan_provider_overlay_enabled(session, overlay):
    key = get_plan_provider_overlay_visibility_key(
        getattr(overlay, "provider_id", ""),
        getattr(overlay, "key", ""),
    )
    if key is None:
        return True
    return _provider_overlay_read_state(session).visibility.get(key, True)


def is_plan_provider_overlay_visible_for_mode(session, overlay, mode=None):
    overlay_mode = normalize_plan_provider_overlay_mode(
        get_plan_provider_overlay_mode(session) if mode is None else mode
    )
    if overlay_mode == PLAN_PROVIDER_OVERLAY_MODE_ALL:
        return True
    return get_plan_provider_overlay_category(overlay) == overlay_mode


def is_plan_provider_overlay_visible(session, overlay):
    if not bool(getattr(overlay, "visible", True)):
        return False
    if not is_plan_provider_overlay_enabled(session, overlay):
        return False
    return is_plan_provider_overlay_visible_for_mode(session, overlay)


def set_plan_provider_overlay_visible(session, provider_id, overlay_key, visible):
    key = get_plan_provider_overlay_visibility_key(provider_id, overlay_key)
    if key is None:
        return
    visible = bool(visible)
    overlay_state = _provider_overlay_read_state(session)
    if visible:
        overlay_state.visibility.pop(key, None)
    else:
        overlay_state.visibility[key] = False
    overlay_state.render_state = None
    invalidate_plan_provider_document_cache(session)
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def queue_plan_provider_overlay_refresh(session):
    _provider_overlay_read_state(session).render_state = None
    invalidate_plan_provider_document_cache(session)
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def queue_plan_provider_overlay_sync(session):
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def normalize_plan_provider_target(
    provider_id: str,
    target: object,
) -> PlanProviderTargetSpec | None:
    if not isinstance(target, PlanProviderTargetSpec):
        return None
    key = _normalize_plan_provider_target_text(target.key)
    object_name = _normalize_plan_provider_target_text(target.object_name)
    if not key or not object_name:
        return None
    replacements = {}
    normalized_provider_id = _normalize_plan_provider_target_text(provider_id)
    if target.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    label = _normalize_plan_provider_target_text(target.label)
    if label != target.label:
        replacements["label"] = label
    document_name = _normalize_plan_provider_target_text(target.document_name)
    if document_name != target.document_name:
        replacements["document_name"] = document_name
    if object_name != target.object_name:
        replacements["object_name"] = object_name
    semantic_document_name = _normalize_plan_provider_target_text(target.semantic_document_name)
    if semantic_document_name != target.semantic_document_name:
        replacements["semantic_document_name"] = semantic_document_name
    semantic_object_name = _normalize_plan_provider_target_text(target.semantic_object_name)
    if semantic_object_name != target.semantic_object_name:
        replacements["semantic_object_name"] = semantic_object_name
    category = _normalize_plan_provider_target_text(target.category)
    if category != target.category:
        replacements["category"] = category
    role = _normalize_plan_provider_target_text(target.role)
    if role != target.role:
        replacements["role"] = role
    if key != target.key:
        replacements["key"] = key
    if not replacements:
        return target
    return replace(target, **replacements)


def get_plan_provider_targets(session) -> tuple[PlanProviderTargetSpec, ...]:
    external_targets = _get_external_provider_targets(session)
    if external_targets is not _MISSING:
        return external_targets
    depth = _get_provider_target_collection_depth(session)
    if depth > 0:
        return ()
    _set_provider_target_collection_depth(session, depth + 1)
    try:
        return collect_plan_provider_contributions(
            session,
            "get_targets",
            normalize_plan_provider_target,
        )
    finally:
        _set_provider_target_collection_depth(session, depth)


def get_plan_provider_target_for_object(session, obj) -> PlanProviderTargetSpec | None:
    if obj is None:
        return None
    object_key = _make_plan_provider_target_object_key(
        getattr(getattr(obj, "Document", None), "Name", "")
        or _get_default_plan_provider_target_document_name(session),
        getattr(obj, "Name", ""),
    )
    if object_key is None:
        return None
    external_target = _find_external_provider_target_for_object(session, object_key)
    if external_target is not _MISSING:
        return external_target
    return _get_plan_provider_target_lookup(session).get(object_key)


def is_plan_provider_target_object(session, obj) -> bool:
    return get_plan_provider_target_for_object(session, obj) is not None


def is_plan_provider_target_visible_for_mode(session, obj, mode=None) -> bool:
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return False
    return bool(is_plan_provider_overlay_visible_for_mode(session, target, mode=mode))


def get_plan_provider_target_role_key(session, obj) -> str:
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return ""
    return str(target.role or "").strip()


def get_plan_provider_target_role_label(session, obj) -> str:
    role = get_plan_provider_target_role_key(session, obj)
    if not role:
        return translate("BIM_PlanEdit", "Object")
    return role.replace("_", " ").title()


def format_plan_provider_target_help(session, obj) -> str:
    from bimplan.providers import edit as plan_provider_edit

    if not is_plan_provider_target_object(session, obj):
        return ""
    role = get_plan_provider_target_role_key(session, obj).replace("_", " ").lower()
    has_handles = False
    try:
        has_handles = bool(
            session.selection.state.is_selected_plan_target("provider", obj)
        ) and bool(tuple(plan_provider_edit.get_selected_provider_edit_handles(session, obj) or ()))
    except Exception:
        has_handles = False
    if role:
        if has_handles:
            return translate(
                "BIM_PlanEdit",
                "Use in-view handles or the integration details below for the selected {role}.",
            ).format(role=role)
        return translate(
            "BIM_PlanEdit",
            "Use the integration details and actions below for the selected {role}.",
        ).format(role=role)
    if has_handles:
        return translate(
            "BIM_PlanEdit",
            "Use in-view handles or the integration details below for the selected object.",
        )
    return translate(
        "BIM_PlanEdit",
        "Use the integration details and actions below for the selected object.",
    )


def _get_provider_target_semantic_resolution(session, semantic_obj, provider_target):
    semantic_resolved = None
    if provider_target is not None:
        semantic_resolved = session.selection.targets.resolve_plan_semantic_object(provider_target)
        if semantic_resolved is not None:
            semantic_obj = semantic_resolved
    return semantic_obj, semantic_resolved


def _build_provider_target_display_fields(semantic_obj, fallback_label):
    semantic_doc = getattr(semantic_obj, "Document", None)
    return _PlanProviderTargetDisplayFields(
        label=str(fallback_label or ""),
        semantic_document_name=str(getattr(semantic_doc, "Name", "") or ""),
        semantic_object_name=str(getattr(semantic_obj, "Name", "") or ""),
        semantic_label=str(getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""),
    )


def _apply_provider_target_display_overrides(fields, provider_target, semantic_resolved):
    provider_label = str(provider_target.label or "").strip()
    if provider_label:
        fields.label = provider_label
    fields.provider_id = str(provider_target.provider_id or "").strip()
    fields.target_key = str(provider_target.key or "").strip()
    fields.category = str(provider_target.category or "").strip()
    fields.role = str(provider_target.role or "").strip()
    fields.semantic_document_name = str(
        provider_target.semantic_document_name or fields.semantic_document_name
    ).strip()
    fields.semantic_object_name = str(
        provider_target.semantic_object_name or fields.semantic_object_name
    ).strip()
    if semantic_resolved is not None:
        fields.semantic_label = str(
            getattr(semantic_resolved, "Label", getattr(semantic_resolved, "Name", "")) or ""
        )


def resolve_plan_provider_target_display_fields(
    session,
    semantic_obj,
    provider_target: PlanProviderTargetSpec | None,
    fallback_label,
) -> _PlanProviderTargetDisplayFields:
    semantic_obj, semantic_resolved = _get_provider_target_semantic_resolution(
        session,
        semantic_obj,
        provider_target,
    )
    fields = _build_provider_target_display_fields(semantic_obj, fallback_label)
    if provider_target is None:
        return fields
    _apply_provider_target_display_overrides(fields, provider_target, semantic_resolved)
    return fields


def _get_plan_semantic_record_fields(session, semantic_obj, target_kind):
    space_label = session.visibility.get_plan_text_property(
        semantic_obj,
        ("SpaceLabel", "RoomLabel", "Label"),
    )
    source_space_name = session.visibility.get_plan_text_property(
        semantic_obj,
        ("SourceSpaceName",),
    )
    if target_kind == "space" and not source_space_name:
        source_space_name = str(getattr(semantic_obj, "Name", "") or "")
    usage_category = session.visibility.get_plan_text_property(
        semantic_obj,
        ("UsageCategory", "SpaceType"),
    )
    return {
        "space_key": session.visibility.get_plan_text_property(semantic_obj, ("SpaceKey",)),
        "space_label": str(space_label or ""),
        "source_space_name": str(source_space_name or ""),
        "usage_category": str(usage_category or ""),
        "object_role": session.visibility.get_plan_text_property(semantic_obj, ("ObjectRole",)),
        "semantic_preset": session.visibility.get_plan_text_property(
            semantic_obj, ("SemanticPreset",)
        ),
        "host_ref": session.selection.targets.get_plan_host_ref(semantic_obj),
        "mount_height_mm": session.visibility.get_plan_float_property(
            semantic_obj,
            ("MountHeight", "MEPMountHeight", "PlumbingMountHeight"),
        ),
        "requirement_tags": session.selection.targets.normalize_plan_requirement_tags(
            getattr(semantic_obj, "RequirementTags", None)
        ),
    }


def build_plan_semantic_record(session, target_kind, target_obj):
    if not target_kind or target_obj is None:
        return None
    semantic_obj = session.visibility.get_plan_semantic_object(target_obj)
    if semantic_obj is None:
        return None
    doc = getattr(target_obj, "Document", None)
    semantic_doc = getattr(semantic_obj, "Document", None)
    fields = _get_plan_semantic_record_fields(session, semantic_obj, target_kind)
    return PlanSemanticRecord(
        target_kind=str(target_kind or ""),
        document_name=str(getattr(doc, "Name", "") or ""),
        object_name=str(getattr(target_obj, "Name", "") or ""),
        label=str(getattr(target_obj, "Label", getattr(target_obj, "Name", "")) or ""),
        semantic_document_name=str(getattr(semantic_doc, "Name", "") or ""),
        semantic_object_name=str(getattr(semantic_obj, "Name", "") or ""),
        semantic_label=str(getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""),
        space_key=fields["space_key"],
        space_label=fields["space_label"],
        source_space_name=fields["source_space_name"],
        usage_category=fields["usage_category"],
        object_role=fields["object_role"],
        semantic_preset=fields["semantic_preset"],
        host_ref=fields["host_ref"],
        mount_height_mm=fields["mount_height_mm"],
        requirement_tags=fields["requirement_tags"],
    )


def get_plan_semantic_records(session, targets=None):
    from bimplan.selection.targets import PlanTarget

    if targets is None:
        targets = _call_provider_method(
            session, "get_plan_targets", selected_only=True, default=None
        )
        if targets is None:
            targets = session.selection.targets.get_plan_targets(selected_only=True)
    records = []
    for target in targets or ():
        target_kind = None
        target_obj = None
        if isinstance(target, PlanTarget):
            target_kind = target.kind
            target_obj = session.selection.targets.resolve_plan_target_object(target)
        else:
            try:
                target_kind, target_obj = target
            except Exception:
                continue
        record = build_plan_semantic_record(session, target_kind, target_obj)
        if record is not None:
            records.append(record)
    return tuple(records)


def get_plan_provider_id(provider):
    if provider is None:
        return ""
    getter = getattr(provider, "get_provider_id", None)
    if callable(getter):
        try:
            provider_id = str(getter() or "").strip()
        except Exception:
            provider_id = ""
        if provider_id:
            return provider_id
    return str(getattr(provider, "provider_id", "") or "").strip()


def coerce_plan_provider_results(result):
    if result is None:
        return ()
    if isinstance(result, (str, bytes)):
        return ()
    try:
        return tuple(result)
    except TypeError:
        return (result,)


def normalize_plan_provider_action(provider_id, action):
    if not isinstance(action, PlanActionSpec):
        return None
    if action.provider_id == provider_id:
        return action
    return replace(action, provider_id=str(provider_id or ""))


def normalize_plan_provider_tool(provider_id, tool):
    if not isinstance(tool, PlanToolSpec):
        return None
    if not isinstance(tool.interaction, PlanToolInteraction):
        return None
    if tool.provider_id == provider_id:
        return tool
    return replace(tool, provider_id=str(provider_id or ""))


def _normalize_plan_provider_edit_handle_scalars(handle):
    return {
        "key": str(handle.key or "").strip(),
        "label": str(handle.label or "").strip(),
        "tooltip": str(handle.tooltip or "").strip(),
        "target_key": str(handle.target_key or "").strip(),
        "action_key": str(handle.action_key or "").strip(),
        "transaction_label": str(handle.transaction_label or "").strip(),
        "prompt": str(handle.prompt or "").strip(),
        "role": str(handle.role or "").strip(),
    }


def _collect_plan_provider_edit_handle_replacements(provider_id, handle, key, point, fields):
    replacements = {}
    normalized_provider_id = str(provider_id or "")
    if handle.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    if key != handle.key:
        replacements["key"] = key
    if point != handle.point:
        replacements["point"] = point
    for field_name in (
        "label",
        "tooltip",
        "target_key",
        "transaction_label",
        "prompt",
        "role",
    ):
        field_value = fields[field_name]
        if field_value != getattr(handle, field_name):
            replacements[field_name] = field_value
    action_key = fields["action_key"] or key
    if action_key != handle.action_key:
        replacements["action_key"] = action_key
    return replacements


def normalize_plan_provider_edit_handle(provider_id, handle):
    if not isinstance(handle, PlanEditHandleSpec):
        return None
    if not isinstance(handle.interaction, PlanToolInteraction):
        return None
    if not isinstance(handle.marker_kind, PlanOverlayMarkerKind):
        return None
    key = str(handle.key or "").strip()
    point = _coerce_plan_overlay_point(handle.point)
    if not key or point is None:
        return None
    fields = _normalize_plan_provider_edit_handle_scalars(handle)
    replacements = _collect_plan_provider_edit_handle_replacements(
        provider_id,
        handle,
        key,
        point,
        fields,
    )
    if not replacements:
        return handle
    return replace(handle, **replacements)


def _normalize_plan_provider_actions(session, provider_id, actions):
    return tuple(
        normalized
        for normalized in (
            normalize_plan_provider_action(provider_id, action) for action in (actions or ())
        )
        if normalized is not None
    )


def _set_normalized_plan_provider_id(replacements, value, provider_id):
    normalized_provider_id = str(provider_id or "")
    if value != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id


def _set_normalized_text_field(replacements, field_name, value):
    normalized_value = str(value or "").strip()
    if normalized_value != value:
        replacements[field_name] = normalized_value
    return normalized_value


def _normalize_plan_provider_context_rows(rows):
    return tuple(
        normalized
        for normalized in (normalize_plan_provider_context_row(row) for row in (rows or ()))
        if normalized is not None
    )


def normalize_plan_provider_issue(session, provider_id, issue):
    if not isinstance(issue, PlanIssueSpec):
        return None
    if not isinstance(issue.severity, PlanIssueSeverity):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, issue.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, issue.provider_id, provider_id)
    if actions != tuple(issue.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return issue
    return replace(issue, **replacements)


def normalize_plan_provider_suggestion(session, provider_id, suggestion):
    if not isinstance(suggestion, PlanSuggestionSpec):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, suggestion.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, suggestion.provider_id, provider_id)
    if actions != tuple(suggestion.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return suggestion
    return replace(suggestion, **replacements)


def normalize_plan_provider_section(session, provider_id, section):
    if not isinstance(section, PlanInspectorSection):
        return None
    actions = _normalize_plan_provider_actions(session, provider_id, section.actions)
    replacements = {}
    _set_normalized_plan_provider_id(replacements, section.provider_id, provider_id)
    if actions != tuple(section.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return section
    return replace(section, **replacements)


def normalize_plan_provider_context_row(row):
    if not isinstance(row, PlanContextRowSpec):
        return None
    replacements = {}
    label = _set_normalized_text_field(replacements, "label", row.label)
    value = _set_normalized_text_field(replacements, "value", row.value)
    if not label:
        return None
    if not replacements:
        return row
    return replace(row, **replacements)


def normalize_plan_provider_context_detail(detail):
    if not isinstance(detail, PlanContextDetailSpec):
        return None
    rows = _normalize_plan_provider_context_rows(detail.rows)
    replacements = {}
    key = _set_normalized_text_field(replacements, "key", detail.key)
    title = _set_normalized_text_field(replacements, "title", detail.title)
    body = _set_normalized_text_field(replacements, "body", detail.body)
    if not key or not title:
        return None
    if rows != tuple(detail.rows or ()):
        replacements["rows"] = rows
    if not replacements:
        return detail
    return replace(detail, **replacements)


def normalize_plan_provider_context_panel(session, provider_id, panel):
    if not isinstance(panel, PlanContextPanelSpec):
        return None
    if not isinstance(panel.state, PlanContextPanelState):
        return None
    if not isinstance(panel.subject_kind, PlanContextSubjectKind):
        return None
    summary_rows = _normalize_plan_provider_context_rows(panel.summary_rows)
    details = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_detail(detail) for detail in (panel.details or ())
        )
        if normalized is not None
    )
    primary_action = None
    if panel.primary_action is not None:
        primary_action = normalize_plan_provider_action(
            provider_id,
            panel.primary_action,
        )
        if primary_action is None:
            return None
    secondary_actions = _normalize_plan_provider_actions(
        session,
        provider_id,
        panel.secondary_actions,
    )
    replacements = {}
    key = _set_normalized_text_field(replacements, "key", panel.key)
    title = _set_normalized_text_field(replacements, "title", panel.title)
    subtitle = _set_normalized_text_field(replacements, "subtitle", panel.subtitle)
    message = _set_normalized_text_field(replacements, "message", panel.message)
    if not key or not title:
        return None
    _set_normalized_plan_provider_id(replacements, panel.provider_id, provider_id)
    if summary_rows != tuple(panel.summary_rows or ()):
        replacements["summary_rows"] = summary_rows
    if primary_action != panel.primary_action:
        replacements["primary_action"] = primary_action
    if secondary_actions != tuple(panel.secondary_actions or ()):
        replacements["secondary_actions"] = secondary_actions
    if details != tuple(panel.details or ()):
        replacements["details"] = details
    if not replacements:
        return panel
    return replace(panel, **replacements)


_SESSION_AWARE_PROVIDER_NORMALIZERS = {
    normalize_plan_provider_issue,
    normalize_plan_provider_suggestion,
    normalize_plan_provider_section,
    normalize_plan_provider_context_panel,
}


def _normalize_plan_overlay_target_keys(target_keys):
    raw_target_keys = tuple(target_keys or ())
    normalized_target_keys = tuple(str(key or "") for key in raw_target_keys if key)
    return raw_target_keys, normalized_target_keys


def _normalize_plan_overlay_points_and_targets(overlay):
    raw_points = tuple(overlay.points or ())
    raw_point_targets = tuple(overlay.point_targets or ())
    point_pairs = []
    for index, raw_point in enumerate(raw_points):
        point = _coerce_plan_overlay_point(raw_point)
        if point is None:
            continue
        target = None
        if raw_point_targets:
            raw_target = raw_point_targets[index] if index < len(raw_point_targets) else None
            target = _normalize_plan_overlay_target(raw_target)
            if raw_target is not None and target is None:
                return None, None, None
        point_pairs.append((point, target))
    points = tuple(point for point, _target in point_pairs)
    point_targets = None
    if raw_point_targets:
        point_targets = tuple(target or PlanOverlayTargetSpec() for _point, target in point_pairs)
    return raw_points, raw_point_targets, (points, point_targets)


def _normalize_plan_overlay_polylines(polylines):
    normalized_polylines = tuple(
        _coerce_plan_overlay_polyline(polyline) for polyline in tuple(polylines or ())
    )
    return tuple(polyline for polyline in normalized_polylines if len(polyline) >= 2)


def _collect_overlay_normalization_replacements(provider_id, overlay):
    replacements = {}
    if overlay.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")

    raw_target_keys, target_keys = _normalize_plan_overlay_target_keys(overlay.target_keys)
    if target_keys != raw_target_keys:
        replacements["target_keys"] = target_keys

    raw_points, raw_point_targets, point_data = _normalize_plan_overlay_points_and_targets(overlay)
    if point_data is None:
        return None
    points, point_targets = point_data
    if points != raw_points:
        replacements["points"] = points
    if raw_point_targets and point_targets != raw_point_targets:
        replacements["point_targets"] = point_targets

    polylines = _normalize_plan_overlay_polylines(overlay.polylines)
    if polylines != tuple(overlay.polylines or ()):
        replacements["polylines"] = polylines

    color = _coerce_plan_overlay_color(overlay.color)
    if color != overlay.color:
        replacements["color"] = color
    return replacements


def normalize_plan_provider_overlay(provider_id, overlay):
    if not isinstance(overlay, PlanOverlaySpec):
        return None
    if not isinstance(overlay.marker_kind, PlanOverlayMarkerKind):
        return None
    replacements = _collect_overlay_normalization_replacements(provider_id, overlay)
    if replacements is None:
        return None
    if not replacements:
        return overlay
    return replace(overlay, **replacements)


def _normalize_plan_overlay_target(target):
    if target is None:
        return PlanOverlayTargetSpec()
    if not isinstance(target, PlanOverlayTargetSpec):
        return None
    if target.target_kind is not None and not isinstance(target.target_kind, PlanOverlayTargetKind):
        return None
    document_name = str(target.document_name or "").strip()
    object_name = str(target.object_name or "").strip()
    subname = str(target.subname or "").strip()
    replacements = {}
    if document_name != target.document_name:
        replacements["document_name"] = document_name
    if object_name != target.object_name:
        replacements["object_name"] = object_name
    if subname != target.subname:
        replacements["subname"] = subname
    if not replacements:
        return target
    return replace(target, **replacements)


def _coerce_plan_overlay_point_from_attributes(point):
    try:
        return (
            float(point.x),
            float(point.y),
            float(getattr(point, "z", 0.0) or 0.0),
        )
    except AttributeError:
        return _MISSING


def _coerce_plan_overlay_point_from_sequence(point):
    try:
        z_value = point[2] if len(point) > 2 else 0.0
        return (float(point[0]), float(point[1]), float(z_value))
    except (TypeError, ValueError, IndexError):
        return None


def _coerce_plan_overlay_point(point):
    coerced = _coerce_plan_overlay_point_from_attributes(point)
    if coerced is not _MISSING:
        return coerced
    return _coerce_plan_overlay_point_from_sequence(point)


def _coerce_plan_overlay_polyline(polyline):
    points = []
    for point in tuple(polyline or ()):
        coerced = _coerce_plan_overlay_point(point)
        if coerced is not None:
            points.append(coerced)
    return tuple(points)


def _coerce_plan_overlay_color(color):
    try:
        values = tuple(float(value) for value in tuple(color or ()))
    except (TypeError, ValueError):
        return (0.2, 0.55, 0.85)
    if len(values) < 3:
        return (0.2, 0.55, 0.85)
    return values[:3]


def collect_plan_provider_contributions(session, method_name, normalizer):
    with _perf_trace_span(session, f"collect_plan_provider_contributions_{method_name}"):
        if not _is_active_provider_session(session):
            _perf_count(session, "plan_provider_inactive_session")
            return ()
        if plan_provider_integrations_disabled(session):
            _perf_count(session, "plan_provider_integrations_disabled")
            return ()
        cached_contributions = _get_cached_provider_contributions(session, method_name)
        if cached_contributions is not None:
            return cached_contributions
        context = _get_plan_edit_context_or_none(session)
        if context is None:
            return ()
        cached_contributions = _get_document_cached_provider_contributions(
            session, context, method_name
        )
        if cached_contributions is not None:
            _set_cached_provider_contributions(session, method_name, cached_contributions)
            return cached_contributions
        contributions = _collect_plan_provider_contributions_for_method(
            session,
            context,
            method_name,
            normalizer,
        )
        _set_cached_provider_contributions(session, method_name, contributions)
        _set_document_cached_provider_contributions(session, context, method_name, contributions)
        return contributions


def _get_plan_provider_contributions(session, api_method_name, provider_method_name, normalizer):
    external_results = _call_provider_method(session, api_method_name, default=None)
    if external_results is not None:
        return tuple(external_results or ())
    return collect_plan_provider_contributions(
        session,
        provider_method_name,
        normalizer,
    )


def get_plan_provider_edit_handles(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_edit_handles",
        "get_edit_handles",
        normalize_plan_provider_edit_handle,
    )


def get_plan_provider_issues(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_issues",
        "get_issues",
        normalize_plan_provider_issue,
    )


def get_plan_provider_suggestions(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_suggestions",
        "get_suggestions",
        normalize_plan_provider_suggestion,
    )


def get_plan_provider_tools(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_tools",
        "get_tools",
        normalize_plan_provider_tool,
    )


def get_plan_provider_inspector_sections(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_inspector_sections",
        "get_inspector_sections",
        normalize_plan_provider_section,
    )


def get_plan_provider_context_panels(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_context_panels",
        "get_context_panels",
        normalize_plan_provider_context_panel,
    )


def get_plan_provider_overlays(session):
    return _get_plan_provider_contributions(
        session,
        "get_plan_provider_overlays",
        "get_overlays",
        normalize_plan_provider_overlay,
    )


def get_plan_provider_snapshot(session):
    if not _is_active_provider_session(session):
        _perf_count(session, "plan_provider_inactive_session")
        return PlanProviderSnapshot()
    if plan_provider_integrations_disabled(session):
        _perf_count(session, "plan_provider_integrations_disabled")
        return PlanProviderSnapshot()
    return collect_plan_provider_snapshot(session)


def _execute_plan_provider_action_callback(
    execute_action,
    action_key,
    context,
    action_context,
    payload,
):
    if payload is None:
        return execute_action(action_key, context, action_context)
    return execute_action(action_key, context, action_context, payload)


def _get_plan_provider_action_executor(session, provider_id):
    provider = _get_plan_provider_registry(session).get_provider(provider_id)
    if provider is None:
        return None
    execute_action = getattr(provider, "execute_action", None)
    if not callable(execute_action):
        return None
    return execute_action


def _run_plan_provider_action(
    session,
    execute_action,
    action_key,
    transaction_label="",
    payload=None,
):
    context = _get_plan_edit_context_or_none(session)
    if context is None:
        return False
    action_context = get_plan_provider_action_context(session, payload=payload)
    transaction_label = str(transaction_label or "").strip()
    with _get_document_visual_update_scope(session):
        if transaction_label:
            with PlanEditTransaction(session.doc, transaction_label):
                handled = _execute_plan_provider_action_callback(
                    execute_action,
                    action_key,
                    context,
                    action_context,
                    payload,
                )
        else:
            handled = _execute_plan_provider_action_callback(
                execute_action,
                action_key,
                context,
                action_context,
                payload,
            )
        if handled is not False:
            try:
                if session.doc is not None:
                    session.doc.recompute()
            except Exception:
                pass
    return handled


def _finalize_plan_provider_action(session):
    session.selection.refresh.refresh_primary_selected_plan_target()
    session.document_visuals.invalidate_document_dependent_plan_visuals()
    session.task_panels.refresh_task_panel_status()
    session.viewport.focus_plan_view()


def execute_plan_provider_action(
    session,
    provider_id,
    action_key,
    transaction_label="",
    payload=None,
):
    if not session.document_visuals.document_is_alive():
        return False
    execute_action = _get_plan_provider_action_executor(session, provider_id)
    if execute_action is None:
        return False

    try:
        handled = _run_plan_provider_action(
            session,
            execute_action,
            action_key,
            transaction_label=transaction_label,
            payload=payload,
        )
    except Exception as exc:
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider '{provider}' action '{action}' failed: {error}\n",
            ).format(provider=provider_id, action=action_key, error=exc)
        )
        return False

    if handled is False:
        return False

    _finalize_plan_provider_action(session)
    return True


def get_plan_edit_context(session):
    doc = getattr(session, "doc", None)
    if not session.document_visuals.document_is_alive():
        doc = None
    active_storey = getattr(session, "active_storey", None)
    active_storey_name = session.visibility.safe_plan_object_name(active_storey)
    document_name = session.visibility.safe_plan_object_name(doc)
    if active_storey is not None and not active_storey_name:
        active_storey = None
        session.active_storey = None
    return PlanEditContext(
        session=session,
        document_name=document_name,
        active_storey_name=active_storey_name,
        active_storey_label=str(session.storey.get_storey_label(active_storey) or ""),
        current_tool=str(getattr(session, "current_tool", "") or ""),
    )


def get_plan_provider_action_context(session, payload=None):
    action_context = _call_provider_method(
        session,
        "get_plan_provider_action_context",
        payload=payload,
        default=_MISSING,
    )
    if action_context is not _MISSING:
        return action_context
    doc = session.doc if session.document_visuals.document_is_alive() else None
    return PlanEditContext.make_action_context(
        session,
        payload=payload,
        document_name=session.visibility.safe_plan_object_name(doc),
        current_tool=str(session.current_tool or ""),
    )


def _normalize_plan_provider_target_text(value: object) -> str:
    return str(value or "").strip()


def _get_default_plan_provider_target_document_name(session) -> str:
    return _normalize_plan_provider_target_text(getattr(getattr(session, "doc", None), "Name", ""))


def _make_plan_provider_target_object_key(
    document_name: object,
    object_name: object,
) -> tuple[str, str] | None:
    normalized_object_name = _normalize_plan_provider_target_text(object_name)
    if not normalized_object_name:
        return None
    return (
        _normalize_plan_provider_target_text(document_name),
        normalized_object_name,
    )


def _get_plan_provider_target_lookup(session) -> dict[tuple[str, str], PlanProviderTargetSpec]:
    refresh_cache = _get_provider_refresh_cache(session)
    cache_key = ("provider_targets", "by_object")
    if isinstance(refresh_cache, dict) and cache_key in refresh_cache:
        return refresh_cache[cache_key]

    context = _get_plan_edit_context_or_none(session)
    document_cache = _get_provider_document_cache(session)
    document_cache_key = None
    if context is not None and document_cache is not None:
        document_cache_key = (
            "provider_targets",
            "by_object",
        ) + _make_provider_target_context_cache_key(context)
        cached_lookup = document_cache.get(document_cache_key)
        if isinstance(cached_lookup, dict):
            if isinstance(refresh_cache, dict):
                refresh_cache[cache_key] = cached_lookup
            return cached_lookup

    default_document_name = _get_default_plan_provider_target_document_name(session)
    targets_by_object = {}
    for target in tuple(get_plan_provider_targets(session) or ()):
        target_key = _make_plan_provider_target_object_key(
            target.document_name or default_document_name,
            target.object_name,
        )
        if target_key is None or target_key in targets_by_object:
            continue
        targets_by_object[target_key] = target

    if isinstance(refresh_cache, dict):
        refresh_cache[cache_key] = targets_by_object
    if document_cache_key is not None and document_cache is not None:
        document_cache[document_cache_key] = targets_by_object
    return targets_by_object


PlanProvidersAPI.get_plan_provider_overlay_visibility_key = staticmethod(
    get_plan_provider_overlay_visibility_key
)

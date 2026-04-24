# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from contextlib import nullcontext
from dataclasses import dataclass, replace
from functools import wraps
from typing import TypedDict

import FreeCAD

from bimplan import document_visuals as plan_document_visuals
from . import (
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
    return session.performance.plan_perf_count(name, delta=delta)


class _PlanProviderTargetDisplayFields(TypedDict):
    label: str
    provider_id: str
    target_key: str
    category: str
    role: str
    semantic_document_name: str
    semantic_object_name: str
    semantic_label: str


_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY = ("provider_snapshot", "panel")


def _bind_provider_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


_PLAN_PROVIDERS_API_BOUND_METHODS = (
    "plan_provider_integrations_disabled",
    "get_plan_provider_id",
    "coerce_plan_provider_results",
    "normalize_plan_provider_action",
    "normalize_plan_provider_tool",
    "normalize_plan_provider_edit_handle",
    "normalize_plan_provider_issue",
    "normalize_plan_provider_suggestion",
    "normalize_plan_provider_section",
    "normalize_plan_provider_context_panel",
    "normalize_plan_provider_overlay",
    "normalize_plan_provider_target",
    "collect_plan_provider_contributions",
    "get_plan_provider_display_name",
    "get_plan_provider_issues",
    "get_plan_provider_suggestions",
    "get_plan_provider_tools",
    "get_plan_provider_snapshot",
    "get_plan_provider_edit_handles",
    "get_plan_provider_inspector_sections",
    "get_plan_provider_context_panels",
    "get_plan_provider_overlays",
    "get_plan_provider_overlay_mode",
    "set_plan_provider_overlay_mode",
    "get_plan_provider_overlay_visibility_key",
    "get_plan_provider_targets",
    "get_plan_provider_target_for_object",
    "is_plan_provider_target_object",
    "is_plan_provider_overlay_enabled",
    "set_plan_provider_overlay_mode",
    "is_plan_provider_overlay_visible_for_mode",
    "is_plan_provider_overlay_visible",
    "set_plan_provider_overlay_visible",
    "queue_plan_provider_overlay_refresh",
    "queue_plan_provider_overlay_sync",
    "build_plan_semantic_record",
    "get_plan_semantic_records",
)


class PlanProvidersAPI:
    """Owned session surface for Plan Edit provider behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_plan_edit_context(self):
        return get_plan_edit_context(self.session)

    def get_plan_provider_action_context(self, payload=None):
        return get_plan_provider_action_context(self.session, payload=payload)

    def plan_provider_refresh_cache_scope(self):
        return plan_provider_refresh_cache_scope(self.session)

    def invalidate_plan_provider_document_cache(self):
        return invalidate_plan_provider_document_cache(self.session)

    def get_provider_point_tool_label(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.get_provider_point_tool_label(self.session)

    def get_provider_point_tool_prompt(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.get_provider_point_tool_prompt(self.session)

    def has_active_provider_point_tool(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.has_active_provider_point_tool(self.session)

    def arm_provider_point_tool(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.arm_provider_point_tool(self.session)

    def cancel_provider_point_tool(self, refresh=True):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.cancel_provider_point_tool(self.session, refresh=refresh)

    def start_plan_provider_point_tool(self, tool):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.start_plan_provider_point_tool(self.session, tool)

    def handle_provider_point_tool_point(self, point=None, obj=None):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.handle_provider_point_tool_point(
            self.session,
            point=point,
            obj=obj,
        )

    def update_provider_point_tool_preview(self, point=None, obj=None):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.update_provider_point_tool_preview(
            self.session,
            point=point,
            obj=obj,
        )

    def get_provider_point_snap_info(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.get_provider_point_snap_info()

    def resolve_provider_point_snap_object(self, snap_object, snap_info):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.resolve_provider_point_snap_object(
            self.session,
            snap_object,
            snap_info,
        )

    def normalize_provider_point_host_target(self, target):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.normalize_provider_point_host_target(self.session, target)

    def get_provider_point_context_host_state(self):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.get_provider_point_context_host_state(self.session)

    def get_provider_point_payload_host_target(
        self,
        *,
        snap_target,
        selected_target,
        selected_targets,
        hovered_target,
    ):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.get_provider_point_payload_host_target(
            self.session,
            snap_target=snap_target,
            selected_target=selected_target,
            selected_targets=selected_targets,
            hovered_target=hovered_target,
        )

    def project_provider_point_to_host(self, point, host_wall):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.project_provider_point_to_host(point, host_wall)

    def build_provider_point_tool_payload(
        self,
        tool,
        *,
        raw_point,
        plan_point,
        snap_object,
        snap_info,
    ):
        from bimplan.providers import point as plan_provider_point

        return plan_provider_point.build_provider_point_tool_payload(
            self.session,
            tool,
            raw_point=raw_point,
            plan_point=plan_point,
            snap_object=snap_object,
            snap_info=snap_info,
        )

    def get_selected_provider_edit_handles(self, provider_obj):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.get_selected_provider_edit_handles(self.session, provider_obj)

    def can_move_provider_target_by_placement(self, provider_obj):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.can_move_provider_target_by_placement(self.session, provider_obj)

    def activate_provider_handle(self, provider_obj, handle_index):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.activate_provider_handle(self.session, provider_obj, handle_index)

    def activate_provider_handle_now(self, provider_obj, handle_index):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.activate_provider_handle_now(
            self.session, provider_obj, handle_index
        )

    def start_provider_handle_point_pick(self, provider_obj, handle_index, handle):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.start_provider_handle_point_pick(
            self.session,
            provider_obj,
            handle_index,
            handle,
        )

    def update_provider_handle_point_pick(self, point=None, snap_info=None):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.update_provider_handle_point_pick(
            self.session,
            point=point,
            snap_info=snap_info,
        )

    def finish_provider_handle_point_pick(self, point=None, obj=None):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.finish_provider_handle_point_pick(
            self.session,
            point=point,
            obj=obj,
        )

    def cancel_provider_handle_point_pick(self):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.cancel_provider_handle_point_pick(self.session)

    def restore_selected_provider(self, provider_obj):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.restore_selected_provider(self.session, provider_obj)

    def queue_restore_selected_provider(self, provider_obj):
        from bimplan.providers import edit as plan_provider_edit

        return plan_provider_edit.queue_restore_selected_provider(self.session, provider_obj)

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
            session._tearing_down
            or session._finishing
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


for _method_name in _PLAN_PROVIDERS_API_BOUND_METHODS:
    setattr(PlanProvidersAPI, _method_name, _bind_provider_call(globals()[_method_name]))


@dataclass(frozen=True)
class _PlanProviderSnapshotSurfaceSpec:
    field_name: str
    method_name: str
    normalizer_name: str


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


_PLAN_PROVIDER_SNAPSHOT_SURFACES = (
    _PlanProviderSnapshotSurfaceSpec(
        field_name="tools",
        method_name="get_tools",
        normalizer_name="normalize_plan_provider_tool",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="overlays",
        method_name="get_overlays",
        normalizer_name="normalize_plan_provider_overlay",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="issues",
        method_name="get_issues",
        normalizer_name="normalize_plan_provider_issue",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="context_panels",
        method_name="get_context_panels",
        normalizer_name="normalize_plan_provider_context_panel",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="inspector_sections",
        method_name="get_inspector_sections",
        normalizer_name="normalize_plan_provider_section",
    ),
)


def _is_active_provider_session(session):
    return not (
        getattr(session, "_tearing_down", False)
        or getattr(session, "_finishing", False)
        or not session.document_visuals.document_is_alive()
    )


def plan_provider_integrations_disabled(session):
    import os

    env_value = str(os.environ.get("FC_BIM_PLAN_EDIT_DISABLE_INTEGRATIONS", "") or "").strip()
    if env_value:
        return env_value not in {"0", "false", "False", "no", "off"}
    try:
        return bool(session._plan_edit_params.GetBool("DisableIntegrations", False))
    except Exception:
        return False


def invalidate_plan_provider_document_cache(session):
    session._plan_provider_document_cache = {}


@contextmanager
def plan_provider_refresh_cache_scope(session):
    previous_cache = session._plan_provider_refresh_cache
    session._plan_provider_refresh_cache = {}
    try:
        yield session._plan_provider_refresh_cache
    finally:
        session._plan_provider_refresh_cache = previous_cache


def _get_provider_refresh_cache(session):
    refresh_cache = getattr(session, "_plan_provider_refresh_cache", None)
    if isinstance(refresh_cache, dict):
        return refresh_cache
    return None


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
    for contribution in session.providers.coerce_plan_provider_results(provided):
        normalized = normalizer(provider_id, contribution)
        if normalized is not None:
            results.append(normalized)

    _perf_count(
        session,
        "plan_provider_{}_{}_contributions".format(provider_id, method_name),
        len(results),
    )
    return tuple(results)


def collect_plan_provider_snapshot(session) -> PlanProviderSnapshot:
    with _perf_trace_span(session, "collect_plan_provider_snapshot"):
        if not session.document_visuals.document_is_alive():
            return PlanProviderSnapshot()

        refresh_cache = _get_provider_refresh_cache(session)
        if refresh_cache is not None:
            cached_snapshot = refresh_cache.get(_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY)
            if isinstance(cached_snapshot, PlanProviderSnapshot):
                return cached_snapshot

        try:
            context = session.providers.get_plan_edit_context()
        except (ReferenceError, RuntimeError):
            return PlanProviderSnapshot()

        collected = {
            surface_spec.field_name: [] for surface_spec in _PLAN_PROVIDER_SNAPSHOT_SURFACES
        }
        normalized_surfaces = tuple(
            (surface_spec, getattr(session.providers, surface_spec.normalizer_name))
            for surface_spec in _PLAN_PROVIDER_SNAPSHOT_SURFACES
        )

        for provider in session.get_plan_provider_registry().iter_providers():
            provider_id = session.providers.get_plan_provider_id(provider)
            if not provider_id:
                continue
            for surface_spec, normalizer in normalized_surfaces:
                contributions = _collect_provider_surface_contributions(
                    session,
                    provider,
                    provider_id,
                    context,
                    surface_spec.method_name,
                    normalizer,
                )
                if contributions:
                    collected[surface_spec.field_name].extend(contributions)

        snapshot = PlanProviderSnapshot(
            tools=tuple(collected["tools"]),
            overlays=tuple(collected["overlays"]),
            issues=tuple(collected["issues"]),
            context_panels=tuple(collected["context_panels"]),
            inspector_sections=tuple(collected["inspector_sections"]),
        )
        if refresh_cache is not None:
            refresh_cache[_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY] = snapshot
            for surface_spec in _PLAN_PROVIDER_SNAPSHOT_SURFACES:
                _set_cached_provider_contributions(
                    session,
                    surface_spec.method_name,
                    getattr(snapshot, surface_spec.field_name),
                )
        return snapshot


def get_plan_provider_display_name(session, provider_id):
    provider = session.get_plan_provider_registry().get_provider(provider_id)
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


def get_plan_provider_overlay_mode(session):
    state = getattr(session, "provider_overlay_read_state", None)
    mode = (
        getattr(state, "mode", PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE)
        if state is not None
        else getattr(session, "_provider_overlay_mode", PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE)
    )
    return normalize_plan_provider_overlay_mode(mode)


def is_focused_provider_overlay_pick_mode(mode):
    return normalize_plan_provider_overlay_mode(mode) in FOCUSED_PROVIDER_OVERLAY_PICK_MODES


def set_plan_provider_overlay_mode(session, mode):
    normalized = normalize_plan_provider_overlay_mode(mode)
    if normalized == get_plan_provider_overlay_mode(session):
        return False
    session._provider_overlay_mode = normalized
    session._provider_overlay_state = None
    session.selection.clear_hidden_provider_preselection()
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
    state = getattr(session, "provider_overlay_read_state", None)
    visibility = (
        getattr(state, "visibility", {})
        if state is not None
        else getattr(session, "_provider_overlay_visibility", {})
    )
    return visibility.get(key, True)


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
    if visible:
        session._provider_overlay_visibility.pop(key, None)
    else:
        session._provider_overlay_visibility[key] = False
    session._provider_overlay_state = None
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def queue_plan_provider_overlay_refresh(session):
    session._provider_overlay_state = None
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
    depth = int(getattr(session, "_plan_provider_target_collection_depth", 0) or 0)
    if depth > 0:
        return ()
    session._plan_provider_target_collection_depth = depth + 1
    try:
        return session.providers.collect_plan_provider_contributions(
            "get_targets",
            session.providers.normalize_plan_provider_target,
        )
    finally:
        session._plan_provider_target_collection_depth = depth


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
    return _get_plan_provider_target_lookup(session).get(object_key)


def is_plan_provider_target_object(session, obj) -> bool:
    return get_plan_provider_target_for_object(session, obj) is not None


def is_plan_provider_target_visible_for_mode(session, obj, mode=None) -> bool:
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return False
    return bool(session.providers.is_plan_provider_overlay_visible_for_mode(target, mode=mode))


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
    if not is_plan_provider_target_object(session, obj):
        return ""
    role = get_plan_provider_target_role_key(session, obj).replace("_", " ").lower()
    providers_api = getattr(session, "providers", None)
    get_handles = getattr(providers_api, "get_selected_provider_edit_handles", None)
    has_handles = False
    if callable(get_handles):
        try:
            has_handles = bool(session.selection.is_selected_plan_target("provider", obj)) and bool(
                tuple(get_handles(obj) or ())
            )
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


def resolve_plan_provider_target_display_fields(
    session,
    semantic_obj,
    provider_target: PlanProviderTargetSpec | None,
    fallback_label,
) -> _PlanProviderTargetDisplayFields:
    semantic_resolved = None
    if provider_target is not None:
        semantic_resolved = session.selection.resolve_plan_semantic_object(provider_target)
        if semantic_resolved is not None:
            semantic_obj = semantic_resolved

    semantic_doc = getattr(semantic_obj, "Document", None)
    fields = {
        "label": str(fallback_label or ""),
        "provider_id": "",
        "target_key": "",
        "category": "",
        "role": "",
        "semantic_document_name": str(getattr(semantic_doc, "Name", "") or ""),
        "semantic_object_name": str(getattr(semantic_obj, "Name", "") or ""),
        "semantic_label": str(
            getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""
        ),
    }
    if provider_target is None:
        return fields

    provider_label = str(provider_target.label or "").strip()
    if provider_label:
        fields["label"] = provider_label
    fields["provider_id"] = str(provider_target.provider_id or "").strip()
    fields["target_key"] = str(provider_target.key or "").strip()
    fields["category"] = str(provider_target.category or "").strip()
    fields["role"] = str(provider_target.role or "").strip()
    fields["semantic_document_name"] = str(
        provider_target.semantic_document_name or fields["semantic_document_name"]
    ).strip()
    fields["semantic_object_name"] = str(
        provider_target.semantic_object_name or fields["semantic_object_name"]
    ).strip()
    if semantic_resolved is not None:
        fields["semantic_label"] = str(
            getattr(semantic_resolved, "Label", getattr(semantic_resolved, "Name", "")) or ""
        )
    return fields


def build_plan_semantic_record(session, target_kind, target_obj):
    if not target_kind or target_obj is None:
        return None
    semantic_obj = session.visibility.get_plan_semantic_object(target_obj)
    if semantic_obj is None:
        return None
    doc = getattr(target_obj, "Document", None)
    semantic_doc = getattr(semantic_obj, "Document", None)
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
    requirement_tags = session.selection.normalize_plan_requirement_tags(
        getattr(semantic_obj, "RequirementTags", None)
    )
    return PlanSemanticRecord(
        target_kind=str(target_kind or ""),
        document_name=str(getattr(doc, "Name", "") or ""),
        object_name=str(getattr(target_obj, "Name", "") or ""),
        label=str(getattr(target_obj, "Label", getattr(target_obj, "Name", "")) or ""),
        semantic_document_name=str(getattr(semantic_doc, "Name", "") or ""),
        semantic_object_name=str(getattr(semantic_obj, "Name", "") or ""),
        semantic_label=str(getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""),
        space_key=session.visibility.get_plan_text_property(semantic_obj, ("SpaceKey",)),
        space_label=str(space_label or ""),
        source_space_name=str(source_space_name or ""),
        usage_category=str(usage_category or ""),
        object_role=session.visibility.get_plan_text_property(semantic_obj, ("ObjectRole",)),
        semantic_preset=session.visibility.get_plan_text_property(
            semantic_obj, ("SemanticPreset",)
        ),
        host_ref=session.selection.get_plan_host_ref(semantic_obj),
        mount_height_mm=session.visibility.get_plan_float_property(
            semantic_obj,
            ("MountHeight", "MEPMountHeight", "PlumbingMountHeight"),
        ),
        requirement_tags=requirement_tags,
    )


def get_plan_semantic_records(session, targets=None):
    from bimplan.selection.targets import PlanTarget

    if targets is None:
        targets = session.selection.get_plan_targets(selected_only=True)
    records = []
    for target in targets or ():
        target_kind = None
        target_obj = None
        if isinstance(target, PlanTarget):
            target_kind = target.kind
            target_obj = session.selection.resolve_plan_target_object(target)
        else:
            try:
                target_kind, target_obj = target
            except Exception:
                continue
        record = session.providers.build_plan_semantic_record(target_kind, target_obj)
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
    replacements = {}
    normalized_provider_id = str(provider_id or "")
    if handle.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    label = str(handle.label or "").strip()
    tooltip = str(handle.tooltip or "").strip()
    target_key = str(handle.target_key or "").strip()
    action_key = str(handle.action_key or "").strip()
    transaction_label = str(handle.transaction_label or "").strip()
    prompt = str(handle.prompt or "").strip()
    role = str(handle.role or "").strip()
    if key != handle.key:
        replacements["key"] = key
    if point != handle.point:
        replacements["point"] = point
    if label != handle.label:
        replacements["label"] = label
    if tooltip != handle.tooltip:
        replacements["tooltip"] = tooltip
    if target_key != handle.target_key:
        replacements["target_key"] = target_key
    if not action_key:
        action_key = key
    if action_key != handle.action_key:
        replacements["action_key"] = action_key
    if transaction_label != handle.transaction_label:
        replacements["transaction_label"] = transaction_label
    if prompt != handle.prompt:
        replacements["prompt"] = prompt
    if role != handle.role:
        replacements["role"] = role
    if not replacements:
        return handle
    return replace(handle, **replacements)


def normalize_plan_provider_issue(session, provider_id, issue):
    if not isinstance(issue, PlanIssueSpec):
        return None
    if not isinstance(issue.severity, PlanIssueSeverity):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session.providers.normalize_plan_provider_action(provider_id, action)
            for action in (issue.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if issue.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(issue.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return issue
    return replace(issue, **replacements)


def normalize_plan_provider_suggestion(session, provider_id, suggestion):
    if not isinstance(suggestion, PlanSuggestionSpec):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session.providers.normalize_plan_provider_action(provider_id, action)
            for action in (suggestion.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if suggestion.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(suggestion.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return suggestion
    return replace(suggestion, **replacements)


def normalize_plan_provider_section(session, provider_id, section):
    if not isinstance(section, PlanInspectorSection):
        return None
    actions = tuple(
        normalized
        for normalized in (
            session.providers.normalize_plan_provider_action(provider_id, action)
            for action in (section.actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    if section.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    if actions != tuple(section.actions or ()):
        replacements["actions"] = actions
    if not replacements:
        return section
    return replace(section, **replacements)


def normalize_plan_provider_context_row(row):
    if not isinstance(row, PlanContextRowSpec):
        return None
    replacements = {}
    label = str(row.label or "").strip()
    value = str(row.value or "").strip()
    if not label:
        return None
    if label != row.label:
        replacements["label"] = label
    if value != row.value:
        replacements["value"] = value
    if not replacements:
        return row
    return replace(row, **replacements)


def normalize_plan_provider_context_detail(detail):
    if not isinstance(detail, PlanContextDetailSpec):
        return None
    rows = tuple(
        normalized
        for normalized in (normalize_plan_provider_context_row(row) for row in (detail.rows or ()))
        if normalized is not None
    )
    replacements = {}
    key = str(detail.key or "").strip()
    title = str(detail.title or "").strip()
    body = str(detail.body or "").strip()
    if not key or not title:
        return None
    if key != detail.key:
        replacements["key"] = key
    if title != detail.title:
        replacements["title"] = title
    if body != detail.body:
        replacements["body"] = body
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
    summary_rows = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_row(row) for row in (panel.summary_rows or ())
        )
        if normalized is not None
    )
    details = tuple(
        normalized
        for normalized in (
            normalize_plan_provider_context_detail(detail) for detail in (panel.details or ())
        )
        if normalized is not None
    )
    primary_action = None
    if panel.primary_action is not None:
        primary_action = session.providers.normalize_plan_provider_action(
            provider_id,
            panel.primary_action,
        )
        if primary_action is None:
            return None
    secondary_actions = tuple(
        normalized
        for normalized in (
            session.providers.normalize_plan_provider_action(provider_id, action)
            for action in (panel.secondary_actions or ())
        )
        if normalized is not None
    )
    replacements = {}
    key = str(panel.key or "").strip()
    title = str(panel.title or "").strip()
    subtitle = str(panel.subtitle or "").strip()
    message = str(panel.message or "").strip()
    if not key or not title:
        return None
    if key != panel.key:
        replacements["key"] = key
    if title != panel.title:
        replacements["title"] = title
    if subtitle != panel.subtitle:
        replacements["subtitle"] = subtitle
    if message != panel.message:
        replacements["message"] = message
    if panel.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
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


def normalize_plan_provider_overlay(provider_id, overlay):
    if not isinstance(overlay, PlanOverlaySpec):
        return None
    if not isinstance(overlay.marker_kind, PlanOverlayMarkerKind):
        return None
    replacements = {}
    if overlay.provider_id != provider_id:
        replacements["provider_id"] = str(provider_id or "")
    target_keys = tuple(str(key or "") for key in tuple(overlay.target_keys or ()) if key)
    if target_keys != tuple(overlay.target_keys or ()):
        replacements["target_keys"] = target_keys
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
                return None
        point_pairs.append((point, target))
    points = tuple(point for point, _target in point_pairs)
    if points != tuple(overlay.points or ()):
        replacements["points"] = points
    if raw_point_targets:
        point_targets = tuple(target or PlanOverlayTargetSpec() for _point, target in point_pairs)
        if point_targets != raw_point_targets:
            replacements["point_targets"] = point_targets
    polylines = tuple(
        _coerce_plan_overlay_polyline(polyline) for polyline in tuple(overlay.polylines or ())
    )
    polylines = tuple(polyline for polyline in polylines if len(polyline) >= 2)
    if polylines != tuple(overlay.polylines or ()):
        replacements["polylines"] = polylines
    color = _coerce_plan_overlay_color(overlay.color)
    if color != overlay.color:
        replacements["color"] = color
    if not replacements:
        return overlay
    return replace(overlay, **replacements)


def get_plan_provider_edit_handles(session):
    return session.providers.collect_plan_provider_contributions(
        "get_edit_handles",
        session.providers.normalize_plan_provider_edit_handle,
    )


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


def _coerce_plan_overlay_point(point):
    try:
        return (
            float(point.x),
            float(point.y),
            float(getattr(point, "z", 0.0) or 0.0),
        )
    except AttributeError:
        pass
    try:
        z_value = point[2] if len(point) > 2 else 0.0
        return (float(point[0]), float(point[1]), float(z_value))
    except (TypeError, ValueError, IndexError):
        return None


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
        if session.providers.plan_provider_integrations_disabled():
            _perf_count(session, "plan_provider_integrations_disabled")
            return ()
        cached_contributions = _get_cached_provider_contributions(session, method_name)
        if cached_contributions is not None:
            return cached_contributions
        try:
            context = session.providers.get_plan_edit_context()
        except (ReferenceError, RuntimeError):
            return ()
        results = []
        for provider in session.get_plan_provider_registry().iter_providers():
            provider_id = session.providers.get_plan_provider_id(provider)
            if not provider_id:
                continue
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
        contributions = tuple(results)
        _set_cached_provider_contributions(session, method_name, contributions)
        return contributions


def get_plan_provider_issues(session):
    return session.providers.collect_plan_provider_contributions(
        "get_issues",
        session.providers.normalize_plan_provider_issue,
    )


def get_plan_provider_suggestions(session):
    return session.providers.collect_plan_provider_contributions(
        "get_suggestions",
        session.providers.normalize_plan_provider_suggestion,
    )


def get_plan_provider_tools(session):
    return session.providers.collect_plan_provider_contributions(
        "get_tools",
        session.providers.normalize_plan_provider_tool,
    )


def get_plan_provider_snapshot(session):
    if not _is_active_provider_session(session):
        _perf_count(session, "plan_provider_inactive_session")
        return PlanProviderSnapshot()
    if session.providers.plan_provider_integrations_disabled():
        _perf_count(session, "plan_provider_integrations_disabled")
        return PlanProviderSnapshot()
    return collect_plan_provider_snapshot(session)


def get_plan_provider_inspector_sections(session):
    return session.providers.collect_plan_provider_contributions(
        "get_inspector_sections",
        session.providers.normalize_plan_provider_section,
    )


def get_plan_provider_context_panels(session):
    return session.providers.collect_plan_provider_contributions(
        "get_context_panels",
        session.providers.normalize_plan_provider_context_panel,
    )


def get_plan_provider_overlays(session):
    return session.providers.collect_plan_provider_contributions(
        "get_overlays",
        session.providers.normalize_plan_provider_overlay,
    )


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


def execute_plan_provider_action(
    session,
    provider_id,
    action_key,
    transaction_label="",
    payload=None,
):
    if not session.document_visuals.document_is_alive():
        return False
    provider = session.get_plan_provider_registry().get_provider(provider_id)
    if provider is None:
        return False
    execute_action = getattr(provider, "execute_action", None)
    if not callable(execute_action):
        return False

    context = session.providers.get_plan_edit_context()
    action_context = session.providers.get_plan_provider_action_context(payload=payload)
    transaction_label = str(transaction_label or "").strip()
    defer_updates = getattr(session, "defer_document_visual_updates", None)
    visual_update_context = defer_updates() if callable(defer_updates) else nullcontext()
    try:
        with visual_update_context:
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

    session.selection.refresh_primary_selected_plan_target()
    session.document_visuals.invalidate_document_dependent_plan_visuals()
    session.task_panels.refresh_task_panel_status()
    session.viewport.focus_plan_view()
    return True


def get_plan_edit_context(session):
    doc = session.doc if session.document_visuals.document_is_alive() else None
    active_storey = session.active_storey
    active_storey_name = session.visibility.safe_plan_object_name(active_storey)
    if active_storey is not None and not active_storey_name:
        active_storey = None
        session.active_storey = None
    return PlanEditContext(
        session=session,
        document_name=session.visibility.safe_plan_object_name(doc),
        active_storey_name=active_storey_name,
        active_storey_label=str(session.storey.get_storey_label(active_storey) or ""),
        current_tool=str(session.current_tool or ""),
    )


def get_plan_provider_action_context(session, payload=None):
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
    refresh_cache = getattr(session, "_plan_provider_refresh_cache", None)
    cache_key = ("provider_targets", "by_object")
    if isinstance(refresh_cache, dict) and cache_key in refresh_cache:
        return refresh_cache[cache_key]

    default_document_name = _get_default_plan_provider_target_document_name(session)
    targets_by_object = {}
    for target in tuple(session.providers.get_plan_provider_targets() or ()):
        target_key = _make_plan_provider_target_object_key(
            target.document_name or default_document_name,
            target.object_name,
        )
        if target_key is None or target_key in targets_by_object:
            continue
        targets_by_object[target_key] = target

    if isinstance(refresh_cache, dict):
        refresh_cache[cache_key] = targets_by_object
    return targets_by_object

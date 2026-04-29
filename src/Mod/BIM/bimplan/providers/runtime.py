# SPDX-License-Identifier: LGPL-2.1-or-later

"""Runtime helpers for BIM Plan Edit provider integrations."""

from contextlib import contextmanager, nullcontext

import FreeCAD

from bimplan.providers import get_plan_edit_registry
from bimplan.runtime import tools as plan_runtime_tools
from .contracts import (
    PlanEditContext,
    PlanProviderTargetSpec,
)
from bimplan.semantics import PlanSemanticRecord
from .actions import (
    _execute_plan_provider_action_callback,
    _finalize_plan_provider_action,
    _get_plan_provider_action_executor,
    _run_plan_provider_action,
    execute_plan_provider_action,
    get_plan_provider_action_context,
)
from .snapshot import (
    PlanProviderSnapshot,
    collect_plan_provider_contributions,
    collect_plan_provider_snapshot,
    get_plan_provider_snapshot,
)
from .normalization import (
    _SESSION_AWARE_PROVIDER_NORMALIZERS,
    coerce_plan_provider_results,
    normalize_plan_provider_action,
    normalize_plan_provider_context_detail,
    normalize_plan_provider_context_panel,
    normalize_plan_provider_context_row,
    normalize_plan_provider_edit_handle,
    normalize_plan_provider_issue,
    normalize_plan_provider_overlay,
    normalize_plan_provider_section,
    normalize_plan_provider_suggestion,
    normalize_plan_provider_tool,
)
from .targets import (
    _find_external_provider_target_for_object,
    _get_default_plan_provider_target_document_name,
    _get_external_provider_targets,
    _get_plan_provider_target_lookup,
    _make_plan_provider_target_object_key,
    _normalize_plan_provider_target_text,
    format_plan_provider_target_help,
    get_plan_provider_target_for_object,
    get_plan_provider_target_role_key,
    get_plan_provider_target_role_label,
    get_plan_provider_targets,
    is_plan_provider_target_object,
    is_plan_provider_target_visible_for_mode,
    normalize_plan_provider_target,
    resolve_plan_provider_target_display_fields,
)
from .overlay_state import (
    FOCUSED_PROVIDER_OVERLAY_PICK_MODES,
    PLAN_PROVIDER_OVERLAY_MODE_ALL,
    PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE,
    PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL,
    PLAN_PROVIDER_OVERLAY_MODE_PLUMBING,
    _provider_overlay_read_state,
    get_plan_provider_overlay_category,
    get_plan_provider_overlay_mode,
    is_focused_provider_overlay_pick_mode,
    is_plan_provider_overlay_enabled,
    is_plan_provider_overlay_visible,
    is_plan_provider_overlay_visible_for_mode,
    normalize_plan_provider_overlay_mode,
    queue_plan_provider_overlay_refresh,
    queue_plan_provider_overlay_sync,
    set_plan_provider_overlay_mode,
    set_plan_provider_overlay_visible,
)

translate = FreeCAD.Qt.translate


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

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

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

    def cancel_provider_point_tool(self, refresh=True):
        from bimplan.providers import point

        return point.cancel_provider_point_tool(self.session, refresh=refresh)

    def cancel_for_select(self):
        if not self.has_active_provider_point_tool():
            return False
        self.cancel_provider_point_tool()
        return True

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

    def project_provider_point_to_host(self, point, host_wall):
        del self
        from bimplan.providers import point as provider_point

        return provider_point.project_provider_point_to_host(point, host_wall)

    def get_selected_provider_edit_handles(self, provider_obj):
        from bimplan.providers import edit

        return edit.get_selected_provider_edit_handles(self.session, provider_obj)

    def activate_provider_handle(self, provider_obj, handle_index):
        from bimplan.providers import edit

        return edit.activate_provider_handle(self.session, provider_obj, handle_index)

    def activate_provider_handle_now(self, provider_obj, handle_index):
        from bimplan.providers import edit

        return edit.activate_provider_handle_now(self.session, provider_obj, handle_index)

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

    def cancel_active_tool_for_finish(self):
        if self.session.current_tool != plan_runtime_tools.PlanTool.MOVE_PROVIDER:
            return False
        self.cancel_provider_handle_point_pick()
        return True

    def cancel_active_tool_for_teardown(self):
        if self.session.current_tool != plan_runtime_tools.PlanTool.MOVE_PROVIDER:
            return False
        self.cancel_provider_handle_point_pick()
        return True

    def plan_provider_integrations_disabled(self):
        return plan_provider_integrations_disabled(self.session)

    def normalize_plan_provider_tool(self, provider_id, tool):
        del self
        return normalize_plan_provider_tool(provider_id, tool)

    def get_plan_provider_display_name(self, provider_id):
        return get_plan_provider_display_name(self.session, provider_id)

    def get_plan_provider_tools(self):
        return get_plan_provider_tools(self.session)

    def get_plan_provider_snapshot(self):
        return get_plan_provider_snapshot(self.session)

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

    def is_plan_provider_overlay_visible(self, overlay):
        return is_plan_provider_overlay_visible(self.session, overlay)

    def set_plan_provider_overlay_visible(self, provider_id, overlay_key, visible):
        return set_plan_provider_overlay_visible(
            self.session,
            provider_id,
            overlay_key,
            visible,
        )

    def queue_plan_provider_overlay_sync(self):
        return queue_plan_provider_overlay_sync(self.session)

    def plan_provider_refresh_cache_scope(self):
        return plan_provider_refresh_cache_scope(self.session)

    def invalidate_plan_provider_document_cache(self):
        return invalidate_plan_provider_document_cache(self.session)


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


def discard_runtime_references(session):
    provider_point_state = session.provider_point_state
    provider_transient_state = session.provider_transient_state
    provider_transient_state.provider_selected_objects = []
    provider_point_state.provider_point_host_target = None
    provider_point_state.provider_point_host_source = ""
    provider_point_state.provider_point_preview_trackers = []
    provider_point_state.provider_point_preview_render_state = None
    provider_point_state.provider_point_preview_style_state = None
    provider_point_state.provider_point_preview_source_point = None
    provider_point_state.provider_point_preview_point = None
    provider_point_state.provider_point_preview_host_target = None
    provider_point_state.provider_point_preview_host_source = ""
    session.provider_runtime_state.target_collection_depth = 0


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


PlanProvidersAPI.get_plan_provider_overlay_visibility_key = staticmethod(
    get_plan_provider_overlay_visibility_key
)

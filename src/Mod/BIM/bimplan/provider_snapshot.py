# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider snapshot builder for Plan Edit read-side surfaces."""

from __future__ import annotations

from dataclasses import dataclass

import FreeCAD

from bimplan.providers import (
    PlanContextPanelSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanToolSpec,
)

translate = FreeCAD.Qt.translate

_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY = ("provider_snapshot", "panel")


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
        normalizer_name="_normalize_plan_provider_tool",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="overlays",
        method_name="get_overlays",
        normalizer_name="_normalize_plan_provider_overlay",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="issues",
        method_name="get_issues",
        normalizer_name="_normalize_plan_provider_issue",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="context_panels",
        method_name="get_context_panels",
        normalizer_name="_normalize_plan_provider_context_panel",
    ),
    _PlanProviderSnapshotSurfaceSpec(
        field_name="inspector_sections",
        method_name="get_inspector_sections",
        normalizer_name="_normalize_plan_provider_section",
    ),
)


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
    with session._plan_perf_trace_span(span_name):
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
    for contribution in session._coerce_plan_provider_results(provided):
        normalized = normalizer(provider_id, contribution)
        if normalized is not None:
            results.append(normalized)

    session._plan_perf_count(
        "plan_provider_{}_{}_contributions".format(provider_id, method_name),
        len(results),
    )
    return tuple(results)


def collect_plan_provider_snapshot(session) -> PlanProviderSnapshot:
    with session._plan_perf_trace_span("collect_plan_provider_snapshot"):
        document_is_alive = getattr(session, "_document_is_alive", None)
        if callable(document_is_alive) and not document_is_alive():
            return PlanProviderSnapshot()

        refresh_cache = _get_provider_refresh_cache(session)
        if refresh_cache is not None:
            cached_snapshot = refresh_cache.get(_PLAN_PROVIDER_SNAPSHOT_CACHE_KEY)
            if isinstance(cached_snapshot, PlanProviderSnapshot):
                return cached_snapshot

        try:
            context = session.get_plan_edit_context()
        except (ReferenceError, RuntimeError):
            return PlanProviderSnapshot()

        collected = {
            surface_spec.field_name: [] for surface_spec in _PLAN_PROVIDER_SNAPSHOT_SURFACES
        }
        normalized_surfaces = tuple(
            (
                surface_spec,
                getattr(session, surface_spec.normalizer_name),
            )
            for surface_spec in _PLAN_PROVIDER_SNAPSHOT_SURFACES
        )

        for provider in session.get_plan_provider_registry().iter_providers():
            provider_id = session._get_plan_provider_id(provider)
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

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Snapshot and contribution collection for BIM Plan Edit providers."""

from dataclasses import dataclass

from .contracts import (
    PlanContextPanelSpec,
    PlanInspectorSection,
    PlanIssueSpec,
    PlanOverlaySpec,
    PlanToolSpec,
)


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


def _runtime():
    from bimplan.providers import runtime as provider_runtime

    return provider_runtime


def collect_plan_provider_snapshot(session) -> PlanProviderSnapshot:
    provider_runtime = _runtime()
    with provider_runtime._perf_trace_span(session, "collect_plan_provider_snapshot"):
        if not session.document_visuals.document_is_alive():
            return PlanProviderSnapshot()

        cached_snapshot = provider_runtime._get_cached_provider_snapshot(session)
        if cached_snapshot is not None:
            return cached_snapshot

        context = provider_runtime._get_plan_edit_context_or_none(session)
        if context is None:
            return PlanProviderSnapshot()
        cached_snapshot = provider_runtime._get_document_cached_provider_snapshot(session, context)
        if cached_snapshot is not None:
            provider_runtime._set_cached_provider_snapshot(session, cached_snapshot)
            provider_runtime._set_cached_provider_snapshot_contributions(session, cached_snapshot)
            return cached_snapshot

        snapshot = provider_runtime._collect_plan_provider_snapshot_from_providers(session, context)
        provider_runtime._set_cached_provider_snapshot(session, snapshot)
        provider_runtime._set_document_cached_provider_snapshot(session, context, snapshot)
        provider_runtime._set_cached_provider_snapshot_contributions(session, snapshot)
        provider_runtime._set_document_cached_provider_snapshot_contributions(
            session, context, snapshot
        )
        return snapshot


def collect_plan_provider_contributions(session, method_name, normalizer):
    provider_runtime = _runtime()
    with provider_runtime._perf_trace_span(
        session, f"collect_plan_provider_contributions_{method_name}"
    ):
        if not provider_runtime._is_active_provider_session(session):
            provider_runtime._perf_count(session, "plan_provider_inactive_session")
            return ()
        if provider_runtime.plan_provider_integrations_disabled(session):
            provider_runtime._perf_count(session, "plan_provider_integrations_disabled")
            return ()
        cached_contributions = provider_runtime._get_cached_provider_contributions(
            session, method_name
        )
        if cached_contributions is not None:
            return cached_contributions
        context = provider_runtime._get_plan_edit_context_or_none(session)
        if context is None:
            return ()
        cached_contributions = provider_runtime._get_document_cached_provider_contributions(
            session, context, method_name
        )
        if cached_contributions is not None:
            provider_runtime._set_cached_provider_contributions(
                session, method_name, cached_contributions
            )
            return cached_contributions
        contributions = provider_runtime._collect_plan_provider_contributions_for_method(
            session,
            context,
            method_name,
            normalizer,
        )
        provider_runtime._set_cached_provider_contributions(session, method_name, contributions)
        provider_runtime._set_document_cached_provider_contributions(
            session, context, method_name, contributions
        )
        return contributions


def get_plan_provider_snapshot(session):
    provider_runtime = _runtime()
    if not provider_runtime._is_active_provider_session(session):
        provider_runtime._perf_count(session, "plan_provider_inactive_session")
        return PlanProviderSnapshot()
    if provider_runtime.plan_provider_integrations_disabled(session):
        provider_runtime._perf_count(session, "plan_provider_integrations_disabled")
        return PlanProviderSnapshot()
    return collect_plan_provider_snapshot(session)

# Plan Edit Architecture Cleanup Plan

This plan is for tightening the BIM Plan Edit codebase into a clearer long-term shape.

## Target State

- `PlanEditSession` composes and coordinates.
- Owned APIs implement behavior.
- Read-model layers shape UI-facing data and do not act as compatibility surfaces.
- Stable cross-module payloads use typed records instead of raw tuples and dicts.
- Internal `bimplan` code calls owned APIs directly and fails loudly when those APIs are missing.

## Working Rules

- Remove compatibility fallbacks inside `bimplan`.
- Keep defensive handling at FreeCAD, Qt, and external provider boundaries.
- Prefer explicit APIs over generated or string-based dispatch.
- Introduce dataclasses and enums only for stable contracts shared across modules.
- Avoid refactors that only move code without clarifying ownership or contracts.

## Current Priorities

1. Remove owned-API fallback patterns.
   Delete `getattr(...)`, `hasattr(...)`, and string dispatch for required internal collaborators.

2. Retire tuple compatibility in product code.
   Keep compatibility only at boundaries. Internal loops and records should use typed refs directly.

3. Tighten provider integration contracts.
   Prefer typed action-context accessors and typed provider-side payload records over raw dict-style access.

4. Reduce selection and picking policy ambiguity.
   Keep priority stages explicit, keep debug payload construction isolated, and keep result shapes typed.

5. Tighten exception boundaries.
   Keep broad defensive handling only at FreeCAD, Qt, and external provider/plugin edges.

6. Normalize names by behavior.
   Use `get_`, `resolve_`, `build_`, `apply_`, `sync_`, and `queue_` consistently.

## Near-Term Batches

1. Remove owned-API fallback calls around provider overlay mode and similar required provider/session APIs.
2. Continue replacing raw tuple target usage in product code with `.kind` / `.obj`.
3. Remove remaining owned-API `getattr` / `hasattr` fallback calls highlighted by `devtools/cruft_report.py`.
4. Audit broad `except Exception` usage and narrow internal cases that no longer need compatibility shielding.
5. Re-run `devtools/cruft_report.py` after each batch and choose the next cleanup from the report.

## Stop Conditions

The architecture is in good shape when:

- `session.py` is composition and lifecycle only.
- task-panel readers are direct owned-API consumers with minimal UI-specific normalization.
- provider and selection payloads are typed through their main flows.
- no internal code relies on compatibility indirection to reach owned APIs.
- the cruft report mostly points at genuinely complex workflows, not avoidable compatibility noise.

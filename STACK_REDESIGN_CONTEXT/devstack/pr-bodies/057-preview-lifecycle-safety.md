# BIM: harden contextual preview lifecycles

## Summary

Make semantic preview teardown deterministic across rapid pointer updates, renderer replacement,
repeated Plan Edit sessions, and document closure.

## Architectural invariant

Queued presentation work may be discarded during shutdown, but teardown finalizers must run and
release every viewer-local Coin node even after its document or view has disappeared.

## Changes

- Preserve teardown finalizers when ordinary queued view updates are cancelled.
- Make contextual renderer cleanup idempotent when the document or view is already invalid.
- Coalesce rapid semantic joint previews so only the latest state reaches Coin.
- Reject callbacks captured from an obsolete renderer generation.
- Cover document-close teardown and repeated Plan Edit entry/exit cycles with real GUI tests.

## Tests

- `BIM.bimtests.TestBimPlanEditSessionGui` (23 tests under Xvfb)
- Debug build with the devstack ccache preset

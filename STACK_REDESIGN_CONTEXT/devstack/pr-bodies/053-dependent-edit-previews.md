## Summary

Coordinate renderer-neutral edit previews across a semantic object and its
visual dependencies. Opening move and width previews now transiently rebuild
the affected host-wall cut while leaving the document model untouched.

## Architectural invariant

A live edit proposes one coherent viewer state. All affected representations
are installed and removed together, and committed representations are restored
on commit, cancellation, invalid input, or renderer teardown.

## Changes

- Add `BIMPreviewState` and typed preview entries to the semantic contract.
- Let hosted-opening providers derive a proposed opening and host-wall cut.
- Apply coordinated preview entries in one queued scene-graph mutation.
- Preserve normal styling for replacement wall geometry and edit styling for
  the actively changing opening.
- Track replacement groups so cleanup restores every committed viewer branch.

## Tests

- Headless semantic representation suite (27 tests).
- Geometric proof that the transient wall closes the old void and cuts the
  proposed opening location without changing the document.
- Real Coin Plan Edit opening move/resize/flip test, including host replacement
  across repeated updates, invalid previews, and restoration.

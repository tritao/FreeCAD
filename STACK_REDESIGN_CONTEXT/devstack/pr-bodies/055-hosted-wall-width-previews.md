## Summary

Preview wall-width edits together with every hosted opening. The proposed wall
section remains cut through, while opening jambs and plan symbols are
reinterpreted against the new host faces without modifying the document.

## Architectural invariant

A host geometry edit asks hosted semantic providers for representations against
the proposed host state. Wall and opening viewer branches are replaced and
restored as one bounded preview group.

## Changes

- Move wall-width previews onto `BIMPreviewState`.
- Add a hosted-opening provider capability for proposed wall sections.
- Subtract semantic opening voids from the proposed wall face.
- Regenerate opening jamb and symbol geometry at the proposed wall depth.
- Avoid rendering semantic void geometry as an opaque opening object.

## Tests

- Headless checks for wall depth, opening cut-through, jamb length, and no
  document mutation.
- Real Coin preview/cancel/commit/undo coverage using the generated basic file.

## Summary

Preview dependent Space regions from proposed wall representations. Spaces can
now contribute renderer-neutral room geometry to the same atomic edit state
without recomputing or modifying their document objects.

## Architectural invariant

Dependency discovery is capability-based. Consumers inspect semantic proposed
representations, never Coin nodes, and preview evaluation cannot modify Space
shape, area, boundary links, hints, or status properties.

## Changes

- Add generic dependent-preview expansion to `BIMPreviewState`.
- Let Space derive a seeded planar room region from proposed and committed wall
  boundaries.
- Render the proposed Space region and boundary as part of the coordinated
  preview group.
- Give `BIMPlanEditBasic` real stable wall-boundary links and a room-region
  reference point instead of a visually coincident static box only.

## Tests

- Verify proposed Space area changes while the persisted area stays unchanged.
- Verify the real Coin preview contains the Space overlay and cleans it on
  cancel.
- Re-run the generated example loading and semantic rendering test.
- Re-run all 27 semantic representation tests.

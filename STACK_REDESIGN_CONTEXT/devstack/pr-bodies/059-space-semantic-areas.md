# BIM: compute Space areas from semantic footprints

## Summary

Compute Space horizontal quantities directly from the resolved semantic footprint instead of
projecting every horizontal BRep face through the generic component area calculator.

## Architectural invariant

A valid Space boundary remains authoritative during dependent wall and opening recomputes; an
unrelated intermediate projection failure must not reset its area properties.

## Changes

- Override Space area computation with its canonical footprint geometry.
- Derive horizontal area and full boundary perimeter from footprint faces and wires.
- Retain vertical-area calculation without invoking generic horizontal projection.
- Preserve valid quantities when no transient footprint can be produced.
- Verify opening commit and undo keep both semantic geometry and persistent Space area stable.
- Keep the legacy fallback test aligned with the Space-owned calculator.

## Tests

- Semantic Space area test rejects any call to the generic horizontal projector.
- Installed Basic example opening E2E passed under Xvfb with no area-computation warning.
- Debug build with the devstack ccache preset.

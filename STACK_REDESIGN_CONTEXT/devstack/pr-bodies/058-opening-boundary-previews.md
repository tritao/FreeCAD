# BIM: coordinate opening boundary previews

## Summary

Propagate semantic door and window edits through their host-wall cut representation and dependent
Space preview without mutating the document during pointer movement.

## Architectural invariant

Opening voids affect a wall's displayed cut geometry, but they do not puncture the continuous
spatial boundary used to resolve enclosed rooms.

## Changes

- Describe whether a preview entry changes spatial-boundary topology.
- Replace opening voids once across the unified host-wall section.
- Clip proposed voids to the host section before applying them.
- Let walls expose continuous room-boundary geometry independently of display cutouts.
- Keep dependent Space previews stable for opening-only edits while retaining live wall/path
  boundary recomputation.
- Exercise preview, cancel, commit, undo, and re-entry with the installed Basic example and real
  Coin nodes.

## Tests

- `BIM.bimtests.TestArchRepresentation` (27 existing semantic tests plus the new entry-contract test)
- `BIM.bimtests.TestBimPlanEditExamplesGui.TestBimPlanEditExamplesGui.test_basic_example_opening_handles_drive_real_coin_edits`
- Debug build with the devstack ccache preset

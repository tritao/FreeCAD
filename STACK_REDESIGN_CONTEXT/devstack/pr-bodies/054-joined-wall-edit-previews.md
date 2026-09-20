## Summary

Preview a moved wall joint as one coherent proposed state for both participating
walls. The miter is solved and rendered from hypothetical paths without
modifying either document object during pointer movement.

## Architectural invariant

Wall-relation solving accepts resolved geometry values independently of live
document properties. A joined edit replaces every affected viewer-local wall
representation together and restores them together.

## Changes

- Allow the two-wall relation solver to consume explicit paths and sections.
- Generate trimmed planar wall representations from hypothetical baselines.
- Attach coordinated preview state to the semantic wall-joint move operation.
- Retain relation-owned endpoint suppression; the joint diamond remains the
  single semantic control for a relation-owned corner.

## Tests

- Headless proof that both proposed miter faces touch and neither wall changes.
- Real Coin Plan Edit test covering coordinated preview, cancel restoration,
  atomic commit, and undo.

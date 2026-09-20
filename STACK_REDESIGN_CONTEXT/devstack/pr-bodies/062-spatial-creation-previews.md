# Summary

Render Plan Region and Space Separator creation previews through semantic, viewer-local BIM representations.

# Why

These tools still used Draft line trackers after wall and opening creation had moved onto the contextual representation pipeline. That left creation with inconsistent rendering ownership, teardown, and geometry semantics.

# Architectural invariant

Spatial creation tools describe proposed semantic geometry. The contextual viewer realizes it transiently, and cancellation removes it without changing the document.

# Changes

- Represent proposed region edges and the closing edge with distinct semantic roles.
- Add a proposed region fill once the pointer defines a valid closed polygon.
- Represent a proposed Space Separator as a typed semantic segment.
- Replace tracker lists with one preview identity per active tool.
- Clear stale separator geometry when the pointer no longer defines a valid segment.
- Reuse queued contextual-renderer cleanup for cancel and teardown.

# Compatibility

Point acquisition, snapping, region and separator document objects, validation, and transaction behavior are unchanged.

# Tests

- Renderer-neutral region edge, closure, fill, and separator geometry.
- Real-Coin realization and cleanup of spatial creation preview geometry.

# Deferred

Multiple enclosed-region candidate selection already uses semantic candidate geometry but retains its specialized hover presentation; unifying that presentation is independent of creation correctness.

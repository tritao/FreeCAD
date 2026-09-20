# Summary

Render interactive single, chained, and rectangular wall previews through `BIMRepresentation` and the viewer-local contextual renderer.

# Why

Plan Edit already uses semantic representations for committed walls and contextual edits, but wall creation still depended on legacy Draft Coin trackers. Using the same renderer-neutral preview contract gives creation consistent geometry, ordering, lifecycle, and future semantic feedback.

# Architectural invariant

Wall creation owns model creation and transactions; `BIMRepresentation` owns preview geometry; the viewer owns transient realization. Previewing never creates or mutates document objects.

# Changes

- Add a semantic wall preview tracker implementing the small tracker contract consumed by the existing wall command.
- Supply that tracker through the Plan Edit interaction host for single and chained wall creation.
- Replace four rectangle trackers with one four-segment semantic representation.
- Clear queued viewer-local preview state on cancel and teardown.
- Test semantic geometry and lifecycle behavior.

# Compatibility

The standalone BIM wall command keeps its existing Draft tracker. Only the Plan Edit host selects semantic preview realization. Existing creation, auto-join, snapping, and transaction APIs remain authoritative.

# Tests

- `test_semantic_wall_creation_tracker_uses_contextual_preview`
- `test_rectangular_wall_preview_is_one_semantic_representation`

# Deferred

Opening and Space creation previews will adopt the same contract in later layers.

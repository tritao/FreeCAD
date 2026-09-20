# Summary

Preview hosted window creation as one coordinated semantic state containing the proposed opening, its host-wall cutout, and dependent spatial representation.

# Why

Window placement previously drew four viewer-only tracker lines. That preview could not express the wall void, participate in dependent representation updates, or share lifecycle guarantees with contextual editing.

# Architectural invariant

A proposed hosted opening is preview state over existing semantic objects. The document remains unchanged until commit, and all affected viewer-local representations install and clear atomically.

# Changes

- Replace window-placement line trackers with `BIMPreviewState`.
- Describe the proposed opening cut and window symbol using `BIMRepresentation`.
- Derive a replacement host-wall representation with the proposed void applied.
- Mark opening creation as preserving the wall's authoritative spatial boundary.
- Expand dependent previews through the established semantic contract.
- Keep the preview key separate from the selected host so host changes clear safely.

# Compatibility

The existing window builder, hosted-opening service, snapping, sizing, and transaction behavior are unchanged. Only transient Plan Edit preview realization changes.

# Tests

- Semantic opening and host-cut geometry test.
- Real-Coin atomic realization, replacement, clear, and restoration test.

# Deferred

Door-type selection during creation and generic opening presets remain separate product features.

# Summary

Render enclosed Space candidates through stable semantic preview representations instead of Draft trackers.

# Why

Candidate discovery was already semantic, but its presentation was still a collection of anonymous tracker lines recreated on every hover update. This prevented candidate state from participating in the common representation and lifecycle model.

# Architectural invariant

Candidate geometry and state are renderer-neutral BIM data. A viewer consumer chooses colors, opacity, and line weight, while candidate identity remains stable throughout the picking session.

# Changes

- Add renderer-neutral preview presentation intents for available, emphasized, muted, and invalid geometry.
- Teach the Coin contextual renderer to realize those intents.
- Build candidate fill and boundary representations with semantic source mappings.
- Preserve stable transient candidate identities across hover updates.
- Express available, hovered, claimed, and invalid candidate states without Coin data in BIM logic.
- Clear candidate representations before discarding session identities.
- Remove the dedicated Space-candidate tracker store.

# Compatibility

Candidate discovery, spatial filtering, hit testing, selection, Space creation/reassignment, and transactions remain unchanged.

# Tests

- Full renderer-neutral representation suite.
- Real-Coin candidate realization, stable identity, hover emphasis, reset, and cleanup.
- Preview-style default and semantic-state conversion coverage.

# Deferred

The generic semantic picking API can later consume candidate source mappings directly; the current proven face/segment candidate picker remains authoritative in this layer.

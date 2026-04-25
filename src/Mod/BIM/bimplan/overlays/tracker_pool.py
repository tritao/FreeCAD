# SPDX-License-Identifier: LGPL-2.1-or-later

"""Small helpers for overlay tracker lifecycle state."""

from dataclasses import dataclass, field

from . import manager as overlay_manager


@dataclass
class TrackerPool:
    trackers: list = field(default_factory=list)
    render_state: object = None
    style_state: object = None


def finalize_tracker_pool(pool):
    overlay_manager.finalize_trackers(pool.trackers)
    pool.trackers = []
    pool.render_state = None
    pool.style_state = None


def ensure_line_tracker_specs(
    DraftTrackers,
    pool,
    specs,
    *,
    create_tracker,
    apply_tracker,
):
    style_state = tuple((spec["label"], spec.get("dotted", False)) for spec in specs)
    if len(pool.trackers) != len(specs) or pool.style_state != style_state:
        finalize_tracker_pool(pool)
        pool.style_state = style_state
        for spec in specs:
            pool.trackers.append(create_tracker(spec))

    for tracker, spec in zip(pool.trackers, specs):
        apply_tracker(tracker, spec)

    return pool

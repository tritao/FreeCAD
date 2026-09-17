# SPDX-License-Identifier: LGPL-2.1-or-later

"""View-local state used by Draft's shared Snapper service."""

from dataclasses import dataclass, field


@dataclass
class SnapTrackers:
    """Transient Coin trackers belonging to one 3D viewport."""

    grid: object = None
    snap: object = None
    extension: object = None
    radius: object = None
    dim1: object = None
    dim2: object = None
    track_line: object = None
    extension2: object = None
    hold: object = None


@dataclass
class SnapViewContext:
    """Snapping configuration and trackers for one originating viewport.

    ``modes=None`` means that the normal Draft snap settings are inherited.
    The other fields are deliberately small: command lifecycle and point
    requests remain owned by the shared Snapper.
    """

    view: object = None
    modes: object = None
    interaction_plane: object = None
    grid_provider: object = None
    semantic_providers: list = field(default_factory=list)
    trackers: SnapTrackers = field(default_factory=SnapTrackers)

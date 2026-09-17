# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared BIM planar-grid preferences and unit parsing."""

from dataclasses import dataclass
import math

import FreeCAD


GRID_PREFERENCES = "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
DEFAULT_GRID_SPACING = 100.0
DEFAULT_GRID_MAJOR_EVERY = 10


@dataclass(frozen=True)
class GridSettings:
    """Validated BIM grid settings in FreeCAD's internal millimetres."""

    spacing: float = DEFAULT_GRID_SPACING
    major_every: int = DEFAULT_GRID_MAJOR_EVERY


def _parse_spacing(raw_spacing):
    try:
        spacing = float(FreeCAD.Units.Quantity(raw_spacing).Value)
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError):
        return DEFAULT_GRID_SPACING
    if not math.isfinite(spacing) or spacing <= 0.0:
        return DEFAULT_GRID_SPACING
    return spacing


def get_grid_settings(preferences=None):
    """Read and validate the shared BIM grid preferences.

    ``GridSpacing`` is parsed as a FreeCAD quantity, so values such as
    ``100 mm``, ``10 cm`` and ``4 in`` are normalized to internal millimetres
    before they reach a snap lattice.  A preference-like object can be passed
    by tests and callers that already own a ``ParamGet`` instance.
    """

    if preferences is None:
        preferences = FreeCAD.ParamGet(GRID_PREFERENCES)
    spacing = _parse_spacing(preferences.GetString("GridSpacing", "100 mm"))
    try:
        major_every = int(preferences.GetInt("GridMainlines", DEFAULT_GRID_MAJOR_EVERY))
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError):
        major_every = DEFAULT_GRID_MAJOR_EVERY
    if major_every <= 0:
        major_every = DEFAULT_GRID_MAJOR_EVERY
    return GridSettings(spacing=spacing, major_every=major_every)

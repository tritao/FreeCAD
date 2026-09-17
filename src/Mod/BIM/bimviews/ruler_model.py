# SPDX-License-Identifier: LGPL-2.1-or-later

"""UI-neutral coordinate and tick model for BIM viewport rulers."""

from dataclasses import dataclass
import math

import FreeCAD

from draftutils.grid import adaptive_grid_interval
from draftutils.units import display_external


def engineering_interval(units_per_pixel, target_pixels=100.0):
    """Return a readable major interval using the engineering 1/2/5 series."""
    return adaptive_grid_interval(units_per_pixel, target_pixels)


def tick_values(start, end, interval):
    """Return interval-aligned values covering an arbitrary directed range."""

    low, high = sorted((float(start), float(end)))
    interval = abs(float(interval))
    if interval <= 0.0 or not math.isfinite(interval):
        return ()
    first = math.ceil((low - interval * 1e-9) / interval) * interval
    count = max(0, int(math.floor((high - first) / interval + 1e-9)) + 1)
    return tuple(first + index * interval for index in range(count))


def format_length(value, interval=None, cursor=False):
    """Format an internal millimetre length using the active unit schema."""

    value = float(value)
    quantity = FreeCAD.Units.Quantity(value, FreeCAD.Units.Length)
    if interval is None and not cursor:
        return _compact_quantity_text(quantity.UserString)

    if cursor and interval is None:
        # Cursor feedback benefits from millimetre-level precision regardless
        # of whether the preferred display unit is metres, feet or inches.
        decimals = 3
    else:
        interval = abs(float(interval or 0.0))
        conversion = _preferred_length_conversion(quantity)
        preferred_interval = interval / conversion if conversion else interval
        if preferred_interval <= 0.0 or not math.isfinite(preferred_interval):
            decimals = 0
        else:
            decimals = max(0, min(6, int(math.ceil(-math.log10(preferred_interval)))))
            if cursor:
                decimals = min(6, decimals + 1)
    try:
        text = display_external(value, decimals=decimals, dim="Length", showUnit=True)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        text = quantity.UserString
    return _compact_quantity_text(text)


def format_metric(value, interval=None, cursor=False):
    """Compatibility alias for the unit-aware ruler formatter."""

    return format_length(value, interval=interval, cursor=cursor)


def preferred_length_unit():
    """Return the active schema's preferred length unit label."""

    try:
        quantity = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length)
        return str(quantity.getUserPreferred()[2])
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return ""


def _preferred_length_conversion(quantity):
    try:
        conversion = float(quantity.getUserPreferred()[1])
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return 1.0
    return conversion if math.isfinite(conversion) and conversion > 0.0 else 1.0


def _compact_quantity_text(text):
    """Trim formatter padding while preserving unit/schema tokens."""

    compact = []
    for token in str(text).split():
        for separator in (".", ","):
            if separator in token:
                head, tail = token.rsplit(separator, 1)
                tail = tail.rstrip("0")
                token = head if not tail else head + separator + tail
                break
        if token in ("-0", "+0"):
            token = "0"
        compact.append(token)
    return " ".join(compact)


@dataclass(frozen=True)
class RulerTransform:
    """Linear mapping between viewport pixels and view-frame coordinates."""

    x_left: float
    x_right: float
    y_top: float
    y_bottom: float
    width: float
    height: float
    units_per_pixel: float

    def x_at_pixel(self, pixel):
        if self.width <= 0.0:
            return self.x_left
        return self.x_left + (self.x_right - self.x_left) * float(pixel) / self.width

    def y_at_pixel(self, pixel):
        if self.height <= 0.0:
            return self.y_top
        return self.y_top + (self.y_bottom - self.y_top) * float(pixel) / self.height

    def pixel_for_x(self, coordinate):
        span = self.x_right - self.x_left
        if abs(span) <= 1e-12:
            return 0.0
        return (float(coordinate) - self.x_left) * self.width / span

    def pixel_for_y(self, coordinate):
        span = self.y_bottom - self.y_top
        if abs(span) <= 1e-12:
            return 0.0
        return (float(coordinate) - self.y_top) * self.height / span

    @property
    def major_interval(self):
        return engineering_interval(self.units_per_pixel)

    @property
    def minor_interval(self):
        return self.major_interval / 10.0

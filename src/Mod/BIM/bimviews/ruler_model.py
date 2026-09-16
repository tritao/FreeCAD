# SPDX-License-Identifier: LGPL-2.1-or-later

"""UI-neutral coordinate and tick model for BIM viewport rulers."""

from dataclasses import dataclass
import math


def engineering_interval(units_per_pixel, target_pixels=100.0):
    """Return a readable major interval using the engineering 1/2/5 series."""

    required = max(float(units_per_pixel) * float(target_pixels), 1e-12)
    decade = 10.0 ** math.floor(math.log10(required))
    normalized = required / decade
    for step in (1.0, 2.0, 5.0, 10.0):
        if normalized <= step:
            return step * decade
    return 10.0 * decade


def tick_values(start, end, interval):
    """Return interval-aligned values covering an arbitrary directed range."""

    low, high = sorted((float(start), float(end)))
    interval = abs(float(interval))
    if interval <= 0.0 or not math.isfinite(interval):
        return ()
    first = math.ceil((low - interval * 1e-9) / interval) * interval
    count = max(0, int(math.floor((high - first) / interval + 1e-9)) + 1)
    return tuple(first + index * interval for index in range(count))


def format_metric(value, interval=None, cursor=False):
    """Format FreeCAD's millimetre coordinates using compact metric labels."""

    value = float(value)
    interval = abs(float(interval or 0.0))
    if abs(value) >= 1000.0 or interval >= 1000.0:
        decimals = 3 if cursor else max(
            0,
            min(3, int(math.ceil(-math.log10(max(interval / 1000.0, 1e-9))))),
        )
        text = ("{:.%df}" % decimals).format(value / 1000.0)
        return "{} m".format(_trim_decimal(text))
    decimals = 1 if cursor or interval < 1.0 else 0
    text = ("{:.%df}" % decimals).format(value)
    return "{} mm".format(_trim_decimal(text))


def _trim_decimal(text):
    return text.rstrip("0").rstrip(".") if "." in text else text


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

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Deterministic layout of drawing views inside printable sheet bounds."""

from dataclasses import dataclass
import re


class SheetLayoutError(ValueError):
    """Raised when a drawing view cannot fit inside the printable area."""


@dataclass(frozen=True)
class SheetMargins:
    left: float = 10.0
    top: float = 10.0
    right: float = 10.0
    bottom: float = 10.0


@dataclass(frozen=True)
class SheetRect:
    """Axis-aligned sheet rectangle expressed by center and size in mm."""

    x: float
    y: float
    width: float
    height: float

    @property
    def left(self):
        return self.x - self.width / 2.0

    @property
    def right(self):
        return self.x + self.width / 2.0

    @property
    def top(self):
        return self.y - self.height / 2.0

    @property
    def bottom(self):
        return self.y + self.height / 2.0

    def intersects(self, other, gap=0.0):
        return not (
            self.right + gap <= other.left
            or other.right + gap <= self.left
            or self.bottom + gap <= other.top
            or other.bottom + gap <= self.top
        )


class BIMSheetLayout:
    """Place rectangular views using deterministic top-left first fit."""

    def __init__(self, width, height, margins=None, gap=5.0):
        self.width = float(width)
        self.height = float(height)
        self.margins = margins or SheetMargins()
        self.gap = float(gap)
        if self.width <= 0.0 or self.height <= 0.0:
            raise SheetLayoutError("sheet dimensions must be positive")

    def place(self, size, occupied=(), position=None):
        width, height = (float(value) for value in size)
        if width <= 0.0 or height <= 0.0:
            raise SheetLayoutError("view dimensions must be positive")
        occupied = tuple(occupied)
        if position is not None:
            result = SheetRect(float(position[0]), float(position[1]), width, height)
            self._ensure_inside(result)
            return result

        left = self.margins.left
        top = self.margins.top
        x_candidates = {left + width / 2.0}
        y_candidates = {top + height / 2.0}
        for rect in occupied:
            x_candidates.add(rect.right + self.gap + width / 2.0)
            y_candidates.add(rect.bottom + self.gap + height / 2.0)
        for y in sorted(y_candidates):
            for x in sorted(x_candidates):
                candidate = SheetRect(x, y, width, height)
                if not self._inside(candidate):
                    continue
                if not any(candidate.intersects(rect, self.gap) for rect in occupied):
                    return candidate
        raise SheetLayoutError("no printable sheet space is available for this view")

    def _inside(self, rect):
        return (
            rect.left >= self.margins.left
            and rect.top >= self.margins.top
            and rect.right <= self.width - self.margins.right
            and rect.bottom <= self.height - self.margins.bottom
        )

    def _ensure_inside(self, rect):
        if not self._inside(rect):
            raise SheetLayoutError("view position lies outside printable sheet bounds")


def svg_footprint(svg, scale=1.0, fallback=(64.0, 64.0)):
    """Estimate an SVG symbol footprint from path coordinates."""

    points = []
    for path_data in re.findall(r"<path[^>]*\bd\s*=\s*['\"]([^'\"]+)", svg or ""):
        number_pattern = r"[-+]?(?:\d*\.\d+|\d+)(?:e[-+]?\d+)?"
        values = [
            float(value) for value in re.findall(number_pattern, path_data, re.I)
        ]
        points.extend(zip(values[0::2], values[1::2]))
    if not points:
        return tuple(float(value) for value in fallback)
    xs, ys = zip(*points)
    width = (max(xs) - min(xs)) * float(scale)
    height = (max(ys) - min(ys)) * float(scale)
    if width <= 0.0 or height <= 0.0:
        return tuple(float(value) for value in fallback)
    return width, height

# SPDX-License-Identifier: LGPL-2.1-or-later

"""UI-independent planar grid mathematics shared by Draft and BIM."""

from dataclasses import dataclass
import math

import FreeCAD


def adaptive_grid_interval(units_per_pixel, target_pixels=50.0):
    """Return a readable interval from the engineering 1/2/5 series."""

    required = max(float(units_per_pixel) * float(target_pixels), 1e-12)
    decade = 10.0 ** math.floor(math.log10(required))
    normalized = required / decade
    for step in (1.0, 2.0, 5.0, 10.0):
        if normalized <= step:
            return step * decade
    return 10.0 * decade


@dataclass(frozen=True)
class GridLine:
    """One line in a planar grid, expressed in global coordinates."""

    start: object
    end: object
    major: bool = False


class GridLattice:
    """A regular two-dimensional snap/display lattice.

    The lattice is independent of Coin, Qt, preferences and commands. Its
    origin and axes are FreeCAD vectors, while ``lines`` returns geometry that
    any renderer can consume.
    """

    def __init__(self, origin=None, u_axis=None, v_axis=None, spacing=100.0, major_every=10):
        self.origin = origin or FreeCAD.Vector()
        self.u_axis = self._normalise(u_axis or FreeCAD.Vector(1, 0, 0))
        self.v_axis = self._normalise(v_axis or FreeCAD.Vector(0, 1, 0))
        self.spacing = float(spacing)
        self.major_every = int(major_every)
        if not math.isfinite(self.spacing) or self.spacing <= 0.0:
            raise ValueError("Grid spacing must be positive")
        if self.major_every <= 0:
            raise ValueError("Grid major interval must be positive")

    def nearest_node(self, point):
        """Return the nearest lattice node to a global point."""

        relative = point.sub(self.origin)
        u = round(relative.dot(self.u_axis) / self.spacing) * self.spacing
        v = round(relative.dot(self.v_axis) / self.spacing) * self.spacing
        return self.origin.add(self.u_axis.multiply(u)).add(self.v_axis.multiply(v))

    def lines(self, bounds, display_spacing=None):
        """Generate visible grid lines for ``(u_min, u_max, v_min, v_max)``.

        ``display_spacing`` may be coarser than snap spacing. Major lines are
        aligned to the snap lattice whenever the display interval is an exact
        multiple of it.
        """

        u_min, u_max, v_min, v_max = (float(value) for value in bounds)
        step = float(display_spacing or self.spacing)
        if not math.isfinite(step) or step <= 0.0:
            return ()
        u_values = self._values(u_min, u_max, step)
        v_values = self._values(v_min, v_max, step)
        lines = []
        for u in u_values:
            lines.append(
                GridLine(
                    self._point(u, v_min),
                    self._point(u, v_max),
                    self._is_major(u, step),
                )
            )
        for v in v_values:
            lines.append(
                GridLine(
                    self._point(u_min, v),
                    self._point(u_max, v),
                    self._is_major(v, step),
                )
            )
        return tuple(lines)

    def _point(self, u, v):
        return self.origin.add(self.u_axis.multiply(u)).add(self.v_axis.multiply(v))

    def _is_major(self, value, display_spacing):
        lattice_units = value / self.spacing
        display_units = display_spacing / self.spacing
        if abs(display_units - round(display_units)) <= 1e-9:
            return abs(lattice_units / self.major_every - round(lattice_units / self.major_every)) <= 1e-9
        return abs(value / (self.spacing * self.major_every) - round(value / (self.spacing * self.major_every))) <= 1e-9

    @staticmethod
    def _values(low, high, step):
        first = math.ceil((min(low, high) - step * 1e-9) / step)
        last = math.floor((max(low, high) + step * 1e-9) / step)
        return tuple(index * step for index in range(first, last + 1))

    @staticmethod
    def _normalise(axis):
        result = FreeCAD.Vector(axis.x, axis.y, axis.z)
        if result.Length <= 1e-12:
            raise ValueError("Grid axis must not be zero")
        result.normalize()
        return result

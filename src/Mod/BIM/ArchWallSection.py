# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026                                                    *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Section adapters for BIM wall joint solving.

This module exposes the wall cross-section as structured data instead of a
single width scalar. The current adapter mirrors the existing straight-wall
section model: alignment-driven extents and an ordered list of section layers.
"""

from dataclasses import dataclass, field


@dataclass
class WallSectionLayer:
    """One ordered layer in a wall cross-section."""

    index: int
    raw_thickness: float
    thickness: float
    y_min: float
    y_max: float
    visible: bool = True


@dataclass
class WallSection:
    """Normalized wall cross-section used by the wall-joint solver."""

    total_thickness: float
    align: str
    y_min: float
    y_max: float
    layers: list = field(default_factory=list)
    wall: object = None

    @property
    def positive_extent(self):
        """Extent on the path's positive lateral side."""
        return max(0.0, -self.y_min)

    @property
    def negative_extent(self):
        """Extent on the path's negative lateral side."""
        return max(0.0, self.y_max)

    def thickness(self):
        return self.total_thickness


def get_wall_section(wall):
    """Returns the normalized wall section used by the wall-joint solver."""
    if not wall:
        return None

    align = getattr(wall, "Align", "Center")
    raw_layers = _get_section_layer_thicknesses(wall)
    if not raw_layers:
        return None

    total = sum(abs(layer) for layer in raw_layers)
    y_offset = _get_initial_y_offset(total, align)
    layers = []
    for index, raw_thickness in enumerate(raw_layers):
        thickness = abs(raw_thickness)
        layer = WallSectionLayer(
            index=index,
            raw_thickness=raw_thickness,
            thickness=thickness,
            y_min=y_offset,
            y_max=y_offset + thickness,
            visible=raw_thickness > 0,
        )
        layers.append(layer)
        y_offset += thickness

    if layers:
        y_min = min(layer.y_min for layer in layers)
        y_max = max(layer.y_max for layer in layers)
    else:
        y_min = 0.0
        y_max = 0.0

    return WallSection(
        total_thickness=total,
        align=align,
        y_min=y_min,
        y_max=y_max,
        layers=layers,
        wall=wall,
    )


def coerce_wall_section(section_or_wall):
    """Returns a WallSection from an existing section or a wall object."""
    if isinstance(section_or_wall, WallSection):
        return section_or_wall
    return get_wall_section(section_or_wall)


def get_section_thickness(section_or_wall):
    """Returns the total thickness of a section-like input."""
    section = coerce_wall_section(section_or_wall)
    if section:
        return section.total_thickness
    if section_or_wall is None:
        return None
    return float(section_or_wall)


def get_section_extent_towards(section_or_wall, lateral_direction, world_direction):
    """Returns the section extent on the side pointed to by the given world direction."""
    section = coerce_wall_section(section_or_wall)
    if not section or lateral_direction is None or world_direction is None:
        return None
    if lateral_direction.Length <= 1e-9 or world_direction.Length <= 1e-9:
        return section.total_thickness / 2.0
    if lateral_direction.dot(world_direction) >= 0:
        return section.positive_extent
    return section.negative_extent


def _get_section_layer_thicknesses(wall):
    proxy = getattr(wall, "Proxy", None)
    if proxy and hasattr(proxy, "get_layers"):
        layers = proxy.get_layers(wall)
        if layers:
            return layers

    width = None
    if proxy and hasattr(proxy, "get_width"):
        width = proxy.get_width(wall, widths=False)
    if width is None and hasattr(wall, "Width"):
        width_value = getattr(wall.Width, "Value", wall.Width)
        width = width_value
    if width is None:
        return None
    return [width]


def _get_initial_y_offset(total_thickness, align):
    if align == "Center":
        return -total_thickness / 2.0
    if align == "Left":
        return -total_thickness
    return 0.0

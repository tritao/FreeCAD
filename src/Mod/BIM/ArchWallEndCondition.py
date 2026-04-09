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

"""End-condition models for BIM wall trimming.

This module exposes wall-end trim contributors as ordered condition stacks.
Walls currently contribute manual endings and relation-derived endings, but the
stack model is intentionally open-ended so future cap and cleanup rules can be
resolved through the same mechanism.
"""

from dataclasses import dataclass, field

import FreeCAD

END_CONDITION_SOURCES = ("Relation", "Manual")
DEFAULT_END_CONDITION_ORDER = ["Relation", "Manual"]


@dataclass
class WallEndCondition:
    """One trim contributor for a wall end."""

    source: str
    placement: FreeCAD.Placement = field(default_factory=FreeCAD.Placement)
    is_global: bool = False
    enabled: bool = True

    def is_active(self):
        return self.enabled and not is_null_placement(self.placement)


@dataclass
class WallEndConditionStack:
    """Ordered trim contributors for one wall end."""

    end_name: str
    order: list = field(default_factory=list)
    conditions: list = field(default_factory=list)

    def add(self, condition):
        if condition:
            self.conditions.append(condition)

    def ordered_conditions(self):
        normalized_order = normalize_end_condition_order(self.order)
        buckets = {source: [] for source in normalized_order}
        extras = []
        for condition in self.conditions:
            if condition.source in buckets:
                buckets[condition.source].append(condition)
            else:
                extras.append(condition)

        ordered = []
        for source in normalized_order:
            ordered.extend(buckets[source])
        ordered.extend(extras)
        return ordered

    def active_condition(self):
        for condition in self.ordered_conditions():
            if condition.is_active():
                return condition
        return None


def normalize_end_condition_order(order):
    """Normalizes a persisted provider order."""
    if order:
        normalized = []
        for source in order:
            if source in END_CONDITION_SOURCES and source not in normalized:
                normalized.append(source)
        if normalized:
            return normalized
    return list(DEFAULT_END_CONDITION_ORDER)


def is_null_placement(placement, tol=1e-9):
    if placement is None:
        return True
    return placement.Base.Length < tol and placement.Rotation.Angle < tol

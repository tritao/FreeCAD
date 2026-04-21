# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import Sequence, TypeAlias, TypedDict

Point3: TypeAlias = tuple[float, float, float]
ShapeSequence: TypeAlias = Sequence[Shape] | Shape
EdgeSequence: TypeAlias = Sequence[Edge]

OCCError: type[Exception]
OCCDomainError: type[Exception]
OCCRangeError: type[Exception]
OCCConstructionError: type[Exception]
OCCDimensionError: type[Exception]

ExportUnits = TypedDict(
    "ExportUnits",
    {
        "write.iges.unit": str,
        "write.step.unit": str,
    },
)

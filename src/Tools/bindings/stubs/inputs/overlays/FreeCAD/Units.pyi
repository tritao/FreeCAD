# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import Literal, TypeAlias, overload

from FreeCAD.Base import Quantity

_NumberFormat: TypeAlias = Literal["g", "f", "e"]

Radian: Quantity

@overload
def listSchemas() -> tuple[str, ...]: ...
@overload
def listSchemas(index: int, /) -> str: ...
@overload
def toNumber(value: Quantity, format: _NumberFormat = ..., decimals: int = ..., /) -> str: ...
@overload
def toNumber(value: float, format: _NumberFormat = ..., decimals: int = ..., /) -> str: ...

# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from FreeCAD import DocumentObject, Vector
from FreeCAD.Base import BoundBox, Matrix, Placement
from typing import Any, Literal, Sequence, TypeAlias, TypedDict, overload

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
@overload
def makeRevolution(
    pCrv: Geometry,
    vmin: float = ...,
    vmax: float = ...,
    angle: float = 360,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    type: type | None = None,
    /,
) -> Shape: ...
@overload
def makeRevolution(
    pCrv: Edge,
    vmin: float = ...,
    vmax: float = ...,
    angle: float = 360,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    type: type | None = None,
    /,
) -> Shape: ...

@overload
def makeWireString(
    intext: str | bytes,
    dir: str,
    fontfile: str,
    height: float,
    track: float = 0,
    /,
) -> list[list[Wire]]: ...
@overload
def makeWireString(
    intext: str | bytes, fontspec: str, height: float, track: float = 0, /
) -> list[list[Wire]]: ...
@overload
def setStaticValue(name: str, cval: str, /) -> None: ...
@overload
def setStaticValue(name: str, value: int | float, /) -> None: ...
@overload
def getShape(
    obj: DocumentObject,
    subname: str | None = None,
    mat: Matrix | None = None,
    needSubElement: bool = False,
    transform: bool = True,
    retType: Literal[0] = 0,
    noElementMap: bool = False,
    refine: bool = False,
) -> Shape: ...
@overload
def getShape(
    obj: DocumentObject,
    subname: str | None,
    mat: Matrix | None,
    needSubElement: bool,
    transform: bool,
    retType: Literal[1, 2],
    noElementMap: bool = False,
    refine: bool = False,
) -> tuple[Shape, Matrix, DocumentObject | None]: ...
@overload
def getShape(
    obj: DocumentObject,
    subname: str | None = None,
    mat: Matrix | None = None,
    needSubElement: bool = False,
    transform: bool = True,
    retType: int = 0,
    noElementMap: bool = False,
    refine: bool = False,
) -> Shape | tuple[Shape, Matrix, DocumentObject | None]: ...

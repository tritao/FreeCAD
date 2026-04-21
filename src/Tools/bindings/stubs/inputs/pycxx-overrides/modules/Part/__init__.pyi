# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

def open(Name: str, /) -> None: ...
def insert(Name: str, DocName: str, /) -> None: ...
def export(object: Sequence[DocumentObject], Name: str, /) -> None: ...
def read(Name: str, /) -> Shape: ...
def show(pcObj: Shape, name: str = "Shape", /) -> Feature: ...
def getFacets(shape: Shape, /) -> list[tuple[Point3, Point3, Point3]]: ...
def makeCompound(shapes: ShapeSequence, force: Any = ..., op: str | None = None) -> Compound: ...
def makeShell(shapes: ShapeSequence, op: str | None = None) -> Shell: ...
def makeFace(
    shapes: ShapeSequence,
    class_name: str | None = None,
    op: str | None = None,
    *,
    noElementMap: bool = False,
) -> Face: ...
def makeFilledSurface(
    shapes: ShapeSequence,
    surface: Shape | None = None,
    supports: Any = None,
    orders: Any = None,
    degree: int = ...,
    ptsOnCurve: int = ...,
    numIter: int = ...,
    anisotropy: bool = ...,
    tol2d: float = ...,
    tol3d: float = ...,
    tolG1: float = ...,
    tolG2: float = ...,
    maxDegree: int = ...,
    maxSegments: int = ...,
    op: str | None = None,
) -> Face: ...
def makeFilledFace(
    shapes: ShapeSequence,
    surface: Shape | None = None,
    supports: Any = None,
    orders: Any = None,
    degree: int = ...,
    ptsOnCurve: int = ...,
    numIter: int = ...,
    anisotropy: bool = ...,
    tol2d: float = ...,
    tol3d: float = ...,
    tolG1: float = ...,
    tolG2: float = ...,
    maxDegree: int = ...,
    maxSegments: int = ...,
    op: str | None = None,
) -> Face: ...
def makeSolid(shape: Shape, op: str | None = None) -> Solid: ...
def makeRuledSurface(
    path: Edge | Wire,
    profile: Edge | Wire,
    orientation: int = 0,
    op: str | None = None,
) -> Face | Shell: ...
def makeShellFromWires(shape: ShapeSequence, op: str | None = None) -> Shell: ...
def makeTube(
    pshape: Shape,
    radius: float,
    scont: str = "C0",
    maxdegree: int = 3,
    maxsegment: int = 30,
    /,
) -> Face: ...
def makeSweepSurface(
    path: Shape,
    profile: Shape,
    tolerance: float = 0.001,
    fillMode: int = 0,
    /,
) -> Shape: ...
def makeLoft(
    shapes: list[Shape],
    solid: bool = False,
    ruled: bool = False,
    closed: bool = False,
    max_degree: int = 5,
    op: str | None = None,
) -> Shape: ...
def makePlane(
    length: float,
    width: float,
    pPnt: Vector | None = None,
    pDirZ: Vector | None = None,
    pDirX: Vector | None = None,
    /,
) -> Face: ...
def makeBox(
    length: float,
    width: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    /,
) -> Solid: ...
def makeWedge(
    xmin: float,
    ymin: float,
    zmin: float,
    z2min: float,
    x2min: float,
    xmax: float,
    ymax: float,
    zmax: float,
    z2max: float,
    x2max: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    /,
) -> Solid: ...
def makeLine(obj1: Vector | Point3, obj2: Vector | Point3, /) -> Edge: ...
def makePolygon(pcObj: Sequence[Vector | Point3], pclosed: bool = False, /) -> Wire: ...
def makeCircle(
    radius: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = 0.0,
    angle2: float = 360,
    /,
) -> Edge: ...
def makeSphere(
    radius: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = -90,
    angle2: float = 90,
    angle3: float = 360,
    /,
) -> Solid: ...
def makeCylinder(
    radius: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle: float = 360,
    /,
) -> Solid: ...
def makeCone(
    radius1: float,
    radius2: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle: float = 360,
    /,
) -> Solid: ...
def makeTorus(
    radius1: float,
    radius2: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = 0.0,
    angle2: float = 360,
    angle: float = 360,
    /,
) -> Solid: ...
def makeHelix(
    pitch: float,
    height: float,
    radius: float,
    angle: float = -1.0,
    pleft: bool = False,
    pvertHeight: bool = False,
    /,
) -> Wire: ...
def makeLongHelix(
    pitch: float,
    height: float,
    radius: float,
    angle: float = -1.0,
    pleft: bool = False,
    /,
) -> Wire: ...
def makeThread(pitch: float, depth: float, height: float, radius: float, /) -> Wire: ...
def makeSplitShape(
    shape: Shape,
    list: Sequence[tuple[Shape, Shape]],
    checkInterior: bool = True,
    /,
) -> tuple[list[Shape], list[Shape]]: ...
def exportUnits(unit: str | None = None, /) -> ExportUnits: ...
def cast_to_shape(object: Shape, /) -> Shape: ...
def getSortedClusters(obj: EdgeSequence, /) -> list[list[Edge]]: ...
def __sortEdges__(obj: EdgeSequence, /) -> list[Edge]: ...
def sortEdges(obj: EdgeSequence, tol3d: float | None = None, /) -> list[list[Edge]]: ...
def __toPythonOCC__(pcObj: Shape, /) -> Any: ...
def __fromPythonOCC__(proxy: Any, /) -> Shape: ...
def clearShapeCache() -> Any: ...
def splitSubname(subname: str, /) -> list[str]: ...
def joinSubname(sub: str, mapped: str, element: str, /) -> str: ...

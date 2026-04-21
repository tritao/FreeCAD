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

def open(Name: str, /) -> None:
    """Create a new document and load the file into it."""
    ...

def insert(Name: str, DocName: str, /) -> None:
    """Insert the file into the named document, creating the document if needed."""
    ...

def export(object: Sequence[DocumentObject], Name: str, /) -> None:
    """Export document objects into a single shape file."""
    ...

def read(Name: str, /) -> Shape:
    """Load a shape file and return the shape."""
    ...

def show(pcObj: Shape, name: str = "Shape", /) -> Feature:
    """Add a shape to the active document and return the document object."""
    ...

def getFacets(shape: Shape, /) -> list[tuple[Point3, Point3, Point3]]:
    """Return triangulated face facets for a shape."""
    ...

def makeCompound(shapes: ShapeSequence, force: Any = ..., op: str | None = None) -> Compound:
    """Create a compound from a shape or sequence of shapes."""
    ...

def makeShell(shapes: ShapeSequence, op: str | None = None) -> Shell:
    """Create a shell from shapes."""
    ...

def makeFace(
    shapes: ShapeSequence,
    class_name: str | None = None,
    op: str | None = None,
    *,
    noElementMap: bool = False,
) -> Face:
    """Create a face using a face-maker class."""
    ...

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
) -> Face:
    """Create a filled surface from boundary curves."""
    ...

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
) -> Face:
    """Create a filled face from boundary edges."""
    ...

def makeSolid(shape: Shape, op: str | None = None) -> Solid:
    """Create a solid from the shells of a shape."""
    ...

def makePlane(
    length: float,
    width: float,
    pPnt: Vector | None = None,
    pDirZ: Vector | None = None,
    pDirX: Vector | None = None,
    /,
) -> Face:
    """Create a plane face."""
    ...

def makeBox(
    length: float,
    width: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    /,
) -> Solid:
    """Create a box solid."""
    ...

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
) -> Solid:
    """Create a wedge solid."""
    ...

def makeLine(obj1: Vector | Point3, obj2: Vector | Point3, /) -> Edge:
    """Create an edge between two points."""
    ...

def makePolygon(pcObj: Sequence[Vector | Point3], pclosed: bool = False, /) -> Wire:
    """Create a polygon wire from points."""
    ...

def makeCircle(
    radius: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = 0.0,
    angle2: float = 360,
    /,
) -> Edge:
    """Create a circle edge."""
    ...

def makeSphere(
    radius: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = -90,
    angle2: float = 90,
    angle3: float = 360,
    /,
) -> Solid:
    """Create a sphere solid."""
    ...

def makeCylinder(
    radius: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle: float = 360,
    /,
) -> Solid:
    """Create a cylinder solid."""
    ...

def makeCone(
    radius1: float,
    radius2: float,
    height: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle: float = 360,
    /,
) -> Solid:
    """Create a cone solid."""
    ...

def makeTorus(
    radius1: float,
    radius2: float,
    pPnt: Vector | None = None,
    pDir: Vector | None = None,
    angle1: float = 0.0,
    angle2: float = 360,
    angle: float = 360,
    /,
) -> Solid:
    """Create a torus solid."""
    ...

def makeHelix(
    pitch: float,
    height: float,
    radius: float,
    angle: float = -1.0,
    pleft: bool = False,
    pvertHeight: bool = False,
    /,
) -> Wire:
    """Create a helix wire."""
    ...

def makeLongHelix(
    pitch: float,
    height: float,
    radius: float,
    angle: float = -1.0,
    pleft: bool = False,
    /,
) -> Wire:
    """Create a multi-edge helix wire."""
    ...

def makeThread(pitch: float, depth: float, height: float, radius: float, /) -> Wire:
    """Create a thread wire."""
    ...

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
def makeRuledSurface(
    path: Edge | Wire,
    profile: Edge | Wire,
    orientation: int = 0,
    op: str | None = None,
) -> Face | Shell:
    """Create a ruled surface from two edges or wires."""
    ...

def makeShellFromWires(shape: ShapeSequence, op: str | None = None) -> Shell:
    """Create a shell from wires."""
    ...

def makeTube(
    pshape: Shape,
    radius: float,
    scont: str = "C0",
    maxdegree: int = 3,
    maxsegment: int = 30,
    /,
) -> Face:
    """Create a tube face along an edge."""
    ...

def makeSweepSurface(
    path: Shape,
    profile: Shape,
    tolerance: float = 0.001,
    fillMode: int = 0,
    /,
) -> Shape:
    """Create a sweep surface from a path and profile."""
    ...

def makeLoft(
    shapes: list[Shape],
    solid: bool = False,
    ruled: bool = False,
    closed: bool = False,
    max_degree: int = 5,
    op: str | None = None,
) -> Shape:
    """Create a loft shape."""
    ...

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
def makeSplitShape(
    shape: Shape,
    list: Sequence[tuple[Shape, Shape]],
    checkInterior: bool = True,
    /,
) -> tuple[list[Shape], list[Shape]]:
    """Split a shape with edge/face or wire/face pairs."""
    ...

def exportUnits(unit: str | None = None, /) -> ExportUnits:
    """Set or return STEP and IGES export units."""
    ...

@overload
def setStaticValue(name: str, cval: str, /) -> None: ...
@overload
def setStaticValue(name: str, value: int | float, /) -> None: ...
def cast_to_shape(object: Shape, /) -> Shape:
    """Cast to the actual shape subtype."""
    ...

def getSortedClusters(obj: EdgeSequence, /) -> list[list[Edge]]:
    """Cluster a sequence of edges."""
    ...

def __sortEdges__(obj: EdgeSequence, /) -> list[Edge]:
    """Sort one connected run of edges."""
    ...

def sortEdges(obj: EdgeSequence, tol3d: float | None = None, /) -> list[list[Edge]]:
    """Sort all edges into connected runs."""
    ...

def __toPythonOCC__(pcObj: Shape, /) -> Any:
    """Convert an internal shape to a pythonocc shape."""
    ...

def __fromPythonOCC__(proxy: Any, /) -> Shape:
    """Convert a pythonocc shape to an internal shape."""
    ...

def clearShapeCache() -> Any:
    """Clear the internal Part shape cache."""
    ...

def splitSubname(subname: str, /) -> list[str]:
    """Split a subname into sub, mapped, and subelement components."""
    ...

def joinSubname(sub: str, mapped: str, element: str, /) -> str:
    """Join sub, mapped, and subelement components into a subname."""
    ...

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

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
ExportUnits = TypedDict('ExportUnits', {'write.iges.unit': str, 'write.step.unit': str})

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

def show(pcObj: Shape, name: str='Shape', /) -> Feature:
    """Add a shape to the active document and return the document object."""
    ...

def getFacets(shape: Shape, /) -> list[tuple[Point3, Point3, Point3]]:
    """Return triangulated face facets for a shape."""
    ...

def makeCompound(shapes: ShapeSequence, force: Any=..., op: str | None=None) -> Compound:
    """Create a compound from a shape or sequence of shapes."""
    ...

def makeShell(shapes: ShapeSequence, op: str | None=None) -> Shell:
    """Create a shell from shapes."""
    ...

def makeFace(shapes: ShapeSequence, class_name: str | None=None, op: str | None=None, *, noElementMap: bool=False) -> Face:
    """Create a face using a face-maker class."""
    ...

def makeFilledSurface(shapes: ShapeSequence, surface: Shape | None=None, supports: Any=None, orders: Any=None, degree: int=..., ptsOnCurve: int=..., numIter: int=..., anisotropy: bool=..., tol2d: float=..., tol3d: float=..., tolG1: float=..., tolG2: float=..., maxDegree: int=..., maxSegments: int=..., op: str | None=None) -> Face:
    """Create a filled surface from boundary curves."""
    ...

def makeFilledFace(shapes: ShapeSequence, surface: Shape | None=None, supports: Any=None, orders: Any=None, degree: int=..., ptsOnCurve: int=..., numIter: int=..., anisotropy: bool=..., tol2d: float=..., tol3d: float=..., tolG1: float=..., tolG2: float=..., maxDegree: int=..., maxSegments: int=..., op: str | None=None) -> Face:
    """Create a filled face from boundary edges."""
    ...

def makeSolid(shape: Shape, op: str | None=None) -> Solid:
    """Create a solid from the shells of a shape."""
    ...

def makePlane(length: float, width: float, pPnt: Vector | None=None, pDirZ: Vector | None=None, pDirX: Vector | None=None, /) -> Face:
    """Create a plane face."""
    ...

def makeBox(length: float, width: float, height: float, pPnt: Vector | None=None, pDir: Vector | None=None, /) -> Solid:
    """Create a box solid."""
    ...

def makeWedge(xmin: float, ymin: float, zmin: float, z2min: float, x2min: float, xmax: float, ymax: float, zmax: float, z2max: float, x2max: float, pPnt: Vector | None=None, pDir: Vector | None=None, /) -> Solid:
    """Create a wedge solid."""
    ...

def makeLine(obj1: Vector | Point3, obj2: Vector | Point3, /) -> Edge:
    """Create an edge between two points."""
    ...

def makePolygon(pcObj: Sequence[Vector | Point3], pclosed: bool=False, /) -> Wire:
    """Create a polygon wire from points."""
    ...

def makeCircle(radius: float, pPnt: Vector | None=None, pDir: Vector | None=None, angle1: float=0.0, angle2: float=360, /) -> Edge:
    """Create a circle edge."""
    ...

def makeSphere(radius: float, pPnt: Vector | None=None, pDir: Vector | None=None, angle1: float=-90, angle2: float=90, angle3: float=360, /) -> Solid:
    """Create a sphere solid."""
    ...

def makeCylinder(radius: float, height: float, pPnt: Vector | None=None, pDir: Vector | None=None, angle: float=360, /) -> Solid:
    """Create a cylinder solid."""
    ...

def makeCone(radius1: float, radius2: float, height: float, pPnt: Vector | None=None, pDir: Vector | None=None, angle: float=360, /) -> Solid:
    """Create a cone solid."""
    ...

def makeTorus(radius1: float, radius2: float, pPnt: Vector | None=None, pDir: Vector | None=None, angle1: float=0.0, angle2: float=360, angle: float=360, /) -> Solid:
    """Create a torus solid."""
    ...

def makeHelix(pitch: float, height: float, radius: float, angle: float=-1.0, pleft: bool=False, pvertHeight: bool=False, /) -> Wire:
    """Create a helix wire."""
    ...

def makeLongHelix(pitch: float, height: float, radius: float, angle: float=-1.0, pleft: bool=False, /) -> Wire:
    """Create a multi-edge helix wire."""
    ...

def makeThread(pitch: float, depth: float, height: float, radius: float, /) -> Wire:
    """Create a thread wire."""
    ...

@overload
def makeRevolution(pCrv: Geometry, vmin: float=..., vmax: float=..., angle: float=360, pPnt: Vector | None=None, pDir: Vector | None=None, type: type | None=None, /) -> Shape:
    ...

@overload
def makeRevolution(pCrv: Edge, vmin: float=..., vmax: float=..., angle: float=360, pPnt: Vector | None=None, pDir: Vector | None=None, type: type | None=None, /) -> Shape:
    ...

def makeRuledSurface(path: Edge | Wire, profile: Edge | Wire, orientation: int=0, op: str | None=None) -> Face | Shell:
    """Create a ruled surface from two edges or wires."""
    ...

def makeShellFromWires(shape: ShapeSequence, op: str | None=None) -> Shell:
    """Create a shell from wires."""
    ...

def makeTube(pshape: Shape, radius: float, scont: str='C0', maxdegree: int=3, maxsegment: int=30, /) -> Face:
    """Create a tube face along an edge."""
    ...

def makeSweepSurface(path: Shape, profile: Shape, tolerance: float=0.001, fillMode: int=0, /) -> Shape:
    """Create a sweep surface from a path and profile."""
    ...

def makeLoft(shapes: list[Shape], solid: bool=False, ruled: bool=False, closed: bool=False, max_degree: int=5, op: str | None=None) -> Shape:
    """Create a loft shape."""
    ...

@overload
def makeWireString(intext: str | bytes, dir: str, fontfile: str, height: float, track: float=0, /) -> list[list[Wire]]:
    ...

@overload
def makeWireString(intext: str | bytes, fontspec: str, height: float, track: float=0, /) -> list[list[Wire]]:
    ...

def makeSplitShape(shape: Shape, list: Sequence[tuple[Shape, Shape]], checkInterior: bool=True, /) -> tuple[list[Shape], list[Shape]]:
    """Split a shape with edge/face or wire/face pairs."""
    ...

def exportUnits(unit: str | None=None, /) -> ExportUnits:
    """Set or return STEP and IGES export units."""
    ...

@overload
def setStaticValue(name: str, cval: str, /) -> None:
    ...

@overload
def setStaticValue(name: str, value: int | float, /) -> None:
    ...

def cast_to_shape(object: Shape, /) -> Shape:
    """Cast to the actual shape subtype."""
    ...

def getSortedClusters(obj: EdgeSequence, /) -> list[list[Edge]]:
    """Cluster a sequence of edges."""
    ...

def __sortEdges__(obj: EdgeSequence, /) -> list[Edge]:
    """Sort one connected run of edges."""
    ...

def sortEdges(obj: EdgeSequence, tol3d: float | None=None, /) -> list[list[Edge]]:
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
def getShape(obj: DocumentObject, subname: str | None=None, mat: Matrix | None=None, needSubElement: bool=False, transform: bool=True, retType: Literal[0]=0, noElementMap: bool=False, refine: bool=False) -> Shape:
    ...

@overload
def getShape(obj: DocumentObject, subname: str | None, mat: Matrix | None, needSubElement: bool, transform: bool, retType: Literal[1, 2], noElementMap: bool=False, refine: bool=False) -> tuple[Shape, Matrix, DocumentObject | None]:
    ...

@overload
def getShape(obj: DocumentObject, subname: str | None=None, mat: Matrix | None=None, needSubElement: bool=False, transform: bool=True, retType: int=0, noElementMap: bool=False, refine: bool=False) -> Shape | tuple[Shape, Matrix, DocumentObject | None]:
    ...
from FreeCAD.Base import Vector
from FreeCAD.Base import BaseClass
from FreeCAD.Base import Placement
from FreeCAD import DocumentObjectExtension
from FreeCAD.Base import Axis as AxisPy
from FreeCAD.Base import Persistence
from FreeCAD import Extension
from FreeCAD.Base import Matrix
from FreeCAD.Base import Rotation as RotationPy
from FreeCAD.Base import TypeId as Type
from FreeCAD import GeoFeature
from FreeCAD import ComplexGeoData
import Part
from typing import *
from FreeCAD.Base import Precision as Precision

class Arc(TrimmedCurve):
    """
    Describes a portion of a curve

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    @overload
    def __init__(self, circ: Geom_Circle, T: type=...) -> None:
        ...

    @overload
    def __init__(self, circ: Geom_Ellipse, T: type=...) -> None:
        ...

    @overload
    def __init__(self, p1: Vector, p2: Vector, p3: Vector, /) -> None:
        ...

class ArcOfCircle(ArcOfConic):
    """
    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    Describes a portion of a circle
    """
    Radius: float = ...
    'The radius of the circle.'
    Circle: Final[object] = ...
    'The internal circle representation'

class ArcOfConic(TrimmedCurve):
    """
    Describes a portion of a conic

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...
    Location: Vector = ...
    'Center of the conic.'
    Center: Vector = ...
    'Deprecated -- use Location.'
    AngleXU: float = ...
    'The angle between the X axis and the major axis of the conic.'
    Axis: Vector = ...
    'The axis direction of the conic'
    XAxis: Vector = ...
    'The X axis direction of the circle'
    YAxis: Vector = ...
    'The Y axis direction of the circle'

class ArcOfEllipse(ArcOfConic):
    """
    Describes a portion of an ellipse

    Author: Abdullah Tahiri (abdullah.tahiri.yo[at]gmail.com)
    Licence: LGPL
    """
    MajorRadius: float = ...
    'The major radius of the ellipse.'
    MinorRadius: float = ...
    'The minor radius of the ellipse.'
    Ellipse: Final[object] = ...
    'The internal ellipse representation'

    def __init__(self, ellipse: 'Part.Ellipse', u1: float, u2: float, sense: bool=..., /) -> None:
        ...

class ArcOfHyperbola(ArcOfConic):
    """
    Describes a portion of an hyperbola
    """
    MajorRadius: float = 0.0
    'The major radius of the hyperbola.'
    MinorRadius: float = 0.0
    'The minor radius of the hyperbola.'
    Hyperbola: Final[object] = ...
    'The internal hyperbola representation'

class ArcOfParabola(ArcOfConic):
    """
    Describes a portion of a parabola

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    Focal: float = ...
    'The focal length of the parabola.'
    Parabola: Final[object] = ...
    'The internal parabola representation'

class AttachEngine(BaseClass):
    """
    AttachEngine abstract class - the functionality of AttachableObject, but outside of DocumentObject

    Author: DeepSOIC (vv.titov@gmail.com)
    Licence: LGPL
    DeveloperDocu: AttachEngine abstract class
    """
    AttacherType: Final[str] = ''
    'Type of engine: 3d, plane, line, or point.'
    Mode: str = ''
    'Current attachment mode.'
    References: object = ...
    'Current attachment mode.'
    AttachmentOffset: object = ...
    'Current attachment mode.'
    Reverse: bool = False
    'If True, Z axis of attached placement is flipped. X axis is flipped in addition (CS has to remain right-handed).'
    Parameter: float = 0.0
    'Value of parameter for some curve attachment modes. Range of 0..1 spans the length of the edge (parameter value can be outside of the range for curves that allow extrapolation.'
    CompleteModeList: Final[list] = []
    'List of all attachment modes of all AttachEngines. This is the list of modes in MapMode enum properties of AttachableObjects.'
    ImplementedModes: Final[list] = []
    'List of all attachment modes of all AttachEngines. This is the list of modes in MapMode enum properties of AttachableObjects.'
    CompleteRefTypeList: Final[list] = []
    'List of all reference shape types recognized by AttachEngine.'

    def getModeInfo(self, mode: str, /) -> dict:
        """
        getModeInfo(mode): returns supported reference combinations, user-friendly name, and so on.
        """
        ...

    def getRefTypeOfShape(self, shape: str, /) -> str:
        """
        getRefTypeOfShape(shape): returns shape type as interpreted by AttachEngine. Returns a string.
        """
        ...

    def isFittingRefType(self, type_shape: str, type_needed: str, /) -> bool:
        """
        isFittingRefType(type_shape, type_needed): tests if shape type, specified by type_shape (string), fits a type required by attachment mode type_needed (string). e.g. 'Circle' fits a requirement of 'Edge', and 'Curve' doesn't fit if a 'Circle' is required.
        """
        ...

    def downgradeRefType(self, type: str, /) -> str:
        """
        downgradeRefType(type): returns next more general type. E.g. downgradeType('Circle') yields 'Curve'.
        """
        ...

    def getRefTypeInfo(self, type: str, /) -> dict:
        """
        getRefTypeInfo(type): returns information (dict) on shape type. Keys:'UserFriendlyName', 'TypeIndex', 'Rank'. Rank is the number of times reftype can be downgraded, before it becomes 'Any'.
        """
        ...

    def copy(self) -> 'AttachEngine':
        """
        copy(): returns a new instance of AttachEngine.
        """
        ...

    def calculateAttachedPlacement(self, orig_placement: Placement, /) -> Optional[Placement]:
        """
        calculateAttachedPlacement(orig_placement): returns result of attachment, based
        on current Mode, References, etc. AttachmentOffset is included.

        original_placement is the previous placement of the object being attached. It
        is used to preserve orientation for Translate attachment mode. For other modes,
        it is ignored.

        Returns the new placement. If not attached, returns None. If attachment fails,
        an exception is raised.
        """
        ...

    def suggestModes(self) -> dict:
        """
        suggestModes(): runs mode suggestion routine and returns a dictionary with
        results and supplementary information.

        Keys:
        'allApplicableModes': list of modes that can accept current references. Note
        that it is only a check by types, and does not guarantee the modes will
        actually work.

        'bestFitMode': mode that fits current references best. Note that the mode may
        not be valid for the set of references; check for if 'message' is 'OK'.

        'error': error message for when 'message' is 'UnexpectedError' or
        'LinkBroken'.

        'message': general result of suggestion. 'IncompatibleGeometry', 'NoModesFit':
        no modes accept current set of references; 'OK': some modes do accept current
        set of references (though it's not guarantted the modes will work - surrestor
        only checks for correct types); 'UnexpectedError': should never happen.

        'nextRefTypeHint': what more can be added to references to reach other modes
        ('reachableModes' provide more extended information on this)

        'reachableModes': a dict, where key is mode, and value is a list of sequences
        of references that can be added to fit that mode.

        'references_Types': a list of types of geometry linked by references (that's
        the input information for suggestor, actually).
        """
        ...

    def readParametersFromFeature(self, document_object: DocumentObject, /) -> None:
        """
        readParametersFromFeature(document_object): sets AttachEngine parameters (References, Mode, etc.) by reading out properties of AttachableObject-derived feature.
        """
        ...

    def writeParametersToFeature(self, document_object: DocumentObject, /) -> None:
        """
        writeParametersToFeature(document_object): updates properties of
        AttachableObject-derived feature with current AttachEngine parameters
        (References, Mode, etc.).

        Warning: if a feature linked by AttachEngine.References was deleted, this method
        will crash FreeCAD.
        """
        ...

class AttachExtension(DocumentObjectExtension):
    """
    This object represents an attachable object with OCC shape.

    Author: DeepSOIC (vv.titov@gmail.com)
    Licence: LGPL
    """
    Attacher: Final[Any] = ...
    'AttachEngine object driving this AttachableObject. Returns a copy.'

    def positionBySupport(self) -> bool:
        """
        positionBySupport() -> bool

        Reposition object based on AttachmentSupport, MapMode and MapPathParameter properties.
        Returns True if attachment calculation was successful, false if object is not attached and Placement wasn't updated,
        and raises an exception if attachment calculation fails.
        """
        ...

    def changeAttacherType(self, typename: str, /) -> None:
        """
        changeAttacherType(typename) -> None

        Changes Attacher class of this object.
        typename: string. The following are accepted so far:
        'Attacher::AttachEngine3D'
        'Attacher::AttachEnginePlane'
        'Attacher::AttachEngineLine'
        'Attacher::AttachEnginePoint'
        """
        ...

class BSplineCurve(BoundedCurve):
    """
    Describes a B-Spline curve in 3D space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Degree: Final[int] = 0
    'Returns the polynomial degree of this B-Spline curve.'
    MaxDegree: Final[int] = 25
    '\n    Returns the value of the maximum polynomial degree of any\n    B-Spline curve curve. This value is 25.\n    '
    NbPoles: Final[int] = 0
    'Returns the number of poles of this B-Spline curve.'
    NbKnots: Final[int] = 0
    'Returns the number of knots of this B-Spline curve.'
    StartPoint: Final[Vector] = Vector()
    'Returns the start point of this B-Spline curve.'
    EndPoint: Final[Vector] = Vector()
    'Returns the end point of this B-Spline curve.'
    FirstUKnotIndex: Final[int] = 0
    '\n    Returns the index in the knot array of the knot\n    corresponding to the first or last parameter\n    of this B-Spline curve.\n    '
    LastUKnotIndex: Final[int] = 0
    '\n    Returns the index in the knot array of the knot\n    corresponding to the first or last parameter\n    of this B-Spline curve.\n    '
    KnotSequence: Final[List[float]] = []
    'Returns the knots sequence of this B-Spline curve.'

    def __reduce__(self) -> Any:
        """
        __reduce__()
        Serialization of Part.BSplineCurve objects
        """
        ...

    def isRational(self) -> bool:
        """
        Returns true if this B-Spline curve is rational.
        A B-Spline curve is rational if, at the time of construction,
        the weight table has been initialized.
        """
        ...

    def isPeriodic(self) -> bool:
        """
        Returns true if this BSpline curve is periodic.
        """
        ...

    def isClosed(self) -> bool:
        """
        Returns true if the distance between the start point and end point of
        this B-Spline curve is less than or equal to gp::Resolution().
        """
        ...

    def increaseDegree(self, Degree: int=..., /) -> None:
        """
        increase(Int=Degree)
        Increases the degree of this B-Spline curve to Degree.
        As a result, the poles, weights and multiplicities tables
        are modified; the knots table is not changed. Nothing is
        done if Degree is less than or equal to the current degree.
        """
        ...

    @overload
    def increaseMultiplicity(self, index: int, mult: int, /) -> None:
        ...

    @overload
    def increaseMultiplicity(self, start: int, end: int, mult: int, /) -> None:
        ...

    def increaseMultiplicity(self, *args, **kwargs) -> None:
        """
        increaseMultiplicity(int index, int mult)
        increaseMultiplicity(int start, int end, int mult)
        Increases multiplicity of knots up to mult.

        index: the index of a knot to modify (1-based)
        start, end: index range of knots to modify.
        If mult is lower or equal to the current multiplicity nothing is done.
        If mult is higher than the degree the degree is used.
        """
        ...

    def incrementMultiplicity(self, start: int, end: int, mult: int, /) -> None:
        """
        incrementMultiplicity(int start, int end, int mult)

        Raises multiplicity of knots by mult.

        start, end: index range of knots to modify.
        """
        ...

    def insertKnot(self, u: float, mult: int=1, tol: float=0.0, /) -> None:
        """
        insertKnot(u, mult = 1, tol = 0.0)

        Inserts a knot value in the sequence of knots. If u is an existing knot the
        multiplicity is increased by mult.
        """
        ...

    def insertKnots(self, list_of_floats: List[float], list_of_ints: List[int], tol: float=0.0, bool_add: bool=True, /) -> None:
        """
        insertKnots(list_of_floats, list_of_ints, tol = 0.0, bool_add = True)

        Inserts a set of knots values in the sequence of knots.

        For each u = list_of_floats[i], mult = list_of_ints[i]

        If u is an existing knot the multiplicity is increased by mult if bool_add is
        True, otherwise increased to mult.

        If u is not on the parameter range nothing is done.

        If the multiplicity is negative or null nothing is done. The new multiplicity
        is limited to the degree.

        The tolerance criterion for knots equality is the max of Epsilon(U) and ParametricTolerance.
        """
        ...

    def removeKnot(self, Index: int, M: int, tol: float, /) -> bool:
        """
        removeKnot(Index, M, tol)

        Reduces the multiplicity of the knot of index Index to M.
        If M is equal to 0, the knot is removed.
        With a modification of this type, the array of poles is also modified.
        Two different algorithms are systematically used to compute the new
        poles of the curve. If, for each pole, the distance between the pole
        calculated using the first algorithm and the same pole calculated using
        the second algorithm, is less than Tolerance, this ensures that the curve
        is not modified by more than Tolerance. Under these conditions, true is
        returned; otherwise, false is returned.

        A low tolerance is used to prevent modification of the curve.
        A high tolerance is used to 'smooth' the curve.
        """
        ...

    def segment(self, u1: float, u2: float, /) -> None:
        """
        segment(u1,u2)

        Modifies this B-Spline curve by segmenting it.
        """
        ...

    def split(self, u: float, tolerance: float=0.0, /) -> tuple[BSplineCurve, BSplineCurve]:
        """
        split(u, tolerance=0.0)

        Splits this B-Spline curve at parameter u and returns the two resulting curves.
        """
        ...

    def setKnot(self, knot: float, index: int, /) -> None:
        """
        Set a knot of the B-Spline curve.
        """
        ...

    def getKnot(self, index: int, /) -> float:
        """
        Get a knot of the B-Spline curve.
        """
        ...

    def setKnots(self, knots: List[float], /) -> None:
        """
        Set knots of the B-Spline curve.
        """
        ...

    def getKnots(self) -> List[float]:
        """
        Get all knots of the B-Spline curve.
        """
        ...

    def setPole(self, P: Vector, Index: int, /) -> None:
        """
        Modifies this B-Spline curve by assigning P
        to the pole of index Index in the poles table.
        """
        ...

    def getPole(self, Index: int, /) -> Vector:
        """
        Get a pole of the B-Spline curve.
        """
        ...

    def getPoles(self) -> List[Vector]:
        """
        Get all poles of the B-Spline curve.
        """
        ...

    def setWeight(self, weight: float, index: int, /) -> None:
        """
        Set a weight of the B-Spline curve.
        """
        ...

    def getWeight(self, index: int, /) -> float:
        """
        Get a weight of the B-Spline curve.
        """
        ...

    def getWeights(self) -> List[float]:
        """
        Get all weights of the B-Spline curve.
        """
        ...

    def getPolesAndWeights(self) -> List[float]:
        """
        Returns the table of poles and weights in homogeneous coordinates.
        """
        ...

    def getResolution(self, Tolerance3D: float, /) -> float:
        """
        Computes for this B-Spline curve the parametric tolerance (UTolerance)
        for a given 3D tolerance (Tolerance3D).
        If f(t) is the equation of this B-Spline curve, the parametric tolerance
        ensures that:
        |t1-t0| < UTolerance =""==> |f(t1)-f(t0)| < Tolerance3D
        """
        ...

    def movePoint(self, U: float, P: Vector, Index1: int, Index2: int, /) -> tuple[int, int]:
        """
        movePoint(U, P, Index1, Index2)

        Moves the point of parameter U of this B-Spline curve to P.
        Index1 and Index2 are the indexes in the table of poles of this B-Spline curve
        of the first and last poles designated to be moved.

        Returns: (FirstModifiedPole, LastModifiedPole). They are the indexes of the
        first and last poles which are effectively modified.
        """
        ...

    def setNotPeriodic(self) -> None:
        """
        Changes this B-Spline curve into a non-periodic curve.
        If this curve is already non-periodic, it is not modified.
        """
        ...

    def setPeriodic(self) -> None:
        """
        Changes this B-Spline curve into a periodic curve.
        """
        ...

    def setOrigin(self, Index: int, /) -> None:
        """
        Assigns the knot of index Index in the knots table
        as the origin of this periodic B-Spline curve. As a consequence,
        the knots and poles tables are modified.
        """
        ...

    def getMultiplicity(self, index: int, /) -> int:
        """
        Returns the multiplicity of the knot of index
        from the knots table of this B-Spline curve.
        """
        ...

    def getMultiplicities(self) -> List[int]:
        """
        Returns the multiplicities table M of the knots of this B-Spline curve.
        """
        ...

    @overload
    def approximate(self, Points: List[Vector], DegMin: int=3, DegMax: int=8, Tolerance: float=0.001, Continuity: str='C2', LengthWeight: float=0.0, CurvatureWeight: float=0.0, TorsionWeight: float=0.0, Parameters: List[float]=None, ParamType: str='Uniform') -> None:
        ...

    def approximate(self, **kwargs) -> None:
        """
        Replaces this B-Spline curve by approximating a set of points.

        The function accepts keywords as arguments.

        approximate(Points = list_of_points)

        Optional arguments :

        DegMin = integer (3) : Minimum degree of the curve.
        DegMax = integer (8) : Maximum degree of the curve.
        Tolerance = float (1e-3) : approximating tolerance.
        Continuity = string ('C2') : Desired continuity of the curve.
        Possible values : 'C0','G1','C1','G2','C2','C3','CN'

        LengthWeight = float, CurvatureWeight = float, TorsionWeight = float
        If one of these arguments is not null, the functions approximates the
        points using variational smoothing algorithm, which tries to minimize
        additional criterium:
        LengthWeight*CurveLength + CurvatureWeight*Curvature + TorsionWeight*Torsion
                Continuity must be C0, C1(with DegMax >= 3) or C2(with DegMax >= 5).

        Parameters = list of floats : knot sequence of the approximated points.
        This argument is only used if the weights above are all null.

        ParamType = string ('Uniform','Centripetal' or 'ChordLength')
        Parameterization type. Only used if weights and Parameters above aren't specified.

        Note : Continuity of the spline defaults to C2. However, it may not be applied if
        it conflicts with other parameters ( especially DegMax ).
        """
        ...

    @overload
    def getCardinalSplineTangents(self, **kwargs) -> List[Vector]:
        ...

    def getCardinalSplineTangents(self, **kwargs) -> List[Vector]:
        """
        Compute the tangents for a Cardinal spline
        """
        ...

    @overload
    def interpolate(self, Points: List[Vector], PeriodicFlag: bool=False, Tolerance: float=1e-06, Parameters: List[float]=None, InitialTangent: Vector=None, FinalTangent: Vector=None, Tangents: List[Vector]=None, TangentFlags: List[bool]=None) -> None:
        ...

    def interpolate(self, **kwargs) -> None:
        """
        Replaces this B-Spline curve by interpolating a set of points.

        The function accepts keywords as arguments.

        interpolate(Points = list_of_points)

        Optional arguments :

        PeriodicFlag = bool (False) : Sets the curve closed or opened.
        Tolerance = float (1e-6) : interpolating tolerance

        Parameters : knot sequence of the interpolated points.
        If not supplied, the function defaults to chord-length parameterization.
        If PeriodicFlag == True, one extra parameter must be appended.

        EndPoint Tangent constraints :

        InitialTangent = vector, FinalTangent = vector
        specify tangent vectors for starting and ending points
        of the BSpline. Either none, or both must be specified.

        Full Tangent constraints :

        Tangents = list_of_vectors, TangentFlags = list_of_bools
        Both lists must have the same length as Points list.
        Tangents specifies the tangent vector of each point in Points list.
        TangentFlags (bool) activates or deactivates the corresponding tangent.
        These arguments will be ignored if EndPoint Tangents (above) are also defined.

        Note : Continuity of the spline defaults to C2. However, if periodic, or tangents
        are supplied, the continuity will drop to C1.
        """
        ...

    def buildFromPoles(self, poles: List[Vector], periodic: bool=False, degree: int=3, interpolate: bool=False, /) -> None:
        """
        Builds a B-Spline by a list of poles.
        arguments: poles (sequence of Base.Vector), [periodic (default is False), degree (default is 3), interpolate (default is False)]

        Examples:
        from FreeCAD import Base
        import Part
        V = Base.Vector
        poles = [V(-2, 2, 0),V(0, 2, 1),V(2, 2, 0),V(2, -2, 0),V(0, -2, 1),V(-2, -2, 0)]

        # non-periodic spline
        n=Part.BSplineCurve()
        n.buildFromPoles(poles)
        Part.show(n.toShape())

        # periodic spline
        n=Part.BSplineCurve()
        n.buildFromPoles(poles, True)
        Part.show(n.toShape())
        """
        ...

    @overload
    def buildFromPolesMultsKnots(self, poles: List[Vector], mults: List[int], knots: List[float], periodic: bool, degree: int, weights: List[float]=None, CheckRational: bool=False) -> None:
        ...

    def buildFromPolesMultsKnots(self, **kwargs) -> None:
        """
        Builds a B-Spline by a lists of Poles, Mults, Knots.
        arguments: poles (sequence of Base.Vector), [mults , knots, periodic, degree, weights (sequence of float), CheckRational]

        Examples:
        from FreeCAD import Base
        import Part
        V=Base.Vector
        poles=[V(-10,-10),V(10,-10),V(10,10),V(-10,10)]

        # non-periodic spline
        n=Part.BSplineCurve()
        n.buildFromPolesMultsKnots(poles,(3,1,3),(0,0.5,1),False,2)
        Part.show(n.toShape())

        # periodic spline
        p=Part.BSplineCurve()
        p.buildFromPolesMultsKnots(poles,(1,1,1,1,1),(0,0.25,0.5,0.75,1),True,2)
        Part.show(p.toShape())

        # periodic and rational spline
        r=Part.BSplineCurve()
        r.buildFromPolesMultsKnots(poles,(1,1,1,1,1),(0,0.25,0.5,0.75,1),True,2,(1,0.8,0.7,0.2))
        Part.show(r.toShape())
        """
        ...

    def toBezier(self) -> List[BezierCurve]:
        """
        Build a list of Bezier splines.
        """
        ...

    def toBiArcs(self, tolerance: float, /) -> List[Arc]:
        """
        Build a list of arcs and lines to approximate the B-spline.
        toBiArcs(tolerance) -> list.
        """
        ...

    def join(self, other: 'BSplineCurve', /) -> None:
        """
        Build a new spline by joining this and a second spline.
        """
        ...

    def makeC1Continuous(self, tol: float=1e-06, ang_tol: float=1e-07, /) -> 'BSplineCurve':
        """
        makeC1Continuous(tol = 1e-6, ang_tol = 1e-7)
        Reduces as far as possible the multiplicities of the knots of this BSpline
        (keeping the geometry). It returns a new BSpline, which could still be C0.
        tol is a geometrical tolerance.
        The tol_ang is angular tolerance, in radians. It sets tolerable angle mismatch
        of the tangents on the left and on the right to decide if the curve is G1 or
        not at a given point.
        """
        ...

    def scaleKnotsToBounds(self, u0: float=0.0, u1: float=1.0, /) -> None:
        """
        Scales the knots list to fit the specified bounds.
        The shape of the curve is not modified.
        bspline_curve.scaleKnotsToBounds(u0, u1)
        Default arguments are (0.0, 1.0)
        """
        ...

class BSplineSurface(GeometrySurface):
    """
    Describes a B-Spline surface in 3D space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    DeveloperDocu: Describes a B-Spline surface in 3D space
    """
    UDegree: Final[int] = 0
    'Returns the degree of this B-Spline surface in the u parametric direction.'
    VDegree: Final[int] = 0
    'Returns the degree of this B-Spline surface in the v parametric direction.'
    MaxDegree: Final[int] = 25
    '\n    Returns the value of the maximum polynomial degree of any\n    B-Spline surface surface in either parametric directions.\n    This value is 25.\n    '
    NbUPoles: Final[int] = 0
    'Returns the number of poles of this B-Spline surface in the u parametric direction.'
    NbVPoles: Final[int] = 0
    'Returns the number of poles of this B-Spline surface in the v parametric direction.'
    NbUKnots: Final[int] = 0
    'Returns the number of knots of this B-Spline surface in the u parametric direction.'
    NbVKnots: Final[int] = 0
    'Returns the number of knots of this B-Spline surface in the v parametric direction.'
    FirstUKnotIndex: Final[Any] = ...
    '\n    Returns the index in the knot array associated with the u parametric direction,\n    which corresponds to the first parameter of this B-Spline surface in the specified\n    parametric direction.\n\n    The isoparametric curves corresponding to these values are the boundary curves of\n    this surface.\n\n    Note: The index does not correspond to the first knot of the surface in the specified\n    parametric direction unless the multiplicity of the first knot is equal to Degree + 1,\n    where Degree is the degree of this surface in the corresponding parametric direction.\n    '
    LastUKnotIndex: Final[Any] = ...
    '\n    Returns the index in the knot array associated with the u parametric direction,\n    which corresponds to the last parameter of this B-Spline surface in the specified\n    parametric direction.\n\n    The isoparametric curves corresponding to these values are the boundary curves of\n    this surface.\n\n    Note: The index does not correspond to the first knot of the surface in the specified\n    parametric direction unless the multiplicity of the last knot is equal to Degree + 1,\n    where Degree is the degree of this surface in the corresponding parametric direction.\n    '
    FirstVKnotIndex: Final[Any] = ...
    '\n    Returns the index in the knot array associated with the v parametric direction,\n    which corresponds to the first parameter of this B-Spline surface in the specified\n    parametric direction.\n\n    The isoparametric curves corresponding to these values are the boundary curves of\n    this surface.\n\n    Note: The index does not correspond to the first knot of the surface in the specified\n    parametric direction unless the multiplicity of the first knot is equal to Degree + 1,\n    where Degree is the degree of this surface in the corresponding parametric direction.\n    '
    LastVKnotIndex: Final[Any] = ...
    '\n    Returns the index in the knot array associated with the v parametric direction,\n    which corresponds to the last parameter of this B-Spline surface in the specified\n    parametric direction.\n\n    The isoparametric curves corresponding to these values are the boundary curves of\n    this surface.\n\n    Note: The index does not correspond to the first knot of the surface in the specified\n    parametric direction unless the multiplicity of the last knot is equal to Degree + 1,\n    where Degree is the degree of this surface in the corresponding parametric direction.\n    '
    UKnotSequence: Final[List[Any]] = []
    '\n    Returns the knots sequence of this B-Spline surface in\n    the u direction.\n    '
    VKnotSequence: Final[List[Any]] = []
    '\n    Returns the knots sequence of this B-Spline surface in\n    the v direction.\n    '

    def bounds(self) -> Any:
        """
        Returns the parametric bounds (U1, U2, V1, V2) of this B-Spline surface.
        """
        ...

    def isURational(self) -> Any:
        """
        Returns false if the equation of this B-Spline surface is polynomial
        (e.g. non-rational) in the u or v parametric direction.
        In other words, returns false if for each row of poles, the associated
        weights are identical
        """
        ...

    def isVRational(self) -> Any:
        """
        Returns false if the equation of this B-Spline surface is polynomial
        (e.g. non-rational) in the u or v parametric direction.
        In other words, returns false if for each column of poles, the associated
        weights are identical
        """
        ...

    def isUPeriodic(self) -> Any:
        """
        Returns true if this surface is periodic in the u parametric direction.
        """
        ...

    def isVPeriodic(self) -> Any:
        """
        Returns true if this surface is periodic in the v parametric direction.
        """
        ...

    def isUClosed(self) -> Any:
        """
        Checks if this surface is closed in the u parametric direction.
        Returns true if, in the table of poles the first row and the last
        row are identical.
        """
        ...

    def isVClosed(self) -> Any:
        """
        Checks if this surface is closed in the v parametric direction.
        Returns true if, in the table of poles the first column and the
        last column are identical.
        """
        ...

    def increaseDegree(self, DegMin: int, DegMax: int, Continuity: int, Tolerance: float, X0: float=..., dX: float=..., Y0: float=..., dY: float=..., /) -> None:
        """
        increase(Int=UDegree, int=VDegree)
        Increases the degrees of this B-Spline surface to UDegree and VDegree
        in the u and v parametric directions respectively.
        As a result, the tables of poles, weights and multiplicities are modified.
        The tables of knots is not changed.

        Note: Nothing is done if the given degree is less than or equal to the
        current degree in the corresponding parametric direction.
        """
        ...

    def increaseUMultiplicity(self) -> None:
        """
        Increases the multiplicity in the u direction.
        """
        ...

    def increaseVMultiplicity(self) -> None:
        """
        Increases the multiplicity in the v direction.
        """
        ...

    def incrementUMultiplicity(self) -> None:
        """
        Increment the multiplicity in the u direction
        """
        ...

    def incrementVMultiplicity(self) -> None:
        """
        Increment the multiplicity in the v direction
        """
        ...

    def insertUKnot(self, U: float, Index: int, Tolerance: float, /) -> None:
        """
        insertUKnote(float U, int Index, float Tolerance) - Insert or override a knot
        """
        ...

    def insertUKnots(self, U: List[float], Mult: List[float], Tolerance: float, /) -> None:
        """
        insertUKnote(List of float U, List of float Mult, float Tolerance) - Inserts knots.
        """
        ...

    def insertVKnot(self, V: float, Index: int, Tolerance: float, /) -> None:
        """
        insertUKnote(float V, int Index, float Tolerance) - Insert or override a knot.
        """
        ...

    def insertVKnots(self, V: List[float], Mult: List[float], Tolerance: float, /) -> None:
        """
        insertUKnote(List of float V, List of float Mult, float Tolerance) - Inserts knots.
        """
        ...

    def removeUKnot(self, M: int, Index: int, Tolerance: float, /) -> bool:
        """
        Reduces to M the multiplicity of the knot of index Index in the given
        parametric direction. If M is 0, the knot is removed.
        With a modification of this type, the table of poles is also modified.
        Two different algorithms are used systematically to compute the new
        poles of the surface. For each pole, the distance between the pole
        calculated using the first algorithm and the same pole calculated using
        the second algorithm, is checked. If this distance is less than Tolerance
        it ensures that the surface is not modified by more than Tolerance.
        Under these conditions, the function returns true; otherwise, it returns
        false.

        A low tolerance prevents modification of the surface. A high tolerance
        'smoothes' the surface.
        """
        ...

    def removeVKnot(self, M: int, Index: int, Tolerance: float, /) -> bool:
        """
        Reduces to M the multiplicity of the knot of index Index in the given
        parametric direction. If M is 0, the knot is removed.
        With a modification of this type, the table of poles is also modified.
        Two different algorithms are used systematically to compute the new
        poles of the surface. For each pole, the distance between the pole
        calculated using the first algorithm and the same pole calculated using
        the second algorithm, is checked. If this distance is less than Tolerance
        it ensures that the surface is not modified by more than Tolerance.
        Under these conditions, the function returns true; otherwise, it returns
        false.

        A low tolerance prevents modification of the surface. A high tolerance
        'smoothes' the surface.
        """
        ...

    def segment(self, U1: float, U2: float, V1: float, V2: float, /) -> None:
        """
        Modifies this B-Spline surface by segmenting it between U1 and U2 in the
        u parametric direction and between V1 and V2 in the v parametric direction.
        Any of these values can be outside the bounds of this surface, but U2 must
        be greater than U1 and V2 must be greater than V1.

        All the data structure tables of this B-Spline surface are modified but the
        knots located between U1 and U2 in the u parametric direction, and between
        V1 and V2 in the v parametric direction are retained.
        The degree of the surface in each parametric direction is not modified.
        """
        ...

    def setUKnot(self, K: float, UIndex: int, M: int=..., /) -> None:
        """
        Modifies this B-Spline surface by assigning the value K to the knot of index
        UIndex of the knots table corresponding to the u parametric direction.
        This modification remains relatively local, since K must lie between the values
        of the knots which frame the modified knot.

        You can also increase the multiplicity of the modified knot to M. Note however
        that it is not possible to decrease the multiplicity of a knot with this function.
        """
        ...

    def setVKnot(self, K: float, VIndex: int, M: int=..., /) -> None:
        """
        Modifies this B-Spline surface by assigning the value K to the knot of index
        VIndex of the knots table corresponding to the v parametric direction.
        This modification remains relatively local, since K must lie between the values
        of the knots which frame the modified knot.

        You can also increase the multiplicity of the modified knot to M. Note however
        that it is not possible to decrease the multiplicity of a knot with this function.
        """
        ...

    def getUKnot(self, UIndex: int, /) -> Any:
        """
        Returns, for this B-Spline surface, in the u parametric direction
        the knot of index UIndex of the knots table.
        """
        ...

    def getVKnot(self, VIndex: int, /) -> Any:
        """
        Returns, for this B-Spline surface, in the v parametric direction
        the knot of index VIndex of the knots table.
        """
        ...

    def setUKnots(self, knots: List[Any], /) -> None:
        """
        Changes all knots of this B-Spline surface in the u parametric
        direction. The multiplicity of the knots is not modified.
        """
        ...

    def setVKnots(self, knots: List[Any], /) -> None:
        """
        Changes all knots of this B-Spline surface in the v parametric
        direction. The multiplicity of the knots is not modified.
        """
        ...

    def getUKnots(self) -> List[Any]:
        """
        Returns, for this B-Spline surface, the knots table
        in the u parametric direction
        """
        ...

    def getVKnots(self) -> List[Any]:
        """
        Returns, for this B-Spline surface, the knots table
        in the v parametric direction
        """
        ...

    def setPole(self, P: Any, UIndex: int, VIndex: int, Weight: float=..., /) -> None:
        """
        Modifies this B-Spline surface by assigning P to the pole of
        index (UIndex, VIndex) in the poles table.
        The second syntax allows you also to change the weight of the
        modified pole. The weight is set to Weight. This syntax must
        only be used for rational surfaces.
        Modifies this B-Spline curve by assigning P to the pole of
        index Index in the poles table.
        """
        ...

    def setPoleCol(self, VIndex: int, values: List[Any], CPoleWeights: List[float], /) -> None:
        """
        Modifies this B-Spline surface by assigning values to all or part
        of the column of poles of index VIndex, of this B-Spline surface.
        You can also change the weights of the modified poles. The weights
        are set to the corresponding values of CPoleWeights.
        These syntaxes must only be used for rational surfaces.
        """
        ...

    def setPoleRow(self, UIndex: int, values: List[Any], CPoleWeights: List[float], /) -> None:
        """
        Modifies this B-Spline surface by assigning values to all or part
        of the row of poles of index UIndex, of this B-Spline surface.
        You can also change the weights of the modified poles. The weights
        are set to the corresponding values of CPoleWeights.
        These syntaxes must only be used for rational surfaces.
        """
        ...

    def getPole(self, UIndex: int, VIndex: int, /) -> Any:
        """
        Returns the pole of index (UIndex,VIndex) of this B-Spline surface.
        """
        ...

    def getPoles(self) -> List[Any]:
        """
        Returns the table of poles of this B-Spline surface.
        """
        ...

    def setWeight(self, Weight: float, UIndex: int, VIndex: int, /) -> None:
        """
        Modifies this B-Spline surface by assigning the value Weight to the weight
        of the pole of index (UIndex, VIndex) in the poles tables of this B-Spline
        surface.

        This function must only be used for rational surfaces.
        """
        ...

    def setWeightCol(self, VIndex: int, CPoleWeights: List[float], /) -> None:
        """
        Modifies this B-Spline surface by assigning values to all or part of the
        weights of the column of poles of index VIndex of this B-Spline surface.

        The modified part of the column of weights is defined by the bounds
        of the array CPoleWeights.

        This function must only be used for rational surfaces.
        """
        ...

    def setWeightRow(self, UIndex: int, CPoleWeights: List[float], /) -> None:
        """
        Modifies this B-Spline surface by assigning values to all or part of the
        weights of the row of poles of index UIndex of this B-Spline surface.

        The modified part of the row of weights is defined by the bounds of the
        array CPoleWeights.

        This function must only be used for rational surfaces.
        """
        ...

    def getWeight(self, UIndex: int, VIndex: int, /) -> float:
        """
        Return the weight of the pole of index (UIndex,VIndex)
        in the poles table for this B-Spline surface.
        """
        ...

    def getWeights(self) -> List[float]:
        """
        Returns the table of weights of the poles for this B-Spline surface.
        """
        ...

    def getPolesAndWeights(self) -> List[Any]:
        """
        Returns the table of poles and weights in homogeneous coordinates.
        """
        ...

    def getResolution(self, Tolerance3D: float, /) -> Any:
        """
        Computes two tolerance values for this B-Spline surface, based on the
        given tolerance in 3D space Tolerance3D. The tolerances computed are:
        -- UTolerance in the u parametric direction and
        -- VTolerance in the v parametric direction.

        If f(u,v) is the equation of this B-Spline surface, UTolerance and
        VTolerance guarantee that:
        |u1 - u0| < UTolerance
        |v1 - v0| < VTolerance
        ====> ||f(u1, v1) - f(u2, v2)|| < Tolerance3D
        """
        ...

    def movePoint(self, U: float, V: float, P: Any, UIndex1: int=..., UIndex2: int=..., VIndex1: int=..., VIndex2: int=..., /) -> Any:
        """
        Moves the point of parameters (U, V) of this B-Spline surface to P.
        UIndex1, UIndex2, VIndex1 and VIndex2 are the indexes in the poles
        table of this B-Spline surface, of the first and last poles which
        can be moved in each parametric direction.
        The returned indexes UFirstIndex, ULastIndex, VFirstIndex and
        VLastIndex are the indexes of the first and last poles effectively
        modified in each parametric direction.
        In the event of incompatibility between UIndex1, UIndex2, VIndex1,
        VIndex2 and the values U and V:
        -- no change is made to this B-Spline surface, and
        -- UFirstIndex, ULastIndex, VFirstIndex and VLastIndex are set to
           null.
        """
        ...

    def setUNotPeriodic(self) -> None:
        """
        Changes this B-Spline surface into a non-periodic one in the u parametric direction.
        If this B-Spline surface is already non-periodic in the given parametric direction,
        it is not modified.
        If this B-Spline surface is periodic in the given parametric direction, the boundaries
        of the surface are not given by the first and last rows (or columns) of poles (because
        the multiplicity of the first knot and of the last knot in the given parametric direction
        are not modified, nor are they equal to Degree+1, where Degree is the degree of this
        B-Spline surface in the given parametric direction). Only the function Segment ensures
        this property.

        Note: the poles and knots tables are modified.
        """
        ...

    def setVNotPeriodic(self) -> None:
        """
        Changes this B-Spline surface into a non-periodic one in the v parametric direction.
        If this B-Spline surface is already non-periodic in the given parametric direction,
        it is not modified.
        If this B-Spline surface is periodic in the given parametric direction, the boundaries
        of the surface are not given by the first and last rows (or columns) of poles (because
        the multiplicity of the first knot and of the last knot in the given parametric direction
        are not modified, nor are they equal to Degree+1, where Degree is the degree of this
        B-Spline surface in the given parametric direction). Only the function Segment ensures
        this property.

        Note: the poles and knots tables are modified.
        """
        ...

    def setUPeriodic(self, I1: int, I2: int, /) -> None:
        """
        Modifies this surface to be periodic in the u parametric direction.
        To become periodic in a given parametric direction a surface must
        be closed in that parametric direction, and the knot sequence relative
        to that direction must be periodic.
        To generate this periodic sequence of knots, the functions FirstUKnotIndex
        and LastUKnotIndex are used to compute I1 and I2. These are the indexes,
        in the knot array associated with the given parametric direction, of the
        knots that correspond to the first and last parameters of this B-Spline
        surface in the given parametric direction. Hence the period is:

        Knots(I1) - Knots(I2)

        As a result, the knots and poles tables are modified.
        """
        ...

    def setVPeriodic(self, I1: int, I2: int, /) -> None:
        """
        Modifies this surface to be periodic in the v parametric direction.
        To become periodic in a given parametric direction a surface must
        be closed in that parametric direction, and the knot sequence relative
        to that direction must be periodic.
        To generate this periodic sequence of knots, the functions FirstUKnotIndex
        and LastUKnotIndex are used to compute I1 and I2. These are the indexes,
        in the knot array associated with the given parametric direction, of the
        knots that correspond to the first and last parameters of this B-Spline
        surface in the given parametric direction. Hence the period is:

        Knots(I1) - Knots(I2)

        As a result, the knots and poles tables are modified.
        """
        ...

    def setUOrigin(self, Index: int, /) -> None:
        """
        Assigns the knot of index Index in the knots table
        in the u parametric direction to be the origin of
        this periodic B-Spline surface. As a consequence,
        the knots and poles tables are modified.
        """
        ...

    def setVOrigin(self, Index: int, /) -> None:
        """
        Assigns the knot of index Index in the knots table
        in the v parametric direction to be the origin of
        this periodic B-Spline surface. As a consequence,
        the knots and poles tables are modified.
        """
        ...

    def getUMultiplicity(self, UIndex: int, /) -> Any:
        """
        Returns, for this B-Spline surface, the multiplicity of
        the knot of index UIndex in the u parametric direction.
        """
        ...

    def getVMultiplicity(self, VIndex: int, /) -> Any:
        """
        Returns, for this B-Spline surface, the multiplicity of
        the knot of index VIndex in the v parametric direction.
        """
        ...

    def getUMultiplicities(self) -> List[Any]:
        """
        Returns, for this B-Spline surface, the table of
        multiplicities in the u parametric direction
        """
        ...

    def getVMultiplicities(self) -> List[Any]:
        """
        Returns, for this B-Spline surface, the table of
        multiplicities in the v parametric direction
        """
        ...

    def exchangeUV(self) -> None:
        """
        Exchanges the u and v parametric directions on this B-Spline surface.
        As a consequence:
        -- the poles and weights tables are transposed,
        -- the knots and multiplicities tables are exchanged,
        -- degrees of continuity and rational, periodic and uniform
           characteristics are exchanged and
        -- the orientation of the surface is reversed.
        """
        ...

    def reparametrize(self) -> Any:
        """
        Returns a reparametrized copy of this surface
        """
        ...

    def approximate(self, *, Points: Any=..., DegMin: int=..., DegMax: int=..., Continuity: int=..., Tolerance: float=..., X0: float=..., dX: float=..., Y0: float=..., dY: float=..., ParamType: str=..., LengthWeight: float=..., CurvatureWeight: float=..., TorsionWeight: float=...) -> None:
        """
        Replaces this B-Spline surface by approximating a set of points.
        This method uses keywords :
        - Points = 2Darray of points (or floats, in combination with X0, dX, Y0, dY)
        - DegMin (int), DegMax (int)
        - Continuity = 0,1 or 2 (for C0, C1, C2)
        - Tolerance (float)
        - X0, dX, Y0, dY (floats) with Points = 2Darray of floats
        - ParamType = 'Uniform','Centripetal' or 'ChordLength'
        - LengthWeight, CurvatureWeight, TorsionWeight (floats)
        (with this smoothing algorithm, continuity C1 requires DegMax >= 3 and C2, DegMax >=5)

        Possible combinations :
        - approximate(Points, DegMin, DegMax, Continuity, Tolerance)
        - approximate(Points, DegMin, DegMax, Continuity, Tolerance, X0, dX, Y0, dY)
        With explicit keywords :
        - approximate(Points, DegMin, DegMax, Continuity, Tolerance, ParamType)
        - approximate(Points, DegMax, Continuity, Tolerance, LengthWeight, CurvatureWeight, TorsionWeight)
        """
        ...

    def interpolate(self, points: Any=..., zpoints: Any=..., X0: float=..., dX: float=..., Y0: float=..., dY: float=..., /) -> None:
        """
        interpolate(points)
        interpolate(zpoints, X0, dX, Y0, dY)

        Replaces this B-Spline surface by interpolating a set of points.
        The resulting surface is of degree 3 and continuity C2.
        Arguments:
        a 2 dimensional array of vectors, that the surface passes through
        or
        a 2 dimensional array of floats with the z values,
        the x starting point X0 (float),
        the x increment dX (float),
        the y starting point Y0 and increment dY
        """
        ...

    def buildFromPolesMultsKnots(self, *, poles: List[List[Any]], umults: List[Any], vmults: List[Any], uknots: List[Any]=..., vknots: List[Any]=..., uperiodic: bool=..., vperiodic: bool=..., udegree: int=..., vdegree: int=..., weights: List[List[float]]=...) -> None:
        """
        Builds a B-Spline by a lists of Poles, Mults and Knots
        arguments: poles (sequence of sequence of Base.Vector), umults, vmults, [uknots, vknots, uperiodic, vperiodic, udegree, vdegree, weights (sequence of sequence of float)]
        """
        ...

    def buildFromNSections(self, control_curves: Any, /) -> None:
        """
        Builds a B-Spline from a list of control curves
        """
        ...

    def scaleKnotsToBounds(self, u0: float, u1: float, v0: float, v1: float, /) -> None:
        """
        Scales the U and V knots lists to fit the specified bounds.
        The shape of the surface is not modified.
        bspline_surf.scaleKnotsToBounds(u0, u1, v0, v1)
        Default arguments are 0.0, 1.0, 0.0, 1.0
        """
        ...

class BezierCurve(BoundedCurve):
    """
    Describes a rational or non-rational Bezier curve:
    -- a non-rational Bezier curve is defined by a table of poles (also called control points)
    -- a rational Bezier curve is defined by a table of poles with varying weights

    Constructor takes no arguments.

    Example usage:
        p1 = Base.Vector(-1, 0, 0)
        p2 = Base.Vector(0, 1, 0.2)
        p3 = Base.Vector(1, 0, 0.4)
        p4 = Base.Vector(0, -1, 1)

        bc = BezierCurve()
        bc.setPoles([p1, p2, p3, p4])
        curveShape = bc.toShape()
    """
    Degree: Final[int] = 0
    '\n    Returns the polynomial degree of this Bezier curve,\n    which is equal to the number of poles minus 1.\n    '
    MaxDegree: Final[int] = 25
    '\n    Returns the value of the maximum polynomial degree of any\n    Bezier curve curve. This value is 25.\n    '
    NbPoles: Final[int] = 0
    'Returns the number of poles of this Bezier curve.'
    StartPoint: Final[Vector] = Vector()
    'Returns the start point of this Bezier curve.'
    EndPoint: Final[Vector] = Vector()
    'Returns the end point of this Bezier curve.'

    def isRational(self) -> bool:
        """
        Returns false if the weights of all the poles of this Bezier curve are equal.
        """
        ...

    def isPeriodic(self) -> bool:
        """
        Returns false.
        """
        ...

    def isClosed(self) -> bool:
        """
        Returns true if the distance between the start point and end point of
        this Bezier curve is less than or equal to gp::Resolution().
        """
        ...

    def increase(self, Int: int=..., /) -> None:
        """
        Increases the degree of this Bezier curve to Degree.
        As a result, the poles and weights tables are modified.
        """
        ...

    def insertPoleAfter(self, index: int, /) -> None:
        """
        Inserts after the pole of index.
        """
        ...

    def insertPoleBefore(self, index: int, /) -> None:
        """
        Inserts before the pole of index.
        """
        ...

    def removePole(self, Index: int, /) -> None:
        """
        Removes the pole of index Index from the table of poles of this Bezier curve.
        If this Bezier curve is rational, it can become non-rational.
        """
        ...

    def segment(self) -> None:
        """
        Modifies this Bezier curve by segmenting it.
        """
        ...

    def setPole(self, pole: Vector, /) -> None:
        """
        Set a pole of the Bezier curve.
        """
        ...

    def getPole(self, index: int, /) -> Vector:
        """
        Get a pole of the Bezier curve.
        """
        ...

    def getPoles(self) -> List[Vector]:
        """
        Get all poles of the Bezier curve.
        """
        ...

    def setPoles(self, poles: List[Vector], /) -> None:
        """
        Set the poles of the Bezier curve.

        Takes a list of 3D Base.Vector objects.
        """
        ...

    def setWeight(self, id: int, weight: float, /) -> None:
        """
        (id, weight) Set a weight of the Bezier curve.
        """
        ...

    def getWeight(self, id: int, /) -> float:
        """
        Get a weight of the Bezier curve.
        """
        ...

    def getWeights(self) -> List[float]:
        """
        Get all weights of the Bezier curve.
        """
        ...

    def getResolution(self, Tolerance3D: float, /) -> float:
        """
        Computes for this Bezier curve the parametric tolerance (UTolerance)
        for a given 3D tolerance (Tolerance3D).
        If f(t) is the equation of this Bezier curve, the parametric tolerance
        ensures that:
        |t1-t0| < UTolerance =""==> |f(t1)-f(t0)| < Tolerance3D
        """
        ...

    def interpolate(self, constraints: List[List], parameters: List[float]=..., /) -> None:
        """
        Interpolates a list of constraints.
        Each constraint is a list of a point and some optional derivatives
        An optional list of parameters can be passed. It must be of same size as constraint list.
        Otherwise, a simple uniform parametrization is used.
        Example :
        bezier.interpolate([[pt1, deriv11, deriv12], [pt2,], [pt3, deriv31]], [0, 0.4, 1.0])
        """
        ...

class BezierSurface(GeometrySurface):
    """
    Describes a rational or non-rational Bezier surface
    -- A non-rational Bezier surface is defined by a table of poles (also known as control points).
    -- A rational Bezier surface is defined by a table of poles with varying associated weights.
    """
    UDegree: Final[int]
    '\n    Returns the polynomial degree in u direction of this Bezier surface,\n    which is equal to the number of poles minus 1.\n    '
    VDegree: Final[int]
    '\n    Returns the polynomial degree in v direction of this Bezier surface,\n    which is equal to the number of poles minus 1.\n    '
    MaxDegree: Final[int]
    '\n    Returns the value of the maximum polynomial degree of any\n    Bezier surface. This value is 25.\n    '
    NbUPoles: Final[int]
    'Returns the number of poles in u direction of this Bezier surface.'
    NbVPoles: Final[int]
    'Returns the number of poles in v direction of this Bezier surface.'

    def bounds(self) -> Tuple[float, float, float, float]:
        """
        Returns the parametric bounds (U1, U2, V1, V2) of this Bezier surface.
        """
        ...

    def isURational(self) -> bool:
        """
        Returns false if the equation of this Bezier surface is polynomial
        (e.g. non-rational) in the u or v parametric direction.
        In other words, returns false if for each row of poles, the associated
        weights are identical.
        """
        ...

    def isVRational(self) -> bool:
        """
        Returns false if the equation of this Bezier surface is polynomial
        (e.g. non-rational) in the u or v parametric direction.
        In other words, returns false if for each column of poles, the associated
        weights are identical.
        """
        ...

    def isUPeriodic(self) -> bool:
        """
        Returns false.
        """
        ...

    def isVPeriodic(self) -> bool:
        """
        Returns false.
        """
        ...

    def isUClosed(self) -> bool:
        """
        Checks if this surface is closed in the u parametric direction.
        Returns true if, in the table of poles the first row and the last
        row are identical.
        """
        ...

    def isVClosed(self) -> bool:
        """
        Checks if this surface is closed in the v parametric direction.
        Returns true if, in the table of poles the first column and the
        last column are identical.
        """
        ...

    def increase(self, DegreeU: int, DegreeV: int, /) -> None:
        """
        increase(DegreeU: int, DegreeV: int)
        Increases the degree of this Bezier surface in the two
        parametric directions.
        """
        ...

    def insertPoleColAfter(self, index: int, /) -> None:
        """
        Inserts into the table of poles of this surface, after the column
        of poles of index.
        If this Bezier surface is non-rational, it can become rational if
        the weights associated with the new poles are different from each
        other, or collectively different from the existing weights in the
        table.
        """
        ...

    def insertPoleRowAfter(self, index: int, /) -> None:
        """
        Inserts into the table of poles of this surface, after the row
        of poles of index.
        If this Bezier surface is non-rational, it can become rational if
        the weights associated with the new poles are different from each
        other, or collectively different from the existing weights in the
        table.
        """
        ...

    def insertPoleColBefore(self, index: int, /) -> None:
        """
        Inserts into the table of poles of this surface, before the column
        of poles of index.
        If this Bezier surface is non-rational, it can become rational if
        the weights associated with the new poles are different from each
        other, or collectively different from the existing weights in the
        table.
        """
        ...

    def insertPoleRowBefore(self, index: int, /) -> None:
        """
        Inserts into the table of poles of this surface, before the row
        of poles of index.
        If this Bezier surface is non-rational, it can become rational if
        the weights associated with the new poles are different from each
        other, or collectively different from the existing weights in the
        table.
        """
        ...

    def removePoleCol(self, VIndex: int, /) -> None:
        """
        removePoleRow(VIndex: int)
        Removes the column of poles of index VIndex from the table of
        poles of this Bezier surface.
        If this Bezier curve is rational, it can become non-rational.
        """
        ...

    def removePoleRow(self, UIndex: int, /) -> None:
        """
        removePoleRow(UIndex: int)
        Removes the row of poles of index UIndex from the table of
        poles of this Bezier surface.
        If this Bezier curve is rational, it can become non-rational.
        """
        ...

    def segment(self, U1: float, U2: float, V1: float, V2: float, /) -> None:
        """
        segment(U1: double, U2: double, V1: double, V2: double)
        Modifies this Bezier surface by segmenting it between U1 and U2
        in the u parametric direction, and between V1 and V2 in the v
        parametric direction.
        U1, U2, V1, and V2 can be outside the bounds of this surface.

        -- U1 and U2 isoparametric Bezier curves, segmented between
            V1 and V2, become the two bounds of the surface in the v
            parametric direction (0. and 1. u isoparametric curves).
        -- V1 and V2 isoparametric Bezier curves, segmented between
            U1 and U2, become the two bounds of the surface in the u
            parametric direction (0. and 1. v isoparametric curves).

        The poles and weights tables are modified, but the degree of
        this surface in the u and v parametric directions does not
        change.U1 can be greater than U2, and V1 can be greater than V2.
        In these cases, the corresponding parametric direction is inverted.
        The orientation of the surface is inverted if one (and only one)
        parametric direction is inverted.
        """
        ...

    def setPole(self, pole: Any, /) -> None:
        """
        Set a pole of the Bezier surface.
        """
        ...

    def setPoleCol(self, poles: Any, /) -> None:
        """
        Set the column of poles of the Bezier surface.
        """
        ...

    def setPoleRow(self, poles: Any, /) -> None:
        """
        Set the row of poles of the Bezier surface.
        """
        ...

    def getPole(self, UIndex: int, VIndex: int, /) -> Any:
        """
        Get a pole of index (UIndex, VIndex) of the Bezier surface.
        """
        ...

    def getPoles(self) -> Any:
        """
        Get all poles of the Bezier surface.
        """
        ...

    def setWeight(self, UIndex: int, VIndex: int, weight: float, /) -> None:
        """
        Set the weight of pole of the index (UIndex, VIndex)
        for the Bezier surface.
        """
        ...

    def setWeightCol(self, VIndex: int, weights: Any, /) -> None:
        """
        Set the weights of the poles in the column of poles
        of index VIndex of the Bezier surface.
        """
        ...

    def setWeightRow(self, UIndex: int, weights: Any, /) -> None:
        """
        Set the weights of the poles in the row of poles
        of index UIndex of the Bezier surface.
        """
        ...

    def getWeight(self, UIndex: int, VIndex: int, /) -> float:
        """
        Get a weight of the pole of index (UIndex, VIndex)
        of the Bezier surface.
        """
        ...

    def getWeights(self) -> Any:
        """
        Get all weights of the Bezier surface.
        """
        ...

    def getResolution(self, Tolerance3D: float, /) -> Tuple[float, float]:
        """
        Computes two tolerance values for this Bezier surface, based on the
        given tolerance in 3D space Tolerance3D. The tolerances computed are:
        -- UTolerance in the u parametric direction and
        -- VTolerance in the v parametric direction.

        If f(u,v) is the equation of this Bezier surface, UTolerance and VTolerance
        guarantee that:
        |u1 - u0| < UTolerance
        |v1 - v0| < VTolerance
        ====> ||f(u1, v1) - f(u2, v2)|| < Tolerance3D
        """
        ...

    def exchangeUV(self) -> None:
        """
        Exchanges the u and v parametric directions on this Bezier surface.
        As a consequence:
        -- the poles and weights tables are transposed,
        -- degrees, rational characteristics and so on are exchanged between
           the two parametric directions, and
        -- the orientation of the surface is reversed.
        """
        ...

class BodyBase(Feature):
    """
    Base class of all Body objects

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    ...

class BoundedCurve(Curve):
    """
    The abstract class BoundedCurve is the root class of all bounded curve objects.

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    StartPoint: Final[Any] = ...
    'Returns the starting point of the bounded curve.'
    EndPoint: Final[Any] = ...
    'Returns the end point of the bounded curve.'

class Circle(Conic):
    """
    Describes a circle in 3D space
    To create a circle there are several ways:
    Part.Circle()
        Creates a default circle with center (0,0,0) and radius 1

    Part.Circle(Circle)
        Creates a copy of the given circle

    Part.Circle(Circle, Distance)
        Creates a circle parallel to given circle at a certain distance

    Part.Circle(Center,Normal,Radius)
        Creates a circle defined by center, normal direction and radius

    Part.Circle(Point1,Point2,Point3)
        Creates a circle defined by three non-linear points
    """
    Radius: float = 0.0
    'The radius of the circle.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, circle: 'Circle') -> None:
        ...

    @overload
    def __init__(self, circle: 'Circle', distance: float) -> None:
        ...

    @overload
    def __init__(self, center: Point, normal: Vector, radius: float) -> None:
        ...

    @overload
    def __init__(self, point1: Point, point2: Point, point3: Point) -> None:
        ...

class Cone(GeometrySurface):
    """
    Describes a cone in 3D space

    To create a cone there are several ways:

    Part.Cone()
        Creates a default cone with radius 1

    Part.Cone(Cone)
        Creates a copy of the given cone

    Part.Cone(Cone, Distance)
        Creates a cone parallel to given cone at a certain distance

    Part.Cone(Point1,Point2,Radius1,Radius2)
        Creates a cone defined by two points and two radii
        The axis of the cone is the line passing through
        Point1 and Poin2.
        Radius1 is the radius of the section passing through
        Point1 and Radius2 the radius of the section passing
        through Point2.

    Part.Cone(Point1,Point2,Point3,Point4)
        Creates a cone passing through three points Point1,
        Point2 and Point3.
        Its axis is defined by Point1 and Point2 and the radius of
        its base is the distance between Point3 and its axis.
        The distance between Point and the axis is the radius of
        the section passing through Point4.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Apex: Final[Vector] = Vector()
    'Compute the apex of the cone.'
    Radius: float = 0.0
    'The radius of the cone.'
    SemiAngle: float = 0.0
    'The semi-angle of the cone.'
    Center: Vector = Vector()
    'Center of the cone.'
    Axis: AxisPy = AxisPy()
    'The axis direction of the cone'

class Conic(Curve):
    """
    Describes an abstract conic in 3d space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Location: Vector = ...
    'Location of the conic.'
    Center: Vector = ...
    'Deprecated -- use Location.'
    Eccentricity: Final[float] = ...
    '\n    Returns the eccentricity value of the conic e.\n    e = 0 for a circle\n    0 < e < 1 for an ellipse  (e = 0 if MajorRadius = MinorRadius)\n    e > 1 for a hyperbola\n    e = 1 for a parabola\n    '
    AngleXU: float = ...
    'The angle between the X axis and the major axis of the conic.'
    Axis: Vector = ...
    'The axis direction of the circle'
    XAxis: Vector = ...
    'The X axis direction of the circle'
    YAxis: Vector = ...
    'The Y axis direction of the circle'

class Cylinder(GeometrySurface):
    """
    Describes a cylinder in 3D space

    To create a cylinder there are several ways:

    Part.Cylinder()
        Creates a default cylinder with center (0,0,0) and radius 1

    Part.Cylinder(Cylinder)
        Creates a copy of the given cylinder

    Part.Cylinder(Cylinder, Distance)
        Creates a cylinder parallel to given cylinder at a certain distance

    Part.Cylinder(Point1, Point2, Point2)
        Creates a cylinder defined by three non-linear points

    Part.Cylinder(Circle)
        Creates a cylinder by a circular base

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Radius: float
    'The radius of the cylinder.'
    Center: Vector
    'Center of the cylinder.'
    Axis: Vector
    'The axis direction of the cylinder'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, cylinder: 'Cylinder') -> None:
        ...

    @overload
    def __init__(self, cylinder: 'Cylinder', distance: float) -> None:
        ...

    @overload
    def __init__(self, point1: Vector, point2: Vector, point3: Vector) -> None:
        ...

    @overload
    def __init__(self, circle: Circle) -> None:
        ...

class Ellipse(Conic):
    """
    Describes an ellipse in 3D space

    To create an ellipse there are several ways:

    Part.Ellipse()
        Creates an ellipse with major radius 2 and minor radius 1 with the
        center in (0,0,0)

    Part.Ellipse(Ellipse)
        Create a copy of the given ellipse

    Part.Ellipse(S1,S2,Center)
        Creates an ellipse centered on the point Center, where
        the plane of the ellipse is defined by Center, S1 and S2,
        its major axis is defined by Center and S1,
        its major radius is the distance between Center and S1, and
        its minor radius is the distance between S2 and the major axis.

    Part.Ellipse(Center,MajorRadius,MinorRadius)
        Creates an ellipse with major and minor radii MajorRadius and
        MinorRadius, and located in the plane defined by Center and
        the normal (0,0,1)
    """
    MajorRadius: float = 0.0
    'The major radius of the ellipse.'
    MinorRadius: float = 0.0
    'The minor radius of the ellipse.'
    Focal: Final[float] = 0.0
    'The focal distance of the ellipse.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, ellipse: 'Ellipse', /) -> None:
        ...

    @overload
    def __init__(self, s1: Vector, s2: Vector, center: Vector, /) -> None:
        ...

    @overload
    def __init__(self, center: Vector, major_radius: float, minor_radius: float, /) -> None:
        ...
    Focus1: Final[Vector] = ...
    'The first focus is on the positive side of the major axis of the ellipse.'
    Focus2: Final[Vector] = ...
    'The second focus is on the negative side of the major axis of the ellipse.'

class Geometry(Persistence):
    """
    The abstract class Geometry for 3D space is the root class of all geometric objects.
    It describes the common behavior of these objects when:
    - applying geometric transformations to objects, and
    - constructing objects by geometric transformation (including copying).
    """
    Tag: Final[str]
    'Gives the tag of the geometry as string.'

    def mirror(self, geometry: 'Geometry', /) -> None:
        """
        Performs the symmetrical transformation of this geometric object
        """
        ...

    def rotate(self, angle: float, axis: Vector, /) -> None:
        """
        Rotates this geometric object at angle Ang (in radians) about axis
        """
        ...

    def scale(self, center: Vector, factor: float, /) -> None:
        """
        Applies a scaling transformation on this geometric object with a center and scaling factor
        """
        ...

    def transform(self, transformation: Matrix, /) -> None:
        """
        Applies a transformation to this geometric object
        """
        ...

    def translate(self, vector: Vector, /) -> None:
        """
        Translates this geometric object
        """
        ...

    def copy(self) -> 'Geometry':
        """
        Create a copy of this geometry
        """
        ...

    def clone(self) -> 'Geometry':
        """
        Create a clone of this geometry with the same Tag
        """
        ...

    def isSame(self, geom: 'Geometry', tol: float, angulartol: float, /) -> bool:
        """
        isSame(geom, tol, angulartol) -> boolean

        Compare this geometry to another one
        """
        ...

    def hasExtensionOfType(self, type_name: str, /) -> bool:
        """
        Returns a boolean indicating whether a geometry extension of the type indicated as a string exists.
        """
        ...

    def hasExtensionOfName(self, name: str, /) -> bool:
        """
        Returns a boolean indicating whether a geometry extension with the name indicated as a string exists.
        """
        ...

    def getExtensionOfType(self, type_name: str, /) -> Optional[Extension]:
        """
        Gets the first geometry extension of the type indicated by the string.
        """
        ...

    def getExtensionOfName(self, name: str, /) -> Optional[Extension]:
        """
        Gets the first geometry extension of the name indicated by the string.
        """
        ...

    def setExtension(self, extension: Extension, /) -> None:
        """
        Sets a geometry extension of the indicated type.
        """
        ...

    def deleteExtensionOfType(self, type_name: str, /) -> None:
        """
        Deletes all extensions of the indicated type.
        """
        ...

    def deleteExtensionOfName(self, name: str, /) -> None:
        """
        Deletes all extensions of the indicated name.
        """
        ...

    def getExtensions(self) -> List[Extension]:
        """
        Returns a list with information about the geometry extensions.
        """
        ...

class GeometryBoolExtension(GeometryExtension):
    """
    A GeometryExtension extending geometry objects with a boolean.
    """
    Value: bool = ...
    'Returns the value of the GeometryBoolExtension.'

class Curve(Geometry):
    """
    The abstract class GeometryCurve is the root class of all curve objects.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Continuity: Final[str] = ''
    'Returns the global continuity of the curve.'
    FirstParameter: Final[float] = 0.0
    'Returns the value of the first parameter.'
    LastParameter: Final[float] = 0.0
    'Returns the value of the last parameter.'
    Rotation: Final[RotationPy] = ...
    'Returns a rotation object to describe the orientation for curve that supports it'

    def toShape(self) -> Shape:
        """
        Return the shape for the geometry.
        """
        ...

    @overload
    def discretize(self, Number: int, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points.
        """
        ...

    @overload
    def discretize(self, QuasiNumber: int, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of quasi equidistant points.
        """
        ...

    @overload
    def discretize(self, Distance: float, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of equidistant points with distance 'd'.
        """
        ...

    @overload
    def discretize(self, Deflection: float, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points with a maximum deflection 'd' to the curve.
        """
        ...

    @overload
    def discretize(self, QuasiDeflection: float, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points with a maximum deflection 'd' to the curve (faster).
        """
        ...

    @overload
    def discretize(self, Angular: float, Curvature: float, Minimum: int=2, *, First: Optional[float]=None, Last: Optional[float]=None) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points with an angular deflection of 'a' and a curvature deflection of 'c'.
        Optionally a minimum number of points can be set.
        """
        ...

    def discretize(self, **kwargs) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points.

        The function accepts keywords as argument:

        discretize(Number=n) => gives a list of 'n' equidistant points
        discretize(QuasiNumber=n) => gives a list of 'n' quasi equidistant points (is faster than the method above)
        discretize(Distance=d) => gives a list of equidistant points with distance 'd'
        discretize(Deflection=d) => gives a list of points with a maximum deflection 'd' to the curve
        discretize(QuasiDeflection=d) => gives a list of points with a maximum deflection 'd' to the curve (faster)
        discretize(Angular=a,Curvature=c,[Minimum=m]) => gives a list of points with an angular deflection of 'a'
                                            and a curvature deflection of 'c'. Optionally a minimum number of points
                                            can be set which by default is set to 2.

        Optionally you can set the keywords 'First' and 'Last' to define a sub-range of the parameter range
        of the curve.

        If no keyword is given then it depends on whether the argument is an int or float.
        If it's an int then the behaviour is as if using the keyword 'Number', if it's float
        then the behaviour is as if using the keyword 'Distance'.

        Example:

        import Part
        c=Part.Circle()
        c.Radius=5
        p=c.discretize(Number=50,First=3.14)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)


        p=c.discretize(Angular=0.09,Curvature=0.01,Last=3.14,Minimum=100)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)
        """
        ...

    def getD0(self, parameter: float, /) -> Vector:
        """
        Returns the point of given parameter
        """
        ...

    def getD1(self, parameter: float, /) -> Vector:
        """
        Returns the point and first derivative of given parameter
        """
        ...

    def getD2(self, parameter: float, /) -> Vector:
        """
        Returns the point, first and second derivatives
        """
        ...

    def getD3(self, parameter: float, /) -> Vector:
        """
        Returns the point, first, second and third derivatives
        """
        ...

    def getDN(self, n: int, parameter: float, /) -> Vector:
        """
        Returns the n-th derivative
        """
        ...

    def length(self, uMin: Optional[float]=None, uMax: Optional[float]=None, Tol: Optional[float]=None, /) -> float:
        """
        Computes the length of a curve
        length([uMin, uMax, Tol]) -> float
        """
        ...

    def parameterAtDistance(self, abscissa: Optional[float]=None, startingParameter: Optional[float]=None, /) -> float:
        """
        Returns the parameter on the curve of a point at the given distance from a starting parameter.
        parameterAtDistance([abscissa, startingParameter]) -> float
        """
        ...

    def value(self, u: float, /) -> Vector:
        """
        Computes the point of parameter u on this curve
        """
        ...

    def tangent(self, u: float, /) -> Vector:
        """
        Computes the tangent of parameter u on this curve
        """
        ...

    def makeRuledSurface(self, otherCurve: 'GeometryCurve', /) -> object:
        """
        Make a ruled surface of this and the given curves
        """
        ...

    def intersect2d(self, otherCurve: 'GeometryCurve', /) -> List[Vector]:
        """
        Get intersection points with another curve lying on a plane.
        """
        ...

    def continuityWith(self, otherCurve: 'GeometryCurve', /) -> str:
        """
        Computes the continuity of two curves
        """
        ...

    def parameter(self, point: Vector, /) -> float:
        """
        Returns the parameter on the curve of the nearest orthogonal projection of the point.
        """
        ...

    def normal(self, pos: float, /) -> Vector:
        """
        Vector = normal(pos) - Get the normal vector at the given parameter [First|Last] if defined
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='NearestPoint') -> Vector:
        """
        projectPoint(Point=Vector, Method="NearestPoint") -> Vector
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='LowerDistance') -> float:
        """
        projectPoint(Vector, "LowerDistance") -> float.
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='LowerDistanceParameter') -> float:
        """
        projectPoint(Vector, "LowerDistanceParameter") -> float.
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='Distance') -> List[float]:
        """
        projectPoint(Vector, "Distance") -> list of floats.
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='Parameter') -> List[float]:
        """
        projectPoint(Vector, "Parameter") -> list of floats.
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: str='Point') -> List[Vector]:
        """
        projectPoint(Vector, "Point") -> list of points.
        """
        ...

    def projectPoint(self, **kwargs) -> Union[Vector, float, List[float], List[Vector]]:
        """
        Computes the projection of a point on the curve

        projectPoint(Point=Vector,[Method="NearestPoint"])
        projectPoint(Vector,"NearestPoint") -> Vector
        projectPoint(Vector,"LowerDistance") -> float
        projectPoint(Vector,"LowerDistanceParameter") -> float
        projectPoint(Vector,"Distance") -> list of floats
        projectPoint(Vector,"Parameter") -> list of floats
        projectPoint(Vector,"Point") -> list of points
        """
        ...

    def curvature(self, pos: float, /) -> float:
        """
        Float = curvature(pos) - Get the curvature at the given parameter [First|Last] if defined
        """
        ...

    def centerOfCurvature(self, pos: float, /) -> Vector:
        """
        Vector = centerOfCurvature(float pos) - Get the center of curvature at the given parameter [First|Last] if defined
        """
        ...

    def intersect(self, curve_or_surface: object, precision: float, /) -> object:
        """
        Returns all intersection points and curve segments between the curve and the curve/surface.

        arguments: curve/surface (for the intersection), precision (float)
        """
        ...

    def intersectCS(self, surface: object, /) -> object:
        """
        Returns all intersection points and curve segments between the curve and the surface.
        """
        ...

    def intersectCC(self, otherCurve: 'GeometryCurve', /) -> List[Vector]:
        """
        Returns all intersection points between this curve and the given curve.
        """
        ...

    def toBSpline(self, points: Tuple[float, float], /) -> BSplineCurve:
        """
        Converts a curve of any type (only part from First to Last) to BSpline curve.
        toBSpline((first: float, last: float)) -> BSplineCurve
        """
        ...

    def toNurbs(self, points: Tuple[float, float], /) -> BSplineCurve:
        """
        Converts a curve of any type (only part from First to Last) to NURBS curve.
        toNurbs((first: float, last: float)) -> NurbsCurve
        """
        ...

    def trim(self, points: Tuple[float, float], /) -> TrimmedCurve:
        """
        Returns a trimmed curve defined in the given parameter range.
        trim((first: float, last: float)) -> TrimmedCurve
        """
        ...

    def approximateBSpline(self, Tolerance: float, MaxSegments: int, MaxDegree: int, Order: str='C2', /) -> BSplineCurve:
        """
        Approximates a curve of any type to a B-Spline curve.
        approximateBSpline(Tolerance, MaxSegments, MaxDegree, [Order='C2']) -> BSplineCurve
        """
        ...

    def reverse(self) -> None:
        """
        Changes the direction of parametrization of the curve.
        """
        ...

    def reversedParameter(self, U: float, /) -> float:
        """
        Returns the parameter on the reversed curve for the point of parameter U on this curve.
        """
        ...

    def isPeriodic(self) -> bool:
        """
        Returns true if this curve is periodic.
        """
        ...

    def period(self) -> float:
        """
        Returns the period of this curve or raises an exception if it is not periodic.
        """
        ...

    def isClosed(self) -> bool:
        """
        Returns true if the curve is closed.
        """
        ...

class GeometryDoubleExtension(GeometryExtension):
    """
    A GeometryExtension extending geometry objects with a double.

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    Value: float = ...
    'Returns the value of the GeometryDoubleExtension.'

class GeometryExtension:
    """
    The abstract class GeometryExtension enables to extend geometry objects with application specific data.
    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    Name: str = ''
    'Sets/returns the name of this extension.'

    def copy(self) -> 'GeometryExtension':
        """Create a copy of this geometry extension."""
        ...

class GeometryIntExtension(GeometryExtension):
    """
    A GeometryExtension extending geometry objects with an int.

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    Value: int = ...
    'returns the value of the GeometryIntExtension.'

class GeometryStringExtension(GeometryExtension):
    """
    A GeometryExtension extending geometry objects with a string.

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """
    Value: str = ...
    'returns the value of the GeometryStringExtension.'

class GeometrySurface(Geometry):
    """
    The abstract class GeometrySurface is the root class of all surface objects.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Continuity: Final[str] = ''
    'Returns the global continuity of the surface.'
    Rotation: Final[RotationPy] = ...
    'Returns a rotation object to describe the orientation for surface that supports it'

    def toShape(self) -> Any:
        """
        Return the shape for the geometry.
        """
        ...

    def toShell(self, Bounds: object, Segment: object) -> Any:
        """
        Make a shell of the surface.
        """
        ...

    def getD0(self, param: float, /) -> Vector:
        """
        Returns the point of given parameter
        """
        ...

    def getDN(self, n: int, /) -> Any:
        """
        Returns the n-th derivative
        """
        ...

    def value(self, u: float, v: float, /) -> Vector:
        """
        value(u,v) -> Point
        Computes the point of parameter (u,v) on this surface
        """
        ...

    def tangent(self, u: float, v: float, /) -> Tuple[Vector, Vector]:
        """
        tangent(u,v) -> (Vector,Vector)
        Computes the tangent of parameter (u,v) on this geometry
        """
        ...

    def normal(self, u: float, v: float, /) -> Vector:
        """
        normal(u,v) -> Vector
        Computes the normal of parameter (u,v) on this geometry
        """
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['NearestPoint']='NearestPoint') -> Vector:
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['LowerDistance']) -> float:
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['LowerDistanceParameters']) -> Tuple[float, float]:
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['Distance']) -> List[float]:
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['Parameters']) -> List[Tuple[float, float]]:
        ...

    @overload
    def projectPoint(self, Point: Vector, Method: Literal['Point']) -> List[Vector]:
        ...

    def projectPoint(self, Point: Vector, Method: str=...) -> Any:
        """
        Computes the projection of a point on the surface

        projectPoint(Point=Vector,[Method="NearestPoint"])
        projectPoint(Vector,"NearestPoint") -> Vector
        projectPoint(Vector,"LowerDistance") -> float
        projectPoint(Vector,"LowerDistanceParameters") -> tuple of floats (u,v)
        projectPoint(Vector,"Distance") -> list of floats
        projectPoint(Vector,"Parameters") -> list of tuples of floats
        projectPoint(Vector,"Point") -> list of points
        """
        ...

    def isUmbillic(self, u: float, v: float, /) -> bool:
        """
        isUmbillic(u,v) -> bool
        Check if the geometry on parameter is an umbillic point,
        i.e. maximum and minimum curvature are equal.
        """
        ...

    def curvature(self, u: float, v: float, type: str, /) -> float:
        """
        curvature(u,v,type) -> float
        The value of type must be one of this: Max, Min, Mean or Gauss
        Computes the curvature of parameter (u,v) on this geometry
        """
        ...

    def curvatureDirections(self, u: float, v: float, /) -> Tuple[Vector, Vector]:
        """
        curvatureDirections(u,v) -> (Vector,Vector)
        Computes the directions of maximum and minimum curvature
        of parameter (u,v) on this geometry.
        The first vector corresponds to the maximum curvature,
        the second vector corresponds to the minimum curvature.
        """
        ...

    def bounds(self) -> Tuple[float, float, float, float]:
        """
        Returns the parametric bounds (U1, U2, V1, V2) of this trimmed surface.
        """
        ...

    def isPlanar(self, tolerance: float=0.0, /) -> bool:
        """
        isPlanar([float]) -> Bool
        Checks if the surface is planar within a certain tolerance.
        """
        ...

    def uIso(self, u: Tuple, /) -> Union[Curve, Line]:
        """
        Builds the U isoparametric curve
        """
        ...

    def vIso(self, v: Tuple, /) -> Union[Curve, Line]:
        """
        Builds the V isoparametric curve
        """
        ...

    def isUPeriodic(self) -> bool:
        """
        Returns true if this patch is periodic in the given parametric direction.
        """
        ...

    def isVPeriodic(self) -> bool:
        """
        Returns true if this patch is periodic in the given parametric direction.
        """
        ...

    def isUClosed(self) -> bool:
        """
        Checks if this surface is closed in the u parametric direction.
        """
        ...

    def isVClosed(self) -> bool:
        """
        Checks if this surface is closed in the v parametric direction.
        """
        ...

    def UPeriod(self) -> float:
        """
        Returns the period of this patch in the u parametric direction.
        """
        ...

    def VPeriod(self) -> float:
        """
        Returns the period of this patch in the v parametric direction.
        """
        ...

    def parameter(self) -> float:
        """
        Returns the parameter on the curve
        of the nearest orthogonal projection of the point.
        """
        ...

    @overload
    def toBSpline(self, tolerance: float=1e-07, continuity_u: Literal['C0', 'G0', 'G1', 'C1', 'G2', 'C3', 'CN']='C1', continuity_v: Literal['C0', 'G0', 'G1', 'C1', 'G2', 'C3', 'CN']='C1', max_degree_u: int=25, max_degree_v: int=25, max_segments: int=1000, precision_code: int=0) -> Any:
        ...

    def toBSpline(self, tolerance: float=1e-07, continuity_u: str='C1', continuity_v: str='C1', max_degree_u: int=25, max_degree_v: int=25, max_segments: int=1000, precision_code: int=0) -> Any:
        """
        Returns a B-Spline representation of this surface.
        The optional arguments are:
        * tolerance (default=1e-7)
        * continuity in u (as string e.g. C0, G0, G1, C1, G2, C3, CN) (default='C1')
        * continuity in v (as string e.g. C0, G0, G1, C1, G2, C3, CN) (default='C1')
        * maximum degree in u (default=25)
        * maximum degree in v (default=25)
        * maximum number of segments (default=1000)
        * precision code (default=0)
        Will raise an exception if surface is infinite in U or V (like planes, cones or cylinders)
        """
        ...

    def intersect(self) -> Any:
        """
        Returns all intersection points/curves between the surface and the curve/surface.
        """
        ...

    def intersectSS(self, SecondSurface: Any, precision_code: int=0, /) -> Any:
        """
        Returns all intersection curves of this surface and the given surface.
        The required arguments are:
        * Second surface
        * precision code (optional, default=0)
        """
        ...

class Hyperbola(Conic):
    """
    Describes an hyperbola in 3D space

    To create a hyperbola there are several ways:

    Part.Hyperbola()
        Creates an hyperbola with major radius 2 and minor radius 1 with the
        center in (0,0,0)

    Part.Hyperbola(Hyperbola)
        Create a copy of the given hyperbola

    Part.Hyperbola(S1,S2,Center)
        Creates an hyperbola centered on the point Center, where
        the plane of the hyperbola is defined by Center, S1 and S2,
        its major axis is defined by Center and S1,
        its major radius is the distance between Center and S1, and
        its minor radius is the distance between S2 and the major axis.

    Part.Hyperbola(Center,MajorRadius,MinorRadius)
        Creates an hyperbola with major and minor radii MajorRadius and
        MinorRadius, and located in the plane defined by Center and
        the normal (0,0,1)
    """
    MajorRadius: float
    'The major radius of the hyperbola.'
    MinorRadius: float
    'The minor radius of the hyperbola.'
    Focal: Final[float]
    'The focal distance of the hyperbola.'
    Focus1: Final[Vector]
    'The first focus is on the positive side of the major axis of the hyperbola.'
    Focus2: Final[Vector]
    'The second focus is on the negative side of the major axis of the hyperbola.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, hyperbola: 'Hyperbola') -> None:
        ...

    @overload
    def __init__(self, S1: Vector, S2: Vector, Center: Vector) -> None:
        ...

    @overload
    def __init__(self, Center: Vector, MajorRadius: float, MinorRadius: float) -> None:
        ...

class Line(Curve):
    """
    Describes an infinite line
    To create a line there are several ways:
    Part.Line()
        Creates a default line

    Part.Line(Line)
        Creates a copy of the given line

    Part.Line(Point1,Point2)
        Creates a line that goes through two given points

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Location: Vector = ...
    'Returns the location of this line.'
    Direction: Vector = ...
    'Returns the direction of this line.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, line: 'Line') -> None:
        ...

    @overload
    def __init__(self, point1: Vector, point2: Vector) -> None:
        ...

class LineSegment(TrimmedCurve):
    """
    Describes a line segment
    To create a line segment there are several ways:
    Part.LineSegment()
        Creates a default line segment

    Part.LineSegment(LineSegment)
        Creates a copy of the given line segment

    Part.LineSegment(Point1,Point2)
        Creates a line segment that goes through two given points
    """
    StartPoint: Type = ...
    'Returns the start point of this line.'
    EndPoint: Type = ...
    'Returns the end point point of this line.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, line_segment: 'LineSegment') -> None:
        ...

    @overload
    def __init__(self, point1: Point, point2: Point) -> None:
        ...

    def setParameterRange(self) -> None:
        """
        Set the parameter range of the underlying line geometry
        """
        ...

class OffsetCurve(Curve):
    """
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    OffsetValue: float = ...
    'Sets or gets the offset value to offset the underlying curve.'
    OffsetDirection: Vector = ...
    'Sets or gets the offset direction to offset the underlying curve.'
    BasisCurve: Curve = ...
    'Sets or gets the basic curve.'

class OffsetSurface(GeometrySurface):
    """
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    OffsetValue: float = 0.0
    'Sets or gets the offset value to offset the underlying surface.'
    BasisSurface: object = ...
    'Sets or gets the basic surface.'

class Parabola(Conic):
    """
    Describes a parabola in 3D space
    """
    Focal: float = ...
    '\n    The focal distance is the distance between\n    the apex and the focus of the parabola.\n    '
    Focus: Final[Vector] = ...
    "\n    The focus is on the positive side of the\n    'X Axis' of the local coordinate system of the parabola.\n    "
    Parameter: Final[float] = ...
    '\n    Compute the parameter of this parabola\n    which is the distance between its focus\n    and its directrix. This distance is twice the focal length.\n    '

    def compute(self, p1: Vector, p2: Vector, p3: Vector, /) -> None:
        """
        compute(p1,p2,p3) -> None

        The three points must lie on a plane parallel to xy plane and must not be collinear
        """
        ...

class Part2DObject(Feature):
    """
    This object represents a 2D Shape in a 3D World

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    ...

class Feature(GeoFeature):
    """
    This is the father of all shape object classes

    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """

    def getElementHistory(self, name: str, *, recursive: bool=True, sameType: bool=False, showName: bool=False) -> Union[Tuple[DocumentObject, str, List[str]], List[Tuple[DocumentObject, str, List[str]]]]:
        """
        getElementHistory(name,recursive=True,sameType=False,showName=False) - returns the element mapped name history

        name: mapped element name belonging to this shape
        recursive: if True, then track back the history through other objects till the origin
        sameType: if True, then stop trace back when element type changes
        showName: if False, return the owner object, or else return a tuple of object name and label

        If not recursive, then return tuple(sourceObject, sourceElementName, [intermediateNames...]),
        otherwise return a list of tuple.
        """
        ...
    Shape: 'Part.Shape' = ...

class Plane(GeometrySurface):
    """
        Describes an infinite plane
    To create a plane there are several ways:
    Part.Plane()
        Creates a default plane with base (0,0,0) and normal (0,0,1)

    Part.Plane(Plane)
        Creates a copy of the given plane

    Part.Plane(Plane, Distance)
        Creates a plane parallel to given plane at a certain distance

    Part.Plane(Location,Normal)
        Creates a plane with a given location and normal

    Part.Plane(Point1,Point2,Point3)
        Creates a plane defined by three non-linear points

    Part.Plane(A,B,C,D)
        Creates a plane from its cartesian equation
        Ax+By+Cz+D=0
    """
    Position: object = ...
    'Returns the position point of this plane.'
    Axis: object = ...
    'Returns the axis of this plane.'

class PlateSurface(GeometrySurface):
    """
    Represents a plate surface in FreeCAD. Plate surfaces can be defined by specifying points or curves as constraints, and they can also be approximated to B-spline surfaces using the makeApprox method. This class is commonly used in CAD modeling for creating surfaces that represent flat or curved plates, such as sheet metal components or structural elements.
    """

    def makeApprox(self, *, Tol3d: float=0, MaxSegments: int=0, MaxDegree: int=0, MaxDistance: float=0, CritOrder: int=0, Continuity: str='', EnlargeCoeff: float=0) -> None:
        """
        Approximate the plate surface to a B-Spline surface
        """
        ...

class Point(Geometry):
    """
    Describes a point
    To create a point there are several ways:
    Part.Point()
        Creates a default point

    Part.Point(Point)
        Creates a copy of the given point

    Part.Point(Vector)
        Creates a line for the given coordinates

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, other: 'Point') -> None:
        ...

    @overload
    def __init__(self, coordinates: Vector) -> None:
        ...

    def toShape(self) -> object:
        """
        Create a vertex from this point.
        """
        ...
    X: float = ...
    'X component of this point.'
    Y: float = ...
    'Y component of this point.'
    Z: float = ...
    'Z component of this point.'

class RectangularTrimmedSurface(GeometrySurface):
    """
    Describes a portion of a surface (a patch) limited by two values of the
    u parameter in the u parametric direction, and two values of the v parameter in the v parametric
    direction. The domain of the trimmed surface must be within the domain of the surface being trimmed.

    The trimmed surface is defined by:
    - the basis surface, and
    - the values (umin, umax) and (vmin, vmax) which limit it in the u and v parametric directions.

    The trimmed surface is built from a copy of the basis surface. Therefore, when the basis surface
    is modified the trimmed surface is not changed. Consequently, the trimmed surface does not
    necessarily have the same orientation as the basis surface.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    BasisSurface: Final[Any] = ...
    'Represents the basis surface from which the trimmed surface is derived.'

    def setTrim(self, params: Tuple[float, float, float, float], /) -> None:
        """
        setTrim(self, params: (u1, u2, v1, v2)) -> None

        Modifies this patch by changing the trim values applied to the original surface
        """
        ...

class Sphere(GeometrySurface):
    """
    Describes a sphere in 3D space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Radius: float = ...
    'The radius of the sphere.'
    Area: Final[float] = 0.0
    'Compute the area of the sphere.'
    Volume: Final[float] = 0.0
    'Compute the volume of the sphere.'
    Center: Vector = ...
    'Center of the sphere.'
    Axis: AxisPy = ...
    'The axis direction of the circle'

class SurfaceOfExtrusion(GeometrySurface):
    """
    Describes a surface of linear extrusion
    Author: Werner Mayer (<wmayer@users.sourceforge.net>)
    Licence: LGPL
    """
    Direction: Vector = ...
    'Sets or gets the direction of revolution.'
    BasisCurve: Curve = ...
    'Sets or gets the basic curve.'

class SurfaceOfRevolution(GeometrySurface):
    """
    Describes a surface of revolution

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Location: Placement
    'Sets or gets the location of revolution.'
    Direction: Vector
    'Sets or gets the direction of revolution.'
    BasisCurve: Curve
    'Sets or gets the basic curve.'

    @overload
    def __init__(self, location: Placement, direction: Vector, basis_curve: Curve) -> None:
        ...

class Shape(ComplexGeoData):
    """
    TopoShape is the OpenCasCade topological shape wrapper.
    Sub-elements such as vertices, edges or faces are accessible as:
    * Vertex#, where # is in range(1, number of vertices)
    * Edge#, where # is in range(1, number of edges)
    * Face#, where # is in range(1, number of faces)
    """
    ShapeType: Final[str] = ''
    'Returns the type of the shape.'
    Orientation: str = ''
    'Returns the orientation of the shape.'
    Faces: Final[List] = []
    'List of faces in this shape.'
    Vertexes: Final[List] = []
    'List of vertexes in this shape.'
    Shells: Final[List] = []
    'List of subsequent shapes in this shape.'
    Solids: Final[List] = []
    'List of subsequent shapes in this shape.'
    CompSolids: Final[List] = []
    'List of subsequent shapes in this shape.'
    Edges: Final[List] = []
    'List of Edges in this shape.'
    Wires: Final[List] = []
    'List of wires in this shape.'
    Compounds: Final[List] = []
    'List of compounds in this shape.'
    SubShapes: Final[List] = []
    'List of sub-shapes in this shape.'
    Length: Final[float] = 0.0
    'Total length of the edges of the shape.'
    Area: Final[float] = 0.0
    'Total area of the faces of the shape.'
    Volume: Final[float] = 0.0
    'Total volume of the solids of the shape.'

    def dumps(self) -> str:
        """
        Serialize the content of this shape to a string in BREP format.
        """
        ...

    def loads(self, brep_str: str, /) -> None:
        """
        Deserialize the content of this shape from a string in BREP format.
        """
        ...

    def read(self, filename: str, /) -> None:
        """
        Read in an IGES, STEP or BREP file.
        read(filename)
        """
        ...

    def writeInventor(self, *, Mode: int, Deviation: float, Angle: float, FaceColors: object) -> str:
        """
        Write the mesh in OpenInventor format to a string.
        writeInventor() -> string
        """
        ...

    def exportIges(self, filename: str, /) -> None:
        """
        Export the content of this shape to an IGES file.
        exportIges(filename)
        """
        ...

    def exportStep(self, filename: str, /) -> None:
        """
        Export the content of this shape to an STEP file.
        exportStep(filename)
        """
        ...

    def exportBrep(self, filename: str, /) -> None:
        """
        Export the content of this shape to an BREP file.
        exportBrep(filename)
        --
        BREP is an OpenCasCade native format.
        """
        ...

    def exportBinary(self, filename: str, /) -> None:
        """
        Export the content of this shape in binary format to a file.
        exportBinary(filename)
        """
        ...

    def exportBrepToString(self) -> str:
        """
        Export the content of this shape to a string in BREP format.
        exportBrepToString() -> string
        --
        BREP is an OpenCasCade native format.
        """
        ...

    def dumpToString(self) -> str:
        """
        Dump information about the shape to a string.
        dumpToString() -> string
        """
        ...

    def exportStl(self, filename: str, /) -> None:
        """
        Export the content of this shape to an STL mesh file.
        exportStl(filename)
        """
        ...

    def importBrep(self, filename: str, /) -> None:
        """
        Load the shape from a file in BREP format.
        importBrep(filename)
        """
        ...

    def importBinary(self, filename: str, /) -> None:
        """
        Import the content to this shape of a string in BREP format.
        importBinary(filename)
        """
        ...

    def importBrepFromString(self, s: str, displayProgressBar: bool=True, /) -> None:
        """
        Load the shape from a string that keeps the content in BREP format.
        importBrepFromString(string, [displayProgressBar=True])
        --
        importBrepFromString(str, False) to not display a progress bar.
        """
        ...

    def extrude(self, vector: Vector, /) -> Shape:
        """
        Extrude the shape along a vector.
        extrude(vector) -> Shape
        --
        Shp2 = Shp1.extrude(App.Vector(0,0,10)) - extrude the shape 10 mm in the +Z direction.
        """
        ...

    def revolve(self, base: Vector, direction: Vector, angle: float, /) -> Shape:
        """
        Revolve the shape around an Axis to a given degree.
        revolve(base, direction, angle)
        --
        Part.revolve(App.Vector(0,0,0),App.Vector(0,0,1),360) - revolves the shape around the Z Axis 360 degree.

        Hints: Sometimes you want to create a rotation body out of a closed edge or wire.
        Example:
        from FreeCAD import Base
        import Part
        V=Base.Vector

        e=Part.Ellipse()
        s=e.toShape()
        r=s.revolve(V(0,0,0),V(0,1,0), 360)
        Part.show(r)

        However, you may possibly realize some rendering artifacts or that the mesh
        creation seems to hang. This is because this way the surface is created twice.
        Since the curve is a full ellipse it is sufficient to do a rotation of 180 degree
        only, i.e. r=s.revolve(V(0,0,0),V(0,1,0), 180)

        Now when rendering this object you may still see some artifacts at the poles. Now the
        problem seems to be that the meshing algorithm doesn't like to rotate around a point
        where there is no vertex.

        The idea to fix this issue is that you create only half of the ellipse so that its shape
        representation has vertexes at its start and end point.

        from FreeCAD import Base
        import Part
        V=Base.Vector

        e=Part.Ellipse()
        s=e.toShape(e.LastParameter/4,3*e.LastParameter/4)
        r=s.revolve(V(0,0,0),V(0,1,0), 360)
        Part.show(r)
        """
        ...

    def check(self, runBopCheck: bool=False, /) -> bool:
        """
        Checks the shape and report errors in the shape structure.
        check([runBopCheck = False])
        --
        This is a more detailed check as done in isValid().
        if runBopCheck is True, a BOPCheck analysis is also performed.
        """
        ...

    def fuse(self, tools: Tuple[Shape, ...], tolerance: float=0.0, /) -> Shape:
        """
        Union of this and a given (list of) topo shape.
        fuse(tool) -> Shape
          or
        fuse((tool1,tool2,...),[tolerance=0.0]) -> Shape
        --
        Union of this and a given list of topo shapes.

        Supports (OCCT 6.9.0 and above):
        - Fuzzy Boolean operations (global tolerance for a Boolean operation)
        - Support of multiple arguments for a single Boolean operation
        - Parallelization of Boolean Operations algorithm

        Beginning from OCCT 6.8.1 a tolerance value can be specified.
        """
        ...

    def multiFuse(self, tools: Tuple[Shape, ...], tolerance: float=0.0, /) -> Shape:
        """
        Union of this and a given list of topo shapes.
        multiFuse((tool1,tool2,...),[tolerance=0.0]) -> Shape
        --
        Supports (OCCT 6.9.0 and above):
        - Fuzzy Boolean operations (global tolerance for a Boolean operation)
        - Support of multiple arguments for a single Boolean operation
        - Parallelization of Boolean Operations algorithm

        Beginning from OCCT 6.8.1 a tolerance value can be specified.
        Deprecated: use fuse() instead.
        """
        ...

    def common(self, tools: Tuple[Shape, ...], tolerance: float=0.0, /) -> Shape:
        """
        Intersection of this and a given (list of) topo shape.
        common(tool) -> Shape
          or
        common((tool1,tool2,...),[tolerance=0.0]) -> Shape
        --
        Supports:
        - Fuzzy Boolean operations (global tolerance for a Boolean operation)
        - Support of multiple arguments for a single Boolean operation (s1 AND (s2 OR s3))
        - Parallelization of Boolean Operations algorithm

        OCC 6.9.0 or later is required.
        """
        ...

    def section(self, tool: Tuple[Shape, ...], tolerance: float=0.0, approximation: bool=False, /) -> Shape:
        """
        Section of this with a given (list of) topo shape.
        section(tool,[approximation=False]) -> Shape
          or
        section((tool1,tool2,...),[tolerance=0.0, approximation=False]) -> Shape
        --
        If approximation is True, section edges are approximated to a C1-continuous BSpline curve.

        Supports:
        - Fuzzy Boolean operations (global tolerance for a Boolean operation)
        - Support of multiple arguments for a single Boolean operation (s1 AND (s2 OR s3))
        - Parallelization of Boolean Operations algorithm

        OCC 6.9.0 or later is required.
        """
        ...

    def slices(self, direction: Vector, distancesList: List[float], /) -> List:
        """
        Make slices of this shape.
        slices(direction, distancesList) --> Wires
        """
        ...

    def slice(self, direction: Vector, distance: float, /) -> List:
        """
        Make single slice of this shape.
        slice(direction, distance) --> Wires
        """
        ...

    def cut(self, tool: Tuple[Shape, ...], tolerance: float=0.0, /) -> Shape:
        """
        Difference of this and a given (list of) topo shape
        cut(tool) -> Shape
          or
        cut((tool1,tool2,...),[tolerance=0.0]) -> Shape
        --
        Supports:
        - Fuzzy Boolean operations (global tolerance for a Boolean operation)
        - Support of multiple arguments for a single Boolean operation
        - Parallelization of Boolean Operations algorithm

        OCC 6.9.0 or later is required.
        """
        ...

    def generalFuse(self, shapes: Tuple[Shape, ...], fuzzy_value: float=0.0, /) -> Tuple[Shape, List[List[Shape]]]:
        """
        Run general fuse algorithm (GFA) between this and given shapes.
        generalFuse(list_of_other_shapes, [fuzzy_value = 0.0]) -> (result, map)
        --
        list_of_other_shapes: shapes to run the algorithm against (the list is
        effectively prepended by 'self').

        fuzzy_value: extra tolerance to apply when searching for interferences, in
        addition to tolerances of the input shapes.

        Returns a tuple of 2: (result, map).

        result is a compound containing all the pieces generated by the algorithm
        (e.g., for two spheres, the pieces are three touching solids). Pieces that
        touch share elements.

        map is a list of lists of shapes, providing the info on which children of
        result came from which argument. The length of list is equal to length of
        list_of_other_shapes + 1. First element is a list of pieces that came from
        shape of this, and the rest are those that come from corresponding shapes in
        list_of_other_shapes.
        hint: use isSame method to test shape equality

        Parallelization of Boolean Operations algorithm

        OCC 6.9.0 or later is required.
        """
        ...

    def sewShape(self) -> None:
        """
        Sew the shape if there is a gap.
        sewShape()
        """
        ...

    def childShapes(self, cumOri: bool=True, cumLoc: bool=True, /) -> List:
        """
        Return a list of sub-shapes that are direct children of this shape.
        childShapes([cumOri=True, cumLoc=True]) -> list
        --
        * If cumOri is true, the function composes all
          sub-shapes with the orientation of this shape.
        * If cumLoc is true, the function multiplies all
          sub-shapes by the location of this shape, i.e. it applies to
          each sub-shape the transformation that is associated with this shape.
        """
        ...

    def ancestorsOfType(self, shape: Shape, shape_type: str, /) -> List:
        """
        For a sub-shape of this shape get its ancestors of a type.
        ancestorsOfType(shape, shape type) -> list
        """
        ...

    def removeInternalWires(self, minimalArea: float, /) -> bool:
        """
        Removes internal wires (also holes) from the shape.
        removeInternalWires(minimalArea) -> bool
        """
        ...

    def mirror(self, base: Vector, norm: Vector, /) -> Shape:
        """
        Mirror this shape on a given plane.
        mirror(base, norm) -> Shape
        --
        The plane is given with its base point and its normal direction.
        """
        ...

    def transformGeometry(self, matrix: Matrix, /) -> Shape:
        """
        Apply geometric transformation on this or a copy the shape.
        transformGeometry(matrix) -> Shape
        --
        This method returns a new shape.
        The transformation to be applied is defined as a 4x4 matrix.
        The underlying geometry of the following shapes may change:
        - a curve which supports an edge of the shape, or
        - a surface which supports a face of the shape;

        For example, a circle may be transformed into an ellipse when
        applying an affinity transformation. It may also happen that
        the circle then is represented as a B-spline curve.

        The transformation is applied to:
        - all the curves which support edges of the shape, and
        - all the surfaces which support faces of the shape.

        Note: If you want to transform a shape without changing the
        underlying geometry then use the methods translate or rotate.
        """
        ...

    def transformShape(self, matrix: Matrix, copy: bool=False, checkScale: bool=False, /) -> Shape:
        """
        Apply transformation on a shape without changing the underlying geometry.
        transformShape(Matrix, [boolean copy=False, checkScale=False]) -> shape
        --
        If copy is True, returns a transformed copy and leaves the original unchanged.
        If copy is False, transforms this shape in place and returns itself.
        If checkScale is True, it will use transformGeometry if non-uniform
        scaling is detected.
        """
        ...

    def transformed(self, matrix: Matrix, *, copy: bool=False, checkScale: bool=False, op: str=None) -> Shape:
        """
        Create a new transformed shape
        transformed(Matrix,copy=False,checkScale=False,op=None) -> shape
        """
        ...

    def translate(self, vector: Vector, /) -> None:
        """
        Apply the translation to the current location of this shape.
        translate(vector)
        """
        ...

    def translated(self, vector: Vector, /) -> Shape:
        """
        Create a new shape with translation
        translated(vector) -> shape
        """
        ...

    def rotate(self, base: Vector, dir: Vector, degree: float, /) -> None:
        """
        Apply the rotation (base, dir, degree) to the current location of this shape
        rotate(base, dir, degree)
        --
        Shp.rotate(App.Vector(0,0,0), App.Vector(0,0,1), 180) - rotate the shape around the Z Axis 180 degrees.
        """
        ...

    def rotated(self, base: Vector, dir: Vector, degree: float, /) -> Shape:
        """
        Create a new shape with rotation.
        rotated(base, dir, degree) -> shape
        """
        ...

    def scale(self, factor: float, base: Vector=None, /) -> None:
        """
        Apply scaling with point and factor to this shape.
        scale(factor, [base=App.Vector(0,0,0)])
        """
        ...

    def scaled(self, factor: float, base: Vector=None, /) -> Shape:
        """
        Create a new shape with scale.
        scaled(factor, [base=App.Vector(0,0,0)]) -> shape
        """
        ...

    @overload
    def makeFillet(self, radius: float, edgeList: List, /) -> Shape:
        ...

    @overload
    def makeFillet(self, radius1: float, radius2: float, edgeList: List, /) -> Shape:
        ...

    def makeFillet(self, *args) -> Shape:
        """
        Make fillet.
        makeFillet(radius, edgeList) -> Shape
        or
        makeFillet(radius1, radius2, edgeList) -> Shape
        """
        ...

    @overload
    def makeChamfer(self, radius: float, edgeList: List, /) -> Shape:
        ...

    @overload
    def makeChamfer(self, radius1: float, radius2: float, edgeList: List, /) -> Shape:
        ...

    def makeChamfer(self, *args) -> Shape:
        """
        Make chamfer.
        makeChamfer(radius, edgeList) -> Shape
        or
        makeChamfer(radius1, radius2, edgeList) -> Shape
        """
        ...

    def makeThickness(self, faces: List, offset: float, tolerance: float, /) -> Shape:
        """
        Hollow a solid according to given thickness and faces.
        makeThickness(List of faces, Offset (Float), Tolerance (Float)) -> Shape
        --
        A hollowed solid is built from an initial solid and a set of faces on this solid,
        which are to be removed. The remaining faces of the solid become the walls of
        the hollowed solid, their thickness defined at the time of construction.
        """
        ...

    def makeOffsetShape(self, offset: float, tolerance: float, *, inter: bool=False, self_inter: bool=False, offsetMode: int=0, join: int=0, fill: bool=False) -> Shape:
        """
        Makes an offset shape (3d offsetting).
        makeOffsetShape(offset, tolerance, [inter=False, self_inter=False, offsetMode=0, join=0, fill=False]) -> Shape
        --
        The function supports keyword arguments.

        * offset: distance to expand the shape by. Negative value will shrink the shape.

        * tolerance: precision of approximation.

        * inter: (parameter to OCC routine; not implemented)

        * self_inter: (parameter to OCC routine; not implemented)

        * offsetMode: 0 = skin; 1 = pipe; 2 = recto-verso

        * join: method of offsetting non-tangent joints. 0 = arcs, 1 = tangent, 2 =
        intersection

        * fill: if true, offsetting a shell is to yield a solid

        Returns: result of offsetting.
        """
        ...

    def makeOffset2D(self, offset: float, *, join: int=0, fill: bool=False, openResult: bool=False, intersection: bool=False) -> Shape:
        """
        Makes an offset shape (2d offsetting).
        makeOffset2D(offset, [join=0, fill=False, openResult=False, intersection=False]) -> Shape
        --
        The function supports keyword arguments.
        Input shape (self) can be edge, wire, face, or a compound of those.

        * offset: distance to expand the shape by. Negative value will shrink the shape.

        * join: method of offsetting non-tangent joints. 0 = arcs, 1 = tangent, 2 = intersection

        * fill: if true, the output is a face filling the space covered by offset. If
        false, the output is a wire.

        * openResult: affects the way open wires are processed. If False, an open wire
        is made. If True, a closed wire is made from a double-sided offset, with rounds
        around open vertices.

        * intersection: affects the way compounds are processed. If False, all children
        are offset independently. If True, and children are edges/wires, the children
        are offset in a collective manner. If compounding is nested, collectiveness
        does not spread across compounds (only direct children of a compound are taken
        collectively).

        Returns: result of offsetting (wire or face or compound of those). Compounding
        structure follows that of source shape.
        """
        ...

    def makeEvolved(self, Profile: Shape, Join: int, AxeProf: bool, *, Solid: bool, ProfOnSpine: bool, Tolerance: float) -> None:
        """
        Profile along the spine
        """
        ...

    def makeWires(self, op: str=None, /) -> Shape:
        """
        Make wire(s) using the edges of this shape
        makeWires([op=None])
        --
        The function will sort any edges inside the current shape, and connect them
        into wire. If more than one wire is found, then it will make a compound out of
        all found wires.

        This function is element mapping aware. If the input shape has non-zero Tag,
        it will map any edge and vertex element name inside the input shape into the
        itself.

        op: an optional string to be appended when auto generates element mapping.
        """
        ...

    def reverse(self) -> None:
        """
        Reverses the orientation of this shape.
        reverse()
        """
        ...

    def reversed(self) -> Shape:
        """
        Reverses the orientation of a copy of this shape.
        reversed() -> Shape
        """
        ...

    def complement(self) -> None:
        """
        Computes the complement of the orientation of this shape,
        i.e. reverses the interior/exterior status of boundaries of this shape.
        complement()
        """
        ...

    def nullify(self) -> None:
        """
        Destroys the reference to the underlying shape stored in this shape.
        As a result, this shape becomes null.
        nullify()
        """
        ...

    def isClosed(self) -> bool:
        """
        Checks if the shape is closed.
        isClosed() -> bool
        --
        If the shape is a shell it returns True if it has no free boundaries (edges).
        If the shape is a wire it returns True if it has no free ends (vertices).
        (Internal and External sub-shapes are ignored in these checks)
        If the shape is an edge it returns True if its vertices are the same.
        """
        ...

    def isPartner(self, shape: Shape, /) -> bool:
        """
        Checks if both shapes share the same geometry.
        Placement and orientation may differ.
        isPartner(shape) -> bool
        """
        ...

    def isSame(self, shape: Shape, /) -> bool:
        """
        Checks if both shapes share the same geometry
        and placement. Orientation may differ.
        isSame(shape) -> bool
        """
        ...

    def isEqual(self, shape: Shape, /) -> bool:
        """
        Checks if both shapes are equal.
        This means geometry, placement and orientation are equal.
        isEqual(shape) -> bool
        """
        ...

    def isNull(self) -> bool:
        """
        Checks if the shape is null.
        isNull() -> bool
        """
        ...

    def isValid(self) -> bool:
        """
        Checks if the shape is valid, i.e. neither null, nor empty nor corrupted.
        isValid() -> bool
        """
        ...

    def isCoplanar(self, shape: Shape, tol: float=None, /) -> bool:
        """
        Checks if this shape is coplanar with the given shape.
        isCoplanar(shape,tol=None) -> bool
        """
        ...

    def isInfinite(self) -> bool:
        """
        Checks if this shape has an infinite expansion.
        isInfinite() -> bool
        """
        ...

    def findPlane(self, tol: float=None, /) -> Shape:
        """
        Returns a plane if the shape is planar
        findPlane(tol=None) -> Shape
        """
        ...

    def fix(self, working_precision: float, minimum_precision: float, maximum_precision: float, /) -> bool:
        """
        Tries to fix a broken shape.
        fix(working precision, minimum precision, maximum precision) -> bool
        --
        True is returned if the operation succeeded, False otherwise.
        """
        ...

    def hashCode(self) -> int:
        """
        This value is computed from the value of the underlying shape reference and the location.
        hashCode() -> int
        --
        Orientation is not taken into account.
        """
        ...

    def tessellate(self) -> Tuple[List[Vector], List]:
        """
        Tessellate the shape and return a list of vertices and face indices
        tessellate() -> (vertex,facets)
        """
        ...

    def project(self, shapeList: List[Shape], /) -> Shape:
        """
        Project a list of shapes on this shape
        project(shapeList) -> Shape
        """
        ...

    def makeParallelProjection(self, shape: Shape, dir: Vector, /) -> Shape:
        """
        Parallel projection of an edge or wire on this shape
        makeParallelProjection(shape, dir) -> Shape
        """
        ...

    def makePerspectiveProjection(self, shape: Shape, pnt: Vector, /) -> Shape:
        """
        Perspective projection of an edge or wire on this shape
        makePerspectiveProjection(shape, pnt) -> Shape
        """
        ...

    def reflectLines(self, ViewDir: Vector, *, ViewPos: Vector=None, UpDir: Vector=None, EdgeType: str=None, Visible: bool=True, OnShape: bool=False) -> Shape:
        """
        Build projection or reflect lines of a shape according to a view direction.
        reflectLines(ViewDir, [ViewPos, UpDir, EdgeType, Visible, OnShape]) -> Shape (Compound of edges)
        --
        This algorithm computes the projection of the shape in the ViewDir direction.
        If OnShape is False(default), the returned edges are flat on the XY plane defined by
        ViewPos(origin) and UpDir(up direction).
        If OnShape is True, the returned edges are the corresponding 3D reflect lines located on the shape.
        EdgeType is a string defining the type of result edges :
        - IsoLine : isoparametric line
        - OutLine : outline (silhouette) edge
        - Rg1Line : smooth edge of G1-continuity between two surfaces
        - RgNLine : sewn edge of CN-continuity on one surface
        - Sharp : sharp edge (of C0-continuity)
        If Visible is True (default), only visible edges are returned.
        If Visible is False, only invisible edges are returned.
        """
        ...

    def makeShapeFromMesh(self, mesh: Tuple[List[Vector], List], tolerance: float, /) -> Shape:
        """
        Make a compound shape out of mesh data.
        makeShapeFromMesh((vertex,facets),tolerance) -> Shape
        --
        Note: This should be used for rather small meshes only.
        """
        ...

    def toNurbs(self) -> Shape:
        """
        Conversion of the complete geometry of a shape into NURBS geometry.
        toNurbs() -> Shape
        --
        For example, all curves supporting edges of the basis shape are converted
        into B-spline curves, and all surfaces supporting its faces are converted
        into B-spline surfaces.
        """
        ...

    def copy(self, copyGeom: bool=True, copyMesh: bool=False, /) -> Shape:
        """
        Create a copy of this shape
        copy(copyGeom=True, copyMesh=False) -> Shape
        --
        If copyMesh is True, triangulation contained in original shape will be
        copied along with geometry.
        If copyGeom is False, only topological objects will be copied, while
        geometry and triangulation will be shared with original shape.
        """
        ...

    def cleaned(self) -> Shape:
        """
        This creates a cleaned copy of the shape with the triangulation removed.
        clean()
        --
        This can be useful to reduce file size when exporting as a BREP file.
        Warning: Use the cleaned shape with care because certain algorithms may work incorrectly
        if the shape has no internal triangulation any more.
        """
        ...

    def replaceShape(self, tupleList: List[Tuple[Shape, Shape]], /) -> Shape:
        """
        Replace a sub-shape with a new shape and return a new shape.
        replaceShape(tupleList) -> Shape
        --
        The parameter is in the form list of tuples with the two shapes.
        """
        ...

    def removeShape(self, shapeList: List[Shape], /) -> Shape:
        """
        Remove a sub-shape and return a new shape.
        removeShape(shapeList) -> Shape
        --
        The parameter is a list of shapes.
        """
        ...

    def defeaturing(self, shapeList: List[Shape], /) -> Shape:
        """
        Remove a feature defined by supplied faces and return a new shape.
        defeaturing(shapeList) -> Shape
        --
        The parameter is a list of faces.
        """
        ...

    def isInside(self, point: Vector, tolerance: float, checkFace: bool, /) -> bool:
        """
        Checks whether a point is inside or outside the shape.
        isInside(point, tolerance, checkFace) => Boolean
        --
        checkFace indicates if the point lying directly on a face is considered to be inside or not
        """
        ...

    def removeSplitter(self) -> Shape:
        """
        Removes redundant edges from the B-REP model
        removeSplitter() -> Shape
        """
        ...

    def proximity(self, shape: Shape, tolerance: float=None, /) -> Tuple[List[int], List[int]]:
        """
        Returns two lists of Face indexes for the Faces involved in the intersection.
        proximity(shape,[tolerance]) -> (selfFaces, shapeFaces)
        """
        ...

    def distToShape(self, shape: Shape, tol: float=1e-07, /) -> Tuple[float, List[Tuple[Vector, Vector]], List[Tuple]]:
        """
        Find the minimum distance to another shape.
        distToShape(shape, tol=1e-7) -> (dist, vectors, infos)
        --
        dist is the minimum distance, in mm (float value).

        vectors is a list of pairs of App.Vector. Each pair corresponds to solution.
        Example: [(App.Vector(2.0, -1.0, 2.0), App.Vector(2.0, 0.0, 2.0)),
        (App.Vector(2.0, -1.0, 2.0), App.Vector(2.0, -1.0, 3.0))]
        First vector is a point on self, second vector is a point on s.

        infos contains additional info on the solutions. It is a list of tuples:
        (topo1, index1, params1, topo2, index2, params2)

            topo1, topo2 are strings identifying type of BREP element: 'Vertex',
            'Edge', or 'Face'.

            index1, index2 are indexes of the elements (zero-based).

            params1, params2 are parameters of internal space of the elements. For
            vertices, params is None. For edges, params is one float, u. For faces,
            params is a tuple (u,v).
        """
        ...

    def getElement(self, elementName: str, silent: bool=False, /) -> Shape:
        """
        Returns a SubElement
        getElement(elementName, [silent = False]) -> Face | Edge | Vertex
        elementName:  SubElement name - i.e. 'Edge1', 'Face3' etc.
                      Accepts TNP mitigation mapped names as well
        silent:  True to suppress the exception throw if the shape isn't found.
        """
        ...

    def countElement(self, type: str, /) -> int:
        """
        Returns the count of a type of element
        countElement(type) -> int
        """
        ...

    def mapSubElement(self, shape: Union[Shape, Tuple[Shape, ...]], op: str='', /) -> None:
        """
        mapSubElement(shape|[shape...], op='') - maps the sub element of other shape

        shape:  other shape or sequence of shapes to map the sub-elements
        op:     optional string prefix to append before the mapped sub element names
        """
        ...

    def mapShapes(self, generated: List[Tuple[Shape, Shape]], modified: List[Tuple[Shape, Shape]], op: str='', /) -> None:
        """
        mapShapes(generated, modified, op='')

        generate element names with user defined mapping

        generated: a list of tuple(src, dst) that indicating src shape or shapes
        generates dst shape or shapes. Note that the dst shape or shapes
        must be sub-shapes of this shape.
        modified: a list of tuple(src, dst) that indicating src shape or shapes
        modifies into dst shape or shapes. Note that the dst shape or
        shapes must be sub-shapes of this shape.
        op: optional string prefix to append before the mapped sub element names
        """
        ...

    def getElementHistory(self, name: str, /) -> Union[Tuple[str, str, List[str]], None]:
        """
        getElementHistory(name) - returns the element mapped name history

        name: mapped element name belonging to this shape

        Returns tuple(sourceShapeTag, sourceName, [intermediateNames...]),
        or None if no history.
        """
        ...

    def getTolerance(self, mode: int, ShapeType: str='Shape', /) -> float:
        """
        Determines a tolerance from the ones stored in a shape
        getTolerance(mode, ShapeType=Shape) -> float
        --
        mode = 0 : returns the average value between sub-shapes,
        mode > 0 : returns the maximal found,
        mode < 0 : returns the minimal found.
        ShapeType defines what kinds of sub-shapes to consider:
        Shape (default) : all : Vertex, Edge, Face,
        Vertex : only vertices,
        Edge   : only edges,
        Face   : only faces,
        Shell  : combined Shell + Face, for each face (and containing
                 shell), also checks edge and Vertex
        """
        ...

    def overTolerance(self, value: float, ShapeType: str='Shape', /) -> List[Shape]:
        """
        Determines which shapes have a tolerance over the given value
        overTolerance(value, [ShapeType=Shape]) -> ShapeList
        --
        ShapeType is interpreted as in the method getTolerance
        """
        ...

    def inTolerance(self, valmin: float, valmax: float, ShapeType: str='Shape', /) -> List[Shape]:
        """
        Determines which shapes have a tolerance within a given interval
        inTolerance(valmin, valmax, [ShapeType=Shape]) -> ShapeList
        --
        ShapeType is interpreted as in the method getTolerance
        """
        ...

    def globalTolerance(self, mode: int, /) -> float:
        """
        Returns the computed tolerance according to the mode
        globalTolerance(mode) -> float
        --
        mode = 0 : average
        mode > 0 : maximal
        mode < 0 : minimal
        """
        ...

    def fixTolerance(self, value: float, ShapeType: str='Shape', /) -> None:
        """
        Sets (enforces) tolerances in a shape to the given value
        fixTolerance(value, [ShapeType=Shape])
        --
        ShapeType = Vertex : only vertices are set
        ShapeType = Edge   : only edges are set
        ShapeType = Face   : only faces are set
        ShapeType = Wire   : to have edges and their vertices set
        ShapeType = other value : all (vertices,edges,faces) are set
        """
        ...

    def limitTolerance(self, tmin: float, tmax: float=0, ShapeType: str='Shape', /) -> bool:
        """
        Limits tolerances in a shape
        limitTolerance(tmin, [tmax=0, ShapeType=Shape]) -> bool
        --
        tmin = tmax -> as fixTolerance (forces)
        tmin = 0   -> maximum tolerance will be tmax
        tmax = 0 or not given (more generally, tmax < tmin) ->
        tmax ignored, minimum will be tmin
        else, maximum will be max and minimum will be min
        ShapeType = Vertex : only vertices are set
        ShapeType = Edge   : only edges are set
        ShapeType = Face   : only faces are set
        ShapeType = Wire   : to have edges and their vertices set
        ShapeType = other value : all (vertices,edges,faces) are set
        Returns True if at least one tolerance of the sub-shape has been modified
        """
        ...

    def optimalBoundingBox(self, useTriangulation: bool=True, useShapeTolerance: bool=False, /) -> BoundBox:
        """
        Get the optimal bounding box
        optimalBoundingBox([useTriangulation = True, useShapeTolerance = False]) -> bound box
        """
        ...

    def clearCache(self) -> None:
        """
        Clear internal sub-shape cache
        """
        ...

    def findSubShape(self, shape: Shape, /) -> Tuple[Union[str, None], int]:
        """
        findSubShape(shape) -> (type_name, index)

        Find sub shape and return the shape type name and index. If not found,
        then return (None, 0)
        """
        ...

    def findSubShapesWithSharedVertex(self, shape: Shape, *, needName: bool=False, checkGeometry: bool=True, tol: float=1e-07, atol: float=1e-12) -> Union[List[Tuple[str, Shape]], List[Shape]]:
        """
        findSubShapesWithSharedVertex(shape, needName=False, checkGeometry=True, tol=1e-7, atol=1e-12) -> Shape

        shape: input elementary shape, currently only support Face, Edge, or Vertex

        needName: if True, return a list of tuple(name, shape), or else return a list
        of shapes.

        checkGeometry: whether to compare geometry

        tol: distance tolerance

        atol: angular tolerance

        Search sub shape by checking vertex coordinates and comparing the underlying
        geometries, This can find shapes that are copied. It currently only works with
        elementary shapes, Face, Edge, Vertex.
        """
        ...

    def getChildShapes(self, shapetype: str, avoidtype: str='', /) -> List[Shape]:
        """
        getChildShapes(shapetype, avoidtype='') -> list(Shape)

        Return a list of child sub-shapes of given type.

        shapetype: the type of requesting sub shapes
        avoidtype: optional shape type to skip when exploring
        """
        ...
    BoundBox: 'Part.BoundBox' = ...
    Placement: 'Part.Placement' = ...

class CompSolid(Shape):
    """
    TopoShapeCompSolid is the OpenCasCade topological compound solid wrapper
    """

    def add(self, solid: Shape, /) -> None:
        """
        Add a solid to the compound.
        add(solid)
        """
        ...

class Compound(Shape):
    """
    Create a compound out of a list of shapes

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, shapes: Shape | Sequence[Shape], /) -> None:
        ...

    def add(self, shape: Shape, /) -> None:
        """
        Add a shape to the compound.
        add(shape)
        """
        ...

    def connectEdgesToWires(self, Shared: bool=True, Tolerance: float=1e-07, /) -> 'TopoShapeCompound':
        """
        Build a compound of wires out of the edges of this compound.
        connectEdgesToWires([Shared = True, Tolerance = 1e-7]) -> Compound
        --
        If Shared is True  connection is performed only when adjacent edges share the same vertex.
        If Shared is False connection is performed only when ends of adjacent edges are at distance less than Tolerance.
        """
        ...

    def setFaces(self) -> None:
        """
        A shape is created from points and triangles and set to this object
        """
        ...

class Edge(Shape):
    """
    TopoShapeEdge is the OpenCasCade topological edge wrapper

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, curve: Geometry, first: float=..., last: float=..., /) -> None:
        ...

    @overload
    def __init__(self, shape: Shape, /) -> None:
        ...

    @overload
    def __init__(self, start: Vertex, end: Vertex, /) -> None:
        ...
    Tolerance: float = 0.0
    'Set or get the tolerance of the vertex'
    Length: Final[float] = 0.0
    'Returns the cartesian length of the curve'
    ParameterRange: Final[Tuple[float, float]] = (0.0, 0.0)
    '\n    Returns a 2 tuple with the range of the primary parameter\n    defining the curve. This is the same as would be returned by\n    the FirstParameter and LastParameter properties, i.e.\n\n    (LastParameter,FirstParameter)\n\n    What the parameter is depends on what type of edge it is. For a\n    Line the parameter is simply its cartesian length. Some other\n    examples are shown below:\n\n    Type                 Parameter\n    ---------------------------------------------------------------\n    Circle               Angle swept by circle (or arc) in radians\n    BezierCurve          Unitless number in the range 0.0 to 1.0\n    Helix                Angle swept by helical turns in radians\n    '
    FirstParameter: Final[float] = 0.0
    '\n    Returns the start value of the range of the primary parameter\n    defining the curve.\n\n    What the parameter is depends on what type of edge it is. For a\n    Line the parameter is simply its cartesian length. Some other\n    examples are shown below:\n\n    Type                 Parameter\n    -----------------------------------------------------------\n    Circle               Angle swept by circle (or arc) in radians\n    BezierCurve          Unitless number in the range 0.0 to 1.0\n    Helix                Angle swept by helical turns in radians\n    '
    LastParameter: Final[float] = 0.0
    '\n    Returns the end value of the range of the primary parameter\n    defining the curve.\n\n    What the parameter is depends on what type of edge it is. For a\n    Line the parameter is simply its cartesian length. Some other\n    examples are shown below:\n\n    Type                 Parameter\n    -----------------------------------------------------------\n    Circle               Angle swept by circle (or arc) in radians\n    BezierCurve          Unitless number in the range 0.0 to 1.0\n    Helix                Angle swept by helical turns in radians\n    '
    Curve: Final[object] = object()
    'Returns the 3D curve of the edge'
    Closed: Final[bool] = False
    'Returns true if the edge is closed'
    Degenerated: Final[bool] = False
    'Returns true if the edge is degenerated'
    Mass: Final[object] = object()
    'Returns the mass of the current system.'
    CenterOfMass: Final[object] = object()
    '\n    Returns the center of mass of the current system.\n    If the gravitational field is uniform, it is the center of gravity.\n    The coordinates returned for the center of mass are expressed in the\n    absolute Cartesian coordinate system.\n    '
    MatrixOfInertia: Final[object] = object()
    '\n    Returns the matrix of inertia. It is a symmetrical matrix.\n    The coefficients of the matrix are the quadratic moments of\n    inertia.\n\n     | Ixx Ixy Ixz 0 |\n     | Ixy Iyy Iyz 0 |\n     | Ixz Iyz Izz 0 |\n     | 0   0   0   1 |\n\n    The moments of inertia are denoted by Ixx, Iyy, Izz.\n    The products of inertia are denoted by Ixy, Ixz, Iyz.\n    The matrix of inertia is returned in the central coordinate\n    system (G, Gx, Gy, Gz) where G is the centre of mass of the\n    system and Gx, Gy, Gz the directions parallel to the X(1,0,0)\n    Y(0,1,0) Z(0,0,1) directions of the absolute cartesian\n    coordinate system.\n    '
    StaticMoments: Final[object] = object()
    '\n    Returns Ix, Iy, Iz, the static moments of inertia of the\n    current system; i.e. the moments of inertia about the\n    three axes of the Cartesian coordinate system.\n    '
    PrincipalProperties: Final[Dict] = {}
    '\n    Computes the principal properties of inertia of the current system.\n    There is always a set of axes for which the products\n    of inertia of a geometric system are equal to 0; i.e. the\n    matrix of inertia of the system is diagonal. These axes\n    are the principal axes of inertia. Their origin is\n    coincident with the center of mass of the system. The\n    associated moments are called the principal moments of inertia.\n    This function computes the eigen values and the\n    eigen vectors of the matrix of inertia of the system.\n    '
    Continuity: Final[str] = ''
    'Returns the continuity'

    def getParameterByLength(self, pos: float, tolerance: float=1e-07, /) -> float:
        """
        Get the value of the primary parameter at the given distance along the cartesian length of the edge.
        getParameterByLength(pos, [tolerance = 1e-7]) -> Float
        --
        Args:
            pos (float or int): The distance along the length of the edge at which to
                determine the primary parameter value. See help for the FirstParameter or
                LastParameter properties for more information on the primary parameter.
                If the given value is positive, the distance from edge start is used.
                If the given value is negative, the distance from edge end is used.
            tol (float): Computing tolerance. Optional, defaults to 1e-7.

        Returns:
            paramval (float): the value of the primary parameter defining the edge at the
                given position along its cartesian length.
        """
        ...

    def tangentAt(self, paramval: float, /) -> Vector:
        """
        Get the tangent direction at the given primary parameter value along the Edge if it is defined
        tangentAt(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the tangent direction e.g:

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.tangentAt(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is the Vector (-0.7071067811865475, 0.7071067811865476, 0.0)

                Values with magnitude greater than the Edge length return
                values of the tangent on the curve extrapolated beyond its
                length. This may not be valid for all Edges. Negative values
                similarly return a tangent on the curve extrapolated backwards
                (before the start point of the Edge). For example, using the
                same shape as above:

                >>> x.tangentAt(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865477, 0.7071067811865474, 0.0)

                Which gives the same result as

                >>> x.tangentAt(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865475, 0.7071067811865476, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the tangent to the Edge at the given
               location along its length (or extrapolated length)
        """
        ...

    def valueAt(self, paramval: float, /) -> Vector:
        """
        Get the value of the cartesian parameter value at the given parameter value along the Edge
        valueAt(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the value in terms of the main parameter defining
                the edge, what the parameter value is depends on the type of
                edge. See  e.g:

                For a circle value

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.valueAt(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is theVector (0.7071067811865476, 0.7071067811865475, 0.0)

                Values with magnitude greater than the Edge length return
                values on the curve extrapolated beyond its length. This may
                not be valid for all Edges. Negative values similarly return
                a parameter value on the curve extrapolated backwards (before the
                start point of the Edge). For example, using the same shape
                as above:

                >>> x.valueAt(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865474, -0.7071067811865477, 0.0)

                Which gives the same result as

                >>> x.valueAt(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865476, -0.7071067811865475, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the cartesian location on the Edge at the given
               distance along its length (or extrapolated length)
        """
        ...

    def parameters(self, face: object=..., /) -> List[float]:
        """
        Get the list of parameters of the tessellation of an edge.
        parameters([face]) -> list
        --
        If the edge is part of a face then this face is required as argument.
        An exception is raised if the edge has no polygon.
        """
        ...

    def parameterAt(self, vertex: object, /) -> float:
        """
        Get the parameter at the given vertex if lying on the edge
        parameterAt(Vertex) -> Float
        """
        ...

    def normalAt(self, paramval: float, /) -> Vector:
        """
        Get the normal direction at the given parameter value along the Edge if it is defined
        normalAt(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the normal direction e.g:

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.normalAt(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is the Vector (-0.7071067811865476, -0.7071067811865475, 0.0)

                Values with magnitude greater than the Edge length return
                values of the normal on the curve extrapolated beyond its
                length. This may not be valid for all Edges. Negative values
                similarly return a normal on the curve extrapolated backwards
                (before the start point of the Edge). For example, using the
                same shape as above:

                >>> x.normalAt(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865474, 0.7071067811865477, 0.0)

                Which gives the same result as

                >>> x.normalAt(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865476, 0.7071067811865475, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the normal to the Edge at the given
               location along its length (or extrapolated length)
        """
        ...

    def derivative1At(self, paramval: float, /) -> Vector:
        """
        Get the first derivative at the given parameter value along the Edge if it is defined
        derivative1At(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the first derivative e.g:

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.derivative1At(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is the Vector (-0.7071067811865475, 0.7071067811865476, 0.0)

                Values with magnitude greater than the Edge length return
                values of the first derivative on the curve extrapolated
                beyond its length. This may not be valid for all Edges.
                Negative values similarly return a first derivative on the
                curve extrapolated backwards (before the start point of the
                Edge). For example, using the same shape as above:

                >>> x.derivative1At(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865477, 0.7071067811865474, 0.0)

                Which gives the same result as

                >>> x.derivative1At(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (0.7071067811865475, 0.7071067811865476, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the first derivative to the Edge at the
               given location along its length (or extrapolated length)
        """
        ...

    def derivative2At(self, paramval: float, /) -> Vector:
        """
        Get the second derivative at the given parameter value along the Edge if it is defined
        derivative2At(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the second derivative e.g:

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.derivative2At(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is the Vector (-0.7071067811865476, -0.7071067811865475, 0.0)

                Values with magnitude greater than the Edge length return
                values of the second derivative on the curve extrapolated
                beyond its length. This may not be valid for all Edges.
                Negative values similarly return a second derivative on the
                curve extrapolated backwards (before the start point of the
                Edge). For example, using the same shape as above:

                >>> x.derivative2At(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865474, 0.7071067811865477, 0.0)

                Which gives the same result as

                >>> x.derivative2At(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865476, 0.7071067811865475, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the second derivative to the Edge at the
               given location along its length (or extrapolated length)
        """
        ...

    def derivative3At(self, paramval: float, /) -> Vector:
        """
        Get the third derivative at the given parameter value along the Edge if it is defined
        derivative3At(paramval) -> Vector
        --
        Args:
            paramval (float or int): The parameter value along the Edge at which to
                determine the third derivative e.g:

                x = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                y = x.derivative3At(x.FirstParameter + 0.5 * (x.LastParameter - x.FirstParameter))

                y is the Vector (0.7071067811865475, -0.7071067811865476, -0.0)

                Values with magnitude greater than the Edge length return
                values of the third derivative on the curve extrapolated
                beyond its length. This may not be valid for all Edges.
                Negative values similarly return a third derivative on the
                curve extrapolated backwards (before the start point of the
                Edge). For example, using the same shape as above:

                >>> x.derivative3At(x.FirstParameter + 3.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865477, -0.7071067811865474, 0.0)

                Which gives the same result as

                >>> x.derivative3At(x.FirstParameter -0.5*(x.LastParameter - x.FirstParameter))
                Vector (-0.7071067811865475, -0.7071067811865476, 0.0)

                Since it is a circle

        Returns:
            Vector: representing the third derivative to the Edge at the
               given location along its length (or extrapolated length)
        """
        ...

    def curvatureAt(self, paramval: float, /) -> float:
        """
        Get the curvature at the given parameter [First|Last] if defined
        curvatureAt(paramval) -> Float
        """
        ...

    def centerOfCurvatureAt(self, paramval: float, /) -> Vector:
        """
        Get the center of curvature at the given parameter [First|Last] if defined
        centerOfCurvatureAt(paramval) -> Vector
        """
        ...

    def firstVertex(self, Orientation: bool=False, /) -> Vertex:
        """
        Returns the Vertex of orientation FORWARD in this edge.
        firstVertex([Orientation=False]) -> Vertex
        --
        If there is none a Null shape is returned.
        Orientation = True : taking into account the edge orientation
        """
        ...

    def lastVertex(self, Orientation: bool=False, /) -> Vertex:
        """
        Returns the Vertex of orientation REVERSED in this edge.
        lastVertex([Orientation=False]) -> Vertex
        --
        If there is none a Null shape is returned.
        Orientation = True : taking into account the edge orientation
        """
        ...

    @overload
    def discretize(self, Number: int, First: float=..., Last: float=...) -> List[Vector]:
        ...

    @overload
    def discretize(self, QuasiNumber: int, First: float=..., Last: float=...) -> List[Vector]:
        ...

    @overload
    def discretize(self, Distance: float, First: float=..., Last: float=...) -> List[Vector]:
        ...

    @overload
    def discretize(self, Deflection: float, First: float=..., Last: float=...) -> List[Vector]:
        ...

    @overload
    def discretize(self, QuasiDeflection: float, First: float=..., Last: float=...) -> List[Vector]:
        ...

    @overload
    def discretize(self, Angular: float, Curvature: float, Minimum: int=..., First: float=..., Last: float=...) -> List[Vector]:
        ...

    def discretize(self, **kwargs) -> List[Vector]:
        """
        Discretizes the edge and returns a list of points.
        discretize(kwargs) -> list
        --
        The function accepts keywords as argument:
        discretize(Number=n) => gives a list of 'n' equidistant points
        discretize(QuasiNumber=n) => gives a list of 'n' quasi equidistant points (is faster than the method above)
        discretize(Distance=d) => gives a list of equidistant points with distance 'd'
        discretize(Deflection=d) => gives a list of points with a maximum deflection 'd' to the edge
        discretize(QuasiDeflection=d) => gives a list of points with a maximum deflection 'd' to the edge (faster)
        discretize(Angular=a,Curvature=c,[Minimum=m]) => gives a list of points with an angular deflection of 'a'
                                            and a curvature deflection of 'c'. Optionally a minimum number of points
                                            can be set which by default is set to 2.

        Optionally you can set the keywords 'First' and 'Last' to define a sub-range of the parameter range
        of the edge.

        If no keyword is given then it depends on whether the argument is an int or float.
        If it's an int then the behaviour is as if using the keyword 'Number', if it's float
        then the behaviour is as if using the keyword 'Distance'.

        Example:

        import Part
        e=Part.makeCircle(5)
        p=e.discretize(Number=50,First=3.14)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)

        p=e.discretize(Angular=0.09,Curvature=0.01,Last=3.14,Minimum=100)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)
        """
        ...

    def countNodes(self) -> int:
        """
        Returns the number of nodes of the 3D polygon of the edge.
        """
        ...

    def split(self, paramval: float, /) -> Wire:
        """
        Splits the edge at the given parameter values and builds a wire out of it
        split(paramval) -> Wire
        --
        Args:
            paramval (float or list_of_floats): The parameter values along the Edge at which to
                split it e.g:

                edge = Part.makeCircle(1, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), 0, 90)
                wire = edge.split([0.5, 1.0])

        Returns:
            Wire: wire made up of two Edges
        """
        ...

    def isSeam(self, Face: object, /) -> bool:
        """
        Checks whether the edge is a seam edge.
        isSeam(Face)
        """
        ...

    def curveOnSurface(self, idx: int, /) -> Tuple[object, object, object, float, float]:
        """
        Returns the 2D curve, the surface, the placement and the parameter range of index idx.
        curveOnSurface(idx) -> None or tuple
        --
        Returns None if index idx is out of range.
        Returns a 5-items tuple of a curve, a surface, a placement, first parameter and last parameter.
        """
        ...

class Face(Shape):
    """
    TopoShapeFace is the OpenCasCade topological face wrapper

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, shape: Shape, /) -> None:
        ...

    @overload
    def __init__(self, face: Shape, wire: Shape, /) -> None:
        ...

    @overload
    def __init__(self, wires: Sequence[Shape], /) -> None:
        ...
    Tolerance: float = ...
    'Set or get the tolerance of the vertex'
    ParameterRange: Final[Tuple] = ...
    'Returns a 4 tuple with the parameter range'
    Surface: Final[object] = ...
    'Returns the geometric surface of the face'
    Wire: Final[object] = ...
    '\n    The outer wire of this face\n    deprecated -- use OuterWire\n    '
    OuterWire: Final[object] = ...
    'The outer wire of this face'
    Mass: Final[object] = ...
    'Returns the mass of the current system.'
    CenterOfMass: Final[object] = ...
    '\n    Returns the center of mass of the current system.\n    If the gravitational field is uniform, it is the center of gravity.\n    The coordinates returned for the center of mass are expressed in the\n    absolute Cartesian coordinate system.\n    '
    MatrixOfInertia: Final[object] = ...
    '\n    Returns the matrix of inertia. It is a symmetrical matrix.\n    The coefficients of the matrix are the quadratic moments of\n    inertia.\n\n     | Ixx Ixy Ixz 0 |\n     | Ixy Iyy Iyz 0 |\n     | Ixz Iyz Izz 0 |\n     | 0   0   0   1 |\n\n    The moments of inertia are denoted by Ixx, Iyy, Izz.\n    The products of inertia are denoted by Ixy, Ixz, Iyz.\n    The matrix of inertia is returned in the central coordinate\n    system (G, Gx, Gy, Gz) where G is the centre of mass of the\n    system and Gx, Gy, Gz the directions parallel to the X(1,0,0)\n    Y(0,1,0) Z(0,0,1) directions of the absolute cartesian\n    coordinate system.\n    '
    StaticMoments: Final[object] = ...
    '\n    Returns Ix, Iy, Iz, the static moments of inertia of the\n    current system; i.e. the moments of inertia about the\n    three axes of the Cartesian coordinate system.\n    '
    PrincipalProperties: Final[Dict] = ...
    '\n    Computes the principal properties of inertia of the current system.\n    There is always a set of axes for which the products\n    of inertia of a geometric system are equal to 0; i.e. the\n    matrix of inertia of the system is diagonal. These axes\n    are the principal axes of inertia. Their origin is\n    coincident with the center of mass of the system. The\n    associated moments are called the principal moments of inertia.\n    This function computes the eigen values and the\n    eigen vectors of the matrix of inertia of the system.\n    '

    def addWire(self, wire: object, /) -> None:
        """
        Adds a wire to the face.
        addWire(wire)
        """
        ...

    def makeOffset(self, dist: float, /) -> object:
        """
        Offset the face by a given amount.
        makeOffset(dist) -> Face
        --
        Returns Compound of Wires. Deprecated - use makeOffset2D instead.
        """
        ...

    def makeEvolved(self, Profile: Shape, Join: int, *, AxeProf: bool, Solid: bool, ProfOnSpine: bool, Tolerance: float) -> Shape:
        """
        Profile along the spine
        """
        ...

    def getUVNodes(self) -> List[Tuple[float, float]]:
        """
        Get the list of (u,v) nodes of the tessellation
        getUVNodes() -> list
        --
        An exception is raised if the face is not triangulated.
        """
        ...

    def tangentAt(self, u: float, v: float, /) -> Vector:
        """
        Get the tangent in u and v isoparametric at the given point if defined
        tangentAt(u,v) -> Vector
        """
        ...

    def valueAt(self, u: float, v: float, /) -> Vector:
        """
        Get the point at the given parameter [0|Length] if defined
        valueAt(u,v) -> Vector
        """
        ...

    def normalAt(self, pos: float, /) -> Vector:
        """
        Get the normal vector at the given parameter [0|Length] if defined
        normalAt(pos) -> Vector
        """
        ...

    def derivative1At(self, u: float, v: float, /) -> Tuple[Vector, Vector]:
        """
        Get the first derivative at the given parameter [0|Length] if defined
        derivative1At(u,v) -> (vectorU,vectorV)
        """
        ...

    def derivative2At(self, u: float, v: float, /) -> Tuple[Vector, Vector]:
        """
        Vector = d2At(pos) - Get the second derivative at the given parameter [0|Length] if defined
        derivative2At(u,v) -> (vectorU,vectorV)
        """
        ...

    def curvatureAt(self, u: float, v: float, /) -> float:
        """
        Get the curvature at the given parameter [0|Length] if defined
        curvatureAt(u,v) -> Float
        """
        ...

    def isPartOfDomain(self, u: float, v: float, /) -> bool:
        """
        Check if a given (u,v) pair is inside the domain of a face
        isPartOfDomain(u,v) -> bool
        """
        ...

    def makeHalfSpace(self, pos: object, /) -> object:
        """
        Make a half-space solid by this face and a reference point.
        makeHalfSpace(pos) -> Shape
        """
        ...

    def validate(self) -> None:
        """
        Validate the face.
        validate()
        """
        ...

    def countNodes(self) -> int:
        """
        Returns the number of nodes of the triangulation.
        """
        ...

    def countTriangles(self) -> int:
        """
        Returns the number of triangles of the triangulation.
        """
        ...

    def curveOnSurface(self, Edge: object, /) -> Optional[Tuple[object, float, float]]:
        """
        Returns the curve associated to the edge in the parametric space of the face.
        curveOnSurface(Edge) -> (curve, min, max) or None
        --
        If this curve exists then a tuple of curve and parameter range is returned.
        Returns None if this curve does not exist.
        """
        ...

    def cutHoles(self, list_of_wires: List[object], /) -> None:
        """
        Cut holes in the face.
        cutHoles(list_of_wires)
        """
        ...

class Shell(Shape):
    """
    Create a shell out of a list of faces

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    """
    Mass: Final[object] = ...
    'Returns the mass of the current system.'
    CenterOfMass: Final[object] = ...
    '\n    Returns the center of mass of the current system.\n    If the gravitational field is uniform, it is the center of gravity.\n    The coordinates returned for the center of mass are expressed in the\n    absolute Cartesian coordinate system.\n    '
    MatrixOfInertia: Final[object] = ...
    '\n    Returns the matrix of inertia. It is a symmetrical matrix.\n    The coefficients of the matrix are the quadratic moments of\n    inertia.\n\n     | Ixx Ixy Ixz 0 |\n     | Ixy Iyy Iyz 0 |\n     | Ixz Iyz Izz 0 |\n     | 0   0   0   1 |\n\n    The moments of inertia are denoted by Ixx, Iyy, Izz.\n    The products of inertia are denoted by Ixy, Ixz, Iyz.\n    The matrix of inertia is returned in the central coordinate\n    system (G, Gx, Gy, Gz) where G is the centre of mass of the\n    system and Gx, Gy, Gz the directions parallel to the X(1,0,0)\n    Y(0,1,0) Z(0,0,1) directions of the absolute cartesian\n    coordinate system.\n    '
    StaticMoments: Final[object] = ...
    '\n    Returns Ix, Iy, Iz, the static moments of inertia of the\n    current system; i.e. the moments of inertia about the\n    three axes of the Cartesian coordinate system.\n    '
    PrincipalProperties: Final[Dict] = ...
    '\n    Computes the principal properties of inertia of the current system.\n    There is always a set of axes for which the products\n    of inertia of a geometric system are equal to 0; i.e. the\n    matrix of inertia of the system is diagonal. These axes\n    are the principal axes of inertia. Their origin is\n    coincident with the center of mass of the system. The\n    associated moments are called the principal moments of inertia.\n    This function computes the eigen values and the\n    eigen vectors of the matrix of inertia of the system.\n    '

    def add(self, face: object, /) -> None:
        """
        Add a face to the shell.
        add(face)
        """
        ...

    def getFreeEdges(self) -> object:
        """
        Get free edges as compound.
        getFreeEdges() -> compound
        """
        ...

    def getBadEdges(self) -> object:
        """
        Get bad edges as compound.
        getBadEdges() -> compound
        """
        ...

    def makeHalfSpace(self, point: object, /) -> object:
        """
        Make a half-space solid by this shell and a reference point.
        makeHalfSpace(point) -> Solid
        """
        ...

class Solid(Shape):
    """
    Part.Solid(shape): Create a solid out of shells of shape. If shape is a compsolid, the overall volume solid is created.

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    """
    Mass: Final[float] = 0.0
    'Returns the mass of the current system.'
    CenterOfMass: Final[Vector] = Vector()
    '\n    Returns the center of mass of the current system.\n    If the gravitational field is uniform, it is the center of gravity.\n    The coordinates returned for the center of mass are expressed in the\n    absolute Cartesian coordinate system.\n    '
    MatrixOfInertia: Final[Matrix] = Matrix()
    '\n    Returns the matrix of inertia. It is a symmetrical matrix.\n    The coefficients of the matrix are the quadratic moments of\n    inertia.\n\n     | Ixx Ixy Ixz 0 |\n     | Ixy Iyy Iyz 0 |\n     | Ixz Iyz Izz 0 |\n     | 0   0   0   1 |\n\n    The moments of inertia are denoted by Ixx, Iyy, Izz.\n    The products of inertia are denoted by Ixy, Ixz, Iyz.\n    The matrix of inertia is returned in the central coordinate\n    system (G, Gx, Gy, Gz) where G is the centre of mass of the\n    system and Gx, Gy, Gz the directions parallel to the X(1,0,0)\n    Y(0,1,0) Z(0,0,1) directions of the absolute cartesian\n    coordinate system.\n    '
    StaticMoments: Final[object] = object()
    '\n    Returns Ix, Iy, Iz, the static moments of inertia of the\n    current system; i.e. the moments of inertia about the\n    three axes of the Cartesian coordinate system.\n    '
    PrincipalProperties: Final[Dict[str, float]] = {}
    '\n    Computes the principal properties of inertia of the current system.\n    There is always a set of axes for which the products\n    of inertia of a geometric system are equal to 0; i.e. the\n    matrix of inertia of the system is diagonal. These axes\n    are the principal axes of inertia. Their origin is\n    coincident with the center of mass of the system. The\n    associated moments are called the principal moments of inertia.\n    This function computes the eigen values and the\n    eigen vectors of the matrix of inertia of the system.\n    '
    OuterShell: Final[Shape] = Shape()
    '\n    Returns the outer most shell of this solid or an null\n    shape if the solid has no shells\n    '

    def getMomentOfInertia(self, point: Vector, direction: Vector, /) -> float:
        """
        computes the moment of inertia of the material system about the axis A.
        getMomentOfInertia(point,direction) -> Float
        """
        ...

    def getRadiusOfGyration(self, point: Vector, direction: Vector, /) -> float:
        """
        Returns the radius of gyration of the current system about the axis A.
        getRadiusOfGyration(point,direction) -> Float
        """
        ...

    @overload
    def offsetFaces(self, facesTuple: Tuple[Shape, ...], offset: float, /) -> Shape:
        ...

    @overload
    def offsetFaces(self, facesDict: Dict[Shape, float], /) -> Shape:
        ...

    def offsetFaces(self, *args, **kwargs) -> Shape:
        """
        Extrude single faces of the solid.
        offsetFaces(facesTuple, offset) -> Solid
        or
        offsetFaces(dict) -> Solid
        --
        Example:
        solid.offsetFaces((solid.Faces[0],solid.Faces[1]), 1.5)

        solid.offsetFaces({solid.Faces[0]:1.0,solid.Faces[1]:2.0})
        """
        ...

class Vertex(Shape):
    """
    TopoShapeVertex is the OpenCasCade topological vertex wrapper

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    """

    @overload
    def __init__(self, x: float=..., y: float=..., z: float=..., /) -> None:
        ...

    @overload
    def __init__(self, coordinates: Vector, /) -> None:
        ...

    @overload
    def __init__(self, coordinates: tuple[float, float, float], /) -> None:
        ...

    @overload
    def __init__(self, point: 'Part.Point', /) -> None:
        ...

    @overload
    def __init__(self, shape: Shape, /) -> None:
        ...
    X: Final[float] = ...
    'X component of this Vertex.'
    Y: Final[float] = ...
    'Y component of this Vertex.'
    Z: Final[float] = ...
    'Z component of this Vertex.'
    Point: Final[Vector] = ...
    'Position of this Vertex as a Vector'
    Tolerance: float = ...
    'Set or get the tolerance of the vertex'

class Wire(Shape):
    """
    TopoShapeWire is the OpenCasCade topological wire wrapper

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    Licence: LGPL
    DeveloperDocu: TopoShapeWire is the OpenCasCade topological wire wrapper
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, shape: Shape, /) -> None:
        ...

    @overload
    def __init__(self, shapes: Sequence[Shape], /) -> None:
        ...
    Mass: Final[object] = ...
    'Returns the mass of the current system.'
    CenterOfMass: Final[object] = ...
    '\n    Returns the center of mass of the current system.\n    If the gravitational field is uniform, it is the center of gravity.\n    The coordinates returned for the center of mass are expressed in the\n    absolute Cartesian coordinate system.\n    '
    MatrixOfInertia: Final[object] = ...
    '\n    Returns the matrix of inertia. It is a symmetrical matrix.\n    The coefficients of the matrix are the quadratic moments of\n    inertia.\n\n     | Ixx Ixy Ixz 0 |\n     | Ixy Iyy Iyz 0 |\n     | Ixz Iyz Izz 0 |\n     | 0   0   0   1 |\n\n    The moments of inertia are denoted by Ixx, Iyy, Izz.\n    The products of inertia are denoted by Ixy, Ixz, Iyz.\n    The matrix of inertia is returned in the central coordinate\n    system (G, Gx, Gy, Gz) where G is the centre of mass of the\n    system and Gx, Gy, Gz the directions parallel to the X(1,0,0)\n    Y(0,1,0) Z(0,0,1) directions of the absolute cartesian\n    coordinate system.\n    '
    StaticMoments: Final[object] = ...
    '\n    Returns Ix, Iy, Iz, the static moments of inertia of the\n    current system; i.e. the moments of inertia about the\n    three axes of the Cartesian coordinate system.\n    '
    PrincipalProperties: Final[Dict] = ...
    '\n    Computes the principal properties of inertia of the current system.\n    There is always a set of axes for which the products\n    of inertia of a geometric system are equal to 0; i.e. the\n    matrix of inertia of the system is diagonal. These axes\n    are the principal axes of inertia. Their origin is\n    coincident with the center of mass of the system. The\n    associated moments are called the principal moments of inertia.\n    This function computes the eigen values and the\n    eigen vectors of the matrix of inertia of the system.\n    '
    OrderedEdges: Final[List] = ...
    'List of ordered edges in this shape.'
    Continuity: Final[str] = ...
    'Returns the continuity'
    OrderedVertexes: Final[List] = ...
    'List of ordered vertexes in this shape.'

    def makeOffset(self) -> object:
        """
        Offset the shape by a given amount. DEPRECATED - use makeOffset2D instead.
        """
        ...

    def add(self, edge: object, /) -> None:
        """
        Add an edge to the wire
        add(edge)
        """
        ...

    def fixWire(self, face: Optional[object]=None, tolerance: Optional[float]=None, /) -> None:
        """
        Fix wire
        fixWire([face, tolerance])
        --
        A face and a tolerance can optionally be supplied to the algorithm:
        """
        ...

    def makeHomogenousWires(self, wire: object, /) -> object:
        """
        Make this and the given wire homogeneous to have the same number of edges
        makeHomogenousWires(wire) -> Wire
        """
        ...

    def makePipe(self, profile: object, /) -> object:
        """
        Make a pipe by sweeping along a wire.
        makePipe(profile) -> Shape
        """
        ...

    def makePipeShell(self, shapeList: List[object], isSolid: bool=False, isFrenet: bool=False, transition: int=0, /) -> object:
        """
        Make a loft defined by a list of profiles along a wire.
        makePipeShell(shapeList,[isSolid=False,isFrenet=False,transition=0]) -> Shape
        --
        Transition can be 0 (default), 1 (right corners) or 2 (rounded corners).
        """
        ...

    def makeEvolved(self, Profile: Shape, Join: int, *, AxeProf: bool, Solid: bool, ProfOnSpine: bool, Tolerance: float) -> Shape:
        """
        Profile along the spine
        """
        ...

    def approximate(self, Tol2d: float=None, Tol3d: float=0.0001, MaxSegments: int=10, MaxDegree: int=3) -> object:
        """
        Approximate B-Spline-curve from this wire
        approximate([Tol2d,Tol3d=1e-4,MaxSegments=10,MaxDegree=3]) -> BSpline
        """
        ...

    @overload
    def discretize(self, Number: int) -> List[object]:
        """
        discretize(Number=n) -> list
        """
        ...

    @overload
    def discretize(self, QuasiNumber: int) -> List[object]:
        """
        discretize(QuasiNumber=n) -> list
        """
        ...

    @overload
    def discretize(self, Distance: float) -> List[object]:
        """
        discretize(Distance=d) -> list
        """
        ...

    @overload
    def discretize(self, Deflection: float) -> List[object]:
        """
        discretize(Deflection=d) -> list
        """
        ...

    @overload
    def discretize(self, QuasiDeflection: float) -> List[object]:
        """
        discretize(QuasiDeflection=d) -> list
        """
        ...

    @overload
    def discretize(self, Angular: float, Curvature: float, Minimum: int=2) -> List[object]:
        """
        discretize(Angular=a,Curvature=c,[Minimum=m]) -> list
        """
        ...

    def discretize(self, **kwargs) -> List[object]:
        """
        Discretizes the wire and returns a list of points.
        discretize(kwargs) -> list
        --
        The function accepts keywords as argument:
        discretize(Number=n) => gives a list of 'n' equidistant points
        discretize(QuasiNumber=n) => gives a list of 'n' quasi equidistant points (is faster than the method above)
        discretize(Distance=d) => gives a list of equidistant points with distance 'd'
        discretize(Deflection=d) => gives a list of points with a maximum deflection 'd' to the wire
        discretize(QuasiDeflection=d) => gives a list of points with a maximum deflection 'd' to the wire (faster)
        discretize(Angular=a,Curvature=c,[Minimum=m]) => gives a list of points with an angular deflection of 'a'
                                            and a curvature deflection of 'c'. Optionally a minimum number of points
                                            can be set which by default is set to 2.

        Optionally you can set the keywords 'First' and 'Last' to define a sub-range of the parameter range
        of the wire.

        If no keyword is given then it depends on whether the argument is an int or float.
        If it's an int then the behaviour is as if using the keyword 'Number', if it's float
        then the behaviour is as if using the keyword 'Distance'.

        Example:

        import Part
        V=App.Vector

        e1=Part.makeCircle(5,V(0,0,0),V(0,0,1),0,180)
        e2=Part.makeCircle(5,V(10,0,0),V(0,0,1),180,360)
        w=Part.Wire([e1,e2])

        p=w.discretize(Number=50)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)


        p=w.discretize(Angular=0.09,Curvature=0.01,Minimum=100)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)
        """
        ...

class Toroid(GeometrySurface):
    """
    Describes a toroid in 3D space
    """
    MajorRadius: float = ...
    'The major radius of the toroid.'
    MinorRadius: float = ...
    'The minor radius of the toroid.'
    Center: Vector = ...
    'Center of the toroid.'
    Axis: Vector = ...
    'The axis direction of the toroid'
    Area: Final[float] = 0.0
    'Compute the area of the toroid.'
    Volume: Final[float] = 0.0
    'Compute the volume of the toroid.'

class TrimmedCurve(BoundedCurve):
    """
    The abstract class TrimmedCurve is the root class of all trimmed curve objects.

    Author: Abdullah Tahiri (abdullah.tahiri.yo@gmail.com)
    Licence: LGPL
    """

    def setParameterRange(self, first: float, last: float, /) -> None:
        """
        Re-trims this curve to the provided parameter range ([Float=First, Float=Last])
        """
        ...

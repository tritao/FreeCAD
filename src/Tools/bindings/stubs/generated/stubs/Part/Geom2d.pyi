# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import Vector

from typing import *

# src/Mod/Part/App/Geom2d/ArcOfCircle2d.pyi:17
class ArcOfCircle2d(ArcOfConic2d):
    """
    Describes a portion of a circle

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """
    Radius: float = ...
    'The radius of the circle.'
    Circle: Final[object] = ...
    'The internal circle representation'

    @overload
    def __init__(self, Radius: float, Circle: object) -> None:
        ...
    '\n    ArcOfCircle2d(Radius, Circle) -> None\n\n    Constructor for ArcOfCircle2d.\n\n    Parameters:\n        Radius : float\n            The radius of the circle.\n        Circle : object\n            The internal circle representation.\n    '
    ...

# src/Mod/Part/App/Geom2d/ArcOfConic2d.pyi:18
class ArcOfConic2d(Curve2d):
    """
    Describes an abstract arc of conic in 2d space.

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """
    Location: object = ...
    'Location of the conic.'
    Eccentricity: Final[float] = ...
    '\n    returns the eccentricity value of the conic e.\n    e = 0 for a circle\n    0 < e < 1 for an ellipse  (e = 0 if MajorRadius = MinorRadius)\n    e > 1 for a hyperbola\n    e = 1 for a parabola\n    '
    XAxis: object = ...
    'The X axis direction of the circle.'
    YAxis: object = ...
    'The Y axis direction of the circle.'

# src/Mod/Part/App/Geom2d/ArcOfEllipse2d.pyi:17
class ArcOfEllipse2d(ArcOfConic2d):
    """
    Describes a portion of an ellipse
    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """
    MajorRadius: float = ...
    'The major radius of the ellipse.'
    MinorRadius: float = ...
    'The minor radius of the ellipse.'
    Ellipse: Final[object] = ...
    'The internal ellipse representation'

    @overload
    def __init__(self) -> None:
        ...

# src/Mod/Part/App/Geom2d/ArcOfHyperbola2d.pyi:17
class ArcOfHyperbola2d(ArcOfConic2d):
    """
    Describes a portion of an hyperbola
    Author: Werner Mayer (wmayer@users.sourceforge.net) Licence: LGPL
    """
    MajorRadius: float = ...
    'The major radius of the hyperbola.'
    MinorRadius: float = ...
    'The minor radius of the hyperbola.'
    Hyperbola: Final[object] = ...
    'The internal hyperbola representation'

    @overload
    def __init__(self) -> None:
        ...

# src/Mod/Part/App/Geom2d/ArcOfParabola2d.pyi:17
class ArcOfParabola2d(ArcOfConic2d):
    """
    Describes a portion of a parabola.

    Author: Werner Mayer
    Licence: LGPL
    """
    Focal: float = ...
    'The focal length of the parabola.'
    Parabola: Final[object] = ...
    'The internal parabola representation.'

    @overload
    def __init__(self) -> None:
        ...

# src/Mod/Part/App/Geom2d/BSplineCurve2d.pyi:18
class BSplineCurve2d(Curve2d):
    """
    Describes a B-Spline curve in 3D space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Degree: Final[int] = ...
    'Returns the polynomial degree of this B-Spline curve.'
    MaxDegree: Final[int] = ...
    'Returns the value of the maximum polynomial degree of any\n                    B-Spline curve curve. This value is 25.'
    NbPoles: Final[int] = ...
    'Returns the number of poles of this B-Spline curve.'
    NbKnots: Final[int] = ...
    'Returns the number of knots of this B-Spline curve.'
    StartPoint: Final[object] = ...
    'Returns the start point of this B-Spline curve.'
    EndPoint: Final[object] = ...
    'Returns the end point of this B-Spline curve.'
    FirstUKnotIndex: Final[object] = ...
    'Returns the index in the knot array of the knot\n                    corresponding to the first or last parameter\n                    of this B-Spline curve.'
    LastUKnotIndex: Final[object] = ...
    'Returns the index in the knot array of the knot\n                    corresponding to the first or last parameter\n                    of this B-Spline curve.'
    KnotSequence: Final[list] = ...
    'Returns the knots sequence of this B-Spline curve.'

    def isRational(self) -> bool:
        """
        Returns true if this B-Spline curve is rational.
        A B-Spline curve is rational if, at the time of construction, the weight table has been initialized.
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

    def increaseDegree(self, Degree: int, /) -> None:
        """
        increaseDegree(Int=Degree)

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

        Inserts a knot value in the sequence of knots. If u is an existing knot the multiplicity is increased by mult.
        """
        ...

    def insertKnots(self, list_of_floats: list[float], list_of_ints: list[int], tol: float=0.0, bool_add: bool=True, /) -> None:
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

    def removeKnot(self, Index: int, M: int, tol: float, /) -> None:
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

    def setKnot(self, value: float, /) -> None:
        """
        Set a knot of the B-Spline curve.
        """
        ...

    def getKnot(self, index: int, /) -> float:
        """
        Get a knot of the B-Spline curve.
        """
        ...

    def setKnots(self, knots: list[float], /) -> None:
        """
        Set knots of the B-Spline curve.
        """
        ...

    def getKnots(self) -> list[float]:
        """
        Get all knots of the B-Spline curve.
        """
        ...

    def setPole(self, P: Vector, Index: int, /) -> None:
        """
        Modifies this B-Spline curve by assigning P to the pole of index Index in the poles table.
        """
        ...

    def getPole(self, Index: int, /) -> Vector:
        """
        Get a pole of the B-Spline curve.
        """
        ...

    def getPoles(self) -> list[Vector]:
        """
        Get all poles of the B-Spline curve.
        """
        ...

    def setWeight(self, weight: float, Index: int, /) -> None:
        """
        Set a weight of the B-Spline curve.
        """
        ...

    def getWeight(self, Index: int, /) -> float:
        """
        Get a weight of the B-Spline curve.
        """
        ...

    def getWeights(self) -> list[float]:
        """
        Get all weights of the B-Spline curve.
        """
        ...

    def getPolesAndWeights(self) -> tuple[list[Vector], list[float]]:
        """
        Returns the table of poles and weights in homogeneous coordinates.
        """
        ...

    def getResolution(self) -> float:
        """
        Computes for this B-Spline curve the parametric tolerance (UTolerance)
        for a given 3D tolerance (Tolerance3D).
        If f(t) is the equation of this B-Spline curve, the parametric tolerance ensures that:
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
        Assigns the knot of index Index in the knots table as the origin of this periodic B-Spline curve.
        As a consequence, the knots and poles tables are modified.
        """
        ...

    def getMultiplicity(self, index: int, /) -> int:
        """
        Returns the multiplicity of the knot of index from the knots table of this B-Spline curve.
        """
        ...

    def getMultiplicities(self) -> list[int]:
        """
        Returns the multiplicities table M of the knots of this B-Spline curve.
        """
        ...

    def approximate(self, **kwargs) -> None:
        """
        Replaces this B-Spline curve by approximating a set of points.
        The function accepts keywords as arguments.

        approximate2(Points = list_of_points)

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
        Continuity must be C0, C1 or C2, else defaults to C2.

        Parameters = list of floats : knot sequence of the approximated points.
        This argument is only used if the weights above are all null.

        ParamType = string ('Uniform','Centripetal' or 'ChordLength')
        Parameterization type. Only used if weights and Parameters above aren't specified.

        Note : Continuity of the spline defaults to C2. However, it may not be applied if
        it conflicts with other parameters ( especially DegMax ).
        """
        ...

    def getCardinalSplineTangents(self, **kwargs) -> None:
        """
        Compute the tangents for a Cardinal spline
        """
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

    def buildFromPoles(self, poles: list[Vector], /) -> None:
        """
        Builds a B-Spline by a list of poles.
        """
        ...

    @overload
    def buildFromPolesMultsKnots(self, poles: list[Vector], mults: tuple[int, ...], knots: tuple[float, ...], periodic: bool, degree: int) -> None:
        ...

    @overload
    def buildFromPolesMultsKnots(self, poles: list[Vector], mults: tuple[int, ...], knots: tuple[float, ...], periodic: bool, degree: int, weights: tuple[float, ...], CheckRational: bool) -> None:
        ...

    def buildFromPolesMultsKnots(self, **kwargs) -> None:
        """
        Builds a B-Spline by a lists of Poles, Mults, Knots.
        arguments: poles (sequence of Base.Vector),
        [mults , knots, periodic, degree, weights (sequence of float), CheckRational]

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

    def toBezier(self) -> list:
        """
        Build a list of Bezier splines.
        """
        ...

    def toBiArcs(self, tolerance: float, /) -> list:
        """
        toBiArcs(tolerance) -> list.
        Build a list of arcs and lines to approximate the B-spline.
        """
        ...

    def join(self, other: 'BSplineCurve2d', /) -> 'BSplineCurve2d':
        """
        Build a new spline by joining this and a second spline.
        """
        ...

    def makeC1Continuous(self, tol: float=1e-06, ang_tol: float=1e-07, /) -> 'BSplineCurve2d':
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

# src/Mod/Part/App/Geom2d/BezierCurve2d.pyi:17
class BezierCurve2d(Curve2d):
    """
    Describes a rational or non-rational Bezier curve in 2d space:
        -- a non-rational Bezier curve is defined by a table of poles (also called control points)
        -- a rational Bezier curve is defined by a table of poles with varying weights

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Degree: Final[int] = ...
    'Returns the polynomial degree of this Bezier curve, which is equal to the number of poles minus 1.'
    MaxDegree: Final[int] = ...
    'Returns the value of the maximum polynomial degree of any Bezier curve curve. This value is 25.'
    NbPoles: Final[int] = ...
    'Returns the number of poles of this Bezier curve.'
    StartPoint: Final[object] = ...
    'Returns the start point of this Bezier curve.'
    EndPoint: Final[object] = ...
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
        Returns true if the distance between the start point and end point of this Bezier curve
        is less than or equal to gp::Resolution().
        """
        ...

    def increase(self, Degree: int, /) -> None:
        """
        increase(Int=Degree)
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

    def removePole(self, index: int, /) -> None:
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

    def setPole(self, index: int, pole: object, /) -> None:
        """
        Set a pole of the Bezier curve.
        """
        ...

    def getPole(self, index: int, /) -> object:
        """
        Get a pole of the Bezier curve.
        """
        ...

    def getPoles(self) -> List[object]:
        """
        Get all poles of the Bezier curve.
        """
        ...

    def setPoles(self, poles: List[object], /) -> None:
        """
        Set the poles of the Bezier curve.
        """
        ...

    def setWeight(self, index: int, weight: float, /) -> None:
        """
        Set a weight of the Bezier curve.
        """
        ...

    def getWeight(self, index: int, /) -> float:
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
        If f(t) is the equation of this Bezier curve,
        the parametric tolerance ensures that:
        |t1-t0| < UTolerance =""==> |f(t1)-f(t0)| < Tolerance3D
        """
        ...

# src/Mod/Part/App/Geom2d/Circle2d.pyi:17
class Circle2d(Conic2d):
    """
    Describes a circle in 3D space
    To create a circle there are several ways:
    Part.Geom2d.Circle2d()
        Creates a default circle with center (0,0) and radius 1

    Part.Geom2d.Circle2d(circle)
        Creates a copy of the given circle

    Part.Geom2d.Circle2d(circle, Distance)
        Creates a circle parallel to given circle at a certain distance

    Part.Geom2d.Circle2d(Center,Radius)
        Creates a circle defined by center and radius

    Part.Geom2d.Circle2d(Point1,Point2,Point3)
        Creates a circle defined by three non-linear points

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Radius: float = ...
    'The radius of the circle.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, circle: 'Circle2d') -> None:
        ...

    @overload
    def __init__(self, circle: 'Circle2d', Distance: float) -> None:
        ...

    @overload
    def __init__(self, Center: Tuple[float, float], Radius: float) -> None:
        ...

    @overload
    def __init__(self, Point1: Tuple[float, float], Point2: Tuple[float, float], Point3: Tuple[float, float]) -> None:
        ...

    @overload
    def __init__(self, *args, **kwargs) -> None:
        """
        Describes a circle in 3D space
        To create a circle there are several ways:
        Part.Geom2d.Circle2d()
            Creates a default circle with center (0,0) and radius 1

        Part.Geom2d.Circle2d(circle)
            Creates a copy of the given circle

        Part.Geom2d.Circle2d(circle, Distance)
            Creates a circle parallel to given circle at a certain distance

        Part.Geom2d.Circle2d(Center,Radius)
            Creates a circle defined by center and radius

        Part.Geom2d.Circle2d(Point1,Point2,Point3)
            Creates a circle defined by three non-linear points
        """
        ...

    @staticmethod
    def getCircleCenter() -> Tuple[float, float]:
        """
        Get the circle center defined by three points
        """
        ...

# src/Mod/Part/App/Geom2d/Conic2d.pyi:17
class Conic2d(Curve2d):
    """
    Describes an abstract conic in 2d space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Location: object = ...
    'Location of the conic.'
    Eccentricity: Final[float] = ...
    '\n    returns the eccentricity value of the conic e.\n        e = 0 for a circle\n        0 < e < 1 for an ellipse  (e = 0 if MajorRadius = MinorRadius)\n        e > 1 for a hyperbola\n        e = 1 for a parabola\n    '
    XAxis: object = ...
    'The X axis direction of the circle'
    YAxis: object = ...
    'The Y axis direction of the circle'

# src/Mod/Part/App/Geom2d/Curve2d.pyi:19
class Curve2d(Geometry2d):
    """
    The abstract class Geom2dCurve is the root class of all curve objects.
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Continuity: Final[str] = ...
    'Returns the global continuity of the curve.'
    Closed: Final[bool] = ...
    'Returns true if the curve is closed.'
    Periodic: Final[bool] = ...
    'Returns true if the curve is periodic.'
    FirstParameter: Final[float] = ...
    'Returns the value of the first parameter.'
    LastParameter: Final[float] = ...
    'Returns the value of the last parameter.'

    def reverse(self) -> None:
        """
        Changes the direction of parametrization of the curve.
        """
        ...

    def toShape(self) -> object:
        """
        Return the shape for the geometry.
        """
        ...

    @overload
    def discretize(self, *, Number: int) -> List[Vector]:
        ...

    @overload
    def discretize(self, *, QuasiNumber: int) -> List[Vector]:
        ...

    @overload
    def discretize(self, *, Distance: float) -> List[Vector]:
        ...

    @overload
    def discretize(self, *, Deflection: float) -> List[Vector]:
        ...

    @overload
    def discretize(self, *, QuasiDeflection: float) -> List[Vector]:
        ...

    @overload
    def discretize(self, *, Angular: float, Curvature: float, Minimum: int=2) -> List[Vector]:
        ...

    def discretize(self, **kwargs) -> List[Vector]:
        """
        Discretizes the curve and returns a list of points.
        The function accepts keywords as argument:
        discretize(Number=n) => gives a list of 'n' equidistant points.
        discretize(QuasiNumber=n) => gives a list of 'n' quasi-equidistant points (is faster than the method above).
        discretize(Distance=d) => gives a list of equidistant points with distance 'd'.
        discretize(Deflection=d) => gives a list of points with a maximum deflection 'd' to the curve.
        discretize(QuasiDeflection=d) => gives a list of points with a maximum deflection 'd' to the curve (faster).
        discretize(Angular=a,Curvature=c,[Minimum=m]) => gives a list of points with an angular deflection of 'a'
            and a curvature deflection of 'c'. Optionally a minimum number of points
            can be set, which by default is set to 2.

        Optionally you can set the keywords 'First' and 'Last' to define
            a sub-range of the parameter range of the curve.

        If no keyword is given, then it depends on whether the argument is an int or float.
        If it's an int then the behaviour is as if using the keyword 'Number',
        if it's a float then the behaviour is as if using the keyword 'Distance'.

        Example:

        import Part
        c=PartGeom2d.Circle2d()
        c.Radius=5
        p=c.discretize(Number=50,First=3.14)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)


        p=c.discretize(Angular=0.09,Curvature=0.01,Last=3.14,Minimum=100)
        s=Part.Compound([Part.Vertex(i) for i in p])
        Part.show(s)
        """
        ...

    @overload
    def length(self, /) -> float:
        ...

    @overload
    def length(self, uMin: float, /) -> float:
        ...

    @overload
    def length(self, uMin: float, uMax: float, /) -> float:
        ...

    @overload
    def length(self, uMin: float, uMax: float, Tol: float, /) -> float:
        ...

    def length(self, *args: float) -> float:
        """
        Computes the length of a curve
        length([uMin,uMax,Tol]) -> Float
        """
        ...

    @overload
    def parameterAtDistance(self, abscissa: float, /) -> float:
        ...

    @overload
    def parameterAtDistance(self, abscissa: float, startingParameter: float, /) -> float:
        ...

    def parameterAtDistance(self, *args: float) -> float:
        """
        Returns the parameter on the curve of a point at
        the given distance from a starting parameter.
        parameterAtDistance([abscissa, startingParameter]) -> Float
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

    def parameter(self, point: Vector, /) -> float:
        """
        Returns the parameter on the curve of the
        nearest orthogonal projection of the point.
        """
        ...

    def normal(self, pos: float, /) -> Vector:
        """
        Vector = normal(pos) - Get the normal vector at the given parameter [First|Last] if defined.
        """
        ...

    def curvature(self, pos: float, /) -> float:
        """
        Float = curvature(pos) - Get the curvature at the given parameter [First|Last] if defined.
        """
        ...

    def centerOfCurvature(self, pos: float, /) -> Vector:
        """
        Vector = centerOfCurvature(float pos) - Get the center of curvature at the given parameter [First|Last] if defined.
        """
        ...

    def intersectCC(self, other: 'Curve2d', /) -> List[Vector]:
        """
        Returns all intersection points between this curve and the given curve.
        """
        ...

    @overload
    def toBSpline(self, /) -> BSplineCurve:
        ...

    @overload
    def toBSpline(self, First: float, Last: float, /) -> BSplineCurve:
        ...

    def toBSpline(self, *args: float) -> BSplineCurve:
        """
        Converts a curve of any type (only part from First to Last)
        toBSpline([Float=First, Float=Last]) -> B-Spline curve
        """
        ...

    def approximateBSpline(self, Tolerance: float, MaxSegments: int, MaxDegree: int, Order: str='C2', /) -> BSplineCurve:
        """
        Approximates a curve of any type to a B-Spline curve
        approximateBSpline(Tolerance, MaxSegments, MaxDegree, [Order='C2']) -> B-Spline curve
        """
        ...

# src/Mod/Part/App/Geom2d/Ellipse2d.pyi:17
class Ellipse2d(Conic2d):
    """
    Describes an ellipse in 2D space
    To create an ellipse there are several ways:
    Part.Geom2d.Ellipse2d()
        Creates an ellipse with major radius 2 and minor radius 1 with the
        center in (0,0)

    Part.Geom2d.Ellipse2d(Ellipse)
        Create a copy of the given ellipse

    Part.Geom2d.Ellipse2d(S1,S2,Center)
        Creates an ellipse centered on the point Center,
        its major axis is defined by Center and S1,
        its major radius is the distance between Center and S1, and
        its minor radius is the distance between S2 and the major axis.

    Part.Geom2d.Ellipse2d(Center,MajorRadius,MinorRadius)
        Creates an ellipse with major and minor radii MajorRadius and
        MinorRadius

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    MajorRadius: float = ...
    'The major radius of the ellipse.'
    MinorRadius: float = ...
    'The minor radius of the ellipse.'
    Focal: Final[float] = ...
    'The focal distance of the ellipse.'
    Focus1: Final[object] = ...
    'The first focus is on the positive side of the major axis of the ellipse.'
    Focus2: Final[object] = ...
    'The second focus is on the negative side of the major axis of the ellipse.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, Ellipse: 'Ellipse2d') -> None:
        ...

    @overload
    def __init__(self, S1: object, S2: object, Center: object) -> None:
        ...

    @overload
    def __init__(self, Center: object, MajorRadius: float, MinorRadius: float) -> None:
        ...

    @overload
    def __init__(self, *args, **kwargs) -> None:
        ...

# src/Mod/Part/App/Geom2d/Geometry2d.pyi:16
class Geometry2d:
    """
    The abstract class Geometry for 2D space is the root class of all geometric objects.
    It describes the common behavior of these objects when:
    - applying geometric transformations to objects, and
    - constructing objects by geometric transformation (including copying).

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def mirror(self) -> None:
        """
        Performs the symmetrical transformation of this geometric object.
        """
        ...

    def rotate(self) -> None:
        """
        Rotates this geometric object at angle Ang (in radians) around a point.
        """
        ...

    def scale(self) -> None:
        """
        Applies a scaling transformation on this geometric object with a center and scaling factor.
        """
        ...

    def transform(self) -> None:
        """
        Applies a transformation to this geometric object.
        """
        ...

    def translate(self) -> None:
        """
        Translates this geometric object.
        """
        ...

    def copy(self) -> 'Geometry2d':
        """
        Create a copy of this geometry.
        """
        ...

# src/Mod/Part/App/Geom2d/Hyperbola2d.pyi:17
class Hyperbola2d(Conic2d):
    """
    Describes a hyperbola in 2D space
    To create a hyperbola there are several ways:
    Part.Geom2d.Hyperbola2d()
        Creates a hyperbola with major radius 2 and minor radius 1 with the
        center in (0,0)

    Part.Geom2d.Hyperbola2d(Hyperbola)
        Create a copy of the given hyperbola

    Part.Geom2d.Hyperbola2d(S1,S2,Center)
        Creates a hyperbola centered on the point Center, S1 and S2,
        its major axis is defined by Center and S1,
        its major radius is the distance between Center and S1, and
        its minor radius is the distance between S2 and the major axis.

    Part.Geom2d.Hyperbola2d(Center,MajorRadius,MinorRadius)
        Creates a hyperbola with major and minor radii MajorRadius and
        MinorRadius and located at Center

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    MajorRadius: float = ...
    'The major radius of the hyperbola.'
    MinorRadius: float = ...
    'The minor radius of the hyperbola.'
    Focal: Final[float] = ...
    'The focal distance of the hyperbola.'
    Focus1: Final[object] = ...
    '\n    The first focus is on the positive side of the major axis of the hyperbola;\n    the second focus is on the negative side.\n    '
    Focus2: Final[object] = ...
    '\n    The first focus is on the positive side of the major axis of the hyperbola;\n    the second focus is on the negative side.\n    '

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, Hyperbola: 'Hyperbola2d') -> None:
        ...

    @overload
    def __init__(self, S1: object, S2: object, Center: object) -> None:
        ...

    @overload
    def __init__(self, Center: object, MajorRadius: float, MinorRadius: float) -> None:
        ...

# src/Mod/Part/App/Geom2d/Line2d.pyi:16
class Line2d(Curve2d):
    """
    Describes an infinite line in 2D space
    To create a line there are several ways:
    Part.Geom2d.Line2d()
        Creates a default line.

    Part.Geom2d.Line2d(Line)
        Creates a copy of the given line.

    Part.Geom2d.Line2d(Point,Dir)
        Creates a line that goes through two given points.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Location: object = ...
    'Returns the location of this line.'
    Direction: object = ...
    'Returns the direction of this line.'

# src/Mod/Part/App/Geom2d/Line2dSegment.pyi:17
class Line2dSegment(Curve2d):
    """
    Describes a line segment in 2D space.

    To create a line there are several ways:
    Part.Geom2d.Line2dSegment()
        Creates a default line

    Part.Geom2d.Line2dSegment(Line)
        Creates a copy of the given line

    Part.Geom2d.Line2dSegment(Point1,Point2)
        Creates a line that goes through two given points.
    """
    StartPoint: object = ...
    'Returns the start point of this line segment.'
    EndPoint: object = ...
    'Returns the end point of this line segment.'

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, Line: 'Line2dSegment') -> None:
        ...

    @overload
    def __init__(self, Point1: object, Point2: object) -> None:
        ...

    def setParameterRange(self) -> None:
        """
        Set the parameter range of the underlying line segment geometry.
        """
        ...

# src/Mod/Part/App/Geom2d/OffsetCurve2d.pyi:20
class OffsetCurve2d(Curve2d):
    """
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    OffsetValue: float = ...
    'Sets or gets the offset value to offset the underlying curve.'
    BasisCurve: object = ...
    'Sets or gets the basic curve.'

# src/Mod/Part/App/Geom2d/Parabola2d.pyi:17
class Parabola2d(Conic2d):
    """
    Describes a parabola in 2D space

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    Focal: float = ...
    '\n    The focal distance is the distance between the apex and the focus of the parabola.\n    '
    Focus: Final[object] = ...
    "\n    The focus is on the positive side of the\n    'X Axis' of the local coordinate system of the parabola.\n    "
    Parameter: Final[float] = ...
    '\n    Compute the parameter of this parabola which is the distance between its focus\n    and its directrix. This distance is twice the focal length.\n    '

# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from typing import *

# src/Mod/Part/App/GeomPlate/BuildPlateSurface.pyi:17
class BuildPlateSurface:
    """
    This class provides an algorithm for constructing such a plate surface.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Resets all constraints
        """
        ...

    def setNbBounds(self) -> None:
        """
        Sets the number of bounds
        """
        ...

    def loadInitSurface(self) -> None:
        """
        Loads the initial surface
        """
        ...

    def surfInit(self) -> object:
        """
        Returns the initial surface
        """
        ...

    def surface(self) -> object:
        """
        Returns the plate surface
        """
        ...

    def add(self) -> None:
        """
        Adds a linear or point constraint
        """
        ...

    def perform(self) -> None:
        """
        Calls the algorithm and computes the plate surface
        """
        ...

    def isDone(self) -> bool:
        """
        Tests whether computation of the plate has been completed
        """
        ...

    def sense(self) -> object:
        """
        Returns the orientation of the curves in the array returned by curves2d
        """
        ...

    def order(self) -> int:
        """
        Returns the order of the curves in the array returned by curves2d
        """
        ...

    def curves2d(self) -> List[object]:
        """
        Extracts the array of curves on the plate surface which
        correspond to the curve constraints set in add()
        """
        ...

    def curveConstraint(self) -> object:
        """
        Returns the curve constraint of order
        """
        ...

    def pointConstraint(self) -> object:
        """
        Returns the point constraint of order
        """
        ...

    def disc2dContour(self) -> object:
        """
        Returns the 2D contour of the plate surface
        """
        ...

    def disc3dContour(self) -> object:
        """
        Returns the 3D contour of the plate surface
        """
        ...

    def G0Error(self) -> float:
        """
        Returns the max distance between the result and the constraints
        """
        ...

    def G1Error(self) -> float:
        """
        Returns the max angle between the result and the constraints
        """
        ...

    def G2Error(self) -> float:
        """
        Returns the max difference of curvature between the result and the constraints
        """
        ...

# src/Mod/Part/App/GeomPlate/CurveConstraint.pyi:17
class CurveConstraint:
    """
    Defines curves as constraints to be used to deform a surface

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    NbPoints: int = ...
    '\n    The number of points on the curve used as a\n    constraint. The default setting is 10. This parameter\n    affects computation time, which increases by the cube of\n    the number of points.\n    '
    FirstParameter: Final[float] = ...
    '\n    This function returns the first parameter of the curve.\n    The first parameter is the lowest parametric value for the curve, which defines the starting point of the curve.\n    '
    LastParameter: Final[float] = ...
    '\n    This function returns the last parameter of the curve.\n    The last parameter is the highest parametric value for the curve, which defines the ending point of the curve.\n    '
    Length: Final[float] = ...
    '\n    This function returns the length of the curve.\n    The length of the curve is a geometric property that indicates how long the curve is in the space.\n    '

    def setOrder(self) -> None:
        """
        Allows you to set the order of continuity required for the constraints: G0, G1, and G2, controlled
        respectively by G0Criterion G1Criterion and G2Criterion.
        """
        ...

    def order(self) -> None:
        """
        Returns the order of constraint, one of G0, G1 or G2
        """
        ...

    def G0Criterion(self) -> None:
        """
        Returns the G0 criterion at the parametric point U on the curve.
        This is the greatest distance allowed between the constraint and the target surface at U.
        """
        ...

    def G1Criterion(self) -> None:
        """
        Returns the G1 criterion at the parametric point U on the curve.
        This is the greatest angle allowed between the constraint and the target surface at U.
        Raises an exception if the curve is not on a surface.
        """
        ...

    def G2Criterion(self) -> None:
        """
        Returns the G2 criterion at the parametric point U on the curve.
        This is the greatest difference in curvature allowed between the constraint and the target surface at U.
        Raises an exception if the curve is not on a surface.
        """
        ...

    def setG0Criterion(self) -> None:
        """
        Allows you to set the G0 criterion. This is the law
        defining the greatest distance allowed between the
        constraint and the target surface for each point of the
        constraint. If this criterion is not set, TolDist, the
        distance tolerance from the constructor, is used.
        """
        ...

    def setG1Criterion(self) -> None:
        """
        Allows you to set the G1 criterion. This is the law
        defining the greatest angle allowed between the
        constraint and the target surface. If this criterion is not
        set, TolAng, the angular tolerance from the constructor, is used.
        Raises an exception if the curve is not on a surface.
        """
        ...

    def setG2Criterion(self) -> None:
        """
        Allows you to set the G2 criterion. This is the law
        defining the greatest difference in curvature allowed
        between the constraint and the target surface. If this
        criterion is not set, TolCurv, the curvature tolerance from
        the constructor, is used.
        Raises ConstructionError if the point is not on the surface.
        """
        ...

    def curve3d(self) -> None:
        """
        Returns a 3d curve associated the surface resulting of the constraints
        """
        ...

    def setCurve2dOnSurf(self) -> None:
        """
        Loads a 2d curve associated the surface resulting of the constraints
        """
        ...

    def curve2dOnSurf(self) -> None:
        """
        Returns a 2d curve associated the surface resulting of the constraints
        """
        ...

    def setProjectedCurve(self) -> None:
        """
        Loads a 2d curve  resulting from the normal projection of
        the curve on the initial surface
        """
        ...

    def projectedCurve(self) -> None:
        """
        Returns the projected curve resulting from the normal projection of the
        curve on the initial surface
        """
        ...

# src/Mod/Part/App/GeomPlate/PointConstraint.pyi:17
class PointConstraint:
    """
    Defines points as constraints to be used to deform a surface

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def setOrder(self, order: str, /) -> None:
        """
        Allows you to set the order of continuity required for
        the constraints: G0, G1, and G2, controlled
        respectively by G0Criterion G1Criterion and G2Criterion.
        """
        ...

    def order(self) -> str:
        """
        Returns the order of constraint, one of G0, G1 or G2
        """
        ...

    def G0Criterion(self, U: float, /) -> float:
        """
        Returns the G0 criterion at the parametric point U on
        the curve. This is the greatest distance allowed between
        the constraint and the target surface at U.
        """
        ...

    def G1Criterion(self, U: float, /) -> float:
        """
        Returns the G1 criterion at the parametric point U on
        the curve. This is the greatest angle allowed between
        the constraint and the target surface at U.
        Raises an exception if  the  curve  is  not  on  a  surface.
        """
        ...

    def G2Criterion(self, U: float, /) -> float:
        """
        Returns the G2 criterion at the parametric point U on
        the curve. This is the greatest difference in curvature
        allowed between the constraint and the target surface at U.
        Raises an exception if  the  curve  is  not  on  a  surface.
        """
        ...

    def setG0Criterion(self, value: float, /) -> None:
        """
        Allows you to set the G0 criterion. This is the law
        defining the greatest distance allowed between the
        constraint and the target surface for each point of the
        constraint. If this criterion is not set, TolDist, the
        distance tolerance from the constructor, is used.
        """
        ...

    def setG1Criterion(self, value: float, /) -> None:
        """
        Allows you to set the G1 criterion. This is the law
        defining the greatest angle allowed between the
        constraint and the target surface. If this criterion is not
        set, TolAng, the angular tolerance from the constructor, is used.
        Raises an exception if  the  curve  is  not  on  a  surface
        """
        ...

    def setG2Criterion(self, value: float, /) -> None:
        """
        Allows you to set the G2 criterion. This is the law
        defining the greatest difference in curvature  allowed between the
        constraint and the target surface. If this criterion is not
        set, TolCurv, the curvature tolerance from the constructor, is used.
        Raises  ConstructionError if  the  curve  is  not  on  a  surface
        """
        ...

    def hasPnt2dOnSurf(self) -> bool:
        """
        Checks if there is a 2D point associated with the surface. It returns a boolean indicating whether such a point exists.
        """
        ...

    def setPnt2dOnSurf(self, x: float, y: float, /) -> None:
        """
        Allows you to set a 2D point on the surface. It takes a gp_Pnt2d as an argument, representing the 2D point to be associated with the surface.
        """
        ...

    def pnt2dOnSurf(self) -> Tuple[float, float]:
        """
        Returns the 2D point on the surface. It returns a gp_Pnt2d representing the associated 2D point.
        """
        ...

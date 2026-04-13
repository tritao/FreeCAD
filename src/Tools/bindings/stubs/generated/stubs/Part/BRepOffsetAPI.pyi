# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from Part import Shape as TopoShape
from Part import Face as TopoShapeFace
from Part import Edge as TopoShapeEdge
from Part import Point
from FreeCAD.Base import Vector

from typing import *

# src/Mod/Part/App/BRepOffsetAPI_MakeFilling.pyi:19
class MakeFilling:
    """
    N-Side Filling

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """

    def setConstrParam(self, *, Tol2d: float=1e-05, Tol3d: float=0.0001, TolAng: float=0.01, TolCurv: float=0.1) -> None:
        """
        setConstrParam(Tol2d=0.00001, Tol3d=0.0001, TolAng=0.01, TolCurv=0.1)
        Sets the values of Tolerances used to control the constraint.
        """
        ...

    def setResolParam(self, *, Degree: int=3, NbPtsOnCur: int=15, NbIter: int=2, Anisotropy: bool=False) -> None:
        """
        setResolParam(Degree=3, NbPtsOnCur=15, NbIter=2, Anisotropy=False)
        Sets the parameters used for resolution.
        """
        ...

    def setApproxParam(self, *, MaxDeg: int=8, MaxSegments: int=9) -> None:
        """
        setApproxParam(MaxDeg=8, MaxSegments=9)
        Sets the parameters used to approximate the filling the surface
        """
        ...

    def loadInitSurface(self, face: TopoShapeFace, /) -> None:
        """
        loadInitSurface(face)
        Loads the initial surface.
        """
        ...

    @overload
    def add(self, Edge: TopoShapeEdge, Order: int, *, IsBound: bool=True) -> None:
        ...

    @overload
    def add(self, Edge: TopoShapeEdge, Support: TopoShapeFace, Order: int, *, IsBound: bool=True) -> None:
        ...

    @overload
    def add(self, Support: TopoShapeFace, Order: int) -> None:
        ...

    @overload
    def add(self, Point: Point) -> None:
        ...

    @overload
    def add(self, U: float, V: float, Support: TopoShapeFace, Order: int) -> None:
        ...

    def add(self, **kwargs) -> None:
        """
        add(Edge, Order, IsBound=True)
        add(Edge, Support, Order, IsBound=True)
        add(Support, Order)
        add(Point)
        add(U, V, Support, Order)
        Adds a new constraint.
        """
        ...

    def build(self) -> None:
        """
        Builds the resulting faces.
        """
        ...

    def isDone(self) -> bool:
        """
        Tests whether computation of the filling plate has been completed.
        """
        ...

    @overload
    def G0Error(self, /) -> float:
        ...

    @overload
    def G0Error(self, arg: int, /) -> float:
        ...

    def G0Error(self, arg: int=0, /) -> float:
        """
        G0Error([int])
        Returns the maximum distance between the result and the constraints.
        """
        ...

    @overload
    def G1Error(self, /) -> float:
        ...

    @overload
    def G1Error(self, arg: int, /) -> float:
        ...

    def G1Error(self, arg: int=0, /) -> float:
        """
        G1Error([int])
        Returns the maximum angle between the result and the constraints.
        """
        ...

    @overload
    def G2Error(self, /) -> float:
        ...

    @overload
    def G2Error(self, arg: int, /) -> float:
        ...

    def G2Error(self, arg: int=0, /) -> float:
        """
        G2Error([int])
        Returns the greatest difference in curvature between the result and the constraints.
        """
        ...

    def shape(self) -> TopoShape:
        """
        shape()
        Returns the resulting shape.
        """
        ...

# src/Mod/Part/App/BRepOffsetAPI_MakePipeShell.pyi:17
class MakePipeShell:
    """
    Low level API to create a PipeShell using OCC API

    Ref: https://dev.opencascade.org/doc/refman/html/class_b_rep_offset_a_p_i___make_pipe_shell.html

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """

    def setFrenetMode(self, mode: bool, /) -> None:
        """
        setFrenetMode(True|False)
        Sets a Frenet or a CorrectedFrenet trihedron to perform the sweeping.
        True  = Frenet
        False = CorrectedFrenet
        """
        ...

    def setTrihedronMode(self, point: Vector, direction: Vector, /) -> None:
        """
        setTrihedronMode(point,direction)
        Sets a fixed trihedron to perform the sweeping.
        All sections will be parallel.
        """
        ...

    def setBiNormalMode(self, direction: Vector, /) -> None:
        """
        setBiNormalMode(direction)
        Sets a fixed BiNormal direction to perform the sweeping.
        Angular relations between the section(s) and the BiNormal direction will be constant.
        """
        ...

    def setSpineSupport(self, shape: TopoShape, /) -> None:
        """
        setSpineSupport(shape)
        Sets support to the spine to define the BiNormal of the trihedron, like the normal to the surfaces.
        Warning: To be effective, Each edge of the spine must have an representation on one face of SpineSupport.
        """
        ...

    def setAuxiliarySpine(self, wire: TopoShape, CurvilinearEquivalence: bool, TypeOfContact: int, /) -> None:
        """
        setAuxiliarySpine(wire, CurvilinearEquivalence, TypeOfContact)
        Sets an auxiliary spine to define the Normal.

        CurvilinearEquivalence = bool
        For each Point of the Spine P, an Point Q is evalued on AuxiliarySpine.
        If CurvilinearEquivalence=True Q split AuxiliarySpine with the same length ratio than P split Spine.

        * OCC >= 6.7
        TypeOfContact = long
        0: No contact
        1: Contact
        2: Contact On Border (The auxiliary spine becomes a boundary of the swept surface)
        """
        ...

    @overload
    def add(self, Profile: TopoShape, *, WithContact: bool=False, WithCorrection: bool=False) -> None:
        ...

    @overload
    def add(self, Profile: TopoShape, Location: TopoShape, *, WithContact: bool=False, WithCorrection: bool=False) -> None:
        ...

    def add(self, **kwargs) -> None:
        """
        add(shape Profile, bool WithContact=False, bool WithCorrection=False)
        add(shape Profile, vertex Location, bool WithContact=False, bool WithCorrection=False)
        Adds the section Profile to this framework.
        First and last sections may be punctual, so the shape Profile may be both wire and vertex.
        If WithContact is true, the section is translated to be in contact with the spine.
        If WithCorrection is true, the section is rotated to be orthogonal to the spine tangent in the correspondent point.
        """
        ...

    def remove(self, Profile: TopoShape, /) -> None:
        """
        remove(shape Profile)
        Removes the section Profile from this framework.
        """
        ...

    def isReady(self) -> bool:
        """
        isReady()
        Returns true if this tool object is ready to build the shape.
        """
        ...

    def getStatus(self) -> int:
        """
        getStatus()
        Get a status, when Simulate or Build failed.
        """
        ...

    def makeSolid(self) -> bool:
        """
        makeSolid()
        Transforms the sweeping Shell in Solid. If a propfile is not closed returns False.
        """
        ...

    def setTolerance(self, tol3d: float, boundTol: float, tolAngular: float, /) -> None:
        """
        setTolerance( tol3d, boundTol, tolAngular)
        Tol3d = 3D tolerance
        BoundTol = boundary tolerance
        TolAngular = angular tolerance
        """
        ...

    def setTransitionMode(self, mode: int, /) -> None:
        """
        0: BRepBuilderAPI_Transformed
        1: BRepBuilderAPI_RightCorner
        2: BRepBuilderAPI_RoundCorner
        """
        ...

    def firstShape(self) -> TopoShape:
        """
        firstShape()
        Returns the Shape of the bottom of the sweep.
        """
        ...

    def lastShape(self) -> TopoShape:
        """
        lastShape()
        Returns the Shape of the top of the sweep.
        """
        ...

    def build(self) -> None:
        """
        build()
        Builds the resulting shape.
        """
        ...

    def shape(self) -> TopoShape:
        """
        shape()
        Returns the resulting shape.
        """
        ...

    def generated(self, S: TopoShape, /) -> list[TopoShape]:
        """
        generated(shape S)
        Returns a list of new shapes generated from the shape S by the shell-generating algorithm.
        """
        ...

    def setMaxDegree(self, degree: int, /) -> None:
        """
        setMaxDegree(int degree)
        Define the maximum V degree of resulting surface.
        """
        ...

    def setMaxSegments(self, num: int, /) -> None:
        """
        setMaxSegments(int num)
        Define the maximum number of spans in V-direction on resulting surface.
        """
        ...

    def setForceApproxC1(self, flag: bool, /) -> None:
        """
        setForceApproxC1(bool)
        Set the flag that indicates attempt to approximate a C1-continuous surface if a swept surface proved to be C0.
        """
        ...

    def simulate(self, nbsec: int, /) -> None:
        """
        simulate(int nbsec)
        Simulates the resulting shape by calculating the given number of cross-sections.
        """
        ...

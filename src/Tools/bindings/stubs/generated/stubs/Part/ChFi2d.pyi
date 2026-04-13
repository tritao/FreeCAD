# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import Vector

from typing import *

# src/Mod/Part/App/ChFi2d/ChFi2d_AnaFilletAlgo.pyi:18
class AnaFilletAlgo:
    """
    An analytical algorithm for calculation of the fillets.
    It is implemented for segments and arcs of circle only.
    """

    def init(self) -> None:
        """
        Initializes a fillet algorithm: accepts a wire consisting of two edges in a plane
        """
        ...

    def perform(self, radius: float, /) -> bool:
        """
        perform(radius) -> bool

        Constructs a fillet edge
        """
        ...

    def result(self) -> Tuple[PyObjectBase, PyObjectBase, PyObjectBase]:
        """
        result()

        Returns result (fillet edge, modified edge1, modified edge2)
        """
        ...

# src/Mod/Part/App/ChFi2d/ChFi2d_ChamferAPI.pyi:18
class ChamferAPI:
    """
    Algorithm that creates a chamfer between two linear edges

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes a chamfer algorithm: accepts a wire consisting of two edges in a plane
        """
        ...

    def perform(self, radius: float, /) -> bool:
        """
        perform(radius) -> bool

        Constructs a chamfer edge
        """
        ...

    def result(self, point: object, solution: int=-1, /) -> Tuple[object, object, object]:
        """
        result(point, solution=-1)

        Returns result (chamfer edge, modified edge1, modified edge2)
        """
        ...

# src/Mod/Part/App/ChFi2d/ChFi2d_FilletAPI.pyi:18
class FilletAPI:
    """
    Algorithm that creates fillet edge

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes a fillet algorithm: accepts a wire consisting of two edges in a plane
        """
        ...

    def perform(self, radius: float, /) -> bool:
        """
        perform(radius) -> bool

        Constructs a fillet edge
        """
        ...

    def numberOfResults(self) -> int:
        """
        Returns number of possible solutions
        """
        ...

    def result(self, point: Point, solution: int=-1, /) -> tuple[TopoShapeEdge, TopoShapeEdge, TopoShapeEdge]:
        """
        result(point, solution=-1)

        Returns result (fillet edge, modified edge1, modified edge2)
        """
        ...

# src/Mod/Part/App/ChFi2d/ChFi2d_FilletAlgo.pyi:18
class FilletAlgo:
    """
    Algorithm that creates fillet edge

    Author: Werner Mayer (wmayer[at]users.sourceforge.net)
    Licence: LGPL
    """

    def init(self) -> None:
        """
        Initializes a fillet algorithm: accepts a wire consisting of two edges in a plane
        """
        ...

    def perform(self, radius: float, /) -> bool:
        """
        perform(radius) -> bool

        Constructs a fillet edge
        """
        ...

    def numberOfResults(self) -> int:
        """
        Returns number of possible solutions
        """
        ...

    def result(self, point: Vector, solution: int=-1, /) -> tuple[object, object, object]:
        """
        result(point, solution=-1)

        Returns result (fillet edge, modified edge1, modified edge2)
        """
        ...

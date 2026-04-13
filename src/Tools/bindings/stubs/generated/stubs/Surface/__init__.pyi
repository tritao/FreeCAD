# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from typing import *

# src/Mod/Surface/App/Blending/BlendCurve.pyi:16
class BlendCurve:
    """
    Create a BlendCurve that interpolate 2 BlendPoints.
        curve = BlendCurve(BlendPoint1, BlendPoint2)

    Author: Mattéo Grellier (matteogrellier@gmail.com)
    License: LGPL-2.1-or-later
    """

    def compute(self) -> Any:
        """
        Return the BezierCurve that interpolate the input BlendPoints.
        """
        ...

    def setSize(self) -> Any:
        """
        Set the tangent size of the blendpoint at given index.
        If relative is true, the size is considered relative to the distance between the two blendpoints.
        myBlendCurve.setSize(idx, size, relative)
        """
        ...

# src/Mod/Surface/App/Blending/BlendPoint.pyi:16
class BlendPoint:
    """
    Create BlendPoint from a point and some derivatives.
    myBlendPoint = BlendPoint([Point, D1, D2, ..., DN])
    BlendPoint can also be constructed from an edge
    myBlendPoint = BlendPoint(Edge, parameter = float, continuity = int)

    Author: Mattéo Grellier (matteogrellier@gmail.com)
    License: LGPL-2.1-or-later
    """

    def getSize(self) -> Any:
        """Return BlendPoint first derivative length."""
        ...

    def setSize(self) -> Any:
        """
        Resizes the BlendPoint vectors,
        by setting the length of the first derivative.
        theBlendPoint.setSize(new_size)
        """
        ...

    def setvectors(self) -> Any:
        """
        Set the vectors of BlendPoint.
        BlendPoint.setvectors([Point, D1, D2, ..., DN])
        """
        ...
    Vectors: Final[list]
    'The list of vectors of this BlendPoint.'

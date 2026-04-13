# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import BaseClass
from FreeCAD.Base import Vector

from typing import *

# src/Mod/CAM/App/Voronoi.pyi:16
class Diagram(BaseClass):
    """
    Voronoi([segments]): Create voronoi for given collection of line segments

    Author: sliptonic (shopinthewoods@gmail.com)
    License: LGPL-2.1-or-later
    """

    def numCells(self) -> Any:
        """Return number of cells"""
        ...

    def numEdges(self) -> Any:
        """Return number of edges"""
        ...

    def numVertices(self) -> Any:
        """Return number of vertices"""
        ...

    def addPoint(self, point: Vector, /) -> None:
        """add given point to input collection"""
        ...

    def addSegment(self, point1: Vector, point2: Vector, /) -> Any:
        """add given segment to input collection"""
        ...

    def construct(self) -> Any:
        """constructs the voronoi diagram from the input collections"""
        ...

    def colorExterior(self) -> Any:
        """assign given color to all exterior edges and vertices"""
        ...

    def colorTwins(self) -> Any:
        """assign given color to all twins of edges (which one is considered a twin is arbitrary)"""
        ...

    def colorColinear(self) -> Any:
        """assign given color to all edges sourced by two segments almost in line with each other (optional angle in degrees)"""
        ...

    def resetColor(self) -> Any:
        """assign color 0 to all elements with the given color"""
        ...

    def getPoints(self) -> Any:
        """Get list of all input points."""
        ...

    def numPoints(self) -> Any:
        """Return number of input points"""
        ...

    def getSegments(self) -> Any:
        """Get list of all input segments."""
        ...

    def numSegments(self) -> Any:
        """Return number of input segments"""
        ...
    Cells: Final[list]
    'List of all cells of the voronoi diagram'
    Edges: Final[list]
    'List of all edges of the voronoi diagram'
    Vertices: Final[list]
    'List of all vertices of the voronoi diagram'

# src/Mod/CAM/App/VoronoiCell.pyi:15
class Cell(BaseClass):
    """
    Cell of a Voronoi diagram

    Author: sliptonic (shopinthewoods@gmail.com)
    License: LGPL-2.1-or-later
    """

    def containsPoint(self) -> Any:
        """Returns true if the cell contains a point site"""
        ...

    def containsSegment(self) -> Any:
        """Returns true if the cell contains a segment site"""
        ...

    def isDegenerate(self) -> Any:
        """Returns true if the cell doesn't have an incident edge"""
        ...

    def getSource(self) -> Any:
        """Returns the Source for the cell"""
        ...
    Index: Final[int]
    'Internal id of the element.'
    Color: int
    'Assigned color of the receiver.'
    SourceIndex: Final[int]
    "Returns the index of the cell's source"
    SourceCategory: Final[int]
    "Returns the cell's category as an integer"
    SourceCategoryName: Final[str]
    "Returns the cell's category as a string"
    IncidentEdge: Final[Any]
    'Incident edge of the cell - if exists'

# src/Mod/CAM/App/VoronoiEdge.pyi:15
class Edge(BaseClass):
    """
    Edge of a Voronoi diagram

    Author: sliptonic (shopinthewoods@gmail.com)
    License: LGPL-2.1-or-later
    """

    def isFinite(self) -> Any:
        """Returns true if both vertices are finite"""
        ...

    def isInfinite(self) -> Any:
        """Returns true if the end vertex is infinite"""
        ...

    def isLinear(self) -> Any:
        """Returns true if edge is straight"""
        ...

    def isCurved(self) -> Any:
        """Returns true if edge is curved"""
        ...

    def isPrimary(self) -> Any:
        """Returns false if edge goes through endpoint of the segment site"""
        ...

    def isSecondary(self) -> Any:
        """Returns true if edge goes through endpoint of the segment site"""
        ...

    def isBorderline(self) -> Any:
        """Returns true if the point is on the segment"""
        ...

    def toShape(self) -> Any:
        """Returns a shape for the edge"""
        ...

    def getDistances(self) -> Any:
        """Returns the distance of the vertices to the input source"""
        ...

    def getSegmentAngle(self) -> Any:
        """Returns the angle (in degree) of the segments if the edge was formed by two segments"""
        ...
    Index: Final[int]
    'Internal id of the element.'
    Color: int
    'Assigned color of the receiver.'
    Cell: Final[Any]
    'cell the edge belongs to'
    Vertices: Final[list]
    'Begin and End voronoi vertex'
    Next: Final[Any]
    'CCW next edge within voronoi cell'
    Prev: Final[Any]
    'CCW previous edge within voronoi cell'
    RotNext: Final[Any]
    'Rotated CCW next edge within voronoi cell'
    RotPrev: Final[Any]
    'Rotated CCW previous edge within voronoi cell'
    Twin: Final[Any]
    'Twin edge'

# src/Mod/CAM/App/VoronoiVertex.pyi:15
class Vertex(BaseClass):
    """
    Vertex of a Voronoi diagram

    Author: sliptonic (shopinthewoods@gmail.com)
    License: LGPL-2.1-or-later
    """

    def toPoint(self) -> Any:
        """Returns a Vector - or None if not possible"""
        ...
    Index: Final[int]
    'Internal id of the element.'
    Color: int
    'Assigned color of the receiver.'
    X: Final[float]
    'X position'
    Y: Final[float]
    'Y position'
    IncidentEdge: Final[Any]
    'Y position'

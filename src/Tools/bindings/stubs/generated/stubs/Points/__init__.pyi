# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def open(*args: Any) -> Any: ...
def insert(*args: Any) -> Any: ...
def export(*args: Any) -> Any: ...
def show(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from typing import *

# src/Mod/Points/App/Points.pyi:20
class Points(object):
    """
    Points() -- Create an empty points object.

    This class allows one to manipulate the Points object by adding new points, deleting facets, importing from an STL file,
    transforming and much more.

    Author: Juergen Riegel (Juergen.Riegel@web.de)
    License: LGPL-2.1-or-later
    """

    def copy(self) -> Any:
        """Create a copy of this points object"""
        ...

    def read(self) -> Any:
        """Read in a points object from file."""
        ...

    def write(self) -> Any:
        """Write the points object into file."""
        ...

    def writeInventor(self) -> Any:
        """Write the points in OpenInventor format to a string."""
        ...

    def addPoints(self) -> Any:
        """add one or more (list of) points to the object"""
        ...

    def fromSegment(self) -> Any:
        """Get a new point object from a given segment"""
        ...

    def fromValid(self) -> Any:
        """Get a new point object from points with valid coordinates (i.e. that are not NaN)"""
        ...
    CountPoints: Final[int]
    'Return the number of vertices of the points object.'
    Points: Final[list]
    'A collection of points\nWith this attribute it is possible to get access to the points of the object\n\nfor p in pnt.Points:\n\tprint p'

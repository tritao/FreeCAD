# This is a generated inventory skeleton. Refine signatures before publishing.
from __future__ import annotations
from typing import Any

def getLocatedTopoShape(*args: Any) -> Any: ...

# Generated public class stubs from binding .pyi specs.
from FreeCAD import DocumentObject
from FreeCAD.Base import BaseClass

from typing import *

# src/Mod/Measure/App/MeasureBase.pyi:14
class MeasureBase(DocumentObject):
    """
    User documentation here

    Author: David Friedli(hlorus) (david@friedli-be.ch)
    License: LGPL-2.1-or-later
    """

# src/Mod/Measure/App/Measurement.pyi:15
class Measurement(BaseClass):
    """
    Make a measurement

    Author: Luke Parry (l.parry@warwick.ac.uk)
    License: LGPL-2.1-or-later
    """

    def addReference3D(self) -> Any:
        """add a geometric reference"""
        ...

    def has3DReferences(self) -> Any:
        """does Measurement have links to 3D geometry"""
        ...

    def clear(self) -> Any:
        """measure the difference between references to obtain resultant vector"""
        ...

    def delta(self) -> Any:
        """measure the difference between references to obtain resultant vector"""
        ...

    def length(self) -> Any:
        """measure the length of the references"""
        ...

    def volume(self) -> Any:
        """measure the volume of the references"""
        ...

    def area(self) -> Any:
        """measure the area of the references"""
        ...

    def lineLineDistance(self) -> Any:
        """measure the line-Line Distance of the references. Returns 0 if references are not 2 lines."""
        ...

    def planePlaneDistance(self) -> Any:
        """measure the plane-plane distance of the references. Returns 0 if references are not 2 planes."""
        ...

    def angle(self) -> Any:
        """measure the angle between two edges"""
        ...

    def radius(self) -> Any:
        """measure the radius of an arc or circle edge"""
        ...

    def com(self) -> Any:
        """measure the center of mass for selected volumes"""
        ...

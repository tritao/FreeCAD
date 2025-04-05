from Metadata import export, constmethod
from typing import overload, Final
from Base.Vector import Vector
from DrawView import DrawView

@export(
    Father="DrawView",
    Twin="DrawViewDimension",
    TwinPointer="DrawViewDimension",
    Include="Mod/TechDraw/App/DrawViewDimension.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw"
)
class DrawViewDimension(DrawView):
    """
    Feature for creating and manipulating Technical Drawing Dimensions

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """

    def getRawValue(self) -> float:
        """
        getRawValue() - returns Dimension value in mm.
        """
        ...

    def getText(self) -> str:
        """
        getText() - returns Dimension text.
        """
        ...

    def getLinearPoints(self) -> list[Vector]:
        """
        getLinearPoints() - returns list of points for linear Dimension
        """
        ...

    def getArcPoints(self) -> list[Vector]:
        """
        getArcPoints() - returns list of points for circle/arc Dimension
        """
        ...

    def getAnglePoints(self) -> list[Vector]:
        """
        getAnglePoints() - returns list of points for angle Dimension
        """
        ...

    def getAreaPoints(self) -> tuple[Vector, float, float]:
        """
        getAreaPoints() - returns list of values (center, filled area, actual area) for area Dimension.
        """
        ...

    def getArrowPositions(self) -> list[Vector]:
        """
        getArrowPositions() - returns list of locations or Dimension Arrowheads. Locations are in unscaled coordinates of parent View 
        """
        ...
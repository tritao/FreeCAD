from Base.Metadata import export, constmethod
from typing import Final, overload
from DrawTemplate import DrawTemplate

@export(
    Father="DrawTemplate",
    Name="DrawParametricTemplate",
    Twin="DrawParametricTemplate",
    TwinPointer="DrawParametricTemplate",
    Include="Mod/TechDraw/App/DrawParametricTemplate.h",
    Namespace="TechDraw",
    FatherInclude="DrawTemplate.h",
    FatherNamespace="TechDraw",
)
class DrawParametricTemplate(DrawTemplate):
    """
    Feature for creating and manipulating Technical Drawing Templates
    Author: Luke Parry (l.parry@warwick.ac.uk)
    Licence: LGPL
    """

    GeometryCount: Final[int] = 0
    """Number of geometry in template"""

    def drawLine(self) -> None:
        """
        Draw a line
        """
        ...
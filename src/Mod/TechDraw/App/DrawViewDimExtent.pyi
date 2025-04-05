from Base.Metadata import export
from typing import Final

@export(
    Father="DrawViewDimension",
    Name="DrawViewDimExtent",
    Twin="DrawViewDimExtent",
    TwinPointer="DrawViewDimExtent",
    Include="Mod/TechDraw/App/DrawViewDimExtent.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewDimensionPy.h",
    FatherNamespace="TechDraw",
)
class DrawViewDimExtent(DrawViewDimension):
    """
    Feature for creating and manipulating Technical Drawing DimExtents
    Author: WandererFan (wandererfan@gmail.com) Licence: LGPL
    """

    def tbd(self) -> None:
        """
        tbd() - returns tbd.
        """
        ...
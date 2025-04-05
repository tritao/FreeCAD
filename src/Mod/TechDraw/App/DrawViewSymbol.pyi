from Metadata import export, constmethod
from typing import Final


@export(
    Father="DrawView",
    Name="DrawViewSymbol",
    Twin="DrawViewSymbol",
    TwinPointer="DrawViewSymbol",
    Include="Mod/TechDraw/App/DrawViewSymbol.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawView.h",
    FatherNamespace="TechDraw",
)
class DrawViewSymbol(DrawView):
    """
    Feature for creating and manipulating Drawing SVG Symbol Views

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """

    @constmethod
    def dumpSymbol(self, fileSpec: str) -> None:
        """
        dumpSymbol(fileSpec) - dump the contents of Symbol to a file
        """
        ...
from Base.Metadata import export, constmethod
from TechDraw.DrawViewPart import DrawViewPart

@export(
    Twin="DrawProjGroupItem",
    TwinPointer="DrawProjGroupItem",
    Include="Mod/TechDraw/App/DrawProjGroupItem.h",
    Namespace="TechDraw",
    Father="DrawViewPart",
    FatherInclude="Mod/TechDraw/App/DrawViewPartPy.h",
    FatherNamespace="TechDraw",
)
class DrawProjGroupItem(DrawViewPart):
    """
    Feature for creating and manipulating component Views Technical Drawing Projection Groups

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """

    def autoPosition(self) -> None:
        """
        autoPosition() - Move to AutoDistribute/Unlocked position on Page. Returns none.
        """
        ...
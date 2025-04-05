from Base.Metadata import export
from typing import List

from DrawView import DrawView

@export(
    Father="DrawView",
    Name="DrawViewClip",
    Twin="DrawViewClip",
    TwinPointer="DrawViewClip",
    Include="Mod/TechDraw/App/DrawViewClip.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw",
)
class DrawViewClip(DrawView):
    """
      Feature for creating and manipulating Technical Drawing Clip Views
      Author: WandererFan (LGPL, wandererfan@gmail.com)
    """

    def addView(self, view: DrawView) -> None:
        """
        addView(DrawView) - Add a View to this ClipView
        """
        ...

    def removeView(self, view: DrawView) -> None:
        """
        removeView(DrawView) - Remove specified View to this ClipView
        """
        ...

    def getChildViewNames(self) -> List[str]:
        """
        getChildViewNames() - get a list of the DrawViews in this ClipView
        """
        ...
from Metadata import export
from typing import Final

@export(
    Father="DrawViewPy",
    Name="DrawViewCollectionPy",
    Twin="DrawViewCollection",
    TwinPointer="DrawViewCollection",
    Include="Mod/TechDraw/App/DrawViewCollection.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw",
)
class DrawViewCollection(DrawView):
    """
      <Documentation>
      <Author Licence="LGPL" Name="WandererFan" EMail="wandererfan@gmail.com" />
      <UserDocu>Feature for creating and manipulating Technical Drawing View Collections</UserDocu>
    </Documentation>
    """

    def addView(self, view: "DrawView") -> int:
        """
        addView(DrawView object) - Add a new View to this Group. Returns count of views.
        """
        ...

    def removeView(self, view: "DrawView") -> int:
        """
        removeView(DrawView object) - Remove specified Viewfrom this Group. Returns count of views in Group.
        """
        ...
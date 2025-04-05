from Base.Metadata import export, constmethod
from typing import Final
from TechDraw.DrawViewCollection import DrawViewCollection
from App.DocumentObject import DocumentObject
from Base.CoordinateSystem import CoordinateSystem


@export(
    Father="DrawViewCollection",
    Twin="DrawProjGroup",
    TwinPointer="DrawProjGroup",
    Include="Mod/TechDraw/App/DrawProjGroup.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewCollectionPy.h",
    FatherNamespace="TechDraw"
)
class DrawProjGroup(DrawViewCollection):
    """
    DrawProjGroup class.

    Feature for creating and manipulating Technical Drawing Projection Groups

    Author: WandererFan (wandererfan@gmail.com)
    Licence: LGPL
    """

    @constmethod
    def addProjection(self, projectionType: str) -> DocumentObject:
        """
        addProjection(string projectionType) - Add a new Projection Item to this Group. Returns DocObj.
        """
        ...

    def removeProjection(self, projectionType: str) -> int:
        """
        removeProjection(string projectionType) - Remove specified Projection Item from this Group. Returns int number of views in Group.
        """
        ...

    def purgeProjections(self) -> int:
        """
        purgeProjections() - Remove all Projection Items from this Group. Returns int number of views in Group (0).
        """
        ...

    def getItemByLabel(self, projectionType: str) -> DocumentObject:
        """
        getItemByLabel(string projectionType) - return specified Projection Item
        """
        ...

    def getXYPosition(self, projectionType: str) -> CoordinateSystem:
        """
        getXYPosition(string projectionType) - return the AutoDistribute position for specified Projection Item
        """
        ...
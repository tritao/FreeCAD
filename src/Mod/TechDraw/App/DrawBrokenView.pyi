from Base.Metadata import export, constmethod
from TechDraw.DrawViewPart import DrawViewPart
from Base.Vector import Vector
from typing import Final

@export(
    Father="DrawViewPart",
    Twin="DrawBrokenView",
    TwinPointer="DrawBrokenView",
    Include="Mod/TechDraw/App/DrawBrokenView.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPartPy.h",
    FatherNamespace="TechDraw"
)
class DrawBrokenView(DrawViewPart):
    """
    Author: WandererFan, Licence: LGPL, EMail: wandererfan@gmail.com
    Feature for creating and manipulating Technical Drawing broken views
    """

    def mapPoint3dToView(self, point3d: Vector) -> Vector:
        """
        point2d = mapPoint3dToView(point3d) - returns the position of the 3d point within the broken view.
        """
        ...

    def mapPoint2dFromView(self, point3d: Vector) -> Vector:
        """
        point2d = mapPoint2dFromView(point3d) - returns the position of the 2d point within an unbroken view.
        """
        ...

    def getCompressedCenter(self) -> Vector:
        """
        point3d = getCompressedCenter() - returns the geometric center of the source shapes after break cuts and gap compression.
        """
        ...
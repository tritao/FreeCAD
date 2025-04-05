from Base.Metadata import export
from typing import Final
from Base.Vector import Vector
from App.PyObjectBase import PyObjectBase as ObjectBase

@export(
    Father="PyObjectBase",
    Twin="CosmeticEdge",
    TwinPointer="CosmeticEdge",
    Include="Mod/TechDraw/App/Cosmetic.h",
    Namespace="TechDraw",
    FatherInclude="Base/GeometryPyCXX.h",
    FatherNamespace="Base",
    Constructor=True,
    Delete=True,
)
class CosmeticEdge(ObjectBase):
    """
    CosmeticEdge specifies an extra (cosmetic) edge in Views

    Author: WandererFan (wandererfan@gmail.com)
    Licence: LGPL
    """

    Tag: Final[str] = ""
    """Gives the tag of the CosmeticEdge as string."""

    Start: Vector = ...
    """Gives the position of one end of this CosmeticEdge as vector."""

    End: Vector = ...
    """Gives the position of one end of this CosmeticEdge as vector."""

    Center: Vector = ...
    """Gives the position of center point of this CosmeticEdge as vector."""

    Radius: float = ...
    """Gives the radius of CosmeticEdge in mm."""

    Format: dict = ...
    """The appearance attributes (style, weight, color, visible) for this CosmeticEdge."""
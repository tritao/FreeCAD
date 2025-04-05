from Base.Metadata import export, constmethod
from Base.PyObjectBase import PyObjectBase
from typing import Final

@export(
    Delete=True,
)
class CosmeticVertex(PyObjectBase):
    """
    CosmeticVertex specifies an extra (cosmetic) vertex in Views

    Author: WandererFan (LGPL, wandererfan@gmail.com)
    """

    Tag: Final[str] = ""
    """Gives the tag of the CosmeticVertex as string."""

    Point: object = ...
    """Gives the position of this CosmeticVertex as vector."""

    Show: bool = ...
    """Show/hide the vertex."""

    Color: object = ...
    """set/return the vertex's colour using a tuple (rgba)."""

    Size: object = ...
    """set/return the vertex's radius in mm."""

    Style: object = ...
    """set/return the vertex's style as integer."""

    @constmethod
    def clone(self) -> "CosmeticVertex":
        """
        clone() -> CosmeticVertex

        Create a clone of this CosmeticVertex
        """
        ...

    @constmethod
    def copy(self) -> "CosmeticVertex":
        """
        copy() -> CosmeticVertex

        Create a copy of this CosmeticVertex
        """
        ...
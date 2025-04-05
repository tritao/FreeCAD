from Base.Metadata import export, constmethod
from Base.PyObjectBase import PyObjectBase as ObjectBase
from typing import Final, List, Dict

@export(
    Delete=True,
)
class CenterLine(ObjectBase):
    """
    CenterLine specifies additional mark up edges in a View

    Author: WandererFan
    Licence: LGPL
    """

    Tag: Final[str] = ""
    """Gives the tag of the CenterLine as string."""

    Type: Final[int] = 0
    """0 - face, 1 - 2 line, 2 - 2 point."""

    Mode: int = 0
    """0 - vert/ 1 - horiz/ 2 - aligned."""

    Format: Dict[str, str] = {}
    """The appearance attributes (style, color, weight, visible) for this CenterLine."""

    HorizShift: float = 0.0
    """The left/right offset for this CenterLine."""

    VertShift: float = 0.0
    """The up/down offset for this CenterLine."""

    Rotation: float = 0.0
    """The rotation of the Centerline in degrees."""

    Extension: float = 0.0
    """The additional length to be added to this CenterLine."""

    Flip: bool = False
    """Reverse the order of points for 2 point CenterLine."""

    Edges: List[str] = []
    """The names of source edges for this CenterLine."""

    Faces: List[str] = []
    """The names of source Faces for this CenterLine."""

    Points: List[str] = []
    """The names of source Points for this CenterLine."""

    @constmethod
    def clone(self) -> "CenterLine":
        """
        clone() -> CenterLine

        Create a clone of this centerline
        """
        ...

    @constmethod
    def copy(self) -> "CenterLine":
        """
        copy() -> CenterLine

        Create a copy of this centerline
        """
        ...
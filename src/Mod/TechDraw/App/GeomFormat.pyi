from Base.Metadata import export, constmethod
from typing import Final

@export(
    Father="PyObjectBase",
    Twin="GeomFormat",
    TwinPointer="GeomFormat",
    Include="Mod/TechDraw/App/Cosmetic.h",
    Namespace="TechDraw",
    FatherInclude="Base/PyObjectBase.h",
    FatherNamespace="Base",
    Constructor=True,
    Delete=True,
)
class GeomFormat(PyObjectBase):
    """
    GeomFormat specifies appearance parameters for TechDraw Geometry objects
    Author: WandererFan (wandererfan@gmail.com)
    Licence: LGPL
    """

    Tag: Final[str] = ""
    """Gives the tag of the GeomFormat as string."""

    @constmethod
    def clone(self) -> "GeomFormat":
        """
        clone() -> GeomFormat

        Create a clone of this geomformat
        """
        ...

    @constmethod
    def copy(self) -> "GeomFormat":
        """
        copy() -> GeomFormat

        Create a copy of this geomformat
        """
        ...
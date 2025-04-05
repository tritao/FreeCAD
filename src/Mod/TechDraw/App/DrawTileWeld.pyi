from Base.Metadata import export

@export(
    Father="DrawTile",
    Twin="DrawTileWeld",
    TwinPointer="DrawTileWeld",
    Include="Mod/TechDraw/App/DrawTileWeld.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawTilePy.h",
    FatherNamespace="TechDraw",
)
class DrawTileWeld(DrawTile):
    """
    Feature for adding welding tiles to leader lines
    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """
    ...
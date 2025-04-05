from Base.Metadata import export
from TechDraw.DrawView import DrawView

@export(
    Father="DrawView",
    Twin="DrawRichAnno",
    TwinPointer="DrawRichAnno",
    Include="Mod/TechDraw/App/DrawRichAnno.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw",
)
class DrawRichAnno(DrawView):
    """
    Feature for adding rich annotation blocks to Technical Drawings

    Author: WandererFan (wandererfan@gmail.com) Licence: LGPL
    """
    ...
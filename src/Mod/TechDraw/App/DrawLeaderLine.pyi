from Base.Metadata import export
from TechDraw.DrawView import DrawView

@export(
    Father="DrawView",
    Twin="DrawLeaderLine",
    TwinPointer="DrawLeaderLine",
    Include="Mod/TechDraw/App/DrawLeaderLine.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawViewPy.h",
    FatherNamespace="TechDraw",
)
class DrawLeaderLine(DrawView):
    """
      <Documentation>
        <Author Licence="LGPL" Name="WandererFan" EMail="wandererfan@gmail.com" />
        <UserDocu>Feature for adding leaders to Technical Drawings</UserDocu>
      </Documentation>
    """
    ...
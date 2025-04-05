from Base.Metadata import export

@export(
    Father="DrawView",
    Twin="DrawWeldSymbol",
    TwinPointer="DrawWeldSymbol",
    Include="Mod/TechDraw/App/DrawWeldSymbol.h",
    Namespace="TechDraw",
    FatherInclude="Mod/TechDraw/App/DrawView.h",
    FatherNamespace="TechDraw",
)
class DrawWeldSymbol(DrawView):
    """
      <Documentation>
        <Author Licence="LGPL" Name="WandererFan" EMail="wandererfan@gmail.com" />
        <UserDocu>Feature for adding welding tiles to leader lines</UserDocu>
      </Documentation>
    """
    ...
from Base.Metadata import export
from App.DocumentObject import DocumentObject

@export(
    Father="DocumentObject",
    Name="DrawTile",
    Twin="DrawTile",
    TwinPointer="DrawTile",
    Include="Mod/TechDraw/App/DrawTile.h",
    Namespace="TechDraw",
    FatherInclude="App/DocumentObjectPy.h",
    FatherNamespace="App",
)
class DrawTile(DocumentObject):
    """
    Feature for adding tiles to leader lines

    Author: WandererFan
    Licence: LGPL
    EMail: wandererfan@gmail.com
    """
    ...
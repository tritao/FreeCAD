from Base.Metadata import export
from App.DocumentObjectExtension import DocumentObjectExtension

@export(
    Father="DocumentObjectExtensionPy",
    Name="CosmeticExtensionPy",
    Twin="CosmeticExtension",
    TwinPointer="CosmeticExtension",
    Include="Mod/TechDraw/App/CosmeticExtension.h",
    Namespace="TechDraw",
    FatherInclude="App/DocumentObjectExtensionPy.h",
    FatherNamespace="App",
)
class CosmeticExtension(DocumentObjectExtension):
    """
      <Documentation>
        <Author Licence="LGPL" Name="WandererFan" EMail="wandererfan@gmail.com" />
        <UserDocu>This object represents cosmetic features for a DrawViewPart.</UserDocu>
      </Documentation>
    """
    ...
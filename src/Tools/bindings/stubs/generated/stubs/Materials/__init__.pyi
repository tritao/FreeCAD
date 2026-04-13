# Generated public class stubs from binding .pyi specs.
from __future__ import annotations
from FreeCAD.Base import BaseClass

from typing import *

# src/Mod/Material/App/Array2D.pyi:19
class Array2D(BaseClass):
    """
    2D Array of material properties.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Array: Final[List] = ...
    'The 2 dimensional array.'
    Dimensions: Final[int] = ...
    'The number of dimensions in the array, in this case 2.'
    Rows: int = ...
    'The number of rows in the array.'
    Columns: int = ...
    'The number of columns in the array.'

    def getRow(self, value: Any, /) -> Any:
        """
        Get the row given the first column value
        """
        ...

    def getValue(self, row: int, column: int, /) -> Any:
        """
        Get the value at the given row and column
        """
        ...

    def setValue(self, row: int, column: int, value: Any, /):
        """
        Set the value at the given row and column
        """
        ...

# src/Mod/Material/App/Array3D.pyi:18
class Array3D(BaseClass):
    """
    3D Array of material properties.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Array: Final[List] = ...
    'The 3 dimensional array.'
    Dimensions: Final[int] = ...
    'The number of dimensions in the array, in this case 3.'
    Columns: int = ...
    'The number of columns in the array.'
    Depth: int = ...
    'The depth of the array (3rd dimension).'

    def getRows(self) -> int:
        """
        Get the number of rows in the array at the specified depth.
        """
        ...

    def getValue(self) -> Any:
        """
        Get the value at the given row and column
        """
        ...

    def getDepthValue(self) -> Any:
        """
        Get the column value at the given depth
        """
        ...

    def setDepthValue(self, value: Any, /):
        """
        Set the column value at the given depth
        """
        ...

    def setValue(self, depth: int, row: int, column: int, value: Any, /):
        """
        Set the value at the given depth, row, and column
        """
        ...

    def setRows(self, depth: int, value: int, /):
        """
        Set the number of rows at the given depth
        """
        ...

# src/Mod/Material/App/Material.pyi:17
class Material(BaseClass):
    """
    Material descriptions.

    Author: David Carter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    LibraryName: Final[str] = ...
    'Material library name.'
    LibraryRoot: Final[str] = ...
    'Material library path.'
    LibraryIcon: Final[bytes] = ...
    'Material icon.'
    Name: str = ...
    'Material name.'
    Directory: str = ...
    'Material directory relative to the library root.'
    UUID: Final[str] = ...
    'Unique material identifier. This is only valid after the material is saved.'
    Description: str = ...
    'Description of the material.'
    URL: str = ...
    'URL to a material reference.'
    Reference: str = ...
    'Reference for material data.'
    Parent: str = ...
    'Parent material UUID.'
    AuthorAndLicense: Final[str] = ...
    'deprecated -- Author and license information.'
    Author: str = ...
    'Author information.'
    License: str = ...
    'License information.'
    PhysicalModels: Final[list] = ...
    'List of implemented models.'
    AppearanceModels: Final[list] = ...
    'List of implemented models.'
    Tags: Final[list] = ...
    'List of searchable tags.'
    Properties: Final[dict] = ...
    'deprecated -- Dictionary of all material properties.'
    PhysicalProperties: Final[dict] = ...
    'deprecated -- Dictionary of material physical properties.'
    AppearanceProperties: Final[dict] = ...
    'deprecated -- Dictionary of material appearance properties.'
    LegacyProperties: Final[dict] = ...
    'deprecated -- Dictionary of material legacy properties.'
    PropertyObjects: Final[dict] = ...
    'Dictionary of MaterialProperty objects.'

    def addPhysicalModel(self) -> None:
        """Add the physical model with the given UUID"""
        ...

    def removePhysicalModel(self) -> None:
        """Remove the physical model with the given UUID"""
        ...

    def hasPhysicalModel(self) -> bool:
        """Check if the material implements the physical model with the given UUID"""
        ...

    def addAppearanceModel(self) -> None:
        """Add the appearance model with the given UUID"""
        ...

    def removeAppearanceModel(self) -> None:
        """Remove the appearance model with the given UUID"""
        ...

    def hasAppearanceModel(self) -> bool:
        """Check if the material implements the appearance model with the given UUID"""
        ...

    def isPhysicalModelComplete(self) -> bool:
        """Check if the material implements the physical model with the given UUID, and has values defined for each property"""
        ...

    def isAppearanceModelComplete(self) -> bool:
        """Check if the material implements the appearance model with the given UUID, and has values defined for each property"""
        ...

    def hasPhysicalProperty(self) -> bool:
        """Check if the material implements the physical property with the given name"""
        ...

    def hasAppearanceProperty(self) -> bool:
        """Check if the material implements the appearance property with the given name"""
        ...

    def hasLegacyProperties(self) -> bool:
        """Returns true of there are legacy properties"""
        ...

    def getPhysicalValue(self) -> str:
        """Get the value associated with the property"""
        ...

    def setPhysicalValue(self) -> None:
        """Set the value associated with the property"""
        ...

    def getAppearanceValue(self) -> str:
        """Get the value associated with the property"""
        ...

    def setAppearanceValue(self) -> None:
        """Set the value associated with the property"""
        ...

    def setValue(self) -> None:
        """Set the value associated with the property"""
        ...

    def keys(self) -> list:
        """Property keys"""
        ...

    def values(self) -> list:
        """Property values"""
        ...

# src/Mod/Material/App/MaterialFilter.pyi:16
class MaterialFilter(BaseClass):
    """
    Material filters.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Name: str = ...
    'Name of the filter used to select a filter in a list'
    RequiredModels: List = ...
    'Materials must include the specified models.'
    RequiredCompleteModels: List = ...
    'Materials must have complete versions of the specified models.'

# src/Mod/Material/App/MaterialFilterOptions.pyi:15
class MaterialFilterOptions(BaseClass):
    """
    Material filtering options.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    IncludeFavorites: bool = ...
    'Include materials marked as favorite.'
    IncludeRecent: bool = ...
    'Include recently used materials.'
    IncludeEmptyFolders: bool = ...
    'Include empty folders.'
    IncludeEmptyLibraries: bool = ...
    'Include empty libraries.'
    IncludeLegacy: bool = ...
    'Include materials using the older legacy format.'

# src/Mod/Material/App/MaterialLibrary.pyi:15
class MaterialLibrary(BaseClass):
    """
    Material library.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Name: str = ...
    'Name of the library'
    Icon: bytes = ...
    'Icon as an array of bytes.'
    Directory: str = ...
    'Local directory where the library is located. For non-local libraries this will be empty'
    ReadOnly: bool = ...
    'True if the library is local.'
    Local: bool = ...
    'True if the library is local.'

# src/Mod/Material/App/MaterialManager.pyi:11
class MaterialManager(BaseClass):
    """
    Material descriptions.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    MaterialLibraries: Final[List] = ...
    'List of Material libraries.'
    Materials: Final[Dict] = ...
    'List of Materials.'

    def getMaterial(self) -> None:
        """
        Get a material object by specifying its UUID
        """
        ...

    def getMaterialByPath(self) -> None:
        """
        Get a material object by specifying its path and library name
        """
        ...

    def inheritMaterial(self) -> None:
        """
        Create a new material object by specifying the UUID of its parent
        """
        ...

    def materialsWithModel(self) -> None:
        """
        Get a list of materials implementing the specified model
        """
        ...

    def materialsWithModelComplete(self) -> None:
        """
        Get a list of materials implementing the specified model, with values for all properties
        """
        ...

    def save(self, **kwargs) -> None:
        """
        Save the material in the specified library
        """
        ...

    def filterMaterials(self, **kwargs) -> None:
        """
        Returns a filtered material list
        """
        ...

    def refresh(self) -> None:
        """
        Refreshes the material tree. Use sparingly as this is an expensive operation.
        """
        ...

# src/Mod/Material/App/MaterialProperty.pyi:18
class MaterialProperty(ModelProperty):
    """
    Material property descriptions.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Value: Final[object] = ...
    'The value of the material property.'
    Empty: Final[bool] = False
    'The property value is undefined.'

# src/Mod/Material/App/Model.pyi:16
class Model(BaseClass):
    """
    Material model descriptions.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    LibraryName: Final[str] = ''
    'Model library name.'
    LibraryRoot: Final[str] = ''
    'Model library path.'
    LibraryIcon: Final[bytes] = ''
    'Model icon.'
    Name: str = ''
    'Model name.'
    Type: str = ''
    'Model type.'
    Directory: str = ''
    'Model directory.'
    UUID: Final[str] = ''
    'Unique model identifier.'
    Description: str = ''
    'Description of the model.'
    URL: str = ''
    'URL to a detailed description of the model.'
    DOI: str = ''
    'Digital Object Identifier (see https://doi.org/)'
    Inherited: Final[List[str]] = []
    'List of inherited models identified by UUID.'
    Properties: Final[Dict[str, str]] = {}
    'Dictionary of model properties.'

    def addInheritance(self) -> None:
        """
        Add an inherited model.
        """
        ...

    def addProperty(self) -> None:
        """
        Add a model property.
        """
        ...

# src/Mod/Material/App/ModelManager.pyi:11
class ModelManager(BaseClass):
    """
    Material model descriptions.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    ModelLibraries: Final[List] = ...
    'List of model libraries.'
    LocalModelLibraries: Final[List] = ...
    'List of local model libraries.'
    Models: Final[Dict] = ...
    'List of model libraries.'

    def getModel(self) -> ...:
        """
        Get a model object by specifying its UUID
        """
        ...

    def getModelByPath(self) -> ...:
        """
        Get a model object by specifying its path
        """
        ...

# src/Mod/Material/App/ModelProperty.pyi:16
class ModelProperty(BaseClass):
    """
    Material property descriptions.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Name: str = ...
    'Property name.'
    DisplayName: str = ...
    'Property display friendly name.'
    Type: str = ...
    'Property type.'
    Units: str = ...
    'Property units category.'
    URL: str = ...
    'URL to a detailed description of the property.'
    Description: str = ...
    'Property description.'
    Columns: Final[list] = ...
    'List of array columns.'
    Inheritance: Final[str] = ...
    'UUID of the model in which the property is defined.'
    Inherited: Final[bool] = ...
    'True if the property is inherited.'

    def addColumn(self) -> None:
        """
        Add a model property column.
        """
        ...

# src/Mod/Material/App/UUIDs.pyi:19
class UUIDs(BaseClass):
    """
    Material model UUID identifiers.

    Author: DavidCarter (dcarter@davidcarter.ca)
    Licence: LGPL
    """
    Father: Final[str] = ...
    'UUID for model System:Legacy/Father'
    MaterialStandard: Final[str] = ...
    'UUID for model System:Legacy/MaterialStandard'
    ArrudaBoyce: Final[str] = ...
    'UUID for model System:Mechanical/ArrudaBoyce'
    Density: Final[str] = ...
    'UUID for model System:Mechanical/Density'
    Hardness: Final[str] = ...
    'UUID for model System:Mechanical/Hardness'
    IsotropicLinearElastic: Final[str] = ...
    'UUID for model System:Mechanical/IsotropicLinearElastic'
    LinearElastic: Final[str] = ...
    'UUID for model System:Mechanical/LinearElastic'
    Machinability: Final[str] = ...
    'UUID for model System:Machining/Machinability'
    MooneyRivlin: Final[str] = ...
    'UUID for model System:Mechanical/MooneyRivlin'
    NeoHooke: Final[str] = ...
    'UUID for model System:Mechanical/NeoHooke'
    OgdenN1: Final[str] = ...
    'UUID for model System:Mechanical/OgdenN1'
    OgdenN2: Final[str] = ...
    'UUID for model System:Mechanical/OgdenN2'
    OgdenN3: Final[str] = ...
    'UUID for model System:Mechanical/OgdenN3'
    OgdenYld2004p18: Final[str] = ...
    'UUID for model System:Mechanical/OgdenYld2004p18'
    OrthotropicLinearElastic: Final[str] = ...
    'UUID for model System:Mechanical/OrthotropicLinearElastic'
    PolynomialN1: Final[str] = ...
    'UUID for model System:Mechanical/PolynomialN1'
    PolynomialN2: Final[str] = ...
    'UUID for model System:Mechanical/PolynomialN2'
    PolynomialN3: Final[str] = ...
    'UUID for model System:Mechanical/PolynomialN3'
    ReducedPolynomialN1: Final[str] = ...
    'UUID for model System:Mechanical/ReducedPolynomialN1'
    ReducedPolynomialN2: Final[str] = ...
    'UUID for model System:Mechanical/ReducedPolynomialN2'
    ReducedPolynomialN3: Final[str] = ...
    'UUID for model System:Mechanical/ReducedPolynomialN3'
    Yeoh: Final[str] = ...
    'UUID for model System:Mechanical/Yeoh'
    Fluid: Final[str] = ...
    'UUID for model System:Fluid/Fluid'
    Thermal: Final[str] = ...
    'UUID for model System:Thermal/Thermal'
    Electromagnetic: Final[str] = ...
    'UUID for model System:Electromagnetic/Electromagnetic'
    Architectural: Final[str] = ...
    'UUID for model System:Architectural/Architectural'
    ArchitecturalRendering: Final[str] = ...
    'UUID for model System:Architectural/ArchitecturalRendering'
    Costs: Final[str] = ...
    'UUID for model System:Costs/Costs'
    BasicRendering: Final[str] = ...
    'UUID for model System:Rendering/BasicRendering'
    TextureRendering: Final[str] = ...
    'UUID for model System:Rendering/TextureRendering'
    AdvancedRendering: Final[str] = ...
    'UUID for model System:Rendering/AdvancedRendering'
    VectorRendering: Final[str] = ...
    'UUID for model System:Rendering/VectorRendering'
    RenderAppleseed: Final[str] = ...
    'UUID for model System:Rendering/RenderAppleseed'
    RenderCarpaint: Final[str] = ...
    'UUID for model System:Rendering/RenderCarpaint'
    RenderCycles: Final[str] = ...
    'UUID for model System:Rendering/RenderCycles'
    RenderDiffuse: Final[str] = ...
    'UUID for model System:Rendering/RenderDiffuse'
    RenderDisney: Final[str] = ...
    'UUID for model System:Rendering/RenderDisney'
    RenderEmission: Final[str] = ...
    'UUID for model System:Rendering/RenderEmission'
    RenderGlass: Final[str] = ...
    'UUID for model System:Rendering/RenderGlass'
    RenderLuxcore: Final[str] = ...
    'UUID for model System:Rendering/RenderLuxcore'
    RenderLuxrender: Final[str] = ...
    'UUID for model System:Rendering/RenderLuxrender'
    RenderMixed: Final[str] = ...
    'UUID for model System:Rendering/RenderMixed'
    RenderOspray: Final[str] = ...
    'UUID for model System:Rendering/RenderOspray'
    RenderPbrt: Final[str] = ...
    'UUID for model System:Rendering/RenderPbrt'
    RenderPovray: Final[str] = ...
    'UUID for model System:Rendering/RenderPovray'
    RenderSubstancePBR: Final[str] = ...
    'UUID for model System:Rendering/RenderSubstancePBR'
    RenderTexture: Final[str] = ...
    'UUID for model System:Rendering/RenderTexture'
    RenderWB: Final[str] = ...
    'UUID for model System:Rendering/RenderWB'
    TestModel: Final[str] = ...
    'UUID for model System:Test/Test Model'

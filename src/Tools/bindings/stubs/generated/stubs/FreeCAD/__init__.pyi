# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations
from . import Console as Console
from . import Units as Units
from typing import TYPE_CHECKING, Literal, Sequence, TypeAlias, overload
if TYPE_CHECKING:
    from Part import Feature as _PartFeature
_FileTypeModules: TypeAlias = dict[str, str | list[str] | None]
_LogLevelName: TypeAlias = Literal['Default', 'Error', 'Warning', 'Message', 'Log', 'Trace']
GuiUp: int
ActiveDocument: Document | None

def ParamGet(path: str, /) -> _ParameterGrp:
    ...

def saveParameter(name: str='User parameter', /) -> None:
    ...

def Version() -> list[str]:
    ...

def ConfigGet(key: str, /) -> str:
    ...

def ConfigSet(key: str, value: str, /) -> None:
    ...

def ConfigDump() -> dict[str, str]:
    ...

def addImportType(extension: str, module: str, /) -> None:
    ...

def changeImportModule(extension: str, old_module: str, new_module: str, /) -> None:
    ...

@overload
def getImportType() -> _FileTypeModules:
    ...

@overload
def getImportType(extension: str, /) -> list[str]:
    ...

def addExportType(extension: str, module: str, /) -> None:
    ...

def addTranslatableExportType(description: str, extensions: list[str], module: str, /) -> None:
    ...

def changeExportModule(extension: str, old_module: str, new_module: str, /) -> None:
    ...

@overload
def getExportType() -> _FileTypeModules:
    ...

@overload
def getExportType(extension: str, /) -> list[str]:
    ...

def getResourceDir() -> str:
    ...

def getLibraryDir() -> str:
    ...

def getTempPath() -> str:
    ...

def getUserCachePath() -> str:
    ...

def getUserConfigDir() -> str:
    ...

def getUserAppDataDir() -> str:
    ...

def getUserMacroDir(actual: bool=False, /) -> str:
    ...

def getHelpDir() -> str:
    ...

def getHomePath() -> str:
    ...

def loadFile(path: str, doc: str='', module: str='', /) -> None:
    ...

def open(name: str, hidden: bool=False, temporary: bool=False) -> Document:
    ...

def openDocument(name: str, hidden: bool=False, temporary: bool=False) -> Document:
    ...

def newDocument(name: str | None=None, label: str | None=None, hidden: bool=False, temp: bool=False) -> Document:
    ...

def closeDocument(document: str | Document, /) -> None:
    ...

def activeDocument() -> Document | None:
    ...

def setActiveDocument(name: str, /) -> None:
    ...

def getDocument(name: str, /) -> Document:
    ...

def listDocuments(sort: bool=False, /) -> dict[str, Document]:
    ...

def addDocumentObserver(observer: object, /) -> None:
    ...

def removeDocumentObserver(observer: object, /) -> None:
    ...

def setLogLevel(tag: str, level: _LogLevelName | int, /) -> None:
    ...

def getLogLevel(tag: str, /) -> int:
    ...

def checkLinkDepth(depth: int, /) -> int:
    ...

def getLinksTo(obj: DocumentObject | None=None, options: int=0, maxCount: int=0, /) -> tuple[DocumentObject, ...]:
    ...

def getDependentObjects(obj: DocumentObject | Sequence[DocumentObject], options: int=0, /) -> tuple[DocumentObject, ...]:
    ...

def setActiveTransaction(name: str, persist: bool=False, /) -> int:
    ...

def getActiveTransaction() -> tuple[str, int] | None:
    ...

def closeActiveTransaction(abort: bool=False, id: int=0, /) -> None:
    ...

def isRestoring() -> bool:
    ...

def checkAbort() -> None:
    ...
from typing import Any

class _ParameterGrp:

    def GetGroup(self, name: str, /) -> _ParameterGrp:
        ...

    def GetGroupName(self) -> str:
        ...

    def GetGroups(self) -> list[str]:
        ...

    def RemGroup(self, name: str, /) -> None:
        ...

    def HasGroup(self, name: str, /) -> bool:
        ...

    def RenameGroup(self, old_name: str, new_name: str, /) -> bool:
        ...

    def CopyTo(self, group: _ParameterGrp, /) -> None:
        ...

    def Manager(self) -> _ParameterGrp | None:
        ...

    def Parent(self) -> _ParameterGrp | None:
        ...

    def IsEmpty(self) -> bool:
        ...

    def Clear(self) -> None:
        ...

    def Attach(self, observer: object, /) -> None:
        ...

    def AttachManager(self, observer: object, /) -> None:
        ...

    def Detach(self, observer: object, /) -> None:
        ...

    def Notify(self, name: str, /) -> None:
        ...

    def NotifyAll(self) -> None:
        ...

    def SetBool(self, name: str, value: bool | int, /) -> None:
        ...

    def GetBool(self, name: str, default: bool | int=False, /) -> bool:
        ...

    def GetBools(self, filter: str='', /) -> list[str]:
        ...

    def RemBool(self, name: str, /) -> None:
        ...

    def SetInt(self, name: str, value: int, /) -> None:
        ...

    def GetInt(self, name: str, default: int=0, /) -> int:
        ...

    def GetInts(self, filter: str='', /) -> list[str]:
        ...

    def RemInt(self, name: str, /) -> None:
        ...

    def SetUnsigned(self, name: str, value: int, /) -> None:
        ...

    def GetUnsigned(self, name: str, default: int=0, /) -> int:
        ...

    def GetUnsigneds(self, filter: str='', /) -> list[str]:
        ...

    def RemUnsigned(self, name: str, /) -> None:
        ...

    def SetFloat(self, name: str, value: float, /) -> None:
        ...

    def GetFloat(self, name: str, default: float=0.0, /) -> float:
        ...

    def GetFloats(self, filter: str='', /) -> list[str]:
        ...

    def RemFloat(self, name: str, /) -> None:
        ...

    def SetString(self, name: str, value: str, /) -> None:
        ...

    def GetString(self, name: str, default: str='', /) -> str:
        ...

    def GetStrings(self, filter: str='', /) -> list[str]:
        ...

    def RemString(self, name: str, /) -> None:
        ...

    def Import(self, path: str, /) -> None:
        ...

    def Insert(self, path: str, /) -> None:
        ...

    def Export(self, path: str, /) -> None:
        ...

    def GetContents(self) -> list[tuple[str, str, str | int | float | bool]] | None:
        ...
import FreeCAD
from FreeCAD.Base import Persistence
from FreeCAD.Base import BaseClass
from typing import *
from .Base import Axis as Axis
from .Base import BoundBox as BoundBox
from .Base import Matrix as Matrix
from .Base import Placement as Placement
from .Base import Rotation as Rotation
from .Base import Vector as Vector

class ApplicationDirectories:
    """
    Provides access to the directory versioning methods of its C++ counterpart.

    These are all static methods, so no instance is needed. The main methods of
    this class are migrateAllPaths(), usingCurrentVersionConfig(), and versionStringForPath().
    """

    @staticmethod
    def usingCurrentVersionConfig(path: str, /) -> bool:
        """
        Determine if a given config path is for the current version of the program.

        Args:
            path: The path to check.
        """
        ...

    @staticmethod
    def migrateAllPaths(paths: list[str], /) -> list[str]:
        """
        Migrate a set of versionable configuration directories from the given paths to a new version.

        The new version's directories cannot exist yet, and the old ones *must* exist.
        If the old paths are themselves versioned, then the new paths will be placed at the same
        level in the directory structure (e.g., they will be siblings of each entry in paths).
        If paths are NOT versioned, the new (versioned) copies will be placed *inside* the
        original paths.

        If the list contains the same path multiple times, the duplicates are ignored, so it is safe
        to pass the same path multiple times.

        Args:
            paths: List of paths to migrate from.

        Examples:
            Running FreeCAD 1.1, /usr/share/FreeCAD/Config/ -> /usr/share/FreeCAD/Config/v1-1/
            Running FreeCAD 1.1, /usr/share/FreeCAD/Config/v1-1 -> raises exception, path exists
            Running FreeCAD 1.2, /usr/share/FreeCAD/Config/v1-1/ -> /usr/share/FreeCAD/Config/v1-2/
        """
        ...

    @staticmethod
    def versionStringForPath(major: int, minor: int, /) -> str:
        """
        Given a major and minor version number, return the name for a versioned subdirectory.

        Args:
            major: Major version number.
            minor: Minor version number.

        Returns:
            A string that can be used as the name for a versioned subdirectory.
            Only returns the version string, not the full path.
        """
        ...

    @staticmethod
    def isVersionedPath(startingPath: str, /) -> bool:
        """
        Determine if a given path is versioned.

        That is, if its last component contains something that this class would have
        created as a versioned subdirectory).

        Args:
            startingPath: The path to check.

        Returns:
            True for any path that the *current* version of FreeCAD would recognize as versioned,
            and False for either something that is not versioned, or something that is versioned
            but for a later version of FreeCAD.
        """
        ...

    @staticmethod
    def mostRecentAvailableConfigVersion(startingPath: str, /) -> str:
        """
        Given a base path that is expected to contain versioned subdirectories, locate the
        directory name (*not* the path, only the final component, the version string itself)
        corresponding to the most recent version of the software, up to and including the current
        running version, but NOT exceeding it -- any *later* version whose directories exist
        in the path is ignored. See also mostRecentConfigFromBase().

        Args:
            startingPath: The path to check.

        Returns:
            Most recent available dir name (not path).
        """
        ...

    @staticmethod
    def mostRecentConfigFromBase(startingPath: str, /) -> str:
        """
        Given a base path that is expected to contained versioned subdirectories, locate the
        directory corresponding to the most recent version of the software, up to and including
        the current version, but NOT exceeding it. Returns the complete path, not just the final
        component. See also mostRecentAvailableConfigVersion().

        Args:
            startingPath: The base path to check.

        Returns:
            Most recent available full path (not just dir name).
        """
        ...

    @staticmethod
    def migrateConfig(oldPath: str, newPath: str, /) -> list[str]:
        """
        A utility method to copy all files and directories from oldPath to newPath, handling the
        case where newPath might itself be a subdirectory of oldPath (and *not* attempting that
        otherwise-recursive copy).

        Args:
            oldPath: Path from.
            newPath: Path to.
        """
        ...

class ComplexGeoData(Persistence):
    """
    Father of all complex geometric data types.
    """

    def getElementTypes(self) -> list[str]:
        """
        Return a list of element types present in the complex geometric data.
        """
        ...

    def countSubElements(self) -> int:
        """
        Return the number of elements of a type.
        """
        ...

    def getFacesFromSubElement(self) -> tuple[list[Vector], list[tuple[int, int, int]]]:
        """
        Return vertexes and faces from a sub-element.
        """
        ...

    def getLinesFromSubElement(self) -> tuple[list[Vector], list[tuple[int, int]]]:
        """
        Return vertexes and lines from a sub-element.
        """
        ...

    def getPoints(self) -> tuple[list[Vector], list[Vector]]:
        """
        Return a tuple of points and normals with a given accuracy
        """
        ...

    def getLines(self) -> tuple[list[Vector], list[tuple[int, int]]]:
        """
        Return a tuple of points and lines with a given accuracy
        """
        ...

    def getFaces(self) -> tuple[list[Vector], list[tuple[int, int, int]]]:
        """
        Return a tuple of points and triangles with a given accuracy
        """
        ...

    def applyTranslation(self, translation: Vector, /) -> None:
        """
        Apply an additional translation to the placement
        """
        ...

    def applyRotation(self, rotation: Rotation, /) -> None:
        """
        Apply an additional rotation to the placement
        """
        ...

    def transformGeometry(self, transformation: Matrix, /) -> None:
        """
        Apply a transformation to the underlying geometry
        """
        ...

    def setElementName(self, *, element: str, name: str=None, postfix: str=None, overwrite: bool=False, sid: Any=None) -> None:
        """
        Set an element name.

        Args:
            element  : the original element name, e.g. Edge1, Vertex2
            name     : the new name for the element, None to remove the mapping
            postfix  : postfix of the name that will not be hashed
            overwrite: if true, it will overwrite exiting name
            sid      : to hash the name any way you want, provide your own string id(s) in this parameter

        An element can have multiple mapped names. However, a name can only be mapped
        to one element
        """
        ...

    def getElementName(self, name: str, direction: int=0, /) -> str:
        """
        Return a mapped element name or reverse.
        """
        ...

    def getElementIndexedName(self, name: str, /) -> str | tuple[str, list[int]]:
        """
        Return the indexed element name.
        """
        ...

    def getElementMappedName(self, name: str, /) -> str | tuple[str, list[int]]:
        """
        Return the mapped element name
        """
        ...
    BoundBox: 'Final[FreeCAD.BoundBox]' = ...
    'Get the bounding box (BoundBox) of the complex geometric data.'
    CenterOfGravity: Final[Vector] = ...
    'Get the center of gravity'
    Placement: 'FreeCAD.Placement' = ...
    'Get the current transformation of the object as placement'
    Tag: int = 0
    'Geometry Tag'
    Hasher: StringHasher = ...
    'Get/Set the string hasher of this object'
    ElementMapSize: Final[int] = 0
    'Get the current element map size'
    ElementMap: dict[str, str] = {}
    'Get/Set a dict of element mapping'
    ElementReverseMap: Final[dict[str, str | list[str]]] = {}
    'Get a dict of element reverse mapping'
    ElementMapVersion: Final[str] = ''
    'Element map version'

class Document(PropertyContainer):
    """
    This is the Document class.
    """
    DependencyGraph: Final[str] = ''
    'The dependency graph as GraphViz text'
    ActiveObject: Final[DocumentObject] = ...
    'The last created object in this document'
    Objects: Final[list[DocumentObject]] = []
    'The list of objects in this document'
    TopologicalSortedObjects: Final[list[DocumentObject]] = []
    'The list of objects in this document in topological sorted order'
    RootObjects: Final[list[DocumentObject]] = []
    'The list of root objects in this document'
    RootObjectsIgnoreLinks: Final[list[DocumentObject]] = []
    'The list of root objects in this document ignoring references from links.'
    UndoMode: int = 0
    'The Undo mode of the Document (0 = no Undo, 1 = Undo/Redo)'
    UndoRedoMemSize: Final[int] = 0
    'The size of the Undo stack in byte'
    UndoCount: Final[int] = 0
    'Number of possible Undos'
    RedoCount: Final[int] = 0
    'Number of possible Redos'
    UndoNames: Final[list[str]] = []
    'A list of Undo names'
    RedoNames: Final[list[str]] = []
    'A List of Redo names'
    Name: Final[str] = ''
    'The internal name of the document'
    RecomputesFrozen: bool = False
    'Returns or sets if automatic recomputes for this document are disabled.'
    HasPendingTransaction: Final[bool] = False
    'Check if there is a pending transaction'
    InList: Final[list[Document]] = []
    'A list of all documents that link to this document.'
    OutList: Final[list[Document]] = []
    'A list of all documents that this document links to.'
    Restoring: Final[bool] = False
    'Indicate if the document is restoring'
    Partial: Final[bool] = False
    'Indicate if the document is partially loaded'
    Importing: Final[bool] = False
    'Indicate if the document is importing. Note the document will also report Restoring while importing'
    Recomputing: Final[bool] = False
    'Indicate if the document is recomputing'
    Transacting: Final[bool] = False
    'Indicate whether the document is undoing/redoing'
    OldLabel: Final[str] = ''
    'Contains the old label before change'
    Temporary: Final[bool] = False
    'Check if this is a temporary document'

    def save(self) -> None:
        """
        Save the document to disk.
        """
        ...

    def saveAs(self, path: str, /) -> None:
        """
        Save the document under a new name to disk.
        """
        ...

    def saveCopy(self, path: str, /) -> None:
        """
        Save a copy of the document under a new name to disk.
        """
        ...

    def load(self, path: str, /) -> None:
        """
        Load the document from the given path.
        """
        ...

    def restore(self) -> None:
        """
        Restore the document from disk
        """
        ...

    def isSaved(self) -> bool:
        """
        Checks if the document is saved
        """
        ...

    def getProgramVersion(self) -> str:
        """
        Get the program version that a project file was created with
        """
        ...

    def getFileName(self) -> str:
        """
        For a regular document it returns its file name property.
        For a temporary document it returns its transient directory.
        """
        ...

    def getUniqueObjectName(self, objName: str, /) -> str:
        """
        Return the same name, or the name made unique, for Example Box -> Box002 if there are conflicting name
        already in the document.

        Args:
            objName: Object name candidate.

        Returns:
            Unique object name based on objName.
        """
        ...

    def mergeProject(self, path: str, /) -> None:
        """
        Merges this document with another project file.
        """
        ...

    def exportGraphviz(self, path: str=None, /) -> str | None:
        """
        Export the dependencies of the objects as graph.

        If path is passed, graph is written to it. if not a string is returned.
        """
        ...

    def openTransaction(self, name: str, /) -> None:
        """
        Open a new Undo/Redo transaction.

        This function no long creates a new transaction, but calls
        FreeCAD.setActiveTransaction(name) instead, which will auto creates a
        transaction with the given name when any change happened in any opened document.
        If more than one document is changed, all newly created transactions will have
        the same internal ID and will be undo/redo together.
        """
        ...

    def abortTransaction(self) -> None:
        """
        Abort an Undo/Redo transaction (rollback)
        """
        ...

    def commitTransaction(self) -> None:
        """
        Commit an Undo/Redo transaction
        """
        ...

    @overload
    def addObject(self, type: Literal['Part::Feature'], name: str=None, objProxy: object=None, viewProxy: object=None, attach: bool=False, viewType: str=None) -> _PartFeature:
        ...

    @overload
    def addObject(self, type: str, name: str=None, objProxy: object=None, viewProxy: object=None, attach: bool=False, viewType: str=None) -> DocumentObject:
        ...

    def addObject(self, type: str, name: str=None, objProxy: object=None, viewProxy: object=None, attach: bool=False, viewType: str=None) -> DocumentObject:
        """
        Add an object to document.

        Args:
            type: the type of the document object to create.
                  Call method supportedTypes() to get a list of possible values.
            name: the optional name of the new object.
            objProxy: the Python binding object to attach to the new document object.
            viewProxy: the Python binding object to attach the view provider of this object.
            attach: if True, then bind the document object first before adding to the document
                    to allow Python code to override view provider type. Once bound, and before adding to
                    the document, it will try to call Python binding object's attach(obj) method.
            viewType: override the view provider type directly, only effective when attach is False.
        """
        ...

    def addProperty(self, type: str, name: str, group: str='', doc: str='', attr: int=0, read_only: bool=False, hidden: bool=False, locked: bool=False, enum_vals: list[str] | None=None) -> Document:
        """
        Add a generic property.

        Args:
            type: The type of the property to add.
            name: The name of the property.
            group: The group to which the property belongs. Defaults to "".
            doc: The documentation string for the property. Defaults to "".
            attr: Attribute flags for the property. Defaults to 0.
            read_only: Whether the property is read-only. Defaults to False.
            hidden: Whether the property is hidden. Defaults to False.
            locked: Whether the property is locked. Defaults to False.

        Returns:
            The document instance with the added property.
        """
        ...

    def removeProperty(self, name: str, /) -> None:
        """
        Remove a generic property.

        Note, you can only remove user-defined properties but not built-in ones.
        """
        ...

    def removeObject(self, name: str, /) -> None:
        """
        Remove an object from the document.
        """
        ...

    @overload
    def copyObject(self, object: Sequence[DocumentObject], recursive: bool=False, return_all: bool=False) -> tuple[DocumentObject, ...]:
        ...

    @overload
    def copyObject(self, object: DocumentObject, recursive: bool=False, return_all: Literal[False]=False) -> DocumentObject:
        ...

    @overload
    def copyObject(self, object: DocumentObject, recursive: bool=False, return_all: Literal[True]=True) -> DocumentObject | tuple[DocumentObject, ...]:
        ...

    def copyObject(self, object: DocumentObject | Sequence[DocumentObject], recursive: bool=False, return_all: bool=False) -> DocumentObject | tuple[DocumentObject, ...]:
        """
        Copy an object or objects from another document to this document.

        Args:
            object: can either be a single object or sequence of objects
            recursive: if True, also recursively copies internal objects
            return_all: if True, returns all copied objects, or else return only the copied
                        object corresponding to the input objects.
        """
        ...

    def moveObject(self, object: DocumentObject, with_dependencies: bool=False, /) -> DocumentObject:
        """
        Transfers an object from another document to this document.

        Args:
            object: can either a single object or sequence of objects
            with_dependencies: if True, all internal dependent objects are copied too.
        """
        ...

    def importLinks(self, object: DocumentObject=None, /) -> tuple[DocumentObject, ...]:
        """
        Import any externally linked object given a list of objects in
        this document.  Any link type properties of the input objects
        will be automatically reassigned to the imported object

        If no object is given as input, it import all externally linked
        object of this document.
        """
        ...

    def undo(self) -> None:
        """
        Undo one transaction
        """
        ...

    def redo(self) -> None:
        """
        Redo a previously undone transaction
        """
        ...

    def clearUndos(self) -> None:
        """
        Clear the undo stack of the document
        """
        ...

    def clearDocument(self) -> None:
        """
        Clear the whole document
        """
        ...

    def setClosable(self, closable: bool, /) -> None:
        """
        Set a flag that allows or forbids to close a document
        """
        ...

    def isClosable(self) -> bool:
        """
        Check if the document can be closed. The default value is True
        """
        ...

    def setAutoCreated(self, autoCreated: bool, /) -> None:
        """
        Set a flag that indicates if a document is autoCreated
        """
        ...

    def isAutoCreated(self) -> bool:
        """
        Check if the document is autoCreated. The default value is False
        """
        ...

    def recompute(self, objs: Sequence[DocumentObject]=None, force: bool=False, check_cycle: bool=False, /) -> int:
        """
        Recompute the document and returns the amount of recomputed features.
        """
        ...

    def mustExecute(self) -> bool:
        """
        Check if any object must be recomputed
        """
        ...

    def purgeTouched(self) -> None:
        """
        Purge the touched state of all objects
        """
        ...

    def isTouched(self) -> bool:
        """
        Check if any object is in touched state
        """
        ...

    def getObject(self, name: str, /) -> DocumentObject:
        """
        Return the object with the given name
        """
        ...

    def getObjectsByLabel(self, label: str, /) -> list[DocumentObject]:
        """
        Return the objects with the given label name.

        NOTE: It's possible that several objects have the same label name.
        """
        ...

    def findObjects(self, Type: str=None, Name: str=None, Label: str=None) -> list[DocumentObject]:
        """
        Return a list of objects that match the specified type, name or label.

        Name and label support regular expressions. All parameters are optional.

        Args:
            Type: Type of the feature.
            Name: Name
            Label: Label
        """
        ...

    def getLinksTo(self, obj: DocumentObject, options: int=0, maxCount: int=0, /) -> tuple[DocumentObject, ...]:
        """
        Return objects linked to 'obj'

        Args:
            options: 1: recursive, 2: check link array. Options can combine.
            maxCount: to limit the number of links returned.
        """
        ...

    def supportedTypes(self) -> list[str]:
        """
        A list of supported types of objects
        """
        ...

    def getTempFileName(self) -> str:
        """
        Returns a file name with path in the temp directory of the document.
        """
        ...

    def getDependentDocuments(self, sort: bool=True, /) -> list[DocumentObject]:
        """
        Returns a list of documents that this document directly or indirectly links to including itself.

        Args:
            sort: whether to topologically sort the return list
        """
        ...

    def getBookedTransactionID(self) -> int:
        """
        getBookedTransactionID() -> int

        Returns the currently booked transaction id, which is the id of the current transaction OR the id
        the next transaction will stick to if no change has occured yet
        """
        ...

class DocumentObject(ExtensionContainer):
    """
    This is the father of all classes handled by the document
    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    """
    OutList: Final[List['DocumentObject']] = []
    'A list of all objects this object links to.'
    OutListRecursive: Final[List['DocumentObject']] = []
    'A list of all objects this object links to recursively.'
    InList: Final[List['DocumentObject']] = []
    'A list of all objects which link to this object.'
    InListRecursive: Final[List['DocumentObject']] = []
    'A list of all objects which link to this object recursively.'
    FullName: Final[str] = ''
    'Return the document name and internal name of this object'
    Name: Final[Optional[str]] = ''
    'Return the internal name of this object'
    Document: 'Final[FreeCAD.Document]' = ...
    'Return the document this object is part of'
    State: Final[List[Any]] = []
    'State of the object in the document'
    ViewObject: Final[Any] = ...
    '\n    If the GUI is loaded the associated view provider is returned\n    or None if the GUI is not up\n    '
    MustExecute: Final[bool] = False
    'Check if the object must be recomputed'
    ID: Final[int] = 0
    'The unique identifier (among its document) of this object'
    Removing: Final[bool] = False
    'Indicate if the object is being removed'
    Parents: Final[List[Any]] = []
    'A List of tuple(parent,subname) holding all parents to this object'
    OldLabel: Final[str] = ''
    'Contains the old label before change'
    NoTouch: bool = False
    'Enable/disable no touch on any property change'

    def addProperty(self, type: str, name: str, group: str='', doc: str='', attr: int=0, read_only: bool=False, hidden: bool=False, locked: bool=False, enum_vals: list=[]) -> 'DocumentObject':
        """
        Add a generic property.
        """
        ...

    def removeProperty(self, string: str, /) -> None:
        """
        Remove a generic property.

        Note, you can only remove user-defined properties but not built-in ones.
        """
        ...

    def supportedProperties(self) -> list:
        """
        A list of supported property types
        """
        ...

    def touch(self) -> None:
        """
        Mark the object as changed (touched)
        """
        ...

    def purgeTouched(self) -> None:
        """
        Mark the object as unchanged
        """
        ...

    def enforceRecompute(self) -> None:
        """
        Mark the object for recompute
        """
        ...

    def setExpression(self, name: str, expression: str, /) -> None:
        """
        Register an expression for a property
        """
        ...

    def clearExpression(self, name: str, /) -> None:
        """
        Clear the expression for a property
        """
        ...

    @classmethod
    def evalExpression(cls, expression: str, /) -> Any:
        """
        Evaluate an expression
        """
        ...

    def recompute(self, recursive: bool=False, /) -> None:
        """
        Recomputes this object
        """
        ...

    def getStatusString(self) -> str:
        """
        Returns the status of the object as string.
        If the object is invalid its error description will be returned.
        If the object is valid but touched then 'Touched' will be returned,
        'Valid' otherwise.
        """
        ...

    def isValid(self) -> bool:
        """
        Returns True if the object is valid, False otherwise
        """
        ...

    def getSubObject(self, subname: Union[str, List[str], Tuple[str, ...]], *, retType: int=0, matrix: Matrix=None, transform: bool=True, depth: int=0) -> Any:
        """
        * subname(string|list|tuple): dot separated string or sequence of strings
        referencing subobject.

        * retType: return type, 0=PyObject, 1=DocObject, 2=DocAndPyObject, 3=Placement

            PyObject: return a python binding object for the (sub)object referenced in
            each 'subname' The actual type of 'PyObject' is implementation dependent.
            For Part::Feature compatible objects, this will be of type TopoShapePy and
            pre-transformed by accumulated transformation matrix along the object path.

            DocObject:  return the document object referenced in subname, if 'matrix' is
            None. Or, return a tuple (object, matrix) for each 'subname' and 'matrix' is
            the accumulated transformation matrix for the sub object.

            DocAndPyObject: return a tuple (object, matrix, pyobj) for each subname

            Placement: return a transformed placement of the sub-object

        * matrix: the initial transformation to be applied to the sub object.

        * transform: whether to transform the sub object using this object's placement

        * depth: current recursive depth
        """
        ...

    def getSubObjectList(self, subname: str, /) -> list:
        """
        Return a list of objects referenced by a given subname including this object
        """
        ...

    def getSubObjects(self, reason: int=0, /) -> list:
        """
        Return subname reference of all sub-objects
        """
        ...

    def getLinkedObject(self, *, recursive: bool=True, matrix: Matrix=None, transform: bool=True, depth: int=0) -> Any:
        """
        Returns the linked object if there is one, or else return itself

        * recursive: whether to recursively resolve the links

        * transform: whether to transform the sub object using this object's placement

        * matrix: If not none, this specifies the initial transformation to be applied
        to the sub object. And cause the method to return a tuple (object, matrix)
        containing the accumulated transformation matrix

        * depth: current recursive depth
        """
        ...

    def setElementVisible(self, element: str, visible: bool, /) -> int:
        """
        Set the visibility of a child element
        Return -1 if element visibility is not supported, 0 if element not found, 1 if success
        """
        ...

    def isElementVisible(self, element: str, /) -> int:
        """
        Check if a child element is visible
        Return -1 if element visibility is not supported or element not found, 0 if invisible, or else 1
        """
        ...

    def hasChildElement(self) -> bool:
        """
        Return true to indicate the object having child elements
        """
        ...

    def getParentGroup(self) -> DocumentObjectGroup:
        """
        Returns the group the object is in or None if it is not part of a group.

        Note that an object can only be in a single group, hence only a single return value.
        """
        ...

    def getParentGeoFeatureGroup(self) -> Any:
        """
        Returns the GeoFeatureGroup, and hence the local coordinate system, the object
        is in or None if it is not part of a group.

        Note that an object can only be in a single group, hence only a single return value.
        """
        ...

    def getParent(self) -> Any:
        """
        Returns the group the object is in or None if it is not part of a group.

        Note that an object can only be in a single group, hence only a single return value.
        The parent can be a simple group as with getParentGroup() or a GeoFeature group as
        with getParentGeoFeatureGroup().
        """
        ...

    def getPathsByOutList(self) -> list:
        """
        Get all paths from this object to another object following the OutList.
        """
        ...

    def resolve(self, subname: str, /) -> tuple:
        """
        resolve the sub object

        Returns a tuple (subobj,parent,elementName,subElement), where 'subobj' is the
        last object referenced in 'subname', and 'parent' is the direct parent of
        'subobj', and 'elementName' is the name of the subobj, which can be used
        to call parent.isElementVisible/setElementVisible(). 'subElement' is the
        non-object sub-element name if any.
        """
        ...

    def resolveSubElement(self, subname: str, append: bool, type: int, /) -> tuple:
        """
        resolve both new and old style sub element

        subname: subname reference containing object hierarchy
        append: Whether to append object hierarchy prefix inside subname to returned element name
        type: 0: normal, 1: for import, 2: for export

        Return tuple(obj,newElementName,oldElementName)
        """
        ...

    def adjustRelativeLinks(self, parent: DocumentObject, recursive: bool=True, /) -> bool:
        """
        auto correct potential cyclic dependencies
        """
        ...

    def getElementMapVersion(self, property_name: str, /) -> str:
        """
        return element map version of a given geometry property
        """
        ...

    def isAttachedToDocument(self) -> bool:
        """
        Return true if the object is part of a document, false otherwise.
        """
        ...

    def getPlacementOf(self, subname: str, target: DocumentObject=None, /) -> Any:
        """
        Return the placement of the sub-object relative to the link object.
        getPlacementOf(subname, [targetObj]) -> Base.Placement
        """
        ...
    Label: str = ...
    Label2: str = ...

class DocumentObjectExtension(Extension):
    """
    Base class for all document object extensions
    Author: Stefan Troeger (stefantroeger@gmx.net)
    Licence: LGPL
    """
    ...

class DocumentObjectGroup(DocumentObject):
    """
    This class handles document objects in group
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """
    ...

class Extension:
    """
    Base class for all extensions
    Author: Stefan Troeger (stefantroeger@gmx.net)
    Licence: LGPL
    """
    ExtendedObject: Final[Any] = ...
    'Get extended container object'

class ExtensionContainer(PropertyContainer):
    """
    Base class for all objects which can be extended
    Author: Stefan Troeger (stefantroeger@gmx.net)
    Licence: LGPL
    """

    def addExtension(self, identifier: str, /) -> None:
        """
        Adds an extension to the object. Requires the string identifier for the python extension as argument
        """
        ...

    def hasExtension(self, identifier: str, /) -> bool:
        """
        Returns if this object has the specified extension
        """
        ...

class GeoFeature(DocumentObject):
    """
    App.GeoFeature class.

    Base class of all geometric document objects.
    This class does the whole placement and position handling.
    With the method `getPropertyOfGeometry` is possible to obtain
    the main geometric property in general form, without reference
    to any particular property name.
    """
    ElementMapVersion: Final[str] = ''
    'Element map version'

    def getPaths(self) -> Any:
        """
        Returns all possible paths to the root of the document.
        Note: Not implemented.
        """
        ...

    def getGlobalPlacement(self) -> Placement:
        """
        Deprecated: This function does not handle Links correctly. Use getGlobalPlacementOf instead.

        Returns the placement of the object in the global coordinate space, respecting all stacked
        relationships.
        Note: This function is not available during recompute, as there the placements of parents
        can change after the execution of this object, rendering the result wrong.
        """
        ...

    @staticmethod
    def getGlobalPlacementOf(targetObj: Any, rootObj: Any, subname: str, /) -> Placement:
        """
        Examples:
            obj = "part1"
            sub = "linkToPart2.LinkToBody.Pad.face1"

            Global placement of Pad in this context:
            getGlobalPlacementOf(pad, part1, "linkToPart2.LinkToBody.Pad.face1")


            Global placement of linkToPart2 in this context:
            getGlobalPlacementOf(linkToPart2, part1, "linkToPart2.LinkToBody.Pad.face1")

        Returns the placement of the object in the global coordinate space, respecting all stacked
        relationships.
        """
        ...

    def getPropertyNameOfGeometry(self) -> Optional[str]:
        """
        Returns the property name of the actual geometry.
        For example for a Part feature it returns the value 'Shape', for a mesh feature the value
        'Mesh' and so on.
        If an object has no such property then None is returned.
        """
        ...

    def getPropertyOfGeometry(self) -> Optional[Any]:
        """
        Returns the property of the actual geometry.
        For example for a Part feature it returns its Shape property, for a Mesh feature its
        Mesh property and so on.
        If an object has no such property then None is returned.
        Unlike to getPropertyNameOfGeometry this function returns the geometry, not its name.
        """
        ...

class GeoFeatureGroupExtension(GroupExtension):
    """
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    This class handles placeable group of document objects
    """
    ...

class GroupExtension(DocumentObjectExtension):
    """
    Extension class which allows grouping of document objects
    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    """

    def newObject(self, type: str, name: str, /) -> Any:
        """
        Create and add an object with given type and name to the group
        """
        ...

    def addObject(self, obj: Any, /) -> List[Any]:
        """
        Add an object to the group. Returns all objects that have been added.
        """
        ...

    def addObjects(self, objects: List[Any], /) -> List[Any]:
        """
        Adds multiple objects to the group. Expects a list and returns all objects that have been added.
        """
        ...

    def setObjects(self, objects: List[Any], /) -> List[Any]:
        """
        Sets the objects of the group. Expects a list and returns all objects that are now in the group.
        """
        ...

    def removeObject(self, obj: Any, /) -> List[Any]:
        """
        Remove an object from the group and returns all objects that have been removed.
        """
        ...

    def removeObjects(self, objects: List[Any], /) -> List[Any]:
        """
        Remove multiple objects from the group. Expects a list and returns all objects that have been removed.
        """
        ...

    def removeObjectsFromDocument(self) -> None:
        """
        Remove all child objects from the group and document
        """
        ...

    def getObject(self, name: str, /) -> Any:
        """
        Return the object with the given name
        """
        ...

    def getObjectsOfType(self, typename: str, /) -> List[Any]:
        """
        Returns all object in the group of given type
        @param typename     The Freecad type identifier
        """
        ...

    def hasObject(self, obj: Any, recursive: bool=False, /) -> bool:
        """
        Checks if the group has a given object
        @param obj        the object to check for.
        @param recursive  if true check also if the obj is child of some sub group (default is false).
        """
        ...

    def allowObject(self, obj: Any, /) -> bool:
        """
        Returns true if obj is allowed in the group extension.
        """
        ...

class LinkBaseExtension(DocumentObjectExtension):
    """
    Link extension base class
    Author: Zheng, Lei (realthunder.dev@gmail.com)
    Licence: LGPL
    """
    LinkedChildren: Final[List[Any]] = []
    'Return a flattened (in case grouped by plain group) list of linked children'

    def configLinkProperty(self, *args, **kwargs) -> Any:
        """
        Examples:
            Called with default names:
                configLinkProperty(prop1, prop2, ..., propN)
            Called with custom names:
                configLinkProperty(prop1=val1, prop2=val2, ..., propN=valN)

        This method is here to implement what I called Property Design
        Pattern. The extension operates on a predefined set of properties,
        but it relies on the extended object to supply the actual property by
        calling this method. You can choose a sub set of functionality of
        this extension by supplying only some of the supported properties.

        The 'key' are names used to refer to properties supported by this
        extension, and 'val' is the actual name of the property of your
        object. You can obtain the key names and expected types using
        getLinkPropertyInfo().  You can use property of derived type when
        calling configLinkProperty().  Other types will cause exception to
        ben thrown. The actual properties supported may be different
        depending on the actual extension object underlying this python
        object.

        If 'val' is omitted, i.e. calling configLinkProperty(key,...), then
        it is assumed that the actual property name is the same as 'key'
        """
        ...

    def getLinkExtProperty(self, name: str, /) -> Any:
        """
        return the property value by its predefined name
        """
        ...

    def getLinkExtPropertyName(self, name: str, /) -> str:
        """
        lookup the property name by its predefined name
        """
        ...

    @overload
    def getLinkPropertyInfo(self, /) -> tuple[tuple[str, str, str]]:
        ...

    @overload
    def getLinkPropertyInfo(self, index: int, /) -> tuple[str, str, str]:
        ...

    @overload
    def getLinkPropertyInfo(self, name: str, /) -> tuple[str, str]:
        ...

    def getLinkPropertyInfo(self, arg: Any=None, /) -> tuple:
        """
        Overloads:
            (): return (name,type,doc) for all supported properties.
            (index): return (name,type,doc) of a specific property
            (name): return (type,doc) of a specific property
        """
        ...

    def setLink(self, obj: Any, subName: Optional[str]=None, subElements: Optional[Union[str, Tuple[str, ...]]]=None, /) -> None:
        """
        Called with only obj, set link object, otherwise set link element of a link group.

        obj (DocumentObject): the object to link to. If this is None, then the link is cleared

        subName (String): Dot separated object path.

        subElements (String|tuple(String)): non-object sub-elements, e.g. Face1, Edge2.
        """
        ...

    def cacheChildLabel(self, enable: bool=True, /) -> None:
        """
        enable/disable child label cache

        The cache is not updated on child label change for performance reason. You must
        call this function on any child label change
        """
        ...

    def flattenSubname(self, subname: str, /) -> str:
        """
        Return a flattened subname in case it references an object inside a linked plain group
        """
        ...

    def expandSubname(self, subname: str, /) -> str:
        """
        Return an expanded subname in case it references an object inside a linked plain group
        """
        ...

class Material:
    """
    App.Material class.

    Author: Werner Mayer (wmayer@users.sourceforge.net)
    Licence: LGPL
    UserDocu: This is the Material class
    """

    def set(self, string: str, /) -> None:
        """
        Set(string) -- Set the material.

        The material must be one of the following values:
        Brass, Bronze, Copper, Gold, Pewter, Plaster, Plastic, Silver, Steel, Stone, Shiny plastic,
        Satin, Metalized, Neon GNC, Chrome, Aluminium, Obsidian, Neon PHC, Jade, Ruby or Emerald.
        """
        ...
    AmbientColor: Any = ...
    'Ambient color'
    DiffuseColor: Any = ...
    'Diffuse color'
    EmissiveColor: Any = ...
    'Emissive color'
    SpecularColor: Any = ...
    'Specular color'
    Shininess: float = 0.0
    'Shininess'
    Transparency: float = 0.0
    'Transparency'

class MeasureManager:
    """
    MeasureManager class.

    The MeasureManager handles measure types and geometry handler across FreeCAD.

    Author: David Friedli (david@friedli-be.ch)
    Licence: LGPL
    DeveloperDocu: MeasureManager
    """

    @staticmethod
    def addMeasureType(id: str, label: str, measureType: MeasureType, /) -> None:
        """
        Add a new measure type.

        id : str
            Unique identifier of the measure type.
        label : str
            Name of the module.
        measureType : Measure.MeasureBasePython
            The actual measure type.
        """
        ...

    @staticmethod
    def getMeasureTypes() -> List[Tuple[str, str, MeasureType]]:
        """
        Returns a list of all registered measure types.
        """
        ...

class Metadata:
    """
    App.Metadata class.

    A Metadata object reads an XML-formatted package metadata file and provides
    read and write access to its contents.

    The following constructors are supported:

    Metadata()
    Empty constructor.

    Metadata(metadata)
    Copy constructor.
    metadata : App.Metadata

    Metadata(file)
    Reads the XML file and provides access to the metadata it specifies.
    file : str
        XML file name.

    Metadata(bytes)
    Treats the bytes as UTF-8-encoded XML data and provides access to the metadata it specifies.
    bytes : bytes
        Python bytes-like object.

    Author: Chris Hennes (chennes@pioneerlibrarysystem.org)
    Licence: LGPL
    DeveloperDocu: Metadata
    """

    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, metadata: 'Metadata') -> None:
        ...

    @overload
    def __init__(self, file: str) -> None:
        ...

    @overload
    def __init__(self, bytes: bytes) -> None:
        ...
    Name: str = ''
    'String representing the name of this item.'
    Version: str = ''
    'String representing the version of this item in semantic triplet format.'
    Date: str = ''
    'String representing the date of this item in YYYY-MM-DD format (format not currently programmatically enforced)'
    Type: str = ''
    'String representing the type of this item (text only, no markup allowed).'
    Description: str = ''
    'String representing the description of this item (text only, no markup allowed).'
    Maintainer: List[Any] = []
    "List of maintainer objects with 'name' and 'email' string attributes."
    License: List[Any] = []
    "List of applicable licenses as objects with 'name' and 'file' string attributes."
    Urls: List[Any] = []
    "\n    List of URLs as objects with 'location' and 'type' string attributes, where type\n    is one of:\n    * website\n    * repository\n    * bugtracker\n    * readme\n    * documentation\n    "
    Author: List[Any] = []
    "\n    List of author objects, each with a 'name' and a (potentially empty) 'email'\n    string attribute.\n    "
    Depend: List[Any] = []
    "\n    List of dependencies, as objects with the following attributes:\n    * package\n        Required. Must exactly match the contents of the 'name' element in the\n        referenced package's package.xml file.\n    * version_lt\n        Optional. The dependency to the package is restricted to versions less than\n        the stated version number.\n    * version_lte\n        Optional. The dependency to the package is restricted to versions less or\n        equal than the stated version number.\n    * version_eq\n        Optional. The dependency to the package is restricted to a version equal\n        than the stated version number.\n    * version_gte\n        Optional. The dependency to the package is restricted to versions greater\n        or equal than the stated version number.\n    * version_gt\n        Optional. The dependency to the package is restricted to versions greater\n        than the stated version number.\n    * condition\n        Optional. Conditional expression as documented in REP149.\n    "
    Conflict: List[Any] = []
    'List of conflicts, format identical to dependencies.'
    Replace: List[Any] = []
    '\n    List of things this item is considered by its author to replace. The format is\n    identical to dependencies.\n    '
    Tag: List[str] = []
    'List of strings.'
    Icon: str = ''
    'Relative path to an icon file.'
    Classname: str = ''
    '\n    String representing the name of the main Python class this item\n    creates/represents.\n    '
    Subdirectory: str = ''
    '\n    String representing the name of the subdirectory this content item is located in.\n    If empty, the item is in a directory named the same as the content item.\n    '
    File: List[Any] = []
    '\n    List of files associated with this item.\n    The meaning of each file is implementation-defined.\n    '
    Content: Dict[str, List['Metadata']] = {}
    '\n    Dictionary of lists of content items: defined recursively, each item is itself\n    a Metadata object.\n    See package.xml file format documentation for details.\n    '
    FreeCADMin: str = ''
    '\n    String representing the minimum version of FreeCAD needed for this item.\n    If unset it will be 0.0.0.\n    '
    FreeCADMax: str = ''
    '\n    String representing the maximum version of FreeCAD needed for this item.\n    If unset it will be 0.0.0.\n    '
    PythonMin: str = ''
    '\n    String representing the minimum version of Python needed for this item.\n    If unset it will be 0.0.0.\n    '

    def getLastSupportedFreeCADVersion(self) -> Optional[str]:
        """
        Search through all content package items, and determine if a maximum supported
        version of FreeCAD is set.
        Returns None if no maximum version is set, or if *any* content item fails to
        provide a maximum version (implying that that content item will work with all
        known versions).
        """
        ...

    def getFirstSupportedFreeCADVersion(self) -> Optional[str]:
        """
        Search through all content package items, and determine if a minimum supported
        version of FreeCAD is set.
        Returns 0.0 if no minimum version is set, or if *any* content item fails to
        provide a minimum version (implying that that content item will work with all
        known versions. Technically limited to 0.20 as the lowest known version since
        the metadata standard was added then).
        """
        ...

    def supportsCurrentFreeCAD(self) -> bool:
        """
        Returns False if this metadata object directly indicates that it does not
        support the current version of FreeCAD, or True if it makes no indication, or
        specifically indicates that it does support the current version. Does not
        recurse into Content items.
        """
        ...

    def getGenericMetadata(self, name: str, /) -> List[Any]:
        """
        Get the list of GenericMetadata objects with key 'name'.
        Generic metadata objects are Python objects with a string 'contents' and a
        dictionary of strings, 'attributes'. They represent unrecognized simple XML tags
        in the metadata file.
        """
        ...

    def addContentItem(self, content_type: str, metadata: 'Metadata', /) -> None:
        """
        Add a new content item of type 'content_type' with metadata 'metadata'.
        """
        ...

    def removeContentItem(self, content_type: str, name: str, /) -> None:
        """
        Remove the content item of type 'content_type' with name 'name'.
        """
        ...

    def addMaintainer(self, name: str, email: str, /) -> None:
        """
        Add a new Maintainer.
        """
        ...

    def removeMaintainer(self, name: str, email: str, /) -> None:
        """
        Remove the Maintainer.
        """
        ...

    def addLicense(self, short_code: str, path: str, /) -> None:
        """
        Add a new License.
        """
        ...

    def removeLicense(self, short_code: str, /) -> None:
        """
        Remove the License.
        """
        ...

    def addUrl(self, url_type: str, url: str, branch: str, /) -> None:
        """
        Add a new Url or type 'url_type' (which should be one of 'repository', 'readme',

        'bugtracker', 'documentation', or 'webpage') If type is 'repository' you

        must also specify the 'branch' parameter.
        """
        ...

    def removeUrl(self, url_type: str, url: str, /) -> None:
        """
        Remove the Url.
        """
        ...

    def addAuthor(self, name: str, email: str, /) -> None:
        """
        Add a new Author with name 'name', and optionally email 'email'.
        """
        ...

    def removeAuthor(self, name: str, email: str, /) -> None:
        """
        Remove the Author.
        """
        ...

    def addDepend(self, name: str, kind: str, optional: bool, /) -> None:
        """
        Add a new Dependency on package 'name' of kind 'kind' (optional, one of 'auto' (the default),

        'internal', 'addon', or 'python').
        """
        ...

    def removeDepend(self, name: str, kind: str, /) -> None:
        """
        Remove the Dependency on package 'name' of kind 'kind' (optional - if unspecified any

        matching name is removed).
        """
        ...

    def addConflict(self, name: str, kind: str, /) -> None:
        """
        Add a new Conflict. See documentation for addDepend().
        """
        ...

    def removeConflict(self, name: str, kind: str, /) -> None:
        """
        Remove the Conflict. See documentation for removeDepend().
        """
        ...

    def addReplace(self, name: str, /) -> None:
        """
        Add a new Replace.
        """
        ...

    def removeReplace(self, name: str, /) -> None:
        """
        Remove the Replace.
        """
        ...

    def addTag(self, tag: str, /) -> None:
        """
        Add a new Tag.
        """
        ...

    def removeTag(self, tag: str, /) -> None:
        """
        Remove the Tag.
        """
        ...

    def addFile(self, filename: str, /) -> None:
        """
        Add a new File.
        """
        ...

    def removeFile(self, filename: str, /) -> None:
        """
        Remove the File.
        """
        ...

    def write(self, filename: str, /) -> None:
        """
        Write the metadata to the given file as XML data.
        """
        ...

class OriginGroupExtension(GeoFeatureGroupExtension):
    """
    Author: Alexander Golubev (fatzer2@gmail.com)
    Licence: LGPL
    This class handles placable group of document objects with an Origin
    """
    ...

class Part(GeoFeature):
    """
    Author: Juergen Riegel (FreeCAD@juergen-riegel.net)
    Licence: LGPL
    This class handles document objects in Part
    """
    ...

class PropertyContainer(Persistence):
    """
    App.PropertyContainer class.
    """
    PropertiesList: Final[list] = []
    'A list of all property names.'

    def getPropertyByName(self, name: str, checkOwner: int=0, /) -> Any:
        """
        Returns the value of a named property. Note that the returned property may not
        always belong to this container (e.g. from a linked object).

        name : str
            Name of the property.
        checkOwner : int
            0: just return the property.
            1: raise exception if not found or the property does not belong to this container.
            2: return a tuple (owner, propertyValue).
        """
        ...

    def getPropertyTouchList(self, name: str, /) -> tuple:
        """
        Returns a list of index of touched values for list type properties.

        name : str
            Property name.
        """
        ...

    def getTypeOfProperty(self, name: str, /) -> list:
        """
        Returns the type of a named property. This can be a list conformed by elements in
        (Hidden, NoRecompute, NoPersist, Output, ReadOnly, Transient).

        name : str
            Property name.
        """
        ...

    def getTypeIdOfProperty(self, name: str, /) -> str:
        """
        Returns the C++ class name of a named property.

        name : str
            Property name.
        """
        ...

    def setEditorMode(self, name: str, type: Union[int, List[str]], /) -> None:
        """
        Set the behaviour of the property in the property editor.

        name : str
            Property name.
        type : int, sequence of str
            Property type.
            0: default behaviour. 1: item is ready-only. 2: item is hidden. 3: item is hidden and read-only.
            If sequence, the available items are 'ReadOnly' and 'Hidden'.
        """
        ...

    def getEditorMode(self, name: str, /) -> list:
        """
        Get the behaviour of the property in the property editor.
        It returns a list of strings with the current mode. If the list is empty there are no
        special restrictions.
        If the list contains 'ReadOnly' then the item appears in the property editor but is
        disabled.
        If the list contains 'Hidden' then the item even doesn't appear in the property editor.

        name : str
            Property name.
        """
        ...

    def getGroupOfProperty(self, name: str, /) -> str:
        """
        Returns the name of the group which the property belongs to in this class.
        The properties are sorted in different named groups for convenience.

        name : str
            Property name.
        """
        ...

    def setGroupOfProperty(self, name: str, group: str, /) -> None:
        """
        Set the name of the group of a dynamic property.

        name : str
            Property name.
        group : str
            Group name.
        """
        ...

    def setPropertyStatus(self, name: str, val: Union[int, str, List[Union[str, int]]], /) -> None:
        """
        Set property status.

        name : str
            Property name.
        val : int, str, sequence of str or int
            Call getPropertyStatus() to get a list of supported text value.
            If the text start with '-' or the integer value is negative, then the status is cleared.
        """
        ...

    def getPropertyStatus(self, name: str='', /) -> list:
        """
        Get property status.

        name : str
            Property name. If empty, returns a list of supported text names of the status.
        """
        ...

    def getDocumentationOfProperty(self, name: str, /) -> str:
        """
        Returns the documentation string of the property of this class.

        name : str
            Property name.
        """
        ...

    def setDocumentationOfProperty(self, name: str, docstring: str, /) -> None:
        """
        Set the documentation string of a dynamic property of this class.

        name : str
            Property name.
        docstring : str
            Documentation string.
        """
        ...

    def getEnumerationsOfProperty(self, name: str, /) -> Optional[list]:
        """
        Return all enumeration strings of the property of this class or None if not a
        PropertyEnumeration.

        name : str
            Property name.
        """
        ...

    def dumpPropertyContent(self, Property: str, *, Compression: int=3) -> bytearray:
        """
        Dumps the content of the property, both the XML representation and the additional
        data files required, into a byte representation.

        Property : str
            Property Name.
        Compression : int
            Set the data compression level in the range [0, 9]. Set to 0 for no compression.
        """
        ...

    def restorePropertyContent(self, name: str, obj: object, /) -> None:
        """
        Restore the content of the object from a byte representation as stored by `dumpPropertyContent`.
        It could be restored from any Python object implementing the buffer protocol.

        name : str
            Property name.
        obj : buffer
            Object with buffer protocol support.
        """
        ...

    def renameProperty(self, oldName: str, newName: str, /) -> None:
        """
        Rename a property.

        oldName : str
            Old property name.
        newName : str
            New property name.
        """
        ...

class StringHasher(BaseClass):
    """
    This is the StringHasher class

    Author: Zheng, Lei (realthunder.dev@gmail.com)
    Licence: LGPL
    """

    @overload
    def getID(self, txt: str, base64: bool=False, /) -> Any:
        ...

    @overload
    def getID(self, id: int, base64: bool=False, /) -> Any:
        ...

    def getID(self, arg: Any, base64: bool=False, /) -> Any:
        """
        If the input is text, return a StringID object that is unique within this hasher. This
        StringID object is reference counted. The hasher may only save hash ID's that are used.

        If the input is an integer, then the hasher will try to find the StringID object stored
        with the same integer value.

        base64: indicate if the input 'txt' is base64 encoded binary data
        """
        ...

    def isSame(self, other: 'StringHasher', /) -> bool:
        """
        Check if two hasher are the same
        """
        ...
    Count: Final[int] = 0
    'Return count of used hashes'
    Size: Final[int] = 0
    'Return the size of the hashes'
    SaveAll: bool = False
    'Whether to save all string hashes regardless of its use count'
    Threshold: int = 0
    'Data length exceed this threshold will be hashed before storing'
    Table: Final[Dict[int, str]] = {}
    'Return the entire string table as Int->String dictionary'

class StringID(BaseClass):
    """
    This is the StringID class

    Author: Zheng, Lei (realthunder.dev@gmail.com)
    Licence: LGPL
    """

    def isSame(self, other: 'StringID', /) -> bool:
        """
        Check if two StringIDs are the same
        """
        ...
    Value: Final[int] = 0
    'Return the integer value of this ID'
    Related: Final[List[Any]] = []
    'Return the related string IDs'
    Data: Final[str] = ''
    'Return the data associated with this ID'
    IsBinary: Final[bool] = False
    'Check if the data is binary,'
    IsHashed: Final[bool] = False
    "Check if the data is hash, if so 'Data' returns a base64 encoded string of the raw hash"
    Index: int = 0
    'Geometry index. Only meaningful for geometry element name'

class SuppressibleExtension(DocumentObjectExtension):
    """
    Author: Florian Foinant-Willig (flachyjoe@users.sourceforge.net)
    Licence: LGPL
    Extension class which allows suppressing of document objects
    """
    ...

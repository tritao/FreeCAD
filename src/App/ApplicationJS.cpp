/***************************************************************************
 *   Copyright (c) 2002 Jürgen Riegel <juergen.riegel@web.de>              *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Library General Public License (LGPL)   *
 *   as published by the Free Software Foundation; either version 2 of     *
 *   the License, or (at your option) any later version.                   *
 *   for detail see the LICENCE text file.                                 *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful,            *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with FreeCAD; if not, write to the Free Software        *
 *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
 *   USA                                                                   *
 *                                                                         *
 ***************************************************************************/


#include "PreCompiled.h"

#include <Base/VectorJS.h>
#include <App/Application.h>
#include <App/DocumentJS.h>

#include <emscripten.h>
#include <emscripten/bind.h>

using namespace Base;
using namespace App;

static EMSCRIPTEN_KEEPALIVE void embind_init()
{
    printf("embind_init");
    embind_init_base_vector();
    embind_init_app_document();
}

static struct EmBindInit : emscripten::internal::InitFunc {
    EmBindInit() : InitFunc(embind_init) {}
} EmBindInit_instance;


//**************************************************************************
// JS stuff

// Application methods structure
//PyMethodDef Application::Methods[] = {
//    {"ParamGet",       (PyCFunction) Application::sGetParam, METH_VARARGS,
//     "Get parameters by path"},
//    {"saveParameter",  (PyCFunction) Application::sSaveParameter, METH_VARARGS,
//     "saveParameter(config='User parameter') -> None\n"
//     "Save parameter set to file. The default set is 'User parameter'"},
//    {"Version",        (PyCFunction) Application::sGetVersion, METH_VARARGS,
//     "Print the version to the output."},
//    {"ConfigGet",      (PyCFunction) Application::sGetConfig, METH_VARARGS,
//     "ConfigGet(string) -- Get the value for the given key."},
//    {"ConfigSet",      (PyCFunction) Application::sSetConfig, METH_VARARGS,
//     "ConfigSet(string, string) -- Set the given key to the given value."},
//    {"ConfigDump",     (PyCFunction) Application::sDumpConfig, METH_VARARGS,
//     "Dump the configuration to the output."},
//    {"addImportType",  (PyCFunction) Application::sAddImportType, METH_VARARGS,
//     "Register filetype for import"},
//    {"changeImportModule",  (PyCFunction) Application::sChangeImportModule, METH_VARARGS,
//     "Change the import module name of a registered filetype"},
//    {"getImportType",  (PyCFunction) Application::sGetImportType, METH_VARARGS,
//     "Get the name of the module that can import the filetype"},
//    {"addExportType",  (PyCFunction) Application::sAddExportType, METH_VARARGS,
//     "Register filetype for export"},
//    {"changeExportModule",  (PyCFunction) Application::sChangeExportModule, METH_VARARGS,
//     "Change the export module name of a registered filetype"},
//    {"getExportType",  (PyCFunction) Application::sGetExportType, METH_VARARGS,
//     "Get the name of the module that can export the filetype"},
//    {"getResourceDir", (PyCFunction) Application::sGetResourcePath, METH_VARARGS,
//     "Get the root directory of all resources"},
//    {"getLibraryDir", (PyCFunction) Application::sGetLibraryPath, METH_VARARGS,
//     "Get the directory of all extension modules"},
//    {"getTempPath", (PyCFunction) Application::sGetTempPath, METH_VARARGS,
//     "Get the root directory of cached files"},
//    {"getUserCachePath", (PyCFunction) Application::sGetUserCachePath, METH_VARARGS,
//     "Get the root path of cached files"},
//    {"getUserConfigDir", (PyCFunction) Application::sGetUserConfigPath, METH_VARARGS,
//     "Get the root path of user config files"},
//    {"getUserAppDataDir", (PyCFunction) Application::sGetUserAppDataPath, METH_VARARGS,
//     "Get the root directory of application data"},
//    {"getUserMacroDir", (PyCFunction) Application::sGetUserMacroPath, METH_VARARGS,
//     "getUserMacroDir(bool=False) -> string"
//     "Get the directory of the user's macro directory\n"
//     "If parameter is False (the default) it returns the standard path in the"
//     "user's home directory, otherwise it returns the user-defined path."},
//    {"getHelpDir", (PyCFunction) Application::sGetHelpPath, METH_VARARGS,
//     "Get the directory of the documentation"},
//    {"getHomePath",    (PyCFunction) Application::sGetHomePath, METH_VARARGS,
//     "Get the home path, i.e. the parent directory of the executable"},
//
//    {"loadFile",       (PyCFunction) Application::sLoadFile, METH_VARARGS,
//     "loadFile(string=filename,[string=module]) -> None\n\n"
//     "Loads an arbitrary file by delegating to the given Python module:\n"
//     "* If no module is given it will be determined by the file extension.\n"
//     "* If more than one module can load a file the first one will be taken.\n"
//     "* If no module exists to load the file an exception will be raised."},
//    {"open",   reinterpret_cast<PyCFunction>(reinterpret_cast<void (*) ()>( Application::sOpenDocument )), METH_VARARGS|METH_KEYWORDS,
//     "See openDocument(string)"},
//    {"openDocument",   reinterpret_cast<PyCFunction>(reinterpret_cast<void (*) ()>( Application::sOpenDocument )), METH_VARARGS|METH_KEYWORDS,
//     "openDocument(filepath,hidden=False) -> object\n"
//     "Create a document and load the project file into the document.\n\n"
//     "filepath: file path to an existing file. If the file doesn't exist\n"
//     "          or the file cannot be loaded an I/O exception is thrown.\n"
//     "          In this case the document is kept alive.\n"
//     "hidden: whether to hide document 3D view."},
////  {"saveDocument",   (PyCFunction) Application::sSaveDocument, METH_VARARGS,
////   "saveDocument(string) -- Save the document to a file."},
////  {"saveDocumentAs", (PyCFunction) Application::sSaveDocumentAs, METH_VARARGS},
//    {"newDocument",    reinterpret_cast<PyCFunction>(reinterpret_cast<void (*) ()>( Application::sNewDocument )), METH_VARARGS|METH_KEYWORDS,
//     "newDocument(name, label=None, hidden=False, temp=False) -> object\n"
//     "Create a new document with a given name.\n\n"
//     "name: unique document name which is checked automatically.\n"
//     "label: optional user changeable label for the document.\n"
//     "hidden: whether to hide document 3D view.\n"
//     "temp: mark the document as temporary so that it will not be saved"},
//    {"closeDocument",  (PyCFunction) Application::sCloseDocument, METH_VARARGS,
//     "closeDocument(string) -> None\n\n"
//     "Close the document with a given name."},
//    {"activeDocument", (PyCFunction) Application::sActiveDocument, METH_VARARGS,
//     "activeDocument() -> object or None\n\n"
//     "Return the active document or None if there is no one."},
//    {"setActiveDocument", (PyCFunction) Application::sSetActiveDocument, METH_VARARGS,
//     "setActiveDocement(string) -> None\n\n"
//     "Set the active document by its name."},
//    {"getDocument",    (PyCFunction) Application::sGetDocument, METH_VARARGS,
//     "getDocument(string) -> object\n\n"
//     "Get a document by its name or raise an exception\n"
//     "if there is no document with the given name."},
//    {"listDocuments",  (PyCFunction) Application::sListDocuments, METH_VARARGS,
//     "listDocuments(sort=False) -> list\n\n"
//     "Return a list of names of all documents, optionally sort in dependency order."},
//    {"addDocumentObserver",  (PyCFunction) Application::sAddDocObserver, METH_VARARGS,
//     "addDocumentObserver() -> None\n\n"
//     "Add an observer to get notified about changes on documents."},
//    {"removeDocumentObserver",  (PyCFunction) Application::sRemoveDocObserver, METH_VARARGS,
//     "removeDocumentObserver() -> None\n\n"
//     "Remove an added document observer."},
//    {"setLogLevel",          (PyCFunction) Application::sSetLogLevel, METH_VARARGS,
//     "setLogLevel(tag, level) -- Set the log level for a string tag.\n"
//     "'level' can either be string 'Log', 'Msg', 'Wrn', 'Error', or an integer value"},
//    {"getLogLevel",          (PyCFunction) Application::sGetLogLevel, METH_VARARGS,
//     "getLogLevel(tag) -- Get the log level of a string tag"},
//    {"checkLinkDepth",       (PyCFunction) Application::sCheckLinkDepth, METH_VARARGS,
//     "checkLinkDepth(depth) -- check link recursion depth"},
//    {"getLinksTo",       (PyCFunction) Application::sGetLinksTo, METH_VARARGS,
//     "getLinksTo(obj,options=0,maxCount=0) -- return the objects linked to 'obj'\n\n"
//     "options: 1: recursive, 2: check link array. Options can combine.\n"
//     "maxCount: to limit the number of links returned\n"},
//    {"getDependentObjects", (PyCFunction) Application::sGetDependentObjects, METH_VARARGS,
//     "getDependentObjects(obj|[obj,...], options=0)\n"
//     "Return a list of dependent objects including the given objects.\n\n"
//     "options: can have the following bit flags,\n"
//     "         1: to sort the list in topological order.\n"
//     "         2: to exclude dependency of Link type object."},
//    {"setActiveTransaction", (PyCFunction) Application::sSetActiveTransaction, METH_VARARGS,
//     "setActiveTransaction(name, persist=False) -- setup active transaction with the given name\n\n"
//     "name: the transaction name\n"
//     "persist(False): by default, if the calling code is inside any invocation of a command, it\n"
//     "                will be auto closed once all commands within the current stack exists. To\n"
//     "                disable auto closing, set persist=True\n"
//     "Returns the transaction ID for the active transaction. An application-wide\n"
//     "active transaction causes any document changes to open a transaction with\n"
//     "the given name and ID."},
//    {"getActiveTransaction", (PyCFunction) Application::sGetActiveTransaction, METH_VARARGS,
//     "getActiveTransaction() -> (name,id) return the current active transaction name and ID"},
//    {"closeActiveTransaction", (PyCFunction) Application::sCloseActiveTransaction, METH_VARARGS,
//     "closeActiveTransaction(abort=False) -- commit or abort current active transaction"},
//    {"isRestoring", (PyCFunction) Application::sIsRestoring, METH_VARARGS,
//     "isRestoring() -> Bool -- Test if the application is opening some document"},
//    {"checkAbort", (PyCFunction) Application::sCheckAbort, METH_VARARGS,
//     "checkAbort() -- check for user abort in length operation.\n\n"
//     "This only works if there is an active sequencer (or ProgressIndicator in Python).\n"
//     "There is an active sequencer during document restore and recomputation. User may\n"
//     "abort the operation by pressing the ESC key. Once detected, this function will\n"
//     "trigger a Base.FreeCADAbort exception."},
//    {nullptr, nullptr, 0, nullptr} /* Sentinel */
//};




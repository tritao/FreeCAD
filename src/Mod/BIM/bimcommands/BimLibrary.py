# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2018 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function

"""The BIM library tool"""

import html
import json
import os
import sys
import tempfile

import FreeCAD
import FreeCADGui

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")

FILTERS = [
    "*.fcstd",
    "*.FCStd",
    "*.FCSTD",
    "*.stp",
    "*.STP",
    "*.step",
    "*.STEP",
    "*.brp",
    "*.BRP",
    "*.brep",
    "*.BREP",
    "*.ifc",
    "*.IFC",
    "*.sat",
    "*.SAT",
]
LOCAL_IMPORT_EXTENSIONS = {os.path.splitext(f)[1].lower() for f in FILTERS}
ONLINE_IMPORT_EXTENSIONS = {
    ext for ext in LOCAL_IMPORT_EXTENSIONS if ext not in {".brp", ".brep", ".ifc", ".sat", ".sab"}
}
TEMPLIBPATH = os.path.join(FreeCAD.getUserAppDataDir(), "BIM", "OfflineLibrary")
THUMBNAILSPATH = os.path.join(TEMPLIBPATH, "__thumbcache__")
LIBRARYURL = "https://github.com/FreeCAD/FreeCAD-library/tree/master"
RAWURL = LIBRARYURL.replace("/tree", "/raw")
LIBINDEXFILE = "OfflineLibrary.py"
USE_API = True  # True to use github API instead of web fetching... Way faster
REFRESH_INTERVAL = 3600  # Min seconds between allowing a new API calls (3600 = one hour)
SYMBOL_DEFINITIONS_GROUP = "_SymbolDefinitions"
SYMBOL_LIBRARY_GROUP = "Library"
ASSET_MANIFEST = "asset.json"
LIBRARY_MARKER_FILES = (".freecad-library", "library.json")


# TODO as https://github.com/yorikvanhavre/BIM_Workbench/pull/77

# All the print() statements in your code should be replaced by
# FreeCAD.Console.PrintMessage() or FreeCAD.Console.PrintWarning() or
# FreeCAD.Console.PrintError() and the text should be placed in a translate()
# function and "\n" should be added to it.
# Example FreeCAD.Console.PrintError(translate("BIM","Please save the document first")+"\n")

# It would be cool if the preview image would have a max width of the available
# column width, so if the task column is smaller than the image, it gets smaller
# to fit the space. I don't remember exactly how to do that, but it should be
# findable in QDesigner


def _normalize_library_root(path):

    if not path:
        return ""
    return os.path.normpath(path).replace("\\", "/")


def _get_configured_library_root():

    pr = FreeCAD.ParamGet("User parameter:Plugins/parts_library")
    path = pr.GetString("destination", "")
    if path and os.path.exists(path):
        return _normalize_library_root(path)
    return ""


def _normalize_asset_kind(kind):

    key = "".join(char.lower() for char in str(kind or "") if char.isalnum())
    if key in {"equipment", "furniture", "furnishingelement", "furnishing"}:
        return "equipment"
    return key


def _coerce_asset_vector(value):

    if isinstance(value, FreeCAD.Vector):
        return FreeCAD.Vector(value.x, value.y, value.z)
    if isinstance(value, dict):
        try:
            return FreeCAD.Vector(
                float(value.get("x", 0.0)),
                float(value.get("y", 0.0)),
                float(value.get("z", 0.0)),
            )
        except Exception:
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return FreeCAD.Vector(
                float(value[0]),
                float(value[1]),
                float(value[2]) if len(value) > 2 else 0.0,
            )
        except Exception:
            return None
    if isinstance(value, str):
        try:
            parts = [float(part.strip()) for part in value.split(",")]
        except Exception:
            return None
        if len(parts) >= 2:
            return FreeCAD.Vector(parts[0], parts[1], parts[2] if len(parts) > 2 else 0.0)
    return None


def _iter_module_search_roots():

    seen = set()
    additional_paths = FreeCAD.ConfigGet("AdditionalModulePaths") or ""
    for raw_path in additional_paths.split(";"):
        raw_path = raw_path.strip()
        if not raw_path:
            continue
        path = _normalize_library_root(raw_path)
        if path and path not in seen and os.path.isdir(path):
            seen.add(path)
            yield path

    for raw_path in sys.path:
        if not raw_path:
            continue
        path = _normalize_library_root(raw_path)
        if path and path not in seen and os.path.isdir(path):
            seen.add(path)
            yield path


def _find_marked_library_root(module_root):

    candidates = [
        module_root,
        os.path.join(module_root, "Library"),
    ]
    for candidate in candidates:
        if not os.path.isdir(candidate):
            continue
        for marker in LIBRARY_MARKER_FILES:
            if os.path.isfile(os.path.join(candidate, marker)):
                return _normalize_library_root(candidate)
    return ""


def resolve_library_root_info():

    configured = _get_configured_library_root()
    if configured:
        return configured, "configured"

    for module_root in _iter_module_search_roots():
        discovered = _find_marked_library_root(module_root)
        if discovered:
            return discovered, "module_marker"

    addondir = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "parts_library")
    if os.path.exists(addondir):
        return _normalize_library_root(addondir), "legacy_fallback"
    return "", "none"


def resolve_library_root():

    return resolve_library_root_info()[0]


class BIM_Library:

    def GetResources(self):
        return {
            "Pixmap": "BIM_Library",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Library", "BIM Library"),
            "ToolTip": QT_TRANSLATE_NOOP("BIM_Library", "Opens the BIM library"),
        }

    def Activated(self):

        self.librarypath, self.librarysource = resolve_library_root_info()
        target_gui_doc = getattr(FreeCADGui, "ActiveDocument", None)
        target_doc_name = ""
        if target_gui_doc and getattr(target_gui_doc, "Document", None):
            target_doc_name = target_gui_doc.Document.Name
        panel = BIM_Library_TaskPanel(
            offlinemode=bool(self.librarypath),
            librarypath=self.librarypath,
            librarysource=self.librarysource,
            target_doc_name=target_doc_name,
        )
        task = FreeCADGui.Control.showDialog(panel, target_gui_doc)
        task.setDocumentName(panel.mainDocName)
        task.setAutoCloseOnDeletedDocument(True)


class BIM_Library_TaskPanel:

    def __init__(self, offlinemode=False, librarypath="", librarysource="", target_doc_name=""):

        from PySide import QtCore, QtGui

        if target_doc_name:
            self.mainDocName = target_doc_name
        else:
            self.mainDocName = FreeCAD.Gui.ActiveDocument.Document.Name
        self.previewDocName = "Viewer"

        self.linked = False
        self.instance_definition_roots = []
        self._local_search_index = None
        self._local_search_index_root = None

        resolved_path, resolved_source = resolve_library_root_info()
        self.librarypath = librarypath or resolved_path
        if librarysource:
            self.librarysource = librarysource
        elif self.librarypath == resolved_path:
            self.librarysource = resolved_source
        elif self.librarypath:
            self.librarysource = "provided"
        else:
            self.librarysource = "none"
        self.form = FreeCADGui.PySideUic.loadUi(":/ui/dialogLibrary.ui")
        self.form.setWindowIcon(QtGui.QIcon(":/icons/BIM_Library.svg"))
        self.form.labelLibraryRootStatus = QtGui.QLabel(self.form)
        self.form.labelLibraryRootStatus.setObjectName("labelLibraryRootStatus")
        self.form.labelLibraryRootStatus.setWordWrap(True)
        self.form.labelLibraryRootStatus.setTextFormat(QtCore.Qt.RichText)
        self.form.labelLibraryRootStatus.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.form.verticalLayout.insertWidget(0, self.form.labelLibraryRootStatus)
        self.form.labelLibraryModeStatus = QtGui.QLabel(self.form)
        self.form.labelLibraryModeStatus.setObjectName("labelLibraryModeStatus")
        self.form.labelLibraryModeStatus.setWordWrap(True)
        self.form.labelLibraryModeStatus.hide()
        self.form.verticalLayout.insertWidget(1, self.form.labelLibraryModeStatus)
        self.form.previewDetails = QtGui.QFrame(self.form)
        self.form.previewDetails.setObjectName("previewDetails")
        self.form.previewDetailsLayout = QtGui.QVBoxLayout(self.form.previewDetails)
        self.form.previewDetailsLayout.setContentsMargins(0, 0, 0, 0)
        self.form.previewTitle = QtGui.QLabel(self.form.previewDetails)
        self.form.previewTitle.setObjectName("previewTitle")
        self.form.previewTitle.setWordWrap(True)
        self.form.previewTitle.setTextFormat(QtCore.Qt.RichText)
        self.form.previewMeta = QtGui.QLabel(self.form.previewDetails)
        self.form.previewMeta.setObjectName("previewMeta")
        self.form.previewMeta.setWordWrap(True)
        self.form.previewMeta.setTextFormat(QtCore.Qt.RichText)
        self.form.previewMeta.setStyleSheet("color: #666;")
        self.form.previewSummary = QtGui.QLabel(self.form.previewDetails)
        self.form.previewSummary.setObjectName("previewSummary")
        self.form.previewSummary.setWordWrap(True)
        self.form.previewSummary.setTextFormat(QtCore.Qt.PlainText)
        self.form.previewSummary.setStyleSheet("color: #444;")
        self.form.previewSummary.hide()
        self.form.previewDetailsLayout.addWidget(self.form.previewTitle)
        self.form.previewDetailsLayout.addWidget(self.form.previewMeta)
        self.form.previewDetailsLayout.addWidget(self.form.previewSummary)
        preview_index = self.form.verticalLayout.indexOf(self.form.framePreview)
        self.form.verticalLayout.insertWidget(preview_index + 1, self.form.previewDetails)
        self.form.previewDetails.hide()
        self._update_library_root_status()
        self._tree_item_kind_role = QtCore.Qt.UserRole + 1
        self._tree_item_loaded_role = QtCore.Qt.UserRole + 2

        # setting up a flat (no directories) file model for search
        self.filemodel = QtGui.QStandardItemModel()
        self.filemodel.setColumnCount(1)
        self.form.buttonInsert.clicked.connect(self.insert)
        self.form.buttonLink.clicked.connect(self.link)
        self.form.label_3.hide()
        self.form.horizontalLayout_4.removeWidget(self.form.buttonLink)
        self.form.horizontalLayout_4.removeWidget(self.form.buttonInsert)
        self.form.horizontalLayout_4.insertWidget(0, self.form.buttonLink)
        self.form.horizontalLayout_4.insertWidget(1, self.form.buttonInsert)
        self.form.buttonInsert.setText(translate("BIM", "Insert Copy"))
        self.form.buttonInsert.setToolTip(
            translate(
                "BIM", "Imports the selected object as regular geometry in the current document"
            )
        )
        self.form.buttonLink.setText(translate("BIM", "Insert Instance"))
        self.form.buttonLink.setToolTip(
            translate(
                "BIM",
                "Creates or reuses a hidden local symbol definition and inserts visible App::Link instances",
            )
        )
        self.form.buttonLink.setDefault(True)
        self.form.buttonLink.setAutoDefault(True)
        self.form.buttonLink.setStyleSheet("font-weight: 600;")
        self.form.buttonInsert.setStyleSheet("font-weight: 500;")

        self.modelmode = 0
        self._set_tree_model(self.filemodel)
        self.form.tree.expanded.connect(self.onTreeExpanded)
        self.form.tree.doubleClicked.connect(self.onTreeDoubleClicked)

        # Don't show columns for size, file type, and last modified
        self.form.tree.setHeaderHidden(True)
        self.form.tree.setUniformRowHeights(True)
        self.form.tree.setExpandsOnDoubleClick(False)
        self.form.tree.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.form.tree.hideColumn(1)
        self.form.tree.hideColumn(2)
        self.form.tree.hideColumn(3)
        self.form.searchBox.textChanged.connect(self.onSearch)
        self.form.searchBox.setPlaceholderText(translate("BIM", "Search local assets"))
        self.form.comboSearch.setToolTip(translate("BIM", "Search external asset websites"))
        self.form.comboSearch.setMinimumContentsLength(10)
        self.form.comboSearch.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.form.comboSearch.setMaximumWidth(140)

        # external search
        sites = {
            "BimObject": [
                "bimobject.png",
                "https://www.bimobject.com/en/product?filetype=8&freetext=",
            ],
            "NBS Library": [
                "nbslibrary.png",
                "https://www.nationalbimlibrary.com/en/search/?facet=Xo-P0w&searchTerm=",
            ],
            "BIMTool": [
                "bimtool.png",
                "https://www.bimtool.com/Catalog.aspx?criterio=",
            ],
            "3DFindIt": ["3dfindit.svg", "https://www.3dfindit.com/textsearch?q="],
            "GrabCAD": [
                "grabcad.svg",
                "https://grabcad.com/library?softwares=step-slash-iges&query=",
            ],
        }
        self.form.comboSearch.setItemText(0, translate("BIM", "Search Web"))
        for k, v in sites.items():
            self.form.comboSearch.addItem(QtGui.QIcon(":/icons/" + v[0]), k, v[1])
        self.form.comboSearch.currentIndexChanged.connect(self.onExternalSearch)

        # retrieve preferences
        self.form.checkOnline.toggled.connect(self.onCheckOnline)
        self.form.checkOnline.setText(translate("BIM", "Online catalog"))
        self.form.checkOnline.setToolTip(
            translate(
                "BIM",
                "Shows the online catalog instead of the local library. When enabled, local assets are hidden from the tree.",
            )
        )
        mode_chosen = PARAMS.GetBool("LibraryModeChosen", False)
        initial_online = PARAMS.GetBool("LibraryOnline", not offlinemode)
        if not mode_chosen:
            initial_online = False if self.librarypath else True
        if not self.librarypath:
            initial_online = True
        self.form.checkOnline.setChecked(initial_online)
        self.form.checkFCStdOnly.toggled.connect(self.onCheckFCStdOnly)
        self.form.checkFCStdOnly.setText(translate("BIM", "Alternative formats"))
        self.form.checkFCStdOnly.setToolTip(
            translate(
                "BIM",
                "Show available alternative file formats for library items such as STEP and IFC.",
            )
            + "\n\n"
            + translate(
                "BIM",
                "STEP and BREP files can be placed at a custom location. FCStd and IFC files are placed where objects are defined in the file.",
            )
        )
        self.form.checkFCStdOnly.setChecked(PARAMS.GetBool("LibraryFCStdOnly", False))

        # collapsables
        if PARAMS.GetBool("LibraryPreview", False):
            self.form.framePreview.show()
            self.form.buttonPreview.setText(translate("BIM", "Preview") + " ▼")
        else:
            self.form.framePreview.hide()
            self.form.buttonPreview.setText(translate("BIM", "Preview") + " ▸")
        self.form.buttonPreview.clicked.connect(self.onButtonPreview)

        # update the tree
        self.onCheckOnline()

    def _get_library_source_label(self):

        labels = {
            "configured": translate("BIM", "Configured"),
            "module_marker": translate("BIM", "Module"),
            "legacy_fallback": translate("BIM", "Legacy"),
            "provided": translate("BIM", "Custom"),
            "none": translate("BIM", "Not found"),
        }
        return labels.get(self.librarysource, self.librarysource or translate("BIM", "Unknown"))

    def _get_library_display_path(self):

        if not self.librarypath:
            return ""
        parts = [part for part in self.librarypath.replace("\\", "/").split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[-2:])
        if parts:
            return parts[-1]
        return self.librarypath

    def _update_library_root_status(self):

        if self.librarypath:
            path_text = self._get_library_display_path()
            tooltip = self.librarypath
            text = (
                "<b>{}</b> · {} "
                '<span style="color:#555; background:#f0f0f0; '
                'border:1px solid #d8d8d8; border-radius:6px; padding:1px 6px;">{}</span>'
            ).format(
                html.escape(translate("BIM", "Local Library")),
                html.escape(path_text),
                html.escape(self._get_library_source_label()),
            )
        else:
            tooltip = translate(
                "BIM",
                "Set a library folder explicitly or mount a marked module library root.",
            )
            text = "<b>{}</b>".format(html.escape(translate("BIM", "No local library detected")))
        self.form.labelLibraryRootStatus.setText(text)
        self.form.labelLibraryRootStatus.setToolTip(tooltip)

    def _update_library_mode_status(self, online_mode):

        label = self.form.labelLibraryModeStatus
        if online_mode and self.librarypath:
            label.setText(
                translate(
                    "BIM",
                    "Showing online catalog. Local library content is hidden in this mode.",
                )
            )
            label.setToolTip(self.librarypath)
            label.show()
            return
        if (not online_mode) and (not self.librarypath):
            label.setText(
                translate(
                    "BIM",
                    "No local library detected. Configure a library folder or use the online catalog.",
                )
            )
            label.setToolTip(
                translate(
                    "BIM",
                    "Set a local library root explicitly or mount a marked module library root.",
                )
            )
            label.show()
            return
        label.clear()
        label.hide()

    def _set_tree_model(self, model):

        selection_model = self.form.tree.selectionModel()
        if selection_model:
            try:
                selection_model.selectionChanged.disconnect(self.onItemSelected)
            except Exception:
                pass
        self.form.tree.setModel(model)
        selection_model = self.form.tree.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.onItemSelected)

    def _create_tree_folder_item(self, label, folder_path):

        from PySide import QtGui

        item = QtGui.QStandardItem(label)
        item.setEditable(False)
        item.setToolTip(folder_path)
        item.setIcon(QtGui.QIcon.fromTheme("folder", QtGui.QIcon(":/icons/Group.svg")))
        item.setData("folder", self._tree_item_kind_role)
        item.setData(False, self._tree_item_loaded_role)
        placeholder = QtGui.QStandardItem("")
        placeholder.setEditable(False)
        item.appendRow(placeholder)
        return item

    def _populate_local_folder_item(self, root_item, folder_path):

        from PySide import QtGui

        root_item.removeRows(0, root_item.rowCount())
        try:
            names = sorted(os.listdir(folder_path))
        except OSError:
            if isinstance(root_item, QtGui.QStandardItem):
                root_item.setData(True, self._tree_item_loaded_role)
            return

        for name in names:
            path = os.path.join(folder_path, name)
            if os.path.isdir(path):
                manifest_path = os.path.join(path, ASSET_MANIFEST)
                if os.path.isfile(manifest_path):
                    label = self._get_asset_label(manifest_path)
                    item = QtGui.QStandardItem(label)
                    item.setEditable(False)
                    item.setToolTip(manifest_path)
                    item.setIcon(self._get_leaf_icon(label, manifest_path))
                    root_item.appendRow(item)
                    continue
                if not self._folder_contains_browsable_content(path):
                    continue
                folder_item = self._create_tree_folder_item(name, path)
                root_item.appendRow(folder_item)
                if root_item is self.filemodel:
                    self._populate_local_folder_item(folder_item, path)
                continue
            if os.path.isfile(path) and self.isAllowed(name):
                item = QtGui.QStandardItem(name)
                item.setEditable(False)
                item.setToolTip(path)
                item.setIcon(self._get_leaf_icon(name, path))
                root_item.appendRow(item)

        if isinstance(root_item, QtGui.QStandardItem):
            root_item.setData(True, self._tree_item_loaded_role)

    def _populate_local_root_model(self):

        self.filemodel.clear()
        self._populate_local_folder_item(self.filemodel, self.librarypath)

    def onTreeExpanded(self, index):

        if self.form.checkOnline.isChecked():
            return
        if self.form.searchBox.text():
            return
        item = self.filemodel.itemFromIndex(index)
        if not item:
            return
        if item.data(self._tree_item_kind_role) != "folder":
            return
        if item.data(self._tree_item_loaded_role):
            return
        self._populate_local_folder_item(item, item.toolTip())

    def onTreeDoubleClicked(self, index):

        item = self.filemodel.itemFromIndex(index)
        if not item:
            return
        if item.data(self._tree_item_kind_role) == "folder":
            self.form.tree.setExpanded(index, not self.form.tree.isExpanded(index))
            return
        self.link(index)

    def onItemSelected(self, selected, deselected):
        """Generates and displays needed previews"""

        from PySide import QtGui

        if not selected:
            return
        index = selected[0].indexes()[0]
        raw_path = self.filemodel.itemFromIndex(index).toolTip()
        metadata = self._get_preview_metadata(raw_path)
        path = self._resolve_asset_path(raw_path)
        thumb = self.getThumbnail(raw_path)
        if thumb:
            px = QtGui.QPixmap(thumb)
        else:
            px = QtGui.QPixmap()
        self.form.framePreview.setPixmap(px)
        self.form.framePreview.setText(
            "" if not px.isNull() else translate("BIM", "No preview available")
        )
        self._update_preview_details(metadata)

        if False:
            # TO BE REFACTORED

            import Part
            import zipfile

            self.previewOn = PARAMS.GetBool("3DPreview", False)
            try:
                self.path = self.filemodel.itemFromIndex(index).toolTip()
            except:
                self.path = self.previousIndex
                print(self.path)
            self.isFile = os.path.isfile(self.path)
            # if the 3D preview checkbox is on ticked, show the preview
            if self.previewOn == True or self.linked == True:
                if self.isFile == True:
                    # close a non linked preview document
                    if self.linked == False:
                        try:
                            FreeCAD.closeDocument(self.previewDocName)
                        except:
                            pass
                    # create different kinds of previews based on file type
                    if (
                        self.path.lower().endswith(".stp")
                        or self.path.lower().endswith(".step")
                        or self.path.lower().endswith(".brp")
                        or self.path.lower().endswith(".brep")
                    ):
                        self.previewDocName = "Viewer"
                        FreeCAD.newDocument(self.previewDocName)
                        FreeCAD.setActiveDocument(self.previewDocName)
                        Part.show(Part.read(self.path))
                        FreeCADGui.SendMsgToActiveView("ViewFit")
                    elif self.path.lower().endswith(".fcstd"):
                        openedDoc = FreeCAD.openDocument(self.path)
                        FreeCADGui.SendMsgToActiveView("ViewFit")
                        self.previewDocName = FreeCAD.ActiveDocument.Name
                        thumbnailSave = PARAMS.GetBool("SaveThumbnails", False)
                        if thumbnailSave == True:
                            FreeCAD.ActiveDocument.save()
            if self.linked == False:
                self.previousIndex = self.path

            # create a 2D image preview
            if self.path.lower().endswith(".fcstd"):
                zfile = zipfile.ZipFile(self.path)
                files = zfile.namelist()
                # check for meta-file if it's really a FreeCAD document
                if files[0] == "Document.xml":
                    image = "thumbnails/Thumbnail.png"
                    if image in files:
                        image = zfile.read(image)
                        thumbfile = tempfile.mkstemp(suffix=".png")[1]
                        thumb = open(thumbfile, "wb")
                        thumb.write(image)
                        thumb.close()
                        im = QtGui.QPixmap(thumbfile)
                        self.form.framePreview.setPixmap(im)
                        return self.previewDocName, self.previousIndex, self.linked
            self.form.framePreview.clear()
            return self.previewDocName, self.previousIndex, self.linked

    def link(self, index=None):

        doc = self._get_main_document()
        if not doc:
            return
        path = self._resolve_index_path(index)
        if not path:
            return

        self.name = self._build_asset_descriptor(path)["label"]
        ext = os.path.splitext(path.lower())[1]
        definition_roots = self._ensure_symbol_definition_roots(doc, path)
        if not definition_roots:
            FreeCAD.Console.PrintWarning(
                translate(
                    "BIM",
                    "Insert Instance currently supports FCStd, STEP and BREP library assets.",
                )
                + "\n"
            )
            return

        if ext in [".stp", ".step", ".brp", ".brep"]:
            self.instance_definition_roots = definition_roots
            self.place(path)
            return

        if ext == ".fcstd":
            preview_shape = self._build_definition_preview_shape(definition_roots)
            if preview_shape and not preview_shape.isNull():
                self.instance_definition_roots = definition_roots
                self._start_shape_placement(preview_shape)
                return

        links = [
            self._create_symbol_link(doc, definition_obj) for definition_obj in definition_roots
        ]
        self._add_instances_to_active_container(links)
        doc.recompute()
        self._select_inserted_objects(links)
        self._clear_pending_insert_state()

    def addtolibrary(self):
        # DISABLED

        import os
        import Mesh
        import Part

        self.fileDialog = QtGui.QFileDialog.getSaveFileName(None, "Save As", self.librarypath)
        # print(self.fileDialog[0])
        # check if file saving has been canceled and save .fcstd, .step and .stl copies
        if self.fileDialog[0] != "":
            # remove the file extension from the file path
            fileName = os.path.splitext(self.fileDialog[0])[0]
            FCfilename = fileName + ".fcstd"
            FreeCAD.ActiveDocument.saveAs(FCfilename)
            if self.stepCB.isChecked() or self.stlCB.isChecked():
                toexport = []
                objs = FreeCAD.ActiveDocument.Objects
                for obj in objs:
                    if obj.ViewObject.Visibility == True:
                        toexport.append(obj)
                if self.stepCB.isChecked() and self.linked == False:
                    STEPfilename = fileName + ".step"
                    Part.export(toexport, STEPfilename)
                if self.stlCB.isChecked() and self.linked == False:
                    STLfilename = fileName + ".stl"
                    Mesh.export(toexport, STLfilename)
        return self.fileDialog[0]

    def onSearch(self, text):

        if text:
            self.setSearchModel(text)
        else:
            self.setFileModel()

    def setSearchModel(self, text):

        from PySide import QtGui

        def add_line(label, path, search_text=None):
            search_blob = search_text or self._build_local_search_text(label)
            allowed_name = os.path.basename(self._resolve_asset_path(path) or path)
            if self.isAllowed(allowed_name) and (query in search_blob):
                it = QtGui.QStandardItem(label)
                it.setEditable(False)
                it.setToolTip(path)
                it.setIcon(self._get_leaf_icon(label, path))
                self.filemodel.appendRow(it)

        query = text.lower().strip()
        self._set_tree_model(self.filemodel)
        self.filemodel.clear()
        if self.form.checkOnline.isChecked():
            res = self.getOfflineLib(structured=True)
            for i in range(len(res[0])):
                add_line(res[0][i], res[2][i] + "/" + res[0][i])
        else:
            for entry in self._get_local_search_index():
                if query not in entry["search_text"]:
                    continue
                add_line(entry["label"], entry["path"], entry["search_text"])
        self.modelmode = 0

    def getFilters(self):

        if self.form.checkFCStdOnly.isChecked():
            return FILTERS
        else:
            return FILTERS[:3]

    def isAllowed(self, filename):

        if not filename:
            return False
        if filename.startswith("."):
            return False
        e = os.path.splitext(filename)[1].lower()
        if not e:
            return True
        return e in {os.path.splitext(pattern)[1].lower() for pattern in self.getFilters()}

    def _get_leaf_icon(self, label, path):

        from PySide import QtGui

        leaf_path = self._resolve_asset_path(path)
        leaf_name = os.path.basename(leaf_path or label).lower()
        if leaf_name.endswith(".fcstd"):
            return QtGui.QIcon(":icons/freecad-doc.png")
        if leaf_name.endswith(".ifc"):
            return QtGui.QIcon(":/icons/IFC.svg")
        return QtGui.QIcon(":/icons/Part_document.svg")

    def _populate_tree_model(self, root, data):

        from PySide import QtGui

        for label, value in data.items():
            if not self.isAllowed(label):
                continue
            item = QtGui.QStandardItem(label)
            item.setEditable(False)
            root.appendRow(item)
            if isinstance(value, dict):
                item.setIcon(QtGui.QIcon.fromTheme("folder", QtGui.QIcon(":/icons/Group.svg")))
                item.setToolTip("")
                item.setData("folder", self._tree_item_kind_role)
                self._populate_tree_model(item, value)
            else:
                item.setToolTip(value)
                item.setIcon(self._get_leaf_icon(label, value))

    def setFileModel(self):

        self._set_tree_model(self.filemodel)
        self._populate_local_root_model()
        self.modelmode = 0

    def setOnlineModel(self):

        from PySide import QtGui

        def addItems(root, d, path):
            for k, v in d.items():
                if self.isAllowed(k):
                    it = QtGui.QStandardItem(k)
                    it.setEditable(False)
                    root.appendRow(it)
                    it.setToolTip(path + "/" + k)
                    if isinstance(v, dict):
                        it.setIcon(
                            QtGui.QIcon.fromTheme("folder", QtGui.QIcon(":/icons/Group.svg"))
                        )
                        it.setData("folder", self._tree_item_kind_role)
                        addItems(it, v, path + "/" + k)
                        it.setToolTip("")
                    elif k.lower().endswith(".fcstd"):
                        it.setIcon(QtGui.QIcon(":icons/freecad-doc.png"))
                    elif k.lower().endswith(".ifc"):
                        it.setIcon(QtGui.QIcon(":/icons/IFC.svg"))
                    else:
                        it.setIcon(QtGui.QIcon(":/icons/Part_document.svg"))

        self._set_tree_model(self.filemodel)
        self.filemodel.clear()
        d = self.getOfflineLib()
        addItems(self.filemodel, d, ":github")
        self.modelmode = 0

    def getOfflineLib(self, structured=False):

        def addDir(d, root):
            fn = []
            dn = []
            dp = []
            for k, v in d.items():
                if isinstance(v, dict) and v:
                    fn2, dn2, dp2 = addDir(v, root + "/" + k)
                    fn.extend(fn2)
                    dn.extend(dn2)
                    dp.extend(dp2)
                elif v and self._is_online_file_candidate(k):
                    fn.append(k)
                    dn.append(root)
                    dp.append(root)
            return fn, dn, dp

        templibfile = os.path.join(TEMPLIBPATH, LIBINDEXFILE)
        if not os.path.exists(templibfile):
            FreeCAD.Console.PrintError(
                translate("BIM", "No structure in cache. Refresh required.") + "\n"
            )
            return {}
        import sys

        sys.path.append(TEMPLIBPATH)
        import OfflineLibrary

        d = OfflineLibrary.library
        if structured:
            return addDir(d, ":github")
        else:
            return d

    def _load_asset_manifest(self, manifest_path):

        try:
            with open(manifest_path, "r", encoding="utf8") as handle:
                manifest = json.load(handle)
        except Exception:
            return {}
        return manifest if isinstance(manifest, dict) else {}

    def _get_asset_label(self, manifest_path):

        manifest = self._load_asset_manifest(manifest_path)
        return (
            manifest.get("label")
            or manifest.get("name")
            or manifest.get("title")
            or os.path.basename(os.path.dirname(manifest_path))
        )

    def _get_asset_thumbnail_path(self, manifest_path):

        manifest = self._load_asset_manifest(manifest_path)
        thumb = manifest.get("thumbnail")
        if isinstance(thumb, dict):
            thumb = thumb.get("file") or thumb.get("path")
        preview = manifest.get("preview")
        if (not thumb) and isinstance(preview, dict):
            thumb = preview.get("thumbnail") or preview.get("file") or preview.get("path")
        elif (not thumb) and isinstance(preview, str):
            thumb = preview
        if not thumb:
            return None
        thumb_path = os.path.normpath(os.path.join(os.path.dirname(manifest_path), thumb))
        if os.path.isfile(thumb_path):
            return thumb_path
        return None

    def _get_preview_metadata(self, path):

        manifest_path = self._get_asset_manifest_path(path)
        if manifest_path:
            manifest = self._load_asset_manifest(manifest_path)
            label = self._get_asset_label(manifest_path)
            category = manifest.get("category", "")
            asset_id = manifest.get("id", "")
            tags = manifest.get("tags", [])
            summary = manifest.get("summary") or manifest.get("description") or ""
            return {
                "label": label,
                "category": category,
                "id": asset_id,
                "tags": tags if isinstance(tags, (list, tuple, set)) else [],
                "summary": summary,
                "thumbnail": self._get_asset_thumbnail_path(manifest_path),
            }
        if os.path.isdir(path):
            return {
                "label": os.path.basename(path),
                "category": "",
                "id": "",
                "tags": [],
                "summary": translate("BIM", "Folder"),
                "thumbnail": None,
            }
        label = os.path.splitext(os.path.basename(path))[0]
        return {
            "label": label,
            "category": "",
            "id": "",
            "tags": [],
            "summary": "",
            "thumbnail": None,
        }

    def _update_preview_details(self, metadata):

        title = html.escape(metadata.get("label", "") or translate("BIM", "No selection"))
        self.form.previewTitle.setText(f"<b>{title}</b>")

        meta_parts = []
        if metadata.get("category"):
            meta_parts.append(html.escape(metadata["category"]))
        if metadata.get("id"):
            meta_parts.append(html.escape(metadata["id"]))
        tags = metadata.get("tags") or []
        if tags:
            meta_parts.append(
                translate("BIM", "Tags") + ": " + html.escape(", ".join(str(tag) for tag in tags))
            )
        self.form.previewMeta.setText(" · ".join(meta_parts))
        self.form.previewMeta.setVisible(bool(meta_parts))

        summary = metadata.get("summary", "")
        self.form.previewSummary.setText(summary)
        self.form.previewSummary.setVisible(bool(summary))
        has_details = bool(title or meta_parts or summary)
        self.form.previewDetails.setVisible(has_details and self.form.framePreview.isVisible())

    def _get_asset_manifest_path(self, path):

        if not path:
            return None
        if os.path.basename(path).lower() == ASSET_MANIFEST and os.path.isfile(path):
            return path
        candidate = os.path.join(os.path.dirname(path), ASSET_MANIFEST)
        if os.path.isfile(candidate):
            return candidate
        return None

    def _get_asset_representation_data(self, manifest, primary_key, aliases=()):

        representations = manifest.get("representations", {})
        for key in (primary_key,) + tuple(aliases):
            if key in representations:
                return representations[key]
        for key in (primary_key,) + tuple(aliases):
            if key in manifest:
                return manifest[key]
        return None

    def _get_asset_representation_path(self, manifest_path, representation):

        if isinstance(representation, str):
            relpath = representation
        elif isinstance(representation, dict):
            relpath = representation.get("file") or representation.get("path")
        else:
            relpath = None
        if not relpath:
            return None
        return os.path.normpath(os.path.join(os.path.dirname(manifest_path), relpath))

    def _get_asset_representation_root_name(self, representation):

        if isinstance(representation, dict):
            return representation.get("root") or representation.get("object")
        return None

    def _get_asset_plan_contract(self, manifest, plan_representation=None):

        plan_data = manifest.get("plan", {})
        if not isinstance(plan_data, dict):
            plan_data = {}
        rep_data = plan_representation if isinstance(plan_representation, dict) else {}

        anchor = _coerce_asset_vector(
            rep_data.get("anchor")
            or rep_data.get("insertion")
            or plan_data.get("anchor")
            or plan_data.get("insertion")
        )
        facing = _coerce_asset_vector(
            rep_data.get("facing")
            or rep_data.get("forward")
            or plan_data.get("facing")
            or plan_data.get("forward")
        )
        return anchor, facing

    def _get_asset_kind(self, manifest):

        kind = _normalize_asset_kind(manifest.get("kind") or manifest.get("type"))
        if kind:
            return kind

        category = str(manifest.get("category", "") or "").strip().lower()
        if category.startswith("furniture/"):
            return "equipment"

        tags = manifest.get("tags", [])
        if isinstance(tags, (list, tuple, set)):
            normalized_tags = {_normalize_asset_kind(tag) for tag in tags}
            if "equipment" in normalized_tags:
                return "equipment"
            if "furniture" in normalized_tags:
                return "equipment"

        return ""

    def _build_asset_descriptor(self, path):

        manifest_path = self._get_asset_manifest_path(path)
        if not manifest_path:
            label = os.path.splitext(os.path.basename(path))[0]
            return {
                "label": label,
                "source_path": self.cleanPath(path),
                "kind": "",
                "model_path": path,
                "model_root": None,
                "plan_path": None,
                "plan_root": None,
                "plan_anchor": None,
                "plan_facing": None,
            }

        manifest = self._load_asset_manifest(manifest_path)
        model_data = self._get_asset_representation_data(manifest, "model3d", aliases=("model",))
        plan_data = self._get_asset_representation_data(
            manifest,
            "plan2d",
            aliases=("plan", "symbol2d", "footprint"),
        )
        plan_anchor, plan_facing = self._get_asset_plan_contract(manifest, plan_data)
        model_path = self._get_asset_representation_path(manifest_path, model_data) or path
        return {
            "label": self._get_asset_label(manifest_path),
            "source_path": manifest.get("id") or self.cleanPath(manifest_path),
            "kind": self._get_asset_kind(manifest),
            "model_path": model_path,
            "model_root": self._get_asset_representation_root_name(model_data),
            "plan_path": self._get_asset_representation_path(manifest_path, plan_data),
            "plan_root": self._get_asset_representation_root_name(plan_data),
            "plan_anchor": plan_anchor,
            "plan_facing": plan_facing,
        }

    def _get_asset_model_path(self, manifest_path):

        return self._build_asset_descriptor(manifest_path)["model_path"] or manifest_path

    def _resolve_asset_path(self, path):

        if path and os.path.basename(path).lower() == ASSET_MANIFEST:
            return self._get_asset_model_path(path)
        return path

    def _make_unique_entry_label(self, entries, label, fallback_name):

        base = label or fallback_name
        if base not in entries:
            return base
        suffix = 2
        while True:
            candidate = f"{base} ({suffix})"
            if candidate not in entries:
                return candidate
            suffix += 1

    def _invalidate_local_search_index(self):

        self._local_search_index = None
        self._local_search_index_root = None

    def _is_library_file_candidate(self, name):

        return os.path.splitext(name)[1].lower() in LOCAL_IMPORT_EXTENSIONS

    def _is_online_file_candidate(self, name):

        return os.path.splitext(name)[1].lower() in ONLINE_IMPORT_EXTENSIONS

    def _folder_contains_browsable_content(self, folder):

        try:
            names = os.listdir(folder)
        except OSError:
            return False
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                if os.path.isfile(os.path.join(path, ASSET_MANIFEST)):
                    return True
                if self._folder_contains_browsable_content(path):
                    return True
                continue
            if os.path.isfile(path) and self._is_library_file_candidate(name):
                return True
        return False

    def _build_local_search_text(self, *values):

        tokens = []
        for value in values:
            if isinstance(value, (list, tuple, set)):
                tokens.extend(str(item) for item in value if item)
            elif value:
                tokens.append(str(value))
        return " ".join(tokens).lower()

    def _append_local_search_entries(self, entries, folder):

        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return
        for name in names:
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                manifest_path = os.path.join(path, ASSET_MANIFEST)
                if os.path.isfile(manifest_path):
                    manifest = self._load_asset_manifest(manifest_path)
                    label = self._get_asset_label(manifest_path)
                    relative_path = os.path.relpath(manifest_path, self.librarypath)
                    entries.append(
                        {
                            "label": label,
                            "path": manifest_path,
                            "search_text": self._build_local_search_text(
                                label,
                                manifest.get("id"),
                                manifest.get("category"),
                                manifest.get("tags", []),
                                relative_path.replace(os.sep, " "),
                            ),
                        }
                    )
                    continue
                self._append_local_search_entries(entries, path)
                continue
            if not (os.path.isfile(path) and self._is_library_file_candidate(name)):
                continue
            relative_path = os.path.relpath(path, self.librarypath)
            entries.append(
                {
                    "label": name,
                    "path": path,
                    "search_text": self._build_local_search_text(
                        name,
                        relative_path.replace(os.sep, " "),
                    ),
                }
            )

    def _get_local_search_index(self):

        if not self.librarypath:
            return []
        if self._local_search_index is None or self._local_search_index_root != self.librarypath:
            entries = []
            self._append_local_search_entries(entries, self.librarypath)
            self._local_search_index = entries
            self._local_search_index_root = self.librarypath
        return self._local_search_index

    def _build_local_library_tree(self, folder):

        entries = {}
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return entries
        for name in names:
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                manifest_path = os.path.join(path, ASSET_MANIFEST)
                if os.path.isfile(manifest_path):
                    label = self._get_asset_label(manifest_path)
                    label = self._make_unique_entry_label(entries, label, name)
                    entries[label] = manifest_path
                    continue
                subtree = self._build_local_library_tree(path)
                if subtree:
                    entries[name] = subtree
                continue
            if os.path.isfile(path) and self.isAllowed(name):
                entries[name] = path
        return entries

    def getLocalLib(self, structured=False):

        def flatten(tree):
            labels = []
            paths = []
            for label, value in tree.items():
                if isinstance(value, dict):
                    child_labels, child_paths = flatten(value)
                    labels.extend(child_labels)
                    paths.extend(child_paths)
                elif value:
                    labels.append(label)
                    paths.append(value)
            return labels, paths

        tree = self._build_local_library_tree(self.librarypath)
        if structured:
            return flatten(tree)
        return tree

    def urlencode(self, text):

        # print(text, type(text))
        if sys.version_info.major < 3:
            import urllib

            return urllib.quote_plus(text)
        else:
            import urllib.parse

            return urllib.parse.quote_plus(text)

    def openUrl(self, url):

        from PySide import QtGui

        QtGui.QDesktopServices.openUrl(url)

    def needsFullSpace(self):

        return True

    def getStandardButtons(self):

        from PySide import QtGui

        return QtGui.QDialogButtonBox.Close

    def reject(self):

        self._clear_pending_insert_state()
        FreeCADGui.Control.closeDialog()
        if self.previewDocName in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.previewDocName)
        doc = self._get_main_document()
        if doc:
            doc.recompute()

    def _clear_pending_insert_state(self):

        if hasattr(self, "box") and self.box:
            self.box.off()
            self.box = None
        if hasattr(self, "origin") and self.origin:
            try:
                self.origin.hide()
                self.origin.deleteLater()
            except Exception:
                pass
            self.origin = None
        self.instance_definition_roots = []
        if hasattr(self, "shape"):
            self.shape = None

    def _resolve_index_path(self, index=None):

        if not index:
            index = self.form.tree.selectedIndexes()
            if not index:
                return None
            index = index[0]
        path = self.filemodel.itemFromIndex(index).toolTip()
        if path.startswith(":github"):
            path = self.download(RAWURL + "/" + path[7:])
        return self._resolve_asset_path(path)

    def _get_main_document(self):

        try:
            return FreeCAD.getDocument(self.mainDocName)
        except Exception:
            FreeCAD.Console.PrintError(
                translate(
                    "BIM",
                    "It is not possible to insert this object because the document has been closed.",
                )
                + "\n"
            )
            return None

    def _get_main_gui_document(self):

        doc = self._get_main_document()
        if not doc:
            return None
        try:
            return FreeCADGui.getDocument(doc.Name)
        except Exception:
            return None

    def _activate_target_document(self):

        doc = self._get_main_document()
        if not doc:
            return None
        try:
            FreeCAD.setActiveDocument(doc.Name)
        except Exception:
            pass
        try:
            gui_doc = FreeCADGui.getDocument(doc.Name)
            if gui_doc:
                FreeCADGui.ActiveDocument = gui_doc
        except Exception:
            pass
        return doc

    def _merge_project_into_main_document(self, path):

        gui_doc = self._get_main_gui_document()
        if not gui_doc:
            return False
        try:
            gui_doc.mergeProject(path)
            return True
        except Exception:
            return False

    def _ensure_library_metadata(self, obj, source_path, role="instance"):

        if "LibrarySourcePath" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString",
                "LibrarySourcePath",
                SYMBOL_LIBRARY_GROUP,
                QT_TRANSLATE_NOOP("App::Property", "The source path for this library symbol"),
            )
        if "IsLibraryDefinition" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "IsLibraryDefinition",
                SYMBOL_LIBRARY_GROUP,
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Whether this object is a hidden local symbol definition used for links",
                ),
            )
        if "LibraryDefinitionRole" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString",
                "LibraryDefinitionRole",
                SYMBOL_LIBRARY_GROUP,
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The internal role of this hidden library definition object",
                ),
            )
        obj.LibrarySourcePath = source_path
        obj.IsLibraryDefinition = True
        obj.LibraryDefinitionRole = role

    def _set_definition_view_state(self, obj):

        view_object = getattr(obj, "ViewObject", None)
        if not view_object:
            return
        if hasattr(view_object, "Visibility"):
            try:
                view_object.Visibility = False
            except Exception:
                pass
        if hasattr(view_object, "Selectable"):
            try:
                view_object.Selectable = False
            except Exception:
                pass

    def _ensure_active_document(self, doc):

        if not doc:
            return
        try:
            if getattr(FreeCAD.ActiveDocument, "Name", None) != doc.Name:
                FreeCAD.setActiveDocument(doc.Name)
        except Exception:
            pass
        if not FreeCAD.GuiUp:
            return
        try:
            gui_doc = FreeCADGui.getDocument(doc.Name)
            if gui_doc:
                FreeCADGui.ActiveDocument = gui_doc
        except Exception:
            pass

    def _ensure_symbol_definitions_group(self, doc):

        group = doc.getObject(SYMBOL_DEFINITIONS_GROUP)
        if group is None:
            group = doc.addObject("App::DocumentObjectGroup", SYMBOL_DEFINITIONS_GROUP)
            group.Label = translate("BIM", "Symbol Definitions")
        self._ensure_library_metadata(group, "", role="definitions")
        self._set_definition_view_state(group)
        return group

    def _get_symbol_asset_group(self, doc, source_path):

        definitions_group = self._ensure_symbol_definitions_group(doc)
        for obj in getattr(definitions_group, "Group", []) or []:
            if getattr(obj, "LibrarySourcePath", "") == source_path:
                return obj
        return None

    def _ensure_symbol_asset_group(self, doc, source_path, label):

        group = self._get_symbol_asset_group(doc, source_path)
        if group is not None:
            self._set_definition_view_state(group)
            return group

        group = doc.addObject("App::DocumentObjectGroup", "SymbolAsset")
        group.Label = label
        self._ensure_library_metadata(group, source_path, role="asset")
        self._set_definition_view_state(group)
        self._ensure_symbol_definitions_group(doc).addObject(group)
        return group

    def _remove_from_parent_groups(self, obj, keep=None):

        keep = keep or set()
        for parent in list(getattr(obj, "InList", []) or []):
            if parent in keep:
                continue
            if hasattr(parent, "removeObject"):
                try:
                    parent.removeObject(obj)
                except Exception:
                    pass

    def _retarget_definition_links(self, doc, old_target, new_target):

        if not doc or not old_target or not new_target or old_target == new_target:
            return
        for obj in getattr(doc, "Objects", []) or []:
            if getattr(obj, "TypeId", "") != "App::Link":
                continue
            linked = getattr(obj, "LinkedObject", None)
            if linked != old_target:
                continue
            try:
                obj.setLink(new_target)
            except Exception:
                pass

    def _get_imported_root_objects(self, added_objects):

        added_names = {obj.Name for obj in added_objects}
        roots = []
        for obj in added_objects:
            parents = [
                parent for parent in getattr(obj, "InList", []) if parent.Name in added_names
            ]
            if not parents:
                roots.append(obj)
        return roots

    def _normalize_symbol_key(self, text):

        return "".join(char.lower() for char in str(text or "") if char.isalnum())

    def _is_explicit_symbol_root(self, obj):

        root_markers = {"root", "symbolroot", "libraryroot", "definitionroot"}
        for prop_name in ("IsLibraryRoot", "IsSymbolRoot", "LibraryRole", "SymbolRole"):
            if prop_name not in getattr(obj, "PropertiesList", []):
                continue
            value = getattr(obj, prop_name, None)
            if isinstance(value, bool) and value:
                return True
            if isinstance(value, str) and value.strip().lower() in root_markers:
                return True
        return False

    def _get_symbol_object_type(self, obj):

        proxy_type = getattr(getattr(obj, "Proxy", None), "Type", "")
        if proxy_type:
            return proxy_type
        try:
            import Draft

            draft_type = Draft.getType(obj)
        except Exception:
            draft_type = ""
        if draft_type:
            return draft_type
        return getattr(obj, "TypeId", "")

    def _is_symbol_container_object(self, obj):

        try:
            if obj.isDerivedFrom("App::DocumentObjectGroup"):
                return True
        except Exception:
            pass
        return self._get_symbol_object_type(obj) in {"BuildingPart", "App::DocumentObjectGroup"}

    def _is_symbol_helper_object(self, obj):

        type_name = self._get_symbol_object_type(obj)
        type_id = getattr(obj, "TypeId", "")
        if type_name == "App::Link":
            return True
        if self._is_symbol_container_object(obj):
            return True
        if type_id.startswith("Sketcher::") or type_id.startswith("Image::"):
            return True
        shape = getattr(obj, "Shape", None)
        return not (shape and not shape.isNull()) and not getattr(obj, "OutList", [])

    def _is_preferred_symbol_type(self, obj):

        return self._get_symbol_object_type(obj) in {
            "Door",
            "Equipment",
            "Furniture",
            "Structure",
            "Window",
        }

    def _matches_symbol_asset_label(self, obj, asset_label):

        asset_key = self._normalize_symbol_key(asset_label)
        if not asset_key:
            return False
        name_keys = {
            self._normalize_symbol_key(getattr(obj, "Label", "")),
            self._normalize_symbol_key(getattr(obj, "Name", "")),
        }
        return asset_key in name_keys

    def _get_candidate_symbol_objects(self, added_objects, allow_helper_objects=False):

        candidates = []
        for obj in added_objects:
            if self._get_symbol_object_type(obj) == "App::Link" or self._is_symbol_container_object(
                obj
            ):
                continue
            if not allow_helper_objects and self._is_symbol_helper_object(obj):
                continue
            candidates.append(obj)
        candidate_names = {obj.Name for obj in candidates}
        filtered = []
        for obj in candidates:
            parents = [
                parent for parent in getattr(obj, "InList", []) if parent.Name in candidate_names
            ]
            if parents and not self._is_explicit_symbol_root(obj):
                continue
            filtered.append(obj)
        return filtered

    def _choose_fcstd_definition_roots(
        self,
        added_objects,
        asset_label,
        root_name=None,
        allow_helper_objects=False,
        preferred_types=None,
    ):

        imported_roots = self._get_imported_root_objects(added_objects)
        root_key = self._normalize_symbol_key(root_name)
        if root_key:
            named_roots = [
                obj
                for obj in added_objects
                if root_key
                in {
                    self._normalize_symbol_key(getattr(obj, "Label", "")),
                    self._normalize_symbol_key(getattr(obj, "Name", "")),
                }
            ]
            if named_roots:
                return named_roots
        explicit_roots = [obj for obj in added_objects if self._is_explicit_symbol_root(obj)]
        if explicit_roots:
            return explicit_roots

        candidates = self._get_candidate_symbol_objects(
            added_objects, allow_helper_objects=allow_helper_objects
        )
        if not candidates:
            return imported_roots

        matching_candidates = [
            obj for obj in candidates if self._matches_symbol_asset_label(obj, asset_label)
        ]
        if matching_candidates:
            preferred_matches = [
                obj
                for obj in matching_candidates
                if not preferred_types
                or self._get_symbol_object_type(obj) in preferred_types
                or self._is_preferred_symbol_type(obj)
            ]
            return preferred_matches or matching_candidates

        preferred_candidates = [
            obj
            for obj in candidates
            if (preferred_types and self._get_symbol_object_type(obj) in preferred_types)
            or (not preferred_types and self._is_preferred_symbol_type(obj))
        ]
        if len(preferred_candidates) == 1:
            return preferred_candidates
        if len(candidates) == 1:
            return candidates
        return imported_roots

    def _get_symbol_definition_roots(self, asset_group):

        return [
            obj
            for obj in list(getattr(asset_group, "Group", []) or [])
            if getattr(obj, "IsLibraryDefinition", False)
            and getattr(obj, "LibraryDefinitionRole", "instance") in {"", "instance"}
        ]

    def _get_symbol_plan_roots(self, asset_group):

        return [
            obj
            for obj in list(getattr(asset_group, "Group", []) or [])
            if getattr(obj, "IsLibraryDefinition", False)
            and getattr(obj, "LibraryDefinitionRole", "") == "plan2d"
        ]

    def _ensure_equipment_plan_symbol_property(self, obj):

        if self._get_symbol_object_type(obj) != "Equipment":
            return False
        if "PlanSymbols" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkList",
                "PlanSymbols",
                "Equipment",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Optional authored 2D plan symbol objects for this equipment"
                ),
            )
        return True

    def _attach_plan_symbol_roots(self, definition_roots, plan_roots):

        changed = False
        if not plan_roots:
            return changed
        for definition_obj in definition_roots:
            if not self._ensure_equipment_plan_symbol_property(definition_obj):
                continue
            plan_symbols = [plan_root for plan_root in plan_roots if plan_root != definition_obj]
            current_symbols = list(getattr(definition_obj, "PlanSymbols", []) or [])
            if current_symbols == plan_symbols:
                continue
            definition_obj.PlanSymbols = plan_symbols
            changed = True
        return changed

    def _apply_asset_plan_contract(self, definition_obj, asset_descriptor):

        if not definition_obj or asset_descriptor.get("kind") != "equipment":
            return False
        anchor = asset_descriptor.get("plan_anchor")
        facing = asset_descriptor.get("plan_facing")
        if anchor is None and facing is None:
            return False
        try:
            import ArchEquipment

            return bool(
                ArchEquipment.apply_plan_contract(definition_obj, anchor=anchor, facing=facing)
            )
        except Exception:
            return False

    def _apply_asset_plan_contract_to_roots(self, definition_roots, asset_descriptor):

        changed = False
        for definition_obj in definition_roots or []:
            changed = self._apply_asset_plan_contract(definition_obj, asset_descriptor) or changed
        return changed

    def _normalize_definition_roots(self, doc, asset_group, asset_descriptor, root_objects):

        if asset_descriptor.get("kind") != "equipment":
            return root_objects
        if not root_objects:
            return root_objects

        import Arch

        self._ensure_active_document(doc)
        normalized_roots = []
        source_path = getattr(asset_group, "LibrarySourcePath", "")
        multiple_roots = len(root_objects) > 1

        for root_obj in root_objects:
            if self._get_symbol_object_type(root_obj) == "Equipment":
                self._apply_asset_plan_contract(root_obj, asset_descriptor)
                normalized_roots.append(root_obj)
                continue

            self._ensure_library_metadata(root_obj, source_path, role="source")
            self._remove_from_parent_groups(root_obj, keep={asset_group})
            try:
                if root_obj not in (getattr(asset_group, "Group", []) or []):
                    asset_group.addObject(root_obj)
            except Exception:
                pass
            self._set_definition_view_state(root_obj)

            if multiple_roots:
                component_label = getattr(root_obj, "Label", None) or getattr(root_obj, "Name", "")
                equipment_label = "{} {}".format(asset_descriptor["label"], component_label).strip()
            else:
                equipment_label = asset_descriptor["label"]

            equipment = Arch.makeEquipment(root_obj, name=equipment_label)
            self._ensure_library_metadata(equipment, source_path, role="instance")
            self._apply_asset_plan_contract(equipment, asset_descriptor)
            self._remove_from_parent_groups(equipment, keep={asset_group})
            try:
                if equipment not in (getattr(asset_group, "Group", []) or []):
                    asset_group.addObject(equipment)
            except Exception:
                pass
            self._set_definition_view_state(equipment)
            self._retarget_definition_links(doc, root_obj, equipment)
            normalized_roots.append(equipment)

        return normalized_roots

    def _create_shape_symbol_definitions(self, doc, asset_group, asset_descriptor):

        import Arch
        import Part

        self._ensure_active_document(doc)
        obj = Arch.makeEquipment()
        obj.Shape = Part.read(asset_descriptor["model_path"])
        obj.Label = asset_descriptor["label"]
        self._ensure_library_metadata(
            obj, getattr(asset_group, "LibrarySourcePath", ""), role="instance"
        )
        self._apply_asset_plan_contract(obj, asset_descriptor)
        self._remove_from_parent_groups(obj)
        asset_group.addObject(obj)
        self._set_definition_view_state(obj)
        if asset_descriptor["plan_path"] and asset_descriptor["plan_path"].lower().endswith(
            ".fcstd"
        ):
            plan_roots = self._create_auxiliary_symbol_roots(
                doc,
                asset_group,
                asset_descriptor["plan_path"],
                asset_descriptor["label"],
                asset_descriptor["plan_root"],
            )
            self._attach_plan_symbol_roots([obj], plan_roots)
        doc.recompute()
        return [obj]

    def _create_auxiliary_symbol_roots(self, doc, asset_group, path, asset_label, root_name=None):

        before = {obj.Name for obj in doc.Objects}
        if not self._merge_project_into_main_document(path):
            return []
        added_objects = [obj for obj in doc.Objects if obj.Name not in before]
        root_objects = self._choose_fcstd_definition_roots(
            added_objects,
            asset_label,
            root_name=root_name,
            allow_helper_objects=True,
        )

        for obj in added_objects:
            self._set_definition_view_state(obj)

        for obj in root_objects:
            self._ensure_library_metadata(
                obj, getattr(asset_group, "LibrarySourcePath", ""), role="plan2d"
            )
            self._remove_from_parent_groups(obj, keep={asset_group})
            asset_group.addObject(obj)
            self._set_definition_view_state(obj)
        return root_objects

    def _create_fcstd_symbol_definitions(self, doc, asset_group, asset_descriptor):

        before = {obj.Name for obj in doc.Objects}
        if not self._merge_project_into_main_document(asset_descriptor["model_path"]):
            return []
        added_objects = [obj for obj in doc.Objects if obj.Name not in before]
        root_objects = self._choose_fcstd_definition_roots(
            added_objects,
            asset_descriptor["label"],
            root_name=asset_descriptor["model_root"],
        )
        if asset_descriptor["plan_path"] and os.path.normpath(
            asset_descriptor["plan_path"]
        ) == os.path.normpath(asset_descriptor["model_path"]):
            plan_roots = self._choose_fcstd_definition_roots(
                added_objects,
                asset_descriptor["label"],
                root_name=asset_descriptor["plan_root"],
                allow_helper_objects=True,
            )
        elif asset_descriptor["plan_path"] and asset_descriptor["plan_path"].lower().endswith(
            ".fcstd"
        ):
            plan_roots = self._create_auxiliary_symbol_roots(
                doc,
                asset_group,
                asset_descriptor["plan_path"],
                asset_descriptor["label"],
                asset_descriptor["plan_root"],
            )
        else:
            plan_roots = []

        for obj in added_objects:
            self._set_definition_view_state(obj)

        root_objects = self._normalize_definition_roots(
            doc, asset_group, asset_descriptor, root_objects
        )
        for obj in root_objects:
            self._ensure_library_metadata(
                obj, getattr(asset_group, "LibrarySourcePath", ""), role="instance"
            )
            self._remove_from_parent_groups(obj, keep={asset_group})
            asset_group.addObject(obj)
            self._set_definition_view_state(obj)

        if plan_roots:
            for obj in plan_roots:
                if obj in root_objects:
                    continue
                self._ensure_library_metadata(
                    obj, getattr(asset_group, "LibrarySourcePath", ""), role="plan2d"
                )
                self._remove_from_parent_groups(obj, keep={asset_group})
                asset_group.addObject(obj)
                self._set_definition_view_state(obj)
            self._attach_plan_symbol_roots(root_objects, plan_roots)

        self._set_definition_view_state(asset_group)
        doc.recompute()
        return root_objects

    def _ensure_symbol_definition_roots(self, doc, path):

        asset_descriptor = self._build_asset_descriptor(path)
        source_path = asset_descriptor["source_path"]
        asset_group = self._ensure_symbol_asset_group(doc, source_path, asset_descriptor["label"])
        roots = self._get_symbol_definition_roots(asset_group)
        if roots:
            initial_root_names = tuple(obj.Name for obj in roots)
            roots = self._normalize_definition_roots(doc, asset_group, asset_descriptor, roots)
            roots_changed = tuple(obj.Name for obj in roots) != initial_root_names
            plan_roots = self._get_symbol_plan_roots(asset_group)
            plan_symbols_changed = False
            if plan_roots:
                plan_symbols_changed = self._attach_plan_symbol_roots(roots, plan_roots)
            plan_contract_changed = self._apply_asset_plan_contract_to_roots(
                roots, asset_descriptor
            )
            self._set_definition_view_state(asset_group)
            if roots_changed or plan_symbols_changed or plan_contract_changed:
                doc.recompute()
            return roots

        ext = os.path.splitext(asset_descriptor["model_path"].lower())[1]
        if ext in [".stp", ".step", ".brp", ".brep"]:
            return self._create_shape_symbol_definitions(doc, asset_group, asset_descriptor)
        if ext == ".fcstd":
            return self._create_fcstd_symbol_definitions(doc, asset_group, asset_descriptor)
        return []

    def _compose_preview_placement(self, parent_placement=None, local_placement=None):

        if parent_placement is None:
            parent_placement = FreeCAD.Placement()
        if local_placement is None:
            return FreeCAD.Placement(parent_placement)
        try:
            return parent_placement.multiply(local_placement)
        except Exception:
            try:
                return FreeCAD.Placement(local_placement)
            except Exception:
                return FreeCAD.Placement(parent_placement)

    def _copy_preview_shape(self, shape, placement=None):

        if not shape or shape.isNull():
            return None
        preview_shape = shape.copy()
        if placement is None:
            return preview_shape
        try:
            preview_shape.Placement = placement.multiply(preview_shape.Placement)
        except Exception:
            pass
        return preview_shape

    def _get_object_preview_shapes(self, obj, parent_placement=None):

        shapes = []
        placement = self._compose_preview_placement(
            parent_placement, getattr(obj, "Placement", None)
        )
        shape = getattr(obj, "Shape", None)
        if shape and not shape.isNull():
            preview_shape = self._copy_preview_shape(shape, placement=placement)
            if preview_shape and not preview_shape.isNull():
                shapes.append(preview_shape)
            return shapes

        for child in getattr(obj, "OutList", []) or []:
            shapes.extend(self._get_object_preview_shapes(child, parent_placement=placement))
        return shapes

    def _should_prefer_plan_symbol_preview(self):

        try:
            from bimcommands import BimPlanSession

            session = BimPlanSession.get_active_session()
        except Exception:
            session = None
        return bool(session and not getattr(session, "_tearing_down", False))

    def _get_object_plan_preview_shapes(self, obj):

        try:
            import ArchEquipment

            shapes = list(ArchEquipment.get_plan_representation_shapes(obj))
            if shapes:
                return shapes
        except Exception:
            pass

        shapes = []
        for plan_obj in getattr(obj, "PlanSymbols", []) or []:
            shapes.extend(self._get_object_preview_shapes(plan_obj))
        return shapes

    def _build_definition_preview_shape(self, definition_roots):

        import Part

        shapes = []
        prefer_plan_symbols = self._should_prefer_plan_symbol_preview()
        for obj in definition_roots:
            if prefer_plan_symbols:
                object_shapes = self._get_object_plan_preview_shapes(obj)
                if object_shapes:
                    shapes.extend(object_shapes)
                    continue
            shapes.extend(self._get_object_preview_shapes(obj))
        if not shapes:
            return None
        if len(shapes) == 1:
            return shapes[0]
        return Part.makeCompound(shapes)

    def _next_instance_label(self, doc, base_label):

        used = {obj.Label for obj in doc.Objects}
        index = 1
        while True:
            label = f"{base_label}{index:03d}"
            if label not in used:
                return label
            index += 1

    def _create_symbol_link(self, doc, definition_obj):

        link = doc.addObject("App::Link", "Link")
        link.setLink(definition_obj)
        link.Label = self._next_instance_label(doc, definition_obj.Label)
        return link

    def _get_active_container(self):

        selection = FreeCADGui.Selection.getSelection(self.mainDocName)
        for obj in selection:
            if hasattr(obj, "addObject") and not getattr(obj, "IsLibraryDefinition", False):
                return obj
        return None

    def _add_instances_to_active_container(self, links):

        container = self._get_active_container()
        if not container:
            return
        for link in links:
            try:
                container.addObject(link)
            except Exception:
                pass

    def _select_inserted_objects(self, objects, fit_view=False):

        FreeCADGui.Selection.clearSelection(self.mainDocName)
        for obj in objects:
            FreeCADGui.Selection.addSelection(self.mainDocName, obj.Name)
        if fit_view:
            FreeCADGui.SendMsgToActiveView("ViewSelection")

    def insert(self, index=None):

        doc = self._get_main_document()
        if not doc:
            return
        path = self._resolve_index_path(index)
        if not path:
            return
        before = list(doc.Objects)
        self.name = self._build_asset_descriptor(path)["label"]
        ext = os.path.splitext(path.lower())[1]
        if ext in [".stp", ".step", ".brp", ".brep"]:
            self.place(path)
        elif ext == ".fcstd":
            self._merge_project_into_main_document(path)
            self._clear_pending_insert_state()
        elif ext == ".ifc":
            from importers import importIFC

            importIFC.ZOOMOUT = False
            importIFC.insert(path, doc.Name)
            self._clear_pending_insert_state()
        elif ext in [".sat", ".sab"]:
            try:
                # InventorLoader addon
                import importerIL
            except ImportError:
                try:
                    # CADExchanger addon
                    import CadExchangerIO
                except ImportError:
                    FreeCAD.Console.PrintError(
                        translate(
                            "BIM",
                            "Error: Unable to import SAT files - InventorLoader or CadExchanger addon must be installed",
                        )
                        + "\n"
                    )
                else:
                    path = CadExchangerIO.insert(path, doc.Name, returnpath=True)
                    self.place(path)
            else:
                path = importerIL.insert(path, doc.Name)
        inserted = []
        for o in doc.Objects:
            if o not in before:
                inserted.append(o)
        self._select_inserted_objects(inserted)

    def download(self, url):

        import urllib.request

        filepath = os.path.join(TEMPLIBPATH, url.split("/")[-1])
        url = url.replace(" ", "%20")
        if not os.path.exists(filepath):
            from PySide import QtCore, QtGui

            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            u = urllib.request.urlopen(url)
            if not u:
                FreeCAD.Console.PrintError(
                    translate("BIM", "Error: Unable to download") + " " + url + "\n"
                )
            b = u.read()
            f = open(filepath, "wb")
            f.write(b)
            f.close()
            QtGui.QApplication.restoreOverrideCursor()
        return filepath

    def _start_shape_placement(self, shape):

        import Part
        import WorkingPlane

        self._activate_target_document()
        self.shape = shape
        if hasattr(FreeCADGui, "Snapper"):
            try:
                import DraftTrackers
            except Exception:
                import draftguitools.gui_trackers as DraftTrackers
            self.box = DraftTrackers.ghostTracker(
                self.shape, dotted=True, scolor=(0.0, 0.0, 1.0), swidth=1.0
            )
            self.delta = self.shape.BoundBox.Center
            self.box.move(self.delta)
            self.box.on()
            WorkingPlane.get_working_plane()
            self.origin = self.makeOriginWidget()
            FreeCADGui.Snapper.getPoint(
                movecallback=self.mouseMove,
                callback=self.mouseClick,
                extradlg=self.origin,
                hints=self.get_hints(),
            )
        else:
            Part.show(self.shape)

    def get_hints(self):
        "returns status bar input hints for the current tool state"
        from draftguitools import gui_tool_utils

        return (
            [
                FreeCADGui.InputHint(
                    translate("BIM", "%1 pick insertion point"), FreeCADGui.UserInput.MouseLeft
                )
            ]
            + gui_tool_utils._get_hint_xyz_constrain()
            + gui_tool_utils._get_hint_mod_constrain()
            + gui_tool_utils._get_hint_mod_snap()
        )

    def place(self, path):

        import Part

        self._start_shape_placement(Part.read(path))

    def makeOriginWidget(self):

        from PySide import QtGui

        w = QtGui.QWidget()
        w.setWindowTitle(translate("BIM", "Insertion Point"))
        w.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(__file__), "icons", "BIM_Library.svg"))
        )
        l = QtGui.QVBoxLayout()
        w.setLayout(l)
        c = QtGui.QComboBox()
        c.ObjectName = "comboOrigin"
        w.comboOrigin = c
        c.addItems(
            [
                translate("BIM", "Asset anchor / origin"),
                translate("BIM", "Top left"),
                translate("BIM", "Top center"),
                translate("BIM", "Top right"),
                translate("BIM", "Middle left"),
                translate("BIM", "Middle center"),
                translate("BIM", "Middle right"),
                translate("BIM", "Bottom left"),
                translate("BIM", "Bottom center"),
                translate("BIM", "Bottom right"),
            ]
        )
        c.setCurrentIndex(PARAMS.GetInt("LibraryDefaultInsert", 0))
        c.currentIndexChanged.connect(self.storeInsert)
        l.addWidget(c)
        return w

    def storeInsert(self, index):

        PARAMS.SetInt("LibraryDefaultInsert", index)

    def mouseMove(self, point, info):

        self.box.move(point.add(self.getDelta()))

    def mouseClick(self, point, info):

        if point:
            import Arch

            doc = self._get_main_document()
            if doc and self.instance_definition_roots:
                links = []
                placement = FreeCAD.Placement(point.add(self.getDelta()), FreeCAD.Rotation())
                for definition_obj in self.instance_definition_roots:
                    link = self._create_symbol_link(doc, definition_obj)
                    if hasattr(link, "Placement"):
                        link.Placement = placement
                    links.append(link)
                self._add_instances_to_active_container(links)
                doc.recompute()
                self._select_inserted_objects(links)
            else:
                doc = self._activate_target_document()
                if not doc:
                    self._clear_pending_insert_state()
                    return
                self.shape.translate(point.add(self.getDelta()))
                obj = Arch.makeEquipment()
                obj.Shape = self.shape
                obj.Label = self.name
        self._clear_pending_insert_state()

    def _get_instance_definition_anchor(self):

        definition_roots = list(getattr(self, "instance_definition_roots", []) or [])
        if not definition_roots:
            return FreeCAD.Vector()
        try:
            import ArchEquipment

            return ArchEquipment.get_plan_anchor(definition_roots[0])
        except Exception:
            return FreeCAD.Vector()

    def getDelta(self):

        d = FreeCAD.Vector(-self.shape.BoundBox.Center.x, -self.shape.BoundBox.Center.y, 0)
        idx = self.origin.comboOrigin.currentIndex()
        if idx <= 0:
            anchor = self._get_instance_definition_anchor()
            return FreeCAD.Vector(-anchor.x, -anchor.y, -anchor.z)
        elif idx == 1:
            return d.add(
                FreeCAD.Vector(self.shape.BoundBox.XLength / 2, -self.shape.BoundBox.YLength / 2, 0)
            )
        elif idx == 2:
            return d.add(FreeCAD.Vector(0, -self.shape.BoundBox.YLength / 2, 0))
        elif idx == 3:
            return d.add(
                FreeCAD.Vector(
                    -self.shape.BoundBox.XLength / 2,
                    -self.shape.BoundBox.YLength / 2,
                    0,
                )
            )
        elif idx == 4:
            return d.add(FreeCAD.Vector(self.shape.BoundBox.XLength / 2, 0, 0))
        elif idx == 5:
            return d
        elif idx == 6:
            return d.add(FreeCAD.Vector(-self.shape.BoundBox.XLength / 2, 0, 0))
        elif idx == 7:
            return d.add(
                FreeCAD.Vector(self.shape.BoundBox.XLength / 2, self.shape.BoundBox.YLength / 2, 0)
            )
        elif idx == 8:
            return d.add(FreeCAD.Vector(0, self.shape.BoundBox.YLength / 2, 0))
        elif idx == 9:
            return d.add(
                FreeCAD.Vector(-self.shape.BoundBox.XLength / 2, self.shape.BoundBox.YLength / 2, 0)
            )

    def getOnlineContentsAPI(self, url):
        """same as getOnlineContents but uses github API (faster)"""

        import json
        import requests

        result = {}
        count = 0
        r = requests.get(
            "https://api.github.com/repos/FreeCAD/FreeCAD-library/git/trees/master?recursive=1"
        )
        if r.ok:
            j = json.loads(r.content)
            if j["truncated"]:
                print(
                    "WARNING: The fetched content exceeds maximum GitHub allowance and is truncated"
                )
            t = j["tree"]
            for f in t:
                path = f["path"].split("/")
                if f["type"] == "tree":
                    name = None
                else:
                    name = path[-1]
                    path = path[:-1]
                host = result
                for fp in path:
                    if fp in host:
                        host = host[fp]
                    else:
                        host[fp] = {}
                        host = host[fp]
                if name:
                    for ft in self.getFilters():
                        if name.endswith(ft[1:]):
                            break
                    else:
                        continue
                    host[name] = name
                    count += 1
        else:
            FreeCAD.Console.PrintError(translate("BIM", "Could not fetch library contents") + "\n")
        # print("result:",result)
        if not result:
            FreeCAD.Console.PrintError(
                translate("BIM", "No results fetched from online library") + "\n"
            )
        else:
            FreeCAD.Console.PrintLog("BIM Library: Reloaded " + str(count) + " files\n")
        return result

    def onCheckOnline(self, state=None):
        """if the Online checkbox is clicked"""

        import datetime

        if state == None:
            state = self.form.checkOnline.isChecked()
        # save state
        PARAMS.SetBool("LibraryModeChosen", True)
        PARAMS.SetBool("LibraryOnline", state)
        if state:
            # online
            if USE_API:
                needrefresh = True
                timestamp = datetime.datetime.now()
                if os.path.exists(os.path.join(TEMPLIBPATH, LIBINDEXFILE)):
                    stored = PARAMS.GetUnsigned("LibraryTimeStamp", 0)
                    if stored:
                        stored = datetime.datetime.fromtimestamp(stored)
                        if (timestamp - stored).total_seconds() < REFRESH_INTERVAL:
                            needrefresh = False
                if needrefresh:
                    PARAMS.SetUnsigned("LibraryTimeStamp", int(timestamp.timestamp()))
                    self.onRefresh()
                else:
                    FreeCAD.Console.PrintLog("BIM Library: Using cached library\n")
            self.setOnlineModel()
        else:
            # offline
            self.setFileModel()
        self._update_library_mode_status(state)

    def onRefresh(self):
        """refreshes the tree"""

        from PySide import QtCore, QtGui

        def writeOfflineLib():
            if USE_API:
                rootfiles = self.getOnlineContentsAPI(LIBRARYURL)
            if rootfiles:
                templibfile = os.path.join(TEMPLIBPATH, LIBINDEXFILE)
                os.makedirs(TEMPLIBPATH, exist_ok=True)
                tf = open(templibfile, "w", encoding="utf8")
                tf.write("library=" + str(rootfiles) + "\n")
                tf.close()
                self.setOnlineModel()

        reply = PARAMS.GetBool("LibraryWarning", False)
        if not reply:
            reply = QtGui.QMessageBox.information(
                None, "", translate("BIM", "Warning, this can take several minutes!")
            )
        if reply:
            PARAMS.SetBool("LibraryWarning", True)
            self.form.setEnabled(False)
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.form.repaint()
            QtGui.QApplication.processEvents()
            QtCore.QTimer.singleShot(1, writeOfflineLib)
            self.form.setEnabled(True)
            QtGui.QApplication.restoreOverrideCursor()
        else:
            self.setOnlineModel()

    def onCheckFCStdOnly(self, state):
        """if the FCStd only checkbox is clicked"""

        # save state
        PARAMS.SetBool("LibraryFCStdOnly", state)
        self.onCheckOnline(self.form.checkOnline.isChecked())

    def onButtonPreview(self):
        """hides/shows the preview"""

        if self.form.framePreview.isVisible():
            self.form.framePreview.hide()
            self.form.previewDetails.hide()
            self.form.buttonPreview.setText(translate("BIM", "Preview") + " ▸")
            PARAMS.SetBool("LibraryPreview", False)
        else:
            self.form.framePreview.show()
            if self.form.previewTitle.text() or self.form.previewMeta.text():
                self.form.previewDetails.show()
            self.form.buttonPreview.setText(translate("BIM", "Preview") + " ▼")
            PARAMS.SetBool("LibraryPreview", True)

    def getThumbnail(self, filepath):
        """returns a thumbnail image path for a given file path"""

        import urllib.request
        import urllib.parse
        import zipfile
        import io

        manifest_path = self._get_asset_manifest_path(filepath)
        if manifest_path:
            asset_thumb = self._get_asset_thumbnail_path(manifest_path)
            if asset_thumb:
                return asset_thumb
            filepath = self._get_asset_model_path(manifest_path)
        if filepath.startswith(":github"):
            filepath = RAWURL + filepath[7:]
        if not filepath.lower().endswith(".fcstd"):
            return None
        iconname = self.getHashname(filepath)
        iconfile = os.path.join(THUMBNAILSPATH, iconname)
        if os.path.exists(iconfile):
            return iconfile
        else:
            if self.form.checkOnline.isChecked():
                # download file
                u = urllib.request.urlopen(urllib.parse.quote(filepath, safe=":/."))
                fdata = u.read()
                u.close()
                f = io.BytesIO(fdata)
            else:
                f = filepath
            zfile = zipfile.ZipFile(f)
            if "thumbnails/Thumbnail.png" in zfile.namelist():
                data = zfile.read("thumbnails/Thumbnail.png")
                os.makedirs(os.path.dirname(iconfile), exist_ok=True)
                thumb = open(iconfile, "wb")
                thumb.write(data)
                thumb.close()
                return iconfile
            else:
                return None

    def getHashname(self, filepath):
        """creates a png filename for a given file path"""

        import hashlib

        filepath = self.cleanPath(filepath)
        return hashlib.md5(filepath.encode()).hexdigest() + ".png"

    def cleanPath(self, filepath):
        """cleans a file path into subfolder/subfolder/file form"""

        import urllib.request
        import urllib.parse

        filepath = self._resolve_asset_path(filepath)
        if filepath.startswith(self.librarypath):
            # strip local part od the path
            filepath = filepath[len(self.librarypath) :]
        if filepath.startswith(RAWURL):
            filepath = filepath[len(RAWURL) :]
        filepath = filepath.replace("\\", "/")
        if filepath.startswith("/"):
            filepath = filepath[1:]
        filepath = urllib.parse.quote(filepath)
        return filepath

    def onExternalSearch(self, index):
        """searches on external websites"""

        if index > 0:
            baseurl = self.form.comboSearch.itemData(index)
            term = self.form.searchBox.text()
            if term:
                self.openUrl(baseurl + self.urlencode(term))


if FreeCAD.GuiUp:

    from PySide import QtCore, QtGui

    class LibraryModel(QtGui.QFileSystemModel):
        "a custom QFileSystemModel that displays FreeCAD file icons"

        def __init__(self):

            QtGui.QFileSystemModel.__init__(self)

        def data(self, index, role):

            if index.column() == 0 and role == QtCore.Qt.DecorationRole:
                if index.data().lower().endswith(".fcstd"):
                    return QtGui.QIcon(":icons/freecad-doc.png")
                elif index.data().lower().endswith(".ifc"):
                    return QtGui.QIcon(os.path.join(os.path.dirname(__file__), "icons", "IFC.svg"))
                elif index.data().lower() == "private":
                    return QtGui.QIcon.fromTheme("folder-lock")
            return super(LibraryModel, self).data(index, role)


FreeCADGui.addCommand("BIM_Library", BIM_Library())

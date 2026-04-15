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

import BimAssetSemantics
import BimLibrarySources
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
PREVIEW_MODE_AUTO = "auto"
PREVIEW_MODE_2D = "2d"
PREVIEW_MODE_3D = "3d"
PREVIEW_IMAGE_SIZE = 256
PREVIEW_IMAGE_PADDING = 18
PREVIEW_3D_DIRECTION = FreeCAD.Vector(1.0, -1.0, 0.85)


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


def _normalize_library_root_entries(entries):

    return BimLibrarySources.coerce_library_roots(entries)


def resolve_library_root_entries():

    return BimLibrarySources.resolve_library_roots()


def resolve_library_root_info():

    return BimLibrarySources.resolve_library_root_info()


def resolve_library_root():

    return BimLibrarySources.resolve_library_root()


def resolve_library_roots():

    return BimLibrarySources.resolve_library_root_paths()


def get_configured_library_roots():

    return BimLibrarySources.get_configured_library_roots()


def get_configured_library_root_entries():

    return BimLibrarySources.get_configured_library_root_entries()


class BIM_LibraryRootManagerDialog:
    """Dialog used to manage configured local library roots."""

    def __init__(self, parent=None, configured_roots=None):

        from PySide import QtCore, QtGui

        self._qtcore = QtCore
        self._qtgui = QtGui
        self.dialog = QtGui.QDialog(parent)
        self.dialog.setWindowTitle(translate("BIM", "Manage local libraries"))
        self.dialog.resize(560, 360)

        layout = QtGui.QVBoxLayout(self.dialog)

        intro = QtGui.QLabel(
            translate(
                "BIM",
                "Configured libraries are searched before discovered module libraries. "
                "The first enabled configured root has the highest priority.",
            ),
            self.dialog,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        body_layout = QtGui.QHBoxLayout()
        self.listWidget = QtGui.QListWidget(self.dialog)
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.listWidget.currentRowChanged.connect(self._update_buttons)
        self.listWidget.itemChanged.connect(lambda *_args: self._update_buttons())
        body_layout.addWidget(self.listWidget, 1)

        controls_layout = QtGui.QVBoxLayout()
        self.buttonAdd = QtGui.QPushButton(translate("BIM", "Add folder..."), self.dialog)
        self.buttonRemove = QtGui.QPushButton(translate("BIM", "Remove"), self.dialog)
        self.buttonMoveUp = QtGui.QPushButton(translate("BIM", "Move up"), self.dialog)
        self.buttonMoveDown = QtGui.QPushButton(translate("BIM", "Move down"), self.dialog)
        self.buttonAdd.clicked.connect(self.onAddFolder)
        self.buttonRemove.clicked.connect(self.onRemoveSelected)
        self.buttonMoveUp.clicked.connect(lambda: self._move_current_item(-1))
        self.buttonMoveDown.clicked.connect(lambda: self._move_current_item(1))
        controls_layout.addWidget(self.buttonAdd)
        controls_layout.addWidget(self.buttonRemove)
        controls_layout.addWidget(self.buttonMoveUp)
        controls_layout.addWidget(self.buttonMoveDown)
        controls_layout.addStretch(1)
        body_layout.addLayout(controls_layout)
        layout.addLayout(body_layout)

        hint = QtGui.QLabel(
            translate(
                "BIM",
                "Checked entries are enabled. Unchecked entries stay configured but are skipped.",
            ),
            self.dialog,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        self.buttonBox = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel,
            self.dialog,
        )
        self.buttonBox.accepted.connect(self.dialog.accept)
        self.buttonBox.rejected.connect(self.dialog.reject)
        layout.addWidget(self.buttonBox)

        for entry in configured_roots or []:
            self.addConfiguredRoot(entry)

        if self.listWidget.count():
            self.listWidget.setCurrentRow(0)
        self._update_buttons()

    def exec_(self):

        return self.dialog.exec_()

    def _format_item_text(self, path):

        label = BimLibrarySources.get_library_root_label(path)
        if not os.path.isdir(path):
            label = "{} [{}]".format(label, translate("BIM", "Missing"))
        return "{}\n{}".format(label, path)

    def _create_item(self, path, enabled=True):

        item = self._qtgui.QListWidgetItem(self._format_item_text(path))
        item.setFlags(
            item.flags()
            | self._qtcore.Qt.ItemIsEnabled
            | self._qtcore.Qt.ItemIsSelectable
            | self._qtcore.Qt.ItemIsUserCheckable
        )
        item.setData(self._qtcore.Qt.UserRole, path)
        item.setToolTip(path)
        item.setCheckState(self._qtcore.Qt.Checked if enabled else self._qtcore.Qt.Unchecked)
        return item

    def addConfiguredRoot(self, entry):

        path = BimLibrarySources.normalize_library_root(getattr(entry, "path", entry))
        if not path:
            return False
        enabled = bool(getattr(entry, "enabled", True))
        for row in range(self.listWidget.count()):
            item = self.listWidget.item(row)
            if item.data(self._qtcore.Qt.UserRole) == path:
                item.setCheckState(
                    self._qtcore.Qt.Checked if enabled else self._qtcore.Qt.Unchecked
                )
                self.listWidget.setCurrentRow(row)
                self._update_buttons()
                return False

        item = self._create_item(path, enabled)
        self.listWidget.addItem(item)
        self.listWidget.setCurrentItem(item)
        self._update_buttons()
        return True

    def onAddFolder(self):

        path = self._qtgui.QFileDialog.getExistingDirectory(
            self.dialog,
            translate("BIM", "Add library folder"),
            "",
            self._qtgui.QFileDialog.ShowDirsOnly,
        )
        if path:
            self.addConfiguredRoot(path)

    def onRemoveSelected(self):

        row = self.listWidget.currentRow()
        if row < 0:
            return
        item = self.listWidget.takeItem(row)
        del item
        if self.listWidget.count():
            self.listWidget.setCurrentRow(min(row, self.listWidget.count() - 1))
        self._update_buttons()

    def _move_current_item(self, offset):

        row = self.listWidget.currentRow()
        if row < 0:
            return
        target_row = row + offset
        if target_row < 0 or target_row >= self.listWidget.count():
            return
        item = self.listWidget.takeItem(row)
        self.listWidget.insertItem(target_row, item)
        self.listWidget.setCurrentRow(target_row)
        self._update_buttons()

    def _update_buttons(self, *_args):

        row = self.listWidget.currentRow()
        count = self.listWidget.count()
        has_selection = row >= 0
        self.buttonRemove.setEnabled(has_selection)
        self.buttonMoveUp.setEnabled(has_selection and row > 0)
        self.buttonMoveDown.setEnabled(has_selection and row < (count - 1))

    def getConfiguredRoots(self):

        entries = []
        for row in range(self.listWidget.count()):
            item = self.listWidget.item(row)
            path = BimLibrarySources.normalize_library_root(item.data(self._qtcore.Qt.UserRole))
            if not path:
                continue
            entries.append(
                BimLibrarySources.ConfiguredLibraryRoot(
                    path,
                    item.checkState() == self._qtcore.Qt.Checked,
                )
            )
        return entries


class BIM_Library:

    def GetResources(self):
        return {
            "Pixmap": "BIM_Library",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Library", "BIM Library"),
            "ToolTip": QT_TRANSLATE_NOOP("BIM_Library", "Opens the BIM library"),
        }

    def Activated(self):

        self.libraryroots = resolve_library_root_entries()
        self.librarypath = self.libraryroots[0].path if self.libraryroots else ""
        self.librarysource = (
            self.libraryroots[0].source
            if self.libraryroots
            else BimLibrarySources.LIBRARY_SOURCE_NONE
        )
        target_gui_doc = getattr(FreeCADGui, "ActiveDocument", None)
        target_doc_name = ""
        if target_gui_doc and getattr(target_gui_doc, "Document", None):
            target_doc_name = target_gui_doc.Document.Name
        panel = BIM_Library_TaskPanel(
            offlinemode=bool(self.libraryroots),
            libraryroots=self.libraryroots,
            target_doc_name=target_doc_name,
        )
        task = FreeCADGui.Control.showDialog(panel, target_gui_doc)
        task.setDocumentName(panel.mainDocName)
        task.setAutoCloseOnDeletedDocument(True)


class BIM_Library_TaskPanel:

    def __init__(
        self,
        offlinemode=False,
        librarypath="",
        librarysource="",
        target_doc_name="",
        libraryroots=None,
    ):

        from PySide import QtCore, QtGui

        self._qtcore = QtCore
        if target_doc_name:
            self.mainDocName = target_doc_name
        else:
            self.mainDocName = FreeCAD.Gui.ActiveDocument.Document.Name
        self.previewDocName = "Viewer"

        self.linked = False
        self.instance_definition_roots = []
        self._local_search_index = None
        self._local_search_index_root = None
        self._local_root_asset_counts = {}
        self._local_root_asset_counts_signature = None
        self._auto_preview_mode_state = None
        self._expanded_tree_paths = set()

        resolved_roots = resolve_library_root_entries()
        if libraryroots is not None:
            initial_roots = _normalize_library_root_entries(libraryroots)
        elif isinstance(librarypath, (list, tuple)):
            initial_roots = _normalize_library_root_entries(librarypath)
        elif librarypath:
            initial_roots = _normalize_library_root_entries(
                [
                    {
                        "path": librarypath,
                        "source": librarysource or BimLibrarySources.LIBRARY_SOURCE_PROVIDED,
                    }
                ]
            )
        else:
            initial_roots = resolved_roots
        self._set_library_roots(initial_roots)
        self.form = FreeCADGui.PySideUic.loadUi(":/ui/dialogLibrary.ui")
        self.form.setWindowIcon(QtGui.QIcon(":/icons/BIM_Library.svg"))
        self.form.libraryHeader = QtGui.QFrame(self.form)
        self.form.libraryHeader.setObjectName("libraryHeader")
        self.form.libraryHeaderLayout = QtGui.QVBoxLayout(self.form.libraryHeader)
        self.form.libraryHeaderLayout.setContentsMargins(0, 0, 0, 0)
        self.form.libraryHeaderLayout.setSpacing(2)
        self.form.libraryHeaderTopLayout = QtGui.QHBoxLayout()
        self.form.libraryHeaderTopLayout.setContentsMargins(0, 0, 0, 0)
        self.form.libraryHeaderTopLayout.setSpacing(4)
        self.form.labelLibraryRootStatus = QtGui.QLabel(self.form.libraryHeader)
        self.form.labelLibraryRootStatus.setObjectName("labelLibraryRootStatus")
        self.form.labelLibraryRootStatus.setWordWrap(False)
        self.form.labelLibraryRootStatus.setTextFormat(QtCore.Qt.RichText)
        self.form.libraryHeaderTopLayout.addWidget(self.form.labelLibraryRootStatus, 1)
        self.form.buttonManageLibraries = QtGui.QToolButton(self.form.libraryHeader)
        self.form.buttonManageLibraries.setObjectName("buttonManageLibraries")
        self.form.buttonManageLibraries.setAutoRaise(True)
        self.form.buttonManageLibraries.setText("")
        self.form.buttonManageLibraries.setIcon(
            QtGui.QIcon.fromTheme(
                "preferences-system",
                QtGui.QIcon(":/icons/preferences-general.svg"),
            )
        )
        self.form.buttonManageLibraries.setToolTip(
            translate(
                "BIM",
                "Add, remove, reorder, or disable configured local libraries.",
            )
        )
        self.form.buttonManageLibraries.clicked.connect(self.onManageLibraries)
        self.form.libraryHeaderTopLayout.addWidget(
            self.form.buttonManageLibraries, 0, QtCore.Qt.AlignTop
        )
        self.form.libraryHeaderLayout.addLayout(self.form.libraryHeaderTopLayout)
        self.form.labelLibraryRootSummary = QtGui.QLabel(self.form.libraryHeader)
        self.form.labelLibraryRootSummary.setObjectName("labelLibraryRootSummary")
        self.form.labelLibraryRootSummary.setWordWrap(True)
        self.form.labelLibraryRootSummary.setStyleSheet("color: #666;")
        self.form.libraryHeaderLayout.addWidget(self.form.labelLibraryRootSummary)
        self.form.labelLibraryRootSources = QtGui.QLabel(self.form.libraryHeader)
        self.form.labelLibraryRootSources.setObjectName("labelLibraryRootSources")
        self.form.labelLibraryRootSources.setWordWrap(True)
        self.form.labelLibraryRootSources.setTextFormat(QtCore.Qt.RichText)
        self.form.libraryHeaderLayout.addWidget(self.form.labelLibraryRootSources)
        self.form.verticalLayout.insertWidget(0, self.form.libraryHeader)
        self.form.labelLibraryModeStatus = QtGui.QLabel(self.form)
        self.form.labelLibraryModeStatus.setObjectName("labelLibraryModeStatus")
        self.form.labelLibraryModeStatus.setWordWrap(True)
        self.form.labelLibraryModeStatus.hide()
        self.form.labelLibraryModeStatus.setStyleSheet("color: #666;")
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
        self.form.comboPreviewMode = QtGui.QComboBox(self.form)
        self.form.comboPreviewMode.setObjectName("comboPreviewMode")
        self.form.comboPreviewMode.addItem(translate("BIM", "Auto"), PREVIEW_MODE_AUTO)
        self.form.comboPreviewMode.addItem(translate("BIM", "2D plan"), PREVIEW_MODE_2D)
        self.form.comboPreviewMode.addItem(translate("BIM", "3D model"), PREVIEW_MODE_3D)
        self.form.comboPreviewMode.setToolTip(
            translate(
                "BIM",
                "Choose how local asset previews are generated. Auto uses 2D in Plan Edit and 3D otherwise.",
            )
        )
        self.form.horizontalLayout_5.insertWidget(1, self.form.comboPreviewMode)
        self.previewModeTimer = QtCore.QTimer(self.form)
        self.previewModeTimer.setInterval(750)
        self.previewModeTimer.timeout.connect(self._refresh_preview_mode_if_needed)
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
        self.form.tree.collapsed.connect(self.onTreeCollapsed)
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
        self.form.label_2.hide()
        self.form.searchBox.setPlaceholderText(translate("BIM", "Search local assets"))
        try:
            self.form.searchBox.setClearButtonEnabled(True)
        except Exception:
            pass
        self.form.comboSearch.setToolTip(translate("BIM", "Search external asset websites"))
        self.form.comboSearch.setMinimumContentsLength(6)
        self.form.comboSearch.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.form.comboSearch.setMaximumWidth(110)

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
        self.form.comboSearch.setItemText(0, translate("BIM", "Web"))
        for k, v in sites.items():
            self.form.comboSearch.addItem(QtGui.QIcon(":/icons/" + v[0]), k, v[1])
        self.form.comboSearch.currentIndexChanged.connect(self.onExternalSearch)

        # retrieve preferences
        self.form.checkOnline.toggled.connect(self.onCheckOnline)
        self.form.checkOnline.setText(translate("BIM", "Online"))
        self.form.checkOnline.setToolTip(
            translate(
                "BIM",
                "Shows the online catalog instead of local libraries. When enabled, local assets are hidden from the tree.",
            )
        )
        mode_chosen = PARAMS.GetBool("LibraryModeChosen", False)
        initial_online = PARAMS.GetBool("LibraryOnline", not offlinemode)
        if not mode_chosen:
            initial_online = False if self.libraryroots else True
        if not self.libraryroots:
            initial_online = True
        self.form.checkOnline.setChecked(initial_online)
        self.form.checkFCStdOnly.toggled.connect(self.onCheckFCStdOnly)
        self.form.checkFCStdOnly.setText(translate("BIM", "Other formats"))
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
        self._set_preview_mode(PARAMS.GetString("LibraryPreviewMode", PREVIEW_MODE_AUTO))
        self.form.comboPreviewMode.currentIndexChanged.connect(self.onPreviewModeChanged)
        self._update_preview_mode_watch()
        self._set_empty_preview_state()

        # update the tree
        self.onCheckOnline()

    def _set_library_roots(self, libraryroots):

        self.libraryroots = _normalize_library_root_entries(libraryroots)
        self.librarypaths = [entry.path for entry in self.libraryroots]
        self.librarypath = self.librarypaths[0] if self.librarypaths else ""
        self.librarysource = (
            self.libraryroots[0].source
            if self.libraryroots
            else BimLibrarySources.LIBRARY_SOURCE_NONE
        )

    def _get_asset_count_label(self, count):

        if count == 1:
            return translate("BIM", "1 asset")
        return translate("BIM", "{} assets").format(count)

    def _count_browsable_assets(self, folder):

        try:
            names = os.listdir(folder)
        except OSError:
            return 0

        count = 0
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                if os.path.isfile(os.path.join(path, ASSET_MANIFEST)):
                    count += 1
                else:
                    count += self._count_browsable_assets(path)
                continue
            if os.path.isfile(path) and self._is_library_file_candidate(name):
                count += 1
        return count

    def _get_local_library_root_asset_counts(self):

        signature = self._get_local_library_root_signature()
        if self._local_root_asset_counts_signature != signature:
            self._local_root_asset_counts = {
                entry.path: self._count_browsable_assets(entry.path) for entry in self.libraryroots
            }
            self._local_root_asset_counts_signature = signature
        return self._local_root_asset_counts

    def _get_local_library_root_asset_count(self, root_path):

        return self._get_local_library_root_asset_counts().get(root_path, 0)

    def _refresh_library_browser(self, online_mode=None):

        self._invalidate_local_search_index()
        self._update_library_root_status()

        if online_mode is None:
            online_mode = self.form.checkOnline.isChecked()
        search_text = self.form.searchBox.text().strip()
        if online_mode:
            self.setOnlineModel()
        else:
            self.setFileModel()
        self._update_library_mode_status(online_mode)
        if search_text:
            self.setSearchModel(search_text)

    def _coerce_preview_mode(self, mode):

        mode = str(mode or PREVIEW_MODE_AUTO).strip().lower()
        if mode in {PREVIEW_MODE_AUTO, PREVIEW_MODE_2D, PREVIEW_MODE_3D}:
            return mode
        return PREVIEW_MODE_AUTO

    def _set_preview_mode(self, mode):

        mode = self._coerce_preview_mode(mode)
        index = self.form.comboPreviewMode.findData(mode)
        if index < 0:
            index = self.form.comboPreviewMode.findData(PREVIEW_MODE_AUTO)
        self.form.comboPreviewMode.setCurrentIndex(max(index, 0))

    def _get_selected_preview_mode(self):

        return self._coerce_preview_mode(self.form.comboPreviewMode.currentData())

    def _get_effective_preview_mode(self):

        mode = self._get_selected_preview_mode()
        if mode != PREVIEW_MODE_AUTO:
            return mode
        if self._should_prefer_plan_symbol_preview():
            return PREVIEW_MODE_2D
        return PREVIEW_MODE_3D

    def _update_preview_mode_watch(self):

        effective_mode = self._get_effective_preview_mode()
        can_watch = False
        try:
            current_thread = self._qtcore.QThread.currentThread()
            can_watch = bool(current_thread and current_thread.eventDispatcher())
        except Exception:
            can_watch = False
        if self._get_selected_preview_mode() == PREVIEW_MODE_AUTO:
            self._auto_preview_mode_state = effective_mode
            if can_watch and not self.previewModeTimer.isActive():
                self.previewModeTimer.start()
            if not can_watch:
                self.previewModeTimer.stop()
            return
        self._auto_preview_mode_state = effective_mode
        self.previewModeTimer.stop()

    def _refresh_preview_mode_if_needed(self):

        if self._get_selected_preview_mode() != PREVIEW_MODE_AUTO:
            self.previewModeTimer.stop()
            return
        effective_mode = self._get_effective_preview_mode()
        if effective_mode == self._auto_preview_mode_state:
            return
        self._auto_preview_mode_state = effective_mode
        self._refresh_current_preview()

    def onPreviewModeChanged(self, _index=None):

        mode = self._get_selected_preview_mode()
        PARAMS.SetString("LibraryPreviewMode", mode)
        self._update_preview_mode_watch()
        self._refresh_current_preview()

    def _apply_configured_library_root_entries(self, entries, online_mode=None):

        BimLibrarySources.set_configured_library_root_entries(entries)
        self._set_library_roots(resolve_library_root_entries())
        self._refresh_library_browser(online_mode)

    def onManageLibraries(self):

        dialog = BIM_LibraryRootManagerDialog(
            self.form,
            get_configured_library_root_entries(),
        )
        if dialog.exec_() == dialog._qtgui.QDialog.Accepted:
            self._apply_configured_library_root_entries(
                dialog.getConfiguredRoots(),
                self.form.checkOnline.isChecked(),
            )

    def _get_library_source_label(self, source=None):

        source = source or self.librarysource
        labels = {
            BimLibrarySources.LIBRARY_SOURCE_CONFIGURED: translate("BIM", "Configured"),
            BimLibrarySources.LIBRARY_SOURCE_MODULE: translate("BIM", "Module"),
            BimLibrarySources.LIBRARY_SOURCE_LEGACY: translate("BIM", "Legacy"),
            BimLibrarySources.LIBRARY_SOURCE_PROVIDED: translate("BIM", "Custom"),
            BimLibrarySources.LIBRARY_SOURCE_NONE: translate("BIM", "Not found"),
        }
        return labels.get(source, source or translate("BIM", "Unknown"))

    def _format_status_badge(self, text):

        return (
            '<span style="color:#555; background:#f0f0f0; '
            'border:1px solid #d8d8d8; border-radius:6px; padding:1px 6px;">{}</span>'
        ).format(html.escape(text))

    def _get_matching_library_root(self, filepath):

        filepath = BimLibrarySources.normalize_library_root(filepath)
        matches = [root for root in self.librarypaths if filepath.startswith(root)]
        if not matches:
            return ""
        return max(matches, key=len)

    def _get_library_root_label(self, entry):

        return BimLibrarySources.get_library_root_label(entry)

    def _get_library_root_tree_label(self, entry):

        return self._get_library_root_label(entry)

    def _get_library_root_tree_text(self, entry):

        label = self._get_library_root_tree_label(entry) or os.path.basename(entry.path)
        count = self._get_local_library_root_asset_count(getattr(entry, "path", ""))
        return "{} · {}".format(label, count)

    def _get_local_library_summary(self):

        count = len(self.libraryroots)
        if count == 1:
            return translate("BIM", "1 local library")
        if count > 1:
            return translate("BIM", "{} local libraries").format(count)
        return ""

    def _get_local_library_detail_summary(self):

        if len(self.libraryroots) == 1:
            return self._get_library_root_tree_text(self.libraryroots[0])
        return ""

    def _get_local_library_source_badges(self):

        source_labels = []
        for entry in self.libraryroots:
            source_label = self._get_library_source_label(entry.source)
            if source_label not in source_labels:
                source_labels.append(source_label)
        return source_labels

    def _get_library_root_tooltip(self):

        return "\n\n".join(
            "{}\n{}\n{}".format(
                "{} · {}".format(
                    self._get_library_root_label(entry),
                    self._get_library_source_label(getattr(entry, "source", None)),
                ),
                self._get_asset_count_label(
                    self._get_local_library_root_asset_count(getattr(entry, "path", ""))
                ),
                entry.path,
            )
            for entry in self.libraryroots
        )

    def _get_local_library_root_signature(self):

        return tuple(self.librarypaths)

    def _update_library_root_status(self):

        if self.libraryroots:
            summary = self._get_local_library_summary()
            tooltip = self._get_library_root_tooltip()
            detail = self._get_local_library_detail_summary()
            badges = self._get_local_library_source_badges()
            text = "<b>{}</b>".format(html.escape(summary))
        else:
            tooltip = translate(
                "BIM",
                "Set a library folder explicitly or mount a marked module library root.",
            )
            detail = ""
            badges = []
            text = "<b>{}</b>".format(html.escape(translate("BIM", "No local library detected")))
        self.form.labelLibraryRootStatus.setText(text)
        self.form.labelLibraryRootStatus.setToolTip(tooltip)
        self.form.labelLibraryRootSummary.setText(detail)
        self.form.labelLibraryRootSummary.setToolTip(tooltip)
        self.form.labelLibraryRootSummary.setVisible(bool(detail))
        self.form.labelLibraryRootSources.setText(
            " ".join(self._format_status_badge(label) for label in badges)
        )
        self.form.labelLibraryRootSources.setToolTip(tooltip)
        self.form.labelLibraryRootSources.setVisible(bool(badges))

    def _update_library_mode_status(self, online_mode):

        label = self.form.labelLibraryModeStatus
        if online_mode and self.libraryroots:
            label.setText(
                translate(
                    "BIM",
                    "Showing online catalog. Local library content is hidden in this mode.",
                )
            )
            label.setToolTip(self._get_library_root_tooltip())
            label.show()
            return
        if (not online_mode) and (not self.libraryroots):
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
        if not self.libraryroots:
            return
        if len(self.libraryroots) == 1:
            self._populate_local_folder_item(self.filemodel, self.librarypath)
            return

        used_labels = {}
        for entry in self.libraryroots:
            label = self._make_unique_entry_label(
                used_labels,
                self._get_library_root_tree_text(entry),
                self._get_library_root_label(entry) or os.path.basename(entry.path),
            )
            used_labels[label] = entry.path
            root_item = self._create_tree_folder_item(label, entry.path)
            self.filemodel.appendRow(root_item)
            self._populate_local_folder_item(root_item, entry.path)

    def _capture_expanded_tree_paths(self):

        expanded = set()
        found_local_folder = [False]

        def collect(parent_index=None):
            parent_index = parent_index or self._qtcore.QModelIndex()
            for row in range(self.filemodel.rowCount(parent_index)):
                index = self.filemodel.index(row, 0, parent_index)
                item = self.filemodel.itemFromIndex(index)
                if not item or item.data(self._tree_item_kind_role) != "folder":
                    continue
                item_path = BimLibrarySources.normalize_library_root(item.toolTip())
                if self._get_matching_library_root(item_path):
                    found_local_folder[0] = True
                if self.form.tree.isExpanded(index):
                    if self._get_matching_library_root(item_path):
                        expanded.add(item_path)
                    collect(index)

        collect()
        if found_local_folder[0]:
            self._expanded_tree_paths = expanded

    def _get_default_expanded_tree_paths(self):

        if len(self.libraryroots) > 1:
            return {entry.path for entry in self.libraryroots}
        return set()

    def _get_tree_expansion_restore_paths(self):

        if self._expanded_tree_paths:
            return set(self._expanded_tree_paths)
        return self._get_default_expanded_tree_paths()

    def _remember_tree_expansion_state(self, path, expanded):

        path = BimLibrarySources.normalize_library_root(path)
        if not path:
            return
        if expanded:
            self._expanded_tree_paths.add(path)
        else:
            self._expanded_tree_paths.discard(path)

    def _expand_tree_item_path(self, item, target_path):

        if not item or item.data(self._tree_item_kind_role) != "folder":
            return False

        item_path = BimLibrarySources.normalize_library_root(item.toolTip())
        target_path = BimLibrarySources.normalize_library_root(target_path)
        if not item_path or not target_path:
            return False

        item_index = self.filemodel.indexFromItem(item)
        if item_path == target_path:
            self.form.tree.setExpanded(item_index, True)
            return True

        if not target_path.startswith(item_path.rstrip("/") + "/"):
            return False

        if not item.data(self._tree_item_loaded_role):
            self._populate_local_folder_item(item, item_path)
        self.form.tree.setExpanded(item_index, True)
        for row in range(item.rowCount()):
            if self._expand_tree_item_path(item.child(row), target_path):
                return True
        return False

    def _restore_tree_expansion_state(self):

        if self.form.checkOnline.isChecked() or self.form.searchBox.text():
            return

        target_paths = self._get_tree_expansion_restore_paths()
        if not target_paths:
            return

        for path in sorted(target_paths, key=lambda value: value.count("/")):
            for row in range(self.filemodel.rowCount()):
                if self._expand_tree_item_path(self.filemodel.item(row), path):
                    break

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
        self._remember_tree_expansion_state(item.toolTip(), True)
        if item.data(self._tree_item_loaded_role):
            return
        self._populate_local_folder_item(item, item.toolTip())

    def onTreeCollapsed(self, index):

        if self.form.checkOnline.isChecked() or self.form.searchBox.text():
            return
        item = self.filemodel.itemFromIndex(index)
        if not item or item.data(self._tree_item_kind_role) != "folder":
            return
        self._remember_tree_expansion_state(item.toolTip(), False)

    def onTreeDoubleClicked(self, index):

        item = self.filemodel.itemFromIndex(index)
        if not item:
            return
        if item.data(self._tree_item_kind_role) == "folder":
            self.form.tree.setExpanded(index, not self.form.tree.isExpanded(index))
            return
        self.link(index)

    def _get_current_tree_index(self):

        current_index = self.form.tree.currentIndex()
        if current_index and current_index.isValid():
            return current_index
        selection_model = self.form.tree.selectionModel()
        if not selection_model:
            return None
        indexes = selection_model.selectedRows()
        if indexes:
            return indexes[0]
        return None

    def _get_current_tree_raw_path(self):

        index = self._get_current_tree_index()
        if not index:
            return ""
        item = self.filemodel.itemFromIndex(index)
        if not item:
            return ""
        return item.toolTip()

    def _set_empty_preview_state(self, message=None):

        message = message or translate("BIM", "Select an asset to preview and insert")
        self.form.framePreview.clear()
        self.form.framePreview.setText(message)
        self.form.previewTitle.clear()
        self.form.previewMeta.clear()
        self.form.previewSummary.clear()
        self.form.previewSummary.hide()
        self.form.previewDetails.hide()

    def _sync_preview_to_tree_selection(self):

        raw_path = self._get_current_tree_raw_path()
        if not raw_path:
            self._set_empty_preview_state()
            return
        self._update_preview_for_raw_path(raw_path)

    def _refresh_current_preview(self):

        raw_path = self._get_current_tree_raw_path()
        if raw_path:
            self._update_preview_for_raw_path(raw_path)
        else:
            self._set_empty_preview_state()

    def _update_preview_for_raw_path(self, raw_path):

        from PySide import QtGui

        if not raw_path:
            self._set_empty_preview_state()
            return

        metadata = self._get_preview_metadata(raw_path)
        thumb = self.getThumbnail(raw_path)
        if thumb:
            px = QtGui.QPixmap(thumb)
        else:
            px = QtGui.QPixmap()
        self.form.framePreview.setPixmap(px)
        if px.isNull():
            if os.path.isdir(raw_path):
                self.form.framePreview.setText(
                    translate("BIM", "Select an asset to preview and insert")
                )
            else:
                self.form.framePreview.setText(translate("BIM", "No preview available"))
        else:
            self.form.framePreview.setText("")
        self._update_preview_details(metadata)

    def onItemSelected(self, selected, deselected):
        """Generates and displays needed previews"""

        if not selected or not selected[0].indexes():
            self._set_empty_preview_state()
            return
        index = selected[0].indexes()[0]
        item = self.filemodel.itemFromIndex(index)
        if not item:
            self._set_empty_preview_state()
            return
        raw_path = item.toolTip()
        self._update_preview_for_raw_path(raw_path)

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
        self._capture_expanded_tree_paths()
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
                add_line(
                    entry.get("display_label", entry["label"]), entry["path"], entry["search_text"]
                )
        self.modelmode = 0
        self._sync_preview_to_tree_selection()

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

        self._capture_expanded_tree_paths()
        self._set_tree_model(self.filemodel)
        self._populate_local_root_model()
        self.modelmode = 0
        self._restore_tree_expansion_state()
        self._sync_preview_to_tree_selection()

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

        self._capture_expanded_tree_paths()
        self._set_tree_model(self.filemodel)
        self.filemodel.clear()
        d = self.getOfflineLib()
        addItems(self.filemodel, d, ":github")
        self.modelmode = 0
        self._sync_preview_to_tree_selection()

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
                "summary": translate("BIM", "Open a folder or select an asset to preview."),
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

        meta_parts = list(metadata.get("meta_parts") or [])
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

        return BimAssetSemantics.get_asset_manifest_path(path, asset_manifest=ASSET_MANIFEST)

    def _get_asset_representation_data(self, manifest, primary_key, aliases=()):

        return BimAssetSemantics.get_asset_representation_data(
            manifest, primary_key, aliases=aliases
        )

    def _get_asset_representation_path(self, manifest_path, representation):

        return BimAssetSemantics.get_asset_representation_path(manifest_path, representation)

    def _get_asset_representation_root_name(self, representation):

        return BimAssetSemantics.get_asset_representation_root_name(representation)

    def _get_asset_plan_contract(self, manifest, plan_representation=None):

        return BimAssetSemantics.get_asset_plan_contract(manifest, plan_representation)

    def _get_asset_kind(self, manifest):

        return BimAssetSemantics.get_asset_kind(manifest)

    def _build_asset_descriptor(self, path):

        return BimAssetSemantics.build_asset_descriptor(
            path,
            clean_path=self.cleanPath,
            load_manifest=self._load_asset_manifest,
            get_asset_label=self._get_asset_label,
            asset_manifest=ASSET_MANIFEST,
        )

    def _get_asset_provider(self, asset_descriptor):

        return BimAssetSemantics.get_provider(asset_descriptor)

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
        self._local_root_asset_counts = {}
        self._local_root_asset_counts_signature = None

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

    def _append_local_search_entries(self, entries, folder, root_path, root_label):

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
                    relative_path = os.path.relpath(manifest_path, root_path)
                    entries.append(
                        {
                            "label": label,
                            "display_label": (
                                "{} ({})".format(label, root_label)
                                if len(self.libraryroots) > 1
                                else label
                            ),
                            "path": manifest_path,
                            "search_text": self._build_local_search_text(
                                label,
                                root_label,
                                manifest.get("id"),
                                manifest.get("category"),
                                manifest.get("tags", []),
                                relative_path.replace(os.sep, " "),
                            ),
                        }
                    )
                    continue
                self._append_local_search_entries(entries, path, root_path, root_label)
                continue
            if not (os.path.isfile(path) and self._is_library_file_candidate(name)):
                continue
            relative_path = os.path.relpath(path, root_path)
            entries.append(
                {
                    "label": name,
                    "display_label": (
                        "{} ({})".format(name, root_label) if len(self.libraryroots) > 1 else name
                    ),
                    "path": path,
                    "search_text": self._build_local_search_text(
                        name,
                        root_label,
                        relative_path.replace(os.sep, " "),
                    ),
                }
            )

    def _get_local_search_index(self):

        if not self.libraryroots:
            return []
        signature = self._get_local_library_root_signature()
        if self._local_search_index is None or self._local_search_index_root != signature:
            entries = []
            for entry in self.libraryroots:
                self._append_local_search_entries(
                    entries,
                    entry.path,
                    entry.path,
                    self._get_library_root_label(entry),
                )
            self._local_search_index = entries
            self._local_search_index_root = signature
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

        if not self.libraryroots:
            tree = {}
        elif len(self.libraryroots) == 1:
            tree = self._build_local_library_tree(self.librarypath)
        else:
            tree = {}
            for entry in self.libraryroots:
                label = self._make_unique_entry_label(
                    tree,
                    self._get_library_root_tree_label(entry),
                    self._get_library_root_label(entry) or os.path.basename(entry.path),
                )
                subtree = self._build_local_library_tree(entry.path)
                if subtree:
                    tree[label] = subtree
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
        self.previewModeTimer.stop()
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

        return BimAssetSemantics.ensure_equipment_plan_symbol_property(obj)

    def _attach_plan_symbol_roots(self, definition_roots, plan_roots):

        return BimAssetSemantics.attach_plan_symbol_roots(definition_roots, plan_roots)

    def _apply_asset_plan_contract(self, definition_obj, asset_descriptor):

        return BimAssetSemantics.apply_asset_plan_contract(definition_obj, asset_descriptor)

    def _apply_asset_plan_contract_to_roots(self, definition_roots, asset_descriptor):

        return BimAssetSemantics.apply_asset_plan_contract_to_roots(
            definition_roots, asset_descriptor
        )

    def _normalize_definition_roots(self, doc, asset_group, asset_descriptor, root_objects):

        return BimAssetSemantics.normalize_definition_roots(
            self, doc, asset_group, asset_descriptor, root_objects
        )

    def _create_shape_symbol_definitions(self, doc, asset_group, asset_descriptor):

        return BimAssetSemantics.create_shape_symbol_definitions(
            self, doc, asset_group, asset_descriptor
        )

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

        return list(BimAssetSemantics.get_object_plan_shapes(obj))

    def _build_definition_preview_shape(self, definition_roots, prefer_plan_symbols=None):

        import Part

        shapes = []
        if prefer_plan_symbols is None:
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

    def _get_preview_cache_path(self, filepath, preview_mode):

        import hashlib

        cache_key = "{}::{}".format(
            str(filepath or "").replace("\\", "/"),
            self._coerce_preview_mode(preview_mode),
        )
        filename = hashlib.md5(cache_key.encode()).hexdigest() + ".png"
        return os.path.join(THUMBNAILSPATH, filename)

    def _get_preview_source_paths(self, filepath, preview_mode):

        preview_mode = self._coerce_preview_mode(preview_mode)
        sources = []
        manifest_path = self._get_asset_manifest_path(filepath)
        if manifest_path and os.path.isfile(manifest_path):
            sources.append(manifest_path)
            asset_descriptor = self._build_asset_descriptor(manifest_path)
            if preview_mode == PREVIEW_MODE_2D and asset_descriptor["plan_path"]:
                sources.append(asset_descriptor["plan_path"])
            if asset_descriptor["model_path"]:
                sources.append(asset_descriptor["model_path"])
        else:
            path = self._resolve_asset_path(filepath)
            if path:
                sources.append(path)

        normalized = []
        seen = set()
        for source in sources:
            normalized_source = os.path.normpath(source)
            if (
                not normalized_source
                or normalized_source in seen
                or not os.path.isfile(normalized_source)
            ):
                continue
            seen.add(normalized_source)
            normalized.append(normalized_source)
        return normalized

    def _is_preview_cache_current(self, cache_path, source_paths):

        if not os.path.isfile(cache_path):
            return False
        try:
            cache_mtime = os.path.getmtime(cache_path)
        except OSError:
            return False
        for source_path in source_paths:
            try:
                if os.path.getmtime(source_path) > cache_mtime:
                    return False
            except OSError:
                return False
        return True

    def _get_active_document_name(self):

        return getattr(getattr(FreeCAD, "ActiveDocument", None), "Name", "")

    def _restore_active_document(self, doc_name):

        if not doc_name:
            return
        try:
            doc = FreeCAD.getDocument(doc_name)
        except Exception:
            return
        try:
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

    def _open_hidden_preview_document(self, path):

        try:
            return FreeCAD.openDocument(path, hidden=True)
        except TypeError:
            return FreeCAD.openDocument(path, True)

    def _build_preview_shape_from_document(
        self,
        doc,
        asset_label,
        root_name=None,
        allow_helper_objects=False,
        prefer_plan_symbols=False,
    ):

        if not doc:
            return None
        try:
            doc.recompute()
        except Exception:
            pass
        root_objects = self._choose_fcstd_definition_roots(
            list(getattr(doc, "Objects", []) or []),
            asset_label,
            root_name=root_name,
            allow_helper_objects=allow_helper_objects,
        )
        if not root_objects:
            return None
        return self._build_definition_preview_shape(
            root_objects,
            prefer_plan_symbols=prefer_plan_symbols,
        )

    def _build_preview_shape_from_source_path(
        self,
        path,
        asset_label,
        root_name=None,
        allow_helper_objects=False,
        prefer_plan_symbols=False,
    ):

        import Part

        if not path or path.startswith(":github") or not os.path.isfile(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext == ".fcstd":
            previous_doc_name = self._get_active_document_name()
            preview_doc = None
            try:
                preview_doc = self._open_hidden_preview_document(path)
                return self._build_preview_shape_from_document(
                    preview_doc,
                    asset_label,
                    root_name=root_name,
                    allow_helper_objects=allow_helper_objects,
                    prefer_plan_symbols=prefer_plan_symbols,
                )
            except Exception:
                return None
            finally:
                if preview_doc and preview_doc.Name in FreeCAD.listDocuments():
                    FreeCAD.closeDocument(preview_doc.Name)
                self._restore_active_document(previous_doc_name)
        if ext in {".stp", ".step", ".brp", ".brep"}:
            try:
                shape = Part.read(path)
            except Exception:
                return None
            if shape and not shape.isNull():
                return shape
        return None

    def _build_generated_preview_shape(self, filepath, preview_mode):

        preview_mode = self._coerce_preview_mode(preview_mode)
        manifest_path = self._get_asset_manifest_path(filepath)
        if manifest_path:
            asset_descriptor = self._build_asset_descriptor(manifest_path)
            if preview_mode == PREVIEW_MODE_2D:
                plan_path = asset_descriptor["plan_path"]
                if plan_path and os.path.isfile(plan_path):
                    return self._build_preview_shape_from_source_path(
                        plan_path,
                        asset_descriptor["label"],
                        root_name=asset_descriptor["plan_root"],
                        allow_helper_objects=True,
                        prefer_plan_symbols=False,
                    )
                return self._build_preview_shape_from_source_path(
                    asset_descriptor["model_path"],
                    asset_descriptor["label"],
                    root_name=asset_descriptor["model_root"],
                    allow_helper_objects=False,
                    prefer_plan_symbols=True,
                )
            return self._build_preview_shape_from_source_path(
                asset_descriptor["model_path"],
                asset_descriptor["label"],
                root_name=asset_descriptor["model_root"],
                allow_helper_objects=False,
                prefer_plan_symbols=False,
            )

        resolved_path = self._resolve_asset_path(filepath)
        label = os.path.splitext(os.path.basename(resolved_path))[0]
        return self._build_preview_shape_from_source_path(
            resolved_path,
            label,
            prefer_plan_symbols=(preview_mode == PREVIEW_MODE_2D),
        )

    def _collect_preview_edge_points(self, shape):

        def coerce_point(point):

            if isinstance(point, FreeCAD.Vector):
                return FreeCAD.Vector(point.x, point.y, point.z)
            if hasattr(point, "x") and hasattr(point, "y") and hasattr(point, "z"):
                try:
                    return FreeCAD.Vector(point.x, point.y, point.z)
                except Exception:
                    return None
            if isinstance(point, (list, tuple)) and len(point) >= 3:
                try:
                    return FreeCAD.Vector(point[0], point[1], point[2])
                except Exception:
                    return None
            return None

        polylines = []
        for edge in getattr(shape, "Edges", []) or []:
            try:
                points = edge.discretize(Deflection=1.0)
            except Exception:
                points = []
            if not points:
                try:
                    points = edge.tessellate(1)
                except Exception:
                    points = []
            if isinstance(points, tuple) and points:
                points = points[0]
            if not points:
                points = [vertex.Point for vertex in getattr(edge, "Vertexes", [])]
            converted = [coerce_point(point) for point in points]
            converted = [point for point in converted if point is not None]
            if len(converted) >= 2:
                polylines.append(converted)
        return polylines

    def _get_preview_projection_axes(self, preview_mode):

        if preview_mode == PREVIEW_MODE_2D:
            return FreeCAD.Vector(1.0, 0.0, 0.0), FreeCAD.Vector(0.0, 1.0, 0.0)

        direction = FreeCAD.Vector(
            PREVIEW_3D_DIRECTION.x,
            PREVIEW_3D_DIRECTION.y,
            PREVIEW_3D_DIRECTION.z,
        )
        if direction.Length < 1e-9:
            direction = FreeCAD.Vector(1.0, -1.0, 1.0)
        direction.normalize()

        up_axis = FreeCAD.Vector(0.0, 0.0, 1.0)
        x_axis = up_axis.cross(direction)
        if x_axis.Length < 1e-9:
            up_axis = FreeCAD.Vector(0.0, 1.0, 0.0)
            x_axis = up_axis.cross(direction)
        if x_axis.Length < 1e-9:
            return FreeCAD.Vector(1.0, 0.0, 0.0), FreeCAD.Vector(0.0, 1.0, 0.0)

        x_axis.normalize()
        y_axis = direction.cross(x_axis)
        if y_axis.Length < 1e-9:
            return FreeCAD.Vector(1.0, 0.0, 0.0), FreeCAD.Vector(0.0, 1.0, 0.0)
        y_axis.normalize()
        return x_axis, y_axis

    def _render_generated_preview_image(self, shape, preview_mode):

        from PySide import QtCore, QtGui

        polylines = self._collect_preview_edge_points(shape)
        if not polylines:
            return None

        x_axis, y_axis = self._get_preview_projection_axes(preview_mode)
        projected = []
        min_x = None
        min_y = None
        max_x = None
        max_y = None

        for polyline in polylines:
            projected_polyline = []
            for point in polyline:
                x_coord = point.dot(x_axis)
                y_coord = point.dot(y_axis)
                projected_polyline.append((x_coord, y_coord))
                min_x = x_coord if min_x is None else min(min_x, x_coord)
                min_y = y_coord if min_y is None else min(min_y, y_coord)
                max_x = x_coord if max_x is None else max(max_x, x_coord)
                max_y = y_coord if max_y is None else max(max_y, y_coord)
            if len(projected_polyline) >= 2:
                projected.append(projected_polyline)

        if not projected or min_x is None or min_y is None or max_x is None or max_y is None:
            return None

        width = max(max_x - min_x, 1.0)
        height = max(max_y - min_y, 1.0)
        available = PREVIEW_IMAGE_SIZE - (2 * PREVIEW_IMAGE_PADDING)
        if available <= 0:
            return None
        scale = min(float(available) / width, float(available) / height)
        x_offset = (PREVIEW_IMAGE_SIZE - (width * scale)) / 2.0
        y_offset = (PREVIEW_IMAGE_SIZE - (height * scale)) / 2.0

        image = QtGui.QImage(
            PREVIEW_IMAGE_SIZE,
            PREVIEW_IMAGE_SIZE,
            QtGui.QImage.Format_ARGB32_Premultiplied,
        )
        image.fill(QtGui.QColor("#fbfbfb"))

        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor("#e4e4e4"), 1.0))
        painter.drawRect(0, 0, PREVIEW_IMAGE_SIZE - 1, PREVIEW_IMAGE_SIZE - 1)

        pen = QtGui.QPen(QtGui.QColor("#222222"))
        pen.setWidthF(1.6 if preview_mode == PREVIEW_MODE_2D else 1.35)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)

        for polyline in projected:
            polygon = QtGui.QPolygonF()
            for x_coord, y_coord in polyline:
                px = x_offset + ((x_coord - min_x) * scale)
                py = PREVIEW_IMAGE_SIZE - (y_offset + ((y_coord - min_y) * scale))
                polygon.append(QtCore.QPointF(px, py))
            if polygon.size() == 2 and polygon[0] == polygon[1]:
                painter.drawPoint(polygon[0])
            else:
                painter.drawPolyline(polygon)

        painter.end()
        return image

    def _get_generated_preview_path(self, filepath, preview_mode):

        preview_mode = self._coerce_preview_mode(preview_mode)
        cache_path = self._get_preview_cache_path(filepath, preview_mode)
        source_paths = self._get_preview_source_paths(filepath, preview_mode)
        if self._is_preview_cache_current(cache_path, source_paths):
            return cache_path

        shape = self._build_generated_preview_shape(filepath, preview_mode)
        if not shape or shape.isNull():
            return None
        image = self._render_generated_preview_image(shape, preview_mode)
        if image is None or image.isNull():
            return None

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        if image.save(cache_path):
            return cache_path
        return None

    def _next_instance_label(self, doc, base_label):

        used = {obj.Label for obj in doc.Objects}
        index = 1
        while True:
            label = f"{base_label}{index:03d}"
            if label not in used:
                return label
            index += 1

    def _create_symbol_link(self, doc, definition_obj):

        return BimAssetSemantics.create_instance(self, doc, definition_obj)

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
        return BimAssetSemantics.get_object_plan_anchor(definition_roots[0])

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
            self._sync_preview_to_tree_selection()
            if (
                self.form.previewTitle.text()
                or self.form.previewMeta.text()
                or self.form.previewSummary.text()
            ):
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
        generated_thumb = self._get_generated_preview_path(
            filepath,
            self._get_effective_preview_mode(),
        )
        if generated_thumb:
            return generated_thumb
        if manifest_path:
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
        library_root = self._get_matching_library_root(filepath)
        if library_root:
            # strip local part od the path
            filepath = filepath[len(library_root) :]
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

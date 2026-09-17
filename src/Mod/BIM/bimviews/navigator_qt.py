# SPDX-License-Identifier: LGPL-2.1-or-later

"""Qt item model for the BIM Navigator dock."""

from dataclasses import dataclass, field

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui


def configure_navigator_columns(tree):
    """Keep labels readable as the navigator dock changes width."""

    header = tree.header()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
    header.setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QtGui.QHeaderView.ResizeToContents)


@dataclass
class _Node:
    key: str
    label: str
    kind: str
    object: object = None
    value: str = ""
    height: str = ""
    hidden: bool = False
    parent: object = None
    children: list = field(default_factory=list)

    def add(self, node):
        node.parent = self
        self.children.append(node)
        return node


class BIMNavigatorQtModel(QtCore.QAbstractItemModel):
    """Present :class:`BIMNavigatorModel` as one hierarchical Qt model."""

    ObjectRole = QtCore.Qt.UserRole + 1
    KindRole = QtCore.Qt.UserRole + 2
    KeyRole = QtCore.Qt.UserRole + 3

    def __init__(self, navigator, parent=None):
        super().__init__(parent)
        self.navigator = navigator
        self.root = _Node("root", "", "root")
        self._object_nodes = {}
        self.rebuild()

    def rebuild(self, navigator=None):
        self.beginResetModel()
        if navigator is not None:
            self.navigator = navigator
        self.root = _Node("root", "", "root")
        self._object_nodes = {}
        self._build()
        self.endResetModel()

    def _build(self):
        project = self.root.add(_Node("section:project", self._tr("Project"), "section"))
        for node in self.navigator.project_nodes():
            self._add_project_node(project, node)

        views = self.root.add(_Node("section:views", self._tr("Views"), "section"))
        for group in self.navigator.saved_view_groups():
            group_node = views.add(
                _Node("view-group:" + group.key, self._tr(group.label), "view-group")
            )
            for view in group.views:
                self._add_object(group_node, view, "saved-view")
        legacy = self.navigator.legacy_views()
        if legacy:
            group_node = views.add(
                _Node("view-group:legacy", self._tr("Legacy Views"), "legacy-group")
            )
            for view in legacy:
                self._add_object(group_node, view, "legacy-view")

        current = self.root.add(
            _Node("section:current", self._tr("Current View"), "section")
        )
        scope = self.navigator.current_view_scope()
        for category in scope.categories:
            category_node = current.add(
                _Node(
                    "category:" + category.key,
                    self._tr(category.label),
                    "category",
                    value=str(len(category.objects)),
                )
            )
            hidden = set(category.hidden_objects)
            for obj in category.objects:
                self._add_object(category_node, obj, "scope-object", obj in hidden)

        sheets = self.root.add(_Node("section:sheets", self._tr("Sheets"), "section"))
        for page in self.navigator.pages():
            self._add_object(sheets, page, "sheet")

    def _add_project_node(self, parent, project_node):
        node = self._add_object(parent, project_node.object, project_node.kind.lower())
        for child in project_node.children:
            self._add_project_node(node, child)

    def _add_object(self, parent, obj, kind, hidden=False):
        elevation = ""
        height = ""
        if kind in ("building", "storey", "workingplane"):
            try:
                elevation = FreeCAD.Units.Quantity(
                    obj.Placement.Base.z, FreeCAD.Units.Length
                ).UserString
            except (AttributeError, RuntimeError):
                pass
            value = getattr(obj, "Height", None)
            if value is not None:
                height = getattr(value, "UserString", str(value))
        node = parent.add(
            _Node(
                "object:" + obj.Name,
                obj.Label,
                kind,
                object=obj,
                value=elevation,
                height=height,
                hidden=hidden,
            )
        )
        self._object_nodes.setdefault(obj.Name, []).append(node)
        return node

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._node(parent).children) if parent.column() <= 0 else 0

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 3

    def index(self, row, column, parent=QtCore.QModelIndex()):
        parent_node = self._node(parent)
        if row < 0 or row >= len(parent_node.children):
            return QtCore.QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        parent = index.internalPointer().parent
        if parent is None or parent is self.root:
            return QtCore.QModelIndex()
        grandparent = parent.parent or self.root
        return self.createIndex(grandparent.children.index(parent), 0, parent)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return (node.label, node.value, node.height)[index.column()]
        if role == self.ObjectRole:
            return node.object
        if role == self.KindRole:
            return node.kind
        if role == self.KeyRole:
            return node.key
        if role == QtCore.Qt.ToolTipRole and node.object is not None:
            return node.object.Name
        if role == QtCore.Qt.DecorationRole and index.column() == 0:
            if node.object is not None:
                try:
                    return node.object.ViewObject.Icon
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
            if node.kind in ("section", "view-group", "legacy-group", "category"):
                return QtGui.QIcon.fromTheme("folder", QtGui.QIcon(":/icons/folder.svg"))
        if role == QtCore.Qt.FontRole:
            font = QtGui.QFont()
            if node.kind == "section" or self._is_active(node):
                font.setBold(True)
            return font
        if role == QtCore.Qt.ForegroundRole and node.hidden:
            return QtGui.QBrush(QtGui.QColor(QtCore.Qt.gray))
        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole or not index.isValid():
            return False
        node = index.internalPointer()
        obj = node.object
        if obj is None:
            return False
        text = str(value)
        document = obj.Document
        document.openTransaction("Edit BIM navigator item")
        try:
            if index.column() == 0:
                obj.Label = text
                node.label = obj.Label
            elif index.column() == 1 and node.kind in ("building", "storey", "workingplane"):
                obj.Placement.Base.z = FreeCAD.Units.parseQuantity(text)
                node.value = text
            elif index.column() == 2 and hasattr(obj, "Height"):
                obj.Height = FreeCAD.Units.parseQuantity(text)
                node.height = text
            else:
                document.abortTransaction()
                return False
            document.commitTransaction()
            document.recompute()
        except Exception:
            document.abortTransaction()
            raise
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if not index.isValid():
            return flags
        node = index.internalPointer()
        try:
            has_height = node.object is not None and hasattr(node.object, "Height")
        except ReferenceError:
            # Document notifications are delivered asynchronously. Qt can ask
            # about an old index between object deletion and the queued reset.
            return flags
        if node.object is not None and index.column() == 0:
            flags |= QtCore.Qt.ItemIsEditable
        elif index.column() == 1 and node.kind in ("building", "storey", "workingplane"):
            flags |= QtCore.Qt.ItemIsEditable
        elif index.column() == 2 and has_height:
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return (self._tr("Element"), self._tr("Elevation / Count"), self._tr("Height"))[section]
        return None

    def object_for_index(self, index):
        return index.internalPointer().object if index.isValid() else None

    def kind_for_index(self, index):
        return index.internalPointer().kind if index.isValid() else ""

    def key_for_index(self, index):
        return index.internalPointer().key if index.isValid() else ""

    def indexes_for_object(self, obj):
        nodes = self._object_nodes.get(getattr(obj, "Name", ""), ())
        return [self._index_for_node(node) for node in nodes]

    def index_for_key(self, key):
        pending = list(self.root.children)
        while pending:
            node = pending.pop(0)
            if node.key == key:
                return self._index_for_node(node)
            pending.extend(node.children)
        return QtCore.QModelIndex()

    def all_project_objects(self):
        result = []
        pending = list(self.root.children[0].children)
        while pending:
            node = pending.pop(0)
            if node.object is not None:
                result.append(node.object)
            pending.extend(node.children)
        return result

    def _index_for_node(self, node):
        if node.parent is None:
            return QtCore.QModelIndex()
        return self.createIndex(node.parent.children.index(node), 0, node)

    def _node(self, index):
        return index.internalPointer() if index.isValid() else self.root

    def _is_active(self, node):
        obj = node.object
        if obj is None:
            return False
        try:
            if node.kind == "saved-view":
                return bool(getattr(obj, "BIMIsActiveView", False))
            view = FreeCADGui.activeDocument().activeView()
            return obj in (view.getActiveObject("NativeIFC"), view.getActiveObject("Arch"))
        except (AttributeError, ReferenceError, RuntimeError):
            return False

    @staticmethod
    def _tr(text):
        return FreeCAD.Qt.translate("BIM", text)

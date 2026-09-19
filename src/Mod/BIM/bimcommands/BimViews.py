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

"""The BIM Views command"""

import sys

import ArchRepresentation
import FreeCAD
import FreeCADGui
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate

PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
_view_services = {}


if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui

    class _NavigatorObserver:
        """Coalesce document and selection notifications for the navigator."""

        def __init__(self, owner):
            self.owner = owner

        def slotCreatedObject(self, obj):
            self.owner.scheduleUpdate()

        def slotDeletedObject(self, obj):
            self.owner.scheduleUpdate()

        def slotChangedObject(self, obj, prop):
            self.owner.scheduleUpdate()

        def slotActivateDocument(self, doc):
            self.owner.scheduleUpdate()

        def slotDeletedDocument(self, doc):
            self.owner.scheduleUpdate()

        def addSelection(self, doc, obj, sub, point):
            self.owner.scheduleSelectionSync()

        def removeSelection(self, doc, obj, sub):
            self.owner.scheduleSelectionSync()

        def clearSelection(self, doc):
            self.owner.scheduleSelectionSync()


    class _SectionViewPlacement:
        """Collect a plan section line and viewing side through Draft snapping."""

        def __init__(self, owner, source, reference_frame, view):
            self.owner = owner
            self.source = source
            self.reference_frame = reference_frame
            self.view = view
            self.points = []

        def start(self):
            FreeCAD.activeDraftCommand = self
            self._request_point()

        def _request_point(self):
            labels = (
                translate("BIM", "Pick section line start"),
                translate("BIM", "Pick section line end"),
                translate("BIM", "Pick the viewing side"),
            )
            last = None
            if len(self.points) == 1:
                last = self.points[0]
            elif len(self.points) == 2:
                last = (self.points[0] + self.points[1]) * 0.5
            request = ArchRepresentation.RepresentationRequest(
                purpose=ArchRepresentation.RepresentationPurpose.PLAN,
                reference_frame=self.reference_frame,
                source=self.source,
            )
            interaction_plane = self.owner.viewService._snap_plane_for(request)
            FreeCADGui.Snapper.getPoint(
                last=last,
                callback=self.accept_point,
                hints=[
                    FreeCADGui.InputHint(
                        labels[len(self.points)], FreeCADGui.UserInput.MouseLeft
                    )
                ],
                interaction_plane=interaction_plane,
                view=self.view,
            )

        def accept_point(self, point=None, _obj=None):
            if point is None:
                self.cancel()
                return
            self.points.append(FreeCAD.Vector(point))
            if len(self.points) < 3:
                self._request_point()
                return
            self._finish()

        def _finish(self):
            self._cleanup()
            self.owner._finishSectionPlacement(
                self.source,
                self.reference_frame,
                *self.points,
            )

        def cancel(self):
            self._cleanup()

        def _cleanup(self):
            FreeCADGui.Snapper.cancelPointRequest()
            FreeCADGui.Snapper.off()
            if FreeCAD.activeDraftCommand is self:
                FreeCAD.activeDraftCommand = None
            if getattr(self.owner, "_sectionPlacement", None) is self:
                self.owner._sectionPlacement = None


class BIM_Views:

    def GetResources(self):
        return {
            "Pixmap": "BIM_Views",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Views", "BIM Navigator"),
            "ToolTip": QT_TRANSLATE_NOOP("BIM_Views", "Shows or hides the BIM Navigator"),
        }

    def Activated(self):
        from PySide import QtCore, QtGui

        vm = findWidget()
        self.model = _manager_model()
        self.viewService = _view_service()
        self._updatePending = False
        self._selectionPending = False
        bimviewsbutton = None
        mw = FreeCADGui.getMainWindow()
        st = mw.statusBar()
        statuswidget = st.findChild(QtGui.QToolBar, "BIMStatusWidget")
        if statuswidget and hasattr(statuswidget, "bimviewsbutton"):
            bimviewsbutton = statuswidget.bimviewsbutton
        if vm:
            if vm.isVisible():
                vm.hide()
                if bimviewsbutton:
                    bimviewsbutton.setChecked(False)
                PARAMS.SetBool("RestoreBimViews", False)
            else:
                vm.show()
                placeInComboView(vm)
                if bimviewsbutton:
                    bimviewsbutton.setChecked(True)
                PARAMS.SetBool("RestoreBimViews", True)
                self.update()
        else:
            vm = QtGui.QDockWidget()

            # create the dialog
            self.dialog = FreeCADGui.PySideUic.loadUi(":/ui/dialogViews.ui")
            vm.setWidget(self.dialog)
            vm.navigator = self.dialog.navigator
            vm.closeEvent = self.onClose

            # set context menu
            self.dialog.navigator.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

            # set button
            self.dialog.menu = QtGui.QMenu()
            for button in [
                ("NewPlanView", translate("BIM", "New Floor Plan")),
                ("NewSectionView", translate("BIM", "New Section")),
                ("NewElevationView", translate("BIM", "New Elevation")),
                ("NewModelView", translate("BIM", "New 3D View")),
                ("Active", translate("BIM", "Active")),
                ("AddLevel", translate("BIM", "New Level Above")),
                ("AddProxy", translate("BIM", "New Working Plane Proxy")),
                ("Delete", translate("BIM", "Delete")),
                ("Toggle", translate("BIM", "Toggle Visibility")),
                ("Isolate", translate("BIM", "Isolate")),
                ("SaveView", translate("BIM", "Save Camera View")),
                ("SaveVisibility", translate("BIM", "Save Visibility of Objects")),
                ("DuplicateView", translate("BIM", "Duplicate View")),
                ("NewSheet", translate("BIM", "New Sheet…")),
                ("PlaceOnSheet", translate("BIM", "Place on Sheet…")),
                ("OpenSheet", translate("BIM", "Open Sheet")),
                ("EditSheet", translate("BIM", "Sheet Properties…")),
                ("RefreshTitleBlock", translate("BIM", "Refresh Title Block")),
                ("PublishSheet", translate("BIM", "Publish Sheet…")),
                ("PublishSheetSet", translate("BIM", "Publish Sheet Set…")),
                ("CreateIssue", translate("BIM", "Create Issue…")),
                ("CompareIssue", translate("BIM", "Compare with Previous Issue")),
                ("LocatePlacement", translate("BIM", "Locate Placement")),
                ("RemoveFromSheet", translate("BIM", "Remove from Sheet")),
                ("Rename", translate("BIM", "Rename")),
            ]:
                action = QtGui.QAction(button[1])

                # Make the "Activate" button bold, as this is the default one
                if button[0] == "Active":
                    font = action.font()
                    font.setBold(True)
                    action.setFont(font)
                    action.setCheckable(True)

                self.dialog.menu.addAction(action)
                setattr(self.dialog, "button" + button[0], action)

            # # set button icons
            self.dialog.buttonAddLevel.setIcon(QtGui.QIcon(":/icons/Arch_Floor_Tree.svg"))
            self.dialog.buttonAddProxy.setIcon(QtGui.QIcon(":/icons/Draft_PlaneProxy.svg"))
            self.dialog.buttonDelete.setIcon(QtGui.QIcon(":/icons/delete.svg"))
            self.dialog.buttonToggle.setIcon(QtGui.QIcon(":/icons/dagViewVisible.svg"))
            self.dialog.buttonIsolate.setIcon(QtGui.QIcon(":/icons/Std_ShowSelection.svg"))
            self.dialog.buttonSaveView.setIcon(QtGui.QIcon(":/icons/Std_ViewScreenShot.svg"))
            self.dialog.buttonRename.setIcon(QtGui.QIcon(":/icons/edit-edit.svg"))

            # set tooltips
            self.dialog.buttonAddLevel.setToolTip(
                translate("BIM", "Creates a new level above the highest existing one")
            )
            self.dialog.buttonAddProxy.setToolTip(
                translate("BIM", "Creates a new working plane proxy")
            )
            self.dialog.buttonDelete.setToolTip(translate("BIM", "Deletes the selected item"))
            self.dialog.buttonToggle.setToolTip(
                translate("BIM", "Toggles the visibility of selected items")
            )
            self.dialog.buttonIsolate.setToolTip(
                translate("BIM", "Turns all items off except the selected ones")
            )
            self.dialog.buttonSaveView.setToolTip(
                translate("BIM", "Saves the current camera view to the selected items")
            )
            self.dialog.buttonRename.setToolTip(translate("BIM", "Renames the selected item"))
            self.dialog.buttonActive.setToolTip(translate("BIM", "Activates the selected item"))

            # connect signals
            self.dialog.buttonAddLevel.triggered.connect(self.addLevel)
            self.dialog.buttonAddProxy.triggered.connect(self.addProxy)
            self.dialog.buttonNewPlanView.triggered.connect(self.newPlanView)
            self.dialog.buttonNewSectionView.triggered.connect(self.newSectionView)
            self.dialog.buttonNewElevationView.triggered.connect(self.newElevationView)
            self.dialog.buttonNewModelView.triggered.connect(self.newModelView)
            self.dialog.buttonDelete.triggered.connect(self.delete)
            self.dialog.buttonToggle.triggered.connect(self.toggle)
            self.dialog.buttonIsolate.triggered.connect(self.isolate)
            self.dialog.buttonSaveView.triggered.connect(self.saveView)
            self.dialog.buttonSaveVisibility.triggered.connect(self.saveVisibility)
            self.dialog.buttonDuplicateView.triggered.connect(self.duplicateView)
            self.dialog.buttonNewSheet.triggered.connect(self.newSheet)
            self.dialog.buttonPlaceOnSheet.triggered.connect(self.placeOnSheet)
            self.dialog.buttonOpenSheet.triggered.connect(self.openSheet)
            self.dialog.buttonEditSheet.triggered.connect(self.editSheet)
            self.dialog.buttonRefreshTitleBlock.triggered.connect(self.refreshTitleBlock)
            self.dialog.buttonPublishSheet.triggered.connect(self.publishSheet)
            self.dialog.buttonPublishSheetSet.triggered.connect(self.publishSheetSet)
            self.dialog.buttonCreateIssue.triggered.connect(self.createIssue)
            self.dialog.buttonCompareIssue.triggered.connect(self.compareIssue)
            self.dialog.buttonLocatePlacement.triggered.connect(self.locatePlacement)
            self.dialog.buttonRemoveFromSheet.triggered.connect(self.removeFromSheet)
            self.dialog.buttonRename.triggered.connect(self.rename)
            self.dialog.buttonActive.triggered.connect(self.activateContextItem)
            self.dialog.navigator.clicked.connect(self.select)
            self.dialog.navigator.doubleClicked.connect(self.activateIndex)
            self.dialog.navigator.customContextMenuRequested.connect(self.onNavigatorContextMenu)
            self.dialog.navigator.expanded.connect(self.saveExpansion)
            self.dialog.navigator.collapsed.connect(self.saveExpansion)
            # delay connecting after FreeCAD finishes setting up
            FreeCADGui.invokeLater(self.connectDock)

            # set the dock widget
            width = PARAMS.GetInt("BimViewWidth", 300)
            height = PARAMS.GetInt("BimViewHeight", 500)
            vm.setObjectName("BIM Navigator")
            vm.setWindowTitle(translate("BIM", "BIM Navigator"))
            mw = FreeCADGui.getMainWindow()
            vm.setGeometry(vm.x(), vm.y(), width, height)
            mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, vm)
            placeInComboView(vm)

            self.observer = _NavigatorObserver(self)
            FreeCAD.addDocumentObserver(self.observer)
            FreeCADGui.Selection.addObserver(self.observer)

            # check the status bar button
            if bimviewsbutton:
                bimviewsbutton.setChecked(True)
            PARAMS.SetBool("RestoreBimViews", True)

            self.update()

    def onClose(self, event):
        from PySide import QtGui
        from bimsheets.gui import hide_sheet_inspector

        st = FreeCADGui.getMainWindow().statusBar()
        statuswidget = st.findChild(QtGui.QToolBar, "BIMStatusWidget")
        if statuswidget and hasattr(statuswidget, "bimviewsbutton"):
            statuswidget.bimviewsbutton.setChecked(False)
        PARAMS.SetBool("RestoreBimViews", False)
        hide_sheet_inspector()
        event.accept()

    def connectDock(self):
        "watch for dock location"

        vm = findWidget()
        if vm:
            vm.dockLocationChanged.connect(self.onDockLocationChanged)

    def scheduleUpdate(self):
        if self._updatePending:
            return
        self._updatePending = True
        FreeCADGui.invokeLater(self.update)

    def scheduleSelectionSync(self):
        if self._selectionPending:
            return
        self._selectionPending = True
        FreeCADGui.invokeLater(self.syncSelection)

    def _expandedKeys(self):
        vm = findWidget()
        if not vm or not hasattr(vm, "navigatorModel"):
            return set()
        model = vm.navigatorModel
        keys = set()
        pending = [model.index(row, 0) for row in range(model.rowCount())]
        while pending:
            index = pending.pop(0)
            if vm.navigator.isExpanded(index):
                keys.add(model.key_for_index(index))
            pending.extend(model.index(row, 0, index) for row in range(model.rowCount(index)))
        return keys

    def saveExpansion(self, _index=None):
        """Persist stable virtual/object node keys across dock sessions."""

        keys = sorted(self._expandedKeys())
        PARAMS.SetString("BimNavigatorExpanded", "\n".join(keys))

    def update(self, retrigger=True):
        """Refresh the navigator in response to document notifications."""

        from bimviews.navigator_qt import BIMNavigatorQtModel, configure_navigator_columns

        self._updatePending = False
        vm = findWidget()
        if not vm or not vm.isVisible() or FreeCAD.isRestoring() or not FreeCAD.ActiveDocument:
            return
        expanded = self._expandedKeys()
        self.model = _manager_model()
        if not hasattr(vm, "navigatorModel"):
            vm.navigatorModel = BIMNavigatorQtModel(self.model, vm.navigator)
            vm.navigator.setModel(vm.navigatorModel)
            configure_navigator_columns(vm.navigator)
            saved = PARAMS.GetString("BimNavigatorExpanded", "")
            expanded = set(saved.splitlines()) if saved else {
                "section:project",
                "section:views",
                "section:current",
                "section:sheets",
            }
        else:
            vm.navigatorModel.rebuild(self.model)
        for key in expanded:
            index = vm.navigatorModel.index_for_key(key)
            if index.isValid():
                vm.navigator.setExpanded(index, True)
        PARAMS.SetBool("ViewManagerFloating", vm.isFloating())
        self.syncSelection()

    def syncSelection(self):
        self._selectionPending = False
        vm = findWidget()
        if not vm or not hasattr(vm, "navigatorModel"):
            return
        selection_model = vm.navigator.selectionModel()
        selection_model.clearSelection()
        flags = QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows
        for obj in FreeCADGui.Selection.getSelection():
            indexes = vm.navigatorModel.indexes_for_object(obj)
            for index in indexes:
                selection_model.select(index, flags)
        selected = selection_model.selectedRows(0)
        self._showSheetInspector(selected[0] if len(selected) == 1 else QtCore.QModelIndex())

    def select(self, index):
        """Synchronize an object-backed navigator row with global selection."""

        vm = findWidget()
        obj = vm.navigatorModel.object_for_index(index) if vm else None
        self._showSheetInspector(index)
        if obj is not None:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj)

    def _showSheetInspector(self, index):
        """Route Navigator context to the standard right-side Task View."""

        from bimsheets.gui import show_sheet_inspector

        vm = findWidget()
        if vm is None or not index.isValid():
            show_sheet_inspector(None, "")
            return
        show_sheet_inspector(
            vm.navigatorModel.object_for_index(index),
            vm.navigatorModel.kind_for_index(index),
            refresh_callback=lambda: self.update(False),
        )

    def activateIndex(self, index):
        vm = findWidget()
        if not vm:
            return
        obj = vm.navigatorModel.object_for_index(index)
        kind = vm.navigatorModel.kind_for_index(index)
        self.contextObject = obj
        if kind == "sheet":
            self.openSheet()
            return
        if kind == "sheet-placement":
            self.locatePlacement()
            return
        if obj is not None and kind != "scope-object":
            show(obj.Name)

    def addLevel(self):
        """Add a new level, auto-stacked above the highest sibling level.

        The new level is placed at the elevation of the highest existing
        level's top and added to the same parent building. This mirrors the
        level workflow in Revit and ArchiCAD: levels are sequential, sorted by
        elevation, and adding one extends the stack upward rather than
        colliding with existing storeys at z=0.
        """

        import Arch
        import Draft

        DEFAULT_SPACING = 3000.0  # mm, fallback vertical spacing for stacking

        # Determine sibling levels (children of the same parent), if any.
        sel = FreeCADGui.Selection.getSelection()
        parent = None
        if len(sel) == 1:
            s = sel[0]
            t = Draft.getType(s)
            if t in ["Building", "IfcBuilding"] or getattr(s, "IfcType", "") == "Building":
                parent = s
            elif t in ["BuildingPart", "Building Storey", "IfcBuildingStorey"]:
                parent = getParent(s)

        siblings = []
        scope = (
            parent.Group if parent and hasattr(parent, "Group") else FreeCAD.ActiveDocument.Objects
        )
        for o in scope:
            t = Draft.getType(o)
            if (
                t in ["BuildingPart", "Building Storey", "IfcBuildingStorey"]
                or getattr(o, "IfcType", "") == "Building Storey"
            ):
                siblings.append(o)

        top_elevation = 0.0
        if siblings:
            highest = max(siblings, key=getObjectElevation)
            h = getattr(highest, "Height", None)
            # Use the explicit height of the level below when set, otherwise a
            # default spacing, so the new level does not overlap the one below.
            spacing = h.Value if (h is not None and h.Value) else DEFAULT_SPACING
            top_elevation = getObjectElevation(highest) + spacing

        FreeCAD.ActiveDocument.openTransaction("Create Level")
        obj = Arch.makeFloor()
        setObjectElevation(obj, top_elevation)
        if parent is not None and hasattr(parent, "addObject"):
            parent.addObject(obj)
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(obj)
        self.update(False)

    def _selectedProjectContext(self):
        """Return the selected or active building/storey context, if any."""

        import Draft

        candidates = []
        context_object = getattr(self, "contextObject", None)
        if context_object is not None:
            candidates.append(context_object)
        candidates.extend(FreeCADGui.Selection.getSelection())
        active_storey = _view_service().active_storey
        if active_storey is not None:
            candidates.append(active_storey)
        for obj in candidates:
            obj_type = Draft.getType(obj)
            if obj_type in (
                "Building",
                "BuildingPart",
                "Building Storey",
                "IfcBuilding",
                "IfcBuildingStorey",
            ) or getattr(obj, "IfcType", "") in ("Building", "Building Storey"):
                return obj
        return None

    def _uniqueViewLabel(self, base):
        labels = {view.Label for view in _manager_model().saved_views()}
        if base not in labels:
            return base
        index = 2
        while "{} {}".format(base, index) in labels:
            index += 1
        return "{} {}".format(base, index)

    def newPlanView(self):
        source = self._selectedProjectContext()
        base = (
            translate("BIM", "{} Plan").format(source.Label)
            if source is not None
            else translate("BIM", "Floor Plan")
        )
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM floor plan")
        try:
            definition = _view_service().create_plan_view(
                self._uniqueViewLabel(base), source
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(definition)

    def newModelView(self):
        source = self._selectedProjectContext()
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM 3D view")
        try:
            definition = _view_service().create_model_view(
                self._uniqueViewLabel(translate("BIM", "Default 3D")), source
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(definition)

    def _selectedSectionPlane(self):
        candidates = [self.contextObject]
        candidates.extend(FreeCADGui.Selection.getSelection())
        for obj in candidates:
            if (
                obj is not None
                and getattr(getattr(obj, "Proxy", None), "Type", "") == "SectionPlane"
                and str(getattr(obj, "Purpose", "")) == "Section"
            ):
                return obj
        return None

    def newSectionView(self):
        """Save a selected section plane or draw a new section in a plan."""

        plane = self._selectedSectionPlane()
        if plane is not None:
            self._createSectionViewFromPlane(plane)
            return
        source = self._selectedProjectContext()
        active_definition = self.viewService.active_view
        if (
            active_definition is not None
            and str(getattr(active_definition, "Purpose", "")) == "Plan"
        ):
            source = self.viewService.context_source(active_definition) or source
            reference_frame = active_definition.ReferenceFrame
        elif source is not None:
            reference_frame = source.Placement
        else:
            return
        self._sectionPlacement = _SectionViewPlacement(
            self,
            source,
            reference_frame,
            FreeCADGui.ActiveDocument.ActiveView,
        )
        self._sectionPlacement.start()

    def _createSectionViewFromPlane(self, plane):
        base = translate("BIM", "{} View").format(plane.Label)
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM section")
        try:
            definition = _view_service().create_section_view(
                self._uniqueViewLabel(base), plane
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(definition)

    def _finishSectionPlacement(self, source, reference_frame, start, end, side):
        base = translate("BIM", "{} Section").format(source.Label)
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM section")
        try:
            definition = _view_service().create_section_view_from_line(
                self._uniqueViewLabel(base),
                source,
                start,
                end,
                side,
                reference_frame=reference_frame,
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(definition)

    def newElevationView(self):
        """Create the default south elevation for the selected project context."""

        source = self._selectedProjectContext()
        if source is None:
            return
        base = translate("BIM", "{} South Elevation").format(source.Label)
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM elevation")
        try:
            definition = _view_service().create_elevation_view(
                self._uniqueViewLabel(base), source, direction="South"
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(definition)

    def duplicateView(self):
        if not self.contextObject or not _view_service().is_view_definition(
            self.contextObject
        ):
            return
        document = FreeCAD.ActiveDocument
        document.openTransaction("Duplicate BIM view")
        try:
            duplicate = _view_service().duplicate_view(self.contextObject)
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(duplicate)

    def placeOnSheet(self):
        from PySide import QtGui
        from bimsheets import BIMSheetService

        definition = self.contextObject
        service = _view_service()
        if not definition or not service.can_place_on_sheet(definition):
            return
        sheet_service = BIMSheetService(FreeCAD.ActiveDocument)
        pages = [
            page
            for page in _manager_model().pages()
            if sheet_service.is_sheet(page)
        ]
        if not pages:
            QtGui.QMessageBox.information(
                self.dialog,
                translate("BIM", "Place on Sheet"),
                translate("BIM", "Create a TechDraw sheet before placing this view."),
            )
            return
        page = _preferred_sheet(FreeCAD.ActiveDocument, self._selectedObjects())
        if page is None:
            labels = [_sheet_display_label(candidate) for candidate in pages]
            label, accepted = QtGui.QInputDialog.getItem(
                self.dialog,
                translate("BIM", "Place on Sheet"),
                translate("BIM", "Sheet"),
                labels,
                0,
                False,
            )
            if not accepted:
                return
            page = pages[labels.index(label)]
        existing = service.placements_for(definition, page)
        allow_duplicate = False
        if existing:
            answer = QtGui.QMessageBox.question(
                self.dialog,
                translate("BIM", "Additional Placement"),
                translate(
                    "BIM",
                    "This view is already on the selected sheet. Add another placement?",
                ),
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.No,
            )
            if answer != QtGui.QMessageBox.Yes:
                self.contextObject = existing[0]
                self.locatePlacement()
                return
            allow_duplicate = True
        document = FreeCAD.ActiveDocument
        document.openTransaction("Place BIM view on sheet")
        try:
            drawing_view = service.place_on_sheet(
                definition, page, allow_duplicate=allow_duplicate
            )
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(drawing_view)
        FreeCADGui.getMainWindow().statusBar().showMessage(
            translate("BIM", "Placed {view} on {sheet}").format(
                view=definition.Label,
                sheet=_sheet_display_label(page),
            ),
            5000,
        )

    def newSheet(self):
        """Create a BIM sheet through the shared sheet creation workflow."""

        from bimsheets.gui import create_sheet_interactive, show_sheet_inspector

        page = create_sheet_interactive(FreeCAD.ActiveDocument, self.dialog)
        if page is None:
            return
        self.contextObject = page
        self.update(False)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(page)
        panel = show_sheet_inspector(
            page,
            "sheet",
            refresh_callback=lambda: self.update(False),
        )
        if panel is not None:
            panel.editor.title.setFocus()
            panel.editor.title.selectAll()

    def editSheet(self):
        """Edit normalized sheet metadata in one undoable operation."""

        from bimsheets.gui import edit_sheet_interactive

        page = self.contextObject
        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            return
        if edit_sheet_interactive(page, self.dialog):
            self.update(False)

    def openSheet(self):
        """Open the selected sheet or a placement's parent sheet."""

        obj = self.contextObject
        page = obj if obj and obj.isDerivedFrom("TechDraw::DrawPage") else None
        if page is None and obj is not None and hasattr(obj, "findParentPage"):
            page = obj.findParentPage()
        if page is not None:
            page.ViewObject.Visibility = True
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(page)

    def locatePlacement(self):
        """Open a placement's sheet and select the placed TechDraw view."""

        drawing_view = self.contextObject
        if drawing_view is None or not drawing_view.isDerivedFrom(
            "TechDraw::DrawViewArch"
        ):
            return
        page = drawing_view.findParentPage()
        if page is not None:
            page.ViewObject.Visibility = True
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(drawing_view)

    def refreshTitleBlock(self):
        """Undoably refresh and report the selected sheet's title-block mapping."""

        from PySide import QtGui
        from bimsheets import BIMSheetService, BIMTitleBlockService

        page = self.contextObject
        if page is None or not BIMSheetService.is_sheet(page):
            return
        document = FreeCAD.ActiveDocument
        document.openTransaction("Refresh BIM sheet title block")
        try:
            service = BIMTitleBlockService(document)
            result = service.synchronize(page)
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        mapping = service.describe(page)
        lines = [
            "{} → {}".format(key, field or translate("BIM", "not mapped"))
            for key, field in mapping
        ]
        if result.missing:
            lines.append(
                translate("BIM", "Missing: {}").format(", ".join(result.missing))
            )
        QtGui.QMessageBox.information(
            self.dialog,
            translate("BIM", "Title Block Mapping"),
            "\n".join(lines),
        )
        self.update(False)

    def removeFromSheet(self):
        """Undoably remove the selected placement while retaining its definition."""

        drawing_view = self.contextObject
        if drawing_view is None:
            return
        document = FreeCAD.ActiveDocument
        document.openTransaction("Remove BIM view from sheet")
        try:
            _view_service().remove_sheet_placement(drawing_view)
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()
        self.contextObject = None
        self.update(False)

    def publishSheet(self):
        """Publish the selected sheet to an output directory."""

        self._publishSheets(False)

    def publishSheetSet(self):
        """Publish all BIM sheets in deterministic drawing-set order."""

        self._publishSheets(True)

    def _publishSheets(self, publish_set):
        from PySide import QtGui
        from bimsheets import BIMSheetPublishingService, SheetPublicationError

        page = self.contextObject
        if page is None or not page.isDerivedFrom("TechDraw::DrawPage"):
            return
        directory = QtGui.QFileDialog.getExistingDirectory(
            self.dialog, translate("BIM", "Publish Drawing Sheets")
        )
        if not directory:
            return
        format, accepted = QtGui.QInputDialog.getItem(
            self.dialog,
            translate("BIM", "Publication Format"),
            translate("BIM", "Format"),
            ["PDF", "SVG"],
            0,
            False,
        )
        if not accepted:
            return
        service = BIMSheetPublishingService(FreeCAD.ActiveDocument)
        publish = service.publish_set if publish_set else service.publish_sheet
        try:
            if publish_set:
                result = publish(directory, format.lower())
            else:
                result = publish(page, directory, format.lower())
        except SheetPublicationError as error:
            if "overwrite" not in str(error):
                QtGui.QMessageBox.warning(
                    self.dialog, translate("BIM", "Publication Failed"), str(error)
                )
                return
            answer = QtGui.QMessageBox.question(
                self.dialog,
                translate("BIM", "Replace Published Files?"),
                str(error),
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.No,
            )
            if answer != QtGui.QMessageBox.Yes:
                return
            if publish_set:
                result = publish(directory, format.lower(), overwrite=True)
            else:
                result = publish(page, directory, format.lower(), overwrite=True)
        QtGui.QMessageBox.information(
            self.dialog,
            translate("BIM", "Publication Complete"),
            translate("BIM", "Published {} sheet(s).").format(len(result.sheets)),
        )
        self.update(False)

    def createIssue(self):
        """Create an immutable issue from the current published sheet set."""

        from PySide import QtGui
        from bimsheets import BIMSheetIssueService, SheetIssueError

        identifier, accepted = QtGui.QInputDialog.getText(
            self.dialog,
            translate("BIM", "Create Drawing Issue"),
            translate("BIM", "Issue identifier"),
        )
        if not accepted or not identifier.strip():
            return
        document = FreeCAD.ActiveDocument
        document.openTransaction("Create BIM sheet issue")
        try:
            issue = BIMSheetIssueService(document).create_issue(identifier)
            document.commitTransaction()
        except SheetIssueError as error:
            document.abortTransaction()
            QtGui.QMessageBox.warning(
                self.dialog, translate("BIM", "Issue Creation Failed"), str(error)
            )
            return
        self.contextObject = issue
        self.update(False)

    def compareIssue(self):
        """Show changes between the selected issue and its predecessor."""

        from PySide import QtGui
        from bimsheets import BIMSheetIssueService

        issue = self.contextObject
        service = BIMSheetIssueService(FreeCAD.ActiveDocument)
        if issue is None or getattr(issue, "BIMType", "") != service.BIM_TYPE:
            return
        comparison = service.compare(issue)
        lines = [
            translate("BIM", "Added: {}").format(", ".join(comparison.added) or "—"),
            translate("BIM", "Removed: {}").format(", ".join(comparison.removed) or "—"),
            translate("BIM", "Changed: {}").format(
                ", ".join(number for number, _reasons in comparison.changed) or "—"
            ),
        ]
        QtGui.QMessageBox.information(
            self.dialog,
            translate("BIM", "Issue Comparison"),
            "\n".join(lines),
        )

    def addProxy(self):
        "adds a WP proxy"

        import Draft
        import WorkingPlane

        FreeCAD.ActiveDocument.openTransaction("Create WP Proxy")
        obj = Draft.makeWorkingPlaneProxy(WorkingPlane.get_working_plane().get_placement())
        self.addToSelection(obj)
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()
        self.update(False)

    def addToSelection(self, obj):
        "Adds the given object to the current selected item"

        import Draft
        from nativeifc import ifc_tools

        sel = FreeCADGui.Selection.getSelection()
        if len(sel) == 1:
            sel = sel[0]
            if hasattr(sel, "addObject"):
                sel.addObject(obj)
                return
            elif Draft.getType(sel).startswith("Ifc"):
                ifc_tools.aggregate(obj, sel)
            elif "Group" in sel.PropertiesList:
                g = sel.Group
                if obj not in g:
                    g.append(obj)
                sel.Group = g
                return

    def delete(self):
        "deletes the selected object"

        if findWidget():
            context_object = getattr(self, "contextObject", None)
            selected = [context_object] if context_object is not None else self._selectedObjects()
            if selected:
                FreeCAD.ActiveDocument.openTransaction("Delete")
                for obj in selected:
                    if obj:
                        if _view_service().is_view_definition(obj):
                            _view_service().delete_view(obj)
                        else:
                            FreeCAD.ActiveDocument.removeObject(obj.Name)
                FreeCAD.ActiveDocument.commitTransaction()
                FreeCAD.ActiveDocument.recompute()
                self.update(False)

    def rename(self):
        "renames the selected object"

        vm = findWidget()
        if vm:
            context_object = getattr(self, "contextObject", None)
            indexes = (
                vm.navigatorModel.indexes_for_object(context_object)
                if context_object is not None
                else vm.navigator.selectionModel().selectedRows(0)
            )
            if indexes:
                vm.navigator.edit(indexes[-1])

    @staticmethod
    def activate(dialog=None):
        vm = findWidget()
        if vm and hasattr(vm, "navigatorModel"):
            indexes = vm.navigator.selectionModel().selectedRows(0)
            obj = vm.navigatorModel.object_for_index(indexes[-1]) if indexes else None
            if obj and hasattr(obj.ViewObject, "DoubleClickActivates"):
                _toggle_active_container(obj, dialog=dialog)
                FreeCADGui.Selection.clearSelection()

    def activateContextItem(self):
        """Activate the item under the context menu."""

        import Draft

        if not self.contextObject:
            return
        if Draft.getType(self.contextObject) == "WorkingPlaneProxy":
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(self.contextObject)
            FreeCADGui.runCommand("Draft_SelectPlane")
        elif _view_service().is_view_definition(self.contextObject):
            _view_service().activate_view(self.contextObject)
        elif hasattr(self.contextObject.ViewObject, "DoubleClickActivates"):
            _toggle_active_container(self.contextObject, dialog=self.dialog)
            FreeCADGui.Selection.clearSelection()

    def editObject(self, item, column):
        "renames or edits the elevation or height of the actual object"

        obj = FreeCAD.ActiveDocument.getObject(item.toolTip(0))
        if not obj:
            return
        text = item.text(column)
        FreeCAD.ActiveDocument.openTransaction("Edit level")
        try:
            if column == 0:
                obj.Label = text
            elif column == 1:
                if text:
                    setObjectElevation(obj, FreeCAD.Units.parseQuantity(text))
            elif column == 2:
                if text and hasattr(obj, "Height"):
                    obj.Height = FreeCAD.Units.parseQuantity(text)
        finally:
            FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()

    def toggle(self):
        "toggle selected item on/off"

        if findWidget():
            for obj in self._selectedObjects():
                obj.ViewObject.Visibility = not obj.ViewObject.Visibility
            FreeCAD.ActiveDocument.recompute()

    def isolate(self):
        import Draft

        """
        Isolate the currently selected items in the tree view.

        This function first makes all items in the tree visible to ensure a clean slate.
        Then, it hides all items that are not currently selected by the user in the GUI tree view.
        As a result, only the selected items remain visible in the 3D view, effectively isolating them.

        The operation is limited to objects represented by the Project branch.
        """

        vm = findWidget()
        if vm and hasattr(vm, "navigatorModel"):
            selected = set(self._selectedObjects())
            include_descendants = len(selected) == 1 and any(
                getattr(obj, "IfcType", "") == "Building" for obj in selected
            )
            visible = set(selected)
            if include_descendants:
                pending = list(getattr(next(iter(selected)), "Group", ()) or ())
                while pending:
                    obj = pending.pop(0)
                    if obj not in visible:
                        visible.add(obj)
                        pending.extend(getattr(obj, "Group", ()) or ())
            for obj in vm.navigatorModel.all_project_objects():
                obj.ViewObject.Visibility = obj in visible

    def saveView(self):
        "save the current camera and context to the selected item"

        vm = findWidget()
        if vm:
            context_object = getattr(self, "contextObject", None)
            if context_object and _view_service().is_view_definition(context_object):
                _view_service().capture(context_object)
                FreeCAD.ActiveDocument.recompute()
                return
            for obj in self._selectedObjects():
                if obj and _view_service().is_view_definition(obj):
                    _view_service().capture(obj)
                if obj:
                    if hasattr(obj.ViewObject.Proxy, "writeCamera"):
                        obj.ViewObject.Proxy.writeCamera()
        FreeCAD.ActiveDocument.recompute()

    def saveVisibility(self):
        "save the current visibility state to the selected item"

        vm = findWidget()
        if vm:
            context_object = getattr(self, "contextObject", None)
            if context_object and _view_service().is_view_definition(context_object):
                _view_service().capture(context_object)
                FreeCAD.ActiveDocument.recompute()
                return
            for obj in self._selectedObjects():
                if obj and _view_service().is_view_definition(obj):
                    _view_service().capture(obj)
                if obj and hasattr(obj.ViewObject.Proxy, "writeState"):
                    obj.ViewObject.Proxy.writeState()
        FreeCAD.ActiveDocument.recompute()

    def onDockLocationChanged(self, area):
        """Saves dock widget size and location"""
        if hasattr(area, "value"):  # To support Qt5.15
            PARAMS.SetInt("BimViewArea", area.value)
        else:
            PARAMS.SetInt("BimViewArea", int(area))
        mw = FreeCADGui.getMainWindow()
        vm = findWidget()
        if vm:
            PARAMS.SetBool("BimViewFloat", vm.isFloating())
            PARAMS.SetInt("BimViewWidth", vm.width())
            PARAMS.SetInt("BimViewHeight", vm.height())
            tabs = "+".join([o.objectName() for o in mw.tabifiedDockWidgets(vm)])
            PARAMS.SetString("BimViewTabs", tabs)

    def getDockArea(self, area):
        """Turns an int into a qt dock area"""

        from PySide import QtCore

        if area == 1:
            return QtCore.Qt.LeftDockWidgetArea
        elif area == 4:
            return QtCore.Qt.TopDockWidgetArea
        elif area == 8:
            return QtCore.Qt.BottomDockWidgetArea
        else:
            return QtCore.Qt.RightDockWidgetArea

    def _selectedObjects(self):
        vm = findWidget()
        if not vm or not hasattr(vm, "navigatorModel"):
            return []
        result = []
        for index in vm.navigator.selectionModel().selectedRows(0):
            obj = vm.navigatorModel.object_for_index(index)
            if obj is not None and obj not in result:
                result.append(obj)
        return result

    def onNavigatorContextMenu(self, pos):
        """Show actions appropriate to the navigator row under the cursor."""

        import Draft

        vm = findWidget()
        index = self.dialog.navigator.indexAt(pos)
        obj = vm.navigatorModel.object_for_index(index) if index.isValid() else None
        kind = vm.navigatorModel.kind_for_index(index) if index.isValid() else ""
        self.contextObject = obj
        for action in (
            self.dialog.buttonNewPlanView,
            self.dialog.buttonNewSectionView,
            self.dialog.buttonNewElevationView,
            self.dialog.buttonNewModelView,
            self.dialog.buttonActive,
            self.dialog.buttonAddLevel,
            self.dialog.buttonAddProxy,
            self.dialog.buttonDelete,
            self.dialog.buttonToggle,
            self.dialog.buttonIsolate,
            self.dialog.buttonSaveView,
            self.dialog.buttonSaveVisibility,
            self.dialog.buttonDuplicateView,
            self.dialog.buttonNewSheet,
            self.dialog.buttonPlaceOnSheet,
            self.dialog.buttonOpenSheet,
            self.dialog.buttonEditSheet,
            self.dialog.buttonRefreshTitleBlock,
            self.dialog.buttonPublishSheet,
            self.dialog.buttonPublishSheetSet,
            self.dialog.buttonCreateIssue,
            self.dialog.buttonCompareIssue,
            self.dialog.buttonLocatePlacement,
            self.dialog.buttonRemoveFromSheet,
            self.dialog.buttonRename,
        ):
            action.setEnabled(True)
            action.setVisible(True)
        self.dialog.buttonDuplicateView.setVisible(False)
        self.dialog.buttonNewSheet.setVisible(False)
        self.dialog.buttonPlaceOnSheet.setVisible(False)
        self.dialog.buttonOpenSheet.setVisible(False)
        self.dialog.buttonEditSheet.setVisible(False)
        self.dialog.buttonRefreshTitleBlock.setVisible(False)
        self.dialog.buttonPublishSheet.setVisible(False)
        self.dialog.buttonPublishSheetSet.setVisible(False)
        self.dialog.buttonCreateIssue.setVisible(False)
        self.dialog.buttonCompareIssue.setVisible(False)
        self.dialog.buttonLocatePlacement.setVisible(False)
        self.dialog.buttonRemoveFromSheet.setVisible(False)
        self.dialog.buttonActive.setText(translate("BIM", "Active"))
        self.dialog.buttonActive.setCheckable(True)
        self.dialog.buttonActive.setChecked(False)
        self.dialog.buttonActive.setToolTip(translate("BIM", "Activates the selected item"))
        if kind in (
            "saved-view",
            "legacy-view",
            "sheet",
            "sheet-placement",
            "sheet-issue",
        ) or kind.endswith("group"):
            for action in self.dialog.menu.actions():
                action.setVisible(False)
            self.dialog.buttonNewPlanView.setVisible(True)
            self.dialog.buttonNewModelView.setVisible(True)
            if kind == "saved-view":
                self.dialog.buttonActive.setText(translate("BIM", "Open"))
                self.dialog.buttonActive.setCheckable(False)
                for action in (
                    self.dialog.buttonActive,
                    self.dialog.buttonDelete,
                    self.dialog.buttonSaveView,
                    self.dialog.buttonSaveVisibility,
                    self.dialog.buttonDuplicateView,
                    self.dialog.buttonRename,
                    self.dialog.buttonPlaceOnSheet,
                ):
                    action.setVisible(True)
                self.dialog.buttonPlaceOnSheet.setEnabled(
                    _view_service().can_place_on_sheet(obj)
                    and bool(_manager_model().pages())
                )
                if str(getattr(obj, "Purpose", "")) == "Plan":
                    self.dialog.buttonNewSectionView.setVisible(True)
                    self.dialog.buttonNewSectionView.setEnabled(True)
            elif kind == "sheet":
                self.dialog.buttonNewPlanView.setVisible(False)
                self.dialog.buttonNewModelView.setVisible(False)
                self.dialog.buttonNewSheet.setVisible(True)
                self.dialog.buttonOpenSheet.setVisible(True)
                self.dialog.buttonEditSheet.setVisible(True)
                self.dialog.buttonRefreshTitleBlock.setVisible(True)
                self.dialog.buttonPublishSheet.setVisible(True)
                self.dialog.buttonPublishSheetSet.setVisible(True)
                self.dialog.buttonCreateIssue.setVisible(True)
                self.dialog.buttonRename.setVisible(True)
            elif kind == "sheet-placement":
                self.dialog.buttonNewPlanView.setVisible(False)
                self.dialog.buttonNewModelView.setVisible(False)
                self.dialog.buttonLocatePlacement.setVisible(True)
                self.dialog.buttonRemoveFromSheet.setVisible(True)
            elif kind == "sheet-issue":
                self.dialog.buttonNewPlanView.setVisible(False)
                self.dialog.buttonNewModelView.setVisible(False)
                self.dialog.buttonCompareIssue.setVisible(True)
        elif obj is None:
            for action in self.dialog.menu.actions():
                action.setVisible(False)
            self.dialog.buttonNewPlanView.setVisible(True)
            self.dialog.buttonNewModelView.setVisible(True)
            if vm.navigatorModel.key_for_index(index) == "section:sheets":
                self.dialog.buttonNewPlanView.setVisible(False)
                self.dialog.buttonNewModelView.setVisible(False)
                self.dialog.buttonNewSheet.setVisible(True)
        else:
            self.dialog.buttonNewSectionView.setEnabled(
                (
                    getattr(getattr(obj, "Proxy", None), "Type", "")
                    == "SectionPlane"
                    and str(getattr(obj, "Purpose", "")) == "Section"
                )
                or self._selectedProjectContext() is not None
            )
            if Draft.getType(obj).startswith("Ifc"):
                self.dialog.buttonAddProxy.setEnabled(False)
            if Draft.getType(obj) == "WorkingPlaneProxy":
                self.dialog.buttonActive.setText(translate("BIM", "Set Working Plane"))
                self.dialog.buttonActive.setCheckable(False)
            else:
                active = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("NativeIFC")
                active = active or FreeCADGui.ActiveDocument.ActiveView.getActiveObject("Arch")
                self.dialog.buttonActive.setChecked(active == obj)
        self.dialog.menu.exec_(self.dialog.navigator.viewport().mapToGlobal(pos))

    def getViews(self):
        """Return legacy 2D views retained for document compatibility."""
        return list(_manager_model().legacy_views())

    def getPages(self):
        """Returns a list of TD pages"""
        return [o for o in FreeCAD.ActiveDocument.Objects if o.isDerivedFrom("TechDraw::DrawPage")]


# These functions need to be localized outside the command class, as they are used outside this module


def findWidget():
    """Find the navigator, including docks created under its legacy name."""

    from PySide import QtGui

    mw = FreeCADGui.getMainWindow()
    vm = mw.findChild(QtGui.QDockWidget, "BIM Navigator")
    if vm is None:
        vm = mw.findChild(QtGui.QDockWidget, "BIM Views Manager")
        if vm is not None:
            vm.setObjectName("BIM Navigator")
            vm.setWindowTitle(translate("BIM", "BIM Navigator"))
    if vm:
        return vm
    return None


def placeInComboView(vm=None):
    """Tab the BIM Navigator with Combo View and select it.

    The generic Model/Tasks dock remains available as the adjacent ``Model``
    tab.  Its normal title is restored when the BIM workbench is deactivated.
    """

    from PySide import QtCore, QtGui

    mw = FreeCADGui.getMainWindow()
    vm = vm or findWidget()
    if vm is None:
        return
    combo = _findModelDock(mw)
    if combo is None or combo is vm:
        vm.show()
        vm.raise_()
        return
    if combo.property("BIMOriginalWindowTitle") is None:
        combo.setProperty("BIMOriginalWindowTitle", combo.windowTitle())
    combo.setWindowTitle(translate("BIM", "Model"))
    vm.setWindowTitle(translate("BIM", "BIM Navigator"))
    vm.setFloating(False)
    mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, vm)
    # Using the navigator as the first dock gives it the leading tab position.
    mw.tabifyDockWidget(vm, combo)
    combo.show()
    vm.show()
    vm.raise_()


def restoreComboViewTitle():
    """Restore the generic Combo View title after leaving BIM."""

    from PySide import QtGui

    combo = _findModelDock(FreeCADGui.getMainWindow())
    if combo is None:
        return
    title = combo.property("BIMOriginalWindowTitle")
    if title is not None:
        combo.setWindowTitle(str(title))
        combo.setProperty("BIMOriginalWindowTitle", None)


def _findModelDock(main_window=None):
    """Return the standard combined Model/Tasks dock across FreeCAD versions."""

    from PySide import QtGui

    main_window = main_window or FreeCADGui.getMainWindow()
    for name in ("Model", "Combo View", "ComboView"):
        dock = main_window.findChild(QtGui.QDockWidget, name)
        if dock is not None:
            return dock
    return None


def show(item, column=None):
    "item has been double-clicked"
    import Draft

    obj = None
    vm = findWidget()
    if isinstance(item, str) or ((sys.version_info.major < 3) and isinstance(item, unicode)):
        # called from Python code
        obj = FreeCAD.ActiveDocument.getObject(item)
    else:
        # called from GUI
        if column in (1, 2):
            # user clicked the elevation or height field
            if vm:
                vm.tree.editItem(item, column)
                return
        else:
            # TODO find a way to not edit the object name
            obj = FreeCAD.ActiveDocument.getObject(item.toolTip(0))
    if obj:
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(obj)
        vparam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        if obj.isDerivedFrom("App::ViewDefinition"):
            _view_service().activate_view(obj)
        elif obj.isDerivedFrom("TechDraw::DrawPage"):
            # TD page: We switch to it.
            obj.ViewObject.Visibility = True
        elif isView(obj):
            # 2D view
            ssel = [obj] + obj.Group
            FreeCADGui.Selection.clearSelection()
            for o in ssel:
                o.ViewObject.Visibility = True
                FreeCADGui.Selection.addSelection(o)
            if not hasattr(FreeCADGui.ActiveDocument.ActiveView, "getSceneGraph"):
                # Find first 3d view and switch to it
                for w in FreeCADGui.getMainWindow().getWindows():
                    if hasattr(w, "getSceneGraph"):
                        FreeCADGui.getMainWindow().setActiveWindow(w)
                        break
            FreeCADGui.runCommand("Std_OrthographicCamera")
            FreeCADGui.ActiveDocument.ActiveView.viewTop()
            FreeCADGui.ActiveDocument.ActiveView.sendMessage("ViewSelection")
            FreeCADGui.ActiveDocument.ActiveView.viewTop()
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj)
            if PARAMS.GetBool("BimViewsSwitchBackground", False):
                vparam.SetBool("Simple", True)
                vparam.SetBool("Gradient", False)
                vparam.SetBool("RadialGradient", False)
        elif Draft.getType(obj) in ("BuildingPart", "IfcBuilding", "IfcBuildingStorey") and getattr(
            obj.ViewObject, "DoubleClickActivates", True
        ):
            BIM_Views.activate()
        else:
            # WP Proxy
            FreeCADGui.runCommand("Draft_SelectPlane")

    if vm:
        # store the last double-clicked item for the BIM WPView command
        if isinstance(item, str) or ((sys.version_info.major < 3) and isinstance(item, unicode)):
            vm.lastSelected = item
        else:
            vm.lastSelected = item.toolTip(0)


def isView(obj):
    """Returns true if this object is used as Source of a view on a TD page"""

    for p in obj.InList:
        if p.isDerivedFrom("TechDraw::DrawView"):
            if hasattr(p, "Source"):
                if p.Source == obj:
                    return True
    if getattr(obj, "DrawingView", False):
        return True
    if getattr(obj, "IfcType", None) == "Annotation":
        if getattr(obj, "ObjectType", "").upper() == "DRAWING":
            return True
    if getattr(obj, "Class", None) == "IfcAnnotation":
        if getattr(obj, "ObjectType", "").upper() == "DRAWING":
            return True
    return False


def getTreeViewItem(obj):
    """
    Build a QTreeWidgetItem for obj with three columns: label, elevation, height.

    Elevation is always read from Placement.Base.z, which is the source of
    truth for a level's position. The IFC Elevation attribute is derived from
    this placement and must never be used as a fallback. Height comes from the
    BuildingPart Height property when present. Returns the item together with
    the elevation as a number, used to sort levels vertically.
    """
    from PySide import QtCore, QtGui

    z = getObjectElevation(obj)
    elevStr = FreeCAD.Units.Quantity(z, FreeCAD.Units.Length).UserString

    heightStr = ""
    if hasattr(obj, "Height") and hasattr(obj.Height, "UserString"):
        heightStr = obj.Height.UserString

    it = QtGui.QTreeWidgetItem([obj.Label, elevStr, heightStr])
    it.setFlags(it.flags() | QtCore.Qt.ItemIsEditable)
    it.setData(2, QtCore.Qt.UserRole, hasattr(obj, "Height"))
    it.setToolTip(0, obj.Name)
    if obj.ViewObject:
        if hasattr(obj.ViewObject, "Icon"):
            it.setIcon(0, obj.ViewObject.Icon)
    return (it, z)


def getObjectElevation(obj):
    """Return the elevation represented by an object's placement."""

    return obj.Placement.Base.z


def setObjectElevation(obj, elevation):
    """Set an object's elevation through its Placement property.

    Placement is the source of truth; IFC Elevation is derived from it.
    Assign the complete placement to notify dependent objects.
    """

    obj.Placement.Base.z = elevation


def getAllItemsInTree(tree_widget):
    "return list of all items in QtreeWidget"

    def get_child_items(parent_item):
        child_items = []
        # get how many sub items
        child_count = parent_item.childCount()
        for j in range(child_count):
            child_item = parent_item.child(j)
            child_items.append(child_item)
            child_items.extend(get_child_items(child_item))

        return child_items

    all_items = []
    # get top level items
    top_level_item_count = tree_widget.topLevelItemCount()
    for i in range(top_level_item_count):
        top_level_item = tree_widget.topLevelItem(i)
        all_items.append(top_level_item)
        # iterate sub-items
        all_items.extend(get_child_items(top_level_item))

    return all_items


def getParent(obj):
    "return the first parent of this object"

    if obj.getParent():
        return obj.getParent()
    else:
        for parent in obj.InList:
            if hasattr(parent, "Group") and obj in parent.Group:
                return parent


def _toggle_active_container(obj, action=None, dialog=None):
    """Toggle the active state of a BIM building or level.

    This function handles the logic for activating BuildingParts (buildings and levels),
    IfcBuildings and IfcBuildingStoreys.

    Parameters
    ----------
    obj : App::DocumentObject
        The object to activate or deactivate as a working plane.
        Must be a BuildingPart, an IfcBuilding or an IfcBuildingStorey.
    action : QAction, optional
        The action button that triggered this function, to update its checked state.
    dialog : QDialog, optional
        If provided, will update the checked state of the activate button in the dialog.

    Returns
    -------
    bool
        True if the object was activated, False if it was deactivated.
    """

    active_obj = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("NativeIFC")
    if active_obj is None:
        active_obj = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("Arch")
    is_active = obj == active_obj

    if getattr(obj.ViewObject, "SetWorkingPlane", False):
        obj.ViewObject.Proxy.setWorkingPlane(restore=is_active)
    elif (
        not is_active
        and active_obj is not None
        and getattr(active_obj.ViewObject, "SetWorkingPlane", False)
    ):
        active_obj.ViewObject.Proxy.setWorkingPlane(restore=True)

    if action:
        action.setChecked((not is_active))
    if dialog and hasattr(dialog, "buttonActive"):
        dialog.buttonActive.setChecked((not is_active))

    if is_active:
        # Deactivate the object
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("NativeIFC", None)
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("Arch", None)
        return False
    else:
        # Activate the object
        import Draft

        context = (
            "NativeIFC" if Draft.getType(obj) in ("IfcBuilding", "IfcBuildingStorey") else "Arch"
        )
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject(context, obj)
        _view_service().activate_storey(obj)
        return True


def _manager_model():
    """Return the document-query model used by the dock."""

    from bimviews.navigator_model import BIMNavigatorModel

    return BIMNavigatorModel(FreeCAD.ActiveDocument, legacy_view_predicate=isView)


def _preferred_sheet(document, selected_objects=()):
    """Resolve an unambiguous placement target without prompting the user."""

    from bimsheets import BIMSheetService, BIMSheetTargetResolver

    service = BIMSheetService(document)
    active_page = None
    try:
        gui_document = FreeCADGui.activeDocument()
        active_view = gui_document.activeView() if gui_document is not None else None
        active_page = active_view.getPage() if hasattr(active_view, "getPage") else None
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return BIMSheetTargetResolver(document, service.is_sheet).resolve(
        active_page=active_page,
        selected=selected_objects,
    )


def _sheet_display_label(page):
    number = str(getattr(page, "SheetNumber", "")).strip()
    title = str(getattr(page, "SheetTitle", "") or page.Label).strip()
    return "{} — {}".format(number, title) if number else title


def _apply_representation_request(request):
    """Forward saved-view intent to the representation editing runtime."""

    try:
        from bimplan.runtime.session import activate_representation_request

        return activate_representation_request(request)
    except (AttributeError, ImportError, ReferenceError, RuntimeError, TypeError, ValueError):
        return


def _view_service():
    """Return one activation service per open document."""

    from bimviews.service import BIMViewService

    document = FreeCAD.ActiveDocument
    key = document.Name
    service = _view_services.get(key)
    if service is None or service.document is not document:
        service = BIMViewService(document, representation_applier=_apply_representation_request)
        _view_services[key] = service
        if service.active_view is not None:
            try:
                service.restore_active_view()
            except (RuntimeError, ValueError):
                pass
    return service


FreeCADGui.addCommand("BIM_Views", BIM_Views())

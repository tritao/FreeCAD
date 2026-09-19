# SPDX-License-Identifier: LGPL-2.1-or-later

"""Qt workflows for creating and editing BIM drawing sheets."""

import os
from dataclasses import replace

import FreeCAD
from PySide import QtGui

from .service import BIMSheetMetadata, BIMSheetService


translate = FreeCAD.Qt.translate


class BIMSheetPropertiesWidget(QtGui.QWidget):
    """Reusable editor for the mutable drawing-set metadata of one sheet."""

    def __init__(self, metadata, parent=None):
        super().__init__(parent)
        self._source = metadata
        form = QtGui.QFormLayout(self)
        self.number = QtGui.QLineEdit(metadata.number)
        self.title = QtGui.QLineEdit(metadata.title)
        self.discipline = QtGui.QComboBox()
        self.discipline.addItems(BIMSheetService.DISCIPLINES)
        self.discipline.setCurrentText(metadata.discipline)
        self.revision = QtGui.QLineEdit(metadata.revision)
        self.status = QtGui.QComboBox()
        self.status.addItems(BIMSheetService.STATUSES)
        self.status.setCurrentText(metadata.status)
        self.order = QtGui.QSpinBox()
        self.order.setRange(-999999, 999999)
        self.order.setValue(metadata.order)
        form.addRow(translate("BIM", "Sheet number"), self.number)
        form.addRow(translate("BIM", "Title"), self.title)
        form.addRow(translate("BIM", "Discipline"), self.discipline)
        form.addRow(translate("BIM", "Revision"), self.revision)
        form.addRow(translate("BIM", "Status"), self.status)
        form.addRow(translate("BIM", "Set order"), self.order)

    def set_metadata(self, metadata):
        self._source = metadata
        self.number.setText(metadata.number)
        self.title.setText(metadata.title)
        self.discipline.setCurrentText(metadata.discipline)
        self.revision.setText(metadata.revision)
        self.status.setCurrentText(metadata.status)
        self.order.setValue(metadata.order)

    def metadata(self):
        """Return edited values while preserving metadata not shown here."""

        return replace(
            self._source,
            number=self.number.text().strip(),
            title=self.title.text().strip(),
            discipline=self.discipline.currentText(),
            revision=self.revision.text().strip(),
            status=self.status.currentText(),
            order=self.order.value(),
        )


class BIMSheetPropertiesDialog(QtGui.QDialog):
    """Modal wrapper retained for bounded sheet-properties workflows."""

    def __init__(self, metadata, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("BIM", "Sheet Properties"))
        layout = QtGui.QVBoxLayout(self)
        self.editor = BIMSheetPropertiesWidget(metadata, self)
        layout.addWidget(self.editor)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.editor.title.setFocus()

    def metadata(self):
        return self.editor.metadata()

    def __getattr__(self, name):
        editor = self.__dict__.get("editor")
        if editor is not None and hasattr(editor, name):
            return getattr(editor, name)
        raise AttributeError(name)


class BIMSheetPlacementPropertiesWidget(QtGui.QWidget):
    """Reusable editor for a saved-view placement on a drawing sheet."""

    RENDER_MODES = ("Wireframe", "Solid", "Coin", "Coin mono")

    def __init__(self, drawing_view, parent=None):
        super().__init__(parent)
        form = QtGui.QFormLayout(self)
        self.number = QtGui.QLineEdit()
        self.title = QtGui.QLineEdit()
        self.title.setClearButtonEnabled(True)
        self.title.setPlaceholderText(
            translate("BIM", "Use the saved-view title when empty")
        )
        self.scale = self._decimal(0.000001, 1000.0, 6)
        self.x = self._decimal(-1000000.0, 1000000.0, 2, " mm")
        self.y = self._decimal(-1000000.0, 1000000.0, 2, " mm")
        self.title_offset = self._decimal(0.0, 1000000.0, 2, " mm")
        self.title_size = self._decimal(0.1, 1000.0, 2, " mm")
        self.render_mode = QtGui.QComboBox()
        self.render_mode.addItems(self.RENDER_MODES)
        self.show_hidden = QtGui.QCheckBox(translate("BIM", "Show hidden lines"))
        self.show_fill = QtGui.QCheckBox(translate("BIM", "Show cut fills"))
        form.addRow(translate("BIM", "View number"), self.number)
        form.addRow(translate("BIM", "Title override"), self.title)
        form.addRow(translate("BIM", "Scale"), self.scale)
        form.addRow(translate("BIM", "Horizontal position"), self.x)
        form.addRow(translate("BIM", "Vertical position"), self.y)
        form.addRow(translate("BIM", "Title offset"), self.title_offset)
        form.addRow(translate("BIM", "Title text size"), self.title_size)
        form.addRow(translate("BIM", "Render mode"), self.render_mode)
        form.addRow(self.show_hidden)
        form.addRow(self.show_fill)
        self.drawing_view = None
        self.set_drawing_view(drawing_view)

    @staticmethod
    def _decimal(minimum, maximum, decimals, suffix=""):
        field = QtGui.QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(decimals)
        field.setSuffix(suffix)
        field.setKeyboardTracking(False)
        return field

    def set_drawing_view(self, drawing_view):
        self.drawing_view = drawing_view
        annotation = _title_annotation(drawing_view)
        self.number.setText(str(getattr(drawing_view, "ViewNumber", "")))
        self.title.setText(str(getattr(drawing_view, "ViewTitle", "")))
        self.scale.setValue(float(drawing_view.Scale))
        self.x.setValue(drawing_view.X.Value)
        self.y.setValue(drawing_view.Y.Value)
        if annotation is not None:
            self.title_offset.setValue(abs(annotation.OwnerOffsetY.Value))
            self.title_size.setValue(annotation.TextSize.Value)
        self.render_mode.setCurrentText(str(drawing_view.RenderMode))
        self.show_hidden.setChecked(bool(drawing_view.ShowHidden))
        self.show_fill.setChecked(bool(drawing_view.ShowFill))

    def apply(self):
        from .titles import BIMSheetViewTitleService

        view = self.drawing_view
        page = view.findParentPage()
        number = self.number.text().strip()
        BIMSheetViewTitleService.validate_number(page, number, view)
        document = view.Document
        document.openTransaction("Edit BIM sheet placement")
        try:
            view.ViewNumber = number
            view.ViewTitle = self.title.text().strip()
            view.Scale = self.scale.value()
            view.X = self.x.value()
            view.Y = self.y.value()
            view.RenderMode = self.render_mode.currentText()
            view.ShowHidden = self.show_hidden.isChecked()
            view.ShowFill = self.show_fill.isChecked()
            annotation = _title_annotation(view)
            if annotation is not None:
                annotation.OwnerOffsetY = -self.title_offset.value()
                annotation.TextSize = self.title_size.value()
                annotation.touch()
            document.commitTransaction()
        except Exception:
            document.abortTransaction()
            raise
        document.recompute()


class BIMSheetInspectorPanel:
    """Contextual Task View editor for sheets and their placements."""

    def __init__(self, refresh_callback=None, close_callback=None):
        self.form = QtGui.QWidget()
        self.form.setWindowTitle(translate("BIM", "Sheet Inspector"))
        self._layout = QtGui.QVBoxLayout(self.form)
        self.heading = QtGui.QLabel()
        heading_font = self.heading.font()
        heading_font.setBold(True)
        self.heading.setFont(heading_font)
        self._layout.addWidget(self.heading)
        self.editor_host = QtGui.QWidget()
        self.editor_layout = QtGui.QVBoxLayout(self.editor_host)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.editor_host)
        self.error = QtGui.QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #b04040;")
        self.error.hide()
        self._layout.addWidget(self.error)
        buttons = QtGui.QDialogButtonBox()
        self.apply_button = buttons.addButton(
            translate("BIM", "Apply"), QtGui.QDialogButtonBox.ApplyRole
        )
        self.revert_button = buttons.addButton(
            translate("BIM", "Revert"), QtGui.QDialogButtonBox.ResetRole
        )
        self.apply_button.clicked.connect(self.apply)
        self.revert_button.clicked.connect(self.revert)
        self._layout.addWidget(buttons)
        self._layout.addStretch(1)
        self.object = None
        self.kind = ""
        self.editor = None
        self._refresh_callback = refresh_callback
        self._close_callback = close_callback

    def set_context(self, obj, kind):
        self.object = obj
        self.kind = kind
        self.error.hide()
        self._replace_editor()

    def _replace_editor(self):
        if self.editor is not None:
            self.editor_layout.removeWidget(self.editor)
            self.editor.deleteLater()
        if self.kind == "sheet":
            service = BIMSheetService(self.object.Document)
            self.heading.setText(self.object.Label)
            self.editor = BIMSheetPropertiesWidget(
                service.metadata_for(self.object), self.editor_host
            )
        elif self.kind == "sheet-placement":
            self.heading.setText(self.object.Label)
            self.editor = BIMSheetPlacementPropertiesWidget(
                self.object, self.editor_host
            )
        else:
            self.heading.clear()
            self.editor = QtGui.QLabel(
                translate("BIM", "Select a sheet or sheet placement."),
                self.editor_host,
            )
        self.editor_layout.addWidget(self.editor)

    def apply(self):
        self.error.hide()
        try:
            if self.kind == "sheet":
                service = BIMSheetService(self.object.Document)
                metadata = self.editor.metadata()
                self.object.Document.openTransaction("Edit BIM sheet properties")
                try:
                    service.apply_metadata(self.object, metadata)
                    self.object.Label = metadata.title or metadata.number or self.object.Label
                    self.object.Document.commitTransaction()
                except Exception:
                    self.object.Document.abortTransaction()
                    raise
                self.object.Document.recompute()
            elif self.kind == "sheet-placement":
                self.editor.apply()
            else:
                return
        except (TypeError, ValueError, RuntimeError) as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.revert()
        if callable(self._refresh_callback):
            self._refresh_callback()

    def revert(self):
        self.error.hide()
        if self.object is not None:
            self._replace_editor()

    def getStandardButtons(self):
        return 0

    def accept(self):
        self._closed()
        return True

    def reject(self):
        self._closed()
        return True

    def _closed(self):
        if callable(self._close_callback):
            self._close_callback(self)


_sheet_inspector = None


def show_sheet_inspector(obj, kind, refresh_callback=None):
    """Show or update the BIM sheet inspector in FreeCAD's right Task View."""

    global _sheet_inspector
    if kind not in ("sheet", "sheet-placement") or obj is None:
        hide_sheet_inspector()
        return None
    if _sheet_inspector is not None:
        _sheet_inspector._refresh_callback = refresh_callback
        _sheet_inspector.set_context(obj, kind)
        return _sheet_inspector
    import FreeCADGui

    gui_document = FreeCADGui.activeDocument()
    if gui_document is None or FreeCADGui.Control.activeDialog(gui_document):
        return None
    _sheet_inspector = BIMSheetInspectorPanel(
        refresh_callback=refresh_callback,
        close_callback=_forget_sheet_inspector,
    )
    _sheet_inspector.set_context(obj, kind)
    FreeCADGui.Control.showDialog(_sheet_inspector, gui_document)
    return _sheet_inspector


def hide_sheet_inspector():
    global _sheet_inspector
    if _sheet_inspector is None:
        return
    import FreeCADGui

    panel = _sheet_inspector
    _sheet_inspector = None
    try:
        FreeCADGui.Control.closeDialog()
    except RuntimeError:
        pass
    panel._refresh_callback = None


def _forget_sheet_inspector(panel):
    global _sheet_inspector
    if _sheet_inspector is panel:
        _sheet_inspector = None


def _title_annotation(drawing_view):
    from .titles import BIMSheetViewTitleService

    return BIMSheetViewTitleService.annotation_for(drawing_view)


def create_sheet_interactive(document, parent=None):
    """Prompt for a template and create one BIM sheet transactionally."""

    import TechDraw  # noqa: F401 - load the document object types before creation

    parameters = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
    template_dir = parameters.GetString("TDTemplateDir", "") or None
    filename, _selected_filter = QtGui.QFileDialog.getOpenFileName(
        parent,
        translate("BIM", "Select Page Template"),
        template_dir,
        "SVG file (*.svg)",
    )
    if not filename:
        return None

    name = os.path.splitext(os.path.basename(filename))[0]
    document.openTransaction("Create BIM sheet")
    try:
        page = BIMSheetService(document).create_sheet(
            filename,
            BIMSheetMetadata(
                title=name,
                template_identity=os.path.basename(filename),
            ),
        )
        page.Template.Label = translate("BIM", "Template")
        _apply_template_scale(page, parameters.GetFloat("DefaultPageScale", 0.01))
        document.commitTransaction()
    except Exception:
        document.abortTransaction()
        raise

    parameters.SetString("TDTemplateDir", filename.replace("\\", "/"))
    page.ViewObject.show()
    document.recompute()
    return page


def edit_sheet_interactive(page, parent=None):
    """Edit one sheet's metadata and synchronize its mapped title block."""

    service = BIMSheetService(page.Document)
    if not service.is_sheet(page):
        raise ValueError("page is not a BIM sheet")
    dialog = BIMSheetPropertiesDialog(service.metadata_for(page), parent)
    if dialog.exec_() != QtGui.QDialog.Accepted:
        return False

    page.Document.openTransaction("Edit BIM sheet properties")
    try:
        metadata = dialog.metadata()
        service.apply_metadata(page, metadata)
        page.Label = metadata.title or metadata.number or page.Label
        page.Document.commitTransaction()
    except Exception:
        page.Document.abortTransaction()
        raise
    page.Document.recompute()
    return True


def _apply_template_scale(page, default_scale):
    for key in ("scale", "Scale", "SCALE", "scaling", "Scaling", "SCALING"):
        value = page.Template.EditableTexts.get(key, "")
        if not value:
            continue
        value = value.replace(":", "/")
        try:
            if "/" in value:
                numerator, denominator = value.split("/", 1)
                page.Scale = float(numerator) / float(denominator)
            else:
                page.Scale = float(value)
        except (ValueError, ZeroDivisionError):
            continue
        return
    page.Scale = default_scale

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Qt workflows for creating and editing BIM drawing sheets."""

import os
from dataclasses import replace

import FreeCAD
from PySide import QtGui

from .service import BIMSheetMetadata, BIMSheetService


translate = FreeCAD.Qt.translate


class BIMSheetPropertiesDialog(QtGui.QDialog):
    """Edit the drawing-set metadata presented in the BIM Navigator."""

    def __init__(self, metadata, parent=None):
        super().__init__(parent)
        self._source = metadata
        self.setWindowTitle(translate("BIM", "Sheet Properties"))

        layout = QtGui.QVBoxLayout(self)
        form = QtGui.QFormLayout()
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
        layout.addLayout(form)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.title.setFocus()

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

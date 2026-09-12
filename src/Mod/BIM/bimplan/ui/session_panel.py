# SPDX-License-Identifier: LGPL-2.1-or-later

"""Small task panel for the reversible Plan Edit session."""

from PySide import QtWidgets

import FreeCAD


class PlanEditSessionPanel:
    """Expose storey selection and session exit through the Task panel."""

    def __init__(self, session):
        self.session = session
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(FreeCAD.Qt.translate("BIM_PlanEdit", "Plan Edit"))
        layout = QtWidgets.QVBoxLayout(self.form)

        self.storey_label = QtWidgets.QLabel(
            FreeCAD.Qt.translate("BIM_PlanEdit", "Context"), self.form
        )
        layout.addWidget(self.storey_label)

        self.storey_selector = QtWidgets.QComboBox(self.form)
        self.storey_selector.addItem(
            FreeCAD.Qt.translate("BIM_PlanEdit", "All model geometry"), None
        )
        for storey in session.storeys:
            self.storey_selector.addItem(session.get_storey_label(storey), storey.Name)
        if session.active_storey:
            index = self.storey_selector.findData(session.active_storey.Name)
            if index >= 0:
                self.storey_selector.setCurrentIndex(index)
        self.storey_selector.currentIndexChanged.connect(self._storey_changed)
        layout.addWidget(self.storey_selector)

        description = QtWidgets.QLabel(
            FreeCAD.Qt.translate(
                "BIM_PlanEdit",
                "Plan Edit keeps its camera, visibility and appearance changes local to this view.",
            ),
            self.form,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.exit_button = QtWidgets.QPushButton(
            FreeCAD.Qt.translate("BIM_PlanEdit", "Exit Plan Edit"), self.form
        )
        self.exit_button.clicked.connect(lambda: self.session.finish())
        layout.addWidget(self.exit_button)

    def _storey_changed(self, index):
        name = self.storey_selector.itemData(index)
        storey = self.session.doc.getObject(name) if name else None
        self.session.set_active_storey(storey)

    def getStandardButtons(self):
        return 0

    def accept(self):
        self.session.finish()

    def reject(self):
        self.session.finish()

    def show(self):
        self.form.show()
        self.form.raise_()

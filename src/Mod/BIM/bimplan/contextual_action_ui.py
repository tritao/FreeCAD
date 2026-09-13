# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compact action and inspector surface for contextual BIM editing."""

from PySide import QtWidgets

import FreeCADGui


class ContextualActionPanel:
    def __init__(self):
        self.actions = ()
        self.sections = ()
        self._container = None

    def update(self, actions, sections, callback):
        self.close()
        self.actions = tuple(actions or ())
        self.sections = tuple(sections or ())
        if not self.actions and not self.sections:
            return
        status_bar = FreeCADGui.getMainWindow().statusBar()
        container = QtWidgets.QWidget(status_bar)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(6, 0, 6, 0)
        if self.sections:
            section = self.sections[0]
            label = QtWidgets.QLabel(
                "{}: {}".format(section.title, section.body), container
            )
            label.setToolTip(section.body)
            layout.addWidget(label)
        for action in self.actions:
            button = QtWidgets.QToolButton(container)
            button.setText(action.label)
            button.setToolTip(action.tooltip)
            button.setEnabled(action.enabled)
            button.clicked.connect(
                lambda _checked=False, selected=action: callback(selected)
            )
            layout.addWidget(button)
        status_bar.addPermanentWidget(container)
        container.show()
        self._container = container

    def close(self):
        container = self._container
        self._container = None
        if container is None:
            return
        try:
            FreeCADGui.getMainWindow().statusBar().removeWidget(container)
        except (RuntimeError, ReferenceError):
            pass
        container.hide()
        container.deleteLater()

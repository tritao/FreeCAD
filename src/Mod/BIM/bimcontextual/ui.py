# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task-view action, tool, and inspector surface for contextual BIM editing."""

from PySide import QtWidgets

import FreeCADGui

class ContextualActionPanel:
    """Generic TaskView panel populated entirely from contextual providers."""

    def __init__(self, close_callback=None):
        self.actions = ()
        self.tools = ()
        self.sections = ()
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Contextual Editing")
        self._layout = QtWidgets.QVBoxLayout(self.form)
        self._shown = False
        self._closing = False
        self._close_callback = close_callback

    def update(self, actions, tools, sections, action_callback, tool_callback):
        self.actions = tuple(actions or ())
        self.tools = tuple(tools or ())
        self.sections = tuple(sections or ())
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                FreeCADGui.deleteLater(widget)
        for section in self.sections:
            group = QtWidgets.QGroupBox(section.title, self.form)
            layout = QtWidgets.QVBoxLayout(group)
            label = QtWidgets.QLabel(section.body, group)
            label.setWordWrap(True)
            layout.addWidget(label)
            self._layout.addWidget(group)
        for title, entries, callback in (
            ("Actions", self.actions, action_callback),
            ("Tools", self.tools, tool_callback),
        ):
            if not entries:
                continue
            group = QtWidgets.QGroupBox(title, self.form)
            layout = QtWidgets.QVBoxLayout(group)
            for entry in entries:
                button = QtWidgets.QPushButton(entry.label, group)
                button.setToolTip(entry.tooltip)
                button.setEnabled(entry.enabled)
                button.clicked.connect(
                    lambda _checked=False, selected=entry, invoke=callback: invoke(selected)
                )
                layout.addWidget(button)
            self._layout.addWidget(group)
        self._layout.addStretch(1)
        if not self._shown and (self.actions or self.tools or self.sections):
            FreeCADGui.Control.showDialog(self, FreeCADGui.ActiveDocument)
            self._shown = True

    def getStandardButtons(self):
        return 0

    def accept(self):
        self._finish_from_ui()
        return True

    def reject(self):
        self._finish_from_ui()
        return True

    def _finish_from_ui(self):
        if self._closing:
            return
        self._shown = False
        if callable(self._close_callback):
            self._close_callback()

    def close(self):
        if not self._shown:
            return
        self._closing = True
        try:
            FreeCADGui.Control.closeDialog()
        except RuntimeError:
            pass
        finally:
            self._shown = False
            self._closing = False

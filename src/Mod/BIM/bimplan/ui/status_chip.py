# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewport status chip for BIM Plan Edit."""


class _PlanEditViewportStatusChip:
    def __new__(cls, session, host_widget):
        from PySide import QtCore, QtGui

        class _Chip(QtGui.QFrame):
            def __init__(self, plan_session, parent_widget):
                super().__init__(parent_widget)
                self.session = plan_session
                self.host_widget = parent_widget
                self.setObjectName("BIMPlanEditViewportStatusChip")
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                self.setFocusPolicy(QtCore.Qt.NoFocus)
                self.setFrameShape(QtGui.QFrame.NoFrame)
                self.setStyleSheet("""
                    QFrame#BIMPlanEditViewportStatusChip {
                        background: rgba(250, 250, 248, 230);
                        border: 1px solid rgba(24, 40, 56, 60);
                        border-radius: 10px;
                    }
                    QLabel#BIMPlanEditViewportStatusTitle {
                        color: rgb(25, 32, 38);
                        font-weight: 600;
                    }
                    QLabel#BIMPlanEditViewportStatusBody {
                        color: rgb(60, 68, 76);
                    }
                    """)

                layout = QtGui.QVBoxLayout(self)
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(2)

                self.title_label = QtGui.QLabel(self)
                self.title_label.setObjectName("BIMPlanEditViewportStatusTitle")
                self.body_label = QtGui.QLabel(self)
                self.body_label.setObjectName("BIMPlanEditViewportStatusBody")
                self.body_label.setWordWrap(True)
                self.body_label.setMaximumWidth(300)

                layout.addWidget(self.title_label)
                layout.addWidget(self.body_label)

                try:
                    self.host_widget.installEventFilter(self)
                except Exception:
                    pass

            def set_texts(self, title, body):
                self.title_label.setText(title)
                self.body_label.setText(body)
                self.adjustSize()
                self._reposition()
                self.show()
                self.raise_()

            def _reposition(self):
                host = self.host_widget
                if host is None:
                    return
                margin = 14
                max_width = max(180, host.width() - (margin * 2))
                self.setMaximumWidth(max_width)
                self.body_label.setMaximumWidth(max_width - 24)
                self.adjustSize()
                self.move(margin, margin)

            def eventFilter(self, watched, event):
                if watched is self.host_widget and event.type() in (
                    QtCore.QEvent.Resize,
                    QtCore.QEvent.Move,
                    QtCore.QEvent.Show,
                ):
                    self._reposition()
                return QtGui.QFrame.eventFilter(self, watched, event)

            def close_chip(self):
                host = self.host_widget
                if host is not None:
                    try:
                        host.removeEventFilter(self)
                    except Exception:
                        pass
                self.host_widget = None
                self.hide()
                self.deleteLater()

        return _Chip(session, host_widget)

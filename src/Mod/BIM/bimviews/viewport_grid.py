# SPDX-License-Identifier: LGPL-2.1-or-later

"""Screen-space grid rendering for planar BIM view contexts."""

import math

import FreeCAD

from ArchRepresentation import RepresentationPurpose
from draftutils.grid import GridLattice, adaptive_lattice_interval
from .grid_settings import get_grid_settings
from .ruler_model import RulerTransform
from . import viewport_widgets
import FreeCADGui

PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
SHOW_GRID_PARAM = "ShowViewGrid"


def grid_enabled():
    """Return whether the BIM planar grid should be displayed."""

    return PARAMS.GetBool(SHOW_GRID_PARAM, True)


if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui

    class ViewportGridOverlay(QtGui.QWidget):
        """Transparent input-pass-through grid painted over a 3D viewport."""

        MINOR_COLOR = (190, 198, 207, 64)
        MAJOR_COLOR = (145, 157, 170, 105)
        AXIS_COLOR = (80, 110, 140, 130)

        def __init__(self, host_widget, transform_provider, lattice_provider, content_widget=None):
            super().__init__(host_widget)
            self.host_widget = host_widget
            self.content_widget = content_widget or host_widget
            self._transform_provider = transform_provider
            self._lattice_provider = lattice_provider
            self.transform = None
            self.lattice = None
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
            self.setGeometry(host_widget.rect())
            self.show()
            self.raise_()

        def sync_geometry(self):
            self.setGeometry(self.host_widget.rect())
            self.raise_()
            self.refresh()

        def refresh(self):
            self.transform = self._transform_provider()
            self.lattice = self._lattice_provider()
            self.update()

        def paintEvent(self, _event):
            transform = self.transform
            lattice = self.lattice
            if transform is None or lattice is None:
                return
            origin_x, origin_y = self._content_origin()
            width = self.content_widget.width()
            height = self.content_widget.height()
            if width <= 0 or height <= 0:
                return

            # Keep display lines on the snap lattice.  The renderer may make
            # this interval coarser below if an extreme zoom would create too
            # many lines, but it never switches to a non-lattice interval.
            display_spacing = adaptive_lattice_interval(
                lattice.spacing, transform.units_per_pixel
            )
            bounds = (
                transform.x_left,
                transform.x_right,
                transform.y_top,
                transform.y_bottom,
            )
            lines = lattice.lines(bounds, display_spacing=display_spacing)
            # A malformed camera or an extreme zoom should never allocate an
            # unbounded amount of paint geometry.  Increase the display step
            # while retaining the same snap lattice.
            if len(lines) > 1200:
                multiplier = int(math.ceil(len(lines) / 1200.0))
                display_spacing *= max(1, multiplier)
                lines = lattice.lines(bounds, display_spacing=display_spacing)

            painter = QtGui.QPainter(self)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
                painter.setClipRect(
                    QtCore.QRectF(float(origin_x), float(origin_y), float(width), float(height))
                )
                for line in lines:
                    start = self._pixel(line.start, transform, origin_x, origin_y)
                    end = self._pixel(line.end, transform, origin_x, origin_y)
                    is_vertical_axis = (
                        abs(line.start.x) <= 1e-9 and abs(line.end.x) <= 1e-9
                    )
                    is_horizontal_axis = (
                        abs(line.start.y) <= 1e-9 and abs(line.end.y) <= 1e-9
                    )
                    if is_vertical_axis or is_horizontal_axis:
                        color = QtGui.QColor(*self.AXIS_COLOR)
                    elif line.major:
                        color = QtGui.QColor(*self.MAJOR_COLOR)
                    else:
                        color = QtGui.QColor(*self.MINOR_COLOR)
                    painter.setPen(QtGui.QPen(color, 1.0))
                    painter.drawLine(start, end)
            finally:
                painter.end()

        @staticmethod
        def _pixel(point, transform, origin_x, origin_y):
            return QtCore.QPoint(
                int(round(origin_x + transform.pixel_for_x(point.x))),
                int(round(origin_y + transform.pixel_for_y(point.y))),
            )

        def _content_origin(self):
            if self.content_widget is self.host_widget:
                return 0, 0
            global_origin = self.content_widget.mapToGlobal(QtCore.QPoint(0, 0))
            point = self.mapFromGlobal(global_origin)
            return point.x(), point.y()


    class _ViewportGridEventFilter(QtCore.QObject):
        def __init__(self, controller):
            super().__init__(controller.overlay)
            self.controller = controller

        def eventFilter(self, watched, event):
            if event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Move):
                self.controller.overlay.sync_geometry()
            return QtCore.QObject.eventFilter(self, watched, event)


class ViewportGridController:
    """Own an adaptive BIM grid overlay for one planar view."""

    def __init__(self, session, request=None):
        self.session = session
        self.request = request
        self.host_widget = None
        self.graphics_view = None
        self.overlay = None
        self.event_filter = None
        self.timer = None
        self._projection_key = None

    def attach(self):
        if not FreeCAD.GuiUp or not grid_enabled() or not self._is_planar_request():
            return False
        graphics_view, host_widget = viewport_widgets.resolve_widgets(
            self.session.viewport
        )
        if graphics_view is None:
            return False
        self.graphics_view = graphics_view
        self.host_widget = host_widget
        graphics_view.destroyed.connect(self._graphics_view_destroyed)
        host_widget.destroyed.connect(self._host_widget_destroyed)
        if self.host_widget is None:
            return False
        self.host_widget.setMouseTracking(True)
        self.overlay = ViewportGridOverlay(
            self.host_widget,
            self._make_transform,
            self._make_lattice,
            self.host_widget,
        )
        self.event_filter = _ViewportGridEventFilter(self)
        self.host_widget.installEventFilter(self.event_filter)
        graphics_view.installEventFilter(self.event_filter)
        self.timer = QtCore.QTimer(self.overlay)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.refresh_if_needed)
        self.timer.start()
        self.overlay.refresh()
        FreeCADGui.adoptQObject(self.overlay)
        return True

    def set_request(self, request):
        self.request = request
        visible = grid_enabled() and self._is_planar_request()
        if self.overlay is None and visible:
            self.attach()
        elif self.overlay is not None:
            self.overlay.setVisible(visible)
            if visible:
                self.overlay.refresh()

    def refresh_if_needed(self):
        key = self.session.viewport.get_plan_projection_cache_key()
        if key != self._projection_key:
            self._projection_key = key
            if self.overlay is not None:
                self.overlay.refresh()

    def close(self):
        if FreeCADGui.isValidQObject(self.timer):
            self.timer.stop()
        viewport_widgets.remove_event_filter(self.host_widget, self.event_filter)
        viewport_widgets.remove_event_filter(self.graphics_view, self.event_filter)
        if FreeCADGui.isValidQObject(self.overlay):
            self.overlay.close()
            # Delete the overlay (and the timer it parents) while its Python
            # wrapper is still alive; see viewport_ruler.close().
            FreeCADGui.deleteLater(self.overlay)
        self.timer = None
        self.event_filter = None
        self.overlay = None
        self.host_widget = None
        self.graphics_view = None
        self._projection_key = None

    def _graphics_view_destroyed(self, *_args):
        self.graphics_view = None
        self.host_widget = None

    def _host_widget_destroyed(self, *_args):
        self.host_widget = None

    def _is_planar_request(self):
        return getattr(self.request, "purpose", None) in (
            RepresentationPurpose.PLAN,
            RepresentationPurpose.SECTION,
            RepresentationPurpose.ELEVATION,
        )

    def _make_lattice(self):
        settings = get_grid_settings()
        return GridLattice(
            FreeCAD.Vector(),
            FreeCAD.Vector(1, 0, 0),
            FreeCAD.Vector(0, 1, 0),
            spacing=settings.spacing,
            major_every=settings.major_every,
        )

    def _make_transform(self):
        if not self._is_planar_request() or self.host_widget is None:
            return None
        width = self.host_widget.width()
        height = self.host_widget.height()
        if width <= 0 or height <= 0:
            return None
        left = self._local_point((0, height // 2))
        right = self._local_point((width, height // 2))
        top = self._local_point((width // 2, height))
        bottom = self._local_point((width // 2, 0))
        units_per_pixel = self.session.viewport.get_plan_view_units_per_pixel()
        if any(point is None for point in (left, right, top, bottom)) or not units_per_pixel:
            return None
        return RulerTransform(
            left.x,
            right.x,
            top.y,
            bottom.y,
            float(width),
            float(height),
            float(units_per_pixel),
        )

    def _local_point(self, mouse_position):
        point = self.session.viewport.get_plan_point_from_mouse_pos(mouse_position)
        if point is None:
            return None
        frame = getattr(self.request, "reference_frame", None)
        if frame is None:
            source = getattr(self.request, "source", None)
            frame = getattr(source, "Placement", None)
        return frame.inverse().multVec(point) if frame is not None else point

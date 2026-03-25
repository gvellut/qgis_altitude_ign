from __future__ import annotations

from functools import partial

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsNetworkAccessManager,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsDockWidget, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.PyQt.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .elevation_request import (
    ElevationRequestError,
    RequestTracker,
    build_elevation_network_request,
    parse_elevation_payload,
)

PLUGIN_TITLE = "Altitude IGN"

if hasattr(QgsWkbTypes, "PointGeometry"):
    POINT_GEOM = QgsWkbTypes.PointGeometry
else:
    POINT_GEOM = QgsWkbTypes.GeometryType.PointGeometry


class ClickedPointMarker:
    def __init__(self, iface) -> None:
        self.canvas = iface.mapCanvas()
        self._wgs84 = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        self._transform = QgsCoordinateTransform(
            self._wgs84,
            self.canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        self._point_band = QgsRubberBand(self.canvas, POINT_GEOM)
        self._point_band.setColor(QColor("magenta"))
        self._point_band.setIconSize(12)
        self._point_band.setWidth(3)

    def cleanup(self) -> None:
        self.clear()

    def clear(self) -> None:
        self._point_band.reset(POINT_GEOM)

    def show_point(self, point_wgs84) -> None:
        self.clear()
        point = self._transform_point(point_wgs84)
        if point is None:
            return
        self._point_band.addPoint(point)

    def _transform_point(self, point):
        destination_crs = self.canvas.mapSettings().destinationCrs()
        if destination_crs.authid() == "EPSG:4326":
            return point

        self._transform.setDestinationCrs(destination_crs)
        try:
            return self._transform.transform(point)
        except Exception:
            return None


class AltitudeIgnDock(QgsDockWidget):
    def __init__(self, iface, title: str) -> None:
        main_window = iface.mainWindow()
        assert isinstance(main_window, QMainWindow)
        super().__init__(title, parent=main_window)

        self.iface = iface
        self.setObjectName("AltitudeIgnDock")
        self.setWindowTitle(title)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._request_tracker = RequestTracker()
        self._pending_reply: QNetworkReply | None = None
        self._clicked_point_marker = ClickedPointMarker(iface)

        self._build_ui()

        if not main_window.restoreDockWidget(self):
            main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self)

        self.visibilityChanged.connect(self._on_visibility_changed)
        self.hide()

    def cleanup(self) -> None:
        self._request_tracker.invalidate()
        self._clear_pending_reply()
        self._clicked_point_marker.cleanup()

        main_window = self.iface.mainWindow()
        if isinstance(main_window, QMainWindow):
            main_window.removeDockWidget(self)

    def ensure_visible(self) -> None:
        self.show()
        self.raise_()

    def clear_value(self) -> None:
        self.value_field.clear()
        self.copy_button.setEnabled(False)

    def show_clicked_point(self, point_wgs84) -> None:
        self._clicked_point_marker.show_point(point_wgs84)

    def clear_clicked_point(self) -> None:
        self._clicked_point_marker.clear()

    def start_lookup(self, lon: float, lat: float) -> None:
        self.ensure_visible()
        request_id = self._request_tracker.start_new_request()
        self.clear_value()
        self._clear_pending_reply()

        reply = QgsNetworkAccessManager.instance().get(
            build_elevation_network_request(lon, lat)
        )
        self._pending_reply = reply
        reply.finished.connect(partial(self._on_reply_finished, request_id, reply))

    def handle_tool_deactivated(self) -> None:
        self._request_tracker.invalidate()
        self._clear_pending_reply()
        self.clear_clicked_point()
        self.clear_value()
        self.hide()

    def _build_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.value_field = QLineEdit(container)
        self.value_field.setReadOnly(True)

        self.copy_button = QPushButton("Copy", container)
        self.copy_button.setEnabled(False)
        self.copy_button.setToolTip("Copy altitude to clipboard")
        self.copy_button.clicked.connect(self._copy_value)

        copy_icon = QgsApplication.getThemeIcon("/mActionEditCopy.svg")
        if not copy_icon.isNull():
            self.copy_button.setIcon(copy_icon)

        row_layout.addWidget(self.value_field, 1)
        row_layout.addWidget(self.copy_button)
        layout.addLayout(row_layout)
        layout.addStretch(1)

        self.setWidget(container)

    def _copy_value(self) -> None:
        value = self.value_field.text()
        if not value:
            return
        QApplication.clipboard().setText(value)

    def _on_reply_finished(self, request_id: int, reply: QNetworkReply) -> None:
        if reply is self._pending_reply:
            self._pending_reply = None

        try:
            if not self._request_tracker.is_current(request_id):
                return

            if reply.error() != QNetworkReply.NetworkError.NoError:
                if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                    return
                raise ElevationRequestError(
                    reply.errorString() or "Network error while requesting elevation."
                )

            value = parse_elevation_payload(bytes(reply.readAll()))
        except ElevationRequestError as exc:
            self.clear_value()
            self.iface.messageBar().pushMessage(
                PLUGIN_TITLE,
                str(exc),
                level=Qgis.Warning,
                duration=5,
            )
        else:
            self.value_field.setText(value)
            self.copy_button.setEnabled(True)
        finally:
            reply.deleteLater()

    def _clear_pending_reply(self) -> None:
        if self._pending_reply is None:
            return

        reply = self._pending_reply
        self._pending_reply = None
        reply.abort()
        reply.deleteLater()

    def _on_visibility_changed(self, visible: bool) -> None:
        if not visible:
            self.clear_clicked_point()

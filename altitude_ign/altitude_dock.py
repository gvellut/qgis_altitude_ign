from __future__ import annotations

from functools import partial

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsNetworkAccessManager,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsDockWidget, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
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
    REQUEST_TIMEOUT_MS,
    ElevationRequestError,
    RequestTracker,
    build_elevation_network_request,
    parse_elevation_payload,
)

PLUGIN_TITLE = "Altitude IGN"
MAX_LOG_PAYLOAD_PREVIEW_LENGTH = 200

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
        self._clear_pending_reply(reason="plugin cleanup")
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
        self._clear_pending_reply(
            reason=f"starting elevation request #{request_id}",
        )

        request = build_elevation_network_request(lon, lat)
        self._log_message(
            (
                f"Starting elevation request #{request_id} for "
                f"lon={lon:.6f}, lat={lat:.6f}, timeout={REQUEST_TIMEOUT_MS} ms, "
                f"url={request.url().toString()}"
            ),
            Qgis.Info,
        )

        reply = QgsNetworkAccessManager.instance().get(request)
        self._pending_reply = reply
        reply.finished.connect(partial(self._on_reply_finished, request_id, reply))

    def handle_tool_deactivated(self) -> None:
        self._request_tracker.invalidate()
        self._clear_pending_reply(reason="tool deactivation")
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
                self._log_message(
                    (
                        f"Ignoring reply for superseded elevation request "
                        f"#{request_id} ({self._describe_reply(reply)})"
                    ),
                    Qgis.Info,
                )
                return

            response_body = bytes(reply.readAll())
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                    self._log_message(
                        (
                            f"Elevation request #{request_id} was canceled "
                            f"({self._describe_reply(reply)})"
                        ),
                        Qgis.Info,
                    )
                    return
                self._log_message(
                    (
                        f"Elevation request #{request_id} failed "
                        f"({self._describe_reply(reply)}, "
                        f"payload={self._payload_preview(response_body)})"
                    ),
                    Qgis.Warning,
                )
                raise ElevationRequestError(
                    reply.errorString() or "Network error while requesting elevation."
                )

            self._log_message(
                (
                    f"Received reply for elevation request #{request_id} "
                    f"({self._describe_reply(reply)}, bytes={len(response_body)})"
                ),
                Qgis.Info,
            )
            try:
                value = parse_elevation_payload(response_body)
            except ElevationRequestError:
                self._log_message(
                    (
                        f"Elevation request #{request_id} returned an invalid payload "
                        f"({self._describe_reply(reply)}, "
                        f"payload={self._payload_preview(response_body)})"
                    ),
                    Qgis.Warning,
                )
                raise
        except ElevationRequestError as exc:
            self.clear_value()
            self.iface.messageBar().pushMessage(
                PLUGIN_TITLE,
                str(exc),
                level=Qgis.Warning,
                duration=5,
            )
        else:
            self._log_message(
                f"Parsed altitude {value} m for elevation request #{request_id}",
                Qgis.Info,
            )
            self.value_field.setText(value)
            self.copy_button.setEnabled(True)
        finally:
            reply.deleteLater()

    def _clear_pending_reply(self, reason: str) -> None:
        if self._pending_reply is None:
            return

        reply = self._pending_reply
        self._pending_reply = None
        self._log_message(
            f"Canceling pending elevation request ({reason}; "
            f"{self._describe_reply(reply)})",
            Qgis.Info,
        )
        reply.abort()
        reply.deleteLater()

    def _on_visibility_changed(self, visible: bool) -> None:
        if not visible:
            self.clear_clicked_point()

    def _describe_reply(self, reply: QNetworkReply) -> str:
        parts = [f"url={reply.url().toString()}"]
        http_status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if http_status is not None:
            parts.append(f"http_status={http_status}")
        if reply.error() != QNetworkReply.NetworkError.NoError:
            parts.append(f"network_error={reply.error()}")
            if reply.errorString():
                parts.append(f"error={reply.errorString()}")
        return ", ".join(parts)

    def _payload_preview(self, payload: bytes) -> str:
        if not payload:
            return "<empty>"

        preview = payload[:MAX_LOG_PAYLOAD_PREVIEW_LENGTH].decode(
            "utf-8",
            errors="replace",
        )
        preview = " ".join(preview.split())
        if len(payload) > MAX_LOG_PAYLOAD_PREVIEW_LENGTH:
            return f"{preview}..."
        return preview

    def _log_message(self, message: str, level: Qgis.MessageLevel) -> None:
        QgsMessageLog.logMessage(message, PLUGIN_TITLE, level)

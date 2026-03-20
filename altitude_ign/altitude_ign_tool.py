from __future__ import annotations

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
)
from qgis.gui import QgsMapMouseEvent, QgsMapTool
from qgis.PyQt.QtCore import Qt

PLUGIN_TITLE = "Altitude IGN"


class AltitudeIgnMapTool(QgsMapTool):
    def __init__(self, iface, action, altitude_dock) -> None:
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.altitude_dock = altitude_dock
        self.setAction(action)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def activate(self) -> None:
        super().activate()
        self.altitude_dock.ensure_visible()
        self.altitude_dock.clear_value()

    def deactivate(self) -> None:
        self.altitude_dock.handle_tool_deactivated()
        super().deactivate()

    def canvasReleaseEvent(self, event: QgsMapMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        try:
            point_wgs84 = self._event_point_to_wgs84(event)
        except Exception as exc:
            self.altitude_dock.clear_value()
            self.iface.messageBar().pushMessage(
                PLUGIN_TITLE,
                str(exc),
                level=Qgis.Warning,
                duration=5,
            )
            return

        self.altitude_dock.show_clicked_point(point_wgs84)
        self.altitude_dock.start_lookup(point_wgs84.x(), point_wgs84.y())

    def _event_point_to_wgs84(self, event: QgsMapMouseEvent) -> QgsPointXY:
        source_crs = self.canvas.mapSettings().destinationCrs()
        destination_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        point = self.canvas.getCoordinateTransform().toMapCoordinates(event.pos())
        transform = QgsCoordinateTransform(
            source_crs,
            destination_crs,
            QgsProject.instance(),
        )
        return transform.transform(QgsPointXY(point.x(), point.y()))

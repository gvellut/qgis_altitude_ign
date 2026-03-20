from __future__ import annotations

import os
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .altitude_dock import AltitudeIgnDock
from .altitude_ign_tool import AltitudeIgnMapTool


class AltitudeIgnPlugin:
    def __init__(self, iface) -> None:
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.tool_action: QAction | None = None
        self.map_tool: AltitudeIgnMapTool | None = None
        self.altitude_dock: AltitudeIgnDock | None = None
        self._previous_tool = None

    def tr(self, message: str) -> str:
        return QCoreApplication.translate(self.__class__.__name__, message)

    def initGui(self) -> None:
        icon_path = str(Path(self.plugin_dir) / "icons" / "altitude_ign.svg")
        icon = QIcon(icon_path)

        self.tool_action = QAction(
            icon,
            self.tr("Altitude IGN"),
            self.iface.mainWindow(),
        )
        self.tool_action.setCheckable(True)
        self.tool_action.setStatusTip(
            self.tr("Click the map to fetch altitude from the IGN service")
        )
        self.tool_action.toggled.connect(self._on_toggled)

        self.altitude_dock = AltitudeIgnDock(
            self.iface,
            self.tr("Altitude IGN"),
        )
        self.map_tool = AltitudeIgnMapTool(
            self.iface,
            self.tool_action,
            self.altitude_dock,
        )

        self.iface.mapToolActionGroup().addAction(self.tool_action)
        self.iface.addPluginToMenu(self.tr("Altitude IGN"), self.tool_action)
        self.iface.addToolBarIcon(self.tool_action)

    def unload(self) -> None:
        canvas = self.iface.mapCanvas()
        if (
            self.map_tool is not None
            and canvas.mapTool() == self.map_tool
            and self._previous_tool is not None
        ):
            canvas.setMapTool(self._previous_tool)

        if self.tool_action is not None:
            try:
                self.tool_action.toggled.disconnect(self._on_toggled)
            except TypeError:
                pass

            self.iface.removePluginMenu(self.tr("Altitude IGN"), self.tool_action)
            self.iface.removeToolBarIcon(self.tool_action)
            self.tool_action.deleteLater()
            self.tool_action = None

        if self.altitude_dock is not None:
            self.altitude_dock.cleanup()
            self.altitude_dock.deleteLater()
            self.altitude_dock = None

        if self.map_tool is not None:
            self.map_tool.deleteLater()
            self.map_tool = None

        self._previous_tool = None

    def _on_toggled(self, checked: bool) -> None:
        if self.map_tool is None or self.altitude_dock is None:
            return

        canvas = self.iface.mapCanvas()
        if checked:
            self._previous_tool = canvas.mapTool()
            canvas.setMapTool(self.map_tool)
            return

        self.altitude_dock.handle_tool_deactivated()
        if canvas.mapTool() == self.map_tool and self._previous_tool is not None:
            canvas.setMapTool(self._previous_tool)

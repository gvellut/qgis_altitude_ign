# Altitude IGN (QGIS plugin)

Altitude IGN is a small QGIS plugin that lets you click on the map and retrieve the altitude of the clicked point from the IGN elevation service: https://geoservices.ign.fr/documentation/services/services-geoplateforme/altimetrie

The web service only covers France and surrounding areas (like Geneva).

## Features

- One checkable action in the QGIS plugin toolbar and in the `Plugins` menu.
- Crosshair map tool while the plugin is active.
- Dock panel with a read-only altitude field and a copy button.
- Automatic conversion of clicked coordinates to WGS84 before calling the IGN API.
- Asynchronous network requests with latest-click-wins behavior.

## Requirements

- QGIS 3.22+
- Python 3.11
- Network access to `https://data.geopf.fr/`

## Install (development)

1. Set `QGIS_PLUGINPATH` to the repository root, for example:
   `/Users/guilhem/Documents/projects/github/qgis_altitude_ign`
2. Restart QGIS.
3. Enable the plugin in `Plugins -> Manage and Install Plugins...`.
4. Optional: install the `Plugin Reloader` plugin to speed up development.

## Usage

1. Activate `Altitude IGN` from the plugin toolbar or the `Plugins` menu.
2. Click on the map.
3. Read the altitude in the `Altitude IGN` dock.
4. Use `Copy` to send the raw value to the clipboard.

When another map tool becomes active, `Altitude IGN` deactivates and hides its dock.

## Development

```bash
uv sync
uv run pytest
```

### VSCode settings

Add these paths to get PyQGIS autocomplete:

```json
{
    "python.analysis.extraPaths": [
        "/Applications/QGIS.app/Contents/Resources/python3.11/site-packages"
    ],
    "python.autoComplete.extraPaths": [
        "/Applications/QGIS.app/Contents/Resources/python3.11/site-packages"
    ]
}
```

## License

GPL v3 or later. See `COPYING`.

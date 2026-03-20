from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

BASE_ELEVATION_URL = (
    "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
)
ELEVATION_RESOURCE = "ign_rge_alti_wld"


class ElevationRequestError(RuntimeError):
    pass


@dataclass
class RequestTracker:
    _current_request_id: int = 0

    def start_new_request(self) -> int:
        self._current_request_id += 1
        return self._current_request_id

    def invalidate(self) -> None:
        self._current_request_id += 1

    def is_current(self, request_id: int) -> bool:
        return request_id == self._current_request_id


def build_elevation_url(lon: float, lat: float) -> str:
    query = urlencode(
        {
            "lon": str(float(lon)),
            "lat": str(float(lat)),
            "resource": ELEVATION_RESOURCE,
            "zonly": "true",
        }
    )
    return f"{BASE_ELEVATION_URL}?{query}"


def parse_elevation_payload(payload: bytes | str) -> str:
    try:
        decoded_payload = json.loads(payload)
    except Exception as exc:
        raise ElevationRequestError("Invalid JSON response from the elevation service.") from exc

    if not isinstance(decoded_payload, dict):
        raise ElevationRequestError("Unexpected response from the elevation service.")

    elevations = decoded_payload.get("elevations")
    if not isinstance(elevations, list) or not elevations:
        raise ElevationRequestError("Elevation service returned no value.")

    elevation = elevations[0]
    if isinstance(elevation, bool) or not isinstance(elevation, int | float):
        raise ElevationRequestError("Elevation service returned an invalid value.")

    rounded_elevation = Decimal(str(elevation)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return str(int(rounded_elevation))

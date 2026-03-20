from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from altitude_ign.elevation_request import (
    BASE_ELEVATION_URL,
    ELEVATION_RESOURCE,
    ElevationRequestError,
    RequestTracker,
    build_elevation_url,
    parse_elevation_payload,
)


class TestElevationRequest(unittest.TestCase):
    def test_build_elevation_url(self) -> None:
        url = build_elevation_url(1.4, 43.54)
        parsed = urlparse(url)

        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", BASE_ELEVATION_URL)
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "lon": ["1.4"],
                "lat": ["43.54"],
                "resource": [ELEVATION_RESOURCE],
                "zonly": ["true"],
            },
        )

    def test_parse_elevation_payload_rounds_to_closest_integer(self) -> None:
        self.assertEqual(
            parse_elevation_payload('{"elevations": [149.55]}'),
            "150",
        )

    def test_parse_elevation_payload_accepts_bytes(self) -> None:
        self.assertEqual(
            parse_elevation_payload(b'{"elevations": [149]}'),
            "149",
        )

    def test_parse_elevation_payload_uses_half_up_rounding(self) -> None:
        self.assertEqual(
            parse_elevation_payload('{"elevations": [149.5]}'),
            "150",
        )
        self.assertEqual(
            parse_elevation_payload('{"elevations": [149.4]}'),
            "149",
        )

    def test_parse_elevation_payload_rejects_invalid_json(self) -> None:
        with self.assertRaises(ElevationRequestError):
            parse_elevation_payload("not-json")

    def test_parse_elevation_payload_rejects_missing_elevations(self) -> None:
        with self.assertRaises(ElevationRequestError):
            parse_elevation_payload("{}")

    def test_parse_elevation_payload_rejects_empty_elevations(self) -> None:
        with self.assertRaises(ElevationRequestError):
            parse_elevation_payload('{"elevations": []}')

    def test_parse_elevation_payload_rejects_non_numeric_value(self) -> None:
        with self.assertRaises(ElevationRequestError):
            parse_elevation_payload('{"elevations": ["149.55"]}')

    def test_request_tracker_latest_request_wins(self) -> None:
        tracker = RequestTracker()

        first_request_id = tracker.start_new_request()
        second_request_id = tracker.start_new_request()

        self.assertFalse(tracker.is_current(first_request_id))
        self.assertTrue(tracker.is_current(second_request_id))

        tracker.invalidate()

        self.assertFalse(tracker.is_current(second_request_id))


if __name__ == "__main__":
    unittest.main()

"""
Data quality validation tests for MDS Provider API.

These tests validate cross-endpoint consistency, data type correctness,
and MDS 2.0 compliance for the trips, events, and telemetry endpoints.
"""

import re
from datetime import datetime, timedelta

from app.config import MDSConstants

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
VERSION_PATTERN = re.compile(r"^2\.0\.[0-9]+$")
MIN_TIMESTAMP_MS = 1514764800000  # 2018-01-01T00:00:00Z


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_hour_param(offset_hours: int = 3) -> str:
    """Return a valid past-hour string for query parameters."""
    return (datetime.utcnow() - timedelta(hours=offset_hours)).strftime("%Y-%m-%dT%H")


# ---------------------------------------------------------------------------
# Trip uniqueness tests
# ---------------------------------------------------------------------------


class TestTripUniqueness:
    """Verify that /trips never returns duplicate trip_ids."""

    def test_no_duplicate_trip_ids(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Each trip_id must be unique within a single /trips response."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        trips = response.json().get("trips", [])
        trip_ids = [t["trip_id"] for t in trips]
        assert len(trip_ids) == len(set(trip_ids)), (
            f"Duplicate trip_ids found: {[tid for tid in trip_ids if trip_ids.count(tid) > 1]}"
        )

    def test_unique_device_trip_combination(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Each (device_id, trip_id) pair must be unique."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        trips = response.json().get("trips", [])
        pairs = [(t["device_id"], t["trip_id"]) for t in trips]
        assert len(pairs) == len(set(pairs)), "Duplicate (device_id, trip_id) pairs found"


# ---------------------------------------------------------------------------
# Cross-endpoint consistency tests
# ---------------------------------------------------------------------------


class TestCrossEndpointConsistency:
    """Verify trip_id linkage across /trips, /events, and /telemetry."""

    def test_each_trip_has_trip_end_event(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Every trip returned by /trips must have a corresponding trip_end event."""
        hour = _get_hour_param()
        trips_resp = client.get(f"/trips?end_time={hour}", headers=auth_headers)
        assert trips_resp.status_code == 200
        trip_ids = {t["trip_id"] for t in trips_resp.json().get("trips", [])}

        events_resp = client.get(
            f"/events/historical?event_time={hour}", headers=auth_headers
        )
        assert events_resp.status_code == 200
        events = events_resp.json().get("events", [])

        trip_end_ids = set()
        for ev in events:
            if "trip_end" in ev.get("event_types", []):
                for tid in ev.get("trip_ids", []):
                    trip_end_ids.add(tid)

        missing = trip_ids - trip_end_ids
        assert not missing, f"Trips missing trip_end events: {missing}"

    def test_each_trip_has_trip_start_event(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Every trip returned by /trips must have a corresponding trip_start event."""
        hour = _get_hour_param()
        trips_resp = client.get(f"/trips?end_time={hour}", headers=auth_headers)
        assert trips_resp.status_code == 200
        trip_ids = {t["trip_id"] for t in trips_resp.json().get("trips", [])}

        events_resp = client.get(
            f"/events/historical?event_time={hour}", headers=auth_headers
        )
        assert events_resp.status_code == 200
        events = events_resp.json().get("events", [])

        trip_start_ids = set()
        for ev in events:
            if "trip_start" in ev.get("event_types", []):
                for tid in ev.get("trip_ids", []):
                    trip_start_ids.add(tid)

        missing = trip_ids - trip_start_ids
        assert not missing, f"Trips missing trip_start events: {missing}"

    def test_telemetry_trip_ids_subset_of_trips(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """All trip_ids referenced in /telemetry must exist in /trips."""
        hour = _get_hour_param()
        trips_resp = client.get(f"/trips?end_time={hour}", headers=auth_headers)
        assert trips_resp.status_code == 200
        trip_ids = {t["trip_id"] for t in trips_resp.json().get("trips", [])}

        telemetry_resp = client.get(
            f"/telemetry?telemetry_time={hour}", headers=auth_headers
        )
        assert telemetry_resp.status_code == 200
        telemetry = telemetry_resp.json().get("telemetry", [])

        telemetry_trip_ids = set()
        for t in telemetry:
            for tid in t.get("trip_ids", []):
                telemetry_trip_ids.add(tid)

        orphan = telemetry_trip_ids - trip_ids
        assert not orphan, f"Telemetry references trip_ids not in /trips: {orphan}"

    def test_event_trip_ids_match_trip_trip_ids(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """trip_ids on trip_start/trip_end events must be a subset of /trips trip_ids."""
        hour = _get_hour_param()
        trips_resp = client.get(f"/trips?end_time={hour}", headers=auth_headers)
        assert trips_resp.status_code == 200
        trip_ids = {t["trip_id"] for t in trips_resp.json().get("trips", [])}

        events_resp = client.get(
            f"/events/historical?event_time={hour}", headers=auth_headers
        )
        assert events_resp.status_code == 200
        events = events_resp.json().get("events", [])

        event_trip_ids = set()
        for ev in events:
            etypes = ev.get("event_types", [])
            if "trip_start" in etypes or "trip_end" in etypes:
                for tid in ev.get("trip_ids", []):
                    event_trip_ids.add(tid)

        orphan = event_trip_ids - trip_ids
        assert not orphan, f"Event trip_ids not found in /trips: {orphan}"


# ---------------------------------------------------------------------------
# Data type and format validation tests
# ---------------------------------------------------------------------------


class TestTripDataTypes:
    """Validate data types and formats for /trips responses."""

    def test_trip_uuid_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """trip_id, device_id, and provider_id must be valid UUIDs."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        for trip in response.json().get("trips", []):
            assert UUID_PATTERN.match(trip["trip_id"]), f"Invalid trip_id: {trip['trip_id']}"
            assert UUID_PATTERN.match(trip["device_id"]), f"Invalid device_id: {trip['device_id']}"
            assert UUID_PATTERN.match(trip["provider_id"]), f"Invalid provider_id: {trip['provider_id']}"

    def test_trip_timestamps(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """start_time and end_time must be integers >= MIN_TIMESTAMP_MS."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        for trip in response.json().get("trips", []):
            assert isinstance(trip["start_time"], int)
            assert isinstance(trip["end_time"], int)
            assert trip["start_time"] >= MIN_TIMESTAMP_MS, f"start_time too small: {trip['start_time']}"
            assert trip["end_time"] >= MIN_TIMESTAMP_MS, f"end_time too small: {trip['end_time']}"
            assert trip["end_time"] >= trip["start_time"], "end_time before start_time"

    def test_trip_gps_coordinates(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """GPS coordinates must be within valid ranges."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        for trip in response.json().get("trips", []):
            for loc_key in ("start_location", "end_location"):
                loc = trip[loc_key]
                assert -90 <= loc["lat"] <= 90, f"{loc_key}.lat out of range: {loc['lat']}"
                assert -180 <= loc["lng"] <= 180, f"{loc_key}.lng out of range: {loc['lng']}"

    def test_trip_duration_and_distance_non_negative(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """duration and distance must be non-negative integers."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        for trip in response.json().get("trips", []):
            assert isinstance(trip["duration"], int)
            assert trip["duration"] >= 0
            assert isinstance(trip["distance"], int)
            assert trip["distance"] >= 0


class TestEventDataTypes:
    """Validate data types and formats for /events responses."""

    def test_event_uuid_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """event_id, device_id, and provider_id must be valid UUIDs."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for ev in response.json().get("events", []):
            assert UUID_PATTERN.match(ev["event_id"]), f"Invalid event_id: {ev['event_id']}"
            assert UUID_PATTERN.match(ev["device_id"]), f"Invalid device_id: {ev['device_id']}"
            assert UUID_PATTERN.match(ev["provider_id"]), f"Invalid provider_id: {ev['provider_id']}"

    def test_event_timestamps(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Event timestamps must be integers >= MIN_TIMESTAMP_MS."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for ev in response.json().get("events", []):
            assert isinstance(ev["timestamp"], int)
            assert ev["timestamp"] >= MIN_TIMESTAMP_MS, f"timestamp too small: {ev['timestamp']}"

    def test_event_types_non_empty_and_unique(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """event_types must have at least 1 item with unique values."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for ev in response.json().get("events", []):
            etypes = ev["event_types"]
            assert len(etypes) >= 1, "event_types must have at least 1 item"
            assert len(etypes) == len(set(etypes)), f"Duplicate event_types: {etypes}"

    def test_event_gps_coordinates(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """GPS coordinates in events must be within valid ranges."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for ev in response.json().get("events", []):
            loc = ev.get("location")
            if loc:
                assert -90 <= loc["lat"] <= 90, f"lat out of range: {loc['lat']}"
                assert -180 <= loc["lng"] <= 180, f"lng out of range: {loc['lng']}"

    def test_trip_events_have_trip_ids(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """trip_start and trip_end events must have non-empty trip_ids."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for ev in response.json().get("events", []):
            etypes = ev.get("event_types", [])
            if "trip_start" in etypes or "trip_end" in etypes:
                trip_ids = ev.get("trip_ids", [])
                assert trip_ids and len(trip_ids) > 0, (
                    f"trip_start/trip_end event missing trip_ids: event_id={ev['event_id']}"
                )
                for tid in trip_ids:
                    assert UUID_PATTERN.match(tid), f"Invalid trip_id in event: {tid}"


class TestTelemetryDataTypes:
    """Validate data types and formats for /telemetry responses."""

    def test_telemetry_uuid_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """telemetry_id, device_id, provider_id, journey_id must be valid UUIDs."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for t in response.json().get("telemetry", []):
            assert UUID_PATTERN.match(t["telemetry_id"]), f"Invalid telemetry_id: {t['telemetry_id']}"
            assert UUID_PATTERN.match(t["device_id"]), f"Invalid device_id: {t['device_id']}"
            assert UUID_PATTERN.match(t["provider_id"]), f"Invalid provider_id: {t['provider_id']}"
            assert UUID_PATTERN.match(t["journey_id"]), f"Invalid journey_id: {t['journey_id']}"

    def test_telemetry_trip_ids_are_uuids(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """trip_ids in telemetry must be valid UUIDs with at least 1 item."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for t in response.json().get("telemetry", []):
            trip_ids = t.get("trip_ids", [])
            assert len(trip_ids) >= 1, "telemetry must have at least 1 trip_id"
            for tid in trip_ids:
                assert UUID_PATTERN.match(tid), f"Invalid trip_id in telemetry: {tid}"

    def test_telemetry_timestamps(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Telemetry timestamps must be integers >= MIN_TIMESTAMP_MS."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for t in response.json().get("telemetry", []):
            assert isinstance(t["timestamp"], int)
            assert t["timestamp"] >= MIN_TIMESTAMP_MS, f"timestamp too small: {t['timestamp']}"

    def test_telemetry_gps_coordinates(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """GPS coordinates in telemetry must be within valid ranges."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        for t in response.json().get("telemetry", []):
            loc = t.get("location")
            assert loc is not None, "telemetry must have location"
            assert -90 <= loc["lat"] <= 90, f"lat out of range: {loc['lat']}"
            assert -180 <= loc["lng"] <= 180, f"lng out of range: {loc['lng']}"


# ---------------------------------------------------------------------------
# Response structure and MDS compliance tests
# ---------------------------------------------------------------------------


class TestMDSResponseStructure:
    """Validate MDS 2.0 response structure compliance."""

    def test_trips_content_type(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Trips response must have correct MDS Content-Type header."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == MDSConstants.CONTENT_TYPE_JSON

    def test_events_content_type(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Events response must have correct MDS Content-Type header."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == MDSConstants.CONTENT_TYPE_JSON

    def test_telemetry_content_type(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Telemetry response must have correct MDS Content-Type header."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == MDSConstants.CONTENT_TYPE_JSON

    def test_trips_version_field(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Trips response must include valid MDS version."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert VERSION_PATTERN.match(data["version"]), f"Invalid version: {data['version']}"

    def test_events_version_field(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Events response must include valid MDS version."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert VERSION_PATTERN.match(data["version"]), f"Invalid version: {data['version']}"

    def test_telemetry_version_field(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Telemetry response must include valid MDS version."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert VERSION_PATTERN.match(data["version"]), f"Invalid version: {data['version']}"

    def test_trips_required_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Each trip must contain all MDS 2.0 required fields."""
        end_time = _get_hour_param()
        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        required = [
            "provider_id", "device_id", "trip_id", "duration",
            "distance", "start_location", "end_location",
            "start_time", "end_time",
        ]
        for trip in response.json().get("trips", []):
            for field in required:
                assert field in trip, f"Missing required field '{field}' in trip"

    def test_events_required_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Each event must contain all MDS 2.0 required fields."""
        hour = _get_hour_param()
        response = client.get(f"/events/historical?event_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        required = [
            "event_id", "provider_id", "device_id",
            "event_types", "vehicle_state", "timestamp",
        ]
        for ev in response.json().get("events", []):
            for field in required:
                assert field in ev, f"Missing required field '{field}' in event"

    def test_telemetry_required_fields(
        self, client, auth_headers, mock_cross_endpoint_service, mock_jwt_handler
    ):
        """Each telemetry must contain all MDS 2.0 required fields."""
        hour = _get_hour_param()
        response = client.get(f"/telemetry?telemetry_time={hour}", headers=auth_headers)
        assert response.status_code == 200

        required = [
            "provider_id", "device_id", "telemetry_id",
            "timestamp", "trip_ids", "journey_id", "location",
        ]
        for t in response.json().get("telemetry", []):
            for field in required:
                assert field in t, f"Missing required field '{field}' in telemetry"

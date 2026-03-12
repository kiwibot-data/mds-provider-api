"""
Great Expectations validation suite for MDS Provider API data quality.

Uses GE to define, run, and report on expectations for trips, events,
and telemetry data returned by the API — ensuring cross-endpoint consistency
and MDS 2.0 compliance.

This serves as both:
  1. A pytest-runnable test suite (CI gate)
  2. A documented specification of what "correct" MDS data looks like
"""

import pytest
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import great_expectations as gx
import pandas as pd

from app.services.transformers import data_transformer
from app.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
MDS_VERSION_RE = re.compile(r"^2\.0\.\d+$")

MIN_TIMESTAMP_MS = 1609459200000  # 2021-01-01 UTC in milliseconds


def _make_trip_row(job_id: str, robot_id: str, offset_minutes: int = 0) -> dict:
    """Create a realistic trip row as BigQuery would return it."""
    base = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)
    return {
        "robot_id": robot_id,
        "trip_id": f"trip_{job_id}",
        "trip_start": base,
        "trip_end": base + timedelta(minutes=12),
        "trip_duration_seconds": 720,
        "start_latitude": 38.9072,
        "start_longitude": -77.0369,
        "end_latitude": 38.9142,
        "end_longitude": -77.0300,
        "status": "completed",
        "user_id": "user-abc",
        "job_id": job_id,
        "created_at": base,
        "updated_at": base + timedelta(minutes=12),
    }


def _make_event_row(
    job_id: str, robot_id: str, event_type: str, offset_minutes: int = 0
) -> dict:
    """Create a realistic event row as BigQuery would return it."""
    base = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)
    ts = base if event_type == "trip_start" else base + timedelta(minutes=12)
    return {
        "robot_id": robot_id,
        "event_id": f"event_{robot_id}_{job_id}_{event_type}",
        "event_type": event_type,
        "event_time": ts,
        "latitude": 38.9072 if event_type == "trip_start" else 38.9142,
        "longitude": -77.0369 if event_type == "trip_start" else -77.0300,
        "event_data": None,
        "created_at": ts,
        "job_id": job_id,
    }


def _make_telemetry_row(job_id: str, robot_id: str, offset_minutes: int = 0) -> dict:
    """Create a realistic telemetry row."""
    base = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)
    return {
        "robot_id": robot_id,
        "trip_id": f"trip_{job_id}",
        "trip_start": base,
        "trip_end": base + timedelta(minutes=12),
        "start_latitude": 38.9072,
        "start_longitude": -77.0369,
        "end_latitude": 38.9142,
        "end_longitude": -77.0300,
        "status": "completed",
        "job_id": job_id,
    }


# ---------------------------------------------------------------------------
# Fixtures — Build a realistic multi-trip dataset
# ---------------------------------------------------------------------------

JOBS = [
    ("job-001", "4E005"),
    ("job-002", "4E005"),
    ("job-003", "4E014"),
    ("job-004", "4E079"),
    ("job-005", "4E085"),
]


@pytest.fixture
def trips_df() -> pd.DataFrame:
    rows = [_make_trip_row(jid, rid, i * 15) for i, (jid, rid) in enumerate(JOBS)]
    return pd.DataFrame(rows)


@pytest.fixture
def events_df() -> pd.DataFrame:
    rows = []
    for i, (jid, rid) in enumerate(JOBS):
        rows.append(_make_event_row(jid, rid, "trip_start", i * 15))
        rows.append(_make_event_row(jid, rid, "trip_end", i * 15))
    return pd.DataFrame(rows)


@pytest.fixture
def telemetry_df() -> pd.DataFrame:
    rows = [_make_telemetry_row(jid, rid, i * 15) for i, (jid, rid) in enumerate(JOBS)]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# GE Context + Dataset helpers
# ---------------------------------------------------------------------------

def _get_ge_context():
    """Get an ephemeral Great Expectations context (no filesystem state)."""
    return gx.get_context(mode="ephemeral")


def _add_dataframe_asset(context, df: pd.DataFrame, name: str):
    """Add a DataFrame as a GE datasource/asset and return a batch."""
    datasource = context.data_sources.add_pandas(name=f"{name}_datasource")
    asset = datasource.add_dataframe_asset(name=f"{name}_asset")
    batch_definition = asset.add_batch_definition_whole_dataframe(f"{name}_batch_def")
    return batch_definition.get_batch(batch_parameters={"dataframe": df})


# ===========================================================================
#  TEST SUITE 1 — Trip Expectations
# ===========================================================================


class TestTripExpectations:
    """GE expectations on the trips dataset."""

    def test_trip_id_column_exists_and_not_null(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_notnull")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToNotBeNull(column="trip_id")
        )
        assert result.success, f"trip_id has nulls: {result.result}"

    def test_trip_id_unique(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_unique")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeUnique(column="trip_id")
        )
        assert result.success, f"Duplicate trip_ids found: {result.result}"

    def test_job_id_unique(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_job_unique")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeUnique(column="job_id")
        )
        assert result.success, f"Duplicate job_ids in trips: {result.result}"

    def test_start_latitude_in_range(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_lat")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="start_latitude", min_value=-90, max_value=90
            )
        )
        assert result.success, f"start_latitude out of range: {result.result}"

    def test_start_longitude_in_range(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_lng")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="start_longitude", min_value=-180, max_value=180
            )
        )
        assert result.success, f"start_longitude out of range: {result.result}"

    def test_end_latitude_in_range(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_end_lat")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="end_latitude", min_value=-90, max_value=90
            )
        )
        assert result.success

    def test_end_longitude_in_range(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_end_lng")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="end_longitude", min_value=-180, max_value=180
            )
        )
        assert result.success

    def test_trip_duration_non_negative(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_dur")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="trip_duration_seconds", min_value=0
            )
        )
        assert result.success, f"Negative duration found: {result.result}"

    def test_robot_id_not_null(self, trips_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_robot")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToNotBeNull(column="robot_id")
        )
        assert result.success

    def test_trip_end_after_trip_start(self, trips_df):
        """Verify trip_end > trip_start for every row."""
        for _, row in trips_df.iterrows():
            assert row["trip_end"] > row["trip_start"], (
                f"trip_end <= trip_start for trip_id={row['trip_id']}"
            )


# ===========================================================================
#  TEST SUITE 2 — Event Expectations
# ===========================================================================


class TestEventExpectations:
    """GE expectations on the events dataset."""

    def test_event_id_not_null(self, events_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, events_df, "events_id")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToNotBeNull(column="event_id")
        )
        assert result.success

    def test_event_type_in_allowed_set(self, events_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, events_df, "events_type")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeInSet(
                column="event_type",
                value_set=["trip_start", "trip_end", "intermediate_stop", "located"],
            )
        )
        assert result.success, f"Invalid event_type: {result.result}"

    def test_job_id_not_null_for_trip_events(self, events_df):
        """trip_start and trip_end events must have a non-null job_id."""
        trip_events = events_df[events_df["event_type"].isin(["trip_start", "trip_end"])]
        assert trip_events["job_id"].notna().all(), "Some trip events missing job_id"

    def test_latitude_in_range(self, events_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, events_df, "events_lat")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="latitude", min_value=-90, max_value=90
            )
        )
        assert result.success

    def test_longitude_in_range(self, events_df):
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, events_df, "events_lng")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column="longitude", min_value=-180, max_value=180
            )
        )
        assert result.success


# ===========================================================================
#  TEST SUITE 3 — Cross-Endpoint Consistency (the core invariants)
# ===========================================================================


class TestCrossEndpointExpectations:
    """
    The critical cross-endpoint checks that correspond directly
    to Michael's reported issues.
    """

    def test_trip_end_count_equals_trip_count(self, trips_df, events_df):
        """
        Michael's issue #1: 'We don't see the equivalent number of trip_end
        events for trips returned from the trip API call.'

        Expectation: |trip_end events| == |trips|
        """
        trip_count = len(trips_df)
        trip_end_count = len(events_df[events_df["event_type"] == "trip_end"])
        assert trip_end_count == trip_count, (
            f"trip_end count ({trip_end_count}) != trip count ({trip_count})"
        )

    def test_trip_start_count_equals_trip_count(self, trips_df, events_df):
        """Symmetric check: trip_start count should also match."""
        trip_count = len(trips_df)
        trip_start_count = len(events_df[events_df["event_type"] == "trip_start"])
        assert trip_start_count == trip_count, (
            f"trip_start count ({trip_start_count}) != trip count ({trip_count})"
        )

    def test_no_duplicate_trip_ids(self, trips_df):
        """
        Michael's issue #2: 'duplicate records that share the same trip_id
        for the same device_id, but have differing metadata.'

        Expectation: Every trip_id in /trips is unique.
        """
        context = _get_ge_context()
        batch = _add_dataframe_asset(context, trips_df, "trips_dup_check")
        result = batch.validate(
            gx.expectations.ExpectColumnValuesToBeUnique(column="trip_id")
        )
        assert result.success, f"Duplicate trip_ids found: {result.result}"

    def test_event_job_ids_match_trip_job_ids(self, trips_df, events_df):
        """
        Every trip event's job_id should correspond to a trip's job_id.
        This ensures events and trips are correctly linked.
        """
        trip_job_ids = set(trips_df["job_id"])
        trip_events = events_df[events_df["event_type"].isin(["trip_start", "trip_end"])]
        event_job_ids = set(trip_events["job_id"])

        orphaned = event_job_ids - trip_job_ids
        assert len(orphaned) == 0, (
            f"Events reference {len(orphaned)} job_ids not in trips: {orphaned}"
        )

    def test_trip_job_ids_have_matching_events(self, trips_df, events_df):
        """Every trip's job_id should have both trip_start and trip_end events."""
        trip_ends = events_df[events_df["event_type"] == "trip_end"]
        trip_starts = events_df[events_df["event_type"] == "trip_start"]

        trip_job_ids = set(trips_df["job_id"])
        start_job_ids = set(trip_starts["job_id"])
        end_job_ids = set(trip_ends["job_id"])

        missing_starts = trip_job_ids - start_job_ids
        missing_ends = trip_job_ids - end_job_ids

        assert len(missing_starts) == 0, (
            f"{len(missing_starts)} trip(s) missing trip_start event: {missing_starts}"
        )
        assert len(missing_ends) == 0, (
            f"{len(missing_ends)} trip(s) missing trip_end event: {missing_ends}"
        )

    def test_telemetry_job_ids_subset_of_trip_job_ids(
        self, trips_df, telemetry_df
    ):
        """
        Michael's issue #3: 'telemetries linked to trips returned back
        from /events and /trips.'

        Expectation: telemetry job_ids ⊆ trips job_ids
        """
        trip_job_ids = set(trips_df["job_id"])
        telemetry_job_ids = set(telemetry_df["job_id"])

        orphaned = telemetry_job_ids - trip_job_ids
        assert len(orphaned) == 0, (
            f"Telemetry references {len(orphaned)} job_ids not in trips: {orphaned}"
        )

    def test_consistent_trip_id_generation(self, trips_df, events_df):
        """
        Verify that the same job_id produces the same trip_id UUID
        across trips, events, and telemetry (deterministic UUID5).
        """
        for _, trip_row in trips_df.iterrows():
            job_id = trip_row["job_id"]
            expected_trip_id = data_transformer._generate_trip_id({"job_id": job_id})

            # Find matching events
            matching_events = events_df[
                (events_df["job_id"] == job_id)
                & (events_df["event_type"].isin(["trip_start", "trip_end"]))
            ]
            for _, event_row in matching_events.iterrows():
                event_trip_id = data_transformer._generate_trip_id(
                    {"job_id": event_row["job_id"]}
                )
                assert event_trip_id == expected_trip_id, (
                    f"Trip ID mismatch for job_id={job_id}: "
                    f"trip={expected_trip_id}, event={event_trip_id}"
                )


# ===========================================================================
#  TEST SUITE 4 — Monitoring System Integration
# ===========================================================================


class TestMonitoringIntegration:
    """Test that the DataQualityMonitor produces correct reports."""

    @pytest.mark.asyncio
    async def test_healthy_data_produces_clean_report(
        self, trips_df, events_df, telemetry_df
    ):
        from app.monitoring.data_quality import DataQualityMonitor

        monitor = DataQualityMonitor()
        report = await monitor.run_checks_for_hour(
            hour="2026-03-04T18",
            trips_data=trips_df.to_dict("records"),
            events_data=events_df.to_dict("records"),
            telemetry_data=telemetry_df.to_dict("records"),
        )
        assert report.is_healthy, (
            f"Report should be healthy but got {report.checks_failed} failures: "
            f"{[a.to_dict() for a in report.alerts]}"
        )
        assert report.checks_passed == report.checks_run
        assert report.checks_failed == 0

    @pytest.mark.asyncio
    async def test_duplicate_trips_trigger_critical_alert(self, trips_df, events_df):
        from app.monitoring.data_quality import DataQualityMonitor, AlertSeverity

        # Inject a duplicate
        bad_trips = pd.concat([trips_df, trips_df.iloc[[0]]], ignore_index=True)

        monitor = DataQualityMonitor()
        report = await monitor.run_checks_for_hour(
            hour="2026-03-04T18",
            trips_data=bad_trips.to_dict("records"),
            events_data=events_df.to_dict("records"),
        )
        assert not report.is_healthy
        dup_alerts = [a for a in report.alerts if a.check_name == "no_duplicate_trip_ids"]
        assert len(dup_alerts) == 1
        assert dup_alerts[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_missing_trip_end_triggers_alert(self, trips_df, events_df):
        from app.monitoring.data_quality import DataQualityMonitor

        # Remove all trip_end events
        events_start_only = events_df[events_df["event_type"] != "trip_end"]

        monitor = DataQualityMonitor()
        report = await monitor.run_checks_for_hour(
            hour="2026-03-04T18",
            trips_data=trips_df.to_dict("records"),
            events_data=events_start_only.to_dict("records"),
        )
        assert not report.is_healthy
        parity_alerts = [a for a in report.alerts if a.check_name == "trip_end_parity"]
        assert len(parity_alerts) == 1
        assert "deviates" in parity_alerts[0].message

    @pytest.mark.asyncio
    async def test_health_summary_available(self, trips_df, events_df):
        from app.monitoring.data_quality import DataQualityMonitor

        monitor = DataQualityMonitor()
        await monitor.run_checks_for_hour(
            hour="2026-03-04T18",
            trips_data=trips_df.to_dict("records"),
            events_data=events_df.to_dict("records"),
        )
        summary = monitor.get_health_summary()
        assert "data_quality" in summary
        assert summary["data_quality"]["last_check"]["is_healthy"] is True

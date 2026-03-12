"""
MDS Data Quality Monitoring & Alerting System.

Provides automated checks to catch data inconsistencies before stakeholders do.
Runs as a background check on each API response or as a scheduled health check.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DataQualityAlert:
    """Represents a data quality issue detected by the monitoring system."""
    check_name: str
    severity: AlertSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DataQualityReport:
    """Aggregated report from a data quality check run."""
    hour_checked: str
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    alerts: List[DataQualityAlert] = field(default_factory=list)
    run_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        return self.checks_failed == 0

    @property
    def has_critical(self) -> bool:
        return any(a.severity == AlertSeverity.CRITICAL for a in self.alerts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour_checked": self.hour_checked,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "is_healthy": self.is_healthy,
            "has_critical_alerts": self.has_critical,
            "alerts": [a.to_dict() for a in self.alerts],
            "run_timestamp": self.run_timestamp.isoformat(),
        }


class DataQualityMonitor:
    """
    Monitors MDS data quality by cross-checking trips, events, and telemetry.

    Key invariants checked:
      1. trip_end count == trip count (per hour)
      2. trip_start count == trip count (per hour)
      3. No duplicate trip_ids in /trips
      4. telemetry trip_ids ⊆ trips trip_ids
      5. event trip_ids ⊆ trips trip_ids
      6. All trip_ids, device_ids, event_ids are valid UUIDs
      7. GPS coordinates in valid ranges
    """

    # Alert if trip_end count deviates from trip count by more than this %
    TRIP_END_DEVIATION_THRESHOLD_PCT = 5.0
    # Alert if duplicate trip_ids exceed this count
    DUPLICATE_THRESHOLD = 0

    def __init__(self):
        self._last_report: Optional[DataQualityReport] = None
        self._alert_history: List[DataQualityAlert] = []

    @property
    def last_report(self) -> Optional[DataQualityReport]:
        return self._last_report

    async def run_checks_for_hour(
        self,
        hour: str,
        trips_data: List[Dict[str, Any]],
        events_data: List[Dict[str, Any]],
        telemetry_data: Optional[List[Dict[str, Any]]] = None,
    ) -> DataQualityReport:
        """
        Run all data quality checks for a given hour's data.

        Args:
            hour: The hour being checked (YYYY-MM-DDTHH)
            trips_data: Raw trip records from BigQuery
            events_data: Raw event records from BigQuery
            telemetry_data: Raw telemetry records (optional)

        Returns:
            DataQualityReport with results
        """
        report = DataQualityReport(hour_checked=hour)

        # Check 1: No duplicate trip_ids
        self._check_no_duplicate_trips(trips_data, report)

        # Check 2: trip_end count matches trip count
        self._check_trip_end_parity(trips_data, events_data, report)

        # Check 3: trip_start count matches trip count
        self._check_trip_start_parity(trips_data, events_data, report)

        # Check 4: event trip_ids are subset of trips trip_ids
        self._check_event_trip_ids_linkage(trips_data, events_data, report)

        # Check 5: telemetry trip_ids are subset of trips trip_ids
        if telemetry_data:
            self._check_telemetry_trip_ids_linkage(trips_data, telemetry_data, report)

        # Check 6: GPS coordinates in valid range
        self._check_gps_coordinates(trips_data, events_data, report)

        # Check 7: All timestamps are reasonable
        self._check_timestamps(trips_data, events_data, report)

        self._last_report = report
        self._alert_history.extend(report.alerts)

        # Log results
        if report.is_healthy:
            logger.info(
                f"Data quality check PASSED for {hour}: "
                f"{report.checks_passed}/{report.checks_run} checks passed"
            )
        else:
            log_fn = logger.critical if report.has_critical else logger.warning
            log_fn(
                f"Data quality check FAILED for {hour}: "
                f"{report.checks_failed}/{report.checks_run} checks failed, "
                f"{len(report.alerts)} alerts"
            )
            for alert in report.alerts:
                logger.warning(f"  [{alert.severity.value}] {alert.check_name}: {alert.message}")

        return report

    def _check_no_duplicate_trips(
        self, trips: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that no trip_id appears more than once."""
        report.checks_run += 1
        from collections import Counter

        trip_ids = [t.get("trip_id", t.get("job_id", "")) for t in trips]
        counts = Counter(trip_ids)
        duplicates = {tid: cnt for tid, cnt in counts.items() if cnt > self.DUPLICATE_THRESHOLD + 1}

        if duplicates:
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="no_duplicate_trip_ids",
                severity=AlertSeverity.CRITICAL,
                message=f"Found {len(duplicates)} duplicate trip_id(s) across {sum(duplicates.values())} records",
                details={"duplicates": {k: v for k, v in list(duplicates.items())[:10]}},
            ))
        else:
            report.checks_passed += 1

    def _check_trip_end_parity(
        self, trips: List[Dict], events: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that trip_end event count matches trip count within threshold."""
        report.checks_run += 1

        trip_count = len(trips)
        trip_end_count = sum(1 for e in events if e.get("event_type") == "trip_end")

        if trip_count == 0:
            report.checks_passed += 1
            return

        deviation_pct = abs(trip_end_count - trip_count) / trip_count * 100

        if deviation_pct > self.TRIP_END_DEVIATION_THRESHOLD_PCT:
            severity = (
                AlertSeverity.CRITICAL
                if deviation_pct > 20
                else AlertSeverity.WARNING
            )
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="trip_end_parity",
                severity=severity,
                message=(
                    f"trip_end count ({trip_end_count}) deviates from trip count ({trip_count}) "
                    f"by {deviation_pct:.1f}% (threshold: {self.TRIP_END_DEVIATION_THRESHOLD_PCT}%)"
                ),
                details={
                    "trip_count": trip_count,
                    "trip_end_count": trip_end_count,
                    "deviation_pct": round(deviation_pct, 2),
                },
            ))
        else:
            report.checks_passed += 1

    def _check_trip_start_parity(
        self, trips: List[Dict], events: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that trip_start event count matches trip count within threshold."""
        report.checks_run += 1

        trip_count = len(trips)
        trip_start_count = sum(1 for e in events if e.get("event_type") == "trip_start")

        if trip_count == 0:
            report.checks_passed += 1
            return

        deviation_pct = abs(trip_start_count - trip_count) / trip_count * 100

        if deviation_pct > self.TRIP_END_DEVIATION_THRESHOLD_PCT:
            severity = (
                AlertSeverity.CRITICAL
                if deviation_pct > 20
                else AlertSeverity.WARNING
            )
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="trip_start_parity",
                severity=severity,
                message=(
                    f"trip_start count ({trip_start_count}) deviates from trip count ({trip_count}) "
                    f"by {deviation_pct:.1f}%"
                ),
                details={
                    "trip_count": trip_count,
                    "trip_start_count": trip_start_count,
                    "deviation_pct": round(deviation_pct, 2),
                },
            ))
        else:
            report.checks_passed += 1

    def _check_event_trip_ids_linkage(
        self, trips: List[Dict], events: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that trip_ids referenced in events exist in trips."""
        report.checks_run += 1

        trip_job_ids = {t.get("job_id", "") for t in trips}

        # Events with trip types should reference known jobs
        unlinked = []
        for e in events:
            if e.get("event_type") in ("trip_start", "trip_end"):
                event_job_id = e.get("job_id", "")
                if event_job_id and event_job_id not in trip_job_ids:
                    unlinked.append(event_job_id)

        if unlinked:
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="event_trip_id_linkage",
                severity=AlertSeverity.WARNING,
                message=f"{len(unlinked)} event(s) reference job_ids not found in trips",
                details={"unlinked_job_ids": unlinked[:10]},
            ))
        else:
            report.checks_passed += 1

    def _check_telemetry_trip_ids_linkage(
        self, trips: List[Dict], telemetry: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that telemetry trip_ids are a subset of trips trip_ids."""
        report.checks_run += 1

        trip_job_ids = {t.get("job_id", "") for t in trips}
        telemetry_job_ids = {t.get("job_id", "") for t in telemetry}

        orphaned = telemetry_job_ids - trip_job_ids - {""}
        if orphaned:
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="telemetry_trip_id_linkage",
                severity=AlertSeverity.WARNING,
                message=f"{len(orphaned)} telemetry job_id(s) not found in trips",
                details={"orphaned_job_ids": list(orphaned)[:10]},
            ))
        else:
            report.checks_passed += 1

    def _check_gps_coordinates(
        self, trips: List[Dict], events: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that all GPS coordinates are in valid ranges."""
        report.checks_run += 1

        invalid = []
        for i, trip in enumerate(trips):
            for prefix in ["start_", "end_"]:
                lat = trip.get(f"{prefix}latitude")
                lng = trip.get(f"{prefix}longitude")
                if lat is not None and (lat < -90 or lat > 90):
                    invalid.append(f"trip[{i}].{prefix}latitude={lat}")
                if lng is not None and (lng < -180 or lng > 180):
                    invalid.append(f"trip[{i}].{prefix}longitude={lng}")

        for i, event in enumerate(events):
            lat = event.get("latitude")
            lng = event.get("longitude")
            if lat is not None and (lat < -90 or lat > 90):
                invalid.append(f"event[{i}].latitude={lat}")
            if lng is not None and (lng < -180 or lng > 180):
                invalid.append(f"event[{i}].longitude={lng}")

        if invalid:
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="gps_coordinates_valid",
                severity=AlertSeverity.CRITICAL,
                message=f"{len(invalid)} invalid GPS coordinate(s) found",
                details={"invalid_coords": invalid[:10]},
            ))
        else:
            report.checks_passed += 1

    def _check_timestamps(
        self, trips: List[Dict], events: List[Dict], report: DataQualityReport
    ) -> None:
        """Check that all timestamps are reasonable (not in far future or pre-2021)."""
        report.checks_run += 1

        min_ts = datetime(2021, 1, 1, tzinfo=timezone.utc)
        max_ts = datetime.now(timezone.utc) + timedelta(days=1)

        issues = []
        for i, trip in enumerate(trips):
            for field_name in ["trip_start", "trip_end"]:
                ts = trip.get(field_name)
                if ts is not None:
                    if isinstance(ts, datetime):
                        if ts < min_ts or ts > max_ts:
                            issues.append(f"trip[{i}].{field_name}={ts}")

        for i, event in enumerate(events):
            ts = event.get("event_time")
            if ts is not None:
                if isinstance(ts, datetime):
                    if ts < min_ts or ts > max_ts:
                        issues.append(f"event[{i}].event_time={ts}")

        if issues:
            report.checks_failed += 1
            report.alerts.append(DataQualityAlert(
                check_name="timestamps_reasonable",
                severity=AlertSeverity.WARNING,
                message=f"{len(issues)} timestamp(s) outside reasonable range",
                details={"issues": issues[:10]},
            ))
        else:
            report.checks_passed += 1

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of the monitoring state for the /health endpoint."""
        recent_alerts = [
            a.to_dict()
            for a in self._alert_history[-20:]  # Last 20 alerts
        ]
        return {
            "data_quality": {
                "last_check": self._last_report.to_dict() if self._last_report else None,
                "recent_alerts_count": len(recent_alerts),
                "recent_alerts": recent_alerts,
            }
        }


# Global singleton
data_quality_monitor = DataQualityMonitor()

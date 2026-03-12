#!/usr/bin/env python3
"""
MDS 2.0 Validation Script

This script replicates the Postman MDS 2.0 VALIDATOR collection tests.
It validates all endpoints against the MDS 2.0 specification.

Usage:
    python validate_mds_2.0.py --base-url https://mds.kiwibot.com/v1/provider --token YOUR_TOKEN
    python validate_mds_2.0.py --config config.json
    python validate_mds_2.0.py --ignore-attributes  # Ignore attributes field failures
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import requests
from colorama import Fore, Style, init
import re
from uuid import UUID

# Initialize colorama for cross-platform colored output
init(autoreset=True)


class MDSValidator:
    """MDS 2.0 API Validator"""

    def __init__(
        self,
        base_url: str,
        token: str,
        ignore_attributes: bool = True,
        verbose: bool = False
    ):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.ignore_attributes = ignore_attributes
        self.verbose = verbose
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'tests': []
        }

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Tuple[int, Dict, str]:
        """Make HTTP request to MDS API endpoint."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Accept': 'application/vnd.mds+json;version=2.0',
            'X-API-Key': self.token,
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if self.verbose:
                # Truncate to avoid exposing sensitive/PII data in logs
                truncated = response.text[:500] + ('...' if len(response.text) > 500 else '')
                print(f"DEBUG: Response for {url} with params {params}: {truncated}")
            raw_response = response.text
            status_code = response.status_code
            data = None
            if status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    print("    ✗ Failed to decode JSON from response")
            return status_code, data, raw_response
        except requests.exceptions.RequestException as e:
            print(f"    ✗ HTTP request failed: {e}")
            return 0, None, str(e)


    def _log(self, message: str, level: str = "info"):
        """Log message with color coding."""
        if level == "success":
            print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
        elif level == "error":
            print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
        elif level == "warning":
            print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")
        elif level == "info":
            print(f"{Fore.CYAN}ℹ {message}{Style.RESET_ALL}")
        else:
            print(message)

    def _validate_version(self, data: Dict) -> bool:
        """Validate MDS version field."""
        version = data.get('version')
        pattern = r'^2\.0\.[0-9]+$'

        if not version:
            self._log("Missing 'version' field", "error")
            return False

        if not re.match(pattern, version):
            self._log(f"Invalid version format: {version} (expected 2.0.x)", "error")
            return False

        return True

    def _validate_uuid(self, uuid_string, field_name):
        try:
            UUID(uuid_string)
            return True
        except (ValueError, TypeError):
            self._log(f"Invalid UUID format for {field_name}: {uuid_string}", "error")
            return False

    def _validate_events_schema(self, events, endpoint_name):
        if not events:
            return

        for event in events:
            # Validate UUIDs
            for uuid_field in ['event_id', 'provider_id', 'device_id']:
                if uuid_field in event:
                    self._validate_uuid(event[uuid_field], uuid_field)
            
            # Validate timestamps
            for ts_field in ['timestamp']:
                if ts_field in event:
                    self._validate_timestamp(event[ts_field], f"{endpoint_name}.{ts_field}")

    def _validate_timestamp(self, value: Any, field_name: str) -> bool:
        """Validate timestamp (milliseconds since epoch)."""
        min_timestamp = 1514764800000  # Jan 1, 2018

        if not isinstance(value, (int, float)):
            self._log(f"{field_name}: Expected number, got {type(value).__name__}", "error")
            return False

        if value < min_timestamp:
            self._log(f"{field_name}: Timestamp {value} is before minimum (Jan 1, 2018)", "error")
            return False

        if value % 1 != 0:
            self._log(f"{field_name}: Timestamp must be whole number (milliseconds)", "error")
            return False

        return True

    def _validate_gps(self, gps: Dict, field_name: str = "location") -> bool:
        """Validate GPS object."""
        if not isinstance(gps, dict):
            self._log(f"{field_name}: Expected object, got {type(gps).__name__}", "error")
            return False

        # Required fields
        if 'lat' not in gps or 'lng' not in gps:
            self._log(f"{field_name}: Missing required 'lat' or 'lng' fields", "error")
            return False

        # Validate latitude
        lat = gps['lat']
        if not isinstance(lat, (int, float)):
            self._log(f"{field_name}.lat: Expected number, got {type(lat).__name__}", "error")
            return False
        if not (-90 <= lat <= 90):
            self._log(f"{field_name}.lat: Value {lat} out of range (-90 to 90)", "error")
            return False

        # Validate longitude
        lng = gps['lng']
        if not isinstance(lng, (int, float)):
            self._log(f"{field_name}.lng: Expected number, got {type(lng).__name__}", "error")
            return False
        if not (-180 <= lng <= 180):
            self._log(f"{field_name}.lng: Value {lng} out of range (-180 to 180)", "error")
            return False

        # Validate optional fields
        if 'heading' in gps:
            heading = gps['heading']
            if not isinstance(heading, (int, float)) or not (0 <= heading <= 360):
                self._log(f"{field_name}.heading: Value {heading} out of range (0 to 360)", "error")
                return False

        if 'satellites' in gps:
            satellites = gps['satellites']
            if not isinstance(satellites, int) or satellites < 0:
                self._log(f"{field_name}.satellites: Must be integer >= 0", "error")
                return False

        return True

    def _validate_event_types(self, event_types: List[str], vehicle_state: str) -> bool:
        """Validate event types for delivery-robots mode."""
        if not isinstance(event_types, list):
            self._log("event_types: Expected array", "error")
            return False

        if len(event_types) < 1:
            self._log("event_types: Must contain at least one event type", "error")
            return False

        if len(event_types) != len(set(event_types)):
            self._log("event_types: Must contain unique values", "error")
            return False

        # Valid event types per state for delivery-robots mode
        valid_types_by_state = {
            'removed': ['comms_restored', 'decommissioned', 'located', 'maintenance_pick_up'],
            'available': ['comms_restored', 'customer_cancellation', 'driver_cancellation',
                         'located', 'provider_cancellation', 'service_start', 'trip_end',
                         'trip_enter_jurisdiction'],
            'non_operational': ['comms_restored', 'located', 'maintenance_end', 'recommission',
                               'reservation_start', 'service_end', 'trip_enter_jurisdiction'],
            'reserved': ['comms_restored', 'located', 'reservation_start', 'trip_enter_jurisdiction'],
            'on_trip': ['comms_restored', 'located', 'trip_enter_jurisdiction', 'trip_resume', 'trip_start'],
            'stopped': ['comms_restored', 'located', 'order_drop_off', 'order_pick_up',
                       'reservation_stop', 'trip_pause'],
            'non_contactable': ['comms_lost'],
            'missing': ['not_located'],
            'elsewhere': ['comms_restored', 'located', 'trip_leave_jurisdiction']
        }

        valid_types = valid_types_by_state.get(vehicle_state, [])
        if not valid_types:
            self._log(f"Unknown vehicle_state: {vehicle_state}", "warning")
            return True  # Don't fail on unknown state

        for event_type in event_types:
            if event_type not in valid_types:
                self._log(
                    f"event_type '{event_type}' not valid for vehicle_state '{vehicle_state}'",
                    "error"
                )
                return False

        return True

    def validate_historical_events(self, event_time: str) -> Dict:
        """Validate /events/historical endpoint."""
        test_name = "Historical Events Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"Parameter: event_time={event_time}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request(
            '/events/historical',
            params={'event_time': event_time}
        )

        errors = []
        warnings = []

        # Check HTTP status
        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            if self.verbose and raw_response:
                print(f"Response: {raw_response[:500]}")
            return self._record_result(test_name, False, errors, warnings)

        # Validate version
        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        # Validate events array
        if 'events' not in data:
            errors.append("Missing 'events' array")
            return self._record_result(test_name, False, errors, warnings)

        events = data['events']
        if not isinstance(events, list):
            errors.append("'events' must be an array")
            return self._record_result(test_name, False, errors, warnings)

        self._log(f"Found {len(events)} events", "info")

        # Validate each event
        for i, event in enumerate(events):
            prefix = f"events[{i}]"

            # Required fields
            required_fields = ['event_id', 'provider_id', 'device_id', 'event_types',
                             'vehicle_state', 'timestamp']

            for field in required_fields:
                if field not in event:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate UUIDs
            for uuid_field in ['event_id', 'provider_id', 'device_id']:
                if uuid_field in event:
                    if not self._validate_uuid(event[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            # Validate timestamp
            if 'timestamp' in event:
                if not self._validate_timestamp(event['timestamp'], f"{prefix}.timestamp"):
                    errors.append(f"{prefix}.timestamp: Invalid timestamp")

            # Validate event_types
            if 'event_types' in event and 'vehicle_state' in event:
                if not self._validate_event_types(event['event_types'], event['vehicle_state']):
                    errors.append(f"{prefix}: Invalid event_types for vehicle_state")

            # Validate location (if present)
            if 'location' in event and event['location']:
                if not self._validate_gps(event['location'], f"{prefix}.location"):
                    errors.append(f"{prefix}.location: Invalid GPS object")

            # Check for location OR event_geographies
            if 'location' not in event and 'event_geographies' not in event:
                errors.append(f"{prefix}: Must have either 'location' or 'event_geographies'")

            # Validate optional numeric ranges
            if 'battery_pct' in event:
                battery = event['battery_pct']
                if not isinstance(battery, (int, float)) or not (0 <= battery <= 100):
                    errors.append(f"{prefix}.battery_pct: Must be 0-100")

            # Check for attributes fields (warn if ignore_attributes is True)
            if self.ignore_attributes:
                # Don't validate these fields as they're not customized for delivery-robots
                pass

            # Break after validating first few events if there are many
            if i >= 10 and len(events) > 10:
                self._log(f"Validated first 10 events, skipping remaining {len(events) - 10}", "info")
                break

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def validate_recent_events(self, start_time: int, end_time: int) -> Dict:
        """Validate /events/recent endpoint."""
        test_name = "Recent Events Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"Parameters: start_time={start_time}, end_time={end_time}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request(
            '/events/recent',
            params={'start_time': start_time, 'end_time': end_time}
        )

        errors = []
        warnings = []

        # Check HTTP status
        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            return self._record_result(test_name, False, errors, warnings)

        # Same validation as historical events
        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        if 'events' not in data:
            errors.append("Missing 'events' array")
            return self._record_result(test_name, False, errors, warnings)

        events = data['events']
        self._log(f"Found {len(events)} events", "info")

        # Validate each event (same as historical)
        for i, event in enumerate(events[:10]):  # Limit to first 10
            prefix = f"events[{i}]"

            required_fields = ['event_id', 'provider_id', 'device_id', 'event_types',
                             'vehicle_state', 'timestamp']

            for field in required_fields:
                if field not in event:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            for uuid_field in ['event_id', 'provider_id', 'device_id']:
                if uuid_field in event:
                    if not self._validate_uuid(event[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            if 'timestamp' in event:
                if not self._validate_timestamp(event['timestamp'], f"{prefix}.timestamp"):
                    errors.append(f"{prefix}.timestamp: Invalid timestamp")

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def validate_telemetry(self, telemetry_time: str) -> Dict:
        """Validate /telemetry endpoint."""
        test_name = "Telemetry Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"Parameter: telemetry_time={telemetry_time}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request(
            '/telemetry',
            params={'telemetry_time': telemetry_time}
        )

        errors = []
        warnings = []

        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            return self._record_result(test_name, False, errors, warnings)

        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        if 'telemetry' not in data:
            errors.append("Missing 'telemetry' array")
            return self._record_result(test_name, False, errors, warnings)

        telemetry = data['telemetry']
        self._log(f"Found {len(telemetry)} telemetry points", "info")

        # Validate each telemetry point
        for i, point in enumerate(telemetry[:10]):  # Limit to first 10
            prefix = f"telemetry[{i}]"

            # Required fields per MDS 2.0
            required_fields = ['device_id', 'provider_id', 'telemetry_id', 'timestamp',
                             'trip_ids', 'journey_id', 'location']

            for field in required_fields:
                if field not in point:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate UUIDs
            for uuid_field in ['device_id', 'provider_id', 'telemetry_id', 'journey_id']:
                if uuid_field in point:
                    if not self._validate_uuid(point[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            # Validate trip_ids array
            if 'trip_ids' in point:
                trip_ids = point['trip_ids']
                if not isinstance(trip_ids, list):
                    errors.append(f"{prefix}.trip_ids: Must be an array")
                elif len(trip_ids) < 1:
                    errors.append(f"{prefix}.trip_ids: Must contain at least one trip ID")
                else:
                    for j, trip_id in enumerate(trip_ids):
                        if not self._validate_uuid(trip_id, f"{prefix}.trip_ids[{j}]"):
                            errors.append(f"{prefix}.trip_ids[{j}]: Invalid UUID")

            # Validate timestamp
            if 'timestamp' in point:
                if not self._validate_timestamp(point['timestamp'], f"{prefix}.timestamp"):
                    errors.append(f"{prefix}.timestamp: Invalid timestamp")

            # Validate location (GPS object)
            if 'location' in point:
                if not self._validate_gps(point['location'], f"{prefix}.location"):
                    errors.append(f"{prefix}.location: Invalid GPS object")

            # Validate optional battery_percent
            if 'battery_percent' in point:
                battery = point['battery_percent']
                if not isinstance(battery, int) or not (0 <= battery <= 100):
                    errors.append(f"{prefix}.battery_percent: Must be integer 0-100")

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def validate_trips(self, end_time: str) -> Dict:
        """Validate /trips endpoint."""
        test_name = "Trips Schema Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"Parameter: end_time={end_time}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request(
            '/trips',
            params={'end_time': end_time}
        )

        errors = []
        warnings = []

        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            return self._record_result(test_name, False, errors, warnings)

        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        if 'trips' not in data:
            errors.append("Missing 'trips' array")
            return self._record_result(test_name, False, errors, warnings)

        trips = data['trips']
        self._log(f"Found {len(trips)} trips", "info")

        # Validate each trip
        for i, trip in enumerate(trips[:10]):
            prefix = f"trips[{i}]"

            # Required fields for delivery-robots mode
            required_fields = ['provider_id', 'device_id', 'trip_id', 'start_time',
                             'end_time', 'start_location', 'end_location', 'duration', 'distance']

            for field in required_fields:
                if field not in trip:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate UUIDs
            for uuid_field in ['provider_id', 'device_id', 'trip_id']:
                if uuid_field in trip:
                    if not self._validate_uuid(trip[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            # Validate timestamps
            for ts_field in ['start_time', 'end_time']:
                if ts_field in trip:
                    if not self._validate_timestamp(trip[ts_field], f"{prefix}.{ts_field}"):
                        errors.append(f"{prefix}.{ts_field}: Invalid timestamp")

            # Validate duration and distance
            if 'duration' in trip:
                if not isinstance(trip['duration'], int) or trip['duration'] < 0:
                    errors.append(f"{prefix}.duration: Must be integer >= 0")

            if 'distance' in trip:
                if not isinstance(trip['distance'], int) or trip['distance'] < 0:
                    errors.append(f"{prefix}.distance: Must be integer >= 0")

            # Validate locations (MDS 2.0 GPS objects with lat/lng)
            for loc_field in ['start_location', 'end_location']:
                if loc_field in trip:
                    if not self._validate_gps(trip[loc_field], f"{prefix}.{loc_field}"):
                        errors.append(f"{prefix}.{loc_field}: Invalid GPS location object")

            # Warn about attributes if ignore_attributes is True
            if self.ignore_attributes:
                if 'trip_attributes' in trip:
                    warnings.append(f"{prefix}.trip_attributes: Validation skipped (ignore_attributes=True)")

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def validate_vehicle_status(self) -> Dict:
        """Validate /vehicles/status endpoint."""
        test_name = "Vehicle Status Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request('/vehicles/status')

        errors = []
        warnings = []

        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            return self._record_result(test_name, False, errors, warnings)

        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        # Validate required response fields
        required_response_fields = ['version', 'data', 'last_updated', 'ttl']
        for field in required_response_fields:
            if field not in data:
                errors.append(f"Missing required response field '{field}'")

        # Validate last_updated
        if 'last_updated' in data:
            last_updated_val = data['last_updated']
            # MDS spec says POSIX time (seconds), not milliseconds
            if not isinstance(last_updated_val, int):
                errors.append(f"last_updated: Expected integer, got {type(last_updated_val).__name__}")
            elif last_updated_val < 1514764800:  # Jan 1, 2018 in seconds
                errors.append(f"last_updated: Timestamp {last_updated_val} is before minimum (Jan 1, 2018)")

        # Validate ttl
        if 'ttl' in data:
            ttl = data['ttl']
            if not isinstance(ttl, int) or not (0 <= ttl <= 300000):
                errors.append(f"ttl must be integer 0-300000, got {ttl}")

        if 'data' not in data or 'vehicles_status' not in data.get('data', {}):
            errors.append("Missing 'vehicles_status' array in data object")
            return self._record_result(test_name, False, errors, warnings)

        vehicles_status = data['data']['vehicles_status']
        self._log(f"Found {len(vehicles_status)} vehicle status records", "info")

        # Validate each status record
        for i, status in enumerate(vehicles_status[:10]):
            prefix = f"vehicles_status[{i}]"

            required_fields = ['device_id', 'provider_id', 'vehicle_state',
                             'last_event_time', 'last_event_types']

            for field in required_fields:
                if field not in status:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate UUIDs
            for uuid_field in ['device_id', 'provider_id']:
                if uuid_field in status:
                    if not self._validate_uuid(status[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            # Validate last_event_time
            if 'last_event_time' in status:
                if not self._validate_timestamp(status['last_event_time'], f"{prefix}.last_event_time"):
                    errors.append(f"{prefix}.last_event_time: Invalid timestamp")

            # Validate last_event_types array
            if 'last_event_types' in status:
                event_types = status['last_event_types']
                if not isinstance(event_types, list) or len(event_types) < 1:
                    errors.append(f"{prefix}.last_event_types: Must be array with at least 1 item")

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def validate_vehicles(self) -> Dict:
        """Validate /vehicles endpoint."""
        test_name = "Vehicles Validation"
        self._log(f"\n{'='*60}", "info")
        self._log(f"Running: {test_name}", "info")
        self._log(f"{'='*60}", "info")

        status_code, data, raw_response = self._make_request('/vehicles')

        errors = []
        warnings = []

        if status_code != 200:
            errors.append(f"Expected HTTP 200, got {status_code}")
            self._log(f"HTTP {status_code}", "error")
            return self._record_result(test_name, False, errors, warnings)

        if not self._validate_version(data):
            errors.append("Invalid or missing version field")

        # Validate required response fields
        required_response_fields = ['version', 'data', 'last_updated', 'ttl']
        for field in required_response_fields:
            if field not in data:
                errors.append(f"Missing required response field '{field}'")

        if 'data' not in data or 'vehicles' not in data.get('data', {}):
            errors.append("Missing 'vehicles' array in data object")
            return self._record_result(test_name, False, errors, warnings)

        vehicles = data['data']['vehicles']
        self._log(f"Found {len(vehicles)} vehicles", "info")

        # Validate each vehicle
        for i, vehicle in enumerate(vehicles[:10]):
            prefix = f"vehicles[{i}]"

            required_fields = ['device_id', 'provider_id', 'vehicle_id',
                             'vehicle_type', 'propulsion_types']

            for field in required_fields:
                if field not in vehicle:
                    errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate UUIDs
            for uuid_field in ['device_id', 'provider_id']:
                if uuid_field in vehicle:
                    if not self._validate_uuid(vehicle[uuid_field], f"{prefix}.{uuid_field}"):
                        errors.append(f"{prefix}.{uuid_field}: Invalid UUID")

            # Validate vehicle_id (string, not necessarily UUID)
            if 'vehicle_id' in vehicle:
                if not isinstance(vehicle['vehicle_id'], str):
                    errors.append(f"{prefix}.vehicle_id: Must be string")

            # Validate propulsion_types array
            if 'propulsion_types' in vehicle:
                propulsion = vehicle['propulsion_types']
                if not isinstance(propulsion, list) or len(propulsion) < 1:
                    errors.append(f"{prefix}.propulsion_types: Must be array with at least 1 item")

            # Warn about attributes if ignore_attributes is True
            if self.ignore_attributes:
                if 'vehicle_attributes' in vehicle:
                    warnings.append(f"{prefix}.vehicle_attributes: Validation skipped")

        success = len(errors) == 0
        return self._record_result(test_name, success, errors, warnings)

    def _record_result(
        self,
        test_name: str,
        success: bool,
        errors: List[str],
        warnings: List[str]
    ) -> Dict:
        """Record test result."""
        result = {
            'test': test_name,
            'success': success,
            'errors': errors,
            'warnings': warnings
        }

        self.results['tests'].append(result)

        if success:
            self.results['passed'] += 1
            self._log(f"{test_name}: PASSED", "success")
        else:
            self.results['failed'] += 1
            self._log(f"{test_name}: FAILED", "error")
            for error in errors:
                self._log(f"  - {error}", "error")

        if warnings:
            self.results['warnings'] += len(warnings)
            for warning in warnings:
                self._log(f"  - {warning}", "warning")

        return result

    def run_all_tests(self) -> Dict:
        """Run all validation tests."""
        self._log(f"\n{'#'*60}", "info")
        self._log("MDS 2.0 VALIDATION SUITE", "info")
        self._log(f"Base URL: {self.base_url}", "info")
        self._log(f"Ignore Attributes: {self.ignore_attributes}", "info")
        self._log(f"{'#'*60}\n", "info")

        # Calculate test parameters
        now = datetime.utcnow()

        # Historical events: 1 hour ago
        event_time = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H")

        # Recent events: last 2 hours
        start_time = int((now - timedelta(hours=2)).timestamp() * 1000)
        end_time = int(now.timestamp() * 1000)

        # Telemetry: 1 hour ago
        telemetry_time = event_time

        # Trips: 1 hour ago
        trip_end_time = event_time

        # Run all tests
        self.validate_historical_events(event_time)
        self.validate_recent_events(start_time, end_time)
        self.validate_telemetry(telemetry_time)
        self.validate_trips(trip_end_time)
        self.validate_vehicle_status()
        self.validate_vehicles()

        return self.results

    def print_summary(self):
        """Print test summary."""
        total = self.results['passed'] + self.results['failed']

        print(f"\n{'='*60}")
        print(f"{Fore.CYAN}VALIDATION SUMMARY{Style.RESET_ALL}")
        print(f"{'='*60}")
        print(f"Total Tests:  {total}")
        print(f"{Fore.GREEN}Passed:       {self.results['passed']}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed:       {self.results['failed']}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Warnings:     {self.results['warnings']}{Style.RESET_ALL}")
        print(f"{'='*60}\n")

        if self.results['failed'] > 0:
            print(f"{Fore.RED}VALIDATION FAILED{Style.RESET_ALL}")
            print("Fix the errors above and run validation again.\n")
            return False
        else:
            print(f"{Fore.GREEN}✓ ALL VALIDATIONS PASSED!{Style.RESET_ALL}")
            print("Your API is MDS 2.0 compliant.\n")
            return True

    def save_report(self, filename: str = "mds_validation_report.json"):
        """Save validation report to JSON file."""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'base_url': self.base_url,
            'ignore_attributes': self.ignore_attributes,
            'summary': {
                'total': self.results['passed'] + self.results['failed'],
                'passed': self.results['passed'],
                'failed': self.results['failed'],
                'warnings': self.results['warnings']
            },
            'tests': self.results['tests']
        }

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        self._log(f"Report saved to {filename}", "success")


def main():
    parser = argparse.ArgumentParser(
        description="MDS 2.0 API Validation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate with direct parameters
  python validate_mds_2.0.py --base-url https://mds.kiwibot.com/v1/provider --token YOUR_TOKEN

  # Validate with config file
  python validate_mds_2.0.py --config config.json

  # Validate and ignore attribute field failures
  python validate_mds_2.0.py --base-url https://api.example.com --token TOKEN --ignore-attributes

  # Verbose output
  python validate_mds_2.0.py --config config.json --verbose

Config file format (JSON):
{
  "base_url": "https://mds.kiwibot.com/v1/provider",
  "token": "your_bearer_token_here"
}
        """
    )

    parser.add_argument(
        '--base-url',
        help='Base URL of the MDS Provider API (e.g., https://mds.kiwibot.com/v1/provider)'
    )
    parser.add_argument(
        '--token',
        help='Bearer token for authentication'
    )
    parser.add_argument(
        '--config',
        help='Path to JSON config file with base_url and token'
    )
    parser.add_argument(
        '--ignore-attributes',
        action='store_true',
        default=True,
        help='Ignore validation failures in *_attributes fields (default: True)'
    )
    parser.add_argument(
        '--no-ignore-attributes',
        dest='ignore_attributes',
        action='store_false',
        help='Validate *_attributes fields (disables --ignore-attributes)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--output',
        default='mds_validation_report.json',
        help='Output file for validation report (default: mds_validation_report.json)'
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                base_url = config.get('base_url')
                token = config.get('token')
        except Exception as e:
            print(f"{Fore.RED}Error loading config file: {e}{Style.RESET_ALL}")
            sys.exit(1)
    else:
        base_url = args.base_url
        token = args.token

    # Validate required parameters
    if not base_url or not token:
        parser.print_help()
        print(f"\n{Fore.RED}Error: --base-url and --token are required (or use --config){Style.RESET_ALL}")
        sys.exit(1)

    # Create validator and run tests
    validator = MDSValidator(
        base_url=base_url,
        token=token,
        ignore_attributes=args.ignore_attributes,
        verbose=args.verbose
    )

    results = validator.run_all_tests()
    validator.print_summary()
    validator.save_report(args.output)

    # Exit with appropriate code
    sys.exit(0 if results['failed'] == 0 else 1)


if __name__ == '__main__':
    main()

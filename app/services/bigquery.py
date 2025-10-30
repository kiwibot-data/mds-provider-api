"""
BigQuery service for fetching robot data.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, GoogleCloudError
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

logger = logging.getLogger(__name__)


class BigQueryService:
    """Service for interacting with BigQuery data sources."""

    def __init__(self):
        """Initialize BigQuery client."""
        self.client = bigquery.Client(project=settings.BIGQUERY_PROJECT_ID)
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def _run_query_async(self, query: str) -> List[Dict[str, Any]]:
        """Run BigQuery query asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor, self._execute_query, query
            )
            return result
        except Exception as e:
            logger.error(f"BigQuery query failed: {str(e)}")
            raise

    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute BigQuery query synchronously."""
        try:
            logger.info(f"Executing BigQuery query")
            query_job = self.client.query(query)
            results = query_job.result()
            return [dict(row) for row in results]
        except GoogleCloudError as e:
            logger.error(f"BigQuery error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in BigQuery query: {str(e)}")
            raise

    async def get_robot_locations(
        self,
        robot_ids: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch robot location data from pre-computed BigQuery table.

        Args:
            robot_ids: List of specific robot IDs to filter
            since: Only return locations after this timestamp
            limit: Maximum number of records to return

        Returns:
            List of location records
        """
        # Use the specific robot IDs from the sample query
        default_robots = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        # Build query for pre-computed vehicles table
        query = f"""
        SELECT
            robot_id,
            latitude,
            longitude,
            timestamp,
            accuracy,
            status,
            battery_level,
            last_updated
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}`
        WHERE 1=1
        """

        # Add robot ID filter
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" AND robot_id IN ('{robot_ids_str}')"
        else:
            # Use default robot list
            robot_ids_str = "', '".join(default_robots)
            query += f" AND robot_id IN ('{robot_ids_str}')"

        # Add time filter
        if since:
            query += f" AND timestamp >= '{since.isoformat()}'"

        # Add ordering and limit
        query += " ORDER BY timestamp DESC"
        if limit:
            query += f" LIMIT {limit}"

        return await self._run_query_async(query)

    async def get_robot_trips(
        self,
        robot_ids: Optional[List[str]] = None,
        end_time_hour: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch robot trip data from pre-computed BigQuery table.

        Args:
            robot_ids: List of specific robot IDs to filter
            end_time_hour: Hour in format YYYY-MM-DDTHH for MDS compliance
            since: Only return trips after this timestamp

        Returns:
            List of trip records
        """
        # Use the specific robot IDs from the sample query
        default_robots = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        # Build query for pre-computed trips table
        query = f"""
        SELECT
            robot_id,
            trip_id,
            trip_start,
            trip_end,
            trip_duration_seconds,
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
            status,
            user_id,
            job_id,
            created_at,
            updated_at
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_TRIPS_PROCESSED}`
        WHERE 1=1
        """

        # Add robot ID filter
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" AND robot_id IN ('{robot_ids_str}')"
        else:
            # Use default robot list
            robot_ids_str = "', '".join(default_robots)
            query += f" AND robot_id IN ('{robot_ids_str}')"

        # Add time filters
        if end_time_hour:
            # Parse hour format and create time range
            try:
                start_time = datetime.strptime(end_time_hour, "%Y-%m-%dT%H")
                end_time = start_time + timedelta(hours=1)
                query += f" AND trip_end >= '{start_time.isoformat()}'"
                query += f" AND trip_end < '{end_time.isoformat()}'"
            except ValueError:
                raise ValueError(f"Invalid end_time format. Expected YYYY-MM-DDTHH, got: {end_time_hour}")
        elif since:
            query += f" AND created_at >= '{since.isoformat()}'"
        else:
            # Default to last 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            query += f" AND created_at >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        query += " ORDER BY created_at DESC"

        return await self._run_query_async(query)

    async def get_robot_current_status(
        self,
        robot_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get current status of robots from pre-computed table.

        Args:
            robot_ids: List of specific robot IDs to filter

        Returns:
            List of current robot status records
        """
        query = f"""
        SELECT
            robot_id,
            latitude,
            longitude,
            timestamp,
            accuracy,
            status,
            battery_level,
            last_updated
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}`
        """

        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" WHERE robot_id IN ('{robot_ids_str}')"

        query += " ORDER BY last_updated DESC"

        return await self._run_query_async(query)

    async def get_active_robot_list(self) -> List[Dict[str, Any]]:
        """
        Get list of currently active robot data from the specific robot list.

        Returns:
            List of robot data dictionaries for robots with recent activity
        """
        robot_ids = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        cutoff_date = datetime.utcnow() - timedelta(days=settings.VEHICLE_RETENTION_DAYS)
        robot_ids_str = "', '".join(robot_ids)
        
        query = f"""
        SELECT
            t1.robot_id,
            t1.latitude,
            t1.longitude,
            t1.timestamp,
            t1.accuracy,
            t1.status,
            t1.battery_level,
            t1.last_updated
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}` AS t1
        INNER JOIN (
            SELECT robot_id, MAX(last_updated) as max_last_updated
            FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}`
            WHERE robot_id IN ('{robot_ids_str}')
            AND last_updated >= '{cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}'
            GROUP BY robot_id
        ) AS t2 ON t1.robot_id = t2.robot_id AND t1.last_updated = t2.max_last_updated
        WHERE t1.robot_id IN ('{robot_ids_str}')
        """

        results = await self._run_query_async(query)
        return results

    async def get_robot_events(
        self,
        robot_ids: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch robot event data from pre-computed BigQuery table.

        Args:
            robot_ids: List of specific robot IDs to filter
            since: Only return events after this timestamp
            until: Only return events before this timestamp
            limit: Maximum number of records to return

        Returns:
            List of event records
        """
        # Use the specific robot IDs from the sample query
        default_robots = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        # Build query for pre-computed events table
        query = f"""
        SELECT
            robot_id,
            event_id,
            event_type,
            event_time,
            latitude,
            longitude,
            event_data,
            created_at
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_EVENTS}`
        WHERE 1=1
        """

        # Add robot ID filter
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" AND robot_id IN ('{robot_ids_str}')"
        else:
            # Use default robot list
            robot_ids_str = "', '".join(default_robots)
            query += f" AND robot_id IN ('{robot_ids_str}')"

        # Add time filters (temporarily disabled for debugging)
        if since:
            query += f" AND event_time >= '{since.isoformat()}'"
        if until:
            query += f" AND event_time < '{until.isoformat()}'"

        # Add ordering and limit
        query += " ORDER BY event_time DESC"
        if limit:
            query += f" LIMIT {limit}"

        # Debug: Log the query being executed
        logger.info(f"Executing events query: {query}")
        
        result = await self._run_query_async(query)
        logger.info(f"Events query returned {len(result)} rows")
        return result

    async def get_robot_telemetry(
        self,
        telemetry_time: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch robot telemetry data from pre-computed BigQuery table.

        Args:
            telemetry_time: Hour in format YYYY-MM-DDTHH for MDS compliance

        Returns:
            List of telemetry records (using trip start/end points as minimum viable telemetry)
        """
        # Use the specific robot IDs from the sample query
        default_robots = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        # Build query for pre-computed trips table (using start/end points as telemetry)
        query = f"""
        SELECT
            robot_id,
            trip_id,
            trip_start,
            trip_end,
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
            status
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_TRIPS_PROCESSED}`
        WHERE 1=1
        """

        # Add robot ID filter
        robot_ids_str = "', '".join(default_robots)
        query += f" AND robot_id IN ('{robot_ids_str}')"

        # Add time filter for the specified hour
        try:
            start_time = datetime.strptime(telemetry_time, "%Y-%m-%dT%H")
            end_time = start_time + timedelta(hours=1)
            query += f" AND trip_end >= '{start_time.isoformat()}'"
            query += f" AND trip_end < '{end_time.isoformat()}'"
        except ValueError:
            raise ValueError(f"Invalid telemetry_time format. Expected YYYY-MM-DDTHH, got: {telemetry_time}")

        query += " ORDER BY trip_start ASC"

        return await self._run_query_async(query)

    async def check_data_availability(self, hour: str) -> bool:
        """
        Check if data is available for a given hour.

        Args:
            hour: Hour in format YYYY-MM-DDTHH

        Returns:
            True if data is available, False otherwise
        """
        try:
            start_time = datetime.strptime(hour, "%Y-%m-%dT%H")
            end_time = start_time + timedelta(hours=1)

            # Check if we have any trip data for this hour in the pre-computed table
            query = f"""
            SELECT COUNT(*) as count
            FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_TRIPS_PROCESSED}`
            WHERE trip_end >= '{start_time.isoformat()}'
            AND trip_end < '{end_time.isoformat()}'
            LIMIT 1
            """

            results = await self._run_query_async(query)
            return results[0]['count'] > 0 if results else False

        except ValueError:
            return False
        except Exception as e:
            logger.error(f"Error checking data availability: {str(e)}")
            return False


# Global BigQuery service instance
bigquery_service = BigQueryService()


async def get_all_robots() -> List[Dict[str, Any]]:
    """
    Get all active robots.
    """
    return await bigquery_service.get_active_robot_list()


async def get_robot_by_id(robot_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single robot by its ID.
    """
    # This should return the latest status record for the given robot_id
    query = f"""
    SELECT
        t1.robot_id,
        t1.latitude,
        t1.longitude,
        t1.timestamp,
        t1.accuracy,
        t1.status,
        t1.battery_level,
        t1.last_updated
    FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}` AS t1
    INNER JOIN (
        SELECT robot_id, MAX(last_updated) as max_last_updated
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_PRECOMPUTED}.{settings.BIGQUERY_TABLE_VEHICLES}`
        WHERE robot_id = '{robot_id}'
        GROUP BY robot_id
    ) AS t2 ON t1.robot_id = t2.robot_id AND t1.last_updated = t2.max_last_updated
    WHERE t1.robot_id = '{robot_id}'
    LIMIT 1
    """
    results = await bigquery_service._run_query_async(query)
    return results[0] if results else None
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
        Fetch robot location data from BigQuery.

        Args:
            robot_ids: List of specific robot IDs to filter
            since: Only return locations after this timestamp
            limit: Maximum number of records to return

        Returns:
            List of location records
        """
        # Build base query
        query = f"""
        SELECT
            robot_id,
            date,
            timestamp,
            latitude,
            longitude,
            accuracy
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_LOCATIONS}.{settings.BIGQUERY_TABLE_LOCATIONS}`
        WHERE accuracy > {settings.MIN_LOCATION_ACCURACY}
        """

        # Add robot ID filter
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" AND robot_id IN ('{robot_ids_str}')"

        # Add time filter
        if since:
            query += f" AND timestamp >= '{since.isoformat()}'"
        else:
            # Default to last 30 days for vehicle data
            cutoff_date = datetime.utcnow() - timedelta(days=settings.VEHICLE_RETENTION_DAYS)
            query += f" AND date >= '{cutoff_date.strftime('%Y-%m-%d')}'"

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
        Fetch robot trip data from BigQuery.

        Args:
            robot_ids: List of specific robot IDs to filter
            end_time_hour: Hour in format YYYY-MM-DDTHH for MDS compliance
            since: Only return trips after this timestamp

        Returns:
            List of trip records
        """
        # Use the exact query structure from the sample
        query = f"""
        SELECT 
            robot_id, 
            r.created_at, 
            TIMESTAMP_MILLIS(steps.startedAt) as trip_start, 
            TIMESTAMP_MILLIS(steps.finishedAt) as trip_end, 
            (steps.finishedAt-steps.startedAt)/1000 as trip_duration_seconds, 
            steps.point_data.point_latitude as start_latitude, 
            steps.point_data.point_longitude as start_longitude,
            r.id as job_id,
            steps.step_type,
            steps.step_status,
            r.user_id,
            r.bot_id
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_TRIPS}.{settings.BIGQUERY_TABLE_TRIPS}` r, 
        UNNEST(steps_data) as steps 
        WHERE robot_id IN (
            '4F403',
            '4E006',
            '4E072',
            '4E096',
            '4E103',
            '4E105',
            '4F148',
            '4F175',
            '4F055',
            '4H001',
            '4H002',
            '4H004',
            '4H005',
            '4H011',
            '4H013',
            '4H014',
            '4H015',
            '4H017',
            '4H020'
        ) 
        AND date(r.created_at) > '2025-07-01'
        AND steps.point_data.point_latitude IS NOT NULL
        """

        # Add robot ID filter if specific robots requested
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query = query.replace(
                "WHERE robot_id IN (",
                f"WHERE robot_id IN ('{robot_ids_str}'"
            )

        # Add time filters
        if end_time_hour:
            # Parse hour format and create time range
            try:
                start_time = datetime.strptime(end_time_hour, "%Y-%m-%dT%H")
                end_time = start_time + timedelta(hours=1)
                query += f" AND TIMESTAMP_MILLIS(steps.finishedAt) >= '{start_time.isoformat()}'"
                query += f" AND TIMESTAMP_MILLIS(steps.finishedAt) < '{end_time.isoformat()}'"
            except ValueError:
                raise ValueError(f"Invalid end_time format. Expected YYYY-MM-DDTHH, got: {end_time_hour}")
        elif since:
            query += f" AND r.created_at >= '{since.isoformat()}'"
        else:
            # Default to last 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            query += f" AND date(r.created_at) >= '{cutoff_date.strftime('%Y-%m-%d')}'"

        query += " ORDER BY r.created_at DESC"

        return await self._run_query_async(query)

    async def get_robot_current_status(
        self,
        robot_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get current status of robots (latest location data).

        Args:
            robot_ids: List of specific robot IDs to filter

        Returns:
            List of current robot status records
        """
        # Get latest location for each robot
        query = f"""
        WITH latest_locations AS (
            SELECT
                robot_id,
                latitude,
                longitude,
                timestamp,
                accuracy,
                ROW_NUMBER() OVER (PARTITION BY robot_id ORDER BY timestamp DESC) as rn
            FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_LOCATIONS}.{settings.BIGQUERY_TABLE_LOCATIONS}`
            WHERE accuracy > {settings.MIN_LOCATION_ACCURACY}
            AND date >= '{(datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')}'
        )
        SELECT
            robot_id,
            latitude,
            longitude,
            timestamp,
            accuracy
        FROM latest_locations
        WHERE rn = 1
        """

        # Add robot ID filter
        if robot_ids:
            robot_ids_str = "', '".join(robot_ids)
            query += f" AND robot_id IN ('{robot_ids_str}')"

        query += " ORDER BY timestamp DESC"

        return await self._run_query_async(query)

    async def get_active_robot_list(self) -> List[str]:
        """
        Get list of currently active robot IDs from the specific robot list.

        Returns:
            List of robot IDs that have recent activity
        """
        # Use the specific robot IDs from the sample query
        robot_ids = [
            '4F403', '4E006', '4E072', '4E096', '4E103', '4E105', '4F148', '4F175', '4F055',
            '4H001', '4H002', '4H004', '4H005', '4H011', '4H013', '4H014', '4H015', '4H017', '4H020'
        ]
        
        # Check which robots have recent activity
        cutoff_date = datetime.utcnow() - timedelta(days=settings.VEHICLE_RETENTION_DAYS)
        robot_ids_str = "', '".join(robot_ids)
        
        query = f"""
        SELECT DISTINCT robot_id
        FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_LOCATIONS}.{settings.BIGQUERY_TABLE_LOCATIONS}`
        WHERE robot_id IN ('{robot_ids_str}')
        AND date >= '{cutoff_date.strftime('%Y-%m-%d')}'
        AND accuracy > {settings.MIN_LOCATION_ACCURACY}
        ORDER BY robot_id
        """

        results = await self._run_query_async(query)
        return [row['robot_id'] for row in results]

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

            # Check if we have any trip data for this hour
            query = f"""
            SELECT COUNT(*) as count
            FROM `{settings.BIGQUERY_PROJECT_ID}.{settings.BIGQUERY_DATASET_TRIPS}.{settings.BIGQUERY_TABLE_TRIPS}` r,
            UNNEST(steps_data) as steps
            WHERE TIMESTAMP_MILLIS(steps.finishedAt) >= '{start_time.isoformat()}'
            AND TIMESTAMP_MILLIS(steps.finishedAt) < '{end_time.isoformat()}'
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
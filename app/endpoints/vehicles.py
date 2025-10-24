"""
Vehicle endpoints for MDS Provider API.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse

from app.models.vehicles import VehiclesResponse, VehicleStatusResponse
from app.services.bigquery import bigquery_service
from app.services.transformers import data_transformer
from app.auth.middleware import get_current_provider_id
from app.config import settings, MDSConstants

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status",
    response_model=VehicleStatusResponse,
    summary="Get vehicle status",
    description="Near-realtime endpoint returning current status of vehicles in the jurisdiction."
)
@router.get(
    "/status/{device_id}",
    response_model=VehicleStatusResponse,
    summary="Get specific vehicle status",
    description="Returns current status for a specific vehicle by device_id."
)
async def get_vehicle_status(
    request: Request,
    device_id: Optional[UUID] = None
):
    """
    Get vehicle status information.

    This is a near-realtime endpoint that returns current status of vehicles.
    All vehicles in any PROW state should be returned.
    """
    try:
        # Authenticate request
        provider_id = get_current_provider_id(request)

        # Get robot IDs to query
        robot_ids = None
        if device_id:
            # Convert device_id back to robot_id
            active_robots = await bigquery_service.get_active_robot_list()
            target_robot_id = None
            for robot_id in active_robots:
                if data_transformer.robot_id_to_device_id(robot_id) == device_id:
                    target_robot_id = robot_id
                    break

            if not target_robot_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "vehicle_not_found", "error_details": f"Vehicle {device_id} not found"}
                )

            robot_ids = [target_robot_id]

        # Get current robot status data
        location_data = await bigquery_service.get_robot_current_status(robot_ids)

        if not location_data:
            # Return empty response if no current data
            current_time = int(datetime.utcnow().timestamp() * 1000)
            return VehicleStatusResponse(
                vehicles_status=[],
                last_updated=current_time,
                ttl=settings.CACHE_TTL_VEHICLES * 1000  # Convert to milliseconds
            )

        # Transform to vehicle status objects
        vehicle_statuses = data_transformer.batch_transform_vehicle_status(location_data)

        # Calculate timestamps
        current_time = int(datetime.utcnow().timestamp() * 1000)
        ttl = settings.CACHE_TTL_VEHICLES * 1000  # Convert to milliseconds

        logger.info(f"Returning status for {len(vehicle_statuses)} vehicles for provider {provider_id}")

        return VehicleStatusResponse(
            vehicles_status=vehicle_statuses,
            last_updated=current_time,
            ttl=ttl,
            links={"self": "/vehicles/status"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vehicle_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "internal_error", "error_details": str(e)}
        )


@router.get(
    "/",
    response_model=VehiclesResponse,
    summary="Get vehicle information",
    description="Returns vehicle information for delivery robots. Contains rarely-changed vehicle properties."
)
@router.get(
    "/{device_id}",
    response_model=VehiclesResponse,
    summary="Get specific vehicle information",
    description="Returns information for a specific vehicle by device_id."
)
async def get_vehicles(
    request: Request,
    device_id: Optional[UUID] = None
):
    """
    Get vehicle information.

    This endpoint returns vehicle properties that do not change often.
    When called without device_id, returns all vehicles deployed in the last 30 days.
    """
    try:
        # Authenticate request
        provider_id = get_current_provider_id(request)

        # Get active robot list
        active_robots = await bigquery_service.get_active_robot_list()

        if not active_robots:
            # Return empty response if no active robots
            current_time = int(datetime.utcnow().timestamp() * 1000)
            return VehiclesResponse(
                vehicles=[],
                last_updated=current_time,
                ttl=settings.CACHE_TTL_VEHICLES * 1000
            )

        # If specific device_id requested, filter to that robot
        if device_id:
            # Convert device_id back to robot_id for filtering
            target_robot_id = None
            for robot_id in active_robots:
                if data_transformer.robot_id_to_device_id(robot_id) == device_id:
                    target_robot_id = robot_id
                    break

            if not target_robot_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "vehicle_not_found", "error_details": f"Vehicle {device_id} not found"}
                )

            active_robots = [target_robot_id]

        # Transform robot IDs to vehicle data
        # For now, create vehicle objects from robot IDs
        # In production, this would fetch actual vehicle metadata
        vehicles = []
        for robot_id in active_robots:
            robot_data = {"robot_id": robot_id}
            vehicle = data_transformer.transform_robot_to_vehicle(robot_data)
            vehicles.append(vehicle)

        # Calculate timestamps
        current_time = int(datetime.utcnow().timestamp() * 1000)
        ttl = settings.CACHE_TTL_VEHICLES * 1000  # Convert to milliseconds

        logger.info(f"Returning {len(vehicles)} vehicles for provider {provider_id}")

        return VehiclesResponse(
            vehicles=vehicles,
            last_updated=current_time,
            ttl=ttl,
            links=[{"rel": "self", "href": "/vehicles/"}]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_vehicles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "internal_error", "error_details": str(e)}
        )
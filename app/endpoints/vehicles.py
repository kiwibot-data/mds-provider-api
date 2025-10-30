"""
Vehicle endpoints for MDS Provider API.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.services.bigquery import get_all_robots, get_robot_by_id
from app.services.transformers import transform_robot_to_vehicle, transform_robot_to_vehicle_status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    summary="Get all vehicles",
    description="Returns a list of all vehicles, including their properties and current status.",
    tags=["Vehicles"],
)
async def get_vehicles(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    vehicle_id: Optional[str] = None,
    status: Optional[str] = None,
    is_reserved: Optional[bool] = None,
    is_disabled: Optional[bool] = None,
    vehicle_type: Optional[str] = None,
    propulsion_type: Optional[str] = None,
    provider_id: Optional[str] = None,
):
    """
    Get all vehicles.
    """
    robots = await get_all_robots()
    vehicles = [transform_robot_to_vehicle(robot) for robot in robots]

    response_payload = {
        "version": settings.MDS_VERSION,
        "last_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ttl": 3600,
        "vehicles": vehicles,
    }
    logger.info(f"Response for /vehicles: {response_payload}")
    return JSONResponse(content=jsonable_encoder(response_payload))


@router.get(
    "/status",
    summary="Get the status of all vehicles",
    description="Returns a list of all vehicles with their current status, including location and battery level.",
    tags=["Vehicles"],
)
async def get_all_vehicle_statuses(
    request: Request,
    skip: int = 0,
    limit: int = 100,
):
    """
    Get the status of all vehicles.
    """
    robots = await get_all_robots()
    vehicle_statuses = [transform_robot_to_vehicle_status(robot) for robot in robots]

    response_payload = {
        "version": settings.MDS_VERSION,
        "last_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ttl": 60,
        "vehicles_status": vehicle_statuses,
        "links": {
            "first": str(request.url.include_query_params(skip=0, limit=limit)),
            "last": str(request.url.include_query_params(skip=0, limit=limit)),
            "prev": str(request.url.include_query_params(skip=max(0, skip - limit), limit=limit)),
            "next": str(request.url.include_query_params(skip=skip + limit, limit=limit)),
        },
    }
    logger.info(f"Response for /vehicles/status: {response_payload}")
    return JSONResponse(content=jsonable_encoder(response_payload))


@router.get(
    "/{vehicle_id}",
    summary="Get a specific vehicle",
    description="Returns the properties of a single vehicle, identified by its ID.",
    tags=["Vehicles"],
)
async def get_vehicle_by_id(
    request: Request,
    vehicle_id: str,
):
    """
    Get a specific vehicle by its ID.
    """
    robot = await get_robot_by_id(vehicle_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle = transform_robot_to_vehicle(robot)
    
    response_payload = {
        "version": settings.MDS_VERSION,
        "last_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ttl": 3600,
        "vehicles": [vehicle],
    }
    logger.info(f"Response for /vehicles/{vehicle_id}: {response_payload}")
    return JSONResponse(content=jsonable_encoder(response_payload))


@router.get(
    "/{vehicle_id}/status",
    summary="Get the status of a specific vehicle",
    description="Returns the current status of a single vehicle, identified by its ID.",
    tags=["Vehicles"],
)
async def get_vehicle_status_by_id(
    request: Request,
    vehicle_id: str,
):
    """
    Get the status of a specific vehicle by its robot_id.
    """
    robot = await get_robot_by_id(vehicle_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle_status = transform_robot_to_vehicle_status(robot)

    response_payload = {
        "version": settings.MDS_VERSION,
        "last_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ttl": 60,
        "vehicles_status": [vehicle_status],
    }
    logger.info(f"Response for /vehicles/{vehicle_id}/status: {response_payload}")
    return JSONResponse(content=jsonable_encoder(response_payload))
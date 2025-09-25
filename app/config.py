"""
Configuration settings for MDS Provider API.
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    # Auth0 Configuration (from IT)
    AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN", "kiwibot.auth0.com")
    AUTH0_AUDIENCE: str = os.getenv("AUTH0_AUDIENCE", "https://mds.kiwibot.com")
    
    # Cloud Run Configuration
    PORT: int = int(os.getenv("PORT", "8000"))

    
    # MDS Configuration
    MDS_VERSION: str = "2.0.0"
    PROVIDER_ID: str = os.getenv("MDS_PROVIDER_ID", "kiwibot-delivery-robots")
    PROVIDER_NAME: str = "Kiwibot Delivery Robots"
    API_BASE_URL: str = os.getenv("API_BASE_URL", "https://mds.kiwibot.com")

    # Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "RS256"

    # BigQuery Configuration
    BIGQUERY_PROJECT_ID: str = os.getenv("BIGQUERY_PROJECT_ID", "kiwibot-atlas")
    BIGQUERY_DATASET_LOCATIONS: str = "bot_analytics"
    BIGQUERY_DATASET_TRIPS: str = "remi"
    BIGQUERY_TABLE_LOCATIONS: str = "robot_location"
    BIGQUERY_TABLE_TRIPS: str = "jobs_processed"

    # Google Cloud Configuration
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "kiwibot-atlas")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    # API Configuration
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
    API_PREFIX: str = "/v1/provider"

    # Cache Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL_VEHICLES: int = 60  # seconds
    CACHE_TTL_TRIPS: int = 3600   # seconds
    CACHE_TTL_EVENTS: int = 300   # seconds

    # Data Filtering
    MIN_LOCATION_ACCURACY: float = 0.7
    VEHICLE_RETENTION_DAYS: int = 30
    EVENT_RETENTION_DAYS: int = 14

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Development
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# MDS-specific constants
class MDSConstants:
    """MDS specification constants."""

    # Content Types
    CONTENT_TYPE_JSON = f"application/vnd.mds+json;version={settings.MDS_VERSION}"
    CONTENT_TYPE_CSV = f"text/vnd.mds+csv;version={settings.MDS_VERSION}"

    # Vehicle States for Delivery Robots
    VEHICLE_STATES = [
        "removed",
        "available",
        "non_operational",
        "reserved",
        "on_trip",
        "stopped",
        "non_contactable",
        "missing",
        "elsewhere"
    ]

    # Event Types for Delivery Robots
    EVENT_TYPES = [
        "comms_lost",
        "comms_restored",
        "compliance_pick_up",
        "decommissioned",
        "not_located",
        "located",
        "maintenance",
        "maintenance_pick_up",
        "maintenance_end",
        "driver_cancellation",
        "order_drop_off",
        "order_pick_up",
        "customer_cancellation",
        "provider_cancellation",
        "recommission",
        "reservation_start",
        "reservation_stop",
        "service_end",
        "service_start",
        "trip_end",
        "trip_enter_jurisdiction",
        "trip_leave_jurisdiction",
        "trip_resume",
        "trip_start",
        "trip_pause"
    ]

    # Trip Types for Delivery Robots
    TRIP_TYPES = [
        "delivery",
        "return",
        "advertising",
        "mapping",
        "roaming"
    ]

    # Driver Types
    DRIVER_TYPES = [
        "human",
        "semi_autonomous",
        "autonomous"
    ]

    # Vehicle Types for Delivery Robots
    VEHICLE_TYPE = "robot"

    # Propulsion Types
    PROPULSION_TYPES = [
        "electric"
    ]
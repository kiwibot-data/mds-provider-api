# MDS Provider API - Kiwibot

A production-ready implementation of the Mobility Data Specification (MDS) 2.0.0 Provider API for autonomous delivery robot services from Kiwibot.

## Overview

This API implements the MDS Provider specification for delivery robots, providing standardized endpoints for:
- **Vehicle Information** (`/vehicles`) - Static vehicle properties and metadata
- **Vehicle Status** (`/vehicles/status`) - Near-realtime vehicle location and state data
- **Trip Data** (`/trips`) - Historical delivery trip information by hour
- **Telemetry** (`/telemetry`) - GPS trajectory data for vehicle movements
- **Events** (`/events`) - Vehicle state change events and operational data

**Live Deployment:** https://mds-provider-api-862961741611.us-central1.run.app

## Features

- **MDS 2.0.0 Compliant**: Full compliance with MDS 2.0.0 specification for delivery robots
- **Dual Authentication**: JWT (Auth0) and API Key authentication support
- **BigQuery Integration**: Direct integration with Google BigQuery for data retrieval
- **Async Performance**: Built with FastAPI and async/await for high performance
- **Production Ready**: Comprehensive error handling, logging, and monitoring
- **Cloud Run Deployment**: Automated deployment to Google Cloud Run
- **Docker Support**: Complete containerization with optimized Docker images
- **Comprehensive Testing**: Full test suite with pytest and coverage reports
- **Type Safety**: Full type hints with Pydantic models and validation

## Architecture

```
mds-provider-api/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and settings
│   ├── auth/                # JWT authentication
│   ├── endpoints/           # API endpoint implementations
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic and data services
│   └── utils/               # Utility functions
├── tests/                   # Comprehensive test suite
├── docker/                  # Docker configuration
└── docs/                    # API documentation
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Google Cloud credentials with BigQuery access
- Auth0 account for authentication

### Installation

1. **Clone and set up the project:**
```bash
cd mds-provider-api
cp .env.example .env
# Edit .env with your configuration
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up Google Cloud credentials:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

4. **Run the application:**
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker Deployment

1. **Build and run with Docker Compose:**
```bash
docker-compose up -d
```

2. **Check service health:**
```bash
curl http://localhost:8000/health
```

### Google Cloud Run Deployment

The project includes a `cloudbuild.yaml` configuration for automated deployment to Google Cloud Run:

1. **Deploy using Cloud Build:**
```bash
gcloud builds submit --config cloudbuild.yaml
```

2. **Manual deployment steps:**
   - Builds Docker image tagged with your project ID
   - Pushes image to Google Container Registry
   - Deploys to Cloud Run in `us-central1` region
   - Configures service to run on port 8000 with public access

3. **Service configuration:**
   - **Platform**: Google Cloud Run (managed)
   - **Region**: us-central1
   - **Port**: 8000
   - **Access**: Public (unauthenticated)
   - **Auto-scaling**: Enabled

The deployment automatically handles containerization, registry management, and service provisioning.

## API Endpoints

### Authentication

All endpoints support two authentication methods:

**1. API Key Authentication (Recommended for partners):**
```bash
X-API-Key: your-api-key
```

**2. JWT Bearer Token (Auth0):**
```bash
Authorization: Bearer <jwt-token>
```

The JWT token must contain a `provider_id` claim matching your configured provider ID.

### Core Endpoints

#### Vehicles
- `GET /vehicles` - List all vehicles with static properties
  - Returns: Array of vehicles with `last_updated` and `ttl`
  - Response includes `vehicle_id`, `device_id`, `vehicle_type`, `propulsion_types`
  
- `GET /vehicles/{device_id}` - Get specific vehicle by device ID
  - Parameters: `device_id` (UUID, required)
  
- `GET /vehicles/status` - Current vehicle status (near-realtime)
  - Returns: Array of vehicles with current state and location
  - Includes `last_updated` and `ttl` fields for cache control
  
- `GET /vehicles/status/{device_id}` - Specific vehicle status
  - Parameters: `device_id` (UUID, required)

#### Trips
- `GET /trips?end_time=YYYY-MM-DDTHH` - Historical trip data by hour
  - Parameters: 
    - `end_time` (string, required) - Hour to query in format `YYYY-MM-DDTHH`
  - Returns: Array of trips completed during the specified hour
  - Response includes `start_location` and `end_location` as GeoJSON Points
  - Status codes:
    - `200 OK` - Data available
    - `202 Accepted` - Data still processing
    - `400 Bad Request` - Invalid parameters
    - `404 Not Found` - Future time or no operations

#### Telemetry
- `GET /telemetry?telemetry_time=YYYY-MM-DDTHH` - GPS trajectory data
  - Parameters:
    - `telemetry_time` (string, required) - Hour to query in format `YYYY-MM-DDTHH`
  - Returns: Array of GPS points for all trips during the specified hour
  - Includes all telemetry points for trips that intersect jurisdiction
  - Coordinates rounded to appropriate GPS accuracy (5-6 decimal places)
  - Status codes:
    - `200 OK` - Data available (may be empty array)
    - `400 Bad Request` - Invalid or missing parameter
    - `404 Not Found` - Future time or no operations

#### Events
- `GET /events/historical?event_time=YYYY-MM-DDTHH` - Historical events by hour
  - Parameters:
    - `event_time` (string, required) - Hour to query in format `YYYY-MM-DDTHH`
  - Returns: Array of state change events during the specified hour
  - Each event includes `event_id`, `timestamp`, `event_types`, `vehicle_state`
  
- `GET /events/recent?start_time=<ms>&end_time=<ms>` - Recent events
  - Parameters:
    - `start_time` (integer, required) - Start timestamp in milliseconds
    - `end_time` (integer, required) - End timestamp in milliseconds
  - Returns: Events within the last 2 weeks only
  - Time range cannot exceed 2 weeks in the past

#### Health & Debug
- `GET /health` - Health check endpoint
  - Returns: API status, version, and configuration info
  - Public endpoint (no authentication required)
  
- `GET /test-auth` - Test authentication status
  - Returns: Current authentication details
  - Useful for debugging API key or JWT issues

### Response Format

All responses follow MDS 2.0.0 specification with Content-Type: `application/vnd.mds+json;version=2.0.0`

**Standard MDS Response:**
```json
{
  "version": "2.0.0",
  "trips": [...],
  "telemetry": [...],
  "events": [...],
  "vehicles": [...]
}
```

**Near-realtime Response (vehicles/status):**
```json
{
  "version": "2.0.0",
  "vehicles": [...],
  "last_updated": 1760622668103,
  "ttl": 60000
}
```

**Error Response:**
```json
{
  "error": "invalid_end_time",
  "error_description": "Invalid end_time format. Expected YYYY-MM-DDTHH",
  "error_details": "Invalid end_time format. Expected YYYY-MM-DDTHH, got: invalid"
}
```

### Example Requests

**Get trips for a specific hour:**
```bash
curl -H "X-API-Key: your-api-key" \
  "https://mds-provider-api-862961741611.us-central1.run.app/trips?end_time=2025-09-25T15"
```

**Get telemetry data:**
```bash
curl -H "X-API-Key: your-api-key" \
  "https://mds-provider-api-862961741611.us-central1.run.app/telemetry?telemetry_time=2025-09-25T15"
```

**Get vehicle status:**
```bash
curl -H "X-API-Key: your-api-key" \
  "https://mds-provider-api-862961741611.us-central1.run.app/vehicles/status"
```

**Get historical events:**
```bash
curl -H "X-API-Key: your-api-key" \
  "https://mds-provider-api-862961741611.us-central1.run.app/events/historical?event_time=2025-09-25T15"
```

## Configuration

Key configuration options in `.env`:

```bash
# Provider Configuration
MDS_PROVIDER_ID=kiwibot-delivery-robots
MDS_VERSION=2.0.0
DEBUG=false

# Authentication (Auth0)
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_AUDIENCE=your-api-audience
JWT_ALGORITHM=RS256

# Authentication (API Keys)
API_KEY_WASHINGTON_DDOT=key:provider:permissions

# BigQuery
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET=bot_analytics
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# API Configuration
API_BASE_URL=https://your-api-url.com
CORS_ORIGINS=*
LOG_LEVEL=INFO

# Performance
CACHE_TTL_VEHICLES=60
MIN_LOCATION_ACCURACY=0.7
```

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `MDS_PROVIDER_ID` | Yes | Provider identifier string | `kiwibot-delivery-robots` |
| `MDS_VERSION` | Yes | MDS specification version | `2.0.0` |
| `AUTH0_DOMAIN` | Yes* | Auth0 domain for JWT | `kiwibot.auth0.com` |
| `AUTH0_AUDIENCE` | Yes* | JWT audience identifier | `https://mds.kiwibot.com` |
| `API_KEY_*` | Yes** | API key configuration | `key:provider:permissions` |
| `BIGQUERY_PROJECT_ID` | Yes | GCP project ID | `kiwibot-atlas` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Service account path | `/path/to/sa.json` |
| `DEBUG` | No | Enable debug mode | `false` |

\* Required for JWT authentication  
\*\* At least one API key or Auth0 configuration required

## Data Sources

The API integrates with the following BigQuery datasets:

### Primary Data Tables

1. **Robot Locations** (`bot_analytics.robot_location`)
   - Real-time robot GPS position data
   - GPS accuracy filtering (configurable threshold)
   - Used for: Vehicle status, events, telemetry
   - Fields: `robot_id`, `latitude`, `longitude`, `accuracy`, `timestamp`

2. **Trips Processed** (`bot_analytics.trips_processed`)
   - Pre-computed trip data with start/end locations
   - Aggregated delivery trip information
   - Used for: Trip history, telemetry points
   - Fields: `robot_id`, `trip_start`, `trip_end`, `start_latitude`, `start_longitude`, `end_latitude`, `end_longitude`

3. **Jobs Processed** (`remi.jobs_processed`)
   - Detailed delivery job and step information
   - Complete route and timing data
   - Used for: Historical trip details, event generation
   - Fields: `job_id`, `robot_id`, `step_type`, `step_start`, `step_end`, `location`

### Pre-computed Tables (SQL)

The API uses pre-computed aggregation tables for performance:

- **`trips_processed`** - Hourly trip aggregations
  - Created by: `sql/create_precomputed_tables.sql`
  - Refreshed by: `sql/refresh_precomputed_tables.sql`
  - Improves `/trips` and `/telemetry` endpoint performance
  - Aggregates trip data by hour for faster querying

### Data Pipeline

```
robot_location (raw) → trips_processed (aggregated) → MDS API Response
jobs_processed (raw) → transformers → MDS API Response
```

## Robot Data Mapping

The API transforms robot-specific data to MDS-compliant format:

| Robot Data | MDS Field | Type | Description |
|------------|-----------|------|-------------|
| `robot_id` | `device_id` | UUID | UUID v5 generated from robot ID using DNS namespace |
| `robot_id` | `vehicle_id` | UUID | Same as `device_id` (MDS 2.0 requirement) |
| `provider_id` (string) | `provider_id` | UUID | UUID v5 generated from provider string |
| Robot location | `current_location` | GeoJSON Point | GPS coordinates as GeoJSON Feature |
| Job data | `trip_id` | UUID | UUID v5 generated from job ID |
| Step timing | `start_time`/`end_time` | Integer | Unix timestamps in milliseconds |
| Location data | `start_location`/`end_location` | GeoJSON Point | Trip start/end as GeoJSON Features |
| State changes | `event_id` | UUID | UUID v5 generated from event data |
| GPS points | `telemetry` | Array | GPS trajectory with timestamps |

### UUID Generation

All UUIDs are generated using UUID v5 with DNS namespace for consistency:

```python
device_id = uuid5(NAMESPACE_DNS, f"{provider_id}.device.{robot_id}")
trip_id = uuid5(NAMESPACE_DNS, f"{provider_id}.trip.{job_id}.{step_id}")
event_id = uuid5(NAMESPACE_DNS, f"{provider_id}.event.{robot_id}.{timestamp}.{event_type}")
provider_id_uuid = uuid5(NAMESPACE_DNS, provider_id_string)
```

## Vehicle States

The API supports these delivery robot states:
- `available` - Ready for delivery assignment
- `reserved` - Reserved for incoming order
- `on_trip` - Currently executing delivery
- `stopped` - Paused during delivery
- `non_operational` - Out of service
- `non_contactable` - Communication lost
- `missing` - Robot not located
- `elsewhere` - Outside jurisdiction
- `removed` - Decommissioned

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/test_vehicles.py -v
pytest tests/test_auth.py -v
```

## Development

### Code Quality

The project uses several tools for code quality:

```bash
# Code formatting
black app/ tests/
isort app/ tests/

# Linting
flake8 app/ tests/

# Type checking
mypy app/
```

### Adding New Endpoints

1. Create Pydantic models in `app/models/`
2. Implement business logic in `app/services/`
3. Add endpoint in `app/endpoints/`
4. Include router in `app/main.py`
5. Add comprehensive tests

## Deployment

### Production Considerations

1. **Security**:
   - Use proper JWT signing keys
   - Configure CORS origins appropriately
   - Enable HTTPS with SSL certificates

2. **Performance**:
   - Configure Redis for caching
   - Set appropriate cache TTL values
   - Monitor BigQuery usage and costs

3. **Monitoring**:
   - Set up health checks
   - Monitor response times and error rates
   - Configure logging and alerting

### Environment Variables

Required production environment variables:
- `MDS_PROVIDER_ID` - Your official MDS provider ID
- `AUTH0_DOMAIN` - Auth0 authentication domain
- `AUTH0_AUDIENCE` - API audience identifier
- `BIGQUERY_PROJECT_ID` - Google Cloud project ID
- `GOOGLE_APPLICATION_CREDENTIALS` - Service account credentials path

## MDS 2.0.0 Compliance

This implementation is fully compliant with MDS 2.0.0 specification:

### Compliance Checklist

- ✅ **Version Field**: All responses include `version: "2.0.0"`
- ✅ **UUID Format**: All IDs (`provider_id`, `device_id`, `trip_id`, `event_id`) are UUIDs
- ✅ **Field Naming**: Correct field names (`duration` not `trip_duration`, `timestamp` not `event_time`)
- ✅ **GeoJSON**: Proper GeoJSON Point structures for locations
- ✅ **Vehicle Type**: Uses `delivery_robot` as vehicle type
- ✅ **Trips Structure**: Includes `start_location` and `end_location` (not `route`)
- ✅ **Telemetry Endpoint**: Fully implemented with GPS trajectory data
- ✅ **Near-realtime Fields**: `last_updated` and `ttl` on `/vehicles/status`
- ✅ **Event IDs**: All events have unique `event_id` UUIDs
- ✅ **Error Handling**: Proper HTTP status codes and error messages
- ✅ **Required Parameters**: All required query parameters enforced
- ✅ **Time Format**: Consistent use of millisecond timestamps

### Key Changes from MDS 1.0

1. **Field Renamings**:
   - `trip_duration` → `duration`
   - `trip_distance` → `distance` 
   - `event_time` → `timestamp`
   - `vehicle_type: "robot"` → `vehicle_type: "delivery_robot"`

2. **Structural Changes**:
   - Trip `route` field removed, replaced with `start_location` and `end_location`
   - `vehicle_id` field added (same as `device_id`)
   - All ID fields are now UUIDs instead of strings
   - `accessibility_attributes` is now an array

3. **New Requirements**:
   - `/telemetry` endpoint added for GPS trajectories
   - `event_id` UUID required on all events
   - `last_updated` and `ttl` required on near-realtime endpoints
   - Hourly time parameter format: `YYYY-MM-DDTHH`

### Validation

The API has been tested against MDS 2.0.0 requirements and is ready for partner validation. See `DEPLOYMENT_SUCCESS_REPORT.md` for full test results.

## Testing & Verification

### Running Tests

The project includes comprehensive test scripts:

```bash
# Test deployed API
./test_deployed_api.sh

# Run comprehensive test suite
./final_comprehensive_test.sh

# Test specific endpoints
curl -H "X-API-Key: your-key" \
  "https://mds-provider-api-862961741611.us-central1.run.app/health"
```

### Test Coverage

- ✅ All MDS 2.0.0 endpoints
- ✅ Authentication (JWT and API Key)
- ✅ Error handling and validation
- ✅ Required parameters
- ✅ Response format compliance
- ✅ Edge cases (empty results, invalid inputs)

### Verification Results

See `DEPLOYMENT_SUCCESS_REPORT.md` for complete test results and compliance verification.

## Documentation

- **Live API Docs**: https://mds-provider-api-862961741611.us-central1.run.app/docs (OpenAPI/Swagger)
- **ReDoc**: https://mds-provider-api-862961741611.us-central1.run.app/redoc
- **MDS Specification**: [MDS 2.0.0 on GitHub](https://github.com/openmobilityfoundation/mobility-data-specification/tree/2.0.0)
- **Washington DDOT Guide**: See `WASHINGTON_DDOT_API_GUIDE.md`
- **Deployment Report**: See `DEPLOYMENT_SUCCESS_REPORT.md`

## Support

For questions or issues:

1. **API Documentation**: Check interactive docs at `/docs` endpoint
2. **Test Scripts**: Review test cases in `test_deployed_api.sh` for usage examples
3. **MDS Specification**: Consult official spec at [OpenMobilityFoundation](https://github.com/openmobilityfoundation/mobility-data-specification)
4. **Deployment Issues**: See `DEPLOYMENT_SUCCESS_REPORT.md` for troubleshooting

## Project Status

**Current Status**: ✅ **Production Ready**

- **Deployment**: Live on Google Cloud Run
- **MDS Version**: 2.0.0
- **Compliance**: Fully compliant with MDS 2.0.0 specification
- **Testing**: All endpoints verified and operational
- **Documentation**: Complete with examples and guides

## License

This project follows the same license as the MDS specification.
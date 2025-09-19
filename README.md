# MDS Provider API - Kiwibot

A production-ready implementation of the Mobility Data Specification (MDS) 2.0+ Provider API for autonomous delivery robot services from Kiwibot.

## Overview

This API implements the MDS Provider specification for delivery robots, providing standardized endpoints for:
- **Vehicle Information** (`/vehicles`) - Static vehicle properties and metadata
- **Vehicle Status** (`/vehicles/status`) - Real-time vehicle location and state data
- **Trip Data** (`/trips`) - Historical delivery trip information
- **Events** (`/events`) - Vehicle state change events and operational data

## Features

- **MDS 2.0+ Compliant**: Full compliance with latest MDS specification for delivery robots
- **JWT Authentication**: Secure bearer token authentication with Auth0 integration
- **BigQuery Integration**: Direct integration with Google BigQuery for data retrieval
- **Async Performance**: Built with FastAPI and async/await for high performance
- **Production Ready**: Comprehensive error handling, logging, and monitoring
- **Docker Support**: Complete containerization with Docker and docker-compose
- **Comprehensive Testing**: Full test suite with pytest and test coverage
- **Type Safety**: Full type hints with Pydantic models

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

All endpoints require JWT bearer token authentication:
```bash
Authorization: Bearer <jwt-token>
```

The JWT token must contain a `provider_id` claim matching your configured provider ID.

### Core Endpoints

#### Vehicles
- `GET /vehicles` - List all vehicles
- `GET /vehicles/{device_id}` - Get specific vehicle
- `GET /vehicles/status` - Current vehicle status (real-time)
- `GET /vehicles/status/{device_id}` - Specific vehicle status

#### Trips
- `GET /trips?end_time=YYYY-MM-DDTHH` - Historical trip data

#### Events
- `GET /events/historical?event_time=YYYY-MM-DDTHH` - Historical events
- `GET /events/recent?start_time=<ms>&end_time=<ms>` - Recent events

### Response Format

All responses follow MDS specification with Content-Type: `application/vnd.mds+json;version=2.0`

Example response:
```json
{
  "version": "2.0.0",
  "vehicles": [...],
  "last_updated": 1640995200000,
  "ttl": 60000
}
```

## Configuration

Key configuration options in `.env`:

```bash
# Provider Configuration
MDS_PROVIDER_ID=kiwibot-delivery-robots
MDS_VERSION=2.0.0

# Authentication
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_AUDIENCE=your-api-audience

# BigQuery
BIGQUERY_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Performance
CACHE_TTL_VEHICLES=60
MIN_LOCATION_ACCURACY=0.7
```

## Data Sources

The API integrates with the following BigQuery datasets:

1. **Robot Locations** (`bot_analytics.robot_location`)
   - Real-time robot position data
   - GPS accuracy filtering
   - Used for vehicle status and events

2. **Trip Data** (`remi.jobs_processed`)
   - Delivery job and step information
   - Route and timing data
   - Used for historical trip reporting

## Robot Data Mapping

The API transforms robot-specific data to MDS-compliant format:

| Robot Data | MDS Field | Description |
|------------|-----------|-------------|
| `robot_id` | `device_id` | UUID generated from robot ID |
| Robot location | `current_location` | GeoJSON Point geometry |
| Job data | `trip_id` | UUID generated from job ID |
| Step timing | `start_time`/`end_time` | Millisecond timestamps |

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

## Migration from Legacy Implementation

This implementation improves upon the legacy MDS 1.0 API with:

1. **MDS 2.0+ Compliance**: Updated to latest specification
2. **Better Authentication**: Proper JWT validation with Auth0
3. **Improved Data Models**: Type-safe Pydantic models
4. **Enhanced Error Handling**: Comprehensive error responses
5. **Production Ready**: Docker support and monitoring

### Migration Steps

1. Update provider registration with new MDS version
2. Configure new authentication system
3. Update client applications to use new endpoints
4. Test with MDS validation tools

## Support

For questions or issues:
1. Check the API documentation at `/docs`
2. Review test cases for usage examples
3. Consult MDS specification at [OpenMobilityFoundation](https://github.com/openmobilityfoundation/mobility-data-specification)

## License

This project follows the same license as the MDS specification.
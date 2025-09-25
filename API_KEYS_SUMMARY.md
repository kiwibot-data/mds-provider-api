# MDS Provider API - API Keys Summary

## Generated API Keys

### 1. Test Keys (Development)
- **Key**: `mds_test_key_12345`
- **Provider**: `test-provider-1`
- **Purpose**: Development and testing

- **Key**: `mds_demo_key_67890`
- **Provider**: `test-provider-2`
- **Purpose**: Demo and testing

### 2. Washington DDOT (Production)
- **Key**: `mds_washington_ddot_2024`
- **Provider**: `washingtonddot`
- **Purpose**: Official integration with Washington DDOT
- **Documentation**: `WASHINGTON_DDOT_API_GUIDE.md`

## API Endpoint Summary

**Base URL**: `https://mds-provider-api-862961741611.us-central1.run.app`

### Public Endpoints (No Authentication Required)
- `GET /` - API information
- `GET /health` - Health check
- `GET /docs` - Swagger documentation
- `GET /redoc` - ReDoc documentation

### Protected Endpoints (Authentication Required)
- `GET /vehicles/` - Get all vehicles
- `GET /vehicles/{device_id}` - Get specific vehicle
- `GET /vehicles/status/` - Get vehicle status
- `GET /vehicles/status/{device_id}` - Get specific vehicle status
- `GET /trips?end_time=YYYY-MM-DDTHH` - Get historical trips
- `GET /events/historical?event_time=YYYY-MM-DDTHH` - Get historical events
- `GET /events/recent?start_time={timestamp}&end_time={timestamp}` - Get recent events

## Authentication

All protected endpoints require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key-here" \
     https://mds-provider-api-862961741611.us-central1.run.app/vehicles/
```

## Rate Limits

- **Requests**: 100 requests per minute per API key
- **Data Retention**: 
  - Vehicles: 30 days
  - Trips: Historical data available
  - Events: 14 days for recent events

## Security Notes

- API keys are environment-specific
- Each key is associated with a specific provider
- Keys can be revoked independently
- All requests must use HTTPS

## Support

For technical support or additional API keys, contact the MDS Provider API team.

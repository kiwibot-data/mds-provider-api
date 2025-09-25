# MDS Provider API - Third Party Access Guide

This document explains how third parties can access the MDS Provider API for delivery robot data.

## Authentication Methods

The API supports two authentication methods:

### 1. API Key Authentication (Recommended for Third Parties)

Use the `X-API-Key` header with your API key:

```bash
curl -H "X-API-Key: your-api-key-here" \
     https://mds.kiwibot.com/vehicles/
```

### 2. JWT Authentication (Auth0)

Use the `Authorization` header with a Bearer token:

```bash
curl -H "Authorization: Bearer your-jwt-token-here" \
     https://mds.kiwibot.com/vehicles/
```

## Getting API Keys

To get an API key, contact the API administrator or use the admin endpoints if you have access:

1. **Create API Key**: `POST /admin/api-keys`
2. **List API Keys**: `GET /admin/api-keys`
3. **Revoke API Key**: `DELETE /admin/api-keys/{key_preview}`

## Available Endpoints

### Vehicles
- `GET /vehicles/` - Get all vehicles
- `GET /vehicles/{device_id}` - Get specific vehicle
- `GET /vehicles/status/` - Get vehicle status
- `GET /vehicles/status/{device_id}` - Get specific vehicle status

### Trips
- `GET /trips?end_time=YYYY-MM-DDTHH` - Get historical trips

### Events
- `GET /events/historical?event_time=YYYY-MM-DDTHH` - Get historical events
- `GET /events/recent?start_time={timestamp}&end_time={timestamp}` - Get recent events

## Example Usage

### Get All Vehicles
```bash
curl -H "X-API-Key: your-api-key-here" \
     https://mds.kiwibot.com/vehicles/
```

### Get Vehicle Status
```bash
curl -H "X-API-Key: your-api-key-here" \
     https://mds.kiwibot.com/vehicles/status/
```

### Get Historical Trips
```bash
curl -H "X-API-Key: your-api-key-here" \
     "https://mds.kiwibot.com/trips?end_time=2024-01-15T14"
```

### Get Recent Events
```bash
curl -H "X-API-Key: your-api-key-here" \
     "https://mds.kiwibot.com/events/recent?start_time=1705334400000&end_time=1705338000000"
```

## Response Format

All responses follow the MDS 2.0 specification and include:

- **Content-Type**: `application/vnd.mds+json;version=2.0.0`
- **Error Format**: Standard MDS error responses
- **Data Format**: GeoJSON for locations, standard MDS objects for vehicles/trips/events

## Rate Limits

- **Requests**: 100 requests per minute
- **Data Retention**: 
  - Vehicles: 30 days
  - Trips: Historical data available
  - Events: 14 days for recent events

## Error Handling

The API returns standard HTTP status codes:

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API key)
- `404` - Not Found (no data for requested time/vehicle)
- `500` - Internal Server Error

## Support

For API access requests or technical support, contact the MDS Provider API team.

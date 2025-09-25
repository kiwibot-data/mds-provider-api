#!/bin/bash

# Test script for MDS Provider API
# Make sure to run the SQL setup scripts first!

API_URL="https://mds-provider-api-862961741611.us-central1.run.app"
API_KEY="mds_washington_ddot_2024"

echo "Testing MDS Provider API..."
echo "================================"

# Test health endpoint
echo "1. Testing health endpoint..."
curl -s "$API_URL/health" | jq '.' || echo "Health check failed"
echo ""

# Test vehicles endpoint (with trailing slash)
echo "2. Testing vehicles endpoint..."
curl -s -H "X-API-Key: $API_KEY" "$API_URL/vehicles/" | jq '.vehicles | length' || echo "Vehicles endpoint failed"
echo ""

# Test trips endpoint with a specific hour (using data from September 2025)
echo "3. Testing trips endpoint..."
curl -s -H "X-API-Key: $API_KEY" "$API_URL/trips?end_time=2025-09-08T23" | jq '.trips | length' || echo "Trips endpoint failed"
echo ""

# Test events endpoint (historical events for September 25, 2025)
echo "4. Testing events endpoint..."
curl -s -H "X-API-Key: $API_KEY" "$API_URL/events/historical?event_time=2025-09-25T00" | jq '.events | length' || echo "Events endpoint failed"
echo ""

echo "Test completed!"

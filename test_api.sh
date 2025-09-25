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

# Test trips endpoint with a specific hour
echo "3. Testing trips endpoint..."
curl -s -H "X-API-Key: $API_KEY" "$API_URL/trips?end_time=2025-01-01T12" | jq '.trips | length' || echo "Trips endpoint failed"
echo ""

# Test events endpoint (recent events)
echo "4. Testing events endpoint..."
CURRENT_TIME=$(date +%s)
START_TIME=$((CURRENT_TIME - 3600))  # 1 hour ago
curl -s -H "X-API-Key: $API_KEY" "$API_URL/events/recent?start_time=$START_TIME&end_time=$CURRENT_TIME" | jq '.' || echo "Events endpoint failed"
echo ""

echo "Test completed!"

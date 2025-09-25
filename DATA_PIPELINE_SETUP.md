# MDS Provider API - Data Pipeline Setup

This document explains how to set up the pre-computed tables for the MDS Provider API to ensure fast response times.

## Overview

The MDS Provider API uses pre-computed tables to avoid running complex BigQuery queries on every API request. This approach provides:

- **Fast API responses** (sub-second)
- **Reduced BigQuery costs** (no repeated complex queries)
- **Better reliability** (no timeout issues)
- **Scalability** (can handle high request volumes)

## Architecture

```
Raw Data Tables → Data Pipeline → Pre-computed Tables → MDS API
     ↓                ↓                ↓              ↓
robot_location    Complex Queries   vehicles_current   Fast API
jobs_processed    (run elsewhere)   trips_processed    Responses
```

## Setup Instructions

### 1. Create Pre-computed Tables

Run the initial setup script to create the tables and populate them:

```bash
# Run in BigQuery console or using bq command line
bq query --use_legacy_sql=false < sql/create_precomputed_tables.sql
```

This will:
- Create the `mds_precomputed` dataset
- Create three tables: `vehicles_current`, `trips_processed`, `events_processed`
- Populate them with initial data
- Create indexes for performance

### 2. Set Up Data Pipeline

Create a scheduled job to refresh the pre-computed tables. You can use:

#### Option A: Cloud Scheduler + Cloud Functions
```bash
# Create a Cloud Function that runs the refresh script
gcloud functions deploy refresh-mds-data \
  --runtime python39 \
  --trigger-http \
  --entry-point refresh_data \
  --source ./cloud_function
```

#### Option B: Cloud Composer (Airflow)
Create a DAG that runs the refresh script every hour:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

default_args = {
    'owner': 'mds-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'refresh_mds_data',
    default_args=default_args,
    description='Refresh MDS pre-computed tables',
    schedule_interval='0 * * * *',  # Every hour
    catchup=False,
)

refresh_tables = BigQueryInsertJobOperator(
    task_id='refresh_precomputed_tables',
    configuration={
        "query": {
            "query": "{{ ti.xcom_pull(task_ids='load_sql') }}",
            "useLegacySql": False,
        }
    },
    dag=dag,
)
```

#### Option C: Manual Refresh
Run the refresh script manually when needed:

```bash
bq query --use_legacy_sql=false < sql/refresh_precomputed_tables.sql
```

### 3. Grant Permissions

Ensure the MDS API service account has access to the pre-computed tables:

```bash
# Grant read access to the service account
bq query --use_legacy_sql=false "
GRANT SELECT ON \`kiwibot-atlas.mds_precomputed.*\` 
TO 'mds-api-sa@kiwibot-atlas.iam.gserviceaccount.com'
"
```

### 4. Update API Configuration

The API is already configured to use the pre-computed tables. The configuration is in `app/config.py`:

```python
# Pre-computed tables for fast API access
BIGQUERY_DATASET_PRECOMPUTED: str = "mds_precomputed"
BIGQUERY_TABLE_VEHICLES: str = "vehicles_current"
BIGQUERY_TABLE_TRIPS_PROCESSED: str = "trips_processed"
BIGQUERY_TABLE_EVENTS: str = "events_processed"
```

## Table Schemas

### vehicles_current
Current status of all robots with their latest location and metadata.

| Column | Type | Description |
|--------|------|-------------|
| robot_id | STRING | Unique robot identifier |
| latitude | FLOAT64 | Current latitude |
| longitude | FLOAT64 | Current longitude |
| timestamp | TIMESTAMP | Last location update |
| accuracy | FLOAT64 | Location accuracy |
| status | STRING | Robot status (available/reserved/unavailable) |
| battery_level | FLOAT64 | Battery percentage |
| last_updated | TIMESTAMP | When this record was last updated |
| model | STRING | Robot model (Kiwibot-F/E/H) |
| year | INT64 | Manufacturing year (2025) |
| color | STRING | Robot color (blue) |
| vehicle_type | STRING | MDS vehicle type (scooter) |
| propulsion_type | STRING | MDS propulsion type (electric) |

### trips_processed
Processed trip data ready for MDS API consumption.

| Column | Type | Description |
|--------|------|-------------|
| robot_id | STRING | Robot identifier |
| trip_id | STRING | Unique trip identifier |
| trip_start | TIMESTAMP | Trip start time |
| trip_end | TIMESTAMP | Trip end time |
| trip_duration_seconds | INT64 | Trip duration |
| start_latitude | FLOAT64 | Trip start latitude |
| start_longitude | FLOAT64 | Trip start longitude |
| end_latitude | FLOAT64 | Trip end latitude |
| end_longitude | FLOAT64 | Trip end longitude |
| status | STRING | Trip status |
| user_id | STRING | User who requested the trip |
| job_id | STRING | Original job ID |
| created_at | TIMESTAMP | When trip was created |
| updated_at | TIMESTAMP | When record was last updated |

### events_processed
Robot events for MDS events endpoint.

| Column | Type | Description |
|--------|------|-------------|
| robot_id | STRING | Robot identifier |
| event_id | STRING | Unique event identifier |
| event_type | STRING | Event type (trip_start/trip_end/etc) |
| event_time | TIMESTAMP | When event occurred |
| latitude | FLOAT64 | Event location latitude |
| longitude | FLOAT64 | Event location longitude |
| event_data | JSON | Additional event metadata |
| created_at | TIMESTAMP | When record was created |

## Monitoring

### Check Data Freshness
```sql
SELECT 
  robot_id,
  last_updated,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_updated, MINUTE) as minutes_old
FROM `kiwibot-atlas.mds_precomputed.vehicles_current`
ORDER BY last_updated DESC
LIMIT 10;
```

### Check Data Volume
```sql
SELECT 
  'vehicles_current' as table_name,
  COUNT(*) as record_count,
  MAX(last_updated) as latest_update
FROM `kiwibot-atlas.mds_precomputed.vehicles_current`
UNION ALL
SELECT 
  'trips_processed' as table_name,
  COUNT(*) as record_count,
  MAX(updated_at) as latest_update
FROM `kiwibot-atlas.mds_precomputed.trips_processed`
UNION ALL
SELECT 
  'events_processed' as table_name,
  COUNT(*) as record_count,
  MAX(created_at) as latest_update
FROM `kiwibot-atlas.mds_precomputed.events_processed`;
```

## Troubleshooting

### API Returns Empty Results
1. Check if pre-computed tables exist and have data
2. Verify service account permissions
3. Check BigQuery quotas and limits

### Data is Stale
1. Check if refresh pipeline is running
2. Verify Cloud Scheduler/Composer jobs are active
3. Check for errors in refresh logs

### Performance Issues
1. Check table partitioning and clustering
2. Verify indexes are created
3. Monitor BigQuery slot usage

## Cost Optimization

- **Partitioning**: Tables are partitioned by date to reduce scan costs
- **Clustering**: Tables are clustered by robot_id for faster queries
- **Retention**: Only keep last 7 days of trip/event data
- **Refresh Frequency**: Balance between data freshness and cost

## Next Steps

1. Run the initial setup script
2. Set up your preferred refresh mechanism
3. Test the API endpoints
4. Monitor data freshness and costs
5. Adjust refresh frequency as needed

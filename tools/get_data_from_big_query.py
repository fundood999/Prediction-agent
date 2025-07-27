from google.cloud import bigquery
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account

# Path to the service account key inside the container
KEY_PATH = "tools/key.json"

# Load credentials
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)

# Initialize client with credentials
client = bigquery.Client(credentials=credentials, project=credentials.project_id)


async def find_location_anomaly_match(locations: list) -> list:
    matches = []
    # Current time and two hours ago in UTC
    current_utc_time = datetime.now(timezone.utc)
    two_hours_ago_utc = current_utc_time - timedelta(hours=1000000)

    for location in locations:
        # Prepare parameterized query
        QUERY = f"""
            SELECT
                event_type, sub_event_type, area_name, street_name, city, severity_score, description
            FROM
                `mystical-magnet-466811-s3.direct_store.anamoly_data`
            WHERE
                LOWER(TRIM(street_name)) = LOWER('{location}')
                AND unix_timestamp >= @two_hours_ago
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("two_hours_ago", "TIMESTAMP", two_hours_ago_utc)
            ]
        )

        # Execute the query
        query_job = client.query(QUERY, job_config=job_config)
        rows = query_job.result()

        # Process the result
        for row in rows:
            if (row.event_type, row.sub_event_type, row.area_name, row.street_name, row.city, row.description, row.severity_score) not in matches:
                matches.append((row.event_type, row.sub_event_type, row.area_name, row.street_name, row.city, row.description, row.severity_score))
    
    return matches

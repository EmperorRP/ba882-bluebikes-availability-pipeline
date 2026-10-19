import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

from google.cloud import bigquery, storage

PROJECT = "ba882-bluebikes-pipeline"
BUCKET = "ba882-bluebikes-pipeline-raw"
TABLE = f"{PROJECT}.raw.weather_hourly"

LAT, LON = 42.3601, -71.0589  # Boston
VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]
logging.basicConfig(level=logging.INFO)


def fetch(base_url, params):
    url = base_url + "?" + urlencode(params)
    with urlopen(url, timeout=120) as response:
        data = json.load(response)
    if data.get("error"):
        raise RuntimeError(data)
    if not data.get("hourly", {}).get("time"):
        raise ValueError("Weather API returned no hourly records")
    return data


def make_rows(data, source):
    hourly = data["hourly"]
    rows = []
    for i, timestamp in enumerate(hourly["time"]):
        rows.append({
            "weather_time": datetime.fromtimestamp(
                timestamp, timezone.utc
            ).isoformat(),
            "source": source,
            "temperature_c": hourly["temperature_2m"][i],
            "humidity_pct": hourly["relative_humidity_2m"][i],
            "precipitation_mm": hourly["precipitation"][i],
            "wind_speed_kmh": hourly["wind_speed_10m"][i],
        })
    return rows


def main():
    today = datetime.now(timezone.utc).date()
    common = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": ",".join(VARIABLES),
        "timeformat": "unixtime",
        "timezone": "UTC",
    }

    datasets = []

    archive_end = today - timedelta(days=7)
    if archive_end.isoformat() >= "2026-01-01":
        historical = fetch(
            "https://archive-api.open-meteo.com/v1/archive",
            {
                **common,
                "start_date": "2026-01-01",
                "end_date": archive_end.isoformat(),
            },
        )
        datasets.append(("historical", historical))

    recent_and_forecast = fetch(
        "https://api.open-meteo.com/v1/forecast",
        {**common, "past_days": 7, "forecast_days": 7},
    )
    datasets.append(("forecast_api", recent_and_forecast))

    storage_client = storage.Client(project=PROJECT)
    bq = bigquery.Client(project=PROJECT)

    schema = [
        bigquery.SchemaField("weather_time", "TIMESTAMP"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("temperature_c", "FLOAT64"),
        bigquery.SchemaField("humidity_pct", "FLOAT64"),
        bigquery.SchemaField("precipitation_mm", "FLOAT64"),
        bigquery.SchemaField("wind_speed_kmh", "FLOAT64"),
    ]

    bq.create_table(
        bigquery.Table(TABLE, schema=schema), exists_ok=True
    )

    for source, data in datasets:
        raw_bytes = json.dumps(data).encode("utf-8")
        digest = hashlib.sha256(raw_bytes).hexdigest()
        object_name = f"weather/{source}/{digest}.json"
        blob = storage_client.bucket(BUCKET).blob(object_name)

        try:
            blob.upload_from_string(
                raw_bytes,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            from google.api_core.exceptions import PreconditionFailed
            if not isinstance(exc, PreconditionFailed):
                raise

        rows = make_rows(data, source)
        staging = (
            f"{PROJECT}.raw._weather_"
            f"{uuid.uuid4().hex[:12]}"
        )

        try:
            config = bigquery.LoadJobConfig(
                schema=schema,
                write_disposition="WRITE_TRUNCATE",
            )
            bq.load_table_from_json(
                rows, staging, job_config=config
            ).result()

            bq.query(f"""
                MERGE `{TABLE}` T
                USING `{staging}` S
                ON T.weather_time = S.weather_time
                   AND T.source = S.source
                WHEN MATCHED THEN UPDATE SET
                    temperature_c = S.temperature_c,
                    humidity_pct = S.humidity_pct,
                    precipitation_mm = S.precipitation_mm,
                    wind_speed_kmh = S.wind_speed_kmh
                WHEN NOT MATCHED THEN INSERT (
                    weather_time, source, temperature_c,
                    humidity_pct, precipitation_mm,
                    wind_speed_kmh
                ) VALUES (
                    S.weather_time, S.source, S.temperature_c,
                    S.humidity_pct, S.precipitation_mm,
                    S.wind_speed_kmh
                )
            """).result()
        finally:
            bq.delete_table(staging, not_found_ok=True)

        logging.info(
            "%s: %s hourly records loaded", source, len(rows)
        )

    logging.info("Weather ingestion completed!")


if __name__ == "__main__":
    main()


import csv
import os
import hashlib
import io
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

PROJECT_ID = "ba882-bluebikes-pipeline"
BUCKET_NAME = "ba882-bluebikes-pipeline-raw"

TRIP_MONTH = os.environ.get("TRIP_MONTH", "202601")

if len(TRIP_MONTH) != 6 or not TRIP_MONTH.isdigit():
    raise ValueError("TRIP_MONTH must be YYYYMM")

year, month = TRIP_MONTH[:4], TRIP_MONTH[4:]
if not 1 <= int(month) <= 12:
    raise ValueError("Invalid month")

SOURCE_URL = (
    f"https://s3.amazonaws.com/hubway-data/"
    f"{TRIP_MONTH}-bluebikes-tripdata.zip"
)

REQUIRED_COLUMNS = {
    "ride_id", "started_at", "ended_at",
    "start_station_id", "end_station_id"
}

logging.basicConfig(level=logging.INFO)



def load_trips_to_bigquery(zip_path):
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.raw.historical_trips"

    string_cols = [
        "ride_id", "rideable_type",
        "start_station_name", "start_station_id",
        "end_station_name", "end_station_id",
        "member_casual",
    ]
    time_cols = ["started_at", "ended_at"]
    float_cols = ["start_lat", "start_lng", "end_lat", "end_lng"]

    column_types = {
        **{c: "STRING" for c in string_cols},
        **{c: "TIMESTAMP" for c in time_cols},
        **{c: "FLOAT64" for c in float_cols},
    }

    columns = [
        "ride_id", "rideable_type", "started_at", "ended_at",
        "start_station_name", "start_station_id",
        "end_station_name", "end_station_id",
        "start_lat", "start_lng", "end_lat", "end_lng",
        "member_casual",
    ]
    schema = [
        bigquery.SchemaField(c, column_types[c]) for c in columns
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)

    import uuid
    staging_id = f"{PROJECT_ID}.raw._trips_load_{uuid.uuid4().hex[:12]}"
    columns = [
        "ride_id", "rideable_type", "started_at", "ended_at",
        "start_station_name", "start_station_id",
        "end_station_name", "end_station_id",
        "start_lat", "start_lng", "end_lat", "end_lng",
        "member_casual",
    ]

    try:
        with zipfile.ZipFile(zip_path) as archive:
            files = [
                n for n in archive.namelist()
                if n.lower().endswith(".csv")
                and not n.startswith("__MACOSX/")
            ]
            for i, name in enumerate(files):
                with tempfile.TemporaryFile() as csv_file:
                    with archive.open(name) as source:
                        shutil.copyfileobj(source, csv_file)
                    csv_file.seek(0)

                    job_config = bigquery.LoadJobConfig(
                        schema=schema,
                        source_format=bigquery.SourceFormat.CSV,
                        skip_leading_rows=1,
                        write_disposition=(
                            bigquery.WriteDisposition.WRITE_TRUNCATE
                            if i == 0
                            else bigquery.WriteDisposition.WRITE_APPEND
                        ),
                    )
                    client.load_table_from_file(
                        csv_file,
                        staging_id,
                        job_config=job_config,
                    ).result()

        fields = ", ".join(columns)
        updates = ", ".join(
            f"T.{c} = S.{c}" for c in columns if c != "ride_id"
        )
        inserts = ", ".join(f"S.{c}" for c in columns)

        query = f"""
        MERGE `{table_id}` T
        USING (
          SELECT * EXCEPT(_rn)
          FROM (
            SELECT *,
              ROW_NUMBER() OVER (
                PARTITION BY ride_id ORDER BY started_at DESC
              ) AS _rn
            FROM `{staging_id}`
            WHERE ride_id IS NOT NULL
          )
          WHERE _rn = 1
        ) S
        ON T.ride_id = S.ride_id
        WHEN MATCHED THEN UPDATE SET {updates}
        WHEN NOT MATCHED THEN
          INSERT ({fields}) VALUES ({inserts})
        """
        client.query(query).result()
        logging.info("BigQuery MERGE completed: %s", table_id)
    finally:
        client.delete_table(staging_id, not_found_ok=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / f"{TRIP_MONTH}-bluebikes-tripdata.zip"

        # Download source ZIP
        with urlopen(SOURCE_URL, timeout=60) as response:
            with zip_path.open("wb") as output:
                shutil.copyfileobj(response, output)

        # Validate CSV schema and count records
        row_count = 0

        with zipfile.ZipFile(zip_path) as archive:
            csv_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
                and not name.startswith("__MACOSX/")
            ]

            if not csv_files:
                raise ValueError("No CSV found in ZIP")

            for name in csv_files:
                with archive.open(name) as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(
                            raw, encoding="utf-8-sig", newline=""
                        )
                    )

                    missing = REQUIRED_COLUMNS - set(
                        reader.fieldnames or []
                    )
                    if missing:
                        raise ValueError(
                            f"Missing required columns: {missing}"
                        )

                    row_count += sum(1 for _ in reader)

        logging.info("Validated %s trip records", row_count)

        # Content hash for safe repeated ingestion
        checksum = hashlib.file_digest(
            zip_path.open("rb"), "sha256"
        ).hexdigest()

        object_name = (
            f"historical_trips/{year}/{month}/{checksum}/"
            f"{TRIP_MONTH}-bluebikes-tripdata.zip"
        )

        client = storage.Client(project=PROJECT_ID)
        blob = client.bucket(BUCKET_NAME).blob(object_name)

        blob.metadata = {
            "source_url": SOURCE_URL,
            "ingested_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "sha256": checksum,
            "row_count": str(row_count),
        }

        try:
            blob.upload_from_filename(
                str(zip_path),
                content_type="application/zip",
                if_generation_match=0,
            )
            logging.info("Uploaded to GCS: %s", object_name)
        except PreconditionFailed:
            logging.info("Already exists in GCS: %s", object_name)

        load_trips_to_bigquery(zip_path)
        logging.info("Historical trips ingestion completed!")


if __name__ == "__main__":
    main()

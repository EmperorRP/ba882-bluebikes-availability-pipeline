import csv
import hashlib
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage

PROJECT = "ba882-bluebikes-pipeline"
BUCKET = "ba882-bluebikes-pipeline-raw"
TABLE = f"{PROJECT}.raw.historical_trips"

MONTH = os.environ.get("TRIP_MONTH", "202601")
if len(MONTH) != 6 or not MONTH.isdigit() or not 1 <= int(MONTH[4:]) <= 12:
    raise ValueError("TRIP_MONTH must be YYYYMM")

COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id",
    "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng",
    "member_casual",
]
TYPES = {
    **{c: "STRING" for c in COLUMNS},
    **{c: "TIMESTAMP" for c in ["started_at", "ended_at"]},
    **{c: "FLOAT64" for c in [
        "start_lat", "start_lng", "end_lat", "end_lng"
    ]},
}
SCHEMA = [bigquery.SchemaField(c, TYPES[c]) for c in COLUMNS]
REQUIRED = {"ride_id", "started_at", "ended_at", "start_station_id", "end_station_id"}

logging.basicConfig(level=logging.INFO)


def download_source(tmp):
    for ext in ("zip", "csv"):
        filename = f"{MONTH}-bluebikes-tripdata.{ext}"
        url = f"https://s3.amazonaws.com/hubway-data/{filename}"
        path = tmp / filename
        try:
            with urlopen(url, timeout=120) as response:
                with path.open("wb") as f:
                    shutil.copyfileobj(response, f)
            logging.info("Downloaded %s", url)
            return path, url
        except HTTPError as exc:
            if exc.code != 404:
                raise

    raise FileNotFoundError(f"No ZIP or CSV published for {MONTH}")


def csv_paths(source, tmp):
    if source.suffix.lower() == ".csv":
        return [source]

    output = []
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".csv") or name.startswith("__MACOSX/"):
                continue
            target = tmp / f"extracted_{len(output)}.csv"
            with archive.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            output.append(target)

    if not output:
        raise ValueError("No CSV files found in ZIP")
    return output


def validate_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing = REQUIRED - set(headers)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        if headers != COLUMNS:
            raise ValueError(f"Unexpected CSV columns/order: {headers}")
        return sum(1 for _ in reader)


def upload_gcs(path, url, count):
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()

    object_name = (
        f"historical_trips/{MONTH[:4]}/{MONTH[4:]}/"
        f"{digest}/{path.name}"
    )
    blob = storage.Client(project=PROJECT).bucket(BUCKET).blob(object_name)
    blob.metadata = {
        "source_url": url,
        "sha256": digest,
        "row_count": str(count),
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        blob.upload_from_filename(
            str(path),
            content_type=("application/zip" if path.suffix == ".zip" else "text/csv"),
            if_generation_match=0,
        )
        logging.info("Uploaded to GCS: %s", object_name)
    except PreconditionFailed:
        logging.info("Already exists in GCS: %s", object_name)

    return f"gs://{BUCKET}/{object_name}", url, digest


def load_bigquery(paths, gcs_path, source_url, checksum):
    client = bigquery.Client(project=PROJECT)
    client.create_table(bigquery.Table(TABLE, schema=SCHEMA), exists_ok=True)
    for name, dtype in [
        ("gcs_path", "STRING"),
        ("source_url", "STRING"),
        ("source_checksum", "STRING"),
        ("ingested_at", "TIMESTAMP"),
    ]:
        client.query(
            f"ALTER TABLE `{TABLE}` ADD COLUMN IF NOT EXISTS {name} {dtype}"
        ).result()

    staging = f"{PROJECT}.raw._trips_load_{uuid.uuid4().hex[:12]}"

    try:
        for i, path in enumerate(paths):
            config = bigquery.LoadJobConfig(
                schema=SCHEMA,
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                write_disposition=(
                    "WRITE_TRUNCATE" if i == 0 else "WRITE_APPEND"
                ),
            )
            with path.open("rb") as f:
                client.load_table_from_file(
                    f, staging, job_config=config
                ).result()

        lineage_columns = [
            "gcs_path", "source_url",
            "source_checksum", "ingested_at"
        ]
        all_columns = COLUMNS + lineage_columns

        names = ", ".join(all_columns)
        values = ", ".join(f"S.{c}" for c in all_columns)
        updates = ", ".join(
            f"T.{c} = S.{c}"
            for c in all_columns if c != "ride_id"
        )

        ingested_at = datetime.now(timezone.utc)

        query = f"""
            MERGE `{TABLE}` T
            USING (
                SELECT
                    D.*,
                    @gcs_path AS gcs_path,
                    @source_url AS source_url,
                    @checksum AS source_checksum,
                    @ingested_at AS ingested_at
                FROM (
                    SELECT * EXCEPT(rn)
                    FROM (
                        SELECT *,
                          ROW_NUMBER() OVER (
                            PARTITION BY ride_id
                            ORDER BY started_at DESC
                          ) AS rn
                        FROM `{staging}`
                        WHERE ride_id IS NOT NULL
                    )
                    WHERE rn = 1
                ) D
            ) S
            ON T.ride_id = S.ride_id
            WHEN MATCHED THEN UPDATE SET {updates}
            WHEN NOT MATCHED THEN
                INSERT ({names}) VALUES ({values})
        """

        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "gcs_path", "STRING", gcs_path
                ),
                bigquery.ScalarQueryParameter(
                    "source_url", "STRING", source_url
                ),
                bigquery.ScalarQueryParameter(
                    "checksum", "STRING", checksum
                ),
                bigquery.ScalarQueryParameter(
                    "ingested_at", "TIMESTAMP", ingested_at
                ),
            ]
        )

        client.query(query, job_config=config).result()

        logging.info("BigQuery MERGE completed: %s", TABLE)
    finally:
        client.delete_table(staging, not_found_ok=True)


def main():
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        source, url = download_source(tmp)
        paths = csv_paths(source, tmp)
        count = sum(validate_csv(path) for path in paths)
        logging.info("Validated %s trip records", count)
        gcs_path, source_url, checksum = upload_gcs(
            source, url, count
        )
        load_bigquery(paths, gcs_path, source_url, checksum)
        logging.info("Historical trips ingestion completed!")


if __name__ == "__main__":
    main()
    
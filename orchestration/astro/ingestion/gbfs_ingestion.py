
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone

from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage

from gbfs_client import GBFS_URL, fetch_json, find_feed
from gbfs_validation import validate_stations

PROJECT = "ba882-bluebikes-pipeline"
BUCKET = "ba882-bluebikes-pipeline-raw"
DATASET = "raw"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

SCHEMAS = {
    "station_information": [
        bigquery.SchemaField("station_id", "STRING"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("lat", "FLOAT"),
        bigquery.SchemaField("lon", "FLOAT"),
        bigquery.SchemaField("capacity", "INTEGER"),
    ],
    "station_status": [
        bigquery.SchemaField("station_id", "STRING"),
        bigquery.SchemaField("num_bikes_available", "INTEGER"),
        bigquery.SchemaField("num_docks_available", "INTEGER"),
        bigquery.SchemaField("is_renting", "INTEGER"),
        bigquery.SchemaField("is_returning", "INTEGER"),
        bigquery.SchemaField("last_reported", "INTEGER"),
    ],
}

METADATA_SCHEMA = [
    bigquery.SchemaField("snapshot_id", "STRING"),
    bigquery.SchemaField("ingested_at_utc", "TIMESTAMP"),
    bigquery.SchemaField("source_url", "STRING"),
    bigquery.SchemaField("raw_json", "STRING"),
]


def get_feed_urls():
    discovery = fetch_json(GBFS_URL)
    data = discovery["data"]

    if "feeds" in data:
        feeds = data["feeds"]
    else:
        feeds = next(
            value["feeds"] for value in data.values()
            if isinstance(value, dict) and "feeds" in value
        )

    return {
        name: find_feed(feeds, name)
        for name in SCHEMAS
    }


def ensure_table(client, feed):
    table_id = f"{PROJECT}.{DATASET}.{feed}"
    table = bigquery.Table(
        table_id,
        schema=SCHEMAS[feed] + METADATA_SCHEMA,
    )
    table.time_partitioning = bigquery.TimePartitioning(
        field="ingested_at_utc"
    )
    table.clustering_fields = ["station_id"]

    client.create_table(table, exists_ok=True)
    return table_id


def upload_raw(client, feed, payload, url, collected_at):
    content = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    checksum = hashlib.sha256(content).hexdigest()
    snapshot_id = collected_at
    object_name = f"gbfs/{feed}/{snapshot_id.replace(':', '-')}/{checksum}.json"

    blob = client.bucket(BUCKET).blob(object_name)
    blob.metadata = {
        "source_url": url,
        "ingested_at_utc": collected_at,
        "sha256": checksum,
        "gbfs_version": str(payload.get("version", "")),
    }

    try:
        blob.upload_from_string(
            content,
            content_type="application/json",
            if_generation_match=0,
        )
        logging.info("Uploaded to GCS: %s", object_name)

    except PreconditionFailed:
        logging.info("Already exists in GCS: %s", object_name)

    return snapshot_id


def prepare_rows(feed, stations, snapshot_id, url, collected_at):
    rows = []

    for station in stations:
        row = {
            field.name: station.get(field.name)
            for field in SCHEMAS[feed]
        }

        row.update({
            "snapshot_id": snapshot_id,
            "ingested_at_utc": collected_at,
            "source_url": url,
            "raw_json": json.dumps(station),
        })
        rows.append(row)

    return rows


def load_without_duplicates(client, feed, rows):
    destination = ensure_table(client, feed)

    # Temporary staging table for safe MERGE
    stage = (
        f"{PROJECT}.{DATASET}."
        f"_ingestion_{feed}_{uuid.uuid4().hex[:12]}"
    )

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=SCHEMAS[feed] + METADATA_SCHEMA,
        write_disposition="WRITE_EMPTY",
    )

    jsonl = "\n".join(json.dumps(row) for row in rows)
    data = io.BytesIO(jsonl.encode("utf-8"))

    try:
        job = client.load_table_from_file(
            data, stage, job_config=job_config
        )
        job.result()

        columns = [f.name for f in SCHEMAS[feed] + METADATA_SCHEMA]
        names = ", ".join(f"`{name}`" for name in columns)
        values = ", ".join(f"S.`{name}`" for name in columns)

        sql = f"""
        MERGE `{destination}` T
        USING `{stage}` S
        ON T.snapshot_id = S.snapshot_id
           AND T.station_id = S.station_id
        WHEN NOT MATCHED THEN
          INSERT ({names})
          VALUES ({values})
        """

        client.query(sql).result()
        logging.info("BigQuery MERGE completed: %s", destination)

    finally:
        client.delete_table(stage, not_found_ok=True)


def main():
    gcs = storage.Client(project=PROJECT)
    bq = bigquery.Client(project=PROJECT)

    feed_urls = get_feed_urls()

    for feed, url in feed_urls.items():
        logging.info("Processing: %s", feed)

        payload = fetch_json(url)
        stations = payload["data"]["stations"]

        errors, station_ids = validate_stations(stations, feed)
        if errors or len(station_ids) != len(stations):
            raise ValueError(
                f"{feed}: invalid or duplicate station records"
            )

        collected_at = datetime.now(timezone.utc).isoformat()

        snapshot_id = upload_raw(
            gcs, feed, payload, url, collected_at
        )

        rows = prepare_rows(
            feed, stations, snapshot_id, url, collected_at
        )

        load_without_duplicates(bq, feed, rows)

        logging.info(
            "%s processed: %s records", feed, len(rows)
        )

    logging.info("GBFS ingestion completed successfully!")


if __name__ == "__main__":
    main()

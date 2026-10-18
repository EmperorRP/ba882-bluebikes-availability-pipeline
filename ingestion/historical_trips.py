
import csv
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

SOURCE_URL = (
    "https://s3.amazonaws.com/hubway-data/"
    "202601-bluebikes-tripdata.zip"
)

REQUIRED_COLUMNS = {
    "ride_id", "started_at", "ended_at",
    "start_station_id", "end_station_id"
}

logging.basicConfig(level=logging.INFO)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "202601-bluebikes-tripdata.zip"

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
            f"historical_trips/2026/01/{checksum}/"
            "202601-bluebikes-tripdata.zip"
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

        logging.info("Historical trips ingestion completed!")


if __name__ == "__main__":
    main()

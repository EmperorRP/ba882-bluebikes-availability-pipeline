
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from gbfs_client import GBFS_URL, fetch_json, find_feed

# Local test storage (not GCS yet)
RAW_DIR = Path("data/raw/gbfs")


def get_feed_urls():
    discovery = fetch_json(GBFS_URL)
    data = discovery["data"]

    if "feeds" in data:
        feeds = data["feeds"]
    else:
        feeds = next(
            value["feeds"]
            for value in data.values()
            if isinstance(value, dict) and "feeds" in value
        )

    return {
        name: find_feed(feeds, name)
        for name in ("station_information", "station_status")
    }


def save_snapshot(feed_name, url, payload, collected_at):
    # Stable identity for a source observation
    content = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    checksum = hashlib.sha256(content).hexdigest()

    # GBFS last_updated is usually Unix seconds
    source_timestamp = payload.get("last_updated")

    # Same source timestamp + content = same object key
    identity = (
        f"{source_timestamp}_{checksum[:16]}"
        if source_timestamp is not None
        else checksum[:16]
    )

    folder = RAW_DIR / feed_name
    folder.mkdir(parents=True, exist_ok=True)

    file_path = folder / f"{identity}.json"

    metadata_path = folder / f"{identity}.metadata.json"

    metadata = {
        "feed_name": feed_name,
        "source_url": url,
        "source_timestamp": source_timestamp,
        "ingested_at_utc": collected_at,
        "sha256": checksum,
        "gbfs_version": payload.get("version"),
    }

    # Exclusive mode prevents overwriting existing files
    try:
        with file_path.open("x", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except FileExistsError:
        print(f"Already stored: {file_path}")
        return

    with metadata_path.open("x", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved: {file_path}")
    print(f"Metadata: {metadata_path}")


def main():
    feed_urls = get_feed_urls()

    for feed_name, url in feed_urls.items():
        payload = fetch_json(url)
        collected_at = datetime.now(timezone.utc).isoformat()

        save_snapshot(feed_name, url, payload, collected_at)


if __name__ == "__main__":
    main()


from datetime import datetime, timezone

from gbfs_client import fetch_json, find_feed, GBFS_URL


def validate_stations(stations, feed_name):
    """Check station identifiers and numeric fields."""
    errors = []
    seen_ids = set()

    for index, station in enumerate(stations):
        station_id = station.get("station_id")

        # Check station IDs
        if not isinstance(station_id, str) or not station_id.strip():
            errors.append((index, "Missing/invalid station_id"))
        elif station_id in seen_ids:
            errors.append((index, "Duplicate station_id"))
        else:
            seen_ids.add(station_id)

        # Validate station availability counts
        if feed_name == "station_status":
            for field in [
                "num_bikes_available",
                "num_docks_available",
            ]:
                value = station.get(field)

                if type(value) is not int or value < 0:
                    errors.append((index, f"Invalid {field}: {value}"))

            # Validate Unix timestamp
            timestamp = station.get("last_reported")

            if type(timestamp) is not int or timestamp < 0:
                errors.append((index, "Invalid last_reported"))
            elif timestamp > 0:
                try:
                    datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except (OverflowError, OSError, ValueError):
                    errors.append((index, "Unparseable last_reported"))

    return errors, seen_ids


def main():
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

    info_url = find_feed(feeds, "station_information")
    status_url = find_feed(feeds, "station_status")

    information = fetch_json(info_url)
    status = fetch_json(status_url)

    info_stations = information["data"]["stations"]
    status_stations = status["data"]["stations"]

    info_errors, info_ids = validate_stations(
        info_stations, "station_information"
    )
    status_errors, status_ids = validate_stations(
        status_stations, "station_status"
    )

    print("--- GBFS DATA VALIDATION ---")
    print("Validation time (UTC):", datetime.now(timezone.utc).isoformat())

    print("Information records:", len(info_stations))
    print("Status records:", len(status_stations))

    print("Information errors:", len(info_errors))
    print("Status errors:", len(status_errors))

    print("Status IDs missing from information:", len(status_ids - info_ids))
    print("Information IDs missing from status:", len(info_ids - status_ids))

    print("\nFirst 10 status errors:")
    for error in status_errors[:10]:
        print(error)

    print("\nFirst 10 information errors:")
    for error in info_errors[:10]:
        print(error)


if __name__ == "__main__":
    main()


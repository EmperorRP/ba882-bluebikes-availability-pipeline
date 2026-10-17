
import json
from urllib.request import Request, urlopen

GBFS_URL = "https://gbfs.bluebikes.com/gbfs/gbfs.json"


def fetch_json(url):
    request = Request(
        url,
        headers={"User-Agent": "BA882-Bluebikes-Project/1.0"}
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def find_feed(feeds, name):
    for feed in feeds:
        if feed.get("name") == name:
            return feed["url"]
    raise ValueError(f"Feed not found: {name}")


def main():
    # 1. Discover available feeds
    discovery = fetch_json(GBFS_URL)

    data = discovery["data"]

    # Support GBFS discovery structures with language groups
    if "feeds" in data:
        feeds = data["feeds"]
    else:
        language_data = next(
            value for value in data.values()
            if isinstance(value, dict) and "feeds" in value
        )
        feeds = language_data["feeds"]

    # 2. Locate required feed URLs
    info_url = find_feed(feeds, "station_information")
    status_url = find_feed(feeds, "station_status")

    print("Station information URL:", info_url)
    print("Station status URL:", status_url)

    # 3. Fetch station data
    information = fetch_json(info_url)
    status = fetch_json(status_url)

    info_stations = information["data"]["stations"]
    status_stations = status["data"]["stations"]

    # 4. Inspect results
    print("\n--- ING-01 Results ---")
    print("Station information records:", len(info_stations))
    print("Station status records:", len(status_stations))

    print("\nInformation fields:")
    print(list(info_stations[0].keys()))

    print("\nStatus fields:")
    print(list(status_stations[0].keys()))

    print("\nExample station status:")
    print(json.dumps(status_stations[0], indent=2))


if __name__ == "__main__":
    main()


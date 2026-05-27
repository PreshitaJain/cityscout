"""Seed CityScout's local cache with the curated city list.

Run from a residential IP (e.g., your laptop), since Reddit blocks
cloud-provider IPs. The resulting cache files in ./cache/ are committed
to the repo and served by the deployed app.

Usage:
    python seed_cities.py

The script is idempotent: cities already cached are skipped, so you
can re-run after an interruption.
"""

import time

from cityscout import get_recommendations, load_from_cache

SLEEP_BETWEEN_CITIES = 25

CITIES = [
    ("Tokyo", None),
    ("Lisbon", None),
    ("Paris", None),
    ("London", None),
    ("Barcelona", None),
    ("Berlin", None),
    ("Chicago", None),
    ("Seattle", None),
    ("Sydney", None),
    ("Melbourne", None),
    ("Bangkok", None),
    ("Singapore", None),
    ("Mumbai", None),
    ("Delhi", None),
    ("Istanbul", None),
    ("Cairo", None),
    ("Rome", None),
    ("Amsterdam", None),
    ("Prague", None),
    ("Vienna", None),
    ("Stockholm", None),
    ("Copenhagen", None),
    ("Dublin", None),
    ("Edinburgh", None),
    ("Bali", None),
    ("Hanoi", None),
    ("Taipei", None),
    ("Seoul", None),
    ("Vancouver", None),
    ("Toronto", None),
    ("Boston", None),
    ("Austin", None),
    ("Miami", None),
    ("Marrakech", None),
    ("Reykjavik", None),
    ("Pune", None),
    ("Anchorage", None),
    ("New York", "nyc"),
    ("San Francisco", "sanfrancisco"),
    ("Los Angeles", "losangeles"),
    ("Mexico City", "mexicocity"),
    ("Buenos Aires", "buenosaires"),
    ("Sao Paulo", "saopaulo"),
    ("Rio de Janeiro", "riodejaneiro"),
    ("Cape Town", "capetown"),
    ("Hong Kong", "hongkong"),
    ("New Orleans", "neworleans"),
    ("Kuala Lumpur", "kualalumpur"),
]


def main():
    total = len(CITIES)
    succeeded = 0
    failed = []

    for i, (city, subreddit) in enumerate(CITIES, 1):
        if load_from_cache(city):
            print(f"[{i}/{total}] {city} already cached, skipping.")
            succeeded += 1
            continue

        print(f"[{i}/{total}] Seeding {city}...", flush=True)
        result = get_recommendations(city, subreddit=subreddit)
        if result:
            print(f"  -> OK")
            succeeded += 1
        else:
            print(f"  -> FAILED")
            failed.append(city)
        time.sleep(SLEEP_BETWEEN_CITIES)

    print(f"\nDone. {succeeded}/{total} cached.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()

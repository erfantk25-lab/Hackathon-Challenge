"""
Exploration script for the unofficial blocket_api package.

Goal: understand the actual shape of the data so we can design our
database schema and feature extraction against reality, not guesses.

This is a one-off discovery script. Run it, read the output, then
hand the findings to the team before anyone writes schema code.

Run with:
    python scripts/explore_api.py
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from blocket_api import (
    BlocketAPI,
    Category,
    CarSortOrder,
    Region,
    Location,
)


# All samples land here so we can re-read them without hitting the API
SAMPLES_DIR = Path(__file__).parent / "sample_data"
SAMPLES_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def save_json(name: str, data: Any) -> Path:
    """Dump anything JSON-serialisable to sample_data/<name>.json."""
    path = SAMPLES_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  → saved {path.relative_to(Path.cwd())}")
    return path


def extract_items(response: Any) -> list[dict]:
    """Pull the list of ads out of whatever shape the API returned.

    The package wraps responses inconsistently (sometimes {'data': [...]},
    sometimes a bare list). Normalise here so callers don't care.
    """
    if isinstance(response, dict):
        for key in ("data", "items", "results", "ads"):
            if key in response and isinstance(response[key], list):
                return response[key]
        # Fallback: response IS the dict we want, wrap it
        return [response]
    if isinstance(response, list):
        return response
    return []


def flatten_keys(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts so we can see all leaf fields at once.

    {'a': {'b': 1}} becomes {'a.b': 1}. Lists are summarised as
    '<list of N>' rather than expanded — we just want field presence.
    """
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten_keys(v, key))
            elif isinstance(v, list):
                out[key] = f"<list of {len(v)}>"
            else:
                out[key] = v
    return out


# ---------------------------------------------------------------------
# Field analysis
# ---------------------------------------------------------------------
def analyse_fields(items: list[dict], label: str) -> None:
    """Print which fields appear, how often, and what types they have.

    This is the single most useful output of the whole script. Read
    it carefully — it tells you which fields are reliable enough to
    treat as NOT NULL and which need to be Optional in the schema.
    """
    print(f"\n{'=' * 70}")
    print(f"Field analysis: {label}  ({len(items)} items)")
    print("=" * 70)

    if not items:
        print("  (no items to analyse)")
        return

    presence: Counter = Counter()
    empty_count: Counter = Counter()
    type_seen: dict[str, set[str]] = {}
    examples: dict[str, Any] = {}

    for item in items:
        flat = flatten_keys(item)
        for key, value in flat.items():
            presence[key] += 1
            if value is None or value == "" or value == [] or value == {}:
                empty_count[key] += 1
            else:
                type_seen.setdefault(key, set()).add(type(value).__name__)
                if key not in examples:
                    # Truncate long examples for readability
                    str_val = str(value)
                    examples[key] = (
                        str_val if len(str_val) <= 50 else str_val[:47] + "..."
                    )

    # Pretty table
    total = len(items)
    print(f"\n{'Field':<40} {'Filled':<10} {'Types':<15} {'Example'}")
    print("-" * 100)
    for key in sorted(presence.keys()):
        filled = presence[key] - empty_count[key]
        types = ",".join(sorted(type_seen.get(key, {"-"})))
        example = examples.get(key, "")
        print(f"{key:<40} {filled}/{total:<7} {types:<15} {example}")

    # Reliability summary
    print(f"\nReliability summary (for schema design):")
    always_filled = [
        k for k in presence
        if presence[k] == total and empty_count[k] == 0
    ]
    sometimes_filled = [
        k for k in presence
        if 0 < (presence[k] - empty_count[k]) < total
    ]
    print(f"  Always present (candidates for NOT NULL): {len(always_filled)}")
    for k in always_filled[:15]:
        print(f"    - {k}")
    if len(always_filled) > 15:
        print(f"    ... and {len(always_filled) - 15} more")

    print(f"  Sometimes empty (must be Optional):       {len(sometimes_filled)}")


# ---------------------------------------------------------------------
# Exploration steps
# ---------------------------------------------------------------------
def explore_general_search(api: BlocketAPI) -> list[dict]:
    """Hit the public custom_search endpoint with a common term.

    This is the simplest endpoint and works without a token. If this
    fails, the whole package is broken and we need to investigate.
    """
    print("\n" + "#" * 70)
    print("# 1. General search: 'iphone' (public endpoint, no token)")
    print("#" * 70)

    try:
        response = api.custom_search("iphone")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
        print("  This is a blocker — check the package's auth/network behaviour.")
        return []

    items = extract_items(response)
    print(f"  got {len(items)} items")
    save_json("01_general_iphone_raw", response)
    if items:
        save_json("01_general_iphone_first_item", items[0])
    return items


def explore_electronics(api: BlocketAPI) -> list[dict]:
    """Search within the electronics category using the typed enum.

    We want to see if filtering by Category changes the data shape
    and whether electronics-specific fields appear.
    """
    print("\n" + "#" * 70)
    print("# 2. Electronics category search")
    print("#" * 70)

    try:
        # The exact attribute name may vary by package version —
        # check Category.__members__ if this raises AttributeError.
        response = api.custom_search(
            "iphone",
            category=Category.ELEKTRONIK,
        )
    except AttributeError:
        print("  Category.ELEKTRONIK not found, listing available categories:")
        print(f"  {list(Category.__members__)[:10]}...")
        return []
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
        return []

    items = extract_items(response)
    print(f"  got {len(items)} items")
    save_json("02_electronics_raw", response)
    return items


def explore_cars(api: BlocketAPI) -> list[dict]:
    """Cars use a dedicated endpoint with much richer filtering.

    This is where we expect the most structured data (year, mileage,
    fuel type, transmission) and where our ML price model will live.
    """
    print("\n" + "#" * 70)
    print("# 3. Car search (dedicated endpoint with structured filters)")
    print("#" * 70)

    try:
        response = api.search_car(
            "volvo",
            sort_order=CarSortOrder.PRICE_ASC,
            price_from=20_000,
            price_to=200_000,
        )
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
        print("  Trying without filters...")
        try:
            response = api.search_car("volvo")
        except Exception as e2:
            print(f"  Still failed: {e2}")
            return []

    items = extract_items(response)
    print(f"  got {len(items)} items")
    save_json("03_cars_raw", response)
    if items:
        save_json("03_cars_first_item", items[0])
    return items


def explore_regions(api: BlocketAPI) -> None:
    """List what regions and locations are available.

    Useful for designing the location filter in the frontend.
    """
    print("\n" + "#" * 70)
    print("# 4. Available regions and locations")
    print("#" * 70)

    regions = [r.name for r in Region]
    locations = [l.name for l in Location]
    print(f"  Region enum ({len(regions)}):   {regions[:8]}...")
    print(f"  Location enum ({len(locations)}): {locations[:8]}...")

    save_json("04_enums", {
        "regions": regions,
        "locations": locations,
        "categories": [c.name for c in Category],
    })


def deep_dive(items: list[dict], label: str, n: int = 3) -> None:
    """Print n complete items in full for visual inspection.

    The aggregated field table is great for breadth; this gives you
    depth on individual ads so you can spot quirks no aggregate
    statistic would catch (weird formats, nested structures, etc).
    """
    print(f"\n{'=' * 70}")
    print(f"Deep dive: {label} — {n} full items")
    print("=" * 70)
    for i, item in enumerate(items[:n], 1):
        print(f"\n--- Item {i} ---")
        print(json.dumps(item, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main() -> None:
    """Run the full exploration and produce a summary report."""
    print(f"Blocket API exploration — {datetime.now().isoformat(timespec='seconds')}")
    print(f"Output directory: {SAMPLES_DIR.resolve()}\n")

    api = BlocketAPI()  # no token; public endpoints only

    # Phase 1: hit each endpoint, save raw JSON
    general = explore_general_search(api)
    electronics = explore_electronics(api)
    cars = explore_cars(api)
    explore_regions(api)

    # Phase 2: field analysis per category
    if general:
        analyse_fields(general, "general iphone search")
    if electronics:
        analyse_fields(electronics, "electronics category")
    if cars:
        analyse_fields(cars, "cars search")

    # Phase 3: deep look at sample items
    if electronics:
        deep_dive(electronics, "electronics", n=2)
    if cars:
        deep_dive(cars, "cars", n=2)

    # Final hand-off summary
    print("\n" + "#" * 70)
    print("# Next steps")
    print("#" * 70)
    print(f"  1. Open files in {SAMPLES_DIR}/ and inspect them")
    print("  2. Note which fields are reliable enough for NOT NULL")
    print("  3. Note which fields are missing that we wanted (seller age etc)")
    print("  4. Share findings with the team before writing models.py")


if __name__ == "__main__":
    main()
"""
Check how much electronics ads vary in structure.

We've only looked at iPhones so far. This script searches for a
variety of electronics categories and compares which fields each
type of product carries.

If TVs, laptops, and headphones have wildly different attribute
fields, we know we can't put them in dedicated columns — they have
to go in a flexible JSON 'attributes' field.

Run with:
    python scripts/test_electronics_variety.py
"""

import json
from collections import Counter
from pathlib import Path

from blocket_api import BlocketAPI


# A spread of electronics search terms covering different product
# types likely to have different attribute sets
ELECTRONICS_QUERIES = [
    "iphone",  # phones — memory_size, brand
    "samsung tv",  # TVs — likely screen_size
    "macbook",  # laptops — cpu, ram, storage
    "playstation",  # consoles — different again
    "airpods",  # headphones — minimal attributes
    "ipad",  # tablets — similar to phones?
]


def collect_all_fields(items: list[dict]) -> tuple[Counter, dict[str, set]]:
    """Count which top-level fields appear and which extras IDs exist.

    Returns:
        (field_presence, extras_ids_per_query)
        Where extras_ids is the set of 'id' values found in the
        'extras' list — these are the category-specific attribute
        names.
    """
    presence: Counter = Counter()
    extras_ids: set[str] = set()

    for item in items:
        for key in item.keys():
            presence[key] += 1
        # The 'extras' list contains category-specific attributes,
        # each with an 'id' that names the attribute
        for extra in item.get("extras", []):
            if isinstance(extra, dict) and "id" in extra:
                extras_ids.add(extra["id"])

    return presence, extras_ids


def main() -> None:
    api = BlocketAPI()
    output_dir = Path(__file__).parent / "sample_data"
    output_dir.mkdir(exist_ok=True)

    # Track which extras IDs appear across all query types
    per_query_extras: dict[str, set[str]] = {}
    per_query_fields: dict[str, Counter] = {}

    for query in ELECTRONICS_QUERIES:
        print(f"\nSearching: '{query}'")
        try:
            response = api.search(query)
        except Exception as e:
            print(f"  ✗ failed: {e}")
            continue

        items = response.get("docs", [])
        if not items:
            print(f"  no results")
            continue

        # Save a sample for later
        sample_path = output_dir / f"variety_{query.replace(' ', '_')}.json"
        with sample_path.open("w", encoding="utf-8") as f:
            json.dump(items[:5], f, indent=2, ensure_ascii=False, default=str)

        fields, extras = collect_all_fields(items)
        per_query_fields[query] = fields
        per_query_extras[query] = extras

        print(f"  got {len(items)} items")
        print(f"  extras IDs found: {sorted(extras)}")

    # Compare: which fields are shared across ALL queries?
    if per_query_fields:
        print("\n" + "=" * 70)
        print("FIELD CONSISTENCY ACROSS ELECTRONICS")
        print("=" * 70)

        all_field_sets = [set(c.keys()) for c in per_query_fields.values()]
        always_present = set.intersection(*all_field_sets) if all_field_sets else set()
        any_present = set.union(*all_field_sets) if all_field_sets else set()
        sometimes_only = any_present - always_present

        print(
            f"\nFields present in ALL {len(per_query_fields)} queries ({len(always_present)}):"
        )
        for f in sorted(always_present):
            print(f"  ✓ {f}")

        print(f"\nFields present in only SOME queries ({len(sometimes_only)}):")
        for f in sorted(sometimes_only):
            queries_with = [q for q, fc in per_query_fields.items() if f in fc]
            print(f"  ~ {f:<25} ({', '.join(queries_with)})")

    # Compare: which category-specific attributes (extras) appear?
    print("\n" + "=" * 70)
    print("CATEGORY-SPECIFIC ATTRIBUTES (extras.id values)")
    print("=" * 70)

    all_extras: set[str] = set()
    for extras in per_query_extras.values():
        all_extras.update(extras)

    print(f"\nTotal unique attribute IDs across all electronics: {len(all_extras)}")
    print(f"\nAttribute ID per product type:")
    for query, extras in per_query_extras.items():
        print(f"  {query:<20} {sorted(extras)}")


if __name__ == "__main__":
    main()

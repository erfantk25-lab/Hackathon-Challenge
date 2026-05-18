"""
Sample the car search endpoint to see how its structure differs
from generic electronics search.

Cars have their own dedicated endpoint with structured filters
(year, mileage, transmission, etc) — they're likely a completely
different shape than recommerce ads.

Run with:
    python scripts/sample_cars.py
"""
import json
from pathlib import Path

from blocket_api import BlocketAPI, CarSortOrder


def main() -> None:
    api = BlocketAPI()

    print("Calling api.search_car('volvo')...")
    try:
        response = api.search_car(
            "volvo",
            sort_order=CarSortOrder.RELEVANCE,
            price_from=20_000,
            price_to=200_000,
        )
    except Exception as e:
        print(f"  failed with filters: {e}")
        print("  retrying without filters...")
        response = api.search_car("volvo")

    output_dir = Path(__file__).parent / "sample_data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "cars_volvo.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False, default=str)

    print(f"  ✓ saved to {output_path}")

    if isinstance(response, dict):
        print(f"  top-level keys: {list(response.keys())}")
        docs = response.get("docs", [])
        print(f"  got {len(docs)} car ads")

        if docs:
            first = docs[0]
            print(f"\n  Fields on first car:")
            for key in sorted(first.keys()):
                value = first[key]
                preview = str(value)[:60]
                print(f"    {key:<25} {type(value).__name__:<10} {preview}")


if __name__ == "__main__":
    main()
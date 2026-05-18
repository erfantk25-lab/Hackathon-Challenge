"""
Test that the parsers handle real Blocket data correctly.

Loads saved samples from earlier exploration and runs each doc
through the appropriate parser, printing what we extracted.
No database involved — purely tests parsing logic.

Run with:
    python scripts/test_parsing.py
"""

import json
import sys
from pathlib import Path

# Make src/ importable regardless of cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from src.services.parsing.cars import parse_car_listing
from src.services.parsing.electronics import parse_electronics_listing


SAMPLES_DIR = Path(__file__).parent / "sample_data"
ELECTRONICS_SAMPLE = SAMPLES_DIR / "smoke_test_iphone.json"
CARS_SAMPLE = SAMPLES_DIR / "cars_volvo.json"


def test_electronics() -> None:
    """Run the electronics parser against the iPhone sample."""
    print("\n" + "#" * 70)
    print("# ELECTRONICS")
    print("#" * 70)

    if not ELECTRONICS_SAMPLE.exists():
        print(f"Sample missing: {ELECTRONICS_SAMPLE}")
        return

    with ELECTRONICS_SAMPLE.open(encoding="utf-8") as f:
        response = json.load(f)

    docs = response.get("docs", [])
    print(f"Parsing {len(docs)} electronics listings...\n")

    errors = []
    for i, doc in enumerate(docs):
        try:
            parsed = parse_electronics_listing(doc)
            if i < 3:  # show first 3 in detail
                print(f"--- Listing {i + 1}: {parsed['heading'][:50]} ---")
                _print_key_fields(parsed)
        except Exception as e:
            errors.append((i, doc.get("ad_id"), type(e).__name__, str(e)))

    print(f"\nElectronics result: {len(docs) - len(errors)} / {len(docs)} parsed OK")
    if errors:
        print("Errors:")
        for i, ad_id, err_type, msg in errors[:5]:
            print(f"  doc[{i}] ad_id={ad_id}: {err_type}: {msg}")


def test_cars() -> None:
    """Run the car parser against the Volvo sample."""
    print("\n" + "#" * 70)
    print("# CARS")
    print("#" * 70)

    if not CARS_SAMPLE.exists():
        print(f"Sample missing: {CARS_SAMPLE}")
        return

    with CARS_SAMPLE.open(encoding="utf-8") as f:
        response = json.load(f)

    docs = response.get("docs", [])
    print(f"Parsing {len(docs)} car listings...\n")

    errors = []
    for i, doc in enumerate(docs):
        try:
            listing_dict, car_details_dict = parse_car_listing(doc)
            if i < 3:  # show first 3 in detail
                print(f"--- Listing {i + 1}: {listing_dict['heading'][:50]} ---")
                _print_key_fields(listing_dict)
                _print_car_details(car_details_dict)
        except Exception as e:
            errors.append((i, doc.get("ad_id"), type(e).__name__, str(e)))

    print(f"\nCars result: {len(docs) - len(errors)} / {len(docs)} parsed OK")
    if errors:
        print("Errors:")
        for i, ad_id, err_type, msg in errors[:5]:
            print(f"  doc[{i}] ad_id={ad_id}: {err_type}: {msg}")


def _print_key_fields(parsed: dict) -> None:
    """Print the most interesting fields of a parsed listing."""
    for key in [
        "blocket_id",
        "category",
        "price",
        "location",
        "seller_type",
        "organisation_name",
        "can_be_shipped",
        "buy_now_available",
        "posted_at",
    ]:
        print(f"  {key:<25} {parsed[key]}")
    print(f"  image_urls               ({len(parsed['image_urls'])} URLs)")


def _print_car_details(car: dict) -> None:
    """Print car-specific fields."""
    print(f"  --- car details ---")
    for key in [
        "make",
        "model",
        "year",
        "mileage",
        "fuel",
        "transmission",
        "regno",
        "dealer_segment",
    ]:
        print(f"  {key:<25} {car[key]}")
    print()


def main() -> None:
    test_electronics()
    test_cars()


if __name__ == "__main__":
    main()

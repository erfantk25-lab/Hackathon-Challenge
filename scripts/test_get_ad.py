"""
Test the get_ad endpoint to see what extra fields we get when
fetching a single ad in detail.

Background: api.search() returns lightweight cards meant for list
rendering. To get descriptions, seller info, and other heavy fields
we need to call api.get_ad() per listing.

Run with:
    python scripts/test_get_ad.py
"""
import json
from pathlib import Path

from blocket_api import BlocketAPI, RecommerceAd


def main() -> None:
    api = BlocketAPI()

    print("Running a quick search to get one ad to fetch in detail...")
    search_response = api.search("iphone")
    docs = search_response.get("docs", [])
    if not docs:
        print("  no search results, cannot continue")
        return

    first_ad = docs[0]
    ad_id = first_ad["ad_id"]
    print(f"  picked ad_id={ad_id} — '{first_ad['heading']}'")

    print("\nCalling api.get_ad() for detailed view...")
    try:
        # The signature wants a typed ad object. Try a few shapes —
        # we don't know yet whether it wants the dict, the ID, or
        # a constructed RecommerceAd instance.
        detail = None
        for attempt_name, attempt in [
            ("dict",      lambda: api.get_ad(first_ad)),
            ("id",        lambda: api.get_ad(ad_id)),
            ("ad_obj",    lambda: api.get_ad(RecommerceAd(ad_id))),
        ]:
            try:
                detail = attempt()
                print(f"  ✓ worked with {attempt_name} argument")
                break
            except Exception as e:
                print(f"  - {attempt_name} failed: {type(e).__name__}: {e}")

        if detail is None:
            print("  ✗ none of the argument shapes worked")
            return

    except Exception as e:
        print(f"  ✗ get_ad failed entirely: {e}")
        return

    # Save the response so we can study what fields it adds
    output_path = Path(__file__).parent / "sample_data" / "single_ad_detail.json"
    output_path.parent.mkdir(exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(detail, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  ✓ saved detail to {output_path}")

    # Compare which keys are new vs the search response
    search_keys = set(first_ad.keys())
    detail_keys = set(detail.keys()) if isinstance(detail, dict) else set()
    new_keys = detail_keys - search_keys

    print(f"\nFields in search result: {len(search_keys)}")
    print(f"Fields in detail result: {len(detail_keys)}")
    print(f"\nNew fields available only via get_ad():")
    for key in sorted(new_keys):
        value = detail.get(key) if isinstance(detail, dict) else None
        preview = str(value)[:80]
        print(f"  + {key:<25} {preview}")


if __name__ == "__main__":
    main()
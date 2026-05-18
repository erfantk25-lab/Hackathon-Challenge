"""
Inspect the structure of the get_ad response so we can find the
actual ad details inside it.

The response wraps real data in Remix/Next.js loaderData structures,
so we need to navigate into the tree to find description, body,
and any seller information.

Run with:
    python scripts/inspect_detail.py
"""
import json
from pathlib import Path
from typing import Any


SAMPLE_PATH = Path(__file__).parent / "sample_data" / "single_ad_detail.json"


def walk_structure(
    obj: Any,
    path: str = "",
    max_depth: int = 6,
    current_depth: int = 0,
) -> None:
    """Recursively print the shape of a nested structure.

    Shows keys with their value types, truncating long values so we
    can see the overall map without scrolling through megabytes of
    text. Lists show their length and the shape of the first element.
    """
    if current_depth >= max_depth:
        print(f"{path} ... (max depth)")
        return

    indent = "  " * current_depth

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key

            if isinstance(value, dict):
                print(f"{indent}{key}: dict({len(value)} keys)")
                walk_structure(value, new_path, max_depth, current_depth + 1)

            elif isinstance(value, list):
                print(f"{indent}{key}: list({len(value)})")
                if value and isinstance(value[0], (dict, list)):
                    walk_structure(value[0], f"{new_path}[0]", max_depth, current_depth + 1)
                elif value:
                    preview = str(value[0])[:60]
                    print(f"{indent}  [0]: {preview}")

            elif value is None:
                print(f"{indent}{key}: None")

            else:
                # Leaf value — show type and truncated preview
                type_name = type(value).__name__
                preview = str(value)
                if len(preview) > 80:
                    preview = preview[:77] + "..."
                print(f"{indent}{key}: ({type_name}) {preview}")


def find_keys(obj: Any, target_keys: set[str], path: str = "") -> dict[str, str]:
    """Search the entire nested structure for specific key names.

    Useful for finding where 'body', 'description', 'advertiser' etc
    live without knowing the path in advance.

    Returns a dict mapping each found key to its full dotted path.
    """
    found: dict[str, str] = {}

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            if key in target_keys and new_path not in found.values():
                found[new_path] = type(value).__name__
            sub_found = find_keys(value, target_keys, new_path)
            found.update(sub_found)

    elif isinstance(obj, list):
        for i, item in enumerate(obj[:3]):  # only check first 3 items
            new_path = f"{path}[{i}]"
            sub_found = find_keys(item, target_keys, new_path)
            found.update(sub_found)

    return found


def main() -> None:
    if not SAMPLE_PATH.exists():
        print(f"  no sample found at {SAMPLE_PATH}")
        print("  run test_get_ad.py first")
        return

    with SAMPLE_PATH.open(encoding="utf-8") as f:
        detail = json.load(f)

    print(f"File size: {SAMPLE_PATH.stat().st_size:,} bytes")
    print(f"Top-level keys: {list(detail.keys())}\n")

    # Step 1: visual map of the structure
    print("=" * 70)
    print("STRUCTURE MAP (depth 4)")
    print("=" * 70)
    walk_structure(detail, max_depth=4)

    # Step 2: search for fields we care about by name
    print("\n" + "=" * 70)
    print("HUNTING FOR KEY FIELDS")
    print("=" * 70)

    targets = {
        "body",
        "description",
        "advertiser",
        "account_id",
        "subject",
        "price",
        "list_time",
        "ad_id",
        "list_id",
        "zipcode",
        "company_ad",
        "phone_hidden",
        "params",
        "category",
    }

    found = find_keys(detail, targets)
    if found:
        print(f"\nFound {len(found)} matching paths:")
        for path, type_name in sorted(found.items()):
            print(f"  {type_name:<10} {path}")
    else:
        print("\nNo matches. Field names may be different in this response.")


if __name__ == "__main__":
    main()
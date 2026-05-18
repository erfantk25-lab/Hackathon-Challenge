"""
Discovery test: figure out what methods blocket_api actually exposes.

Since the package API doesn't match what we expected, this script
introspects the BlocketAPI class to find the right method names,
then tries to call them.

Run with:
    python scripts/quick_test.py
"""
import inspect
import json
from pathlib import Path


def main() -> None:
    print("Importing blocket_api...")
    from blocket_api import BlocketAPI
    print(f"  ✓ import works")

    # Show the package version if available
    try:
        import blocket_api
        version = getattr(blocket_api, "__version__", "unknown")
        print(f"  package version: {version}")
        print(f"  package location: {blocket_api.__file__}")
    except Exception as e:
        print(f"  (could not get version: {e})")

    print("\nIntrospecting BlocketAPI class...")
    api = BlocketAPI()

    # List all public methods (not starting with _)
    methods = [
        name for name in dir(api)
        if not name.startswith("_") and callable(getattr(api, name))
    ]
    print(f"  found {len(methods)} public methods:")
    for name in methods:
        method = getattr(api, name)
        try:
            sig = inspect.signature(method)
            print(f"    - api.{name}{sig}")
        except (ValueError, TypeError):
            print(f"    - api.{name}(?)")

    # List public attributes that aren't methods
    attrs = [
        name for name in dir(api)
        if not name.startswith("_") and not callable(getattr(api, name))
    ]
    if attrs:
        print(f"\n  public attributes: {attrs}")

    # Show what's importable from the top-level package
    print("\nWhat else is exported from blocket_api?")
    import blocket_api as pkg
    exports = [name for name in dir(pkg) if not name.startswith("_")]
    print(f"  {exports}")

    # Try the most likely method names automatically
    print("\nAttempting common search method names...")
    candidates = ["search", "search_ads", "find", "query", "get_listings"]
    response = None
    used_method = None

    for method_name in candidates:
        if hasattr(api, method_name):
            print(f"  trying api.{method_name}('iphone')...")
            try:
                method = getattr(api, method_name)
                response = method("iphone")
                used_method = method_name
                print(f"  ✓ success with api.{method_name}()")
                break
            except TypeError as e:
                # Method exists but wrong signature, try without args
                print(f"    needs different args: {e}")
                try:
                    response = method(query="iphone")
                    used_method = method_name
                    print(f"  ✓ success with api.{method_name}(query='iphone')")
                    break
                except Exception as e2:
                    print(f"    also failed: {e2}")
            except Exception as e:
                print(f"    failed: {type(e).__name__}: {e}")

    if response is None:
        print("\n  ✗ no working search method found.")
        print("  → Inspect the methods listed above and try one manually.")
        print(f"  → Or open the source: {pkg.__file__}")
        return

    # Save whatever we got
    output_dir = Path(__file__).parent / "sample_data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "smoke_test_iphone.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  ✓ saved response to {output_path}")
    print(f"  method used: api.{used_method}()")
    print(f"  response type: {type(response).__name__}")

    if isinstance(response, dict):
        print(f"  top-level keys: {list(response.keys())}")
    elif isinstance(response, list):
        print(f"  top-level list with {len(response)} items")


if __name__ == "__main__":
    main()
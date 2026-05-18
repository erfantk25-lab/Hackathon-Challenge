"""
End-to-end test of the database and embedding stack.

Inserts a sample listing with an embedding, queries it back via
semantic search, then cleans up.

Run from anywhere:
    python scripts/test_end_to_end.py
"""

import sys
from pathlib import Path

# Make src/ importable regardless of where this script is run from.
# scripts/ is a sibling of backend/, so we add backend/ to sys.path.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from datetime import datetime

from sqlalchemy import text

from src.db.core import SessionLocal
from src.db.models import Listing, ListingEmbedding
from src.services.embedding_service import embed_text, EMBEDDING_MODEL_NAME


def main() -> None:
    db = SessionLocal()

    try:
        # ── Step 1: insert a test listing ────────────────────────
        print("1. Inserting test listing...")
        test_listing = Listing(
            blocket_id="test_99999",
            category="electronics",
            heading="iPhone 14 Pro 256GB, fint skick",
            description="Säljes pga uppgradering. Helt fungerande, sparsamt använd.",
            price=7900,
            location="Stockholm",
            seller_type="private",
            image_urls=[],
            blocket_flags_raw=["private"],
            canonical_url="https://example.com/test",
            posted_at=datetime.utcnow(),
        )
        db.add(test_listing)
        db.flush()
        listing_id = test_listing.id
        print(f"   ✓ inserted with id={listing_id}")

        # ── Step 2: generate and store embedding ─────────────────
        print("\n2. Generating embedding (first run downloads ~500MB)...")
        text_to_embed = f"{test_listing.heading}\n{test_listing.description}"
        vector = embed_text(text_to_embed)
        print(f"   ✓ got vector of length {len(vector)}")

        embedding_row = ListingEmbedding(
            listing_id=listing_id,
            embedding=vector,
            model_name=EMBEDDING_MODEL_NAME,
        )
        db.add(embedding_row)
        db.commit()
        print(f"   ✓ saved to listing_embeddings")

        # ── Step 3: semantic search ──────────────────────────────
        print("\n3. Searching for 'pålitlig Apple-telefon i bra skick'...")
        query_vector = embed_text("pålitlig Apple-telefon i bra skick")

        results = db.execute(
            text("""
                SELECT
                    l.id,
                    l.heading,
                    e.embedding <=> CAST(:qvec AS vector) AS distance
                FROM listings l
                JOIN listing_embeddings e ON e.listing_id = l.id
                ORDER BY distance ASC
                LIMIT 5
            """),
            {"qvec": str(query_vector)},
        ).fetchall()

        print(f"   ✓ search returned {len(results)} results")
        for row in results:
            print(f"     id={row.id:<5} distance={row.distance:.4f}  {row.heading}")

        if results and results[0].distance < 0.5:
            print(f"\n   ✓ Good semantic match (distance < 0.5)")
        elif results:
            print(f"\n   ⚠ Distance is high ({results[0].distance:.4f})")

        # ── Step 4: cleanup ──────────────────────────────────────
        print("\n4. Cleaning up test data...")
        db.delete(test_listing)
        db.commit()
        print(f"   ✓ removed test listing")

        print("\n" + "=" * 50)
        print("✓ End-to-end test PASSED")
        print("=" * 50)

    except Exception as e:
        db.rollback()
        print(f"\n✗ Test FAILED: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()

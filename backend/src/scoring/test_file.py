from src.scoring.engine import score_ad
from src.schemas.ad import ListingBase
from decimal import Decimal
from datetime import datetime

# Normal legitimate ad
fake_ad = ListingBase(
    blocket_id="123456",
    category="electronics",
    heading="iPhone 14 Pro 256GB",
    description="Säljer en iPhone 14 Pro i mycket bra skick. Köpt för ett år sedan, inga repor. Kvitto finns.",
    price=Decimal("7500"),
    location="Stockholm",
    image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    seller_type="private",
)

# Scam ad
fake_scam = ListingBase(
    blocket_id="999999",
    category="electronics",
    heading="iPhone 14",
    description="Swish först så skickar jag. Förskott krävs. Kontakta via mail.",
    price=Decimal("100"),
    location=None,
    image_urls=[],
    seller_type="private",
)

if __name__ == "__main__":
    print("--- NORMAL AD ---")
    result = score_ad(fake_ad)
    print(f"Final score: {result.score}/10")
    print(f"Suspicious:  {result.is_suspicious}")
    for r in result.reasons:
        print(f"  {r['flag_type'].upper()}: {r['reason']}")

    print("\n--- SCAM AD ---")
    scam_result = score_ad(fake_scam)
    print(f"Final score: {scam_result.score}/10")
    print(f"Suspicious:  {scam_result.is_suspicious}")
    for r in scam_result.reasons:
        print(f"  {r['flag_type'].upper()}: {r['reason']}")
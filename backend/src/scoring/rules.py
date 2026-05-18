from dataclasses import dataclass

SUSPICIOUS_KEYWORDS = [
    "förskott", "western union", "swish först",
    "betala innan", "kontakta via mail", "utomlands",
    "ej avhämtning", "skickas mot betalning",
    "bankoverföring", "snabb affär", "måste sälja"
]

URGENCY_KEYWORDS = [
    "säljer snabbt", "första bud", "idag", 
    "måste bort", "akut", "sista chansen"
]

# Expected price ranges per category (min, max)
PRICE_RANGES = {
    "elektronik": (200, 80_000),
    "fordon":     (5_000, 800_000),
    "mobler":     (100, 50_000),
    "båtar":      (10_000, 500_000),
    "mc":         (5_000, 200_000),
}


@dataclass
class RuleResult:
    score: float          # 0.0 to 1.0
    reasons: list[dict]   # [{"reason": str, "flag_type": str, "source": str}]


def _make_reason(reason: str, flag_type: str) -> dict:
    return {
        "reason": reason,
        "flag_type": flag_type,   # 'positive', 'negative', 'warning'
        "source": "rules"
    }


def score_rules(ad) -> RuleResult:
    """
    Rule-based credibility scoring.
    Takes a blocket_api ad object, returns a RuleResult
    with a normalized score (0.0-1.0) and list of reasons.
    """
    points = 0
    max_points = 0
    reasons = []

    # ── Images ────────────────────────────────────────────────
    max_points += 2
    image_count = len(getattr(ad, "images", []) or [])

    if image_count >= 3:
        points += 2
        reasons.append(_make_reason(
            f"Flera bilder ({image_count} st)", "positive"
        ))
    elif image_count == 1:
        points += 1
        reasons.append(_make_reason(
            "Endast en bild", "warning"
        ))
    else:
        reasons.append(_make_reason(
            "Inga bilder uppladdade", "negative"
        ))

    # ── Description length ────────────────────────────────────
    max_points += 2
    body = getattr(ad, "body", "") or ""

    if len(body) > 150:
        points += 2
        reasons.append(_make_reason(
            "Utförlig beskrivning", "positive"
        ))
    elif len(body) > 50:
        points += 1
        reasons.append(_make_reason(
            "Kort beskrivning", "warning"
        ))
    else:
        reasons.append(_make_reason(
            "Mycket kort eller saknad beskrivning", "negative"
        ))

    # ── Location ──────────────────────────────────────────────
    max_points += 1
    if getattr(ad, "location", None):
        points += 1
        reasons.append(_make_reason(
            "Platsinformation finns", "positive"
        ))
    else:
        reasons.append(_make_reason(
            "Platsinformation saknas", "negative"
        ))

    # ── Price plausibility ────────────────────────────────────
    max_points += 2
    price = getattr(ad, "price", None)
    category = getattr(ad, "category", "").lower()
    price_range = PRICE_RANGES.get(category)

    if price is None or price == 0:
        reasons.append(_make_reason(
            "Pris saknas eller är 0", "negative"
        ))
    elif price_range:
        low, high = price_range
        if low <= price <= high:
            points += 2
            reasons.append(_make_reason(
                f"Rimligt pris för kategorin ({price:,} kr)", "positive"
            ))
        elif price < low * 0.5:
            reasons.append(_make_reason(
                f"Ovanligt lågt pris ({price:,} kr)", "negative"
            ))
        else:
            points += 1
            reasons.append(_make_reason(
                f"Pris något utanför förväntat intervall ({price:,} kr)", "warning"
            ))
    else:
        # No range defined for this category, give neutral points
        points += 1
        reasons.append(_make_reason(
            "Pris finns men kategori okänd", "warning"
        ))

    # ── Suspicious keywords ───────────────────────────────────
    max_points += 2
    body_lower = body.lower()
    hits = [kw for kw in SUSPICIOUS_KEYWORDS if kw in body_lower]

    if not hits:
        points += 2
        reasons.append(_make_reason(
            "Inga misstänkta nyckelord", "positive"
        ))
    elif len(hits) == 1:
        points += 1
        reasons.append(_make_reason(
            f"Misstänkt nyckelord hittades: '{hits[0]}'", "warning"
        ))
    else:
        reasons.append(_make_reason(
            f"Flera misstänkta nyckelord: {', '.join(hits)}", "negative"
        ))

    # ── Urgency keywords ──────────────────────────────────────
    max_points += 1
    urgency_hits = [kw for kw in URGENCY_KEYWORDS if kw in body_lower]

    if not urgency_hits:
        points += 1
        reasons.append(_make_reason(
            "Inget onödigt säljpressande språk", "positive"
        ))
    else:
        reasons.append(_make_reason(
            f"Säljpressande språk: {', '.join(urgency_hits)}", "warning"
        ))

    # ── Seller type ───────────────────────────────────────────
    max_points += 1
    seller = getattr(ad, "store", None)

    if seller:
        points += 1
        reasons.append(_make_reason(
            "Verifierad butik/företagssäljare", "positive"
        ))
    else:
        reasons.append(_make_reason(
            "Privatsäljare", "warning"
        ))

    # ── Normalize to 0.0 - 1.0 ───────────────────────────────
    normalized = points / max_points if max_points > 0 else 0.0

    return RuleResult(score=round(normalized, 3), reasons=reasons)
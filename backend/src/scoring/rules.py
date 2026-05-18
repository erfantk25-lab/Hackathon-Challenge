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

PRICE_RANGES = {
    "electronics": (200, 80_000),
    "cars":        (5_000, 800_000),
}


@dataclass
class RuleResult:
    score: float
    reasons: list[dict]


def _make_reason(reason: str, flag_type: str) -> dict:
    return {
        "reason": reason,
        "flag_type": flag_type,
        "source": "rules"
    }


def score_rules(ad) -> RuleResult:
    points = 0
    max_points = 0
    reasons = []

    # ── Images ────────────────────────────────────────────────
    # Skip image check for cars — API doesn't return image_urls for them
    category = getattr(ad, "category", "").lower()
    if category != "cars":
        max_points += 2
        image_count = len(getattr(ad, "image_urls", []) or [])

        if image_count >= 3:
            points += 2
            reasons.append(_make_reason(f"Flera bilder ({image_count} st)", "positive"))
        elif image_count == 1:
            points += 1
            reasons.append(_make_reason("Endast en bild", "warning"))
        else:
            reasons.append(_make_reason("Inga bilder uppladdade", "negative"))

    # ── Description ───────────────────────────────────────────
    body = getattr(ad, "description", "") or ""
    if body:
        max_points += 2
        if len(body) > 150:
            points += 2
            reasons.append(_make_reason("Utförlig beskrivning", "positive"))
        elif len(body) > 50:
            points += 1
            reasons.append(_make_reason("Kort beskrivning", "warning"))
        else:
            reasons.append(_make_reason("Mycket kort beskrivning", "negative"))

    # ── Location ──────────────────────────────────────────────
    max_points += 1
    if getattr(ad, "location", None):
        points += 1
        reasons.append(_make_reason("Platsinformation finns", "positive"))
    else:
        reasons.append(_make_reason("Platsinformation saknas", "negative"))

    # ── Price ─────────────────────────────────────────────────
    max_points += 2
    price = getattr(ad, "price", None)
    price_range = PRICE_RANGES.get(category)

    if price is None or price == 0:
        reasons.append(_make_reason("Pris saknas eller är 0", "negative"))
    elif price_range:
        low, high = price_range
        if low <= price <= high:
            points += 2
            reasons.append(_make_reason(f"Rimligt pris ({price:,} kr)", "positive"))
        elif price < low * 0.5:
            reasons.append(_make_reason(f"Ovanligt lågt pris ({price:,} kr)", "negative"))
        else:
            points += 1
            reasons.append(_make_reason(f"Pris utanför normalt intervall ({price:,} kr)", "warning"))
    else:
        points += 1
        reasons.append(_make_reason("Pris finns", "warning"))

    # ── Suspicious keywords ───────────────────────────────────
    if body:
        max_points += 2
        body_lower = body.lower()
        hits = [kw for kw in SUSPICIOUS_KEYWORDS if kw in body_lower]

        if not hits:
            points += 2
            reasons.append(_make_reason("Inga misstänkta nyckelord", "positive"))
        elif len(hits) == 1:
            points += 1
            reasons.append(_make_reason(f"Misstänkt nyckelord: '{hits[0]}'", "warning"))
        else:
            reasons.append(_make_reason(f"Flera misstänkta nyckelord: {', '.join(hits)}", "negative"))

        # ── Urgency ───────────────────────────────────────────
        max_points += 1
        urgency_hits = [kw for kw in URGENCY_KEYWORDS if kw in body_lower]
        if not urgency_hits:
            points += 1
            reasons.append(_make_reason("Inget säljpressande språk", "positive"))
        else:
            reasons.append(_make_reason(f"Säljpressande språk: {', '.join(urgency_hits)}", "warning"))

    # ── Seller type ───────────────────────────────────────────
    max_points += 1
    seller_type = getattr(ad, "seller_type", None)
    if seller_type == "company":
        points += 1
        reasons.append(_make_reason("Verifierad företagssäljare", "positive"))
    else:
        reasons.append(_make_reason("Privatsäljare", "warning"))

    # ── Normalize ─────────────────────────────────────────────
    normalized = points / max_points if max_points > 0 else 0.0
    return RuleResult(score=round(normalized, 3), reasons=reasons)
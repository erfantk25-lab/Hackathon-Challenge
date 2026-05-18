import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

st.set_page_config(layout="wide", page_title="Smart Sökning")

st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; color: #f7f7f8; }
    .block-container { padding-top: 2rem; max-width: 1180px; }
    .metric-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0 20px; }
    .metric-box { background: #171b22; border: 1px solid #2c3340; border-radius: 8px; padding: 14px 16px; }
    .metric-box small { color: #98a2b3; display: block; margin-bottom: 4px; }
    .metric-box strong { font-size: 24px; }
    .ad-card { background: #171b22; border: 1px solid #2c3340; border-left: 6px solid #22c55e; border-radius: 8px; padding: 16px 18px; margin-bottom: 12px; }
    .ad-card.warning { border-left-color: #f59e0b; }
    .ad-card.suspicious { border-left-color: #ef4444; background: #211719; }
    .ad-title { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
    .ad-title h3 { margin: 0; font-size: 19px; line-height: 1.25; }
    .ad-meta { color: #cbd5e1; margin: 8px 0 10px; }
    .trust-badge { white-space: nowrap; color: #05120a; font-weight: 800; padding: 4px 9px; border-radius: 999px; }
    .reason { color: #d0d5dd; margin: 4px 0 0; }
    .detail-box { background: #12161d; border: 1px solid #334155; border-radius: 8px; padding: 18px; margin: 14px 0 22px; }
    .detail-box h2 { margin-top: 0; font-size: 24px; }
    .detail-meta { color: #cbd5e1; margin-bottom: 12px; }
    .summary-box { background: #10201b; border: 1px solid #1f8f5f; border-radius: 8px; padding: 14px 16px; margin: 12px 0 18px; }
    .subtle { color: #98a2b3; }
    a { color: #86efac !important; }
</style>
""",
    unsafe_allow_html=True,
)


@dataclass
class SearchIntent:
    raw_prompt: str
    query: str
    category: str | None = None
    location: str | None = None
    max_price: int | None = None
    min_trust: int | None = None
    suspicious_only: bool = False


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY saknas i .env")
    return OpenAI(api_key=api_key)


def get_model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def json_from_text(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json\n", "", 1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return json.loads(text)


def ask_ai_for_intent(prompt: str) -> SearchIntent:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {
                "role": "system",
                "content": (
                    "You convert Swedish classified-ad search prompts into JSON. "
                    "Return only JSON with keys: query, category, location, max_price, "
                    "min_trust, suspicious_only. category must be electronics, cars, or null. "
                    "query must be short and usable in Blocket search. max_price and "
                    "min_trust are numbers or null. suspicious_only is boolean. "
                    "Remove subjective words like pålitlig, trygg, bra, billig from query. "
                    "If the user asks for a safe/trusted/reliable listing, set min_trust to 7. "
                    "If the user asks for suspicious/risky/scam listings, set suspicious_only true."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    parsed = json_from_text(response.choices[0].message.content or "{}")
    category = parsed.get("category")
    if category not in {"electronics", "cars", None}:
        category = None
    return SearchIntent(
        raw_prompt=prompt,
        query=str(parsed.get("query") or prompt).strip(),
        category=category,
        location=parsed.get("location") or None,
        max_price=to_int_or_none(parsed.get("max_price")),
        min_trust=to_int_or_none(parsed.get("min_trust")),
        suspicious_only=bool(parsed.get("suspicious_only", False)),
    )


def to_int_or_none(value: Any) -> int | None:
    if value in {None, "", "null"}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def extract_price(raw_price: Any) -> int:
    if isinstance(raw_price, dict):
        raw_price = (
            raw_price.get("amount")
            or raw_price.get("value")
            or raw_price.get("formatted")
            or 0
        )
    if isinstance(raw_price, str):
        raw_price = re.sub(r"[^0-9]", "", raw_price)
    try:
        return int(float(raw_price or 0))
    except (TypeError, ValueError):
        return 0


def extract_location(raw_location: Any) -> str:
    if isinstance(raw_location, dict):
        return (
            raw_location.get("name")
            or raw_location.get("region")
            or raw_location.get("municipality")
            or raw_location.get("display_name")
            or "Sverige"
        )
    if isinstance(raw_location, list) and raw_location:
        return extract_location(raw_location[0])
    return str(raw_location or "Sverige")


def extract_image_urls(raw: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.startswith("http"):
            urls.append(value)
        elif isinstance(value, dict):
            add(value.get("url") or value.get("uri"))
        elif isinstance(value, list):
            for item in value:
                add(item)

    add(raw.get("image_urls"))
    add(raw.get("images"))
    add(raw.get("image"))
    add(raw.get("thumbnail"))
    add(raw.get("thumbnail_url"))

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def normalize_api_ad(raw: dict[str, Any], category: str | None) -> dict[str, Any]:
    image_urls = extract_image_urls(raw)
    flags = raw.get("flags") or []
    ad_id = raw.get("ad_id") or raw.get("id")
    return {
        "id": str(ad_id or ""),
        "title": raw.get("heading") or raw.get("subject") or "Okand annons",
        "description": raw.get("body") or raw.get("description") or raw.get("text") or "",
        "price": extract_price(raw.get("price")),
        "location": extract_location(raw.get("location")),
        "category": category or "electronics",
        "url": raw.get("share_url") or raw.get("url") or raw.get("canonical_url") or "https://www.blocket.se/",
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "seller_type": "company" if "company" in str(flags).lower() else "private",
    }


def fetch_listing_detail(ad: dict[str, Any]) -> dict[str, Any]:
    if not ad.get("id"):
        return ad

    try:
        from blocket_api import BlocketAPI, RecommerceAd  # type: ignore

        detail = BlocketAPI().get_ad(RecommerceAd(int(ad["id"])))
    except Exception as exc:
        return {**ad, "detail_error": str(exc)}

    loader = detail.get("loaderData", {}) if isinstance(detail, dict) else {}
    page = loader.get("item-recommerce", {}) if isinstance(loader, dict) else {}
    item = page.get("itemData", {}) if isinstance(page, dict) else {}
    meta = page.get("meta", {}) if isinstance(page, dict) else {}

    detail_images = extract_image_urls(item)
    if isinstance(meta.get("image"), dict):
        detail_images.extend(extract_image_urls({"image": meta["image"]}))

    merged_images = []
    for url in [*detail_images, *ad.get("image_urls", [])]:
        if url and url not in merged_images:
            merged_images.append(url)

    extras = []
    for extra in item.get("extras", []) if isinstance(item, dict) else []:
        if isinstance(extra, dict) and extra.get("label") and extra.get("value"):
            extras.append(f"{extra['label']}: {extra['value']}")

    return {
        **ad,
        "title": item.get("title") or ad["title"],
        "description": item.get("description") or ad.get("description", ""),
        "price": extract_price(item.get("price")) or ad["price"],
        "location": extract_location(item.get("location")) if item.get("location") else ad["location"],
        "url": meta.get("canonical") or ad["url"],
        "image_urls": merged_images,
        "image_count": len(merged_images),
        "extras": extras,
        "detail_loaded": True,
    }


def fetch_real_ads(intent: SearchIntent) -> list[dict[str, Any]]:
    from blocket_api import BlocketAPI  # type: ignore

    api = BlocketAPI()
    if intent.category == "cars" and hasattr(api, "search_car"):
        response = api.search_car(intent.query or None, price_to=intent.max_price)
    elif hasattr(api, "search"):
        response = api.search(intent.query)
    else:
        raise RuntimeError("Kunde inte hitta api.search i blocket_api")

    docs = response.get("docs", []) if isinstance(response, dict) else response
    if not isinstance(docs, list):
        docs = []

    ads = [normalize_api_ad(doc, intent.category) for doc in docs[:30]]
    if intent.max_price:
        ads = [ad for ad in ads if not ad["price"] or ad["price"] <= intent.max_price]
    if intent.location:
        wanted = intent.location.lower()
        ads = [ad for ad in ads if wanted in ad["location"].lower()]
    return ads


def ask_ai_to_score(prompt: str, ads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if not ads:
        return [], "Inga liveannonser togs emot fran Blocket for den har prompten."

    client = get_openai_client()
    compact_ads = [
        {
            "index": index,
            "title": ad["title"],
            "description": ad["description"][:500],
            "price": ad["price"],
            "location": ad["location"],
            "category": ad["category"],
            "seller_type": ad["seller_type"],
            "image_count": ad["image_count"],
            "url": ad["url"],
        }
        for index, ad in enumerate(ads[:12])
    ]
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Swedish classified-ad risk analyst. Rank the real Blocket "
                    "listings against the user's prompt and estimate trust. Return only JSON: "
                    "{\"overall_comment\":\"short Swedish comment about the received result set\","
                    "\"results\":[{\"index\":0,\"trust\":1-10,\"match_score\":1-10,"
                    "\"reasons\":[\"short Swedish reason\"],\"match_reason\":\"short Swedish text\"}]}. "
                    "Use only the listing data provided. Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"prompt": prompt, "listings": compact_ads},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.2,
    )
    parsed = json_from_text(response.choices[0].message.content or "{}")
    overall_comment = str(
        parsed.get("overall_comment")
        or "AI analyserade annonserna men gav ingen separat sammanfattning."
    )
    by_index = {
        int(item["index"]): item
        for item in parsed.get("results", [])
        if isinstance(item, dict) and "index" in item
    }

    scored = []
    for index, ad in enumerate(ads[:12]):
        ai = by_index.get(index, {})
        trust = max(1, min(10, to_int_or_none(ai.get("trust")) or 5))
        match_score = max(1, min(10, to_int_or_none(ai.get("match_score")) or 5))
        reasons = ai.get("reasons") if isinstance(ai.get("reasons"), list) else []
        if not reasons:
            reasons = ["AI kunde inte hitta en tydlig motivering i svaret."]
        scored.append(
            {
                **ad,
                "trust": trust,
                "match_score": match_score,
                "match_reason": str(ai.get("match_reason") or ""),
                "reasons": [str(reason) for reason in reasons[:3]],
            }
        )
    scored.sort(key=lambda item: (-item["match_score"], -item["trust"], item["price"] or 0))
    return scored, overall_comment


def run_search(prompt: str) -> None:
    intent = ask_ai_for_intent(prompt)
    ads = fetch_real_ads(intent)
    scored_ads, result_comment = ask_ai_to_score(prompt, ads)
    if intent.min_trust:
        scored_ads = [ad for ad in scored_ads if ad["trust"] >= intent.min_trust]
    if intent.suspicious_only:
        scored_ads = [ad for ad in scored_ads if ad["trust"] <= 5]

    st.session_state.intent = intent
    st.session_state.ads = scored_ads
    st.session_state.raw_count = len(ads)
    st.session_state.result_comment = result_comment
    st.session_state.source = f"Live Blocket API + OpenAI {get_model_name()}"


if "ads" not in st.session_state:
    st.session_state.ads = []
if "source" not in st.session_state:
    st.session_state.source = "Ingen sokning an"
if "raw_count" not in st.session_state:
    st.session_state.raw_count = 0
if "result_comment" not in st.session_state:
    st.session_state.result_comment = ""
if "detail_cache" not in st.session_state:
    st.session_state.detail_cache = {}


def get_cached_detail(ad: dict[str, Any], index: int) -> dict[str, Any]:
    cache_key = ad.get("id") or str(index)
    if cache_key not in st.session_state.detail_cache:
        with st.spinner("Hamtar detaljer och bilder fran Blocket..."):
            st.session_state.detail_cache[cache_key] = fetch_listing_detail(ad)
    return st.session_state.detail_cache[cache_key]


@st.dialog("Annonsinfo")
def show_listing_dialog(index: int) -> None:
    if index < 0 or index >= len(st.session_state.ads):
        st.warning("Annonsen finns inte langre i resultatlistan.")
        return

    detail = get_cached_detail(st.session_state.ads[index], index)

    st.subheader(detail["title"])
    st.write(
        f"{detail['price']} kr | {detail['location']} | "
        f"trovärdighet {detail['trust']}/10 | match {detail['match_score']}/10"
    )

    image_urls = detail.get("image_urls", [])
    if image_urls:
        st.image(image_urls, width=260)
    else:
        st.info("Inga bilder kom med fran Blocket for den har annonsen.")

    st.write("**AI-bedömning**")
    st.write(detail.get("match_reason") or "AI-matchning baserad pa prompten.")
    for reason in detail.get("reasons", []):
        st.write(f"- {reason}")

    st.write("**Beskrivning**")
    st.write(detail.get("description") or "Ingen langre beskrivning hittades i Blocket-svaret.")

    if detail.get("extras"):
        st.write("**Extra annonsdata**")
        for extra in detail["extras"]:
            st.write(f"- {extra}")

    if detail.get("detail_error"):
        st.warning(f"Kunde inte hamta detaljsidan, visar sokresultatet: {detail['detail_error']}")

    st.link_button("öppna annonsen pa Blocket", detail.get("url") or "https://www.blocket.se/")


st.title("Smart Sokning pa Blocket")

with st.form("search_form"):
    prompt = st.text_input(
        "Prompt",
        "pålitlig iPhone under 10000 kr i Stockholm",
        help="Exempel: trygg pendlarbil under 80000 kr, misstänkta iPhones, MacBook med kvitto",
    )
    submitted = st.form_submit_button("Hamta annonser med AI")

if submitted:
    with st.spinner("Tolkar prompt, hamtar Blocket-annonser och analyserar med AI..."):
        try:
            run_search(prompt)
        except ImportError as exc:
            st.error(f"blocket_api saknas. Installera med: python3 -m pip install -r backend/requirements.txt ({exc})")
        except OpenAIError as exc:
            st.error(f"OpenAI-anropet misslyckades: {exc}")
        except Exception as exc:
            st.error(f"Sokningen misslyckades: {exc}")

intent = st.session_state.get("intent")
ads = st.session_state.ads
trusted = len([ad for ad in ads if ad["trust"] >= 7])
suspicious = len([ad for ad in ads if ad["trust"] <= 5])

if intent:
    if st.toggle("Visa AI-tolkning"):
        max_price_text = f"{intent.max_price:,} kr".replace(",", " ") if intent.max_price else "ingen"
        st.info(
            "AI-tolkat som: "
            f"sok='{intent.query}', kategori='{intent.category or 'alla'}', "
            f"plats='{intent.location or 'alla'}', maxpris='{max_price_text}', "
            f"misstankta='{intent.suspicious_only}'. Källa: {st.session_state.source}."
        )

st.markdown(
    f"""
<div class="metric-row">
  <div class="metric-box"><small>Liveannonser</small><strong>{st.session_state.raw_count}</strong></div>
  <div class="metric-box"><small>Visade resultat</small><strong>{len(ads)}</strong></div>
  <div class="metric-box"><small>Trygga annonser</small><strong>{trusted}</strong></div>
  <div class="metric-box"><small>Flaggade annonser</small><strong>{suspicious}</strong></div>
</div>
""",
    unsafe_allow_html=True,
)

if ads:
    best = ads[0]
    st.success(
        f"Basta AI-matchning: {best['title']} for {best['price']} kr "
        f"med trovärdighet {best['trust']}/10."
    )
elif intent:
    st.warning("Blocket gav inga annonser som matchade prompten och filtren.")

if st.session_state.result_comment:
    st.markdown(
        f"""
<div class="summary-box">
  <strong>AI-kommentar om mottagna resultat</strong>
  <p class="reason">{html.escape(st.session_state.result_comment)}</p>
</div>
""",
        unsafe_allow_html=True,
    )

for index, ad in enumerate(ads):
    trust = ad["trust"]
    css_class = "suspicious" if trust <= 5 else "warning" if trust <= 7 else ""
    badge_color = "#ef4444" if trust <= 5 else "#f59e0b" if trust <= 7 else "#22c55e"
    title = html.escape(ad["title"])
    location = html.escape(ad["location"])
    url = html.escape(ad.get("url") or "https://www.blocket.se/")
    reasons = "".join(f"<p class='reason'>- {html.escape(reason)}</p>" for reason in ad["reasons"])
    match_reason = html.escape(ad.get("match_reason") or "AI-matchning baserad pa prompten.")

    st.markdown(
        f"""
<div class="ad-card {css_class}">
  <div class="ad-title">
    <h3>{title}</h3>
    <span class="trust-badge" style="background:{badge_color};">{trust}/10</span>
  </div>
  <div class="ad-meta">{ad['price']} kr | {location} | {ad.get('seller_type', 'private')} | match {ad['match_score']}/10</div>
  <p class="reason">{match_reason}</p>
  {reasons}
  <p class="subtle"><a href="{url}" target="_blank">öppna pa Blocket</a></p>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("Info", key=f"details-{ad.get('id')}-{index}"):
        show_listing_dialog(index)

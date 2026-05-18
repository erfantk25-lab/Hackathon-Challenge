import streamlit as st
import random

# --- Konfiguration ---
st.set_page_config(layout="wide", page_title="Smart Sökning")

# --- CSS Design ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: white; }
    .ad-card { background-color: #1e1e24; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 6px solid #21c354; }
    .ad-card.suspicious { border-left: 6px solid #ff4b4b; background-color: #3b1c1c; }
    .trust-badge { font-weight: bold; padding: 2px 8px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- Logik: Trovärdighetsbedömning ---
def calculate_trust(title, price):
    trust = 10
    title_low = title.lower()
    
    if price < 2500 and price > 0: trust -= 6
    if "ny" in title_low or "obruten" in title_low or "kvitto" in title_low:
        if price < 4000: trust -= 3
    if "snabb affär" in title_low: trust -= 2
    
    return max(1, min(10, trust))

# --- UI ---
st.title("💠 Smart Sökning Blocket")
query = st.text_input("Sök annonser", "iPhone")

if 'ads' not in st.session_state: st.session_state.ads =[]

if st.button("▶ Starta sökning"):
    try:
        from blocket_api import BlocketAPI
        api = BlocketAPI()
        
        # Hämta data
        res = api.search(query) if hasattr(api, 'search') else api.custom_search(query)
        annonser = res["docs"] if isinstance(res, dict) and "docs" in res else (res if isinstance(res, list) else [])
        
        st.session_state.ads =[] 
        for r in annonser:
            raw_price = r.get("price", 0)
            price = raw_price.get("amount", 0) if isinstance(raw_price, dict) else raw_price
            title = r.get("heading", "Okänd annons")
            
            # Beräkna trovärdighet på riktigt!
            trust_score = calculate_trust(title, price)
            
            st.session_state.ads.append({
                "title": title,
                "price": price,
                "location": r.get("location", "Sverige"),
                "trust": trust_score
            })
    except Exception as e:
        st.error(f"API-fel: {e}")

if st.button("🗑️ Rensa"):
    st.session_state.ads =[]
    st.rerun()

# --- Rendera resultat ---
st.write(f"### Hittade annonser ({len(st.session_state.ads)})")

for ad in st.session_state.ads:
    is_suspicious = ad['trust'] < 5
    css_class = "ad-card suspicious" if is_suspicious else "ad-card"
    
    st.markdown(f"""
    <div class="{css_class}">
        <h3 style="margin:0;">{ad['title']}</h3>
        <p style="margin:0;">Pris: {ad['price']} kr | Plats: {ad['location']} | 
        <span class="trust-badge" style="background:{'#ff4b4b' if is_suspicious else '#21c354'}">
        Trovärdighet: {ad['trust']}/10</span></p>
    </div>
    """, unsafe_allow_html=True)
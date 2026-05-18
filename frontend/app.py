import streamlit as st
import pandas as pd
import numpy as np
import time
import datetime
import random

# --- Konfiguration ---
st.set_page_config(page_title="Smart Sökning Blocket", page_icon="💠", layout="wide")

try:
    from blocket_api import BlocketAPI
    API_AVAILABLE = True
except ImportError:
    BlocketAPI = None
    API_AVAILABLE = False

# --- Session State ---
if 'all_ads' not in st.session_state: st.session_state.all_ads =[]
if 'seen_ids' not in st.session_state: st.session_state.seen_ids = set()
if 'is_scanning' not in st.session_state: st.session_state.is_scanning = False
if 'api_hits' not in st.session_state: st.session_state.api_hits = 0

def parse_ad(ad):
    """Extraherar data oavsett format (dict eller objekt)."""
    try:
        def get_val(key, d):
            return ad.get(key, d) if isinstance(ad, dict) else getattr(ad, key, d)
        
        title = get_val("title", get_val("subject", "Okänd titel"))
        price = get_val("price", 0)
        if isinstance(price, dict): price = price.get("value", 0)
        elif hasattr(price, "value"): price = price.value
        
        return {
            "id": str(get_val("id", str(time.time()))),
            "title": str(title),
            "price": int(price) if str(price).isdigit() else 0,
            "location": str(get_val("location", "Sverige")),
            "description": str(get_val("body", get_val("description", ""))),
            "images": len(get_val("images",[])),
            "trust_score": round(random.uniform(1, 10), 1), # Simulera analys
            "is_suspicious": False
        }
    except: return None

# --- UI & CSS ---
st.markdown("""<style>
    .stApp { background-color: #121216; color: #ffffff; }
    .ad-card { background-color: #1e1e24; border: 1px solid #2a2a35; border-radius: 12px; padding: 15px; margin-bottom: 10px; }
    .kpi-card { background-color: #1c1c21; padding: 15px; border-radius: 8px; border: 1px solid #2a2a35; }
</style>""", unsafe_allow_html=True)

st.title("💠 Smart Sökning Blocket")
search_query = st.text_input("Sök annonser", "iPhone")

# --- Kontroller ---
col_sidebar1, col_sidebar2 = st.columns(2)
if col_sidebar1.button("▶ Starta"): st.session_state.is_scanning = True
if col_sidebar2.button("⏹ Stoppa"): st.session_state.is_scanning = False
use_mock = st.toggle("🛠️ Demo-läge", value=True)

# --- Logik ---
if st.session_state.is_scanning:
    # 1. API Anrop
    results = []
    if use_mock:
        results =[{"title": f"{search_query} {i}", "price": random.randint(1000, 9000), "id": str(random.random())} for i in range(2)]
        st.session_state.api_hits = 2
    elif API_AVAILABLE:
        try:
            api = BlocketAPI()
            # Försök hitta annonser
            raw = api.search(search_query) if hasattr(api, 'search') else api.custom_search(search_query)
            results = raw.data if hasattr(raw, 'data') else raw
            st.session_state.api_hits = len(results)
        except: st.error("API-fel")
    
    # 2. Parsa & Spara
    for r in results:
        ad = parse_ad(r)
        if ad and ad['id'] not in st.session_state.seen_ids:
            ad['is_suspicious'] = ad['price'] < 2000
            st.session_state.all_ads.append(ad)
            st.session_state.seen_ids.add(ad['id'])
            st.toast(f"Hittade: {ad['title']}")
            
    time.sleep(2)
    st.rerun()

# --- Visa Resultat ---
st.write(f"Hittade i API: {st.session_state.api_hits} st")
for ad in reversed(st.session_state.all_ads):
    color = "#fce8e8" if ad['is_suspicious'] else "#1e1e24"
    st.markdown(f"""<div class="ad-card" style="background-color: {color};">
        <h3 style="color: {'#991b1b' if ad['is_suspicious'] else '#ffffff'}">{ad['title']}</h3>
        <p>Pris: {ad['price']} kr | Trovärdighet: {ad['trust_score']}/10</p>
    </div>""", unsafe_allow_html=True)
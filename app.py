import streamlit as st
import google.generativeai as genai
import json
import re
from datetime import datetime

# ── Oldal konfiguráció ──────────────────────────────────────────────
st.set_page_config(
    page_title="Aquashop · Partner Scoring",
    page_icon="💧",
    layout="centered"
)

# ── CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.main { background: #060912; }
[data-testid="stAppViewContainer"] { background: #060912; }
[data-testid="stHeader"] { background: #060912; border-bottom: 1px solid #1c2a42; }

h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

.score-hero {
    background: linear-gradient(135deg, #0d1424, #121d30);
    border: 1px solid #1c2a42;
    border-radius: 16px;
    padding: 28px;
    margin: 16px 0;
    position: relative;
    overflow: hidden;
}
.score-hero::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #0055ff, #00d4ff, #00ffb3);
}
.tier-badge {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 26px;
    margin-bottom: 4px;
}
.score-big {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 56px;
    line-height: 1;
    background: linear-gradient(135deg, #00d4ff, #0055ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ratio-bar-container {
    background: #121d30;
    border: 1px solid #1c2a42;
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
}
.ratio-bar {
    height: 32px;
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    margin: 10px 0;
}
.seg { height: 100%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; color: rgba(0,0,0,0.75); transition: width 0.8s ease; white-space: nowrap; overflow: hidden; }
.seg-aq  { background: #00d4ff; }
.seg-al  { background: #f5c842; }
.seg-fl  { background: #ff6b35; }
.seg-neu { background: #8fa8c8; }

.brand-chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    margin: 3px;
}
.chip-aq  { background: rgba(0,212,255,0.15); color: #00d4ff; border: 1px solid rgba(0,212,255,0.3); }
.chip-al  { background: rgba(245,200,66,0.15); color: #f5c842; border: 1px solid rgba(245,200,66,0.3); }
.chip-fl  { background: rgba(255,107,53,0.15); color: #ff6b35; border: 1px solid rgba(255,107,53,0.3); }
.chip-neu { background: rgba(143,168,200,0.15); color: #8fa8c8; border: 1px solid rgba(143,168,200,0.3); }

.dim-row {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; border-bottom: 1px solid #1c2a42;
    font-size: 13px;
}
.ev-card {
    background: #121d30; border: 1px solid #1c2a42;
    border-radius: 10px; padding: 14px; margin: 6px 0;
}
.ev-title { font-size: 11px; color: #4a6080; margin-bottom: 6px; }
.rec-box {
    background: #121d30; border: 1px solid #243350;
    border-radius: 12px; padding: 18px; margin: 12px 0;
}
.section-label {
    font-family: 'Syne', sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 2px; text-transform: uppercase;
    color: #00d4ff; margin: 20px 0 10px;
}
</style>
""", unsafe_allow_html=True)

# ── Márkaadatbázis ───────────────────────────────────────────────────
BRAND_DB = {
    "aquashop": {
        "label": "Aquashop",
        "color": "#00d4ff",
        "chip": "chip-aq",
        "brands": [
            "Fairland", "InverPro", "Inver-X", "WarriorX", "Inverter Pro",
            "Maytronics", "Dolphin", "Liberty",
            "Saci",
            "Gemas",
            "Microdos", "BSV", "BSV Touch",
            "Sopremapool", "Flagpool",
            "Hidroten", "Nature Works", "Aquajet"
        ]
    },
    "aqualing": {
        "label": "Aqualing",
        "color": "#f5c842",
        "chip": "chip-al",
        "brands": [
            "Pontaqua", "PoolTrend", "Pooltrend", "Dekortrend",
            "Bestway", "Intex", "Kokido",
            "Hydro Force", "HydroForce", "Gladiator SUP", "Gladiator",
            "Wellis", "VitalSpa", "Azton", "Wattsup"
        ]
    },
    "fluidra": {
        "label": "Fluidra-Kerex",
        "color": "#ff6b35",
        "chip": "chip-fl",
        "brands": [
            "Astralpool", "AstralPool", "Astral Pool", "Astral",
            "Zodiac", "Bayrol", "GRE", "Gre",
            "Pahlen", "Speck", "ZDS", "Kripsol",
            "Fluidra", "Kerex", "iAquaLink", "Glass Water Systems", "Omniflex"
        ]
    }
}

ALL_BRANDS_LIST = ", ".join(
    b for data in BRAND_DB.values() for b in data["brands"]
)

SYSTEM_PROMPT = f"""Te egy Aquashop viszonteladói webshop elemző vagy. Az Aquashop egy magyarországi medence és spa nagykereskedő.

ISMERT MÁRKAADATBÁZIS:
AQUASHOP márkák: {", ".join(BRAND_DB["aquashop"]["brands"])}
AQUALING márkák: {", ".join(BRAND_DB["aqualing"]["brands"])}
FLUIDRA-KEREX márkák: {", ".join(BRAND_DB["fluidra"]["brands"])}

FELADATOD:
1. Keresd fel a megadott webshopot (Google Search segítségével)
2. Azonosítsd az összes terméket és márkát a kínálatban
3. Sorolj minden megtalált márkát a fenti adatbázis alapján
4. Ha egy márka nem szerepel az adatbázisban, az "egyeb" kategóriába kerül

ÉRTÉKELÉSI DIMENZIÓK (max pontszámok):
- exkluziv_termekek (max 40): Aquashop-specifikus márkák száma és jelenléte, dedikált kategóriák
- kinalat_teljessege (max 25): A medence/spa termékkör mélysége összességében
- tartalmi_minoseg (max 20): Leírások részletessége, képek, műszaki adatok
- webshop_aktivitas (max 10): Frissesség, aktív árak, készletinfo
- seo_elkotelezettsege (max 5): Kulcsszó-optimalizáltság

Válaszolj KIZÁRÓLAG valid JSON-ban, semmi más szöveg, magyarázat nélkül:
{{
  "domain": "string",
  "partner_neve": "string",
  "scores": {{
    "exkluziv_termekek": 0,
    "kinalat_teljessege": 0,
    "tartalmi_minoseg": 0,
    "webshop_aktivitas": 0,
    "seo_elkotelezettsege": 0
  }},
  "total": 0,
  "tier": "PLATINUM|GOLD|SILVER|BASIC|INAKTÍV",
  "osszefoglalo": "string 2-3 mondat",
  "markak": {{
    "aquashop": ["márkanév1"],
    "aqualing": ["márkanév1"],
    "fluidra": ["márkanév1"],
    "egyeb": ["márkanév1"]
  }},
  "markaok_szama": {{
    "aquashop": 0,
    "aqualing": 0,
    "fluidra": 0,
    "egyeb": 0
  }},
  "bizonyitekok": {{
    "talalt_termekek": "string",
    "kinalat_szelessege": "string",
    "tartalom_minosege": "string",
    "aktivitas_frissesseg": "string"
  }},
  "javasolt_teendok": "string"
}}"""

# ── Tier konfig ──────────────────────────────────────────────────────
TIER_CONFIG = {
    "PLATINUM": {"emoji": "🥇", "color": "#00d4ff", "label": "PLATINUM Partner"},
    "GOLD":     {"emoji": "🥈", "color": "#f5c842", "label": "GOLD Partner"},
    "SILVER":   {"emoji": "🥉", "color": "#8fa8c8", "label": "SILVER Partner"},
    "BASIC":    {"emoji": "⚠️", "color": "#ff8c38", "label": "BASIC Partner"},
    "INAKTÍV":  {"emoji": "🔴", "color": "#ff4455", "label": "INAKTÍV"},
}

DIM_DEFS = [
    ("exkluziv_termekek",    "Aquashop exkluzív termékek", 40),
    ("kinalat_teljessege",   "Kínálat teljessége",         25),
    ("tartalmi_minoseg",     "Tartalmi minőség",           20),
    ("webshop_aktivitas",    "Aktivitás & frissesség",     10),
    ("seo_elkotelezettsege", "SEO elkötelezettsége",        5),
]

# ── Session state ────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Header ───────────────────────────────────────────────────────────
st.markdown("""
<div style='display:flex;align-items:center;gap:12px;padding:8px 0 24px'>
  <div style='width:36px;height:36px;background:linear-gradient(135deg,#00d4ff,#0055ff);border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Syne;font-weight:800;font-size:16px;color:#fff'>A</div>
  <div>
    <span style='font-family:Syne;font-weight:700;font-size:18px;color:#dce8f5'>Aquashop</span>
    <span style='color:#4a6080;font-size:14px'> / Partner Scoring</span>
  </div>
  <div style='margin-left:auto;font-size:10px;letter-spacing:1px;color:#00d4ff;background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);border-radius:4px;padding:3px 8px'>AI · GEMINI</div>
</div>
""", unsafe_allow_html=True)

# ── API kulcs ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Gemini API kulcs")
    st.markdown("""
Ingyenes kulcs szerzése:
1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. **Create API key**
3. Másold be ↓
    """)
    api_key = st.text_input("API kulcs", type="password", placeholder="AIzaSy...",
                             value=st.session_state.get("api_key", ""))
    if api_key:
        st.session_state.api_key = api_key
        st.success("✓ Kulcs beállítva")

    st.divider()
    st.markdown("### 📋 Márkaadatbázis")
    for src, data in BRAND_DB.items():
        with st.expander(f"{data['label']} ({len(data['brands'])} márka)"):
            st.write(", ".join(data["brands"]))

# ── Fő tartalom ──────────────────────────────────────────────────────
st.markdown("<h1 style='font-family:Syne;font-size:32px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Domain → Márkaösszetétel</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#4a6080;margin-bottom:24px'>Add meg a webshop címét – az AI felkeresi, azonosítja a márkákat és elkészíti az elkötelezettségi scorecard-ot.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([4, 1])
with col1:
    domain_input = st.text_input("", placeholder="pl. medencefutar.hu", label_visibility="collapsed")
with col2:
    scan_btn = st.button("Elemzés →", type="primary", use_container_width=True)

# ── Elemzés ──────────────────────────────────────────────────────────
if scan_btn and domain_input:
    if not st.session_state.get("api_key"):
        st.error("⚠️ Először add meg a Gemini API kulcsot a bal oldali sávban!")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    try:
        from urllib.parse import urlparse
        parsed = urlparse(raw)
        domain = parsed.netloc.replace("www.", "")
        full_url = raw
    except:
        st.error("Érvénytelen URL!")
        st.stop()

    # Gemini konfiguráció
    genai.configure(api_key=st.session_state.api_key)

    with st.status(f"🤖 Elemzés folyamatban: {domain}...", expanded=True) as status:
        st.write("🔍 Webshop felkeresése és tartalom elemzése...")

        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                tools="google_search_retrieval"
            )

            prompt = f"""{SYSTEM_PROMPT}

Elemzendő webshop: {full_url}

Keresd fel a webshopot, azonosítsd az összes terméket és márkát.
Különösen keresd ezeket: {ALL_BRANDS_LIST}
Válaszolj KIZÁRÓLAG JSON-ban."""

            st.write("📊 Aquashop vs. konkurens márkák azonosítása...")
            response = model.generate_content(prompt)
            raw_text = response.text

            st.write("⚡ Pontszámok kiszámítása...")

            # JSON kinyerése
            clean = re.sub(r'```json|```', '', raw_text).strip()
            json_match = re.search(r'\{[\s\S]*\}', clean)
            if not json_match:
                raise ValueError("Nem érkezett JSON válasz az AI-tól.")
            result = json.loads(json_match.group())

            status.update(label="✅ Elemzés kész!", state="complete")

        except Exception as e:
            status.update(label=f"❌ Hiba", state="error")
            st.error(f"Hiba: {str(e)}")
            st.stop()

    # ── Eredmény megjelenítése ────────────────────────────────────────
    total = min(100, max(0, int(result.get("total", 0))))
    tier_key = result.get("tier", "INAKTÍV")
    tier = TIER_CONFIG.get(tier_key, TIER_CONFIG["INAKTÍV"])

    # Score hero
    st.markdown(f"""
    <div class="score-hero">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div class="score-big">{total}</div>
        <div>
          <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
          <div style="font-size:12px;color:#4a6080;font-family:monospace">{result.get('partner_neve', domain)} · {domain}</div>
          <div style="font-size:13px;color:#8fa8c8;margin-top:6px;max-width:480px">{result.get('osszefoglalo', '')}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Márka arány ──────────────────────────────────────────────────
    st.markdown('<div class="section-label">▸ Márkaösszetétel & versenytárs arány</div>', unsafe_allow_html=True)

    mc = result.get("markaok_szama", {})
    aq  = int(mc.get("aquashop", 0))
    al  = int(mc.get("aqualing", 0))
    fl  = int(mc.get("fluidra",  0))
    neu = int(mc.get("egyeb",    0))
    total_brands = max(aq + al + fl + neu, 1)

    aq_pct  = round(aq  / total_brands * 100)
    al_pct  = round(al  / total_brands * 100)
    fl_pct  = round(fl  / total_brands * 100)
    neu_pct = 100 - aq_pct - al_pct - fl_pct

    def seg(pct, cls, label):
        if pct < 1:
            return ""
        text = f"{pct}%" if pct > 7 else ""
        return f'<div class="seg {cls}" style="width:{pct}%">{text}</div>'

    bar_html = f"""
    <div class="ratio-bar-container">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:13px">
        <span style="color:#00d4ff;font-weight:700">Aquashop {aq_pct}% ({aq} márka)</span>
        <span style="color:#f5c842;font-weight:700">Aqualing {al_pct}% ({al} márka)</span>
        <span style="color:#ff6b35;font-weight:700">Fluidra-Kerex {fl_pct}% ({fl} márka)</span>
        <span style="color:#8fa8c8;font-weight:700">Egyéb {neu_pct}% ({neu} márka)</span>
      </div>
      <div class="ratio-bar">
        {seg(aq_pct, 'seg-aq', 'Aquashop')}
        {seg(al_pct, 'seg-al', 'Aqualing')}
        {seg(fl_pct, 'seg-fl', 'Fluidra')}
        {seg(neu_pct, 'seg-neu', 'Egyéb')}
      </div>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)

    # Márka chipek
    markak = result.get("markak", {})
    chips_html = ""
    for src, chip_cls in [("aquashop","chip-aq"),("aqualing","chip-al"),("fluidra","chip-fl"),("egyeb","chip-neu")]:
        for b in markak.get(src, []):
            chips_html += f'<span class="brand-chip {chip_cls}">{b}</span>'
    if chips_html:
        st.markdown(f'<div style="margin:10px 0"><div style="font-size:11px;color:#4a6080;margin-bottom:6px">AZONOSÍTOTT MÁRKÁK</div>{chips_html}</div>', unsafe_allow_html=True)

    # ── Dimenzió bontás ──────────────────────────────────────────────
    st.markdown('<div class="section-label">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    scores = result.get("scores", {})
    for key, label, max_pts in DIM_DEFS:
        pts = int(scores.get(key, 0))
        pct = int(pts / max_pts * 100)
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.markdown(f"<div style='font-size:13px;color:#8fa8c8;margin-bottom:2px'>{label}</div>", unsafe_allow_html=True)
            st.progress(pct / 100)
        with col_b:
            st.markdown(f"<div style='font-size:13px;font-weight:700;text-align:right;padding-top:4px'>{pts} / {max_pts}</div>", unsafe_allow_html=True)

    # ── Bizonyítékok ─────────────────────────────────────────────────
    biz = result.get("bizonyitekok", {})
    if any(biz.values()):
        st.markdown('<div class="section-label">▸ Elemzési bizonyítékok</div>', unsafe_allow_html=True)
        ev_items = [
            ("Talált termékek",        biz.get("talalt_termekek", "")),
            ("Kínálat szélessége",     biz.get("kinalat_szelessege", "")),
            ("Tartalom minősége",      biz.get("tartalom_minosege", "")),
            ("Aktivitás & frissesség", biz.get("aktivitas_frissesseg", "")),
        ]
        col1, col2 = st.columns(2)
        for i, (title, text) in enumerate(ev_items):
            if text:
                with (col1 if i % 2 == 0 else col2):
                    st.markdown(f"""
                    <div class="ev-card">
                      <div class="ev-title">{title}</div>
                      <div style="font-size:12px;color:#dce8f5">{text}</div>
                    </div>""", unsafe_allow_html=True)

    # ── Javaslatok ───────────────────────────────────────────────────
    st.markdown('<div class="section-label">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="rec-box">
      <div style="font-size:13px;color:#dce8f5;line-height:1.7">{result.get('javasolt_teendok', '').replace(chr(10), '<br>')}</div>
    </div>
    """, unsafe_allow_html=True)

    # Mentés history-ba
    st.session_state.history.insert(0, {
        "domain": domain,
        "partner": result.get("partner_neve", domain),
        "total": total,
        "tier": tier_key,
        "aq_pct": aq_pct,
        "date": datetime.now().strftime("%Y.%m.%d"),
        "result": result
    })

    st.divider()
    st.button("← Új elemzés", on_click=lambda: None)

# ── Előzmények ───────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="section-label">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    tier_colors = {"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1: st.markdown(f"<span style='font-size:13px'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#00d4ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:{tier_colors.get(h['tier'],'#fff')};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#4a6080;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)

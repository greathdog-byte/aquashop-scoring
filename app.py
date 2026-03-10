import streamlit as st
from google import genai
from google.genai import types
import json
import re
from datetime import datetime

def gemini_call(client, prompt, use_search=False, retries=2):
    """Gemini hívás több modellel és újrapróbálkozással."""
    import time
    MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    cfg_args = {"temperature": 0.1, "max_output_tokens": 2500}
    if use_search:
        cfg_args["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    last_error = ""
    for model in MODELS:
        for attempt in range(retries):
            try:
                return client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**cfg_args)
                )
            except Exception as e:
                err = str(e)
                last_error = err
                if "503" in err or "UNAVAILABLE" in err:
                    if attempt < retries - 1:
                        time.sleep(10)
                        continue
                elif "429" in err or "RESOURCE_EXHAUSTED" in err:
                    break  # kvóta limit - próbáljuk a következő modellt
                elif "404" in err or "NOT_FOUND" in err:
                    break  # modell nem elérhető - következő
                else:
                    raise e
    raise Exception(f"Minden modell elérhetetlen. Utolsó hiba: {last_error}")

st.set_page_config(page_title="Aquashop · Partner Scoring", page_icon="💧", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: #e8f0fe; }
[data-testid="stAppViewContainer"] { background: #060912; color: #e8f0fe; }
[data-testid="stHeader"] { background: #060912; border-bottom: 1px solid #1c2a42; }
[data-testid="stSidebar"] { background: #0d1424; }
[data-testid="stSidebar"] * { color: #c8d8f0 !important; }
p, span, div, label { color: #c8d8f0; }
.stMarkdown p { color: #c8d8f0; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; color: #ffffff; }
input { background: #121d30 !important; color: #e8f0fe !important; border-color: #243350 !important; }
.stTextInput input { color: #e8f0fe !important; }
.score-hero { background: linear-gradient(135deg,#0d1424,#121d30); border: 1px solid #2a3f5a; border-radius: 16px; padding: 28px; margin: 16px 0; position: relative; overflow: hidden; }
.score-hero::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg,#0055ff,#00d4ff,#00ffb3); }
.score-big { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 56px; line-height: 1; background: linear-gradient(135deg,#00d4ff,#0055ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.tier-badge { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 26px; margin-bottom: 4px; }
.ratio-bar-container { background: #0d1830; border: 1px solid #2a3f5a; border-radius: 12px; padding: 20px; margin: 12px 0; }
.ratio-bar { height: 32px; border-radius: 10px; overflow: hidden; display: flex; margin: 10px 0; }
.seg { height: 100%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; color: rgba(0,0,0,0.8); white-space: nowrap; overflow: hidden; }
.seg-aq { background: #00d4ff; } .seg-al { background: #f5c842; } .seg-fl { background: #ff6b35; } .seg-neu { background: #8fa8c8; }
.brand-chip { display: inline-block; padding: 4px 11px; border-radius: 20px; font-size: 12px; font-weight: 600; margin: 3px; }
.chip-aq { background: rgba(0,212,255,0.18); color: #5ee8ff; border: 1px solid rgba(0,212,255,0.4); }
.chip-al { background: rgba(245,200,66,0.18); color: #fdd835; border: 1px solid rgba(245,200,66,0.4); }
.chip-fl { background: rgba(255,107,53,0.18); color: #ff8c5a; border: 1px solid rgba(255,107,53,0.4); }
.chip-neu { background: rgba(180,200,230,0.15); color: #b4c8e6; border: 1px solid rgba(180,200,230,0.3); }
.ev-card { background: #0d1830; border: 1px solid #2a3f5a; border-radius: 10px; padding: 14px; margin: 6px 0; }
.ev-title { font-size: 11px; color: #7a9fc0; margin-bottom: 6px; font-weight: 600; }
.ev-card div { color: #d0e4f8 !important; }
.rec-box { background: #0d1830; border: 1px solid #2a3f5a; border-radius: 12px; padding: 18px; margin: 12px 0; }
.rec-box div { color: #d0e4f8 !important; }
.section-label { font-family: 'Syne', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #00d4ff; margin: 20px 0 10px; }
</style>
""", unsafe_allow_html=True)

# ── Márkaadatbázis ───────────────────────────────────────────────────
BRAND_DB = {
    "aquashop": {
        "label": "Aquashop", "color": "#00d4ff", "chip": "chip-aq",
        "brands": ["Fairland","InverPro","Inver-X","WarriorX","Maytronics","Dolphin","Liberty","Saci","Gemas","Microdos","BSV","BSV Touch","Sopremapool","Flagpool","Hidroten","Nature Works","Aquajet"]
    },
    "aqualing": {
        "label": "Aqualing", "color": "#f5c842", "chip": "chip-al",
        "brands": ["Pontaqua","PoolTrend","Dekortrend","Bestway","Intex","Kokido","Hydro Force","HydroForce","Gladiator","Gladiator SUP","Wellis","VitalSpa","Azton","Wattsup"]
    },
    "fluidra": {
        "label": "Fluidra-Kerex", "color": "#ff6b35", "chip": "chip-fl",
        "brands": ["Astralpool","AstralPool","Astral","Zodiac","Bayrol","GRE","Pahlen","Speck","ZDS","Kripsol","Fluidra","Kerex","iAquaLink","Omniflex"]
    }
}

ALL_BRANDS_LIST = ", ".join(b for d in BRAND_DB.values() for b in d["brands"])

SYSTEM_PROMPT = f"""Te egy Aquashop viszonteladói webshop elemző vagy. Az Aquashop egy magyarországi medence és spa nagykereskedő.

FELADATOD: Elemezd a megadott webshopot és azonosítsd az összes márkát.

MÁRKAADATBÁZIS:
AQUASHOP márkák (Aquashop Kft. által forgalmazott): {", ".join(BRAND_DB["aquashop"]["brands"])}
AQUALING márkák (konkurens nagykereskedő): {", ".join(BRAND_DB["aqualing"]["brands"])}
FLUIDRA-KEREX márkák (konkurens nagykereskedő): {", ".join(BRAND_DB["fluidra"]["brands"])}

KERESÉSI MÓDSZER:
- Végezz több Google keresést a webshopban
- Keresd a termékoldalakat, kategóriákat, márkalistákat
- Minden egyes márkát ellenőrizz a fenti listákban
- Ha egy márka bármilyen formában szerepel (pl. "InverPro szivattyú", "Fairland hőszivattyú") → add a megfelelő listába

PONTOZÁS:
- exkluziv_termekek (max 40 pont):
  * 0 Aquashop márka = 0 pont
  * 1-2 Aquashop márka = 10 pont
  * 3-4 Aquashop márka = 20 pont
  * 5-7 Aquashop márka = 30 pont
  * 8+ Aquashop márka = 40 pont
- kinalat_teljessege (max 25): széles medence/spa kínálat = magasabb pont
- tartalmi_minoseg (max 20): részletes leírások, sok kép, műszaki adatok
- webshop_aktivitas (max 10): naprakész árak, készletjelzés, friss tartalom
- seo_elkotelezettsege (max 5): kulcsszavak a terméknevekben és leírásokban

TIER BESOROLÁS: 85-100=PLATINUM, 65-84=GOLD, 40-64=SILVER, 20-39=BASIC, 0-19=INAKTÍV

Válaszolj KIZÁRÓLAG valid JSON-ban, kód blokk nélkül:
{{"domain":"string","partner_neve":"string","scores":{{"exkluziv_termekek":0,"kinalat_teljessege":0,"tartalmi_minoseg":0,"webshop_aktivitas":0,"seo_elkotelezettsege":0}},"total":0,"tier":"PLATINUM|GOLD|SILVER|BASIC|INAKTÍV","osszefoglalo":"2-3 mondatos magyar összefoglaló","markak":{{"aquashop":["talált aquashop márkák"],"aqualing":["talált aqualing márkák"],"fluidra":["talált fluidra márkák"],"egyeb":["egyéb márkák"]}},"markaok_szama":{{"aquashop":0,"aqualing":0,"fluidra":0,"egyeb":0}},"bizonyitekok":{{"talalt_termekek":"konkrét márkák és termékek amiket találtál","kinalat_szelessege":"milyen termékkategóriák vannak","tartalom_minosege":"leírások és képek minősége","aktivitas_frissesseg":"árak és készlet állapota"}},"javasolt_teendok":"konkrét fejlesztési javaslatok"}}"""

TIER_CONFIG = {
    "PLATINUM": {"emoji": "🥇", "color": "#00d4ff", "label": "PLATINUM Partner"},
    "GOLD":     {"emoji": "🥈", "color": "#f5c842", "label": "GOLD Partner"},
    "SILVER":   {"emoji": "🥉", "color": "#8fa8c8", "label": "SILVER Partner"},
    "BASIC":    {"emoji": "⚠️", "color": "#ff8c38", "label": "BASIC Partner"},
    "INAKTÍV":  {"emoji": "🔴", "color": "#ff4455", "label": "INAKTÍV"},
}
DIM_DEFS = [
    ("exkluziv_termekek","Aquashop exkluzív termékek",40),
    ("kinalat_teljessege","Kínálat teljessége",25),
    ("tartalmi_minoseg","Tartalmi minőség",20),
    ("webshop_aktivitas","Aktivitás & frissesség",10),
    ("seo_elkotelezettsege","SEO elkötelezettsége",5),
]

if "history" not in st.session_state:
    st.session_state.history = []

# API kulcs - Streamlit secrets-ből
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        pass
    import os
    return os.environ.get("GEMINI_API_KEY", "")

if "api_key" not in st.session_state:
    st.session_state.api_key = get_api_key()

# ── Header ───────────────────────────────────────────────────────────
st.markdown("""<div style='display:flex;align-items:center;gap:12px;padding:8px 0 24px'>
  <div style='width:36px;height:36px;background:linear-gradient(135deg,#00d4ff,#0055ff);border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Syne;font-weight:800;font-size:16px;color:#fff'>A</div>
  <span style='font-family:Syne;font-weight:700;font-size:18px;color:#dce8f5'>Aquashop <span style='color:#4a6080;font-weight:400'>/ Partner Scoring</span></span>
  <div style='margin-left:auto;font-size:10px;letter-spacing:1px;color:#00d4ff;background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);border-radius:4px;padding:3px 8px'>AI · GEMINI</div>
</div>""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📋 Márkaadatbázis")
    for src, data in BRAND_DB.items():
        with st.expander(f"{data['label']} ({len(data['brands'])} márka)"):
            st.write(", ".join(data["brands"]))

# ── Fő tartalom ──────────────────────────────────────────────────────
st.markdown("<h1 style='font-family:Syne;font-size:32px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Domain → Márkaösszetétel</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7a9fc0;margin-bottom:24px'>Add meg a webshop címét – az AI felkeresi, azonosítja a márkákat és elkészíti a scorecard-ot.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([4,1])
with col1:
    domain_input = st.text_input("", placeholder="pl. medencefutar.hu", label_visibility="collapsed")
with col2:
    scan_btn = st.button("Elemzés →", type="primary", use_container_width=True)

# ── Elemzés ──────────────────────────────────────────────────────────
if scan_btn and domain_input:
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        st.error("⚠️ Gemini API kulcs hiányzik! Streamlit Cloud → Settings → Secrets → GEMINI_API_KEY")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    from urllib.parse import urlparse
    domain = urlparse(raw).netloc.replace("www.", "") or raw

    st.markdown("""
    <style>
    [data-testid="stStatusWidget"] { color: #ffffff !important; }
    [data-testid="stStatusWidget"] p { color: #e0e0e0 !important; }
    div[data-testid="stStatus"] p { color: #e0e0e0 !important; }
    .st-emotion-cache-1gulkj5 p { color: #e0e0e0 !important; }
    </style>
    """, unsafe_allow_html=True)
    with st.status(f"🤖 Elemzés: {domain}...", expanded=True) as status:
        st.write("🔍 Webshop felkeresése Google kereséssel...")
        try:
            client = genai.Client(api_key=api_key)

            st.write("📊 Aquashop vs. konkurens márkák összehasonlítása...")

            # ── 1. LÉPÉS: Márka keresés ─────────────────────────
            aq_brands = ", ".join(BRAND_DB["aquashop"]["brands"])
            al_brands = ", ".join(BRAND_DB["aqualing"]["brands"])
            fl_brands = ", ".join(BRAND_DB["fluidra"]["brands"])

            brand_prompt = f"""Keresd fel ezt a webshopot: {raw}

Végezd el ezeket a Google kereséseket:
1. site:{domain} termékek
2. site:{domain} {" OR ".join(BRAND_DB["aquashop"]["brands"][:6])}
3. site:{domain} {" OR ".join(BRAND_DB["aqualing"]["brands"][:5])}
4. site:{domain} {" OR ".join(BRAND_DB["fluidra"]["brands"][:5])}

Ellenőrzendő AQUASHOP márkák: {aq_brands}
Ellenőrzendő AQUALING márkák: {al_brands}
Ellenőrzendő FLUIDRA márkák: {fl_brands}

Add vissza CSAK ezt a JSON-t, semmi más szöveg:
{{"aquashop":["ide írd a talált aquashop márkákat"],"aqualing":["ide írd a talált aqualing márkákat"],"fluidra":["ide írd a talált fluidra márkákat"],"egyeb":["egyéb márkák"],"webshop_neve":"string","osszefoglalo":"mit talaltál a webshopban 2-3 mondatban"}}"""

            brand_response = gemini_call(client, brand_prompt, use_search=True)

            # Márka JSON kinyerése
            brand_raw = brand_response.text if brand_response.text else ""
            brand_text = re.sub(r'```json|```', '', brand_raw).strip()
            bs = brand_text.find('{')
            be = brand_text.rfind('}')

            if bs == -1 or be == -1:
                # AI nem adott JSON-t - megpróbáljuk a nyers szövegből kinyerni a márkákat
                st.write("⚠️ JSON nem érkezett, szöveges feldolgozás...")
                brand_data = {"aquashop": [], "aqualing": [], "fluidra": [], "egyeb": [],
                              "webshop_neve": domain, "osszefoglalo": brand_raw[:300]}
                # Végigmegyünk az összes ismert márkanéven és keressük a szövegben
                for b in BRAND_DB["aquashop"]["brands"]:
                    if b.lower() in brand_raw.lower():
                        brand_data["aquashop"].append(b)
                for b in BRAND_DB["aqualing"]["brands"]:
                    if b.lower() in brand_raw.lower():
                        brand_data["aqualing"].append(b)
                for b in BRAND_DB["fluidra"]["brands"]:
                    if b.lower() in brand_raw.lower():
                        brand_data["fluidra"].append(b)
            else:
                try:
                    brand_data = json.loads(brand_text[bs:be+1])
                except json.JSONDecodeError:
                    brand_data = {"aquashop": [], "aqualing": [], "fluidra": [], "egyeb": [],
                                  "webshop_neve": domain, "osszefoglalo": ""}
                    for b in BRAND_DB["aquashop"]["brands"]:
                        if b.lower() in brand_raw.lower():
                            brand_data["aquashop"].append(b)
                    for b in BRAND_DB["aqualing"]["brands"]:
                        if b.lower() in brand_raw.lower():
                            brand_data["aqualing"].append(b)
                    for b in BRAND_DB["fluidra"]["brands"]:
                        if b.lower() in brand_raw.lower():
                            brand_data["fluidra"].append(b)

            found_aq  = brand_data.get("aquashop", [])
            found_al  = brand_data.get("aqualing", [])
            found_fl  = brand_data.get("fluidra", [])
            found_neu = brand_data.get("egyeb", [])
            webshop_neve = brand_data.get("webshop_neve", domain)
            raw_osszefoglalo = brand_data.get("osszefoglalo", "")
            # Ha JSON kód szivárgott be az összefoglalóba, töröljük
            if raw_osszefoglalo.strip().startswith(("{", "```")):
                osszefoglalo = ""
            else:
                osszefoglalo = raw_osszefoglalo

            st.write(f"📊 Talált márkák: Aquashop={len(found_aq)}, Aqualing={len(found_al)}, Fluidra={len(found_fl)}, Egyéb={len(found_neu)}")

            # ── 2. LÉPÉS: Pontozás ──────────────────────────────────
            score_prompt = f"""Keresd fel ezt a webshopot és pontozd: {raw}

MÁR ISMERT ADATOK az előző keresésből:
- Webshop neve: {webshop_neve}
- Talált AQUASHOP márkák ({len(found_aq)} db): {", ".join(found_aq) if found_aq else "nincs"}
- Talált AQUALING márkák ({len(found_al)} db): {", ".join(found_al) if found_al else "nincs"}
- Talált FLUIDRA márkák ({len(found_fl)} db): {", ".join(found_fl) if found_fl else "nincs"}
- Talált EGYÉB márkák ({len(found_neu)} db): {", ".join(found_neu) if found_neu else "nincs"}

MOST: Nézd meg a webshop termékoldalait, kategóriáit, leírásait és pontozd:

exkluziv_termekek (max 40) - KÖTELEZŐ SZABÁLY:
  {len(found_aq)} Aquashop márka van → {"0 pont" if len(found_aq)==0 else "10 pont" if len(found_aq)<=2 else "20 pont" if len(found_aq)<=4 else "30 pont" if len(found_aq)<=7 else "40 pont"}
  TEHÁT exkluziv_termekek = {"0" if len(found_aq)==0 else "10" if len(found_aq)<=2 else "20" if len(found_aq)<=4 else "30" if len(found_aq)<=7 else "40"}

kinalat_teljessege (max 25):
  1-5 pont: csak néhány alaptermék
  6-15 pont: közepes kínálat, több kategória
  16-25 pont: széles medence/spa kínálat, sok kategória

tartalmi_minoseg (max 20):
  1-7 pont: rövid leírások, kevés kép
  8-14 pont: közepes minőség
  15-20 pont: részletes leírások, sok kép, műszaki adatok

webshop_aktivitas (max 10):
  1-4 pont: régi tartalom, hiányzó árak
  5-7 pont: részben friss
  8-10 pont: naprakész árak, készletjelzés, friss tartalom

seo_elkotelezettsege (max 5):
  1-2 pont: nincs optimalizálás
  3-5 pont: kulcsszavak a terméknevekben és leírásokban

FONTOS: Minden mezőbe írj NEM NULLA értéket ha a webshop él és van tartalma!

Add vissza CSAK ezt a JSON-t, semmi más szöveg:
{{"scores":{{"exkluziv_termekek":{0 if len(found_aq)==0 else 10 if len(found_aq)<=2 else 20 if len(found_aq)<=4 else 30 if len(found_aq)<=7 else 40},"kinalat_teljessege":0,"tartalmi_minoseg":0,"webshop_aktivitas":0,"seo_elkotelezettsege":0}},"javasolt_teendok":"konkrét fejlesztési javaslatok magyarul","bizonyitekok":{{"talalt_termekek":"mit találtál","kinalat_szelessege":"milyen kategóriák vannak","tartalom_minosege":"leírások és képek","aktivitas_frissesseg":"árak és frissesség"}}}}"""

            score_response = gemini_call(client, score_prompt, use_search=True)

            score_raw = score_response.text if score_response.text else "{}"
            score_text = re.sub(r'```json|```', '', score_raw).strip()
            ss = score_text.find('{')
            se = score_text.rfind('}')
            if ss == -1:
                raise ValueError("Pontozás sikertelen. Próbáld újra!")
            try:
                score_data = json.loads(score_text[ss:se+1])
            except json.JSONDecodeError:
                score_data = {"scores": {"exkluziv_termekek": 0, "kinalat_teljessege": 0,
                              "tartalmi_minoseg": 0, "webshop_aktivitas": 0, "seo_elkotelezettsege": 0},
                              "tier": "BASIC", "javasolt_teendok": "", "bizonyitekok": {}}

            # Összerakjuk a végeredményt
            scores = score_data.get("scores", {})
            calc_total = sum(int(v) for v in scores.values())

            # Tier automatikus meghatározása a total alapján
            if calc_total >= 85:   auto_tier = "PLATINUM"
            elif calc_total >= 65: auto_tier = "GOLD"
            elif calc_total >= 40: auto_tier = "SILVER"
            elif calc_total >= 20: auto_tier = "BASIC"
            else:                  auto_tier = "INAKTÍV"

            result = {
                "domain": domain,
                "partner_neve": webshop_neve,
                "osszefoglalo": osszefoglalo,
                "scores": scores,
                "total": min(100, calc_total),
                "tier": auto_tier,
                "markak": {"aquashop": found_aq, "aqualing": found_al, "fluidra": found_fl, "egyeb": found_neu},
                "markaok_szama": {"aquashop": len(found_aq), "aqualing": len(found_al), "fluidra": len(found_fl), "egyeb": len(found_neu)},
                "bizonyitekok": score_data.get("bizonyitekok", {}),
                "javasolt_teendok": score_data.get("javasolt_teendok", ""),
            }

            status.update(label="✅ Elemzés kész!", state="complete")

        except Exception as e:
            status.update(label="❌ Hiba", state="error")
            st.error(f"Hiba: {str(e)}")
            st.stop()

    # ── Eredmény ──────────────────────────────────────────────────────
    total = min(100, max(0, int(result.get("total", 0))))
    tier_key = result.get("tier", "INAKTÍV")
    tier = TIER_CONFIG.get(tier_key, TIER_CONFIG["INAKTÍV"])

    st.markdown(f"""<div class="score-hero">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div class="score-big">{total}</div>
        <div>
          <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
          <div style="font-size:12px;color:#7a9fc0;font-family:monospace">{result.get('partner_neve', domain)} · {domain}</div>
          <div style="font-size:13px;color:#c8d8f0;margin-top:6px;max-width:480px">{result.get('osszefoglalo', '')}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Márka arány
    st.markdown('<div class="section-label">▸ Márkaösszetétel & versenytárs arány</div>', unsafe_allow_html=True)
    mc = result.get("markaok_szama", {})
    aq=int(mc.get("aquashop",0)); al=int(mc.get("aqualing",0)); fl=int(mc.get("fluidra",0)); neu=int(mc.get("egyeb",0))
    tb=max(aq+al+fl+neu, 1)
    aq_pct=round(aq/tb*100); al_pct=round(al/tb*100); fl_pct=round(fl/tb*100); neu_pct=100-aq_pct-al_pct-fl_pct

    def seg(pct, cls):
        if pct <= 0: return ''
        txt = f"{pct}%" if pct > 7 else ""
        return f'<div class="seg {cls}" style="width:{pct}%">{txt}</div>'

    st.markdown(f"""<div class="ratio-bar-container">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:13px">
        <span style="color:#5ee8ff;font-weight:700">Aquashop {aq_pct}% ({aq})</span>
        <span style="color:#fdd835;font-weight:700">Aqualing {al_pct}% ({al})</span>
        <span style="color:#ff8c5a;font-weight:700">Fluidra-Kerex {fl_pct}% ({fl})</span>
        <span style="color:#b4c8e6;font-weight:700">Egyéb {neu_pct}% ({neu})</span>
      </div>
      <div class="ratio-bar">{seg(aq_pct,'seg-aq')}{seg(al_pct,'seg-al')}{seg(fl_pct,'seg-fl')}{seg(neu_pct,'seg-neu')}</div>
    </div>""", unsafe_allow_html=True)

    markak = result.get("markak", {})
    chips = ""
    for src, cls in [("aquashop","chip-aq"),("aqualing","chip-al"),("fluidra","chip-fl"),("egyeb","chip-neu")]:
        for b in markak.get(src, []):
            chips += f'<span class="brand-chip {cls}">{b}</span>'
    if chips:
        st.markdown(f'<div style="margin:10px 0"><div style="font-size:11px;color:#7a9fc0;margin-bottom:6px;letter-spacing:1px">AZONOSÍTOTT MÁRKÁK</div>{chips}</div>', unsafe_allow_html=True)

    # Dimenzió bontás
    st.markdown('<div class="section-label">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    scores = result.get("scores", {})
    for key, label, max_pts in DIM_DEFS:
        pts = int(scores.get(key, 0))
        pct = pts / max_pts if max_pts > 0 else 0
        c1, c2 = st.columns([4,1])
        with c1:
            st.markdown(f"<div style='font-size:13px;color:#e0eeff;margin-bottom:4px;font-weight:500'>{label}</div>", unsafe_allow_html=True)
            st.progress(pct)
        with c2:
            color = "#00d4ff" if pts > 0 else "#666"
            st.markdown(f"<div style='font-size:14px;font-weight:700;color:{color};text-align:right;padding-top:4px'>{pts}/{max_pts}</div>", unsafe_allow_html=True)

    # Bizonyítékok
    biz = result.get("bizonyitekok", {})
    if any(biz.values()):
        st.markdown('<div class="section-label">▸ Elemzési bizonyítékok</div>', unsafe_allow_html=True)
        items = [
            ("Talált termékek", biz.get("talalt_termekek","")),
            ("Kínálat szélessége", biz.get("kinalat_szelessege","")),
            ("Tartalom minősége", biz.get("tartalom_minosege","")),
            ("Aktivitás & frissesség", biz.get("aktivitas_frissesseg","")),
        ]
        c1, c2 = st.columns(2)
        for i, (t, v) in enumerate(items):
            if v:
                with (c1 if i%2==0 else c2):
                    st.markdown(f'<div class="ev-card"><div class="ev-title">{t}</div><div style="font-size:12px;color:#e0eeff;line-height:1.6">{v}</div></div>', unsafe_allow_html=True)

    # Javaslatok
    st.markdown('<div class="section-label">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    javasolt = result.get("javasolt_teendok", "")
    if javasolt and not javasolt.strip().startswith(("{","```")):
        st.markdown(f'<div class="rec-box"><div style="font-size:13px;color:#e0eeff;line-height:1.8">{javasolt.replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="rec-box"><div style="font-size:13px;color:#7a9fc0">Nem érkezett javaslat ebből az elemzésből.</div></div>', unsafe_allow_html=True)

    # History
    st.session_state.history.insert(0, {
        "domain": domain, "partner": result.get("partner_neve", domain),
        "total": total, "tier": tier_key, "aq_pct": aq_pct,
        "date": datetime.now().strftime("%Y.%m.%d"), "result": result
    })

# ── Előzmények ───────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="section-label">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    colors = {"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        with c1: st.markdown(f"<span style='font-size:13px;color:#c8d8f0'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#5ee8ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:{colors.get(h['tier'],'#fff')};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#7a9fc0;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)

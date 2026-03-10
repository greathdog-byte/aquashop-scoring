import streamlit as st
from google import genai
from google.genai import types
import json
import re
from datetime import datetime

st.set_page_config(page_title="Aquashop · Partner Scoring", page_icon="💧", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stAppViewContainer"] { background: #060912; }
[data-testid="stHeader"] { background: #060912; border-bottom: 1px solid #1c2a42; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }
.score-hero { background: linear-gradient(135deg,#0d1424,#121d30); border: 1px solid #1c2a42; border-radius: 16px; padding: 28px; margin: 16px 0; position: relative; overflow: hidden; }
.score-hero::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg,#0055ff,#00d4ff,#00ffb3); }
.score-big { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 56px; line-height: 1; background: linear-gradient(135deg,#00d4ff,#0055ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.tier-badge { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 26px; margin-bottom: 4px; }
.ratio-bar-container { background: #121d30; border: 1px solid #1c2a42; border-radius: 12px; padding: 20px; margin: 12px 0; }
.ratio-bar { height: 32px; border-radius: 10px; overflow: hidden; display: flex; margin: 10px 0; }
.seg { height: 100%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; color: rgba(0,0,0,0.75); white-space: nowrap; overflow: hidden; }
.seg-aq { background: #00d4ff; } .seg-al { background: #f5c842; } .seg-fl { background: #ff6b35; } .seg-neu { background: #8fa8c8; }
.brand-chip { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; margin: 3px; }
.chip-aq { background: rgba(0,212,255,0.15); color: #00d4ff; border: 1px solid rgba(0,212,255,0.3); }
.chip-al { background: rgba(245,200,66,0.15); color: #f5c842; border: 1px solid rgba(245,200,66,0.3); }
.chip-fl { background: rgba(255,107,53,0.15); color: #ff6b35; border: 1px solid rgba(255,107,53,0.3); }
.chip-neu { background: rgba(143,168,200,0.15); color: #8fa8c8; border: 1px solid rgba(143,168,200,0.3); }
.ev-card { background: #121d30; border: 1px solid #1c2a42; border-radius: 10px; padding: 14px; margin: 6px 0; }
.ev-title { font-size: 11px; color: #4a6080; margin-bottom: 6px; }
.rec-box { background: #121d30; border: 1px solid #243350; border-radius: 12px; padding: 18px; margin: 12px 0; }
.section-label { font-family: 'Syne', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #00d4ff; margin: 20px 0 10px; }
</style>
""", unsafe_allow_html=True)

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

ISMERT MÁRKAADATBÁZIS:
AQUASHOP márkák: {", ".join(BRAND_DB["aquashop"]["brands"])}
AQUALING márkák: {", ".join(BRAND_DB["aqualing"]["brands"])}
FLUIDRA-KEREX márkák: {", ".join(BRAND_DB["fluidra"]["brands"])}

FELADATOD:
1. Keresd fel a megadott webshopot Google Search segítségével
2. Azonosítsd az összes terméket és márkát
3. Sorolj minden márkát a fenti adatbázis alapján
4. Ha egy márka nem szerepel, az "egyeb" kategóriába kerül

ÉRTÉKELÉSI DIMENZIÓK:
- exkluziv_termekek (max 40): Aquashop márkák száma, dedikált kategóriák
- kinalat_teljessege (max 25): Medence/spa termékkör mélysége
- tartalmi_minoseg (max 20): Leírások, képek, műszaki adatok
- webshop_aktivitas (max 10): Frissesség, árak, készletinfo
- seo_elkotelezettsege (max 5): Kulcsszó-optimalizáltság

Válaszolj KIZÁRÓLAG valid JSON-ban, semmi más szöveg:
{{"domain":"string","partner_neve":"string","scores":{{"exkluziv_termekek":0,"kinalat_teljessege":0,"tartalmi_minoseg":0,"webshop_aktivitas":0,"seo_elkotelezettsege":0}},"total":0,"tier":"PLATINUM|GOLD|SILVER|BASIC|INAKTÍV","osszefoglalo":"string","markak":{{"aquashop":[],"aqualing":[],"fluidra":[],"egyeb":[]}},"markaok_szama":{{"aquashop":0,"aqualing":0,"fluidra":0,"egyeb":0}},"bizonyitekok":{{"talalt_termekek":"string","kinalat_szelessege":"string","tartalom_minosege":"string","aktivitas_frissesseg":"string"}},"javasolt_teendok":"string"}}"""

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

st.markdown("""<div style='display:flex;align-items:center;gap:12px;padding:8px 0 24px'>
  <div style='width:36px;height:36px;background:linear-gradient(135deg,#00d4ff,#0055ff);border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Syne;font-weight:800;font-size:16px;color:#fff'>A</div>
  <span style='font-family:Syne;font-weight:700;font-size:18px;color:#dce8f5'>Aquashop <span style='color:#4a6080;font-weight:400'>/ Partner Scoring</span></span>
  <div style='margin-left:auto;font-size:10px;letter-spacing:1px;color:#00d4ff;background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);border-radius:4px;padding:3px 8px'>AI · GEMINI</div>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🔑 Gemini API kulcs")
    st.markdown("Ingyenes kulcs: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)\n\n1. Nyisd meg a linket\n2. Kattints: **Create API key**\n3. Másold be ↓")
    api_key = st.text_input("API kulcs", type="password", placeholder="AIzaSy...", value=st.session_state.get("api_key",""))
    if api_key:
        st.session_state.api_key = api_key
        st.success("✓ Kulcs beállítva")
    st.divider()
    st.markdown("### 📋 Márkaadatbázis")
    for src, data in BRAND_DB.items():
        with st.expander(f"{data['label']} ({len(data['brands'])} márka)"):
            st.write(", ".join(data["brands"]))

st.markdown("<h1 style='font-family:Syne;font-size:32px;font-weight:800;color:#dce8f5;margin-bottom:4px'>Domain → Márkaösszetétel</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#4a6080;margin-bottom:24px'>Add meg a webshop címét – az AI felkeresi, azonosítja a márkákat és elkészíti a scorecard-ot.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([4,1])
with col1:
    domain_input = st.text_input("", placeholder="pl. medencefutar.hu", label_visibility="collapsed")
with col2:
    scan_btn = st.button("Elemzés →", type="primary", use_container_width=True)

if scan_btn and domain_input:
    if not st.session_state.get("api_key"):
        st.error("⚠️ Először add meg a Gemini API kulcsot a bal oldali sávban!")
        st.stop()

    raw = domain_input.strip()
    if not raw.startswith("http"):
        raw = "https://" + raw
    from urllib.parse import urlparse
    domain = urlparse(raw).netloc.replace("www.","") or raw

    with st.status(f"🤖 Elemzés: {domain}...", expanded=True) as status:
        st.write("🔍 Webshop felkeresése Google kereséssel...")
        try:
            client = genai.Client(api_key=st.session_state.api_key)
            prompt = f"""{SYSTEM_PROMPT}\n\nElemzendő webshop: {raw}\n\nKeresd fel Google kereséssel, azonosítsd az összes márkát. Különösen keresd: {ALL_BRANDS_LIST}\nVálaszolj KIZÁRÓLAG JSON-ban."""

            st.write("📊 Aquashop vs. konkurens márkák összehasonlítása...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.1,
                    max_output_tokens=2500,
                )
            )
            st.write("⚡ Pontszámok kiszámítása...")
            raw_text = response.text
            # Robusztus JSON kinyerés
            clean = re.sub(r'```json|```', '', raw_text).strip()
            # Megkeressük a JSON kezdetét és végét
            start = clean.find('{')
            end = clean.rfind('}')
            if start == -1 or end == -1:
                raise ValueError("Nem érkezett JSON válasz. Próbáld újra!")
            json_str = clean[start:end+1]
            # Escape-eljük a problémás karaktereket
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # Ha még mindig hibás, kérjük újra csak a JSON-t
                fix_response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Az alábbi szövegből nyerd ki a JSON objektumot és add vissza CSAK a valid JSON-t, semmi mást:\n\n{json_str[:3000]}",
                    config=types.GenerateContentConfig(temperature=0)
                )
                fix_text = re.sub(r'```json|```', '', fix_response.text).strip()
                fix_start = fix_text.find('{')
                fix_end = fix_text.rfind('}')
                result = json.loads(fix_text[fix_start:fix_end+1])
            status.update(label="✅ Elemzés kész!", state="complete")
        except Exception as e:
            status.update(label="❌ Hiba", state="error")
            st.error(f"Hiba: {str(e)}")
            st.stop()

    total = min(100, max(0, int(result.get("total",0))))
    tier_key = result.get("tier","INAKTÍV")
    tier = TIER_CONFIG.get(tier_key, TIER_CONFIG["INAKTÍV"])

    st.markdown(f"""<div class="score-hero">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div class="score-big">{total}</div>
        <div>
          <div class="tier-badge" style="color:{tier['color']}">{tier['emoji']} {tier['label']}</div>
          <div style="font-size:12px;color:#4a6080;font-family:monospace">{result.get('partner_neve',domain)} · {domain}</div>
          <div style="font-size:13px;color:#8fa8c8;margin-top:6px;max-width:480px">{result.get('osszefoglalo','')}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">▸ Márkaösszetétel & versenytárs arány</div>', unsafe_allow_html=True)
    mc = result.get("markaok_szama",{})
    aq=int(mc.get("aquashop",0)); al=int(mc.get("aqualing",0)); fl=int(mc.get("fluidra",0)); neu=int(mc.get("egyeb",0))
    tb=max(aq+al+fl+neu,1)
    aq_pct=round(aq/tb*100); al_pct=round(al/tb*100); fl_pct=round(fl/tb*100); neu_pct=100-aq_pct-al_pct-fl_pct

    def seg(pct, cls):
        if pct<=0: return ''
        txt=f"{pct}%" if pct>7 else ""
        return f'<div class="seg {cls}" style="width:{pct}%">{txt}</div>'

    st.markdown(f"""<div class="ratio-bar-container">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:13px">
        <span style="color:#00d4ff;font-weight:700">Aquashop {aq_pct}% ({aq})</span>
        <span style="color:#f5c842;font-weight:700">Aqualing {al_pct}% ({al})</span>
        <span style="color:#ff6b35;font-weight:700">Fluidra-Kerex {fl_pct}% ({fl})</span>
        <span style="color:#8fa8c8;font-weight:700">Egyéb {neu_pct}% ({neu})</span>
      </div>
      <div class="ratio-bar">{seg(aq_pct,'seg-aq')}{seg(al_pct,'seg-al')}{seg(fl_pct,'seg-fl')}{seg(neu_pct,'seg-neu')}</div>
    </div>""", unsafe_allow_html=True)

    markak=result.get("markak",{})
    chips=""
    for src,cls in [("aquashop","chip-aq"),("aqualing","chip-al"),("fluidra","chip-fl"),("egyeb","chip-neu")]:
        for b in markak.get(src,[]):
            chips+=f'<span class="brand-chip {cls}">{b}</span>'
    if chips:
        st.markdown(f'<div style="margin:10px 0"><div style="font-size:11px;color:#4a6080;margin-bottom:6px">AZONOSÍTOTT MÁRKÁK</div>{chips}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">▸ Dimenzió bontás</div>', unsafe_allow_html=True)
    scores=result.get("scores",{})
    for key,label,max_pts in DIM_DEFS:
        pts=int(scores.get(key,0))
        c1,c2=st.columns([4,1])
        with c1:
            st.markdown(f"<div style='font-size:13px;color:#8fa8c8;margin-bottom:2px'>{label}</div>", unsafe_allow_html=True)
            st.progress(pts/max_pts)
        with c2:
            st.markdown(f"<div style='font-size:13px;font-weight:700;text-align:right;padding-top:4px'>{pts}/{max_pts}</div>", unsafe_allow_html=True)

    biz=result.get("bizonyitekok",{})
    if any(biz.values()):
        st.markdown('<div class="section-label">▸ Elemzési bizonyítékok</div>', unsafe_allow_html=True)
        items=[("Talált termékek",biz.get("talalt_termekek","")),("Kínálat szélessége",biz.get("kinalat_szelessege","")),("Tartalom minősége",biz.get("tartalom_minosege","")),("Aktivitás & frissesség",biz.get("aktivitas_frissesseg",""))]
        c1,c2=st.columns(2)
        for i,(t,v) in enumerate(items):
            if v:
                with (c1 if i%2==0 else c2):
                    st.markdown(f'<div class="ev-card"><div class="ev-title">{t}</div><div style="font-size:12px;color:#dce8f5">{v}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">▸ Javasolt teendők</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rec-box"><div style="font-size:13px;color:#dce8f5;line-height:1.7">{result.get("javasolt_teendok","").replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)

    st.session_state.history.insert(0,{"domain":domain,"partner":result.get("partner_neve",domain),"total":total,"tier":tier_key,"aq_pct":aq_pct,"date":datetime.now().strftime("%Y.%m.%d"),"result":result})

if st.session_state.history:
    st.markdown('<div class="section-label">▸ Korábbi értékelések</div>', unsafe_allow_html=True)
    colors={"PLATINUM":"#00d4ff","GOLD":"#f5c842","SILVER":"#8fa8c8","BASIC":"#ff8c38","INAKTÍV":"#ff4455"}
    for h in st.session_state.history[:10]:
        c1,c2,c3,c4=st.columns([3,1,1,1])
        with c1: st.markdown(f"<span style='font-size:13px'>{h['partner']} · {h['domain']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#00d4ff;font-size:12px'>AQ: {h['aq_pct']}%</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:{colors.get(h['tier'],'#fff')};font-weight:700'>{h['total']} pt</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='color:#4a6080;font-size:11px'>{h['date']}</span>", unsafe_allow_html=True)

"""
Streamlit UI — AGÜ Mühendislik RAG Asistanı
Çalıştır: streamlit run app.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import streamlit.components.v1 as components
from src.rag import answer

st.set_page_config(
    page_title="AGÜ Öğrenci Asistanı",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================ GLOBAL STYLE ============================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

    :root {
        --brand-1: #7B1E3A;
        --brand-2: #C2185B;
        --brand-3: #FF6B6B;
        --accent: #FFB800;
        --bg-soft: rgba(255,255,255,0.04);
        --border-soft: rgba(255,255,255,0.08);
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .stApp {
        background:
            radial-gradient(1200px 600px at 10% -10%, rgba(194,24,91,0.18), transparent 60%),
            radial-gradient(900px 500px at 110% 10%, rgba(255,184,0,0.10), transparent 60%),
            radial-gradient(800px 400px at 50% 120%, rgba(123,30,58,0.20), transparent 60%),
            linear-gradient(180deg, #0E1117 0%, #14171F 100%);
    }

    /* Hero başlık */
    .hero {
        position: relative;
        padding: 28px 32px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(123,30,58,0.55) 0%, rgba(194,24,91,0.45) 50%, rgba(255,107,107,0.35) 100%);
        border: 1px solid rgba(255,255,255,0.10);
        box-shadow:
            0 10px 40px -10px rgba(194,24,91,0.45),
            inset 0 1px 0 rgba(255,255,255,0.08);
        margin-bottom: 22px;
        overflow: hidden;
    }
    .hero::before {
        content: "";
        position: absolute;
        inset: -50% -10% auto auto;
        width: 360px; height: 360px;
        background: radial-gradient(circle, rgba(255,184,0,0.35), transparent 60%);
        filter: blur(40px);
        pointer-events: none;
    }
    .hero h1 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        margin: 0 0 6px 0 !important;
        background: linear-gradient(90deg, #fff 0%, #FFE9C4 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
    }
    .hero p {
        margin: 0;
        color: rgba(255,255,255,0.82);
        font-size: 1.02rem;
        font-weight: 400;
    }
    .hero .pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.14);
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #FFE9C4;
        margin-bottom: 10px;
        backdrop-filter: blur(8px);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #14171F 0%, #0E1117 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    [data-testid="stSidebar"] .sidebar-logo {
        text-align: center;
        padding: 14px 8px 18px 8px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 18px;
    }
    [data-testid="stSidebar"] .sidebar-logo .emoji {
        display: inline-block;
        font-size: 2.2rem;
        background: linear-gradient(135deg, #C2185B, #FFB800);
        -webkit-background-clip: text;
        background-clip: text;
        filter: drop-shadow(0 4px 14px rgba(194,24,91,0.4));
        margin-bottom: 4px;
    }
    [data-testid="stSidebar"] .sidebar-logo h2 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 800 !important;
        font-size: 1.35rem !important;
        margin: 0 !important;
        background: linear-gradient(90deg, #fff, #FFE9C4);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    [data-testid="stSidebar"] .sidebar-logo span {
        font-size: 0.78rem;
        opacity: 0.6;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }

    /* Selectbox & inputs */
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
        border-color: rgba(255,184,0,0.4) !important;
        background: rgba(255,255,255,0.06) !important;
    }

    /* Info kutusu — özel kart */
    .info-card {
        background: linear-gradient(135deg, rgba(194,24,91,0.12), rgba(255,184,0,0.08));
        border: 1px solid rgba(255,184,0,0.18);
        border-radius: 14px;
        padding: 12px 14px;
        font-size: 0.88rem;
        color: rgba(255,255,255,0.85);
        line-height: 1.45;
        margin: 12px 0;
    }
    .info-card strong { color: #FFB800; }

    /* Detay kartı */
    .detail-card {
        padding: 12px 14px;
        border-radius: 12px;
        border-left: 3px solid #FFB800;
        background: rgba(255,184,0,0.06);
        margin-top: 12px;
        font-size: 0.85em;
        line-height: 1.45;
    }
    .detail-card strong { color: #FFB800; }

    /* Slider thumb */
    div[data-testid="stThumbValue"] {
        font-weight: 700 !important;
        color: #FFB800 !important;
        font-size: 1.05rem !important;
        cursor: help !important;
    }
    [data-testid="stSlider"] [role="slider"] {
        background: linear-gradient(135deg, #C2185B, #FFB800) !important;
        box-shadow: 0 0 12px rgba(255,184,0,0.5) !important;
    }

    /* Chat mesajları */
    [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 16px !important;
        padding: 14px 18px !important;
        margin-bottom: 10px !important;
        backdrop-filter: blur(10px);
        animation: fadeIn 0.4s ease;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: linear-gradient(135deg, rgba(194,24,91,0.18), rgba(123,30,58,0.10)) !important;
        border-color: rgba(194,24,91,0.30) !important;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* Chat input */
    [data-testid="stChatInput"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 16px !important;
        backdrop-filter: blur(12px);
        transition: all 0.2s ease;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: rgba(255,184,0,0.5) !important;
        box-shadow: 0 0 0 3px rgba(255,184,0,0.12) !important;
    }

    /* Expander (kaynaklar) */
    [data-testid="stExpander"] {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        margin-top: 8px;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600;
        color: #FFB800;
    }

    /* Suggestion chips */
    .suggest-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 10px;
        margin: 10px 0 24px 0;
    }
    .suggest-chip {
        background: linear-gradient(135deg, rgba(194,24,91,0.10), rgba(255,184,0,0.05));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 14px 16px;
        cursor: pointer;
        transition: all 0.25s ease;
        color: rgba(255,255,255,0.88);
        font-size: 0.92rem;
        line-height: 1.4;
    }
    .suggest-chip:hover {
        transform: translateY(-2px);
        border-color: rgba(255,184,0,0.4);
        background: linear-gradient(135deg, rgba(194,24,91,0.18), rgba(255,184,0,0.10));
        box-shadow: 0 8px 24px -8px rgba(194,24,91,0.4);
    }
    .suggest-chip .icon {
        font-size: 1.1rem;
        margin-right: 6px;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.10);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,184,0,0.30); }

    /* Streamlit footer/menu gizle */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { background: transparent !important; }

    /* Boş durum (welcome) */
    .welcome {
        text-align: center;
        padding: 24px 16px 8px 16px;
        opacity: 0.75;
    }
    .welcome h3 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        margin-bottom: 6px !important;
    }
    .welcome p { font-size: 0.92rem; opacity: 0.8; }

    /* Bölüm SVG ikon — monokrom beyaz, hero ve sidebar için */
    .bolum-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        vertical-align: -0.15em;
        margin: 0 6px;
    }
    .bolum-icon svg {
        width: 1.1em;
        height: 1.1em;
        stroke: #fff;
        fill: none;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.25));
    }
    .hero .bolum-icon svg { width: 1.05em; height: 1.05em; }
    .info-card .bolum-icon { margin: 0 4px 0 0; }
    .info-card .bolum-icon svg { width: 1em; height: 1em; }

    /* Emoji ikonlar (Makine ⚙️ ve İnşaat 🏗️) */
    .bolum-emoji {
        display: inline-block;
        vertical-align: -0.10em;
        margin: 0 6px;
        font-size: 1em;
        line-height: 1;
    }
    .info-card .bolum-emoji { margin: 0 4px 0 0; font-size: 0.95em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================ SIDEBAR ============================
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-logo">
            <div class="emoji">🎓</div>
            <h2>AGÜ Asistanı</h2>
            <span>Yapay Zeka Destekli Rehber</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bolum_secim = st.selectbox(
        "📚 **Bölüm Seçimi**",
        [
            "Bilgisayar Mühendisliği",
            "Makine Mühendisliği",
            "Endüstri Mühendisliği",
            "Elektrik-Elektronik Mühendisliği",
            "İnşaat Mühendisliği",
            "Malzeme Bilimi ve Nanoteknoloji Mühendisliği",
        ],
    )
    BOLUM_ID_MAP = {
        "Bilgisayar Mühendisliği": "bilgisayar",
        "Makine Mühendisliği": "makine",
        "Endüstri Mühendisliği": "endustri",
        "Elektrik-Elektronik Mühendisliği": "elektrik",
        "İnşaat Mühendisliği": "insaat",
        "Malzeme Bilimi ve Nanoteknoloji Mühendisliği": "malzeme",
    }
    BOLUM_SVG = {
        "bilgisayar": (
            '<span class="bolum-icon" title="Bilgisayar Mühendisliği">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="2" y="3" width="20" height="14" rx="2"/>'
            '<path d="M8 21h8"/><path d="M12 17v4"/>'
            '<path d="M9 8l-2 2 2 2"/><path d="M15 8l2 2-2 2"/>'
            '</svg></span>'
        ),
        "makine": '<span class="bolum-emoji" title="Makine Mühendisliği">⚙️</span>',
        "endustri": (
            '<span class="bolum-icon" title="Endüstri Mühendisliği">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M3 3v18h18"/>'
            '<rect x="7" y="13" width="3" height="5"/>'
            '<rect x="12" y="9" width="3" height="9"/>'
            '<rect x="17" y="5" width="3" height="13"/>'
            '</svg></span>'
        ),
        "elektrik": (
            '<span class="bolum-icon" title="Elektrik-Elektronik Mühendisliği">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
            '</svg></span>'
        ),
        "insaat": '<span class="bolum-emoji" title="İnşaat Mühendisliği">🏗️</span>',
        "malzeme": (
            '<span class="bolum-icon" title="Malzeme Bilimi ve Nanoteknoloji">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<circle cx="12" cy="12" r="1.2" fill="#fff"/>'
            '<ellipse cx="12" cy="12" rx="10" ry="4"/>'
            '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/>'
            '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>'
            '</svg></span>'
        ),
    }
    bolum_id = BOLUM_ID_MAP[bolum_secim]
    bolum_icon = BOLUM_SVG[bolum_id]

    st.markdown(
        f"""
        <div class="info-card">
            <strong>{bolum_icon} {bolum_secim}</strong><br>
            Müfredat, ders içerikleri, staj yönergesi ve daha fazlası hakkında soru sorabilirsin.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("⚙️ **Cevap Detay Seviyesi**")

    level_info = {
        "Kısa": "Net, tek bilgi soruları için (örn. COMP 101 kaç kredi?)",
        "Dengeli": "Günlük kullanım için ideal — çoğu soruya uyar.",
        "Kapsamlı": "Karşılaştırma / geniş konu soruları için.",
    }
    level_to_k = {"Kısa": 4, "Dengeli": 8, "Kapsamlı": 14}

    components.html(
        f"""
        <script>
        const info = {{
            "Kısa": "Net, tek bilgi soruları için",
            "Dengeli": "Günlük kullanım için ideal",
            "Kapsamlı": "Karşılaştırma / geniş konu soruları için"
        }};
        function updateThumb() {{
            const thumb = window.parent.document.querySelector('div[data-testid="stThumbValue"]');
            if(thumb && thumb.innerText) {{
                thumb.title = info[thumb.innerText.trim()] || "";
            }}
        }}
        const observer = new MutationObserver(updateThumb);
        observer.observe(window.parent.document.body, {{ childList: true, subtree: true, characterData: true }});
        setTimeout(updateThumb, 500);
        </script>
        """,
        height=0,
        width=0,
    )

    detail_level = st.select_slider(
        "detay",
        options=["Kısa", "Dengeli", "Kapsamlı"],
        value="Dengeli",
        label_visibility="collapsed",
    )
    st.markdown(
        f"""
        <div class="detail-card">
            <strong>Ayar: {detail_level}</strong><br>
            <span style="opacity:0.8;">{level_info[detail_level]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    top_k = level_to_k[detail_level]

    st.divider()
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

    st.markdown(
        """
        <div style="text-align:center; opacity:0.5; font-size:0.75rem; margin-top:18px; line-height:1.5;">
            Abdullah Gül Üniversitesi<br>
            Mühendislik Fakültesi
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================ HERO ============================
st.markdown(
    f"""
    <div class="hero">
        <div class="pill">✨ AKILLI ASİSTAN</div>
        <h1>Merhaba! {bolum_icon} {bolum_secim}</h1>
        <p>Müfredat, ders içerikleri, ön şartlar ve staj süreçleri hakkında doğal dilde sorular sor — anında Türkçe cevap al.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================ STATE ============================
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ============================ ÖNERİLER (boş durum) ============================
SUGGESTIONS = {
    "bilgisayar": [
        ("📚", "2023 girişliyim 3. dönem hangi dersler var?"),
        ("🔢", "COMP 101 dersi kaç AKTS?"),
        ("🧩", "COMP 305 dersinin ön şartı nedir?"),
        ("📋", "Staj yönergesi maddeleri neler?"),
    ],
    "makine": [
        ("📚", "2024 girişliyim 4. dönem dersleri neler?"),
        ("⚙️", "ME 201 dersi kaç kredi?"),
        ("🧩", "ME 301 ön şartı var mı?"),
        ("📋", "Makine müfredatı 2025 nasıl?"),
    ],
    "endustri": [
        ("📚", "2022 girişli 2. sınıf dersleri neler?"),
        ("📊", "IE 202 kaç AKTS?"),
        ("🧩", "IE 305 ön şartları neler?"),
        ("📋", "2021 müfredatı tüm dersler"),
    ],
    "elektrik": [
        ("📚", "2023 girişli 5. dönem dersleri?"),
        ("⚡", "EE 201 dersi içeriği nedir?"),
        ("🧩", "Seçmeli kapsüller nelerdir?"),
        ("📋", "2025 müfredatı 1. sınıf"),
    ],
    "insaat": [
        ("📚", "2023 girişliyim 3. dönem dersleri?"),
        ("🏗️", "CE 201 kaç kredi?"),
        ("🧩", "CE 305 ön şartı?"),
        ("📋", "2021 müfredatı tüm dersler"),
    ],
    "malzeme": [
        ("📚", "1. sınıf dersleri neler?"),
        ("🔬", "MSNE 201 kaç AKTS?"),
        ("🧩", "Müfredat hakkında bilgi"),
        ("📋", "Tüm dersleri listele"),
    ],
}

if not st.session_state["messages"]:
    st.markdown(
        '<div class="welcome"><h3>💬 Sormak istediğin bir şey var mı?</h3>'
        '<p>Aşağıdaki örneklerden birini seç ya da kendi sorunu yaz.</p></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (icon, text) in enumerate(SUGGESTIONS.get(bolum_id, [])):
        with cols[i % 2]:
            if st.button(f"{icon}  {text}", key=f"sug_{i}", use_container_width=True):
                st.session_state["pending_q"] = text
                st.rerun()

# ============================ MESAJ GEÇMİŞİ ============================
for m in st.session_state["messages"]:
    avatar = "🧑‍🎓" if m["role"] == "user" else "🎓"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        if m.get("hits"):
            with st.expander("🔎 Kullanılan kaynaklar"):
                for i, h in enumerate(m["hits"], 1):
                    md = h["metadata"]
                    st.markdown(
                        f"**[{i}]** `{md.get('tip')}` — {md.get('kaynak','')} — "
                        f"dist={h['distance']:.3f}"
                    )
                    st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))

# ============================ CHAT INPUT ============================
q = st.chat_input("Örn: 2023 girişliyim 3. dönem hangi dersler var?")
if not q and "pending_q" in st.session_state:
    q = st.session_state.pop("pending_q")

if q:
    st.session_state["messages"].append({"role": "user", "content": q})
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(q)
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("✨ Düşünüyorum..."):
            try:
                result = answer(q, k=top_k, bolum=bolum_id)
                st.markdown(result["answer"])
                st.session_state["messages"].append(
                    {"role": "assistant", "content": result["answer"], "hits": result["hits"]}
                )
                with st.expander("🔎 Kullanılan kaynaklar"):
                    for i, h in enumerate(result["hits"], 1):
                        md = h["metadata"]
                        st.markdown(
                            f"**[{i}]** `{md.get('tip')}` — {md.get('kaynak','')} — dist={h['distance']:.3f}"
                        )
                        st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))
            except Exception as e:
                st.error(f"⚠️ Hata: {e}")

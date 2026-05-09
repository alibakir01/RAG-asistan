"""
Streamlit UI — AGÜ Mühendislik RAG Asistanı
Çalıştır: streamlit run app.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

import base64
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src import gpa
from src.rag import BOLUM_ADI_MAP, answer_stream, detect_bolum


# ============================ MODEL WARMUP ============================
# Embedder + reranker + BM25 indeksleri arka planda preload — ilk sorguda
# 5-15 saniye bekleme yerine kullanıcı yazarken paralel yüklensin.
@st.cache_resource(show_spinner=False)
def _warmup_models():
    import threading
    from src.rag import _get_embedder, _get_reranker, _get_bm25, BOLUM_ADI_MAP

    def _load():
        try:
            _get_embedder()
            _get_reranker()
            for bolum in BOLUM_ADI_MAP.keys():
                _get_bm25(bolum)
        except Exception:
            pass  # warmup hatası UI'yı durdurmasın

    t = threading.Thread(target=_load, daemon=True)
    t.start()
    return True


_warmup_models()

# ============================ LOGO ============================
_LOGO_PATH = Path(__file__).parent / "assets" / "agu_logo.png"
try:
    _LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    LOGO_DATA_URI = f"data:image/png;base64,{_LOGO_B64}"
except Exception:
    LOGO_DATA_URI = ""


# ============================ FEEDBACK LOG ============================
FEEDBACK_PATH = Path(__file__).parent / "data" / "feedback.jsonl"


def log_feedback(message_id: str, rating: str, question: str, answer_text: str,
                 bolum: str, hits: list[dict], comment: str = "") -> None:
    """Kullanıcı 👍/👎 feedback'ini JSONL'e ekle."""
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "message_id": message_id,
        "rating": rating,  # "up" | "down"
        "bolum": bolum,
        "question": question,
        "answer": answer_text,
        "comment": comment,
        "hits": [
            {"id": h.get("metadata", {}).get("ders_kodu") or h.get("metadata", {}).get("madde_no"),
             "tip": h.get("metadata", {}).get("tip"),
             "kaynak": h.get("metadata", {}).get("kaynak"),
             "distance": h.get("distance")}
            for h in (hits or [])[:8]
        ],
    }
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================ SESSION-LEVEL CACHE ============================
# Streaming + cache uyumu: aynı (soru, bölüm, k, history) için sonuç
# session boyunca yeniden hesaplanmasın. LLM cevabı stream'lendikten sonra
# tam metin + hits buraya kaydedilir.
def _cache_key(q: str, k: int, bolum: str, history_json: str) -> str:
    return f"{bolum}|{k}|{hash(history_json)}|{q}"


def get_cached(q: str, k: int, bolum: str, history_json: str) -> dict | None:
    return st.session_state.setdefault("_qa_cache", {}).get(
        _cache_key(q, k, bolum, history_json)
    )


def set_cached(q: str, k: int, bolum: str, history_json: str, payload: dict) -> None:
    st.session_state.setdefault("_qa_cache", {})[
        _cache_key(q, k, bolum, history_json)
    ] = payload

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
    [data-testid="stSidebar"] .sidebar-logo .agu-logo {
        display: block;
        width: 64px;
        height: auto;
        margin: 0 auto 8px auto;
        filter: drop-shadow(0 6px 18px rgba(194, 24, 91, 0.35));
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

    /* ==== Selectbox DROPDOWN (popup) — tüm öğeler görünsün ==== */
    /* Container — yeterli yükseklik ver, scroll yokken tüm öğeler sığsın */
    [data-baseweb="popover"],
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"],
    [data-baseweb="select-dropdown"] {
        background: #1A1D24 !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        max-height: 600px !important;
        overflow-y: auto !important;
    }
    /* Tüm dropdown öğeleri (li/option) — ZORUNLU GÖRÜNÜR */
    [data-baseweb="popover"] [role="option"],
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li,
    [data-baseweb="select-dropdown"] li {
        color: rgba(255,255,255,0.92) !important;
        background: transparent !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        padding: 10px 14px !important;
        line-height: 1.4 !important;
    }
    /* Öğe içindeki text node (BaseWeb genelde <div> sarar) */
    [data-baseweb="popover"] [role="option"] *,
    [data-baseweb="menu"] li * {
        color: inherit !important;
        opacity: 1 !important;
        visibility: visible !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="menu"] li:hover {
        background: rgba(255,184,0,0.12) !important;
        color: #FFE9C4 !important;
    }
    /* Aktif/seçili öğe — text görünür, sadece arka plan vurgulanır */
    [data-baseweb="popover"] [role="option"][aria-selected="true"],
    [data-baseweb="popover"] [role="option"][aria-checked="true"],
    [data-baseweb="menu"] li[aria-selected="true"] {
        background: rgba(194,24,91,0.18) !important;
        color: #FFE9C4 !important;
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

    /* ============= Feedback (👍/👎) butonları — outline SVG ikonlar ============= */
    /* Kolonları yapıştır */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] {
        gap: 0 !important;
    }
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    /* Buton: 30x30 kare, transparan, çerçevesiz */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] .stButton button {
        width: 30px !important;
        height: 30px !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 2px !important;
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 0 !important;
        color: transparent !important;
        line-height: 0 !important;
        position: relative !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 20px 20px !important;
        transition: background-image 0.18s ease, transform 0.18s ease, filter 0.18s ease !important;
    }
    /* Tüm iç içeriği gizle (emoji p, container div, vs.) */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"] .stButton button * {
        display: none !important;
    }
    /* 1. kolon — Thumbs UP (default beyaz) */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"]
        [data-testid="stColumn"]:nth-of-type(1) .stButton button {
        background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ffffffd9' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 10v12'/%3E%3Cpath d='M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z'/%3E%3C/svg%3E") !important;
    }
    /* 1. kolon hover — yeşil */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"]
        [data-testid="stColumn"]:nth-of-type(1) .stButton button:hover {
        background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232ecc71' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 10v12'/%3E%3Cpath d='M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z'/%3E%3C/svg%3E") !important;
        transform: scale(1.18) !important;
    }
    /* 2. kolon — Thumbs DOWN (default beyaz) */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"]
        [data-testid="stColumn"]:nth-of-type(2) .stButton button {
        background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ffffffd9' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M17 14V2'/%3E%3Cpath d='M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z'/%3E%3C/svg%3E") !important;
    }
    /* 2. kolon hover — kırmızı */
    [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"]
        [data-testid="stColumn"]:nth-of-type(2) .stButton button:hover {
        background-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23e74c3c' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M17 14V2'/%3E%3Cpath d='M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z'/%3E%3C/svg%3E") !important;
        transform: scale(1.18) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================ SIDEBAR ============================
with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-logo">
            <img src="{LOGO_DATA_URI}" alt="AGÜ" class="agu-logo" />
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
            "Mimarlık",
            "İşletme",
        ],
    )
    BOLUM_ID_MAP = {
        "Bilgisayar Mühendisliği": "bilgisayar",
        "Makine Mühendisliği": "makine",
        "Endüstri Mühendisliği": "endustri",
        "Elektrik-Elektronik Mühendisliği": "elektrik",
        "İnşaat Mühendisliği": "insaat",
        "Malzeme Bilimi ve Nanoteknoloji Mühendisliği": "malzeme",
        "Mimarlık": "mimarlik",
        "İşletme": "isletme",
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
        "mimarlik": (
            '<span class="bolum-icon" title="Mimarlık">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M3 21h18"/>'
            '<path d="M5 21V8l7-5 7 5v13"/>'
            '<path d="M9 21v-6h6v6"/>'
            '</svg></span>'
        ),
        "isletme": (
            '<span class="bolum-icon" title="İşletme">'
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M3 21V8h18v13"/>'
            '<path d="M9 21V12h6v9"/>'
            '<path d="M3 8l9-5 9 5"/>'
            '<path d="M7 16h2"/><path d="M15 16h2"/>'
            '</svg></span>'
        ),
    }
    bolum_id = BOLUM_ID_MAP[bolum_secim]
    bolum_icon = BOLUM_SVG[bolum_id]

    # Bölüm değiştiyse konuşma geçmişini + GPA state'ini sıfırla.
    if st.session_state.get("_active_bolum") != bolum_id:
        st.session_state["_active_bolum"] = bolum_id
        st.session_state["messages"] = []
        st.session_state["_qa_cache"] = {}
        for k in list(st.session_state.keys()):
            if isinstance(k, str) and k.startswith("gpa_"):
                del st.session_state[k]

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
        st.session_state["_qa_cache"] = {}
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

# ============================ TABS ============================
chat_tab, gpa_tab = st.tabs(["💬 Asistan", "📊 GPA Hesaplayıcı"])

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
    "mimarlik": [
        ("📚", "1. sınıf mimarlık dersleri neler?"),
        ("🏛️", "ARCH 101 dersinin içeriği nedir?"),
        ("🧩", "ARCH 223 kaç kredi?"),
        ("📋", "3. sınıf güz dönemi dersleri"),
    ],
    "isletme": [
        ("📚", "1. sınıf işletme dersleri neler?"),
        ("📊", "BA 207 Principles of Finance kaç AKTS?"),
        ("🧩", "BA 222 ön şartı var mı?"),
        ("📋", "3. sınıf güz dönemi dersleri"),
    ],
}

with chat_tab:
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
def _render_sources(hits: list[dict], key_prefix: str):
    if not hits:
        return
    with st.expander("🔎 Kullanılan kaynaklar"):
        for i, h in enumerate(hits, 1):
            md = h.get("metadata", {})
            dist = h.get("distance", 0.0) or 0.0
            st.markdown(
                f"**[{i}]** `{md.get('tip')}` — {md.get('kaynak','')} — "
                f"dist={dist:.3f}"
            )
            st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))


def _render_rating(msg_idx: int, m: dict):
    """Asistan mesajı altına 👍/👎 + opsiyonel yorum kutusu."""
    rating = m.get("rating")
    msg_id = m.get("id", f"msg-{msg_idx}")

    if rating:
        st.caption(
            f"{'👍' if rating == 'up' else '👎'} Geri bildirimin için teşekkürler."
        )
        return

    cols = st.columns([1, 1, 8])
    if cols[0].button("👍", key=f"up-{msg_id}", help="Bu cevap işime yaradı"):
        m["rating"] = "up"
        log_feedback(
            message_id=msg_id, rating="up",
            question=m.get("question", ""),
            answer_text=m.get("content", ""),
            bolum=m.get("bolum", ""),
            hits=m.get("hits", []),
        )
        st.rerun()
    if cols[1].button("👎", key=f"down-{msg_id}", help="Bu cevap yetersiz / yanlış"):
        st.session_state[f"_pending_down_{msg_id}"] = True

    if st.session_state.get(f"_pending_down_{msg_id}"):
        comment = st.text_input(
            "Neyin eksik/yanlış olduğunu yazar mısın? (opsiyonel)",
            key=f"comment-{msg_id}",
            placeholder="Örn: ön şartı yanlış söyledi",
        )
        if st.button("Gönder", key=f"send-{msg_id}", type="primary"):
            m["rating"] = "down"
            log_feedback(
                message_id=msg_id, rating="down",
                question=m.get("question", ""),
                answer_text=m.get("content", ""),
                bolum=m.get("bolum", ""),
                hits=m.get("hits", []),
                comment=comment or "",
            )
            st.session_state.pop(f"_pending_down_{msg_id}", None)
            st.rerun()


# ============================ CHAT — TEMİZ RERUN PATTERN ============================
# Sıra: history → (varsa) yeni turn → chat_input (en altta).
# Submit olduğunda _processing_q flag'i set edip st.rerun() yapıyoruz; bir sonraki
# çalıştırmada eski DOM tamamen yenilenir, ghost element kalmaz.
with chat_tab:
    # 1) Geçmiş mesajları render et
    for idx, m in enumerate(st.session_state["messages"]):
        avatar = "🧑‍🎓" if m["role"] == "user" else "🎓"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])
            if m["role"] == "assistant":
                _render_sources(m.get("hits", []), key_prefix=f"hist-{idx}")
                _render_rating(idx, m)

    # 2) Bekleyen bir soru varsa: yeni turn'ü tarihçenin hemen altına stream'le
    pending = st.session_state.pop("_processing_q", None)
    if pending:
        q = pending
        detected = detect_bolum(q)
        effective_bolum = detected if detected and detected != bolum_id else bolum_id
        auto_switched = detected is not None and detected != bolum_id

        st.session_state["messages"].append({"role": "user", "content": q})
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(q)
            if auto_switched:
                st.info(
                    f"🔀 Bu soru **{BOLUM_ADI_MAP[detected]}** ile ilgili görünüyor — "
                    f"cevabı o bölümün kaynaklarından getiriyorum.",
                    icon="ℹ️",
                )

        history_for_rag = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state["messages"][:-1]
            if m["role"] in ("user", "assistant")
        ]
        history_json = json.dumps(history_for_rag, ensure_ascii=False) if history_for_rag else ""

        msg_id = f"msg-{int(time.time() * 1000)}"

        with st.chat_message("assistant", avatar="🎓"):
            try:
                cached = get_cached(q, top_k, effective_bolum, history_json)
                if cached:
                    st.markdown(cached["answer"])
                    final_text = cached["answer"]
                    final_hits = cached["hits"]
                else:
                    # Spinner için explicit placeholder — stream başlamadan ÖNCE temizlenir
                    status_ph = st.empty()
                    status_ph.markdown(
                        '<div style="display:flex;align-items:center;gap:8px;'
                        'opacity:0.75;font-size:0.95rem;">'
                        '<span class="thinking-dot">●</span> '
                        '<em>Düşünüyorum…</em></div>'
                        '<style>.thinking-dot{animation:pulse 1.2s ease-in-out infinite;'
                        'color:#FFB800;}@keyframes pulse{0%,100%{opacity:0.3}50%{opacity:1}}</style>',
                        unsafe_allow_html=True,
                    )
                    result = answer_stream(q, k=top_k, bolum=effective_bolum, history=history_for_rag)
                    status_ph.empty()  # spinner'ı KESİN sil — stream başlamadan önce
                    final_hits = result["hits"]
                    if result["mode"] == "llm":
                        final_text = st.write_stream(result["token_iter"])
                    else:
                        st.markdown(result["text"])
                        final_text = result["text"]
                    set_cached(q, top_k, effective_bolum, history_json, {
                        "answer": final_text, "hits": final_hits,
                    })

                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": final_text,
                    "hits": final_hits,
                    "id": msg_id,
                    "question": q,
                    "bolum": effective_bolum,
                })
                _render_sources(final_hits, key_prefix=f"new-{msg_id}")
                _render_rating(len(st.session_state["messages"]) - 1, st.session_state["messages"][-1])
            except Exception as e:
                st.error(f"⚠️ Hata: {e}")

    # 3) Chat input — her zaman EN ALTTA (DOM sırasının sonunda)
    new_q = st.chat_input("Örn: 2023 girişliyim 3. dönem hangi dersler var?")
    pending_from_suggestion = st.session_state.pop("pending_q", None)
    submission = new_q or pending_from_suggestion
    if submission:
        st.session_state["_processing_q"] = submission
        st.rerun()


# ============================ GPA TAB ============================
with gpa_tab:
    st.markdown("### 📊 GPA Hesaplayıcı")
    st.caption(
        f"**Aktif bölüm:** {bolum_secim} · "
        "Sınıfını seç, bu dönem aldığın derslere harf notunu gir, geçmiş ortalamanı yaz — "
        "yeni Genel Ortalamanı (CGPA) hesaplayalım."
    )

    cur_years = gpa.available_curricula(bolum_id)
    if not cur_years:
        st.warning("Bu bölüm için henüz müfredat verisi yüklenmemiş.")
    else:
        # ---- Seçimler: müfredat yılı + sınıf + dönem ----
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            sel_year = st.selectbox(
                "📚 Müfredat yılı",
                cur_years,
                index=len(cur_years) - 1,
                key=f"gpa_year_{bolum_id}",
            )
        with sc2:
            SINIF_LABELS = {1: "1. Sınıf", 2: "2. Sınıf", 3: "3. Sınıf", 4: "4. Sınıf", 0: "Tüm sınıflar"}
            sel_sinif = st.selectbox(
                "🎓 Sınıf",
                options=[1, 2, 3, 4, 0],
                index=0,
                format_func=lambda x: SINIF_LABELS[x],
                key=f"gpa_sinif_{bolum_id}",
            )
        with sc3:
            if sel_sinif == 0:
                donem_opts = [0]
                donem_labels = {0: "Tüm Dönemler"}
            else:
                d1 = sel_sinif * 2 - 1
                d2 = sel_sinif * 2
                donem_opts = [0, d1, d2]
                donem_labels = {0: "İki Dönem de", d1: f"{d1}. Dönem (Güz)", d2: f"{d2}. Dönem (Bahar)"}
                
            sel_donem = st.selectbox(
                "📅 Dönem",
                options=donem_opts,
                index=0,
                format_func=lambda x: donem_labels[x],
                key=f"gpa_donem_{bolum_id}",
            )

        # ---- Geçmiş CGPA + kredi ----
        st.markdown("#### Geçmiş Akademik Bilgi")
        gc1, gc2 = st.columns(2)
        with gc1:
            prev_cgpa = st.number_input(
                "Geçmiş Genel Ortalaman (önceki CGPA)",
                min_value=0.0, max_value=4.0, value=0.0, step=0.01,
                key=f"gpa_prev_cgpa_{bolum_id}",
                help="Bu döneme girmeden önceki kümülatif ortalaman. İlk dönemse 0.00 bırak.",
            )
        with gc2:
            prev_credits = st.number_input(
                "Önceki Toplam Kredi",
                min_value=0, max_value=300, value=0, step=1,
                key=f"gpa_prev_cred_{bolum_id}",
                help="Şimdiye kadar geçtiğin derslerin toplam kredisi.",
            )

        st.markdown("---")

        # ---- Müfredat tablosu (sınıfa göre filtreli) ----
        df_key = f"gpa_df_{bolum_id}_{sel_year}_{sel_sinif}_{sel_donem}"
        if df_key not in st.session_state:
            courses = gpa.courses_for_year(bolum_id, sel_year, sel_sinif, sel_donem)
            st.session_state[df_key] = pd.DataFrame([
                {
                    "Dönem": c["donem"],
                    "Ders Kodu": c["ders_kodu"],
                    "Ders Adı": c["ders_adi"],
                    "Kredi": c["kredi"],
                    "AKTS": c["akts"],
                    "Not": "—",
                    "P/F": gpa.is_default_pf(c["ders_kodu"], c["ders_adi"]),
                }
                for c in courses
            ])

        sinif_label = SINIF_LABELS[sel_sinif]
        donem_label = donem_labels[sel_donem] if sel_donem != 0 else ""
        donem_text = f" ({donem_label})" if donem_label else ""
        st.markdown(f"##### Bu Dönem Dersleri — {sinif_label}{donem_text}")
        if st.session_state[df_key].empty:
            st.info("Bu sınıf için müfredatta ders bulunamadı.")
            edited = st.session_state[df_key]
        else:
            edited = st.data_editor(
                st.session_state[df_key],
                column_config={
                    "Dönem": st.column_config.NumberColumn(width="small", disabled=True),
                    "Ders Kodu": st.column_config.TextColumn(width="small", disabled=True),
                    "Ders Adı": st.column_config.TextColumn(width="medium", disabled=True),
                    "Kredi": st.column_config.NumberColumn(width="small", disabled=True),
                    "AKTS": st.column_config.NumberColumn(width="small", disabled=True),
                    "Not": st.column_config.SelectboxColumn(
                        options=gpa.GRADE_OPTIONS, width="small",
                        help="Bu dönem aldığın harf notu (A, A-, B+, ...). Almadıysan '—' bırak.",
                    ),
                    "P/F": st.column_config.CheckboxColumn(
                        width="small",
                        help="Pass/Fail dersi (GPA'ya katılmaz; AKTS sayılır).",
                    ),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key=f"editor_{df_key}",
            )

        # ---- Müfredat dışı ekstra dersler ----
        extra_key = f"gpa_extras_{bolum_id}"
        if extra_key not in st.session_state:
            st.session_state[extra_key] = pd.DataFrame(
                columns=["Ders Kodu", "Ders Adı", "Kredi", "AKTS", "Not", "Tip", "P/F"]
            )

        with st.expander("➕ Müfredat dışı ders ekle (yatay geçiş, intibak, yaz okulu...)"):
            # ----- Arama + ekle widget'ı (tüm bölüm-müfredatlarındaki dersler) -----
            catalog = gpa.all_courses_catalog()
            code_options = [""] + sorted(catalog.keys())

            def _fmt_option(c: str) -> str:
                if not c:
                    return "— ders ara veya kod yaz —"
                info = catalog[c]
                return f"{c} — {info['ders_adi']} ({info['kredi']} kredi · {info['akts']} AKTS)"

            sc1, sc2 = st.columns([5, 1])
            with sc1:
                sel_code = st.selectbox(
                    "🔎 Ders ara (kod veya isim ile filtrele — yazmaya başla)",
                    options=code_options,
                    format_func=_fmt_option,
                    index=0,
                    key=f"gpa_extra_search_{bolum_id}",
                )
            with sc2:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                if st.button("➕ Ekle", key=f"gpa_extra_add_{bolum_id}", use_container_width=True):
                    if sel_code:
                        c = catalog[sel_code]
                        existing = st.session_state[extra_key]
                        already = (
                            "Ders Kodu" in existing.columns
                            and (existing["Ders Kodu"].astype(str).str.upper() == c["ders_kodu"]).any()
                        )
                        if not already:
                            new_row = pd.DataFrame([{
                                "Ders Kodu": c["ders_kodu"],
                                "Ders Adı": c["ders_adi"],
                                "Kredi": c["kredi"],
                                "AKTS": c["akts"],
                                "Not": "—",
                                "Tip": "Yatay geçiş",
                                "P/F": gpa.is_default_pf(c["ders_kodu"], c["ders_adi"]),
                            }])
                            st.session_state[extra_key] = pd.concat(
                                [existing, new_row], ignore_index=True
                            )
                            st.rerun()

            st.caption(
                "Aradığın dersi seç → **➕ Ekle** → ders kodu, adı, kredi ve AKTS otomatik dolar. "
                "Sadece harf notunu seçmen yeterli. Manuel satır da ekleyebilirsin."
            )

            edited_extras = st.data_editor(
                st.session_state[extra_key],
                column_config={
                    "Ders Kodu": st.column_config.TextColumn(width="small"),
                    "Ders Adı": st.column_config.TextColumn(width="medium"),
                    "Kredi": st.column_config.NumberColumn(min_value=0, max_value=15, default=3, width="small"),
                    "AKTS": st.column_config.NumberColumn(min_value=0, max_value=30, default=5, width="small"),
                    "Not": st.column_config.SelectboxColumn(options=gpa.GRADE_OPTIONS, default="—", width="small"),
                    "Tip": st.column_config.SelectboxColumn(options=gpa.EXTRA_TYPES, width="medium"),
                    "P/F": st.column_config.CheckboxColumn(width="small"),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key=f"editor_{extra_key}",
            )

        # ---- Hesapla / Sıfırla ----
        bc1, bc2 = st.columns([1, 1])
        do_calc = bc1.button("🎯 Yeni CGPA Hesapla", type="primary", use_container_width=True)
        if bc2.button("🔄 Notları Sıfırla", use_container_width=True):
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and (k.startswith("gpa_df_") or k.startswith("editor_gpa_df_") or k == extra_key or k == f"editor_{extra_key}"):
                    st.session_state.pop(k, None)
            st.rerun()

        if do_calc:
            entries: list[dict] = []
            if hasattr(edited, "iterrows"):
                for _, r in edited.iterrows():
                    grade = str(r.get("Not", "—") or "—").strip()
                    if grade in ("", "—", "nan"):
                        continue
                    entries.append({
                        "ders_kodu": str(r["Ders Kodu"]),
                        "kredi": int(r["Kredi"] or 0),
                        "akts": int(r["AKTS"] or 0),
                        "not": grade,
                        "pf": bool(r.get("P/F")),
                    })
            for _, r in edited_extras.iterrows():
                kod = str(r.get("Ders Kodu", "") or "").strip()
                grade = str(r.get("Not", "—") or "—").strip()
                if not kod or grade in ("", "—", "nan"):
                    continue
                entries.append({
                    "ders_kodu": kod,
                    "kredi": int(r["Kredi"] or 0) if pd.notna(r.get("Kredi")) else 0,
                    "akts": int(r["AKTS"] or 0) if pd.notna(r.get("AKTS")) else 0,
                    "not": grade,
                    "pf": bool(r.get("P/F")),
                })

            if not entries:
                st.warning("Hiç not girilmemiş. En az bir derse harf notu seç.")
            else:
                # Validation: prev_cgpa > 0 ama prev_credits = 0 → uyar (yoksa CGPA = sem_gpa olur)
                if prev_cgpa > 0 and int(prev_credits) == 0:
                    st.error(
                        "⚠️ **Geçmiş Genel Ortalaman'ı girdin ama 'Önceki Toplam Kredi' = 0.** "
                        "Doğru CGPA hesabı için ikisini de girmen gerek (örn. 2. yıl sonu: ~60 kredi). "
                        "Aksi halde Yeni CGPA, Bu Dönem GPA'sı ile aynı çıkacaktır."
                    )

                result = gpa.compute_combined(prev_cgpa, int(prev_credits), entries)
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🎯 Yeni CGPA", f"{result['new_cgpa']:.2f} / 4.00",
                          delta=f"{result['new_cgpa'] - result['prev_cgpa']:+.2f}"
                          if result['prev_credits'] > 0 else None)
                m2.metric("📅 Bu Dönem GPA", f"{result['sem_gpa']:.2f}")
                m3.metric(
                    "✅ Geçen / ❌ Kalan",
                    f"{result['sem_passed']} / {result['sem_failed']}",
                )
                m4.metric("📊 Toplam Kredi", result['total_credits'],
                          delta=f"+{result['sem_credits']} bu dönem" if result['sem_credits'] else None)

                # Şeffaf hesap kırılımı — kullanıcı formülü görsün
                prev_pts = result['prev_cgpa'] * result['prev_credits']
                sem_pts_calc = result['sem_gpa'] * result['sem_credits']
                with st.expander("🧮 Hesap detayı"):
                    st.markdown(
                        f"""
**Formül:**
`Yeni CGPA = (Geçmiş CGPA × Geçmiş Kredi + Bu dönem puanları) / Toplam Kredi`

| | Kredi | Ortalama | Puan |
|---|---:|---:|---:|
| Geçmiş | {result['prev_credits']} | {result['prev_cgpa']:.2f} | {prev_pts:.2f} |
| Bu dönem | {result['sem_credits']} | {result['sem_gpa']:.2f} | {sem_pts_calc:.2f} |
| **Toplam** | **{result['total_credits']}** | **{result['new_cgpa']:.2f}** | **{prev_pts + sem_pts_calc:.2f}** |

`{prev_pts:.2f} + {sem_pts_calc:.2f} = {prev_pts + sem_pts_calc:.2f}` puan ÷ `{result['total_credits']}` kredi = **{result['new_cgpa']:.2f}**
                        """
                    )

                if result["onor"]:
                    st.success(f"**{result['onor']}** kategorisindesin! (CGPA ≥ "
                               f"{gpa.YUKSEK_ONOR_THRESHOLD if 'Yüksek' in result['onor'] else gpa.ONOR_THRESHOLD:.2f})")
                elif result["new_cgpa"] > 0:
                    delta = gpa.ONOR_THRESHOLD - result["new_cgpa"]
                    if delta > 0:
                        st.info(f"Onur eşiğine **{delta:.2f}** puan kaldı (3.00).")

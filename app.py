"""
Streamlit UI — AGÜ Bilgisayar Müh. RAG Asistanı
Çalıştır: streamlit run app.py
"""
import os
from dotenv import load_dotenv

# API key'i .env dosyasından yükle
load_dotenv()

import streamlit as st
import streamlit.components.v1 as components
from src.rag import answer

st.set_page_config(page_title="AGÜ Öğrenci Asistanı", page_icon="🎓", layout="wide")

with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 25px;">
            <h2 style="margin-bottom: 5px;">🎓 AGÜ Asistanı</h2>
            <span style="opacity: 0.7; font-size: 0.9em;">Yapay Zeka Destekli Öğrenci Rehberi</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    bolum_secim = st.selectbox(
        "📚 **Bölüm Seçimi**",
        ["Bilgisayar Mühendisliği", "Makine Mühendisliği", "Endüstri Mühendisliği", "Elektrik-Elektronik Mühendisliği", "İnşaat Mühendisliği", "Malzeme Bilimi ve Nanoteknoloji Mühendisliği"]
    )
    BOLUM_ID_MAP = {
        "Bilgisayar Mühendisliği": "bilgisayar",
        "Makine Mühendisliği": "makine",
        "Endüstri Mühendisliği": "endustri",
        "Elektrik-Elektronik Mühendisliği": "elektrik",
        "İnşaat Mühendisliği": "insaat",
        "Malzeme Bilimi ve Nanoteknoloji Mühendisliği": "malzeme",
    }
    bolum_id = BOLUM_ID_MAP[bolum_secim]
    
    st.info(f"💡 **{bolum_secim}** müfredatı, ders içerikleri ve staj yönergeleri hakkında merak ettiğiniz her şeyi sorabilirsiniz.")
    
    st.divider()
    st.markdown("⚙️ **Cevap Detay Seviyesi**")

    level_info = {
        "Kısa": "Net, tek bilgi soruları için (örn. COMP 101 kaç kredi?)",
        "Dengeli": "Günlük kullanım için ideal — çoğu soruya uyar.",
        "Kapsamlı": "Karşılaştırma / geniş konu soruları için (örn. 2016 ve 2023 müfredatı ne fark var?)",
    }
    level_to_k = {"Kısa": 4, "Dengeli": 8, "Kapsamlı": 14}

    # UI adjustments using CSS
    st.markdown(
        """
        <style>
        /* Sürüklerken çıkan değer kutucuğunu (thumb) özelleştir ve renklendir */
        div[data-testid="stThumbValue"] {
            font-weight: bold !important;
            color: #FF4B4B !important;
            font-size: 1.1rem !important;
            cursor: help !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # JS ile Thumb üzerine gelince çıkacak baloncukları (tooltip) ekle
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

    level_options = ["Kısa", "Dengeli", "Kapsamlı"]
    default_level = "Dengeli"

    detail_level = st.select_slider(
        "detay",
        options=level_options,
        value=default_level,
        label_visibility="collapsed",
    )
    st.markdown(
        f"""
        <div style="padding: 10px; border-radius: 8px; border-left: 4px solid #FF4B4B; background-color: var(--secondary-background-color); margin-top: 15px; font-size: 0.85em; line-height: 1.4;">
            <strong style="color: var(--text-color);">Ayar: {detail_level}</strong><br>
            <span style="color: var(--text-color); opacity: 0.8;">{level_info[detail_level]}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
    top_k = level_to_k[detail_level]

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
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

q = st.chat_input("Örn: 2023 girişliyim 3. dönem hangi dersler var?")
if not q and "pending_q" in st.session_state:
    q = st.session_state.pop("pending_q")

if q:
    st.session_state["messages"].append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("Düşünüyorum..."):
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
                st.error(f"Hata: {e}")

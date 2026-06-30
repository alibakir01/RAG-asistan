"""
AGÜ RAG Asistanı — hafif bulut arayüzü (Streamlit Community Cloud için).

Torch/chroma YÜKLEMEZ. Retrieval'ı Voyage + Pinecone (src/rag_cloud.py) ile yapar;
GPA hesaplayıcı src/gpa.py ile (o zaten saf-Python). Ağır yerel sürüm app.py'dir.

Çalıştır (yerel):  streamlit run streamlit_app.py
Streamlit Cloud:   Main file = streamlit_app.py, Secrets paneline anahtarları gir.
"""
import os
from pathlib import Path

import streamlit as st

# --------------------------------------------------------------------------- #
# Anahtar köprüsü: Streamlit Cloud secrets.toml -> os.environ (yerelde .env)
# rag_cloud import'undan ÖNCE.
# --------------------------------------------------------------------------- #
_KEYS = ["VOYAGE_AI_KEY", "PINECONE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
         "LLM_PROVIDER", "OPENROUTER_MODEL"]
try:
    for _k in _KEYS:
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

import pandas as pd

from src import gpa, rag_cloud

# --------------------------------------------------------------------------- #
# Sayfa
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="AGÜ RAG Asistanı", page_icon="🎓", layout="centered")

_LOGO = Path(__file__).parent / "assets" / "agu_logo.png"
hcol1, hcol2 = st.columns([1, 6])
with hcol1:
    if _LOGO.exists():
        st.image(str(_LOGO), width=64)
with hcol2:
    st.title("AGÜ RAG Asistanı")

# Anahtar kontrolü
if not os.getenv("VOYAGE_AI_KEY") or not os.getenv("PINECONE_API_KEY"):
    st.error("VOYAGE_AI_KEY / PINECONE_API_KEY tanımlı değil. Streamlit Cloud → Settings → Secrets'a ekle.")
    st.stop()

# --------------------------------------------------------------------------- #
# Bölüm seçimi (chat + GPA için ortak)
# --------------------------------------------------------------------------- #
_BOLUM_IDS = list(rag_cloud.BOLUM_ADI_MAP.keys())
with st.sidebar:
    st.markdown("### Bölüm")
    bolum_id = st.selectbox(
        "Aktif bölüm",
        options=_BOLUM_IDS,
        format_func=lambda b: rag_cloud.BOLUM_ADI_MAP[b],
        index=0,
        label_visibility="collapsed",
    )
    st.caption("Sorular ve GPA hesaplayıcı bu bölüme göre çalışır.")
bolum_secim = rag_cloud.BOLUM_ADI_MAP[bolum_id]

chat_tab, gpa_tab = st.tabs(["💬 Asistan", "📊 GPA Hesaplayıcı"])

# ============================ ASİSTAN ============================
with chat_tab:
    st.caption(f"**{bolum_secim}** · Müfredat, dersler, staj ve yönergeler. Cevaplar yalnızca AGÜ dokümanlarına dayanır.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if soru := st.chat_input("Örn: 2023 girişliyim 3. dönem hangi dersler var?"):
        st.session_state.messages.append({"role": "user", "content": soru})
        with st.chat_message("user"):
            st.markdown(soru)

        with st.chat_message("assistant"):
            try:
                r = rag_cloud.respond(soru, bolum=bolum_id)
                if r["mode"] == "list":
                    st.markdown(r["text"])
                    cevap = r["text"]
                else:
                    cevap = st.write_stream(r["token_iter"])
                st.caption(f"📚 {r['n']} kaynak · {rag_cloud.BOLUM_ADI_MAP.get(r['bolum'], 'AGÜ')}")
            except Exception as e:
                cevap = f"Bir hata oluştu: {e}"
                st.error(cevap)
        st.session_state.messages.append({"role": "assistant", "content": cevap})

# ============================ GPA HESAPLAYICI ============================
with gpa_tab:
    st.markdown("### 📊 GPA Hesaplayıcı")
    st.caption(
        f"**Aktif bölüm:** {bolum_secim} · Sınıfını seç, bu dönem aldığın derslere harf notunu gir, "
        "geçmiş ortalamanı yaz — yeni Genel Ortalamanı (CGPA) hesaplayalım."
    )

    cur_years = gpa.available_curricula(bolum_id)
    if not cur_years:
        st.warning("Bu bölüm için henüz müfredat verisi yüklenmemiş.")
    else:
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            sel_year = st.selectbox("📚 Müfredat yılı", cur_years, index=len(cur_years) - 1, key=f"gpa_year_{bolum_id}")
        with sc2:
            SINIF_LABELS = {1: "1. Sınıf", 2: "2. Sınıf", 3: "3. Sınıf", 4: "4. Sınıf", 0: "Tüm sınıflar"}
            sel_sinif = st.selectbox("🎓 Sınıf", options=[1, 2, 3, 4, 0], index=0,
                                     format_func=lambda x: SINIF_LABELS[x], key=f"gpa_sinif_{bolum_id}")
        with sc3:
            if sel_sinif == 0:
                donem_opts, donem_labels = [0], {0: "Tüm Dönemler"}
            else:
                d1, d2 = sel_sinif * 2 - 1, sel_sinif * 2
                donem_opts = [0, d1, d2]
                donem_labels = {0: "İki Dönem de", d1: f"{d1}. Dönem (Güz)", d2: f"{d2}. Dönem (Bahar)"}
            sel_donem = st.selectbox("📅 Dönem", options=donem_opts, index=0,
                                     format_func=lambda x: donem_labels[x], key=f"gpa_donem_{bolum_id}")

        st.markdown("#### Geçmiş Akademik Bilgi")
        gc1, gc2 = st.columns(2)
        with gc1:
            prev_cgpa = st.number_input("Geçmiş Genel Ortalaman (önceki CGPA)", min_value=0.0, max_value=4.0,
                                        value=0.0, step=0.01, key=f"gpa_prev_cgpa_{bolum_id}",
                                        help="Bu döneme girmeden önceki kümülatif ortalaman. İlk dönemse 0.00 bırak.")
        with gc2:
            prev_credits = st.number_input("Önceki Toplam Kredi", min_value=0, max_value=300, value=0, step=1,
                                           key=f"gpa_prev_cred_{bolum_id}",
                                           help="Şimdiye kadar geçtiğin derslerin toplam kredisi.")

        st.markdown("---")

        df_key = f"gpa_df_{bolum_id}_{sel_year}_{sel_sinif}_{sel_donem}"
        if df_key not in st.session_state:
            courses = gpa.courses_for_year(bolum_id, sel_year, sel_sinif, sel_donem)
            st.session_state[df_key] = pd.DataFrame([
                {"Dönem": c["donem"], "Ders Kodu": c["ders_kodu"], "Ders Adı": c["ders_adi"],
                 "Kredi": c["kredi"], "AKTS": c["akts"], "Not": "—",
                 "P/F": gpa.is_default_pf(c["ders_kodu"], c["ders_adi"])}
                for c in courses
            ])

        sinif_label = SINIF_LABELS[sel_sinif]
        donem_label = donem_labels[sel_donem] if sel_donem != 0 else ""
        st.markdown(f"##### Bu Dönem Dersleri — {sinif_label}{(' (' + donem_label + ')') if donem_label else ''}")
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
                    "Not": st.column_config.SelectboxColumn(options=gpa.GRADE_OPTIONS, width="small",
                                                            help="Bu dönem aldığın harf notu. Almadıysan '—' bırak."),
                    "P/F": st.column_config.CheckboxColumn(width="small",
                                                           help="Pass/Fail dersi (GPA'ya katılmaz; AKTS sayılır)."),
                },
                use_container_width=True, hide_index=True, num_rows="fixed", key=f"editor_{df_key}",
            )

        extra_key = f"gpa_extras_{bolum_id}"
        if extra_key not in st.session_state:
            st.session_state[extra_key] = pd.DataFrame(
                columns=["Ders Kodu", "Ders Adı", "Kredi", "AKTS", "Not", "Tip", "P/F"])

        with st.expander("➕ Müfredat dışı ders ekle (yatay geçiş, intibak, yaz okulu...)"):
            catalog = gpa.all_courses_catalog()
            code_options = [""] + sorted(catalog.keys())

            def _fmt_option(c: str) -> str:
                if not c:
                    return "— ders ara veya kod yaz —"
                info = catalog[c]
                return f"{c} — {info['ders_adi']} ({info['kredi']} kredi · {info['akts']} AKTS)"

            ec1, ec2 = st.columns([5, 1])
            with ec1:
                sel_code = st.selectbox("🔎 Ders ara (kod veya isim ile filtrele)", options=code_options,
                                        format_func=_fmt_option, index=0, key=f"gpa_extra_search_{bolum_id}")
            with ec2:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                if st.button("➕ Ekle", key=f"gpa_extra_add_{bolum_id}", use_container_width=True) and sel_code:
                    c = catalog[sel_code]
                    existing = st.session_state[extra_key]
                    already = ("Ders Kodu" in existing.columns
                               and (existing["Ders Kodu"].astype(str).str.upper() == c["ders_kodu"]).any())
                    if not already:
                        new_row = pd.DataFrame([{
                            "Ders Kodu": c["ders_kodu"], "Ders Adı": c["ders_adi"], "Kredi": c["kredi"],
                            "AKTS": c["akts"], "Not": "—", "Tip": "Yatay geçiş",
                            "P/F": gpa.is_default_pf(c["ders_kodu"], c["ders_adi"])}])
                        st.session_state[extra_key] = pd.concat([existing, new_row], ignore_index=True)
                        st.rerun()

            st.caption("Aradığın dersi seç → **➕ Ekle** → kredi/AKTS otomatik dolar. Sadece harf notunu seç.")

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
                use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_{extra_key}",
            )

        bc1, bc2 = st.columns([1, 1])
        do_calc = bc1.button("🎯 Yeni CGPA Hesapla", type="primary", use_container_width=True)
        if bc2.button("🔄 Notları Sıfırla", use_container_width=True):
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and (k.startswith("gpa_df_") or k.startswith("editor_gpa_df_")
                                           or k == extra_key or k == f"editor_{extra_key}"):
                    st.session_state.pop(k, None)
            st.rerun()

        if do_calc:
            entries: list[dict] = []
            if hasattr(edited, "iterrows"):
                for _, row in edited.iterrows():
                    grade = str(row.get("Not", "—") or "—").strip()
                    if grade in ("", "—", "nan"):
                        continue
                    entries.append({"ders_kodu": str(row["Ders Kodu"]), "kredi": int(row["Kredi"] or 0),
                                    "akts": int(row["AKTS"] or 0), "not": grade, "pf": bool(row.get("P/F"))})
            for _, row in edited_extras.iterrows():
                kod = str(row.get("Ders Kodu", "") or "").strip()
                grade = str(row.get("Not", "—") or "—").strip()
                if not kod or grade in ("", "—", "nan"):
                    continue
                entries.append({
                    "ders_kodu": kod,
                    "kredi": int(row["Kredi"] or 0) if pd.notna(row.get("Kredi")) else 0,
                    "akts": int(row["AKTS"] or 0) if pd.notna(row.get("AKTS")) else 0,
                    "not": grade, "pf": bool(row.get("P/F"))})

            if not entries:
                st.warning("Hiç not girilmemiş. En az bir derse harf notu seç.")
            else:
                if prev_cgpa > 0 and int(prev_credits) == 0:
                    st.error("⚠️ Geçmiş CGPA girdin ama 'Önceki Toplam Kredi' = 0. Doğru hesap için ikisini de gir.")
                result = gpa.compute_combined(prev_cgpa, int(prev_credits), entries)
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🎯 Yeni CGPA", f"{result['new_cgpa']:.2f} / 4.00",
                          delta=f"{result['new_cgpa'] - result['prev_cgpa']:+.2f}" if result['prev_credits'] > 0 else None)
                m2.metric("📅 Bu Dönem GPA", f"{result['sem_gpa']:.2f}")
                m3.metric("✅ Geçen / ❌ Kalan", f"{result['sem_passed']} / {result['sem_failed']}")
                m4.metric("📊 Toplam Kredi", result['total_credits'],
                          delta=f"+{result['sem_credits']} bu dönem" if result['sem_credits'] else None)

                prev_pts = result['prev_cgpa'] * result['prev_credits']
                sem_pts_calc = result['sem_gpa'] * result['sem_credits']
                with st.expander("🧮 Hesap detayı"):
                    st.markdown(
                        f"**Formül:** `Yeni CGPA = (Geçmiş CGPA × Geçmiş Kredi + Bu dönem puanları) / Toplam Kredi`\n\n"
                        f"| | Kredi | Ortalama | Puan |\n|---|---:|---:|---:|\n"
                        f"| Geçmiş | {result['prev_credits']} | {result['prev_cgpa']:.2f} | {prev_pts:.2f} |\n"
                        f"| Bu dönem | {result['sem_credits']} | {result['sem_gpa']:.2f} | {sem_pts_calc:.2f} |\n"
                        f"| **Toplam** | **{result['total_credits']}** | **{result['new_cgpa']:.2f}** | "
                        f"**{prev_pts + sem_pts_calc:.2f}** |\n"
                    )
                if result["onor"]:
                    thr = gpa.YUKSEK_ONOR_THRESHOLD if "Yüksek" in result["onor"] else gpa.ONOR_THRESHOLD
                    st.success(f"**{result['onor']}** kategorisindesin! (CGPA ≥ {thr:.2f})")
                elif result["new_cgpa"] > 0:
                    delta = gpa.ONOR_THRESHOLD - result["new_cgpa"]
                    if delta > 0:
                        st.info(f"Onur eşiğine **{delta:.2f}** puan kaldı (3.00).")

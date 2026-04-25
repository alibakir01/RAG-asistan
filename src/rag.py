"""
RAG çekirdeği: soru -> retrieval -> Groq (Llama 3.3 70B) ile Türkçe cevap.
Kullanım:
    python src/rag.py "2023 girişliyim 3. dönem hangi dersler var"

Ortam değişkeni: GROQ_API_KEY  (https://console.groq.com/keys — bedava)
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

import chromadb
from groq import Groq
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = ROOT / "data" / "chroma"
MODEL_NAME = "intfloat/multilingual-e5-large"
COLLECTION = "agu_comp"
LLM_MODEL = "llama-3.3-70b-versatile"  # Groq'ta bedava, Türkçesi iyi
TOP_K = 8

SYSTEM_PROMPT = """Sen Abdullah Gül Üniversitesi {bolum_adi} bölümü için bir yardımcı asistansın.
Öğrencilere müfredat, dersler, staj yönergesi gibi konularda Türkçe yardım edersin.

KURALLAR:
1. Sadece sana verilen BAĞLAM içindeki bilgilere dayanarak cevap ver.
2. Bağlamda olmayan bir şey sorulursa "Bu bilgi elimdeki dokümanlarda yok" de — UYDURMA.
3. Cevabı verirken hangi kaynağı kullandığını belirt (örn: "2023 müfredatına göre...", "Staj Yönergesi MADDE 10'a göre...").
4. Ders kodu, AKTS, dönem gibi sayısal bilgileri aynen aktar.
5. Samimi, öğrenci dostu bir ton kullan ama doğruluktan ödün verme.
6. Makine Mühendisliği için: 2022, 2023, 2024 ve 2025 girişli öğrenciler "2025" müfredatına tabidir. 2021 ve öncesi girişliler "2021" müfredatına tabidir.
7. Endüstri Mühendisliği için: 2016-2020 girişliler "2016" müfredatına, 2021-2024 girişliler "2021" müfredatına, 2025 ve sonrası "2025" müfredatına tabidir.
8. Bilgisayar Mühendisliği için: 2016-2020 girişliler "2016" müfredatına, 2021-2022 girişliler "2021" müfredatına, 2023-2024 girişliler "2023" müfredatına, 2025 ve sonrası "2025" müfredatına tabidir.
9. Bir dersin ön şartı (prerequisite) sorulursa: BAĞLAM'daki "Ön şart:" alanına bak. Değer "yok" ise "Bu dersin ön şartı yoktur" de. Aksi halde aynen aktar (örn "COMP 101"). Bu bilgi her ders chunk'ında MUTLAKA vardır — "bilgi yok" deme.
10. Elektrik-Elektronik Mühendisliği için: 2019-2020 girişliler "2019" Capsule müfredatına, 2021-2024 girişliler "2021" Capsule müfredatına, 2025 ve sonrası girişliler "2025" müfredatına tabidir. EE programında 3. ve 4. sınıfta "Seçmeli Kapsüller" (Elective Capsules) havuzundan dersler seçilir.
11. İnşaat Mühendisliği için: 2016-2020 girişliler "2016" müfredatına, 2021-2024 girişliler "2021" müfredatına, 2025 ve sonrası girişliler "2025" müfredatına tabidir.
"""


@lru_cache(maxsize=1)
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION)


# ----------------------------- Intent / Router -----------------------------

MUFREDAT_RE = re.compile(r"\b(20\d\d)\b")
DONEM_RE = re.compile(r"(\d+)\s*\.?\s*(?:dönem|yariyil|yarıyıl|semester)", re.IGNORECASE)
YIL_SEZON_RE = re.compile(r"(\d+)\s*\.?\s*y[ıi]l.{0,15}?(g[üu]z|bahar)", re.IGNORECASE)
# 1-4 arası tek hane ister; "2022 yılı" gibi giriş yıllarını yakalamasın
SINIF_RE = re.compile(r"\b([1-4])\s*\.?\s*(s[ıi]n[ıi]f|y[ıi]l)\b", re.IGNORECASE)
LIST_TRIGGERS = [
    "hangi dersler", "dersleri listele", "tüm dersler", "tum dersler",
    "ders listesi", "neler var", "hangi ders", "dersler neler",
    "dersleri neler", "dersleri ne", "ders neler",
    "sınıf dersleri", "sinif dersleri", "yıl dersleri", "yil dersleri",
    "ders programı", "ders programi", "müfredat", "mufredat",
    "sınıfta", "sinifta", "dönemde", "donemde", "dönem dersleri",
    "donem dersleri", "sınıfın dersleri", "sinifin dersleri",
    "dersler hangileri", "dersler neler", "listele",
]

LATEST_MUFREDAT = {"bilgisayar": "2025", "makine": "2025", "endustri": "2025", "elektrik": "2025", "insaat": "2025"}


def parse_intent(question: str, bolum: str) -> dict | None:
    """Soru bir 'dönem listesi' sorusu mu? İse mufredat + dönem döndür."""
    q = question.lower()
    is_list = any(t in q for t in LIST_TRIGGERS)
    if not is_list:
        return None

    muf = MUFREDAT_RE.search(question)
    mufredat_yili = None
    if muf:
        year = int(muf.group(1))
        if bolum == "makine":
            if 2022 <= year <= 2025:
                mufredat_yili = "2025"
            elif year <= 2021:
                mufredat_yili = "2021"
            else:
                mufredat_yili = str(year)
        elif bolum == "endustri":
            # Endüstri müfredatları: 2016 (16-21 arası), 2021 (21-25 arası), 2025 (25-26)
            if 2016 <= year <= 2020:
                mufredat_yili = "2016"
            elif 2021 <= year <= 2024:
                mufredat_yili = "2021"
            elif year >= 2025:
                mufredat_yili = "2025"
        elif bolum == "elektrik":
            # EE: 2019-2020 -> "2019" | 2021-2024 -> "2021" | 2025+ -> "2025"
            if 2019 <= year <= 2020:
                mufredat_yili = "2019"
            elif 2021 <= year <= 2024:
                mufredat_yili = "2021"
            elif year >= 2025:
                mufredat_yili = "2025"
        elif bolum == "insaat":
            # CE: 2016-2020 -> "2016" | 2021-2024 -> "2021" | 2025+ -> "2025"
            if 2016 <= year <= 2020:
                mufredat_yili = "2016"
            elif 2021 <= year <= 2024:
                mufredat_yili = "2021"
            elif year >= 2025:
                mufredat_yili = "2025"
        else:
            # Bilgisayar Mühendisliği:
            # 2016-2020 -> "2016" | 2021-2022 -> "2021" | 2023-2024 -> "2023" | 2025+ -> "2025"
            if 2016 <= year <= 2020:
                mufredat_yili = "2016"
            elif 2021 <= year <= 2022:
                mufredat_yili = "2021"
            elif 2023 <= year <= 2024:
                mufredat_yili = "2023"
            elif year >= 2025:
                mufredat_yili = "2025"

    donems: list[int] = []
    m = DONEM_RE.search(question)
    if m:
        donems = [int(m.group(1))]
    else:
        m2 = YIL_SEZON_RE.search(q)
        if m2:
            yil = int(m2.group(1))
            sezon = m2.group(2)
            donems = [(yil - 1) * 2 + (1 if sezon.startswith("g") else 2)]
        else:
            m3 = SINIF_RE.search(q)
            if m3:
                yil = int(m3.group(1))
                if 1 <= yil <= 4:
                    donems = [(yil - 1) * 2 + 1, (yil - 1) * 2 + 2]

    giris_yili = None
    if muf:
        try:
            giris_yili = int(muf.group(1))
        except (ValueError, TypeError):
            pass

    if not mufredat_yili and donems:
        mufredat_yili = LATEST_MUFREDAT.get(bolum)

    # Sınıf/dönem belirtilmemiş ama yıl + liste trigger varsa: TÜM müfredatı dök (8 dönem)
    if mufredat_yili and not donems:
        donems = [1, 2, 3, 4, 5, 6, 7, 8]

    if mufredat_yili and donems:
        return {"mufredat_yili": mufredat_yili, "donems": donems, "giris_yili": giris_yili}
    return None


COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,5})\s*[-_ ]?\s*(\d{2,4})\b")
PREREQ_TRIGGERS = ["ön şart", "on sart", "önşart", "onsart", "prereq", "ön koşul", "on kosul"]


def fetch_courses_by_code(code: str, bolum: str) -> list[dict]:
    """Verilen ders koduyla eşleşen tüm chunk'ları çek (tüm müfredat yıllarından)."""
    col = _get_collection()
    # Hem boşluklu hem boşluksuz varyantı dene
    code_norm = re.sub(r"\s+", "", code).upper()
    code_spaced = re.sub(r"([A-Z]+)(\d+)", r"\1 \2", code_norm)
    hits = []
    seen = set()
    for code_var in {code_norm, code_spaced, code.upper()}:
        try:
            r = col.get(where={"$and": [{"bolum": bolum}, {"ders_kodu": code_var}]})
            for _id, doc, md in zip(r["ids"], r["documents"], r["metadatas"]):
                if _id in seen:
                    continue
                seen.add(_id)
                hits.append({"text": doc, "metadata": md, "distance": 0.0})
        except Exception:
            continue
    return hits


def fetch_semester_courses(mufredat_yili: str, donems: list[int], bolum: str) -> list[dict]:
    col = _get_collection()
    donem_clause = {"donem": donems[0]} if len(donems) == 1 else {"donem": {"$in": donems}}
    r = col.get(where={"$and": [{"mufredat_yili": mufredat_yili}, donem_clause, {"bolum": bolum}]})
    hits = []
    for _id, doc, md in zip(r["ids"], r["documents"], r["metadatas"]):
        hits.append({"text": doc, "metadata": md, "distance": 0.0})
    hits.sort(key=lambda h: (h["metadata"].get("donem", 0), h["metadata"].get("ders_kodu", "")))
    return hits


def retrieve(question: str, k: int = TOP_K, bolum: str = "bilgisayar") -> list[dict]:
    model = _get_embedder()
    col = _get_collection()
    emb = model.encode([f"query: {question}"], normalize_embeddings=True).tolist()
    r = col.query(query_embeddings=emb, n_results=k, where={"bolum": bolum})
    hits = []
    for doc, md, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        hits.append({"text": doc, "metadata": md, "distance": dist})
    return hits


def format_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        md = h["metadata"]
        tip = md.get("tip", "?")
        kaynak = md.get("kaynak", "")
        header = f"[Kaynak {i}] tip={tip} | {kaynak}"
        blocks.append(f"{header}\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def _llm_answer(question: str, hits: list[dict], bolum: str) -> dict:
    """Standart LLM cevabı — ders detay/ön şart sorularında kullanılır."""
    context = format_context(hits)
    bolum_adi = {
        "bilgisayar": "Bilgisayar Mühendisliği",
        "makine": "Makine Mühendisliği",
        "endustri": "Endüstri Mühendisliği",
        "elektrik": "Elektrik-Elektronik Mühendisliği",
        "insaat": "İnşaat Mühendisliği",
    }.get(bolum, "Mühendislik")
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)
    client = Groq()
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": (
                    f"BAĞLAM:\n{context}\n\n"
                    f"SORU: {question}\n\n"
                    "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. "
                    "Eğer ön şart soruluyorsa BAĞLAM'daki 'Ön şart:' alanına bak. "
                    "Kaynak belirt."
                ),
            },
        ],
    )
    text = resp.choices[0].message.content or ""
    return {"answer": text, "hits": hits}


def _render_list_answer(intent: dict, hits: list[dict], bolum_adi: str) -> str:
    """Liste modunda dersleri deterministik olarak markdown bullet listesi yap."""
    muf = intent["mufredat_yili"]
    donems = intent["donems"]
    giris_yili = intent.get("giris_yili")
    sezon_adi = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar", 5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}

    baslik_yil = giris_yili if giris_yili else muf
    lines = [f"## {baslik_yil} {bolum_adi} müfredatı — seçili dönem dersleri\n"]
    for d in donems:
        yil = (d - 1) // 2 + 1
        sezon = sezon_adi.get(d, "")
        donem_hits = [h for h in hits if h["metadata"].get("tip") == "mufredat" and h["metadata"].get("donem") == d]
        if not donem_hits:
            continue
        lines.append(f"### {yil}. yıl {sezon} dönemi ({d}. dönem) — {len(donem_hits)} ders")
        for h in donem_hits:
            md = h["metadata"]
            kod = md.get("ders_kodu", "")
            ad = md.get("ders_adi", "")
            t = md.get("teorik", "") or "—"
            l = md.get("lab", "") or "—"
            k = md.get("kredi", "") or "—"
            a = md.get("akts", "") or "—"
            on = md.get("on_sart", "").strip() or "yok"
            lines.append(f"- **{kod}** — {ad}  \n  T: {t}, L: {l}, Kredi: {k}, AKTS: {a} · Ön şart: {on}")
        lines.append("")
    lines.append(f"_Kaynak: {muf} müfredat dokümanı ({bolum_adi})._")
    if giris_yili and str(giris_yili) != muf:
        lines.append(
            f"\n> ℹ️ **Not:** {giris_yili} girişli öğrenciler **{muf} müfredatına** tabidir; "
            f"yukarıdaki ders listesi {muf} müfredatından alınmıştır."
        )
    return "\n".join(lines)


def answer(question: str, k: int = TOP_K, bolum: str = "bilgisayar") -> dict:
    intent = parse_intent(question, bolum)
    list_mode = False

    # Ders kodu + ön şart (veya genel ders detayı) -> doğrudan kod ile fetch
    code_match = COURSE_CODE_RE.search(question.upper())
    if code_match:
        code = f"{code_match.group(1)} {code_match.group(2)}"
        code_hits = fetch_courses_by_code(code, bolum)
        if code_hits:
            extra = retrieve(question, k=3, bolum=bolum)
            seen = {h["text"] for h in code_hits}
            for h in extra:
                if h["text"] not in seen:
                    code_hits.append(h)
            hits = code_hits
            # Liste modu DEĞİL — LLM normal cevap verecek (ön şart vb için)
            return _llm_answer(question, hits, bolum)

    if intent:
        hits = fetch_semester_courses(intent["mufredat_yili"], intent["donems"], bolum)
        extra = retrieve(question, k=3, bolum=bolum)
        seen = {h["text"] for h in hits}
        for h in extra:
            if h["text"] not in seen:
                hits.append(h)
        list_mode = True
    else:
        hits = retrieve(question, k=k, bolum=bolum)

    bolum_adi = {
        "bilgisayar": "Bilgisayar Mühendisliği",
        "makine": "Makine Mühendisliği",
        "endustri": "Endüstri Mühendisliği",
        "elektrik": "Elektrik-Elektronik Mühendisliği",
        "insaat": "İnşaat Mühendisliği",
    }.get(bolum, "Mühendislik")

    if list_mode:
        # LLM'i atla: dersleri deterministik markdown olarak render et (hiçbir ders kaçmaz)
        text = _render_list_answer(intent, hits, bolum_adi)
        return {"answer": text, "hits": hits}

    context = format_context(hits)
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)

    client = Groq()
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": (
                    f"BAĞLAM:\n{context}\n\n"
                    f"SORU: {question}\n\n"
                    "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. Kaynak belirt."
                ),
            },
        ],
    )
    text = resp.choices[0].message.content or ""
    return {"answer": text, "hits": hits}


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python src/rag.py \"sorunuz\"")
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    result = answer(q)
    print("=" * 60)
    print(f"SORU: {q}")
    print("=" * 60)
    print(result["answer"])
    print("\n" + "-" * 60)
    print("Kullanılan kaynaklar:")
    for i, h in enumerate(result["hits"], 1):
        md = h["metadata"]
        print(f"  [{i}] {md.get('tip')} | {md.get('kaynak','')} | dist={h['distance']:.3f}")


if __name__ == "__main__":
    main()

"""
Bulut RAG çekirdeği — Voyage AI + Pinecone + Voyage Reranker + Groq/OpenRouter.

TORCH/CHROMA İÇERMEZ — Streamlit Community Cloud (1GB RAM) gibi ücretsiz ortamlarda
çalışacak hafif retrieval. Hem `app_cloud.py` (FastAPI) hem `streamlit_app.py` bunu kullanır.

Kalite katmanları:
  1) Bölüm tespiti  → Pinecone metadata filtresi ({bolum, ortak})
  2) Alias genişletme → Türkçe terimlerin İngilizce karşılıkları (data/term_aliases.json)
  3) Hibrit retrieval → Dense (Pinecone) + BM25 (rank-bm25) → RRF füzyon
  4) Voyage Reranker → rerank-2.5 ile en iyi FINAL_K
  5) Groq/OpenRouter → Türkçe cevap (stream veya tek seferde)

Gerekli ortam değişkenleri: VOYAGE_AI_KEY, PINECONE_API_KEY, GROQ_API_KEY (ve/veya OPENROUTER_API_KEY)
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

# --------------------------------------------------------------------------- #
# Ayarlar
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

INDEX_NAME = "rag-asistan"
EMBED_MODEL = "voyage-3.5"       # veri_yukleyici.py ile AYNI olmalı
RERANK_MODEL = "rerank-2.5"      # Voyage hosted reranker (torch gerekmez)

VECTOR_K = 30                    # Pinecone dense aday sayısı
BM25_K = 30                      # BM25 keyword aday sayısı
RRF_C = 60                       # Reciprocal Rank Fusion sabiti
RRF_CANDIDATES = 40              # Füzyon sonrası rerank'e giren aday sayısı
FINAL_K = 8                      # bağlama giren chunk sayısı
RERANK_ESIK = 0.3                # rerank relevance_score eşiği

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
LLM_MODEL_GROQ = "meta-llama/llama-4-scout-17b-16e-instruct"
LLM_MODEL_OPENROUTER = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")


# --------------------------------------------------------------------------- #
# Lazy istemciler (anahtar yoksa import sırasında çökmesin)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _voyage():
    import voyageai

    return voyageai.Client(api_key=os.getenv("VOYAGE_AI_KEY"))


@lru_cache(maxsize=1)
def _pc_index():
    from pinecone import Pinecone

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index(INDEX_NAME)


# --------------------------------------------------------------------------- #
# Bölüm tespiti
# --------------------------------------------------------------------------- #
BOLUM_ADI_MAP = {
    "bilgisayar": "Bilgisayar Mühendisliği",
    "makine": "Makine Mühendisliği",
    "endustri": "Endüstri Mühendisliği",
    "elektrik": "Elektrik-Elektronik Mühendisliği",
    "insaat": "İnşaat Mühendisliği",
    "malzeme": "Malzeme Bilimi ve Nanoteknoloji Mühendisliği",
    "mimarlik": "Mimarlık",
    "isletme": "İşletme",
    "ekonomi": "Ekonomi",
    "siyaset": "Siyaset Bilimi ve Uluslararası İlişkiler",
    "psikoloji": "Psikoloji",
    "biyomuhendislik": "Biyomühendislik",
    "mbg": "Moleküler Biyoloji ve Genetik",
}

BOLUM_KEYWORDS: dict[str, list[str]] = {
    "malzeme": ["msne", "malzeme bilimi", "malzeme müh", "malzeme muh", "nanoteknoloji", "nano teknoloji"],
    "bilgisayar": ["bilgisayar müh", "bilgisayar muh", "yazılım müh", "yazilim muh", "computer eng"],
    "makine": ["makine müh", "makine muh", "mechanical eng", "mech eng"],
    "endustri": ["endüstri", "endustri", "industrial eng"],
    "elektrik": ["elektrik müh", "elektrik muh", "elektronik müh", "elektronik muh", "electrical eng"],
    "insaat": ["inşaat", "insaat", "civil eng"],
    "mimarlik": ["mimarlık", "mimarlik", "architecture"],
    "isletme": ["işletme", "isletme", "business administration", "business adm"],
    "ekonomi": ["ekonomi", "iktisat", "economics", "econ"],
    "siyaset": ["siyaset bilimi", "siyaset bil", "uluslararası ilişkiler", "uluslararasi iliskiler",
                "uluslar arası ilişkiler", "uluslar arasi iliskiler", "political science",
                "international relations", "pols", "siyaset müh", "siyaset böl"],
    "psikoloji": ["psikoloji", "psychology", "psikolog", "psyc", "psyf", "psys", "psyt", "psyi", "psyp",
                  "psyl", "klinik psikoloji", "sosyal psikoloji", "gelişim psikolojisi", "bilişsel psikoloji",
                  "biliş psikolojisi", "anormal psikoloji", "sağlık psikolojisi", "politik psikoloji",
                  "nöropsikoloji", "noropsikoloji", "eğitim psikolojisi"],
    "biyomuhendislik": ["biyomühendislik", "biyomuhendislik", "biyo mühendislik", "biyo muhendislik",
                        "bioengineering", "biyomedikal", "biyomalzeme", "doku mühendisliği",
                        "doku muhendisligi", "biyoproses", "biyoenstrüman"],
    "mbg": ["moleküler biyoloji", "molekuler biyoloji", "moleküler biyoloji ve genetik",
            "molekuler biyoloji ve genetik", "molecular biology", "genetik bölüm", "genetik bol",
            "mbg", "moleküler genetik", "molekuler genetik"],
}

_CODE_PREFIXES = {
    "MSNE": "malzeme", "COMP": "bilgisayar", "ME": "makine", "IE": "endustri", "EE": "elektrik",
    "CE": "insaat", "ARCH": "mimarlik", "BA": "isletme", "ECON": "ekonomi", "POLS": "siyaset",
    "PSYC": "psikoloji", "PSYF": "psikoloji", "PSYS": "psikoloji", "PSYT": "psikoloji",
    "PSYI": "psikoloji", "PSYP": "psikoloji", "PSYL": "psikoloji", "PSYX": "psikoloji",
    "BENG": "biyomuhendislik", "MBG": "mbg",
}
_CODE_RE = re.compile(
    r"\b(MSNE|BENG|COMP|ARCH|ECON|POLS|PSYC|PSYF|PSYS|PSYT|PSYI|PSYP|PSYL|PSYX|MBG|ME|IE|EE|CE|BA)\s*\d{2,4}\b"
)


def detect_bolum(question: str) -> str | None:
    """Soruda bir bölüme spesifik anahtar kelime/ders kodu varsa bolum_id döndür."""
    code_match = _CODE_RE.search(question.upper())
    if code_match:
        return _CODE_PREFIXES[code_match.group(1)]
    # Türkçe lowercase tuzağı: "İ".lower() düz "i" değil noktalı birleşik karakter üretir.
    q = question.replace("İ", "i").replace("I", "ı").lower()
    for bolum, kws in BOLUM_KEYWORDS.items():
        if any(kw in q for kw in kws):
            return bolum
    return None


# --------------------------------------------------------------------------- #
# Tokenizasyon + alias + BM25 + RRF
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(r"[A-Za-zÇĞİıÖŞÜçğöşü0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower()) if text else []


def _tr_normalize(s: str) -> str:
    tr_map = str.maketrans({
        "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    })
    return s.translate(tr_map).lower()


@lru_cache(maxsize=1)
def _load_term_aliases() -> tuple[tuple[str, tuple[str, ...]], ...]:
    path = ROOT / "data" / "term_aliases.json"
    if not path.exists():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("aliases", {})
        return tuple((_tr_normalize(k), tuple(v)) for k, v in raw.items())
    except Exception:
        return ()


def _expand_query_with_aliases(question: str) -> str:
    aliases = _load_term_aliases()
    if not aliases:
        return question
    q_norm = _tr_normalize(question)
    additions: list[str] = []
    seen: set[str] = set()
    for term, en_list in sorted(aliases, key=lambda x: len(x[0]), reverse=True):
        idx = q_norm.find(term)
        if idx == -1:
            continue
        before_ok = idx == 0 or not q_norm[idx - 1].isalnum()
        after_pos = idx + len(term)
        after_ok = after_pos >= len(q_norm) or not q_norm[after_pos].isalnum()
        if not (before_ok and after_ok):
            continue
        for en in en_list:
            en_low = en.lower()
            if en_low not in seen and en_low not in q_norm:
                additions.append(en)
                seen.add(en_low)
    return question + " " + " ".join(additions) if additions else question


@lru_cache(maxsize=1)
def _load_all_chunks() -> tuple[dict, ...]:
    chunks: list[dict] = []
    for jsonl_file in sorted(PROCESSED_DIR.glob("*.jsonl")):
        with jsonl_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
    return tuple(chunks)


@lru_cache(maxsize=16)
def _get_bm25(bolum: str | None):
    from rank_bm25 import BM25Okapi

    all_chunks = _load_all_chunks()
    if bolum is None:
        filtered = list(all_chunks)
    else:
        filtered = [c for c in all_chunks if c.get("metadata", {}).get("bolum") in (bolum, "ortak")]
    if not filtered:
        return None, []
    bm25 = BM25Okapi([_tokenize(c["text"]) for c in filtered])
    return bm25, filtered


def bm25_search(expanded_query: str, bolum: str | None, k: int = BM25_K) -> list[dict]:
    bm25, chunks = _get_bm25(bolum)
    if bm25 is None:
        return []
    tokens = _tokenize(expanded_query)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [
        {"text": chunks[i]["text"], "metadata": chunks[i].get("metadata", {})}
        for i in top_idx
        if scores[i] > 0
    ]


def _rrf_fuse(vector_hits: list[dict], bm25_hits: list[dict], k: int, c: int = RRF_C) -> list[dict]:
    def _key(h: dict) -> str:
        md = h.get("metadata", {}) or {}
        return md.get("ders_kodu", "") + "|" + (h.get("text", "") or "")[:120]

    scores: dict[str, float] = {}
    by_key: dict[str, dict] = {}
    for hits in (vector_hits, bm25_hits):
        for rank, h in enumerate(hits, start=1):
            key = _key(h)
            scores[key] = scores.get(key, 0.0) + 1.0 / (c + rank)
            by_key.setdefault(key, h)
    sorted_keys = sorted(scores, key=lambda kk: scores[kk], reverse=True)
    return [by_key[kk] for kk in sorted_keys[:k]]


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
_AUTO = object()  # retrieve() için "bölümü otomatik tespit et" işareti


def retrieve(soru: str, bolum=_AUTO, k: int | None = None) -> tuple[list[str], str | None]:
    """Bağlam metinlerini ve (etkin) bölümü döndür.
    bolum=_AUTO → detect_bolum; bolum=None → filtresiz; bolum='x' → o bölümle filtrele.
    k → bağlama giren chunk sayısı (None ise FINAL_K)."""
    final_k = k or FINAL_K
    if bolum is _AUTO:
        bolum = detect_bolum(soru)
    expanded = _expand_query_with_aliases(soru)

    # 1) Dense
    sorgu_vek = _voyage().embed([expanded], model=EMBED_MODEL, input_type="query").embeddings[0]
    flt = {"bolum": {"$in": [bolum, "ortak"]}} if bolum else None
    sonuc = _pc_index().query(vector=sorgu_vek, top_k=VECTOR_K, include_metadata=True, filter=flt)
    vector_hits = [
        {"text": (m["metadata"] or {}).get("text", ""), "metadata": m.get("metadata", {}) or {}}
        for m in sonuc.get("matches", [])
        if (m.get("metadata") or {}).get("text")
    ]

    # 2) BM25
    bm25_hits = bm25_search(expanded, bolum)

    # 3) RRF füzyon
    fused = _rrf_fuse(vector_hits, bm25_hits, k=RRF_CANDIDATES)
    adaylar = [h["text"] for h in fused if h.get("text")]
    if not adaylar:
        return [], bolum

    # 4) Voyage reranker
    rr = _voyage().rerank(soru, adaylar, model=RERANK_MODEL, top_k=min(final_k, len(adaylar)))
    secilen = [r.document for r in rr.results if r.relevance_score >= RERANK_ESIK]
    if not secilen:
        secilen = [r.document for r in rr.results[:3]]
    return secilen, bolum


# --------------------------------------------------------------------------- #
# Yapılandırılmış sorgular — parse_intent + fetch_* (bellek-içi, Chroma'sız)
# src/rag.py'den taşındı; col.get(where=...) yerine _load_all_chunks filtresi.
# --------------------------------------------------------------------------- #
MUFREDAT_RE = re.compile(r"\b(20\d\d)\b")
DONEM_RE = re.compile(r"(\d+)\s*\.?\s*(?:dönem|yariyil|yarıyıl|semester)", re.IGNORECASE)
YIL_SEZON_RE = re.compile(r"(\d+)\s*\.?\s*y[ıi]l.{0,15}?(g[üu]z|bahar)", re.IGNORECASE)
SINIF_RE = re.compile(r"\b([1-4])\s*\.?\s*(s[ıi]n[ıi]f|y[ıi]l|sene)", re.IGNORECASE)
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,5})\s*[-_ ]?\s*(\d{2,4})\b")

LIST_TRIGGERS = [
    "hangi dersler", "dersleri listele", "tüm dersler", "tum dersler", "ders listesi",
    "neler var", "hangi ders", "dersler neler", "dersleri neler", "dersleri ne", "ders neler",
    "sınıf dersleri", "sinif dersleri", "yıl dersleri", "yil dersleri", "ders programı",
    "ders programi", "müfredat", "mufredat", "sınıfta", "sinifta", "dönemde", "donemde",
    "dönem dersleri", "donem dersleri", "sınıfın dersleri", "sinifin dersleri", "sene dersleri",
    "senenin dersleri", "senede", "senesinde", "yılında", "yilinda", "yılın dersleri",
    "yilin dersleri", "dersler hangileri", "listele",
]
LATEST_MUFREDAT = {
    "bilgisayar": "2025", "makine": "2025", "endustri": "2025", "elektrik": "2025",
    "insaat": "2025", "malzeme": "2025", "mimarlik": "2025", "isletme": "2025",
    "ekonomi": "2025", "siyaset": "2025", "psikoloji": "2021", "biyomuhendislik": "2021", "mbg": "2021",
}


def parse_intent(question: str, bolum: str) -> dict | None:
    """Soru bir 'dönem listesi' sorusu mu? İse {mufredat_yili, donems, giris_yili} döndür."""
    q = question.lower()
    if not any(t in q for t in LIST_TRIGGERS):
        return None

    muf = MUFREDAT_RE.search(question)
    mufredat_yili = None
    if muf:
        year = int(muf.group(1))
        if bolum == "makine":
            mufredat_yili = "2025" if 2022 <= year <= 2025 else ("2021" if year <= 2021 else str(year))
        elif bolum == "endustri":
            mufredat_yili = "2016" if 2016 <= year <= 2020 else ("2021" if 2021 <= year <= 2024 else ("2025" if year >= 2025 else None))
        elif bolum == "elektrik":
            mufredat_yili = "2019" if 2019 <= year <= 2020 else ("2021" if 2021 <= year <= 2024 else ("2025" if year >= 2025 else None))
        elif bolum == "insaat":
            mufredat_yili = "2016" if 2016 <= year <= 2020 else ("2021" if 2021 <= year <= 2024 else ("2025" if year >= 2025 else None))
        elif bolum in ("malzeme", "mimarlik", "isletme", "ekonomi", "siyaset"):
            mufredat_yili = "2025"
        elif bolum == "psikoloji":
            mufredat_yili = "2021"
        elif bolum in ("biyomuhendislik", "mbg"):
            mufredat_yili = "2021"
        else:  # bilgisayar
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
    elif (m2 := YIL_SEZON_RE.search(q)):
        yil, sezon = int(m2.group(1)), m2.group(2)
        donems = [(yil - 1) * 2 + (1 if sezon.startswith("g") else 2)]
    elif (m3 := SINIF_RE.search(q)):
        yil = int(m3.group(1))
        if 1 <= yil <= 4:
            donems = [(yil - 1) * 2 + 1, (yil - 1) * 2 + 2]

    giris_yili = int(muf.group(1)) if muf else None
    if not mufredat_yili and donems:
        mufredat_yili = LATEST_MUFREDAT.get(bolum)
    if mufredat_yili and not donems:
        donems = [1, 2, 3, 4, 5, 6, 7, 8]
    if mufredat_yili and donems:
        return {"mufredat_yili": mufredat_yili, "donems": donems, "giris_yili": giris_yili}
    return None


SECMELI_CATEGORY_PATTERNS = [
    (re.compile(r"b[öo]l[üu]m[\s\-_]*i[çc]i[\s\-_]*se[çc]meli", re.I), "Bölüm İçi Seçmeli"),
    (re.compile(r"s[ıi]n[ıi]rl[ıi][\s\-_]*se[çc]meli", re.I), "Sınırlı Seçmeli"),
    (re.compile(r"b[öo]l[üu]m[\s\-_]*d[ıi][şs][ıi][\s\-_]*zorunlu", re.I), "Bölüm Dışı Zorunlu"),
]
SECMELI_LIST_TRIGGERS_NORM = [
    "neler", "nelerdir", "hepsi", "tum ", "tum", "listele", "goster", "göster",
    "hangileri", "ders listesi", "ders havuzu", "ne var", "var mi",
]


def parse_secmeli_intent(question: str) -> str | None:
    q_norm = _tr_normalize(question)
    if "secmeli" not in q_norm and "zorunlu" not in q_norm:
        return None
    for pattern, kategori in SECMELI_CATEGORY_PATTERNS:
        if pattern.search(question):
            return kategori
    if "secmeli" in q_norm and any(t in q_norm for t in SECMELI_LIST_TRIGGERS_NORM):
        return "ALL"
    return None


def fetch_courses_by_code(code: str, bolum: str) -> list[dict]:
    """Ders koduyla eşleşen tüm chunk'lar (boşluk normalize edilerek)."""
    target = re.sub(r"\s+", "", code).upper()
    hits = []
    for c in _load_all_chunks():
        md = c.get("metadata", {})
        if md.get("bolum") != bolum:
            continue
        dk = md.get("ders_kodu")
        if dk and re.sub(r"\s+", "", str(dk)).upper() == target:
            hits.append({"text": c["text"], "metadata": md})
    return hits


def fetch_semester_courses(mufredat_yili: str, donems: list[int], bolum: str) -> list[dict]:
    donemset = set(donems)
    hits = []
    for c in _load_all_chunks():
        md = c.get("metadata", {})
        if md.get("bolum") != bolum or str(md.get("mufredat_yili")) != str(mufredat_yili):
            continue
        try:
            d = int(md.get("donem"))
        except (TypeError, ValueError):
            continue
        if d in donemset:
            hits.append({"text": c["text"], "metadata": md})
    hits.sort(key=lambda h: (h["metadata"].get("donem", 0), h["metadata"].get("ders_kodu", "")))
    return hits


def fetch_electives_by_category(kategori_or_all: str, bolum: str) -> list[dict]:
    hits = []
    for c in _load_all_chunks():
        md = c.get("metadata", {})
        if md.get("bolum") != bolum or md.get("tip") != "secmeli":
            continue
        if kategori_or_all != "ALL" and md.get("kategori") != kategori_or_all:
            continue
        hits.append({"text": c["text"], "metadata": md})
    hits.sort(key=lambda h: (h["metadata"].get("kategori", ""), h["metadata"].get("ders_kodu", "")))
    return hits


def _render_list_answer(intent: dict, hits: list[dict], bolum_adi: str) -> str:
    muf, donems = intent["mufredat_yili"], intent["donems"]
    giris_yili = intent.get("giris_yili")
    sezon_adi = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar", 5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}
    baslik_yil = giris_yili if giris_yili else muf
    lines = [f"## {baslik_yil} {bolum_adi} müfredatı — seçili dönem dersleri\n"]
    for d in donems:
        yil = (d - 1) // 2 + 1
        donem_hits = [h for h in hits if h["metadata"].get("tip") == "mufredat" and h["metadata"].get("donem") == d]
        if not donem_hits:
            continue
        lines.append(f"### {yil}. yıl {sezon_adi.get(d, '')} dönemi ({d}. dönem) — {len(donem_hits)} ders")
        for h in donem_hits:
            md = h["metadata"]
            on = (md.get("on_sart", "") or "").strip() or "yok"
            lines.append(
                f"- **{md.get('ders_kodu','')}** — {md.get('ders_adi','')}  \n"
                f"  T: {md.get('teorik','') or '—'}, L: {md.get('lab','') or '—'}, "
                f"Kredi: {md.get('kredi','') or '—'}, AKTS: {md.get('akts','') or '—'} · Ön şart: {on}"
            )
        lines.append("")
    lines.append(f"_Kaynak: {muf} müfredat dokümanı ({bolum_adi})._")
    if giris_yili and str(giris_yili) != str(muf):
        lines.append(
            f"\n> ℹ️ **Not:** {giris_yili} girişli öğrenciler **{muf} müfredatına** tabidir; "
            f"yukarıdaki liste {muf} müfredatından alınmıştır."
        )
    return "\n".join(lines)


def _render_elective_list(kategori_or_all: str, hits: list[dict], bolum_adi: str) -> str:
    if not hits:
        return f"## {bolum_adi} — Seçmeli ders havuzu\n\nBu kategori için dokümanlarda kayıt bulunamadı."

    def _row(md: dict) -> str:
        return (
            f"- **{md.get('ders_kodu','')}** — {md.get('ders_adi','') or '—'}  \n"
            f"  Haftalık saat: {md.get('haftalik_saat','') or '—'}, "
            f"Kredi: {md.get('kredi','') or '—'}, AKTS: {md.get('akts','') or '—'}"
        )

    if kategori_or_all == "ALL":
        from collections import defaultdict

        by_kat: dict[str, list[dict]] = defaultdict(list)
        for h in hits:
            by_kat[h["metadata"].get("kategori", "Diğer")].append(h)
        lines = [f"## {bolum_adi} — Seçmeli ve Bölüm Dışı Ders Havuzları\n"]
        for kat, items in by_kat.items():
            lines.append(f"### {kat} ({len(items)} ders)\n")
            lines += [_row(h["metadata"]) for h in items]
            lines.append("")
        lines.append(f"_Kaynak: seçmeli ders havuzu dokümanı ({bolum_adi})._")
        return "\n".join(lines)

    lines = [f"## {bolum_adi} — {kategori_or_all} ders havuzu\n", f"Toplam **{len(hits)} ders**:\n"]
    lines += [_row(h["metadata"]) for h in hits]
    lines.append(f"\n_Kaynak: seçmeli ders havuzu dokümanı ({bolum_adi})._")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """Sen Abdullah Gül Üniversitesi {bolum_adi} bölümü için bir yardımcı asistansın.
Öğrencilere müfredat, dersler, staj yönergesi gibi konularda Türkçe yardım edersin.

KURALLAR:
1. Sadece sana verilen BAĞLAM içindeki bilgilere dayanarak cevap ver.
2. Bağlamda olmayan bir şey sorulursa ASLA UYDURMA; bilgi olmadığını kibarca söyle ve ilgili bölüm web sayfasına/yönergeye yönlendir. Kısmi bilgi varsa önce onu ver, sonra eksik kısmı belirt.
3. Cevabı verirken hangi kaynağı kullandığını belirt (örn: "2023 müfredatına göre...", "Staj Yönergesi MADDE 10'a göre...").
4. Ders kodu, AKTS, dönem gibi sayısal bilgileri aynen aktar.
5. CEVAP UZUNLUĞU: Soru kapsamlıysa (Erasmus şartları, staj süreci, yatay geçiş) bağlamdaki TÜM ilgili maddeleri/şartları/detayları cevabın gövdesinde tek tek say (sayısal kriterler, MADDE no, ders kodları, e-posta dahil). Tek bir gerçek sorulduğunda (ör. "BA499 kaç AKTS?") tek satır yeterli.
6. Makine Mühendisliği: 2022-2025 girişliler "2025", 2021 ve öncesi "2021" müfredatına tabidir.
7. Endüstri Mühendisliği: 2016-2020 "2016", 2021-2024 "2021", 2025+ "2025" müfredatına tabidir.
8. Bilgisayar Mühendisliği: 2016-2020 "2016", 2021-2022 "2021", 2023-2024 "2023", 2025+ "2025" müfredatına tabidir.
9. Bir dersin ön şartı sorulursa BAĞLAM'daki "Ön şart:" alanına bak. "yok" ise "Bu dersin ön şartı yoktur" de; aksi halde aynen aktar. Bu bilgi her ders chunk'ında vardır — "bilgi yok" deme.
10. Elektrik-Elektronik: 2019-2020 "2019", 2021-2024 "2021", 2025+ "2025" Capsule müfredatına tabidir. 3-4. sınıfta "Seçmeli Kapsüller" havuzundan ders seçilir.
11. İnşaat: 2016-2020 "2016", 2021-2024 "2021", 2025+ "2025" müfredatına tabidir.
12. Malzeme Bilimi ve Nanoteknoloji (MSNE): tüm girişler "2025" (tek aktif müfredat).
13. Mimarlık (ARCH): tüm girişler "2025" (tek aktif müfredat). Eğitim dili İngilizce.
14. İşletme (BA): tüm girişler "2025" (tek aktif müfredat). Eğitim dili İngilizce.
15. Siyaset Bilimi ve Uluslararası İlişkiler (POLS): tüm girişler "2025". Toplam mezuniyet kredisi 147, AKTS 240.
16. Biyomühendislik (BENG): tüm girişler "2021". Eğitim dili İngilizce, 240 AKTS. 3. sınıfta alan seçimi: A) Biyomateryal ve Doku, B) Genetik ve Biyoproses, C) Biyomedikal Elektroniği. Bazı seçmeliler MBG kodlu.
17. Moleküler Biyoloji ve Genetik (MBG): tüm girişler "2021". İngilizce, 240 AKTS, 8 yarıyıl. Mezuniyet için ≥2.00/4.00 GNO ve zorunlu MBG 499 Yaz Stajı gerekir. MBG, Biyomühendislik'ten (BENG) AYRI bir bölümdür.
18. Samimi, öğrenci dostu bir ton kullan ama doğruluktan ödün verme."""


def _messages_for(soru: str, context_texts: list[str], bolum: str | None) -> list[dict]:
    context = "\n---\n".join(context_texts) if context_texts else "Bilgi havuzunda ilgili kaynak bulunamadı."
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "AGÜ") if bolum else "AGÜ"
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(bolum_adi=bolum_adi)},
        {"role": "user", "content": f"BAĞLAM:\n{context}\n\nSORU: {soru}"},
    ]


def _groq_client():
    from groq import Groq

    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def _openrouter_client():
    from openai import OpenAI

    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))


def _complete_groq(messages, max_tokens, temperature):
    resp = _groq_client().chat.completions.create(
        model=LLM_MODEL_GROQ, max_tokens=max_tokens, temperature=temperature, messages=messages)
    return resp.choices[0].message.content or ""


def _complete_openrouter(messages, max_tokens, temperature):
    resp = _openrouter_client().chat.completions.create(
        model=LLM_MODEL_OPENROUTER, max_tokens=max_tokens, temperature=temperature, messages=messages)
    return resp.choices[0].message.content or ""


def _stream_provider(client, model, messages, max_tokens, temperature):
    stream = client.chat.completions.create(
        model=model, max_tokens=max_tokens, temperature=temperature, messages=messages, stream=True)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _llm_complete(messages: list[dict], max_tokens: int = 1800, temperature: float = 0.2) -> str:
    """LLM_PROVIDER: 'groq' | 'openrouter' | 'auto' (Groq dene, hata olursa OpenRouter'a düş)."""
    if LLM_PROVIDER == "openrouter":
        return _complete_openrouter(messages, max_tokens, temperature)
    if LLM_PROVIDER == "auto":
        try:
            return _complete_groq(messages, max_tokens, temperature)
        except Exception:
            return _complete_openrouter(messages, max_tokens, temperature)
    return _complete_groq(messages, max_tokens, temperature)


def _llm_stream(messages: list[dict], max_tokens: int = 1800, temperature: float = 0.2):
    if LLM_PROVIDER == "openrouter":
        yield from _stream_provider(_openrouter_client(), LLM_MODEL_OPENROUTER, messages, max_tokens, temperature)
        return
    if LLM_PROVIDER == "auto":
        # Groq'u dene; ilk token gelmeden hata/boş olursa OpenRouter'a düş.
        try:
            gen = _stream_provider(_groq_client(), LLM_MODEL_GROQ, messages, max_tokens, temperature)
            first = next(gen, None)
            if first is None:
                yield from _stream_provider(_openrouter_client(), LLM_MODEL_OPENROUTER, messages, max_tokens, temperature)
                return
            yield first
            yield from gen
        except Exception:
            yield from _stream_provider(_openrouter_client(), LLM_MODEL_OPENROUTER, messages, max_tokens, temperature)
        return
    yield from _stream_provider(_groq_client(), LLM_MODEL_GROQ, messages, max_tokens, temperature)


# --------------------------------------------------------------------------- #
# Genel API — yapılandırılmış sorgu yönlendirmesi (src/rag.py.answer_stream mantığı)
# --------------------------------------------------------------------------- #
def respond(soru: str, bolum=_AUTO, k: int | None = None) -> dict:
    """Soruyu uygun moda yönlendirir.

    Dönüş:
      {"mode": "list" | "llm", "text": str|None, "token_iter": gen|None, "bolum": str|None, "n": int}
      - "list": deterministik metin (text dolu, token_iter None)
      - "llm" : LLM stream (token_iter dolu, text None)
    k → genel RAG'da bağlama giren chunk sayısı (detay seviyesi).
    """
    if bolum is _AUTO:
        bolum = detect_bolum(soru)
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "AGÜ") if bolum else "AGÜ"
    intent = parse_intent(soru, bolum) if bolum else None

    # 1) Ders kodu → tam ders chunk'ları + birkaç RAG bağlamı → LLM stream
    code_match = COURSE_CODE_RE.search(soru.upper())
    if bolum and code_match:
        code = f"{code_match.group(1)} {code_match.group(2)}"
        code_hits = fetch_courses_by_code(code, bolum)
        if code_hits:
            ctx = [h["text"] for h in code_hits]
            extra, _ = retrieve(soru, bolum=bolum)
            for t in extra:
                if t not in ctx:
                    ctx.append(t)
            ctx = ctx[:12]
            return {"mode": "llm", "text": None, "token_iter": _llm_stream(_messages_for(soru, ctx, bolum)),
                    "bolum": bolum, "n": len(ctx)}

    # 2) Seçmeli ders havuzu listesi → deterministik
    if bolum:
        sec_kat = parse_secmeli_intent(soru)
        if sec_kat:
            sec_hits = fetch_electives_by_category(sec_kat, bolum)
            if sec_hits:
                text = _render_elective_list(sec_kat, sec_hits, bolum_adi)
                return {"mode": "list", "text": text, "token_iter": None, "bolum": bolum, "n": len(sec_hits)}

    # 3) Dönem/sınıf ders listesi → deterministik (mufredat kaydı varsa)
    if intent:
        hits = fetch_semester_courses(intent["mufredat_yili"], intent["donems"], bolum)
        mufredat_hits = [h for h in hits if h["metadata"].get("tip") == "mufredat"]
        if mufredat_hits:
            text = _render_list_answer(intent, hits, bolum_adi)
            return {"mode": "list", "text": text, "token_iter": None, "bolum": bolum, "n": len(mufredat_hits)}
        # mufredat kaydı yoksa (örn. psikoloji) genel RAG'a düş

    # 4) Genel RAG → LLM stream
    ctx, _ = retrieve(soru, bolum=bolum, k=k)
    return {"mode": "llm", "text": None, "token_iter": _llm_stream(_messages_for(soru, ctx, bolum)),
            "bolum": bolum, "n": len(ctx)}


def answer(soru: str, bolum=_AUTO) -> dict:
    """Tek seferde cevap (FastAPI için). Stream'i toplar."""
    r = respond(soru, bolum)
    text = r["text"] if r["mode"] == "list" else "".join(r["token_iter"])
    return {"cevap": text, "bolum": r["bolum"], "kullanilan_chunk": r["n"], "kaynak_bulundu": r["n"] > 0}

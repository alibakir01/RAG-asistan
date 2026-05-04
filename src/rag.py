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

import json

import chromadb
from groq import Groq
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = ROOT / "data" / "chroma"
PROCESSED_DIR = ROOT / "data" / "processed"
MODEL_NAME = "intfloat/multilingual-e5-large"
COLLECTION = "agu_comp"
LLM_MODEL = "llama-3.3-70b-versatile"  # Groq'ta bedava, Türkçesi iyi
TOP_K = 8

# Hibrit retrieval ayarları
HYBRID_VECTOR_K = 20   # vektör adayları
HYBRID_BM25_K = 20     # BM25 adayları
RRF_C = 60             # Reciprocal Rank Fusion sabiti

# Reranker ayarları
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"  # multilingual, Türkçe destekli (~1.1GB)
RERANK_CANDIDATES = 15   # hibrit sonrası kaç adayı reranker'a sokalım (CPU'da hız için 15)

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
12. Malzeme Bilimi ve Nanoteknoloji Mühendisliği (MSNE) için: tüm girişler "2025" müfredatına tabidir (tek aktif müfredat).
"""


@lru_cache(maxsize=1)
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    """Cross-encoder reranker (lazy load — ilk sorguda yaklaşık 200MB model indirir)."""
    return CrossEncoder(RERANKER_MODEL, max_length=512)


def rerank(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Cross-encoder ile (query, document) çiftlerini puanla, top_k al."""
    if not candidates:
        return []
    if len(candidates) <= top_k:
        # Yine de skor ekleyelim ki UI tutarlı olsun
        pass
    reranker = _get_reranker()
    pairs = [[question, c["text"]] for c in candidates]
    scores = reranker.predict(pairs, show_progress_bar=False)
    scored = []
    for c, s in zip(candidates, scores):
        c2 = dict(c)
        c2["_rerank_score"] = float(s)
        scored.append(c2)
    scored.sort(key=lambda h: h["_rerank_score"], reverse=True)
    return scored[:top_k]


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION)


# ----------------------------- BM25 Index -----------------------------

# Türkçe için basit tokenizer: küçült + alfanümerik tokenler.
_TOKEN_RE = re.compile(r"[A-Za-zÇĞİıÖŞÜçğöşü0-9]+")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


@lru_cache(maxsize=1)
def _load_all_chunks() -> tuple[tuple, ...]:
    """Tüm processed/*.jsonl chunk'larını belleğe al. Tuple döndürür ki lru_cache mutlu olsun."""
    chunks: list[dict] = []
    for jsonl_file in sorted(PROCESSED_DIR.glob("*.jsonl")):
        with jsonl_file.open(encoding="utf-8") as f:
            for line in f:
                ch = json.loads(line)
                chunks.append(ch)
    return tuple(chunks)


@lru_cache(maxsize=8)
def _get_bm25(bolum: str):
    """Belirli bölüm için BM25 indexi inşa et (bellekte cache'lenir)."""
    all_chunks = _load_all_chunks()
    filtered = [c for c in all_chunks if c.get("metadata", {}).get("bolum") == bolum]
    docs_tokens = [_tokenize(c["text"]) for c in filtered]
    if not docs_tokens:
        return None, []
    bm25 = BM25Okapi(docs_tokens)
    return bm25, filtered


def bm25_search(question: str, bolum: str, k: int = HYBRID_BM25_K) -> list[dict]:
    bm25, chunks = _get_bm25(bolum)
    if bm25 is None or not chunks:
        return []
    tokens = _tokenize(question)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    # En yüksek skorlu k'yı sırala
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    hits = []
    for i in top_idx:
        if scores[i] <= 0:
            continue
        c = chunks[i]
        hits.append({
            "text": c["text"],
            "metadata": c["metadata"],
            "distance": 1.0 / (1.0 + scores[i]),  # uyumluluk için "distance benzeri"
            "_bm25_score": float(scores[i]),
        })
    return hits


# ----------------------------- Intent / Router -----------------------------

MUFREDAT_RE = re.compile(r"\b(20\d\d)\b")
DONEM_RE = re.compile(r"(\d+)\s*\.?\s*(?:dönem|yariyil|yarıyıl|semester)", re.IGNORECASE)
YIL_SEZON_RE = re.compile(r"(\d+)\s*\.?\s*y[ıi]l.{0,15}?(g[üu]z|bahar)", re.IGNORECASE)
# 1-4 arası tek hane ister; "2022 yılı" gibi giriş yıllarını yakalamasın.
# Türkçe çekim ekleri için trailing \b kaldırıldı: "2. yıl", "2. yılın", "2. senenin",
# "2. sınıfın", "2. sınıfın dersleri" gibi varyantların hepsi eşleşir.
SINIF_RE = re.compile(r"\b([1-4])\s*\.?\s*(s[ıi]n[ıi]f|y[ıi]l|sene)", re.IGNORECASE)
LIST_TRIGGERS = [
    "hangi dersler", "dersleri listele", "tüm dersler", "tum dersler",
    "ders listesi", "neler var", "hangi ders", "dersler neler",
    "dersleri neler", "dersleri ne", "ders neler",
    "sınıf dersleri", "sinif dersleri", "yıl dersleri", "yil dersleri",
    "ders programı", "ders programi", "müfredat", "mufredat",
    "sınıfta", "sinifta", "dönemde", "donemde", "dönem dersleri",
    "donem dersleri", "sınıfın dersleri", "sinifin dersleri",
    "sene dersleri", "senenin dersleri", "senede", "senesinde",
    "yılında", "yilinda", "yılın dersleri", "yilin dersleri",
    "dersler hangileri", "dersler neler", "listele",
]

LATEST_MUFREDAT = {"bilgisayar": "2025", "makine": "2025", "endustri": "2025", "elektrik": "2025", "insaat": "2025", "malzeme": "2025"}


# --- Otomatik bölüm tespiti ---
# Anahtar kelime / ders kodu eşleşmeleri. Eşleşme bulunursa bolum override edilir.
BOLUM_KEYWORDS: dict[str, list[str]] = {
    "malzeme": [
        "msne", "malzeme bilimi", "malzeme müh", "malzeme muh",
        "nanoteknoloji", "nano teknoloji",
    ],
    "bilgisayar": [
        "comp ", "bilgisayar müh", "bilgisayar muh", "yazılım müh",
        "yazilim muh", "computer eng",
    ],
    "makine": [
        "me ", "makine müh", "makine muh", "mechanical eng", "mech eng",
    ],
    "endustri": [
        "ie ", "endüstri", "endustri", "industrial eng",
    ],
    "elektrik": [
        "ee ", "elektrik müh", "elektrik muh", "elektronik müh",
        "elektronik muh", "electrical eng",
    ],
    "insaat": [
        "ce ", "inşaat", "insaat", "civil eng",
    ],
}


def detect_bolum(question: str) -> str | None:
    """Soruda bir bölüme spesifik anahtar kelime varsa bolum_id döndür, yoksa None."""
    q = question.lower()
    # 1) Ders kodu prefix'i (boşluklu / boşluksuz): MSNE 302, MSNE302, COMP101 vb.
    code_prefixes = {
        "MSNE": "malzeme", "COMP": "bilgisayar", "ME": "makine",
        "IE": "endustri", "EE": "elektrik", "CE": "insaat",
    }
    code_match = re.search(r"\b(MSNE|COMP|ME|IE|EE|CE)\s*\d{2,4}\b", question.upper())
    if code_match:
        return code_prefixes[code_match.group(1)]
    # 2) İsim tabanlı anahtar kelimeler
    for bolum, kws in BOLUM_KEYWORDS.items():
        if any(kw in q for kw in kws):
            return bolum
    return None


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
        elif bolum == "malzeme":
            # MSNE: tek aktif müfredat -> "2025" (tüm girişler)
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


def _expand_query_with_history(question: str, history: list[dict] | None) -> str:
    """Takip sorusu kısa olabilir ('peki ön şartı?'). Retrieval kalitesi için
    son birkaç user mesajını mevcut soruya iliştir."""
    if not history:
        return question
    prev_users = [m["content"] for m in history if m.get("role") == "user"][-2:]
    if not prev_users:
        return question
    return " ".join(prev_users + [question])


def vector_search(question: str, bolum: str, k: int = HYBRID_VECTOR_K,
                  history: list[dict] | None = None) -> list[dict]:
    """Saf semantic vector retrieval (Chroma + e5)."""
    model = _get_embedder()
    col = _get_collection()
    expanded = _expand_query_with_history(question, history)
    emb = model.encode([f"query: {expanded}"], normalize_embeddings=True).tolist()
    r = col.query(query_embeddings=emb, n_results=k, where={"bolum": bolum})
    hits = []
    for doc, md, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        hits.append({"text": doc, "metadata": md, "distance": dist})
    return hits


def _rrf_fuse(vector_hits: list[dict], bm25_hits: list[dict], k: int,
              c: int = RRF_C) -> list[dict]:
    """Reciprocal Rank Fusion: 1/(c+rank) ile iki listeyi birleştir.
    Aynı text içeren hit'ler aynı sayılır."""
    def _key(h: dict) -> str:
        md = h.get("metadata", {})
        return md.get("ders_kodu", "") + "|" + h.get("text", "")[:120]

    scores: dict[str, float] = {}
    by_key: dict[str, dict] = {}

    for rank, h in enumerate(vector_hits, start=1):
        key = _key(h)
        scores[key] = scores.get(key, 0.0) + 1.0 / (c + rank)
        by_key.setdefault(key, h)
    for rank, h in enumerate(bm25_hits, start=1):
        key = _key(h)
        scores[key] = scores.get(key, 0.0) + 1.0 / (c + rank)
        by_key.setdefault(key, h)

    sorted_keys = sorted(scores.keys(), key=lambda kk: scores[kk], reverse=True)
    fused = []
    for kk in sorted_keys[:k]:
        h = dict(by_key[kk])
        h["_rrf_score"] = scores[kk]
        fused.append(h)
    return fused


def retrieve(question: str, k: int = TOP_K, bolum: str = "bilgisayar",
             history: list[dict] | None = None,
             use_reranker: bool = True) -> list[dict]:
    """Üç aşamalı retrieval:
       1) Vektör (e5)  + BM25 → RRF ile RERANK_CANDIDATES (≈30) aday
       2) Cross-encoder reranker (bge-reranker-base) ile yeniden sırala
       3) En iyi k'yı döndür
    """
    vec = vector_search(question, bolum, k=HYBRID_VECTOR_K, history=history)
    # BM25 için orijinal soru daha doğru — query expansion sadece vektörde fayda sağlar
    bm = bm25_search(question, bolum, k=HYBRID_BM25_K)

    if not bm and not vec:
        return []
    if not bm:
        candidates = vec[:RERANK_CANDIDATES]
    elif not vec:
        candidates = bm[:RERANK_CANDIDATES]
    else:
        candidates = _rrf_fuse(vec, bm, k=RERANK_CANDIDATES)

    if not use_reranker or len(candidates) <= 1:
        return candidates[:k]
    return rerank(question, candidates, top_k=k)


def format_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        md = h["metadata"]
        tip = md.get("tip", "?")
        kaynak = md.get("kaynak", "")
        header = f"[Kaynak {i}] tip={tip} | {kaynak}"
        blocks.append(f"{header}\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


BOLUM_ADI_MAP = {
    "bilgisayar": "Bilgisayar Mühendisliği",
    "makine": "Makine Mühendisliği",
    "endustri": "Endüstri Mühendisliği",
    "elektrik": "Elektrik-Elektronik Mühendisliği",
    "insaat": "İnşaat Mühendisliği",
    "malzeme": "Malzeme Bilimi ve Nanoteknoloji Mühendisliği",
}

# Konuşma geçmişinden LLM'e geçirilecek maksimum mesaj sayısı (son N mesaj)
MAX_HISTORY_MESSAGES = 6


def _build_history_messages(history: list[dict] | None) -> list[dict]:
    """app.py session_state.messages -> Groq messages formatı (sadece role+content)."""
    if not history:
        return []
    msgs = []
    for m in history[-MAX_HISTORY_MESSAGES:]:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    return msgs


def _llm_answer(question: str, hits: list[dict], bolum: str,
                history: list[dict] | None = None) -> dict:
    """Standart LLM cevabı — ders detay/ön şart sorularında kullanılır."""
    context = format_context(hits)
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)
    history_msgs = _build_history_messages(history)
    client = Groq()
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys_prompt},
            *history_msgs,
            {
                "role": "user",
                "content": (
                    f"BAĞLAM:\n{context}\n\n"
                    f"SORU: {question}\n\n"
                    "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. "
                    "Önceki konuşma akışını dikkate al — kullanıcı kısa takip soruları sorabilir "
                    "(örn. 'peki ön şartı ne?'). "
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


# --- Karşılaştırma modu ---
# "2021 vs 2025", "2016 ile 2025 farkı", "2021 ve 2025 müfredat" gibi sorgular.
COMPARE_TRIGGERS = ["fark", "kıyas", "kiyas", "karşılaş", "karsilas",
                    " vs ", " v.s.", " ile ", " ve "]
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def detect_compare_intent(question: str, bolum: str) -> dict | None:
    """Birden fazla müfredat yılı + karşılaştırma tetikleyicisi varsa
    {'years': [...], 'mufredat_yillari': [...]} döndürür."""
    q = question.lower()
    years_raw = list(dict.fromkeys(YEAR_RE.findall(question)))  # benzersiz, sıralı
    if len(years_raw) < 2:
        return None
    has_trigger = any(t in q for t in COMPARE_TRIGGERS)
    if not has_trigger:
        return None
    # Her yıl için aktif müfredat eşlemesini parse_intent kuralından geçir
    mufredat = []
    for y in years_raw[:3]:  # en fazla 3 yıl karşılaştır
        fake_q = f"{y} ders programı"
        intent = parse_intent(fake_q, bolum)
        if intent:
            mufredat.append({"giris_yili": int(y), "mufredat_yili": intent["mufredat_yili"]})
    # Aynı müfredata düşen yılları teklemesin
    seen = set()
    uniq = []
    for m in mufredat:
        if m["mufredat_yili"] in seen:
            continue
        seen.add(m["mufredat_yili"])
        uniq.append(m)
    if len(uniq) < 2:
        return None
    return {"items": uniq}


def _format_courses_table(hits: list[dict]) -> dict[str, dict]:
    """Müfredat hit'lerini ders_kodu -> {ad, donem, ...} sözlüğüne çevir."""
    table: dict[str, dict] = {}
    for h in hits:
        md = h["metadata"]
        if md.get("tip") != "mufredat":
            continue
        kod = md.get("ders_kodu", "").strip()
        if not kod:
            continue
        table[kod] = {
            "ders_adi": md.get("ders_adi", ""),
            "donem": md.get("donem"),
            "akts": md.get("akts", ""),
            "kredi": md.get("kredi", ""),
            "on_sart": md.get("on_sart", ""),
        }
    return table


def compare_curricula(intent: dict, bolum: str, bolum_adi: str) -> dict:
    """Birden fazla müfredat yılını yan yana karşılaştır + farkları markdown'la döndür."""
    items = intent["items"]
    tables: list[tuple[dict, dict[str, dict]]] = []  # (item, course_table)
    all_hits: list[dict] = []
    for item in items:
        muf = item["mufredat_yili"]
        hits = fetch_semester_courses(muf, [1, 2, 3, 4, 5, 6, 7, 8], bolum)
        all_hits.extend(hits)
        tables.append((item, _format_courses_table(hits)))

    lines: list[str] = []
    lines.append(f"## {bolum_adi} — Müfredat Karşılaştırması")
    yrs = ", ".join(f"{it['mufredat_yili']}" for it, _ in tables)
    lines.append(f"_Karşılaştırılan müfredatlar: **{yrs}**_\n")

    # Her müfredatın ders sayısı özeti
    for item, tbl in tables:
        lines.append(
            f"- **{item['mufredat_yili']} müfredatı:** {len(tbl)} ders"
        )
    lines.append("")

    # Farklar: birinde olup diğer(ler)inde olmayanlar
    all_codes = set()
    for _, tbl in tables:
        all_codes.update(tbl.keys())

    only_in: dict[str, list[str]] = {}
    common: list[str] = []
    for kod in sorted(all_codes):
        present = [it["mufredat_yili"] for it, tbl in tables if kod in tbl]
        if len(present) == len(tables):
            common.append(kod)
        else:
            label = " + ".join(present)
            only_in.setdefault(label, []).append(kod)

    if only_in:
        lines.append(f"### ➕ Müfredata Özgü Dersler")
        for label, kodlar in only_in.items():
            lines.append(f"\n**Sadece {label} müfredatında ({len(kodlar)} ders):**")
            for kod in kodlar:
                # ilk eşleşen tabloda detayları bul
                detay = next((tbl[kod] for _, tbl in tables if kod in tbl), {})
                ad = detay.get("ders_adi", "")
                d = detay.get("donem", "")
                lines.append(f"- `{kod}` — {ad} _(dönem {d})_")
        lines.append("")

    if common:
        lines.append(f"### ✓ Ortak Dersler ({len(common)} adet)")
        # Çok kalabalıksa ilk 30 + "..."
        show = common[:30]
        lines.append(", ".join(f"`{k}`" for k in show)
                     + (f" _... ve {len(common)-30} ders daha_" if len(common) > 30 else ""))
        lines.append("")

    # AKTS / dönem değişen dersler
    if len(tables) == 2:
        (it1, t1), (it2, t2) = tables
        changed: list[str] = []
        for kod in sorted(set(t1.keys()) & set(t2.keys())):
            a, b = t1[kod], t2[kod]
            diffs = []
            if a.get("donem") != b.get("donem"):
                diffs.append(f"dönem {a.get('donem')}→{b.get('donem')}")
            if str(a.get("akts", "")).strip() != str(b.get("akts", "")).strip():
                diffs.append(f"AKTS {a.get('akts')}→{b.get('akts')}")
            if diffs:
                changed.append(f"- `{kod}` — {a.get('ders_adi','')}: {', '.join(diffs)}")
        if changed:
            lines.append(f"### 🔀 Aynı Ders, Farklı Konum/AKTS ({len(changed)} adet)")
            lines.extend(changed[:25])
            if len(changed) > 25:
                lines.append(f"_... ve {len(changed)-25} ders daha_")

    return {"answer": "\n".join(lines), "hits": all_hits}


# ============================ STREAMING ============================

class StreamedAnswer:
    """Streaming cevap kapsayıcısı. `hits` sorgu öncesi hazır, metin chunk'ları
    iterator üzerinden yayılır. Streamlit `st.write_stream(...)` ile uyumlu."""

    def __init__(self, hits: list[dict], chunk_iter):
        self.hits = hits
        self._iter = chunk_iter
        self._buffer: list[str] = []

    def __iter__(self):
        for chunk in self._iter:
            self._buffer.append(chunk)
            yield chunk

    @property
    def full_text(self) -> str:
        return "".join(self._buffer)


def _llm_stream_chunks(question: str, hits: list[dict], bolum: str,
                       history: list[dict] | None, prompt_extra: str = ""):
    """Groq streaming generator — token-by-token yield eder."""
    context = format_context(hits)
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)
    history_msgs = _build_history_messages(history)
    user_content = (
        f"BAĞLAM:\n{context}\n\n"
        f"SORU: {question}\n\n"
        "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. "
        "Önceki konuşma akışını dikkate al (kullanıcı kısa takip soruları sorabilir). "
        f"{prompt_extra}"
        "Kaynak belirt."
    )
    client = Groq()
    stream = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0.2,
        stream=True,
        messages=[
            {"role": "system", "content": sys_prompt},
            *history_msgs,
            {"role": "user", "content": user_content},
        ],
    )
    for chunk in stream:
        delta = getattr(chunk.choices[0].delta, "content", None)
        if delta:
            yield delta


def answer_stream(question: str, k: int = TOP_K, bolum: str = "bilgisayar",
                  history: list[dict] | None = None) -> StreamedAnswer:
    """Streaming varyantı. Kararlı (deterministik) modlarda metni tek parça yield eder;
    LLM modlarında token token Groq'tan akıtır."""
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")

    # Karşılaştırma — deterministik
    cmp_intent = detect_compare_intent(question, bolum)
    if cmp_intent:
        result = compare_curricula(cmp_intent, bolum, bolum_adi)
        return StreamedAnswer(result["hits"], iter([result["answer"]]))

    intent = parse_intent(question, bolum)

    # Ders kodu — LLM stream
    code_match = COURSE_CODE_RE.search(question.upper())
    if code_match:
        code = f"{code_match.group(1)} {code_match.group(2)}"
        code_hits = fetch_courses_by_code(code, bolum)
        if code_hits:
            extra = retrieve(question, k=3, bolum=bolum, history=history)
            seen = {h["text"] for h in code_hits}
            for h in extra:
                if h["text"] not in seen:
                    code_hits.append(h)
            extra_prompt = (
                "Eğer ön şart soruluyorsa BAĞLAM'daki 'Ön şart:' alanına bak. "
            )
            return StreamedAnswer(
                code_hits,
                _llm_stream_chunks(question, code_hits, bolum, history, extra_prompt),
            )

    # Liste modu — deterministik
    if intent:
        hits = fetch_semester_courses(intent["mufredat_yili"], intent["donems"], bolum)
        extra = retrieve(question, k=3, bolum=bolum, history=history)
        seen = {h["text"] for h in hits}
        for h in extra:
            if h["text"] not in seen:
                hits.append(h)
        text = _render_list_answer(intent, hits, bolum_adi)
        return StreamedAnswer(hits, iter([text]))

    # Genel LLM stream
    hits = retrieve(question, k=k, bolum=bolum, history=history)
    return StreamedAnswer(hits, _llm_stream_chunks(question, hits, bolum, history))


# =====================================================================


def _llm_messages(question: str, hits: list[dict], bolum: str,
                  history: list[dict] | None) -> list[dict]:
    """Streaming ve non-streaming çağrıların ortak mesaj listesi."""
    context = format_context(hits)
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)
    history_msgs = _build_history_messages(history)
    return [
        {"role": "system", "content": sys_prompt},
        *history_msgs,
        {
            "role": "user",
            "content": (
                f"BAĞLAM:\n{context}\n\n"
                f"SORU: {question}\n\n"
                "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. "
                "Önceki konuşma akışını dikkate al (kullanıcı kısa takip soruları sorabilir). "
                "Eğer ön şart soruluyorsa BAĞLAM'daki 'Ön şart:' alanına bak. "
                "Kaynak belirt."
            ),
        },
    ]


def answer_stream(question: str, k: int = TOP_K, bolum: str = "bilgisayar",
                  history: list[dict] | None = None):
    """Streaming-uyumlu cevap döndürür.

    Dönüş:
        {
          "mode": "list" | "compare" | "llm",
          "hits": [...],
          "text": str | None,           # liste/karşılaştırma modunda dolu
          "token_iter": iter | None,    # LLM modunda dolu — token akışı
        }
    """
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")

    # 1) Karşılaştırma — deterministik, stream yok
    cmp_intent = detect_compare_intent(question, bolum)
    if cmp_intent:
        res = compare_curricula(cmp_intent, bolum, bolum_adi)
        return {"mode": "compare", "hits": res["hits"], "text": res["answer"], "token_iter": None}

    intent = parse_intent(question, bolum)

    # 2) Ders kodu doğrudan fetch -> LLM (stream)
    code_match = COURSE_CODE_RE.search(question.upper())
    if code_match:
        code = f"{code_match.group(1)} {code_match.group(2)}"
        code_hits = fetch_courses_by_code(code, bolum)
        if code_hits:
            # Ek bağlam — reranker kapalı (zaten code_hits asıl kaynak)
            extra = retrieve(question, k=3, bolum=bolum, history=history, use_reranker=False)
            seen = {h["text"] for h in code_hits}
            for h in extra:
                if h["text"] not in seen:
                    code_hits.append(h)
            return _make_llm_stream(question, code_hits, bolum, history)

    # 3) Liste modu — deterministik, stream yok
    if intent:
        hits = fetch_semester_courses(intent["mufredat_yili"], intent["donems"], bolum)
        # Ek bağlam — reranker kapalı (zaten dönem dersleri kesin sonuç)
        extra = retrieve(question, k=3, bolum=bolum, history=history, use_reranker=False)
        seen = {h["text"] for h in hits}
        for h in extra:
            if h["text"] not in seen:
                hits.append(h)
        text = _render_list_answer(intent, hits, bolum_adi)
        return {"mode": "list", "hits": hits, "text": text, "token_iter": None}

    # 4) Genel RAG — LLM stream
    hits = retrieve(question, k=k, bolum=bolum, history=history)
    return _make_llm_stream(question, hits, bolum, history)


def _make_llm_stream(question: str, hits: list[dict], bolum: str,
                     history: list[dict] | None) -> dict:
    """Groq stream çağrısı + token generator döndür."""
    messages = _llm_messages(question, hits, bolum, history)

    def _token_generator():
        client = Groq()
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=1024,
            temperature=0.2,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    return {"mode": "llm", "hits": hits, "text": None, "token_iter": _token_generator()}


def answer(question: str, k: int = TOP_K, bolum: str = "bilgisayar",
           history: list[dict] | None = None) -> dict:
    bolum_adi = BOLUM_ADI_MAP.get(bolum, "Mühendislik")

    # Karşılaştırma modu (multi-year diff) — diğer intent'lerden önce kontrol
    cmp_intent = detect_compare_intent(question, bolum)
    if cmp_intent:
        return compare_curricula(cmp_intent, bolum, bolum_adi)

    intent = parse_intent(question, bolum)
    list_mode = False

    # Ders kodu + ön şart (veya genel ders detayı) -> doğrudan kod ile fetch
    code_match = COURSE_CODE_RE.search(question.upper())
    if code_match:
        code = f"{code_match.group(1)} {code_match.group(2)}"
        code_hits = fetch_courses_by_code(code, bolum)
        if code_hits:
            extra = retrieve(question, k=3, bolum=bolum, history=history)
            seen = {h["text"] for h in code_hits}
            for h in extra:
                if h["text"] not in seen:
                    code_hits.append(h)
            hits = code_hits
            # Liste modu DEĞİL — LLM normal cevap verecek (ön şart vb için)
            return _llm_answer(question, hits, bolum, history=history)

    if intent:
        hits = fetch_semester_courses(intent["mufredat_yili"], intent["donems"], bolum)
        extra = retrieve(question, k=3, bolum=bolum, history=history)
        seen = {h["text"] for h in hits}
        for h in extra:
            if h["text"] not in seen:
                hits.append(h)
        list_mode = True
    else:
        hits = retrieve(question, k=k, bolum=bolum, history=history)

    if list_mode:
        # LLM'i atla: dersleri deterministik markdown olarak render et (hiçbir ders kaçmaz)
        text = _render_list_answer(intent, hits, bolum_adi)
        return {"answer": text, "hits": hits}

    context = format_context(hits)
    sys_prompt = SYSTEM_PROMPT.format(bolum_adi=bolum_adi)
    history_msgs = _build_history_messages(history)

    client = Groq()
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys_prompt},
            *history_msgs,
            {
                "role": "user",
                "content": (
                    f"BAĞLAM:\n{context}\n\n"
                    f"SORU: {question}\n\n"
                    "Yukarıdaki bağlamı kullanarak Türkçe cevap ver. "
                    "Önceki konuşma akışını dikkate al (kullanıcı kısa takip soruları sorabilir). "
                    "Kaynak belirt."
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

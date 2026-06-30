"""
Bulut veri yükleyici — data/processed/*.jsonl chunk'larını Voyage AI ile
vektörleştirip Pinecone'a yükler.

Mevcut yerel sistem (ChromaDB + multilingual-e5-large) ile PARALEL bir bulut
kopyasıdır; yerel sistemi bozmaz. Bulut tarafı Voyage `voyage-3.5` (1024 boyut)
kullanır.

Çalıştır:  python veri_yukleyici.py
Gerekli .env:  VOYAGE_AI_KEY, PINECONE_API_KEY
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import voyageai
from pinecone import Pinecone, ServerlessSpec

# --------------------------------------------------------------------------- #
# Ayarlar
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = ROOT / "data" / "processed"

INDEX_NAME = "rag-asistan"
EMBED_MODEL = "voyage-3.5"        # 1024 boyut, çok dilli (Türkçe güçlü)
EMBED_DIM = 1024
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

EMBED_BATCH = 100                 # Voyage tek istekteki metin sayısı (limit < 1000)
UPSERT_BATCH = 100                # Pinecone tek upsert'teki vektör sayısı
META_TEXT_MAX = 38000             # Pinecone metadata limiti ~40KB; güvenli kırpma

# Anahtar adı .env ile birebir: VOYAGE_AI_KEY (VOYAGE_API_KEY DEĞİL)
vo = voyageai.Client(api_key=os.getenv("VOYAGE_AI_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
# Türkçe karakterleri ASCII'ye çevir (Pinecone vektör ID'leri ASCII olmalı)
_TR_ASCII = str.maketrans({
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
})


def _ascii_id(_id: str) -> str:
    """ID'yi ASCII'ye indirge; kalan ASCII-dışı karakterleri '_' yap."""
    s = _id.translate(_TR_ASCII)
    return s.encode("ascii", "replace").decode("ascii").replace("?", "_")


def chunklari_yukle() -> list[dict]:
    """Tüm data/processed/*.jsonl dosyalarını oku, ASCII-güvenli + benzersiz ID üret."""
    chunks: list[dict] = []
    for jsonl_file in sorted(PROCESSED_DIR.glob("*.jsonl")):
        with jsonl_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))

    # Önce ASCII'ye indirge, SONRA benzersizleştir (translit çakışmalarını da yakalar)
    seen: dict[str, int] = {}
    for c in chunks:
        _id = _ascii_id(c["id"])
        if _id in seen:
            seen[_id] += 1
            _id = f"{_id}__{seen[_id]}"
        else:
            seen[_id] = 0
        c["id"] = _id
    return chunks


def metadata_temizle(md: dict, text: str) -> dict:
    """Pinecone yalnızca str/int/float/bool/list[str] kabul eder; None'ları at.
    Asıl metni de metadata'ya gömüyoruz (retrieval'da gösterilecek)."""
    clean: dict = {}
    for k, v in (md or {}).items():
        if v is None or v == "":
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = [str(x) for x in v]
        else:
            clean[k] = str(v)
    clean["text"] = text[:META_TEXT_MAX]
    return clean


def index_hazirla():
    """Index yoksa doğru boyut/metric ile oluştur."""
    mevcut = [ix["name"] for ix in pc.list_indexes()]
    if INDEX_NAME not in mevcut:
        print(f"[+] '{INDEX_NAME}' index'i oluşturuluyor (dim={EMBED_DIM}, cosine)...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # Index hazır olana kadar bekle
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(1)
    else:
        # Boyut uyuşmazlığını erken yakala
        dim = pc.describe_index(INDEX_NAME).dimension
        if dim != EMBED_DIM:
            raise SystemExit(
                f"[HATA] '{INDEX_NAME}' index boyutu {dim}, beklenen {EMBED_DIM}. "
                f"Index'i {EMBED_DIM} boyutla yeniden oluşturman gerekir."
            )
    return pc.Index(INDEX_NAME)


def embed_batch(metinler: list[str], deneme: int = 3) -> list[list[float]]:
    """Voyage embed — geçici hatada üstel bekleme ile yeniden dene."""
    for i in range(deneme):
        try:
            # DOKÜMAN yüklerken input_type="document"
            r = vo.embed(metinler, model=EMBED_MODEL, input_type="document")
            return r.embeddings
        except Exception as e:
            if i == deneme - 1:
                raise
            bekle = 2 ** i
            print(f"    [!] embed hatası ({e}); {bekle}sn sonra tekrar...")
            time.sleep(bekle)
    return []


# --------------------------------------------------------------------------- #
# Ana akış
# --------------------------------------------------------------------------- #
def verileri_hazirla_ve_yukle():
    if not os.getenv("VOYAGE_AI_KEY"):
        raise SystemExit("[HATA] VOYAGE_AI_KEY .env'de tanımlı değil.")
    if not os.getenv("PINECONE_API_KEY"):
        raise SystemExit("[HATA] PINECONE_API_KEY .env'de tanımlı değil.")

    chunks = chunklari_yukle()
    print(f"[+] {len(chunks)} chunk yüklendi: {PROCESSED_DIR}")

    index = index_hazirla()

    pinecone_verisi: list[dict] = []
    toplam = len(chunks)

    # Batch'ler halinde embed et (tek seferde göndermek Voyage limitini aşar)
    for bas in range(0, toplam, EMBED_BATCH):
        grup = chunks[bas : bas + EMBED_BATCH]
        metinler = [c["text"] for c in grup]
        vektorler = embed_batch(metinler)

        for c, vec in zip(grup, vektorler):
            pinecone_verisi.append(
                {
                    "id": c["id"],
                    "values": vec,
                    "metadata": metadata_temizle(c.get("metadata", {}), c["text"]),
                }
            )
        print(f"    vektörleştirildi: {min(bas + EMBED_BATCH, toplam)}/{toplam}")

    # Pinecone'a batch'ler halinde upsert
    print("[+] Pinecone'a yükleniyor...")
    for bas in range(0, len(pinecone_verisi), UPSERT_BATCH):
        index.upsert(vectors=pinecone_verisi[bas : bas + UPSERT_BATCH])
        print(f"    upsert: {min(bas + UPSERT_BATCH, len(pinecone_verisi))}/{len(pinecone_verisi)}")

    stats = index.describe_index_stats()
    print(f"[OK] Yükleme tamam. Index toplam vektör: {stats.get('total_vector_count')}")


if __name__ == "__main__":
    verileri_hazirla_ve_yukle()

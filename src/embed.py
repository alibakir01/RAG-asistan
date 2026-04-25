"""
chunks.jsonl -> ChromaDB
Multilingual embedding (intfloat/multilingual-e5-large) — Türkçe + İngilizce birlikte.
e5 modeli için döküman prefix'i "passage: " olmalı.
"""
from __future__ import annotations

import json
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
CHROMA_DIR = ROOT / "data" / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "intfloat/multilingual-e5-large"
COLLECTION = "agu_comp"
BATCH = 32


def sanitize_metadata(md: dict) -> dict:
    """Chroma yalnızca str/int/float/bool kabul eder, None'ları temizle."""
    clean = {}
    for k, v in md.items():
        if v is None or v == "":
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def main():
    print(f"[+] chunks yükleniyor: {PROCESSED_DIR}/*.jsonl")
    chunks = []
    for jsonl_file in PROCESSED_DIR.glob("*.jsonl"):
        with jsonl_file.open(encoding="utf-8") as f:
            for line in f:
                chunks.append(json.loads(line))
    print(f"    {len(chunks)} chunk")

    print(f"[+] embedding modeli: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print(f"[+] ChromaDB: {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))

    # Temiz baslangic icin mevcut kolleksiyonu sil
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    # e5 modeli passage prefix'i bekler
    texts = [f"passage: {c['text']}" for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [sanitize_metadata(c["metadata"]) for c in chunks]
    raw_texts = [c["text"] for c in chunks]  # kaydedilen dokuman (retrieval'da gosterilecek)

    print(f"[+] embedding hesaplaniyor (batch={BATCH})...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    print(f"    shape: {embeddings.shape}")

    print(f"[+] ChromaDB'ye yazılıyor...")
    # Chunk'larda ID tekrari olmasin; varsa id'yi index ile zenginleştir
    seen = {}
    unique_ids = []
    for i, _id in enumerate(ids):
        if _id in seen:
            seen[_id] += 1
            unique_ids.append(f"{_id}__{seen[_id]}")
        else:
            seen[_id] = 0
            unique_ids.append(_id)

    # Batch halinde ekle
    B = 200
    for i in range(0, len(ids), B):
        collection.add(
            ids=unique_ids[i : i + B],
            embeddings=embeddings[i : i + B].tolist(),
            documents=raw_texts[i : i + B],
            metadatas=metadatas[i : i + B],
        )
    print(f"[OK] {collection.count()} chunk indexlendi.")


if __name__ == "__main__":
    main()

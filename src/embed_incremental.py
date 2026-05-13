"""
Incremental embedder: Only embeds chunks that are not already in ChromaDB.
"""
import json
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
CHROMA_DIR = ROOT / "data" / "chroma"

MODEL_NAME = "intfloat/multilingual-e5-large"
COLLECTION = "agu_comp"
BATCH = 32

def sanitize_metadata(md: dict) -> dict:
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
    print(f"[+] ChromaDB: {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    
    collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    existing_data = collection.get(include=[])
    existing_ids = set(existing_data["ids"])
    print(f"[+] Veritabanında {len(existing_ids)} adet chunk var.")

    print(f"[+] chunks yükleniyor: {PROCESSED_DIR}/*.jsonl")
    chunks = []
    for jsonl_file in PROCESSED_DIR.glob("*.jsonl"):
        with jsonl_file.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
    
    seen = {}
    unique_ids_map = {}
    for c in chunks:
        _id = c["id"]
        if _id in seen:
            seen[_id] += 1
            uid = f"{_id}__{seen[_id]}"
        else:
            seen[_id] = 0
            uid = _id
        unique_ids_map[uid] = c
        
    missing_ids = [uid for uid in unique_ids_map if uid not in existing_ids]
    print(f"[+] Toplam jsonl chunk sayısı: {len(unique_ids_map)}")
    print(f"[+] Eksik olan ve eklenecek chunk sayısı: {len(missing_ids)}")

    if not missing_ids:
        print("[+] Eklenecek yeni chunk yok. Çıkılıyor.")
        return

    missing_chunks = [unique_ids_map[uid] for uid in missing_ids]

    print(f"[+] embedding modeli yükleniyor: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    texts = [f"passage: {c['text']}" for c in missing_chunks]
    metadatas = [sanitize_metadata(c["metadata"]) for c in missing_chunks]
    raw_texts = [c["text"] for c in missing_chunks]

    print(f"[+] embedding hesaplaniyor (batch={BATCH})...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    print(f"[+] ChromaDB'ye yazılıyor...")
    B = 200
    for i in range(0, len(missing_ids), B):
        collection.add(
            ids=missing_ids[i : i + B],
            embeddings=embeddings[i : i + B].tolist(),
            documents=raw_texts[i : i + B],
            metadatas=metadatas[i : i + B],
        )
    print(f"[OK] {len(missing_ids)} yeni chunk indexlendi. Güncel DB boyutu: {collection.count()}")

if __name__ == "__main__":
    main()

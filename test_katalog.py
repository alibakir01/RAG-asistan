import sys, json
sys.stdout.reconfigure(encoding='utf-8')

with open("data/processed/chunks_siyaset.jsonl", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

print(f"Toplam chunk: {len(chunks)}\n")

# Tip dağılımı
from collections import Counter
tip_count = Counter(c["metadata"]["tip"] for c in chunks)
for t, n in tip_count.most_common():
    print(f"  {t}: {n}")

print("\n--- ÖRNEK ders_icerik (POLS 311 Uluslararası Örgütler) ---")
for c in chunks:
    md = c["metadata"]
    if md["tip"] == "ders_icerik" and md.get("ders_kodu") == "POLS 311":
        print(c["text"][:800])
        break

print("\n--- ÖRNEK program_genel ---")
for c in chunks:
    if c["metadata"]["tip"] == "program_genel":
        print(c["text"][:600])
        break

print("\n--- ÖRNEK program_ciktilari ---")
for c in chunks:
    if c["metadata"]["tip"] == "program_ciktilari":
        print(c["text"][:400])
        break

print("\n--- ÖRNEK not_sistemi ---")
for c in chunks:
    if c["metadata"]["tip"] == "not_sistemi":
        print(c["text"][:400])
        break

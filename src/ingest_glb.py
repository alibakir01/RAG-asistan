"""
GLB Ortak Zorunlu Seçmeli Dersleri — tüm bölümler (bilgisayar/makine/endüstri) için geçerli.
Her ders için her bölüm tarafına bir chunk üretir + bölüm başına bir özet chunk.
Çıktı: data/processed/chunks_glb.jsonl
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

CSV_FILE = RAW / "glb_ortak_secmeli.csv"
OUT_FILE = OUT / "chunks_glb.jsonl"

BOLUMLER = [
    ("bilgisayar", "Bilgisayar Mühendisliği"),
    ("makine", "Makine Mühendisliği"),
    ("endustri", "Endüstri Mühendisliği"),
    ("elektrik", "Elektrik-Elektronik Mühendisliği"),
    ("insaat", "İnşaat Mühendisliği"),
]


def main():
    if not CSV_FILE.exists():
        print(f"[!] bulunamadı: {CSV_FILE}")
        return

    courses = []
    with CSV_FILE.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kod = (row.get("Ders Kodu") or "").strip()
            ad = (row.get("Ders Adı") or "").strip()
            t = (row.get("Teo.") or row.get("Teorik") or "").strip()
            l = (row.get("Lab.") or row.get("Lab") or "").strip()
            k = (row.get("Kredi") or "").strip()
            a = (row.get("AKTS") or "").strip()
            if kod and ad:
                courses.append({"kod": kod, "ad": ad, "t": t, "l": l, "kredi": k, "akts": a})

    chunks = []
    for bolum_id, bolum_adi in BOLUMLER:
        # Per-ders chunk'ları
        for c in courses:
            text = (
                f"{bolum_adi} — Ortak Zorunlu Seçmeli (GLB Havuzu): "
                f"{c['kod']} {c['ad']}. Teorik: {c['t']}, Lab: {c['l']}, "
                f"Kredi: {c['kredi']}, AKTS: {c['akts']}. "
                f"Bu ders tüm bölümler (bilgisayar, makine, endüstri) için ortak GLB seçmeli havuzundan alınır."
            )
            chunks.append({
                "id": f"glb_{bolum_id}_{c['kod'].replace(' ','')}",
                "text": text,
                "metadata": {
                    "tip": "glb_ortak_secmeli",
                    "havuz": "GLB Ortak Zorunlu Seçmeli",
                    "ders_kodu": c["kod"],
                    "ders_adi": c["ad"],
                    "teorik": c["t"],
                    "lab": c["l"],
                    "kredi": c["kredi"],
                    "akts": c["akts"],
                    "kaynak": CSV_FILE.name,
                    "bolum": bolum_id,
                },
            })

        # Bölüm başına toplu özet
        lines = [
            f"- {c['kod']} | {c['ad']} | T:{c['t']}, L:{c['l']}, Kredi:{c['kredi']}, AKTS:{c['akts']}"
            for c in courses
        ]
        body = (
            f"{bolum_adi} — GLB Ortak Zorunlu Seçmeli Ders Havuzu "
            f"(toplam {len(courses)} ders, tüm bölümler için ortak):\n"
            + "\n".join(lines)
            + "\n\nNot: GLB dersleri Bilgisayar, Makine ve Endüstri Mühendisliği bölümlerinin "
              "tümünde ortak zorunlu seçmeli olarak alınır."
        )
        chunks.append({
            "id": f"glb_havuz_ozet_{bolum_id}",
            "text": body,
            "metadata": {
                "tip": "glb_ortak_secmeli_ozet",
                "havuz": "GLB Ortak Zorunlu Seçmeli",
                "ders_sayisi": len(courses),
                "kaynak": CSV_FILE.name,
                "bolum": bolum_id,
            },
        })

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} GLB chunk -> {OUT_FILE}")
    print(f"     ({len(courses)} ders × {len(BOLUMLER)} bölüm + {len(BOLUMLER)} özet)")


if __name__ == "__main__":
    main()

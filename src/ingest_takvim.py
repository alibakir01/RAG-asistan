"""
AGÜ Akademik Takvim — tüm bölümler için ortak ingest.
Çıktı: data/processed/chunks_takvim.jsonl  (bolum="ortak")
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

XLSX = RAW / "akademik_takvim_2025_2026.xlsx"
BOLUM = "ortak"  # tüm bölümler için ortak metadata

AY_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}
GUN_TR = {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}


def fmt_date(ts) -> str:
    if pd.isna(ts):
        return ""
    return f"{ts.day} {AY_TR[ts.month]} {ts.year} {GUN_TR[ts.weekday()]}"


def fmt_range(start, end) -> str:
    s, e = fmt_date(start), fmt_date(end)
    if not s and not e:
        return ""
    if not e or s == e:
        return s
    return f"{s} – {e}"


def main():
    if not XLSX.exists():
        print(f"[!] bulunamadı: {XLSX}")
        return

    df = pd.read_excel(XLSX, sheet_name="Akademik Takvim", header=4)
    df.columns = [str(c).strip() for c in df.columns]
    # Beklenen sütunlar: Dönem | Etkinlik | Başlangıç Tarihi | Bitiş Tarihi | Notlar
    chunks: list[dict] = []
    by_donem: dict[str, list[str]] = {}

    for ri, row in df.iterrows():
        donem = str(row.get("Dönem", "")).strip()
        etkinlik = str(row.get("Etkinlik", "")).strip()
        bas = row.get("Başlangıç Tarihi")
        bit = row.get("Bitiş Tarihi")
        notlar_raw = row.get("Notlar")
        notlar = "" if pd.isna(notlar_raw) else str(notlar_raw).strip()
        if not etkinlik or etkinlik == "nan":
            continue

        tarih_str = fmt_range(bas, bit)
        text_parts = [
            f"AGÜ 2025-2026 Akademik Takvim — {donem}: {etkinlik}.",
            f"Tarih: {tarih_str}." if tarih_str else "",
            f"Notlar: {notlar}" if notlar else "",
        ]
        text = " ".join(p for p in text_parts if p)

        chunks.append({
            "id": f"takvim_2025_26_{ri+1:03d}",
            "text": text,
            "metadata": {
                "tip": "akademik_takvim",
                "donem": donem,
                "etkinlik": etkinlik,
                "baslangic": str(bas)[:10] if not pd.isna(bas) else "",
                "bitis": str(bit)[:10] if not pd.isna(bit) else "",
                "akademik_yili": "2025-2026",
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

        by_donem.setdefault(donem, []).append(
            f"- {etkinlik} ({tarih_str})" + (f" — {notlar}" if notlar else "")
        )

    # Dönem bazlı özet chunk'ları
    for donem, lines in by_donem.items():
        body = (
            f"AGÜ 2025-2026 Akademik Takvim — {donem} dönemine ait tüm etkinlikler "
            f"({len(lines)} adet):\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"takvim_2025_26_ozet_{donem.replace(' ', '_')}",
            "text": body[:5000],
            "metadata": {
                "tip": "akademik_takvim_ozet",
                "donem": donem,
                "akademik_yili": "2025-2026",
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

    out_path = OUT / "chunks_takvim.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"[OK] {len(chunks)} takvim chunk -> {out_path}")
    print(f"     dönemler: {list(by_donem.keys())}")


if __name__ == "__main__":
    main()

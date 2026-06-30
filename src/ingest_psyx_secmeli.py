"""
AGÜ Psikoloji — PSYX152 (Bölüm Dışı / Sınırsız Seçmeli) için onaylı transfer
edilebilen online (Udemy vb.) dersler listesi.

Kaynak: data/raw/PSYX_Ders_Listesi.xlsx
Her satır bir online ders; danışman onayıyla PSYX152'ye karşılık gelir.

Çıktı: data/processed/chunks_psyx_secmeli.jsonl
bolum = "psikoloji"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

XLSX = RAW / "PSYX_Ders_Listesi.xlsx"
BOLUM = "psikoloji"
BOLUM_ADI = "Psikoloji"
TARGET_CODE = "PSYX 152"


def _to_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower())
    return s.strip("_")[:n]


def parse_xlsx() -> list[dict]:
    if not XLSX.exists():
        print(f"[!] bulunamadı: {XLSX}")
        return []

    df = pd.read_excel(XLSX, sheet_name=0)
    # Beklenen kolonlar: Name of the course | Platform | Expected status |
    # Expected ECTS | The transferred course if accepted by advisor | Hours | Link | Note
    chunks: list[dict] = []
    summary_lines: list[str] = []

    for i, row in df.iterrows():
        name = _to_str(row.get("Name of the course"))
        if not name:
            continue
        platform = _to_str(row.get("Platform"))
        status = _to_str(row.get("Expected status"))
        ects = _to_str(row.get("Expected ECTS"))
        transferred = _to_str(row.get("The transferred course if accepted by advisor")) or TARGET_CODE
        hours = _to_str(row.get("Hours"))
        link = _to_str(row.get("Link"))
        note = _to_str(row.get("Note"))

        # Tek satır: bir online ders → PSYX 152
        text = (
            f"AGÜ Psikoloji bölümü — Bölüm Dışı / Sınırsız Seçmeli (PSYX 152) için "
            f"danışman onayıyla TRANSFER EDİLEBİLEN online ders: "
            f"\"{name}\" ({platform}). "
            f"Beklenen statü: {status or 'belirtilmemiş'}. "
            f"Beklenen AKTS (ECTS): {ects or '—'}. "
            f"Karşılık geleceği AGÜ dersi: {transferred}. "
            f"Süre: {hours or '—'}. "
            f"Link: {link or '—'}."
        )
        if note:
            text += f" Bölüm notu: {note}"

        cid = f"psyx_secmeli_{i+1:02d}_{_slug(name)}"
        chunks.append({
            "id": cid,
            "text": text,
            "metadata": {
                "tip": "secmeli_transfer",
                "kategori": "Bölüm Dışı Seçmeli (PSYX 152) Transfer Onaylı Online Ders",
                "ders_adi": name,
                "platform": platform,
                "transferred_to": transferred,
                "ders_kodu": transferred,  # arama kolaylığı
                "akts": ects,
                "sure": hours,
                "link": link,
                "not": note,
                "donem_listesi": "2022-2023",
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

        summary_lines.append(
            f"- \"{name}\" ({platform}, {hours or '—'}) → {transferred} "
            f"({ects or '—'} AKTS)" + (f" — Not: {note[:120]}" if note else "")
        )

    # Topluca özet chunk — "PSYX 152 yerine hangi dersler alınabilir?" gibi sorgular
    if summary_lines:
        body = (
            f"AGÜ Psikoloji Bölümü — PSYX 152 (Bölüm Dışı / Sınırsız Seçmeli) için "
            f"danışman onayıyla TRANSFER EDİLEBİLEN onaylı online ders listesi "
            f"(2022-2023 dönemi referansı, toplam {len(summary_lines)} ders). "
            f"Bu listedeki Udemy vb. platform dersleri başarıyla tamamlandığında "
            f"PSYX 152 (5 AKTS, Bölüm Dışı / Sınırsız Seçmeli) yerine sayılabilir. "
            f"Danışman onayı şarttır. Süresi uzun olan dersler için bölüm 'önerilmez' "
            f"uyarısı yapmıştır:\n\n" + "\n".join(summary_lines) +
            "\n\nNot: Bu liste 2022-2023 Bahar dönemi için onaylanmış referans listedir; "
            "yeni dönemlerde liste değişebilir, güncel durum için danışmana danışılmalıdır."
        )
        chunks.append({
            "id": "psyx152_transfer_listesi_ozet",
            "text": body[:5000],
            "metadata": {
                "tip": "secmeli_transfer_ozet",
                "kategori": "Bölüm Dışı Seçmeli (PSYX 152) Transfer Listesi",
                "ders_kodu": TARGET_CODE,
                "ders_sayisi": len(summary_lines),
                "donem_listesi": "2022-2023",
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def main():
    chunks = parse_xlsx()
    out_path = OUT / "chunks_psyx_secmeli.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} PSYX seçmeli chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

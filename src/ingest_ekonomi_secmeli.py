"""
AGÜ Ekonomi Bölümü Seçmeli Dersler ingest.
Kaynak: data/raw/AGU_Ekonomi_Secmeli.xlsx
Format (header): Ders Kodu | Ders Adı | Ön Koşul | Teorik | Lab | Kredi | AKTS | Kategori

Kategoriler:
  - Seçmeli Dersler (Departmental — ECON 2xx/3xx/4xx kodlu)
  - Exchange Transfer Seçmelileri (ECD4xx)
  - General Transfer Seçmelileri (ECN4xx)

Çıktı: data/processed/chunks_ekonomi_secmeli.jsonl
bolum = "ekonomi"
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

XLSX = RAW / "AGU_Ekonomi_Secmeli.xlsx"
BOLUM = "ekonomi"
BOLUM_ADI = "Ekonomi"


def _norm_kod(raw: str) -> str:
    s = re.sub(r"\s+", "", raw or "").upper()
    m = re.match(r"^([A-Z]+)(\d+\w*)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _to_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _short_label(kategori: str) -> str:
    s = kategori.lower()
    if "exchange transfer" in s:
        return "Exchange Transfer Seçmelileri"
    if "general transfer" in s:
        return "General Transfer Seçmelileri"
    if "seçmeli" in s or "secmeli" in s:
        return "Bölüm Seçmeli Dersleri (Departmental Elective)"
    return kategori


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def parse_xlsx() -> dict[str, list[dict]]:
    if not XLSX.exists():
        print(f"[!] bulunamadı: {XLSX}")
        return {}

    df = pd.read_excel(XLSX, sheet_name=0, header=None)
    rows = df.values.tolist()
    grouped: dict[str, list[dict]] = {}
    for ri, row in enumerate(rows):
        if ri == 0:
            continue  # header
        kod_raw = _to_str(row[0]) if len(row) > 0 else ""
        ad = _to_str(row[1]) if len(row) > 1 else ""
        on_sart = _to_str(row[2]) if len(row) > 2 else ""
        teorik = _to_str(row[3]) if len(row) > 3 else ""
        lab = _to_str(row[4]) if len(row) > 4 else ""
        kredi = _to_str(row[5]) if len(row) > 5 else ""
        akts = _to_str(row[6]) if len(row) > 6 else ""
        kategori = _to_str(row[7]) if len(row) > 7 else ""

        if not kod_raw or not ad or not kategori:
            continue

        kod = _norm_kod(kod_raw)
        on_sart_clean = on_sart.strip().strip("-").strip()
        grouped.setdefault(kategori, []).append({
            "kod": kod,
            "ad": ad,
            "on_sart": on_sart_clean,
            "teorik": teorik,
            "lab": lab,
            "kredi": kredi,
            "akts": akts,
            "kategori_raw": kategori,
        })
    return grouped


def main():
    grouped = parse_xlsx()
    if not grouped:
        print("[!] XLSX verisi yüklenemedi.")
        return

    chunks: list[dict] = []
    total = 0

    # 1) Her ders için bireysel chunk
    for cat_raw, courses in grouped.items():
        label = _short_label(cat_raw)
        for c in courses:
            text = (
                f"AGÜ Ekonomi Bölümü — Seçmeli Ders: {c['kod']} {c['ad']}. "
                f"Kategori: {label}. "
                f"Teorik: {c['teorik'] or '—'}, Lab: {c['lab'] or '—'}, "
                f"Kredi: {c['kredi'] or '—'}, AKTS: {c['akts'] or '—'}. "
                f"Ön şart: {c['on_sart'] if c['on_sart'] else 'yok'}. "
                f"Bu ders {label} havuzundan seçilebilir bir seçmeli derstir."
            )
            chunks.append({
                "id": f"ekonomi_secmeli_{c['kod'].replace(' ', '')}",
                "text": text,
                "metadata": {
                    "tip": "secmeli_havuz",
                    "kategori": label,
                    "ders_kodu": c["kod"],
                    "ders_adi": c["ad"],
                    "on_sart": c["on_sart"],
                    "teorik": c["teorik"],
                    "lab": c["lab"],
                    "kredi": c["kredi"],
                    "akts": c["akts"],
                    "kaynak": XLSX.name,
                    "bolum": BOLUM,
                },
            })
            total += 1

    # 2) Kategori özet chunk'ları
    for cat_raw, courses in grouped.items():
        label = _short_label(cat_raw)
        body_lines = []
        for c in courses:
            on = c["on_sart"] or "yok"
            body_lines.append(
                f"- {c['kod']} | {c['ad']} | T:{c['teorik'] or '—'}, "
                f"Kredi:{c['kredi'] or '—'}, AKTS:{c['akts'] or '—'} | Ön şart: {on}"
            )
        text = (
            f"AGÜ Ekonomi Bölümü — {label} havuzu. "
            f"Bu havuzda toplam {len(courses)} seçmeli ders bulunmaktadır. "
            f"Öğrenci ilgili dönemde bu havuzdan ders seçer.\n\n"
            f"Havuzdaki dersler:\n" + "\n".join(body_lines)
        )
        chunks.append({
            "id": f"ekonomi_secmeli_ozet_{_slug(label)[:40]}",
            "text": text[:5500],
            "metadata": {
                "tip": "secmeli_havuz_ozet",
                "kategori": label,
                "ders_sayisi": len(courses),
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

    # 3) Master overview
    master_lines = [f"- **{_short_label(c)}**: {len(v)} ders" for c, v in grouped.items()]
    master_text = (
        f"AGÜ Ekonomi Bölümü — Seçmeli Ders Havuzları Genel Özeti.\n\n"
        f"Ekonomi programında {len(grouped)} farklı seçmeli kategori bulunmaktadır, "
        f"toplam {total} seçmeli ders:\n\n"
        + "\n".join(master_lines)
        + "\n\nBölüm Seçmeli Dersleri (Departmental Elective) ECON 2xx-4xx kodları altında "
        "konu odaklı (mikroekonometri, davranışsal iktisat, oyun teorisi, sağlık ekonomisi, "
        "uluslararası finans, bölgesel ekonomiler vb.) konularda sunulurken; "
        "Exchange/General Transfer Seçmelileri (ECD/ECN kodlu) yatay geçiş ve değişim "
        "öğrencileri için kullanılır."
    )
    chunks.append({
        "id": "ekonomi_secmeli_master",
        "text": master_text,
        "metadata": {
            "tip": "secmeli_havuz_ozet",
            "kategori": "Tüm Seçmeli Havuzları",
            "ders_sayisi": total,
            "kaynak": XLSX.name,
            "bolum": BOLUM,
        },
    })

    out_path = OUT / "chunks_ekonomi_secmeli.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} ekonomi seçmeli chunk -> {out_path}")
    print(f"     - secmeli_havuz: {total}")
    print(f"     - secmeli_havuz_ozet: {len(grouped) + 1}")
    for cat_raw, courses in grouped.items():
        print(f"       {_short_label(cat_raw)}: {len(courses)} ders")


if __name__ == "__main__":
    main()

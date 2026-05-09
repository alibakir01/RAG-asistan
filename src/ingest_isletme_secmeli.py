"""
AGÜ İşletme Bölümü Seçmeli Dersler ingest.
Kaynak: data/raw/isletme_secmeli.csv (Google Sheets'ten indirildi)
Format: Kategori | Ders Kodu | Ders Adı | Ön Koşul | Teori | Lab. | Kredi | AKTS | Bölüm içi/dışı

Kategoriler:
  - General Transfer Seçmelileri (4 ders, Bölüm Dışı)
  - Exchange Transfer Seçmelileri (3 ders)
  - Bölüm İçi Diğer Seçmeli Dersler (7 ders)
  - Sayısal Yöntemler Alanındaki Seçmeli Dersler (10 ders)
  - Yönetim ve Organizasyon Alanındaki Seçmeli Dersler (11 ders)
  - Muhasebe ve Finans Alanındaki Seçmeli Dersler (12 ders)
  - Üretim Yönetimi ve Pazarlama Alanındaki Seçmeli Dersler (15 ders)

Çıktı: data/processed/chunks_isletme_secmeli.jsonl
bolum = "isletme"
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

CSV_PATH = RAW / "isletme_secmeli.csv"
BOLUM = "isletme"
BOLUM_ADI = "İşletme"


def _norm_kod(raw: str) -> str:
    """BA125 → 'BA 125'."""
    s = re.sub(r"\s+", "", raw or "").upper()
    m = re.match(r"^([A-Z]+)(\d+\w*)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _short_label(kategori: str) -> str:
    """Uzun kategori adından kısa label çıkar (chunk metni / arama için)."""
    s = kategori.lower()
    if "general transfer" in s:
        return "General Transfer Seçmelileri"
    if "exchange transfer" in s:
        return "Exchange Transfer Seçmelileri"
    if "sayısal yöntemler" in s:
        return "Sayısal Yöntemler Alanı Seçmelileri"
    if "yönetim ve organizasyon" in s:
        return "Yönetim ve Organizasyon Alanı Seçmelileri"
    if "muhasebe ve finans" in s:
        return "Muhasebe ve Finans Alanı Seçmelileri"
    if "üretim yönetimi" in s and "pazarlama" in s:
        return "Üretim Yönetimi ve Pazarlama Alanı Seçmelileri"
    if "bölüm içi diğer" in s or "diğer seçmeli" in s:
        return "Bölüm İçi Diğer Seçmeliler"
    return kategori


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def parse_csv() -> dict[str, list[dict]]:
    if not CSV_PATH.exists():
        print(f"[!] bulunamadı: {CSV_PATH}")
        return {}

    grouped: dict[str, list[dict]] = {}
    with CSV_PATH.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kategori = (row.get("Kategori") or "").strip()
            kod_raw = (row.get("Ders Kodu") or "").strip()
            ad = (row.get("Ders Adı") or "").strip()
            on_sart = (row.get("Ön Koşul") or "").strip()
            teorik = (row.get("Teori") or "").strip()
            lab = (row.get("Lab.") or row.get("Lab") or "").strip()
            kredi = (row.get("Kredi") or "").strip()
            akts = (row.get("AKTS") or "").strip()
            ic_dis = (row.get("Bölüm içi/Bölüm dışı seçmeli") or "").strip()

            if not kategori or not kod_raw or not ad:
                continue

            kod = _norm_kod(kod_raw)
            grouped.setdefault(kategori, []).append({
                "kod": kod,
                "ad": ad,
                "on_sart": on_sart,
                "teorik": teorik,
                "lab": lab,
                "kredi": kredi,
                "akts": akts,
                "ic_dis": ic_dis,
                "kategori_raw": kategori,
            })
    return grouped


def main():
    grouped = parse_csv()
    if not grouped:
        print("[!] CSV verisi yüklenemedi.")
        return

    chunks: list[dict] = []
    total = 0

    # ----- 1) Her ders için bir chunk (secmeli_havuz) -----
    for cat_raw, courses in grouped.items():
        label = _short_label(cat_raw)
        for c in courses:
            text = (
                f"AGÜ İşletme Bölümü — Seçmeli Ders: {c['kod']} {c['ad']}. "
                f"Kategori: {label}. "
                f"Teorik: {c['teorik'] or '—'}, Lab: {c['lab'] or '—'}, "
                f"Kredi: {c['kredi'] or '—'}, AKTS: {c['akts'] or '—'}. "
                f"Ön şart: {c['on_sart'] if c['on_sart'] else 'yok'}. "
                f"Tip: {c['ic_dis'] or 'Seçmeli'}. "
                f"Bu ders {label} havuzundan seçilebilir bir seçmeli derstir."
            )
            chunks.append({
                "id": f"isletme_secmeli_{c['kod'].replace(' ', '')}",
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
                    "ders_tipi": c["ic_dis"] or "Seçmeli",
                    "kaynak": CSV_PATH.name,
                    "bolum": BOLUM,
                },
            })
            total += 1

    # ----- 2) Kategori bazlı toplu liste (secmeli_havuz_ozet) -----
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
            f"AGÜ İşletme Bölümü — {label} havuzu. "
            f"Bu havuzda toplam {len(courses)} seçmeli ders bulunmaktadır. "
            f"Öğrenci ilgili dönemde bu havuzdan ders seçer.\n\n"
            f"Havuzdaki dersler:\n" + "\n".join(body_lines)
        )
        chunks.append({
            "id": f"isletme_secmeli_ozet_{_slug(label)[:40]}",
            "text": text[:5500],
            "metadata": {
                "tip": "secmeli_havuz_ozet",
                "kategori": label,
                "ders_sayisi": len(courses),
                "kaynak": CSV_PATH.name,
                "bolum": BOLUM,
            },
        })

    # ----- 3) Master overview chunk -----
    master_lines = []
    for cat_raw, courses in grouped.items():
        label = _short_label(cat_raw)
        master_lines.append(f"- **{label}**: {len(courses)} ders")
    master_text = (
        f"AGÜ İşletme Bölümü — Seçmeli Ders Havuzları Genel Özeti.\n\n"
        f"İşletme programında {len(grouped)} farklı seçmeli kategori bulunmaktadır, "
        f"toplam {total} seçmeli ders:\n\n"
        + "\n".join(master_lines)
        + "\n\nBölüm İçi seçmeliler bölümün uzmanlık alanlarından (Sayısal Yöntemler, "
        "Yönetim & Organizasyon, Muhasebe & Finans, Üretim Yönetimi & Pazarlama) gelirken; "
        "Transfer Seçmelileri (General/Exchange) yatay/dikey geçiş ve değişim öğrencileri "
        "için kullanılır. Detaylı liste için ilgili kategori chunk'ına bakılır."
    )
    chunks.append({
        "id": "isletme_secmeli_master",
        "text": master_text,
        "metadata": {
            "tip": "secmeli_havuz_ozet",
            "kategori": "Tüm Seçmeli Havuzları",
            "ders_sayisi": total,
            "kaynak": CSV_PATH.name,
            "bolum": BOLUM,
        },
    })

    out_path = OUT / "chunks_isletme_secmeli.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} işletme seçmeli chunk -> {out_path}")
    print(f"     - secmeli_havuz: {total}")
    print(f"     - secmeli_havuz_ozet: {len(grouped) + 1} ({len(grouped)} kategori + 1 master)")
    for cat_raw, courses in grouped.items():
        print(f"       {_short_label(cat_raw)}: {len(courses)} ders")


if __name__ == "__main__":
    main()

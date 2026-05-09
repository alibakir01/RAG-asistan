"""
AGÜ İşletme Bölümü Müfredat ingest.
Kaynak: data/raw/AGU_Isletme_Mufredati.xlsx (Müfredat sheet)

Format: Her dönem "X. Yıl Güz/Bahar Dönemi (...)" başlığı ile başlar, ardından
"Ders Kodu | Ders Adı | Ön Koşul | Teorik | Lab | Kredi | AKTS" header'ı +
ders satırları gelir. "Total Credits" satırı dönemi kapatır.

Çıktı: data/processed/chunks_isletme.jsonl
bolum = "isletme"
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

XLSX = RAW / "AGU_Isletme_Mufredati.xlsx"
BOLUM = "isletme"
BOLUM_ADI = "İşletme"
MUFREDAT_YILI = "2025"

# "1. Yıl Güz Dönemi (Freshman Year / FALL Semester)" gibi başlıkları yakala
SEMESTER_HEADER_RE = re.compile(
    r"^\s*(\d)\.\s*Yıl\s*(Güz|Bahar)\s*Dönemi", re.IGNORECASE
)


def _norm_kod(raw) -> str:
    """COMP101 / MATH 111 / BA125 → 'COMP 101' (boşluklu standart)."""
    s = re.sub(r"\s+", "", str(raw or "")).upper()
    m = re.match(r"^([A-Z]+)(\d+\w*)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _to_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _yil_sezon_to_donem(yil: int, sezon: str) -> int:
    offset = 1 if sezon.lower() == "güz" else 2
    return (yil - 1) * 2 + offset


def parse_xlsx() -> list[dict]:
    if not XLSX.exists():
        print(f"[!] bulunamadı: {XLSX}")
        return []

    df = pd.read_excel(XLSX, sheet_name="Müfredat", header=None)
    rows = df.values.tolist()

    chunks: list[dict] = []
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    seen_codes: set[str] = set()

    current_donem: int | None = None
    current_yil: int | None = None
    current_sezon: str = ""
    awaiting_header = False  # ders header satırını bekliyoruz

    for ri, row in enumerate(rows):
        first = _to_str(row[0]) if len(row) > 0 else ""
        second = _to_str(row[1]) if len(row) > 1 else ""

        # Dönem başlığı yakala
        m = SEMESTER_HEADER_RE.match(first)
        if m:
            current_yil = int(m.group(1))
            current_sezon = m.group(2)
            current_donem = _yil_sezon_to_donem(current_yil, current_sezon)
            awaiting_header = True
            continue

        # "Ders Kodu" header satırı — atla
        if first.lower() == "ders kodu" and second.lower().startswith("ders ad"):
            awaiting_header = False
            continue

        # "Total Credits" → dönem bitti
        if "total credits" in second.lower() or "toplam" in second.lower():
            current_donem = None
            continue

        # Boş satır
        if not first and not second:
            continue

        # Ders satırı (current_donem set olmalı)
        if current_donem is None:
            continue

        kod = _norm_kod(first)
        ad = second
        on_sart = _to_str(row[2]) if len(row) > 2 else ""
        teorik = _to_str(row[3]) if len(row) > 3 else ""
        lab = _to_str(row[4]) if len(row) > 4 else ""
        kredi = _to_str(row[5]) if len(row) > 5 else ""
        akts = _to_str(row[6]) if len(row) > 6 else ""

        if not kod or not ad:
            continue

        # Tekrar eden kodları benzersizleştir (placeholder kodları için: GLB1XX, GLB2XX-1 vb.)
        uniq = kod
        if "X" in kod or kod in seen_codes:
            uniq = f"{kod}_{current_donem}"
            i = 1
            while f"{uniq}_{i}" in seen_codes:
                i += 1
            if uniq in seen_codes:
                uniq = f"{uniq}_{i}"
        seen_codes.add(uniq)

        on_sart_clean = on_sart.strip().strip("-").strip()

        # ----- Müfredat chunk'ı (kısa, liste modunda kullanılır) -----
        muf_text = (
            f"{MUFREDAT_YILI} {BOLUM_ADI} müfredatı — "
            f"{current_yil}. yıl {current_sezon} dönemi ({current_donem}. dönem): "
            f"{kod} {ad}. "
            f"Teorik: {teorik or '—'}, Lab: {lab or '—'}, Kredi: {kredi or '—'}, AKTS: {akts or '—'}. "
            f"Ön şart: {on_sart_clean if on_sart_clean else 'yok'}."
        )
        chunks.append({
            "id": f"isletme_muf_d{current_donem}_{uniq.replace(' ', '_').replace('*','')}",
            "text": muf_text,
            "metadata": {
                "tip": "mufredat",
                "mufredat_yili": MUFREDAT_YILI,
                "donem": current_donem,
                "yil": current_yil,
                "sezon": current_sezon,
                "ders_kodu": kod,
                "ders_adi": ad,
                "on_sart": on_sart_clean,
                "teorik": teorik,
                "lab": lab,
                "kredi": kredi,
                "akts": akts,
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

        short = (
            f"- {kod} | {ad} | T:{teorik or '—'}, L:{lab or '—'}, "
            f"Kredi:{kredi or '—'}, AKTS:{akts or '—'} | Ön şart: {on_sart_clean or 'yok'}"
        )
        semester_courses.setdefault(current_donem, []).append(short)
        semester_meta.setdefault(current_donem, {"yil": current_yil, "sezon": current_sezon})

    # ----- Dönem özet chunk'ları -----
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {MUFREDAT_YILI} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — "
            f"Toplam {len(lines)} ders:\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"isletme_muf_sem_d{donem}",
            "text": body[:5000],
            "metadata": {
                "tip": "donem_ozet",
                "mufredat_yili": MUFREDAT_YILI,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": XLSX.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def make_program_overview() -> dict:
    text = (
        "Abdullah Gül Üniversitesi İşletme Bölümü (BA — Business Administration) lisans programı. "
        "4 yıl süreli, 8 dönemlik program. Eğitim dili İngilizce. "
        "İşletme temellerini (BA125, BA120, BA224 — pazarlama, finans, muhasebe), "
        "ekonomi (BA225 Microeconomics, BA224 Macroeconomics), kantitatif analiz "
        "(matematik, istatistik, yöneylem), yönetim ve organizasyon, yönetim bilişim sistemleri "
        "ve seçmeli derslerle birleştirir. Bölüm kodu: BA. "
        "Mezuniyet için tüm zorunlu dersler + bölüm-içi/dışı seçmeliler ve gerekli AKTS "
        "yükümlülükleri tamamlanmalıdır."
    )
    return {
        "id": "isletme_program_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "kaynak": "program_tanitim",
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_xlsx()
    chunks.append(make_program_overview())
    out_path = OUT / "chunks_isletme.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} işletme chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

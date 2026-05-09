"""
AGÜ Mimarlık Bölümü Seçmeli Dersler ingest.
Kaynak: data/raw/mimarlik_secmeli.csv (Google Sheets'ten indirildi)
Format: Kategori | AKTS | Ders Kodu | Ders Adı

Kategoriler:
  - ARCG Elective I (3 ECTS)
  - ARCD Elective II (5 ECTS)
  - ARCA Elective III (6 ECTS)
  - Değişim/Transfer Dersleri (Exchange/Transfer Courses)

Çıktı: data/processed/chunks_mimarlik_secmeli.jsonl
bolum = "mimarlik"
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

CSV_PATH = RAW / "mimarlik_secmeli.csv"
BOLUM = "mimarlik"
BOLUM_ADI = "Mimarlık"

# Kategori adı CSV'de değişebilir (ARCG Elective I, Elective(seçmeli) I, ...)
# Hem kategori adına hem de örnek bir ders kodu prefix'ine bakarak tespit yaparız.
def _resolve_category(cat_raw: str, sample_kod: str = "") -> tuple[str, str, str]:
    """(label, ECTS, prefix) çıkar. Önce Transfer/Exchange kontrolü, sonra kod prefix'i,
    son çare kategori metni."""
    s = (cat_raw or "").upper()
    # 1) Transfer/Exchange/Değişim — kategori adından net belli olur
    if "TRANSFER" in s or "DEĞİŞİM" in s or "DEGISIM" in s or "EXCHANGE" in s:
        return ("Değişim/Transfer Seçmelileri (Exchange/Transfer)", "—", "TRANSFER")
    # 2) Ders kodu prefix'i en güvenilir sinyal — başlıktaki "ARCG" eksik olsa bile yakalar
    kod_clean = (sample_kod or "").upper().replace(" ", "")
    for pref, meta in [
        ("ARCG", ("ARCG Seçmeli I (Elective I)", "3 ECTS", "ARCG")),
        ("ARCD", ("ARCD Seçmeli II (Elective II)", "5 ECTS", "ARCD")),
        ("ARCA", ("ARCA Seçmeli III (Elective III)", "6 ECTS", "ARCA")),
    ]:
        if kod_clean.startswith(pref):
            return meta
    # 3) Yedek: kategori metninde de ara
    if "ARCG" in s:
        return ("ARCG Seçmeli I (Elective I)", "3 ECTS", "ARCG")
    if "ARCD" in s:
        return ("ARCD Seçmeli II (Elective II)", "5 ECTS", "ARCD")
    if "ARCA" in s:
        return ("ARCA Seçmeli III (Elective III)", "6 ECTS", "ARCA")
    return (cat_raw, "—", "")


def _norm_kod(raw: str) -> str:
    """ARCG103 → 'ARCG 103' gibi standart format."""
    s = re.sub(r"\s+", "", raw or "").upper()
    m = re.match(r"^([A-Z]+)(\d+)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def parse_csv() -> dict[str, list[dict]]:
    """Kategori adı (CSV'deki ham hâliyle) → ders listesi sözlüğü döndür."""
    if not CSV_PATH.exists():
        print(f"[!] bulunamadı: {CSV_PATH}")
        return {}

    grouped: dict[str, list[dict]] = {}
    current_cat: str | None = None

    with CSV_PATH.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            cells = [c.strip() for c in row]
            # boş satır
            if not any(cells):
                continue
            kategori = cells[0] if len(cells) > 0 else ""
            akts = cells[1] if len(cells) > 1 else ""
            kod_raw = cells[2] if len(cells) > 2 else ""
            ad = cells[3] if len(cells) > 3 else ""

            # Header satırı (Kategori,AKTS,Ders Kodu,Ders Adı)
            if kategori.lower() == "kategori":
                continue

            # Yeni kategori başlığı: birinci sütun dolu, ders kodu boş
            if kategori and not kod_raw:
                current_cat = kategori
                grouped.setdefault(current_cat, [])
                continue

            # Ders satırı içinde tekrar "Ders Kodu" ara-başlığı (transfer kısmında var)
            if kod_raw.lower() == "ders kodu":
                continue

            if not kod_raw:
                continue

            kod = _norm_kod(kod_raw)
            # AKTS sayısını çıkar (örn. "3 ECTS" → "3")
            akts_num = ""
            m = re.search(r"(\d+)", akts)
            if m:
                akts_num = m.group(1)

            if current_cat is None:
                continue
            grouped[current_cat].append({
                "kod": kod,
                "ad": ad,
                "akts": akts_num,
                "akts_label": akts,
                "kategori_raw": current_cat,
            })

    return grouped


def main():
    grouped = parse_csv()
    if not grouped:
        print("[!] CSV'de veri bulunamadı.")
        return

    chunks: list[dict] = []
    total = 0

    # ----- 1) Her ders için tek chunk (secmeli_havuz) -----
    for cat_raw, courses in grouped.items():
        sample_kod = courses[0]["kod"] if courses else ""
        meta = _resolve_category(cat_raw, sample_kod)
        cat_label, ects, prefix = meta
        for c in courses:
            text = (
                f"AGÜ Mimarlık Bölümü — Seçmeli Ders: {c['kod']} {c['ad']}. "
                f"Kategori: {cat_label} ({c['akts_label'] or ects}). "
                f"AKTS: {c['akts'] or '—'}. "
                f"Bu ders, {cat_label} havuzundan seçilebilir bir seçmeli derstir; "
                f"öğrenci ilgili dönemde bu havuzdan bir ders seçer."
            )
            chunks.append({
                "id": f"mimarlik_secmeli_{c['kod'].replace(' ', '')}",
                "text": text,
                "metadata": {
                    "tip": "secmeli_havuz",
                    "kategori": cat_label,
                    "prefix": prefix,
                    "ders_kodu": c["kod"],
                    "ders_adi": c["ad"],
                    "akts": c["akts"],
                    "kaynak": CSV_PATH.name,
                    "bolum": BOLUM,
                },
            })
            total += 1

    # ----- 2) Her kategori için toplu liste (secmeli_havuz_ozet) -----
    for cat_raw, courses in grouped.items():
        sample_kod = courses[0]["kod"] if courses else ""
        meta = _resolve_category(cat_raw, sample_kod)
        cat_label, ects, prefix = meta
        if not courses:
            continue
        body_lines = [
            f"- {c['kod']} | {c['ad']} | AKTS: {c['akts'] or '—'}"
            for c in courses
        ]
        text = (
            f"AGÜ Mimarlık Bölümü — {cat_label} havuzu ({ects}). "
            f"Bu havuzda toplam {len(courses)} seçmeli ders bulunmaktadır. "
            f"Öğrenci ilgili dönemde bu havuzdan bir ders seçer.\n\n"
            f"Havuzdaki dersler:\n" + "\n".join(body_lines)
        )
        chunks.append({
            "id": f"mimarlik_secmeli_ozet_{prefix or cat_raw.replace(' ', '_')[:20]}",
            "text": text[:5500],
            "metadata": {
                "tip": "secmeli_havuz_ozet",
                "kategori": cat_label,
                "prefix": prefix,
                "ders_sayisi": len(courses),
                "kaynak": CSV_PATH.name,
                "bolum": BOLUM,
            },
        })

    # ----- 3) Tüm seçmeli kategorilerini özetleyen ana chunk -----
    master_lines = []
    for cat_raw, courses in grouped.items():
        sample_kod = courses[0]["kod"] if courses else ""
        meta = _resolve_category(cat_raw, sample_kod)
        cat_label, ects, _ = meta
        master_lines.append(f"- **{cat_label}** ({ects}): {len(courses)} ders")

    master_text = (
        f"AGÜ Mimarlık Bölümü — Seçmeli Ders Havuzları Genel Özeti.\n\n"
        f"Mimarlık programında {len(grouped)} farklı seçmeli kategori bulunmaktadır, "
        f"toplam {total} seçmeli ders:\n\n"
        + "\n".join(master_lines)
        + "\n\nÖğrenci ilgili dönemlerde her havuzdan ayrı bir ders seçer. "
        "Detaylı liste için ilgili kategori chunk'ına bakılır."
    )
    chunks.append({
        "id": "mimarlik_secmeli_master",
        "text": master_text,
        "metadata": {
            "tip": "secmeli_havuz_ozet",
            "kategori": "Tüm Seçmeli Havuzları",
            "ders_sayisi": total,
            "kaynak": CSV_PATH.name,
            "bolum": BOLUM,
        },
    })

    out_path = OUT / "chunks_mimarlik_secmeli.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} mimarlık seçmeli chunk -> {out_path}")
    print(f"     - secmeli_havuz: {total}")
    print(f"     - secmeli_havuz_ozet: {len(grouped) + 1} ({len(grouped)} kategori + 1 master)")
    for cat_raw, courses in grouped.items():
        sample_kod = courses[0]["kod"] if courses else ""
        meta = _resolve_category(cat_raw, sample_kod)
        print(f"       {meta[0]}: {len(courses)} ders")


if __name__ == "__main__":
    main()

"""
Malzeme Bilimi ve Nanoteknoloji Mühendisliği (MSNE) ingest modülü.
Kaynak: Google Sheets müfredat (data/raw/malzeme_mufredat.csv)
Çıktı: data/processed/chunks_malzeme.jsonl
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

BOLUM = "malzeme"
BOLUM_ADI = "Malzeme Bilimi ve Nanoteknoloji Mühendisliği"

# Tek aktif müfredat var (Google Sheets'ten); ileride birden fazla olursa map'e eklenir.
MUFREDAT_CSV = {
    "2025": "malzeme_mufredat.csv",
}

SEZON_TO_OFFSET = {"Güz": 1, "Bahar": 2, "guz": 1, "bahar": 2}


def parse_mufredat_csv(path: Path, mufredat_yili: str):
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    chunks: list[dict] = []

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for ri, row in enumerate(reader, start=1):
            try:
                yil = int(str(row.get("Yıl", "")).strip())
            except (ValueError, TypeError):
                continue
            sezon_raw = (row.get("Dönem") or "").strip()
            offset = SEZON_TO_OFFSET.get(sezon_raw)
            if offset is None:
                continue
            donem = (yil - 1) * 2 + offset
            sezon = "Güz" if offset == 1 else "Bahar"

            kod = (row.get("Ders Kodu") or "").strip()
            ad = (row.get("Ders Adı") or "").strip()
            on = (row.get("Ön-Şart") or row.get("Ön Şart") or "").strip().strip("-").strip()
            t = (row.get("T") or "").strip()
            u = (row.get("U") or "").strip()
            l = (row.get("L") or "").strip()
            k = (row.get("K") or "").strip()
            a = (row.get("AKTS") or "").strip()
            if not ad:
                continue
            if not kod or kod == "-":
                kod = "MSNE-ELEC"

            text = (
                f"{mufredat_yili} {BOLUM_ADI} müfredatı — {yil}. yıl {sezon} dönemi "
                f"({donem}. dönem): {kod} {ad}. "
                f"Teorik (T): {t or '—'}, Uygulama (U): {u or '—'}, Lab (L): {l or '—'}, "
                f"Kredi (K): {k or '—'}, AKTS: {a or '—'}. "
                f"Ön şart: {on if on else 'yok'}."
            )
            chunks.append({
                "id": f"msne_muf_{mufredat_yili}_d{donem}_r{ri}_{kod.replace(' ', '')}",
                "text": text,
                "metadata": {
                    "tip": "mufredat",
                    "mufredat_yili": mufredat_yili,
                    "donem": donem,
                    "yil": yil,
                    "sezon": sezon,
                    "ders_kodu": kod,
                    "ders_adi": ad,
                    "on_sart": on,
                    "teorik": t,
                    "uygulama": u,
                    "lab": l,
                    "kredi": k,
                    "akts": a,
                    "kaynak": path.name,
                    "bolum": BOLUM,
                },
            })

            short = (
                f"- {kod} | {ad} | T:{t or '—'}, U:{u or '—'}, L:{l or '—'}, "
                f"Kredi:{k or '—'}, AKTS:{a or '—'} | Ön şart: {on or 'yok'}"
            )
            semester_courses.setdefault(donem, []).append(short)
            semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — "
            f"Toplam {len(lines)} ders:\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"msne_muf_{mufredat_yili}_sem_summary_d{donem}",
            "text": body,
            "metadata": {
                "tip": "donem_ozet",
                "mufredat_yili": mufredat_yili,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })

    # Tüm müfredata genel bakış chunk'ı (program tanıtımı / arama kolaylığı)
    all_lines: list[str] = []
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        all_lines.append(f"\n## {meta['yil']}. yıl {meta['sezon']} dönemi ({donem}. dönem)")
        all_lines.extend(lines)
    chunks.append({
        "id": f"msne_muf_{mufredat_yili}_full",
        "text": (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Tüm Program (4 yıl, 8 dönem):\n"
            + "\n".join(all_lines)
        )[:6000],
        "metadata": {
            "tip": "mufredat_genel",
            "mufredat_yili": mufredat_yili,
            "kaynak": path.name,
            "bolum": BOLUM,
        },
    })

    return chunks


def parse_secmeli_csv(path: Path, mufredat_yili: str = "2025"):
    """Teknik seçmeli grupları (kategori başlıklı çok bölümlü CSV) parse eder."""
    chunks: list[dict] = []
    if not path.exists():
        return chunks

    # Kategori -> (yil, sezon, donem)
    KATEGORI_META = {
        "Teknik Seçmeli I": (3, "Güz", 5),
        "Teknik Seçmeli II": (3, "Bahar", 6),
        "Teknik Seçmeli III": (4, "Güz", 7),
        "Seçmeli Uzun Dönem Staj": (4, "Bahar", 8),
    }

    current_kategori: str | None = None
    grouped: dict[str, list[dict]] = {}

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            cells = [c.strip() for c in row]
            if not any(cells):
                continue
            # Kategori başlık satırı: ilk hücre boş, ikinci hücre başlık metni
            if len(cells) >= 2 and not cells[0] and cells[1]:
                heading = cells[1]
                matched = None
                for key in KATEGORI_META:
                    if key in heading:
                        matched = key
                        break
                if matched:
                    current_kategori = heading  # tam başlık (parantez dahil)
                    grouped.setdefault(current_kategori, [])
                continue
            # Header satırı (Kod, Ders Adı, Ön-Şart)
            if cells[0].lower() == "kod":
                continue
            # Ders satırı
            if current_kategori and len(cells) >= 2 and cells[0]:
                kod = cells[0]
                ad = cells[1]
                on = (cells[2] if len(cells) >= 3 else "").strip().strip("-").strip()
                grouped[current_kategori].append({"kod": kod, "ad": ad, "on": on})

    for kategori_full, courses in grouped.items():
        # Kategori anahtar kısmını bul
        key = next((k for k in KATEGORI_META if k in kategori_full), None)
        if not key:
            continue
        yil, sezon, donem = KATEGORI_META[key]

        # Her ders için tek chunk
        for ri, c in enumerate(courses, start=1):
            text = (
                f"{BOLUM_ADI} {mufredat_yili} müfredatı — {kategori_full} — "
                f"({yil}. yıl {sezon}, {donem}. dönem): {c['kod']} {c['ad']}. "
                f"Ön şart: {c['on'] if c['on'] else 'yok'}. "
                f"Bu ders bir SEÇMELİ derstir ({key} havuzundan)."
            )
            chunks.append({
                "id": f"msne_secmeli_{key.replace(' ', '_')}_{c['kod'].replace(' ', '')}_{ri}",
                "text": text,
                "metadata": {
                    "tip": "secmeli_ders",
                    "mufredat_yili": mufredat_yili,
                    "kategori": key,
                    "kategori_full": kategori_full,
                    "donem": donem,
                    "yil": yil,
                    "sezon": sezon,
                    "ders_kodu": c["kod"],
                    "ders_adi": c["ad"],
                    "on_sart": c["on"],
                    "kaynak": path.name,
                    "bolum": BOLUM,
                },
            })

        # Kategori özet chunk'ı (havuzdaki tüm dersleri tek yerde)
        body_lines = [
            f"- {c['kod']} | {c['ad']} | Ön şart: {c['on'] or 'yok'}"
            for c in courses
        ]
        summary_text = (
            f"{BOLUM_ADI} — {kategori_full} havuzu "
            f"({yil}. yıl {sezon} dönemi / {donem}. dönem) — "
            f"Toplam {len(courses)} seçmeli ders:\n" + "\n".join(body_lines)
        )
        chunks.append({
            "id": f"msne_secmeli_summary_{key.replace(' ', '_')}",
            "text": summary_text,
            "metadata": {
                "tip": "secmeli_havuz",
                "mufredat_yili": mufredat_yili,
                "kategori": key,
                "kategori_full": kategori_full,
                "donem": donem,
                "yil": yil,
                "sezon": sezon,
                "ders_sayisi": len(courses),
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })

    return chunks


YONETMELIK_PDF = "AGU_Lisans_Egitim_Ogretim_Sinav_Yonetmeligi.pdf"
MSNE_CATALOG_PDF = "MSNE_2025_Program_Bilgileri_Ders_Kataloglari.pdf"

# "MADDE 1 –" / "MADDE 12 -" formatı (en/em-dash veya hyphen)
MADDE_RE = re.compile(r"MADDE\s+(\d+)\s*[–\-—]")
# "Code MSNE205" / "Code MSNE 205" / "Code PHYS 102"
CATALOG_CODE_RE = re.compile(r"^Code\s+([A-Z]{2,5})\s*(\d{2,4})\s*$", re.MULTILINE)


def parse_yonetmelik_pdf(path: Path):
    """AGÜ Lisans Eğitim Öğretim ve Sınav Yönetmeliği — MADDE bazlı parse."""
    chunks: list[dict] = []
    if not path.exists():
        return chunks
    try:
        with pdfplumber.open(path) as pdf:
            full = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return chunks

    matches = list(MADDE_RE.finditer(full))
    if not matches:
        return chunks

    for i, m in enumerate(matches):
        no = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        block = full[start:end].strip()
        # Başlık: MADDE satırından önceki satırı yakalamaya çalış
        before = full[max(0, start - 200):start].strip().split("\n")
        baslik = before[-1].strip() if before else ""
        # Aşırı uzun maddeleri kırp
        body = block[:3500]
        text = (
            f"AGÜ Lisans Eğitim Öğretim ve Sınav Yönetmeliği — MADDE {no}"
            + (f" ({baslik})" if baslik and len(baslik) < 80 else "")
            + f":\n{body}"
        )
        chunks.append({
            "id": f"agu_yonetmelik_madde_{no}",
            "text": text,
            "metadata": {
                "tip": "yonetmelik",
                "kategori": "lisans_egitim_ogretim_sinav",
                "madde_no": int(no),
                "baslik": baslik[:80],
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


def parse_msne_catalog_pdf(path: Path):
    """MSNE 2025 Program Bilgileri ve Ders Katalogları PDF'i.
    İki bölüm:
      (a) Program bilgileri (ilk ~15 sayfa) — blok bazlı genel chunk'lar
      (b) Course Record blokları — her ders için ayrı chunk
    """
    chunks: list[dict] = []
    if not path.exists():
        return chunks
    try:
        with pdfplumber.open(path) as pdf:
            full = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return chunks

    # (b) önce yakala — ilk "Code XXX YYY" başlığının pozisyonunu bul
    code_matches = list(CATALOG_CODE_RE.finditer(full))
    catalog_start = code_matches[0].start() if code_matches else len(full)

    # (a) Program bilgileri kısmı: catalog_start öncesi, blok bazlı (~25 satır)
    intro_text = full[:catalog_start]
    lines = [ln.strip() for ln in intro_text.split("\n") if ln.strip()]
    block, blocks = [], []
    for ln in lines:
        block.append(ln)
        if len(block) >= 25:
            blocks.append(" ".join(block))
            block = []
    if block:
        blocks.append(" ".join(block))

    for i, body in enumerate(blocks):
        text = (
            f"{BOLUM_ADI} 2025 Program Bilgileri — Bölüm {i+1}:\n{body}"
        )
        chunks.append({
            "id": f"msne_program_info_b{i+1}",
            "text": text[:3500],
            "metadata": {
                "tip": "program_bilgi",
                "mufredat_yili": "2025",
                "bolum_no": i + 1,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })

    # (b) Course Record blokları
    for i, m in enumerate(code_matches):
        prefix = m.group(1)
        num = m.group(2)
        kod = f"{prefix} {num}"
        start = m.start()
        end = code_matches[i + 1].start() if i + 1 < len(code_matches) else len(full)
        block = full[start:end].strip()

        def _field(name: str) -> str:
            mm = re.search(rf"^{name}\s+(.+)$", block, re.MULTILINE)
            return mm.group(1).strip() if mm else ""

        ders_adi = _field("Name")
        on_sart = _field("Prerequisites")
        ders_tipi = _field("Type")
        akts = _field("ECTS")
        kredi = _field("Credit")
        seviye = _field("Level/Year")

        text = (
            f"{BOLUM_ADI} — Ders Kataloğu (2025): {kod} {ders_adi}.\n"
            f"Tip: {ders_tipi or '—'}, Seviye/Yıl: {seviye or '—'}, "
            f"Kredi: {kredi or '—'}, AKTS: {akts or '—'}, "
            f"Ön şart: {on_sart if on_sart and on_sart != '-' else 'yok'}.\n\n"
            f"{block}"
        )
        chunks.append({
            "id": f"msne_kat_{kod.replace(' ', '')}",
            "text": text[:4500],
            "metadata": {
                "tip": "ders_katalog",
                "ders_kodu": kod,
                "ders_adi": ders_adi,
                "ders_tipi": ders_tipi,
                "seviye_yil": seviye,
                "on_sart": on_sart if on_sart != "-" else "",
                "kredi": kredi,
                "akts": akts,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def make_program_overview_chunk():
    """MSNE programı hakkında genel bilgi chunk'ı."""
    text = (
        f"Abdullah Gül Üniversitesi {BOLUM_ADI} (MSNE) lisans programı, "
        "malzeme biliminin temellerini nanoteknoloji uygulamalarıyla birleştirir. "
        "Program 4 yıl (8 dönem) sürer ve şu konuları kapsar: "
        "malzeme bilimi temelleri, katıhal fiziği, kuantum fiziği, fizikokimya, "
        "termodinamik ve kinetik, polimer bilimi, seramikler ve camlar, "
        "biyomalzemeler, metaller ve metalik nanomalzemeler, nanomalzemeler ve aygıtlar, "
        "ileri üretim ve karakterizasyon. "
        "Bölüm kodu: MSNE. Mezuniyet için bitirme projesi (MSNE 401) ve yaz stajı (MSNE 403) zorunludur. "
        "Öğrenciler ayrıca Teknik Seçmeli (MSNETX), Teknik Olmayan Seçmeli (MSNENX), "
        "Seçmeli Küresel Sorunlar (GLB) ve isteğe bağlı uzun dönem staj (MSNEIX) derslerini alabilir."
    )
    return [{
        "id": "msne_program_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "kaynak": "program_tanitim",
            "bolum": BOLUM,
        },
    }]


def main():
    all_chunks: list[dict] = []

    for yil, fn in MUFREDAT_CSV.items():
        p = RAW / fn
        if not p.exists():
            print(f"[!] bulunamadı: {p.name}")
            continue
        chs = parse_mufredat_csv(p, yil)
        all_chunks.extend(chs)
        print(f"[MSNE müfredat {yil}] {len(chs)} chunk")

    # Teknik seçmeli havuzları
    secmeli_path = RAW / "malzeme_secmeli.csv"
    sec_chs = parse_secmeli_csv(secmeli_path)
    all_chunks.extend(sec_chs)
    print(f"[MSNE seçmeli dersler] {len(sec_chs)} chunk")

    overview = make_program_overview_chunk()
    all_chunks.extend(overview)
    print(f"[MSNE program tanıtım] {len(overview)} chunk")

    # AGÜ Lisans Eğitim Öğretim ve Sınav Yönetmeliği (genel ama MSNE için indexlenir)
    yonetmelik_chs = parse_yonetmelik_pdf(RAW / YONETMELIK_PDF)
    all_chunks.extend(yonetmelik_chs)
    print(f"[AGÜ Lisans Yönetmeliği] {len(yonetmelik_chs)} chunk")

    # MSNE 2025 Program Bilgileri ve Ders Katalogları PDF
    catalog_chs = parse_msne_catalog_pdf(RAW / MSNE_CATALOG_PDF)
    all_chunks.extend(catalog_chs)
    print(f"[MSNE 2025 program/ders kataloğu] {len(catalog_chs)} chunk")

    out_path = OUT / "chunks_malzeme.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"\n[OK] Toplam {len(all_chunks)} malzeme chunk -> {out_path}")


if __name__ == "__main__":
    main()

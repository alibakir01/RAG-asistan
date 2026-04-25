import json
from pathlib import Path
from typing import Iterator
import pdfplumber
from docx import Document
import pandas as pd
import re

ROOT = Path(__file__).resolve().parents[1]
RAW_ME = ROOT / "data" / "raw" / "makine mühendisliği"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

def parse_pdf_text(path: Path, doc_type: str, lang: str) -> Iterator[dict]:
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            lines = text.split("\n")
            paragraphs = []
            current_chunk = []
            for line in lines:
                if line.strip():
                    current_chunk.append(line.strip())
                if len(current_chunk) >= 15:
                    paragraphs.append(" ".join(current_chunk))
                    current_chunk = []
            if current_chunk:
                paragraphs.append(" ".join(current_chunk))
            
            for i, para in enumerate(paragraphs):
                yield {
                    "id": f"me_{doc_type}_{path.stem}_{i}",
                    "text": f"Makine Mühendisliği {doc_type} ({path.name}):\n{para}",
                    "metadata": {
                        "bolum": "makine",
                        "tip": doc_type,
                        "kaynak": path.name,
                        "dil": lang
                    }
                }
    except Exception as e:
        print(f"Error parsing {path.name}: {e}")

def parse_docx_text(path: Path) -> Iterator[dict]:
    try:
        doc = Document(path)
        text = "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        for i, para in enumerate(paragraphs):
            yield {
                "id": f"me_docx_{path.stem}_{i}",
                "text": f"Makine Mühendisliği Seçmeli Dersler:\n{para}",
                "metadata": {
                    "bolum": "makine",
                    "tip": "secmeli_listesi",
                    "kaynak": path.name,
                }
            }
    except Exception as e:
        print(f"Error parsing {path.name}: {e}")

SEZON_BY_DONEM = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar", 5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}


def _parse_sheet_to_donem(sheet_name: str) -> tuple[int, int, str]:
    """'1. Dönem' veya '1. Sınıf Güz Yarıyılı' -> (donem, yil, sezon)"""
    s = sheet_name.lower()
    # "1. Sınıf Güz/Bahar Yarıyılı" formatı
    m = re.search(r"(\d+)\s*\.?\s*s[ıi]n[ıi]f.{0,15}?(g[üu]z|bahar)", s)
    if m:
        yil = int(m.group(1))
        sezon = "Güz" if m.group(2).startswith("g") else "Bahar"
        donem = (yil - 1) * 2 + (1 if sezon == "Güz" else 2)
        return donem, yil, sezon
    # "1. Dönem" formatı
    m = re.search(r"(\d+)\s*\.?\s*d[öo]nem", s)
    if m:
        donem = int(m.group(1))
        yil = (donem - 1) // 2 + 1
        sezon = SEZON_BY_DONEM.get(donem, "")
        return donem, yil, sezon
    # Fallback: ilk sayıyı dönem olarak al
    m = re.search(r"(\d+)", s)
    if m:
        donem = int(m.group(1))
        return donem, (donem - 1) // 2 + 1, SEZON_BY_DONEM.get(donem, "")
    return 0, 0, ""


COL_ALIASES_ME = {
    "ders_kodu": ["ders kodu", "kod", "course code", "code"],
    "ders_adi": ["ders adı", "ders adi", "ad", "course name", "name"],
    "on_sart": ["ön şart", "on sart", "pre req", "prereq", "prerequisites", "pre-req"],
    "teorik": ["teorik", "lec.", "lec", "lecture", "t"],
    "lab": ["lab.", "lab", "laboratuvar", "p"],
    "kredi": ["kredi", "credits", "credit"],
    "akts": ["akts", "ects"],
}


def _build_col_map(df_cols) -> dict:
    cmap = {}
    for ci, col in enumerate(df_cols):
        cl = str(col).strip().lower()
        for key, alts in COL_ALIASES_ME.items():
            if any(cl == a or cl.startswith(a) for a in alts):
                cmap.setdefault(key, ci)
                break
    return cmap


def _val(row, cmap, key) -> str:
    i = cmap.get(key)
    if i is None or i >= len(row):
        return ""
    v = row.iloc[i] if hasattr(row, "iloc") else row[i]
    if pd.isna(v):
        return ""
    s = str(v).strip()
    # Float gibi görünen tam sayıları temizle (3.0 -> 3)
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s


def parse_excel_mufredat(path: Path, mufredat_yili: str) -> Iterator[dict]:
    """Per-ders + dönem özet chunk'ları (diğer bölümlerle uyumlu şema)."""
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        print(f"Error opening {path.name}: {e}")
        return

    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}

    for sheet_name in xls.sheet_names:
        try:
            df = xls.parse(sheet_name)
        except Exception as e:
            print(f"Error parsing sheet {sheet_name}: {e}")
            continue

        donem, yil, sezon = _parse_sheet_to_donem(sheet_name)
        if not donem:
            continue
        cmap = _build_col_map(df.columns)
        if "ders_kodu" not in cmap or "ders_adi" not in cmap:
            continue

        for ri, row in df.iterrows():
            kod = _val(row, cmap, "ders_kodu")
            ad = _val(row, cmap, "ders_adi")
            if not ad or ad.upper() in ("TOPLAM", "TOTAL", "NAN"):
                continue
            on = _val(row, cmap, "on_sart").strip("-").strip()
            t = _val(row, cmap, "teorik")
            l = _val(row, cmap, "lab")
            k = _val(row, cmap, "kredi")
            a = _val(row, cmap, "akts")
            if not kod:
                kod = "ME-ELEC"

            text = (
                f"Makine Mühendisliği {mufredat_yili} Müfredatı — {yil}. yıl {sezon} dönemi "
                f"({donem}. dönem): {kod} {ad}. "
                f"Teorik: {t or '—'}, Lab: {l or '—'}, Kredi: {k or '—'}, AKTS: {a or '—'}. "
                f"Ön şart: {on if on else 'yok'}."
            )
            yield {
                "id": f"me_muf_{mufredat_yili}_d{donem}_r{ri}_{kod.replace(' ','')}",
                "text": text,
                "metadata": {
                    "bolum": "makine",
                    "tip": "mufredat",
                    "mufredat_yili": mufredat_yili,
                    "donem": donem,
                    "yil": yil,
                    "sezon": sezon,
                    "ders_kodu": kod,
                    "ders_adi": ad,
                    "on_sart": on,
                    "teorik": t,
                    "lab": l,
                    "kredi": k,
                    "akts": a,
                    "kaynak": path.name,
                },
            }

            short = (
                f"- {kod} | {ad} | T:{t or '—'}, L:{l or '—'}, "
                f"Kredi:{k or '—'}, AKTS:{a or '—'} | Ön şart: {on or 'yok'}"
            )
            semester_courses.setdefault(donem, []).append(short)
            semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    # Dönem özet chunk'ları
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"Makine Mühendisliği {mufredat_yili} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — Toplam {len(lines)} ders:\n"
            + "\n".join(lines)
        )
        yield {
            "id": f"me_muf_{mufredat_yili}_sem_summary_d{donem}",
            "text": body,
            "metadata": {
                "bolum": "makine",
                "tip": "donem_ozet",
                "mufredat_yili": mufredat_yili,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": path.name,
            },
        }

def main():
    all_chunks = []
    
    # 1. Internship Handbook (PDF)
    hb_path = RAW_ME / "Internship_Handbook.pdf"
    if hb_path.exists():
        all_chunks.extend(list(parse_pdf_text(hb_path, "staj_el_kitabi", "en")))
        
    # 2. Internship Flow Chart (PDF)
    fc_path = RAW_ME / "Student Internship Application Flow Chart.pdf"
    if fc_path.exists():
        all_chunks.extend(list(parse_pdf_text(fc_path, "staj_akis_semasi", "en")))
        
    # 3. Catalog (PDF)
    cat_path = RAW_ME / "catalog_all course_TR.pdf"
    if cat_path.exists():
        all_chunks.extend(list(parse_pdf_text(cat_path, "program_katalogu", "tr")))
        
    # 4. Technical and Non-technical electives (DOCX)
    tech_path = RAW_ME / "technical_and_non_technical_09_2022.docx"
    if tech_path.exists():
        all_chunks.extend(list(parse_docx_text(tech_path)))

    # 5. Excel from Google Sheets (Müfredat by Year)
    for xls_path in RAW_ME.glob("Makine_Mufredat_*.xlsx"):
        year_match = re.search(r'Makine_Mufredat_(\d{4})\.xlsx', xls_path.name)
        if year_match:
            yili = year_match.group(1)
            all_chunks.extend(list(parse_excel_mufredat(xls_path, yili)))

    # Not: 2021_oncesi.pdf ve 2025_oncesi.pdf taranmış resim (scanned image) oldukları için 
    # standart text extraction (pdfplumber) ile okunamamaktadır. OCR gereklidir.

    out_path = OUT / "me_chunks.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] Makine Mühendisliği: Toplam {len(all_chunks)} chunk -> {out_path}")

if __name__ == "__main__":
    main()

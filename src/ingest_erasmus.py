"""
AGÜ — Erasmus+ KA131 El Kitabı 2025 ingest.
Bolum: 'ortak' — tüm bölümler için paylaşımlı.
Çıktı: data/processed/chunks_erasmus.jsonl
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

PDF = RAW / "Erasmus_Uygulama_El_Kitabi_2025.pdf"
BOLUM = "ortak"

# Roma rakamı + nokta + boşluk + büyük harfli başlık (örn. "III. ÖĞRENCİ HAREKETLİLİĞİ")
SECTION_RE = re.compile(r"^([IVXLCDM]+)\.\s+([A-ZÇĞİÖŞÜ][^\n]{4,90})$", re.MULTILINE)
# Numaralı alt başlık ("1. Öğrenci Hareketliliği Faaliyetleri")
SUBSECTION_RE = re.compile(r"^(\d+)\.\s+([A-ZÇĞİÖŞÜa-zçğıöşü][^\n]{4,90})$", re.MULTILINE)

# Hedef chunk boyutu (karakter) — yaklaşık 400-600 token
CHUNK_TARGET = 1800
CHUNK_OVERLAP = 200


def split_into_chunks(text: str, target: int = CHUNK_TARGET, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window: kelime ortasında kesmemek için boşluğa snap'ler."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) <= target:
        return [text] if text else []
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + target, n)
        if end < n:
            last_break = max(text.rfind("\n", i + target - 300, end),
                             text.rfind(". ", i + target - 300, end),
                             text.rfind(" ", i + target - 100, end))
            if last_break > i:
                end = last_break
        chunks.append(text[i:end].strip())
        if end >= n:
            break
        i = max(end - overlap, i + 1)
    return [c for c in chunks if c]


def parse_pdf() -> list[dict]:
    if not PDF.exists():
        print(f"[!] bulunamadı: {PDF}")
        return []
    with pdfplumber.open(PDF) as pdf:
        full = "\n".join((p.extract_text() or "") for p in pdf.pages)

    # Section başlıklarına göre bölmeyi dene
    sections: list[tuple[str, str, str]] = []  # (section_no, baslik, body)
    matches = list(SECTION_RE.finditer(full))
    if matches:
        for i, m in enumerate(matches):
            sec_no = m.group(1)
            baslik = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
            body = full[start:end].strip()
            sections.append((sec_no, baslik, body))
    else:
        sections = [("", "Tüm İçerik", full)]

    chunks: list[dict] = []
    for sec_no, baslik, body in sections:
        # Section başlığını chunk'lara dahil et
        prefix = f"Erasmus+ KA131 El Kitabı (2025) — Bölüm {sec_no} {baslik}".strip()
        for ci, body_chunk in enumerate(split_into_chunks(body), start=1):
            text = f"{prefix}:\n{body_chunk}"
            chunks.append({
                "id": f"erasmus_{sec_no or 'X'}_{ci:02d}",
                "text": text,
                "metadata": {
                    "tip": "erasmus",
                    "kategori": "el_kitabi_2025",
                    "section": sec_no,
                    "baslik": baslik[:100],
                    "kaynak": PDF.name,
                    "bolum": BOLUM,
                },
            })
    return chunks


def make_overview_chunk() -> dict:
    text = (
        "Erasmus+ KA131 — AGÜ ve diğer yükseköğretim kurumları için 2025 sözleşme dönemi "
        "Bireylerin Öğrenme Hareketliliği el kitabı özeti.\n\n"
        "İÇERİK BAŞLIKLARI:\n"
        "- Öğrenci hareketliliği: Öğrenim (Study Mobility - SMS) ve Staj (Student Mobility for Traineeship - SMT)\n"
        "- Personel hareketliliği: Ders verme (STA) ve Eğitim alma (STT)\n"
        "- Programla ilişkili ülkeler ve ilişkili olmayan üçüncü ülkeler\n"
        "- Kurumlararası anlaşmalar (EWP Dashboard üzerinden çevrimiçi)\n"
        "- Karma hareketlilik (Blended) — fiziksel + sanal bileşen\n"
        "- Karma yoğun programlar (Blended Intensive Programmes - BIP)\n"
        "- Doktora hareketliliği — kısa veya uzun dönem fiziksel/karma\n"
        "- Yeni mezunlar (post-doc) — mezuniyetten 12 ay içinde staj hareketliliği\n"
        "- Hibe miktarları, ek hibeler (yeşil yolculuk, dezavantajlı katılımcı vb.)\n"
        "- Seçim Komisyonu, tarafsızlık/şeffaflık ilkesi, çıkar çatışması\n"
        "- ECHE (Erasmus Charter for Higher Education) yükümlülükleri\n"
        "- Hibe sözleşmesi ve Avrupa Komisyonu belgeleri\n\n"
        "Bu el kitabı tüm AGÜ öğrencileri ve personeli için geçerlidir; "
        "her bölüme açıktır."
    )
    return {
        "id": "erasmus_overview",
        "text": text,
        "metadata": {
            "tip": "erasmus_genel",
            "kaynak": PDF.name,
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_pdf()
    chunks.append(make_overview_chunk())
    out_path = OUT / "chunks_erasmus.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"[OK] {len(chunks)} erasmus chunk -> {out_path}")


if __name__ == "__main__":
    main()

"""
AGÜ Biyomühendislik Bölümü Staj Genel Esasları (2025) ingest.
Kaynak: data/raw/AGU_Biyomuhendislik_Staj_Esaslari_2025.docx
  (Yaşam ve Doğa Bilimleri Fakültesi, MADDE bazlı resmi yönerge, 18 madde)

Çıktı: data/processed/chunks_biyomuhendislik_staj.jsonl
bolum = "biyomuhendislik"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

DOCX_PATH = RAW / "AGU_Biyomuhendislik_Staj_Esaslari_2025.docx"
BOLUM = "biyomuhendislik"
BOLUM_ADI = "Biyomühendislik"
KAYNAK = DOCX_PATH.name

# "MADDE 12 −/–/-/—" (en/em-dash, eksi işareti U+2212 dahil)
MADDE_RE = re.compile(r"MADDE\s+(\d+)\s*[−–\-—−]")


def _read_docx_text() -> str:
    doc = Document(DOCX_PATH)
    return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def parse_maddeler(full: str) -> list[dict]:
    matches = list(MADDE_RE.finditer(full))
    if not matches:
        return []
    chunks: list[dict] = []
    for i, m in enumerate(matches):
        no = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        block = full[start:end].strip()
        # Başlık: bir önceki satırdaki konu adı (ör. "Staj Yarıyılları ve Süresi")
        before = full[max(0, start - 200):start].strip().split("\n")
        baslik = (before[-1].strip() if before else "")[:100]
        body = re.sub(r"\s+", " ", block).strip()[:3500]

        text = (
            f"AGÜ {BOLUM_ADI} Bölümü Staj Genel Esasları — MADDE {no}"
            + (f" ({baslik})" if baslik and len(baslik) < 80 else "")
            + f":\n{body}"
        )
        chunks.append({
            "id": f"biyo_staj_madde_{no}",
            "text": text,
            "metadata": {
                "bolum": BOLUM,
                "tip": "staj_yonerge",
                "madde_no": int(no),
                "baslik": baslik,
                "kaynak": KAYNAK,
            },
        })
    return chunks


def make_overview() -> dict:
    text = (
        "AGÜ Biyomühendislik Bölümü Staj Programı — Genel Özet:\n\n"
        "Abdullah Gül Üniversitesi Yaşam ve Doğa Bilimleri Fakültesi Biyomühendislik Bölümü "
        "öğrencileri için staj, müfredattaki BENG 493 Yaz Stajı kapsamında zorunludur.\n\n"
        "TEMEL BİLGİLER:\n"
        "- Staj süresi: en az 30 iş günü, sürekli (fiilen çalışılan gün sayısı esas alınır)\n"
        "- Ön koşul: en erken 5. dönemi tamamlamış olmak VEYA en az 150 AKTS tamamlamış olmak\n"
        "- Zaman: genel olarak yaz döneminde; uygun görülürse eğitim-öğretim yılı içinde de yapılabilir\n"
        "- Sigorta: zorunlu (resmi) staj için sigorta giderleri üniversite tarafından karşılanır\n"
        "- Başvuru: Staj Başvuru Formu + gerekli belgeler, dönem bitiminden ~2 ay önce Bölüm/Fakülte "
        "Sekreterliğine teslim edilmeli (geç teslimde sigorta yapılamaz, staj geçersiz)\n\n"
        "DEĞERLENDİRME:\n"
        "- Staj raporu + iş yeri değerlendirme formu, staj sonrası dönemin ilk 2 haftasında staj danışmanına teslim\n"
        "- Not dağılımı: Final raporu %30 + Final sunumu %30 + Değerlendirme formu %40\n"
        "- Başarı için toplam puan en az 70/100 olmalı; başarısız öğrenci stajı FARKLI bir iş yerinde tekrarlar\n\n"
        "KURUMSAL YAPI:\n"
        "- Bölüm Staj Komisyonu (BSK): en az 3 öğretim elemanı, 2 yıllık görev — stajları yürütür\n"
        "- Staj Danışmanı: BSK Başkanı tarafından görevlendirilir, raporu değerlendirir\n\n"
        "Soru: 'Biyomühendislik stajı kaç gün?' → en az 30 iş günü. "
        "'Staj için kaç AKTS lazım?' → en az 150 AKTS veya 5. dönem tamamlanmış olmalı. "
        "'Staj nasıl değerlendirilir?' → rapor %30 + sunum %30 + form %40, geçme notu 70/100."
    )
    return {
        "id": "biyo_staj_overview",
        "text": text,
        "metadata": {
            "bolum": BOLUM,
            "tip": "staj_yonerge",
            "kategori": "genel_ozet",
            "kaynak": KAYNAK,
        },
    }


def main():
    full = _read_docx_text()
    chunks: list[dict] = [make_overview()]
    madde_chunks = parse_maddeler(full)
    chunks.extend(madde_chunks)

    out_path = OUT / "chunks_biyomuhendislik_staj.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} biyomühendislik staj chunk -> {out_path}")
    print(f"     - MADDE chunk: {len(madde_chunks)}")
    print(f"     - özet: 1")


if __name__ == "__main__":
    main()

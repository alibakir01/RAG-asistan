"""
AGÜ Moleküler Biyoloji ve Genetik (MBG) Bölümü Staj Genel Esasları (2023) ingest.
Kaynak: data/raw/AGU_MBG_Staj_Yonergesi_2023.pdf
  (Yaşam ve Doğa Bilimleri Fakültesi, MADDE bazlı resmi yönerge)

NOT: PDF'te font kodlama hatası var — dotted 'i' harfi '/' olarak çıkıyor
(ör. "Ün/vers/te" = "Üniversite"). _fix_encoding bunu düzeltir. Dotless 'ı' korunur.

Çıktı: data/processed/chunks_mbg_staj.jsonl
bolum = "mbg"
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

PDF_PATH = RAW / "AGU_MBG_Staj_Yonergesi_2023.pdf"
BOLUM = "mbg"
BOLUM_ADI = "Moleküler Biyoloji ve Genetik"
KAYNAK = PDF_PATH.name

# "MADDE 12 −/–/-/—" (en/em-dash, eksi işareti U+2212 dahil)
MADDE_RE = re.compile(r"MADDE\s+(\d+)\s*[−–\-—]")


def _fix_encoding(s: str) -> str:
    """PDF font subset hatasını düzelt: dotted 'i' glyph'i hem '/' hem 'X'
    olarak çıkıyor (ör. "Ün/vers/te"=Üniversite, "KomXsyonu"=Komisyonu).
    Bu belgede gerçek '/' (rakam/rakam hariç) ve gerçek 'X' yok.
    Dotless 'ı' korunur."""
    s = re.sub(r"(?<!\d)/(?!\d)", "i", s)  # / -> i (rakam/rakam hariç)
    s = s.replace("X", "i")                 # X -> i (bu belgede hepsi i)
    return s


def _read_pdf() -> str:
    if not PDF_PATH.exists():
        print(f"[!] bulunamadı: {PDF_PATH}")
        return ""
    with pdfplumber.open(PDF_PATH) as pdf:
        raw = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    return _fix_encoding(raw)


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
        before = full[max(0, start - 200):start].strip().split("\n")
        baslik = (before[-1].strip() if before else "")[:100]
        body = re.sub(r"\s+", " ", block).strip()[:3500]

        text = (
            f"AGÜ {BOLUM_ADI} Bölümü Staj Genel Esasları — MADDE {no}"
            + (f" ({baslik})" if baslik and len(baslik) < 80 else "")
            + f":\n{body}"
        )
        chunks.append({
            "id": f"mbg_staj_madde_{no}",
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


def make_overview(full: str) -> dict:
    # Staj süresi ve geçme notu gibi kritik bilgileri metinden çek
    sure_m = re.search(r"en az\s+(\d+)\s+iş günü", full)
    sure = sure_m.group(1) if sure_m else "20"
    akts_m = re.search(r"en az\s+(\d+)\s+AKTS", full)
    akts = akts_m.group(1) if akts_m else None

    text = (
        "AGÜ Moleküler Biyoloji ve Genetik (MBG) Bölümü Staj Programı — Genel Özet:\n\n"
        "Abdullah Gül Üniversitesi Yaşam ve Doğa Bilimleri Fakültesi Moleküler Biyoloji ve "
        "Genetik Bölümü öğrencileri için staj, müfredattaki MBG 499 Yaz Stajı kapsamında zorunludur.\n\n"
        "TEMEL BİLGİLER:\n"
        f"- Staj süresi: en az {sure} iş günü, sürekli (fiilen çalışılan gün sayısı esas alınır)\n"
        + (f"- Ön koşul: en az {akts} AKTS tamamlamış olmak\n" if akts else "")
        + "- Zaman: genel olarak yaz döneminde; uygun görülürse eğitim-öğretim yılı içinde de yapılabilir\n"
        "- Sigorta: zorunlu (resmi) staj için sigorta giderleri üniversite tarafından karşılanır\n"
        "- Başvuru: Staj Başvuru Formu + gerekli belgeler, ilan edilen tarih aralığında Bölüm Staj "
        "Komisyonuna teslim edilmeli (geç teslimde sigorta yapılamaz, staj geçersiz)\n\n"
        "KURUMSAL YAPI:\n"
        "- Bölüm Staj Komisyonu (BSK): bölüm başkanı tarafından öğretim üyeleri arasından 2 yıl için "
        "görevlendirilen en az 3 öğretim elemanından oluşur — stajları yürütür\n"
        "- Staj Danışmanı: BSK Başkanı tarafından görevlendirilir, staj raporunu değerlendirir\n\n"
        "DEĞERLENDİRME:\n"
        "- Staj raporu + iş yeri değerlendirme formu, stajın tamamlanmasını takip eden dönemin ilk 2 "
        "haftasında staj danışmanına teslim edilir (geç teslimde staj başarısız sayılır)\n"
        "- Staj sonunda öğrenci sunum yapar; değerlendirme sonucunda staj Başarılı/Başarısız ilan edilir\n"
        "- Başarısız öğrenci stajı FARKLI bir iş yerinde tekrarlar\n\n"
        "Soru: 'MBG stajı kaç gün?' → en az "
        f"{sure} iş günü. 'Staj zorunlu mu?' → Evet (MBG 499 Yaz Stajı). "
        "'Staj nereye başvurulur?' → Bölüm Staj Komisyonuna."
    )
    return {
        "id": "mbg_staj_overview",
        "text": text,
        "metadata": {
            "bolum": BOLUM,
            "tip": "staj_yonerge",
            "kategori": "genel_ozet",
            "kaynak": KAYNAK,
        },
    }


def main():
    full = _read_pdf()
    if not full:
        return
    chunks: list[dict] = [make_overview(full)]
    madde_chunks = parse_maddeler(full)
    chunks.extend(madde_chunks)

    out_path = OUT / "chunks_mbg_staj.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} MBG staj chunk -> {out_path}")
    print(f"     - MADDE chunk: {len(madde_chunks)}")
    print(f"     - özet: 1")
    mn = [c['metadata'].get('madde_no') for c in madde_chunks]
    print(f"     - madde no listesi: {sorted(mn)}")


if __name__ == "__main__":
    main()

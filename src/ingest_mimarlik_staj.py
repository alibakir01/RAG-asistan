"""
AGÜ Mimarlık Bölümü Staj Programı Yönergesi ingest.
Kaynak: AGU_Mimarlik_Staj_Yonergesi.pdf (7 sayfa)
Yapı: numaralı başlıklı bölümler (1. Genel Bilgiler, 2. Zaman Planlaması, 3. Önkoşullar,
4. Staj Dersleri ve Açıklamaları, 5. Roller ve Sorumluluklar, 6. Staj Süreci ve Prosedürleri, ...)

Bölüm 4 içinde her staj dersi (ARCH 250, ARCH 350, ARCD 451, ARCD 452, ARCD X5X) için
ayrıca tek tek chunk üretilir.

Çıktı: data/processed/chunks_mimarlik_staj.jsonl
bolum = "mimarlik"
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

PDF = RAW / "AGU_Mimarlik_Staj_Yonergesi.pdf"
BOLUM = "mimarlik"
BOLUM_ADI = "Mimarlık"

# "1. Bölüm Adı", "2. Bölüm Adı" gibi numaralı başlıkları yakala — satır başında olmalı
SECTION_RE = re.compile(
    r"^(\d+)\.\s+([A-ZÇĞİÖŞÜa-zçğıöşü][^\n]{4,100})$",
    re.MULTILINE,
)

# Bölüm 4'teki ders kartları (Zorunlu/Seçmeli ders adları)
# Örnek: "ARCH 250 Professional Practice on Site (2 AKTS)"
DERS_CARD_RE = re.compile(
    r"^(ARC[HD])\s*(\d+|X5X)\s+([^\n(]+?)(?:\s*\((\d+)\s*AKTS?\))?\s*$",
    re.MULTILINE,
)


def _read_pdf() -> str:
    if not PDF.exists():
        return ""
    try:
        with pdfplumber.open(PDF) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı: {e}")
        return ""


def parse_sections(full: str) -> list[tuple[str, str, str]]:
    """Numaralı başlıklarla full text'i bölümlere ayır.
    Döner: [(no, baslik, body), ...]"""
    matches = list(SECTION_RE.finditer(full))
    if not matches:
        return [("0", "Tüm İçerik", full)]
    sections = []
    for i, m in enumerate(matches):
        no = m.group(1)
        baslik = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        body = full[start:end].strip()
        sections.append((no, baslik, body))
    return sections


def parse_ders_kartlari(bolum4_body: str) -> list[dict]:
    """Bölüm 4 (Staj Dersleri ve Açıklamaları) içinden her dersin ayrı chunk'ını
    çıkar. Ders adından sonraki paragraf(lar) o derse aittir, bir sonraki ders
    başlığına kadar."""
    cards: list[dict] = []
    matches = list(DERS_CARD_RE.finditer(bolum4_body))
    if not matches:
        return cards

    for i, m in enumerate(matches):
        prefix = m.group(1).strip().upper()  # ARCH veya ARCD
        num = m.group(2).strip()
        ad = m.group(3).strip()
        akts = m.group(4) or ""

        kod = f"{prefix} {num}"
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(bolum4_body)
        aciklama = bolum4_body[start:end].strip()

        cards.append({
            "kod": kod,
            "ad": ad,
            "akts": akts,
            "aciklama": aciklama,
        })
    return cards


def main():
    full = _read_pdf()
    if not full:
        print("[!] PDF okunamadı.")
        return

    chunks: list[dict] = []

    # 1) Genel özet chunk (ilk sayfa içeriği — programın amacı)
    chunks.append({
        "id": "mimarlik_staj_overview",
        "text": (
            f"AGÜ Mimarlık Bölümü Staj Programı Yönergesi — Genel Özet:\n\n"
            "AGÜ Mimarlık Bölümü staj programı, 'tasarım yoluyla araştırma' tabanlı "
            "eğitim programının bir parçasıdır ve öğrencilerin tasarım/araştırma "
            "yetkinliklerini geliştirmek için profesyonel hayatla dinamik etkileşim sağlar.\n\n"
            "ZORUNLU STAJLAR:\n"
            "- ARCH 250 Professional Practice on Site (Şantiye Stajı) — 2. yıl yaz dönemi, en az 30 işgünü\n"
            "- ARCH 350 Professional Practice in Architectural Offices (Mimari Büro Stajı) — 3. yıl yaz dönemi, en az 30 işgünü\n"
            "TOPLAM: en az 60 işgünü zorunlu staj.\n\n"
            "SEÇMELİ STAJLAR (zorunlu staj yerine geçmez):\n"
            "- ARCD 451 Practice in Architectural Offices — 4. yıl güz/bahar, dönem boyunca\n"
            "- ARCD 452 Practice on Site — 4. yıl güz/bahar, dönem boyunca\n"
            "- ARCD X5X Practice in Research Activities — 3./4. yıl güz/bahar/yaz, dönem boyunca\n\n"
            "Önkoşullar:\n"
            "- ARCH 250: ARCH 122 ve ARCH 221\n"
            "- ARCH 350: ARCH 250 ve ARCH 301\n"
            "- ARCD 451 / 452: ARCH 250 + ARCH 350 + min. 2.5 GANO\n"
            "- ARCD X5X: min. 2.5 GANO"
        ),
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "genel_ozet",
            "kaynak": PDF.name,
            "bolum": BOLUM,
        },
    })

    # 2) Numaralı bölümleri chunk'la
    sections = parse_sections(full)
    for no, baslik, body in sections:
        if not body.strip():
            continue
        # Çok uzun bölümleri kırp (4000 char civarı)
        body_clean = re.sub(r"\s+", " ", body).strip()
        text = (
            f"AGÜ Mimarlık Staj Yönergesi — Bölüm {no}: {baslik}\n\n{body_clean}"
        )
        chunks.append({
            "id": f"mimarlik_staj_b{no}",
            "text": text[:4000],
            "metadata": {
                "tip": "staj_yonerge",
                "bolum_no": _safe_int(no),
                "baslik": baslik[:100],
                "kaynak": PDF.name,
                "bolum": BOLUM,
            },
        })

        # 3) Bölüm 4 içindeki her staj dersi için ayrı detay chunk
        if no == "4":
            cards = parse_ders_kartlari(body)
            for c in cards:
                t = (
                    f"AGÜ Mimarlık Staj Dersi — {c['kod']} {c['ad']}"
                    + (f" ({c['akts']} AKTS)" if c['akts'] else "")
                    + ":\n\n" + re.sub(r"\s+", " ", c["aciklama"]).strip()
                )
                chunks.append({
                    "id": f"mimarlik_staj_ders_{c['kod'].replace(' ', '')}",
                    "text": t[:3500],
                    "metadata": {
                        "tip": "staj_dersi",
                        "ders_kodu": c["kod"],
                        "ders_adi": c["ad"],
                        "akts": c["akts"],
                        "kaynak": PDF.name,
                        "bolum": BOLUM,
                    },
                })

    out_path = OUT / "chunks_mimarlik_staj.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} mimarlık staj chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


def _safe_int(v) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


if __name__ == "__main__":
    main()

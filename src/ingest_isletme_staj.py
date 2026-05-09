"""
AGÜ İşletme Bölümü Staj kaynaklarını ingest eder:
  - AGU_Isletme_Staj_Yonergesi.pdf (7 sayfa, MADDE bazlı resmi yönerge)
  - AGU_Isletme_BA499_Staj.pdf (5 sayfa, BA499 ders outline formatı)

Çıktı: data/processed/chunks_isletme_staj.jsonl
bolum = "isletme"
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

YONERGE_PDF = RAW / "AGU_Isletme_Staj_Yonergesi.pdf"
BA499_PDF = RAW / "AGU_Isletme_BA499_Staj.pdf"
BOLUM = "isletme"

# "MADDE 12 −", "MADDE 12 –", "MADDE 12 -" formatlarını yakala (en/em-dash dahil)
MADDE_RE = re.compile(r"MADDE\s+(\d+)\s*[−–\-—]")


def _read_pdf(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return ""


# ----------------- 1) YÖNERGE — MADDE bazlı parse -----------------

def parse_yonerge() -> list[dict]:
    full = _read_pdf(YONERGE_PDF)
    if not full:
        return []
    matches = list(MADDE_RE.finditer(full))
    if not matches:
        return []

    chunks: list[dict] = []
    for i, m in enumerate(matches):
        no = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        block = full[start:end].strip()
        # Başlık: bir önceki satırdaki konu adı (ör. "Stajın amacı")
        before = full[max(0, start - 200):start].strip().split("\n")
        baslik = (before[-1].strip() if before else "")[:100]
        body = re.sub(r"\s+", " ", block).strip()[:3500]

        text = (
            f"AGÜ İşletme Bölümü Staj Yönergesi — MADDE {no}"
            + (f" ({baslik})" if baslik and len(baslik) < 80 else "")
            + f":\n{body}"
        )
        chunks.append({
            "id": f"isletme_staj_madde_{no}",
            "text": text,
            "metadata": {
                "tip": "staj_yonerge",
                "madde_no": int(no),
                "baslik": baslik,
                "kaynak": YONERGE_PDF.name,
                "bolum": BOLUM,
            },
        })
    return chunks


# ----------------- 2) BA499 ders outline'ı -----------------

def parse_ba499() -> list[dict]:
    full = _read_pdf(BA499_PDF)
    if not full:
        return []

    # Tek bir kapsamlı chunk + içerik bazlı 2-3 chunk
    full_clean = re.sub(r"\s+", " ", full).strip()

    chunks: list[dict] = []

    # Master chunk: BA499 tüm ders kartı
    chunks.append({
        "id": "isletme_staj_ba499_overview",
        "text": (
            "AGÜ İşletme Bölümü — BA499 Summer Internship (Yaz Stajı) Ders Bilgileri:\n\n"
            f"{full_clean[:3500]}"
        ),
        "metadata": {
            "tip": "staj_dersi",
            "ders_kodu": "BA 499",
            "ders_adi": "Summer Internship",
            "akts": "7",
            "kredi": "3",
            "kaynak": BA499_PDF.name,
            "bolum": BOLUM,
        },
    })

    # Daha uzunsa, 3500-7000 arası ek chunk
    if len(full_clean) > 3500:
        chunks.append({
            "id": "isletme_staj_ba499_detail",
            "text": (
                "AGÜ İşletme Bölümü — BA499 Summer Internship (Yaz Stajı) — Devam:\n\n"
                f"{full_clean[3300:6800]}"
            ),
            "metadata": {
                "tip": "staj_dersi",
                "ders_kodu": "BA 499",
                "ders_adi": "Summer Internship",
                "kaynak": BA499_PDF.name,
                "bolum": BOLUM,
            },
        })

    # Yapılandırılmış özet — kritik bilgileri kolay erişim için
    chunks.append({
        "id": "isletme_staj_ba499_summary",
        "text": (
            "AGÜ İşletme Bölümü — BA499 Summer Internship özet bilgileri:\n\n"
            "- Ders Kodu: BA 499\n"
            "- Ders Adı: Summer Internship (Yaz Stajı)\n"
            "- Tip: Compulsory (Zorunlu)\n"
            "- Kredi: 3\n"
            "- AKTS (ECTS): 7\n"
            "- Haftalık saat: 8\n"
            "- Seviye: Undergraduate (Lisans)\n"
            "- Dönem: All Semester (her dönem alınabilir)\n"
            "- Ön şart: En az 150 ECTS kredisini başarıyla tamamlamış olmak\n"
            "- Öğretim Üyesi: Harika Süklün (harika.suklun@agu.edu.tr)\n"
            "- Platform: CANVAS Course Website\n\n"
            "Amaç: Öğrencinin İşletme alanına uygun bir kuruluşta gerçek iş ortamını "
            "deneyimleyerek teorik bilgileri uygulamaya geçirmesi, mesleki beceri ve "
            "deneyim kazanması.\n\n"
            "Öğrenme Çıktıları: Teorik bilgiyi gerçek iş problemlerine uygulama, mesleki "
            "becerileri geliştirme, iş ortamı dinamiklerini gözlemleme, faaliyet raporu "
            "yazma, takım çalışması ve liderlik deneyimi kazanma."
        ),
        "metadata": {
            "tip": "staj_dersi",
            "ders_kodu": "BA 499",
            "ders_adi": "Summer Internship",
            "akts": "7",
            "kredi": "3",
            "kaynak": BA499_PDF.name,
            "bolum": BOLUM,
        },
    })

    return chunks


# ----------------- 3) Sorumlu Kişi chunk (kim sorularına direkt cevap) -----------------

def make_sorumlu_kisi_chunk() -> dict:
    text = (
        "AGÜ İşletme Bölümü Staj Sorumlusu / Staj Danışmanı / Staj Koordinatörü:\n\n"
        "**Dr. Harika Süklün**\n"
        "📧 İletişim: harika.suklun@agu.edu.tr\n\n"
        "Dr. Harika Süklün, İşletme Bölümü'nde staj programının yürütücüsüdür ve "
        "BA499 Summer Internship (Yaz Stajı) dersinin öğretim üyesidir. "
        "Öğrenciler staj başvurusu, staj süreci, staj raporu ve değerlendirme gibi "
        "konularda Dr. Süklün ile iletişime geçer.\n\n"
        "Soru: 'İşletme staj sorumlusu kim?' / 'BA499 hocası kim?' / 'Staj danışmanı kimdir?' "
        "/ 'Staj için kime ulaşmalıyım?' → Cevap: Dr. Harika Süklün (harika.suklun@agu.edu.tr).\n\n"
        "Ayrıca İşletme Bölümü Staj Komisyonu da staj başvurularını değerlendirir; "
        "Komisyon Başkanı Staj Danışmanı'nı görevlendirir."
    )
    return {
        "id": "isletme_staj_sorumlu_kisi",
        "text": text,
        "metadata": {
            "tip": "staj_sorumlu",
            "kategori": "iletisim",
            "isim": "Harika Süklün",
            "email": "harika.suklun@agu.edu.tr",
            "ders_kodu": "BA 499",
            "kaynak": "AGU_Isletme_Staj_Sorumlu_Kisi",
            "bolum": BOLUM,
        },
    }


# ----------------- 4) Genel özet chunk -----------------

def make_overview() -> dict:
    text = (
        "AGÜ İşletme Bölümü Staj Programı — Genel Özet:\n\n"
        "Abdullah Gül Üniversitesi Yönetim Bilimleri Fakültesi İşletme Bölümü öğrencileri için "
        "stajlar, **BA499 Summer Internship (Yaz Stajı)** dersi kapsamında düzenlenir. "
        "Bu ders zorunludur (Compulsory).\n\n"
        "TEMEL BİLGİLER:\n"
        "- Ders kodu: BA 499\n"
        "- AKTS (ECTS): 7, Kredi: 3, Haftalık saat: 8\n"
        "- Ön şart: En az 150 ECTS kredisi başarıyla tamamlanmış olmalı\n"
        "- Dönem: 'All Semester' — her dönem alınabilir\n"
        "- Öğretim üyesi: Harika Süklün\n\n"
        "KURUMSAL YAPI:\n"
        "- **Fakülte Staj Komisyonu (FSK):** Tüm bölümlerin staj uygulamalarının "
        "koordinasyonundan sorumlu, Dekan Yardımcısı başkanlığında çalışır.\n"
        "- **Bölüm Staj Komisyonu:** İşletme Bölümü öğrencileri için staj başvurularını "
        "değerlendirir.\n"
        "- **Staj Danışmanı:** İşletme Bölümü öğretim üyesi.\n"
        "- **İş yeri:** Kamu/özel kurum, kuruluş, şahıs işletmeleri.\n\n"
        "AMAÇ:\n"
        "Lisans programındaki teorik bilgileri uygulamada görmek, gerçek iş ortamında "
        "mesleki beceri ve deneyim kazanmak.\n\n"
        "Detaylı kurallar için yönerge MADDE'lerine bakılır."
    )
    return {
        "id": "isletme_staj_overview",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "genel_ozet",
            "kaynak": "AGU_Isletme_Staj_Ozeti",
            "bolum": BOLUM,
        },
    }


def main():
    chunks: list[dict] = []
    chunks.append(make_overview())
    chunks.append(make_sorumlu_kisi_chunk())

    yonerge_chs = parse_yonerge()
    chunks.extend(yonerge_chs)
    print(f"[Yönerge] {len(yonerge_chs)} MADDE chunk")

    ba499_chs = parse_ba499()
    chunks.extend(ba499_chs)
    print(f"[BA499 ders outline] {len(ba499_chs)} chunk")

    out_path = OUT / "chunks_isletme_staj.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"\n[OK] Toplam {len(chunks)} işletme staj chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

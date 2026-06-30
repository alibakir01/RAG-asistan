"""
AGÜ Moleküler Biyoloji ve Genetik (MBG) bölümü ingest.
Kaynaklar:
  - data/raw/AGU_MBG_Ders_Katalogu.pdf   (93 sayfa, 46 ders — çift dilli detaylı kayıt)
  - data/raw/AGU_MBG_Program_Bilgileri.pdf (Bologna program bilgileri — müfredat, çıktılar)

Çıktı: data/processed/chunks_mbg.jsonl
bolum = "mbg" | mufredat_yili = "2021"

NOT: MBG, Biyomühendislik (BENG) bölümünden AYRI bir bölümdür. Yaşam ve Doğa
Bilimleri Fakültesi altındadır. Ders kodları MBG prefixlidir.
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

CATALOG_PDF = RAW / "AGU_MBG_Ders_Katalogu.pdf"
PROGRAM_PDF = RAW / "AGU_MBG_Program_Bilgileri.pdf"
BOLUM = "mbg"
BOLUM_ADI = "Moleküler Biyoloji ve Genetik"
MUFREDAT = "2021"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def _ders_id(kod: str) -> str:
    return kod.replace(" ", "").upper()


# ---------------------------------------------------------------------------
# 1) KATALOG — her ders için detaylı chunk (kod, ad, AKTS, ön şart, içerik)
# ---------------------------------------------------------------------------

# İngilizce alan etiketleri arasındaki metni yakalayan yardımcı regexler
_FIELD_RE = {
    "name": re.compile(r"Name\s+(.+?)\s+Hour per week", re.DOTALL),
    "hour": re.compile(r"Hour per week\s+(.+?)\s+Credit", re.DOTALL),
    "credit": re.compile(r"Credit\s+(\d+)"),
    "ects": re.compile(r"ECTS\s+(\d+)"),
    "level": re.compile(r"Level/Year\s+(.+?)\s+Semester", re.DOTALL),
    "semester": re.compile(r"Semester\s+(Fall|Spring|Güz|Bahar|All)"),
    "type": re.compile(r"Type\s+(Compulsory|Elective|Zorunlu|Seçmeli)"),
    "prereq": re.compile(r"Prerequisites\s*(.*?)\s+Description", re.DOTALL),
    "desc": re.compile(r"Description\s+(.+?)\s+Objectives", re.DOTALL),
}
# Türkçe içerik (DERS BİLGİLERİ bölümünden) — varsa
_ICERIK_RE = re.compile(r"İçerik\s+(.+?)(?:\n\d+\s*\n|Bu belge 5070|Amaç|Öğrenme Çıktıları|$)", re.DOTALL)

SEMESTER_TR = {"Fall": "Güz", "Spring": "Bahar", "All": "Her dönem"}


def parse_catalog() -> list[dict]:
    if not CATALOG_PDF.exists():
        print(f"[!] bulunamadı: {CATALOG_PDF}")
        return []
    with pdfplumber.open(CATALOG_PDF) as pdf:
        text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)

    # Her ders "Code <KOD>" ile başlar. Bloklara böl.
    code_iter = list(re.finditer(r"Code\s+(MBG\s*\d+[A-Z]?)", text))
    chunks: list[dict] = []
    seen: set[str] = set()

    for i, m in enumerate(code_iter):
        kod = _clean(m.group(1)).replace("MBG", "MBG ").replace("  ", " ").strip()
        kod = re.sub(r"MBG\s*", "MBG ", kod).strip()
        kod_norm = _ders_id(kod)
        if kod_norm in seen:
            continue
        seen.add(kod_norm)

        start = m.start()
        end = code_iter[i + 1].start() if i + 1 < len(code_iter) else len(text)
        blk = text[start:end]

        def g(key: str) -> str:
            mm = _FIELD_RE[key].search(blk)
            return _clean(mm.group(1)) if mm else ""

        name = g("name")
        hour = g("hour")
        credit = g("credit")
        ects = g("ects")
        level = g("level")
        sem_en = g("semester")
        sem = SEMESTER_TR.get(sem_en, sem_en)
        tip_en = g("type")
        tip = {"Compulsory": "Zorunlu", "Elective": "Seçmeli"}.get(tip_en, tip_en or "")
        prereq = g("prereq").strip() or "yok"
        desc = g("desc")

        icerik_m = _ICERIK_RE.search(blk)
        icerik_tr = _clean(icerik_m.group(1))[:1200] if icerik_m else ""

        text_parts = [
            f"AGÜ {BOLUM_ADI} bölümü ders kataloğu — {kod} {name}.",
            f"AKTS: {ects}." if ects else "",
            f"Kredi: {credit}." if credit else "",
            f"Haftalık saat: {hour}." if hour else "",
            f"Dönem: {sem}." if sem else "",
            f"Seviye: {level}." if level else "",
            f"Tip: {tip}." if tip else "",
            f"Ön şart: {prereq}.",
        ]
        if icerik_tr:
            text_parts.append(f"İçerik (TR): {icerik_tr}")
        if desc:
            text_parts.append(f"Açıklama (EN): {desc[:1500]}")

        chunk_text = " ".join(p for p in text_parts if p)[:4500]

        chunks.append({
            "id": f"mbg_katalog_{kod_norm}",
            "text": chunk_text,
            "metadata": {
                "bolum": BOLUM,
                "tip": "ders_icerik",
                "ders_kodu": kod,
                "ders_adi": name,
                "akts": ects,
                "kredi": credit,
                "donem_sezon": sem,
                "ders_tipi": tip,
                "on_sart": prereq,
                "mufredat_yili": MUFREDAT,
                "kaynak": CATALOG_PDF.name,
            },
        })
    return chunks


# ---------------------------------------------------------------------------
# 2) MÜFREDAT — 8 dönemlik ders programı (program PDF'inden, sabit veri)
# ---------------------------------------------------------------------------

# (dönem_no, yıl, sezon) -> [(kod, ad, akts, ön_şart)]
CURRICULUM: dict[tuple, list[tuple]] = {
    (1, 1, "Güz"): [
        ("MATH 181", "Yaşam Bilimleri için Matematik I", "6", "yok"),
        ("MBG 111", "Genel Biyoloji I", "7", "yok"),
        ("GLB 101", "AGU Ways (AGÜ Yöntemleri)", "4", "yok"),
        ("MBG 115", "Yaşam Bilimleri için Kimya I", "5", "yok"),
        ("BENG 105", "Programlamaya Giriş", "6", "yok"),
        ("ENG 101", "İngilizce I", "4", "yok"),
    ],
    (2, 1, "Bahar"): [
        ("MATH 182", "Yaşam Bilimleri için Matematik II", "6", "MATH 181"),
        ("MBG 112", "Genel Biyoloji II", "8", "yok"),
        ("GLB XXX", "Seçmeli Küresel Sorunlar I", "4", "yok"),
        ("ENG 102", "İngilizce II", "4", "yok"),
        ("MBG 116", "Yaşam Bilimleri için Kimya II", "5", "yok"),
        ("CP100.MBG", "Kariyer Planlaması", "1", "yok"),
    ],
    (3, 2, "Güz"): [
        ("MBG 205", "Hücre Biyolojisi", "7", "MBG 111"),
        ("MBG 207", "Organik Kimya", "5", "MBG 115 & MBG 116"),
        ("MBG 209", "Genetiğin Temelleri", "7", "yok"),
        ("GLB XXX", "Seçmeli Küresel Sorunlar II", "4", "yok"),
        ("PHYS 101", "Fizik I", "5", "yok"),
        ("TURK 101", "Türkçe I", "2", "yok"),
    ],
    (4, 2, "Bahar"): [
        ("MBG 204", "Biyoistatistik", "6", "yok"),
        ("MBG 206", "Mikrobiyoloji", "7", "MBG 112"),
        ("MBG 208", "Moleküler Biyoloji", "7", "MBG 111"),
        ("MBG 210", "Bilim ve Etik", "4", "yok"),
        ("GLB XXX", "Seçmeli Küresel Sorunlar III", "4", "yok"),
        ("TURK 102", "Türkçe II", "2", "yok"),
    ],
    (5, 3, "Güz"): [
        ("MBG 301", "Genel Biyokimya I", "8", "MBG 111"),
        ("GLB XXX", "Seçmeli Küresel Sorunlar IV", "4", "yok"),
        ("MBG 305", "Moleküler Biyolojide Özel Teknikler ve Uygulamalar", "6", "MBG 208"),
        ("MBG 309", "İnsan Genetiği", "5", "MBG 209"),
        ("HIST 201", "Modern Türkiye Tarihi I", "2", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
    ],
    (6, 3, "Bahar"): [
        ("MBG 312", "Genel Biyokimya II", "7", "MBG 301"),
        ("MBG 304", "Biyoinformatik", "6", "yok"),
        ("MBG 306", "Gen Regülasyonu", "7", "MBG 208"),
        ("HIST 202", "Modern Türkiye Tarihi II", "2", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("XXX", "Teknik Olmayan Seçmeli", "3", "yok"),
    ],
    (7, 4, "Güz"): [
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("OHS 401", "İş Sağlığı ve Güvenliği I", "1", "yok"),
        ("XXX", "Teknik Olmayan Seçmeli", "3", "yok"),
        ("MBG 499", "Yaz Stajı", "6", "yok"),
    ],
    (8, 4, "Bahar"): [
        ("MBG 404", "Moleküler Biyolojide Güncel Konular", "6", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("MBG XXX", "Teknik Seçmeli", "5", "yok"),
        ("XXX", "Teknik Olmayan Seçmeli", "3", "yok"),
        ("OHS 402", "İş Sağlığı ve Güvenliği II", "1", "yok"),
    ],
}


def make_curriculum_chunks() -> list[dict]:
    chunks: list[dict] = []
    for (donem, yil, sezon), dersler in CURRICULUM.items():
        lines = [
            f"- {kod} | {ad} | AKTS: {akts} | Ön şart: {on}"
            for (kod, ad, akts, on) in dersler
        ]
        toplam_akts = sum(int(d[2]) for d in dersler if d[2].isdigit())
        body = (
            f"AGÜ {BOLUM_ADI} ({MUFREDAT} müfredatı) — {yil}. yıl {sezon} dönemi "
            f"({donem}. dönem) dersleri (toplam ~{toplam_akts} AKTS):\n"
            + "\n".join(lines)
        )
        chunks.append({
            "id": f"mbg_mufredat_donem{donem}",
            "text": body,
            "metadata": {
                "bolum": BOLUM,
                "tip": "mufredat",
                "donem": donem,
                "yil": yil,
                "sezon": sezon,
                "mufredat_yili": MUFREDAT,
                "kaynak": PROGRAM_PDF.name,
            },
        })
    return chunks


# ---------------------------------------------------------------------------
# 3) TEKNİK SEÇMELİLER — alan seçmeli havuzu
# ---------------------------------------------------------------------------

TEKNIK_SECMELILER = [
    ("MBG 402", "Hesaplamalı Biyoloji"), ("MBG 403", "İnsan Genetik Hastalıkları"),
    ("MBG 405", "Moleküler Evrim"), ("MBG 406", "Moleküler Tıp"),
    ("MBG 407", "Kök Hücre"), ("MBG 408", "Biyomoleküller"),
    ("MBG 409", "Kanser Biyolojisi"), ("MBG 410", "Mikroarray Veri Analizi"),
    ("MBG 411", "Model Organizmalar"), ("MBG 412", "İmmünoloji"),
    ("MBG 413", "Biyoteknoloji"), ("MBG 414", "Biyomalzemeler"),
    ("MBG 415", "Hücre ve Doku Mühendisliği"), ("MBG 416", "Gelişim Biyolojisi"),
    ("MBG 417", "Sinir Biliminin Temelleri"), ("MBG 418", "Nöral Sistemi"),
    ("MBG 419", "Fonksiyonel Genomik"), ("MBG 420", "Klinik Araştırmalara Giriş"),
    ("MBG 421", "RNA Biyolojisi"), ("MBG 425", "Popülasyon Genetiği"),
    ("MBG 426", "Tümör Histolojisi"), ("MBG 428", "Epigenetik"),
    ("MBG 430", "Viroloji"), ("MBG 431", "İnsan Fizyolojisi"),
    ("MBG 435", "Hastalıklar ve Genetik"),
    ("MBG 436", "Fizyoloji ve Tıpta Dönüm Noktası Keşifler"),
    ("MBG 351", "Araştırma Projesi"), ("MBG 463", "Özel Çalışmalar I (ön şart: MBG 351, GPA ≥ 3.00)"),
    ("MBG 464", "Özel Çalışmalar II (ön şart: MBG 463)"),
    ("MBG 465", "Moleküler Endokrinoloji"),
    ("MBG 466", "Nörolojik ve Psikiyatrik Bozuklukların Nörobiyolojisi"),
]

TEKNIK_SECMELI_BENG = [
    ("BENG 304", "Doku Mühendisliği"), ("BENG 307", "Biyomedikal Sensörler ve Transdüserler"),
    ("BENG 302", "Biyomalzeme Bilimi"), ("BENG 310", "Rekombinant DNA Teknolojisi"),
    ("BENG 423", "Tıbbi Görüntüleme Sistemleri"), ("BENG 427", "Doku-Biyomalzeme Etkileşimi"),
    ("BENG 429", "Kontrollü İlaç Salımı"), ("BENG 431", "Nanofabrikasyon"),
    ("BENG 432", "Doku Mühendisliği ve Rejeneratif Tıp"),
    ("BENG 433", "Biyomedikal Uygulamalar için Nanopartiküller"),
    ("BENG 434", "Kök Hücre Teknolojisi ve Rejeneratif Tıp"),
    ("BENG 435", "Ayırma Teknikleri"), ("BENG 436", "İlaç Tasarımı ve Keşfi"),
    ("BENG 437", "Biyoorganik ve Medisinal Kimya"), ("BENG 438", "Biyonanoteknolojiye Giriş"),
    ("BENG 439", "Metabolik Mühendislik"),
    ("BENG 445", "Moleküler ve Hücresel İmmünoloji (ön şart: MBG 412)"),
    ("BENG 448", "Biyoveri Madenciliği"),
]


def make_secmeli_chunks() -> list[dict]:
    bolum_lines = [f"- {kod} | {ad}" for kod, ad in TEKNIK_SECMELILER]
    beng_lines = [f"- {kod} | {ad}" for kod, ad in TEKNIK_SECMELI_BENG]
    text = (
        f"AGÜ {BOLUM_ADI} — Alan Teknik Seçmeli Dersleri:\n\n"
        "Öğrenciler 3. ve 4. yıllarda toplam 10 adet Alan Teknik Seçmeli (MBGXXX) ders alır "
        "(her biri 3 kredi / 5 AKTS, toplam ~50 AKTS). Bunlar bölüm içi havuzdan seçilir.\n\n"
        "BÖLÜM TEKNİK SEÇMELİ DERSLERİ (MBG):\n"
        + "\n".join(bolum_lines)
        + "\n\nBÖLÜM DIŞI TEKNİK SEÇMELİ DERSLER (BENG — Biyomühendislik'ten alınabilir):\n"
        + "\n".join(beng_lines)
        + "\n\nAyrıca XMBG445/446/447 (aktarım seçmeli) ve MBGX151/152 "
        "(Dijital Öğrenme Platformu ileri düzey aktarım seçmeli) dersleri de mevcuttur."
    )
    return [{
        "id": "mbg_teknik_secmeliler",
        "text": text,
        "metadata": {
            "bolum": BOLUM,
            "tip": "secmeli_listesi",
            "kategori": "teknik_secmeli",
            "mufredat_yili": MUFREDAT,
            "kaynak": PROGRAM_PDF.name,
        },
    }]


# ---------------------------------------------------------------------------
# 4) GENEL ÖZET + MEZUNİYET KURALLARI
# ---------------------------------------------------------------------------

def make_overview() -> dict:
    text = (
        "AGÜ Moleküler Biyoloji ve Genetik (MBG) Bölümü — Genel Bilgiler:\n\n"
        "Abdullah Gül Üniversitesi Yaşam ve Doğa Bilimleri Fakültesi bünyesinde, 2012 yılında "
        "kurulmuştur. MBG; moleküler biyoloji, genetik, mikrobiyoloji, hücre biyolojisi, biyokimya "
        "ve biyoinformatik konularında disiplinlerarası güçlü bir altyapı sunar. Araştırma alanları: "
        "gen regülasyonu, kanser biyolojisi, nadir hastalıklar, immünoloji, terapötikler, omiks.\n\n"
        "TEMEL BİLGİLER:\n"
        "- Kazanılan derece: Lisans / Moleküler Biyoloji ve Genetik\n"
        "- Öğrenim süresi: 4 yıl (1 yıllık İngilizce Hazırlık hariç), 8 yarıyıl\n"
        "- Toplam: 240 AKTS\n"
        "- Eğitim dili: İngilizce\n"
        "- Eğitim türü: Tam zamanlı\n"
        "- Fakülte: Yaşam ve Doğa Bilimleri Fakültesi\n\n"
        "MEZUNİYET KOŞULLARI:\n"
        "- Müfredattaki tüm dersleri (240 AKTS) 8 yarıyılda başarıyla tamamlamak\n"
        "- Ağırlıklı genel not ortalaması (GNO) 4.00 üzerinden en az 2.00 olmak\n"
        "- Tüm dersler en az D veya S notu ile tamamlanmalı\n"
        "- En az bir zorunlu staj (MBG 499 Yaz Stajı) tamamlanmalı\n\n"
        "DERS GRUBU DAĞILIMI (240 AKTS):\n"
        "- AGÜ İmza Dersleri (GLB): 5 ders, 20 AKTS\n"
        "- YÖK/Zorunlu Ortak Dersler (ENG, TURK, HIST, OHS, CP100): 9 ders, 19 AKTS\n"
        "- Zorunlu Dersler (laboratuvarlı + laboratuvarsız): 22 ders, ~136 AKTS\n"
        "- Alan Teknik Seçmeliler (MBGXXX): 10 ders, 50 AKTS\n"
        "- Teknik Olmayan Seçmeliler: 3 ders, 9 AKTS\n"
        "- Yaz Stajı (MBG 499): 6 AKTS\n\n"
        "KARİYER: Biyoteknoloji/ilaç firmaları, IVF (tüp bebek) merkezleri, hastaneler ve tanı "
        "laboratuvarları, Adli Tıp, TÜBİTAK, teknoparklar, Tarım/Çevre Bakanlıkları; ayrıca "
        "yüksek lisans ve doktora (akademik kariyer).\n\n"
        "Soru: 'MBG kaç AKTS?' → 240 AKTS. 'Mezuniyet için GNO?' → en az 2.00/4.00. "
        "'Staj zorunlu mu?' → Evet, MBG 499 Yaz Stajı (6 AKTS)."
    )
    return {
        "id": "mbg_genel_ozet",
        "text": text,
        "metadata": {
            "bolum": BOLUM,
            "tip": "program_genel",
            "kategori": "genel_ozet",
            "mufredat_yili": MUFREDAT,
            "kaynak": PROGRAM_PDF.name,
        },
    }


def make_program_outcomes() -> dict:
    text = (
        f"AGÜ {BOLUM_ADI} — Program Çıktıları (PÇ):\n\n"
        "PÇ1. MBG alanında güncel biyolojik literatürü okuma, anlama ve eleştirel yorumlama.\n"
        "PÇ2. Moleküler düzeyde temel biyolojik içerik ve prensipleri tanımlama.\n"
        "PÇ3. Farklı organizmalarda gen ve hücrenin moleküler yapısını, işleyişini ve kontrol "
        "mekanizmalarını bilme.\n"
        "PÇ4. Bilimsel deney tasarlama, veri toplama, analiz etme ve yorumlama.\n"
        "PÇ5. Kazanılan teorik ve pratik bilgiyi kullanma.\n"
        "PÇ6. Bağımsız çalışmalar gerçekleştirme.\n"
        "PÇ7. Problem çözmede bireysel ya da takım üyesi olarak sorumluluk alma.\n"
        "PÇ8. Biyolojik çalışmalar için etik prensipleri tanımlama ve uygulama.\n"
        "PÇ9. Bilim insanlarının toplumdaki rolünü anlama.\n"
        "PÇ10. Yerel ve global sorunların çözüm sürecinde aktif rol oynama.\n\n"
        "Program hedefleri: teorik/pratik araştırma becerisi kazanmak; özgün araştırma tasarlayıp "
        "yürütmek; genetik mühendisliği, eczacılık biyoteknoloji, tarım, gıda, ilaç, çevre ve halk "
        "sağlığı alanlarında problem tanımlayıcı ve çözüm üretici olarak görev almak."
    )
    return {
        "id": "mbg_program_ciktilari",
        "text": text,
        "metadata": {
            "bolum": BOLUM,
            "tip": "program_bilgi",
            "kategori": "program_ciktilari",
            "mufredat_yili": MUFREDAT,
            "kaynak": PROGRAM_PDF.name,
        },
    }


def main():
    chunks: list[dict] = []
    chunks.append(make_overview())
    chunks.append(make_program_outcomes())
    chunks.extend(make_curriculum_chunks())
    chunks.extend(make_secmeli_chunks())

    katalog = parse_catalog()
    chunks.extend(katalog)

    out_path = OUT / "chunks_mbg.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} MBG chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in sorted(by_tip.items()):
        print(f"     - {t}: {n}")
    print(f"[i] Katalogdan parse edilen ders: {len(katalog)}")


if __name__ == "__main__":
    main()

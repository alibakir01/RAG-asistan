"""
AGÜ Psikoloji bölümü — 8 dönemlik yapılandırılmış müfredat ingest.

Kaynak: data/raw/psikoloji_mufredat.csv (Google Sheet export)
Ön şart kaynağı: data/raw/psikoloji_katalog.json (mevcut katalog)

Çıktı: data/processed/chunks_psikoloji_mufredat.jsonl
bolum = "psikoloji"
mufredat_yili = "2021"
tip = "mufredat" (liste modu için kritik)

Mevcut chunks_psikoloji.jsonl (katalog/ders_icerik) bozulmadan kalır;
bu dosya ek olarak gelir — embed.py iki dosyayı da Chroma'ya alır.
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

CSV_PATH = RAW / "psikoloji_mufredat.csv"
KATALOG_PATH = RAW / "psikoloji_katalog.json"
BOLUM = "psikoloji"
BOLUM_ADI = "Psikoloji"
MUFREDAT_YILI = "2021"

SEM_TO_DONEM = {
    "1st sem.": 1, "2nd sem.": 2, "3rd sem.": 3, "4th sem.": 4,
    "5th sem.": 5, "6th sem.": 6, "7th sem.": 7, "8th sem.": 8,
}
SEZON = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar",
         5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}

# Placeholder / havuz kodlarının açıklamaları + tipik adaylar
PLACEHOLDER_INFO = {
    "PSYFXXX": {
        "ad_full": "Fundamental Cluster Dersi (Lecture)",
        "aciklama": (
            "Bu slot, Psikoloji programının 'Fundamental Clusters' (Küme Temel Dersleri) "
            "havuzundan bir teori dersini temsil eder. Öğrenci aşağıdaki PSYF dersleri "
            "arasından seçer: PSYF 211 Cognitive Psychology, PSYF 212 Learning, "
            "PSYF 213 Physiological and Neuropsychology, PSYF 221 Social Psychology, "
            "PSYF 222 Development in Life Span, PSYF 223 Personality, "
            "PSYF 231 Clinical Psychology and Psychotherapy Approaches, "
            "PSYF 232 Abnormal Psychology, PSYF 233 Health Psychology, "
            "PSYF 241 Political Psychology, PSYF 242 Psychology in Education Settings."
        ),
        "on_sart": "Core Courses II (PSYC 101, PSYC 102, PSYC 103, PSYC 104) tamamlanmış olmalı.",
    },
    "PSYLXXX": {
        "ad_full": "Fundamental Cluster Laboratuvar Dersi",
        "aciklama": (
            "Fundamental Clusters havuzundan bir LABORATUVAR dersini temsil eder. "
            "Adaylar: PSYF 210 (Experimental & Physiological Lab), PSYF 220 "
            "(Human Development & Relations Lab), PSYF 230 (Applied: Human Well-Being Lab), "
            "PSYL 240 (Applied: Human Behaviour in Social Setting Lab)."
        ),
        "on_sart": (
            "Core Courses II tamamlanmış + aynı kümeden ilgili PSYF teorik dersi "
            "(örn. PSYF 210 için PSYF 211/212/213) tamamlanmış olmalı. "
            "Küme PSYF dersi alınmadan Lab dersi alınamaz."
        ),
    },
    "PSYSXXX": {
        "ad_full": "Departmental Seminar (Bölüm Seminer Seçmelisi)",
        "aciklama": (
            "Bölüm seminer seçmelileri havuzu. Adaylar: PSYS 301 Social Conflict and "
            "Violence, PSYS 302 Classical Studies in Experimental Psychology, "
            "PSYS 303 Psychology of Stereotyping and Prejudice, PSYS 304 Feline "
            "Cognition, PSYS 305 Critical Psychology."
        ),
        "on_sart": (
            "Core Courses II + ilgili Fundamental Cluster (FC) dersi tamamlanmış olmalı, "
            "ya da eğitmen onayı (instructor consent)."
        ),
    },
    "PSYEXXX": {
        "ad_full": "Departmental Elective (Bölüm-içi Seçmeli)",
        "aciklama": (
            "Bölüm-içi seçmeli ders. PSYS (seminer), PSYT (konu) ve diğer PSY-prefiks "
            "kodlu seçmeli derslerden seçilebilir (PSYS 301-305, PSYT 330-334, vb.)."
        ),
        "on_sart": "Core Courses II tamamlanmış olmalı (ders-spesifik ek şartlar olabilir).",
    },
    "PSYG": {
        "ad_full": "Cognate Course (Yandal / Destek Dersi)",
        "aciklama": (
            "Cognate (yandal) ders havuzu. Psikoloji ile ilgili komşu disiplinlerden "
            "(sosyoloji, felsefe, biyoloji, eğitim bilimleri vb.) seçilen destek dersi."
        ),
        "on_sart": "yok",
    },
    "PSY3N": {
        "ad_full": "Non-Departmental Elective (3000-level)",
        "aciklama": (
            "Bölüm dışı seçmeli ders — 3000 düzeyinde bir başka AGÜ programının "
            "dersinden seçilebilir."
        ),
        "on_sart": "Ders-spesifik (alınan dersin kendi ön şartları geçerlidir).",
    },
    "PSY5N": {
        "ad_full": "Non-Departmental Elective (5000-level)",
        "aciklama": (
            "Bölüm dışı seçmeli ders — 5000 düzeyinde / üst sınıflarda alınan, başka "
            "programdan bir ders."
        ),
        "on_sart": "Ders-spesifik (alınan dersin kendi ön şartları geçerlidir).",
    },
    "PSYU": {
        "ad_full": "Unrestricted Elective (Sınırsız Seçmeli)",
        "aciklama": (
            "Sınırsız seçmeli — öğrencinin AGÜ kataloğundan veya danışman onayıyla "
            "transfer/online (Udemy vb.) bir dersten seçebileceği serbest seçmeli. "
            "Onaylı online transfer dersleri için PSYX 152 transfer listesine de bakılabilir."
        ),
        "on_sart": "Ders-spesifik.",
    },
    "HISTXXX": {
        "ad_full": "Listed History of the Republic of Turkey Course",
        "aciklama": (
            "Türkiye Cumhuriyeti Tarihi listeli ders (YÖK zorunlu çekirdek dersi). "
            "Üniversite tarafından açılan HIST dersinden alınır."
        ),
        "on_sart": "yok",
    },
    "TURKXXX": {
        "ad_full": "Listed Turkish Language Course",
        "aciklama": (
            "Türk Dili listeli ders (YÖK zorunlu çekirdek dersi). Üniversite tarafından "
            "açılan TURK dersinden alınır."
        ),
        "on_sart": "yok",
    },
    "GLB": {
        "ad_full": "Global Issues Elective",
        "aciklama": (
            "AGÜ Küresel Sorunlar (Global Issues) seçmeli havuzundan alınan ders. "
            "GLB-prefiksli derslerden (örn. GLB 1XX/2XX/3XX) seçilebilir."
        ),
        "on_sart": "yok",
    },
}


def _norm_kod(raw: str) -> str:
    s = (raw or "").strip().upper().replace(" ", "")
    m = re.match(r"^([A-Z]+)(\d+\w*)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s.replace("XXX", "XXX")  # PSYFXXX kalır


def load_katalog() -> dict[str, dict]:
    """ders_kodu -> katalog kaydı (kod boşluksuz uppercase anahtar)."""
    if not KATALOG_PATH.exists():
        return {}
    data = json.loads(KATALOG_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for c in data.get("ders_katalogu", []):
        kod_norm = (c.get("kod") or "").strip().upper().replace(" ", "")
        if kod_norm:
            out[kod_norm] = c
    return out


def _enrich_from_katalog(kod: str, katalog: dict[str, dict]) -> dict:
    """Verilen ders koduna karşılık katalogdan zenginleştirici bilgi getir."""
    key = kod.replace(" ", "").upper()
    rec = katalog.get(key)
    if not rec:
        return {}
    return {
        "on_sart": rec.get("on_sart", "").strip(),
        "ders_adi_katalog": rec.get("ad", "").strip(),
        "dil": rec.get("dil", ""),
        "kategori": rec.get("kategori", ""),
        "icerik": rec.get("icerik", "").strip(),
    }


def parse_csv() -> list[dict]:
    if not CSV_PATH.exists():
        print(f"[!] bulunamadı: {CSV_PATH}")
        return []

    katalog = load_katalog()
    chunks: list[dict] = []
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    seen_ids: set[str] = set()

    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for ri, row in enumerate(reader, start=1):
            sem_raw = (row.get("Semester") or "").strip()
            kod_raw = (row.get("Code") or "").strip()
            ad = (row.get("Name") or "").strip()

            if not sem_raw or sem_raw.lower() == "total":
                continue
            if kod_raw.lower() == "total":
                continue
            donem = SEM_TO_DONEM.get(sem_raw)
            if donem is None:
                continue
            if not kod_raw or not ad:
                continue

            kod = _norm_kod(kod_raw)
            teorik = (row.get("T") or "").strip()
            lab = (row.get("A") or "").strip()
            kredi = (row.get("AC") or "").strip()
            akts = (row.get("ECTS") or "").strip()
            csv_on = (row.get("Ön Şart") or "").strip()

            # Katalogdan zenginleştir
            kat = _enrich_from_katalog(kod, katalog)
            on_sart = csv_on or kat.get("on_sart", "") or ""

            # Placeholder ders mi?
            placeholder_key = None
            for ph in PLACEHOLDER_INFO:
                if kod.replace(" ", "") == ph or kod == ph:
                    placeholder_key = ph
                    break
            if placeholder_key:
                info = PLACEHOLDER_INFO[placeholder_key]
                ad_full = info["ad_full"]
                on_sart = on_sart or info["on_sart"]
                ek_aciklama = info["aciklama"]
            else:
                ad_full = kat.get("ders_adi_katalog") or ad
                ek_aciklama = ""

            on_sart_clean = (on_sart or "yok").strip().strip("-").strip() or "yok"

            yil = (donem - 1) // 2 + 1
            sezon = SEZON.get(donem, "")
            dil = kat.get("dil") or "İngilizce"

            # Unique id (placeholder kodlar dönemde birden fazla geçebilir)
            base_id = kod.replace(" ", "_").replace("*", "")
            cid = f"psikoloji_muf_d{donem}_{base_id}"
            idx = 1
            while cid in seen_ids:
                idx += 1
                cid = f"psikoloji_muf_d{donem}_{base_id}_{idx}"
            seen_ids.add(cid)

            text = (
                f"{MUFREDAT_YILI} {BOLUM_ADI} müfredatı — "
                f"{yil}. yıl {sezon} dönemi ({donem}. dönem): "
                f"{kod} {ad_full}. "
                f"Teorik: {teorik or '—'}, Lab/Pratik: {lab or '—'}, "
                f"Kredi: {kredi or '—'}, AKTS: {akts or '—'}. "
                f"Eğitim dili: {dil}. "
                f"Ön şart: {on_sart_clean}."
            )
            if ek_aciklama:
                text += f" Ders havuzu açıklaması: {ek_aciklama}"
            if kat.get("icerik"):
                # Katalog içeriğini kısa olarak ekle (Lite, çok uzun olmasın)
                ic = kat["icerik"]
                text += f" Ders içeriği özeti: {ic[:400]}{'...' if len(ic) > 400 else ''}"

            md = {
                "tip": "mufredat",
                "mufredat_yili": MUFREDAT_YILI,
                "donem": donem,
                "yil": yil,
                "sezon": sezon,
                "ders_kodu": kod,
                "ders_adi": ad_full,
                "ders_adi_csv": ad,
                "on_sart": on_sart_clean,
                "teorik": teorik,
                "lab": lab,
                "kredi": kredi,
                "akts": akts,
                "dil": dil,
                "is_placeholder": placeholder_key is not None,
                "kaynak": CSV_PATH.name,
                "bolum": BOLUM,
            }
            if kat.get("kategori"):
                md["kategori"] = kat["kategori"]

            chunks.append({"id": cid, "text": text, "metadata": md})

            short = (
                f"- {kod} | {ad_full} | "
                f"T:{teorik or '—'}, A:{lab or '—'}, "
                f"Kredi:{kredi or '—'}, AKTS:{akts or '—'} | "
                f"Ön şart: {on_sart_clean}"
            )
            semester_courses.setdefault(donem, []).append(short)
            semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    # Dönem özet chunk'ları (liste modunda kullanılan tip='donem_ozet')
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {MUFREDAT_YILI} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — "
            f"Toplam {len(lines)} ders:\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"psikoloji_muf_sem_d{donem}",
            "text": body[:5000],
            "metadata": {
                "tip": "donem_ozet",
                "mufredat_yili": MUFREDAT_YILI,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": CSV_PATH.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def make_overview() -> dict:
    text = (
        f"AGÜ {BOLUM_ADI} Bölümü — {MUFREDAT_YILI} müfredat özeti. 4 yıllık (8 yarıyıl) "
        f"lisans programı, eğitim dili İngilizce. Toplam 240 AKTS. Program 'Psychological "
        f"Innovation' modeli ile yapılandırılmıştır ve TPD + EFPA akreditasyon kriterleri "
        f"esas alınır. Çekirdek (Core) zorunlular: PSYC 101-104 (Essential Topics I-II, "
        f"Research Methods, Statistics for Psychology), PSYC 111-112 (Orientation I-II), "
        f"PSYC 114 (Ethics in Psychology). Fundamental Cluster (FC) Lecture'lar 3-4. dönemde, "
        f"FC Lab'lar 5-6. dönemde alınır. 5-8. dönemler departmental seminar (PSYS), "
        f"departmental elective (PSYE), non-departmental elective (PSY3N/PSY5N) ve "
        f"unrestricted elective (PSYU) ile şekillenir. Cognate (PSYG) dersleri ilk 3 dönemde, "
        f"GLB Global Issues seçmelileri 1-5. dönemde alınır."
    )
    return {
        "id": "psikoloji_mufredat_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "mufredat_yili": MUFREDAT_YILI,
            "kaynak": CSV_PATH.name,
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_csv()
    chunks.append(make_overview())
    out_path = OUT / "chunks_psikoloji_mufredat.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} psikoloji müfredat chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")

    # Ön şart eşleşme istatistiği
    enriched = sum(1 for c in chunks
                   if c["metadata"].get("tip") == "mufredat"
                   and c["metadata"].get("on_sart", "yok") != "yok")
    total_muf = sum(1 for c in chunks if c["metadata"].get("tip") == "mufredat")
    print(f"     [ön şart eşleşmesi]: {enriched}/{total_muf} derste ön şart bilgisi var")


if __name__ == "__main__":
    main()

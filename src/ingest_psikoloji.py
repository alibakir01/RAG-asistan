"""
AGÜ Psikoloji (Psychology) bölümü ingest.
Kaynak: data/raw/psikoloji_katalog.json (AGU Psychology Undergraduate Catalog, June 2021)

Çıktı: data/processed/chunks_psikoloji.jsonl
bolum = "psikoloji"

NOT: Psikoloji bölümünün resmi katalog (PDF) yapısı diğer mühendislik bölümleri gibi
"X. dönem - Y dersleri" şeklinde sabit bir sıralama içermez. Pek çok PSYF/PSYS/PSYT/PSYI
dersi "2., 3. veya 4. yıl / Güz veya Bahar" esnekliğindedir. Bu yüzden ingest;
ders_icerik, kategori_ozet ve program_genel chunk'larına odaklanır.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

KATALOG_PATH = RAW / "psikoloji_katalog.json"
BOLUM = "psikoloji"
BOLUM_ADI = "Psikoloji"
KAYNAK = "AGU_Psychology_Undergraduate_Catalog_June_2021.pdf"


def _ders_id(kod: str) -> str:
    return kod.replace(" ", "_").replace(".", "_")


def parse_katalog() -> list[dict]:
    if not KATALOG_PATH.exists():
        print(f"[!] bulunamadı: {KATALOG_PATH}")
        return []

    with KATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    chunks: list[dict] = []

    # ---- Ders içerikleri (her ders için bir chunk) ----
    kategori_map = {k["kod"]: k["ad"] for k in data.get("kategoriler", [])}
    by_kategori: dict[str, list[dict]] = {}

    for c in data.get("ders_katalogu", []):
        kod = c["kod"]
        ad = c.get("ad", "")
        kategori = c.get("kategori", "")
        kategori_adi = kategori_map.get(kategori, kategori)
        saat = c.get("saat", "")
        kredi = c.get("kredi", "")
        akts = c.get("akts", "")
        yil = c.get("yil", "")
        donem = c.get("donem", "")
        tip = c.get("tip", "")
        dil = c.get("dil", "İngilizce")
        on_sart = c.get("on_sart") or "yok"
        icerik = c.get("icerik", "")
        amac = c.get("amac", "")
        not_alanı = c.get("not", "")

        yil_str = f"{yil}. yıl" if isinstance(yil, int) else (f"{yil}. yıl" if yil else "")

        text = (
            f"AGÜ {BOLUM_ADI} bölümü ders kataloğu — "
            f"{kod} {ad}. "
            f"Kategori: {kategori_adi}. "
            f"{yil_str}{', ' if yil_str else ''}Dönem: {donem}. "
            f"Tip: {tip}. "
            f"Haftalık saat: {saat}. Kredi: {kredi}. AKTS: {akts}. "
            f"Dersin dili: {dil}. "
            f"Ön şart: {on_sart}. "
            f"İçerik: {icerik} "
            f"Amaç: {amac}"
        )
        if not_alanı:
            text += f" Not: {not_alanı}"

        chunks.append({
            "id": f"psikoloji_katalog_{_ders_id(kod)}",
            "text": text[:5000],
            "metadata": {
                "tip": "ders_icerik",
                "ders_kodu": kod,
                "ders_adi": ad,
                "kategori": kategori,
                "kategori_adi": kategori_adi,
                "ders_tipi": tip,
                "donem_label": donem,
                "yil": yil if isinstance(yil, int) else str(yil) if yil else "",
                "haftalik_saat": saat,
                "kredi": kredi,
                "akts": akts,
                "dil": dil,
                "on_sart": on_sart,
                "kaynak": KAYNAK,
                "bolum": BOLUM,
            },
        })

        by_kategori.setdefault(kategori, []).append({
            "kod": kod, "ad": ad, "kredi": kredi, "akts": akts,
            "on_sart": on_sart, "tip": tip,
        })

    # ---- Kategori özet chunk'ları ----
    for kategori_kod, items in by_kategori.items():
        kategori_adi = kategori_map.get(kategori_kod, kategori_kod)
        # Kategori kurallarını da ekle
        kategori_obj = next(
            (k for k in data.get("kategoriler", []) if k["kod"] == kategori_kod),
            None,
        )
        kurallar = kategori_obj.get("kurallar", "") if kategori_obj else ""
        aciklama = kategori_obj.get("aciklama", "") if kategori_obj else ""

        lines = [
            f"- {it['kod']} | {it['ad']} | Kredi: {it['kredi']}, AKTS: {it['akts']} | Ön şart: {it['on_sart']}"
            for it in items
        ]
        body = (
            f"AGÜ {BOLUM_ADI} bölümü — {kategori_adi} kategorisi, "
            f"toplam {len(items)} ders:\n"
            + "\n".join(lines)
            + (f"\n\nAçıklama: {aciklama}" if aciklama else "")
            + (f"\nKurallar: {kurallar}" if kurallar else "")
        )

        slug = (
            kategori_kod.lower()
            .replace(" ", "_")
        )
        chunks.append({
            "id": f"psikoloji_kategori_{slug}",
            "text": body[:5000],
            "metadata": {
                "tip": "kategori_ozet",
                "kategori": kategori_kod,
                "kategori_adi": kategori_adi,
                "ders_sayisi": len(items),
                "kaynak": KAYNAK,
                "bolum": BOLUM,
            },
        })

    # ---- Program genel bilgi ----
    p = data.get("program", {})
    if p:
        text = (
            f"AGÜ {p.get('ad', BOLUM_ADI)} ({p.get('kod', 'PSY')}) lisans programı — {p.get('fakulte', '')}. "
            f"Derece: {p.get('derece', '')}. Süre: {p.get('sure', '')}. "
            f"Düzey: {p.get('duzey', '')}. Eğitim türü: {p.get('egitim_turu', '')}. "
            f"Temel alan: {p.get('egitim_temel_alan', '')}. "
            f"Akreditasyon: {p.get('akreditasyon', '')} "
            f"Program modeli: {p.get('model', '')} "
            f"Amaç: {p.get('amac', '')} "
            f"Hedefler: {p.get('hedefler', '')} "
            f"Kabul koşulları: {p.get('kabul_kosullari', '')} "
            f"Mezuniyet koşulları: {p.get('mezuniyet_kosullari', '')} "
            f"Kariyer alanları: {p.get('kariyer', '')} "
            f"Üst dereceler: {p.get('ust_derece', '')} "
            f"Ölçme-değerlendirme: {p.get('olcme_degerlendirme', '')}"
        )
        chunks.append({
            "id": "psikoloji_program_genel",
            "text": text[:5000],
            "metadata": {
                "tip": "program_genel",
                "kaynak": KAYNAK,
                "bolum": BOLUM,
            },
        })

    # ---- Mezuniyet kuralları chunk'ı ----
    mez = data.get("mezuniyet_kurallari", {})
    if mez:
        text = (
            f"AGÜ {BOLUM_ADI} bölümü mezuniyet kuralları:\n"
            f"• Core Courses I (Zorunlu Oryantasyon/Etik): {mez.get('core_courses_i', '')}\n"
            f"• Core Courses II (Temel Psikoloji): {mez.get('core_courses_ii', '')}\n"
            f"• Fundamental Cluster Kuralı: {mez.get('fundamental_clusters', '')}\n"
            f"• Seminer Dersleri: {mez.get('seminer_dersleri', '')}\n"
            f"• Kariyer Hazırlığı: {mez.get('kariyer_hazirligi', '')}\n"
            f"• Onur Derecesi (BS Hons): {mez.get('hons_derecesi', '')}\n"
            f"• GPA: {mez.get('gpa', '')}"
        )
        chunks.append({
            "id": "psikoloji_mezuniyet_kurallari",
            "text": text[:5000],
            "metadata": {
                "tip": "mezuniyet_kurallari",
                "kaynak": KAYNAK,
                "bolum": BOLUM,
            },
        })

    return chunks


def make_program_overview() -> dict:
    text = (
        "Abdullah Gül Üniversitesi Psikoloji (Psychology, kod: PSY) lisans programı. "
        "4 yıl süreli, 8 dönemlik program. AGÜ İnsan ve Toplum Bilimleri Fakültesi (PSYW4) altında. "
        "Program yapısı dört temel kategori üzerine kuruludur: "
        "(1) Core Courses I — Orientation and Ethics (PSYC 111, PSYC 112, PSYC 114) — üçü de mezuniyet için zorunlu. "
        "(2) Core Courses II — Essentials to Psychologists (PSYC 101 Essential Topics I, PSYC 102 Essential Topics II, "
        "PSYC 103 Research Methods, PSYC 104 Statistics) — dördü de zorunlu ve diğer tüm PSY kodlu derslerin ön şartıdır. "
        "(3) Fundamental Clusters I-IV — her bir kümeden en az bir PSYF kodlu zorunlu temel ders alınmalı; "
        "küme laboratuvarları (PSYF 210, PSYF 220, PSYF 230, PSYL 240) ilgili PSYF temel dersi tamamlanmadan alınamaz. "
        "Cluster I: Experimental & Physiological Psychology (PSYF 211 Cognitive, PSYF 212 Learning, PSYF 213 Physiological/Neuropsych, PSYF 210 Lab). "
        "Cluster II: Human Development & Relations (PSYF 221 Social, PSYF 222 Lifespan, PSYF 223 Personality, PSYF 220 Lab). "
        "Cluster III: Applied — Human Well-Being (PSYF 231 Clinical, PSYF 232 Abnormal, PSYF 233 Health, PSYF 230 Lab). "
        "Cluster IV: Applied — Behaviour in Social Settings (PSYF 241 Political Psychology, PSYF 242 Psychology in Education, PSYL 240 Lab). "
        "(4) Seçmeli dersler: PSYS (seminer, mezuniyet için en az 2 tane), PSYT (güncel konu), PSYI (Independent Study/Internship/Erasmus) ve PSYP (Capstone Project I-II). "
        "İki Capstone'u başarıyla tamamlayanlar BS (Hons) — Onur Derecesi alır. "
        "Eğitim dili İngilizce. Mezuniyet için minimum GPA 2.00. "
        "Program TPD ve EFPA kriterlerini esas alır ve PIISP (Psychological Innovation and Impact on Social Problems) modelini uygular."
    )
    return {
        "id": "psikoloji_program_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "kaynak": "program_tanitim",
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_katalog()
    chunks.append(make_program_overview())

    out_path = OUT / "chunks_psikoloji.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} psikoloji chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in sorted(by_tip.items()):
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

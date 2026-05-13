"""
AGÜ Siyaset Bilimi ve Uluslararası İlişkiler (POLS) müfredatı ingest.
Kaynak: data/raw/siyaset_mufredat.csv (Google Sheet export)

CSV formatı: Her "X. YIL" başlığı altında iki dönem yan yana — sol 7 kolon
(Ders Kodu | Ders Adı | T | P | Kredi | AKTS | Ön Şart), sağ 7 kolon aynı şema.

Çıktı: data/processed/chunks_siyaset.jsonl
bolum = "siyaset"
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

CSV_PATH = RAW / "siyaset_mufredat.csv"
SECMELI_CSV_PATH = RAW / "siyaset_secmeli.csv"
KATALOG_PATH = RAW / "siyaset_katalog.json"
BOLUM = "siyaset"
BOLUM_ADI = "Siyaset Bilimi ve Uluslararası İlişkiler"
MUFREDAT_YILI = "2025"

NOT_SPECIFIED = "Belirtilmemiş"

DONEM_NAMES = {
    "BİRİNCİ DÖNEM": 1, "İKİNCİ DÖNEM": 2,
    "ÜÇÜNCÜ DÖNEM": 3, "DÖRDÜNCÜ DÖNEM": 4,
    "BEŞİNCİ DÖNEM": 5, "ALTINCI DÖNEM": 6,
    "YEDİNCİ DÖNEM": 7, "SEKİZİNCİ DÖNEM": 8,
}

SEZON = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar",
         5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}


def _norm_kod(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip()).upper()
    # "POLS101" -> "POLS 101"
    m = re.match(r"^([A-Z]+)\s*(\d+\w*)$", s.replace(" ", ""))
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _skip(cells: list[str]) -> bool:
    first = (cells[0] or "").strip()
    if not first:
        return True
    if first.upper().startswith("DÖNEM TOPLAM"):
        return True
    if first.upper().startswith("YIL TOPLAM"):
        return True
    if first.upper().startswith("GENEL TOPLAM"):
        return True
    if first == "Ders Kodu":
        return True
    return False


def _parse_course_block(cells: list[str], offset: int) -> dict | None:
    """cells[offset:offset+7] -> course dict or None."""
    if len(cells) < offset + 7:
        return None
    kod_raw = (cells[offset] or "").strip()
    ad = (cells[offset + 1] or "").strip()
    if not kod_raw or not ad:
        return None
    if kod_raw.upper().startswith("DÖNEM TOPLAM") or kod_raw.upper().startswith("YIL TOPLAM"):
        return None
    teo = (cells[offset + 2] or "").strip()
    p = (cells[offset + 3] or "").strip()
    kredi = (cells[offset + 4] or "").strip()
    akts = (cells[offset + 5] or "").strip()
    on = (cells[offset + 6] or "").strip().strip("-").strip()
    return {
        "ders_kodu": _norm_kod(kod_raw),
        "ders_adi": ad,
        "teorik": teo,
        "lab": p,
        "kredi": kredi,
        "akts": akts,
        "on_sart": on,
    }


def parse_csv() -> list[dict]:
    if not CSV_PATH.exists():
        print(f"[!] bulunamadı: {CSV_PATH}")
        return []

    chunks: list[dict] = []
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    seen_ids: set[str] = set()

    left_donem: int | None = None
    right_donem: int | None = None

    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            cells = [c.strip() for c in row]
            first = cells[0] if cells else ""

            # YIL başlığı? (sadece ilk hücrede "X. YIL" var)
            if first.upper().endswith(" YIL") or first.upper() in (
                "BİRİNCİ YIL", "İKİNCİ YIL", "ÜÇÜNCÜ YIL", "DÖRDÜNCÜ YIL"
            ):
                continue

            # DÖNEM başlığı? (sol col 0, sağ col 7)
            left_label = first.upper().strip()
            right_label = (cells[7].upper().strip() if len(cells) > 7 else "")
            if left_label in DONEM_NAMES or right_label in DONEM_NAMES:
                if left_label in DONEM_NAMES:
                    left_donem = DONEM_NAMES[left_label]
                if right_label in DONEM_NAMES:
                    right_donem = DONEM_NAMES[right_label]
                continue

            # Header satırı (Ders Kodu)?
            if first == "Ders Kodu":
                continue

            # Toplam satırları
            if first.upper().startswith("DÖNEM TOPLAM") or \
               first.upper().startswith("YIL TOPLAM") or \
               first.upper().startswith("GENEL TOPLAM"):
                continue

            # Course satırları: sol ve/veya sağ blok
            for offset, donem in ((0, left_donem), (7, right_donem)):
                if donem is None:
                    continue
                c = _parse_course_block(cells, offset)
                if not c:
                    continue
                # "Dönem Toplam" satırını ad alanında yakalayabiliriz
                if c["ders_adi"].upper().startswith("DÖNEM TOPLAM"):
                    continue

                yil = (donem - 1) // 2 + 1
                sezon = SEZON.get(donem, "")

                # Unique id (placeholder X kodları için dönem suffix ekle)
                base_id = c["ders_kodu"].replace(" ", "_").replace("*", "")
                cid = f"siyaset_muf_d{donem}_{base_id}"
                idx = 1
                while cid in seen_ids:
                    idx += 1
                    cid = f"siyaset_muf_d{donem}_{base_id}_{idx}"
                seen_ids.add(cid)

                text = (
                    f"{MUFREDAT_YILI} {BOLUM_ADI} müfredatı — "
                    f"{yil}. yıl {sezon} dönemi ({donem}. dönem): "
                    f"{c['ders_kodu']} {c['ders_adi']}. "
                    f"Teorik: {c['teorik'] or '—'}, Lab/Pratik: {c['lab'] or '—'}, "
                    f"Kredi: {c['kredi'] or '—'}, AKTS: {c['akts'] or '—'}. "
                    f"Ön şart: {c['on_sart'] if c['on_sart'] else 'yok'}."
                )
                chunks.append({
                    "id": cid,
                    "text": text,
                    "metadata": {
                        "tip": "mufredat",
                        "mufredat_yili": MUFREDAT_YILI,
                        "donem": donem,
                        "yil": yil,
                        "sezon": sezon,
                        "ders_kodu": c["ders_kodu"],
                        "ders_adi": c["ders_adi"],
                        "on_sart": c["on_sart"],
                        "teorik": c["teorik"],
                        "lab": c["lab"],
                        "kredi": c["kredi"],
                        "akts": c["akts"],
                        "kaynak": CSV_PATH.name,
                        "bolum": BOLUM,
                    },
                })

                short = (
                    f"- {c['ders_kodu']} | {c['ders_adi']} | "
                    f"T:{c['teorik'] or '—'}, P:{c['lab'] or '—'}, "
                    f"Kredi:{c['kredi'] or '—'}, AKTS:{c['akts'] or '—'} | "
                    f"Ön şart: {c['on_sart'] or 'yok'}"
                )
                semester_courses.setdefault(donem, []).append(short)
                semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    # Dönem özet chunk'ları
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {MUFREDAT_YILI} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — "
            f"Toplam {len(lines)} ders:\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"siyaset_muf_sem_d{donem}",
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


def parse_secmeli_csv() -> list[dict]:
    """Seçmeli ders havuzunu işle (Bölüm Dışı Zorunlu, Sınırlı Seçmeli, Bölüm İçi Seçmeli)."""
    if not SECMELI_CSV_PATH.exists():
        print(f"[!] bulunamadı: {SECMELI_CSV_PATH}")
        return []

    chunks: list[dict] = []
    by_kategori: dict[str, list[dict]] = {}
    seen_ids: set[str] = set()

    with SECMELI_CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Header trailing-space fix: "Haftalık Saat "
        fieldnames = {k.strip(): k for k in (reader.fieldnames or [])}

        def g(row: dict, key: str) -> str:
            orig = fieldnames.get(key, key)
            return (row.get(orig) or "").strip()

        for row in reader:
            kategori = g(row, "Kategori")
            kod_raw = g(row, "Ders Kodu")
            ad = g(row, "Ders İsmi")
            saat = g(row, "Haftalık Saat")
            kredi = g(row, "Kredi")
            akts = g(row, "AKTS")

            if not kod_raw or not kategori:
                continue

            ders_kodu = _norm_kod(kod_raw)
            # Eksik bilgi normalize
            ad_n = ad if ad and not ad.startswith("PDF") else NOT_SPECIFIED
            saat_n = saat if saat and not saat.startswith("Belirt") else NOT_SPECIFIED
            kredi_n = kredi if kredi and not kredi.startswith("Belirt") else NOT_SPECIFIED
            akts_n = akts if akts and not akts.startswith("Belirt") else NOT_SPECIFIED

            base_id = ders_kodu.replace(" ", "_")
            cid = f"siyaset_sec_{base_id}"
            idx = 1
            while cid in seen_ids:
                idx += 1
                cid = f"siyaset_sec_{base_id}_{idx}"
            seen_ids.add(cid)

            text = (
                f"{BOLUM_ADI} ({MUFREDAT_YILI}) seçmeli ders havuzu — "
                f"Kategori: {kategori}. Ders: {ders_kodu} {ad_n}. "
                f"Haftalık saat: {saat_n}, Kredi: {kredi_n}, AKTS: {akts_n}. "
                f"Ön şart: yok."
            )
            chunks.append({
                "id": cid,
                "text": text,
                "metadata": {
                    "tip": "secmeli",
                    "kategori": kategori,
                    "mufredat_yili": MUFREDAT_YILI,
                    "ders_kodu": ders_kodu,
                    "ders_adi": ad_n,
                    "haftalik_saat": saat_n,
                    "kredi": kredi_n,
                    "akts": akts_n,
                    "on_sart": "yok",
                    "kaynak": SECMELI_CSV_PATH.name,
                    "bolum": BOLUM,
                },
            })

            by_kategori.setdefault(kategori, []).append({
                "kod": ders_kodu, "ad": ad_n, "kredi": kredi_n, "akts": akts_n,
            })

    # Kategori özet chunk'ları (örn. "Tüm Sınırlı Seçmeli dersler" sorusuna cevap için)
    for kategori, items in by_kategori.items():
        lines = [
            f"- {it['kod']} | {it['ad']} | Kredi: {it['kredi']}, AKTS: {it['akts']}"
            for it in items
        ]
        body = (
            f"{BOLUM_ADI} ({MUFREDAT_YILI}) — {kategori} ders havuzu, "
            f"toplam {len(items)} ders:\n" + "\n".join(lines)
        )
        kat_slug = (
            kategori.lower()
            .replace("ı", "i").replace("ş", "s").replace("ç", "c")
            .replace("ö", "o").replace("ü", "u").replace("ğ", "g")
            .replace(" ", "_")
        )
        chunks.append({
            "id": f"siyaset_sec_ozet_{kat_slug}",
            "text": body[:5000],
            "metadata": {
                "tip": "secmeli_ozet",
                "kategori": kategori,
                "mufredat_yili": MUFREDAT_YILI,
                "ders_sayisi": len(items),
                "kaynak": SECMELI_CSV_PATH.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def parse_katalog() -> list[dict]:
    """SBUI katalog JSON'ından zengin ders içerik + program meta chunk'ları üret."""
    if not KATALOG_PATH.exists():
        print(f"[!] bulunamadı: {KATALOG_PATH}")
        return []

    with KATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    chunks: list[dict] = []

    # ---- Ders içerikleri (her ders için bir chunk) ----
    for c in data.get("ders_katalogu", []):
        kod = c["kod"]
        ad = c.get("ad", "")
        saat = c.get("saat", "")
        kredi = c.get("kredi", "")
        akts = c.get("akts", "")
        yil = c.get("yil")
        donem = c.get("donem", "")
        tip = c.get("tip", "")
        dil = c.get("dil", "Türkçe")
        on_sart = c.get("on_sart", "") or ""
        icerik = c.get("icerik", "")

        on_sart_str = on_sart if on_sart else "yok"
        yil_str = f"{yil}. yıl, " if yil else ""

        text = (
            f"{BOLUM_ADI} ({MUFREDAT_YILI}) ders kataloğu — "
            f"{kod} {ad}. {yil_str}Dönem: {donem}. Tip: {tip}. "
            f"Haftalık saat: {saat}. Kredi: {kredi}. AKTS: {akts}. "
            f"Dersin dili: {dil}. Ön şart: {on_sart_str}. "
            f"İçerik: {icerik}"
        )

        base_id = kod.replace(" ", "_").replace(".", "_")
        chunks.append({
            "id": f"siyaset_katalog_{base_id}",
            "text": text[:5000],
            "metadata": {
                "tip": "ders_icerik",
                "mufredat_yili": MUFREDAT_YILI,
                "ders_kodu": kod,
                "ders_adi": ad,
                "ders_tipi": tip,
                "donem_label": donem,
                "yil": yil if yil else "",
                "haftalik_saat": saat,
                "kredi": kredi,
                "akts": akts,
                "dil": dil,
                "on_sart": on_sart_str,
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    # ---- Program genel bilgi ----
    p = data.get("program", {})
    if p:
        text = (
            f"{p.get('ad', BOLUM_ADI)} ({p.get('kod', 'POLS')}) programı — {p.get('fakulte', '')}. "
            f"Program amacı: {p.get('amac', '')} "
            f"Hedefler: {p.get('hedefler', '')} "
            f"Derece: {p.get('derece', '')}. Süre: {p.get('sure', '')}. "
            f"Toplam ders sayısı: {p.get('ders_sayisi_toplam', 54)}, "
            f"toplam kredi: {p.get('kredi_toplam', 145)}, toplam AKTS: {p.get('akts_toplam', 240)}. "
            f"Düzey: {p.get('duzey', '')}. Eğitim türü: {p.get('egitim_turu', '')}. "
            f"Eğitim temel alanı: {p.get('egitim_temel_alan', '')}. "
            f"Kabul koşulları: {p.get('kabul_kosullari', '')} "
            f"Önceki öğrenmenin tanınması: {p.get('onceki_ogrenmenin_taninmasi', '')} "
            f"Mezuniyet koşulları: {p.get('mezuniyet_kosullari', '')} "
            f"Kariyer ve istihdam: {p.get('kariyer', '')} "
            f"Üst derece programlarına geçiş: {p.get('ust_derece', '')} "
            f"Ölçme ve değerlendirme: {p.get('olcme_degerlendirme', '')}"
        )
        chunks.append({
            "id": "siyaset_program_genel",
            "text": text[:5000],
            "metadata": {
                "tip": "program_genel",
                "mufredat_yili": MUFREDAT_YILI,
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    # ---- Program çıktıları (PO1-PO12) ----
    po_list = data.get("program_ciktilari", [])
    if po_list:
        lines = [f"{x['kod']}: {x['ad']}" for x in po_list]
        text = (
            f"{BOLUM_ADI} programının {len(po_list)} program çıktısı (Program Outcomes, PO): "
            + "; ".join(lines) + ". "
            "Bu çıktılar mezunların kazanacağı temel yetkinlikleri tanımlar."
        )
        chunks.append({
            "id": "siyaset_program_ciktilari",
            "text": text,
            "metadata": {
                "tip": "program_ciktilari",
                "mufredat_yili": MUFREDAT_YILI,
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    # ---- Kurumsal öğrenme çıktıları (IO1-IO7) ----
    io_list = data.get("kurumsal_ciktilar", [])
    if io_list:
        lines = [f"{x['kod']}: {x['ad']}" for x in io_list]
        text = (
            "Abdullah Gül Üniversitesi Kurumsal Öğrenme Çıktıları (Institutional Outcomes, IO) "
            f"{BOLUM_ADI} programı için: " + "; ".join(lines) + "."
        )
        chunks.append({
            "id": "siyaset_kurumsal_ciktilar",
            "text": text,
            "metadata": {
                "tip": "kurumsal_ciktilar",
                "mufredat_yili": MUFREDAT_YILI,
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    # ---- Not sistemi ----
    not_list = data.get("not_sistemi", [])
    if not_list:
        rows = []
        for n in not_list:
            harf = n.get("harf", "")
            kat = n.get("katsayi")
            puan = n.get("puan", "")
            statu = n.get("statu", "")
            kat_str = f"{kat:.2f}" if kat is not None else "—"
            puan_str = puan if puan else "—"
            rows.append(f"{harf} (katsayı: {kat_str}, puan: {puan_str}, statü: {statu})")
        text = (
            f"AGÜ {BOLUM_ADI} not sistemi (AGÜ Lisans Eğitim-Öğretim ve Sınav Yönetmeliği): "
            + "; ".join(rows) + ". "
            "GPA hesabında F (0.00) başarısız sayılır. C- ve altı (1.67-) şartlı geçer; "
            "D+ ve D (1.33 ve 1.00) şartlı geçer. NA devamsızlık nedeniyle kalmayı, "
            "W çekilmeyi, EX muafiyeti gösterir."
        )
        chunks.append({
            "id": "siyaset_not_sistemi",
            "text": text[:5000],
            "metadata": {
                "tip": "not_sistemi",
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    # ---- Mezuniyet şablonu ----
    mez = data.get("mezuniyet_sablonu", [])
    if mez:
        sections = []
        for m in mez:
            kat = m.get("kategori", "")
            ds = m.get("ders_sayisi", "?")
            kr = m.get("kredi", "?")
            akts = m.get("akts", "?")
            dlist = m.get("dersler", [])
            ds_str = f" Dersler: {', '.join(dlist)}." if dlist else ""
            sections.append(f"{kat}: {ds} ders, {kr} kredi, {akts} AKTS.{ds_str}")
        text = (
            f"{BOLUM_ADI} mezuniyet şablonu (toplam 54 ders, 145 kredi, 240 AKTS): "
            + " ".join(sections)
            + " Mezuniyet için GPA en az 2.00 olmalıdır."
        )
        chunks.append({
            "id": "siyaset_mezuniyet_sablonu",
            "text": text[:5000],
            "metadata": {
                "tip": "mezuniyet_sablonu",
                "mufredat_yili": MUFREDAT_YILI,
                "kaynak": "SBUI_Katalog_2025_TR.pdf",
                "bolum": BOLUM,
            },
        })

    return chunks


def make_program_overview() -> dict:
    text = (
        "Abdullah Gül Üniversitesi Siyaset Bilimi ve Uluslararası İlişkiler "
        "(POLS — Political Science and International Relations) lisans programı. "
        "4 yıl süreli, 8 dönemlik program. Bölüm kodu: POLS. "
        "Program; siyaset bilimine giriş (POLS 101, POLS 102), siyasi düşünceler "
        "tarihi (POLS 211), uluslararası ilişkilere giriş (POLS 212), uluslararası "
        "örgütler (POLS 311), karşılaştırmalı hükümet sistemleri (POLS 312), Türk "
        "politikası (POLS 301), Türk siyasi hayatı (POLS 322), Türk Anayasa Hukuku "
        "(POLS 222), araştırma yöntemleri (POLS 201, POLS 202), siyasi teoriler "
        "(POLS 302) ve siyasi ekonomi (POLS 401) gibi temel ve uygulamalı siyaset "
        "bilimi alanlarını kapsar. Program ayrıca mikroekonomi (POLS 121), "
        "makroekonomi (POLS 122), sosyolojiye giriş (SOC 201), modern Türkiye "
        "tarihi (HIST 2XX) gibi destek dersleri içerir. Mezuniyet için POLS 299 "
        "(Yaz Stajı I), POLS 499 (Yaz Stajı II), POLS 420-421 (Bitirme Projesi I-II) "
        "tamamlanmalıdır. Bölüm-içi Seçmeli, Sınırlı Seçmeli, Bölüm Dışı Seçmeli "
        "ve Küresel Seçmeli (GLB) havuzlarından seçmeli dersler alınır. Toplam "
        "mezuniyet kredisi: 147, toplam AKTS: 240."
    )
    return {
        "id": "siyaset_program_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "kaynak": "program_tanitim",
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_csv()
    chunks.extend(parse_secmeli_csv())
    chunks.extend(parse_katalog())
    chunks.append(make_program_overview())
    out_path = OUT / "chunks_siyaset.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} siyaset chunk -> {out_path}")
    by_tip: dict[str, int] = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

"""
AGÜ Mimarlık Bölümü Ders Kataloğu ingest.
Kaynak: AGUarch_Course-Catalogues.pdf (160 sayfa)
Format: "DERS BİLGİLERİ" başlıklı bloklar — her ders için Kodu/İsmi/Haftalık Saat/
Kredi/AKTS/Seviye/Dil/Tip/Ön Şart/İçerik alanları.

Her ders için iki chunk üretilir:
  - tip="mufredat"   : kısa müfredat satırı (liste modunda kullanılır)
  - tip="ders_katalog": detaylı ders kartı (içerik + bağlam)

Çıktı: data/processed/chunks_mimarlik.jsonl
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

PDF = RAW / "AGU_Mimarlik_Course_Catalogues.pdf"
BOLUM = "mimarlik"
BOLUM_ADI = "Mimarlık"
MUFREDAT_YILI = "2025"  # tek aktif müfredat

# DERS BİLGİLERİ blokları — her bir ders için ayrı bir başlık
DERS_HEADER_RE = re.compile(r"DERS\s+B[İI]LG[İI]LER[İI]")

# Alan parser'ları (her satır "Etiket Değer" formatında)
FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "kod": re.compile(r"^Kodu\s+(.+)$", re.MULTILINE),
    "ad": re.compile(r"^[İI]smi\s+(.+)$", re.MULTILINE),
    "saat": re.compile(r"^Haftal[ıi]k\s+Saati\s+(.+)$", re.MULTILINE),
    "kredi": re.compile(r"^Kredi\s+(.+)$", re.MULTILINE),
    "akts": re.compile(r"^AKTS\s+(.+)$", re.MULTILINE),
    "seviye": re.compile(r"^Seviye/Y[ıi]l\s+(.+)$", re.MULTILINE),
    "dil": re.compile(r"^Dersin\s+Dili\s+(.+)$", re.MULTILINE),
    "tip": re.compile(r"^Tip\s+(.+)$", re.MULTILINE),
    "on_sart": re.compile(r"^[ÖO]n\s+[ŞS]art\s+(.+)$", re.MULTILINE),
}

# İçerik bloğu — "İçerik" satırından sonraki bütün metni al, "AGU Department"
# veya "DERS BİLGİLERİ" gibi bir başlığa kadar
ICERIK_RE = re.compile(
    r"[İI]çerik\s+(.+?)(?=\n\s*(?:AGU\s+Department|DERS\s+B[İI]LG[İI]LER|COURSE\s+CONTENT|Topic\s+Objectives|\Z))",
    re.DOTALL,
)


def _norm_kod(raw: str) -> str:
    """ARCH101 / ARCH 101 / arch101 → 'ARCH 101'."""
    s = re.sub(r"\s+", "", raw or "").upper()
    m = re.match(r"^([A-Z]+)(\d+)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError, AttributeError):
        return default


def _donem_from_code(kod: str) -> int:
    """ARCH XYZ → dönem tahmini: yıl=X, sezon = (Z tek?güz:bahar) → donem = (X-1)*2 + offset.
    Örnek: ARCH101→1, ARCH102→2, ARCH223→3, ARCH224→4, ARCH301→5, ARCH402→8.
    Üretilemiyorsa 99 döner (sıralama için)."""
    m = re.match(r"^[A-Z]+\s*(\d{3})$", kod)
    if not m:
        return 99
    num = m.group(1)
    yil = int(num[0])
    son = int(num[-1])
    if not (1 <= yil <= 4):
        return 99
    offset = 1 if (son % 2 == 1) else 2
    return (yil - 1) * 2 + offset


def _extract_field(block: str, key: str) -> str:
    pat = FIELD_PATTERNS.get(key)
    if not pat:
        return ""
    m = pat.search(block)
    return m.group(1).strip() if m else ""


def parse_courses() -> list[dict]:
    if not PDF.exists():
        print(f"[!] bulunamadı: {PDF}")
        return []

    with pdfplumber.open(PDF) as pdf:
        full = "\n".join((p.extract_text() or "") for p in pdf.pages)

    # "DERS BİLGİLERİ" başlıklarına göre blokları çıkar
    headers = list(DERS_HEADER_RE.finditer(full))
    if not headers:
        print("[!] DERS BİLGİLERİ başlığı bulunamadı.")
        return []

    chunks: list[dict] = []
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    seen_codes: set[str] = set()

    for i, h in enumerate(headers):
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(full)
        block = full[start:end].strip()

        kod_raw = _extract_field(block, "kod")
        if not kod_raw:
            continue
        kod = _norm_kod(kod_raw)
        if kod in seen_codes:
            continue
        seen_codes.add(kod)

        ad = _extract_field(block, "ad")
        saat = _extract_field(block, "saat")
        kredi_str = _extract_field(block, "kredi")
        akts_str = _extract_field(block, "akts")
        seviye = _extract_field(block, "seviye")
        dil = _extract_field(block, "dil")
        tip = _extract_field(block, "tip")
        on_sart = _extract_field(block, "on_sart").strip().strip("-").strip()

        icerik_m = ICERIK_RE.search(block)
        icerik = (icerik_m.group(1).strip() if icerik_m else "")
        # İçerik içinde fazla newline/whitespace temizle
        icerik = re.sub(r"\s+", " ", icerik).strip()

        donem = _donem_from_code(kod)
        yil = (donem - 1) // 2 + 1 if donem != 99 else 0
        sezon = "Güz" if donem in (1, 3, 5, 7) else ("Bahar" if donem in (2, 4, 6, 8) else "")

        # Saat alanından T/L/U çıkar (örn. "12 (6+6)" veya "3 (2+1)")
        teorik = ""
        lab = ""
        m = re.search(r"\((\d+)\s*\+\s*(\d+)\)", saat)
        if m:
            teorik, lab = m.group(1), m.group(2)

        is_zorunlu = (tip or "").strip().lower().startswith("zorunlu")

        # ----- 1a) Yalnız ZORUNLU dersler için müfredat satırı (liste modunda kullanılır) -----
        # Seçmeli dersler havuz dersi olduğu için müfredat satırına alınmaz; havuz
        # placeholder'ları ayrıca eklenir (aşağıda ELECTIVE_SLOTS kullanarak).
        if is_zorunlu and donem != 99:
            muf_text = (
                f"{MUFREDAT_YILI} {BOLUM_ADI} müfredatı — "
                f"{yil}. yıl {sezon} dönemi ({donem}. dönem): {kod} {ad}. "
                f"Haftalık saat: {saat or '—'} (T:{teorik or '—'}, L:{lab or '—'}), "
                f"Kredi: {kredi_str or '—'}, AKTS: {akts_str or '—'}. "
                f"Tip: Zorunlu, Dil: {dil or '—'}. "
                f"Ön şart: {on_sart if on_sart else 'yok'}."
            )
            chunks.append({
                "id": f"mimarlik_muf_{kod.replace(' ', '')}",
                "text": muf_text,
                "metadata": {
                    "tip": "mufredat",
                    "mufredat_yili": MUFREDAT_YILI,
                    "donem": donem,
                    "yil": yil,
                    "sezon": sezon,
                    "ders_kodu": kod,
                    "ders_adi": ad,
                    "on_sart": on_sart,
                    "teorik": teorik,
                    "lab": lab,
                    "kredi": kredi_str,
                    "akts": akts_str,
                    "ders_tipi": "Zorunlu",
                    "dil": dil,
                    "kaynak": PDF.name,
                    "bolum": BOLUM,
                },
            })
        # NOT: Seçmeli derslerin havuz listesi artık mimarlik_secmeli.csv üzerinden
        # ingest_mimarlik_secmeli.py tarafından üretiliyor. Burada sadece ders_katalog
        # chunk'ı (aşağıda) üretilir — detay sorguları için PDF içeriği korunur.

        # ----- 2) Detaylı katalog chunk'ı (içerik + diğer bilgiler) -----
        kat_text = (
            f"AGÜ Mimarlık Bölümü — Ders Kataloğu: {kod} {ad}.\n"
            f"Haftalık saat: {saat or '—'}, Kredi: {kredi_str or '—'}, AKTS: {akts_str or '—'}, "
            f"Seviye/Yıl: {seviye or '—'}, Dil: {dil or '—'}, Tip: {tip or '—'}, "
            f"Ön şart: {on_sart if on_sart else 'yok'}.\n\n"
            f"İçerik:\n{icerik or '(içerik bilgisi PDFden çıkarılamadı)'}"
        )
        chunks.append({
            "id": f"mimarlik_kat_{kod.replace(' ', '')}",
            "text": kat_text[:4500],
            "metadata": {
                "tip": "ders_katalog",
                "ders_kodu": kod,
                "ders_adi": ad,
                "ders_tipi": tip,
                "seviye": seviye,
                "dil": dil,
                "on_sart": on_sart,
                "kredi": kredi_str,
                "akts": akts_str,
                "kaynak": PDF.name,
                "bolum": BOLUM,
            },
        })

        # Dönem özetleri SADECE Zorunlu'lardan oluşur
        if is_zorunlu and donem != 99:
            short = (
                f"- {kod} | {ad} | T:{teorik or '—'}, L:{lab or '—'}, "
                f"Kredi:{kredi_str or '—'}, AKTS:{akts_str or '—'} | "
                f"Zorunlu | Ön şart: {on_sart or 'yok'}"
            )
            semester_courses.setdefault(donem, []).append(short)
            semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    # ----- 3) Her dönem için seçmeli havuz placeholder'ları (resmi müfredat tablosuna göre) -----
    # AGÜ Mimarlık programının tipik yapısı: 1.-2. yıl ağırlıklı zorunlu;
    # 3. ve 4. yılda seçmeli havuzlardan ders seçimi
    ELECTIVE_SLOTS: dict[int, list[tuple[str, str, int, int]]] = {
        # donem -> [(placeholder_kod, açıklama, kredi, akts), ...]
        1: [("GLB1XX", "Global Issues Elective", 3, 4)],
        2: [("GLB1XX", "Global Issues Elective", 3, 4)],
        3: [("HISTXXX", "History of Turkey Pool", 2, 2)],
        4: [("HISTXXX", "History of Turkey Pool", 2, 2)],
        5: [
            ("GLB3XX", "Global Issues Elective", 3, 4),
            ("ARCGXXX", "Elective (I) — ARCG havuzu", 2, 3),
            ("ARCDXXX", "Elective (II) — ARCD havuzu", 2, 3),
            ("HISTXXX", "History of Turkey Pool", 2, 2),
        ],
        6: [
            ("ARCGXXX", "Elective (I) — ARCG havuzu", 2, 3),
            ("ARCDXXX", "Elective (II) — ARCD havuzu", 2, 3),
            ("HISTXXX", "History of Turkey Pool", 2, 2),
        ],
        7: [
            ("ARCDXXX", "Elective — ARCD havuzu", 2, 3),
            ("ARCGXXX", "Elective — ARCG havuzu", 2, 3),
        ],
        8: [
            ("ARCDXXX", "Elective — ARCD havuzu", 2, 3),
            ("ARCGXXX", "Elective — ARCG havuzu", 2, 3),
        ],
    }

    for donem, slots in ELECTIVE_SLOTS.items():
        for kod_p, ad_p, kredi_p, akts_p in slots:
            yil_p = (donem - 1) // 2 + 1
            sezon_p = "Güz" if donem % 2 == 1 else "Bahar"
            text_p = (
                f"{MUFREDAT_YILI} {BOLUM_ADI} müfredatı — "
                f"{yil_p}. yıl {sezon_p} dönemi ({donem}. dönem): {kod_p} {ad_p} "
                f"(seçmeli havuzdan bir ders seçilir). Kredi: {kredi_p}, AKTS: {akts_p}."
            )
            # Aynı dönemde aynı placeholder kodundan birden fazla varsa benzersizleştir
            existing = sum(
                1 for c in chunks
                if c["metadata"].get("tip") == "mufredat"
                and c["metadata"].get("donem") == donem
                and c["metadata"].get("ders_kodu", "").startswith(kod_p)
            )
            uniq_kod = f"{kod_p}-{existing + 1}" if existing > 0 else kod_p
            chunks.append({
                "id": f"mimarlik_muf_d{donem}_slot_{uniq_kod.replace(' ', '_')}",
                "text": text_p,
                "metadata": {
                    "tip": "mufredat",
                    "mufredat_yili": MUFREDAT_YILI,
                    "donem": donem,
                    "yil": yil_p,
                    "sezon": sezon_p,
                    "ders_kodu": uniq_kod,
                    "ders_adi": ad_p,
                    "on_sart": "",
                    "teorik": "",
                    "lab": "",
                    "kredi": str(kredi_p),
                    "akts": str(akts_p),
                    "ders_tipi": "Seçmeli (havuz)",
                    "dil": "İngilizce",
                    "kaynak": "müfredat_yapı_tahmini",
                    "bolum": BOLUM,
                },
            })
            short_p = (
                f"- {uniq_kod} | {ad_p} | "
                f"Kredi:{kredi_p}, AKTS:{akts_p} | Seçmeli havuz"
            )
            semester_courses.setdefault(donem, []).append(short_p)
            semester_meta.setdefault(donem, {"yil": yil_p, "sezon": sezon_p})

    # NOT: Seçmeli havuz özet chunk'ları artık ingest_mimarlik_secmeli.py
    # tarafından mimarlik_secmeli.csv'den üretiliyor.

    # ----- 5) Dönem özet chunk'ları (zorunlu + havuz placeholder) -----
    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {MUFREDAT_YILI} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — "
            f"Toplam {len(lines)} ders:\n" + "\n".join(lines)
        )
        chunks.append({
            "id": f"mimarlik_muf_sem_d{donem}",
            "text": body[:5000],
            "metadata": {
                "tip": "donem_ozet",
                "mufredat_yili": MUFREDAT_YILI,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": PDF.name,
                "bolum": BOLUM,
            },
        })

    return chunks


def make_program_overview() -> dict:
    text = (
        "Abdullah Gül Üniversitesi Mimarlık Fakültesi — Mimarlık Bölümü (ARCH) "
        "lisans programı. 4 yıl süreli, 8 dönemlik program. Eğitim dili İngilizce. "
        "Tasarım stüdyosu (ARCH101, ARCH102, ARCH201, ...) her dönemin omurgasıdır. "
        "Strüktür, mimarlık tarihi, malzeme, çevre kontrolü, şehir/peyzaj, dijital "
        "araçlar gibi destekleyici alanlardan dersler içerir. Bölüm kodu: ARCH. "
        "Mezuniyet için tüm zorunlu dersler + seçmeliler ve diploma projesi tamamlanır."
    )
    return {
        "id": "mimarlik_program_overview",
        "text": text,
        "metadata": {
            "tip": "program_bilgi",
            "kaynak": "program_tanitim",
            "bolum": BOLUM,
        },
    }


def main():
    chunks = parse_courses()
    chunks.append(make_program_overview())
    out_path = OUT / "chunks_mimarlik.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"[OK] {len(chunks)} mimarlik chunk -> {out_path}")
    # Özetle
    by_tip = {}
    for c in chunks:
        t = c["metadata"]["tip"]
        by_tip[t] = by_tip.get(t, 0) + 1
    for t, n in by_tip.items():
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

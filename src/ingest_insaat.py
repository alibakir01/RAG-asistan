"""
İnşaat Mühendisliği (Civil Engineering / CE) ingest modülü.
Çıktı: data/processed/chunks_insaat.jsonl
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

BOLUM = "insaat"
BOLUM_ADI = "İnşaat Mühendisliği"

SEZON_BY_DONEM = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar", 5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}

# 2016: 2016-2020 girişliler | 2021: 2021-2024 girişliler | 2025: 2025+ girişliler
MUFREDAT_CSV = {
    "2016": "ce_2016_2020_temiz.csv",
    "2021": "ce_2021_2024_temiz.csv",
    "2025": "ce_2025_temiz.csv",
}

# Ek referans PDF'leri — müfredatla ilgili kapsamlı bilgi
REF_PDFS = {
    "2016": "CE_Curriculum_2016.pdf",
    "2021": "CE_Curriculum_2021.pdf",
    "2025": "CE_Curriculum_2025.pdf",
}

# Ders kataloğu PDF (tüm müfredatlar için ortak)
COURSE_CATALOGUE_PDF = "CE_Course_Catalogue.pdf"


def parse_mufredat_csv(path: Path, mufredat_yili: str):
    semester_courses: dict[int, list[str]] = {}
    semester_meta: dict[int, dict] = {}
    chunks = []

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for ri, row in enumerate(reader, start=1):
            try:
                donem = int(str(row.get("Dönem", "")).strip())
            except (ValueError, TypeError):
                continue
            kod = (row.get("Ders Kodu") or "").strip()
            ad = (row.get("Ders Adı") or "").strip()
            on = (row.get("Ön Şart") or "").strip().strip("-").strip()
            t = (row.get("Teorik") or "").strip()
            l = (row.get("Lab.") or row.get("Lab") or "").strip()
            k = (row.get("Kredi") or "").strip()
            a = (row.get("AKTS") or "").strip()
            if not ad:
                continue
            if kod in ("-", ""):
                kod = "CE-ELEC"

            yil = (donem - 1) // 2 + 1
            sezon = SEZON_BY_DONEM.get(donem, "")
            text = (
                f"{mufredat_yili} {BOLUM_ADI} müfredatı — {yil}. yıl {sezon} dönemi "
                f"({donem}. dönem): {kod} {ad}. "
                f"Teorik: {t or '—'}, Lab: {l or '—'}, Kredi: {k or '—'}, AKTS: {a or '—'}. "
                f"Ön şart: {on if on else 'yok'}."
            )
            chunks.append({
                "id": f"ce_muf_{mufredat_yili}_d{donem}_r{ri}_{kod.replace(' ','')}",
                "text": text,
                "metadata": {
                    "tip": "mufredat",
                    "mufredat_yili": mufredat_yili,
                    "donem": donem,
                    "yil": yil,
                    "sezon": sezon,
                    "ders_kodu": kod,
                    "ders_adi": ad,
                    "on_sart": on,
                    "teorik": t,
                    "lab": l,
                    "kredi": k,
                    "akts": a,
                    "kaynak": path.name,
                    "bolum": BOLUM,
                },
            })

            short = (
                f"- {kod} | {ad} | T:{t or '—'}, L:{l or '—'}, "
                f"Kredi:{k or '—'}, AKTS:{a or '—'} | Ön şart: {on or 'yok'}"
            )
            semester_courses.setdefault(donem, []).append(short)
            semester_meta.setdefault(donem, {"yil": yil, "sezon": sezon})

    for donem, lines in sorted(semester_courses.items()):
        meta = semester_meta[donem]
        body = (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — "
            f"{meta['yil']}. sınıf {meta['sezon']} yarıyılı ({donem}. dönem) — Toplam {len(lines)} ders:\n"
            + "\n".join(lines)
        )
        chunks.append({
            "id": f"ce_muf_{mufredat_yili}_sem_summary_d{donem}",
            "text": body,
            "metadata": {
                "tip": "donem_ozet",
                "mufredat_yili": mufredat_yili,
                "donem": donem,
                "yil": meta["yil"],
                "sezon": meta["sezon"],
                "ders_sayisi": len(lines),
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


def parse_pdf_reference(path: Path, mufredat_yili: str):
    """PDF'deki ek bilgileri (seçmeli listeleri, açıklayıcı notlar vb.) chunk'la."""
    chunks = []
    if not path.exists():
        return chunks
    try:
        with pdfplumber.open(path) as pdf:
            full = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return chunks

    # Sayfa başlıklarına göre değil, bloklara göre böl (her ~25 satır)
    lines = [l.strip() for l in full.split("\n") if l.strip()]
    block, blocks = [], []
    for ln in lines:
        block.append(ln)
        if len(block) >= 25:
            blocks.append(" ".join(block))
            block = []
    if block:
        blocks.append(" ".join(block))

    for i, body in enumerate(blocks):
        text = (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Referans Belgesi (Bölüm {i+1}):\n{body}"
        )
        chunks.append({
            "id": f"ce_pdfref_{mufredat_yili}_b{i+1}",
            "text": text[:3500],
            "metadata": {
                "tip": "mufredat_referans",
                "mufredat_yili": mufredat_yili,
                "bolum_no": i + 1,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


CATALOGUE_CODE_RE = re.compile(r"^Code\s+([A-Z]{2,5}\s*\d{2,4})\s*$", re.MULTILINE)


def parse_course_catalogue(path: Path):
    """CE Course Record Catalogue: 'Code CE XXX' blokları ile bölünmüş ders detay PDF'i."""
    chunks = []
    if not path.exists():
        return chunks
    try:
        with pdfplumber.open(path) as pdf:
            full = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return chunks

    # 'Code XXX YYY' başlıklarını yakala, blokları çıkar
    matches = list(CATALOGUE_CODE_RE.finditer(full))
    if not matches:
        return chunks

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        block = full[start:end].strip()
        kod = m.group(1).strip()

        # İçindeki alanları parse et
        def _field(name: str) -> str:
            mm = re.search(rf"^{name}\s+(.+)$", block, re.MULTILINE)
            return mm.group(1).strip() if mm else ""

        ders_adi = _field("Name")
        sezon_yil = _field("Semester")
        on_sart = _field("Prerequisites")
        ders_tipi = _field("Type")
        akts = _field("ECTS")
        kredi = _field("Credit")

        text = (
            f"İnşaat Mühendisliği — Ders Kataloğu: {kod} {ders_adi}.\n"
            f"Tip: {ders_tipi or '—'}, Dönem/Sezon: {sezon_yil or '—'}, "
            f"Kredi: {kredi or '—'}, AKTS: {akts or '—'}, "
            f"Ön şart: {on_sart if on_sart and on_sart != '-' else 'yok'}.\n\n"
            f"{block}"
        )
        chunks.append({
            "id": f"ce_kat_{kod.replace(' ','')}",
            "text": text[:4000],
            "metadata": {
                "tip": "ders_katalog",
                "ders_kodu": kod,
                "ders_adi": ders_adi,
                "ders_tipi": ders_tipi,
                "sezon_yil": sezon_yil,
                "on_sart": on_sart,
                "kredi": kredi,
                "akts": akts,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


# İnşaat Mühendisliği Staj ve Uygulamalı Eğitim Yönergesi MADDE'leri
CE_STAJ_MADDELERI = [
    ("1", "Amaç", "Bu Yönergenin amacı; AGÜ Mühendislik Fakültesi İnşaat Mühendisliği Bölümü "
          "öğrencileri tarafından gerçekleştirilmesi gereken uygulamalı eğitimlerin temel ilkelerinin; "
          "planlama, uygulama ve değerlendirmesine ilişkin usul ve esasları düzenlemektir."),
    ("2", "Kapsam", "Bu Yönerge AGÜ Mühendislik Fakültesi İnşaat Mühendisliği Bölümü'nde "
          "gerçekleştirilmesi gereken uygulamalı eğitimlerin uygulanmasına ilişkin hükümleri kapsar."),
    ("3", "Dayanak", "Yönerge, 18/04/2022 tarih ve 31813 sayılı RG'de yayımlanan 'AGÜ Lisans Eğitim, "
          "Öğretim ve Sınav Yönetmeliği'nin 8. Maddesi ile 17/06/2021 tarih ve 31514 sayılı RG'de "
          "yayımlanan 'Yükseköğretimde Uygulamalı Eğitimler Çerçeve Yönetmeliği'ne dayanılarak "
          "hazırlanmıştır."),
    ("4", "Tanımlar",
        "CE 300 SUMMER PRACTICE: Öğrencilerin alması zorunlu olan ve teorik bilgiyi iş yeri/laboratuvar "
        "ortamında uygulamasını sağlayan staj dersi. "
        "CE 404 WORKPLACE EXPERIENCE: İş yeri deneyimi olarak alınan, mühendislik tasarım ve "
        "uygulamaları + proje geliştirme/yönetim + endüstriyel inovasyon çalışmalarına katılım "
        "sağlayan, bir dönem boyunca süren uygulamalı ders. "
        "Bölüm Uygulamalı Eğitim Komisyonu: İnşaat Müh. Bölümü Uygulamalı Eğitim Komisyonu (staj "
        "komisyonunun adı). "
        "Uygulamalı Eğitim Danışmanı: Her öğrencinin sürecini takip eden bölüm öğretim üyesi. "
        "İsteğe bağlı staj: CE 300'e geçerli minimum 30 iş günü stajı tamamlandıktan sonra yapılan staj. "
        "İş günü: Devlet kurumunda Pzt-Cuma; özel şirkette firmanın çalışma günleri."),
    ("5", "Bölüm Komisyonu ve Danışmanın Görev ve Yetkileri",
        "(a) Uygulamalı eğitim koordinasyonu ve değerlendirilmesi Bölüm Komisyonu tarafından yapılır. "
        "(b) Komisyon iş yeri ve zaman uygunluğuna karar verir. "
        "(c) Danışmanlar raporu değerlendirir, beklenmedik durumlarda Komisyonla birlikte karar alır. "
        "(d) Danışmanlar gerekli görmezse raporu kabul etmeyebilir. "
        "(e) Öğrenciler işletmedeyken Yükseköğretim Kurumları Öğrenci Disiplin Yönetmeliği'ne ve "
        "işletmenin çalışma kurallarına tabidir. "
        "(f) Komisyon üyeleri/öğretim elemanları staj yerlerini ziyaret edebilir; öğrenci yerinde yoksa "
        "tutanakla bildirilir."),
    ("6", "Uygulamalı Eğitimin Amacı",
        "İnşaat Müh. lisans programındaki zorunlu uygulamalı eğitim derslerinin amacı; öğrencilerin "
        "yurt içi/dışı kamu, özel sektör veya STK'larda alanları ile ilgili uygulamalı çalışmalara "
        "katılarak teorik bilgilerin uygulamasını öğrenmeleri ve beceri-deneyim sahibi olmalarıdır."),
    ("7", "Bölüm Uygulamalı Eğitim Komisyonu (Yapısı)",
        "(a) Öğrencilerin uygulamalı eğitim çalışmaları Komisyon tarafından yürütülür. "
        "(b) Komisyon üyeleri 2 yıl için Bölüm Başkanı tarafından seçilir; süresi dolan üye tekrar "
        "seçilebilir. "
        "(c) Komisyon oy çokluğu ile karar alır."),
    ("8", "Staj ve Uygulamalı Derslerin Süreleri ve Alma Şartları",
        "(a) CE 300 SUMMER PRACTICE: 30 iş günü staj zorunludur. Tamamı şantiyede veya gerekli "
        "nitelikleri taşıyan laboratuvarlarda yapılabilir. "
        "(b) CE 404 WORKPLACE EXPERIENCE: Minimum 1 yarıyıl. Devam zorunluluğu %90. CE 404 ile "
        "BİRLİKTE çevrimiçi (online) dersler dışında ders alınamaz. "
        "(c) Ön şart AKTS: CE 300 için en az 90 AKTS, CE 404 için en az 195 AKTS başarılı olmalı. "
        "(d) CE 300 kapsamında tek seferde en az 20 iş günü staj yapılabilir. "
        "(e) Staj eğitim-öğretim dönemi, yaz okulu ve genel sınav dönemlerinde de yapılabilir "
        "(haftalık 3 günden az olmamak şartıyla, aynı süreli olarak). "
        "(f) Fiilen çalışılan gün sayısı esastır. "
        "(g-ı) Mücbir sebep, sağlık, işletme aksaklığı durumlarında Komisyon karar verir."),
    ("9", "Uygulamalı Eğitimin Yeri",
        "(a) Öğrenci yerini kendi imkânlarıyla bulur; uygunluğa Komisyon karar verir. "
        "(b) Komisyon onayıyla zorunlu staj üniversite laboratuvarlarında yapılabilir. "
        "(c) Staj yerinde 'inşaat mühendisi' ünvanına sahip en az bir mühendis bulunmalıdır. "
        "(d) Öğrenci kabul aldıktan sonra ilgili inşaat mühendisi tarafından doldurulan başvuru "
        "formunu Komisyona teslim edip onay alır. "
        "(e) Yerin uygunluğundan öğrenci sorumludur; sonradan uygunsuz çıkarsa staj geçersiz sayılır. "
        "(f) Dönem içinde işin durması halinde öğrenci şirket değiştirebilir; başvuru evrakları yeniden "
        "doldurulup teslim edilir. Şirket değişikliği dönem içinde 1 kez yapılabilir. "
        "(g) Onaylanan yer dışında başka bir yerde staj yapılamaz. "
        "(ı) Yurtdışı stajları IAESTE, ERASMUS, AIESEC veya kendi imkânlarıyla yapılabilir; "
        "eşdeğerliğe Komisyon karar verir."),
    ("10", "Çift Ana Dal, Yatay/Dikey Geçişlerde Staj Geçerliliği",
        "(a) Çift ana dal yapan öğrencilerin stajının İnşaat Müh. programında geçerliliğine Komisyon "
        "karar verir. "
        "(b) Stajın her iki dalda sayılması için staja başlamadan önce her iki Komisyonun da onayı "
        "gerekir. "
        "(c) Yatay/dikey geçişle gelen öğrencilerin önceki stajları belgelendirilirse Fakülte Yönetim "
        "Kurulu karar verir. "
        "(d) Meslek lisesi sonrası kamu/özel kurumlarda çalışma günleri staj olarak kabul edilmez."),
    ("11", "Uygulamalı Eğitimlerde Uyulması Gereken Kurallar",
        "(a) Öğrenci iş düzeni, çalışma saatleri, iş sağlığı ve güvenliği konularında iş yeri "
        "kurallarına uymak zorundadır. "
        "(b) Sosyal güvenlik primi Üniversite tarafından ödenir. "
        "(c) Sigortalama için Uygulamalı Eğitim Başvuru Formu, uygulamalı eğitim başlangıcından 1 ay "
        "kadar önce bölüm sekreterliğine teslim edilmelidir. "
        "(e) Engel olmayan kural ihlalleri raporla Dekanlığa bildirilir; engel teşkil edenler için "
        "öğrenci işten uzaklaştırılır ve disiplin yönetmeliği uygulanabilir. "
        "(f-g) Öğrenci alet/malzeme/araçları özenle kullanmalıdır; verecekleri zararlardan Üniversite "
        "sorumlu değildir."),
    ("12", "Uygulamalı Eğitim Mazereti",
        "CE 300 (staj): Mücbir sebep/haklı mazeretle izin kullanan öğrenci eksik süreyi aynı/gelecek "
        "yıl aynı veya Komisyonun uygun gördüğü başka iş yerinde tamamlar. Mazeret izni 10 günü "
        "geçerse o dönemki staj bütünüyle tekrar ettirilir. İzinsiz terk edenler de aynı hükme tabidir. "
        "CE 404 (uygulamalı ders): Komisyon onayıyla öğrenci dönem içinde firmayı 1 kez "
        "değiştirebilir."),
    ("13", "Staj Dersi Raporu",
        "Staj raporunun her sayfası stajyerden sorumlu mühendis tarafından imzalanıp kaşelenir. "
        "Bölüm formatına uygun yazılan ve onaylanan rapor, akademik takvimdeki ders ekleme-bırakma "
        "tarihlerinin ilk gününe kadar imzalı kapalı zarftaki staj değerlendirme raporuyla birlikte "
        "Komisyona teslim edilir. Sonra teslim edilen kabul edilmez ve staj başarısız sayılır."),
    ("14", "Değerlendirme",
        "(b) Değerlendirme kriterleri her dönem başında Komisyon tarafından Ders İzlencelerinde "
        "belirtilir. "
        "(c) İsteğe bağlı staj için kredi talep edilemez. "
        "(d) CE 300: Raporlar değerlendirildikten sonra harf notu veya başarılı/başarısız notu verilir. "
        "(e) CE 404: Haftalık raporlar + ara dönem raporu/sunumu + final raporu/sunumu dersin hocası "
        "ve Komisyon değerlendirmesiyle harf notu olarak verilir. "
        "(f-h) Gerek görülürse öğrenci mülakata çağrılır; mülakatlar Komisyonun belirlediği jürilerce "
        "yapılır."),
    ("15", "Hüküm Bulunmayan Haller",
        "Yönergede belirtilmeyen hususlarda değerlendirme/karar yetkisi ilgili mevzuat hükümleri "
        "çerçevesinde Bölüm Uygulamalı Eğitim Komisyonuna aittir."),
    ("16", "Yürürlük", "Bu Yönerge AGÜ Senatosu tarafından onaylandığı tarihten itibaren yürürlüğe girer."),
    ("17", "Yürütme", "Bu Yönerge hükümlerini AGÜ Mühendislik Fakültesi Dekanı yürütür."),
]


def make_ce_staj_chunks():
    chunks = []
    for no, baslik, body in CE_STAJ_MADDELERI:
        text = (
            f"İnşaat Mühendisliği Staj ve Uygulamalı Eğitim Yönergesi — MADDE {no} ({baslik}):\n{body}"
        )
        chunks.append({
            "id": f"ce_staj_madde_{no}",
            "text": text,
            "metadata": {
                "tip": "staj_yonerge",
                "madde_no": int(no),
                "baslik": baslik,
                "kaynak": "CE_Staj_Uygulamali_Egitim_Yonergesi.pdf",
                "bolum": BOLUM,
            },
        })
    return chunks


def main():
    all_chunks = []

    for yil, fn in MUFREDAT_CSV.items():
        p = RAW / fn
        if not p.exists():
            print(f"[!] bulunamadı: {p.name}")
            continue
        chs = parse_mufredat_csv(p, yil)
        all_chunks.extend(chs)
        print(f"[CE müfredat {yil}] {len(chs)} chunk")

        if yil in REF_PDFS:
            p2 = RAW / REF_PDFS[yil]
            ref_chs = parse_pdf_reference(p2, yil)
            all_chunks.extend(ref_chs)
            print(f"[CE PDF referans {yil}] {len(ref_chs)} chunk")

    # Ders kataloğu (tüm müfredatlar için ortak)
    cat_path = RAW / COURSE_CATALOGUE_PDF
    if cat_path.exists():
        cat_chs = parse_course_catalogue(cat_path)
        all_chunks.extend(cat_chs)
        print(f"[CE ders kataloğu] {len(cat_chs)} chunk")

    # Staj yönergesi (tüm müfredatlar için ortak)
    staj_chs = make_ce_staj_chunks()
    all_chunks.extend(staj_chs)
    print(f"[CE staj yönergesi] {len(staj_chs)} chunk")

    out_path = OUT / "chunks_insaat.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"\n[OK] Toplam {len(all_chunks)} insaat chunk -> {out_path}")


if __name__ == "__main__":
    main()

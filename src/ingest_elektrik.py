"""
Elektrik-Elektronik Mühendisliği (EE) ingest modülü.
Çıktı: data/processed/chunks_elektrik.jsonl
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

BOLUM = "elektrik"
BOLUM_ADI = "Elektrik-Elektronik Mühendisliği"

SEZON_BY_DONEM = {1: "Güz", 2: "Bahar", 3: "Güz", 4: "Bahar", 5: "Güz", 6: "Bahar", 7: "Güz", 8: "Bahar"}

MUFREDAT_CSV = {
    # 2019: 2019-2020 girişliler (Capsule 2019 programı)
    # 2021: 2021-2024 girişliler (Capsule 2021 programı)
    # 2025: 2025+ girişliler (yeni program)
    "2019": "ee_2019_2020_temiz.csv",
    "2021": "ee_2021_2024_temiz.csv",
    "2025": "ee_2025_temiz.csv",
}

# Müfredat yılına özel kapsül CSV'leri (CSV'de yoksa hardcoded ELECTIVE_CAPSULES kullanılır)
CAPSULES_CSV = {
    "2021": "ee_2021_2024_capsules.csv",
}

# PDF'ten alınmış Elective Capsules (Seçmeli Kapsüller) — 10 ECTS each
ELECTIVE_CAPSULES = [
    ("EE 3001", "Telecommunication System Design with DSP Capsule", "EE 204", 10),
    ("EE 3002", "Embedded Control Systems Design Capsule", "EE 203, EE 204", 10),
    ("EE 3003", "Sensor System Design Capsule", "EE 206", 10),
    ("EE 3004", "Optical System Design Capsule", "EE 205", 10),
    ("EE 3005", "Biomedical System Design Capsule", "Consent (Bölüm onayı)", 10),
    ("EE 3006", "Electromechanical Energy Conversion System Design Capsule", "EE 202, EE 205", 10),
    ("EE 4001", "High Frequency System Design Capsule", "EE 205", 10),
    ("EE 4002", "Robotic System Design Capsule", "EE 3002, MATH 103", 10),
    ("EE 4003", "Power Electronics Motor Drives Design Capsule", "EE 206, EE 205", 10),
    ("EE 4004", "Power System Analysis Capsule", "EE 202, EE 3006", 10),
]


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
                kod = "EE-ELEC"

            yil = (donem - 1) // 2 + 1
            sezon = SEZON_BY_DONEM.get(donem, "")
            text = (
                f"{mufredat_yili} {BOLUM_ADI} müfredatı — {yil}. yıl {sezon} dönemi "
                f"({donem}. dönem): {kod} {ad}. "
                f"Teorik: {t or '—'}, Lab: {l or '—'}, Kredi: {k or '—'}, AKTS: {a or '—'}. "
                f"Ön şart: {on if on else 'yok'}."
            )
            chunks.append({
                "id": f"ee_muf_{mufredat_yili}_d{donem}_r{ri}_{kod.replace(' ','')}",
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
            "id": f"ee_muf_{mufredat_yili}_sem_summary_d{donem}",
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


def make_capsule_chunks(mufredat_yili: str):
    chunks = []
    for kod, ad, on, akts in ELECTIVE_CAPSULES:
        text = (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Seçmeli Kapsül (Elective Capsule): "
            f"{kod} {ad}. AKTS: {akts}. Ön şart: {on}. "
            f"Bu kapsül 3. ve 4. sınıf öğrencileri tarafından seçmeli kapsül havuzundan alınır."
        )
        chunks.append({
            "id": f"ee_capsule_{mufredat_yili}_{kod.replace(' ','')}",
            "text": text,
            "metadata": {
                "tip": "secmeli_havuz",
                "mufredat_yili": mufredat_yili,
                "havuz": "EE Seçmeli Kapsüller (Elective Capsules)",
                "ders_kodu": kod,
                "ders_adi": ad,
                "on_sart": on,
                "akts": akts,
                "kaynak": "AGU-EE-Curriculum-2019.pdf",
                "bolum": BOLUM,
            },
        })

    # Toplu özet chunk
    lines = [f"- {kod} | {ad} | AKTS: {akts} | Ön şart: {on}" for kod, ad, on, akts in ELECTIVE_CAPSULES]
    body = (
        f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Seçmeli Kapsüller (Elective Capsules) "
        f"Havuzu (toplam {len(ELECTIVE_CAPSULES)} kapsül, her biri 10 ECTS):\n"
        + "\n".join(lines)
        + "\n\nNot: 3. sınıf güz, 3. sınıf bahar ve 4. sınıf güz dönemlerinde toplam "
          "60 ECTS değerinde (yani 6 kapsül) bu havuzdan seçilir. Ek olarak öğrenciler "
          "iki adet IE 3XX/4XX, CE 3XX/4XX, COMP 3XX/4XX, ME 3XX/4XX, MSNE 3XX/4XX "
          "dersini birleştirerek bir 10 ECTS kapsül olarak da kullanabilir (bölüm onayıyla)."
    )
    chunks.append({
        "id": f"ee_capsule_havuz_ozet_{mufredat_yili}",
        "text": body,
        "metadata": {
            "tip": "secmeli_havuz_ozet",
            "mufredat_yili": mufredat_yili,
            "havuz": "EE Seçmeli Kapsüller (Elective Capsules)",
            "ders_sayisi": len(ELECTIVE_CAPSULES),
            "kaynak": "AGU-EE-Curriculum-2019.pdf",
            "bolum": BOLUM,
        },
    })
    return chunks


def make_capsule_chunks_from_csv(path: Path, mufredat_yili: str):
    """Kapsül CSV'sinden chunk üret. Format: Ders Kodu,Ders Adı,Ön Şart,Teo.,Lab.,Kredi,AKTS"""
    courses = []
    chunks = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kod = (row.get("Ders Kodu") or "").strip()
            ad = (row.get("Ders Adı") or "").strip()
            on = (row.get("Ön Şart") or "").strip().strip("-").strip()
            t = (row.get("Teo.") or row.get("Teorik") or "").strip()
            l = (row.get("Lab.") or row.get("Lab") or "").strip()
            k = (row.get("Kredi") or "").strip()
            a = (row.get("AKTS") or "").strip()
            if not kod or not ad:
                continue
            courses.append({"kod": kod, "ad": ad, "on": on, "t": t, "l": l, "kredi": k, "akts": a})

            text = (
                f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Seçmeli Kapsül (Elective Capsule): "
                f"{kod} {ad}. Teorik: {t or '—'}, Lab: {l or '—'}, "
                f"Kredi: {k or '—'}, AKTS: {a or '—'}. Ön şart: {on if on else 'yok'}. "
                f"Bu kapsül 3. ve 4. sınıf öğrencileri tarafından seçmeli kapsül havuzundan alınır."
            )
            chunks.append({
                "id": f"ee_capsule_{mufredat_yili}_{kod.replace(' ','')}",
                "text": text,
                "metadata": {
                    "tip": "secmeli_havuz",
                    "mufredat_yili": mufredat_yili,
                    "havuz": "EE Seçmeli Kapsüller (Elective Capsules)",
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

    if courses:
        lines = [
            f"- {c['kod']} | {c['ad']} | T:{c['t'] or '—'}, L:{c['l'] or '—'}, "
            f"Kredi:{c['kredi'] or '—'}, AKTS:{c['akts'] or '—'} | Ön şart: {c['on'] or 'yok'}"
            for c in courses
        ]
        body = (
            f"{BOLUM_ADI} {mufredat_yili} Müfredatı — Seçmeli Kapsüller (Elective Capsules) "
            f"Havuzu (toplam {len(courses)} kapsül):\n"
            + "\n".join(lines)
            + "\n\nNot: 3. sınıf güz, 3. sınıf bahar ve 4. sınıf güz dönemlerinde "
              "bu havuzdan toplam 60 ECTS değerinde (genelde 6 kapsül) seçilir. "
              "XEE kodlu dersler sadece değişim öğrencilerine (Erasmus vb.) yöneliktir."
        )
        chunks.append({
            "id": f"ee_capsule_havuz_ozet_{mufredat_yili}",
            "text": body,
            "metadata": {
                "tip": "secmeli_havuz_ozet",
                "mufredat_yili": mufredat_yili,
                "havuz": "EE Seçmeli Kapsüller (Elective Capsules)",
                "ders_sayisi": len(courses),
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


CAPSULE_RULES_GENEL = [
    ("1", "Bir kapsül, birden fazla alt bileşen içerebilir ya da içermeyebilir. Kapsül alt bileşen içermiyorsa, "
          "o kapsülden alınacak notun en az %15'i proje notu olmalıdır. Eğer bir kapsül birden fazla alt "
          "bileşenden oluşuyorsa, bir kapsülün her bir alt bileşeni proje performansını içerecek şekilde "
          "bağımsız olarak değerlendirilir. Projenin kapsülde yer alan alt bileşenlere etkisi %15 veya daha "
          "fazla olabilir. Projenin ve diğer değerlendirme kriterlerinin her bir kapsül alt bileşenine etkisi "
          "ders izlencesinde belirtilir."),
    ("2", "Eğer kapsül içerisindeki herhangi bir alt bileşenden başarısız olunursa, o alt bileşenin açıldığı "
          "dönemde bütün değerlendirme kriterlerinden sorumlu olunur. Başarısız olunan dönemdeki proje notu "
          "70/100 ve üzerindeyse, son nota alt bileşen ders izlencesinde belirtilen oranda eklenir ve projenin "
          "bir daha alınması gerekmez. O alt bileşen için açılan dönemdeki projeyi tekrar almak da mümkündür."),
    ("3", "Eğer kapsül kapsamındaki iki ya da daha fazla alt bileşenden (laboratuvarlar bu sayıya dahil "
          "edilmez) F veya NA notuyla kalınırsa, kapsül ilk açıldığında o kapsüldeki kalınan alt bileşenler "
          "ve proje tekrar alınır."),
    ("4", "Öğrenci, genel not ortalaması birbirini takip eden iki dönemde 2,00'nin altında olursa tekrar "
          "durumuna düşer. Bu durumda o kapsülde başarısız olduğunuz ve notu C notundan düşük olan dersleri "
          "(C-, D+, D, F veya NA notları) tekrarlamak zorundasınız."),
    ("5", "EE 3000 ve EE 4000 kodlu seçmeli kapsüllerin alınmasıyla ilgili sayı sınırlamaları bölüm kurulu "
          "kararıyla getirilebilir."),
    ("6", "Elektrik-Elektronik Mühendisliği bölümü öğrencisi olarak diğer mühendislik alanlarına ilgi "
          "duyuyorsanız, danışmanınızdan onay alarak seçeceğiniz iki IE 3XX, IE 4XX, CE 3XX, CE 4XX, "
          "COMP3XX, COMP4XX, ME3XX, ME4XX, MSNE 3XX, MSNE 4XX kodlu dersi birleştirerek 10 AKTS'lik "
          "seçmeli bir kapsül oluşturabilirsiniz. Bu tarz iki bölüm dışı dersten oluşturulan seçmeli "
          "kapsüllerin sayısı bir ile sınırlıdır."),
    ("7", "Seçmeli bir kapsülün yerine iki adet ≥5 AKTS'lik EE kodlu teknik seçmeli ders alınarak bir "
          "seçmeli kapsül oluşturulabilir. Bu şekilde oluşturulan seçmeli kapsül sayısına sınırlama "
          "uygulanmaz."),
    ("8", "Değişim programları kapsamında (Erasmus) başka bir üniversitede belli bir dönem eğitim alan "
          "öğrencilerin aldıkları Elektrik-Elektronik Mühendisliği ile alakalı dersler, Erasmus "
          "koordinatörünün ve danışmanın onayı dahilinde seçmeli kapsül olarak işlem görebilir. "
          "Yurt dışındaki üniversiteden alınan iki ders bir seçmeli kapsül yerine sayılır. Bu şekilde "
          "oluşturulmuş kapsüller, 6. maddede belirtilen bölüm dışındaki derslerle oluşturulan seçmeli "
          "kapsül sayısına dahil edilmez."),
]

CAPSULE_RULES_OZEL = [
    ("1", "Kapsül tabanlı müfredata 2018-2019 bahar döneminde başlayan öğrenciler için: "
          "(a) MATH 151, PHYS 101, COMP 101 derslerinden başarısız olunduysa aynı kodlu dersler ortak "
          "müfredattan alınmalıdır; MATH 153, PHYS 105, EE 101 alt bileşenleri seçilmemelidir. "
          "(b) 2018-2019 güz dönemi EE 100 Entegre Proje dersinden başarısız olunduysa BIO 101 veya CHEM 101 "
          "derslerinden biri alınmalıdır; EE 100 dersi bir daha açılmayacaktır. "
          "(c) PDP 101 dersi EDU 100 ile, PDP 300 dersi EE 300 ile eş derstir."),
    ("2", "Bölüme 2019-2020 döneminde yatay/dikey geçiş yapan öğrenci 2018-2019 müfredatından sorumludur. "
          "Daha önceki kurumda alınan dersler içerik benzerliğine göre değerlendirilir. Ders/Kapsül seçimi "
          "esnasında akademik danışmana başvurulması önemlidir."),
    ("3", "Erasmus gibi değişim programlarına katılması planlanıyorsa, değişim danışmanlarına (Erasmus için "
          "Dr. Dooyoung Hah) diğer kurumda alınacak derslerin programdaki eşdeğerliği konusunda "
          "danışılmalıdır."),
    ("4", "Bölümde ders almaya 2018-2019 güz döneminden önce başlanıldıysa: "
          "(a) İlk defa, kalındığı için veya not yükseltme amaçlı alınacak ders yeni müfredatta bir kapsülün "
          "alt bileşeni ise, kapsül kapsamındaki alt bileşenin alınması gerekir. "
          "(b) Eğer alınacak ders yeni müfredatta yer almıyorsa ve bir daha açılmayacaksa, bölüm başkanı ve "
          "akademik danışmanla görüşülerek dilekçeyle yerine sosyal/teknik/konsantrasyon alanı seçmelisi "
          "alınması gerekir. "
          "(c) MATH 203 Lineer Cebir ve MATH 205 Diferansiyel Denklemler tekrar alınacaksa kapsül içindeki "
          "alt bileşenleri (MATH 103 ve MATH 207) değil, ortak açılan MATH 203 ve MATH 205 alınmalıdır."),
    ("5", "Ön koşul denklikleri: MATH 153 ↔ MATH 151 ↔ MATH 101; MATH 154 ↔ MATH 152 ↔ MATH 102; "
          "PHYS 105 ↔ PHYS 101 ↔ SCI 101; PHYS 104 ↔ PHYS 102 ↔ SCI 102; "
          "EE 101 ↔ COMP 101 ↔ EE 112 dersleri birbiriyle denk kabul edilir."),
]


def make_capsule_rules_chunks():
    """EE Kapsül Temelli Müfredat Kuralları (12 Eylül 2024) — tüm EE müfredatları için ortak."""
    chunks = []
    # Tanım chunk
    chunks.append({
        "id": "ee_capsule_rules_tanim",
        "text": (
            "Elektrik-Elektronik Mühendisliği — Kapsül Tanımı: "
            "Kapsül, içerisindeki alt bileşenler ve projesiyle, mühendislik ve özellikle "
            "elektrik-elektronik mühendisliği için temel yetkinliklerin geliştirilmesine odaklanmış "
            "bir öğrenme birimidir. Bir kapsül zorunlu veya seçmeli olabilir ve 10 veya 20 AKTS "
            "kredisine sahip olabilir. Örnek: EE 2100 İşaret Edinim, İşleme & Analiz kapsülü 4 alt "
            "bileşenden oluşur (MATH 207 Diferansiyel Denklemler, EE 204 İşaret ve Sistemler, "
            "EE 202 Elektrik Devreleri II ve EE 212 Elektrik Devreleri Lab II). Kapsülde EKG sistemi "
            "tasarımı gibi takım projeleri yapılır; proje performansı her alt bileşenin notunu etkiler."
        ),
        "metadata": {
            "tip": "kapsul_kurallari",
            "kural_tipi": "Tanım",
            "kaynak": "EE_Capsule_Rules_TR.pdf",
            "bolum": BOLUM,
        },
    })
    # Genel kurallar
    for no, body in CAPSULE_RULES_GENEL:
        chunks.append({
            "id": f"ee_capsule_rule_genel_{no}",
            "text": (
                f"Elektrik-Elektronik Mühendisliği — Kapsül Temelli Müfredat Genel Kural {no}: {body}"
            ),
            "metadata": {
                "tip": "kapsul_kurallari",
                "kural_tipi": "Genel Kural",
                "kural_no": int(no),
                "kaynak": "EE_Capsule_Rules_TR.pdf",
                "bolum": BOLUM,
            },
        })
    # Özel kurallar
    for no, body in CAPSULE_RULES_OZEL:
        chunks.append({
            "id": f"ee_capsule_rule_ozel_{no}",
            "text": (
                f"Elektrik-Elektronik Mühendisliği — Kapsül Temelli Müfredat Özel Kural {no}: {body}"
            ),
            "metadata": {
                "tip": "kapsul_kurallari",
                "kural_tipi": "Özel Kural",
                "kural_no": int(no),
                "kaynak": "EE_Capsule_Rules_TR.pdf",
                "bolum": BOLUM,
            },
        })
    return chunks


# EE Staj Yönergesi MADDE'leri (özet — anahtar bilgiler)
STAJ_MADDELERI = [
    ("1", "Amaç", "Bu Yönergenin amacı; AGÜ Mühendislik Fakültesi Elektrik-Elektronik Mühendisliği Bölümü "
          "öğrencileri tarafından gerçekleştirilmesi gereken stajların temel ilkelerinin; planlama, "
          "uygulama ve değerlendirmesine ilişkin usul ve esasları düzenlemektir."),
    ("2", "Kapsam", "Bu Yönerge, AGÜ Mühendislik Fakültesi Elektrik-Elektronik Mühendisliği Bölümü'nde "
          "gerçekleştirilmesi gereken stajların uygulanmasına ilişkin hükümleri kapsar."),
    ("3", "Dayanak", "Yönerge, 24 Şubat 2015 tarih ve 29277 sayılı Resmi Gazetede yayımlanan "
          "'Abdullah Gül Üniversitesi Lisans Eğitim, Öğretim ve Sınav Yönetmeliği'nin 8. Maddesi'ne "
          "dayanılarak hazırlanmıştır."),
    ("4", "Tanımlar",
        "EE299: Öğrencilerin alması zorunlu olan ve teorik bilgiyi iş yeri/laboratuvar ortamında "
        "uygulamasını sağlayan staj dersi. "
        "EE399: 2016 ve öncesinde başlayan öğrencilerin alması zorunlu olan staj dersi. "
        "EE400: Bir dönem boyunca süren iş yeri deneyimi staj dersi (mühendislik tasarım, proje "
        "yönetimi, endüstriyel inovasyon çalışmalarına katılım). "
        "Bölüm Staj Komisyonu: EE Bölümü Staj Komisyonu (3 öğretim üyesinden oluşur, 2 yıl görev). "
        "Staj Danışmanı: Her öğrencinin staj sürecini takip eden bölüm öğretim üyesi. "
        "İş günü: Devlet kurumunda Pzt-Cuma; özel şirkette firmanın çalışma günleri."),
    ("5", "Stajın Amacı", "EE lisans programındaki zorunlu staj derslerinin amacı; öğrencilerin yurt içi "
          "ve yurt dışında ilgili kamu, özel sektör veya STK'larda alanları ile ilgili uygulamalı "
          "çalışmalara katılarak teorik bilgilerin uygulamasını öğrenmeleri ve beceri-deneyim sahibi "
          "olmalarıdır."),
    ("6", "Bölüm Staj Komisyonu", "Bölüm Staj Komisyonu 3 öğretim üyesinden oluşur, üyeler 2 yıl için "
          "Bölüm Başkanı tarafından seçilir, süresi sona eren üye tekrar seçilebilir. Komisyon oy "
          "çokluğu ile karar alır."),
    ("7", "Staj Süreleri ve Şartları",
        "(a) 2016 öncesi başlayanlar: EE299 + EE399 toplam minimum 50 iş günü. "
        "(b) 2016 ve sonrası başlayanlar: EE299 için 20 iş günü zorunludur. "
        "(c) 2016 ve sonrası: EE400 minimum 1 yarıyıl; devam zorunluluğu %90; EE400 ile birlikte "
        "OHS401 ve OHS402 dışında ders alınamaz. "
        "(d) Ön şart AKTS: EE299 için en az 90 AKTS, EE399 için en az 150 AKTS, EE400 için en az "
        "195 AKTS başarılı olmalı. "
        "(e) En az 165 AKTS başarıyla tamamlanmışsa GANO'ya bakılmaksızın ders yükü en fazla 15 AKTS "
        "artırılabilir. "
        "(f) EE299 ve EE399 kapsamında tek seferde en az 10 iş günü staj yapılabilir. "
        "(g) Eğitim dönemleri içinde EE299/EE399 zorunlu stajı yapılamaz; yaz okulu dönemi içinde de "
        "yapılamaz. "
        "(h) Fiilen çalışılan gün sayısı esastır."),
    ("8", "Staj Yeri",
        "(a) Öğrenci staj yerini kendi imkânlarıyla bulur; uygunluğa Bölüm Staj Komisyonu karar verir. "
        "(b) Komisyon onayıyla zorunlu stajın bir kısmı Üniversite laboratuvarlarında yapılabilir. "
        "(c) Staj yerinde elektrik/elektronik/elektrik-elektronik/elektronik ve haberleşme/bilgisayar/"
        "mekatronik/kontrol/biyomedikal mühendisi pozisyonunda en az bir mühendis bulunmalıdır. "
        "(d) Öğrenci kabul aldıktan sonra Staj Formu'nu Bölüm Staj Komisyonuna teslim edip onay alır. "
        "(e) İş yerinin uygunluğundan öğrenci sorumludur; sonradan uygunsuz çıkarsa staj geçersiz "
        "sayılır. "
        "(f) Staj Formu'nda belirtilen yer dışında başka bir yerde staj yapılamaz. "
        "(h) Yurtdışı stajları IAESTE, ERASMUS, AIESEC veya kendi imkânlarıyla yapılabilir; "
        "eşdeğerliğe Bölüm Staj Komisyonu karar verir."),
    ("9", "Çift Ana Dal, Yatay/Dikey Geçişlerde Staj Geçerliliği",
        "(a) Çift ana dal yapan öğrencilerin staj geçerliliği Bölüm Staj Komisyonu tarafından "
        "değerlendirilir. "
        "(b) Stajın her iki dalda sayılması için staja başlamadan önce her iki Bölüm Staj "
        "Komisyonu'nun onayı gerekir. "
        "(c) Yatay/dikey geçişle gelen öğrencilerin önceki bölümdeki stajları belgelendirilirse, "
        "Bölüm Staj Komisyonu görüş yazısıyla Fakülte Yönetim Kurulu karar verir. "
        "(d) Meslek lisesi sonrası kamu/özel kurumlarda çalışma günleri staj olarak kabul edilmez."),
    ("10", "Stajda Uyulması Gereken Kurallar",
        "(a) Öğrenci iş düzeni, çalışma saatleri, iş sağlığı ve güvenliği konularında iş yeri "
        "kurallarına uymak zorundadır. "
        "(b) Sosyal güvenlik primi Üniversite tarafından ödenir. "
        "(c) Sigortalama için Staj Başvuru Formu staj başlangıcından 1 ay kadar önce bölüm "
        "sekreterliğine teslim edilmelidir. "
        "(e) Stajın devamına engel olmayacak kural ihlalleri iş yeri tarafından raporla Dekanlığa "
        "bildirilir; engel teşkil edenler için öğrenci işten uzaklaştırılır ve disiplin yönetmeliği "
        "uygulanabilir. "
        "(f-g) Öğrenci alet/malzeme/araçları özenle kullanmakla yükümlüdür; verecekleri zararlardan "
        "Üniversite sorumlu değildir."),
    ("11", "Staj Mazereti",
        "Mücbir sebep veya haklı mazeret nedeniyle iş yeri yetkilisince izin verilmesi durumunda "
        "öğrenci eksik kalan süreyi aynı yıl/gelecek yıl aynı veya komisyon onaylı başka iş yerinde "
        "tamamlamak zorundadır. Mazeret izni 10 günü geçerse o dönemki stajının bütünü tekrar "
        "ettirilir. Stajı izinsiz terk eden öğrenciye de süreye bakılmaksızın bu hüküm uygulanır."),
    ("12", "Staj Sonu Raporu",
        "(a) Öğrenciler staj çalışmalarını akademik dille yazılmış bir rapor halinde Bölüm Staj "
        "Komisyonu'na sunar. Rapor dili İNGİLİZCE'dir. Format Bölüm Web sayfasında yayınlanır; "
        "uygun olmayanlar kabul edilmez. "
        "(b) Raporun her sayfası stajyerden sorumlu mühendis tarafından imzalanıp kaşelenir. "
        "Akademik takvimdeki ders ekleme-bırakma tarihlerinin ilk gününe kadar imzalı kapalı zarfta "
        "değerlendirme raporuyla birlikte teslim edilir; sonra teslim edilen kabul edilmez ve staj "
        "başarısız sayılır."),
    ("13", "Değerlendirme",
        "(a) Staj raporu ve değerlendirme formu Staj Danışmanı tarafından değerlendirilir. "
        "(b) Değerlendirme kriterleri her dönem başında Bölüm Staj Komisyonu tarafından Ders "
        "İzlencelerinde belirtilir. "
        "(c) İsteğe bağlı staj için kredi talep edilemez. "
        "(d) Komisyon değerlendirmesine göre harf notu veya başarılı/başarısız notu verilir. "
        "(e-g) Gerek görülürse öğrenci mülakata çağrılır; mülakatlar komisyonun belirlediği jüriler "
        "tarafından yapılır."),
    ("14", "Bölüm Staj Komisyonu ve Staj Danışmanının Görev ve Yetkileri",
        "(a) Staj koordinasyonu ve değerlendirilmesi Komisyon tarafından yapılır. "
        "(b) Komisyon staj yeri ve zaman uygunluğuna karar verir. "
        "(c) Staj Danışmanları raporu değerlendirir, beklenmedik durumlarda Komisyonla birlikte "
        "karar alır. "
        "(d) Danışmanlar gerekli görmezse raporu kabul etmeyebilir. "
        "(e) Rapor nedeniyle kınama+ ceza alan öğrencinin stajı geçersiz sayılır. "
        "(g) Komisyon üyeleri staj yerlerini ziyaret edebilir; öğrenci yerinde bulunamazsa tutanakla "
        "bildirilir."),
    ("15", "Hüküm Bulunmayan Haller",
        "Bu Yönergede belirtilmeyen hususlarda değerlendirme ve karar yetkisi Bölüm Staj "
        "Komisyonuna aittir."),
    ("16", "Yürürlük", "Bu Yönerge AGÜ Senatosu tarafından onaylandığı tarihten itibaren yürürlüğe girer."),
    ("17", "Yürütme", "Bu Yönerge hükümlerini AGÜ Mühendislik Fakültesi Dekanı yürütür."),
]


def make_staj_yonerge_chunks():
    """EE Staj Yönergesi MADDE'leri."""
    chunks = []
    for no, baslik, body in STAJ_MADDELERI:
        text = f"Elektrik-Elektronik Mühendisliği Staj Yönergesi — MADDE {no} ({baslik}):\n{body}"
        chunks.append({
            "id": f"ee_staj_madde_{no}",
            "text": text,
            "metadata": {
                "tip": "staj_yonerge",
                "madde_no": int(no),
                "baslik": baslik,
                "kaynak": "EE_staj_yonergesi_2019.pdf",
                "bolum": BOLUM,
            },
        })
    return chunks


def make_glb_note_chunk(mufredat_yili: str):
    """EE müfredatında 4 GLB dersi alma zorunluluğu var (PDF dipnotu)."""
    text = (
        f"{BOLUM_ADI} {mufredat_yili} Müfredatı — GLB Seçmeli Şartı: "
        "Öğrencilerin müfredat boyunca 4 adet GLB kodlu ders alması zorunludur "
        "(GLB 102 Innovation and Entrepreneurship, GLB 201 Food and Health, "
        "GLB 202 Immigration and Population, GLB 301 Sustainability). "
        "Bu dersler tüm bölümler için ortak GLB seçmeli havuzunda yer alır."
    )
    return [{
        "id": f"ee_glb_note_{mufredat_yili}",
        "text": text,
        "metadata": {
            "tip": "kural_notu",
            "mufredat_yili": mufredat_yili,
            "kural": "GLB Seçmeli Şartı (4 ders zorunlu)",
            "kaynak": "AGU-EE-Curriculum-2019.pdf",
            "bolum": BOLUM,
        },
    }]


def main():
    all_chunks = []

    for yil, fn in MUFREDAT_CSV.items():
        p = RAW / fn
        if not p.exists():
            print(f"[!] bulunamadı: {p}")
            continue
        chs = parse_mufredat_csv(p, yil)
        all_chunks.extend(chs)
        print(f"[EE müfredat {yil}] {len(chs)} chunk")

        if yil in CAPSULES_CSV:
            cap_path = RAW / CAPSULES_CSV[yil]
            if cap_path.exists():
                cap_chs = make_capsule_chunks_from_csv(cap_path, yil)
            else:
                print(f"[!] kapsül CSV bulunamadı: {cap_path.name}")
                cap_chs = make_capsule_chunks(yil)
        else:
            cap_chs = make_capsule_chunks(yil)
        all_chunks.extend(cap_chs)
        print(f"[EE seçmeli kapsüller {yil}] {len(cap_chs)} chunk")

        glb_chs = make_glb_note_chunk(yil)
        all_chunks.extend(glb_chs)
        print(f"[EE GLB notu {yil}] {len(glb_chs)} chunk")

    # Tüm müfredatlar için ortak: Kapsül Kuralları + Staj Yönergesi
    capsule_rules_chs = make_capsule_rules_chunks()
    all_chunks.extend(capsule_rules_chs)
    print(f"[EE kapsül kuralları] {len(capsule_rules_chs)} chunk")

    staj_chs = make_staj_yonerge_chunks()
    all_chunks.extend(staj_chs)
    print(f"[EE staj yönergesi] {len(staj_chs)} chunk")

    out_path = OUT / "chunks_elektrik.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"\n[OK] Toplam {len(all_chunks)} elektrik chunk -> {out_path}")


if __name__ == "__main__":
    main()

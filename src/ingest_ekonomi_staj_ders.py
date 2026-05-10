"""
AGÜ Ekonomi Bölümü — ECON 499 Staj Dersi Ders Tanım & Uygulama Bilgileri ingest.
Kaynak: data/raw/AGU_Ekonomi_ECON499_Staj_Ders_Plani.pdf

İçerikten yapılandırılmış chunk'lar üretir. "DERSİN ÖĞRENİM ÇIKTILARININ PROGRAM
YETERLİLİKLERİ İLE İLİŞKİSİ" tablosu KASITLI olarak DAHİL EDİLMEMİŞTİR.

Çıktı: data/processed/chunks_ekonomi_staj_ders.jsonl
bolum = "ekonomi"
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

KAYNAK = "AGU_Ekonomi_ECON499_Staj_Ders_Plani.pdf"
BOLUM = "ekonomi"
DERS_KODU = "ECON 499"
DERS_ADI = "Staj"


def _meta(tip: str, **extra) -> dict:
    md = {
        "tip": tip,
        "bolum": BOLUM,
        "ders_kodu": DERS_KODU,
        "ders_adi": DERS_ADI,
        "kaynak": KAYNAK,
        "fakulte": "Yönetim Bilimleri Fakültesi",
        "program": "Ekonomi Lisans Programı",
    }
    md.update(extra)
    return md


def build_chunks() -> list[dict]:
    chunks: list[dict] = []

    # ---------- 1) Ders tanım & temel bilgiler ----------
    t1 = (
        "AGÜ Yönetim Bilimleri Fakültesi — Ekonomi Bölümü — Ekonomi Lisans Programı. "
        "DERS TANIM VE UYGULAMA BİLGİLERİ.\n\n"
        "• Dersin Adı: Staj\n"
        "• Dersin Kodu: ECON 499\n"
        "• Yarıyılı: — (belirli bir yarıyıla bağlı değildir)\n"
        "• T+U Saat: — (haftalık teorik/uygulama saati yoktur)\n"
        "• Kredisi: 3\n"
        "• AKTS: 7\n"
        "• Dersin Türü: Zorunlu\n"
        "• Dersin Dili: İngilizce\n"
        "• Dersin Koordinatörü: Ekonomi Bölümü Staj Komisyonu\n"
        "• Dersi Verenler: —\n"
        "• Dersin Yardımcıları: —"
    )
    chunks.append({
        "id": "ekonomi_econ499_ders_tanim",
        "text": t1,
        "metadata": _meta(
            "staj_ders_plani",
            bolum_tablo="ders_tanim",
            kredi=3, akts=7,
            ders_turu="Zorunlu", ders_dili="İngilizce",
            koordinator="Ekonomi Bölümü Staj Komisyonu",
        ),
    })

    # ---------- 2) Ön koşul ----------
    t2 = (
        "ECON 499 Staj dersi — Ön Koşul Dersleri:\n"
        "Ekonomi Bölümü derslerinde 150 AKTS'yi başarıyla tamamlamış olmak. "
        "Yani öğrenci, ECON 499 Staj dersini almadan önce Ekonomi Lisans Programı "
        "kapsamında en az 150 AKTS değerinde dersi başarıyla tamamlamış olmalıdır."
    )
    chunks.append({
        "id": "ekonomi_econ499_on_kosul",
        "text": t2,
        "metadata": _meta("staj_ders_plani", bolum_tablo="on_kosul",
                          on_kosul_aciklama="150 AKTS başarıyla tamamlanmış olmak"),
    })

    # ---------- 3) Dersin amacı ----------
    t3 = (
        "ECON 499 Staj dersi — Dersin Amacı:\n\n"
        "Ekonomi lisans programı öğrencilerinin mezuniyet öncesinde iş ve çalışma "
        "yaşamını tanımaları, böylece mezuniyet sonrasında çalışmaya başladıklarında "
        "belirli bir tecrübe edinmiş olmaları amacıyla uygulanan programdır. "
        "Program çerçevesinde öğrencilerin kendi ilgi ve yeteneklerine uygun iş "
        "alanlarını tanıma ve seçme, derslerde öğrendikleri Ekonomi ve diğer ilgili "
        "bilim dallarının uygulamalarını iş yaşamında görme ve bireysel olarak "
        "uygulama fırsatı edinmeleri amaçlanmaktadır."
    )
    chunks.append({
        "id": "ekonomi_econ499_amac",
        "text": t3,
        "metadata": _meta("staj_ders_plani", bolum_tablo="amac"),
    })

    # ---------- 4) Öğrenme çıktıları ----------
    ciktilar = [
        "Derslerde edinilen teorik bilgiyi, iş yaşamında karşılaşılan gerçek hayat problemlerine uygulama",
        "Kişisel ve mesleki alanlardaki güncel bilgi ve becerileri geliştirme",
        "İlgilenilen iş alanlarında gerçekleşen dinamikleri gözlemleme",
        "İlgilenilen alanlarda iş bulma olasılığını artırma",
        "Mezuniyet sonrasında iş hayatına hazır olma",
        "Derslerde edinilmeyen pratik bilgileri öğrenme ve bu bilgilerin uygulama alanlarını görme",
        "Ekonomi Bölümü mezunlarının çalışma ortamları konusunda bilgi ve tecrübe kazanma",
        "İş yaşamında proje gruplarında, takım halinde ve yönetim düzeni içerisinde çalışma tecrübesi ve becerisi kazanma",
        "Liderlik, yönetim ve iş planlama tecrübesi edinme",
    ]
    t4 = (
        "ECON 499 Staj dersi — Dersin Öğrenme Çıktıları (öğrenci bu dersi "
        "tamamladığında aşağıdaki çıktıları kazanır):\n\n"
        + "\n".join(f"• {c}." for c in ciktilar)
    )
    chunks.append({
        "id": "ekonomi_econ499_ogrenme_ciktilari",
        "text": t4,
        "metadata": _meta("staj_ders_plani", bolum_tablo="ogrenme_ciktilari",
                          cikti_sayisi=len(ciktilar)),
    })

    # ---------- 5) Dersin içeriği ----------
    t5 = (
        "ECON 499 Staj dersi — Dersin İçeriği:\n\n"
        "• Dersin içeriği, staj yapılan işyerinde öğrenciye verilen görevlere bağlı olacaktır. "
        "Standart bir haftalık ders içeriği yoktur; içerik tamamen staj yapılan kurumun "
        "iş alanına, projesine ve öğrenciye atanan sorumluluklara göre şekillenir."
    )
    chunks.append({
        "id": "ekonomi_econ499_icerik",
        "text": t5,
        "metadata": _meta("staj_ders_plani", bolum_tablo="icerik"),
    })

    # ---------- 6) Haftalık konular ve ön hazırlık ----------
    t6 = (
        "ECON 499 Staj dersi — HAFTALIK KONULAR VE İLGİLİ ÖN HAZIRLIK SAYFALARI:\n\n"
        "Hafta 1 (ve genel):\n"
        "• Haftalık ders planı ve ön çalışma bulunmamaktadır.\n"
        "• Öğrenci staj öncesi gerekli belgelerin ve staj sonrası değerlendirme formu, "
        "staj raporu ve staj sunumunun hazırlanmasından sorumludur.\n"
        "• Ön Hazırlık: — (haftalık sayfa/okuma ön hazırlığı yoktur)\n\n"
        "ECON 499; klasik sınıf-içi haftalık konu akışı olan bir ders değildir; "
        "öğrencinin iş yerinde yürüteceği staj faaliyeti üzerine kurulu uygulamalı bir derstir."
    )
    chunks.append({
        "id": "ekonomi_econ499_haftalik_konular",
        "text": t6,
        "metadata": _meta("staj_ders_plani", bolum_tablo="haftalik_konular"),
    })

    # ---------- 7) Kaynaklar ----------
    t7 = (
        "ECON 499 Staj dersi — KAYNAKLAR:\n\n"
        "• Ders Notu: —\n"
        "• Diğer Kaynaklar:\n"
        "  - Ders Kitabı: —\n"
        "  - Yardımcı Kitaplar: —\n\n"
        "Bu ders için belirlenmiş bir ders notu, ders kitabı veya yardımcı kitap bulunmamaktadır; "
        "öğrenme materyali öğrencinin staj yaptığı kurumda edineceği iş tecrübesi üzerinden sağlanır."
    )
    chunks.append({
        "id": "ekonomi_econ499_kaynaklar",
        "text": t7,
        "metadata": _meta("staj_ders_plani", bolum_tablo="kaynaklar"),
    })

    # ---------- 8) Materyal paylaşımı ----------
    t8 = (
        "ECON 499 Staj dersi — MATERYAL PAYLAŞIMI:\n\n"
        "• Dökümanlar: —\n"
        "• Ödevler: Staj öncesi gerekli belgelerin ve prosedürlerin takip edilmesi.\n"
        "• Sınavlar: Staj raporu, tecrübe ve gözlemlerin sunumu, işyerinden alınan staj "
        "değerlendirme notu.\n\n"
        "Yani ECON 499'da klasik anlamda yazılı sınav yoktur; değerlendirme rapor, "
        "sunum ve işyeri değerlendirme formu üzerinden yapılır."
    )
    chunks.append({
        "id": "ekonomi_econ499_materyal_paylasimi",
        "text": t8,
        "metadata": _meta("staj_ders_plani", bolum_tablo="materyal_paylasimi"),
    })

    # ---------- 9) Değerlendirme sistemi ----------
    t9 = (
        "ECON 499 Staj dersi — DEĞERLENDİRME SİSTEMİ (Yarıyıl İçi Çalışmaları):\n\n"
        "| Çalışma | Sayısı | Katkı Payı (%) |\n"
        "|---|---|---|\n"
        "| Rapor | 1 | 30 |\n"
        "| Sunum | 1 | 30 |\n"
        "| İşyerinden alınan staj değerlendirme formu | 1 | 40 |\n"
        "| **TOPLAM** | — | **100** |\n\n"
        "Yani ECON 499 başarı notu üç bileşenden oluşur: "
        "Staj Raporu %30, Staj Sunumu %30, İşyerinden alınan Staj Değerlendirme Formu %40. "
        "Toplam katkı payı %100'dür."
    )
    chunks.append({
        "id": "ekonomi_econ499_degerlendirme",
        "text": t9,
        "metadata": _meta(
            "staj_ders_plani", bolum_tablo="degerlendirme",
            rapor_yuzde=30, sunum_yuzde=30, isyeri_form_yuzde=40, toplam_yuzde=100,
        ),
    })

    # ---------- 10) Ders kategorisi ----------
    t10 = (
        "ECON 499 Staj dersi — DERS KATEGORİSİ:\n\n"
        "• Sosyal Bilimler: %100\n\n"
        "Yani ECON 499 Staj dersi, %100 oranında Sosyal Bilimler kategorisinde "
        "sınıflandırılmaktadır."
    )
    chunks.append({
        "id": "ekonomi_econ499_kategori",
        "text": t10,
        "metadata": _meta("staj_ders_plani", bolum_tablo="ders_kategorisi",
                          sosyal_bilimler_yuzde=100),
    })

    # ---------- 11) AKTS / İş Yükü Tablosu ----------
    t11 = (
        "ECON 499 Staj dersi — AKTS / İŞ YÜKÜ TABLOSU:\n\n"
        "| Etkinlik | Etkinlik Sayısı | Süresi (Saat) | Toplam İş Yükü (Saat) |\n"
        "|---|---|---|---|\n"
        "| Staj süresi, en az 20 işgünü | 20 | 8 | 160 |\n"
        "| Atanan iş yükü | 20 | 2 | 40 |\n"
        "| Rapor ve Sunum | 1 | 10 | 80 |\n"
        "| **Toplam İş Yükü** | — | — | **210** |\n"
        "| Toplam İş Yükü / 30 | — | — | 210/30 |\n"
        "| **Dersin AKTS Kredisi** | — | — | **7** |\n\n"
        "Hesap özeti:\n"
        "• Staj süresi en az 20 iş günüdür; günde 8 saat üzerinden 20×8 = 160 saatlik iş yükü oluşturur.\n"
        "• Stajyer öğrenciye atanan ek iş yükü 20 etkinlik × 2 saat = 40 saattir.\n"
        "• Rapor ve sunum hazırlığı 1 etkinlik × 10 saat ölçeklenmiş şekilde 80 saatlik iş yüküdür.\n"
        "• Toplam iş yükü: 160 + 40 + 80 = 210 saat.\n"
        "• AKTS hesabı: 210 / 30 = 7 → ECON 499 dersi 7 AKTS kredisindedir."
    )
    chunks.append({
        "id": "ekonomi_econ499_akts_is_yuku",
        "text": t11,
        "metadata": _meta(
            "staj_ders_plani", bolum_tablo="akts_is_yuku",
            staj_min_isgunu=20, gunluk_saat=8,
            staj_is_yuku=160, atanan_is_yuku=40, rapor_sunum_is_yuku=80,
            toplam_is_yuku=210, akts=7,
        ),
    })

    # ---------- 12) Master / overview chunk ----------
    master = (
        "AGÜ Ekonomi Bölümü — ECON 499 Staj Dersi GENEL ÖZET:\n\n"
        "ECON 499 Staj, Ekonomi Lisans Programı'nda zorunlu, 3 kredilik, 7 AKTS'lik, "
        "İngilizce dilinde verilen bir derstir. Dersin koordinatörü Ekonomi Bölümü Staj "
        "Komisyonu'dur. Ön koşul olarak öğrencinin Ekonomi Bölümü derslerinden en az "
        "150 AKTS'yi başarıyla tamamlamış olması gerekir.\n\n"
        "Ders, öğrencilere mezuniyet öncesinde iş yaşamını tanıma, teorik bilgilerini "
        "uygulamaya dökme, takım çalışması, liderlik ve iş planlama tecrübesi kazanma "
        "fırsatı sunar. Haftalık klasik ders işlenmez; staj yapılan iş yerindeki "
        "görevler ders içeriğini belirler.\n\n"
        "Değerlendirme; %30 Rapor + %30 Sunum + %40 İşyeri Staj Değerlendirme Formu "
        "şeklindedir (toplam %100). Ders %100 Sosyal Bilimler kategorisindedir.\n\n"
        "İş yükü hesabı: Staj 20 iş günü × 8 saat = 160 saat, atanan iş yükü 40 saat, "
        "rapor+sunum 80 saat → toplam 210 saat → 210/30 = 7 AKTS."
    )
    chunks.append({
        "id": "ekonomi_econ499_master",
        "text": master,
        "metadata": _meta("staj_ders_plani", bolum_tablo="master_ozet",
                          kredi=3, akts=7, ders_turu="Zorunlu", ders_dili="İngilizce"),
    })

    return chunks


def main():
    chunks = build_chunks()
    out_path = OUT / "chunks_ekonomi_staj_ders.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"[OK] {len(chunks)} ekonomi ECON 499 staj-ders-plani chunk -> {out_path}")
    by_tab = {}
    for c in chunks:
        t = c["metadata"].get("bolum_tablo", "?")
        by_tab[t] = by_tab.get(t, 0) + 1
    for t, n in sorted(by_tab.items()):
        print(f"     - {t}: {n}")


if __name__ == "__main__":
    main()

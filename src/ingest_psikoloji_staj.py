"""
AGÜ Psikoloji Bölümü PSYI404 Staj Uygulama Esaslarını ingest eder.
  - AGU_Psikoloji_PSYI404_Staj_Esaslari.pdf

Çıktı: data/processed/chunks_psikoloji_staj.jsonl
bolum = "psikoloji"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

PDF_PATH = RAW / "AGU_Psikoloji_PSYI404_Staj_Esaslari.pdf"
BOLUM = "psikoloji"


def _read_pdf(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return ""


def make_overview() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü Staj Programı — Genel Özet:\n\n"
        "Abdullah Gül Üniversitesi Psikoloji Bölümü öğrencileri için stajlar, "
        "**PSYI404 Psikolojide Staj (Internship in Psychology)** dersi kapsamında düzenlenir.\n\n"
        "TEMEL BİLGİLER:\n"
        "- Ders kodu: PSYI 404\n"
        "- Ders adı: Psikolojide Staj (Internship in Psychology)\n"
        "- Dayanak: AGÜ Lisans Eğitim Öğretim ve Sınav Yönetmeliği\n\n"
        "AMAÇ:\n"
        "Psikoloji lisans öğrencilerinin kuramsal ve uygulamaya yönelik bilgilerini, "
        "alanda doğrudan gözlem/uygulama yaparak pekiştirmeleridir.\n\n"
        "DERSE KAYIT ÖNKOŞULLARı:\n"
        "1. Bölümdeki dördüncü yarıyılı tamamlamış olmak\n"
        "2. Core derslerini (PSYC101, PSYC102, PSYC103, PSYC104) almış olmak\n"
        "3. Başvuru sürecine ait evrak işlemlerini tamamlamış olmak\n\n"
        "STAJ SÜRESİ:\n"
        "- En az 20, en fazla 60 iş günü\n"
        "- İş gününün başlangıç/bitiş saatleri kurumun mesai saatlerine uyulur\n\n"
        "NOT: Erasmus stajı için PSYI405 dersine bakınız (https://psy.agu.edu.tr/erasmusstaj)."
    )
    return {
        "id": "psikoloji_staj_overview",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "genel_ozet",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def make_staj_yerleri() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü — PSYI404 Staj Yapılabilecek Kurumlar:\n\n"
        "Öğrenci, ders sorumlusu öğretim üyesinin onayı ile aşağıdaki kurumlardan "
        "birinde gözlem/uygulama yapabilir:\n\n"
        "a. Yuva, kreş, yetiştirme yurtları ve özel eğitim merkezleri\n"
        "b. Huzur evleri\n"
        "c. Hastaneler, diğer sağlık birimleri; rehabilitasyon merkezleri\n"
        "d. Kamu veya özel sektör kurumlarının insan kaynakları, personel, eğitim ve AR-GE birimleri\n"
        "e. Araştırma laboratuvarları, merkezleri ya da şirketleri\n"
        "f. Reklam şirketleri\n"
        "g. Vakıf, dernek, sivil toplum kuruluşları ve belediyelerin psikoloji uygulamaları ile ilgili birimleri\n"
        "h. Erasmus stajı kapsamında bulunulan kurum/kuruluşlar\n"
        "i. Yukarıdakilerin dışında kalan, ancak bünyesinde en az bir psikoloğun istihdam edildiği "
        "tüm kurum ve kuruluşlar\n\n"
        "Soru: 'Psikoloji stajını nerede yapabilirim?' / 'Staj yerleri nereler?' / "
        "'Hangi kurumlarda staj yapılır?' → Yukarıdaki liste geçerlidir."
    )
    return {
        "id": "psikoloji_staj_kurumlar",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "staj_yerleri",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def make_basvuru_sureci() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü — PSYI404 Staj Başvuru Süreci:\n\n"
        "1. 'Staj Başvuru Formu' üç nüsha doldurulur (biri öğrencide kalır). "
        "Sırasıyla ilgili kuruma, dersin sorumlusuna onaylatılır. "
        "Üçüncü sırada Fakülte Sekreterliğine sigorta girişi için teslim edilir.\n"
        "   - Bir nüsha staj yapılacak kurumda\n"
        "   - Bir nüsha ders sorumlusu öğretim üyesinde\n"
        "   - Bir nüsha Fakülte Sekreterliğinde kalır\n\n"
        "2. 'Kurum onayı' ve 'bölüm onayı' süreçleri tamamlanınca öğrencinin derse kaydı yapılır.\n\n"
        "3. İlgili evrak işlemleri, dönemin ekle-bırak tarihinin son gününe kadar tamamlanmalıdır.\n\n"
        "4. Fakülte Sekreterliğinin sigorta girişi yapabilmesi için staj başlangıç tarihinden "
        "en erken bir ay, en geç bir hafta öncesine kadar form teslim edilmelidir.\n\n"
        "Soru: 'Staj başvurusu nasıl yapılır?' / 'Staj formu nereye teslim edilir?' "
        "→ Yukarıdaki adımlar takip edilir."
    )
    return {
        "id": "psikoloji_staj_basvuru",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "basvuru_sureci",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def make_uygulama_sureci() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü — PSYI404 Staj Uygulama Süreci:\n\n"
        "1. Staja başladığı ilk gün öğrenci şu belgeleri kurum yetkilisine teslim eder:\n"
        "   - Onayları tamamlanmış 'Staj Başvuru Formu'\n"
        "   - 'Staj Devam Formu'\n"
        "   - 'Kurumun Öğrenci Performansını Değerlendirme Formu'\n"
        "   - 'Bölüm Teşekkür Mektubu'\n\n"
        "2. Öğrenci, bölüm web sayfasından indirdiği 'Staj Günlüğü'nü çalışmalar süresince "
        "doldurur ve staj bitiminde ders sorumlusuna teslim eder.\n\n"
        "3. Staj tamamlandığında kurum yetkilisi 'Staj Devam Formu' ve 'Kurumun Öğrenci "
        "Performansını Değerlendirme Formu'nu doldurup kapalı ve kapağı imzalı bir zarf "
        "içerisinde öğrenciye teslim eder.\n\n"
        "4. 'Öğrenci Kurum Değerlendirme Formu' öğrencinin kendisi tarafından doldurulur.\n\n"
        "5. Öğrenci, kurumdan aldığı kapalı zarfı, 'Staj Günlüğü'nü ve 'Öğrenci Kurum "
        "Değerlendirme Formu'nu ders sorumlusu öğretim üyesine teslim eder.\n\n"
        "6. Ders sorumlusu, dönem içinde belirlediği zamanlarda yüz yüze ya da çevrimiçi "
        "toplantılar düzenleyebilir (değerlendirme, sunum, deneyim paylaşımı vb.)."
    )
    return {
        "id": "psikoloji_staj_uygulama",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "uygulama_sureci",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def make_degerlendirme() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü — PSYI404 Staj Değerlendirmesi:\n\n"
        "1. Öğrenci, dersin öğretim üyesine sunduğu tüm belgeler üzerinden değerlendirilir.\n\n"
        "2. Formlar, derse kayıtlı olunan dönemin son ders gününü takip eden en geç 7 gün "
        "içinde teslim edilmelidir. Geç teslim not değerlendirmesine yansıtılır.\n\n"
        "3. Staj süresi toplamda en az 20, en fazla 60 iş günüdür. İş gününün başlangıç ve "
        "bitiş saatleri kurumun mesai saatlerine uyulur. Bu koşullara uymayan stajlar "
        "başarısız sayılır.\n\n"
        "4. 'Staj Devam Formu'nda ya da ders sorumlusunun rastgele yaptığı denetimlerde "
        "devamsızlık tespit edilen öğrencilerin stajı başarısız sayılır.\n\n"
        "Soru: 'Staj kaç gün?' / 'Staj süresi ne kadar?' → En az 20, en fazla 60 iş günü.\n"
        "Soru: 'Staj formları ne zaman teslim edilir?' → Son ders gününden sonra en geç 7 gün içinde."
    )
    return {
        "id": "psikoloji_staj_degerlendirme",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "degerlendirme",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def make_kurallar() -> dict:
    text = (
        "AGÜ Psikoloji Bölümü — PSYI404 Staj Kuralları:\n\n"
        "a. 'Staj Başvuru Formu'nda belirtilen kurum değiştirilemez. Ancak afet, grev, boykot "
        "ya da lokavt gibi durumlarda öğrenci, ders sorumlusuna yazılı başvuru yaparak kurum "
        "değişikliği talep edebilir. Değişiklik öğretim üyesinin onayıyla gerçekleşir ve "
        "başvuru süreci yeniden başlatılır.\n\n"
        "b. Öğrenci staj boyunca etik ilkeleri takip etmekle yükümlüdür.\n\n"
        "Aksi durumlarda, Yüksek Öğretim Kurumları Öğrenci Disiplin Yönetmeliği kapsamında "
        "işlem yapılır.\n\n"
        "Bu esaslarda belirtilmeyen durumlarda ilgili mevzuat hükümleri ile Yükseköğretim Kurulu, "
        "Senato, Üniversite Yönetim Kurulu ve ilgili Yönetim Kurulu kararları uygulanır."
    )
    return {
        "id": "psikoloji_staj_kurallar",
        "text": text,
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "kurallar",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def parse_full_pdf() -> dict:
    """PDF'in tam metnini tek bir chunk olarak ekle — arama coverage için."""
    full = _read_pdf(PDF_PATH)
    if not full:
        return None
    full_clean = re.sub(r"\s+", " ", full).strip()
    return {
        "id": "psikoloji_staj_tam_metin",
        "text": (
            "AGÜ Psikoloji Bölümü — PSYI404 Psikolojide Staj Uygulama Esasları (Tam Metin):\n\n"
            f"{full_clean[:3500]}"
        ),
        "metadata": {
            "tip": "staj_yonerge",
            "kategori": "tam_metin",
            "ders_kodu": "PSYI 404",
            "kaynak": PDF_PATH.name,
            "bolum": BOLUM,
        },
    }


def main():
    chunks: list[dict] = []
    chunks.append(make_overview())
    chunks.append(make_staj_yerleri())
    chunks.append(make_basvuru_sureci())
    chunks.append(make_uygulama_sureci())
    chunks.append(make_degerlendirme())
    chunks.append(make_kurallar())

    full_chunk = parse_full_pdf()
    if full_chunk:
        chunks.append(full_chunk)

    out_path = OUT / "chunks_psikoloji_staj.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    print(f"\n[OK] Toplam {len(chunks)} psikoloji staj chunk -> {out_path}")
    by_kat: dict[str, int] = {}
    for c in chunks:
        k = c["metadata"].get("kategori", "diger")
        by_kat[k] = by_kat.get(k, 0) + 1
    for k, n in by_kat.items():
        print(f"     - {k}: {n}")


if __name__ == "__main__":
    main()

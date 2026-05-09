"""
AGÜ Yatay Geçiş kaynakları (yönerge + başvuru koşulları + istenen belgeler).
Tüm bölümler için ortak (bolum='ortak').
Çıktı: data/processed/chunks_yatay_gecis.jsonl
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

BOLUM = "ortak"

YONERGE_PDF = "Yatay_Gecis_Yonergesi.pdf"
BELGELER_PDF = "Yatay_Gecis_Talep_Edilen_Belgeler.pdf"
KOSULLAR_PDF = "Yatay_Gecis_Basvuru_Kosullari.pdf"

# "MADDE 12 –" / "MADDE 1-" formatını yakala (en/em-dash veya hyphen)
MADDE_RE = re.compile(r"MADDE\s+(\d+)\s*[–\-—]")


def _read_pdf(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"PDF okunamadı {path.name}: {e}")
        return ""


# --------------------- 1) YÖNERGE — MADDE bazlı ---------------------

def parse_yonerge(path: Path) -> list[dict]:
    full = _read_pdf(path)
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
        # Başlık: madde'den hemen önceki satır
        before = full[max(0, start - 200):start].strip().split("\n")
        baslik = (before[-1].strip() if before else "")[:100]
        body = block[:3500]
        text = (
            f"AGÜ Lisans Programları Yatay Geçiş Yönergesi — MADDE {no}"
            + (f" ({baslik})" if baslik and len(baslik) < 80 else "")
            + f":\n{body}"
        )
        chunks.append({
            "id": f"yatay_gecis_madde_{no}",
            "text": text,
            "metadata": {
                "tip": "yatay_gecis_yonerge",
                "madde_no": int(no),
                "baslik": baslik,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


# --------------------- 2) İSTENEN BELGELER — kategori bazlı ---------------------

# Belge kategori başlıkları (büyük harfli satırlar)
BELGE_KATEGORI_RE = re.compile(
    r"^([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9İIı\s\-\(\)/'\.]{5,90})$",
    re.MULTILINE,
)


def parse_belgeler(path: Path) -> list[dict]:
    full = _read_pdf(path)
    if not full:
        return []

    # Tüm büyük harfli başlıkları bul, "BAŞVURUDA..." ve "TALEP EDİLEN BELGELER" gibi
    # Bilinen kategoriler (regex yerine basit string kontrol — daha güvenilir):
    KATEGORI_KEYS = [
        ("EK MADDE-1 KAPSAMINDA YATAY GEÇİŞ", "Ek Madde-1 (Merkezi Yerleştirme Puanıyla) Yatay Geçiş"),
        ("KURUM İÇİ YATAY GEÇİŞ", "Kurum İçi Yatay Geçiş"),
        ("KURUMLARARASI YATAY GEÇİŞ", "Kurumlararası (Yurt İçi) Yatay Geçiş"),
        ("AGÜ’DE OKUYAN ULUSLARARASI", "AGÜ'de Okuyan Uluslararası Öğrenci Başvuruları"),
        ("YURT DIŞI YÜKSEKÖĞRETİM KURUMLARDAN", "Yurt Dışı Yükseköğretim Kurumlarından Yatay Geçiş"),
    ]

    # Pozisyonları bul ve metni bölümlere ayır
    positions: list[tuple[int, str]] = []
    for key, label in KATEGORI_KEYS:
        idx = full.find(key)
        if idx >= 0:
            positions.append((idx, label))
    positions.sort()

    chunks: list[dict] = []
    for i, (start, label) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(full)
        body = full[start:end].strip()
        text = (
            f"AGÜ Yatay Geçiş — {label} kapsamında talep edilen belgeler "
            f"(başvuruda online yüklenmesi gereken evraklar):\n{body}"
        )
        chunks.append({
            "id": f"yatay_gecis_belge_{i+1}_{label.replace(' ', '_')[:40]}",
            "text": text[:3500],
            "metadata": {
                "tip": "yatay_gecis_belgeler",
                "kategori": label,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


# --------------------- 3) BAŞVURU KOŞULLARI — başlık bazlı ---------------------

def parse_kosullar(path: Path) -> list[dict]:
    full = _read_pdf(path)
    if not full:
        return []

    # Bilinen başlıklar
    BASLIK_KEYS = [
        ("Kurum İçi Programlar Arası Yatay Geçiş", "Kurum İçi Yatay Geçiş Başvuru Koşulları"),
        ("Yurt İçi/Kurumlar Arası Yatay Geçiş", "Kurumlararası (Yurt İçi) Yatay Geçiş Başvuru Koşulları"),
        ("Merkezi Yerleştirme Puanıyla Yatay Geçiş", "Ek Madde-1 (Merkezi Yerleştirme Puanı) Yatay Geçiş Başvuru Koşulları"),
        ("Yurt Dışı Yükseköğretim Kurumlarından Yatay Geçiş", "Yurt Dışı Yükseköğretim Kurumlarından Yatay Geçiş Başvuru Koşulları"),
    ]

    positions: list[tuple[int, str]] = []
    for key, label in BASLIK_KEYS:
        idx = full.find(key)
        if idx >= 0:
            positions.append((idx, label))
    positions.sort()

    chunks: list[dict] = []
    if not positions:
        # Yedek: tüm metni tek chunk yap
        chunks.append({
            "id": "yatay_gecis_kosullar_full",
            "text": f"AGÜ Yatay Geçiş Başvuru Koşulları:\n{full[:3500]}",
            "metadata": {
                "tip": "yatay_gecis_kosul",
                "kategori": "Tümü",
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
        return chunks

    for i, (start, label) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(full)
        body = full[start:end].strip()
        text = (
            f"AGÜ Yatay Geçiş — {label}:\n{body}"
        )
        chunks.append({
            "id": f"yatay_gecis_kosul_{i+1}",
            "text": text[:3500],
            "metadata": {
                "tip": "yatay_gecis_kosul",
                "kategori": label,
                "kaynak": path.name,
                "bolum": BOLUM,
            },
        })
    return chunks


# --------------------- Özet / Genel bakış chunk'ı ---------------------

def make_overview_chunk() -> dict:
    text = (
        "AGÜ Yatay Geçiş — Genel Özet:\n\n"
        "Abdullah Gül Üniversitesi'nde yatay geçiş türleri:\n\n"
        "1) **Kurum İçi Yatay Geçiş** — AGÜ içinde başka bir lisans programına geçiş. "
        "Şartlar: en az 2 yarıyıl tamamlamış olmak, GPA ≥ 2.30/4.00, müfredattaki derslerin "
        "en az %70'ini almış ve D/S veya üzeri ile geçmiş olmak.\n\n"
        "2) **Kurumlararası (Yurt İçi) Yatay Geçiş** — başka bir Türk üniversitesinden AGÜ'ye geçiş. "
        "Şartlar: en az 2 yarıyıl tamamlamış (hazırlık dışı), GPA ≥ 3.30/4.00, "
        "tüm dersleri almış ve başarmış olmak (F/NA/U/I/W gibi başarısız not olmaması).\n\n"
        "3) **Ek Madde-1 (Merkezi Yerleştirme Puanı) Yatay Geçiş** — kayıt olunan yıldaki YKS puanına "
        "göre, hedef programın o yılki taban puanına eşit veya üzerinde olunması durumunda yapılan geçiş.\n\n"
        "4) **Yurt Dışı Yükseköğretim Kurumlarından Yatay Geçiş** — yurt dışı üniversitelerden AGÜ'ye geçiş. "
        "İlgili belgelerle (lise diploması, denklik belgesi, dil yeterliliği vb.) başvurulur.\n\n"
        "5) **AGÜ'de Okuyan Uluslararası Öğrenci Başvuruları** — uluslararası öğrenciler için ayrı kontenjan.\n\n"
        "Resmi dayanak: 24/4/2010 tarihli ve 27561 sayılı Resmî Gazete'de yayımlanan "
        "'Yükseköğretim Kurumlarında Lisans Düzeyindeki Programlar Arasında Geçiş, Çift Ana Dal, "
        "Yan Dal ile Kurumlar Arası Kredi Transferi Yapılması Esaslarına İlişkin Yönetmelik' "
        "ve AGÜ Lisans Programları Yatay Geçiş Yönergesi (23.08.2023 tarih ve 2023.24.01 sayılı Senato Kararı ile güncellenmiştir).\n\n"
        "Tüm yatay geçiş türleri için belge yükleme online olarak yapılır. Detaylı belge listeleri "
        "ve madde-bazlı koşullar için ilgili kaynaklara bak."
    )
    return {
        "id": "yatay_gecis_overview",
        "text": text,
        "metadata": {
            "tip": "yatay_gecis_genel",
            "kaynak": "AGU_Yatay_Gecis_Ozeti",
            "bolum": BOLUM,
        },
    }


def main():
    all_chunks: list[dict] = []

    chs = parse_yonerge(RAW / YONERGE_PDF)
    all_chunks.extend(chs)
    print(f"[Yatay Geçiş Yönergesi] {len(chs)} MADDE chunk")

    chs = parse_belgeler(RAW / BELGELER_PDF)
    all_chunks.extend(chs)
    print(f"[Yatay Geçiş İstenen Belgeler] {len(chs)} kategori chunk")

    chs = parse_kosullar(RAW / KOSULLAR_PDF)
    all_chunks.extend(chs)
    print(f"[Yatay Geçiş Başvuru Koşulları] {len(chs)} bölüm chunk")

    all_chunks.append(make_overview_chunk())
    print(f"[Yatay Geçiş Genel Özet] 1 chunk")

    out_path = OUT / "chunks_yatay_gecis.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"\n[OK] Toplam {len(all_chunks)} yatay geçiş chunk -> {out_path}")


if __name__ == "__main__":
    main()

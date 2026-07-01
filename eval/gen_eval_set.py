"""
200 soruluk eval seti üreteci — TÜM bölümler, ground-truth veriden.

Sorular gerçek chunk metadata'sından (ders_kodu, ders_adi, akts, kredi, on_sart)
üretilir → beklenen cevap GARANTİ doğrudur. Böylece "doğruluk testi" gerçekten
objektif olur (uydurma gold yok).

Çıktı: eval/eval_set_200.json  (run_eval_cloud.py --set ile çalıştırılır)
"""
from __future__ import annotations

import glob
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "eval" / "eval_set_200.json"

random.seed(42)  # tekrarlanabilir

# Bölüm başına soru sayısı (toplam 200)
COUNTS = {
    "bilgisayar": 20,
    "endustri": 16, "insaat": 16, "siyaset": 16, "mimarlik": 16, "elektrik": 16,
    "ekonomi": 15, "isletme": 15, "biyomuhendislik": 15,
    "makine": 14, "malzeme": 14, "psikoloji": 14,
    "mbg": 13,
}
assert sum(COUNTS.values()) == 200


def _num(x) -> str | None:
    """Sayısal değeri temiz string'e çevir ('6', '3'); değilse None."""
    s = str(x).strip()
    if not s or s.lower() in ("none", "nan", "-", "—"):
        return None
    try:
        f = float(s.replace(",", "."))
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return None


def load_courses() -> dict[str, list[dict]]:
    """Bölüm -> benzersiz ders listesi. GROUND-TRUTH güvenliği için: aynı ders
    kodunun AKTS'si chunk'lar arası ÇELİŞKİLİYSE (birden çok farklı değer) o ders
    ELENİR — yoksa model doğru cevabı verse bile haksız yanlış sayılır."""
    # (bolum,kod) -> {alan: set(değerler)}
    agg: dict[tuple, dict] = defaultdict(lambda: {"ad": None, "akts": set(), "kredi": set(), "on_sart": set()})
    for fn in glob.glob(str(PROCESSED / "*.jsonl")):
        for line in open(fn, encoding="utf-8"):
            md = json.loads(line).get("metadata", {})
            b, kod, ad = md.get("bolum"), md.get("ders_kodu"), md.get("ders_adi")
            if not b or not kod or not ad:
                continue
            key = (b, str(kod).strip())
            a = agg[key]
            a["ad"] = a["ad"] or str(ad).strip()
            akts = _num(md.get("akts"))
            if akts:
                a["akts"].add(akts)
            kredi = _num(md.get("kredi"))
            if kredi:
                a["kredi"].add(kredi)
            os_ = str(md.get("on_sart", "") or "").strip()
            if os_:
                a["on_sart"].add(os_)

    by_bolum: dict[str, list[dict]] = defaultdict(list)
    for (b, kod), a in agg.items():
        # AKTS tek ve tutarlı değilse ders güvenilir değil → ele
        if len(a["akts"]) != 1:
            continue
        by_bolum[b].append({
            "kod": kod, "ad": a["ad"], "akts": next(iter(a["akts"])),
            # kredi/ön şart sadece TEK değerse kullan (yoksa o tip soru üretme)
            "kredi": next(iter(a["kredi"])) if len(a["kredi"]) == 1 else None,
            "on_sart": next(iter(a["on_sart"])) if len(a["on_sart"]) == 1 else "",
        })
    return dict(by_bolum)


def make_items(bolum: str, courses: list[dict], n: int) -> list[dict]:
    random.shuffle(courses)
    onsartli = [c for c in courses if c["on_sart"] and c["on_sart"].lower() != "yok"]
    kredili = [c for c in courses if c["kredi"]]

    items, used = [], set()
    # Kota: ~%15 ön şart, ~%25 kredi, gerisi AKTS
    n_onsart = min(len(onsartli), max(1, round(n * 0.15)))
    n_kredi = min(len(kredili), round(n * 0.25))

    def add(c: dict, tip: str):
        kod, ad = c["kod"], c["ad"]
        if tip == "akts":
            q = random.choice([f"{kod} dersi kaç AKTS?", f"{kod} kaç AKTS değerinde?",
                               f"{kod} dersinin AKTS'si nedir?"])
            kw, crit = [c["akts"]], f"{kod} ({ad}) dersinin AKTS değeri {c['akts']}'dir. Cevap {c['akts']} sayısını net vermeli."
        elif tip == "kredi":
            q = random.choice([f"{kod} kaç kredidir?", f"{kod} dersinin kredisi nedir?"])
            kw, crit = [c["kredi"]], f"{kod} ({ad}) dersinin kredisi {c['kredi']}'dir. Cevap {c['kredi']} değerini vermeli."
        else:  # on_sart
            q = random.choice([f"{kod} dersinin ön şartı nedir?", f"{kod} için ön şart var mı?"])
            kw, crit = [], f"{kod} ({ad}) dersinin ön şartı '{c['on_sart']}'dır. Cevap bu ön şart(lar)ı belirtmeli."
        items.append({
            "id": f"{bolum[:4]}_{len(items)+1:03d}", "bolum": bolum, "q": q,
            "expected_keywords": kw, "expected_codes": [kod], "judge_criteria": crit,
        })

    for c in onsartli[:n_onsart]:
        add(c, "on_sart"); used.add(c["kod"])
    for c in kredili:
        if len(used) >= n_onsart + n_kredi:
            break
        if c["kod"] not in used:
            add(c, "kredi"); used.add(c["kod"])
    for c in courses:
        if len(items) >= n:
            break
        if c["kod"] not in used:
            add(c, "akts"); used.add(c["kod"])
    return items[:n]


def main():
    all_courses = load_courses()
    items = []
    for bolum, n in COUNTS.items():
        courses = all_courses.get(bolum, [])
        if len(courses) < n:
            print(f"[!] {bolum}: sadece {len(courses)} ders var, {n} isteniyor — hepsi kullanılacak")
        got = make_items(bolum, courses, n)
        # Global benzersiz id
        for k, it in enumerate(got, 1):
            it["id"] = f"{bolum[:4]}_{k:03d}"
        items.extend(got)
        print(f"{bolum:16s}: {len(got)} soru")

    spec = {"description": "200 soruluk, tüm bölümleri kapsayan otomatik eval seti (ground-truth veriden)",
            "items": items}
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] {len(items)} soru -> {OUT}")


if __name__ == "__main__":
    main()

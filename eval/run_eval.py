"""
RAG accuracy eval harness — v2 (LLM-as-judge dahil).

Her soru için:
  1. rag.answer_stream() çağırılır (gerçek pipeline)
  2. Retrieval başarısı: expected_codes hits içinde mi? (Hit@K)
  3. Cevap başarısı: expected_keywords cevap metninde (keyword match)
  4. LLM-as-judge: Daha küçük bir LLM (llama-3.1-8b-instant), soru + cevap +
     judge_criteria'ya bakıp 0-5 arasında skor + 1 cümle gerekçe verir.
  5. TTFT ve toplam süre ölçülür.

Çıktı:
  - eval/results.jsonl
  - eval/report.md

Kullanım:
  python eval/run_eval.py                # tüm sorular + judge
  python eval/run_eval.py --limit 30     # ilk 30 soru
  python eval/run_eval.py --no-judge     # judge'ı atla (token tasarrufu)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from src import rag  # noqa: E402

EVAL_DIR = ROOT / "eval"
EVAL_SET = EVAL_DIR / "eval_set.json"
RESULTS = EVAL_DIR / "results.jsonl"
REPORT = EVAL_DIR / "report.md"

# Judge LLM — daha küçük & hızlı, token tasarruflu
JUDGE_MODEL = "llama-3.1-8b-instant"


def keyword_hit(text: str, kws: list[str]) -> tuple[int, int, list[str]]:
    if not text:
        return 0, len(kws), kws[:]
    low = text.lower()
    missing = []
    matched = 0
    for kw in kws:
        if kw.lower() in low:
            matched += 1
        else:
            missing.append(kw)
    return matched, len(kws), missing


def retrieval_hit(hits: list[dict], expected_codes: list[str]) -> tuple[bool, list[str]]:
    if not expected_codes:
        return True, []
    haystack = []
    for h in hits or []:
        haystack.append(str(h.get("id", "")).upper())
        md = h.get("metadata") or {}
        haystack.append(str(md.get("ders_kodu", "")).upper())
        haystack.append(str(md.get("kaynak", "")).upper())
    joined = " | ".join(haystack)
    found = [c for c in expected_codes if c.upper() in joined]
    return (len(found) > 0), found


def judge_answer(question: str, criteria: str, answer: str) -> tuple[int | None, str, str | None]:
    """LLM-as-judge: 0-5 skor + 1 cümle gerekçe.
    Provider rag.LLM_PROVIDER ile uyumlu (groq veya gemini).
    Dönen: (score, rationale, error)"""
    if not answer.strip():
        return 0, "Cevap boş.", None
    try:
        prompt = (
            f"Sen bir RAG sistemini değerlendiren tarafsız bir hakemsın.\n\n"
            f"SORU: {question}\n\n"
            f"DEĞERLENDİRME KRİTERİ: {criteria}\n\n"
            f"MODELİN CEVABI:\n{answer[:3000]}\n\n"
            f"Cevabı 0-5 arasında değerlendir:\n"
            f"  5 = Kriter tamamen karşılanmış, doğru ve eksiksiz\n"
            f"  4 = Kriter karşılanmış ama ufak eksik var\n"
            f"  3 = Kısmen doğru, önemli eksikler var\n"
            f"  2 = Çoğunlukla yanlış/eksik\n"
            f"  1 = Sadece yüzeysel ilgi var\n"
            f"  0 = Yanlış, alakasız veya 'bilmiyorum' demiş\n\n"
            f"Cevabını TAM olarak şu JSON formatında ver, başka hiçbir şey yazma:\n"
            f'{{"score": <0-5>, "rationale": "<kısa Türkçe gerekçe (max 1 cümle)>"}}'
        )
        # Provider'ı rag modülünden al
        if rag.LLM_PROVIDER == "openrouter":
            import os as _os
            from openai import OpenAI  # type: ignore
            judge_model = _os.getenv("OPENROUTER_JUDGE_MODEL",
                                     "openai/gpt-oss-120b:free")
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=_os.getenv("OPENROUTER_API_KEY"),
                default_headers={"HTTP-Referer": "https://github.com/agu-rag",
                                 "X-Title": "AGU RAG Eval"},
            )
            resp = client.chat.completions.create(
                model=judge_model,
                max_tokens=200,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content or ""
        else:
            from groq import Groq
            client = Groq()
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                max_tokens=200,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content or ""
        # JSON'u ayıkla
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("```")[1]
            if raw_clean.startswith("json"):
                raw_clean = raw_clean[4:]
        # İlk { ile son } arası
        start = raw_clean.find("{")
        end = raw_clean.rfind("}")
        if start >= 0 and end > start:
            raw_clean = raw_clean[start:end+1]
        data = json.loads(raw_clean)
        score = int(data.get("score", 0))
        score = max(0, min(5, score))
        rationale = str(data.get("rationale", ""))[:300]
        return score, rationale, None
    except Exception as e:
        return None, "", f"{type(e).__name__}: {e}"


def run(limit: int | None = None, use_judge: bool = True) -> None:
    spec = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    items = spec["items"]
    if limit:
        items = items[:limit]
    print(f"[i] {len(items)} eval sorusu calistiriliyor (judge={use_judge})...\n")

    results = []
    with RESULTS.open("w", encoding="utf-8") as fout:
        for i, it in enumerate(items, 1):
            qid = it["id"]
            bolum = it["bolum"]
            q = it["q"]
            exp_kws = it.get("expected_keywords", [])
            exp_codes = it.get("expected_codes", [])
            criteria = it.get("judge_criteria", "")

            q_short = q[:55].encode('ascii', 'replace').decode()
            print(f"[{i:3d}/{len(items)}] {qid:14s} ({bolum:11s}) -> {q_short}")
            t0 = time.time()
            ttft = None
            try:
                res = rag.answer_stream(q, bolum=bolum)
                hits = res.get("hits", [])
                text = res.get("text")
                token_iter = res.get("token_iter")
                if token_iter is not None:
                    buf = []
                    for chunk in token_iter:
                        if ttft is None:
                            ttft = time.time() - t0
                        buf.append(chunk)
                    ans = "".join(buf)
                else:
                    ttft = time.time() - t0
                    ans = text or ""
                err = None
            except Exception as e:
                ans = ""
                hits = []
                err = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            dt = time.time() - t0
            if ttft is None:
                ttft = dt

            m, tot, missing = keyword_hit(ans, exp_kws)
            r_ok, r_found = retrieval_hit(hits, exp_codes)
            ans_ok = (tot == 0) or (m == tot)

            # LLM-as-judge
            judge_score: int | None = None
            judge_rationale = ""
            judge_err: str | None = None
            if use_judge and ans and criteria:
                judge_score, judge_rationale, judge_err = judge_answer(q, criteria, ans)

            row = {
                "id": qid,
                "bolum": bolum,
                "question": q,
                "expected_keywords": exp_kws,
                "expected_codes": exp_codes,
                "judge_criteria": criteria,
                "answer": ans,
                "hit_ids": [h.get("id") for h in (hits or [])[:10]],
                "kw_matched": m,
                "kw_total": tot,
                "kw_missing": missing,
                "answer_ok": ans_ok,
                "retrieval_ok": r_ok,
                "retrieval_found": r_found,
                "judge_score": judge_score,
                "judge_rationale": judge_rationale,
                "judge_error": judge_err,
                "latency_s": round(dt, 2),
                "ttft_s": round(ttft, 2),
                "error": err,
            }
            results.append(row)
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            j_str = f" judge={judge_score}/5" if judge_score is not None else ""
            print(f"        retrieval={r_ok}  ans_kw={ans_ok}{j_str}  ttft={ttft:.1f}s  total={dt:.1f}s")
            if judge_rationale:
                print(f"        judge: {judge_rationale[:120]}")

            # OpenRouter free models: 20 RPM = 3 sn/istek; safe tarafta kalalım
            if rag.LLM_PROVIDER == "openrouter":
                time.sleep(3.5)

    write_report(results, use_judge=use_judge)
    print(f"\n[OK] Rapor: {REPORT}")


def write_report(results: list[dict], use_judge: bool = True) -> None:
    n = len(results)
    n_ret = sum(1 for r in results if r["retrieval_ok"])
    n_ans = sum(1 for r in results if r["answer_ok"])
    n_both = sum(1 for r in results if r["retrieval_ok"] and r["answer_ok"])
    n_err = sum(1 for r in results if r["error"])
    avg_lat = sum(r["latency_s"] for r in results) / max(n, 1)
    avg_ttft = sum(r.get("ttft_s", r["latency_s"]) for r in results) / max(n, 1)

    # Judge istatistikleri
    judge_scores = [r["judge_score"] for r in results if r.get("judge_score") is not None]
    judge_avg = sum(judge_scores) / len(judge_scores) if judge_scores else 0
    judge_pass = sum(1 for s in judge_scores if s >= 3)  # >=3: kabul edilebilir
    judge_excellent = sum(1 for s in judge_scores if s >= 4)
    judge_n = len(judge_scores)

    by_b: dict[str, dict] = {}
    for r in results:
        b = r["bolum"]
        s = by_b.setdefault(b, {"n": 0, "ret": 0, "ans": 0, "both": 0,
                                 "lat": 0.0, "ttft": 0.0, "judge": [], "j_pass": 0})
        s["n"] += 1
        s["ret"] += int(r["retrieval_ok"])
        s["ans"] += int(r["answer_ok"])
        s["both"] += int(r["retrieval_ok"] and r["answer_ok"])
        s["lat"] += r["latency_s"]
        s["ttft"] += r.get("ttft_s", r["latency_s"])
        if r.get("judge_score") is not None:
            s["judge"].append(r["judge_score"])
            if r["judge_score"] >= 3:
                s["j_pass"] += 1

    lines = []
    lines.append("# RAG Doğruluk Raporu (v2 — LLM-as-judge ile)\n")
    lines.append(f"- Toplam soru: **{n}**")
    lines.append(f"- Retrieval başarı (Hit@K): **{n_ret}/{n}** → **%{n_ret/n*100:.1f}**")
    lines.append(f"- Cevap doğruluk (keyword match): **{n_ans}/{n}** → **%{n_ans/n*100:.1f}**")
    lines.append(f"- Hem retrieval hem keyword: **{n_both}/{n}** → **%{n_both/n*100:.1f}**")
    if use_judge and judge_n:
        lines.append(f"- **LLM-as-judge ortalama skor: {judge_avg:.2f}/5.0** ({judge_n} skorlu)")
        lines.append(f"- LLM-as-judge kabul (≥3/5): **{judge_pass}/{judge_n}** → **%{judge_pass/judge_n*100:.1f}**")
        lines.append(f"- LLM-as-judge mükemmel (≥4/5): **{judge_excellent}/{judge_n}** → **%{judge_excellent/judge_n*100:.1f}**")
    lines.append(f"- Hata: **{n_err}**")
    lines.append(f"- Ortalama **TTFT** (algılanan gecikme): **{avg_ttft:.2f}s**")
    lines.append(f"- Ortalama toplam cevap süresi: **{avg_lat:.2f}s**\n")

    lines.append("## Bölüm Bazlı Sonuç\n")
    header = "| Bölüm | N | Retrieval % | KW % | Birleşik % |"
    sep    = "|---|---:|---:|---:|---:|"
    if use_judge:
        header += " Judge Ort | Judge ≥3 |"
        sep    += "---:|---:|"
    header += " Ort. TTFT | Ort. Toplam |"
    sep    += "---:|---:|"
    lines.append(header)
    lines.append(sep)
    for b, s in sorted(by_b.items()):
        row = (
            f"| {b} | {s['n']} | "
            f"%{s['ret']/s['n']*100:.0f} | "
            f"%{s['ans']/s['n']*100:.0f} | "
            f"%{s['both']/s['n']*100:.0f} |"
        )
        if use_judge:
            jv = sum(s["judge"])/len(s["judge"]) if s["judge"] else 0
            jp = (s["j_pass"]/len(s["judge"])*100) if s["judge"] else 0
            row += f" {jv:.2f}/5 | %{jp:.0f} |"
        row += f" {s['ttft']/s['n']:.1f}s | {s['lat']/s['n']:.1f}s |"
        lines.append(row)
    lines.append("")

    lines.append("## Detaylı Sonuçlar\n")
    hd = "| # | Bölüm | Soru | Retrieval | KW | Judge | TTFT |"
    sp = "|---|---|---|:---:|:---:|:---:|---:|"
    lines.append(hd); lines.append(sp)
    for i, r in enumerate(results, 1):
        q = r["question"].replace("|", "\\|")
        ret_s = "✅" if r["retrieval_ok"] else "❌"
        ans_s = "✅" if r["answer_ok"] else "❌"
        js = r.get("judge_score")
        j_str = f"{js}/5" if js is not None else "—"
        lines.append(f"| {i} | {r['bolum']} | {q[:80]} | {ret_s} | {ans_s} | {j_str} | {r['ttft_s']:.1f}s |")
    lines.append("")

    # Düşük judge skorlu vakalar (en aydınlatıcı)
    low = sorted(
        [r for r in results if r.get("judge_score") is not None and r["judge_score"] < 3],
        key=lambda r: r["judge_score"],
    )
    if low:
        lines.append(f"## Düşük Skorlu Vakalar (judge < 3) — {len(low)} adet\n")
        for r in low[:25]:
            lines.append(f"### `{r['id']}` ({r['bolum']}) — judge: **{r['judge_score']}/5**")
            lines.append(f"**Soru:** {r['question']}")
            lines.append(f"**Kriter:** _{r['judge_criteria']}_")
            lines.append(f"**Hakem gerekçesi:** {r['judge_rationale']}")
            ans_preview = (r["answer"] or "")[:400].replace("\n", " ")
            lines.append(f"**Cevap (ilk 400 char):** _{ans_preview}_")
            lines.append("")

    bad = [r for r in results if r["error"]]
    if bad:
        lines.append(f"## Çalıştırma Hataları — {len(bad)} adet\n")
        for r in bad[:15]:
            lines.append(f"- `{r['id']}` ({r['bolum']}): `{r['error']}`")
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="İlk N soruyu çalıştır")
    ap.add_argument("--no-judge", action="store_true", help="LLM-as-judge'ı atla")
    args = ap.parse_args()
    run(limit=args.limit, use_judge=not args.no_judge)

"""
BULUT RAG doğruluk eval'ı — run_eval.py'nin bulut (Voyage + Pinecone) eşi.

Aynı eval/eval_set.json'u kullanır ama pipeline olarak src.rag_cloud'u (torch'suz,
canlıda çalışan sürüm) test eder. Böylece deploy edilen modelin gerçek doğruluğunu
ölçer ve yerel sürümle kıyaslayabilirsin.

Her soru için:
  1. rag_cloud.respond() → gerçek cevap (deterministik liste veya LLM)
  2. Retrieval: expected_codes, getirilen bağlam metinlerinde geçiyor mu?
  3. Keyword: expected_keywords cevap metninde mi?
  4. LLM-as-judge: küçük bir model cevabı 0-5 puanlar
  5. Süre ölçülür

Çıktı: eval/results_cloud.jsonl + eval/report_cloud.md

Kullanım:
  python eval/run_eval_cloud.py                # tüm sorular + judge
  python eval/run_eval_cloud.py --limit 20     # hızlı deneme
  python eval/run_eval_cloud.py --no-judge     # judge'ı atla
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from src import rag_cloud  # noqa: E402

EVAL_DIR = ROOT / "eval"
EVAL_SET = EVAL_DIR / "eval_set.json"
RESULTS = EVAL_DIR / "results_cloud.jsonl"
REPORT = EVAL_DIR / "report_cloud.md"

JUDGE_MODEL_GROQ = "llama-3.1-8b-instant"


def keyword_hit(text: str, kws: list[str]) -> tuple[int, int, list[str]]:
    if not text:
        return 0, len(kws), kws[:]
    low = text.lower()
    matched, missing = 0, []
    for kw in kws:
        if kw.lower() in low:
            matched += 1
        else:
            missing.append(kw)
    return matched, len(kws), missing


def retrieval_hit_in_context(context_texts: list[str], expected_codes: list[str]) -> tuple[bool, list[str]]:
    """Bulutta chunk metadata yerine getirilen bağlam METİNLERİNDE kod arıyoruz
    (ders kodları chunk metninde de geçer — makul bir proxy)."""
    if not expected_codes:
        return True, []
    joined = " | ".join(context_texts).upper()
    # 'COMP 101' hem boşluklu hem boşluksuz eşleşsin
    found = []
    for c in expected_codes:
        cu = c.upper()
        if cu in joined or cu.replace(" ", "") in joined.replace(" ", ""):
            found.append(c)
    return (len(found) > 0), found


def judge_answer(question: str, criteria: str, answer: str) -> tuple[int | None, str, str | None]:
    if not answer.strip():
        return 0, "Cevap boş.", None
    prompt = (
        f"Sen bir RAG sistemini değerlendiren tarafsız bir hakemsin.\n\n"
        f"SORU: {question}\n\nDEĞERLENDİRME KRİTERİ: {criteria}\n\n"
        f"MODELİN CEVABI:\n{answer[:3000]}\n\n"
        f"Cevabı 0-5 arasında değerlendir:\n"
        f"  5=tam doğru/eksiksiz, 4=ufak eksik, 3=kısmen doğru, 2=çoğunlukla yanlış, "
        f"1=yüzeysel, 0=yanlış/alakasız/'bilmiyorum'.\n\n"
        f'Cevabını TAM olarak şu JSON ile ver: {{"score": <0-5>, "rationale": "<max 1 cümle>"}}'
    )
    try:
        # Judge için Groq'un küçük modelini tercih et; yoksa OpenRouter free
        if os.getenv("GROQ_API_KEY") and rag_cloud.LLM_PROVIDER != "openrouter":
            from groq import Groq
            raw = Groq(api_key=os.getenv("GROQ_API_KEY")).chat.completions.create(
                model=JUDGE_MODEL_GROQ, max_tokens=200, temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            ).choices[0].message.content or ""
        else:
            from openai import OpenAI
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
            raw = client.chat.completions.create(
                model=os.getenv("OPENROUTER_JUDGE_MODEL", "openai/gpt-oss-120b:free"),
                max_tokens=200, temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            ).choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.startswith("json") else raw
        s, e = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[s:e + 1]) if s >= 0 and e > s else {}
        return max(0, min(5, int(data.get("score", 0)))), str(data.get("rationale", ""))[:300], None
    except Exception as ex:
        return None, "", f"{type(ex).__name__}: {ex}"


def run(limit: int | None = None, use_judge: bool = True, eval_set: Path | None = None) -> None:
    global RESULTS, REPORT
    eval_set = eval_set or EVAL_SET
    stem = eval_set.stem
    RESULTS = EVAL_DIR / f"results_cloud_{stem}.jsonl"
    REPORT = EVAL_DIR / f"report_cloud_{stem}.md"
    items = json.loads(eval_set.read_text(encoding="utf-8"))["items"]
    if limit:
        items = items[:limit]
    print(f"[i] BULUT eval: {len(items)} soru (judge={use_judge})...\n")

    results = []
    with RESULTS.open("w", encoding="utf-8") as fout:
        for i, it in enumerate(items, 1):
            qid, bolum, q = it["id"], it["bolum"], it["q"]
            exp_kws = it.get("expected_keywords", [])
            exp_codes = it.get("expected_codes", [])
            criteria = it.get("judge_criteria", "")
            print(f"[{i:3d}/{len(items)}] {qid:14s} ({bolum:11s}) -> {q[:50].encode('ascii','replace').decode()}")

            t0 = time.time()
            try:
                # Retrieval bağlamı (retrieval metriği için)
                ctx_texts, _ = rag_cloud.retrieve(q, bolum=bolum)
                # Gerçek cevap (liste veya LLM)
                r = rag_cloud.respond(q, bolum=bolum)
                ans = r["text"] if r["mode"] == "list" else "".join(r["token_iter"])
                err = None
            except Exception as e:
                ctx_texts, ans, err = [], "", f"{type(e).__name__}: {e}"
                traceback.print_exc()
            dt = time.time() - t0

            m, tot, missing = keyword_hit(ans, exp_kws)
            r_ok, r_found = retrieval_hit_in_context(ctx_texts, exp_codes)
            ans_ok = (tot == 0) or (m == tot)

            j_score, j_rat, j_err = (None, "", None)
            if use_judge and ans and criteria:
                j_score, j_rat, j_err = judge_answer(q, criteria, ans)

            row = {
                "id": qid, "bolum": bolum, "question": q,
                "answer": ans, "kw_matched": m, "kw_total": tot, "kw_missing": missing,
                "answer_ok": ans_ok, "retrieval_ok": r_ok, "retrieval_found": r_found,
                "judge_score": j_score, "judge_rationale": j_rat, "judge_error": j_err,
                "latency_s": round(dt, 2), "error": err,
            }
            results.append(row)
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            js = f" judge={j_score}/5" if j_score is not None else ""
            print(f"        retrieval={r_ok}  kw={ans_ok}{js}  {dt:.1f}s")
            # Ücretsiz LLM kotalarını uzun koşularda tıkamamak için aralık ver.
            # PACE_SLEEP env ile ayarlanabilir (varsayılan: openrouter/auto için 3.5s).
            pace = float(os.getenv("PACE_SLEEP", "0") or 0)
            if pace <= 0 and rag_cloud.LLM_PROVIDER in ("openrouter", "auto"):
                pace = 3.5
            if pace > 0:
                time.sleep(pace)

    write_report(results, use_judge)
    print(f"\n[OK] Rapor: {REPORT}")


def write_report(results: list[dict], use_judge: bool) -> None:
    n = len(results)
    n_ret = sum(r["retrieval_ok"] for r in results)
    n_ans = sum(r["answer_ok"] for r in results)
    n_both = sum(r["retrieval_ok"] and r["answer_ok"] for r in results)
    avg_lat = sum(r["latency_s"] for r in results) / max(n, 1)
    js = [r["judge_score"] for r in results if r.get("judge_score") is not None]
    j_avg = sum(js) / len(js) if js else 0
    j_pass = sum(1 for s in js if s >= 3)

    by_b: dict[str, dict] = {}
    for r in results:
        s = by_b.setdefault(r["bolum"], {"n": 0, "ret": 0, "ans": 0, "j": []})
        s["n"] += 1
        s["ret"] += int(r["retrieval_ok"])
        s["ans"] += int(r["answer_ok"])
        if r.get("judge_score") is not None:
            s["j"].append(r["judge_score"])

    L = ["# BULUT RAG Doğruluk Raporu (Voyage + Pinecone)\n",
         f"- Toplam soru: **{n}**",
         f"- Retrieval (kod bağlamda): **{n_ret}/{n}** → **%{n_ret/n*100:.1f}**",
         f"- Cevap doğruluk (keyword): **{n_ans}/{n}** → **%{n_ans/n*100:.1f}**",
         f"- Birleşik: **{n_both}/{n}** → **%{n_both/n*100:.1f}**"]
    if use_judge and js:
        L.append(f"- **LLM-as-judge ortalama: {j_avg:.2f}/5.0** ({len(js)} skorlu)")
        L.append(f"- Judge kabul (≥3/5): **{j_pass}/{len(js)}** → **%{j_pass/len(js)*100:.1f}**")
    L.append(f"- Ortalama süre: **{avg_lat:.2f}s**\n")

    L.append("## Bölüm Bazlı\n| Bölüm | N | Retrieval % | KW % | Judge Ort |")
    L.append("|---|---:|---:|---:|---:|")
    for b, s in sorted(by_b.items()):
        jv = sum(s["j"]) / len(s["j"]) if s["j"] else 0
        L.append(f"| {b} | {s['n']} | %{s['ret']/s['n']*100:.0f} | %{s['ans']/s['n']*100:.0f} | {jv:.2f}/5 |")
    L.append("")

    low = sorted([r for r in results if r.get("judge_score") is not None and r["judge_score"] < 3],
                 key=lambda r: r["judge_score"])
    if low:
        L.append(f"## Düşük Skorlu Vakalar (judge < 3) — {len(low)} adet\n")
        for r in low[:25]:
            L.append(f"### `{r['id']}` ({r['bolum']}) — **{r['judge_score']}/5**")
            L.append(f"**Soru:** {r['question']}")
            L.append(f"**Hakem:** {r['judge_rationale']}")
            L.append(f"**Cevap:** _{(r['answer'] or '')[:400]}_\n")

    REPORT.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--set", type=str, default=None, help="eval seti json yolu (varsayılan eval_set.json)")
    args = ap.parse_args()
    eval_set = Path(args.set) if args.set else None
    if eval_set and not eval_set.is_absolute():
        eval_set = ROOT / eval_set
    run(limit=args.limit, use_judge=not args.no_judge, eval_set=eval_set)

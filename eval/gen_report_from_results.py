"""Mevcut results.jsonl'dan rapor üret (eval yeniden çalıştırmaz)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.run_eval import write_report  # noqa

RESULTS = ROOT / "eval" / "results.jsonl"
rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"[i] {len(rows)} satır okundu")
write_report(rows, use_judge=True)
print("[OK] Rapor güncellendi")

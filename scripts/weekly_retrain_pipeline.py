#!/usr/bin/env python3
"""Weekly retrain pipeline stub (data readiness + planning)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="app/data/db/birdlense.db")
    p.add_argument("--golden-dir", default="app/data/datasets/golden_v1")
    p.add_argument("--out-dir", default="app/data/retrain_runs")
    return p.parse_args()


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def main() -> int:
    args = parse_args()
    con = sqlite3.connect(args.db)
    try:
        pending = con.execute(
            "SELECT COUNT(*) FROM active_learning_buffer WHERE status = 'pending'"
        ).fetchone()[0]
        by_reason = con.execute(
            "SELECT reason_code, COUNT(*) AS cnt FROM active_learning_buffer GROUP BY reason_code ORDER BY cnt DESC"
        ).fetchall()
    finally:
        con.close()

    golden_dir = Path(args.golden_dir)
    train_count = _count_jsonl_rows(golden_dir / "train.jsonl")
    test_count = _count_jsonl_rows(golden_dir / "test.jsonl")
    all_count = _count_jsonl_rows(golden_dir / "all_cases.jsonl")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "stub_ready",
        "next_step": "Implement model fine-tuning + evaluation harness hook.",
        "active_learning_buffer_pending": int(pending),
        "active_learning_buffer_by_reason": [
            {"reason_code": str(r[0]), "count": int(r[1])} for r in by_reason
        ],
        "golden_dataset": {
            "path": str(golden_dir.resolve()),
            "all_cases": int(all_count),
            "train_cases": int(train_count),
            "test_cases": int(test_count),
        },
        "planned_pipeline": [
            "load_buffer_and_golden_dataset",
            "materialize_training_manifest",
            "run_fine_tuning_job",
            "evaluate_on_golden_test_split",
            "register_model_and_publish_metrics",
        ],
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"weekly_retrain_plan_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report_file={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

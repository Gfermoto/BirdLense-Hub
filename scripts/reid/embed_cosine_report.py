#!/usr/bin/env python3
"""
Отчёт по cosine similarity для JSONL из ``embed_dinov2_crop.py`` (#383).

Предполагаются **L2-нормированные** эмбеддинги (тогда cosine = скалярное произведение).

Пример::

    python3 scripts/reid/embed_dinov2_crop.py --glob 'crops/*.jpg' -o embed.jsonl
    python3 scripts/reid/embed_cosine_report.py --jsonl embed.jsonl --topk 5

Опционально: файл пар ``path1<TAB>path2`` известных «одинаковых» кропов (--pairs) —
среднее сходство по этим парам vs случайные разные пары.

Зависимость: **numpy** (легковесно отдельно от torch).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


def _load_rows(path: Path) -> tuple[list[str], list[list[float]], str | None]:
    paths: list[str] = []
    embs: list[list[float]] = []
    model: str | None = None
    dim: int | None = None
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            p = row.get("path")
            e = row.get("embedding")
            if not p or not isinstance(e, list):
                raise ValueError(f"line {line_no}: need path + embedding[]")
            if dim is None:
                dim = len(e)
            elif len(e) != dim:
                raise ValueError(f"line {line_no}: embedding dim {len(e)} != {dim}")
            paths.append(str(p))
            embs.append([float(x) for x in e])
            if model is None and row.get("model"):
                model = str(row["model"])
    return paths, embs, model


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True, type=Path, help="Файл JSON Lines от embed_dinov2_crop.py")
    ap.add_argument("--topk", type=int, default=5, help="Топ-K соседей на строку (0 = не выводить)")
    ap.add_argument(
        "--max-rows",
        type=int,
        default=40,
        help="Максимум строк для таблицы соседей (остальные только в статистике)",
    )
    ap.add_argument(
        "--pairs",
        type=Path,
        help="Файл: path1<TAB>path2 для контрольных пар «тот же объект»",
    )
    ap.add_argument(
        "--sample-different",
        type=int,
        default=200,
        help="Сколько случайных пар «разные» для сравнения с --pairs",
    )
    ap.add_argument("--seed", type=int, default=42, help="RNG для sample-different")
    ap.add_argument("--output", "-o", type=Path, help="Записать отчёт в файл (иначе stdout)")
    args = ap.parse_args()

    try:
        import numpy as np
    except ImportError:
        print("Requires numpy: pip install numpy", file=sys.stderr)
        return 2

    paths, embs, model = _load_rows(args.jsonl)
    n = len(paths)
    if n < 2:
        print("Нужно минимум 2 вектора в JSONL.", file=sys.stderr)
        return 2

    E = np.asarray(embs, dtype=np.float64)
    # численная нормализация на всякий случай
    norms = np.linalg.norm(E, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    E = E / norms

    sim = E @ E.T
    tri = np.triu_indices(n, k=1)
    off = sim[tri]
    pct = lambda q: float(np.percentile(off, q))

    lines_out: list[str] = []
    lines_out.append("# Cosine report (embed_cosine_report.py)\n")
    lines_out.append(f"- source: `{args.jsonl}`\n")
    lines_out.append(f"- rows: **{n}**, dim: **{E.shape[1]}**")
    if model:
        lines_out.append(f", model: `{model}`")
    lines_out.append("\n\n## Pairwise cosine (upper triangle, excluding diagonal)\n\n")
    lines_out.append(
        f"| min | p05 | median | mean | p95 | max |\n"
        f"|-----|-----|--------|------|-----|-----|\n"
        f"| {off.min():.4f} | {pct(5):.4f} | {pct(50):.4f} | {off.mean():.4f} | {pct(95):.4f} | {off.max():.4f} |\n"
    )

    path_to_i = {paths[i]: i for i in range(n)}
    if args.pairs and args.pairs.is_file():
        same_sims: list[float] = []
        bad = 0
        for ln, line in enumerate(args.pairs.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else line.split(None, 1)
            if len(parts) != 2:
                bad += 1
                continue
            a, b = parts[0].strip(), parts[1].strip()
            ia, ib = path_to_i.get(a), path_to_i.get(b)
            if ia is None or ib is None:
                bad += 1
                continue
            same_sims.append(float(sim[ia, ib]))
        lines_out.append("\n## Labeled pairs (--pairs)\n\n")
        if same_sims:
            arr = np.asarray(same_sims, dtype=np.float64)
            lines_out.append(f"- pairs matched: **{len(same_sims)}** (lines skipped: {bad})\n")
            lines_out.append(f"- cosine same-pairs: mean **{arr.mean():.4f}**, min **{arr.min():.4f}**, max **{arr.max():.4f}**\n")
            rng = random.Random(args.seed)
            diff_sims: list[float] = []
            attempts = 0
            while len(diff_sims) < min(args.sample_different, n * (n - 1) // 2) and attempts < args.sample_different * 20:
                attempts += 1
                i, j = rng.randrange(n), rng.randrange(n)
                if i == j:
                    continue
                if i > j:
                    i, j = j, i
                diff_sims.append(float(sim[i, j]))
            if diff_sims:
                darr = np.asarray(diff_sims, dtype=np.float64)
                lines_out.append(
                    f"- random different pairs (n={len(diff_sims)}): mean **{darr.mean():.4f}**, "
                    f"p95 **{float(np.percentile(darr, 95)):.4f}**\n"
                )
        else:
            lines_out.append(f"- no matched pairs (skipped lines: {bad})\n")

    k = max(0, int(args.topk))
    if k > 0:
        k = min(k, n - 1)
        lines_out.append(f"\n## Top-{k} neighbors (by cosine)\n\n")
        shown = min(n, max(1, args.max_rows))
        for i in range(shown):
            scores = sim[i].copy()
            scores[i] = -np.inf
            kk = min(k, n - 1)
            idx = np.argpartition(scores, -kk)[-kk:]
            idx = idx[np.argsort(scores[idx])[::-1][:kk]]
            lines_out.append(f"### `{i}` {paths[i][:80]}{'…' if len(paths[i]) > 80 else ''}\n\n")
            lines_out.append("| rank | idx | cosine | path |\n|---|---:|---:|---|\n")
            for rank, j in enumerate(idx, 1):
                lines_out.append(f"| {rank} | {int(j)} | {float(sim[i, j]):.4f} | `{paths[j][:120]}` |\n")
            lines_out.append("\n")
        if n > shown:
            lines_out.append(f"_… truncated: printed {shown}/{n} rows; raise --max-rows to show more._\n")

    text = "".join(lines_out)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

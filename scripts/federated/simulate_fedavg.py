#!/usr/bin/env python3
"""
Toy FedAvg vs pooled least-squares (#375 Phase 1).

Клиенты получают непересекающиеся куски данных из одной линейной модели
``y ≈ X @ w_true``. Локально — МНК; глобально — среднее локальных весов (FedAvg).
Сравниваем ``||w_fed - w_true||`` с ``||w_pool - w_true||``.

**Не продакшен:** нет DP, защиты от poisoning, TLS — только воспроизводимый численный пример.

::

    pip install numpy  # если нет в окружении
    python3 scripts/federated/simulate_fedavg.py --clients 5 --seed 1
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    try:
        import numpy as np
    except ImportError:
        print("pip install numpy", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--samples-per-client", type=int, default=200)
    ap.add_argument("--dim", type=int, default=8)
    ap.add_argument("--noise", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    d = max(2, args.dim)
    n_c = max(2, args.clients)
    m = max(20, args.samples_per_client)

    w_true = rng.normal(0, 1.0, size=d)

    X_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    for c in range(n_c):
        X = rng.normal(0, 1.0, size=(m, d))
        y = X @ w_true + rng.normal(0, args.noise, size=m)
        X_parts.append(X)
        y_parts.append(y)

    X_all = np.vstack(X_parts)
    y_all = np.concatenate(y_parts)

    # Pooled OLS: (X'X)^{-1} X'y
    w_pool, *_ = np.linalg.lstsq(X_all, y_all, rcond=None)

    w_locals: list[np.ndarray] = []
    for X, y in zip(X_parts, y_parts):
        w_c, *_ = np.linalg.lstsq(X, y, rcond=None)
        w_locals.append(w_c)

    w_fed = np.mean(np.stack(w_locals, axis=0), axis=0)

    err_pool = float(np.linalg.norm(w_pool - w_true))
    err_fed = float(np.linalg.norm(w_fed - w_true))

    out = {
        "schema": "fedavg_simulation_v1",
        "clients": n_c,
        "samples_per_client": m,
        "dim": d,
        "seed": args.seed,
        "l2_error_pooled_ols": round(err_pool, 6),
        "l2_error_fedavg_mean_locals": round(err_fed, 6),
        "disclaimer": "Toy linear regression — not production FL (#375).",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

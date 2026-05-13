"""Общая логистическая softmax-экспорт для behavior_logistic_export@v1 (скрипт + web, #416)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EXPORT_SCHEMA = "behavior_logistic_export@v1"


def fit_behavior_logistic_export(
    X_list: list[list[float]],
    y_list: list[str],
    *,
    max_iter: int = 500,
    seed: int = 42,
    feature_mode: str,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Any]:
    """Обучить LogisticRegression, вернуть (export_json, sklearn_clf).

    ``extra`` попадает в корень export (без перезаписи schema/labels/coef/intercept).
    """
    if len(X_list) != len(y_list):
        raise ValueError("X_list and y_list length mismatch")
    if len(X_list) < 4:
        raise ValueError(f"need at least 4 training rows, got {len(X_list)}")
    if len({str(y).strip().lower() for y in y_list if str(y).strip()}) < 2:
        raise ValueError("need at least 2 distinct non-empty labels")

    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as e:  # pragma: no cover - optional in some envs
        raise RuntimeError("scikit-learn is not installed") from e

    import numpy as np

    X = np.array(X_list, dtype=np.float64)
    y = np.array([str(lab).strip().lower() for lab in y_list])

    clf = LogisticRegression(
        max_iter=int(max_iter),
        random_state=int(seed),
        solver="lbfgs",
    )
    clf.fit(X, y)

    classes = [str(c) for c in clf.classes_]
    n_features = int(X.shape[1])
    raw_coef = np.asarray(clf.coef_, dtype=np.float64)
    raw_inter = np.asarray(clf.intercept_, dtype=np.float64).reshape(-1)
    if len(classes) == 2:
        w = raw_coef.reshape(-1)
        b = float(raw_inter[0]) if raw_inter.size else 0.0
        coef = [[0.0] * n_features, w.tolist()]
        intercept = [0.0, b]
    else:
        coef = raw_coef.tolist()
        intercept = raw_inter.tolist()

    export: dict[str, Any] = {
        "schema": EXPORT_SCHEMA,
        "feature_mode": str(feature_mode),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "labels": classes,
        "coef": coef,
        "intercept": intercept,
    }
    if extra:
        for k, v in extra.items():
            if k not in export:
                export[k] = v
    return export, clf

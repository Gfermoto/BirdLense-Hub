"""История показаний весов (JSONL) для оценки дельты за интервал записи — issue #167."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

FEEDER_SCALE_HISTORY_FILE = "feeder_scale_history.jsonl"


def _to_kg(weight: float, unit: str) -> float:
    u = (unit or "kg").strip().lower()[:8]
    if u in ("g", "gram", "grams"):
        return float(weight) / 1000.0
    return float(weight)


def weight_reading_to_kg(weight: float, unit: str) -> float:
    """Сырое значение с MQTT/конфига в килограммы (для порогов триггера и журнала)."""
    return _to_kg(weight, unit)


def append_feeder_scale_sample(data_dir: str, weight: float, unit: str, *, max_lines: int) -> None:
    """Добавить строку в журнал; при переполнении обрезать начало файла."""
    if max_lines < 100:
        max_lines = 100
    try:
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, FEEDER_SCALE_HISTORY_FILE)
        rec = {
            "t": datetime.now(timezone.utc).isoformat(),
            "weight": float(weight),
            "unit": (unit or "kg").strip().lower()[:8] or "kg",
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _trim_head_if_needed(path, max_lines)
    except OSError as e:
        logger.debug("append_feeder_scale_sample: %s", e)


def _trim_head_if_needed(path: str, max_lines: int) -> None:
    """Обрезать начало файла, если строк больше max_lines (соблюдение лимита, не только после 512 KiB)."""
    try:
        # Fast path: skip full read when file is small enough that it cannot exceed max_lines
        # (assume ~80 bytes/line average for scale JSONL).
        size = os.path.getsize(path)
        if size < max(4096, max_lines * 40):
            return
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    if len(lines) <= max_lines:
        return
    tail = lines[-max_lines:]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(tail)
    except OSError as e:
        logger.debug("scale history trim: %s", e)


def _parse_line(obj: dict[str, Any]) -> tuple[datetime | None, float | None]:
    raw_t = obj.get("t")
    if not isinstance(raw_t, str):
        return None, None
    try:
        ts = datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None, None
    try:
        w = float(obj.get("weight"))
    except (TypeError, ValueError):
        return None, None
    unit = str(obj.get("unit") or "kg")
    return ts, _to_kg(w, unit)


# Recording windows are short; reading the whole 10k-line JSONL on every finalize
# was a multi-second stall. Tail-read recent bytes and stop once timestamps leave the window.
_ESTIMATE_TAIL_MAX_BYTES = 512 * 1024
_ESTIMATE_MAX_RUNTIME_SEC = 0.75


def _iter_jsonl_lines_from_tail(path: str, *, max_bytes: int = _ESTIMATE_TAIL_MAX_BYTES):
    """Yield non-empty lines from the end of a JSONL file (oldest→newest within the tail)."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size <= 0:
            return
        start = max(0, size - max(4096, int(max_bytes)))
        f.seek(start)
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    if start > 0:
        # Drop partial first line when we mid-seeked into the file.
        nl = text.find("\n")
        if nl >= 0:
            text = text[nl + 1 :]
    for line in text.splitlines():
        s = line.strip()
        if s:
            yield s


def estimate_weight_delta_kg(
    data_dir: str,
    start: datetime,
    end: datetime,
    *,
    min_delta_kg: float,
    min_samples: int = 2,
    require_consecutive_spike: bool = True,
    max_runtime_sec: float = _ESTIMATE_MAX_RUNTIME_SEC,
    tail_max_bytes: int = _ESTIMATE_TAIL_MAX_BYTES,
) -> tuple[float | None, int]:
    """Оценка размаха веса за окно [start, end] (UTC).

    По умолчанию сохраняем оценку только если был **скачок**: максимальный шаг между
    соседними по времени показаниями >= min_delta_kg (отсекает медленный дрейф при почти
    нулевой платформе после тары). Величина в БД — по-прежнему max-min по всем точкам окна.

    Reads only a recent tail of the history file (O(tail) not O(full file)).
    """
    import time as _time

    path = os.path.join(data_dir, FEEDER_SCALE_HISTORY_FILE)
    if not os.path.isfile(path):
        return None, 0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    else:
        end = end.astimezone(timezone.utc)

    deadline = _time.perf_counter() + max(0.05, float(max_runtime_sec or _ESTIMATE_MAX_RUNTIME_SEC))
    pairs: list[tuple[datetime, float]] = []
    try:
        # Walk newest→oldest so we can stop once we leave the window's past edge.
        lines = list(_iter_jsonl_lines_from_tail(path, max_bytes=tail_max_bytes))
        for line in reversed(lines):
            if _time.perf_counter() >= deadline:
                logger.debug("estimate_weight_delta_kg: runtime budget exhausted")
                break
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            ts, w_kg = _parse_line(obj)
            if ts is None or w_kg is None:
                continue
            if ts > end:
                continue
            if ts < start:
                # Further older lines (still going backward) are also < start.
                break
            pairs.append((ts, w_kg))
    except OSError as e:
        logger.debug("estimate_weight_delta_kg read: %s", e)
        return None, 0

    pairs.sort(key=lambda p: p[0])
    ws = [p[1] for p in pairs]
    n = len(ws)
    if n < min_samples:
        return None, n
    min_d = float(min_delta_kg)
    span = max(ws) - min(ws)
    if span < min_d:
        return None, n
    if require_consecutive_spike:
        max_step = max(abs(ws[i] - ws[i - 1]) for i in range(1, n))
        if max_step < min_d:
            return None, n
    return float(span), n

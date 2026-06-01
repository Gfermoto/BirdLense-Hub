"""Персистентная очередь BirdNET в hub SQLite: WAL, фоновая запись, гидратация (#269)."""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def hub_sqlite_path(data_dir: str) -> str:
    """Путь к birdlense.db как у Flask Config (DATA_DIR/db/birdlense.db)."""
    base = (data_dir or "").strip() or "data"
    return os.path.join(base, "db", "birdlense.db")


def processor_birdnet_persist_db_path(data_dir: str) -> str | None:
    """Путь к SQLite для записи процессором; None если hub на PostgreSQL (нет общего sqlite-файла)."""
    url = (os.environ.get("DATABASE_URL") or "").strip().lower()
    if url.startswith("postgresql"):
        logger.info(
            "BirdNET FIFO SQLite persist skipped: DATABASE_URL is PostgreSQL "
            "(processor uses only file SQLite; use default SQLite hub for #269).",
        )
        return None
    return hub_sqlite_path(data_dir)


def _parse_iso8601_utc(value) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def prune_birdnet_event_list(
    events: Sequence[dict],
    *,
    now: datetime,
    ttl_hours: float,
    cap: int,
) -> list[dict]:
    """Та же семантика, что у MQTTEventAggregator._prune_birdnet_events_locked (TTL + FIFO cap)."""
    try:
        ttl_hours = float(ttl_hours)
    except (TypeError, ValueError):
        ttl_hours = 25.0
    ttl_hours = max(1.0, min(ttl_hours, 168.0))
    low_epoch = now.timestamp() - (ttl_hours * 3600.0)
    kept: list[dict] = []
    for ev in events:
        ts_epoch = ev.get("_ts_epoch")
        if ts_epoch is None:
            ts = _parse_iso8601_utc(ev.get("timestamp"))
            if ts is None:
                continue
            ts_epoch = ts.timestamp()
            ev["_ts_epoch"] = ts_epoch
        else:
            ts = _parse_iso8601_utc(ev.get("timestamp"))
            if ts is not None:
                parsed_epoch = ts.timestamp()
                if abs(float(parsed_epoch) - float(ts_epoch)) > 1.0:
                    ts_epoch = parsed_epoch
                    ev["_ts_epoch"] = ts_epoch
        if float(ts_epoch) >= low_epoch:
            kept.append(ev)
    overflow = max(0, len(kept) - int(cap))
    if overflow:
        kept = kept[overflow:]
    return kept


def hydrate_birdnet_events_from_db(
    db_path: str,
    *,
    ttl_hours: float,
    cap: int,
    now: datetime | None = None,
) -> list[dict]:
    """Загрузить события из SQLite и применить TTL/cap (старт процессора после рестарта)."""
    now = now or datetime.now(timezone.utc)
    if not os.path.isfile(db_path):
        return []
    raw: list[dict] = []
    try:
        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='birdnet_fifo_event'",
            ).fetchone()
            if not row:
                return []
            cur = conn.execute(
                "SELECT payload FROM birdnet_fifo_event ORDER BY id ASC",
            )
            for (blob,) in cur.fetchall():
                if not blob:
                    continue
                if isinstance(blob, str):
                    ev = json.loads(blob)
                else:
                    ev = json.loads(blob.decode("utf-8"))
                if isinstance(ev, dict):
                    raw.append(ev)
        finally:
            conn.close()
    except Exception:
        logger.exception("BirdNET FIFO hydrate failed (path=%s)", db_path)
        return []
    return prune_birdnet_event_list(raw, now=now, ttl_hours=ttl_hours, cap=cap)


class BirdnetFifoPersist:
    """Фоновая запись INSERT + prune в hub SQLite (не блокирует MQTT callback)."""

    def __init__(self, db_path: str, *, busy_timeout_ms: int = 30000, queue_max: int = 8000):
        self.db_path = db_path
        self._busy_timeout_ms = max(1000, int(busy_timeout_ms))
        self._q: queue.Queue[Any] = queue.Queue(maxsize=max(100, int(queue_max)))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        t = threading.Thread(target=self._run, daemon=True, name="birdlense-birdnet-fifo-sqlite")
        t.start()
        self._thread = t

    def enqueue_insert(self, ev: dict) -> None:
        try:
            self._q.put_nowait(("insert", ev))
        except queue.Full:
            logger.warning("BirdNET FIFO persist queue full; drop insert")

    def enqueue_prune(self, low_epoch: float, cap: int) -> None:
        try:
            self._q.put_nowait(("prune", float(low_epoch), int(cap)))
        except queue.Full:
            logger.warning("BirdNET FIFO persist queue full; drop prune")

    def wait_queue_drained(self) -> None:
        """Дождаться обработки всех уже поставленных задач (тесты / отладка)."""
        self._q.join()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(
            self.db_path,
            timeout=self._busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS birdnet_fifo_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_epoch REAL NOT NULL,
                payload TEXT NOT NULL
            )""",
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_birdnet_fifo_event_ts_epoch ON birdnet_fifo_event (ts_epoch)",
        )

    @staticmethod
    def _execute_with_retry(
        conn: sqlite3.Connection,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        retries: int = 6,
        retry_delay_s: float = 0.12,
    ) -> None:
        for attempt in range(max(1, retries)):
            try:
                conn.execute(query, params)
                return
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "locked" not in msg and "busy" not in msg:
                    raise
                if attempt >= retries - 1:
                    raise
                # DB lock contention is expected during startup migration/finalize bursts.
                # Retry instead of crashing worker and dropping persistence.
                threading.Event().wait(retry_delay_s * (attempt + 1))

    def _commit_with_retry(
        self,
        conn: sqlite3.Connection,
        *,
        retries: int = 6,
        retry_delay_s: float = 0.12,
    ) -> None:
        for attempt in range(max(1, retries)):
            try:
                conn.commit()
                return
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "locked" not in msg and "busy" not in msg:
                    raise
                if attempt >= retries - 1:
                    raise
                threading.Event().wait(retry_delay_s * (attempt + 1))

    def _run(self) -> None:
        try:
            conn = self._connect()
        except Exception:
            logger.exception("BirdNET FIFO persist: cannot open %s", self.db_path)
            return
        try:
            self._ensure_table(conn)
            conn.commit()
        except Exception:
            logger.exception("BirdNET FIFO persist: schema init failed")
            try:
                conn.close()
            except OSError as e:
                logger.debug("BirdNET FIFO persist: conn.close after schema error: %s", e, exc_info=True)
            return

        while True:
            item = self._q.get()
            try:
                if item is None:
                    break
                if item[0] == "insert":
                    _, ev = item
                    try:
                        ts = float(ev.get("_ts_epoch") or 0.0)
                    except (TypeError, ValueError):
                        ts = 0.0
                    payload = json.dumps(ev, separators=(",", ":"), ensure_ascii=False, default=str)
                    self._execute_with_retry(
                        conn,
                        "INSERT INTO birdnet_fifo_event (ts_epoch, payload) VALUES (?, ?)",
                        (ts, payload),
                    )
                    self._commit_with_retry(conn)
                elif item[0] == "prune":
                    _, low_epoch, cap = item
                    self._execute_with_retry(
                        conn,
                        "DELETE FROM birdnet_fifo_event WHERE ts_epoch < ?",
                        (low_epoch,),
                    )
                    row = conn.execute("SELECT COUNT(*) FROM birdnet_fifo_event").fetchone()
                    n = int(row[0]) if row else 0
                    excess = max(0, n - int(cap))
                    if excess:
                        self._execute_with_retry(
                            conn,
                            """DELETE FROM birdnet_fifo_event WHERE id IN (
                                SELECT id FROM birdnet_fifo_event ORDER BY id ASC LIMIT ?
                            )""",
                            (excess,),
                        )
                    self._commit_with_retry(conn)
            except Exception:
                logger.exception("BirdNET FIFO persist worker error")
            finally:
                self._q.task_done()

        try:
            conn.close()
        except OSError as e:
            logger.debug("BirdNET FIFO persist: conn.close on worker stop: %s", e, exc_info=True)

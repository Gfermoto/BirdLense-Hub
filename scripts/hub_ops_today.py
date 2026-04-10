#!/usr/bin/env python3
"""Одноразовые операции на хабе: удалить визиты за UTC-сегодня (тесты). Запуск: см. Makefile."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--db",
        default="/app/data/db/birdlense.db",
        help="Путь к SQLite (в контейнере по умолчанию /app/data/db/birdlense.db)",
    )
    p.add_argument(
        "--day",
        default=None,
        help="Дата YYYY-MM-DD (по умолчанию UTC today)",
    )
    args = p.parse_args()
    day = args.day or date.today().isoformat()
    con = sqlite3.connect(args.db)
    cur = con.cursor()
    cur.execute(
        "SELECT id FROM species_visit WHERE date(start_time) = ?",
        (day,),
    )
    ids = [r[0] for r in cur.fetchall()]
    print(f"species_visit day={day} count={len(ids)}", flush=True)
    if not ids:
        return 0
    for vid in ids:
        cur.execute(
            "UPDATE video_species SET species_visit_id = NULL WHERE species_visit_id = ?",
            (vid,),
        )
    cur.execute("DELETE FROM species_visit WHERE date(start_time) = ?", (day,))
    con.commit()
    left = cur.execute(
        "SELECT COUNT(*) FROM species_visit WHERE date(start_time) = ?",
        (day,),
    ).fetchone()[0]
    print(f"after_delete remaining_for_day={left}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

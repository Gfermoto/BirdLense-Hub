#!/usr/bin/env python3
"""Deduplicate Video rows by stable identity keys."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iter_video_duplicate_groups(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          video_path,
          start_time,
          end_time,
          processor_version,
          COUNT(*) AS c
        FROM video
        WHERE deleted_at IS NULL
        GROUP BY video_path, start_time, end_time, processor_version
        HAVING c > 1
        ORDER BY c DESC, video_path ASC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for video_path, start_time, end_time, processor_version, count in rows:
        ids = [
            int(row[0])
            for row in conn.execute(
                """
                SELECT id
                FROM video
                WHERE deleted_at IS NULL
                  AND video_path = ?
                  AND start_time = ?
                  AND end_time = ?
                  AND processor_version = ?
                ORDER BY id ASC
                """,
                (video_path, start_time, end_time, processor_version),
            ).fetchall()
        ]
        if len(ids) > 1:
            out.append(
                {
                    'video_path': video_path,
                    'start_time': start_time,
                    'end_time': end_time,
                    'processor_version': processor_version,
                    'ids': ids,
                }
            )
    return out


def _tables_with_video_id(conn: sqlite3.Connection) -> list[str]:
    tables = [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    out: list[str] = []
    for table in tables:
        if table in {'video'}:
            continue
        cols = [
            str(row[1])
            for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        ]
        if 'video_id' in cols:
            out.append(table)
    return sorted(set(out))


def _dedupe_video_species_rows(conn: sqlite3.Connection) -> int:
    cols = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info('video_species')").fetchall()
    }
    nickname_key = (
        "COALESCE(individual_nickname, '')"
        if 'individual_nickname' in cols
        else "''"
    )
    before = conn.total_changes
    conn.execute(
        f"""
        DELETE FROM video_species
        WHERE id NOT IN (
          SELECT MIN(id) FROM video_species
          GROUP BY
            video_id,
            species_id,
            start_time,
            end_time,
            confidence,
            COALESCE(track_id, -1),
            COALESCE(detection_provider, ''),
            COALESCE(source, ''),
            {nickname_key}
        )
        """
    )
    return int(conn.total_changes - before)


def dedupe_video_records(db_path: str, dry_run: bool = False) -> dict[str, Any]:
    """Merge duplicate videos and remap dependent rows."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('BEGIN')
        groups = _iter_video_duplicate_groups(conn)
        tables = _tables_with_video_id(conn)
        moved_by_table: dict[str, int] = {name: 0 for name in tables}
        deleted_video_ids: list[int] = []

        for group in groups:
            ids = [int(x) for x in (group.get('ids') or [])]
            if len(ids) < 2:
                continue
            keeper = ids[0]
            duplicates = ids[1:]
            for duplicate_id in duplicates:
                for table in tables:
                    if table == 'video_bird_food_association':
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO video_bird_food_association
                              (video_id, birdfood_id)
                            SELECT ?, birdfood_id
                            FROM video_bird_food_association
                            WHERE video_id = ?
                            """,
                            (keeper, duplicate_id),
                        )
                        before = conn.total_changes
                        conn.execute(
                            "DELETE FROM video_bird_food_association WHERE video_id = ?",
                            (duplicate_id,),
                        )
                        moved_by_table[table] += int(
                            conn.total_changes - before
                        )
                        continue
                    before = conn.total_changes
                    conn.execute(
                        f'UPDATE {table} SET video_id = ? WHERE video_id = ?',
                        (keeper, duplicate_id),
                    )
                    moved_by_table[table] += int(conn.total_changes - before)
                deleted_video_ids.append(duplicate_id)

        deduped_video_species_rows = 0
        if 'video_species' in tables:
            deduped_video_species_rows = _dedupe_video_species_rows(conn)

        deleted_video_rows = 0
        if deleted_video_ids:
            before = conn.total_changes
            conn.executemany(
                'DELETE FROM video WHERE id = ?',
                [(int(v),) for v in sorted(set(deleted_video_ids))],
            )
            deleted_video_rows = int(conn.total_changes - before)

        out = {
            'schema': 'dedupe_video_records@v1',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'db_path': db_path,
            'duplicate_groups': int(len(groups)),
            'deleted_video_rows': int(deleted_video_rows),
            'deduped_video_species_rows': int(deduped_video_species_rows),
            'moved_rows_by_table': moved_by_table,
            'dry_run': bool(dry_run),
        }
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
        return out
    finally:
        conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    out = dedupe_video_records(
        db_path=str(args.db),
        dry_run=bool(args.dry_run),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

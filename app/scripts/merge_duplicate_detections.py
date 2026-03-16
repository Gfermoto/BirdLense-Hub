#!/usr/bin/env python3
"""
Слияние дубликатов VideoSpecies в старых записях (raw SQLite, без Flask).

В одном видео несколько детекций одного вида — объединяем в одну.
Запуск: docker exec birdlense python /app/scripts/merge_duplicate_detections.py
"""
import os
import json
import sqlite3

DB_PATH = os.environ.get('DATA_DIR', '/app/data') + '/db/birdlense.db'


def main():
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Найти (video_id, species_id) с count > 1
    cur.execute("""
        SELECT video_id, species_id
        FROM video_species
        WHERE source = 'video'
        GROUP BY video_id, species_id
        HAVING COUNT(*) > 1
    """)
    dupes = cur.fetchall()

    if not dupes:
        print("No duplicate detections found.")
        conn.close()
        return

    merged = 0
    for row in dupes:
        video_id, species_id = row['video_id'], row['species_id']
        cur.execute("""
            SELECT id, start_time, end_time, confidence, frames, track_id, species_visit_id
            FROM video_species
            WHERE video_id=? AND species_id=? AND source='video'
            ORDER BY confidence DESC
        """, (video_id, species_id))
        group = [dict(r) for r in cur.fetchall()]
        if len(group) < 2:
            continue

        keep = group[0]
        to_remove = group[1:]
        start = keep['start_time']
        end = keep['end_time']
        conf = keep['confidence']
        all_frames = []
        if keep['frames']:
            try:
                all_frames = json.loads(keep['frames']) if isinstance(keep['frames'], str) else keep['frames']
            except (json.JSONDecodeError, TypeError):
                pass

        for vs in to_remove:
            start = min(start, vs['start_time'])
            end = max(end, vs['end_time'])
            conf = max(conf, vs['confidence'])
            if vs['frames']:
                try:
                    f = json.loads(vs['frames']) if isinstance(vs['frames'], str) else vs['frames']
                    if f:
                        all_frames.extend(f)
                except (json.JSONDecodeError, TypeError):
                    pass

        frames_json = json.dumps(all_frames[:100]) if all_frames else keep['frames']

        cur.execute("""
            UPDATE video_species
            SET start_time=?, end_time=?, confidence=?, frames=?
            WHERE id=?
        """, (start, end, conf, frames_json, keep['id']))

        visits_to_del = []
        for vs in to_remove:
            cur.execute("DELETE FROM video_species WHERE id=?", (vs['id'],))
            merged += 1
            if vs['species_visit_id'] and vs['species_visit_id'] != keep['species_visit_id']:
                visits_to_del.append(vs['species_visit_id'])

        for vid in set(visits_to_del):
            cur.execute("SELECT COUNT(*) FROM video_species WHERE species_visit_id=?", (vid,))
            if cur.fetchone()[0] == 0:
                cur.execute("DELETE FROM species_visit WHERE id=?", (vid,))

    conn.commit()
    conn.close()
    print(f"Merged {merged} duplicate detections in {len(dupes)} groups.")


if __name__ == '__main__':
    main()

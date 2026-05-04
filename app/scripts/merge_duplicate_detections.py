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


def _first_non_empty(group, key):
    for row in group:
        val = row.get(key)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        return val
    return None


def _first_non_null(group, key):
    for row in group:
        val = row.get(key)
        if val is not None:
            return val
    return None


def main():
    """Merge duplicate per-video species rows without losing identity flags."""
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cols = {
        str(row['name'])
        for row in cur.execute(
            "PRAGMA table_info('video_species')"
        ).fetchall()
    }

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
        print('No duplicate detections found.')
        conn.close()
        return

    merged = 0
    for row in dupes:
        video_id, species_id = row['video_id'], row['species_id']
        cur.execute(
            """
            SELECT *
            FROM video_species
            WHERE video_id=? AND species_id=? AND source='video'
            ORDER BY confidence DESC
            """,
            (video_id, species_id),
        )
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
                all_frames = (
                    json.loads(keep['frames'])
                    if isinstance(keep['frames'], str)
                    else keep['frames']
                )
            except (json.JSONDecodeError, TypeError):
                pass

        for vs in to_remove:
            start = min(start, vs['start_time'])
            end = max(end, vs['end_time'])
            conf = max(conf, vs['confidence'])
            if vs['frames']:
                try:
                    f = (
                        json.loads(vs['frames'])
                        if isinstance(vs['frames'], str)
                        else vs['frames']
                    )
                    if f:
                        all_frames.extend(f)
                except (json.JSONDecodeError, TypeError):
                    pass

        frames_json = json.dumps(all_frames[:100]) if all_frames else keep['frames']
        update_fields = {
            'start_time': start,
            'end_time': end,
            'confidence': conf,
            'frames': frames_json,
        }
        if 'individual_nickname' in cols:
            nickname = _first_non_empty(
                [keep] + to_remove,
                'individual_nickname',
            )
            update_fields['individual_nickname'] = nickname
        if 'detection_provider' in cols:
            provider = _first_non_empty(
                [keep] + to_remove,
                'detection_provider',
            )
            update_fields['detection_provider'] = provider
        if 'track_id' in cols:
            track_id = _first_non_null([keep] + to_remove, 'track_id')
            update_fields['track_id'] = track_id
        if 'species_visit_id' in cols:
            species_visit_id = _first_non_null(
                [keep] + to_remove,
                'species_visit_id',
            )
            update_fields['species_visit_id'] = species_visit_id
        if 'manually_corrected' in cols:
            manually_corrected = any(
                bool(v.get('manually_corrected'))
                for v in [keep] + to_remove
            )
            update_fields['manually_corrected'] = 1 if manually_corrected else 0
        if 'classifier_needs_review' in cols:
            classifier_needs_review = any(
                bool(v.get('classifier_needs_review'))
                for v in [keep] + to_remove
            )
            update_fields['classifier_needs_review'] = (
                1 if classifier_needs_review else 0
            )
        if 'review_reason' in cols:
            review_reason = _first_non_empty(
                [keep] + to_remove,
                'review_reason',
            )
            update_fields['review_reason'] = review_reason

        set_sql = ', '.join([f'{k}=?' for k in update_fields.keys()])
        params = list(update_fields.values()) + [keep['id']]
        cur.execute(
            f"UPDATE video_species SET {set_sql} WHERE id=?",
            params,
        )

        visits_to_del = []
        for vs in to_remove:
            cur.execute('DELETE FROM video_species WHERE id=?', (vs['id'],))
            merged += 1
            if (
                vs['species_visit_id']
                and vs['species_visit_id'] != keep['species_visit_id']
            ):
                visits_to_del.append(vs['species_visit_id'])

        for vid in set(visits_to_del):
            cur.execute(
                'SELECT COUNT(*) FROM video_species WHERE species_visit_id=?',
                (vid,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute('DELETE FROM species_visit WHERE id=?', (vid,))

    conn.commit()
    conn.close()
    print(f"Merged {merged} duplicate detections in {len(dupes)} groups.")


if __name__ == '__main__':
    main()

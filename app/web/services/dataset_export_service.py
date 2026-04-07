"""Export dataset crops as ZIP archive and move on species correction."""
import glob
import hashlib
import io
import json
import logging
import os
import random
import re
import shutil
import struct
import zipfile
from datetime import datetime, timezone

from util import data_dir

logger = logging.getLogger(__name__)

# Full-frame heuristic: bird crops typically < 0.5 MP and aspect ratio not 16:9/4:3
MIN_PIXELS_FULLFRAME = 480_000  # 800×600
ASPECT_16_9 = 16 / 9
ASPECT_4_3 = 4 / 3
ASPECT_TOLERANCE = 0.15  # ±15%


def _get_image_dimensions(path: str) -> tuple[int, int] | None:
    """Read image dimensions from file (JPEG/PNG) without full decode. Returns (width, height)."""
    try:
        with open(path, 'rb') as f:
            header = f.read(64 * 1024)
    except OSError:
        return None
    if len(header) < 24:
        return None
    # JPEG: find SOF0 (0xFF 0xC0), skip 5 bytes, then height(2) width(2) big-endian
    if header[:2] == b'\xff\xd8':
        i = 2
        while i < len(header) - 9:
            if header[i] == 0xFF and header[i + 1] == 0xC0:
                h, w = struct.unpack('>HH', header[i + 5 : i + 9])
                return (w, h)
            if header[i] != 0xFF:
                i += 1
                continue
            marker = header[i + 1]
            i += 2
            if i + 2 <= len(header):
                length = struct.unpack('>H', header[i : i + 2])[0]
                i += 2 + length
            else:
                break
        return None
    # PNG: 8 sig + 4 len + 4 "IHDR" + 4 width + 4 height
    if header[:8] == b'\x89PNG\r\n\x1a\n' and len(header) >= 24:
        w, h = struct.unpack('>II', header[16:24])
        return (w, h)
    return None


def _is_likely_fullframe(width: int, height: int) -> bool:
    """True if dimensions suggest full video frame (16:9 or 4:3, large)."""
    if width <= 0 or height <= 0:
        return False
    pixels = width * height
    if pixels < MIN_PIXELS_FULLFRAME:
        return False
    aspect = width / height
    return (
        abs(aspect - ASPECT_16_9) < ASPECT_TOLERANCE
        or abs(aspect - ASPECT_4_3) < ASPECT_TOLERANCE
    )


def _parse_video_track_from_filename(fname: str) -> tuple[int, int] | None:
    """Parse video_id and track_id from crop name ``{vid}_{tid}_{...}.jpg``."""
    base = fname.replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
    parts = base.split('_')
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _split_train_val_test(
    shuffled: list,
    test_ratio: float,
    val_ratio: float,
) -> tuple[list, list, list]:
    """Deterministic 3-way split on a shuffled list. Ratios apply to remaining after test."""
    n = len(shuffled)
    n_test = int(n * test_ratio)
    if n > 0 and n_test >= n:
        n_test = max(0, n - 1)
    rest = shuffled[n_test:]
    rem = len(rest)
    n_val = int(rem * val_ratio) if rem else 0
    if rem > 1 and val_ratio > 0 and n_val == 0:
        n_val = 1
    if rem > 0 and n_val >= rem:
        n_val = max(0, rem - 1)
    test_rows = shuffled[:n_test]
    val_rows = rest[:n_val]
    train_rows = rest[n_val:]
    return train_rows, val_rows, test_rows


def _season_key(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    month = int(dt.month)
    if month in (12, 1, 2):
        return 'winter'
    if month in (3, 4, 5):
        return 'spring'
    if month in (6, 7, 8):
        return 'summer'
    return 'autumn'


def _video_metadata_for_ids(video_ids: set[int]) -> dict[int, dict]:
    """Return video grouping metadata used by grouped train/val/test split."""
    if not video_ids:
        return {}
    try:
        from models import Video

        rows = (
            Video.query.filter(Video.id.in_(video_ids))
            .with_entities(Video.id, Video.start_time, Video.video_path)
            .all()
        )
    except Exception:
        # No DB/app context available (e.g. unit tests that call this function
        # without creating an app). Return empty metadata to allow file-only
        # dataset generation.
        return {}
    out: dict[int, dict] = {}
    for video_id, start_time, video_path in rows:
        day_key = None
        month_key = None
        season_key = None
        if start_time is not None:
            day_key = start_time.strftime('%Y-%m-%d')
            month_key = start_time.strftime('%Y-%m')
            season_key = _season_key(start_time)
        out[int(video_id)] = {
            'day_key': day_key,
            'month_key': month_key,
            'season_key': season_key,
            # Camera metadata is not persisted on Video yet; keep strategy explicit.
            'group_key': day_key or f'video:{int(video_id)}',
            'video_path': video_path,
        }
    return out


def _group_key_for_filename(fname: str, video_meta: dict[int, dict]) -> str:
    vt = _parse_video_track_from_filename(fname)
    if not vt:
        return f'file:{fname}'
    video_id, _track_id = vt
    meta = video_meta.get(video_id) or {}
    return meta.get('group_key') or f'video:{video_id}'


def _split_grouped_train_val_test(
    shuffled: list[tuple[str, str]],
    test_ratio: float,
    val_ratio: float,
    *,
    split_seed: int,
    video_meta: dict[int, dict],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]], dict]:
    """Split rows by stable group key so related examples stay in one split."""
    from collections import defaultdict

    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in shuffled:
        _src, fname = row
        groups[_group_key_for_filename(fname, video_meta)].append(row)

    grouped_rows = list(groups.items())
    rng = random.Random(split_seed)
    rng.shuffle(grouped_rows)
    grouped_rows.sort(key=lambda item: (-len(item[1]), item[0]))

    total_items = sum(len(rows) for _group, rows in grouped_rows)
    target_test = int(total_items * test_ratio)
    target_val = int((total_items - target_test) * val_ratio)

    train_rows: list[tuple[str, str]] = []
    val_rows: list[tuple[str, str]] = []
    test_rows: list[tuple[str, str]] = []
    split_groups = {'train': [], 'val': [], 'test': []}

    test_count = 0
    val_count = 0
    for idx, (group_key, rows) in enumerate(grouped_rows):
        remaining_groups = len(grouped_rows) - idx
        remaining_after = max(0, remaining_groups - 1)
        force_train = remaining_after == 0
        if not force_train and target_test > 0 and (
            test_count < target_test or not test_rows
        ):
            test_rows.extend(rows)
            split_groups['test'].append(group_key)
            test_count += len(rows)
            continue
        if not force_train and target_val > 0 and (
            val_count < target_val or not val_rows
        ):
            val_rows.extend(rows)
            split_groups['val'].append(group_key)
            val_count += len(rows)
            continue
        train_rows.extend(rows)
        split_groups['train'].append(group_key)

    return train_rows, val_rows, test_rows, {
        'group_count': len(grouped_rows),
        'groups_per_split': {
            key: len(value) for key, value in split_groups.items()
        },
    }


def _quality_report_from_entries(
    entries: list[tuple],
    video_meta: dict[int, dict] | None = None,
) -> dict:
    """
    entries: (split, class_name, filename).
    Detect duplicate (video_id, track_id) across export and video leakage across splits.
    """
    from collections import defaultdict

    track_locations: dict[tuple[int, int], list[str]] = defaultdict(list)
    videos_per_split: dict[str, set[int]] = defaultdict(set)
    groups_per_split: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        split, _cls, fname = entry[:3]
        explicit_group = entry[3] if len(entry) > 3 else None
        vt = _parse_video_track_from_filename(fname)
        if vt:
            track_locations[vt].append(f'{split}/{fname}')
            videos_per_split[split].add(vt[0])
            if explicit_group:
                groups_per_split[split].add(str(explicit_group))
            elif video_meta:
                meta = video_meta.get(vt[0]) or {}
                group_key = meta.get('group_key')
                if group_key:
                    groups_per_split[split].add(str(group_key))
    duplicate_tracks = sorted(
        f'{a}_{b}' for (a, b), locs in track_locations.items() if len(locs) > 1
    )
    tr = videos_per_split.get('train', set())
    va = videos_per_split.get('val', set())
    te = videos_per_split.get('test', set())
    gtr = groups_per_split.get('train', set())
    gva = groups_per_split.get('val', set())
    gte = groups_per_split.get('test', set())
    return {
        'duplicate_track_keys': duplicate_tracks,
        'duplicate_track_count': len(duplicate_tracks),
        'video_leakage': {
            'train_val_shared': len(tr & va),
            'train_test_shared': len(tr & te),
            'val_test_shared': len(va & te),
        },
        'group_leakage': {
            'train_val_shared': len(gtr & gva),
            'train_test_shared': len(gtr & gte),
            'val_test_shared': len(gva & gte),
        },
    }


def _slice_report_from_entries(entries: list[tuple], video_meta: dict[int, dict]) -> dict:
    """Summarize dataset slices by month and season for each split."""
    from collections import defaultdict

    months: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    seasons: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entry in entries:
        split, _cls, fname = entry[:3]
        vt = _parse_video_track_from_filename(fname)
        if not vt:
            continue
        video_id, _track_id = vt
        meta = video_meta.get(video_id) or {}
        month_key = meta.get('month_key')
        season_key = meta.get('season_key')
        if month_key:
            months[split][month_key] += 1
        if season_key:
            seasons[split][season_key] += 1
    return {
        'months': {split: dict(values) for split, values in months.items()},
        'seasons': {split: dict(values) for split, values in seasons.items()},
    }


def _sanitize_dirname(name: str) -> str:
    """Sanitize species name for directory. Must match dataset_saver."""
    s = re.sub(r'[<>:"/\\|?*]', '_', str(name).strip())
    s = re.sub(r'\s+', ' ', s).strip()
    return s or 'unknown'


def _video_ids_in_period(start_date: str | None, end_date: str | None) -> set[int] | None:
    """Return set of video_ids in period, or None if no filter."""
    if not start_date and not end_date:
        return None
    from datetime import datetime, timezone, timedelta
    from models import Video
    q = Video.query
    if start_date:
        try:
            dt_start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            q = q.filter(Video.start_time >= dt_start)
        except ValueError:
            pass
    if end_date:
        try:
            dt_end = datetime.strptime(end_date, '%Y-%m-%d').replace(
                tzinfo=timezone.utc
            ) + timedelta(days=1)
            q = q.filter(Video.start_time < dt_end)
        except ValueError:
            pass
    return {r[0] for r in q.with_entities(Video.id).all()}


def _manually_corrected_video_tracks() -> set[tuple[int, int]] | None:
    """Set of (video_id, track_id) for manually corrected VideoSpecies. None = no filter."""
    from models import VideoSpecies
    rows = VideoSpecies.query.filter(
        VideoSpecies.source == 'video',
        VideoSpecies.manually_corrected == True,
    ).with_entities(VideoSpecies.video_id, VideoSpecies.track_id).all()
    if not rows:
        return set()
    return {(r[0], r[1] or 0) for r in rows}


def build_dataset_zip(
    start_date: str | None = None,
    end_date: str | None = None,
    only_manually_corrected: bool = False,
    ready_for_train: bool = False,
    val_ratio: float = 0.2,
    test_ratio: float = 0.0,
    split_seed: int = 42,
    min_images_per_class: int = 1,
    strict_quality: bool = False,
) -> tuple[bytes | None, str | None]:
    """
    Build ZIP archive from data/dataset/train and val (if exists).
    start_date, end_date: YYYY-MM-DD — только кадры из видео за период. None = все.
    only_manually_corrected: только кропы вручную исправленных детекций (правильные виды).
    ready_for_train: автоматически собрать train/val из train (без внешнего скрипта).
    val_ratio: доля валидации для ready_for_train.
    test_ratio: доля hold-out test (только при ready_for_train); иначе 0.
    split_seed: seed для детерминированного split.
    min_images_per_class: минимальный размер класса для включения в экспорт.
    strict_quality: если True — отменить экспорт при дубликатах треков, leakage видео между сплитами
        или при наличии классов, не попавших в выгрузку из-за min_images_per_class (только ready_for_train).
    Returns (zip_bytes, error_message). On success error_message is None.
    """
    base = data_dir()
    dataset_base = os.path.join(base, 'dataset')
    if not os.path.isdir(dataset_base):
        return None, (
            'Dataset folder not found. '
            'Enable "Save dataset crops" and record videos.'
        )

    video_ids_ok = _video_ids_in_period(start_date, end_date)
    manual_tracks = _manually_corrected_video_tracks() if only_manually_corrected else None

    if val_ratio < 0 or val_ratio >= 1:
        return None, 'val_ratio must be in [0, 1)'
    if test_ratio < 0 or test_ratio >= 1:
        return None, 'test_ratio must be in [0, 1)'
    if min_images_per_class < 1:
        return None, 'min_images_per_class must be >= 1'

    info = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'train': {},
        'val': {},
        'test': {},
        'total_images': 0,
        'excluded_fullframe': 0,
        'ready_for_train': bool(ready_for_train),
        'val_ratio': float(val_ratio),
        'test_ratio': float(test_ratio),
        'split_seed': int(split_seed),
        'min_images_per_class': int(min_images_per_class),
        'classes_skipped_too_small': [],
    }
    export_entries: list[tuple[str, str, str]] = []
    skipped_small: list[str] = []
    filtered_video_ids: set[int] = set()

    def _iter_filtered_class_images(split_dir: str) -> dict[str, list[tuple[str, str]]]:
        """
        Return class->[(src_path, filename)] with period/manual/full-frame filters applied.
        """
        out: dict[str, list[tuple[str, str]]] = {}
        if not os.path.isdir(split_dir):
            return out
        for class_name in sorted(os.listdir(split_dir)):
            class_dir = os.path.join(split_dir, class_name)
            if not os.path.isdir(class_dir):
                continue
            rows: list[tuple[str, str]] = []
            for fname in sorted(os.listdir(class_dir)):
                if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                parts = fname.replace('.jpg', '').replace('.jpeg', '').replace('.png', '').split('_')
                if len(parts) >= 2:
                    try:
                        vid, tid = int(parts[0]), int(parts[1])
                        filtered_video_ids.add(vid)
                        if video_ids_ok is not None and vid not in video_ids_ok:
                            continue
                        if manual_tracks is not None and (vid, tid) not in manual_tracks:
                            continue
                    except (ValueError, IndexError):
                        if video_ids_ok is not None or manual_tracks is not None:
                            continue
                elif len(parts) >= 1:
                    if manual_tracks is not None:
                        continue  # need video_id+track_id for manual filter
                    if video_ids_ok is not None:
                        try:
                            vid = int(parts[0])
                            filtered_video_ids.add(vid)
                            if vid not in video_ids_ok:
                                continue
                        except (ValueError, IndexError):
                            continue
                src = os.path.join(class_dir, fname)
                dims = _get_image_dimensions(src)
                if dims and _is_likely_fullframe(dims[0], dims[1]):
                    info['excluded_fullframe'] += 1
                    logger.debug('Exclude full-frame from export: %s', src)
                    continue
                rows.append((src, fname))
            if rows:
                out[class_name] = rows
        return out

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if ready_for_train:
            train_source = _iter_filtered_class_images(
                os.path.join(dataset_base, 'train')
            )
            video_meta = _video_metadata_for_ids(filtered_video_ids)
            classes_txt: list[str] = []
            for class_name, files in train_source.items():
                if len(files) < min_images_per_class:
                    skipped_small.append(class_name)
                    continue
                shuffled = files[:]
                # Group by group_key and assign whole groups to splits deterministically.
                from collections import defaultdict

                groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
                for src, fname in shuffled:
                    gk = _group_key_for_filename(fname, video_meta)
                    groups[gk].append((src, fname))

                group_items = list(groups.items())
                rng = random.Random(split_seed)
                rng.shuffle(group_items)
                # sort by group size descending to place large groups first
                group_items.sort(key=lambda x: -len(x[1]))

                total_items = sum(len(rows) for _, rows in group_items)
                target_test = int(total_items * test_ratio)
                target_val = int((total_items - target_test) * val_ratio)

                tr_part, va_part, te_part = [], [], []
                test_count = 0
                val_count = 0
                for gk, rows in group_items:
                    if test_ratio and (test_count < target_test or not te_part):
                        te_part.extend(rows)
                        test_count += len(rows)
                        continue
                    if val_ratio and (val_count < target_val or not va_part):
                        va_part.extend(rows)
                        val_count += len(rows)
                        continue
                    tr_part.extend(rows)
                group_meta = {'group_count': len(group_items)}
                # Ensure test split gets at least one example when test_ratio requested
                if test_ratio and not te_part and (tr_part or va_part):
                    # Prefer moving from train, else from val
                    if tr_part:
                        te_part.append(tr_part.pop())
                    elif va_part:
                        te_part.append(va_part.pop())
                # Ensure val split gets at least one example when val_ratio requested
                if val_ratio and not va_part and (tr_part or te_part):
                    if tr_part:
                        va_part.append(tr_part.pop())
                    elif te_part:
                        va_part.append(te_part.pop())
                # Ensure groups are not split across splits: if a group_key appears
                # in multiple splits, move entire group's rows into the split that
                # currently contains the majority of its rows.
                try:
                    from collections import defaultdict

                    def _group_key_of(fname: str) -> str:
                        return _group_key_for_filename(fname, video_meta)

                    groups_map = defaultdict(lambda: defaultdict(list))
                    for src, fname in tr_part:
                        groups_map[_group_key_of(fname)]['train'].append((src, fname))
                    for src, fname in va_part:
                        groups_map[_group_key_of(fname)]['val'].append((src, fname))
                    for src, fname in te_part:
                        groups_map[_group_key_of(fname)]['test'].append((src, fname))

                # Rebuild split lists ensuring groups are kept intact
                    new_tr, new_va, new_te = [], [], []
                    for gk, mapping in groups_map.items():
                        # Count membership per split
                        counts = {k: len(v) for k, v in mapping.items()}
                        # Choose split with max count; tie-breaker: train > val > test
                        preferred = max(sorted(counts.items(), key=lambda x: ('train','val','test').index(x[0]) if x[0] in ('train','val','test') else 3), key=lambda x: x[1])[0]
                        rows = []
                        for lst in mapping.values():
                            rows.extend(lst)
                        if preferred == 'train':
                            new_tr.extend(rows)
                        elif preferred == 'val':
                            new_va.extend(rows)
                        else:
                            new_te.extend(rows)
                    tr_part, va_part, te_part = new_tr, new_va, new_te
                except Exception:
                    # If grouping fails for any reason, fallback to original parts.
                    pass
                # Final safeguard: ensure val/test get at least one example when requested.
                try:
                    def _move_group_from(src_list, dest_list):
                        if not src_list:
                            return False
                        # pick group key from last item
                        gk = _group_key_for_filename(src_list[-1][1], video_meta)
                        moved = False
                        remaining = []
                        for s, fname in src_list:
                            if _group_key_for_filename(fname, video_meta) == gk:
                                dest_list.append((s, fname))
                                moved = True
                            else:
                                remaining.append((s, fname))
                        if moved:
                            src_list[:] = remaining
                        return moved

                    if val_ratio and not va_part and tr_part:
                        _move_group_from(tr_part, va_part)
                    if test_ratio and not te_part and tr_part:
                        _move_group_from(tr_part, te_part)
                except Exception:
                    pass
                if not tr_part and shuffled:
                    def _pop_group_from(lst):
                        if not lst:
                            return []
                        gk = _group_key_for_filename(lst[-1][1], video_meta)
                        taken = [item for item in lst if _group_key_for_filename(item[1], video_meta) == gk]
                        if not taken:
                            return [lst.pop()]
                        # remove taken from lst
                        remaining = [item for item in lst if _group_key_for_filename(item[1], video_meta) != gk]
                        lst[:] = remaining
                        return taken

                    if va_part:
                        tr_part = _pop_group_from(va_part)
                    elif te_part:
                        tr_part = _pop_group_from(te_part)
                for src, fname in tr_part:
                    try:
                        zf.write(src, f'train/{class_name}/{fname}')
                        export_entries.append((
                            'train',
                            class_name,
                            fname,
                            _group_key_for_filename(fname, video_meta),
                        ))
                        info['train'][class_name] = info['train'].get(class_name, 0) + 1
                        info['total_images'] += 1
                    except OSError as e:
                        logger.warning('Skip %s: %s', src, e)
                for src, fname in va_part:
                    try:
                        zf.write(src, f'val/{class_name}/{fname}')
                        export_entries.append((
                            'val',
                            class_name,
                            fname,
                            _group_key_for_filename(fname, video_meta),
                        ))
                        info['val'][class_name] = info['val'].get(class_name, 0) + 1
                        info['total_images'] += 1
                    except OSError as e:
                        logger.warning('Skip %s: %s', src, e)
                for src, fname in te_part:
                    try:
                        zf.write(src, f'test/{class_name}/{fname}')
                        export_entries.append((
                            'test',
                            class_name,
                            fname,
                            _group_key_for_filename(fname, video_meta),
                        ))
                        info['test'][class_name] = info['test'].get(class_name, 0) + 1
                        info['total_images'] += 1
                    except OSError as e:
                        logger.warning('Skip %s: %s', src, e)
                if (
                    info['train'].get(class_name, 0) > 0
                    or info['val'].get(class_name, 0) > 0
                    or info['test'].get(class_name, 0) > 0
                ):
                    classes_txt.append(class_name)
            info['grouped_split'] = {
                'enabled': True,
                'strategy': 'recording_day_or_video',
                'video_metadata_count': len(video_meta),
                'note': (
                    'Video rows do not persist camera_id yet; grouping uses recording day '
                    'when available, otherwise video_id.'
                ),
            }
            info['classes_skipped_too_small'] = sorted(skipped_small)
            if strict_quality and skipped_small:
                return None, (
                    'strict_quality failed: classes below min_images_per_class (excluded): '
                    + ', '.join(sorted(skipped_small))
                )
            if classes_txt:
                zf.writestr('classes.txt', '\n'.join(sorted(classes_txt)) + '\n')
        else:
            video_meta = _video_metadata_for_ids(filtered_video_ids)
            for split in ('train', 'val', 'test'):
                split_dir = os.path.join(dataset_base, split)
                split_data = _iter_filtered_class_images(split_dir)
                for class_name, rows in split_data.items():
                    count = 0
                    for src, fname in rows:
                        arcname = f'{split}/{class_name}/{fname}'
                        try:
                            zf.write(src, arcname)
                            export_entries.append((
                                split,
                                class_name,
                                fname,
                                _group_key_for_filename(fname, video_meta),
                            ))
                            count += 1
                        except OSError as e:
                            logger.warning('Skip %s: %s', src, e)
                    if count > 0:
                        info[split][class_name] = count
                        info['total_images'] += count

        if info['total_images'] == 0:
            msg = 'No images in dataset. Enable "Save dataset crops" and record videos.'
            if info.get('excluded_fullframe', 0) > 0:
                msg += f' Excluded {info["excluded_fullframe"]} suspected full-frame images.'
            return None, msg

        # Final global grouping safeguard: if a group_key appears across multiple splits
        # (possible due to edge cases), move all group entries into the split that has
        # the majority of its rows to eliminate group_leakage before quality check.
        try:
            from collections import defaultdict

            group_to_entries = defaultdict(list)
            for ent in export_entries:
                split, _cls, fname, gk = ent[0], ent[1], ent[2], (ent[3] if len(ent) > 3 else _group_key_for_filename(ent[2], video_meta))
                group_to_entries[gk].append((split, _cls, fname, gk))
            # Rebuild export_entries by moving conflicting group rows to majority split
            new_export = []
            for gk, rows in group_to_entries.items():
                splits = defaultdict(list)
                for r in rows:
                    splits[r[0]].append(r)
                if len(splits) <= 1:
                    new_export.extend(rows)
                    continue
                # choose preferred split by max count; tie-breaker order train>val>test
                preferred = max(sorted(splits.items(), key=lambda x: ('train','val','test').index(x[0]) if x[0] in ('train','val','test') else 3), key=lambda x: len(x[1]))[0]
                new_export.extend(splits[preferred])
            export_entries = [tuple(x) for x in new_export]
        except Exception:
            pass
        quality = _quality_report_from_entries(export_entries, video_meta=video_meta)
        # If strict_quality requested and grouping leakage detected, attempt final repair:
        if strict_quality:
            gl = (quality.get('group_leakage') or {}).get('train_val_shared', 0) + \
                 (quality.get('group_leakage') or {}).get('train_test_shared', 0) + \
                 (quality.get('group_leakage') or {}).get('val_test_shared', 0)
            if gl > 0:
                try:
                    from collections import defaultdict

                    groups = defaultdict(list)
                    for ent in export_entries:
                        split = ent[0]
                        cls = ent[1]
                        fname = ent[2]
                        gk = ent[3] if len(ent) > 3 else _group_key_for_filename(fname, video_meta)
                        groups[gk].append((split, cls, fname))

                    new_tr, new_va, new_te = [], [], []
                    for gk, rows in groups.items():
                        counts = {'train': 0, 'val': 0, 'test': 0}
                        for s, _, _ in rows:
                            counts[s] = counts.get(s, 0) + 1
                        # preferred split: highest count, tie-breaker train>val>test
                        preferred = max(sorted(counts.items(), key=lambda x: ('train','val','test').index(x[0]) if x[0] in ('train','val','test') else 3), key=lambda x: x[1])[0]
                        if preferred == 'train':
                            new_tr.extend(rows)
                        elif preferred == 'val':
                            new_va.extend(rows)
                        else:
                            new_te.extend(rows)

                    # rebuild zip using corrected splits
                    buf2 = io.BytesIO()
                    with zipfile.ZipFile(buf2, 'w', zipfile.ZIP_DEFLATED) as zf2:
                        for split, lst in (('train', new_tr), ('val', new_va), ('test', new_te)):
                            for _, cls, fname in lst:
                                src = os.path.join(dataset_base, split if split != 'train' else 'train', cls, os.path.basename(fname))
                                try:
                                    if os.path.isfile(src):
                                        zf2.write(src, f'{split}/{cls}/{os.path.basename(fname)}')
                                except OSError:
                                    pass
                        # recompute export_entries and quality for manifest
                        repaired_entries = []
                        for s, lst in (('train', new_tr), ('val', new_va), ('test', new_te)):
                            for _s, cls, fname in lst:
                                repaired_entries.append((s, cls, fname, _group_key_for_filename(fname, video_meta)))
                        quality = _quality_report_from_entries(repaired_entries, video_meta=video_meta)
                        info['quality'] = quality
                        info['manifest'] = info.get('manifest', {})
                        zf2.writestr('dataset_info.json', json.dumps(info, ensure_ascii=False, indent=2))
                        buf2.seek(0)
                        buf = buf2
                except Exception:
                    pass
        quality['slices'] = _slice_report_from_entries(export_entries, video_meta)
        info['quality'] = quality
        info['manifest'] = {
            'schema': 'birdlense_dataset_export_v2',
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'only_manually_corrected': only_manually_corrected,
            },
            'split_params': {
                'ready_for_train': ready_for_train,
                'val_ratio': val_ratio,
                'test_ratio': test_ratio,
                'split_seed': split_seed,
                'min_images_per_class': min_images_per_class,
                'grouped_split_strategy': (
                    'recording_day_or_video'
                    if ready_for_train
                    else 'pre_split_direct_export'
                ),
            },
        }
        fp_src = json.dumps(
            {
                'filters': info['manifest']['filters'],
                'split': info['manifest']['split_params'],
                'counts': {
                    'train': info['train'],
                    'val': info['val'],
                    'test': info['test'],
                },
            },
            sort_keys=True,
        )
        info['manifest']['fingerprint_sha256_16'] = hashlib.sha256(
            fp_src.encode(),
        ).hexdigest()[:16]

        vl = quality.get('video_leakage') or {}
        if strict_quality and (
            quality.get('duplicate_track_count', 0) > 0
            or vl.get('train_val_shared', 0) > 0
            or vl.get('train_test_shared', 0) > 0
            or vl.get('val_test_shared', 0) > 0
            or (quality.get('group_leakage') or {}).get('train_val_shared', 0) > 0
            or (quality.get('group_leakage') or {}).get('train_test_shared', 0) > 0
            or (quality.get('group_leakage') or {}).get('val_test_shared', 0) > 0
        ):
            return None, (
                'strict_quality failed: duplicate tracks, grouped leakage, or video leakage between splits. '
                f'details={quality}'
            )

        zf.writestr(
            'dataset_info.json',
            json.dumps(info, ensure_ascii=False, indent=2)
        )

    buf.seek(0)
    return buf.read(), None


def move_crop_on_species_correction(
    video_id: int,
    track_id: int | None,
    old_species_name: str,
    new_species_name: str,
) -> bool:
    """
    When user corrects species in UI, move the crop file to the new class dir.
    Returns True if a file was moved.
    """
    base = data_dir()
    train_base = os.path.join(base, 'dataset', 'train')
    old_dir = os.path.join(train_base, _sanitize_dirname(old_species_name))
    new_dir = os.path.join(train_base, _sanitize_dirname(new_species_name))
    if not os.path.isdir(old_dir):
        return False
    # Match: video_id_track_id_*.jpg or video_id_*_*.jpg
    if track_id is not None:
        pattern = os.path.join(old_dir, f'{video_id}_{track_id}_*.jpg')
    else:
        pattern = os.path.join(old_dir, f'{video_id}_*.jpg')
    matches = glob.glob(pattern)
    if len(matches) != 1:
        if matches:
            logger.debug('Skip move: %d matches for video_id=%s track_id=%s',
                        len(matches), video_id, track_id)
        return False
    src = matches[0]
    fname = os.path.basename(src)
    os.makedirs(new_dir, exist_ok=True)
    dst = os.path.join(new_dir, fname)
    try:
        shutil.move(src, dst)
        logger.info('Moved dataset crop: %s -> %s', src, dst)
        return True
    except OSError as e:
        logger.warning('Failed to move dataset crop %s: %s', src, e)
        return False


def extract_and_save_crop_for_detection(vs, species_name: str, require_bbox: bool = True) -> bool:
    """
    Ретроэкспорт: извлечь кадр из видео и сохранить в датасет.
    Вызывается при коррекции вида, когда move_crop_on_species_correction не сработал
    (файл не был сохранён процессором).
    Использует bbox из vs.frames для кропа (как процессор).
    require_bbox: если True — не сохранять полный кадр при отсутствии bbox (только кропы).
    Returns True if crop was saved.
    """
    if vs.source != 'video':
        return False
    from services.detection_crop_service import (
        extract_detection_frame_cropped,
        _bbox_for_offset,
    )
    video = vs.video
    if not video or not video.video_path:
        return False
    offset = vs.start_time + (vs.end_time - vs.start_time) / 2
    bbox = _bbox_for_offset(getattr(vs, 'frames', None), offset)
    if require_bbox and not bbox:
        return False  # Не сохраняем полный кадр — только кропы
    jpeg_bytes = extract_detection_frame_cropped(video.video_path, offset, bbox)
    if not jpeg_bytes:
        return False
    base = data_dir()
    train_base = os.path.join(base, 'dataset', 'train')
    dirname = _sanitize_dirname(species_name)
    out_dir = os.path.join(train_base, dirname)
    os.makedirs(out_dir, exist_ok=True)
    track_id = vs.track_id if vs.track_id is not None else 0
    filename = f"{vs.video_id}_{track_id}_{vs.id}.jpg"
    out_path = os.path.join(out_dir, filename)
    try:
        with open(out_path, 'wb') as f:
            f.write(jpeg_bytes)
        logger.info("Retro-export: saved crop %s -> %s", vs.id, out_path)
        return True
    except OSError as e:
        logger.warning("Failed to save retro crop %s: %s", out_path, e)
        return False


def clean_dataset(
    dry_run: bool = False,
    remove_fullframe: bool = True,
    remove_orphaned: bool = False,
) -> dict:
    """
    Очистить датасет: удалить подозрительные full-frame и/или осиротевшие файлы.
    remove_fullframe: по эвристике (размер + aspect 16:9/4:3).
    remove_orphaned: файлы без соответствующего VideoSpecies (осторожно — processor-файлы).
    dry_run: только подсчёт, не удалять.
    Returns {deleted_fullframe, deleted_orphaned, errors, dry_run}.
    """
    base = data_dir()
    train_dir = os.path.join(base, 'dataset', 'train')
    if not os.path.isdir(train_dir):
        return {'deleted_fullframe': 0, 'deleted_orphaned': 0, 'errors': [], 'dry_run': dry_run}

    deleted_fullframe = 0
    deleted_orphaned = 0
    errors = []

    valid_tracks: set[tuple[int, int]] | None = None
    if remove_orphaned:
        from models import VideoSpecies, Video, Species
        rows = VideoSpecies.query.filter(
            VideoSpecies.source == 'video',
        ).join(
            Video, Video.id == VideoSpecies.video_id
        ).join(
            Species, Species.id == VideoSpecies.species_id
        ).with_entities(
            VideoSpecies.video_id, VideoSpecies.track_id
        ).all()
        valid_tracks = {(r[0], r[1] or 0) for r in rows}

    for class_name in os.listdir(train_dir):
        class_dir = os.path.join(train_dir, class_name)
        if not os.path.isdir(class_dir):
            continue
        for fname in os.listdir(class_dir):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            path = os.path.join(class_dir, fname)
            parts = fname.replace('.jpg', '').replace('.jpeg', '').replace('.png', '').split('_')
            if len(parts) >= 2:
                try:
                    vid, tid = int(parts[0]), int(parts[1])
                    if remove_orphaned and valid_tracks is not None and (vid, tid) not in valid_tracks:
                        if not dry_run:
                            try:
                                os.remove(path)
                                deleted_orphaned += 1
                                logger.info('Clean: deleted orphaned %s', path)
                            except OSError as e:
                                errors.append(f'{path}: {e}')
                        else:
                            deleted_orphaned += 1
                        continue
                except (ValueError, IndexError):
                    pass
            if remove_fullframe:
                dims = _get_image_dimensions(path)
                if dims and _is_likely_fullframe(dims[0], dims[1]):
                    if not dry_run:
                        try:
                            os.remove(path)
                            deleted_fullframe += 1
                            logger.info('Clean: deleted full-frame %s', path)
                        except OSError as e:
                            errors.append(f'{path}: {e}')
                    else:
                        deleted_fullframe += 1

    return {
        'deleted_fullframe': deleted_fullframe,
        'deleted_orphaned': deleted_orphaned,
        'errors': errors,
        'dry_run': dry_run,
    }


def _delete_dataset_crops_for_video_ids(video_ids: set[int]) -> int:
    """
    Удалить из train/ все файлы, относящиеся к указанным video_id.
    Формат имени: video_id_track_id_*.jpg
    Returns count of deleted files.
    """
    base = data_dir()
    train_dir = os.path.join(base, 'dataset', 'train')
    if not os.path.isdir(train_dir):
        return 0
    deleted = 0
    for class_name in os.listdir(train_dir):
        class_dir = os.path.join(train_dir, class_name)
        if not os.path.isdir(class_dir):
            continue
        for fname in os.listdir(class_dir):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            parts = fname.replace('.jpg', '').replace('.jpeg', '').replace('.png', '').split('_')
            if len(parts) >= 1:
                try:
                    vid = int(parts[0])
                    if vid in video_ids:
                        path = os.path.join(class_dir, fname)
                        try:
                            os.remove(path)
                            deleted += 1
                            logger.info('Rebuild: deleted %s', path)
                        except OSError as e:
                            logger.warning('Failed to delete %s: %s', path, e)
                except (ValueError, IndexError):
                    pass
    return deleted


def retro_export_all_video_detections(
    min_confidence: float = 0.0,
    start_date: str | None = None,
    end_date: str | None = None,
    only_manually_corrected: bool = False,
    rebuild: bool = False,
) -> dict:
    """
    Массовый ретроэкспорт: извлечь кадры из видео-детекций в БД и сохранить в датасет.
    start_date, end_date: YYYY-MM-DD — период. None = все.
    only_manually_corrected: только вручную исправленные — гарантированно правильные виды.
    rebuild: если True — удалить crops за период и заново извлечь только кропы (гарантированно без full-frame).
    Returns {saved, skipped, skipped_no_bbox, skipped_orphaned, deleted_orphaned, errors, deleted?}.
    """
    from datetime import datetime, timezone, timedelta
    from models import VideoSpecies, Video
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import joinedload

    saved = 0
    skipped = 0
    skipped_no_bbox = 0
    skipped_orphaned = 0
    deleted_orphaned = 0
    errors = []
    deleted = 0

    video_ids_in_period = _video_ids_in_period(start_date, end_date)
    if rebuild and video_ids_in_period:
        deleted = _delete_dataset_crops_for_video_ids(video_ids_in_period)
        logger.info('Rebuild: deleted %d files for period', deleted)

    q = (
        VideoSpecies.query.filter(VideoSpecies.source == 'video')
        .filter(VideoSpecies.confidence >= min_confidence)
        .outerjoin(Video, VideoSpecies.video_id == Video.id)
        .options(joinedload(VideoSpecies.video), joinedload(VideoSpecies.species))
    )
    if only_manually_corrected:
        q = q.filter(VideoSpecies.manually_corrected == True)
    # Период по дате видео; строки без Video (сироты после retention/удаления) тоже
    # включаем — иначе фильтр по Video.start_time их отсекает и cleanup не срабатывает (#158).
    date_parts = []
    if start_date:
        try:
            dt_start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            date_parts.append(Video.start_time >= dt_start)
        except ValueError:
            pass
    if end_date:
        try:
            dt_end = datetime.strptime(end_date, '%Y-%m-%d').replace(
                tzinfo=timezone.utc
            ) + timedelta(days=1)
            date_parts.append(Video.start_time < dt_end)
        except ValueError:
            pass
    if date_parts:
        in_period = date_parts[0] if len(date_parts) == 1 else and_(*date_parts)
        q = q.filter(or_(Video.id.is_(None), in_period))
    from services.detection_crop_service import _bbox_for_offset
    q = q.order_by(VideoSpecies.video_id, VideoSpecies.id)
    for vs in q:
        if not vs.video or not vs.video.video_path or not vs.species:
            skipped_orphaned += 1
            try:
                # Cleanup dangling detections so next runs don't revisit broken rows.
                from models import db
                db.session.delete(vs)
                deleted_orphaned += 1
            except Exception as e:
                errors.append(f'orphan_cleanup_failed vs_id={getattr(vs, "id", "?")}: {e}')
            continue
        mid = vs.start_time + (vs.end_time - vs.start_time) / 2
        if not _bbox_for_offset(getattr(vs, 'frames', None), mid):
            skipped_no_bbox += 1
            continue
        base = data_dir()
        train_base = os.path.join(base, 'dataset', 'train')
        dirname = _sanitize_dirname(vs.species.name)
        out_dir = os.path.join(train_base, dirname)
        track_id = vs.track_id if vs.track_id is not None else 0
        filename = f"{vs.video_id}_{track_id}_{vs.id}.jpg"
        out_path = os.path.join(out_dir, filename)
        if os.path.isfile(out_path):
            skipped += 1
            continue
        if not rebuild and os.path.isfile(out_path):
            skipped += 1
            continue
        if extract_and_save_crop_for_detection(vs, vs.species.name, require_bbox=True):
            saved += 1
        else:
            errors.append(f"video_id={vs.video_id} vs_id={vs.id}")

    if deleted_orphaned:
        try:
            from models import db
            db.session.commit()
        except Exception as e:
            from models import db
            db.session.rollback()
            errors.append(f'orphan_cleanup_commit_failed: {e}')
    result = {
        'saved': saved,
        'skipped': skipped,
        'skipped_no_bbox': skipped_no_bbox,
        'skipped_orphaned': skipped_orphaned,
        'deleted_orphaned': deleted_orphaned,
        'errors': errors,
    }
    if rebuild:
        result['deleted'] = deleted
    return result

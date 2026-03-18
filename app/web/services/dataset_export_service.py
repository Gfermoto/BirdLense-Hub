"""Export dataset crops as ZIP archive and move on species correction."""
import glob
import io
import json
import logging
import os
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
) -> tuple[bytes | None, str | None]:
    """
    Build ZIP archive from data/dataset/train and val (if exists).
    start_date, end_date: YYYY-MM-DD — только кадры из видео за период. None = все.
    only_manually_corrected: только кропы вручную исправленных детекций (правильные виды).
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

    info = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'train': {},
        'val': {},
        'total_images': 0,
        'excluded_fullframe': 0,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for split in ('train', 'val'):
            split_dir = os.path.join(dataset_base, split)
            if not os.path.isdir(split_dir):
                continue
            for class_name in sorted(os.listdir(split_dir)):
                class_dir = os.path.join(split_dir, class_name)
                if not os.path.isdir(class_dir):
                    continue
                count = 0
                for fname in os.listdir(class_dir):
                    if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    parts = fname.replace('.jpg', '').replace('.jpeg', '').replace('.png', '').split('_')
                    if len(parts) >= 2:
                        try:
                            vid, tid = int(parts[0]), int(parts[1])
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
                                if int(parts[0]) not in video_ids_ok:
                                    continue
                            except (ValueError, IndexError):
                                continue
                    src = os.path.join(class_dir, fname)
                    dims = _get_image_dimensions(src)
                    if dims and _is_likely_fullframe(dims[0], dims[1]):
                        info['excluded_fullframe'] += 1
                        logger.debug('Exclude full-frame from export: %s', src)
                        continue
                    arcname = f'{split}/{class_name}/{fname}'
                    try:
                        zf.write(src, arcname)
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
        from models import VideoSpecies
        rows = VideoSpecies.query.filter(
            VideoSpecies.source == 'video',
        ).with_entities(VideoSpecies.video_id, VideoSpecies.track_id).all()
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
    Returns {saved, skipped, skipped_no_bbox, errors, deleted?}.
    """
    from datetime import datetime, timezone, timedelta
    from models import VideoSpecies, Video
    from sqlalchemy.orm import joinedload

    saved = 0
    skipped = 0
    skipped_no_bbox = 0
    errors = []
    deleted = 0

    video_ids_in_period = _video_ids_in_period(start_date, end_date)
    if rebuild and video_ids_in_period:
        deleted = _delete_dataset_crops_for_video_ids(video_ids_in_period)
        logger.info('Rebuild: deleted %d files for period', deleted)

    q = (
        VideoSpecies.query.filter(VideoSpecies.source == 'video')
        .filter(VideoSpecies.confidence >= min_confidence)
        .join(Video, VideoSpecies.video_id == Video.id)
        .options(joinedload(VideoSpecies.video), joinedload(VideoSpecies.species))
    )
    if only_manually_corrected:
        q = q.filter(VideoSpecies.manually_corrected == True)
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
    from services.detection_crop_service import _bbox_for_offset
    q = q.order_by(VideoSpecies.video_id, VideoSpecies.id)
    for vs in q:
        if not vs.video or not vs.video.video_path:
            skipped += 1
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

    result = {'saved': saved, 'skipped': skipped, 'skipped_no_bbox': skipped_no_bbox, 'errors': errors}
    if rebuild:
        result['deleted'] = deleted
    return result

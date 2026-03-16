"""Export dataset crops as ZIP archive and move on species correction."""
import glob
import io
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
logger = logging.getLogger(__name__)


def _sanitize_dirname(name: str) -> str:
    """Sanitize species name for directory. Must match dataset_saver."""
    s = re.sub(r'[<>:"/\\|?*]', '_', str(name).strip())
    s = re.sub(r'\s+', ' ', s).strip()
    return s or 'unknown'


def _data_dir() -> str:
    """
    Resolve DATA_DIR for dataset path.
    """
    return os.environ.get('DATA_DIR') or os.path.join(
        os.path.dirname(__file__), '..', '..', 'data'
    )


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
    data_dir = _data_dir()
    dataset_base = os.path.join(data_dir, 'dataset')
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
            return None, (
                'No images in dataset. '
                'Enable "Save dataset crops" and record videos.'
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
    data_dir = _data_dir()
    base = os.path.join(data_dir, 'dataset', 'train')
    old_dir = os.path.join(base, _sanitize_dirname(old_species_name))
    new_dir = os.path.join(base, _sanitize_dirname(new_species_name))
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
    data_dir = _data_dir()
    base = os.path.join(data_dir, 'dataset', 'train')
    dirname = _sanitize_dirname(species_name)
    out_dir = os.path.join(base, dirname)
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


def retro_export_all_video_detections(
    min_confidence: float = 0.0,
    start_date: str | None = None,
    end_date: str | None = None,
    only_manually_corrected: bool = False,
) -> dict:
    """
    Массовый ретроэкспорт: извлечь кадры из видео-детекций в БД и сохранить в датасет.
    start_date, end_date: YYYY-MM-DD — период. None = все.
    only_manually_corrected: только вручную исправленные — гарантированно правильные виды.
    Returns {saved: int, skipped: int, skipped_no_bbox: int, errors: list}.
    """
    from datetime import datetime, timezone, timedelta
    from models import VideoSpecies, Video
    from sqlalchemy.orm import joinedload

    saved = 0
    skipped = 0
    skipped_no_bbox = 0
    errors = []

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
        data_dir = _data_dir()
        base = os.path.join(data_dir, 'dataset', 'train')
        dirname = _sanitize_dirname(vs.species.name)
        out_dir = os.path.join(base, dirname)
        track_id = vs.track_id if vs.track_id is not None else 0
        filename = f"{vs.video_id}_{track_id}_{vs.id}.jpg"
        out_path = os.path.join(out_dir, filename)
        if os.path.isfile(out_path):
            skipped += 1
            continue
        if extract_and_save_crop_for_detection(vs, vs.species.name, require_bbox=True):
            saved += 1
        else:
            errors.append(f"video_id={vs.video_id} vs_id={vs.id}")

    return {'saved': saved, 'skipped': skipped, 'skipped_no_bbox': skipped_no_bbox, 'errors': errors}

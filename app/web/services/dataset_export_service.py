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


def build_dataset_zip() -> tuple[bytes | None, str | None]:
    """
    Build ZIP archive from data/dataset/train and val (if exists).
    Returns (zip_bytes, error_message). On success error_message is None.
    """
    data_dir = _data_dir()
    dataset_base = os.path.join(data_dir, 'dataset')
    if not os.path.isdir(dataset_base):
        return None, (
            'Dataset folder not found. '
            'Enable "Save dataset crops" and record videos.'
        )

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

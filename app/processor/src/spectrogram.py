"""
Generate spectrogram image from video file.
Extracts audio with ffmpeg, creates mel spectrogram with librosa, saves as JPEG.
"""
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def generate_spectrogram(video_path: str, output_path: str, px_per_sec: int = 200) -> bool:
    """
    Generate spectrogram from video and save as JPEG.
    Returns True on success, False on failure.
    """
    if not os.path.isfile(video_path):
        logger.warning(f"Video file not found: {video_path}")
        return False

    try:
        import librosa
        import librosa.display
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        logger.error(f"Spectrogram dependencies missing: {e}. Install librosa, matplotlib.")
        return False

    wav_path = None
    try:
        # Extract audio with ffmpeg
        wav_path = tempfile.mktemp(suffix='.wav')
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1',
            wav_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning(f"FFmpeg audio extraction failed: {result.stderr}")
            return False

        if not os.path.isfile(wav_path) or os.path.getsize(wav_path) < 1000:
            logger.warning("Extracted audio file empty or missing")
            return False

        # Load audio
        y, sr = librosa.load(wav_path, sr=22050, mono=True)

        # Mel spectrogram: hop_length so we get ~px_per_sec columns per second
        n_fft = 2048
        hop_length = max(256, int(sr / px_per_sec))
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length)
        S_db = librosa.power_to_db(S, ref=np.max)

        # Save as image
        fig, ax = plt.subplots(figsize=(12, 4))
        librosa.display.specshow(S_db, sr=sr, hop_length=hop_length, x_axis='time', y_axis='mel', ax=ax)
        ax.set_ylim(0, 8000)  # Focus on bird vocal range
        plt.axis('off')
        plt.tight_layout(pad=0)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0)
        plt.close()

        return os.path.isfile(output_path)
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg audio extraction timed out")
        return False
    except Exception as e:
        logger.exception(f"Spectrogram generation failed: {e}")
        return False
    finally:
        if wav_path and os.path.isfile(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

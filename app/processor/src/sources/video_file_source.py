"""Video file sources for deterministic processor test runs."""

import logging
import os
import subprocess
import time
from pathlib import Path

import cv2


class VideoFileSource:
    """Video source with camera-like timing over an mp4 file."""

    def __init__(
        self,
        video_path,
        main_size=(1280, 720),
        lores_size=(640, 640),
        loop=False,
        realtime_simulation=False,
        record_stream_codec='h264',
    ):
        """Open video source and initialize timing/recording state."""
        self.logger = logging.getLogger(__name__)
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.main_size = main_size
        self.lores_size = lores_size
        self.loop = bool(loop)
        self.realtime_simulation = bool(realtime_simulation)
        rcodec = str(record_stream_codec or 'h264').strip().lower()
        self.record_stream_codec = rcodec if rcodec in ('h264', 'copy') else 'h264'
        self.out = None
        self._record_output = None
        self._recorded_frames = 0
        self._fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        self.source_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_interval = 1.0 / self.source_fps
        self.last_capture_time = None
        self.frame_count = 0

        self.logger.info(f'VideoFileSource: {self.source_fps} FPS')

    def start_recording(self, output):
        """Start writing recorded output video to disk."""
        self.logger.info(f'Start video recording to {output}')
        self._record_output = output
        self._recorded_frames = 0
        candidates = (
            ('avc1', cv2.VideoWriter_fourcc(*'avc1')),
            ('H264', cv2.VideoWriter_fourcc(*'H264')),
            ('X264', cv2.VideoWriter_fourcc(*'X264')),
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
        )
        order = candidates if self.record_stream_codec == 'h264' else (candidates[-1],)
        self.out = None
        for tag, fourcc in order:
            writer = cv2.VideoWriter(
                output,
                fourcc,
                self.source_fps,
                self.main_size,
            )
            if writer is not None and writer.isOpened():
                self.out = writer
                self._fourcc = fourcc
                self.logger.info('Video writer opened with codec=%s', tag)
                break
            if writer is not None:
                writer.release()
        if self.out is None:
            self.logger.error('Failed to open VideoWriter for %s', output)
        self.frame_count = 0
        self.last_capture_time = None

    def stop_recording(self):
        """Stop output recording if active."""
        self.logger.info('Stop video recording')
        if self.out is not None:
            self.out.release()
            self.out = None
        if self._record_output and self.record_stream_codec == 'h264':
            self._ensure_h264(self._record_output)
        if self._record_output and self._recorded_frames == 0:
            try:
                os.remove(self._record_output)
            except OSError:
                pass
        self._record_output = None

    def _ensure_h264(self, output_path: str) -> None:
        try:
            probe = subprocess.run(
                [
                    'ffprobe',
                    '-v',
                    'error',
                    '-select_streams',
                    'v:0',
                    '-show_entries',
                    'stream=codec_name',
                    '-of',
                    'default=noprint_wrappers=1:nokey=1',
                    output_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            codec = (probe.stdout or '').strip().lower()
            if codec == 'h264':
                return
            tmp_path = f'{output_path}.h264.tmp.mp4'
            run = subprocess.run(
                [
                    'ffmpeg',
                    '-y',
                    '-i',
                    output_path,
                    '-c:v',
                    'libx264',
                    '-preset',
                    'veryfast',
                    '-pix_fmt',
                    'yuv420p',
                    '-movflags',
                    '+faststart',
                    '-an',
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if run.returncode == 0 and os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 1024:
                os.replace(tmp_path, output_path)
                self.logger.info('Transcoded recording to H.264: %s', output_path)
            else:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                self.logger.warning(
                    'H.264 transcode failed for %s (codec=%s, code=%s)',
                    output_path,
                    codec or 'unknown',
                    run.returncode,
                )
        except Exception as e:
            self.logger.warning('Failed H.264 normalization for %s: %s', output_path, e)

    def capture(self):
        """Read next frame(s) based on elapsed time and return lores frame."""
        if not self.cap.isOpened():
            return None

        if self.realtime_simulation:
            now = time.time()
            if self.last_capture_time is None:
                frames_to_advance = 1
            else:
                elapsed = now - self.last_capture_time
                frames_to_advance = max(1, int(elapsed / self.frame_interval))
            self.last_capture_time = now
        else:
            frames_to_advance = 1

        result_frame = None
        for _ in range(frames_to_advance):
            ret, frame = self.cap.read()
            if not ret:
                if self.loop:
                    self.logger.info(
                        'Video loop: restarting source %s after %s frames',
                        self.video_path,
                        self.frame_count,
                    )
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.video_path)
                    if not self.cap.isOpened():
                        self.logger.warning(
                            'Video loop failed to reopen source: %s',
                            self.video_path,
                        )
                        return None
                    ret, frame = self.cap.read()
                    if not ret:
                        self.logger.warning(
                            'Video loop failed to read first frame: %s',
                            self.video_path,
                        )
                        return None
                else:
                    self.logger.info(f'Video ended after {self.frame_count} frames')
                    return None

            self.frame_count += 1

            if self.out is not None:
                frame_main = cv2.resize(frame, self.main_size)
                self.out.write(frame_main)
                self._recorded_frames += 1

            result_frame = frame

        res = (
            cv2.resize(result_frame, self.lores_size)
            if result_frame is not None
            else None
        )
        return res

    def get_frame_time(self):
        """Timestamp in seconds for last frame returned by `capture()`."""
        if self.frame_count <= 0:
            return 0.0
        return (self.frame_count - 1) / self.source_fps

    def close(self):
        """Release writer and capture handles."""
        self.stop_recording()
        if self.cap is not None:
            self.cap.release()


class VideoPlaylistSource:
    """Playlist source that cycles through all video files in a folder."""

    def __init__(
        self,
        video_paths,
        main_size=(1280, 720),
        lores_size=(640, 640),
        loop=True,
        advance_on_start=True,
        *,
        split_session_per_file=False,
        realtime_simulation=False,
        record_stream_codec='h264',
    ):
        self.logger = logging.getLogger(__name__)
        self.video_paths = [str(p) for p in (video_paths or []) if str(p).strip()]
        if not self.video_paths:
            raise ValueError('Video playlist is empty')
        self.main_size = main_size
        self.lores_size = lores_size
        self.loop = bool(loop)
        self.advance_on_start = bool(advance_on_start)
        self.split_session_per_file = bool(split_session_per_file)
        self._pending_first_frame_bgr = None
        self.realtime_simulation = bool(realtime_simulation)
        rcodec = str(record_stream_codec or 'h264').strip().lower()
        self.record_stream_codec = rcodec if rcodec in ('h264', 'copy') else 'h264'
        self._started_once = False
        self.video_index = 0
        self.video_path = self.video_paths[0]
        self.cap = None
        self.out = None
        self._fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self._record_output = None
        self._recorded_frames = 0
        self.source_fps = 30.0
        self.frame_interval = 1.0 / self.source_fps
        self.last_capture_time = None
        self.frame_count = 0
        self._open_current_video()
        self.logger.info(
            'VideoPlaylistSource: %s files, first=%s',
            len(self.video_paths),
            Path(self.video_path).name,
        )

    def _open_current_video(self):
        if self.cap is not None:
            self.cap.release()
        self.video_path = self.video_paths[self.video_index]
        self.cap = cv2.VideoCapture(self.video_path)
        fps = self.cap.get(cv2.CAP_PROP_FPS) if self.cap.isOpened() else 0.0
        self.source_fps = fps or 30.0
        self.frame_interval = 1.0 / self.source_fps
        self.frame_count = 0
        self.last_capture_time = None
        self.logger.info(
            'Playlist now playing: %s (fps=%.2f)',
            self.video_path,
            self.source_fps,
        )

    def _advance_video(self):
        next_index = self.video_index + 1
        if next_index >= len(self.video_paths):
            if not self.loop:
                return False
            next_index = 0
        self.video_index = next_index
        self._open_current_video()
        return True

    def start_recording(self, output):
        advanced = False
        if self.advance_on_start and self._started_once:
            self._advance_video()
            advanced = True
        first_session = not self._started_once
        self._started_once = True
        self.logger.info(f'Start video recording to {output}')
        self._record_output = output
        self._recorded_frames = 0
        candidates = (
            ('avc1', cv2.VideoWriter_fourcc(*'avc1')),
            ('H264', cv2.VideoWriter_fourcc(*'H264')),
            ('X264', cv2.VideoWriter_fourcc(*'X264')),
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
        )
        order = candidates if self.record_stream_codec == 'h264' else (candidates[-1],)
        self.out = None
        for tag, fourcc in order:
            writer = cv2.VideoWriter(
                output,
                fourcc,
                self.source_fps,
                self.main_size,
            )
            if writer is not None and writer.isOpened():
                self.out = writer
                self._fourcc = fourcc
                self.logger.info('Video writer opened with codec=%s', tag)
                break
            if writer is not None:
                writer.release()
        if self.out is None:
            self.logger.error('Failed to open VideoWriter for %s', output)
        if advanced or first_session:
            self.frame_count = 0
            self.last_capture_time = None

    def stop_recording(self):
        self.logger.info('Stop video recording')
        if self.out is not None:
            self.out.release()
            self.out = None
        if self._record_output and self.record_stream_codec == 'h264':
            self._ensure_h264(self._record_output)
        if self._record_output and self._recorded_frames == 0:
            try:
                os.remove(self._record_output)
            except OSError:
                pass
        self._record_output = None

    def _ensure_h264(self, output_path: str) -> None:
        try:
            probe = subprocess.run(
                [
                    'ffprobe',
                    '-v',
                    'error',
                    '-select_streams',
                    'v:0',
                    '-show_entries',
                    'stream=codec_name',
                    '-of',
                    'default=noprint_wrappers=1:nokey=1',
                    output_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            codec = (probe.stdout or '').strip().lower()
            if codec == 'h264':
                return
            tmp_path = f'{output_path}.h264.tmp.mp4'
            run = subprocess.run(
                [
                    'ffmpeg',
                    '-y',
                    '-i',
                    output_path,
                    '-c:v',
                    'libx264',
                    '-preset',
                    'veryfast',
                    '-pix_fmt',
                    'yuv420p',
                    '-movflags',
                    '+faststart',
                    '-an',
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if run.returncode == 0 and os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 1024:
                os.replace(tmp_path, output_path)
                self.logger.info('Transcoded recording to H.264: %s', output_path)
            else:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                self.logger.warning(
                    'H.264 transcode failed for %s (codec=%s, code=%s)',
                    output_path,
                    codec or 'unknown',
                    run.returncode,
                )
        except Exception as e:
            self.logger.warning('Failed H.264 normalization for %s: %s', output_path, e)

    def capture(self):
        if self.cap is None or not self.cap.isOpened():
            return None

        if self.split_session_per_file and self._pending_first_frame_bgr is not None:
            frame = self._pending_first_frame_bgr
            self._pending_first_frame_bgr = None
            self.frame_count += 1
            if self.out is not None:
                frame_main = cv2.resize(frame, self.main_size)
                self.out.write(frame_main)
                self._recorded_frames += 1
            return cv2.resize(frame, self.lores_size)

        if self.realtime_simulation:
            now = time.time()
            if self.last_capture_time is None:
                frames_to_advance = 1
            else:
                elapsed = now - self.last_capture_time
                frames_to_advance = max(1, int(elapsed / self.frame_interval))
            self.last_capture_time = now
        else:
            frames_to_advance = 1

        result_frame = None
        for _ in range(frames_to_advance):
            ret, frame = self.cap.read()
            if not ret:
                switched = False
                for _i in range(len(self.video_paths)):
                    if not self._advance_video():
                        return None
                    ret, frame = self.cap.read()
                    if ret:
                        if self.split_session_per_file:
                            self._pending_first_frame_bgr = frame.copy()
                            self.logger.info(
                                'Playlist: end of clip — finalize session; '
                                'next clip=%s',
                                Path(self.video_path).name,
                            )
                            return None
                        switched = True
                        break
                if not switched:
                    return None

            self.frame_count += 1
            if self.out is not None:
                frame_main = cv2.resize(frame, self.main_size)
                self.out.write(frame_main)
                self._recorded_frames += 1
            result_frame = frame

        if result_frame is None:
            return None
        return cv2.resize(result_frame, self.lores_size)

    def get_frame_time(self):
        if self.frame_count <= 0:
            return 0.0
        return (self.frame_count - 1) / self.source_fps

    def close(self):
        self.stop_recording()
        if self.cap is not None:
            self.cap.release()

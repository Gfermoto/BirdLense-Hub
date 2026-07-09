import type { RefObject } from 'react';
import { useCallback, useEffect, useState } from 'react';

export const useVideoControl = (
  videoRef: RefObject<HTMLVideoElement | null>,
) => {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleProgress = useCallback((seconds: number) => {
    setProgress(seconds);
  }, []);

  const handleSeek = useCallback(
    (time: number) => {
      if (videoRef.current) videoRef.current.currentTime = time;
      setProgress(time);
    },
    [videoRef],
  );

  const togglePlayPause = useCallback(() => {
    setPlaying((prev) => !prev);
  }, []);

  // Handle play/pause
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (playing) {
      video.play().catch(console.error);
    } else {
      video.pause();
    }
  }, [playing, videoRef]);

  // timeupdate fires ~4 Hz; rAF keeps bbox overlay aligned during playback.
  useEffect(() => {
    if (!playing) return;
    let rafId = 0;
    const tick = () => {
      const video = videoRef.current;
      if (video) setProgress(video.currentTime);
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [playing, videoRef]);

  return { playing, progress, handleProgress, handleSeek, togglePlayPause };
};

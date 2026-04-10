import React, {
  useEffect,
  useRef,
  useCallback,
  useLayoutEffect,
} from 'react';
import Box from '@mui/material/Box';
import { VideoSpecies } from '../../../types';
import { labelToUniqueHexColor } from '../../../util';

const DEFAULT_PX_PER_SECOND = 200;

const extractPxPerSecond = (imageUrl: string): number => {
  const match = imageUrl.match(/spectrogram_(\d+)\.jpg$/);
  return match ? parseInt(match[1], 10) : DEFAULT_PX_PER_SECOND;
};

interface SpectrogramPlayerProps {
  imageUrl: string;
  audioRef: React.RefObject<HTMLAudioElement | null>;
  playing: boolean;
  detections: VideoSpecies[];
  /** Вкладка «Спектрограмма» видима (иначе родитель 0×0 и canvas остаётся шириной 0 — чёрный экран). */
  visible: boolean;
}

export const SpectrogramPlayer: React.FC<SpectrogramPlayerProps> = ({
  imageUrl,
  audioRef,
  playing,
  detections,
  visible,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const parentRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const pxPerSecond = extractPxPerSecond(imageUrl);

  const drawSpectrogram = useCallback(() => {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image || !audioRef.current) return;
    if (canvas.width < 2 || canvas.height < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const currentTime = audioRef.current.currentTime;
    const currentPx = currentTime * pxPerSecond;
    const halfWidth = canvas.width / 2;

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const sw = Math.min(canvas.width, image.naturalWidth || image.width);
    const maxSx = Math.max(0, (image.naturalWidth || image.width) - sw);
    const sx = Math.max(0, Math.min(currentPx - halfWidth, maxSx));
    ctx.drawImage(
      image,
      sx,
      0,
      sw,
      image.naturalHeight || image.height,
      0,
      0,
      canvas.width,
      canvas.height,
    );

    detections.forEach((detection) => {
      const startPx =
        detection.start_time * pxPerSecond - currentPx + halfWidth;
      const width = (detection.end_time - detection.start_time) * pxPerSecond;
      const color = labelToUniqueHexColor(detection.species_name);

      const barHeight = 30;
      const barY = canvas.height - barHeight;

      ctx.fillStyle = `${color}20`;
      ctx.fillRect(startPx, barY, width, barHeight);

      ctx.fillStyle = color;
      ctx.fillRect(startPx, barY, width, 2);

      ctx.fillStyle = '#fff';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.fillText(
        detection.species_name,
        startPx + width / 2,
        canvas.height - 10,
      );
    });

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(halfWidth, 0);
    ctx.lineTo(halfWidth, canvas.height);
    ctx.stroke();
  }, [pxPerSecond, detections, audioRef]);

  const syncCanvasWidth = useCallback(() => {
    const parent = parentRef.current;
    const canvas = canvasRef.current;
    if (!parent || !canvas) return;
    const w = Math.max(Math.floor(parent.getBoundingClientRect().width), 2);
    if (canvas.width !== w) {
      canvas.width = w;
    }
  }, []);

  const drawSpectrogramAnimate = useCallback(() => {
    drawSpectrogram();
    animationRef.current = requestAnimationFrame(drawSpectrogramAnimate);
  }, [drawSpectrogram]);

  useLayoutEffect(() => {
    if (!visible) return;
    syncCanvasWidth();
    const id = requestAnimationFrame(() => {
      syncCanvasWidth();
      drawSpectrogram();
    });
    return () => cancelAnimationFrame(id);
  }, [visible, syncCanvasWidth, drawSpectrogram]);

  useEffect(() => {
    let cancelled = false;
    const image = new Image();
    image.decoding = 'async';
    image.src = imageUrl;
    image.onload = () => {
      if (cancelled) return;
      imageRef.current = image;
      if (canvasRef.current) {
        canvasRef.current.height = image.height;
      }
      syncCanvasWidth();
      drawSpectrogram();
    };

    return () => {
      cancelled = true;
      imageRef.current = null;
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    };
  }, [drawSpectrogram, imageUrl, syncCanvasWidth]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handleSeeked = () => {
      drawSpectrogram();
    };
    audio.addEventListener('seeked', handleSeeked);
    return () => {
      audio.removeEventListener('seeked', handleSeeked);
    };
  }, [drawSpectrogram, audioRef]);

  useEffect(() => {
    if (playing) {
      drawSpectrogramAnimate();
    } else if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  }, [playing, drawSpectrogramAnimate]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = parentRef.current;
    if (!parent || !canvas) return;
    const resizeObserver = new ResizeObserver(() => {
      if (!visible) return;
      syncCanvasWidth();
      drawSpectrogram();
    });
    resizeObserver.observe(parent);
    return () => {
      resizeObserver.disconnect();
    };
  }, [visible, syncCanvasWidth, drawSpectrogram]);

  return (
    <Box
      sx={{ height: '100%', width: '100%', bgcolor: 'black' }}
      ref={parentRef}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: 'black',
        }}
      />
    </Box>
  );
};

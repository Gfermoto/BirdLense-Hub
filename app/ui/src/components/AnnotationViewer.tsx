import React from 'react';
import Box from '@mui/material/Box';

export type AnnotationFrame = {
  t: number | null;
  bbox: [number, number, number, number]; // normalized xywh
};

export type AnnotationTrack = {
  id: string;
  label: string;
  color: string;
  dashed?: boolean;
  frames: AnnotationFrame[];
};

type AnnotationViewerProps = {
  tracks: AnnotationTrack[];
  currentTime: number | null;
  selectedTrackId?: string | null;
  onSelectTrack?: (trackId: string | null) => void;
  interactive?: boolean;
};

/** Bbox only while `currentTime` is inside stored keyframes; linear interp between keys. */
export function resolveFrameAtTime(
  frames: AnnotationFrame[],
  currentTime: number | null,
): AnnotationFrame | null {
  if (!frames.length) return null;

  const sorted = [...frames]
    .filter((f) => f.t != null && Number.isFinite(f.t))
    .sort((a, b) => (a.t as number) - (b.t as number));
  if (!sorted.length) return null;

  if (currentTime == null) return sorted[0];

  const tMin = sorted[0].t as number;
  const tMax = sorted[sorted.length - 1].t as number;
  if (currentTime < tMin || currentTime > tMax) return null;

  if (currentTime <= tMin) return sorted[0];
  if (currentTime >= tMax) return sorted[sorted.length - 1];

  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];
    const ta = a.t as number;
    const tb = b.t as number;
    if (currentTime < ta || currentTime > tb) continue;
    if (tb - ta < 1e-6) return a;
    const u = (currentTime - ta) / (tb - ta);
    const bbox = a.bbox.map((v, j) => {
      const next = b.bbox[j] ?? v;
      return v + u * (next - v);
    }) as [number, number, number, number];
    return { t: currentTime, bbox };
  }

  return sorted[sorted.length - 1];
}

export const AnnotationViewer: React.FC<AnnotationViewerProps> = ({
  tracks,
  currentTime,
  selectedTrackId = null,
  onSelectTrack,
  interactive = false,
}) => {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const [hoverTrackId, setHoverTrackId] = React.useState<string | null>(null);

  React.useEffect(() => {
    const root = rootRef.current;
    const canvas = canvasRef.current;
    if (!root || !canvas) return;
    const sync = () => {
      const rect = root.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width));
      canvas.height = Math.max(1, Math.floor(rect.height));
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(root);
    return () => ro.disconnect();
  }, []);

  React.useEffect(() => {
    const draw = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext('2d');
      if (!canvas || !ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const track of tracks) {
        const frame = resolveFrameAtTime(track.frames, currentTime);
        if (!frame) continue;
        const [x, y, w, h] = frame.bbox;
        const bx = x * canvas.width;
        const by = y * canvas.height;
        const bw = w * canvas.width;
        const bh = h * canvas.height;
        const selected = selectedTrackId === track.id;
        const hovered = hoverTrackId === track.id;
        ctx.save();
        ctx.strokeStyle = track.color;
        ctx.lineWidth = selected ? 4 : 2;
        if (track.dashed) ctx.setLineDash([8, 4]);
        ctx.strokeRect(bx, by, bw, bh);
        if (hovered || selected) {
          ctx.setLineDash([4, 3]);
          ctx.strokeStyle = '#ffffff';
          ctx.strokeRect(bx - 2, by - 2, bw + 4, bh + 4);
        }
        const label = track.label;
        ctx.font = '12px sans-serif';
        const tw = Math.ceil(ctx.measureText(label).width + 8);
        ctx.fillStyle = track.color;
        ctx.fillRect(bx, Math.max(0, by - 18), tw, 16);
        ctx.fillStyle = '#111';
        ctx.fillText(label, bx + 4, Math.max(12, by - 6));
        ctx.restore();
      }
      requestAnimationFrame(draw);
    };
    const raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [currentTime, hoverTrackId, selectedTrackId, tracks]);

  const hitTrack = (ev: React.MouseEvent<HTMLCanvasElement>): string | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left;
    const py = ev.clientY - rect.top;
    for (const track of tracks) {
      const frame = resolveFrameAtTime(track.frames, currentTime);
      if (!frame) continue;
      const [x, y, w, h] = frame.bbox;
      const bx = x * canvas.width;
      const by = y * canvas.height;
      const bw = w * canvas.width;
      const bh = h * canvas.height;
      if (px >= bx && px <= bx + bw && py >= by && py <= by + bh) return track.id;
    }
    return null;
  };

  return (
    <Box ref={rootRef} sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: interactive ? 'auto' : 'none' }}>
      <Box
        ref={canvasRef}
        component="canvas"
        sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', cursor: interactive ? 'pointer' : 'default' }}
        onMouseMove={(e) => {
          if (!interactive) return;
          setHoverTrackId(hitTrack(e));
        }}
        onMouseLeave={() => {
          if (!interactive) return;
          setHoverTrackId(null);
        }}
        onClick={(e) => {
          if (!interactive) return;
          const hit = hitTrack(e);
          onSelectTrack?.(hit);
        }}
      />
    </Box>
  );
};


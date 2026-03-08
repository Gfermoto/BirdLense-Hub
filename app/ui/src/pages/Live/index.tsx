import { useRef, useLayoutEffect } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { fetchCameras } from '../../api/api';

const MjpegStream = ({
  streamUrl,
  name,
  feeder,
}: {
  streamUrl: string;
  name: string;
  feeder?: string;
}) => {
  const imgRef = useRef<HTMLImageElement>(null);

  useLayoutEffect(() => {
    if (imgRef.current) {
      imgRef.current.src = streamUrl;
    }
    return () => {
      if (imgRef.current) {
        imgRef.current.src = '';
      }
    };
  }, [streamUrl]);

  const label = feeder ? `${feeder} — ${name}` : name;

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        {label}
      </Typography>
      <img width="100%" ref={imgRef} alt={label} />
    </Box>
  );
};

export const LivePage = () => {
  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: fetchCameras,
  });

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h4" mb={3}>
          Live Stream
        </Typography>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  const cams = cameras?.length ? cameras : [{ id: 'default', name: 'Camera', stream_url: '/processor/live' }];

  // Адаптивная сетка: 1 камера — на всю ширину, 2 — в 2 колонки, 3–4 — в 4, 5+ — в 6
  const numCols = cams.length <= 1 ? 1 : cams.length <= 2 ? 2 : cams.length <= 4 ? 4 : 6;
  const gridSize = 12 / numCols;

  return (
    <Box>
      <Typography variant="h4" mb={3}>
        Live — все камеры
      </Typography>
      <Grid container spacing={2}>
        {cams.map((cam) => (
          <Grid key={cam.id} size={{ xs: 12, sm: 6, md: gridSize }}>
            <MjpegStream
              streamUrl={cam.stream_url}
              name={cam.name}
              feeder={cam.feeder}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

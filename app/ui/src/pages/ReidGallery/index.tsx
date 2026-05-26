import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { Link as RouterLink } from 'react-router-dom';
import { PageHeader } from '../../components/PageHeader';
import { PageSection } from '../../components/PageSection';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import {
  fetchExpertQueue,
  fetchReidGallery,
  fetchReidGalleryStatus,
  resolveExpertTask,
} from '../../api/expertReid';

export function ReidGalleryPage() {
  useDocumentTitle('ReID Gallery');
  const qc = useQueryClient();
  const statusQ = useQuery({ queryKey: ['reid', 'status'], queryFn: fetchReidGalleryStatus });
  const galleryQ = useQuery({
    queryKey: ['reid', 'gallery'],
    queryFn: () => fetchReidGallery({ limit: 200 }),
    enabled: Boolean(statusQ.data?.reid_track_clustering_enabled),
  });
  const queueQ = useQuery({
    queryKey: ['expert', 'queue'],
    queryFn: () => fetchExpertQueue({ limit: 40 }),
    enabled: Boolean(statusQ.data?.reid_expert_queue_enabled),
  });
  const resolveM = useMutation({
    mutationFn: resolveExpertTask,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['expert', 'queue'] });
      void qc.invalidateQueries({ queryKey: ['reid', 'gallery'] });
    },
  });

  const disabled = !statusQ.data?.reid_gallery_enabled;

  return (
    <Box>
      <PageHeader title="ReID Gallery" subtitle="Кластеры треков и экспертная очередь (SOTA-13)" />
      {disabled ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          ReID Gallery выключена. Включите{' '}
          <code>processor.reid_gallery_enabled</code> (и clustering / expert queue) в настройках после
          валидации SOTA-10..12 на VPS.
        </Alert>
      ) : null}

      <PageSection title="Expert Queue">
        {queueQ.data?.enabled === false ? (
          <Typography color="text.secondary">Очередь отключена (reid_expert_queue_enabled).</Typography>
        ) : (
          <Stack spacing={1}>
            {(queueQ.data?.items ?? []).map((item) => (
              <Card key={item.id} variant="outlined">
                <CardContent>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Chip size="small" label={item.task_type} />
                    {item.similarity != null ? (
                      <Chip size="small" variant="outlined" label={`sim ${item.similarity}`} />
                    ) : null}
                    <Typography variant="body2">{item.species_name ?? '—'}</Typography>
                    {item.video_id ? (
                      <Button component={RouterLink} to={`/videos/${item.video_id}`} size="small">
                        Видео {item.video_id}
                      </Button>
                    ) : null}
                  </Stack>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={resolveM.isPending}
                      onClick={() => resolveM.mutate({ task_id: item.id, action: 'dismiss' })}
                    >
                      Отклонить
                    </Button>
                    {item.task_type === 'duplicate_candidate' && item.related_video_species_id ? (
                      <Button
                        size="small"
                        variant="contained"
                        disabled={resolveM.isPending}
                        onClick={() =>
                          resolveM.mutate({
                            task_id: item.id,
                            action: 'merge_tracks',
                            note: 'expert_merge_tracks',
                          })
                        }
                      >
                        Merge tracks
                      </Button>
                    ) : null}
                  </Stack>
                </CardContent>
              </Card>
            ))}
            {!queueQ.data?.items?.length && queueQ.data?.enabled ? (
              <Typography color="text.secondary">Нет задач в очереди.</Typography>
            ) : null}
          </Stack>
        )}
      </PageSection>

      <PageSection title="Gallery clusters">
        {galleryQ.data?.enabled === false ? (
          <Typography color="text.secondary">{galleryQ.data?.message ?? 'clustering disabled'}</Typography>
        ) : (
          <Stack spacing={2}>
            {(galleryQ.data?.clusters ?? []).map((cl) => (
              <Card key={cl.cluster_id} variant="outlined">
                <CardContent>
                  <Typography variant="subtitle2">
                    {cl.cluster_id} · {cl.member_count} треков · min sim {cl.min_pairwise_similarity}
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 1 }}>
                    {cl.members.map((m) => (
                      <Chip
                        key={m.video_species_id}
                        component={RouterLink}
                        to={`/videos/${m.video_id}`}
                        clickable
                        size="small"
                        label={`#${m.video_species_id} t${m.track_id ?? '?'}`}
                      />
                    ))}
                  </Stack>
                </CardContent>
              </Card>
            ))}
            {!galleryQ.data?.clusters?.length ? (
              <Typography color="text.secondary">Нет эмбеддингов / кластеров (нужна таблица reid_embedding).</Typography>
            ) : null}
          </Stack>
        )}
      </PageSection>
    </Box>
  );
}

export default ReidGalleryPage;

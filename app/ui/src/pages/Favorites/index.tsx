import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CalendarToday from '@mui/icons-material/CalendarToday';
import Star from '@mui/icons-material/Star';
import VideoCall from '@mui/icons-material/VideoCall';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import {
  fetchFavoritesBySpecies,
  type FavoriteSpeciesGroup,
  type FavoriteVideo,
} from '../../api/favorites';
import { queryKeys } from '../../api/queryKeys';
import { formatLocalDateTime } from '../../util';
import { formatDuration } from '../../utils/timeUtils';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

type SortMode = 'recent' | 'name';

function videoDateParam(video: FavoriteVideo) {
  return video.start_time.slice(0, 10);
}

function FavoriteVideoCard({ video }: { video: FavoriteVideo }) {
  const { t } = useTranslation();
  const location = useLocation();
  const primarySpecies = video.species[0];
  const speciesLabel =
    primarySpecies?.name ?? t('favoritesPage.unclassifiedSpecies');
  const duration =
    video.duration_seconds > 0 ? formatDuration(video.duration_seconds) : null;

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardActionArea
        component={RouterLink}
        to={`/videos/${video.id}`}
        state={{ from: `${location.pathname}${location.search}` }}
        sx={{ height: '100%', alignItems: 'stretch' }}
      >
        <CardContent
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            gap: 1.25,
          }}
        >
          <Stack direction="row" spacing={1.5} alignItems="flex-start">
            <SpeciesIcon
              speciesName={speciesLabel}
              imageUrl={primarySpecies?.image_url ?? undefined}
              size={48}
            />
            <Box minWidth={0} flex={1}>
              <Typography variant="subtitle1" fontWeight={700} noWrap>
                {speciesLabel}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatLocalDateTime(video.start_time)}
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 'auto' }}>
            <Chip
              size="small"
              icon={<Star sx={{ fontSize: 16 }} />}
              label={t('favoritesPage.protected')}
              color="primary"
              variant="outlined"
            />
            {duration ? (
              <Chip
                size="small"
                icon={<VideoCall sx={{ fontSize: 16 }} />}
                label={duration}
              />
            ) : null}
            <Chip
              size="small"
              icon={<CalendarToday sx={{ fontSize: 16 }} />}
              label={videoDateParam(video)}
            />
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function SpeciesSection({ group }: { group: FavoriteSpeciesGroup }) {
  const { t } = useTranslation();
  const sectionId = `favorites-species-${group.species.id}`;
  return (
    <Paper
      id={sectionId}
      variant="outlined"
      sx={{
        overflow: 'hidden',
        scrollMarginTop: 88,
        backgroundColor: 'rgba(15, 23, 42, 0.55)',
      }}
    >
      <Box
        sx={{
          position: { md: 'sticky' },
          top: { md: 0 },
          zIndex: 1,
          p: 2,
          backgroundColor: 'rgba(30, 41, 59, 0.94)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <SpeciesIcon
            speciesName={group.species.name}
            imageUrl={group.species.image_url ?? undefined}
            size={52}
          />
          <Box minWidth={0} flex={1}>
            <Typography variant="h5" component="h2">
              {group.species.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t('favoritesPage.groupMeta', {
                count: group.count,
                date: formatLocalDateTime(group.latest_start_time),
              })}
            </Typography>
          </Box>
        </Stack>
      </Box>
      <Divider />
      <Box
        sx={{
          p: 2,
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, minmax(0, 1fr))',
            lg: 'repeat(3, minmax(0, 1fr))',
            xl: 'repeat(4, minmax(0, 1fr))',
          },
          gap: 2,
        }}
      >
        {group.videos.map((video) => (
          <FavoriteVideoCard key={video.id} video={video} />
        ))}
      </Box>
    </Paper>
  );
}

export function FavoritesPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('recent');
  useDocumentTitle(t('favoritesPage.title'));

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.favorites.bySpecies,
    queryFn: fetchFavoritesBySpecies,
  });

  const groups = useMemo(() => {
    const query = search.trim().toLowerCase();
    const source = data?.groups ?? [];
    const filtered = query
      ? source.filter((group) =>
          group.species.name.toLowerCase().includes(query),
        )
      : source;
    return [...filtered].sort((a, b) => {
      if (sortMode === 'name') {
        return a.species.name.localeCompare(b.species.name);
      }
      return b.latest_start_time.localeCompare(a.latest_start_time);
    });
  }, [data?.groups, search, sortMode]);

  if (isLoading) {
    return <PageLoadingState label={t('common.loading')} />;
  }

  if (error || !data) {
    return (
      <PageMessageState
        title={t('favoritesPage.title')}
        message={t('favoritesPage.errorLoad')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  const hasResults = groups.length > 0 || data.unclassified.count > 0;

  return (
    <Box sx={{ py: 3 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h3" component="h1" gutterBottom>
            {t('favoritesPage.title')}
          </Typography>
          <Typography variant="body1" color="text.secondary" maxWidth="900px">
            {t('favoritesPage.intro')}
          </Typography>
        </Box>

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            alignItems={{ xs: 'stretch', md: 'center' }}
          >
            <Stack direction="row" spacing={1} flexWrap="wrap" flex={1}>
              <Chip
                icon={<Star />}
                label={t('favoritesPage.totalVideos', {
                  count: data.total_videos,
                })}
                color="primary"
              />
              <Chip
                label={t('favoritesPage.totalSpecies', {
                  count: data.total_species,
                })}
              />
              {data.unclassified.count > 0 ? (
                <Chip
                  label={t('favoritesPage.unclassifiedCount', {
                    count: data.unclassified.count,
                  })}
                  variant="outlined"
                />
              ) : null}
            </Stack>
            <TextField
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              label={t('favoritesPage.searchSpecies')}
              size="small"
              sx={{ minWidth: { md: 260 } }}
            />
            <TextField
              select
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              label={t('favoritesPage.sort')}
              size="small"
              sx={{ minWidth: { md: 220 } }}
            >
              <MenuItem value="recent">
                {t('favoritesPage.sortRecent')}
              </MenuItem>
              <MenuItem value="name">{t('favoritesPage.sortName')}</MenuItem>
            </TextField>
          </Stack>
        </Paper>

        {!hasResults ? (
          <Alert severity="info" variant="outlined">
            {t('favoritesPage.empty')}
          </Alert>
        ) : (
          <Stack
            direction={{ xs: 'column', lg: 'row' }}
            spacing={3}
            alignItems="flex-start"
          >
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                width: { xs: '100%', lg: 260 },
                position: { lg: 'sticky' },
                top: { lg: 16 },
              }}
            >
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                {t('favoritesPage.speciesIndex')}
              </Typography>
              <Stack spacing={0.5}>
                {groups.map((group) => (
                  <Button
                    key={group.species.id}
                    href={`#favorites-species-${group.species.id}`}
                    size="small"
                    sx={{ justifyContent: 'space-between' }}
                    endIcon={<Chip size="small" label={group.count} />}
                  >
                    <Box
                      component="span"
                      sx={{
                        minWidth: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {group.species.name}
                    </Box>
                  </Button>
                ))}
              </Stack>
            </Paper>

            <Stack spacing={3} flex={1} minWidth={0} width="100%">
              {groups.map((group) => (
                <SpeciesSection key={group.species.id} group={group} />
              ))}
              {data.unclassified.count > 0 ? (
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="h5" component="h2" gutterBottom>
                    {t('favoritesPage.unclassifiedSpecies')}
                  </Typography>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: {
                        xs: '1fr',
                        sm: 'repeat(2, minmax(0, 1fr))',
                        lg: 'repeat(3, minmax(0, 1fr))',
                      },
                      gap: 2,
                    }}
                  >
                    {data.unclassified.videos.map((video) => (
                      <FavoriteVideoCard key={video.id} video={video} />
                    ))}
                  </Box>
                </Paper>
              ) : null}
            </Stack>
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

export default FavoritesPage;

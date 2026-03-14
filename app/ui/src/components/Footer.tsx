import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import GitHubIcon from '@mui/icons-material/GitHub';
import { fetchStatus } from '../api/api';
import birdnetLogoUrl from '../assets/birdnet-logo.svg';

export function Footer() {
  const { t } = useTranslation();
  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
  });
  const birdnetUrl = status?.birdnet_url?.trim();

  return (
    <Box
      component="footer"
      sx={{
        py: 1.5,
        px: 3,
        mt: 'auto',
        borderTop: '1px solid rgba(148, 163, 184, 0.1)',
        backgroundColor: 'transparent',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', fontSize: '0.8rem' }}
        >
          {t('common.appName')}
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', opacity: 0.5 }}
        >
          ·
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', fontSize: '0.8rem' }}
        >
          v{__APP_VERSION__}
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', opacity: 0.5 }}
        >
          ·
        </Typography>
        {birdnetUrl && (
          <>
            <Link
              href={birdnetUrl}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                color: 'text.secondary',
                textDecoration: 'none',
                fontSize: '0.8rem',
                transition: 'color 0.2s',
                '&:hover': {
                  color: 'primary.main',
                },
              }}
              title="BirdNET"
            >
              <Box
                component="img"
                src={birdnetLogoUrl}
                alt="BirdNET"
                sx={{ height: 18, width: 18, opacity: 0.85 }}
              />
              BirdNET
            </Link>
            <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.5 }}>
              ·
            </Typography>
          </>
        )}
        <Link
          href="https://github.com/Gfermoto/BirdLense-Hub/pkgs/container/birdlense-hub"
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            color: 'text.secondary',
            textDecoration: 'none',
            fontSize: '0.8rem',
            transition: 'color 0.2s',
            '&:hover': {
              color: 'primary.main',
            },
          }}
        >
          <GitHubIcon sx={{ fontSize: '1rem' }} />
          {t('common.dockerImage')}
        </Link>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', opacity: 0.5 }}
        >
          ·
        </Typography>
        <Link
          href="https://creativecommons.org/licenses/by-nc-nd/4.0/"
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            color: 'text.secondary',
            textDecoration: 'none',
            fontSize: '0.8rem',
            '&:hover': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          {t('common.license')}
        </Link>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', opacity: 0.5 }}
        >
          ·
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', fontSize: '0.8rem' }}
        >
          {t('common.createdBy')}{' '}
          <Link
            href="https://github.com/Gfermoto"
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              color: 'inherit',
              textDecoration: 'none',
              '&:hover': {
                color: 'primary.main',
                textDecoration: 'underline',
              },
            }}
          >
            Stanislav Kolesnik
          </Link>
        </Typography>
      </Box>
    </Box>
  );
}

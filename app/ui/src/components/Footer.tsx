import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import { fetchStatus } from '../api/api';
import { queryKeys } from '../api/queryKeys';
import birdnetLogoUrl from '../assets/birdnet-logo.svg';

const footerLinkSx = {
  color: 'text.secondary',
  fontSize: { xs: '0.75rem', sm: '0.8125rem' },
  lineHeight: 1.5,
  textDecoration: 'none',
  transition: 'color 0.2s ease',
  '&:hover': {
    color: 'primary.main',
    textDecoration: 'underline',
  },
} as const;

function Dot() {
  return (
    <Box
      component="span"
      aria-hidden
      sx={{
        color: 'text.secondary',
        opacity: 0.45,
        userSelect: 'none',
        px: { xs: 0.25, sm: 0.5 },
        fontSize: { xs: '0.75rem', sm: '0.8125rem' },
        lineHeight: 1,
      }}
    >
      ·
    </Box>
  );
}

export function Footer() {
  const { t } = useTranslation();
  const { data: status } = useQuery({
    queryKey: queryKeys.health.status,
    queryFn: fetchStatus,
  });
  const birdnetUrl = status?.birdnet_url?.trim();

  return (
    <Box
      component="footer"
      sx={{
        mt: 'auto',
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: (theme) =>
          theme.palette.mode === 'dark'
            ? 'rgba(255,255,255,0.02)'
            : 'rgba(0,0,0,0.02)',
      }}
    >
      <Container
        maxWidth="xl"
        sx={{ py: { xs: 1.25, sm: 1.5 }, px: { xs: 2, sm: 3 } }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            flexWrap: 'wrap',
            columnGap: 0,
            rowGap: 0.75,
            textAlign: 'center',
          }}
        >
          <Link
            href="https://github.com/Gfermoto/BirdLense-Hub"
            target="_blank"
            rel="noopener noreferrer"
            sx={footerLinkSx}
            fontWeight={500}
          >
            {t('common.appName')}
          </Link>
          <Dot />
          <Link
            href={`https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v${__APP_VERSION__}`}
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              ...footerLinkSx,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            v{__APP_VERSION__}
          </Link>
          {birdnetUrl ? (
            <>
              <Dot />
              <Link
                href={birdnetUrl}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="BirdNET"
                sx={{
                  ...footerLinkSx,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.5,
                  textDecoration: 'none',
                  '&:hover': {
                    ...footerLinkSx['&:hover'],
                    textDecoration: 'none',
                  },
                  '&:hover .footer-birdnet-label': {
                    textDecoration: 'underline',
                  },
                }}
              >
                <Box
                  component="img"
                  src={birdnetLogoUrl}
                  alt=""
                  sx={{ height: 17, width: 17, opacity: 0.88, flexShrink: 0 }}
                />
                <Box component="span" className="footer-birdnet-label">
                  BirdNET
                </Box>
              </Link>
            </>
          ) : null}
          <Dot />
          <Link
            href="https://creativecommons.org/licenses/by-nc-nd/4.0/"
            target="_blank"
            rel="noopener noreferrer"
            sx={footerLinkSx}
          >
            {t('common.license')}
          </Link>
          <Dot />
          <Typography
            component="span"
            variant="body2"
            sx={{
              color: 'text.secondary',
              fontSize: { xs: '0.75rem', sm: '0.8125rem' },
              maxWidth: { xs: '100%', sm: 'none' },
            }}
          >
            {t('common.createdBy')}{' '}
            <Link
              href="https://t.me/gfermoto"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Stanislav Kolesnik (Telegram)"
              sx={{
                ...footerLinkSx,
                fontWeight: 500,
                whiteSpace: { xs: 'normal', sm: 'nowrap' },
              }}
            >
              Stanislav Kolesnik
            </Link>
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}

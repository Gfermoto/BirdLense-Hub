import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

type PageLoadingStateProps = {
  label?: string;
  minHeight?: number;
};

export function PageLoadingState({
  label,
  minHeight = 240,
}: PageLoadingStateProps) {
  return (
    <Box
      sx={{
        minHeight,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Stack spacing={1.5} alignItems="center">
        <CircularProgress aria-label={label} />
        {label ? (
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        ) : null}
      </Stack>
    </Box>
  );
}

type PageMessageStateProps = {
  title?: string;
  message: string;
  action?: ReactNode;
  severity?: 'info' | 'warning' | 'error' | 'success';
  minHeight?: number;
};

export function PageMessageState({
  title,
  message,
  action,
  severity = 'info',
  minHeight = 220,
}: PageMessageStateProps) {
  return (
    <Box
      sx={{
        minHeight,
        display: 'flex',
        alignItems: 'center',
      }}
    >
      <Stack spacing={2} sx={{ width: '100%', maxWidth: 760 }}>
        {title ? (
          <Typography component="h1" variant="h5">
            {title}
          </Typography>
        ) : null}
        <Alert severity={severity} variant="outlined">
          {message}
        </Alert>
        {action ? <Box>{action}</Box> : null}
      </Stack>
    </Box>
  );
}

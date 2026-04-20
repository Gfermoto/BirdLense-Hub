import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

type StatusTone = 'default' | 'success' | 'warning' | 'error' | 'info';

type SystemCardShellProps = {
  title: string;
  description?: string;
  statusLabel?: string;
  statusTone?: StatusTone;
  actions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  minHeight?: number;
  id?: string;
};

export function SystemCardShell({
  title,
  description,
  statusLabel,
  statusTone = 'default',
  actions,
  children,
  footer,
  minHeight,
  id,
}: SystemCardShellProps) {
  return (
    <Card
      id={id}
      sx={{
        width: '100%',
        minWidth: 0,
        alignSelf: 'start',
        minHeight,
        borderColor:
          statusTone === 'warning'
            ? 'warning.dark'
            : statusTone === 'error'
              ? 'error.dark'
              : 'divider',
      }}
    >
      <CardContent
        sx={{ display: 'grid', gap: 2.25, minWidth: 0, maxWidth: '100%' }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', sm: 'flex-start' }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              flexWrap="wrap"
              useFlexGap
            >
              <Typography variant="h6">{title}</Typography>
              {statusLabel ? (
                <Chip
                  size="small"
                  color={statusTone === 'default' ? undefined : statusTone}
                  label={statusLabel}
                />
              ) : null}
            </Stack>
            {description ? (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 0.75 }}
              >
                {description}
              </Typography>
            ) : null}
          </Box>
          {actions ? <Box sx={{ flexShrink: 0 }}>{actions}</Box> : null}
        </Stack>

        <Box sx={{ minWidth: 0, maxWidth: '100%' }}>{children}</Box>

        {footer ? (
          <>
            <Divider />
            <Box>{footer}</Box>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

type PageSectionProps = {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  dividerTop?: boolean;
};

export function PageSection({
  title,
  description,
  children,
  actions,
  dividerTop = false,
}: PageSectionProps) {
  return (
    <Stack spacing={2.5}>
      {dividerTop ? <Divider /> : null}
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1.5}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
      >
        <Box>
          <Typography
            component="h2"
            variant="h5"
            sx={{ mb: description ? 0.75 : 0 }}
          >
            {title}
          </Typography>
          {description ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ maxWidth: 900 }}
            >
              {description}
            </Typography>
          ) : null}
        </Box>
        {actions ? <Box>{actions}</Box> : null}
      </Stack>
      <Box display="grid" gap={2} sx={{ minWidth: 0, maxWidth: '100%' }}>
        {children}
      </Box>
    </Stack>
  );
}

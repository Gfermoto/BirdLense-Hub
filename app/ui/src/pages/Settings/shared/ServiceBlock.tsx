import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

export function ServiceBlock({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        mb: 2,
        bgcolor: 'action.hover',
        '&:last-of-type': { mb: 0 },
      }}
    >
      <Typography variant="subtitle2" color="primary" sx={{ mb: 1.5, fontWeight: 600 }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

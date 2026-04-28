import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

export function ProductName({ sx }: { sx?: SxProps<Theme> }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 0.35,
        whiteSpace: 'nowrap',
        ...sx,
      }}
      aria-label="BirdLense Hub ML"
    >
      <Box component="span">BirdLense Hub</Box>
      <Box
        component="sup"
        sx={{
          fontSize: '0.58em',
          lineHeight: 1,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          transform: 'translateY(-0.45em)',
        }}
      >
        ML
      </Box>
    </Box>
  );
}

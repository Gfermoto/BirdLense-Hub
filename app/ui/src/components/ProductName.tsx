import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

/**
 * Decorative product wordmark only. Provide the accessible name on the enclosing
 * control (e.g. home Link `aria-label`); avoids duplicate headings + “BirdLense HubML” in SR trees.
 */
export function ProductName({ sx }: { sx?: SxProps<Theme> }) {
  return (
    <Box
      component="span"
      aria-hidden
      sx={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 0.35,
        whiteSpace: 'nowrap',
        ...sx,
      }}
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

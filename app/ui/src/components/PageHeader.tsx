import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import type { SxProps, Theme } from '@mui/material/styles';
import type { ReactNode } from 'react';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  onHelpClick?: () => void;
  helpTooltip?: string;
  helpAriaLabel?: string;
  titleVariant?: 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  descriptionMaxWidth?: number;
  sx?: SxProps<Theme>;
};

export function PageHeader({
  title,
  description,
  actions,
  onHelpClick,
  helpTooltip,
  helpAriaLabel,
  titleVariant = 'h3',
  descriptionMaxWidth = 900,
  sx,
}: PageHeaderProps) {
  return (
    <Stack spacing={1.25} sx={sx}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1.5}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
      >
        <Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant={titleVariant}>{title}</Typography>
            {onHelpClick ? (
              <Tooltip title={helpTooltip ?? ''}>
                <IconButton
                  onClick={onHelpClick}
                  size="small"
                  aria-label={helpAriaLabel}
                  sx={{ color: 'text.secondary' }}
                >
                  <HelpOutlineIcon />
                </IconButton>
              </Tooltip>
            ) : null}
          </Stack>
          {description ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 0.5, maxWidth: descriptionMaxWidth }}
            >
              {description}
            </Typography>
          ) : null}
        </Box>
        {actions ? <Box sx={{ flexShrink: 0 }}>{actions}</Box> : null}
      </Stack>
    </Stack>
  );
}

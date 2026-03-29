import React, { memo } from 'react';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

interface StatCardProps {
  icon: React.ElementType;
  title: string;
  value: string | number;
  subtitle?: string;
  /** Подсказка при наведении (как у остальных карточек обзора) */
  hint?: string;
}

export const StatCard = memo(function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  hint,
}: StatCardProps) {
  const card = (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box display="flex" alignItems="center" gap={2}>
          <Icon color="primary" sx={{ fontSize: 40 }} />
          <Box flex={1} minWidth={0}>
            <Typography color="text.secondary" variant="subtitle2">
              {title}
            </Typography>
            <Typography variant="h5">{value}</Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
  if (!hint) {
    return card;
  }
  return (
    <Tooltip title={hint} enterDelay={400}>
      <Box sx={{ height: '100%' }}>{card}</Box>
    </Tooltip>
  );
});

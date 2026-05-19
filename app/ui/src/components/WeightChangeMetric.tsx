import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import MonitorWeightIcon from '@mui/icons-material/MonitorWeight';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { useTranslation } from 'react-i18next';

const NOISE_THRESHOLD_G = 5;

export type WeightChangeData = {
  weight_change_grams?: number | null;
  weight_trend?: 'up' | 'down' | 'stable' | string | null;
  /** Legacy scales payload */
  delta_kg?: number;
  display_value?: number;
  display_unit?: string;
};

function resolveGrams(data: WeightChangeData): number | null {
  if (data.weight_change_grams != null && !Number.isNaN(Number(data.weight_change_grams))) {
    return Number(data.weight_change_grams);
  }
  if (data.delta_kg != null && !Number.isNaN(Number(data.delta_kg))) {
    const unit = (data.display_unit || 'g').toLowerCase();
    const kg = Number(data.delta_kg);
    return unit === 'kg' ? kg * 1000 : kg * 1000;
  }
  if (data.display_value != null && (data.display_unit || 'g') === 'g') {
    const dv = Number(data.display_value);
    const kg = data.delta_kg != null ? Number(data.delta_kg) : null;
    if (kg != null && !Number.isNaN(kg)) {
      return kg * 1000;
    }
    return dv;
  }
  return null;
}

function resolveTrend(
  data: WeightChangeData,
  grams: number,
): 'up' | 'down' | 'stable' | null {
  const t = String(data.weight_trend || '').toLowerCase();
  if (t === 'up' || t === 'down' || t === 'stable') {
    return t;
  }
  if (Math.abs(grams) <= NOISE_THRESHOLD_G) {
    return 'stable';
  }
  return grams > 0 ? 'up' : 'down';
}

export function hasVisibleWeightChange(
  scales: WeightChangeData | null | undefined,
): boolean {
  if (!scales) {
    return false;
  }
  const grams = resolveGrams(scales);
  if (grams == null || Number.isNaN(grams)) {
    return false;
  }
  const trend = resolveTrend(scales, grams);
  return trend === 'up' || trend === 'down';
}

/** Weight delta for video/visit cards; hidden when no data or change within noise threshold. */
export function WeightChangeMetric({
  scales,
  compact = false,
}: {
  scales: WeightChangeData | null | undefined;
  /** Hide label on xs — icon + value only */
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (!scales) {
    return null;
  }
  const grams = resolveGrams(scales);
  if (grams == null || Number.isNaN(grams)) {
    return null;
  }
  const trend = resolveTrend(scales, grams);
  if (trend === 'stable' || trend == null) {
    return null;
  }

  const absG = Math.abs(Math.round(grams));
  const sign = trend === 'up' ? '+' : '−';
  const color = trend === 'up' ? 'success.main' : 'error.main';
  const Icon = trend === 'up' ? ArrowUpwardIcon : ArrowDownwardIcon;

  const valueNode = (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        color,
      }}
    >
      <Icon sx={{ fontSize: compact ? 18 : 22 }} aria-hidden />
      <Typography
        variant={compact ? 'body2' : 'subtitle1'}
        component="span"
        sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}
      >
        {sign}
        {absG} {t('videoInfo.weightChangeUnit')}
      </Typography>
    </Box>
  );

  return (
    <Tooltip title={t('videoInfo.weightChangeTooltip')} arrow>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <MonitorWeightIcon fontSize="small" color="action" aria-hidden />
        {!compact && (
          <Typography variant="body2" color="text.secondary" sx={{ mr: 0.5 }}>
            {t('videoInfo.weightChangeTitle')}
          </Typography>
        )}
        {valueNode}
      </Box>
    </Tooltip>
  );
}

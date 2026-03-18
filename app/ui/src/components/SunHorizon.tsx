import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { formatSunTimeLocal } from '../api/api';

export interface SunTimes {
  dawn: string;
  sunrise: string;
  noon: string;
  sunset: string;
  dusk: string;
}

interface SunHorizonProps {
  sunTimes: SunTimes;
  currentTime?: string | null;
}

/** Текстовые пометки: рассвет, восход, полдень, закат, сумерки */
export const SunHorizon = ({ sunTimes }: SunHorizonProps) => {
  const { t } = useTranslation();
  const dawn = formatSunTimeLocal(sunTimes.dawn);
  const sunrise = formatSunTimeLocal(sunTimes.sunrise);
  const noon = formatSunTimeLocal(sunTimes.noon);
  const sunset = formatSunTimeLocal(sunTimes.sunset);
  const dusk = formatSunTimeLocal(sunTimes.dusk);

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        gap: 0.5,
        textAlign: 'center',
      }}
    >
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          {t('weather.dawn')} {dawn}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.8rem' }}>
          {t('weather.sunrise')}
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {sunrise}
        </Typography>
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.8rem' }}>
          {t('weather.noon')}
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {noon}
        </Typography>
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          {t('weather.dusk')} {dusk}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.8rem' }}>
          {t('weather.sunset')}
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {sunset}
        </Typography>
      </Box>
    </Box>
  );
};

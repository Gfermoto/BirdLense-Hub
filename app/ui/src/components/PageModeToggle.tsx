import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useTranslation } from 'react-i18next';

export type PageMode = 'simple' | 'advanced';

type PageModeToggleProps = {
  value: PageMode;
  onChange: (value: PageMode) => void;
};

export function PageModeToggle({ value, onChange }: PageModeToggleProps) {
  const { t } = useTranslation();

  return (
    <ToggleButtonGroup
      value={value}
      exclusive
      size="small"
      color="primary"
      onChange={(_, next: PageMode | null) => {
        if (next) onChange(next);
      }}
      aria-label={t('common.viewMode')}
    >
      <ToggleButton value="simple" aria-label={t('common.simpleMode')}>
        {t('common.simpleMode')}
      </ToggleButton>
      <ToggleButton value="advanced" aria-label={t('common.advancedMode')}>
        {t('common.advancedMode')}
      </ToggleButton>
    </ToggleButtonGroup>
  );
}

import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useTranslation } from 'react-i18next';

export type PageMode = 'simple' | 'advanced';

type PageModeToggleProps = {
  value: PageMode;
  onChange: (value: PageMode) => void;
  simpleLabel?: string;
  advancedLabel?: string;
  ariaLabel?: string;
};

export function PageModeToggle({
  value,
  onChange,
  simpleLabel,
  advancedLabel,
  ariaLabel,
}: PageModeToggleProps) {
  const { t } = useTranslation();
  const resolvedSimpleLabel = simpleLabel ?? t('common.simpleMode');
  const resolvedAdvancedLabel = advancedLabel ?? t('common.advancedMode');

  return (
    <ToggleButtonGroup
      value={value}
      exclusive
      size="small"
      color="primary"
      onChange={(_, next: PageMode | null) => {
        if (next) onChange(next);
      }}
      aria-label={ariaLabel ?? t('common.viewMode')}
    >
      <ToggleButton value="simple" aria-label={resolvedSimpleLabel}>
        {resolvedSimpleLabel}
      </ToggleButton>
      <ToggleButton value="advanced" aria-label={resolvedAdvancedLabel}>
        {resolvedAdvancedLabel}
      </ToggleButton>
    </ToggleButtonGroup>
  );
}

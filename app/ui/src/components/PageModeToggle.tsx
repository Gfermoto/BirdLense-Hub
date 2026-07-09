import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useTranslation } from 'react-i18next';

export type PageMode = 'basic' | 'advanced' | 'expert';

type PageModeToggleProps = {
  value: PageMode;
  onChange: (value: PageMode) => void;
  simpleLabel?: string;
  advancedLabel?: string;
  expertLabel?: string;
  ariaLabel?: string;
  /** When false, only basic + advanced toggles (System/Library). */
  showExpert?: boolean;
};

export function PageModeToggle({
  value,
  onChange,
  simpleLabel,
  advancedLabel,
  expertLabel,
  ariaLabel,
  showExpert = false,
}: PageModeToggleProps) {
  const { t } = useTranslation();
  const resolvedBasicLabel = simpleLabel ?? t('common.simpleMode');
  const resolvedAdvancedLabel = advancedLabel ?? t('common.advancedMode');
  const resolvedExpertLabel = expertLabel ?? t('common.expertMode');

  return (
    <ToggleButtonGroup
      value={value}
      exclusive
      size="medium"
      color="primary"
      onChange={(_, next: PageMode | null) => {
        if (next) onChange(next);
      }}
      aria-label={ariaLabel ?? t('common.viewMode')}
      sx={{
        '& .MuiToggleButton-root': {
          minHeight: 40,
          px: 1.75,
        },
      }}
    >
      <ToggleButton
        value="basic"
        aria-label={resolvedBasicLabel}
        title={t('common.simpleModeHint')}
      >
        {resolvedBasicLabel}
      </ToggleButton>
      <ToggleButton
        value="advanced"
        aria-label={resolvedAdvancedLabel}
        title={t('common.advancedModeHint')}
      >
        {resolvedAdvancedLabel}
      </ToggleButton>
      {showExpert ? (
        <ToggleButton
          value="expert"
          aria-label={resolvedExpertLabel}
          title={t('common.expertModeHint')}
        >
          {resolvedExpertLabel}
        </ToggleButton>
      ) : null}
    </ToggleButtonGroup>
  );
}

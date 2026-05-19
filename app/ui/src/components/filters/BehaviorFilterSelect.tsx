import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTranslation } from 'react-i18next';
import { BEHAVIOR_TAG_OPTIONS } from '../../constants/behaviorTags';

type BehaviorFilterSelectProps = {
  value: string;
  onChange: (behavior: string) => void;
  disabled?: boolean;
  size?: 'small' | 'medium';
  sx?: object;
};

export function BehaviorFilterSelect({
  value,
  onChange,
  disabled = false,
  size = 'small',
  sx,
}: BehaviorFilterSelectProps) {
  const { t } = useTranslation();

  const handleChange = (event: SelectChangeEvent<string>) => {
    onChange(event.target.value);
  };

  return (
    <FormControl size={size} sx={sx} disabled={disabled}>
      <InputLabel id="timeline-behavior-filter-label">
        {t('timeline.behaviorFilter')}
      </InputLabel>
      <Select
        data-testid="timeline-behavior-filter"
        labelId="timeline-behavior-filter-label"
        value={value}
        label={t('timeline.behaviorFilter')}
        onChange={handleChange}
      >
        <MenuItem value="">{t('timeline.behaviorFilterAll')}</MenuItem>
        {BEHAVIOR_TAG_OPTIONS.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {t(option.labelKey)}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

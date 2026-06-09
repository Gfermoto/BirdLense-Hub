import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { fetchCameras, type CameraRow } from '../../api/camerasHealth';
import { queryKeys } from '../../api/queryKeys';

type CameraFilterMultiSelectProps = {
  value: string[];
  onChange: (cameraIds: string[]) => void;
  disabled?: boolean;
  size?: 'small' | 'medium';
  sx?: object;
};

export function CameraFilterMultiSelect({
  value,
  onChange,
  disabled = false,
  size = 'small',
  sx,
}: CameraFilterMultiSelectProps) {
  const { t } = useTranslation();
  const { data: cameras = [], isLoading } = useQuery({
    queryKey: queryKeys.live.cameras,
    queryFn: fetchCameras,
    staleTime: 1000 * 60 * 5,
  });

  const selected = cameras.filter((cam) => value.includes(cam.id));

  return (
    <Autocomplete
      multiple
      data-testid="timeline-camera-filter"
      size={size}
      disabled={disabled || isLoading}
      options={cameras}
      value={selected}
      onChange={(_, next) => onChange(next.map((row) => row.id))}
      getOptionLabel={(option: CameraRow) =>
        option.name?.trim() ? `${option.name} (${option.id})` : option.id
      }
      isOptionEqualToValue={(option, selectedRow) => option.id === selectedRow.id}
      filterSelectedOptions
      renderInput={(params) => (
        <TextField
          {...params}
          label={t('timeline.cameraFilter')}
          placeholder={t('timeline.cameraFilterPlaceholder')}
        />
      )}
      sx={sx}
    />
  );
}

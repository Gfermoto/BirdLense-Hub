import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  fetchBirdProfiles,
  type BirdProfile,
} from '../../api/speciesOverviewDetections';
export function formatBirdProfileOptionLabel(profile: BirdProfile): string {
  const species = profile.species_name?.trim();
  return species ? `${profile.display_name} (${species})` : profile.display_name;
}

type BirdProfileFilterAutocompleteProps = {
  value: number | null;
  onChange: (profileId: number | null) => void;
  disabled?: boolean;
  size?: 'small' | 'medium';
  sx?: object;
};

export function BirdProfileFilterAutocomplete({
  value,
  onChange,
  disabled = false,
  size = 'small',
  sx,
}: BirdProfileFilterAutocompleteProps) {
  const { t } = useTranslation();
  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['bird-profiles', 'timeline-filter'],
    queryFn: async () => (await fetchBirdProfiles({ limit: 200 })).items,
    staleTime: 1000 * 60 * 5,
  });

  const selectedProfile = useMemo(
    () => profiles.find((p) => Number(p.id) === Number(value)) ?? null,
    [profiles, value],
  );

  return (
    <Autocomplete
      data-testid="timeline-bird-profile-filter"
      size={size}
      disabled={disabled || isLoading}
      options={profiles}
      value={selectedProfile}
      onChange={(_, next) => onChange(next ? Number(next.id) : null)}
      getOptionLabel={(option) => formatBirdProfileOptionLabel(option)}
      isOptionEqualToValue={(option, selected) =>
        Number(option.id) === Number(selected.id)
      }
      filterOptions={(options, state) => {
        const needle = state.inputValue.trim().toLowerCase();
        if (!needle) return options;
        return options.filter((option) => {
          const label = formatBirdProfileOptionLabel(option).toLowerCase();
          return label.includes(needle);
        });
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={t('timeline.birdProfileFilter')}
          placeholder={t('timeline.birdProfileFilterAll')}
        />
      )}
      sx={sx}
    />
  );
}

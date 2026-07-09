import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  fetchBirdDirectory,
  speciesDirectoryItems,
} from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';

type SpeciesCorrectionAutocompleteProps = {
  value: number | '';
  onChange: (speciesId: number | '') => void;
  disabled?: boolean;
  label?: string;
  excludeSpeciesId?: number;
  size?: 'small' | 'medium';
  sx?: object;
};

export function SpeciesCorrectionAutocomplete({
  value,
  onChange,
  disabled = false,
  label,
  excludeSpeciesId,
  size = 'small',
  sx,
}: SpeciesCorrectionAutocompleteProps) {
  const { t } = useTranslation();
  const { data: speciesList = [], isLoading } = useQuery({
    queryKey: queryKeys.speciesDirectory.correctionCatalog,
    queryFn: async () =>
      speciesDirectoryItems(await fetchBirdDirectory({ scope: 'allowlist' })),
    staleTime: 5 * 60 * 1000,
  });

  const options = useMemo(() => {
    const rows = speciesList
      .map((s) => ({ id: Number(s.id), name: String(s.name || '').trim() }))
      .filter((s) => Number.isFinite(s.id) && s.id > 0 && s.name.length > 0);
    if (excludeSpeciesId == null || !Number.isFinite(Number(excludeSpeciesId))) {
      return rows;
    }
    return rows.filter((s) => s.id !== Number(excludeSpeciesId));
  }, [excludeSpeciesId, speciesList]);

  const selected =
    value === '' ? null : options.find((s) => s.id === Number(value)) ?? null;

  return (
    <Autocomplete
      size={size}
      sx={sx}
      disabled={disabled || isLoading}
      options={options}
      value={selected}
      getOptionLabel={(option) => option.name}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      onChange={(_, option) => onChange(option?.id ?? '')}
      filterOptions={(items, state) => {
        const q = state.inputValue.trim().toLowerCase();
        if (!q) return items.slice(0, 200);
        return items
          .filter((item) => item.name.toLowerCase().includes(q))
          .slice(0, 200);
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label ?? t('unknowns.correctSpecies')}
          placeholder={t('unknowns.speciesSearchPlaceholder')}
        />
      )}
    />
  );
}

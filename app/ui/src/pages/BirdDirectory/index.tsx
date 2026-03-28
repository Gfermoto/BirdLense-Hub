import { useState, useMemo, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchBirdDirectory } from '../../api/api';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import SearchIcon from '@mui/icons-material/Search';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import { SelectChangeEvent } from '@mui/material/Select';
import { BirdDirectoryTreeView } from './BirdDirectoryTreeView';
import { Species } from '../../types';
import { useTranslation } from 'react-i18next';
import { PageHelp } from '../../components/PageHelp';
import { birdDirHelpConfig } from '../../page-help-config';

type FilterType = 'all' | 'regional' | 'observed';

interface NestedSpecies extends Species {
  children: NestedSpecies[];
  regional_scope?: boolean;
}

// Convert flat species list to nested tree structure
const convertToNested = (speciesList: Species[]): NestedSpecies[] => {
  const speciesMap = new Map<number, NestedSpecies>();

  speciesList.forEach((species) => {
    speciesMap.set(species.id, {
      ...species,
      children: [],
      count: species.count || 0,
    });
  });

  const result: NestedSpecies[] = [];
  speciesList.forEach((species) => {
    if (species.parent_id === null) {
      result.push(speciesMap.get(species.id)!);
    } else {
      speciesMap
        .get(species.parent_id)
        ?.children.push(speciesMap.get(species.id)!);
    }
  });

  // Calculate cumulative counts
  const calculateTotalCount = (node: NestedSpecies): number => {
    const childrenCount = node.children.reduce(
      (sum, child) => sum + calculateTotalCount(child),
      0,
    );
    node.count = (node.count || 0) + childrenCount;
    return node.count;
  };
  result.forEach(calculateTotalCount);

  return result[0]?.children || [];
};

const parentRegionalContext = (
  s: NestedSpecies,
  filter: FilterType,
  hasRegionalParent: boolean,
): boolean => {
  if (filter === 'regional') {
    return Boolean(s.regional_scope) || hasRegionalParent;
  }
  return s.active || hasRegionalParent;
};

// Filter tree by filter type
const filterNestedSpecies = (
  species: NestedSpecies[],
  filter: FilterType,
  hasRegionalParent = false,
): NestedSpecies[] => {
  return species
    .map((s) => ({
      ...s,
      children: filterNestedSpecies(
        s.children,
        filter,
        parentRegionalContext(s, filter, hasRegionalParent),
      ),
    }))
    .filter((s) => {
      if (filter === 'regional')
        return (
          hasRegionalParent ||
          Boolean(s.regional_scope) ||
          s.children.length > 0
        );
      if (filter === 'observed')
        return (s.count || 0) > 0 || s.children.length > 0;
      return true;
    });
};

// Filter tree by search query, keeping ancestors of matches
const filterBySearch = (
  species: NestedSpecies[],
  query: string,
): NestedSpecies[] => {
  if (!query) return species;
  const lowerQuery = query.toLowerCase();
  return species
    .map((node) => ({
      ...node,
      children: filterBySearch(node.children, query),
    }))
    .filter(
      (node) =>
        node.name.toLowerCase().includes(lowerQuery) ||
        node.children.length > 0,
    );
};

// Collect IDs of all expandable nodes + nodes that should auto-expand for search
const collectTreeInfo = (species: NestedSpecies[], searchQuery: string) => {
  const expandableIds: number[] = [];
  const autoExpandIds: number[] = [];
  const lowerQuery = searchQuery.toLowerCase();

  const traverse = (nodes: NestedSpecies[]): boolean => {
    let hasMatch = false;
    nodes.forEach((node) => {
      if (node.children.length > 0) {
        expandableIds.push(node.id);
        const childHasMatch = traverse(node.children);
        const selfMatches =
          searchQuery && node.name.toLowerCase().includes(lowerQuery);
        if (selfMatches || childHasMatch) {
          autoExpandIds.push(node.id);
          hasMatch = true;
        }
      } else if (searchQuery && node.name.toLowerCase().includes(lowerQuery)) {
        hasMatch = true;
      }
    });
    return hasMatch;
  };
  traverse(species);
  return { expandableIds, autoExpandIds };
};

export const BirdDirectory = () => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FilterType>('observed');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const {
    data: rawData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['bird-directory'],
    queryFn: fetchBirdDirectory,
  });

  // Process data once
  const { filteredData, expandableIds, autoExpandIds } = useMemo(() => {
    if (!rawData)
      return { filteredData: [], expandableIds: [], autoExpandIds: [] };
    const nested = convertToNested(rawData);
    const filtered = filterNestedSpecies(nested, filter);
    const searched = filterBySearch(filtered, searchQuery);
    const { expandableIds, autoExpandIds } = collectTreeInfo(
      filtered,
      searchQuery,
    );
    return { filteredData: searched, expandableIds, autoExpandIds };
  }, [rawData, filter, searchQuery]);

  // Auto-expand when searching
  useEffect(() => {
    if (searchQuery) {
      setExpandedIds(new Set(autoExpandIds));
    }
  }, [searchQuery, autoExpandIds]);

  const handleToggleExpand = useCallback((id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error)
    return (
      <Box sx={{ p: 2 }}>
        <Box component="span" sx={{ color: 'error.main' }}>{t('species.errorLoad')}</Box>
        <Button variant="outlined" sx={{ mt: 2 }} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
      </Box>
    );

  return (
    <>
      <PageHelp {...birdDirHelpConfig} />

      {/* Controls row - consistent height with sx overrides */}
      <Box display="flex" flexWrap="wrap" alignItems="center" gap={1.5} mb={3}>
        <TextField
          size="small"
          placeholder={t('species.searchPlaceholder')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                </InputAdornment>
              ),
            },
          }}
          sx={{ width: 180 }}
        />

        <FormControl size="small">
          <InputLabel id="filter-label">{t('species.filter')}</InputLabel>
          <Select<FilterType>
            labelId="filter-label"
            value={filter}
            onChange={(e: SelectChangeEvent<FilterType>) =>
              setFilter(e.target.value as FilterType)
            }
            label={t('species.filter')}
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="all">{t('species.allSpecies')}</MenuItem>
            <MenuItem value="regional">{t('species.regional')}</MenuItem>
            <MenuItem value="observed">{t('species.observed')}</MenuItem>
          </Select>
        </FormControl>

        <IconButton
          size="small"
          onClick={() => setExpandedIds(new Set(expandableIds))}
          disabled={
            expandableIds.length === 0 ||
            expandedIds.size === expandableIds.length
          }
          title={t('species.expandAll')}
        >
          <UnfoldMoreIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          onClick={() => setExpandedIds(new Set())}
          disabled={expandedIds.size === 0}
          title={t('species.collapseAll')}
        >
          <UnfoldLessIcon fontSize="small" />
        </IconButton>
      </Box>

      {filteredData.length === 0 ? (
        <Box sx={{ color: 'text.secondary', py: 4 }}>
          {searchQuery
            ? t('species.noMatch', { query: searchQuery })
            : t('species.noSpeciesFilter')}
        </Box>
      ) : (
        <BirdDirectoryTreeView
          birds={filteredData}
          expandedIds={expandedIds}
          onToggleExpand={handleToggleExpand}
          searchQuery={searchQuery}
          highlightField={filter === 'regional' ? 'regional_scope' : 'active'}
        />
      )}
    </>
  );
};

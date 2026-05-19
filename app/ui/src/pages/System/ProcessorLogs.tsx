import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useProcessorLogsQuery } from '../../hooks/useSystemQueries';
import { SystemCardShell } from './SystemCardShell';

type LogLevelFilter = 'all' | 'error' | 'warning' | 'info' | 'debug';

function lineMatchesLevel(line: string, filter: LogLevelFilter): boolean {
  if (filter === 'all') return true;
  const upper = line.toUpperCase();
  if (filter === 'error') {
    return (
      upper.includes(' ERROR') ||
      upper.includes('[ERROR]') ||
      upper.includes('CRITICAL') ||
      upper.includes('Traceback')
    );
  }
  if (filter === 'warning') {
    return upper.includes(' WARNING') || upper.includes('[WARNING]');
  }
  if (filter === 'info') {
    return upper.includes(' INFO') || upper.includes('[INFO]');
  }
  return upper.includes(' DEBUG') || upper.includes('[DEBUG]');
}

export const ProcessorLogs = () => {
  const { t } = useTranslation();
  const [lines, setLines] = useState(100);
  const [levelFilter, setLevelFilter] = useState<LogLevelFilter>('all');

  const { data, isLoading, error, refetch } = useProcessorLogsQuery(lines);
  const filteredLines = useMemo(() => {
    const raw = data?.lines ?? [];
    if (levelFilter === 'all') return raw;
    return raw.filter((line) => lineMatchesLevel(line, levelFilter));
  }, [data?.lines, levelFilter]);

  return (
    <SystemCardShell
      title={t('system.processorLogs')}
      description={t('system.processorLogsHint', { lines })}
      statusLabel={t('system.processorLogsLive')}
      statusTone="info"
      actions={
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={levelFilter}
            onChange={(_, v: LogLevelFilter | null) => {
              if (v) setLevelFilter(v);
            }}
          >
            {(['all', 'error', 'warning', 'info', 'debug'] as const).map(
              (lvl) => (
                <ToggleButton key={lvl} value={lvl}>
                  {t(`system.processorLogsFilter.${lvl}`)}
                </ToggleButton>
              ),
            )}
          </ToggleButtonGroup>
          {[50, 100, 200, 500].map((n) => (
            <Button
              key={n}
              size="small"
              variant={lines === n ? 'contained' : 'outlined'}
              onClick={() => setLines(n)}
            >
              {n}
            </Button>
          ))}
          <Button size="small" variant="outlined" onClick={() => refetch()}>
            {t('system.refresh')}
          </Button>
        </Box>
      }
    >
      <Box>
        {isLoading && <CircularProgress size={24} />}
        {error ? (
          <Alert severity="error" variant="outlined">
            {error instanceof Error ? error.message : 'Failed to load logs'}
          </Alert>
        ) : null}
        {data ? (
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              maxHeight: 400,
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.75rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {filteredLines.length ? (
              filteredLines.map((line: string, i: number) => (
                <Box key={i} component="span" sx={{ display: 'block' }}>
                  {line}
                </Box>
              ))
            ) : (
              <Typography color="text.secondary">
                {data.lines?.length
                  ? t('system.processorLogsFilterEmpty', {
                      filter: t(`system.processorLogsFilter.${levelFilter}`),
                      lines,
                    })
                  : t('system.noLogs')}
                {data.path ? ` · ${data.path}` : ''}
              </Typography>
            )}
          </Paper>
        ) : null}
      </Box>
    </SystemCardShell>
  );
};

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import { useProcessorLogsQuery } from '../../hooks/useSystemQueries';
import { SystemCardShell } from './SystemCardShell';

export const ProcessorLogs = () => {
  const { t } = useTranslation();
  const [lines, setLines] = useState(100);

  const { data, isLoading, error, refetch } = useProcessorLogsQuery(lines);

  return (
    <SystemCardShell
      title={t('system.processorLogs')}
      description={t('system.processorLogsHint', { lines })}
      statusLabel={t('system.processorLogsLive')}
      statusTone="info"
      actions={
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
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
          <Alert severity="error">
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
            {data.lines?.length ? (
              data.lines.map((line: string, i: number) => (
                <Box key={i} component="span" sx={{ display: 'block' }}>
                  {line}
                </Box>
              ))
            ) : (
              <Typography color="text.secondary">
                {t('system.noLogs')}. File: {data.path}
              </Typography>
            )}
          </Paper>
        ) : null}
      </Box>
    </SystemCardShell>
  );
};

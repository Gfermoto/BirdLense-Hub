import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import { useProcessorLogsQuery } from '../../hooks/useSystemQueries';

export const ProcessorLogs = () => {
  const { t } = useTranslation();
  const [lines, setLines] = useState(100);

  const { data, isLoading, error, refetch } = useProcessorLogsQuery(lines);

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {t('system.processorLogs')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('system.processorLogsHint', { lines })}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
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
      {isLoading && <CircularProgress size={24} />}
      {error && (
        <Typography color="error">
          {error instanceof Error ? error.message : 'Failed to load logs'}
        </Typography>
      )}
      {data && (
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
      )}
    </Box>
  );
};

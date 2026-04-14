import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Alert from '@mui/material/Alert';
import {
  downloadSettingsYamlFull,
  downloadSettingsYamlSafe,
  importSettingsYaml,
} from '../../../api/api';
import { queryKeys } from '../../../api/queryKeys';

type Props = {
  yamlSafeExportEnabled: boolean;
  yamlAdminBackupEnabled: boolean;
};

export function GeneralYamlBackupAccordion({
  yamlSafeExportEnabled,
  yamlAdminBackupEnabled,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [yamlMsg, setYamlMsg] = useState<{ sev: 'success' | 'error'; text: string } | null>(
    null,
  );

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.yamlBackupTitle')}
      </AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {yamlAdminBackupEnabled
            ? t('settings.yamlBackupDesc')
            : t('settings.yamlBackupDescSafeOnly')}
        </Typography>
        {yamlMsg ? (
          <Alert severity={yamlMsg.sev} sx={{ mb: 2 }} onClose={() => setYamlMsg(null)}>
            {yamlMsg.text}
          </Alert>
        ) : null}
        <Stack direction="row" flexWrap="wrap" gap={1} useFlexGap>
          {yamlSafeExportEnabled ? (
            <Button
              variant="outlined"
              size="small"
              onClick={async () => {
                setYamlMsg(null);
                try {
                  await downloadSettingsYamlSafe();
                } catch (e) {
                  setYamlMsg({
                    sev: 'error',
                    text: e instanceof Error ? e.message : t('settings.yamlImportFailed'),
                  });
                }
              }}
            >
              {t('settings.yamlDownloadSafe')}
            </Button>
          ) : null}
          {yamlAdminBackupEnabled ? (
            <>
              <Button
                variant="outlined"
                size="small"
                color="warning"
                onClick={async () => {
                  if (!window.confirm(t('settings.yamlFullConfirm'))) return;
                  setYamlMsg(null);
                  try {
                    await downloadSettingsYamlFull();
                  } catch (e) {
                    setYamlMsg({
                      sev: 'error',
                      text: e instanceof Error ? e.message : t('settings.yamlImportFailed'),
                    });
                  }
                }}
              >
                {t('settings.yamlDownloadFull')}
              </Button>
              <Button variant="outlined" size="small" onClick={() => fileRef.current?.click()}>
                {t('settings.yamlImport')}
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".yaml,.yml,text/yaml"
                hidden
                onChange={async (ev) => {
                  const f = ev.target.files?.[0];
                  ev.target.value = '';
                  if (!f) return;
                  setYamlMsg(null);
                  const r = await importSettingsYaml(f);
                  if (r.ok) {
                    setYamlMsg({ sev: 'success', text: r.message || t('settings.yamlImportOk') });
                    await queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
                  } else {
                    setYamlMsg({
                      sev: 'error',
                      text: r.message || t('settings.yamlImportFailed'),
                    });
                  }
                }}
              />
            </>
          ) : null}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

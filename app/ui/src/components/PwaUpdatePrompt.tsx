import { useState, useEffect } from 'react';
import Button from '@mui/material/Button';
import Snackbar from '@mui/material/Snackbar';
import { useTranslation } from 'react-i18next';

export function PwaUpdatePrompt() {
  const { t } = useTranslation();
  const [showRefresh, setShowRefresh] = useState(false);
  const [showOffline, setShowOffline] = useState(false);
  const [updateSW, setUpdateSW] = useState<(() => void) | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator))
      return;
    import('virtual:pwa-register').then(({ registerSW }) => {
      const upd = registerSW({
        onNeedRefresh() {
          setShowRefresh(true);
        },
        onOfflineReady() {
          setShowOffline(true);
        },
      });
      setUpdateSW(() => upd);
    });
  }, []);

  const handleRefresh = () => {
    updateSW?.();
    setShowRefresh(false);
  };

  const snackbarContentSx = {
    bgcolor: '#1e293b',
    color: '#f8fafc',
    '& .MuiSnackbarContent-action': { color: '#f8fafc' },
  } as const;

  return (
    <>
      <Snackbar
        open={showRefresh}
        message={t('pwa.updateAvailable')}
        action={
          <Button
            color="inherit"
            size="small"
            onClick={handleRefresh}
            sx={{ fontWeight: 600 }}
          >
            {t('pwa.refresh')}
          </Button>
        }
        onClose={() => setShowRefresh(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        ContentProps={{ sx: snackbarContentSx }}
      />
      <Snackbar
        open={showOffline}
        message={t('pwa.offlineReady')}
        onClose={() => setShowOffline(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        ContentProps={{ sx: snackbarContentSx }}
      />
    </>
  );
}

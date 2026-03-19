import React, { useState, useEffect } from 'react';
import { Snackbar, Button } from '@mui/material';
import { useTranslation } from 'react-i18next';

export function PwaUpdatePrompt() {
  const { t } = useTranslation();
  const [showRefresh, setShowRefresh] = useState(false);
  const [showOffline, setShowOffline] = useState(false);
  const [updateSW, setUpdateSW] = useState<(() => void) | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
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

  return (
    <>
      <Snackbar
        open={showRefresh}
        message={t('pwa.updateAvailable')}
        action={
          <Button color="primary" size="small" onClick={handleRefresh}>
            {t('pwa.refresh')}
          </Button>
        }
        onClose={() => setShowRefresh(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
      <Snackbar
        open={showOffline}
        message={t('pwa.offlineReady')}
        onClose={() => setShowOffline(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </>
  );
}

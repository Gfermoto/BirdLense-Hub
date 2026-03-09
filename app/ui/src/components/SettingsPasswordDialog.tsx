import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import { verifySettingsPassword } from '../api/api';

export const SettingsPasswordDialog = ({
  open,
  onSuccess,
}: {
  open: boolean;
  onSuccess: () => void;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const ok = await verifySettingsPassword(password);
    if (ok) {
      setPassword('');
      onSuccess();
    } else {
      setError(t('settings.passwordError'));
    }
  };

  const handleClose = () => {
    setPassword('');
    setError('');
    navigate('/');
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>{t('settings.passwordTitle')}</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            type="password"
            label={t('settings.passwordLabel')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={!!error}
            helperText={error}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose}>{t('common.cancel')}</Button>
          <Button type="submit" variant="contained" disabled={!password.trim()}>
            {t('settings.passwordSubmit')}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

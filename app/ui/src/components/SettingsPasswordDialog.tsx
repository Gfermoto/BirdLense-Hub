import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import { PasswordField } from './PasswordField';
import { verifySettingsPassword } from '../api/settingsSession';

export const SettingsPasswordDialog = ({
  open,
  onSuccess,
  onClose,
  requireAdmin = false,
}: {
  open: boolean;
  onSuccess: (role?: 'admin' | 'contributor') => void;
  onClose?: () => void;
  requireAdmin?: boolean;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const result = await verifySettingsPassword(password);
    if (result.ok) {
      if (requireAdmin && result.role === 'contributor') {
        setError(t('settings.adminRequired'));
        return;
      }
      setPassword('');
      onSuccess(result.role);
    } else {
      setError(
        result.error === 'server_error'
          ? t('settings.passwordServerError')
          : t('settings.passwordError'),
      );
    }
  };

  const handleClose = () => {
    setPassword('');
    setError('');
    if (onClose) {
      onClose();
    } else {
      navigate('/');
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>{t('settings.passwordTitle')}</DialogTitle>
        <DialogContent sx={{ pt: 2.5, px: 3, overflow: 'visible' }}>
          <PasswordField
            value={password}
            onChange={setPassword}
            label={t('settings.passwordLabel')}
            helperText={error}
            error={!!error}
            autoFocus
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

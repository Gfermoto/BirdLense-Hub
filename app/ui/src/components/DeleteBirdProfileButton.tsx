import { useState } from 'react';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteBirdProfile } from '../api/speciesOverviewDetections';
import { getApiErrorMessage } from '../api/api';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

type DeleteBirdProfileButtonProps = {
  profileId: number;
  profileName: string;
  size?: 'small' | 'medium';
  onDeleted?: () => void;
};

/** Удаляет кличку из глобального каталога (все визиты отвязываются). */
export function DeleteBirdProfileButton({
  profileId,
  profileName,
  size = 'small',
  onDeleted,
}: DeleteBirdProfileButtonProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => deleteBirdProfile(profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bird-profiles'] });
      setConfirmOpen(false);
      onDeleted?.();
    },
    onError: (err) => {
      setError(getApiErrorMessage(err, t('birdProfiles.deleteFailed')));
    },
  });

  return (
    <>
      <Tooltip title={t('birdProfiles.deleteTooltip')}>
        <span>
          <IconButton
            size={size}
            color="error"
            aria-label={t('birdProfiles.deleteAction')}
            data-testid="delete-bird-profile-button"
            disabled={deleteMutation.isPending}
            onClick={(event) => {
              event.stopPropagation();
              event.preventDefault();
              setConfirmOpen(true);
            }}
          >
            <DeleteOutlineIcon fontSize="inherit" />
          </IconButton>
        </span>
      </Tooltip>
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>{t('birdProfiles.deleteAction')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('birdProfiles.deleteConfirm', { name: profileName })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate()}
          >
            {t('birdProfiles.deleteAction')}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={!!error} autoHideDuration={8000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </>
  );
}

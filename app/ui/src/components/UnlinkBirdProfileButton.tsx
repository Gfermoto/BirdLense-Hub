import { useState } from 'react';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { clearDetectionBirdProfile } from '../api/speciesOverviewDetections';
import { getApiErrorMessage } from '../api/api';
import { invalidateLocalSpeciesEditCaches } from '../api/invalidateLocalSpeciesCaches';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

type UnlinkBirdProfileButtonProps = {
  detectionId: number;
  videoId?: number;
  profileName: string;
  size?: 'small' | 'medium';
  onUnlinked?: () => void;
};

export function UnlinkBirdProfileButton({
  detectionId,
  videoId,
  profileName,
  size = 'small',
  onUnlinked,
}: UnlinkBirdProfileButtonProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unlinkMutation = useMutation({
    mutationFn: () => clearDetectionBirdProfile(detectionId),
    onSuccess: () => {
      invalidateLocalSpeciesEditCaches(queryClient, videoId);
      queryClient.invalidateQueries({ queryKey: ['bird-profiles'] });
      setConfirmOpen(false);
      onUnlinked?.();
    },
    onError: (err) => {
      setError(getApiErrorMessage(err, t('video.unlinkBirdProfileFailed')));
    },
  });

  return (
    <>
      <Tooltip title={t('video.unlinkBirdProfileTooltip')}>
        <span>
          <IconButton
            size={size}
            aria-label={t('video.unlinkBirdProfile')}
            data-testid="unlink-bird-profile-button"
            disabled={unlinkMutation.isPending}
            onClick={(event) => {
              event.stopPropagation();
              event.preventDefault();
              setConfirmOpen(true);
            }}
          >
            <LinkOffIcon fontSize="inherit" />
          </IconButton>
        </span>
      </Tooltip>
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>{t('video.unlinkBirdProfile')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('video.unlinkBirdProfileConfirm', { name: profileName })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={unlinkMutation.isPending}
            onClick={() => unlinkMutation.mutate()}
          >
            {t('video.unlinkBirdProfileAction')}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={!!error}
        autoHideDuration={8000}
        onClose={() => setError(null)}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </>
  );
}

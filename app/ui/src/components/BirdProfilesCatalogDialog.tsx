import { useState } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteBirdProfile,
  fetchBirdProfiles,
  type BirdProfile,
} from '../api/speciesOverviewDetections';
import { queryKeys } from '../api/queryKeys';
import { formatBirdProfileOptionLabel } from './filters/BirdProfileFilterAutocomplete';
import { getApiErrorMessage } from '../api/api';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import { PageLoadingState } from './PageState';

type BirdProfilesCatalogDialogProps = {
  open: boolean;
  onClose: () => void;
  onDeleted?: (profileId: number) => void;
};

export function BirdProfilesCatalogDialog({
  open,
  onClose,
  onDeleted,
}: BirdProfilesCatalogDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<BirdProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: queryKeys.birdProfiles.catalog,
    queryFn: async () => (await fetchBirdProfiles({ limit: 100 })).items,
    enabled: open,
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (profileId: number) => deleteBirdProfile(profileId),
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.birdProfiles.all });
      setPendingDelete(null);
      setSuccess(
        t('birdProfiles.deletedSuccess', {
          name: payload.display_name,
          count: payload.unlinked_detections,
        }),
      );
      onDeleted?.(payload.id);
    },
    onError: (err) => {
      setError(getApiErrorMessage(err, t('birdProfiles.deleteFailed')));
    },
  });

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>{t('birdProfiles.catalogTitle')}</DialogTitle>
        <DialogContent dividers>
          <DialogContentText sx={{ mb: 2 }}>
            {t('birdProfiles.catalogHint')}
          </DialogContentText>
          {isLoading ? (
            <PageLoadingState label={t('common.loading')} />
          ) : profiles.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t('birdProfiles.empty')}
            </Typography>
          ) : (
            <List dense disablePadding>
              {profiles.map((profile) => (
                <ListItem key={profile.id} divider>
                  <ListItemText
                    primary={formatBirdProfileOptionLabel(profile)}
                    secondary={profile.status}
                  />
                  <ListItemSecondaryAction>
                    <Tooltip title={t('birdProfiles.deleteTooltip')}>
                      <IconButton
                        edge="end"
                        aria-label={t('birdProfiles.deleteAction')}
                        data-testid={`delete-bird-profile-${profile.id}`}
                        disabled={deleteMutation.isPending}
                        onClick={() => setPendingDelete(profile)}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>{t('common.close')}</Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={!!pendingDelete}
        onClose={() => setPendingDelete(null)}
      >
        <DialogTitle>{t('birdProfiles.deleteAction')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('birdProfiles.deleteConfirm', {
              name: pendingDelete
                ? formatBirdProfileOptionLabel(pendingDelete)
                : '',
            })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>
            {t('common.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={!pendingDelete || deleteMutation.isPending}
            onClick={() => {
              if (pendingDelete) {
                deleteMutation.mutate(Number(pendingDelete.id));
              }
            }}
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
      <Snackbar
        open={!!success}
        autoHideDuration={6000}
        onClose={() => setSuccess(null)}
      >
        <Alert severity="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      </Snackbar>
    </>
  );
}

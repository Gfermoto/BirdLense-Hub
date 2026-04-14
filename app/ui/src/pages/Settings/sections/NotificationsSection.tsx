import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';
import {
  fetchCoordinatesByZip,
  fetchVapidPublicKey,
  refreshTelegramProxy,
  subscribePush,
  patchSettings,
  sendTestNotification,
} from '../../../api/api';

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

function WebPushSubscribeButton({ notificationsEnabled }: { notificationsEnabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'idle' | 'loading' | 'subscribed' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const handleSubscribe = async () => {
    if (!notificationsEnabled) return;
    if (!('Notification' in window) || !('PushManager' in window) || !('serviceWorker' in navigator)) {
      setErrorMsg(t('settings.webPushUnsupported'));
      setStatus('error');
      return;
    }
    if (typeof window !== 'undefined' && !window.isSecureContext && !window.location.hostname.includes('localhost')) {
      setErrorMsg(t('settings.webPushUnsupported'));
      setStatus('error');
      return;
    }
    setStatus('loading');
    setErrorMsg('');
    try {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        setErrorMsg('Permission denied');
        setStatus('error');
        return;
      }
      await patchSettings({ general: { enable_notifications: true } });
      const reg = await navigator.serviceWorker.ready;
      const vapidKey = await fetchVapidPublicKey();
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey) as BufferSource,
      });
      await subscribePush(sub);
      setStatus('subscribed');
    } catch (e) {
      const err = e as { message?: string; response?: { data?: { error?: string } } };
      const msg = err.response?.data?.error || (err instanceof Error ? err.message : 'Failed');
      setErrorMsg(msg);
      setStatus('error');
    }
  };

  const supported = typeof window !== 'undefined' && 'Notification' in window && 'PushManager' in window && 'serviceWorker' in navigator;
  const isSecure = typeof window !== 'undefined' && (window.isSecureContext || window.location.hostname === 'localhost');

  if (!supported || !isSecure) {
    return (
      <Typography variant="body2" color="text.secondary">
        {t('settings.webPushUnsupported')}
      </Typography>
    );
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.webPushDesc')}
      </Typography>
      <Button
        variant="outlined"
        onClick={handleSubscribe}
        disabled={!notificationsEnabled || status === 'loading'}
      >
        {status === 'loading' ? '...' : status === 'subscribed' ? t('settings.webPushSubscribed') : t('settings.webPushSubscribe')}
      </Button>
      {errorMsg && (
        <Typography variant="body2" color="error" sx={{ mt: 1 }}>
          {errorMsg}
        </Typography>
      )}
    </Box>
  );
}

function TestTelegramButton({ notificationsEnabled }: { notificationsEnabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [msg, setMsg] = useState<string>('');

  const handleTest = async () => {
    if (!notificationsEnabled) return;
    setStatus('loading');
    setMsg('');
    const result = await sendTestNotification();
    setStatus(result.success ? 'success' : 'error');
    setMsg(result.message || '');
  };

  return (
    <Box>
      <Button
        variant="outlined"
        size="small"
        onClick={handleTest}
        disabled={!notificationsEnabled || status === 'loading'}
      >
        {status === 'loading' ? '...' : t('settings.testTelegram')}
      </Button>
      {msg && (
        <Typography variant="body2" color={status === 'success' ? 'text.secondary' : 'error'} sx={{ mt: 0.5, ml: 1, display: 'inline' }}>
          {msg}
        </Typography>
      )}
    </Box>
  );
}

function RefreshTelegramProxyButton({ notificationsEnabled }: { notificationsEnabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [msg, setMsg] = useState<string>('');

  const handleRefresh = async () => {
    if (!notificationsEnabled) return;
    setStatus('loading');
    setMsg('');
    const result = await refreshTelegramProxy();
    setStatus(result.success ? 'success' : 'error');
    setMsg(result.message || '');
  };

  return (
    <Box>
      <Button
        variant="outlined"
        size="small"
        onClick={handleRefresh}
        disabled={!notificationsEnabled || status === 'loading'}
      >
        {status === 'loading' ? '...' : t('settings.refreshTelegramProxy')}
      </Button>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {t('settings.refreshTelegramProxyHint')}
      </Typography>
      {msg && (
        <Typography variant="body2" color={status === 'success' ? 'text.secondary' : 'error'} sx={{ mt: 0.5, ml: 1, display: 'inline' }}>
          {msg}
        </Typography>
      )}
    </Box>
  );
}

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  observedSpecies: Array<{ id: number; name: string; count: number }>;
};

export function NotificationsSection({ form, observedSpecies }: Props) {
  const { t } = useTranslation();

  const handleZipLookup = async () => {
    const zip = form.getFieldValue('secrets.zip');
    if (!zip) return;
    try {
      const { lat, lon } = await fetchCoordinatesByZip(zip);
      form.setFieldValue('secrets.latitude', lat);
      form.setFieldValue('secrets.longitude', lon);
    } catch (error) {
      console.log(error);
      alert(t('settings.zipFetchFailed'));
    }
  };

  return (
    <>
      {/* ========== 4. УВЕДОМЛЕНИЯ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionNotifications')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionNotifications')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionNotificationsDesc')}
            </Typography>

            <ServiceBlock title={t('settings.serviceTelegram')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="general.enable_notifications">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.notifications')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <form.Subscribe selector={(state) => [state.values.general?.enable_notifications]}>
                  {([notificationsEnabled]) => (
                    <>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="notifications.telegram_bot_token">
                          {(field) => (
                            <PasswordField
                              value={field.state.value ?? ''}
                              onChange={(v) => field.handleChange(v)}
                              label={t('settings.telegramBotToken')}
                              helperText={t('settings.telegramBotTokenHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="notifications.telegram_chat_id">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramChatId')}
                              helperText={t('settings.telegramChatIdHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                  <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="flex-start">
                    <TestTelegramButton notificationsEnabled={!!notificationsEnabled} />
                    <RefreshTelegramProxyButton notificationsEnabled={!!notificationsEnabled} />
                  </Stack>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="notifications.base_url">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.notificationsBaseUrl')}
                              helperText={t('settings.notificationsBaseUrlHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <Typography variant="subtitle2" sx={{ mt: 0.5 }}>
                          {t('settings.telegramNetworkTitle')}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="notifications.telegram_proxy_type">
                          {(field) => (
                            <FormControl fullWidth disabled={!notificationsEnabled}>
                              <InputLabel id="tg-proxy-type-label">
                                {t('settings.telegramProxyType')}
                              </InputLabel>
                              <Select
                                labelId="tg-proxy-type-label"
                                label={t('settings.telegramProxyType')}
                                value={field.state.value ?? 'socks_http'}
                                onChange={(e) => field.handleChange(e.target.value as string)}
                              >
                                <MenuItem value="none">{t('settings.telegramProxyTypeNone')}</MenuItem>
                                <MenuItem value="socks_http">
                                  {t('settings.telegramProxyTypeSocksHttp')}
                                </MenuItem>
                                <MenuItem value="mtproto">
                                  {t('settings.telegramProxyTypeMtproto')}
                                </MenuItem>
                              </Select>
                              <FormHelperText>{t('settings.telegramProxyTypeHint')}</FormHelperText>
                            </FormControl>
                          )}
                        </form.Field>
                      </Grid>
                      <form.Subscribe
                        selector={(s) => s.values.notifications?.telegram_proxy_type ?? 'socks_http'}
                      >
                        {(proxyType) => (
                          <>
                            {(proxyType === 'socks_http' || !proxyType) && (
                              <Grid size={{ xs: 12 }}>
                                <form.Field name="notifications.telegram_proxy_url">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) => field.handleChange(e.target.value)}
                                      label={t('settings.telegramProxyUrl')}
                                      placeholder="socks5h://127.0.0.1:9050"
                                      helperText={t('settings.telegramProxyUrlHint')}
                                      disabled={!notificationsEnabled}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                            )}
                            {proxyType === 'mtproto' && (
                              <>
                                <Grid size={{ xs: 12 }}>
                                  <Alert severity="info" sx={{ py: 1 }}>
                                    {t('settings.telegramMtprotoApiHint')}
                                  </Alert>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 8 }}>
                                  <form.Field name="notifications.telegram_mtproto_host">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        value={field.state.value ?? ''}
                                        onChange={(e) => field.handleChange(e.target.value)}
                                        label={t('settings.telegramMtprotoHost')}
                                        placeholder="proxy.example.com"
                                        disabled={!notificationsEnabled}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 4 }}>
                                  <form.Field name="notifications.telegram_mtproto_port">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        type="number"
                                        inputProps={{ min: 1, max: 65535 }}
                                        value={field.state.value ?? 443}
                                        onChange={(e) =>
                                          field.handleChange(
                                            Math.max(
                                              1,
                                              Math.min(65535, Number(e.target.value) || 443),
                                            ),
                                          )
                                        }
                                        label={t('settings.telegramMtprotoPort')}
                                        disabled={!notificationsEnabled}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12 }}>
                                  <form.Field name="notifications.telegram_mtproto_secret">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        multiline
                                        minRows={2}
                                        value={field.state.value ?? ''}
                                        onChange={(e) => field.handleChange(e.target.value)}
                                        label={t('settings.telegramMtprotoSecret')}
                                        placeholder="ee… / dd…"
                                        helperText={t('settings.telegramMtprotoSecretHint')}
                                        disabled={!notificationsEnabled}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="notifications.telegram_api_id">
                                    {(field) => (
                                      <TextField
                                        fullWidth
                                        type="number"
                                        inputProps={{ min: 0, step: 1 }}
                                        value={field.state.value ?? 0}
                                        onChange={(e) =>
                                          field.handleChange(Math.max(0, Number(e.target.value) || 0))
                                        }
                                        label={t('settings.telegramApiId')}
                                        helperText={t('settings.telegramApiIdHint')}
                                        disabled={!notificationsEnabled}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                  <form.Field name="notifications.telegram_api_hash">
                                    {(field) => (
                                      <PasswordField
                                        value={field.state.value ?? ''}
                                        onChange={(v) => field.handleChange(v)}
                                        label={t('settings.telegramApiHash')}
                                        helperText={t('settings.telegramApiHashHint')}
                                        disabled={!notificationsEnabled}
                                      />
                                    )}
                                  </form.Field>
                                </Grid>
                              </>
                            )}
                          </>
                        )}
                      </form.Subscribe>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="notifications.telegram_api_base">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramApiBase')}
                              helperText={t('settings.telegramApiBaseHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.telegram_timeout">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 30, max: 600, step: 10 }}
                              value={field.state.value ?? 300}
                              onChange={(e) =>
                                field.handleChange(Math.max(30, Math.min(600, Number(e.target.value) || 300)))
                              }
                              label={t('settings.telegramTimeout')}
                              helperText={t('settings.telegramTimeoutHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.telegram_retries">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 1, max: 5, step: 1 }}
                              value={field.state.value ?? 5}
                              onChange={(e) =>
                                field.handleChange(Math.max(1, Math.min(5, Number(e.target.value) || 5)))
                              }
                              label={t('settings.telegramRetries')}
                              helperText={t('settings.telegramRetriesHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.compress_photo_over_kb">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 10000, step: 50 }}
                              value={field.state.value ?? 400}
                              onChange={(e) =>
                                field.handleChange(Math.max(0, Math.min(10000, Number(e.target.value) || 0)))
                              }
                              label={t('settings.telegramCompressOverKb')}
                              helperText={t('settings.telegramCompressOverKbHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.telegram_max_side_px">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 4096, step: 64 }}
                              value={field.state.value ?? 1024}
                              onChange={(e) =>
                                field.handleChange(Math.max(0, Math.min(4096, Number(e.target.value) || 0)))
                              }
                              label={t('settings.telegramMaxSidePx')}
                              helperText={t('settings.telegramMaxSidePxHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.message_thread_id">
                          {(field) => (
                            <TextField
                              fullWidth
                              value={field.state.value ?? ''}
                              onChange={(e) => field.handleChange(e.target.value)}
                              label={t('settings.telegramThreadId')}
                              helperText={t('settings.telegramThreadIdHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.disable_notification">
                          {(field) => (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={field.state.value ?? false}
                                  onChange={(e) => field.handleChange(e.target.checked)}
                                  disabled={!notificationsEnabled}
                                />
                              }
                              label={t('settings.telegramSilent')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.protect_content">
                          {(field) => (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={field.state.value ?? false}
                                  onChange={(e) => field.handleChange(e.target.checked)}
                                  disabled={!notificationsEnabled}
                                />
                              }
                              label={t('settings.telegramProtect')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.link_preview_large">
                          {(field) => (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={field.state.value ?? false}
                                  onChange={(e) => field.handleChange(e.target.checked)}
                                  disabled={!notificationsEnabled}
                                />
                              }
                              label={t('settings.telegramLinkPreviewLarge')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.send_photo">
                          {(field) => (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={field.state.value ?? true}
                                  onChange={(e) => field.handleChange(e.target.checked)}
                                  disabled={!notificationsEnabled}
                                />
                              }
                              label={t('settings.telegramSendPhoto')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.use_custom_emoji">
                          {(field) => (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={field.state.value ?? false}
                                  onChange={(e) => field.handleChange(e.target.checked)}
                                  disabled={!notificationsEnabled}
                                />
                              }
                              label={t('settings.telegramUseCustomEmoji')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <form.Subscribe selector={(state) => state.values.notifications?.use_custom_emoji}>
                        {(useCustomEmoji) =>
                          useCustomEmoji ? (
                            <>
                              <Grid size={{ xs: 12, sm: 4 }}>
                                <form.Field name="notifications.custom_emoji_id_bird">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) => field.handleChange(e.target.value)}
                                      label={t('settings.telegramCustomEmojiBird')}
                                      helperText={t('settings.telegramCustomEmojiHint')}
                                      disabled={!notificationsEnabled}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                              <Grid size={{ xs: 12, sm: 4 }}>
                                <form.Field name="notifications.custom_emoji_id_chipmunk">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) => field.handleChange(e.target.value)}
                                      label={t('settings.telegramCustomEmojiChipmunk')}
                                      helperText={t('settings.telegramCustomEmojiHint')}
                                      disabled={!notificationsEnabled}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                              <Grid size={{ xs: 12, sm: 4 }}>
                                <form.Field name="notifications.custom_emoji_id_open_live">
                                  {(field) => (
                                    <TextField
                                      fullWidth
                                      value={field.state.value ?? ''}
                                      onChange={(e) => field.handleChange(e.target.value)}
                                      label={t('settings.telegramCustomEmojiOpenLive')}
                                      helperText={t('settings.telegramCustomEmojiHint')}
                                      disabled={!notificationsEnabled}
                                    />
                                  )}
                                </form.Field>
                              </Grid>
                            </>
                          ) : null
                        }
                      </form.Subscribe>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.paid_media_view_star_count">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 25000 }}
                              value={field.state.value ?? 0}
                              onChange={(e) =>
                                field.handleChange(Math.max(0, Math.min(25000, Number(e.target.value) || 0)))
                              }
                              label={t('settings.paidMediaViewStars')}
                              helperText={t('settings.paidMediaViewStarsHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="notifications.paid_media_forward_star_count">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 25000 }}
                              value={field.state.value ?? 0}
                              onChange={(e) =>
                                field.handleChange(Math.max(0, Math.min(25000, Number(e.target.value) || 0)))
                              }
                              label={t('settings.paidMediaForwardStars')}
                              helperText={t('settings.paidMediaForwardStarsHint')}
                              disabled={!notificationsEnabled}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <form.Field name="general.notification_excluded_species">
                          {(field) => (
                            <FormControl fullWidth disabled={!notificationsEnabled}>
                              <InputLabel id="settings-exclude-species-label">{t('settings.excludeSpecies')}</InputLabel>
                              <Select
                                labelId="settings-exclude-species-label"
                                multiple
                                value={field.state.value || []}
                                onChange={(e) => field.handleChange(e.target.value as string[])}
                                label={t('settings.excludeSpecies')}
                                renderValue={(selected) => selected.join(', ')}
                              >
                                {(observedSpecies ?? []).map((species) => (
                                  <MenuItem key={species.id} value={species.name}>
                                    <Checkbox checked={(field.state.value || []).includes(species.name)} />
                                    <ListItemText
                                      primary={species.name}
                                      secondary={t('settings.foundCount', { count: species.count })}
                                    />
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          )}
                        </form.Field>
                      </Grid>
                    </>
                  )}
                </form.Subscribe>
              </Grid>
            </ServiceBlock>

            <ServiceBlock title={t('settings.serviceWebhook')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="webhook.url">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.webhookUrl')}
                        helperText={t('settings.webhookUrlHint')}
                        placeholder="https://maker.ifttt.com/trigger/bird_detected/with/key/xxx"
                      />
                    )}
                  </form.Field>
                </Grid>
              </Grid>
            </ServiceBlock>

            <ServiceBlock title={t('settings.serviceGallery')}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <form.Field name="gallery.enabled">
                    {(field) => (
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value ?? false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.galleryEnabled')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <form.Subscribe selector={(state) => state.values.gallery?.enabled}>
                  {(enabled) => (
                    <>
                      {enabled && (
                        <>
                          <Grid size={{ xs: 12 }}>
                            <form.Field name="gallery.upload_url">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  value={field.state.value ?? ''}
                                  onChange={(e) => field.handleChange(e.target.value)}
                                  label={t('settings.galleryUploadUrl')}
                                  helperText={t('settings.galleryUploadUrlHint')}
                                  placeholder="https://gallery.example.com/api/upload"
                                />
                              )}
                            </form.Field>
                          </Grid>
                          <Grid size={{ xs: 12, sm: 6 }}>
                            <form.Field name="gallery.min_confidence">
                              {(field) => (
                                <TextField
                                  fullWidth
                                  type="number"
                                  inputProps={{ min: 0, max: 1, step: 0.05 }}
                                  value={field.state.value ?? 0.5}
                                  onChange={(e) => field.handleChange(parseFloat(e.target.value) || 0.5)}
                                  label={t('settings.galleryMinConfidence')}
                                  helperText={t('settings.galleryMinConfidenceHint')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                          <Grid size={{ xs: 12 }}>
                            <form.Field name="gallery.only_manually_corrected">
                              {(field) => (
                                <FormControlLabel
                                  control={
                                    <Checkbox
                                      checked={field.state.value ?? false}
                                      onChange={(e) => field.handleChange(e.target.checked)}
                                    />
                                  }
                                  label={t('settings.galleryOnlyCorrected')}
                                />
                              )}
                            </form.Field>
                          </Grid>
                        </>
                      )}
                    </>
                  )}
                </form.Subscribe>
              </Grid>
            </ServiceBlock>

            <form.Subscribe selector={(state) => state.values.general?.enable_notifications}>
              {(notificationsEnabled) => (
                <Box sx={{ mt: 2 }}>
                  <WebPushSubscribeButton notificationsEnabled={!!notificationsEnabled} />
                </Box>
              )}
            </form.Subscribe>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* ========== 5. ПОГОДА ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionWeather')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              {t('settings.accordionWeather')}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionWeatherDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="weather.source">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-weather-source-label">{t('settings.weatherSource')}</InputLabel>
                      <Select
                        labelId="settings-weather-source-label"
                        value={field.state.value ?? 'openweather'}
                        label={t('settings.weatherSource')}
                        onChange={(e) => field.handleChange(e.target.value as 'openweather' | 'homeassistant')}
                      >
                        <MenuItem value="openweather">{t('settings.weatherOpenWeather')}</MenuItem>
                        <MenuItem value="homeassistant">{t('settings.weatherHomeAssistant')}</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <form.Subscribe selector={(state) => state.values.weather?.source}>
                {(source) => (
                  <>
                    {source !== 'homeassistant' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="secrets.openweather_api_key">
                            {(field) => (
                              <PasswordField
                                value={field.state.value ?? ''}
                                onChange={(v) => field.handleChange(v)}
                                label={t('settings.openWeatherApiKey')}
                                helperText={t('settings.weatherHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.zip">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange(e.target.value)}
                                label={t('settings.zip')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <Button fullWidth variant="outlined" onClick={handleZipLookup}>
                            {t('settings.zipLookup')}
                          </Button>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.latitude">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange((e.target.value ?? '').replace(',', '.'))}
                                label={t('settings.latitude')}
                                helperText={t('settings.latitudeHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.longitude">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange((e.target.value ?? '').replace(',', '.'))}
                                label={t('settings.longitude')}
                                helperText={t('settings.longitudeHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                    {source === 'homeassistant' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert severity="info" sx={{ mb: 2 }}>
                            {t('settings.weatherHaAlert')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="weather.ha_entity_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) => field.handleChange(e.target.value)}
                                label={t('settings.weatherHaEntity')}
                                placeholder="weather.home"
                                helperText={t('settings.weatherHaEntityHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                  </>
                )}
              </form.Subscribe>
            </Grid>
          </Box>
        </AccordionDetails>
      </Accordion>
    </>
  );
}

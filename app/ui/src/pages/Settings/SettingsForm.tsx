import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import { Settings, Species } from '../../types';
import { fetchCoordinatesByZip } from '../../api/api';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import FormHelperText from '@mui/material/FormHelperText';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

type CameraRow = { stream_name?: string; name?: string };

function CamerasListField({
  value,
  onChange,
}: {
  value: Array<{ id?: string; stream_name?: string; name?: string }> | undefined;
  onChange: (v: Array<{ id?: string; stream_name?: string; name?: string }>) => void;
}) {
  const rows: CameraRow[] = Array.isArray(value) && value.length > 0
    ? value.map((c) => ({
        stream_name: c.stream_name ?? c.id ?? '',
        name: c.name ?? c.id ?? c.stream_name ?? '',
      }))
    : [{ stream_name: '', name: '' }];

  const sync = (newRows: CameraRow[]) => {
    const arr = newRows.map((r) => ({
      id: (r.stream_name ?? '').trim() || undefined,
      stream_name: (r.stream_name ?? '').trim(),
      name: (r.name ?? '').trim() || (r.stream_name ?? '').trim(),
    }));
    onChange(arr);
  };

  const updateRow = (i: number, field: keyof CameraRow, val: string) => {
    const next = [...rows];
    if (!next[i]) next[i] = { stream_name: '', name: '' };
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([...rows, { stream_name: '', name: '' }]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(next.length ? next : [{ stream_name: '', name: '' }]);
  };

  const { t } = useTranslation();
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.streamNameHint')}
      </Typography>
      {rows.map((row, i) => (
        <Grid container key={i} spacing={1} sx={{ mb: 1 }} alignItems="center">
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              fullWidth
              size="small"
              value={row.stream_name ?? ''}
              onChange={(e) => updateRow(i, 'stream_name', e.target.value)}
              label={t('settings.streamName')}
              placeholder="BirdBox"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 5 }}>
            <TextField
              fullWidth
              size="small"
              value={row.name ?? ''}
              onChange={(e) => updateRow(i, 'name', e.target.value)}
              label={t('settings.cameraName')}
              placeholder={t('settings.cameraPlaceholder')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 1 }}>
            <Button
              size="small"
              color="error"
              onClick={() => removeRow(i)}
              disabled={rows.length <= 1}
            >
              −
            </Button>
          </Grid>
        </Grid>
      ))}
      <Button size="small" onClick={addRow} sx={{ mt: 0.5 }}>
        {t('settings.addCamera')}
      </Button>
    </Box>
  );
}

export const SettingsForm = ({
  currentSettings,
  birdFamilies,
  observedSpecies,
  onSubmit,
}: {
  currentSettings: Settings;
  birdFamilies: Partial<Species>[];
  observedSpecies: Species[];
  onSubmit: (settings: Settings) => void;
}) => {
  const { t } = useTranslation();
  const form = useForm<Settings>({
    defaultValues: currentSettings,
    onSubmit: ({ value }) => onSubmit(value),
  });

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

  const resolutions = [
    { label: t('settings.resolutionFullHD'), width: 1920, height: 1080 },
    { label: t('settings.resolutionHD'), width: 1280, height: 720 },
    { label: t('settings.resolutionVGA'), width: 640, height: 480 },
  ];

  return (
    <Box
      component="form"
      noValidate
      autoComplete="off"
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      {/* ========== 1. CONNECTION ========== */}
      <Typography variant="h5" gutterBottom sx={{ mt: 2 }}>
        {t('settings.section1')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section1Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.broker">
            {(field) => (
              <TextField
                fullWidth
                id={field.name}
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.mqttBroker')}
                placeholder="192.168.1.10"
                helperText={t('settings.mqttBrokerHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.port">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                value={field.state.value ?? 1883}
                onChange={(e) => field.handleChange(Number(e.target.value) || 1883)}
                label={t('settings.mqttPort')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.username">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.mqttUser')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.password">
            {(field) => (
              <TextField
                fullWidth
                type="password"
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.mqttPassword')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.frigate_topic">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? 'frigate/events'}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.frigateTopic')}
                placeholder="frigate/events"
                helperText={t('settings.frigateTopicHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.birdnet_topic">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? 'birdnet'}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.birdnetTopic')}
                placeholder="birdnet"
                helperText={t('settings.birdnetTopicHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="video.go2rtc_url">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.go2rtcUrlLabel')}
                placeholder="http://192.168.1.10:1984"
                helperText={t('settings.go2rtcUrlHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="video.go2rtc_username">
            {(field) => (
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.go2rtcUser')} />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="video.go2rtc_password">
            {(field) => (
              <TextField fullWidth type="password" value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.go2rtcPassword')} />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 2. CAMERAS ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section2')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section2Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="video.cameras">
            {(field) => (
              <CamerasListField
                value={field.state.value}
                onChange={field.handleChange}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 3. MOTION DETECTION ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section3')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section3Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="motion.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel>{t('settings.triggerLabel')}</InputLabel>
                <Select
                  value={(field.state.value === 'frigate' ? 'auto' : field.state.value) ?? 'auto'}
                  label={t('settings.triggerLabel')}
                  onChange={(e) => field.handleChange(e.target.value === 'auto' ? 'frigate' : e.target.value)}
                >
                  <MenuItem value="auto">{t('settings.triggerFrigate')}</MenuItem>
                  <MenuItem value="opencv">{t('settings.triggerOpencv')}</MenuItem>
                  <MenuItem value="mqtt">{t('settings.triggerMqtt')}</MenuItem>
                  <MenuItem value="esphome">{t('settings.triggerEsp')}</MenuItem>
                </Select>
                <FormHelperText>
                  {t('settings.triggerHint')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.motion?.source}>
          {(source) => (
            <>
              {source === 'mqtt' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.mqttSensorAlert')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="motion.mqtt_topic">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.mqttTopic')}
                          placeholder="stat/bird_pir/STATE"
                          helperText={t('settings.mqttTopicHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {source === 'esphome' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.esphomeAlert')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="motion.esphome_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.esphomeUrl')}
                          placeholder="http://192.168.1.50"
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="motion.esphome_sensor_id">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.sensorId')}
                          placeholder="bird_pir"
                          helperText={t('settings.sensorIdHint')}
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

      <Divider sx={{ my: 4 }} />

      {/* ========== 4. FEED RELAY ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section4')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section4Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="feed.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel>{t('settings.feedType')}</InputLabel>
                <Select
                  value={field.state.value ?? 'none'}
                  label={t('settings.feedType')}
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="none">{t('settings.feedNone')}</MenuItem>
                  <MenuItem value="mqtt">{t('settings.feedMqtt')}</MenuItem>
                  <MenuItem value="esphome">{t('settings.feedEsp')}</MenuItem>
                </Select>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.feed?.source}>
          {(source) => (
            <>
              {source === 'mqtt' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.feedMqttHint')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.mqtt_topic">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.relayTopic')}
                          placeholder="cmnd/bird_feeder/Power"
                          helperText={t('settings.relayTopicHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {source === 'esphome' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.esphomeFeedHint')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_type">
                      {(field) => (
                        <FormControl fullWidth>
                          <InputLabel>{t('settings.switchType')}</InputLabel>
                          <Select
                            value={field.state.value ?? 'switch'}
                            label={t('settings.switchType')}
                            onChange={(e) => field.handleChange(e.target.value)}
                          >
                            <MenuItem value="switch">{t('settings.switchTypeSwitch')}</MenuItem>
                            <MenuItem value="button">{t('settings.switchTypeButton')}</MenuItem>
                          </Select>
                        </FormControl>
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.deviceUrl')}
                          placeholder="http://192.168.1.50"
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_switch_id">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.switchId')}
                          placeholder="bird_feeder"
                          helperText={t('settings.switchIdHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {(source === 'mqtt' || source === 'esphome') && (
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="feed.duration_seconds">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 1, max: 30 }}
                        value={field.state.value ?? 3}
                        onChange={(e) => field.handleChange(Number(e.target.value) || 3)}
                        label={t('settings.relaySeconds')}
                        helperText={t('settings.relaySecondsHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              )}
            </>
          )}
        </form.Subscribe>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 5. УВЕДОМЛЕНИЯ (Telegram) ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section5')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section5Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 4 }}>
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
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="notifications.telegram_bot_token">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="password"
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.telegramBotToken')}
                      helperText={t('settings.telegramBotTokenHint')}
                      disabled={!notificationsEnabled}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
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
              <form.Subscribe
                selector={(state) => state.values.notifications?.use_custom_emoji}
              >
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
                        field.handleChange(
                          Math.max(0, Math.min(25000, Number(e.target.value) || 0))
                        )
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
                        field.handleChange(
                          Math.max(0, Math.min(25000, Number(e.target.value) || 0))
                        )
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
                      <InputLabel>{t('settings.excludeSpecies')}</InputLabel>
                      <Select
                        multiple
                        value={field.state.value || []}
                        onChange={(e) => field.handleChange(e.target.value as string[])}
                        label={t('settings.excludeSpecies')}
                        renderValue={(selected) => selected.join(', ')}
                      >
                        {(observedSpecies ?? []).map((species) => (
                          <MenuItem key={species.id} value={species.name}>
                            <Checkbox checked={(field.state.value || []).includes(species.name)} />
                            <ListItemText primary={species.name} secondary={t('settings.foundCount', { count: species.count })} />
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

      <Divider sx={{ my: 4 }} />

      {/* ========== 6. ПОГОДА ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section6')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section6Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="weather.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel>{t('settings.weatherSource')}</InputLabel>
                <Select
                  value={field.state.value ?? 'openweather'}
                  label={t('settings.weatherSource')}
                  onChange={(e) => field.handleChange(e.target.value)}
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
                        <TextField
                          fullWidth
                          type="password"
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.openWeatherApiKey')}
                          helperText={t('settings.weatherHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <form.Field name="secrets.zip">
                      {(field) => (
                        <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.zip')} />
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
                    <form.Field name="weather.ha_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.weatherHaUrl')}
                          placeholder="http://homeassistant:8123"
                          helperText={t('settings.weatherHaUrlHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
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
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="weather.ha_token">
                      {(field) => (
                        <TextField
                          fullWidth
                          type="password"
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.weatherHaToken')}
                          placeholder={t('settings.weatherHaTokenPlaceholder')}
                          helperText={t('settings.weatherHaTokenHint')}
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

      <Divider sx={{ my: 4 }} />

      {/* ========== 7. БЕЗОПАСНОСТЬ ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section7')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section7Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="general.settings_password">
            {(field) => (
              <TextField
                fullWidth
                type="password"
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.settingsPassword')}
                placeholder={t('settings.settingsPasswordPlaceholder')}
                helperText={t('settings.settingsPasswordHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 8. MCP ========== */}
      <Typography variant="h5" gutterBottom>
        {t('settings.section8')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.section8Desc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="mcp.enabled">
            {(field) => (
              <>
                <FormControlLabel
                  control={
                    <Switch
                      checked={field.state.value ?? false}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.mcpEnabled')}
                />
                <FormHelperText>{t('settings.mcpHint')}</FormHelperText>
              </>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mcp.token">
            {(field) => (
              <TextField
                fullWidth
                type="password"
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.mcpToken')}
                placeholder={t('settings.mcpTokenPlaceholder')}
                helperText={t('settings.mcpTokenHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== РАСШИРЕННЫЕ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>{t('settings.advanced')}</AccordionSummary>
        <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.advancedDesc')}
            </Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.max_record_seconds">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 60}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.maxRecordSeconds')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.max_inactive_seconds">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 10}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.inactiveSeconds')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.min_track_duration">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 1}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.minTrackDuration')}
                    helperText={t('settings.minTrackDurationHelp')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.spectrogram_px_per_sec">
                {(field) => (
                  <TextField
                    fullWidth
                    type="number"
                    value={field.state.value ?? 200}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    label={t('settings.spectrogramDetail')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="motion.frigate_label_exclude">
                {(field) => (
                  <TextField
                    fullWidth
                    value={(field.state.value || []).join(', ')}
                    onChange={(e) =>
                      field.handleChange(
                        (e.target.value || '')
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      )
                    }
                    label={t('settings.frigateLabelExclude')}
                    placeholder="cat, dog"
                    helperText={t('settings.frigateLabelExcludeHint')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.tracker">
                {(field) => (
                  <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label={t('settings.objectTracker')} />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="processor.included_bird_families">
                {(field) => (
                  <FormControl fullWidth>
                    <InputLabel>{t('settings.birdFamilies')}</InputLabel>
                    <Select
                      multiple
                      value={field.state.value || []}
                      onChange={(e) => field.handleChange(e.target.value as string[])}
                      label={t('settings.birdFamilies')}
                      renderValue={(selected) => selected.join(', ')}
                    >
                      {(birdFamilies ?? []).map((family) => (
                        <MenuItem key={family.id} value={family.name}>
                          <Checkbox checked={(field.state.value || []).includes(family.name as string)} />
                          <ListItemText primary={family.name} />
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="video.video_width">
                {(widthField) => (
                  <form.Field name="video.video_height">
                    {(heightField) => {
                      const w = widthField.state.value;
                      const h = heightField.state.value;
                      const sel = resolutions.find((r) => r.width === w && r.height === h);
                      return (
                        <FormControl fullWidth>
                          <InputLabel>{t('settings.resolution')}</InputLabel>
                          <Select
                            value={sel ? `${sel.width}x${sel.height}` : ''}
                            label={t('settings.resolution')}
                            onChange={(e) => {
                              const [a, b] = (e.target.value as string).split('x').map(Number);
                              widthField.handleChange(a);
                              heightField.handleChange(b);
                            }}
                          >
                            {resolutions.map((r) => (
                              <MenuItem key={r.label} value={`${r.width}x${r.height}`}>
                                {r.label}
                              </MenuItem>
                            ))}
                          </Select>
                          <FormHelperText>
                            {t('settings.resolutionHint')}
                          </FormHelperText>
                        </FormControl>
                      );
                    }}
                  </form.Field>
                )}
              </form.Field>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      <Button variant="contained" fullWidth type="submit" sx={{ mt: 4 }}>
        {t('settings.save')}
      </Button>
    </Box>
  );
};

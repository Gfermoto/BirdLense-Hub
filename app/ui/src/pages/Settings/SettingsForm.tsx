import { useState, useEffect } from 'react';
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

type CameraRow = { stream_name?: string; feeder?: string; name?: string };

function CamerasListField({
  value,
  onChange,
}: {
  value: Array<{ id?: string; stream_name?: string; name?: string; feeder?: string }> | undefined;
  onChange: (v: Array<{ id?: string; stream_name?: string; name?: string; feeder?: string }>) => void;
}) {
  const rows: CameraRow[] = Array.isArray(value) && value.length > 0
    ? value.map((c) => ({
        stream_name: c.stream_name ?? c.id ?? '',
        feeder: c.feeder ?? '',
        name: c.name ?? c.id ?? c.stream_name ?? '',
      }))
    : [{ stream_name: '', feeder: '', name: '' }];

  const sync = (newRows: CameraRow[]) => {
    const filtered = newRows.filter((r) => (r.stream_name ?? '').trim());
    const arr = filtered.length
      ? filtered.map((r) => ({
          id: (r.stream_name ?? '').trim(),
          stream_name: (r.stream_name ?? '').trim(),
          name: (r.name ?? '').trim() || (r.stream_name ?? '').trim(),
          feeder: (r.feeder ?? '').trim() || undefined,
        }))
      : [];
    onChange(arr);
  };

  const updateRow = (i: number, field: keyof CameraRow, val: string) => {
    const next = [...rows];
    if (!next[i]) next[i] = { stream_name: '', feeder: '', name: '' };
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([...rows, { stream_name: '', feeder: '', name: '' }]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(next.length ? next : [{ stream_name: '', feeder: '', name: '' }]);
  };

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Имя потока — из Go2RTC. Номер кормушки и название — для подписи.
      </Typography>
      {rows.map((row, i) => (
        <Grid container key={i} spacing={1} sx={{ mb: 1 }} alignItems="center">
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              size="small"
              value={row.stream_name ?? ''}
              onChange={(e) => updateRow(i, 'stream_name', e.target.value)}
              label="Имя потока (Go2RTC)"
              placeholder="BirdBox"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              fullWidth
              size="small"
              value={row.feeder ?? ''}
              onChange={(e) => updateRow(i, 'feeder', e.target.value)}
              label="Номер кормушки"
              placeholder="1"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              size="small"
              value={row.name ?? ''}
              onChange={(e) => updateRow(i, 'name', e.target.value)}
              label="Название камеры"
              placeholder="Кормушка"
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
        + Добавить камеру
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
      alert('Failed to fetch coordinates. Please check the ZIP code.');
    }
  };

  const resolutions = [
    { label: 'FullHD (1920x1080)', width: 1920, height: 1080 },
    { label: 'HD (1280x720)', width: 1280, height: 720 },
    { label: 'VGA (640x480)', width: 640, height: 480 },
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
      {/* ========== 1. ПОДКЛЮЧЕНИЕ ========== */}
      <Typography variant="h5" gutterBottom sx={{ mt: 2 }}>
        1. Подключение
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        MQTT и Go2RTC — основа для камер, детекции движения и реле.
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
                label="MQTT Broker"
                placeholder="192.168.1.10"
                helperText="IP или домен брокера (Frigate, Tasmota, датчики)"
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
                label="MQTT порт"
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
                label="MQTT логин"
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
                label="MQTT пароль"
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
                label="Frigate топик"
                placeholder="frigate/events"
                helperText="События Frigate для слияния с YOLO"
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.birdnet_topic">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? 'birdnet/sightings'}
                onChange={(e) => field.handleChange(e.target.value)}
                label="BirdNET топик"
                placeholder="birdnet/sightings"
                helperText="BirdNET-Pi. BirdNET-Go — ниже."
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="mqtt.birdnet_go_topic">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label="BirdNET-Go топик (опц.)"
                placeholder="birdnet/detections"
                helperText="Если есть BirdNET-Go — подписка на оба"
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
                label="Go2RTC URL"
                placeholder="http://frigate:1984"
                helperText="В Docker с Frigate: http://frigate:1984. RTSP порт 8554."
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="video.go2rtc_username">
            {(field) => (
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="Go2RTC логин" />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="video.go2rtc_password">
            {(field) => (
              <TextField fullWidth type="password" value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="Go2RTC пароль" />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 2. КАМЕРЫ ========== */}
      <Typography variant="h5" gutterBottom>
        2. Камеры
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Имена камер из Go2RTC/Frigate. Топики Frigate (frigate/events) и BirdNET (birdnet/sightings) — стандартные. Фильтр камер берётся из списка ниже.
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
        <Grid size={{ xs: 12 }}>
          <form.Field name="video.stream_name">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label="Stream name (если одна камера)"
                placeholder="bird_cam"
                helperText="Используется, если список камер выше пуст."
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== 3. ДЕТЕКЦИЯ ДВИЖЕНИЯ ========== */}
      <Typography variant="h5" gutterBottom>
        3. Детекция движения
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Что запускает запись: анализ кадров, события Frigate или внешний датчик (MQTT/ESPHome).
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="motion.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel>Источник движения</InputLabel>
                <Select
                  value={field.state.value ?? 'opencv'}
                  label="Источник движения"
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="opencv">OpenCV — анализ каждого кадра</MenuItem>
                  <MenuItem value="frigate">Frigate — события по MQTT (bird, Bird)</MenuItem>
                  <MenuItem value="mqtt">MQTT — бинарный датчик (Tasmota PIR, Shelly)</MenuItem>
                  <MenuItem value="esphome">ESPHome — бинарный датчик по IP</MenuItem>
                </Select>
                <FormHelperText>
                  OpenCV = всегда включён. Frigate = нужен MQTT. MQTT/ESPHome = как реле подкормки.
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.motion?.source}>
          {(source) => (
            <>
              {source === 'frigate' && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    Frigate публикует события в frigate/events. Фильтр камер — из списка камер выше.
                  </Alert>
                </Grid>
              )}
              {source === 'mqtt' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      <strong>MQTT датчик:</strong> подписка на топик. При ON/1 — запись. Tasmota: stat/ИМЯ/STATE или stat/ИМЯ/PIR.
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12 }}>
                    <form.Field name="motion.mqtt_topic">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label="MQTT топик датчика"
                          placeholder="stat/bird_pir/STATE"
                          helperText="Топик, где публикуется ON при движении"
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
                      <strong>ESPHome:</strong> бинарный датчик (PIR, door). Нужен web_server в конфиге ESPHome.
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="motion.esphome_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label="Адрес ESPHome"
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
                          label="ID датчика"
                          placeholder="bird_pir"
                          helperText="id из YAML: binary_sensor: - id: bird_pir"
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

      {/* ========== 4. РЕЛЕ ПОДКОРМКИ ========== */}
      <Typography variant="h5" gutterBottom>
        4. Реле подкормки
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Кнопка «Выдать корм» включает реле на N секунд. Tasmota или ESPHome — как датчик движения выше.
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="feed.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel>Тип устройства</InputLabel>
                <Select
                  value={field.state.value ?? 'none'}
                  label="Тип устройства"
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="none">Выключено</MenuItem>
                  <MenuItem value="mqtt">Tasmota (MQTT)</MenuItem>
                  <MenuItem value="esphome">ESPHome (по IP)</MenuItem>
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
                      MQTT брокер — в блоке «Подключение». Ниже только топик реле.
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.mqtt_topic">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label="MQTT топик реле"
                          placeholder="cmnd/bird_feeder/Power"
                          helperText="Tasmota: cmnd/ИМЯ/Power"
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
                      IP и имя из конфига ESPHome. Switch — реле (turn_on/turn_off). Button — кнопка (press, длительность на устройстве).
                      <strong> Важно:</strong> в YAML ESPHome должен быть <code>web_server:</code>, иначе REST API (404) не работает.
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_type">
                      {(field) => (
                        <FormControl fullWidth>
                          <InputLabel>Тип: switch или button</InputLabel>
                          <Select
                            value={field.state.value ?? 'switch'}
                            label="Тип: switch или button"
                            onChange={(e) => field.handleChange(e.target.value)}
                          >
                            <MenuItem value="switch">Switch (реле)</MenuItem>
                            <MenuItem value="button">Button (кнопка)</MenuItem>
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
                          label="Адрес устройства"
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
                          label="ID switch или button"
                          placeholder="bird_feeder"
                          helperText="ID из YAML: switch: - id: bird_feeder. Должен совпадать с object_id."
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
                        label="Секунд работы реле"
                        helperText="Длительность включения при нажатии «Выдать корм»"
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

      {/* ========== 5. УВЕДОМЛЕНИЯ, ПОГОДА, ЛОКАЦИЯ ========== */}
      <Typography variant="h5" gutterBottom>
        5. Уведомления и погода
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <form.Field name="general.enable_notifications">
            {(field) => (
              <>
                <FormControlLabel
                  control={
                    <Switch
                      checked={field.state.value}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label="Push-уведомления"
                />
                <FormHelperText>ntfy, топик birdlense, порт 8086</FormHelperText>
              </>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 8 }}>
          <form.Subscribe selector={(state) => [state.values.general?.enable_notifications]}>
            {([notificationsEnabled]) => (
              <form.Field name="general.notification_excluded_species">
                {(field) => (
                  <FormControl fullWidth disabled={!notificationsEnabled}>
                    <InputLabel>Исключить из уведомлений</InputLabel>
                    <Select
                      multiple
                      value={field.state.value || []}
                      onChange={(e) => field.handleChange(e.target.value as string[])}
                      label="Исключить из уведомлений"
                      renderValue={(selected) => selected.join(', ')}
                    >
                      {(observedSpecies ?? []).map((species) => (
                        <MenuItem key={species.id} value={species.name}>
                          <Checkbox checked={(field.state.value || []).includes(species.name)} />
                          <ListItemText primary={species.name} secondary={`Найдено ${species.count} раз`} />
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
              </form.Field>
            )}
          </form.Subscribe>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="secrets.openweather_api_key">
            {(field) => (
              <TextField
                fullWidth
                type="password"
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label="OpenWeather API Key"
                helperText="Погода: Overview, Timeline, детали видео. Сохраняется с каждой записью. Координаты — ниже."
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 6 }}>
          <form.Field name="secrets.zip">
            {(field) => (
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="ZIP" />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 6 }}>
          <Button fullWidth variant="outlined" onClick={handleZipLookup}>
            ZIP → координаты
          </Button>
        </Grid>
        <Grid size={{ xs: 6 }}>
          <form.Field name="secrets.latitude">
            {(field) => (
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="Широта" />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 6 }}>
          <form.Field name="secrets.longitude">
            {(field) => (
              <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="Долгота" />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Divider sx={{ my: 4 }} />

      {/* ========== РАСШИРЕННЫЕ ========== */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>Расширенные настройки</AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            YOLO (детекция птиц) используется в processor — модели в конфиге processor.models. Здесь только параметры записи и фильтры.
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
                    label="Макс. секунд записи"
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
                    label="Секунд без активности"
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
                    label="Детализация спектрограммы"
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <form.Field name="processor.tracker">
                {(field) => (
                  <TextField fullWidth value={field.state.value ?? ''} onChange={(e) => field.handleChange(e.target.value)} label="Object Tracker" />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="processor.included_bird_families">
                {(field) => (
                  <FormControl fullWidth>
                    <InputLabel>Семейства птиц</InputLabel>
                    <Select
                      multiple
                      value={field.state.value || []}
                      onChange={(e) => field.handleChange(e.target.value as string[])}
                      label="Семейства птиц"
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
                          <InputLabel>Разрешение записи</InputLabel>
                          <Select
                            value={sel ? `${sel.width}x${sel.height}` : ''}
                            label="Разрешение записи"
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
                            Размер кадра при захвате и записи видео. Влияет на качество записи и нагрузку.
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
        Сохранить настройки
      </Button>
    </Box>
  );
};

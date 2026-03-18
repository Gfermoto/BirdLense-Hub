# Публичная галерея — формат загрузки

Opt-in: при `gallery.enabled=true` и `gallery.upload_url` BirdLense Hub загружает лучшие кадры детекций на указанный URL.

## Формат запроса

`POST` на `gallery.upload_url` с `multipart/form-data`:

| Поле | Тип | Описание |
|------|-----|----------|
| `image` | file (JPEG) | Crop птицы по bbox из трека |
| `species` | string | Название вида (Common name) |
| `confidence` | string | Confidence 0–1 |
| `timestamp` | string | ISO 8601 (UTC) |
| `detection_id` | string | ID VideoSpecies |
| `video_id` | string | ID Video |
| `latitude` | string | Координата из настроек |
| `longitude` | string | Координата из настроек |

## Фильтры

- `gallery.min_confidence` — только детекции с confidence ≥ порога (по умолчанию 0.5)
- `gallery.only_manually_corrected` — только проверенные вручную (по умолчанию false)

## Пример приёмника

Минимальный Flask-эндпоинт:

```python
@app.route('/api/upload', methods=['POST'])
def upload():
    image = request.files.get('image')
    species = request.form.get('species')
    confidence = request.form.get('confidence')
    timestamp = request.form.get('timestamp')
    # Сохранить image, записать в БД
    return {'ok': True}, 200
```

## Безопасность

- Загрузка идёт в фоне (не блокирует процессор)
- При ошибке (timeout, 4xx/5xx) — логируется, повтор не выполняется
- Рекомендуется: API key в заголовке, rate limit на стороне приёмника

# Ревью изменений: только кропы в датасете

Полный ревью реализации и связанных компонентов.

---

## 1. Реализованные изменения

### P0: Исправление fallback на full frame ✅

**Файл:** `app/web/services/detection_crop_service.py`

- **Было:** При любой ошибке кропа (невалидный bbox, cv2 fail, exception) возвращался полный кадр → сохранялся в датасет.
- **Стало:** Возвращается `None` при любой ошибке. Вызывающий код не сохраняет.
- **Риск:** Нет. `extract_detection_frame_cropped` используется только в dataset_export_service для dataset.

### P1: Режим «Пересобрать» в ретроэкспорте ✅

**API:** `POST /api/ui/dataset/retro-export` с `rebuild: true`

- Удаляет все crops за период (по video_id в имени файла).
- Заново извлекает только кропы из VideoSpecies.
- Требует `start_date` и `end_date`.
- **UI:** Чекбокс «Пересобрать за период» + подтверждение.

### P2: Кнопка «Очистить датасет» ✅

**API:** `POST /api/ui/dataset/clean`

- **remove_fullframe:** по эвристике (≥800×600 px, aspect 16:9 или 4:3).
- **remove_orphaned:** опционально — файлы без VideoSpecies (video_id, track_id). По умолчанию выключено (риск для processor-файлов).
- **dry_run:** предпросмотр без удаления.

### P3: Валидация при экспорте ✅

- **build_dataset_zip:** при добавлении в ZIP проверяет размер каждого файла.
- Подозрительные full-frame исключаются из архива.
- **dataset_info.json:** поле `excluded_fullframe` — количество исключённых.

---

## 2. Критический анализ

### 2.1 Эвристика full-frame

**Пороги:** 480000 px (800×600), aspect 16:9 ±15%, 4:3 ±15%.

**Риски:**
- Ложное срабатывание: большой кроп птицы (например, 900×600) может попасть под 4:3. Митигация: порог 800×600 — большинство кропов меньше.
- Пропуск: маленький full-frame (например, 640×480) не будет удалён. 640×480 = 307200 < 480000. Митигация: консервация — лучше оставить сомнительный, чем удалить кроп.

**Рекомендация:** При необходимости — настраиваемые пороги в конфиге.

### 2.2 Осиротевшие файлы

**Текущее:** Опция `remove_orphaned` по умолчанию `false` в UI. При `true` — удаляются файлы, для которых (video_id, track_id) нет в VideoSpecies.

**Риск:** Processor сохраняет файлы до создания VideoSpecies через API. При быстрой очистке после записи можно удалить свежие файлы. Митигация: не включать в UI по умолчанию; пользователь включает осознанно.

### 2.3 Rebuild: порядок операций

1. Получить video_ids за период.
2. Удалить файлы с этими video_id.
3. Итерировать VideoSpecies за период.
4. Для каждого: извлечь кроп (если bbox есть) и сохранить.

**Корректность:** При rebuild мы не проверяем `if os.path.isfile(out_path)` — файлы уже удалены. Логика верна.

### 2.4 Экспорт: excluded_fullframe

**Поведение:** `excluded_fullframe` добавляется в `info` и в `dataset_info.json` внутри ZIP. Пользователь видит при распаковке.

**Альтернатива:** Отдельный API `GET /api/ui/dataset/export/preview` → `{total, by_species, excluded_fullframe}`. Для будущего.

---

## 3. Согласованность с проектом

### 3.1 Семантика операций (сводка)

| Действие | Описание | Результат |
|----------|----------|-----------|
| **Ретроэкспорт** | Извлечь кропы из видео за период, добавить | Датасет дополнен |
| **Ретроэкспорт + Пересобрать** | Удалить crops за период, заново извлечь | Только кропы за период |
| **Очистить датасет** | Удалить full-frame по эвристике | Меньше мусора |
| **Экспорт ZIP** | Упаковать train/val, исключить full-frame | Архив для обучения |

### 3.2 Документация

- `DATASET_CROPS_ONLY_CONCILIUM.md` — обновлён (план внедрения отмечен как выполненный).
- `DATASET_COLLECTION_BRAINSTORM.md` — сценарий D «Очистка» отмечен как реализованный.

### 3.3 UX (по research)

- **Подтверждение перед деструктивными действиями:** rebuild и clean — есть.
- **Прозрачность:** success-сообщения с числами (saved, deleted, excluded).
- **Единый workflow:** все операции в блоке «Датасет» на странице Library.

---

## 4. Рекомендации на будущее

1. **Предпросмотр экспорта:** API `GET /dataset/export/preview` — total, by_species, excluded_fullframe.
2. **Предпросмотр очистки:** Кнопка «Проверить» с dry_run для clean — уже есть в API, можно добавить в UI.
3. **Настраиваемые пороги:** MIN_PIXELS_FULLFRAME, ASPECT_TOLERANCE в config.
4. **Дашборд датасета:** количество crops по виду, доля manually_corrected — см. DATASET_COLLECTION_BRAINSTORM.

---

## 5. Проверка файлов

| Файл | Изменения |
|------|-----------|
| `detection_crop_service.py` | extract_detection_frame_cropped: return None при ошибке |
| `dataset_export_service.py` | _get_image_dimensions, _is_likely_fullframe, clean_dataset, _delete_dataset_crops_for_video_ids, rebuild в retro_export, excluded_fullframe в build_dataset_zip |
| `ui_routes.py` | rebuild в retro_export, clean_dataset_route |
| `api.tsx` | rebuild, cleanDataset |
| `RecordingsAndDataset.tsx` | rebuild checkbox, clean button, success handling |
| `locales/*.json` | Новые ключи |
| `docs/*.md` | Обновления |

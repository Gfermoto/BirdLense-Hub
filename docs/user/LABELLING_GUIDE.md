# Labelling Guide

## Открыть `/labelling`

1. Откройте UI Hub.
2. Перейдите на `http://<host>:8085/labelling`.
3. Выберите язык `RU/EN/ZH` в верхней панели.

## Единая стратегия интерфейса

- `/labelling` — только проверка геометрии (рамка соответствует птице: Да/Нет).
- `/recordings -> Video Details` — семантика записи: `Вид + Профиль птицы + Поведение`.
- Разделение ответственности жёсткое: геометрия не смешивается с ReID/поведением.

## Сценарий Geometry-Only

1. Открывается кейс с видео/кадром и рамкой детекции.
2. Цвет рамки показывает статус:
   - зелёный — подтверждено,
   - жёлтый — на проверке,
   - красный — отклонено.
3. Если всё верно: `Enter` / `Space` (`Approve and next`).
4. Если ошибка: `Backspace` (`Reject and next`).
5. Для контекста всегда видны: `Вид`, `Кличка`, `Поведение` (read-only), проставленные в карточке видео.
6. Если рамка/медиа недоступны, UI покажет явную заглушку (`Медиа недоступно`) и кнопку `Пропустить`.

## Горячие клавиши

- `Enter` / `Space` — подтвердить и перейти к следующему кейсу.
- `Backspace` — отклонить и перейти к следующему кейсу.
- `ArrowLeft` / `ArrowRight` — предыдущий / следующий кейс.

## Где менять семантику

- Откройте нужный ролик: `/recordings` → `Video Details`.
- Блок вида позволяет:
  - исправить `Species`,
  - выбрать или создать `Bird Profile` (Global ReID),
  - выбрать `Behavior` из словаря.
- После сохранения вернитесь в `/labelling` для быстрой проверки геометрии.

## Фильтры

- `Status`: все / на проверке / готово / ошибка.
- `Workflow`: только новые, только ошибки детекции.
- `Camera`: фильтр по камере.

## If Queue Is Empty

```bash
# automatic miner
curl -X POST "http://<host>:8085/api/ui/labelling/cases/mine" -H "Content-Type: application/json" --cookie "<session_cookie>"
```

или заполнение из текущей БД:

```bash
cd /path/to/BirdLense
python3 scripts/seed_labelling_queue.py --db app/data/db/birdlense.db
```

на production:

```bash
cd /root/BirdLense
python3 scripts/seed_labelling_queue.py --db app/data/db/birdlense.db --max-video-cases 150 --max-runtime-cases 150
```

## Экспертная очередь (semantic review)

- Кнопка `Flag Semantic Error` на `/labelling` отправляет кейс в очередь эксперта.
- Откройте очередь эксперта: `/timeline?review=1&queue=expert`.
- Эксперт подтверждает или исправляет семантику в `Video Details` (вид, профиль, поведение).

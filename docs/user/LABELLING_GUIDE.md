# Labelling Guide

## Открыть `/labelling`

1. Откройте UI Hub.
2. Перейдите на `http://<host>:8085/labelling`.
3. Выберите язык `RU/EN` в верхней панели.

## Единая стратегия интерфейса

- `/labelling` — профессиональная очередь разметки для обучения модели (массовая работа).
- `/timeline` / карточки визитов — быстрые исправления "здесь и сейчас" (только коррекция вида через страницу записи).
- В `/labelling` доступен полный single-pass цикл: выбрать объект, подтвердить/исправить, перейти дальше.

## Новый сценарий (Single-Pass)

1. Открывается кейс с видео/кадром и рамкой детекции.
2. Цвет рамки показывает статус:
   - зелёный — подтверждено,
   - жёлтый — на проверке,
   - красный — отклонено.
3. Если всё верно: `Enter` / `Space` (`Approve and next`).
4. Если ошибка: `Backspace` (`Reject and next`).
5. Для правки выбранного объекта:
   - кликните по рамке,
   - выберите `Species` и `Behavior` в контекстной панели,
   - нажмите `Approve all`.
6. Если рамка/медиа недоступны, UI покажет явную заглушку (`Нет данных для отображения`), а не пустой экран.

## Горячие клавиши

- `Enter` / `Space` — подтвердить и перейти к следующему кейсу.
- `Backspace` — отклонить и перейти к следующему кейсу.
- `ArrowLeft` / `ArrowRight` — предыдущий / следующий кейс.
- `1` / `2` / `3` — быстрый выбор вида из топ-3 кандидатов.
- `B` — переключение поведения.

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

## Main vs Shadow

- `Main` — текущее прод-решение.
- `Shadow` — фоновый кандидат Behavior v2 (без влияния на прод-логику).
- Цель: сверять прогнозы и собирать чистую обратную связь оператора.

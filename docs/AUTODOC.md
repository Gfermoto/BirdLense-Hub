# Автодокументация BirdLense

Генерация API-документации из кода и проверка покрытия docstrings.

## Команды

```bash
# Вся документация (Python + UI)
make docs

# Только Python (web + processor)
make docs-python

# Только UI (TypeDoc)
make docs-ui

# Проверка docstrings (interrogate)
make docs-check
```

## Python (pdoc + interrogate)

- **pdoc** — генерирует HTML из docstrings и типов. Результат: `docs/api/`
- **interrogate** — проверяет покрытие docstrings. Порог: 80% (настраивается)

Запуск в Docker (есть все зависимости):

```bash
cd app
make docs-python
```

Локально (без Docker, с venv):

```bash
python -m venv .venv && . .venv/bin/activate
pip install pdoc interrogate -r app/web/requirements.txt
cd app/web && PYTHONPATH=/app python -m pdoc app util config models routes services -o ../../docs/api
cd app/processor/src && PYTHONPATH=. python -m pdoc frame_processor detection_strategy ... -o ../../docs/api/processor
```

## UI (TypeDoc)

- **TypeDoc** — документация из TypeScript/React. Результат: `docs/ui/`

```bash
cd app/ui
npm run docs
```

## Стиль docstrings (Python)

Краткие однострочные — без Args/Returns для простых функций:

```python
def is_blurry(self, image: np.ndarray) -> Tuple[bool, float]:
    """Лапласиан: выше variance — резче. (is_blur, variance)."""
```

Для сложных — одна строка + при необходимости уточнение:

```python
def process_detections(self, video: Video, detections: List[Dict]) -> List[VideoSpecies]:
    """Обработка детекций видео, создание визитов и VideoSpecies."""
```

## OpenAPI

Спека: `app/web/openapi.yaml`. Меняется вручную при добавлении эндпоинтов. MCP использует её для типизации.

## Автокомментирование (для AI/IDE)

При добавлении нового кода:

1. **Python** — краткий docstring на русском, без Args/Returns для простых функций
2. **TypeScript** — JSDoc `@param` только для неочевидных параметров
3. Комментарии — только для неочевидной логики, не для `# Create variable` и т.п.

## См. также

- [README.md](./README.md) — навигация по документации
- [API.md](./API.md) — краткое описание эндпоинтов

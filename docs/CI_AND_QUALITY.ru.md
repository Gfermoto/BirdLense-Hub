# CI и политика качества кода

[English](./CI_AND_QUALITY.md)

Кратко: что гоняется в GitHub Actions, как повторить проверки локально, как расширять пороги без ломки основного зелёного пайплайна.

## Сводка по workflow

| Workflow / job | Назначение |
|----------------|------------|
| **CI → python-security** | `bandit` по `web/` + `processor/src/`; `pip-audit` по обоим `requirements.txt`. |
| **CI → openapi-contract** | `ruff check` + **`ruff format --check`** по `web/` + `processor/src/`; скрипт версии доков; узкие pytest-наборы. |
| **CI → ui-build** | `npm ci`, `npm run lint`, `npm run build` в `app/ui`. |
| **CI → docs** | MkDocs strict, скрипт покрытия Settings UI, проверка версии. |
| **CI → docker-tests** | Сборка образа; тесты processor + web; Playwright smoke; аудит карточек. |

Источник: `.github/workflows/ci-pr.yml`.

## Ruff

- **Конфиг:** `app/pyproject.toml` (`[tool.ruff]`, длина строки 120, Python 3.11).
- **Линт:** `ruff check web/ processor/src/` — обязателен в CI.
- **Формат:** `ruff format web/ processor/src/` — в CI проверяется через `--check`. Локально перед пушем:
  ```bash
  cd app && docker compose run --rm -v "$(pwd)":/app birdlense \
    bash -c 'pip install ruff==0.9.2 && ruff format web/ processor/src/'
  ```
- **Исключения:** в `processor/src/main.py` порядок импорта намеренный (инициализация OpenCV до bootstrap); для этого файла в `pyproject.toml` отключён `E402`.

## pip-audit

- Запускается в **python-security** по обоим файлам зависимостей.
- Игнор `PYSEC-2022-42969` (транзитивный `py` из dev/docs) зафиксирован комментарием в workflow.

## npm audit

- Раз в неделю / вручную: `.github/workflows/npm-audit-scheduled.yml` (политика в комментариях workflow; [#284](https://github.com/Gfermoto/BirdLense-Hub/issues/284)). Не входит в обязательные проверки PR.

## OpenAPI → TypeScript (впереди)

- Спека: `app/web/openapi.yaml`. Контрактные тесты: `web/tests/test_openapi_contract.py`.
- **Пока не автоматизировано:** codegen для UI — после выбора генератора и пути вывода добавить скрипт в `package.json` и при необходимости шаг в CI; до тех пор этот раздел закрывает пункт из [#297](https://github.com/Gfermoto/BirdLense-Hub/issues/297).

## Сложность / radon (опционально)

- Порог cyclomatic complexity в CI пока не задан. Локально: `pip install radon && radon cc app/web app/processor/src -a -s`.

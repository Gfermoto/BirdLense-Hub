# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Fixed

- **Защита по паролю** — единая точка входа: пароль запрашивается при нажатии на иконку шестерёнки (настройки). После ввода пароля открывается меню «Настройки» и «Система», доступны обе страницы. Прямой переход по URL также защищён.

---

## [0.1.0-beta.1] - 2026-03-10

### Added

- **Coverage** — pytest-cov, `make test-coverage`, `make test-report`, `.coveragerc`
- **PROCESSOR_SECRET** — автогенерация при деплое, запись в `app/.env` на сервере
- Документация: заметка о смене пароля при утечке, E2E требует пароль при защите настроек

### Changed

- **util.py** — путь к `hierarchy_names.txt` через `__file__` (работает при любом cwd)
- **Makefile** — volume `-v $(pwd):/app` для test/test-web/test-coverage (локальный код)
- **TESTING.md** — приоритетные модули для расширения покрытия

### Removed

- **CPU temperature** — убрана из системных метрик (API, UI, OpenAPI)
- **Orphan containers** — удалены старые контейнеры (nginx, processor, web, ntfy)

### Fixed

- Web API тесты падали из-за `seed/hierarchy_names.txt` — исправлен путь

---

## [0.1.0-alpha.1]

Первый альфа-релиз. См. [README.md](./README.md) для обзора возможностей.

[0.1.0-beta.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.1
[0.1.0-alpha.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-alpha.1

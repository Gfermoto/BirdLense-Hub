# Версионирование BirdLense Hub

[English](./VERSIONING.md)

---

## Схема версий

Используется [Semantic Versioning](https://semver.org/lang/ru/): `MAJOR.MINOR.PATCH`.

| Часть | Когда увеличивать |
|-------|-------------------|
| **MAJOR** | Несовместимые изменения API или конфигурации |
| **MINOR** | Новая функциональность с обратной совместимостью |
| **PATCH** | Исправления ошибок, мелкие улучшения |

Примеры:
- `0.1.0` → `0.1.1` — исправление бага
- `0.1.1` → `0.2.0` — новая фича (например, новый тип триггера)
- `1.0.0` → `2.0.0` — ломающее изменение (например, смена формата конфига)

## Где хранится версия

| Файл | Назначение |
|------|------------|
| `VERSION` | Единый источник истины (корень репозитория) |
| `app/ui/package.json` | Версия UI-пакета |
| `app/web/openapi.yaml` | Версия API в OpenAPI |

При релизе обновлять все три.

## Релизы и теги

1. **Перед релизом:** обновить `VERSION`, `package.json`, `openapi.yaml`, `CHANGELOG.md`
2. **Коммит:** `git add -A && git commit -m "Release v0.1.0"`
3. **Тег:** `git tag -a v0.1.0 -m "Release v0.1.0"`
4. **Пуш:** `git push && git push origin v0.1.0`
5. **GitHub Release:** создать Release из тега, вставить заметки из CHANGELOG

### Что запускает GitHub Actions после релиза

- **Docker:** [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml) — образ **`latest`** при каждом push в `main`, тег **semver** (например `0.2.2`) при **опубликованном** GitHub Release с тегом вида `v0.2.2`.
- **Сайт документации:** [`.github/workflows/docs-pages.yml`](../.github/workflows/docs-pages.yml) — деплой при изменениях в `docs/**` и при событии **`release: published`**, чтобы версия на Pages обновлялась после релиза.

## CHANGELOG

Формат [Keep a Changelog](https://keepachangelog.com/).

Секции:
- **Added** — новая функциональность
- **Changed** — изменения в существующем поведении
- **Deprecated** — устаревшее (будет удалено)
- **Removed** — удалённая функциональность
- **Fixed** — исправления багов
- **Security** — уязвимости

## Обновления

- **Минорные (0.x.y):** обновление через `make deploy` или `make pull`. Конфиг и данные сохраняются.
- **Мажорные:** см. заметки к релизу — могут потребоваться миграции.

---

См. также: [Changelog](./project/changelog.md), [INSTALL](./INSTALL.ru.md).

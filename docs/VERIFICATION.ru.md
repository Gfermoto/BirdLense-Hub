# Верификация качества (операторам и мейнтейнерам)

Краткий журнал автоматических проверок перед возвратом к roadmap. Полный цикл — см. [CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md), [TESTING.ru.md](./TESTING.ru.md).

## 2026-04-02 — cleanup, удаление backend-хвостов и финальная полировка

| Проверка | Результат |
|----------|-----------|
| `python -m pytest tests/test_api.py tests/test_species_registry.py -q` (`app/web`) | 96 passed |
| `npm run build` (`app/ui`) | OK |
| Public `GET /api/ui/health` | `200 {"status":"ok"}` |
| Public `GET /api/ui/status/debug` без авторизации | `403 {"error":"Password required"}` |
| Public `POST /api/ui/system/species-registry/enrich-metadata` | `404 Not Found` |
| Public `POST /api/ui/system/species-registry/repair-cards` | `404 Not Found` |
| Диагностика каталога на production | duplicate names `0`, classifier/catalog drift `0`, dataset drift `0` |

**Какие фиксы внесены в репозиторий:**
- Удалены мёртвые legacy UI-файлы, из-за которых старые опасные Library-контролы могли пережить рефакторинг в дереве проекта.
- Публичный debug surface закрыт за доступом к settings, а неиспользуемые sync routes species-registry удалены.
- TESTING / CONFIGURATION / ARCHITECTURE приведены к текущему поведению роутов и актуальной модели UI.

## 2026-03-29 — критический фикс UI

| Проверка | Результат |
|----------|-----------|
| Кнопки «предыдущая / следующая запись» на `/videos/:id` | Исправлен `ReferenceError` (`listReturnState` не был объявлён); см. [CHANGELOG.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Рекомендуется вручную на стенде:** открыть ролик с Timeline → шаг prev/next → «Назад» возвращает в список; прямой заход по URL без `state` — навигация между роликами работает, «Назад» в браузере — по истории.

**Вне объёма автопрогона:** weekly E2E Playwright, полный `make docs` при изменении MkDocs.

## 2026-04-01 — аудит стабилизации и hardening

| Проверка | Результат |
|----------|-----------|
| `python -m pytest app/web/tests/test_system_stabilization.py app/web/tests/test_security_hardening.py -q` | 12 passed |
| `python -m pytest app/web/tests/test_species_catalog_reconcile.py -q` | 4 passed |
| `npm run build` (`app/ui`) | OK |
| Production `storage/stats` после 2026-03-24 | Файлы на диске есть вплоть до 2026-04-01 |
| Production `overview` / `timeline` после 2026-03-24 | Детекций и визитов после 2026-03-24 нет; архив есть, но ingest не создал `video_species` / `species_visit` |

**Какие фиксы внесены в репозиторий:**
- Library теперь показывает реальный архив записей и больше не выставляет опасные maintenance-потоки.
- Обслуживание БД в System поддерживает честный preview/apply для cleanup orphaned visits и realign visit times.
- В production больше нельзя неявно получить доступ к settings/system через «пустой пароль».
- Merge видов сохраняет недостающие metadata у итоговой карточки.
- Overview учитывает визиты, пересекающие выбранный день, включая переход через полночь.

**Как интерпретировать live-хаб:** если день подсвечен в Library, но пуст в Overview или Timeline, значит файлы записей на диске есть, а детекции за этот день не были сохранены в БД. После разведения Library и System это видно и диагностируется заметно проще.

# Runbooks для операторов — BirdLense Hub

[English](../user/runbooks.md)

Короткие сценарии на случай типичных сбоев.

## Установка прошла, но UI не открывается

1. Из корня репозитория выполните `make verify`.
2. Если падает `health`, посмотрите контейнеры: `cd app && docker compose ps && docker compose logs --tail=100 birdlense`.
3. Если образ собрался, но порт занят, задайте `BIRDLENSE_PORT` или добавьте `docker-compose.override.yml`, как в [LOCAL_DEV](./local-dev.ru.md).

## `/api/ui/health` в порядке, но деплою нельзя доверять

Используйте `BASE_URL=http://ВАШ_ХОСТ:8085 make verify` или `scripts/verify-stack.sh --base-url ...`.

Как читать результат:

- `health` OK, `readiness` FAIL: веб-процесс жив, но БД или каталоги для записи недоступны.
- `readiness` OK, `status` degraded: ядро хаба готово, но опциональные части (processor, видео, MQTT и т.д.) требуют внимания.

Если настройки открыты или у вас есть админский доступ, дополнительно проверьте:

- `GET /api/ui/system/domain-health`
- `GET /api/ui/system/species-registry/health`

Для скриптов на хабе с закрытыми настройками передайте `BIRDLENSE_UI_API_KEY` и выполните  
`REQUIRE_SETTINGS_HEALTH=1 BASE_URL=... ./scripts/verify-release.sh`.

Для `scripts/verify-stack.sh` добавьте `--check-domain-health` и задайте `BIRDLENSE_UI_API_KEY` (или `UI_API_KEY`), чтобы запросы к доменным и registry-эндпоинтам проходили с авторизацией.

Деплой через GitHub Actions: опциональный секрет репозитория **`BIRDLENSE_UI_API_KEY`** (то же значение, что в `app/.env` на сервере) включает проверки domain-health на шаге Verify — см. [release-readiness](../../release-readiness.md).

Чеклист релиза: [release-readiness](../../release-readiness.md).

## Матрица rollback для release-gate (C1)

Используйте матрицу при блокировке выката или деградации после канареечного включения.

| Сигнал | Действие | Проверка |
|---|---|---|
| `verify-stack --strict-quality` падает на domain/quality | Релиз остаётся заблокированным, деплой не считаем успешным | `make verify` должен проходить по health/readiness/status; причины блокировки видны в `domain-health` |
| После выката `readiness` деградировал (`503`) | Откат к последнему стабильному образу/конфигу и рестарт стека | `make verify` = PASS и `checks.*.status=ok` |
| Canary SLI регрессирует по `p95/error` выше порога | Остановить rollout и выполнить rollback-drill | Повторно собрать отчёт `make ml-canary-rollback-report`, требуется `ok=true` |
| После отката деградация остаётся | Эскалация инцидента, freeze новых деплоев | Приложить артефакт `canary_rollback_report@v1` и актуальный вывод `verify-stack` в issue |

Команда для rollback-drill (пример):

```bash
BASELINE=/tmp/base_sli.json \
CANARY=/tmp/canary_sli.json \
ROLLBACK=/tmp/rollback_sli.json \
OUT=/tmp/canary_rollback.v1.json \
make ml-canary-rollback-report
```

## Деплой завершён, но в браузере старый UI

1. Жёсткое обновление страницы.
2. Очистка кэша PWA / Service Worker.
3. Повторный `make verify` с `BASE_URL` развёрнутого хаба.

## API отвечает, но нет processor / детекций

1. Проверьте `/api/ui/status`, System → readiness и логи.
2. Логи processor:

```bash
ssh ВАШ_SSH_ХОСТ "tail -100 ВАШ_УДАЛЁННЫЙ_КАТАЛОГ/app/data/processor.log"
```

3. Убедитесь, что в `app/.env` у `PROCESSOR_SECRET` реальное значение, а не заглушка из примера.

## Канарейка PT-детектора (низкое разрешение потока)

Используйте, когда нужно проверить PyTorch-веса детектора (`.pt`) без полного переключения всего контура.

1. **Зафиксируйте baseline за 24ч** на текущем бэкенде:
   - снимок `domain-health`
   - число mismatch Frigate vs Hub
   - сбои артефактов записи (`ingest_gate` reason codes)
   - guardrails по производительности (p95 detect latency + CPU).
2. **Включите PT-canary** на одной камере/временном окне:
   - переключите бэкенд детектора на PT (`processor.inference_backend: torch`)
   - оставьте low-res поток и не меняйте другие пороги
   - держите копию предыдущего конфига для быстрого отката.
3. **Соберите метрики за 24ч** и сравните с baseline:
   - mismatch rate относительно Frigate
   - доля playable артефактов
   - распределение reason-code (`FUSION_*`, `REC_FILE_*`)
   - задержка и CPU по guardrails.
4. **Решение go / no-go**:
   - **go**: mismatch не хуже baseline и без регресса guardrails
   - **no-go**: рост mismatch или регресс guardrails -> немедленный rollback.
5. **Rollback**:
   - вернуть прежний backend/config
   - перезапустить стек
   - прогнать `make verify` и сохранить post-rollback `domain-health`.

## Еженедельный reliability-review KPI и decision log

Используйте этот ритм, чтобы reliability-задачи шли непрерывно и прозрачно.

Каденс и владелец:

- запуск 1 раз в неделю (фиксированные день/время)
- один ответственный за обзор KPI и постановку follow-up issues
- для тренда брать 7 дней, для острых сигналов — последние 24ч.

Источник и фиксация данных:

1. Получить `GET /api/ui/system/domain-health`.
2. Зафиксировать KPI-снимок в одном комментарии к issue (или ops-заметке) минимум по полям:
   - `parity_mismatch_rate_24h`
   - `parity_mismatched_windows_24h`
   - `recording_artifact_failures_24h`
   - `video_encoding_transitions_24h`
   - `ingest_gate_reason_code_counts_24h` (топ причин)
3. Добавить camera/day-night диагностику:
   - `parity_camera_split_24h`
   - `parity_hotspots_24h` (камеры с достаточным объёмом и повышенным mismatch rate)
4. Проверить guardrails:
   - `strict_quality.strict_quality_ready`
   - p95 detect latency + CPU из runtime diagnostics.

Правила решений:

- если mismatch тренд растёт week-over-week — создать follow-up issue и назначить owner
- если `recording_artifact_failures_24h > 0` — сразу открывать P1-инцидент
- если `parity_hotspot_count_24h > 0` — открыть/обновить follow-up issue по каждой hotspot-камере
- если alert `video_encoding_flapping=true` — заморозить config-изменения и разобрать runtime transitions до следующего деплоя.

Шаблон decision log:

```markdown
### Еженедельный reliability-review — YYYY-MM-DD
- Reviewer: <имя>
- Окно: <start>.. <end>
- KPI snapshot:
  - parity_mismatch_rate_24h: <значение>
  - parity_mismatched_windows_24h: <значение>
  - recording_artifact_failures_24h: <значение>
  - video_encoding_transitions_24h: <значение>
  - top_mismatch_causes: <reason_code:count, ...>
- Акценты по камерам:
  - <camera>: mismatch=<x/y>, day=<a/b>, night=<c/d>
- Решения:
  - <keep / rollback / tune / investigate>
- Follow-up issues:
  - #<id> <title> (owner: <имя>, due: <дата>)
```

## В логах «Slow frame processing» (медленная обработка кадра)

Симптом: в логах процессора строки вида **`Slow frame processing: … ms >= … ms`** — время прохода детектора/пайплайна превышает **`processor.frame_processing_warn_ms`** (по умолчанию **450** мс). Высокое разрешение + VA-API всё равно упираются в бюджет кадра.

1. **Система → Аудит конфигурации** — блок **Runtime процессора**: счётчик `slow_frame_processor_detect_total`, **p95** детектора vs порог (данные из `data/diagnostics/processor_runtime_stats.json`).
2. **Настройки → Процессор → Модели** — уменьшите **`processor.binary_imgsz`** (например **640**, затем **512**), сохраните настройки и снова посмотрите логи.
3. Если **шум в логах** приемлем по UX — поднимите **`processor.frame_processing_warn_ms`** (это **не ускоряет** инференс, только реже предупреждает).
4. **Свет / ночь** — если YOLO часто не вызывается из‑за light gate, см. `processor.light_gate_*` и ночные оверрайды (recall vs нагрузка).
5. **GPU (Orin)** — убедитесь, что контейнер использует NVIDIA runtime: `docker logs birdlense` (строки NVENC / GStreamer). Без GPU остаётся CPU.

См. также [PROCESSOR_PERFORMANCE](./processor-performance.ru.md), [CONFIGURATION](./configuration.ru.md), [release-readiness](../../release-readiness.md). Ворота релиза: DEFINITION_OF_DONE (архивирован).

## Падает readiness при установке или после деплоя

Сейчас readiness проверяет:

- путь к БД и возможность запроса;
- наличие и запись в `data/`;
- наличие и запись в `app_config/`.

Типичные исправления:

- пересоздать примонтированные каталоги под `app/data` и `app/app_config`;
- поправить владельца (`uid 1000`) или права на хосте;
- проверить путь к БД и volume в `DATA_DIR`.

## Устаревшие ключи в config-audit (gallery / Heimdall)

Если `GET /api/ui/system/config-audit` всё ещё показывает `gallery.*` или `general.heimdall_url`, они живут в **`app/app_config/user_config.yaml`** на хабе (в API токены/секреты замаскированы, «вытащить» их для чистки нельзя).

Тот же скрипт убирает явные `integrations.scales.mqtt_topic` / `mqtt_bird_present_topic` / `mqtt_command_topic`, если в YAML записаны как `""` — иначе они перекрывают топики, выводимые из `mqtt_topic_prefix` (предупреждения в ревизии конфигурации).

На сервере (путь к деплою подставьте свой):

```bash
cd /root/BirdLense
python3 scripts/prune_deprecated_user_config.py --path app/app_config/user_config.yaml --dry-run
python3 scripts/prune_deprecated_user_config.py --path app/app_config/user_config.yaml
cd app && docker compose restart birdlense
```

Перед записью создаётся резервная копия `user_config.yaml.bak`. См. также [SECRETS_ROTATION](../archive/internal/docs-legacy/SECRETS_ROTATION.ru.md).

## Быстрая проверка MCP (Bearer)

Нужен **тот же** секрет, что на хабе: `MCP_TOKEN` в `app/.env` (или `mcp.token` в UI — не строка `***` из GET settings).

```bash
export MCP_TOKEN='ваш-токен-с-сервера'
./scripts/verify-mcp.sh https://ВАШ_ХОСТ/
```

Подробнее: [MCP_SETUP.ru](./mcp-setup.ru.md).

## PostgreSQL как БД хаба

Compose overlay, `DATABASE_URL`, пул, greenfield vs перенос с SQLite и разделение с файлом процессора **`birdlense.db`**: [POSTGRES_MIGRATION.ru](../archive/internal/docs-legacy/POSTGRES_MIGRATION.ru.md).

## Отладка по запросам

Каждый ответ API содержит заголовок `X-Request-ID`.

Сопоставление с логами сервера:

1. Воспроизведите сбой в браузере или через `curl`.
2. Скопируйте `X-Request-ID` из ответа.
3. Найдите тот же идентификатор в `docker logs birdlense`.

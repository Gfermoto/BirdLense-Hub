# Web: карта bounded contexts → routes → services (#344)

Точка отсчёта для [Roadmap refactor — issue #344](https://github.com/Gfermoto/BirdLense-Hub/issues/344) (**фаза A**): не переносим код, только фиксируем границы, чтобы следующие PR шли **по одному модулю** с понятным контекстом.

Якорь в коде: комментарий в [`app/web/services/__init__.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/services/__init__.py).

Ниже **7 целевых контекстов** из roadmap и типичное соответствие **префикс HTTP** → **регистрация маршрутов** → **основные сервисы** (не исчерпывающий список файлов — уточнять по импортам в `routes/*`).

---

## 1. `species_catalog`

Подпакет кода: `app/web/services/species_catalog/` (фазы B–C [#344](https://github.com/Gfermoto/BirdLense-Hub/issues/344)) — модули **`allowlist.py`**, **`reconcile.py`**, **`api.py`**, **`registry.py`** (канонический реестр видов); shims **`species_catalog_*_service.py`** и **`species_registry_service.py`** сохраняют старые импорты.

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/species`, `/api/ui/bird_families`, `/api/ui/species-image`, `/api/ui/species/...` | `ui_species_catalog_routes.py`, `ui_species_media_routes.py` | `species_catalog_*`, `species_summary_*`, `species_image_proxy_*`, `species_metadata_*`, `xeno_canto_*`, `species_tuning_*` |
| `/api/ui/system/species-registry/...` | `ui_system_species_registry_routes.py` | `species_registry_*`, `species_data_quality_*`, `species_identity_*` |
| Часть maintenance под каталог | `ui_system_maintenance_routes.py` (`species-catalog/reconcile`) | `species_catalog_reconcile_*`, `species_merge_*` |

---

## 2. `timeline_visits`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/overview`, `/api/ui/timeline`, `/api/ui/migration-calendar`, `/api/ui/region-comparison`, `/api/ui/unknowns`, `/api/ui/report/pdf` | `ui_overview_timeline_routes.py` | `overview_*`, `timeline_*`, `migration_calendar_*`, `monthly_report_*`, `corrections_activity_*` |
| `/api/ui/videos/<id>...` (детали, соседи, кадры, merge-species, stream) | `ui_video_routes.py` | `video_*`, `video_neighbors_*`, `detection_*` (часть сценариев коррекции на видео) |

---

## 3. `settings_access_and_config`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/settings`, `requires-password`, `check-access`, `verify-password`, yaml import/export | `ui_settings_routes.py` | `settings_patch_*`, `settings_access_*`, `ui_password_*`, `session_idle_*`, `homeassistant_*` |
| `/api/ui/restart-processor` | `ui_settings_routes.py` | `processor_restart_*` |

---

## 4. `system_diagnostics_and_jobs`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/system/*` (metrics, observability, diagnostics, storage, db, retention, review-queue, maintenance, recognition, fusion eval/export, file-test, processor-weights) | `ui_system_*.py`, фрагменты в `ui_system_routes.py` (config-audit, logs, domain-health, activity, regenerate-*) | `system_*`, `processor_logs_*`, `sqlite_admin_*`, `review_queue_*`, `system_maintenance_*`, `system_file_test_*`, `fusion_*`, `ml_*`, `broken_videos_*`, … |
| `/api/metrics`, `/metrics` | `ui_system_metrics_routes.py` | `prometheus_metrics_*`, `system_metrics_*`, `system_live_metrics_*` |

---

## 5. `dataset_export`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/dataset/*`, `/api/ui/detections/<id>/*` (crop, confirm, PATCH) | `ui_corrections_dataset_routes.py` | `dataset_export_*`, `dataset_export_request_*`, `detection_crop_*`, `detection_species_correction_*` |

---

## 6. `notifications_and_integrations`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/ui/health`, `readiness`, `/api/ui/status`, `cameras`, `/api/ui/push/*` | `ui_status_push_routes.py` | `readiness_*`, `status_*`, `component_status_*`, `web_push_*` |
| `/api/ui/feed/*`, `/api/ui/weather`, `/api/ui/sun-times` | `ui_status_push_routes.py` | `feed_*`, `feeder_scale`, вызовы погоды через `util` / тонкий слой |
| `/api/ui/birdfood` | `ui_birdfood_routes.py` | `bird_food_*` |
| `/api/ui/notify/test` | `ui_settings_routes.py` | `activity_notify_*`, `telegram_proxy_*` (смежно) |
| `/api/ui/system/telegram-proxy/*` | `ui_system_fusion_routes.py` | `telegram_proxy_*`, `system_fusion_telegram_jobs_*` |

---

## 7. `processor_ingest`

| Префикс / зона | Файлы маршрутов | Сервисы (ориентир) |
|----------------|-----------------|---------------------|
| `/api/processor/*` | `processor_routes.py` | `visit_processor`, `http_response_cache`, парсинг JSON из `api_json_validation`; часть доменной логики пока в самом модуле маршрутов — кандидат на вынос (#344 фаза C) |

---

## Как пользоваться

1. Новый сервисный модуль — выбрать **один** контекст из таблицы и класть рядом с родственными `services/*` (в перспективе — подпакет с re-export, фаза B #344).
2. Новый UI-маршрут — зарегистрировать в существующем `ui_*_routes.py` того же контекста; не раздувать «свалку» в одном файле без причины.
3. Менять HTTP-контракт OpenAPI/UI — только осознанно и с тестами (`make test-web`, при ingest — `make ci-local-docker` по процессу репозитория).

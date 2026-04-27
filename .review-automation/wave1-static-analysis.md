# Wave 1: static analysis

| Priority | File | Line | Problem | Recommendation |
|---|---:|---:|---|---|
| high | `app/web/gpu_stats.py` | 29 | subprocess/shell=True без nosec/обоснования | Избегать shell=True или добавить строгий whitelist |
| medium | `app/processor/src/birdnet_fifo_persist.py` | 196 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/birdnet_fifo_persist.py` | 241 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/birdnet_fifo_snapshot.py` | 37 | Точное дублирование функции `_parse_ts` с `app/web/services/birdnet_fifo_view_service.py:36` | Вынести общую реализацию |
| medium | `app/processor/src/birdnet_fifo_snapshot.py` | 92 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/birdnet_fifo_snapshot.py` | 183 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/decision_maker.py` | 239 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/decision_maker.py` | 244 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/file_test_control.py` | 44 | Точное дублирование функции `atomic_write_json` с `app/web/services/system_file_test_service.py:49` | Вынести общую реализацию |
| medium | `app/processor/src/file_test_control.py` | 58 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/frigate_bbox.py` | 23 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/fusion_metrics.py` | 10 | Точное дублирование функции `_safe_float` с `app/processor/src/detection_fusion.py:24` | Вынести общую реализацию |
| medium | `app/processor/src/fusion_model.py` | 101 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/hypothesis_arbitration.py` | 20 | Точное дублирование функции `_safe_float` с `app/processor/src/detection_fusion.py:24` | Вынести общую реализацию |
| medium | `app/processor/src/motion_detectors/frigate_mqtt.py` | 217 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/motion_detectors/frigate_mqtt.py` | 251 | Точное дублирование функции `has_recent_activity` с `app/processor/src/motion_detectors/frigate_mqtt.py:80` | Вынести общую реализацию |
| medium | `app/processor/src/mqtt_aggregator.py` | 944 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/mqtt_aggregator.py` | 1202 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/mqtt_event_parsers.py` | 12 | Точное дублирование функции `_parse_iso8601_utc` с `app/processor/src/birdnet_fifo_persist.py:36` | Вынести общую реализацию |
| medium | `app/processor/src/mqtt_event_parsers.py` | 57 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/processor_cv2_init.py` | 32 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/processor_support.py` | 49 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/processor_support.py` | 77 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/processor_support.py` | 110 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/processor_support.py` | 115 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/recording_session.py` | 106 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/recordings_remote_mirror.py` | 179 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/recordings_remote_mirror.py` | 211 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/recordings_remote_mirror.py` | 232 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/sources/go2rtc_stream_source.py` | 309 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/sources/go2rtc_stream_source.py` | 344 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/sources/video_file_source.py` | 89 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/sources/video_file_source.py` | 343 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/sources/video_file_source.py` | 347 | Точное дублирование функции `_ensure_h264` с `app/processor/src/sources/video_file_source.py:93` | Вынести общую реализацию |
| medium | `app/processor/src/spectrogram.py` | 96 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/processor/src/spectrogram.py` | 101 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/app_startup.py` | 148 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/data_paths.py` | 94 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/data_paths.py` | 149 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/gpu_stats.py` | 88 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/gpu_stats.py` | 148 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/gpu_stats.py` | 154 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/notifications/__init__.py` | 358 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/notifications/__init__.py` | 364 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/notifications/__init__.py` | 369 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/routes/processor_routes.py` | 79 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/routes/ui_system_db_routes.py` | 149 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/birdnet_fifo_view_service.py` | 141 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/cache.py` | 39 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/cache.py` | 166 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/cache.py` | 182 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/cache.py` | 196 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/component_status_service.py` | 69 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 325 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 331 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 497 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 538 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 553 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 568 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 646 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 679 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 845 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 900 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 913 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 1117 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 1170 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 1222 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/dataset_export/export_core.py` | 1228 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/feed_service.py` | 70 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/feed_service.py` | 228 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/feeder_scale.py` | 140 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/migration_calendar_service.py` | 141 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/processor_custom_weights_service.py` | 246 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/processor_custom_weights_service.py` | 255 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 61 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 119 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 123 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 130 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 135 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/retention_service.py` | 161 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/species_catalog/allowlist.py` | 55 | Точное дублирование функции `_norm_key` с `app/web/services/species_data_quality_service.py:25` | Вынести общую реализацию |
| medium | `app/web/services/species_catalog/registry.py` | 40 | Точное дублирование функции `_norm_key` с `app/web/services/species_data_quality_service.py:25` | Вынести общую реализацию |
| medium | `app/web/services/species_catalog/registry.py` | 710 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/species_image_proxy_service.py` | 139 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/species_image_proxy_service.py` | 156 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/species_image_proxy_service.py` | 186 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/sqlite_admin_service.py` | 43 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/status_service.py` | 59 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_file_test_service.py` | 63 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_file_test_service.py` | 263 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_file_test_service.py` | 271 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_metrics_api_service.py` | 98 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_metrics_sampler_service.py` | 156 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_spectrogram_regen_service.py` | 75 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_spectrogram_regen_service.py` | 83 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_sqlite_admin_api_service.py` | 108 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_storage_service.py` | 251 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/system_storage_service.py` | 299 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/services/ui_password_service.py` | 71 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| medium | `app/web/telegram_mtproto.py` | 227 | Исключение полностью игнорируется (`pass`) | Логировать или явно документировать no-op |
| low | `app/processor/src/decision_maker.py` | 44 | Много параметров в `__init__` (13) | Ввести dataclass/config object |
| low | `app/processor/src/decision_trace_builder.py` | 106 | Много параметров в `build_decision_trace_payload` (10) | Ввести dataclass/config object |
| low | `app/processor/src/detection_fusion.py` | 69 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/detection_fusion.py` | 178 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/detection_fusion.py` | 453 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/detection_fusion.py` | 475 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/detection_strategy.py` | 204 | Много параметров в `__init__` (12) | Ввести dataclass/config object |
| low | `app/processor/src/frame_processor.py` | 207 | Много параметров в `update_track` (10) | Ввести dataclass/config object |
| low | `app/processor/src/fusion_model.py` | 21 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/fusion_model.py` | 72 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/fusion_model.py` | 101 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/motion_detectors/factory.py` | 12 | Много параметров в `build_motion_detector` (17) | Ввести dataclass/config object |
| low | `app/processor/src/motion_detectors/frigate_mqtt.py` | 107 | Много параметров в `__init__` (10) | Ввести dataclass/config object |
| low | `app/processor/src/motion_detectors/frigate_mqtt.py` | 217 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/motion_runtime.py` | 15 | Много параметров в `build_processor_motion_detector` (9) | Ввести dataclass/config object |
| low | `app/processor/src/mqtt_aggregator.py` | 73 | Много параметров в `__init__` (25) | Ввести dataclass/config object |
| low | `app/processor/src/mqtt_aggregator.py` | 944 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/processor_cv2_init.py` | 32 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/processor_support.py` | 102 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/processor_support.py` | 110 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/processor_support.py` | 115 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/recording_decision_trace_log.py` | 16 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/recording_finalize.py` | 39 | Много параметров в `finalize_motion_recording` (14) | Ввести dataclass/config object |
| low | `app/processor/src/recording_ingest_gate.py` | 29 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/recording_session.py` | 28 | Много параметров в `__init__` (15) | Ввести dataclass/config object |
| low | `app/processor/src/recording_session.py` | 106 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/recordings_remote_mirror.py` | 211 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/processor/src/sources/go2rtc_stream_source.py` | 71 | Много параметров в `__init__` (9) | Ввести dataclass/config object |
| low | `app/processor/src/sources/video_file_source.py` | 225 | Много параметров в `__init__` (9) | Ввести dataclass/config object |
| low | `app/processor/src/species_normalizer.py` | 168 | Много параметров в `merge_detections` (13) | Ввести dataclass/config object |
| low | `app/ui/src/App.tsx` | 104 | TypeScript `any` | Заменить на точный тип / unknown + narrowing |
| low | `app/ui/src/App.tsx` | 105 | TypeScript `any` | Заменить на точный тип / unknown + narrowing |
| low | `app/ui/src/App.tsx` | 230 | TypeScript `any` | Заменить на точный тип / unknown + narrowing |
| low | `app/ui/src/api/camerasHealth.test.ts` | 40 | TypeScript `any` | Заменить на точный тип / unknown + narrowing |
| low | `app/ui/src/api/client.ts` | 4 | TypeScript `any` | Заменить на точный тип / unknown + narrowing |
| low | `app/ui/src/pages/Settings/sections/GeneralSection.tsx` | 63 | console.* в UI-коде | Убрать или заменить централизованным логированием |
| low | `app/ui/src/pages/VideoDetails/VideoPlayer/index.tsx` | 287 | console.* в UI-коде | Убрать или заменить централизованным логированием |
| low | `app/ui/src/pages/VideoDetails/VideoPlayer/index.tsx` | 304 | console.* в UI-коде | Убрать или заменить централизованным логированием |
| low | `app/web/services/cache.py` | 166 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/cache.py` | 182 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/cache.py` | 196 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/corrections_activity_service.py` | 29 | Много параметров в `write_correction_activity` (14) | Ввести dataclass/config object |
| low | `app/web/services/dataset_export/export_core.py` | 353 | Много параметров в `build_dataset_zip` (9) | Ввести dataclass/config object |
| low | `app/web/services/dataset_export/export_core.py` | 497 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/dataset_export/export_core.py` | 646 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/dataset_export/export_core.py` | 679 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/dataset_export/export_core.py` | 845 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/dataset_export/export_core.py` | 913 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/detection_species_correction_service.py` | 93 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/feed_service.py` | 13 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/feed_service.py` | 70 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/feed_service.py` | 228 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/fusion_training_service.py` | 396 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/processor_ingest/gateway.py` | 22 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/readiness_service.py` | 35 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/retention_service.py` | 309 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 350 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 395 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 493 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 682 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 710 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/species_catalog/registry.py` | 899 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/system_metrics_sampler_service.py` | 156 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/services/track_regen_service.py` | 90 | Много параметров в `build_track_regen_policy_snapshot` (10) | Ввести dataclass/config object |
| low | `app/web/services/visit_processor.py` | 37 | Много параметров в `process_video_detection` (9) | Ввести dataclass/config object |
| low | `app/web/services/visit_processor.py` | 75 | Много параметров в `process_video_detection_review_only` (9) | Ввести dataclass/config object |
| low | `app/web/telegram_mtproto.py` | 131 | Много параметров в `_mtproto_send_inner` (12) | Ввести dataclass/config object |
| low | `app/web/telegram_mtproto.py` | 227 | Широкий except Exception без явного логирования/return рядом | Сузить exception или добавить logging |
| low | `app/web/telegram_mtproto.py` | 231 | Много параметров в `mtproto_send` (12) | Ввести dataclass/config object |

## Summary
- critical: 0
- high: 1
- medium: 99
- low: 69

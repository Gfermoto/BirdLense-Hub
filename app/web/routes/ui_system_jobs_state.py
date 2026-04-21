"""Общие locks и статусы долгих задач UI system API (#265)."""

from __future__ import annotations

import threading

_regenerate_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_regenerate_lock = threading.Lock()
_regenerate_tracks_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_regenerate_tracks_lock = threading.Lock()
_species_metadata_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_species_metadata_lock = threading.Lock()
_catalog_cards_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_catalog_cards_lock = threading.Lock()
_catalog_cards_next_run_ts = 0.0
# Сдвиг окна приоритетов для catalog repair (авто/ручной): иначе при limit=150 вечно
# те же первые неполные строки allowlist и процент «Поля заполнены» замирает.
_catalog_repair_priority_rotate = 0
_fusion_export_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_fusion_export_lock = threading.Lock()
_fusion_eval_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_fusion_eval_lock = threading.Lock()
_recognition_training_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_recognition_training_lock = threading.Lock()
_telegram_proxy_refresh_status = {
    "status": "idle",
    "result": None,
    "error": None,
    "progress": None,
}
_telegram_proxy_refresh_lock = threading.Lock()

_sampler_lock = threading.Lock()
_sampler_started = False

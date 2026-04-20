"""Юнит-тесты сервисов, вынесенных из ui_overview_timeline_routes (#293)."""

from datetime import datetime, timedelta, timezone

import pytest


def test_validate_migration_calendar_params_ok_and_errors():
    from services.migration_calendar_request_service import (
        validate_migration_calendar_params,
    )

    assert validate_migration_calendar_params("observed", None, None) is None
    assert validate_migration_calendar_params("active", "2024-01-01", "2024-01-31") is None
    err = validate_migration_calendar_params("nope", None, None)
    assert err and "catalog" in err
    err = validate_migration_calendar_params("observed", "2024/01/01", None)
    assert "start_date" in err
    err = validate_migration_calendar_params("observed", "2024-02-01", "2024-01-01")
    assert "start_date must be <=" in err


def test_migration_calendar_cache_key_stable():
    from services.migration_calendar_request_service import migration_calendar_cache_key

    k = migration_calendar_cache_key(2024, 2025, None, None, "dataset", "all")
    assert k == "migration_cal:v3:2024:2025:None:None:dataset:all"


def test_validate_timeline_export_format():
    from services.timeline_export_service import validate_timeline_export_format

    assert validate_timeline_export_format("json") is None
    assert validate_timeline_export_format("xml") is not None


def test_resolve_timeline_utc_window_unix_range():
    from services.timeline_window_service import resolve_timeline_utc_window

    ts0 = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    ts1 = int(datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc).timestamp())
    start_dt, end_dt = resolve_timeline_utc_window(
        date_param=None,
        time_of_day="all",
        hour_param=None,
        start_time=str(ts0),
        end_time=str(ts1),
    )
    assert start_dt < end_dt


def test_resolve_timeline_utc_window_requires_both_timestamps():
    from services.timeline_window_service import (
        TimelineWindowError,
        resolve_timeline_utc_window,
    )

    with pytest.raises(TimelineWindowError, match="Both start_time"):
        resolve_timeline_utc_window(
            date_param=None,
            time_of_day="all",
            hour_param=None,
            start_time="123",
            end_time=None,
        )


def test_resolve_monthly_report_window_month():
    from services.monthly_report_window_service import resolve_monthly_report_window

    start_dt, end_dt, label = resolve_monthly_report_window("2026-03", None, None)
    assert start_dt.year == 2026 and start_dt.month == 3 and start_dt.day == 1
    assert end_dt.month == 3 and end_dt >= start_dt
    assert "2026" in label


def test_resolve_monthly_report_window_rejects_long_range():
    from services.monthly_report_window_service import (
        MAX_REPORT_RANGE_DAYS,
        MonthlyReportWindowError,
        resolve_monthly_report_window,
    )

    t0 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    t1 = int(
        (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=MAX_REPORT_RANGE_DAYS + 1)).timestamp(),
    )
    with pytest.raises(MonthlyReportWindowError, match="3 months"):
        resolve_monthly_report_window(None, str(t0), str(t1))


def test_build_timeline_export_response_json_and_empty_csv():
    from services.timeline_export_service import build_timeline_export_response_parts

    start = datetime(2026, 3, 24, 0, 0, 0)
    end = datetime(2026, 3, 24, 23, 0, 0)
    rows = [
        {
            "id": 1,
            "species_name": "Test Bird",
            "start_time": "2026-03-24T10:00:00+00:00",
            "end_time": "2026-03-24T10:00:05+00:00",
            "duration_sec": 5,
            "max_simultaneous": 1,
            "detection_count": 0,
            "temp": None,
            "clouds": None,
        },
    ]
    body, mime, headers = build_timeline_export_response_parts(
        "json",
        rows,
        start,
        end,
    )
    assert mime == "application/json"
    assert "Test Bird" in body
    assert "birdlense_timeline.json" in headers["Content-Disposition"]

    body_csv, mime_csv, _ = build_timeline_export_response_parts(
        "csv",
        [],
        start,
        end,
    )
    assert mime_csv == "text/csv"
    assert "species_name" in body_csv


def test_parse_dataset_export_query_args_defaults():
    from services.dataset_export_request_service import parse_dataset_export_query_args

    class _A(dict):
        def get(self, k, default=None):
            return super().get(k, default)

    args = _A()
    p = parse_dataset_export_query_args(args)
    assert p["val_ratio"] == 0.2
    assert p["only_manually_corrected"] is False
    assert p["strict_quality"] is False


def test_parse_system_activity_month():
    from services.system_activity_service import (
        SystemActivityMonthError,
        parse_system_activity_month,
    )

    start, end = parse_system_activity_month("2026-03")
    assert start.year == 2026 and start.month == 3
    assert end > start
    with pytest.raises(SystemActivityMonthError):
        parse_system_activity_month("not-a-month")


def test_clamp_processor_log_line_count():
    from services.processor_logs_service import (
        LOG_LINES_DEFAULT,
        LOG_LINES_MAX,
        clamp_processor_log_line_count,
    )

    assert clamp_processor_log_line_count("50") == 50
    assert clamp_processor_log_line_count(99999) == LOG_LINES_MAX
    assert clamp_processor_log_line_count("x") == LOG_LINES_DEFAULT


def test_parse_video_neighbors_request_args():
    from werkzeug.datastructures import ImmutableMultiDict

    from services.video_neighbors_service import (
        VideoNeighborsParamError,
        parse_video_neighbors_request_args,
    )

    args = ImmutableMultiDict(
        [
            ("day_scope", "utc"),
            ("neighbor_mode", "video"),
            ("tz_offset_minutes", "0"),
        ]
    )
    scope, cross, mode, vid, tz = parse_video_neighbors_request_args(args)
    assert scope == "utc" and cross is False and mode == "video" and vid is None and tz == 0

    with pytest.raises(VideoNeighborsParamError, match="day_scope"):
        parse_video_neighbors_request_args(
            ImmutableMultiDict([("day_scope", "mars")]),
        )


def test_parse_push_subscription_body_ok_and_errors():
    from services.web_push_service import (
        PushSubscriptionBodyError,
        parse_push_subscription_body,
    )

    ep, p256, au = parse_push_subscription_body(
        {
            "subscription": {
                "endpoint": "https://x.example/push",
                "keys": {"p256dh": "pdh", "auth": "at"},
            },
        }
    )
    assert ep.startswith("https://")
    assert p256 == "pdh" and au == "at"
    with pytest.raises(PushSubscriptionBodyError, match="subscription required"):
        parse_push_subscription_body({"subscription": None})
    with pytest.raises(PushSubscriptionBodyError, match="p256dh"):
        parse_push_subscription_body(
            {
                "subscription": {"endpoint": "x", "keys": {}},
            }
        )


def test_trigger_format_helpers_match_processor_and_status():
    from app_config.trigger_config import format_motion_source_summary, format_trigger_display_line

    assert format_trigger_display_line([]) == ""
    assert format_trigger_display_line(["opencv", "frigate"]) == "opencv + frigate"
    assert format_trigger_display_line(["motion_sensor", "frigate"]) == "motion_sensor + frigate"
    assert format_trigger_display_line(["unknown_src"]) == "unknown_src"
    assert format_motion_source_summary([]) == "none"
    assert format_motion_source_summary(["opencv"]) == "opencv"
    assert format_motion_source_summary(["opencv", "scales"]) == "opencv,scales"


def test_parse_unresolved_limit_species_registry():
    from services.species_registry_admin_service import parse_unresolved_limit

    assert parse_unresolved_limit("25") == 25
    assert parse_unresolved_limit(None) == 100
    assert parse_unresolved_limit("x") == 100


def test_nearest_recording_day_next_prev(monkeypatch):
    import services.system_storage_service as sss

    monkeypatch.setattr(
        sss,
        "recording_days_iso_sorted",
        lambda: ["2026-01-10", "2026-01-20"],
    )
    body, code = sss.nearest_recording_day_response("2026-01-15", "next")
    assert code == 200
    assert body["found"] and body["date"] == "2026-01-20"
    body2, _ = sss.nearest_recording_day_response("2026-01-15", "prev")
    assert body2["date"] == "2026-01-10"


def test_coerce_duplicate_group_limit():
    from services.system_maintenance_service import coerce_duplicate_group_limit

    assert coerce_duplicate_group_limit(500) == (500, None)
    assert coerce_duplicate_group_limit(5) == (10, None)
    assert coerce_duplicate_group_limit(100_000) == (5000, None)
    lim, err = coerce_duplicate_group_limit("bad")
    assert lim is None and err == "duplicate_group_limit must be int"


def test_normalize_export_format():
    from services.species_registry_admin_service import normalize_export_format

    assert normalize_export_format(" CSV ") == "csv"
    assert normalize_export_format(None) == "json"


def test_parse_broken_videos_list_params_clamped():
    from werkzeug.datastructures import ImmutableMultiDict

    from services.system_diagnostics_service import parse_broken_videos_list_params

    args = ImmutableMultiDict(
        [
            ("limit", "5"),
            ("after_id", "10"),
            ("max_scan", "100"),
        ]
    )
    lim, after, mx = parse_broken_videos_list_params(args)
    assert lim == 5 and after == 10 and mx == 100

    args2 = ImmutableMultiDict([("limit", "9999"), ("max_scan", "999999")])
    lim2, _, mx2 = parse_broken_videos_list_params(args2)
    assert lim2 == 200 and mx2 == 20000


def test_parse_review_only_noise_limit():
    from werkzeug.datastructures import ImmutableMultiDict

    from services.system_diagnostics_service import parse_review_only_noise_limit

    assert parse_review_only_noise_limit(ImmutableMultiDict([("limit", "10")])) == 10
    with pytest.raises(ValueError):
        parse_review_only_noise_limit(ImmutableMultiDict([("limit", "nope")]))


def test_birdnet_fifo_snapshot_missing_file(monkeypatch, tmp_path):
    import data_paths
    from services import birdnet_fifo_view_service as bfvs
    from services.system_diagnostics_service import build_birdnet_fifo_snapshot_response

    monkeypatch.setattr(bfvs, "try_build_birdnet_fifo_snapshot_from_db", lambda: None)
    monkeypatch.setattr(data_paths, "data_dir", lambda: str(tmp_path))
    body, code = build_birdnet_fifo_snapshot_response()
    assert code == 200
    assert body.get("available") is False
    assert body.get("reason") == "snapshot_file_missing"


def test_flatten_config_keys_terminal_maps():
    from services.system_config_audit_service import (
        TERMINAL_CONFIG_MAP_KEYS,
        flatten_config_keys,
    )

    nested = {"a": {"b": 1}}
    assert flatten_config_keys(nested) == {"a", "a.b"}
    terminal = next(iter(TERMINAL_CONFIG_MAP_KEYS))
    assert flatten_config_keys({}, prefix=terminal) == {terminal}


def test_build_system_config_audit_payload(monkeypatch, tmp_path):
    from services import system_config_audit_service as scas

    user = tmp_path / "user.yaml"
    user.write_text("extra_key: 1\n", encoding="utf-8")
    default_f = tmp_path / "default.yaml"
    default_f.write_text("known: 1\n", encoding="utf-8")

    def _get(key, default=None):
        mapping = {
            "notifications": {"telegram_proxy_type": "http", "send_photo": True},
            "motion.source": "opencv",
            "mqtt.broker": "",
            "motion.check_every_n_frames": 2,
            "motion.opencv_diff_threshold": 22,
            "motion.opencv_min_contour_area": 320,
            "processor.light_gate_enabled": True,
            "processor.light_gate_min_brightness": 25,
            "processor.light_gate_min_contrast": 20,
            "processor.binary_imgsz": 512,
            "processor.min_center_dist": 0.06,
            "processor.min_box_size_px": 72,
            "detection.species_mapping": {
                "Gray-headed Woodpecker": "Grey-headed Woodpecker",
                "Great Gray Shrike": "Great Grey Shrike",
            },
            "ebird.species_mapping": {},
        }
        return mapping.get(key, default)

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    assert "extra_key" in payload["unknown_keys"]
    assert payload["mapping"]["gray_to_grey_ok"] is True
    assert payload["recall_tuning"]["binary_imgsz"] == 512
    assert payload["recall_tuning"]["check_every_n_frames"] == 2
    rw = payload["recall_warnings"]
    assert rw
    assert any("motion.opencv_diff_threshold=22" in w and "hub default" in w for w in rw)
    assert any("motion.opencv_min_contour_area=320" in w and "240" in w for w in rw)
    assert "scales_mqtt" in payload
    assert payload["scales_mqtt"]["enabled"] is False
    assert payload["scales_warnings"] == []
    assert payload.get("processor_runtime_hints") == []
    # Подсказки recall не смешиваем с блокирующими предупреждениями (Frigate/MQTT-весы).
    assert payload["config_warnings"] == []


def test_build_system_config_audit_payload_processor_runtime_hints(
    monkeypatch, tmp_path
):
    from services import system_config_audit_service as scas
    import data_paths

    diag = tmp_path / "diagnostics"
    diag.mkdir(parents=True)
    stats = diag / "processor_runtime_stats.json"
    stats.write_text(
        '{"counters": {"slow_frame_processor_detect_total": 3}, '
        '"latency_ms": {"frame_processor_detect_p95": 480.0}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(data_paths, "data_dir", lambda: str(tmp_path))

    user = tmp_path / "user.yaml"
    user.write_text("known: 1\n", encoding="utf-8")
    default_f = tmp_path / "default.yaml"
    default_f.write_text("known: 1\n", encoding="utf-8")

    def _get(key, default=None):
        mapping = {
            "notifications": {"telegram_proxy_type": "none", "send_photo": False},
            "motion.source": "opencv",
            "mqtt.broker": "",
            "motion.check_every_n_frames": 1,
            "motion.opencv_diff_threshold": 18,
            "motion.opencv_min_contour_area": 240,
            "processor.light_gate_enabled": True,
            "processor.light_gate_min_brightness": 25,
            "processor.light_gate_min_contrast": 20,
            "processor.binary_imgsz": 512,
            "processor.min_center_dist": 0.06,
            "processor.min_box_size_px": 72,
            "processor.frame_processing_warn_ms": 450,
            "detection.species_mapping": {},
            "ebird.species_mapping": {},
        }
        return mapping.get(key, default)

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    hints = payload["processor_runtime_hints"]
    assert any("SLOW_FRAMES total=3 warn_ms=450" in h for h in hints)
    assert any("DETECT_P95" in h and "480.0" in h for h in hints)


def test_recall_frigate_blocking_goes_to_config_warnings_not_recall_hints(monkeypatch, tmp_path):
    from services import system_config_audit_service as scas

    user = tmp_path / "user.yaml"
    user.write_text("triggers:\n  frigate:\n    enabled: true\n", encoding="utf-8")
    default_f = tmp_path / "default.yaml"
    default_f.write_text("known: 1\n", encoding="utf-8")

    nested = {
        "mqtt": {"broker": ""},
        "motion": {"source": "opencv"},
        "triggers": {"frigate": {"enabled": True}},
    }

    def _get(key, default=None):
        cur: object = nested
        for part in str(key).split("."):
            if not isinstance(cur, dict):
                return default
            if part not in cur:
                return default
            cur = cur[part]
        return cur

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    assert any("Frigate trigger is enabled" in w for w in payload["config_warnings"])
    assert not any("Frigate trigger is enabled" in w for w in payload["recall_warnings"])


def test_scales_mqtt_audit_warns_broker_and_prefix(monkeypatch, tmp_path):
    from services import system_config_audit_service as scas

    user = tmp_path / "user.yaml"
    user.write_text(
        "integrations:\n  scales:\n    enabled: true\n    source: mqtt\n    mqtt_topic_prefix: bird-feeder-scale\n",
        encoding="utf-8",
    )
    default_f = tmp_path / "default.yaml"
    default_f.write_text("known: 1\n", encoding="utf-8")

    def _get(key, default=None):
        m = {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_topic_prefix": "bird-feeder-scale",
            "integrations.scales.mqtt_topic": "",
            "mqtt.broker": "",
            "notifications": {"telegram_proxy_type": "none", "send_photo": False},
            "motion.source": "opencv",
            "motion.check_every_n_frames": 1,
            "motion.opencv_diff_threshold": 18,
            "motion.opencv_min_contour_area": 240,
            "processor.light_gate_enabled": True,
            "processor.light_gate_min_brightness": 20,
            "processor.light_gate_min_contrast": 15,
            "processor.binary_imgsz": 640,
            "processor.min_center_dist": 0.06,
            "processor.min_box_size_px": 72,
            "detection.species_mapping": {},
            "ebird.species_mapping": {},
        }
        return m.get(key, default)

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    sw = payload["scales_warnings"]
    assert any("mqtt.broker is empty" in w for w in sw)
    assert any("bird-feeder-scale" in w and "birdlense/scale" in w for w in sw)
    assert payload["scales_mqtt"]["mqtt_weight_topic_resolved"] == "bird-feeder-scale/weight"


def test_scales_mqtt_audit_no_warn_explicit_empty_topics_when_prefix_set(tmp_path):
    """Explicit '' for topic keys with a non-empty prefix matches omitting keys — no audit spam."""
    from services import system_config_audit_service as scas

    user = tmp_path / "user.yaml"
    user.write_text(
        "integrations:\n  scales:\n    enabled: true\n    source: mqtt\n"
        '    mqtt_topic_prefix: "birdlense/scale"\n'
        '    mqtt_topic: ""\n'
        '    mqtt_bird_present_topic: ""\n'
        '    mqtt_command_topic: ""\n',
        encoding="utf-8",
    )
    default_f = tmp_path / "default.yaml"
    default_f.write_text("known: 1\n", encoding="utf-8")

    def _get(key, default=None):
        m = {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_topic_prefix": "birdlense/scale",
            "integrations.scales.mqtt_topic": "",
            "integrations.scales.mqtt_bird_present_topic": "",
            "integrations.scales.mqtt_command_topic": "",
            "mqtt.broker": "192.168.1.10",
            "notifications": {"telegram_proxy_type": "none", "send_photo": False},
            "motion.source": "opencv",
            "motion.check_every_n_frames": 1,
            "motion.opencv_diff_threshold": 18,
            "motion.opencv_min_contour_area": 240,
            "processor.light_gate_enabled": True,
            "processor.light_gate_min_brightness": 20,
            "processor.light_gate_min_contrast": 15,
            "processor.binary_imgsz": 640,
            "processor.min_center_dist": 0.06,
            "processor.min_box_size_px": 72,
            "detection.species_mapping": {},
            "ebird.species_mapping": {},
        }
        return m.get(key, default)

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    sw = payload["scales_warnings"]
    assert not any("empty string overrides defaults" in w for w in sw)
    assert payload["scales_mqtt"]["mqtt_weight_topic_resolved"] == "birdlense/scale/weight"


def test_scales_mqtt_audit_detects_explicit_empty_prefix(tmp_path):
    from services import system_config_audit_service as scas

    user = tmp_path / "user.yaml"
    # Без PyYAML: в полном web-suite ``yaml`` может быть подменён autouse-фикстурой.
    user.write_text(
        'integrations:\n  scales:\n    enabled: true\n    source: mqtt\n    mqtt_topic_prefix: ""\n',
        encoding="utf-8",
    )
    default_f = tmp_path / "default.yaml"
    default_f.write_text("x: 1\n", encoding="utf-8")

    def _get(key, default=None):
        m = {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "mqtt",
            "integrations.scales.mqtt_topic_prefix": "",
            "integrations.scales.mqtt_topic": "",
            "mqtt.broker": "192.168.1.10",
            "notifications": {"telegram_proxy_type": "none", "send_photo": False},
            "motion.source": "opencv",
            "motion.check_every_n_frames": 1,
            "motion.opencv_diff_threshold": 18,
            "motion.opencv_min_contour_area": 240,
            "processor.light_gate_enabled": True,
            "processor.light_gate_min_brightness": 20,
            "processor.light_gate_min_contrast": 15,
            "processor.binary_imgsz": 640,
            "processor.min_center_dist": 0.06,
            "processor.min_box_size_px": 72,
            "detection.species_mapping": {},
            "ebird.species_mapping": {},
        }
        return m.get(key, default)

    payload = scas.build_system_config_audit_payload(
        user_config_file=str(user),
        default_config_file=str(default_f),
        app_config_get=_get,
    )
    assert any("mqtt_topic_prefix is explicitly empty" in w for w in payload["scales_warnings"])
    assert any("both mqtt_topic and mqtt_topic_prefix are empty" in w for w in payload["scales_warnings"])


def test_build_timeline_export_response_ebird(monkeypatch):
    from services import timeline_export_service as tes

    monkeypatch.setattr(
        tes,
        "build_ebird_csv",
        lambda rows, _s, _e: "stub," + str(len(rows)),
    )
    body, mime, headers = tes.build_timeline_export_response_parts(
        "ebird",
        [
            {"species_name": "A", "x": 1},
            {"species_name": "A", "x": 2},
            {"species_name": "B", "x": 3},
        ],
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
    )
    assert mime == "text/csv"
    assert body == "stub,2"
    assert "ebird" in headers["Content-Disposition"]


def test_compute_system_activity_uptime_bad_month():
    from unittest.mock import MagicMock

    from services.system_admin_api_service import compute_system_activity_uptime

    body, code = compute_system_activity_uptime(MagicMock(), "not-a-month")
    assert code == 400
    assert "error" in body


def test_fusion_export_download_file_or_error_missing(monkeypatch):
    from services import system_fusion_telegram_jobs_service as sft

    monkeypatch.setattr(sft, "latest_fusion_export_path", lambda: None)
    path, err, code = sft.fusion_export_download_file_or_error()
    assert path is None and err and code == 404


def test_fusion_eval_download_file_or_error_missing(monkeypatch):
    from services import system_fusion_telegram_jobs_service as sft

    monkeypatch.setattr(sft, "latest_fusion_eval_report_path", lambda: None)
    path, err, code = sft.fusion_eval_download_file_or_error()
    assert path is None and err and code == 404


def test_prepare_sqlite_db_backup_rejects_non_sqlite_engine():
    from services.system_sqlite_admin_api_service import (
        prepare_sqlite_db_backup_download,
    )

    class _Eng:
        url = "postgresql://localhost/db"

    err, data, code = prepare_sqlite_db_backup_download(_Eng())
    assert err and "SQLite" in err["error"]
    assert data is None
    assert code == 400


def test_start_bulk_spectrogram_requires_birdnet(monkeypatch):
    from services import system_admin_api_service as saa

    monkeypatch.setattr(saa, "_birdnet_configured", lambda: False)

    class _FakeApp:
        pass

    body, code = saa.start_bulk_spectrogram_regeneration(_FakeApp(), {})
    assert code == 400
    assert "BirdNET" in body.get("error", "")


def test_review_queue_bulk_delete_confirm_mismatch(monkeypatch):
    from unittest.mock import MagicMock

    from services import review_queue_bulk_delete_api_service as rq_svc

    monkeypatch.setattr(
        rq_svc,
        "resolve_review_queue_bulk_plan",
        lambda *_a, **_k: {
            "confirmation_phrase": "permanent_full",
            "video_ids": [1],
            "videos_by_id": {},
        },
    )
    sess = MagicMock()
    body, code = rq_svc.execute_review_queue_bulk_delete(
        sess,
        {"confirm_text": "wrong"},
    )
    assert code == 400
    assert "Confirmation" in body.get("error", "")
    sess.commit.assert_not_called()


def test_parse_visitors_days_and_metrics_history_clamps():
    from services.system_metrics_api_service import (
        clamp_metrics_history_hours,
        clamp_metrics_history_max_points,
        parse_visitors_days,
    )
    from services.system_metrics_constants import (
        SYSTEM_METRICS_HISTORY_MAX_HOURS,
        SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP,
    )

    assert parse_visitors_days(None) == 7
    assert parse_visitors_days("bad") == 7
    assert parse_visitors_days("14") == 14

    assert clamp_metrics_history_hours(None) == 24
    assert clamp_metrics_history_hours("9999") == SYSTEM_METRICS_HISTORY_MAX_HOURS
    assert clamp_metrics_history_hours("0") == 1

    assert clamp_metrics_history_max_points("99999") == SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP
    assert clamp_metrics_history_max_points("10") == 50

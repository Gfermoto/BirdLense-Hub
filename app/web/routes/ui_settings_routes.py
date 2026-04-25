"""Настройки, verify-password, eBird suggestions, notify/test, restart-processor (#198)."""

import os
from datetime import datetime, timezone

import yaml
from flask import Response, request, session

from app_config.app_config import app_config, migrate_legacy_homeassistant_from_weather
from auth import (
    _check_verify_password_rate_limit,
    _clear_verify_password_attempts,
    _record_verify_password_failure,
    admin_settings_yaml_access,
    client_ip_for_rate_limit,
    contributor_or_admin_access,
    settings_check_access,
    settings_read_access,
    settings_yaml_safe_export_access,
    verify_password_retry_after_seconds,
)
from services.cache import cache_delete_prefix
from services.http_response_cache import bust_response_caches
from services.processor_restart_service import write_processor_restart_flag
from services.settings_access_service import (
    contributor_tier_configured,
    empty_passwords_block_verify_in_production,
    resolve_password_unlock_role,
    settings_gate_requires_password,
)
from services.api_json_validation import (
    parse_request_json_dict,
    parse_request_json_object_allow_empty,
)
from services.session_idle_service import (
    clear_session_activity_timestamp,
    stamp_session_activity_now,
)
from services.settings_patch_service import (
    SettingsPatchValidationError,
    apply_settings_patch_from_request,
)
from util import data_dir, notify_telegram_test


def register_ui_settings_routes(app):
    @app.route("/api/ui/settings/requires-password", methods=["GET"])
    def settings_requires_password():
        return {
            "requires": settings_gate_requires_password(),
            "has_contributor_tier": contributor_tier_configured(),
        }, 200

    @app.route("/api/ui/settings/check-access", methods=["GET"])
    def settings_check_access_route():
        if settings_check_access():
            return {"unlocked": True, "role": "admin"}, 200
        if contributor_or_admin_access():
            return {"unlocked": True, "role": "contributor"}, 200
        return {"unlocked": False}, 200

    @app.route("/api/ui/settings/verify-password", methods=["POST"])
    def settings_verify_password():
        ip = client_ip_for_rate_limit(request)
        if not _check_verify_password_rate_limit(ip):
            retry = verify_password_retry_after_seconds()
            return (
                {"ok": False, "error": "Too many attempts"},
                429,
                {"Retry-After": str(retry)},
            )
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        pw = (data.get("password") or "").strip()
        admin_pw = (app_config.get("general.settings_password") or "").strip()
        contrib_pw = (app_config.get("general.contributor_password") or "").strip()
        if not admin_pw and not contrib_pw:
            if empty_passwords_block_verify_in_production():
                _record_verify_password_failure(ip)
                return {"ok": False}, 401
            session["access_role"] = "admin"
            session["settings_unlocked"] = True
            session.permanent = True
            stamp_session_activity_now()
            _clear_verify_password_attempts(ip)
            return {"ok": True, "role": "admin"}, 200
        role = resolve_password_unlock_role(pw)
        if role == "admin":
            session["access_role"] = "admin"
            session["settings_unlocked"] = True
            session.permanent = True
            stamp_session_activity_now()
            _clear_verify_password_attempts(ip)
            return {"ok": True, "role": "admin"}, 200
        if role == "contributor":
            session["access_role"] = "contributor"
            session["settings_unlocked"] = False
            session.permanent = True
            stamp_session_activity_now()
            _clear_verify_password_attempts(ip)
            return {"ok": True, "role": "contributor"}, 200
        _record_verify_password_failure(ip)
        return {"ok": False}, 401

    @app.route("/api/ui/settings/logout", methods=["POST"])
    def settings_logout():
        """Сброс сессии входа (оператор/админ) — для смены пользователя за одним ПК."""
        session.pop("access_role", None)
        session.pop("settings_unlocked", None)
        clear_session_activity_timestamp()
        return {"ok": True}, 200

    @app.route("/api/ui/settings", methods=["GET"])
    def get_settings():
        if not settings_read_access():
            return {"error": "Password required"}, 403
        from services.cache import redis_url_effective_masked_for_api

        cfg = app_config.prepare_settings_for_api(app_config.config)
        perf = cfg.setdefault("performance", {})
        perf["redis_url_effective_masked"] = redis_url_effective_masked_for_api()
        return cfg, 200

    @app.route("/api/ui/settings/ebird-species-mapping-suggestions", methods=["GET"])
    def ebird_species_mapping_suggestions():
        if not settings_check_access():
            return {"error": "Password required"}, 403
        from services.ebird_mapping_suggestions import build_ebird_mapping_suggestions

        return build_ebird_mapping_suggestions(), 200

    @app.route("/api/ui/settings/yaml-export", methods=["GET"])
    def settings_yaml_export():
        """Скачать user_config: safe — ***, оператор+админ; full — с секретами, только админ (+MCP)."""
        mode = (request.args.get("mode") or "safe").strip().lower()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if mode == "full":
            if not admin_settings_yaml_access():
                return {"error": "Forbidden"}, 403
            ack = (request.args.get("ack") or "").strip().lower()
            if ack not in ("full", "1", "yes", "true"):
                return {
                    "error": "Full export includes secrets; add query ack=full to confirm.",
                }, 400
            path = app_config.user_config_file
            if not os.path.isfile(path):
                body = "# birdlense user_config (empty)\n"
            else:
                with open(path, "r", encoding="utf-8") as f:
                    body = f.read()
            return Response(
                body,
                mimetype="application/x-yaml",
                headers={
                    "Content-Disposition": f'attachment; filename="user_config_full_{stamp}.yaml"',
                },
            )
        if mode != "safe":
            return {"error": "mode must be safe or full"}, 400
        if not settings_yaml_safe_export_access():
            return {"error": "Forbidden"}, 403
        raw = app_config.load_raw_user_config_dict()
        masked = app_config.mask_sensitive_in_user_tree(raw)
        body = yaml.safe_dump(
            masked,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        return Response(
            body,
            mimetype="application/x-yaml",
            headers={
                "Content-Disposition": f'attachment; filename="user_config_safe_{stamp}.yaml"',
            },
        )

    @app.route("/api/ui/settings/yaml-import", methods=["POST"])
    def settings_yaml_import():
        """Импорт YAML в user_config: merge с текущим user, *** не перезаписывают секреты."""
        if not admin_settings_yaml_access():
            return {"error": "Forbidden"}, 403
        f = request.files.get("file")
        if not f or not f.filename:
            return {"error": "Missing file"}, 400
        try:
            raw = f.read().decode("utf-8")
            incoming = yaml.safe_load(raw)
        except (UnicodeDecodeError, yaml.YAMLError) as e:
            return {"error": "Invalid YAML: %s" % e}, 400
        if not isinstance(incoming, dict):
            return {"error": "YAML root must be a mapping"}, 400
        incoming = app_config.filter_sensitive_placeholders(incoming)
        existing = app_config.load_raw_user_config_dict()
        merged_user = app_config.merge_dicts(existing, incoming)
        if migrate_legacy_homeassistant_from_weather(merged_user):
            pass
        issues = app_config.validate_user_config_tree(merged_user)
        if issues:
            return {"error": "Validation failed", "issues": issues}, 400
        try:
            app_config._persist_raw_user_config(merged_user)
            app_config.reload()
        except OSError as e:
            app.logger.exception("YAML import persist failed")
            return {"error": str(e)}, 500
        bust_response_caches()
        cache_delete_prefix("ebird_region_comparison:")
        from services.cache import reset_redis_client

        reset_redis_client()
        return {
            "ok": True,
            "message": "Settings imported. Restart processor if it should pick up changes.",
        }, 200

    @app.route("/api/ui/settings", methods=["PATCH"])
    def update_settings():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        updates, v_err = parse_request_json_dict(request)
        if v_err is not None:
            return v_err, 400
        if not updates:
            return {"error": "No data provided for update"}, 400
        try:
            payload = apply_settings_patch_from_request(
                updates,
                access_role=session.get("access_role"),
                contributor_tier_configured=contributor_tier_configured(),
            )
            return payload, 200
        except SettingsPatchValidationError as e:
            return {"error": "Validation failed", "issues": e.issues}, 400

        except Exception:
            app.logger.exception("Update settings failed")
            return {"error": "Failed to save settings"}, 500

    @app.route("/api/ui/notify/test", methods=["POST"])
    def notify_test():
        if not settings_check_access():
            return {"error": "Password required"}, 403
        if not app_config.get("general.enable_notifications"):
            return {"error": "Notifications disabled"}, 400
        token = (app_config.get("notifications.telegram_bot_token") or "").strip()
        chat_id = (app_config.get("notifications.telegram_chat_id") or "").strip()
        if not token or not chat_id:
            return {"error": "Telegram bot token or chat_id not configured"}, 400
        success, err = notify_telegram_test()
        if success:
            return {"message": "Test notification sent"}, 200
        return {"error": err or "Failed"}, 500

    @app.route("/api/ui/restart-processor", methods=["POST"])
    def restart_processor():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        try:
            write_processor_restart_flag(data_dir())
            return {"message": "Processor restart requested"}, 200
        except Exception:
            app.logger.exception("Restart processor failed")
            return {"error": "Failed to restart processor"}, 500

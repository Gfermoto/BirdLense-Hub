"""Политика доступа к настройкам без Flask request (#293)."""

from __future__ import annotations

from app_config.app_config import app_config
from services.runtime_env import is_production_runtime
from services.ui_password_service import verify_ui_password


def settings_gate_requires_password() -> bool:
    """Нужен ли ввод пароля для unlock (как GET requires-password)."""
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    return bool(admin_pw or contrib_pw)


def contributor_tier_configured() -> bool:
    """Задан ли пароль оператора (contributor tier)."""
    return bool((app_config.get("general.contributor_password") or "").strip())


def is_production_env() -> bool:
    """True если FLASK_ENV или BIRDLENSE_ENV указывают на production."""
    return is_production_runtime()


def empty_passwords_block_verify_in_production() -> bool:
    """Оба пароля пусты — verify-password должен разрешить (открытый доступ)."""
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    return bool(admin_pw or contrib_pw)


def resolve_password_unlock_role(submitted_password: str) -> str | None:
    """Сопоставить пароль роли (как verify-password): admin, contributor или None."""
    pw = (submitted_password or "").strip()
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    if verify_ui_password(pw, admin_pw):
        return "admin"
    if contrib_pw and verify_ui_password(pw, contrib_pw):
        return "contributor"
    return None

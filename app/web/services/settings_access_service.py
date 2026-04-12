"""Политика доступа к настройкам без Flask request (#293)."""

from __future__ import annotations

import os
import secrets

from app_config.app_config import app_config


def settings_gate_requires_password() -> bool:
    """Нужен ли ввод пароля для unlock (как GET requires-password)."""
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    if not admin_pw and not contrib_pw:
        return os.environ.get("FLASK_ENV") == "production" or os.environ.get("BIRDLENSE_ENV") == "production"
    return bool(admin_pw or contrib_pw)


def contributor_tier_configured() -> bool:
    """Задан ли пароль оператора (contributor tier)."""
    return bool((app_config.get("general.contributor_password") or "").strip())


def is_production_env() -> bool:
    """True если FLASK_ENV или BIRDLENSE_ENV указывают на production."""
    return os.environ.get("FLASK_ENV") == "production" or os.environ.get("BIRDLENSE_ENV") == "production"


def empty_passwords_block_verify_in_production() -> bool:
    """Оба пароля пусты и production — verify-password должен отказать."""
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    if admin_pw or contrib_pw:
        return False
    return is_production_env()


def resolve_password_unlock_role(submitted_password: str) -> str | None:
    """Сопоставить пароль роли (как verify-password): admin, contributor или None."""
    pw = (submitted_password or "").strip()
    admin_pw = (app_config.get("general.settings_password") or "").strip()
    contrib_pw = (app_config.get("general.contributor_password") or "").strip()
    if secrets.compare_digest(pw, admin_pw):
        return "admin"
    if contrib_pw and secrets.compare_digest(pw, contrib_pw):
        return "contributor"
    return None

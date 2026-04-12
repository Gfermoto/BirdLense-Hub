"""UI settings / contributor passwords: bcrypt hashes vs legacy plaintext (#278)."""

from __future__ import annotations

import copy
import logging
import secrets

import bcrypt

logger = logging.getLogger(__name__)

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def stored_ui_password_is_bcrypt(stored: str | None) -> bool:
    s = (stored or "").strip()
    return bool(s) and s.startswith(_BCRYPT_PREFIXES)


def verify_ui_password(plain: str | None, stored: str | None) -> bool:
    """Constant-time friendly: bcrypt.checkpw for hashes; else secrets.compare_digest for plaintext."""
    if stored is None:
        return False
    sp = str(stored).strip()
    if not sp:
        return False
    candidate = (plain or "").strip()
    if not candidate:
        return False
    if stored_ui_password_is_bcrypt(sp):
        try:
            return bcrypt.checkpw(candidate.encode("utf-8"), sp.encode("ascii"))
        except (ValueError, TypeError) as e:
            logger.debug("bcrypt.checkpw failed: %s", e)
            return False
    try:
        return secrets.compare_digest(candidate, sp)
    except (TypeError, ValueError):
        return False


def hash_ui_password_plain(plain: str) -> str:
    """Hash a new plaintext password for storage in user_config (bcrypt, cost 12)."""
    s = (plain or "").strip()
    if not s:
        raise ValueError("empty password")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(s.encode("utf-8"), salt).decode("ascii")


def hash_password_fields_in_updates(updates: dict) -> dict:
    """Before merge/save: replace general.settings_password / contributor_password plaintext with bcrypt."""
    out = copy.deepcopy(updates)
    gen = out.get("general")
    if not isinstance(gen, dict):
        return out
    for key in ("settings_password", "contributor_password"):
        if key not in gen:
            continue
        val = gen[key]
        if val is None or not isinstance(val, str):
            continue
        raw = val.strip()
        if not raw:
            continue
        if stored_ui_password_is_bcrypt(raw):
            continue
        try:
            gen[key] = hash_ui_password_plain(raw)
        except ValueError:
            pass
    return out

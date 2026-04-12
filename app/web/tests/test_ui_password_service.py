"""UI password verify + bcrypt hashing (#278)."""

import bcrypt

from services.ui_password_service import (
    hash_password_fields_in_updates,
    hash_ui_password_plain,
    stored_ui_password_is_bcrypt,
    verify_ui_password,
)


def test_verify_plaintext_legacy():
    assert verify_ui_password("secret", "secret") is True
    assert verify_ui_password("wrong", "secret") is False
    assert verify_ui_password("", "secret") is False


def test_verify_bcrypt_roundtrip():
    h = hash_ui_password_plain("my-password")
    assert stored_ui_password_is_bcrypt(h)
    assert verify_ui_password("my-password", h) is True
    assert verify_ui_password("other", h) is False


def test_verify_bcrypt_prefixed_string():
    # Known test vector format (bcrypt $2b$)
    h = bcrypt.hashpw(b"x", bcrypt.gensalt(rounds=4, prefix=b"2b")).decode("ascii")
    assert verify_ui_password("x", h) is True


def test_hash_password_fields_in_updates_replaces_plaintext():
    updates = {
        "general": {
            "settings_password": "  new-admin  ",
            "contributor_password": "contrib-plain",
        }
    }
    out = hash_password_fields_in_updates(updates)
    sp = out["general"]["settings_password"]
    cp = out["general"]["contributor_password"]
    assert stored_ui_password_is_bcrypt(sp)
    assert stored_ui_password_is_bcrypt(cp)
    assert verify_ui_password("new-admin", sp)
    assert verify_ui_password("contrib-plain", cp)
    # Deep copy: input unchanged semantics — actually function mutates deep copy
    assert updates["general"]["settings_password"] == "  new-admin  "


def test_hash_password_fields_leaves_bcrypt_unchanged():
    h = hash_ui_password_plain("same")
    updates = {"general": {"settings_password": h}}
    out = hash_password_fields_in_updates(updates)
    assert out["general"]["settings_password"] == h

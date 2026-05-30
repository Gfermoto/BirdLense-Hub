"""Tests for scripts/verify_owasp_api_controls.py (#531)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "verify_owasp_api_controls.py"
    spec = importlib.util.spec_from_file_location(
        "verify_owasp_api_controls",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_owasp_api_controls"] = mod
    spec.loader.exec_module(mod)
    return mod


def _readiness(strict: str, flask: str, processor: str) -> dict:
    return {
        "security_gates": {
            "items": [
                {"id": "strict_api_auth", "status": strict},
                {"id": "flask_secret_key", "status": flask},
                {"id": "processor_secret", "status": processor},
            ]
        }
    }


def test_owasp_map_ok_when_guards_and_secrets_ok():
    mod = _load_mod()
    report = mod.evaluate_controls(
        readiness_payload=_readiness("ok", "ok", "ok"),
        protected_unauth_status=403,
        protected_auth_status=200,
    )
    assert report["ok"] is True
    assert report["coverage"]["covered"] == report["coverage"]["total"]


def test_owasp_map_fails_when_auth_guards_not_enforced():
    mod = _load_mod()
    report = mod.evaluate_controls(
        readiness_payload=_readiness("ok", "ok", "ok"),
        protected_unauth_status=200,
        protected_auth_status=200,
    )
    assert report["ok"] is False
    assert report["inputs"]["authz_enforced"] is False


def test_owasp_map_fails_when_strict_auth_or_secrets_bad():
    mod = _load_mod()
    report = mod.evaluate_controls(
        readiness_payload=_readiness("warn", "ok", "error"),
        protected_unauth_status=401,
        protected_auth_status=200,
    )
    assert report["ok"] is False
    assert report["inputs"]["strict_api_auth_ok"] is False
    assert report["inputs"]["secrets_ok"] is False

"""Bug: invalid user_config YAML must not run migrations."""

from __future__ import annotations

import yaml

from app_config import app_config as ac_mod


def test_invalid_user_yaml_skips_migrations(tmp_path, monkeypatch):
    user_path = tmp_path / "user_config.yaml"
    user_path.write_text("processor:\n  min_confidence_binary: [broken\n", encoding="utf-8")
    default_path = tmp_path / "default_config.yaml"
    default_path.write_text(yaml.safe_dump({"processor": {"min_confidence_binary": 0.1}}), encoding="utf-8")

    monkeypatch.setattr(ac_mod.app_config, "user_config_file", str(user_path))
    monkeypatch.setattr(ac_mod.app_config, "default_config_file", str(default_path))

    merged = ac_mod.app_config.load_and_merge_configs()

    assert "_meta" not in (merged.get("_meta") or {})
    assert user_path.read_text(encoding="utf-8") == "processor:\n  min_confidence_binary: [broken\n"
    assert merged.get("processor", {}).get("min_confidence_binary") == 0.1


def test_valid_user_yaml_is_merged_not_discarded(tmp_path, monkeypatch):
    user_path = tmp_path / "user_config.yaml"
    user_path.write_text(
        yaml.safe_dump({"processor": {"min_confidence_binary": 0.42}}),
        encoding="utf-8",
    )
    default_path = tmp_path / "default_config.yaml"
    default_path.write_text(
        yaml.safe_dump({"processor": {"min_confidence_binary": 0.1}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(ac_mod.app_config, "user_config_file", str(user_path))
    monkeypatch.setattr(ac_mod.app_config, "default_config_file", str(default_path))

    merged = ac_mod.app_config.load_and_merge_configs()

    assert merged.get("processor", {}).get("min_confidence_binary") == 0.42

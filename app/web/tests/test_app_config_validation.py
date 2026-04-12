"""Проверки validate_merged_config (#265 фаза C)."""

from app_config.app_config import validate_merged_config


def test_validate_merged_config_empty_ok():
    """Пустой merged-конфиг валиден."""
    assert validate_merged_config({}) == []


def test_validate_merged_config_nested_sections_ok():
    """Типичные секции-mapping проходят проверку."""
    merged = {
        "mqtt": {"broker": "localhost"},
        "processor": {"detection_device": "cpu"},
    }
    assert validate_merged_config(merged) == []


def test_validate_merged_config_rejects_scalar_section():
    """Скаляр вместо mapping на верхнем уровне даёт ошибку."""
    issues = validate_merged_config({"mqtt": "not-a-dict"})
    assert any("mqtt" in msg for msg in issues)

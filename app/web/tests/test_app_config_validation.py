"""Проверки validate_merged_config (#265 фаза C)."""

from app_config.app_config import validate_merged_config, validate_merged_config_semantics


def test_validate_merged_config_empty_ok():
    """Пустой merged-конфиг валиден."""
    assert validate_merged_config({}) == []


def test_validate_merged_config_nested_sections_ok():
    """Типичные секции-mapping проходят проверку."""
    merged = {
        "mqtt": {"broker": "localhost"},
        "processor": {"detection_device": "cpu"},
        "storage": {"recordings_mirror": {"enabled": False}},
    }
    assert validate_merged_config(merged) == []


def test_validate_merged_config_rejects_scalar_section():
    """Скаляр вместо mapping на верхнем уровне даёт ошибку."""
    issues = validate_merged_config({"mqtt": "not-a-dict"})
    assert any("mqtt" in msg for msg in issues)


def test_validate_merged_config_semantics_store_le_process_ok():
    merged = {
        "detection": {"min_confidence_to_store": 0.25},
        "processor": {"min_confidence_to_process": 0.30},
    }
    assert validate_merged_config_semantics(merged) == []


def test_validate_merged_config_semantics_store_gt_process_fails():
    merged = {
        "detection": {"min_confidence_to_store": 0.35},
        "processor": {"min_confidence_to_process": 0.29},
    }
    issues = validate_merged_config_semantics(merged)
    assert len(issues) == 1
    assert "0.35" in issues[0] and "0.29" in issues[0]


def test_validate_merged_config_semantics_non_numeric_store():
    merged = {
        "detection": {"min_confidence_to_store": "nope"},
        "processor": {"min_confidence_to_process": 0.3},
    }
    issues = validate_merged_config_semantics(merged)
    assert any("numeric" in msg for msg in issues)


def test_validate_merged_config_semantics_equal_is_ok():
    merged = {
        "detection": {"min_confidence_to_store": 0.29},
        "processor": {"min_confidence_to_process": 0.29},
    }
    assert validate_merged_config_semantics(merged) == []

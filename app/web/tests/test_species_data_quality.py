"""Качество каталога видов: дубликаты, отчёт."""

import pytest

from services.species_data_quality_service import build_data_quality_report


def test_build_report_has_structure(app):
    from models import db

    with app.app_context():
        rep = build_data_quality_report(
            db.session,
            duplicate_group_limit=5,
        )
    assert 'species_total' in rep
    assert 'duplicate_name_group_count' in rep
    assert 'duplicate_name_groups' in rep
    assert 'hints' in rep

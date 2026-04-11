"""Регрессия: число SQL на горячих путях без роста O(N) по строкам (#294)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from services.overview_service import get_overview_data


def _sql_statement_count(engine, fn) -> int:
    statements: list[object] = []

    def _recv(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', _recv)
    try:
        fn()
    finally:
        event.remove(engine, 'before_cursor_execute', _recv)
    return len(statements)


class TestOverviewSqlBudget:
    """Обзор: цикл по визитам без отдельного SELECT species на каждую строку."""

    def test_get_overview_data_query_count_bounded_with_many_visits(self, app):
        """Много визитов одного вида — запросов к БД не O(N) по числу визитов."""
        from models import Species, SpeciesVisit, Video, db

        day = datetime(2026, 4, 10, 12, 0, 0)
        start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = day.replace(
            hour=23, minute=59, second=59, microsecond=999999,
        )

        with app.app_context():
            species = Species(name='Budget Finch')
            db.session.add(species)
            db.session.flush()
            for i in range(12):
                t0 = start_of_day + timedelta(minutes=i * 5)
                db.session.add(
                    SpeciesVisit(
                        species_id=species.id,
                        start_time=t0,
                        end_time=t0 + timedelta(minutes=2),
                        max_simultaneous=1,
                    ),
                )
            video = Video(
                processor_version='test',
                start_time=start_of_day,
                end_time=start_of_day + timedelta(hours=1),
                video_path='data/recordings/2026/04/10/120000/budget.mp4',
                weather_temp=10.0,
            )
            db.session.add(video)
            db.session.commit()

            engine = db.engine

            def run():
                get_overview_data(db.session, start_of_day, end_of_day)

            n = _sql_statement_count(engine, run)
            # Без contains_eager — десятки SELECT; с eager — порядка одного десятка.
            assert n <= 22, f'expected <= 22 SQL statements, got {n}'


class TestTimelineSqlBudget:
    """Таймлайн: несколько VideoSpecies на визит — eager load, не N+1 по video."""

    def test_build_merged_timeline_query_count_bounded(self, app):
        """Несколько визитов с детекциями — ограниченное число round-trips."""
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        from routes.ui_timeline_helpers import build_merged_timeline_items

        start_dt = datetime(2026, 4, 11, 8, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(2026, 4, 11, 20, 0, 0, tzinfo=timezone.utc)
        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)

        with app.app_context():
            sp = Species(name='Timeline Budget Bird')
            db.session.add(sp)
            db.session.flush()
            for vix in range(4):
                visit = SpeciesVisit(
                    species_id=sp.id,
                    start_time=start_naive + timedelta(minutes=vix * 30),
                    end_time=start_naive + timedelta(minutes=vix * 30 + 10),
                    max_simultaneous=1,
                )
                db.session.add(visit)
                db.session.flush()
                for j in range(2):
                    vid = Video(
                        processor_version='test',
                        start_time=start_naive + timedelta(minutes=vix * 30 + j),
                        end_time=start_naive + timedelta(
                            minutes=vix * 30 + j + 5,
                        ),
                        video_path=(
                            f'data/recordings/2026/04/11/tb{vix}_{j}.mp4'
                        ),
                    )
                    db.session.add(vid)
                    db.session.flush()
                    db.session.add(
                        VideoSpecies(
                            video_id=vid.id,
                            species_id=sp.id,
                            species_visit_id=visit.id,
                            start_time=0.0,
                            end_time=4.0,
                            confidence=0.9,
                            source='video',
                        ),
                    )
            db.session.commit()

            engine = db.engine

            def run():
                build_merged_timeline_items(db.session, start_naive, end_naive)

            n = _sql_statement_count(engine, run)
            assert n <= 28, f'expected <= 28 SQL statements, got {n}'

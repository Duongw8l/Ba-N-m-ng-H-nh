from collections.abc import Callable
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Engine, inspect, text

from app.core.base import Base
from app.core.config import get_settings

pytestmark = pytest.mark.db

BUSINESS_TABLES = {
    "users",
    "school_years",
    "classes",
    "students",
    "class_students",
    "subjects",
    "teaching_assignments",
    "assessments",
    "attendance",
    "conduct_results",
    "exam_registrations",
    "risk_alerts",
    "reports",
    "regulation_chunks",
    "ai_logs",
}
EXPECTED_SETTING_KEYS = {
    "coef_midterm",
    "coef_final",
    "coef_year_semester2",
    "max_absent_sessions",
    "absent_warning_notice",
    "absent_warning_high",
    "score_threshold_fail",
    "score_threshold_pass",
    "score_threshold_fair",
    "score_threshold_good",
    "level_min_subjects",
    "regular_assessment_count",
}
VIEW_COLUMNS = [
    "class_student_id",
    "class_id",
    "student_id",
    "subject_id",
    "assessment_type",
    "periods_per_year",
    "semester",
    "tx_count",
    "tx_sum",
    "gk_score",
    "ck_score",
    "comment_result",
]


def test_upgrade_head_creates_15_business_tables_plus_settings(db_conn: Connection) -> None:
    tables = set(inspect(db_conn).get_table_names())

    assert tables == BUSINESS_TABLES | {"settings", "alembic_version"}
    assert len(BUSINESS_TABLES) == 15


def test_upgrade_head_enables_vector_extension_and_view(db_conn: Connection) -> None:
    extension = db_conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
    assert extension.scalar() == 1
    assert "v_subject_average" in inspect(db_conn).get_view_names()


def test_embedding_column_dimension_follows_configuration(db_conn: Connection) -> None:
    column_type = db_conn.execute(
        text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'regulation_chunks'::regclass AND attname = 'embedding'"
        )
    ).scalar_one()

    assert column_type == f"vector({get_settings().embedding_dim})"


def test_default_settings_are_loaded_by_migration(db_conn: Connection) -> None:
    rows = db_conn.execute(text("SELECT key, value FROM settings")).all()
    values = {key: value for key, value in rows}

    assert set(values) == EXPECTED_SETTING_KEYS
    assert values["coef_midterm"] == 2
    assert values["coef_final"] == 3
    assert values["coef_year_semester2"] == 2
    assert values["max_absent_sessions"] == 45
    assert (values["absent_warning_notice"], values["absent_warning_high"]) == (30, 40)
    assert Decimal(str(values["score_threshold_fail"])) == Decimal("3.5")
    assert Decimal(str(values["score_threshold_pass"])) == Decimal("5.0")
    assert Decimal(str(values["score_threshold_fair"])) == Decimal("6.5")
    assert Decimal(str(values["score_threshold_good"])) == Decimal("8.0")
    assert values["level_min_subjects"] == 6
    assert values["regular_assessment_count"] == [
        {"max_periods": 35, "count": 2},
        {"max_periods": 70, "count": 3},
        {"max_periods": None, "count": 4},
    ]


def test_models_match_migrations(db_conn: Connection) -> None:
    context = MigrationContext.configure(db_conn, opts={"compare_type": True})

    assert compare_metadata(context, Base.metadata) == []


def test_downgrade_to_base_then_upgrade_again_is_clean(
    fresh_database: Callable[[], Engine],
    upgrade_db: Callable[[Engine], None],
    downgrade_db: Callable[[Engine], None],
) -> None:
    engine = fresh_database()

    upgrade_db(engine)
    downgrade_db(engine)
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        assert inspect(connection).get_view_names() == []

    upgrade_db(engine)
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == (
            BUSINESS_TABLES | {"settings", "alembic_version"}
        )
        assert "v_subject_average" in inspect(connection).get_view_names()
        settings_count = connection.execute(text("SELECT count(*) FROM settings")).scalar_one()
        assert settings_count == len(EXPECTED_SETTING_KEYS)


def test_view_exposes_only_raw_aggregates_without_formula_columns(db_conn: Connection) -> None:
    columns = [column["name"] for column in inspect(db_conn).get_columns("v_subject_average")]

    assert columns == VIEW_COLUMNS


def test_view_aggregates_match_assessments_exactly(db_conn: Connection) -> None:
    totals = db_conn.execute(
        text(
            "SELECT count(*), sum(tx_count), sum(tx_sum) FROM v_subject_average "
            "WHERE assessment_type = 'score'"
        )
    ).one()
    raw = db_conn.execute(
        text(
            "SELECT count(*) FILTER (WHERE kind = 'tx'), sum(score) FILTER (WHERE kind = 'tx') "
            "FROM assessments WHERE score IS NOT NULL"
        )
    ).one()
    groups = db_conn.execute(
        text(
            "SELECT count(*) FROM (SELECT DISTINCT class_student_id, subject_id, semester "
            "FROM assessments WHERE score IS NOT NULL) AS g"
        )
    ).scalar_one()

    assert totals[0] == groups
    assert (totals[1], totals[2]) == (raw[0], raw[1])


def test_view_row_of_boundary_student_matches_hand_calculation(db_conn: Connection) -> None:
    # HS1201005: mọi đầu điểm môn Toán bằng 3,5. Học kỳ I: 4 điểm thường xuyên + giữa kỳ + cuối kỳ.
    row = db_conn.execute(
        text(
            """
            SELECT v.tx_count, v.tx_sum, v.gk_score, v.ck_score, v.comment_result
            FROM v_subject_average v
            JOIN class_students cs ON cs.id = v.class_student_id
            JOIN students s ON s.id = cs.student_id
            JOIN subjects j ON j.id = v.subject_id
            WHERE s.student_code = 'HS1201005' AND j.name = 'Toán' AND v.semester = 1
            """
        )
    ).one()

    assert row == (4, Decimal("14.00"), Decimal("3.50"), Decimal("3.50"), None)

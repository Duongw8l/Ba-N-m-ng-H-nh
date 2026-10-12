"""Seed trên PostgreSQL thật: dữ liệu nạp vào đúng, lặp lại được, và an toàn."""

import hashlib
from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal

import pytest
from sqlalchemy import Connection, Engine, select, text

from app.core.base import Base
from app.core.security import verify_password
from data.seed.load import SeedPrerequisiteMissing, SeedRefused, seed_database
from data.seed.params import SeedParams
from data.seed.people import DEV_PASSWORD

pytestmark = pytest.mark.db

# Bảng tính tay: số đầu điểm thường xuyên mỗi học kỳ theo số tiết (không dùng lại hàm của app).
EXPECTED_TX = {
    "Ngữ văn": 4,
    "Toán": 4,
    "Tiếng Anh": 4,
    "Lịch sử": 3,
    "Giáo dục quốc phòng và an ninh": 2,
    "Địa lí": 3,
    "Giáo dục kinh tế và pháp luật": 3,
    "Vật lí": 3,
    "Hóa học": 3,
    "Sinh học": 3,
    "Công nghệ": 3,
    "Tin học": 3,
}
COMMENT_SUBJECTS = {
    "Giáo dục thể chất",
    "Hoạt động trải nghiệm, hướng nghiệp",
    "Nội dung giáo dục địa phương",
    "Âm nhạc",
    "Mĩ thuật",
}
SMALL = SeedParams(seed=1, classes_per_grade=2, class_size=12)


def scalar(conn: Connection, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar_one())


def row_counts(conn: Connection) -> dict[str, int]:
    return {
        table.name: scalar(conn, f"SELECT count(*) FROM {table.name}")
        for table in Base.metadata.sorted_tables
    }


def fingerprint(engine: Engine) -> str:
    """Băm toàn bộ dữ liệu trường học (bỏ password_hash vì muối bcrypt khác nhau mỗi lần băm)."""
    digest = hashlib.sha256()
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name == "settings":
                continue
            columns = [c for c in table.c if (table.name, c.name) != ("users", "password_hash")]
            digest.update(table.name.encode())
            for row in connection.execute(select(*columns).order_by(table.c.id)):
                digest.update(repr(tuple(row)).encode())
    return digest.hexdigest()


# --- Dữ liệu seed mặc định (360 học sinh) -----------------------------------------------------


def test_row_counts_match_the_default_parameters(db_conn: Connection) -> None:
    counts = row_counts(db_conn)

    assert counts["school_years"] == 1
    assert counts["subjects"] == 17
    assert counts["classes"] == 9
    assert counts["students"] == counts["class_students"] == 360
    assert counts["teaching_assignments"] == 9 * 12
    assert counts["users"] == 60
    assert counts["attendance"] == 360 * 175
    assert counts["conduct_results"] == 720
    assert counts["exam_registrations"] == 480
    # Các bảng do giai đoạn sau sinh thì để trống.
    assert (counts["risk_alerts"], counts["reports"], counts["ai_logs"]) == (0, 0, 0)
    assert counts["regulation_chunks"] == 0
    assert counts["settings"] == 12


def test_every_student_subject_pair_has_all_scores_by_hand_table(db_conn: Connection) -> None:
    rows = db_conn.execute(
        text(
            """
            SELECT j.name, a.semester, a.class_student_id,
                   count(*) FILTER (WHERE a.kind = 'tx') AS tx,
                   count(*) FILTER (WHERE a.kind = 'gk') AS gk,
                   count(*) FILTER (WHERE a.kind = 'ck') AS ck,
                   count(*) FILTER (WHERE a.comment_result IS NOT NULL) AS comments
            FROM assessments a JOIN subjects j ON j.id = a.subject_id
            GROUP BY j.name, a.semester, a.class_student_id
            """
        )
    ).all()

    assert len(rows) == 360 * 12 * 2
    for name, _semester, _student, tx, gk, ck, comments in rows:
        if name in EXPECTED_TX:
            assert (tx, gk, ck, comments) == (EXPECTED_TX[name], 1, 1, 0), name
        else:
            assert name in COMMENT_SUBJECTS
            assert (tx, gk, ck, comments) == (0, 0, 1, 1), name


def test_each_student_has_exactly_the_subjects_assigned_to_the_class(db_conn: Connection) -> None:
    missing = scalar(
        db_conn,
        """
        SELECT count(*) FROM (
            SELECT cs.id, ta.subject_id FROM class_students cs
            JOIN teaching_assignments ta ON ta.class_id = cs.class_id
            EXCEPT SELECT class_student_id, subject_id FROM assessments
        ) AS x
        """,
    )
    extra = scalar(
        db_conn,
        """
        SELECT count(*) FROM (
            SELECT class_student_id, subject_id FROM assessments
            EXCEPT SELECT cs.id, ta.subject_id FROM class_students cs
            JOIN teaching_assignments ta ON ta.class_id = cs.class_id
        ) AS x
        """,
    )

    assert (missing, extra) == (0, 0)


def test_there_are_at_risk_students_in_the_expected_proportions(db_conn: Connection) -> None:
    heavy = scalar(
        db_conn,
        """
        SELECT count(*) FROM (
            SELECT class_student_id FROM attendance
            WHERE status IN ('absent_excused', 'absent_unexcused')
            GROUP BY class_student_id HAVING count(*) BETWEEN 30 AND 50
        ) AS t
        """,
    )
    low = scalar(
        db_conn,
        "SELECT count(DISTINCT class_student_id) FROM assessments WHERE score < 3.5",
    )
    low_flat_subject = scalar(
        db_conn,
        """
        SELECT count(DISTINCT class_student_id) FROM (
            SELECT class_student_id, subject_id FROM assessments
            WHERE score IS NOT NULL GROUP BY class_student_id, subject_id
            HAVING max(score) < 3.5
        ) AS t
        """,
    )
    mostly_present = scalar(
        db_conn,
        """
        SELECT count(*) FROM (
            SELECT cs.id FROM class_students cs
            LEFT JOIN attendance a ON a.class_student_id = cs.id
                AND a.status IN ('absent_excused', 'absent_unexcused')
            GROUP BY cs.id HAVING count(a.id) <= 10
        ) AS t
        """,
    )

    assert heavy == 18  # 5% của 360
    assert low == low_flat_subject == 29  # 8% của 360, mọi đầu điểm của một môn đều dưới 3,5
    assert mostly_present >= 0.9 * 360


def test_boundary_students_exist(db_conn: Connection) -> None:
    exactly_45_absences = scalar(
        db_conn,
        """
        SELECT count(*) FROM (
            SELECT class_student_id FROM attendance
            WHERE status IN ('absent_excused', 'absent_unexcused')
            GROUP BY class_student_id HAVING count(*) = 45
        ) AS t
        """,
    )

    def students_with_flat_subject(value: str) -> int:
        return scalar(
            db_conn,
            f"""
            SELECT count(DISTINCT class_student_id) FROM (
                SELECT class_student_id FROM assessments WHERE score IS NOT NULL
                GROUP BY class_student_id, subject_id
                HAVING min(score) = {value} AND max(score) = {value}
            ) AS t
            """,
        )

    assert exactly_45_absences == 1
    assert students_with_flat_subject("3.5") >= 1
    assert students_with_flat_subject("5.0") >= 1


def test_demo_characters_exist_in_class_11a2(db_conn: Connection) -> None:
    rows = db_conn.execute(
        text(
            """
            SELECT s.student_code, s.full_name, c.name,
                   (SELECT count(*) FROM attendance a WHERE a.class_student_id = cs.id
                       AND a.status IN ('absent_excused', 'absent_unexcused')) AS absent
            FROM students s
            JOIN class_students cs ON cs.student_id = s.id
            JOIN classes c ON c.id = cs.class_id
            WHERE s.student_code IN ('HS1102001', 'HS1102002')
            ORDER BY s.student_code
            """
        )
    ).all()
    an_count = scalar(
        db_conn,
        """
        SELECT count(*) FROM students s
        JOIN class_students cs ON cs.student_id = s.id
        JOIN classes c ON c.id = cs.class_id
        WHERE c.name = '11A2' AND s.full_name LIKE '% An'
        """,
    )

    assert [(r[0], r[1], r[2]) for r in rows] == [
        ("HS1102001", "Trần Minh An", "11A2"),
        ("HS1102002", "Lê Hoàng Bảo", "11A2"),
    ]
    assert rows[0][3] == 38
    assert an_count == 1


def test_accounts_cover_all_roles_and_cumulative_permissions(db_conn: Connection) -> None:
    roles = dict(db_conn.execute(text("SELECT role, count(*) FROM users GROUP BY role")).all())
    homeroom_and_subject_teachers = scalar(
        db_conn,
        """
        SELECT count(*) FROM users u
        WHERE EXISTS (SELECT 1 FROM classes c WHERE c.homeroom_teacher_id = u.id)
          AND EXISTS (
              SELECT 1 FROM teaching_assignments ta
              WHERE ta.teacher_id = u.id
                AND ta.class_id NOT IN (SELECT id FROM classes WHERE homeroom_teacher_id = u.id)
          )
        """,
    )
    classes_without_homeroom = scalar(
        db_conn, "SELECT count(*) FROM classes WHERE homeroom_teacher_id IS NULL"
    )
    password_hash = db_conn.execute(
        text("SELECT password_hash FROM users WHERE email = 'admin@example.com'")
    ).scalar_one()

    assert roles == {"admin": 1, "principal": 2, "teacher": 57}
    assert homeroom_and_subject_teachers >= 1
    assert classes_without_homeroom == 0
    assert verify_password(DEV_PASSWORD, password_hash)


def test_personal_data_is_fake(db_conn: Connection) -> None:
    real_looking_emails = scalar(
        db_conn, "SELECT count(*) FROM users WHERE email NOT LIKE '%@example.com'"
    )
    valid_looking_phones = scalar(
        db_conn, "SELECT count(*) FROM students WHERE guardian_phone NOT LIKE '0000%'"
    )

    assert real_looking_emails == 0
    assert valid_looking_phones == 0


def test_conduct_has_only_semester_results_and_grade_12_has_exam_registrations(
    db_conn: Connection,
) -> None:
    periods = {r[0] for r in db_conn.execute(text("SELECT DISTINCT period FROM conduct_results"))}
    exam_students = scalar(
        db_conn,
        """
        SELECT count(DISTINCT er.class_student_id) FROM exam_registrations er
        JOIN class_students cs ON cs.id = er.class_student_id
        JOIN classes c ON c.id = cs.class_id WHERE c.grade_level = 12
        """,
    )
    exam_outside_grade_12 = scalar(
        db_conn,
        """
        SELECT count(*) FROM exam_registrations er
        JOIN class_students cs ON cs.id = er.class_student_id
        JOIN classes c ON c.id = cs.class_id WHERE c.grade_level <> 12
        """,
    )

    assert periods == {"hk1", "hk2"}
    assert exam_students == 120
    assert exam_outside_grade_12 == 0


def test_scores_use_exact_decimals(db_conn: Connection) -> None:
    value = db_conn.execute(
        text(
            "SELECT DISTINCT score FROM assessments a JOIN class_students cs "
            "ON cs.id = a.class_student_id JOIN students s ON s.id = cs.student_id "
            "JOIN subjects j ON j.id = a.subject_id "
            "WHERE s.student_code = 'HS1201005' AND j.name = 'Toán'"
        )
    ).scalar_one()

    assert value == Decimal("3.50")


# --- Lặp lại được, an toàn (dùng database tạm, tham số nhỏ cho nhanh) -------------------------


def test_seed_twice_with_same_params_gives_identical_data_and_other_seed_differs(
    fresh_database: Callable[[], Engine], upgrade_db: Callable[[Engine], None]
) -> None:
    engine = fresh_database()
    upgrade_db(engine)

    first_summary = seed_database(engine, SMALL)
    first = fingerprint(engine)
    second_summary = seed_database(engine, SMALL)  # chạy lại không lỗi, xoá dữ liệu cũ
    second = fingerprint(engine)
    seed_database(engine, SeedParams(seed=2, classes_per_grade=2, class_size=12))
    other = fingerprint(engine)

    assert first == second
    assert first_summary == second_summary
    assert first_summary.row_counts["students"] == 72
    assert other != first


def test_seed_refuses_production_and_leaves_data_untouched(
    fresh_database: Callable[[], Engine], upgrade_db: Callable[[Engine], None]
) -> None:
    engine = fresh_database()
    upgrade_db(engine)
    seed_database(engine, SMALL)
    before = fingerprint(engine)

    with pytest.raises(SeedRefused, match="production"):
        seed_database(
            engine, SeedParams(seed=99, classes_per_grade=2, class_size=12), app_env="production"
        )

    assert fingerprint(engine) == before


def test_seed_requires_migrations_first(fresh_database: Callable[[], Engine]) -> None:
    engine = fresh_database()  # chưa migrate

    with pytest.raises(SeedPrerequisiteMissing, match="make migrate"):
        seed_database(engine, SMALL)


def test_seed_keeps_settings_and_regulation_chunks(
    fresh_database: Callable[[], Engine], upgrade_db: Callable[[Engine], None]
) -> None:
    engine = fresh_database()
    upgrade_db(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE settings SET value = '50' WHERE key = 'max_absent_sessions'"))
        conn.execute(
            text(
                "INSERT INTO regulation_chunks (document_name, content) VALUES ('Thông tư 22', 'x')"
            )
        )

    seed_database(engine, SMALL)

    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT value FROM settings WHERE key = 'max_absent_sessions'")
            ).scalar_one()
            == 50
        )
        assert scalar(conn, "SELECT count(*) FROM regulation_chunks") == 1


def test_sequences_continue_after_seed_so_new_rows_do_not_collide(
    fresh_database: Callable[[], Engine], upgrade_db: Callable[[Engine], None]
) -> None:
    engine = fresh_database()
    upgrade_db(engine)
    seed_database(engine, SMALL)

    with engine.begin() as conn:
        new_id = conn.execute(
            text(
                "INSERT INTO students (student_code, full_name) "
                "VALUES ('HS-MOI-1', 'Học sinh mới') RETURNING id"
            )
        ).scalar_one()

    assert new_id == 73  # sau 72 học sinh của seed


def test_default_seed_summary_lists_every_table(db_engine: Engine) -> None:
    by_table: dict[str, int] = defaultdict(int)
    with db_engine.connect() as conn:
        by_table.update(row_counts(conn))

    assert set(by_table) == {t.name for t in Base.metadata.sorted_tables}

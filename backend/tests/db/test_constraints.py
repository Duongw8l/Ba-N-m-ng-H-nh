"""Ràng buộc ở mức DB chặn được dữ liệu sai. Dùng SQL thô: SQLAlchemy Enum tự từ chối giá trị lạ
trước khi tới DB, còn ở đây cần chứng minh chính DB chặn."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.enums import AuditAction

pytestmark = pytest.mark.db

ASSESSMENT = (
    "INSERT INTO assessments (class_student_id, subject_id, semester, kind, seq, score, "
    "comment_result) VALUES (1, 1, :semester, :kind, :seq, :score, :comment_result)"
)


@pytest.fixture
def expect_rejected(db_conn: Connection) -> Callable[..., None]:
    """Chạy một câu SQL trong savepoint và khẳng định DB từ chối (rollback đúng savepoint đó)."""

    def run(sql: str, **params: Any) -> None:
        with pytest.raises((IntegrityError, DataError)), db_conn.begin_nested():
            db_conn.execute(text(sql), params)

    return run


def assessment_params(**overrides: Any) -> dict[str, Any]:
    # seq=50 để không đụng các đầu điểm của seed.
    params: dict[str, Any] = {
        "semester": 1,
        "kind": "tx",
        "seq": 50,
        "score": 7,
        "comment_result": None,
    }
    return params | overrides


def test_audit_log_accepts_every_known_action_and_rejects_others(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    insert = "INSERT INTO audit_logs (user_id, action) VALUES (1, :action)"
    for action in (
        "view_class_students",
        "view_student_profile",
        "view_class_dashboard",
        "view_subject_scores",
        "import_confirm",
    ):
        db_conn.execute(text(insert), {"action": action})
    # Mọi hành động trong enum đều được CHECK chấp nhận (chặn quên mở rộng CHECK).
    for action in AuditAction:
        db_conn.execute(text(insert), {"action": action.value})

    expect_rejected(insert, action="xem_het_truong")


def test_valid_assessment_is_accepted(db_conn: Connection) -> None:
    db_conn.execute(text(ASSESSMENT), assessment_params())
    db_conn.execute(text(ASSESSMENT), assessment_params(seq=51, score=10))
    db_conn.execute(text(ASSESSMENT), assessment_params(seq=52, score=0))
    # Nhận xét Đạt thay cho điểm số (môn đánh giá bằng nhận xét).
    db_conn.execute(text(ASSESSMENT), assessment_params(seq=53, score=None, comment_result="pass"))


@pytest.mark.parametrize(
    "override",
    [
        {"score": 11},
        {"score": -1},
        {"score": "10.01"},
        {"semester": 3},
        {"semester": 0},
        {"kind": "xx"},
        {"seq": 0},
        {"kind": "gk", "seq": 2},  # giữa kỳ và cuối kỳ chỉ có seq 1
        {"score": None},  # thiếu cả điểm lẫn nhận xét
        {"comment_result": "pass"},  # có cả điểm lẫn nhận xét
        {"score": None, "comment_result": "dat"},
    ],
    ids=lambda override: str(override),
)
def test_invalid_assessments_are_rejected(
    expect_rejected: Callable[..., None], override: dict[str, Any]
) -> None:
    expect_rejected(ASSESSMENT, **assessment_params(**override))


def test_duplicate_assessment_key_is_rejected(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    db_conn.execute(text(ASSESSMENT), assessment_params())

    expect_rejected(ASSESSMENT, **assessment_params())


def test_attendance_rejects_unknown_status_and_duplicate_day(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    existing = db_conn.execute(
        text("SELECT class_student_id, date FROM attendance ORDER BY id LIMIT 1")
    ).one()

    expect_rejected(
        "INSERT INTO attendance (class_student_id, date, status) VALUES (2, '2030-01-01', 'nghi')"
    )
    expect_rejected(
        "INSERT INTO attendance (class_student_id, date, status) VALUES (:cs, :day, 'present')",
        cs=existing[0],
        day=existing[1],
    )


def test_duplicate_student_code_and_case_insensitive_email_are_rejected(
    expect_rejected: Callable[..., None],
) -> None:
    expect_rejected(
        "INSERT INTO students (student_code, full_name) VALUES ('HS1001001', 'Trùng mã')"
    )
    expect_rejected(
        "INSERT INTO users (email, password_hash, full_name, role) "
        "VALUES ('ADMIN@EXAMPLE.COM', 'x', 'Trùng email', 'teacher')"
    )
    expect_rejected(
        "INSERT INTO users (email, password_hash, full_name, role) "
        "VALUES ('moi@example.com', 'x', 'Sai vai trò', 'student')"
    )


def test_class_rules(expect_rejected: Callable[..., None], db_conn: Connection) -> None:
    taken = db_conn.execute(
        text("SELECT school_year_id, homeroom_teacher_id FROM classes ORDER BY id LIMIT 1")
    ).one()

    expect_rejected("INSERT INTO classes (school_year_id, grade_level, name) VALUES (1, 9, '9A1')")
    expect_rejected(
        "INSERT INTO classes (school_year_id, grade_level, name) VALUES (1, 10, '10A1')"
    )
    # Một giáo viên chỉ chủ nhiệm một lớp trong một năm học.
    expect_rejected(
        "INSERT INTO classes (school_year_id, grade_level, name, homeroom_teacher_id) "
        "VALUES (:year, 10, '10A9', :teacher)",
        year=taken[0],
        teacher=taken[1],
    )


def test_school_year_dates_must_be_ordered(expect_rejected: Callable[..., None]) -> None:
    expect_rejected(
        "INSERT INTO school_years (name, start_date, end_date) "
        "VALUES ('2030-2031', '2031-05-31', '2030-09-05')"
    )


def test_conduct_and_risk_values_are_checked(expect_rejected: Callable[..., None]) -> None:
    expect_rejected(
        "INSERT INTO conduct_results (class_student_id, period, level) VALUES (1, 'hk3', 'good')"
    )
    expect_rejected(
        "INSERT INTO conduct_results (class_student_id, period, level) VALUES (1, 'year', 'gioi')"
    )
    expect_rejected(
        "INSERT INTO risk_alerts (class_student_id, level, risk_score) VALUES (1, 'high', 1.5)"
    )
    expect_rejected("INSERT INTO risk_alerts (class_student_id, level) VALUES (1, 'critical')")


def test_report_cannot_be_approved_without_an_approver(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    draft = (
        "INSERT INTO reports (scope, target_id, type, draft_text) "
        "VALUES ('student', 1, 'contact_slip', 'Nháp')"
    )
    db_conn.execute(text(draft))
    default_status = db_conn.execute(
        text("SELECT status FROM reports ORDER BY id DESC LIMIT 1")
    ).scalar_one()
    assert default_status == "draft"

    expect_rejected(
        "INSERT INTO reports (scope, target_id, type, draft_text, status) "
        "VALUES ('student', 1, 'contact_slip', 'Nháp', 'approved')"
    )
    db_conn.execute(
        text(
            "INSERT INTO reports (scope, target_id, type, draft_text, status, approved_by) "
            "VALUES ('student', 1, 'contact_slip', 'Nháp', 'approved', 1)"
        )
    )


def test_deleting_an_enrolment_cascades_to_its_records(db_conn: Connection) -> None:
    def records() -> int:
        return db_conn.execute(
            text(
                "SELECT (SELECT count(*) FROM assessments WHERE class_student_id = 1) "
                "+ (SELECT count(*) FROM attendance WHERE class_student_id = 1) "
                "+ (SELECT count(*) FROM conduct_results WHERE class_student_id = 1)"
            )
        ).scalar_one()

    assert records() > 0
    db_conn.execute(text("DELETE FROM class_students WHERE id = 1"))
    assert records() == 0


def test_deleting_a_student_still_enrolled_is_blocked(
    expect_rejected: Callable[..., None],
) -> None:
    expect_rejected("DELETE FROM students WHERE id = 1")


def test_vector_column_rejects_wrong_dimension(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    dimension = db_conn.execute(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'regulation_chunks'::regclass AND attname = 'embedding'"
        )
    ).scalar_one()
    right = "[" + ",".join(["0.5"] * dimension) + "]"
    document_id = db_conn.execute(
        text(
            "INSERT INTO regulation_documents (name, file_name) VALUES ('a', 'a.txt') RETURNING id"
        )
    ).scalar_one()
    db_conn.execute(
        text(
            "INSERT INTO regulation_chunks (document_id, document_name, content, embedding) "
            "VALUES (:d, 'a', 'b', :v)"
        ),
        {"d": document_id, "v": right},
    )

    expect_rejected(
        "INSERT INTO regulation_chunks (document_id, document_name, content, embedding) "
        f"VALUES ({document_id}, 'a', 'b', '[1,2,3]')"
    )


def test_deleting_a_regulation_document_deletes_its_chunks(db_conn: Connection) -> None:
    document_id = db_conn.execute(
        text(
            "INSERT INTO regulation_documents (name, file_name) VALUES ('b', 'b.txt') RETURNING id"
        )
    ).scalar_one()
    db_conn.execute(
        text(
            "INSERT INTO regulation_chunks (document_id, document_name, content) "
            "VALUES (:d, 'b', 'x')"
        ),
        {"d": document_id},
    )

    db_conn.execute(text("DELETE FROM regulation_documents WHERE id = :d"), {"d": document_id})

    remaining = db_conn.execute(
        text("SELECT count(*) FROM regulation_chunks WHERE document_id = :d"), {"d": document_id}
    ).scalar_one()
    assert remaining == 0


def test_two_active_documents_with_the_same_name_are_rejected(
    db_conn: Connection, expect_rejected: Callable[..., None]
) -> None:
    db_conn.execute(
        text("INSERT INTO regulation_documents (name, file_name) VALUES ('c', 'c.txt')")
    )

    expect_rejected("INSERT INTO regulation_documents (name, file_name) VALUES ('c', 'c2.txt')")

    # Bản cũ đã hết hiệu lực thì được nạp bản mới cùng tên.
    db_conn.execute(text("UPDATE regulation_documents SET status = 'expired' WHERE name = 'c'"))
    db_conn.execute(
        text("INSERT INTO regulation_documents (name, file_name) VALUES ('c', 'c2.txt')")
    )

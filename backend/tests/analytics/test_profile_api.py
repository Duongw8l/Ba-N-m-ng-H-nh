"""Hồ sơ học sinh và biểu đồ nghỉ theo tháng của dashboard lớp (D-066).

Tài khoản (xem test_api.py): gvcn.11a2 chủ nhiệm 11A2; gv.toan.11 chủ nhiệm 11A1 và dạy Toán 11A1
đến 11A3; gv.van.11 dạy Ngữ văn khối 11; gv.toan.12 chủ nhiệm 12A1; bgh1 là BGH; admin là Admin.
Học sinh: HS1102001 (11A2, nghỉ 38 buổi), HS1102002 (11A2, Toán 3,0), HS1201003 (12A1, nghỉ 46).
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog
from app.classes.academic import Attendance
from app.classes.models import ClassStudent, Student
from app.core.enums import ABSENT_STATUSES, AuditAction

pytestmark = pytest.mark.db

Headers = Callable[[str], dict[str, str]]
ClassId = Callable[[str], int]
SubjectId = Callable[[str], int]

FORBIDDEN = {"detail": "Bạn không có quyền truy cập dữ liệu này."}


def get(client: TestClient, url: str, headers: dict[str, str] | None = None) -> Any:
    return client.get(url, headers=headers or {})


@pytest.fixture
def student_id(db_session: Session) -> Callable[[str], int]:
    def find(code: str) -> int:
        found = db_session.scalar(select(Student.id).where(Student.student_code == code))
        assert found is not None, f"Không có học sinh seed {code}"
        return found

    return find


def profile_url(class_id: int, student: int, semester: str | None = None) -> str:
    base = f"/api/v1/classes/{class_id}/students/{student}/profile"
    return base if semester is None else f"{base}?semester={semester}"


# --- Dashboard lớp: số buổi nghỉ theo tháng -------------------------------------------------------


def test_dashboard_lists_every_month_of_the_school_year_with_limits_from_settings(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    class_id = class_id_of("11A2")

    body = get(
        api_client, f"/api/v1/classes/{class_id}/dashboard", auth_headers("gvcn.11a2@example.com")
    ).json()

    assert [m["month"] for m in body["absences_by_month"]] == [
        "2026-09",
        "2026-10",
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
        "2027-03",
        "2027-04",
        "2027-05",
    ]
    assert all(m["total"] == m["excused"] + m["unexcused"] for m in body["absences_by_month"])
    assert body["absence_limits"] == {"notice": 30, "maximum": 45}
    assert body["thresholds"] == {"fail": 3.5, "passing": 5.0, "fair": 6.5, "good": 8.0}
    # Tổng các tháng bằng đúng số dòng nghỉ của cả lớp trong DB (đếm độc lập bằng SQL).
    class_absences = db_session.scalar(
        select(func.count())
        .select_from(Attendance)
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id, Attendance.status.in_(ABSENT_STATUSES))
    )
    assert sum(m["total"] for m in body["absences_by_month"]) == class_absences
    assert class_absences is not None and class_absences > 0


def test_monthly_absences_do_not_depend_on_the_semester_shown(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId
) -> None:
    headers = auth_headers("bgh1@example.com")
    base = f"/api/v1/classes/{class_id_of('11A2')}/dashboard"

    first = get(api_client, f"{base}?semester=1", headers).json()
    year = get(api_client, f"{base}?semester=year", headers).json()

    assert first["absences_by_month"] == year["absences_by_month"]  # nghỉ tính cả năm học (D-053)


# --- Hồ sơ học sinh: phân quyền -------------------------------------------------------------------

# (email, lớp, học sinh, kiểu hồ sơ nhận được)
PROFILE_ALLOWED = [
    ("gvcn.11a2@example.com", "11A2", "HS1102001", "full"),
    ("bgh1@example.com", "11A2", "HS1102001", "full"),
    ("bgh1@example.com", "12A1", "HS1201003", "full"),
    ("gv.toan.11@example.com", "11A1", "HS1101001", "full"),  # chủ nhiệm 11A1 (cộng dồn)
    ("gv.toan.11@example.com", "11A2", "HS1102001", "subjects"),  # chỉ dạy Toán ở 11A2
    ("gv.van.11@example.com", "11A2", "HS1102002", "subjects"),
]
PROFILE_DENIED = [
    ("gvcn.11a2@example.com", "11A3", "HS1103001"),  # GVCN lớp khác cùng khối
    ("gvcn.11a2@example.com", "10A1", "HS1001001"),
    ("gv.van.11@example.com", "10A2", "HS1002001"),  # đúng môn, sai khối
    ("gv.toan.12@example.com", "11A2", "HS1102001"),
    ("admin@example.com", "11A2", "HS1102001"),
]


@pytest.mark.parametrize(("email", "class_name", "code", "scope"), PROFILE_ALLOWED)
def test_profile_allowed_returns_the_right_kind_of_profile(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
    email: str,
    class_name: str,
    code: str,
    scope: str,
) -> None:
    response = get(
        api_client,
        profile_url(class_id_of(class_name), student_id(code)),
        auth_headers(email),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == scope
    assert body["student"]["student_code"] == code
    assert body["class_info"]["name"] == class_name
    assert "date_of_birth" not in response.text  # không bao giờ trả ngày sinh


@pytest.mark.parametrize(("email", "class_name", "code"), PROFILE_DENIED)
def test_profile_denied(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
    email: str,
    class_name: str,
    code: str,
) -> None:
    response = get(
        api_client, profile_url(class_id_of(class_name), student_id(code)), auth_headers(email)
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN


def test_profile_requires_login(
    api_client: TestClient, class_id_of: ClassId, student_id: Callable[[str], int]
) -> None:
    url = profile_url(class_id_of("11A2"), student_id("HS1102001"))

    assert get(api_client, url).status_code == 401
    assert get(api_client, url, {"Authorization": "Bearer rac"}).status_code == 401


def test_a_student_of_another_class_or_nobody_is_404_not_data(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    headers = auth_headers("gvcn.11a2@example.com")
    eleven_a2 = class_id_of("11A2")

    other_class_student = get(api_client, profile_url(eleven_a2, student_id("HS1101001")), headers)
    nobody = get(api_client, profile_url(eleven_a2, 999999), headers)
    teacher_nobody = get(
        api_client, profile_url(eleven_a2, 999999), auth_headers("gv.toan.11@example.com")
    )

    assert other_class_student.status_code == 404
    assert nobody.status_code == 404
    assert teacher_nobody.status_code == 404
    assert "HS1101001" not in other_class_student.text


def test_profile_of_a_missing_class_is_403_for_teachers_and_404_for_principal(
    api_client: TestClient, auth_headers: Headers
) -> None:
    url = profile_url(999999, 1)

    for email in ("gvcn.11a2@example.com", "gv.van.11@example.com", "admin@example.com"):
        assert get(api_client, url, auth_headers(email)).status_code == 403
    assert get(api_client, url, auth_headers("bgh1@example.com")).status_code == 404


def test_profile_rejects_an_unknown_semester(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    url = profile_url(class_id_of("11A2"), student_id("HS1102001"), "3")

    assert get(api_client, url, auth_headers("bgh1@example.com")).status_code == 422


# --- Hồ sơ học sinh: nội dung ---------------------------------------------------------------------


def test_subject_teacher_gets_only_own_subject_and_no_other_keys_at_all(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    response = get(
        api_client,
        profile_url(class_id_of("11A2"), student_id("HS1102002")),
        auth_headers("gv.toan.11@example.com"),
    )

    body = response.json()
    # Khoá không tồn tại, không phải khoá rỗng (D-044, D-066).
    assert set(body) == {"scope", "class_info", "student", "subjects", "thresholds"}
    assert body["thresholds"] == {"fail": 3.5, "passing": 5.0, "fair": 6.5, "good": 8.0}
    assert set(body["student"]) == {"id", "student_code", "full_name"}
    assert [s["name"] for s in body["subjects"]] == ["Toán"]
    for forbidden in ("guardian", "attendance", "conduct", "learning", "promotion", "attention"):
        assert forbidden not in response.text
    # HS1102002 có mọi đầu điểm Toán bằng 3,0: ĐTB = (4×3 + 2×3 + 3×3) / 9 = 3,0 mỗi học kỳ.
    toan = body["subjects"][0]
    first = toan["semesters"][0]
    assert first["tx"] == [3.0] * 4 and first["midterm"] == 3.0 and first["final"] == 3.0
    assert first["average"] == 3.0 and first["complete"] is True and first["tx_missing"] == 0
    assert toan["year_average"] == 3.0


def test_homeroom_teacher_gets_the_full_profile_with_guardian_and_attendance(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    response = get(
        api_client,
        profile_url(class_id_of("11A2"), student_id("HS1102001"), "1"),
        auth_headers("gvcn.11a2@example.com"),
    )

    body = response.json()
    assert body["scope"] == "full" and body["period"] == "1"
    assert isinstance(body["guardian_name"], str) and isinstance(body["guardian_phone"], str)
    attendance = body["attendance"]
    assert attendance["absent_total"] == 38  # em An nghỉ 38 buổi
    assert attendance["excused"] + attendance["unexcused"] == 38
    assert attendance["limits"] == {"notice": 30, "maximum": 45}
    assert len(attendance["by_month"]) == 9
    assert sum(m["total"] for m in attendance["by_month"]) == 38
    assert "absent_notice" in body["attention_reasons"]
    assert len(body["subjects"]) == 12  # 11A2 học 12 môn
    assert body["promotion"] is None  # chỉ khi xem cả năm
    assert body["conduct"]["level"] in {"good", "fair", "pass", "fail"}


def test_subject_below_fail_shows_in_learning_and_attention(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    body = get(
        api_client,
        profile_url(class_id_of("11A2"), student_id("HS1102002")),
        auth_headers("bgh1@example.com"),
    ).json()

    assert body["learning"]["below_fail_subjects"] == ["Toán"]
    assert "subject_below_fail" in body["attention_reasons"]


def test_comment_subject_has_a_result_and_no_average(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    body = get(
        api_client,
        profile_url(class_id_of("11A2"), student_id("HS1102001")),
        auth_headers("gvcn.11a2@example.com"),
    ).json()

    gdtc = next(s for s in body["subjects"] if s["name"] == "Giáo dục thể chất")
    assert gdtc["assessment_type"] == "comment"
    assert gdtc["year_average"] is None
    for semester in gdtc["semesters"]:
        assert semester["average"] is None and semester["tx"] == []
        assert semester["comment_result"] in {"pass", "fail"}
    assert gdtc["year_comment_result"] == gdtc["semesters"][1]["comment_result"]  # cả năm = HK2


def test_whole_year_profile_adds_promotion(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    body = get(
        api_client,
        profile_url(class_id_of("12A1"), student_id("HS1201003"), "year"),
        auth_headers("gv.toan.12@example.com"),
    ).json()

    assert body["attendance"]["absent_total"] == 46
    assert body["promotion"]["eligible"] is False
    assert "absent_over_limit" in body["promotion"]["reasons"]
    assert "absent_over_limit" in body["attention_reasons"]


@pytest.mark.parametrize("semester", ["1", "2", "year"])
def test_profile_agrees_with_the_class_dashboard_and_the_subject_sheet(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: ClassId,
    subject_id_of: SubjectId,
    student_id: Callable[[str], int],
    semester: str,
) -> None:
    """Một con số, ba màn hình: hồ sơ phải khớp dashboard lớp và bảng điểm môn."""
    headers = auth_headers("bgh1@example.com")
    class_id = class_id_of("11A2")
    dashboard = get(
        api_client, f"/api/v1/classes/{class_id}/dashboard?semester={semester}", headers
    ).json()
    sheet = get(
        api_client,
        f"/api/v1/classes/{class_id}/subjects/{subject_id_of('Toán')}/scores?semester=1",
        headers,
    ).json()

    for item in dashboard["attention"]:
        profile = get(
            api_client,
            profile_url(class_id, item["student_id"], semester),
            headers,
        ).json()
        assert profile["attention_reasons"] == item["reasons"]
        assert profile["attendance"]["absent_total"] == item["absent_sessions"]

    row = next(r for r in sheet["rows"] if r["student_code"] == "HS1102001")
    profile = get(api_client, profile_url(class_id, row["student_id"], semester), headers).json()
    toan = next(s for s in profile["subjects"] if s["name"] == "Toán")
    assert toan["semesters"][0]["average"] == row["average_semester1"]
    assert toan["semesters"][1]["average"] == row["average_semester2"]
    assert toan["year_average"] == row["year_average"]
    assert toan["semesters"][0]["tx"] == row["tx"]


# --- Nhật ký --------------------------------------------------------------------------------------


def test_opening_a_profile_is_logged_once_and_denials_are_not(
    api_client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    class_id_of: ClassId,
    student_id: Callable[[str], int],
) -> None:
    class_id, student = class_id_of("11A2"), student_id("HS1102001")

    get(api_client, profile_url(class_id, student), auth_headers("gv.van.11@example.com"))  # 200
    get(api_client, profile_url(class_id, student), auth_headers("admin@example.com"))  # 403
    get(api_client, profile_url(class_id, 999999), auth_headers("gvcn.11a2@example.com"))  # 404
    get(api_client, profile_url(class_id, student, "2"), auth_headers("gvcn.11a2@example.com"))

    subject_log, full_log = list(db_session.scalars(select(AuditLog).order_by(AuditLog.id)))
    assert subject_log.action is AuditAction.VIEW_STUDENT_PROFILE
    assert subject_log.class_id == class_id
    assert subject_log.details == {"student_id": student, "semester": "1", "scope": "subjects"}
    assert full_log.details == {"student_id": student, "semester": "2", "scope": "full"}

"""API cảnh báo sớm: ma trận phân quyền 4 vai trò, nội dung, ghi nhận của GVCN, nhật ký (D-072).

Tài khoản (xem README): gvcn.11a2 chỉ chủ nhiệm 11A2; gv.toan.11 chủ nhiệm 11A1 và dạy Toán 11A1 đến
11A3 (cộng dồn); gv.van.11 dạy Ngữ văn khối 11; bgh1 là BGH; admin là Admin.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditLog
from app.classes.models import ClassStudent, Student
from app.core.enums import AuditAction, RiskLevel, TeacherStatus
from app.warning import repository as repo
from app.warning import service
from app.warning.models import RiskAlert

pytestmark = pytest.mark.db

Headers = Callable[[str], dict[str, str]]
ClassId = Callable[[str], int]

FORBIDDEN = {"detail": "Bạn không có quyền truy cập dữ liệu này."}


@pytest.fixture(autouse=True)
def alerts_exist(db_session: Session, class_id_of: ClassId) -> None:
    """Chạy lớp luật cho ba lớp của ba khối trước mỗi test (DB test không tự có cảnh báo)."""
    for name in ("10A2", "11A2", "12A1"):
        service.refresh_class(db_session, class_id_of(name))


def get(client: TestClient, url: str, headers: dict[str, str] | None = None) -> Any:
    return client.get(url, headers=headers or {})


def alert_id_of(session: Session, code: str) -> int:
    cs_id = session.scalar(
        select(ClassStudent.id)
        .join(Student, Student.id == ClassStudent.student_id)
        .where(Student.student_code == code)
    )
    assert cs_id is not None
    alert = repo.current_for_student(session, cs_id)
    assert alert is not None
    return alert.id


def status_of(session: Session, alert_id: int) -> TeacherStatus:
    session.expire_all()
    alert = session.get(RiskAlert, alert_id)
    assert alert is not None
    return alert.teacher_status


def patch(
    client: TestClient, alert_id: int, status: str, headers: dict[str, str] | None = None
) -> Any:
    return client.patch(
        f"/api/v1/alerts/{alert_id}", json={"teacher_status": status}, headers=headers or {}
    )


# --- Danh sách cảnh báo của lớp -------------------------------------------------------------------

ALLOWED = [
    ("gvcn.11a2@example.com", "11A2"),
    ("bgh1@example.com", "11A2"),
    ("bgh1@example.com", "12A1"),
    ("gv.toan.11@example.com", "11A1"),  # cộng dồn: chủ nhiệm 11A1
]
DENIED = [
    ("gv.toan.11@example.com", "11A2"),  # chỉ dạy Toán ở đó: GVBM không thấy cảnh báo
    ("gv.van.11@example.com", "11A2"),
    ("gvcn.11a2@example.com", "11A3"),  # GVCN lớp khác cùng khối
    ("gvcn.11a2@example.com", "10A1"),
    ("admin@example.com", "11A2"),
]


@pytest.mark.parametrize(("email", "class_name"), ALLOWED)
def test_class_alerts_allowed(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, email: str, class_name: str
) -> None:
    response = get(
        api_client, f"/api/v1/classes/{class_id_of(class_name)}/alerts", auth_headers(email)
    )

    assert response.status_code == 200
    assert response.json()["class_name"] == class_name


@pytest.mark.parametrize(("email", "class_name"), DENIED)
def test_class_alerts_denied(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, email: str, class_name: str
) -> None:
    response = get(
        api_client, f"/api/v1/classes/{class_id_of(class_name)}/alerts", auth_headers(email)
    )

    assert response.status_code == 403
    assert response.json() == FORBIDDEN


def test_class_alerts_need_login_and_a_real_class(
    api_client: TestClient, auth_headers: Headers
) -> None:
    assert get(api_client, "/api/v1/classes/5/alerts").status_code == 401
    assert (
        get(
            api_client, "/api/v1/classes/999999/alerts", auth_headers("bgh1@example.com")
        ).status_code
        == 404
    )
    for email in ("gvcn.11a2@example.com", "gv.van.11@example.com", "admin@example.com"):
        assert (
            get(api_client, "/api/v1/classes/999999/alerts", auth_headers(email)).status_code == 403
        )


def test_class_alerts_content(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    class_id = class_id_of("11A2")
    headers = auth_headers("gvcn.11a2@example.com")

    body = get(api_client, f"/api/v1/classes/{class_id}/alerts", headers).json()
    everyone = get(
        api_client, f"/api/v1/classes/{class_id}/alerts?include_low=true", headers
    ).json()

    counts = body["counts"]
    assert set(counts) == {"high", "medium", "low"} and sum(counts.values()) == 40
    assert len(body["alerts"]) == counts["high"] + counts["medium"]  # mặc định không có mức Thấp
    assert len(everyone["alerts"]) == 40
    levels = [a["level"] for a in body["alerts"]]
    assert levels == sorted(levels, key={"high": 0, "medium": 1, "low": 2}.get)  # Cao trước
    by_code = {a["student"]["student_code"]: a for a in body["alerts"]}
    an = by_code["HS1102001"]
    assert an["level"] == "medium" and any("38 buổi" in text for text in an["top_reasons"])
    assert len(an["top_reasons"]) <= 3 and an["teacher_status"] == "new" and an["model"] is None
    assert by_code["HS1102002"]["level"] == "high"
    # Chỉ định danh tối thiểu của học sinh; không có thông tin phụ huynh hay ngày sinh.
    assert set(an["student"]) == {"id", "student_code", "full_name"}
    text = str(body)
    assert "guardian" not in text and "date_of_birth" not in text


# --- Cảnh báo toàn trường (BGH) -----------------------------------------------------------------


def test_school_alerts_are_for_the_principal_only(
    api_client: TestClient, auth_headers: Headers
) -> None:
    body = get(api_client, "/api/v1/alerts", auth_headers("bgh1@example.com")).json()

    assert body["alerts"] and all(a["level"] == "high" for a in body["alerts"])
    assert {a["class_name"][:2] for a in body["alerts"]} >= {"10", "11", "12"}  # nhiều khối
    medium = get(api_client, "/api/v1/alerts?level=medium", auth_headers("bgh1@example.com")).json()
    assert medium["alerts"] and all(a["level"] == "medium" for a in medium["alerts"])
    assert body["counts"]["high"] == len(body["alerts"])
    for email in (
        "gvcn.11a2@example.com",
        "gv.toan.11@example.com",
        "gv.van.11@example.com",
        "admin@example.com",
    ):
        response = get(api_client, "/api/v1/alerts", auth_headers(email))
        assert response.status_code == 403 and response.json() == FORBIDDEN
    assert get(api_client, "/api/v1/alerts").status_code == 401
    assert (
        get(api_client, "/api/v1/alerts?level=cao", auth_headers("bgh1@example.com")).status_code
        == 422
    )


# --- Ghi nhận của GVCN --------------------------------------------------------------------------


def test_the_homeroom_teacher_records_that_she_talked_or_that_it_was_a_false_alarm(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers("gvcn.11a2@example.com")
    alert_id = alert_id_of(db_session, "HS1102001")

    first = patch(api_client, alert_id, "contacted", headers)
    second = patch(api_client, alert_id, "false_alarm", headers)

    assert first.status_code == 200 and first.json()["teacher_status"] == "contacted"
    assert second.json()["teacher_status"] == "false_alarm" and second.json()["id"] == alert_id
    db_session.expire_all()
    assert status_of(db_session, alert_id) is TeacherStatus.FALSE_ALARM
    listing = get(api_client, "/api/v1/classes/5/alerts", headers).json()
    assert (
        next(a for a in listing["alerts"] if a["id"] == alert_id)["teacher_status"] == "false_alarm"
    )


@pytest.mark.parametrize(
    "email",
    [
        "bgh1@example.com",  # BGH chỉ xem
        "gv.toan.11@example.com",  # dạy Toán ở 11A2 nhưng không chủ nhiệm
        "gv.van.11@example.com",
        "gvcn.11a3@example.com",  # GVCN lớp khác
        "admin@example.com",
    ],
)
def test_only_the_homeroom_teacher_of_the_class_may_record(
    api_client: TestClient, auth_headers: Headers, db_session: Session, email: str
) -> None:
    alert_id = alert_id_of(db_session, "HS1102001")

    response = patch(api_client, alert_id, "false_alarm", auth_headers(email))

    assert response.status_code == 403 and response.json() == FORBIDDEN
    db_session.expire_all()
    assert status_of(db_session, alert_id) is TeacherStatus.NEW


def test_recording_needs_login_a_real_alert_and_a_valid_status(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers("gvcn.11a2@example.com")
    alert_id = alert_id_of(db_session, "HS1102001")

    assert patch(api_client, alert_id, "contacted").status_code == 401
    # Cảnh báo không tồn tại: cùng 403 như không có quyền (không lộ id nào có thật).
    assert patch(api_client, 999999, "contacted", headers).status_code == 403
    assert patch(api_client, alert_id, "khong-hop-le", headers).status_code == 422
    assert (
        api_client.patch(f"/api/v1/alerts/{alert_id}", json={}, headers=headers).status_code == 422
    )


def test_a_replaced_alert_cannot_be_recorded_any_more(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers("gvcn.11a2@example.com")
    old_id = alert_id_of(db_session, "HS1102001")
    old = db_session.get(RiskAlert, old_id)
    assert old is not None
    repo.insert_alert(  # một lần chạy lại thấy nội dung đổi: dòng mới thay dòng cũ
        db_session,
        class_student_id=old.class_student_id,
        level=RiskLevel.HIGH,
        risk_score=None,
        reasons={"rules": [], "model": None},
        model_version=None,
    )

    response = patch(api_client, old_id, "contacted", headers)

    assert response.status_code == 409
    assert "thay bằng cảnh báo mới" in response.json()["detail"]


def test_the_note_is_kept_when_the_warning_is_run_again(
    api_client: TestClient, auth_headers: Headers, db_session: Session, class_id_of: ClassId
) -> None:
    alert_id = alert_id_of(db_session, "HS1102001")
    patch(api_client, alert_id, "false_alarm", auth_headers("gvcn.11a2@example.com"))

    result = service.refresh_class(db_session, class_id_of("11A2"))

    assert result.inserted == 0
    assert alert_id_of(db_session, "HS1102001") == alert_id
    db_session.expire_all()
    assert status_of(db_session, alert_id) is TeacherStatus.FALSE_ALARM


# --- Dashboard và hồ sơ --------------------------------------------------------------------------


def test_dashboard_and_profile_show_the_same_alert(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    class_id = class_id_of("11A2")
    headers = auth_headers("gvcn.11a2@example.com")
    listing = get(api_client, f"/api/v1/classes/{class_id}/alerts", headers).json()

    dashboard = get(api_client, f"/api/v1/classes/{class_id}/dashboard", headers).json()
    an = next(a for a in listing["alerts"] if a["student"]["student_code"] == "HS1102001")
    profile = get(
        api_client, f"/api/v1/classes/{class_id}/students/{an['student']['id']}/profile", headers
    ).json()

    assert dashboard["alert_counts"] == listing["counts"]
    assert profile["alert"]["id"] == an["id"] and profile["alert"]["level"] == "medium"
    assert profile["alert"]["top_reasons"] == an["top_reasons"]
    # BGH cũng thấy; GVBM nhận hồ sơ không có khoá cảnh báo.
    bgh = get(
        api_client,
        f"/api/v1/classes/{class_id}/students/{an['student']['id']}/profile",
        auth_headers("bgh1@example.com"),
    ).json()
    assert bgh["alert"]["id"] == an["id"]
    gvbm = get(
        api_client,
        f"/api/v1/classes/{class_id}/students/{an['student']['id']}/profile",
        auth_headers("gv.toan.11@example.com"),
    ).json()
    assert gvbm["scope"] == "subjects" and "alert" not in gvbm


def test_the_dashboard_counts_are_zero_before_any_warning_is_run(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    db_session.execute(RiskAlert.__table__.delete())

    body = get(
        api_client,
        f"/api/v1/classes/{class_id_of('11A2')}/dashboard",
        auth_headers("gvcn.11a2@example.com"),
    ).json()

    assert body["alert_counts"] == {"high": 0, "medium": 0, "low": 0}


# --- Nhật ký ------------------------------------------------------------------------------------


def audit(session: Session, action: AuditAction) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_viewing_and_recording_are_logged_and_denials_are_not(
    api_client: TestClient, auth_headers: Headers, db_session: Session, class_id_of: ClassId
) -> None:
    class_id = class_id_of("11A2")
    get(api_client, f"/api/v1/classes/{class_id}/alerts", auth_headers("gv.van.11@example.com"))
    get(api_client, "/api/v1/alerts", auth_headers("gvcn.11a2@example.com"))
    patch(
        api_client,
        alert_id_of(db_session, "HS1102001"),
        "contacted",
        auth_headers("bgh1@example.com"),
    )
    assert (
        db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
    )  # bị từ chối: không ghi

    get(api_client, f"/api/v1/classes/{class_id}/alerts", auth_headers("gvcn.11a2@example.com"))
    get(api_client, "/api/v1/alerts?level=medium", auth_headers("bgh1@example.com"))
    alert_id = alert_id_of(db_session, "HS1102001")
    patch(api_client, alert_id, "contacted", auth_headers("gvcn.11a2@example.com"))

    [viewed] = audit(db_session, AuditAction.VIEW_CLASS_ALERTS)
    assert viewed.class_id == class_id and viewed.details["include_low"] is False
    [school] = audit(db_session, AuditAction.VIEW_SCHOOL_ALERTS)
    assert school.class_id is None and school.details["level"] == "medium"
    [updated] = audit(db_session, AuditAction.UPDATE_ALERT)
    assert updated.class_id == class_id
    assert updated.details == {"alert_id": alert_id, "teacher_status": "contacted"}

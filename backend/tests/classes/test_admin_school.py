"""Quản trị năm học, lớp, GVCN, phân công, gỡ học sinh (D-098, D-099): phân quyền và quy tắc."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.models import AuditLog, User
from app.classes.models import (
    ClassStudent,
    SchoolClass,
    SchoolYear,
    Student,
    TeachingAssignment,
)
from app.core.enums import AuditAction, UserRole

pytestmark = pytest.mark.db

API = "/api/v1"
ADMIN = "admin@example.com"
NON_ADMINS = [
    "bgh1@example.com",
    "gvcn.11a2@example.com",
    "gv.van.11@example.com",
    "gv.toan.10@example.com",
]
Headers = Callable[[str], dict[str, str]]


def make_teacher(session: Session, name: str, *, active: bool = True) -> User:
    user = User(
        email=f"{name}@example.com",
        full_name=f"Giáo viên {name}",
        password_hash="khong-dang-nhap-bang-mat-khau",
        role=UserRole.TEACHER,
        is_active=active,
    )
    session.add(user)
    session.flush()
    return user


def new_class(client: TestClient, headers: dict[str, str], **body: Any) -> Response:
    payload = {"grade_level": 11, "name": "11A9", **body}
    return client.post(f"{API}/admin/classes", headers=headers, json=payload)


def add_student(session: Session, class_id: int, code: str) -> int:
    student = Student(student_code=code, full_name="Học sinh thử", guardian_phone="0900000000")
    session.add(student)
    session.flush()
    link = ClassStudent(class_id=class_id, student_id=student.id)
    session.add(link)
    session.flush()
    return student.id


def audit(session: Session, action: AuditAction) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


def class_id_by_name(session: Session, name: str) -> int:
    found = session.scalar(select(SchoolClass.id).where(SchoolClass.name == name))
    assert found is not None
    return found


# --- Phân quyền: 4 vai trò + chưa đăng nhập, mọi endpoint ---------------------------------------


def endpoints(class_id: int, other_class: int, subject_id: int, teacher_id: int):  # noqa: ANN201
    base = f"{API}/admin"
    return [
        ("GET", f"{base}/school", None),
        ("GET", f"{base}/teachers", None),
        (
            "PUT",
            f"{base}/school-year",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-01"},
        ),
        ("POST", f"{base}/classes", {"grade_level": 11, "name": "11A8"}),
        ("PATCH", f"{base}/classes/{class_id}", {"name": "11A2"}),
        ("DELETE", f"{base}/classes/{class_id}", None),
        ("GET", f"{base}/classes/{class_id}/assignments", None),
        ("PUT", f"{base}/classes/{class_id}/assignments/{subject_id}", {"teacher_id": teacher_id}),
        ("DELETE", f"{base}/classes/{class_id}/assignments/{subject_id}", None),
        ("POST", f"{base}/classes/{class_id}/assignments/copy", {"from_class_id": other_class}),
        ("POST", f"{base}/classes/{class_id}/students/remove", {"student_code": "HS1102001"}),
    ]


@pytest.mark.parametrize("email", NON_ADMINS)
def test_every_other_role_gets_403_and_nothing_changes(
    api_client: TestClient, auth_headers: Headers, db_session: Session, email: str
) -> None:
    class_id = class_id_by_name(db_session, "11A2")
    other = class_id_by_name(db_session, "11A1")
    teacher = db_session.scalar(select(User.id).where(User.email == "gv.van.11@example.com"))
    assert teacher is not None
    headers = auth_headers(email)
    before = (
        db_session.scalar(select(func.count()).select_from(SchoolClass)),
        db_session.scalar(select(func.count()).select_from(TeachingAssignment)),
        db_session.scalar(select(func.count()).select_from(ClassStudent)),
    )

    for method, url, body in endpoints(class_id, other, 1, teacher):
        response = api_client.request(method, url, headers=headers, json=body)
        assert response.status_code == 403, (method, url)
    # Sai hình dạng cũng 403, không 422.
    assert api_client.post(f"{API}/admin/classes", headers=headers, json={}).status_code == 403

    after = (
        db_session.scalar(select(func.count()).select_from(SchoolClass)),
        db_session.scalar(select(func.count()).select_from(TeachingAssignment)),
        db_session.scalar(select(func.count()).select_from(ClassStudent)),
    )
    assert after == before


def test_unauthenticated_gets_401_on_every_endpoint(
    api_client: TestClient, db_session: Session
) -> None:
    class_id = class_id_by_name(db_session, "11A2")

    for method, url, body in endpoints(class_id, class_id, 1, 1):
        assert api_client.request(method, url, json=body).status_code == 401, (method, url)


def test_admin_still_cannot_read_student_data(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    # D-039: các màn hình quản trị không mở quyền xem học sinh cho Admin.
    class_id = class_id_by_name(db_session, "11A2")
    headers = auth_headers(ADMIN)

    assert api_client.get(f"{API}/classes/{class_id}/students", headers=headers).status_code == 403
    assert api_client.get(f"{API}/classes/{class_id}/dashboard", headers=headers).status_code == 403


# --- Năm học và danh sách lớp ------------------------------------------------------------------


def test_school_lists_the_year_and_classes_with_counts_only(
    api_client: TestClient, auth_headers: Headers
) -> None:
    response = api_client.get(f"{API}/admin/school", headers=auth_headers(ADMIN))

    assert response.status_code == 200
    body = response.json()
    assert body["school_year"]["name"] == "2026-2027"
    assert body["subject_count"] == 17
    assert [(c["grade_level"], c["name"]) for c in body["classes"]][:3] == [
        (10, "10A1"),
        (10, "10A2"),
        (10, "10A3"),
    ]
    first = body["classes"][0]
    assert first["student_count"] == 40
    assert first["assigned_subject_count"] == 12
    assert first["homeroom_teacher"]["full_name"]
    assert set(first) == {
        "id",
        "name",
        "grade_level",
        "homeroom_teacher",
        "student_count",
        "assigned_subject_count",
    }
    assert "student_code" not in response.text and "guardian" not in response.text


def test_teachers_list_has_only_active_teachers_and_their_homeroom(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    make_teacher(db_session, "giao.vien.khoa", active=False)
    make_teacher(db_session, "giao.vien.tu.do")

    rows = api_client.get(f"{API}/admin/teachers", headers=auth_headers(ADMIN)).json()

    emails = {row["email"]: row for row in rows}
    assert "giao.vien.khoa@example.com" not in emails  # tài khoản bị khoá
    assert "bgh1@example.com" not in emails and ADMIN not in emails  # không phải giáo viên
    assert emails["giao.vien.tu.do@example.com"]["homeroom_class"] is None
    assert emails["gvcn.11a2@example.com"]["homeroom_class"] == "11A2"


def test_school_year_can_be_edited_but_not_across_existing_attendance(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    url = f"{API}/admin/school-year"

    ok = api_client.put(
        url,
        headers=headers,
        json={"name": "2026–2027", "start_date": "2026-08-20", "end_date": "2027-06-15"},
    )
    too_late = api_client.put(
        url,
        headers=headers,
        json={"name": "2026-2027", "start_date": "2026-10-01", "end_date": "2027-06-15"},
    )
    too_early = api_client.put(
        url,
        headers=headers,
        json={"name": "2026-2027", "start_date": "2026-08-20", "end_date": "2027-03-01"},
    )

    assert ok.status_code == 200
    assert ok.json()["start_date"] == "2026-08-20"
    assert too_late.status_code == 409 and "điểm danh" in too_late.json()["detail"]
    assert too_early.status_code == 409
    year = db_session.scalars(select(SchoolYear)).one()
    assert (year.name, year.end_date) == ("2026–2027", date(2027, 6, 15))
    assert db_session.scalar(select(func.count()).select_from(SchoolYear)) == 1
    assert audit(db_session, AuditAction.UPDATE_SCHOOL_YEAR)[0].details["created"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "start_date": "2027-06-01", "end_date": "2026-09-01"},
        {"name": "x", "start_date": "2026-09-01", "end_date": "2026-09-01"},
        {"name": "", "start_date": "2026-09-01", "end_date": "2027-06-01"},
        {"name": "x" * 21, "start_date": "2026-09-01", "end_date": "2027-06-01"},
        {"name": "x", "start_date": "khong-phai-ngay", "end_date": "2027-06-01"},
    ],
)
def test_school_year_rejects_bad_input(
    api_client: TestClient, auth_headers: Headers, body: dict[str, str]
) -> None:
    response = api_client.put(f"{API}/admin/school-year", headers=auth_headers(ADMIN), json=body)

    assert response.status_code == 422


def test_the_first_school_year_can_be_created_and_classes_need_one(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    db_session.execute(text("TRUNCATE school_years RESTART IDENTITY CASCADE"))

    school = api_client.get(f"{API}/admin/school", headers=headers).json()
    refused = new_class(api_client, headers)
    created = api_client.put(
        f"{API}/admin/school-year",
        headers=headers,
        json={"name": "2027-2028", "start_date": "2027-09-05", "end_date": "2028-05-31"},
    )
    class_ok = new_class(api_client, headers)

    assert school["school_year"] is None and school["classes"] == []
    assert refused.status_code == 409 and "năm học" in refused.json()["detail"]
    assert created.status_code == 200
    assert class_ok.status_code == 201
    assert audit(db_session, AuditAction.UPDATE_SCHOOL_YEAR)[0].details["created"] is True


# --- Lớp và GVCN ------------------------------------------------------------


def test_create_class_with_a_homeroom_teacher_who_then_gets_access(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    teacher = make_teacher(db_session, "gvcn.moi")
    headers = auth_headers(ADMIN)

    response = new_class(api_client, headers, homeroom_teacher_id=teacher.id)

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["grade_level"], body["student_count"]) == ("11A9", 11, 0)
    assert body["homeroom_teacher"] == {"id": teacher.id, "full_name": "Giáo viên gvcn.moi"}
    # GVCN mới thấy lớp mình và được vào lớp (authorize() đọc phân công từ DB).
    mine = api_client.get(f"{API}/me/assignments", headers=auth_headers(teacher.email)).json()
    assert [c["name"] for c in mine["homeroom_classes"]] == ["11A9"]
    assert (
        api_client.get(
            f"{API}/classes/{body['id']}/students", headers=auth_headers(teacher.email)
        ).status_code
        == 200
    )
    logged = audit(db_session, AuditAction.CREATE_CLASS)
    assert logged[0].class_id == body["id"]
    assert logged[0].details == {"grade_level": 11, "homeroom_teacher_id": teacher.id}


@pytest.mark.parametrize(
    ("body", "status", "text_in_detail"),
    [
        ({"name": "12A9"}, 422, "bắt đầu bằng 11"),
        ({"name": "11a1"}, 409, "Đã có lớp"),  # không phân biệt hoa thường
        ({"name": "11A2"}, 409, "Đã có lớp"),
        ({"grade_level": 9}, 422, None),
        ({"name": ""}, 422, None),
        ({"homeroom_teacher_id": 999999}, 422, "đang hoạt động"),
    ],
)
def test_create_class_refuses_bad_input(
    api_client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    body: dict[str, Any],
    status: int,
    text_in_detail: str | None,
) -> None:
    before = db_session.scalar(select(func.count()).select_from(SchoolClass))

    response = new_class(api_client, auth_headers(ADMIN), **body)

    assert response.status_code == status
    if text_in_detail:
        assert text_in_detail in response.json()["detail"]
    assert db_session.scalar(select(func.count()).select_from(SchoolClass)) == before


def test_homeroom_teacher_must_be_an_active_teacher_with_no_other_class(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    locked = make_teacher(db_session, "da.khoa", active=False)
    principal = db_session.scalar(select(User.id).where(User.email == "bgh1@example.com"))
    busy = db_session.scalar(select(User.id).where(User.email == "gvcn.11a2@example.com"))

    for teacher_id, status in ((locked.id, 422), (principal, 422), (busy, 409)):
        response = new_class(api_client, headers, homeroom_teacher_id=teacher_id)
        assert response.status_code == status, teacher_id
    assert "11A2" in new_class(api_client, headers, homeroom_teacher_id=busy).json()["detail"]


def test_update_class_renames_and_moves_the_homeroom_teacher(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    free = make_teacher(db_session, "dang.ranh")
    class_id = class_id_by_name(db_session, "11A3")
    old = db_session.scalar(
        select(User.email)
        .join(SchoolClass, SchoolClass.homeroom_teacher_id == User.id)
        .where(SchoolClass.id == class_id)
    )
    assert old is not None

    renamed = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=headers, json={"name": "11C3"}
    )
    moved = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=headers, json={"homeroom_teacher_id": free.id}
    )

    assert renamed.status_code == 200 and renamed.json()["name"] == "11C3"
    assert moved.status_code == 200 and moved.json()["homeroom_teacher"]["id"] == free.id
    # Người cũ mất quyền chủ nhiệm ngay; người mới có.
    assert (
        api_client.get(f"{API}/classes/{class_id}/students", headers=auth_headers(old)).status_code
        == 403
    )
    assert (
        api_client.get(
            f"{API}/classes/{class_id}/students", headers=auth_headers(free.email)
        ).status_code
        == 200
    )
    logged = audit(db_session, AuditAction.UPDATE_CLASS)
    assert [row.details["fields"] for row in logged] == [["name"], ["homeroom_teacher_id"]]


def test_update_class_can_clear_the_homeroom_teacher_and_refuses_clashes(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    class_id = class_id_by_name(db_session, "11A3")
    other_homeroom = db_session.scalar(select(User.id).where(User.email == "gvcn.11a2@example.com"))

    clash = api_client.patch(
        f"{API}/admin/classes/{class_id}",
        headers=headers,
        json={"homeroom_teacher_id": other_homeroom},
    )
    same_name = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=headers, json={"name": "11a2"}
    )
    wrong_grade = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=headers, json={"name": "12A3"}
    )
    cleared = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=headers, json={"homeroom_teacher_id": None}
    )

    assert clash.status_code == 409 and "11A2" in clash.json()["detail"]
    assert same_name.status_code == 409
    assert wrong_grade.status_code == 422
    assert cleared.status_code == 200 and cleared.json()["homeroom_teacher"] is None


@pytest.mark.parametrize("body", [{}, {"name": None}, {"name": " "}])
def test_update_class_rejects_empty_changes(
    api_client: TestClient, auth_headers: Headers, db_session: Session, body: dict[str, Any]
) -> None:
    class_id = class_id_by_name(db_session, "11A3")

    response = api_client.patch(
        f"{API}/admin/classes/{class_id}", headers=auth_headers(ADMIN), json=body
    )

    assert response.status_code == 422


def test_delete_class_only_when_empty(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    full = class_id_by_name(db_session, "11A2")

    refused = api_client.delete(f"{API}/admin/classes/{full}", headers=headers)
    created = new_class(api_client, headers).json()
    api_client.put(
        f"{API}/admin/classes/{created['id']}/assignments/2",
        headers=headers,
        json={"teacher_id": make_teacher(db_session, "dang.day").id},
    )
    with_assignment = api_client.delete(f"{API}/admin/classes/{created['id']}", headers=headers)
    api_client.delete(f"{API}/admin/classes/{created['id']}/assignments/2", headers=headers)
    deleted = api_client.delete(f"{API}/admin/classes/{created['id']}", headers=headers)
    again = api_client.delete(f"{API}/admin/classes/{created['id']}", headers=headers)

    assert refused.status_code == 409
    assert with_assignment.status_code == 409
    assert deleted.status_code == 200
    assert again.status_code == 404
    assert db_session.get(SchoolClass, full) is not None
    assert audit(db_session, AuditAction.DELETE_CLASS)[0].class_id == created["id"]


def test_delete_class_is_refused_while_it_has_students_even_without_assignments(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    created = new_class(api_client, headers).json()["id"]
    add_student(db_session, created, "HS9990003")

    response = api_client.delete(f"{API}/admin/classes/{created}", headers=headers)

    assert response.status_code == 409
    assert db_session.get(SchoolClass, created) is not None


# --- Phân công giảng dạy -------------------------------------------------------------------------


def test_assignments_list_every_subject_with_the_teacher_or_none(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    existing = class_id_by_name(db_session, "11A2")
    empty = new_class(api_client, headers).json()["id"]

    full = api_client.get(f"{API}/admin/classes/{existing}/assignments", headers=headers).json()
    blank = api_client.get(f"{API}/admin/classes/{empty}/assignments", headers=headers).json()

    assert full["class_name"] == "11A2" and full["grade_level"] == 11
    assert len(full["subjects"]) == 17
    assert sum(1 for row in full["subjects"] if row["teacher"]) == 12
    math = next(row for row in full["subjects"] if row["subject_name"] == "Toán")
    assert math["teacher"]["full_name"] and math["assessment_type"] == "score"
    assert len(blank["subjects"]) == 17 and all(row["teacher"] is None for row in blank["subjects"])
    assert (
        api_client.get(f"{API}/admin/classes/999999/assignments", headers=headers).status_code
        == 404
    )


def test_assigning_gives_the_teacher_access_and_replacing_takes_it_away(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    class_id = new_class(api_client, headers).json()["id"]
    first = make_teacher(db_session, "day.mot")
    second = make_teacher(db_session, "day.hai")
    url = f"{API}/admin/classes/{class_id}/assignments/2"  # môn Toán
    scores = f"{API}/classes/{class_id}/subjects/2/scores?semester=1"

    assert api_client.get(scores, headers=auth_headers(first.email)).status_code == 403
    assigned = api_client.put(url, headers=headers, json={"teacher_id": first.id})
    assert api_client.get(scores, headers=auth_headers(first.email)).status_code == 200
    replaced = api_client.put(url, headers=headers, json={"teacher_id": second.id})

    assert assigned.status_code == 200 and replaced.status_code == 200
    math = next(r for r in replaced.json()["subjects"] if r["subject_id"] == 2)
    assert math["teacher"]["id"] == second.id
    assert api_client.get(scores, headers=auth_headers(first.email)).status_code == 403
    assert api_client.get(scores, headers=auth_headers(second.email)).status_code == 200
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(TeachingAssignment)
            .where(TeachingAssignment.class_id == class_id)
        )
        == 1
    )
    rows = audit(db_session, AuditAction.SET_ASSIGNMENT)
    assert [r.details["teacher_id"] for r in rows] == [[None, first.id], [first.id, second.id]]


def test_assignment_refuses_unknown_things_and_unfit_teachers(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    class_id = new_class(api_client, headers).json()["id"]
    locked = make_teacher(db_session, "bi.khoa", active=False)
    principal = db_session.scalar(select(User.id).where(User.email == "bgh1@example.com"))
    good = make_teacher(db_session, "hop.le")
    base = f"{API}/admin/classes"

    for teacher_id in (locked.id, principal, 999999):
        response = api_client.put(
            f"{base}/{class_id}/assignments/2", headers=headers, json={"teacher_id": teacher_id}
        )
        assert response.status_code == 422, teacher_id
    assert (
        api_client.put(
            f"{base}/{class_id}/assignments/999", headers=headers, json={"teacher_id": good.id}
        ).status_code
        == 404
    )
    assert (
        api_client.put(
            f"{base}/999999/assignments/2", headers=headers, json={"teacher_id": good.id}
        ).status_code
        == 404
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(TeachingAssignment)
            .where(TeachingAssignment.class_id == class_id)
        )
        == 0
    )


def test_removing_an_assignment_is_refused_once_the_class_has_scores(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    scored = class_id_by_name(db_session, "11A2")
    fresh = new_class(api_client, headers).json()["id"]
    api_client.put(
        f"{API}/admin/classes/{fresh}/assignments/2",
        headers=headers,
        json={"teacher_id": make_teacher(db_session, "se.go").id},
    )

    refused = api_client.delete(f"{API}/admin/classes/{scored}/assignments/2", headers=headers)
    removed = api_client.delete(f"{API}/admin/classes/{fresh}/assignments/2", headers=headers)
    missing = api_client.delete(f"{API}/admin/classes/{fresh}/assignments/2", headers=headers)

    assert refused.status_code == 409 and "đã có điểm" in refused.json()["detail"]
    assert removed.status_code == 200
    assert all(r["teacher"] is None for r in removed.json()["subjects"])
    assert missing.status_code == 404
    still = db_session.scalar(
        select(TeachingAssignment.id).where(
            TeachingAssignment.class_id == scored, TeachingAssignment.subject_id == 2
        )
    )
    assert still is not None


def test_copy_assignments_fills_only_empty_subjects_from_a_same_grade_class(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    source = class_id_by_name(db_session, "11A1")
    target = new_class(api_client, headers).json()["id"]
    own = make_teacher(db_session, "co.san")
    api_client.put(
        f"{API}/admin/classes/{target}/assignments/2", headers=headers, json={"teacher_id": own.id}
    )
    url = f"{API}/admin/classes/{target}/assignments/copy"

    first = api_client.post(url, headers=headers, json={"from_class_id": source})
    second = api_client.post(url, headers=headers, json={"from_class_id": source})

    assert first.status_code == 200 and first.json() == {"copied": 11}  # 12 môn, trừ Toán đã có
    assert second.json() == {"copied": 0}
    math = db_session.scalar(
        select(TeachingAssignment.teacher_id).where(
            TeachingAssignment.class_id == target, TeachingAssignment.subject_id == 2
        )
    )
    assert math == own.id  # không bị đè
    copied_rows = audit(db_session, AuditAction.SET_ASSIGNMENT)
    assert copied_rows[-2].details == {"copied": 11, "from_class_id": source}


def test_copy_skips_locked_teachers_and_refuses_other_grades_or_itself(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    source = class_id_by_name(db_session, "11A1")
    grade10 = class_id_by_name(db_session, "10A1")
    target = new_class(api_client, headers).json()["id"]
    toan_teacher = db_session.scalar(
        select(TeachingAssignment.teacher_id).where(
            TeachingAssignment.class_id == source, TeachingAssignment.subject_id == 2
        )
    )
    api_client.patch(
        f"{API}/admin/users/{toan_teacher}", headers=headers, json={"is_active": False}
    )
    url = f"{API}/admin/classes/{target}/assignments/copy"

    other_grade = api_client.post(url, headers=headers, json={"from_class_id": grade10})
    itself = api_client.post(url, headers=headers, json={"from_class_id": target})
    unknown = api_client.post(url, headers=headers, json={"from_class_id": 999999})
    copied = api_client.post(url, headers=headers, json={"from_class_id": source})

    assert other_grade.status_code == 422 and itself.status_code == 422
    assert unknown.status_code == 404
    # Giáo viên Toán 11A1 cũng chủ nhiệm 11A1 và dạy nhiều môn: các môn của họ không được mang sang.
    taught = db_session.scalar(
        select(func.count())
        .select_from(TeachingAssignment)
        .where(TeachingAssignment.class_id == source, TeachingAssignment.teacher_id == toan_teacher)
    )
    assert copied.json()["copied"] == 12 - (taught or 0)


# --- Gỡ học sinh khỏi lớp -----------------------------------------------------------------------


def test_remove_a_student_without_data_deletes_the_link_and_the_orphan_record(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    class_id = new_class(api_client, headers).json()["id"]
    student_id = add_student(db_session, class_id, "HS9990001")
    url = f"{API}/admin/classes/{class_id}/students/remove"

    removed = api_client.post(url, headers=headers, json={"student_code": "  hs9990001 "})
    again = api_client.post(url, headers=headers, json={"student_code": "HS9990001"})

    assert removed.status_code == 200
    assert again.status_code == 404 and "mã đó" in again.json()["detail"]
    assert db_session.get(Student, student_id) is None
    logged = audit(db_session, AuditAction.REMOVE_CLASS_STUDENT)
    assert logged[0].class_id == class_id
    assert logged[0].details == {"student_id": student_id, "student_deleted": True}


def test_remove_keeps_the_student_record_when_they_are_in_another_class(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    first = new_class(api_client, headers).json()["id"]
    second = new_class(api_client, headers, name="11A8").json()["id"]
    student_id = add_student(db_session, first, "HS9990002")
    db_session.add(ClassStudent(class_id=second, student_id=student_id))
    db_session.flush()

    response = api_client.post(
        f"{API}/admin/classes/{first}/students/remove",
        headers=headers,
        json={"student_code": "HS9990002"},
    )

    assert response.status_code == 200
    assert db_session.get(Student, student_id) is not None
    assert (
        audit(db_session, AuditAction.REMOVE_CLASS_STUDENT)[0].details["student_deleted"] is False
    )


def test_remove_is_refused_for_a_student_with_data_and_for_the_wrong_class(
    api_client: TestClient, auth_headers: Headers, db_session: Session
) -> None:
    headers = auth_headers(ADMIN)
    class_11a2 = class_id_by_name(db_session, "11A2")
    class_11a1 = class_id_by_name(db_session, "11A1")
    before = db_session.scalar(select(func.count()).select_from(ClassStudent))

    has_data = api_client.post(
        f"{API}/admin/classes/{class_11a2}/students/remove",
        headers=headers,
        json={"student_code": "HS1102001"},
    )
    wrong_class = api_client.post(
        f"{API}/admin/classes/{class_11a1}/students/remove",
        headers=headers,
        json={"student_code": "HS1102001"},
    )

    assert has_data.status_code == 409 and "dữ liệu" in has_data.json()["detail"]
    assert "Trần" not in has_data.text  # không lộ tên học sinh
    assert wrong_class.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(ClassStudent)) == before

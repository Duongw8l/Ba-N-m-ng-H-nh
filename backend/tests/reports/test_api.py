"""API nhận xét và báo cáo (D-107): phân quyền, luồng sinh – sửa – duyệt, mã lỗi, nhật ký.

LLM luôn là `FakeWriter` (không gọi mạng). Mỗi test dùng DB seed thật qua `db_session` (rollback).
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.assistant.llm import LLMError, LLMNotConfigured
from app.auth.models import AuditLog, User
from app.core.enums import AuditAction, ReportStatus, ReportType
from app.reports import service
from app.reports.checks import NOTICES_VI
from app.reports.models import Report
from tests.reports.conftest import NEUTRAL, FailingWriter, FakeWriter

pytestmark = pytest.mark.db

GVCN_11A2 = "gvcn.11a2@example.com"
GVBM_TOAN_11 = "gv.toan.11@example.com"  # dạy Toán khối 11, chủ nhiệm 11A1
GVBM_VAN_11 = "gv.van.11@example.com"
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"
AN = "HS1102001"  # Trần Minh An, lớp 11A2

REPORTS = "/api/v1/reports"
Headers = Callable[[str], dict[str, str]]
UseLlm = Callable[..., None]


@pytest.fixture
def an_id(student_id_of: Callable[[str], int]) -> int:
    return student_id_of(AN)


@pytest.fixture
def first_student_of(
    db_session: Session, class_id_of: Callable[[str], int]
) -> Callable[[str], int]:
    def find(class_name: str) -> int:
        return repo.class_students(db_session, class_id_of(class_name))[0].student_id

    return find


def slip_body(class_id: int, student_id: int, **extra: Any) -> dict[str, Any]:
    return {
        "type": "contact_slip",
        "semester": "1",
        "class_id": class_id,
        "student_id": student_id,
        **extra,
    }


@pytest.fixture
def make_slip(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    an_id: int,
    use_llm: UseLlm,
) -> Callable[..., dict[str, Any]]:
    """GVCN 11A2 sinh phiếu liên lạc cho em An bằng `FakeWriter`; trả JSON của bản nháp."""

    def make(writer: FakeWriter | None = None) -> dict[str, Any]:
        use_llm(writer or FakeWriter())
        response = api_client.post(
            REPORTS,
            json=slip_body(class_id_of("11A2"), an_id),
            headers=auth_headers(GVCN_11A2),
        )
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    return make


# --- Chưa đăng nhập ---------------------------------------------------------------------------


def test_every_endpoint_requires_login_even_with_a_malformed_request(
    api_client: TestClient,
) -> None:
    assert api_client.post(REPORTS, json={}).status_code == 401
    assert api_client.get(REPORTS).status_code == 401
    assert api_client.put(f"{REPORTS}/1", json={}).status_code == 401
    assert api_client.post(f"{REPORTS}/1/regenerate", json={}).status_code == 401


# --- Phân quyền khi tạo -----------------------------------------------------------------------

# (email, loại, lớp, môn, khối, lớp của học sinh, mã trạng thái)
CREATE_MATRIX = [
    (GVCN_11A2, "contact_slip", "11A2", None, None, "11A2", 201),
    (GVCN_11A2, "school_record", "11A2", None, None, "11A2", 201),
    (GVCN_11A2, "contact_slip", "11A1", None, None, "11A1", 403),  # lớp khác
    (GVCN_11A2, "subject_comment", "11A2", "Ngữ văn", None, "11A2", 403),  # không dạy môn đó
    (GVCN_11A2, "report", "11A2", None, None, None, 201),
    (GVCN_11A2, "report", "11A1", None, None, None, 403),
    (GVCN_11A2, "report", None, None, 11, None, 403),  # báo cáo khối chỉ BGH
    (GVBM_VAN_11, "subject_comment", "11A2", "Ngữ văn", None, "11A2", 201),
    (GVBM_VAN_11, "subject_comment", "11A2", "Toán", None, "11A2", 403),  # môn khác
    (GVBM_VAN_11, "subject_comment", "10A1", "Ngữ văn", None, "10A1", 403),  # lớp khác
    (GVBM_VAN_11, "contact_slip", "11A2", None, None, "11A2", 403),
    (GVBM_VAN_11, "report", "11A2", None, None, None, 403),
    (GVBM_TOAN_11, "contact_slip", "11A1", None, None, "11A1", 201),  # chủ nhiệm 11A1
    (GVBM_TOAN_11, "subject_comment", "11A1", "Ngữ văn", None, "11A1", 403),
    (PRINCIPAL, "report", "11A2", None, None, None, 201),
    (PRINCIPAL, "report", None, None, 11, None, 201),
    (PRINCIPAL, "contact_slip", "11A2", None, None, "11A2", 403),  # BGH không viết nhận xét em
    (PRINCIPAL, "school_record", "11A2", None, None, "11A2", 403),
    (PRINCIPAL, "subject_comment", "11A2", "Ngữ văn", None, "11A2", 403),
    (ADMIN, "contact_slip", "11A2", None, None, "11A2", 403),
    (ADMIN, "subject_comment", "11A2", "Ngữ văn", None, "11A2", 403),
    (ADMIN, "report", "11A2", None, None, None, 403),
    (ADMIN, "report", None, None, 11, None, 403),
]


@pytest.mark.parametrize(
    ("email", "type_", "cls", "subject", "grade", "student_class", "expected"), CREATE_MATRIX
)
def test_create_permission_matrix(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
    first_student_of: Callable[[str], int],
    email: str,
    type_: str,
    cls: str | None,
    subject: str | None,
    grade: int | None,
    student_class: str | None,
    expected: int,
) -> None:
    use_llm(FakeWriter())
    body: dict[str, Any] = {"type": type_, "semester": "1"}
    if cls:
        body["class_id"] = class_id_of(cls)
    if subject:
        body["subject_id"] = subject_id_of(subject)
    if grade:
        body["grade_level"] = grade
    if student_class:
        body["student_id"] = first_student_of(student_class)

    response = api_client.post(REPORTS, json=body, headers=auth_headers(email))
    assert response.status_code == expected, response.text


def test_a_forbidden_request_calls_the_llm_zero_times(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    first_student_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    body = slip_body(class_id_of("11A1"), first_student_of("11A1"))
    assert api_client.post(REPORTS, json=body, headers=auth_headers(GVCN_11A2)).status_code == 403
    assert api_client.post(REPORTS, json=body, headers=auth_headers(ADMIN)).status_code == 403
    assert writer.calls == []


# --- Sinh một bản nháp ------------------------------------------------------------------------


def test_the_class_teacher_gets_a_draft_slip_that_is_never_approved_by_the_ai(
    db_session: Session, make_slip: Callable[..., dict[str, Any]], user_of: Callable[[str], User]
) -> None:
    body = make_slip()

    assert body["status"] == "draft" and body["status_label"] == "Bản nháp"
    assert body["type"] == "contact_slip" and body["scope"] == "student"
    assert body["text"] == " ".join(NEUTRAL.values())
    assert body["needs_manual"] is False and body["attempts"] == 1 and body["warnings"] == []
    assert body["student"]["student_code"] == AN
    assert "draft_text" not in body and "final_text" not in body

    row = db_session.get(Report, body["id"])
    assert row is not None
    assert row.status is ReportStatus.DRAFT and row.final_text is None
    assert row.approved_by is None and row.approved_at is None  # nguyên tắc 6
    assert row.created_by == user_of(GVCN_11A2).id
    assert row.prompt_version == "reports-v1" and row.model == "llm-gia"


def test_nothing_identifying_reaches_the_llm_and_no_tool_is_offered(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    an_id: int,
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    response = api_client.post(
        REPORTS, json=slip_body(class_id_of("11A2"), an_id), headers=auth_headers(GVCN_11A2)
    )
    assert response.status_code == 201

    guardian_name, guardian_phone = repo.student_guardian(db_session, an_id)
    assert guardian_name and guardian_phone
    sent = writer.sent()
    for secret in ("trần minh an", AN.casefold(), guardian_name.casefold(), guardian_phone):
        assert secret not in sent
    for key in ("date_of_birth", "guardian_name", "guardian_phone", "full_name", "student_code"):
        assert key not in sent
    assert "hs_01" in sent  # chỉ có mã tạm
    assert len(writer.calls) == 1


def test_generating_is_audited_without_the_text(
    db_session: Session, make_slip: Callable[..., dict[str, Any]], user_of: Callable[[str], User]
) -> None:
    body = make_slip()
    log = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.GENERATE_REPORT)
    ).one()
    assert log.user_id == user_of(GVCN_11A2).id and log.class_id == body["class_id"]
    assert log.details == {
        "report_id": body["id"],
        "type": "contact_slip",
        "semester": "1",
        "count": 1,
        "needs_manual": False,
    }


def test_text_that_fails_the_checks_three_times_is_left_for_the_teacher(
    db_session: Session, make_slip: Callable[..., dict[str, Any]]
) -> None:
    writer = FakeWriter(bad={"HS_01"})
    body = make_slip(writer)

    assert body["needs_manual"] is True and body["text"] == "" and body["attempts"] == 3
    assert "banned_negative" in body["check_notes"]
    assert len(writer.calls) == 3  # lần đầu và đúng 2 lần viết lại
    row = db_session.get(Report, body["id"])
    assert row is not None and row.draft_text == "" and row.status is ReportStatus.DRAFT
    assert "lười" not in row.draft_text and "lười" not in str(row.check_notes)


def test_posting_again_rewrites_the_same_draft_and_never_an_approved_one(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    an_id: int,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    first = make_slip()
    again = api_client.post(
        REPORTS, json=slip_body(class_id_of("11A2"), an_id), headers=auth_headers(GVCN_11A2)
    )
    assert again.status_code == 201 and again.json()["id"] == first["id"]
    assert len(db_session.scalars(select(Report)).all()) == 1

    approve = api_client.put(
        f"{REPORTS}/{first['id']}", json={"approve": True}, headers=auth_headers(GVCN_11A2)
    )
    assert approve.status_code == 200
    blocked = api_client.post(
        REPORTS, json=slip_body(class_id_of("11A2"), an_id), headers=auth_headers(GVCN_11A2)
    )
    assert blocked.status_code == 409
    row = db_session.get(Report, first["id"])
    assert row is not None and row.status is ReportStatus.APPROVED


def test_unknown_class_or_student_is_a_404_only_after_the_permission_check(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    first_student_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter())
    missing_class = {"type": "report", "semester": "1", "class_id": 999_999}
    assert (
        api_client.post(REPORTS, json=missing_class, headers=auth_headers(PRINCIPAL)).status_code
        == 404
    )
    # Giáo viên không biết lớp nào có thật: cùng 403 như lớp không được phân công.
    assert (
        api_client.post(REPORTS, json=missing_class, headers=auth_headers(GVCN_11A2)).status_code
        == 403
    )

    stranger = slip_body(class_id_of("11A2"), first_student_of("11A1"))
    response = api_client.post(REPORTS, json=stranger, headers=auth_headers(GVCN_11A2))
    assert response.status_code == 404
    assert (
        api_client.post(
            REPORTS, json=slip_body(class_id_of("11A2"), 999_999), headers=auth_headers(GVCN_11A2)
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "bad_body",
    [
        {"type": "subject_comment", "semester": "1", "class_id": 1},  # thiếu môn
        {"type": "subject_comment", "semester": "year", "class_id": 1, "subject_id": 1},
        {"type": "contact_slip", "semester": "1", "class_id": 1, "subject_id": 1},
        {"type": "contact_slip", "semester": "1"},  # thiếu lớp
        {"type": "contact_slip", "semester": "1", "class_id": 1, "grade_level": 11},
        {"type": "report", "semester": "1", "class_id": 1, "grade_level": 11},
        {"type": "report", "semester": "1"},
        {"type": "report", "semester": "1", "class_id": 1, "student_id": 1},
        {"type": "report", "semester": "1", "grade_level": 9},
        {"type": "contact_slip", "semester": "1", "class_id": 1, "feedback": "góp ý"},
        {"type": "contact_slip", "semester": "3", "class_id": 1, "student_id": 1},
        {"type": "invoice", "semester": "1", "class_id": 1, "student_id": 1},
        {"type": "contact_slip", "semester": "1", "class_id": 1, "student_id": 1, "x": 1},
        {
            "type": "contact_slip",
            "semester": "1",
            "class_id": 1,
            "student_id": 1,
            "feedback": "x" * 301,
        },
    ],
)
def test_malformed_requests_are_422(
    api_client: TestClient, auth_headers: Headers, use_llm: UseLlm, bad_body: dict[str, Any]
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    response = api_client.post(REPORTS, json=bad_body, headers=auth_headers(PRINCIPAL))
    assert response.status_code == 422
    assert writer.calls == []


def test_a_missing_llm_configuration_is_503_but_only_after_the_permission_check(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    an_id: int,
) -> None:
    use_llm(error=LLMNotConfigured("thiếu khoá"))
    body = slip_body(class_id_of("11A2"), an_id)
    assert api_client.post(REPORTS, json=body, headers=auth_headers(GVCN_11A2)).status_code == 503
    assert api_client.post(REPORTS, json=body, headers=auth_headers(ADMIN)).status_code == 403


def test_an_llm_failure_is_502_and_stores_nothing(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    an_id: int,
) -> None:
    use_llm(FailingWriter(LLMError("hết hạn mức")))
    response = api_client.post(
        REPORTS, json=slip_body(class_id_of("11A2"), an_id), headers=auth_headers(GVCN_11A2)
    )
    assert response.status_code == 502
    assert "hạn mức" not in response.text  # không lộ chi tiết nhà cung cấp
    assert db_session.scalars(select(Report)).all() == []


def test_the_anonymisation_barrier_failing_is_a_500_and_stores_nothing(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    an_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_llm(FakeWriter())

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise service.GenerationBlocked(
            "Không thể gửi dữ liệu cho mô hình ngôn ngữ một cách an toàn."
        )

    monkeypatch.setattr(service, "write", blocked)
    response = api_client.post(
        REPORTS, json=slip_body(class_id_of("11A2"), an_id), headers=auth_headers(GVCN_11A2)
    )
    assert response.status_code == 500
    assert db_session.scalars(select(Report)).all() == []


# --- Sửa và duyệt -----------------------------------------------------------------------------

EDITED = "Em học tập nghiêm túc, chăm chỉ và luôn hợp tác tốt với các thầy cô giáo trong lớp."


def put(client: TestClient, headers: dict[str, str], report_id: int, **json: Any) -> Any:
    return client.put(f"{REPORTS}/{report_id}", json=json, headers=headers)


def test_the_teacher_edits_then_approves_and_the_final_text_is_stored(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    make_slip: Callable[..., dict[str, Any]],
    user_of: Callable[[str], User],
) -> None:
    created = make_slip()
    headers = auth_headers(GVCN_11A2)

    edited = put(api_client, headers, created["id"], text=EDITED)
    assert edited.status_code == 200
    assert edited.json()["text"] == EDITED and edited.json()["status"] == "draft"

    approved = put(api_client, headers, created["id"], approve=True)
    body = approved.json()
    assert approved.status_code == 200
    assert body["status"] == "approved" and body["status_label"] == "Đã duyệt"
    assert body["text"] == EDITED and body["approved_at"] is not None

    row = db_session.get(Report, created["id"])
    assert row is not None
    assert row.status is ReportStatus.APPROVED and row.final_text == EDITED
    assert row.approved_by == user_of(GVCN_11A2).id
    actions = [
        log.action
        for log in db_session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        if log.action in {AuditAction.EDIT_REPORT, AuditAction.APPROVE_REPORT}
    ]
    assert actions == [AuditAction.EDIT_REPORT, AuditAction.APPROVE_REPORT]
    for log in db_session.scalars(select(AuditLog)).all():
        assert EDITED not in str(log.details)


def test_approving_twice_changes_nothing(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip()
    headers = auth_headers(GVCN_11A2)
    first = put(api_client, headers, created["id"], approve=True).json()
    second = put(api_client, headers, created["id"], approve=True).json()
    assert second["approved_at"] == first["approved_at"] and second["status"] == "approved"
    approvals = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.APPROVE_REPORT)
    ).all()
    assert len(approvals) == 1


def test_editing_an_approved_text_puts_it_back_to_draft(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip()
    headers = auth_headers(GVCN_11A2)
    put(api_client, headers, created["id"], approve=True)

    edited = put(api_client, headers, created["id"], text=EDITED)
    assert edited.json()["status"] == "draft" and edited.json()["approved_at"] is None
    row = db_session.get(Report, created["id"])
    assert row is not None
    assert row.final_text is None and row.approved_by is None  # không còn chữ "đã duyệt" cũ

    # Gửi lại đúng văn bản đang có thì không đổi trạng thái; sửa kèm duyệt thì duyệt lại bản mới.
    again = put(api_client, headers, created["id"], text=EDITED, approve=True).json()
    assert again["status"] == "approved" and again["text"] == EDITED


def test_a_draft_that_needs_the_teacher_cannot_be_approved_until_she_writes_it(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip(FakeWriter(bad={"HS_01"}))
    headers = auth_headers(GVCN_11A2)
    refused = put(api_client, headers, created["id"], approve=True)
    assert refused.status_code == 409
    assert put(api_client, headers, created["id"], text="   ").json()["needs_manual"] is True

    written = put(api_client, headers, created["id"], text=EDITED, approve=True)
    assert written.status_code == 200
    assert written.json()["status"] == "approved" and written.json()["needs_manual"] is False


def test_teacher_text_with_problems_is_saved_with_warnings(
    api_client: TestClient, auth_headers: Headers, make_slip: Callable[..., dict[str, Any]]
) -> None:
    created = make_slip()
    risky = "Em lười ôn bài, kém bạn cùng bàn và đạt điểm trung bình 9,9 ở môn Toán trong kỳ."
    response = put(api_client, auth_headers(GVCN_11A2), created["id"], text=risky)
    body = response.json()
    assert response.status_code == 200 and body["text"] == risky and body["status"] == "draft"
    joined = " ".join(body["warnings"])
    assert NOTICES_VI["banned_negative"] in joined
    assert NOTICES_VI["banned_comparison"] in joined
    assert "Số 9,9 không có trong dữ liệu" in joined  # số không có trong dữ liệu của em
    assert "Hãy viết" not in joined  # lời báo cho giáo viên, không phải lời dặn gửi AI


@pytest.mark.parametrize("payload", [{}, {"text": None}, {"approve": False}, {"extra": 1}])
def test_update_needs_text_or_approve(
    api_client: TestClient,
    auth_headers: Headers,
    make_slip: Callable[..., dict[str, Any]],
    payload: dict[str, Any],
) -> None:
    created = make_slip()
    response = put(api_client, auth_headers(GVCN_11A2), created["id"], **payload)
    assert response.status_code == 422


# --- Sinh lại ---------------------------------------------------------------------------------


def test_regenerating_a_draft_takes_the_teacher_feedback_without_the_name(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip()
    writer = FakeWriter(
        sections={**NEUTRAL, "goi_y": "Gia đình hãy động viên em ôn bài nhẹ nhàng."}
    )
    use_llm(writer)
    response = api_client.post(
        f"{REPORTS}/{created['id']}/regenerate",
        json={"feedback": "Trần Minh An cần được động viên nhiều hơn."},
        headers=auth_headers(GVCN_11A2),
    )
    assert response.status_code == 200 and response.json()["id"] == created["id"]
    assert "động viên em ôn bài" in response.json()["text"]
    sent = writer.sent()
    assert "trần minh an" not in sent and "hs_01 cần được động viên" in sent
    assert "<gop_y>" in sent


def test_an_approved_report_cannot_be_regenerated(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip()
    headers = auth_headers(GVCN_11A2)
    put(api_client, headers, created["id"], approve=True)
    writer = FakeWriter()
    use_llm(writer)
    response = api_client.post(f"{REPORTS}/{created['id']}/regenerate", json={}, headers=headers)
    assert response.status_code == 409
    assert writer.calls == []


def test_feedback_that_names_two_students_is_refused_without_calling_the_llm(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    make_slip: Callable[..., dict[str, Any]],
    db_session: Session,
    class_id_of: Callable[[str], int],
) -> None:
    created = make_slip()
    # Tìm một tên gọi riêng trùng nhau trong lớp 11A2 (dữ liệu seed có tên trùng).
    students = repo.class_students(db_session, class_id_of("11A2"))
    given: dict[str, int] = {}
    for student in students:
        name = student.full_name.split()[-1]
        given[name] = given.get(name, 0) + 1
    twin = next((name for name, count in given.items() if count > 1), None)
    if twin is None:
        pytest.skip("Lớp 11A2 trong seed không có hai em trùng tên gọi.")

    writer = FakeWriter()
    use_llm(writer)
    response = api_client.post(
        f"{REPORTS}/{created['id']}/regenerate",
        json={"feedback": f"{twin} cần cố gắng hơn."},
        headers=auth_headers(GVCN_11A2),
    )
    assert response.status_code == 422
    assert writer.calls == []


# --- Phân quyền trên bản đã có ----------------------------------------------------------------


@pytest.mark.parametrize("email", [ADMIN, PRINCIPAL, GVBM_VAN_11, GVBM_TOAN_11])
def test_nobody_else_can_touch_a_slip_of_another_class_teacher(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    make_slip: Callable[..., dict[str, Any]],
    email: str,
) -> None:
    created = make_slip()
    use_llm(FakeWriter())
    headers = auth_headers(email)
    assert put(api_client, headers, created["id"], text=EDITED).status_code == 403
    assert put(api_client, headers, created["id"], approve=True).status_code == 403
    regenerate = api_client.post(f"{REPORTS}/{created['id']}/regenerate", json={}, headers=headers)
    assert regenerate.status_code == 403


def test_an_unknown_report_id_is_403_for_everyone(
    api_client: TestClient, auth_headers: Headers
) -> None:
    for email in (ADMIN, PRINCIPAL, GVCN_11A2, GVBM_VAN_11):
        headers = auth_headers(email)
        assert put(api_client, headers, 999_999, approve=True).status_code == 403
        assert (
            api_client.post(f"{REPORTS}/999999/regenerate", json={}, headers=headers).status_code
            == 403
        )


def test_the_subject_teacher_writes_edits_and_approves_only_her_own_subject(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
    an_id: int,
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    body = {
        "type": "subject_comment",
        "semester": "1",
        "class_id": class_id_of("11A2"),
        "subject_id": subject_id_of("Ngữ văn"),
        "student_id": an_id,
    }
    created = api_client.post(REPORTS, json=body, headers=auth_headers(GVBM_VAN_11))
    assert created.status_code == 201
    report_id = created.json()["id"]
    assert created.json()["subject_id"] == body["subject_id"]
    # Chỉ số liệu môn Ngữ văn được gửi đi, không có môn khác của em.
    sent = writer.sent()
    assert "ngữ văn" in sent and "toán" not in sent and "tiếng anh" not in sent
    assert "attendance" not in sent and "conduct" not in sent

    assert put(api_client, auth_headers(GVBM_VAN_11), report_id, approve=True).status_code == 200
    for email in (GVBM_TOAN_11, GVCN_11A2, PRINCIPAL, ADMIN):
        assert put(api_client, auth_headers(email), report_id, text=EDITED).status_code == 403


# --- Danh sách --------------------------------------------------------------------------------


def test_the_list_has_every_student_of_the_class_with_or_without_a_draft(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    make_slip: Callable[..., dict[str, Any]],
) -> None:
    created = make_slip()
    query = f"?type=contact_slip&semester=1&class_id={class_id_of('11A2')}"
    response = api_client.get(REPORTS + query, headers=auth_headers(GVCN_11A2))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 40 and response.json()["job"] is None
    with_report = [i for i in items if i["report"] is not None]
    assert [i["report"]["id"] for i in with_report] == [created["id"]]
    assert with_report[0]["student"]["student_code"] == AN
    assert all(i["student"]["full_name"] for i in items)

    other_semester = api_client.get(
        REPORTS + query.replace("semester=1", "semester=2"), headers=auth_headers(GVCN_11A2)
    )
    assert all(i["report"] is None for i in other_semester.json()["items"])

    log = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.VIEW_CLASS_REPORTS)
    ).first()
    assert log is not None and log.details["count"] == 40


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        (GVCN_11A2, 200),
        (PRINCIPAL, 403),  # danh sách nhận xét học sinh có tên: chỉ người viết
        (ADMIN, 403),
        (GVBM_VAN_11, 403),
        (GVBM_TOAN_11, 403),  # chủ nhiệm lớp khác
    ],
)
def test_who_may_list_the_slips_of_a_class(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    email: str,
    expected: int,
) -> None:
    url = f"{REPORTS}?type=contact_slip&semester=1&class_id={class_id_of('11A2')}"
    assert api_client.get(url, headers=auth_headers(email)).status_code == expected


def test_the_subject_teacher_lists_only_comments_of_her_own_subject(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    query = f"?type=subject_comment&semester=1&class_id={class_id_of('11A2')}&subject_id="
    van, toan = subject_id_of("Ngữ văn"), subject_id_of("Toán")
    assert (
        api_client.get(f"{REPORTS}{query}{van}", headers=auth_headers(GVBM_VAN_11)).status_code
        == 200
    )
    assert (
        api_client.get(f"{REPORTS}{query}{toan}", headers=auth_headers(GVBM_VAN_11)).status_code
        == 403
    )
    assert (
        api_client.get(f"{REPORTS}{query}{van}", headers=auth_headers(GVCN_11A2)).status_code == 403
    )


# --- Báo cáo lớp và khối ----------------------------------------------------------------------


def test_class_report_is_written_by_the_class_teacher_and_approved_by_the_principal(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    class_id = class_id_of("11A2")
    body = {"type": "report", "semester": "1", "class_id": class_id}
    created = api_client.post(REPORTS, json=body, headers=auth_headers(GVCN_11A2))
    assert created.status_code == 201
    report = created.json()
    assert report["scope"] == "class" and report["target_id"] == class_id
    assert report["student"] is None and report["status"] == "draft"

    # Không có học sinh nào (tên, mã) trong dữ liệu gửi LLM.
    for student in repo.class_students(db_session, class_id):
        assert student.full_name.casefold() not in writer.sent()
        assert student.student_code.casefold() not in writer.sent()

    listing = api_client.get(
        f"{REPORTS}?type=report&semester=1&class_id={class_id}", headers=auth_headers(PRINCIPAL)
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["report"]["id"] == report["id"]
    approved = put(api_client, auth_headers(PRINCIPAL), report["id"], approve=True)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    row = db_session.get(Report, report["id"])
    assert row is not None and row.created_by != row.approved_by


def test_grade_report_is_for_the_principal_only_and_compares_classes(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    body = {"type": "report", "semester": "1", "grade_level": 11}
    created = api_client.post(REPORTS, json=body, headers=auth_headers(PRINCIPAL))
    assert created.status_code == 201
    report = created.json()
    assert report["scope"] == "grade" and report["target_id"] == 11 and report["class_id"] is None

    sent = writer.sent()
    assert "11a1" in sent and "11a3" in sent  # so sánh các lớp trong khối
    for name in ("11A1", "11A2", "11A3"):
        for student in repo.class_students(db_session, class_id_of(name)):
            assert student.full_name.casefold() not in sent

    for email in (GVCN_11A2, GVBM_TOAN_11, GVBM_VAN_11, ADMIN):
        denied = api_client.post(REPORTS, json=body, headers=auth_headers(email))
        assert denied.status_code == 403
        assert put(api_client, auth_headers(email), report["id"], approve=True).status_code == 403
    listing = api_client.get(
        f"{REPORTS}?type=report&semester=1&grade_level=11", headers=auth_headers(PRINCIPAL)
    )
    assert listing.json()["items"][0]["report"]["id"] == report["id"]
    assert (
        api_client.get(
            f"{REPORTS}?type=report&semester=1&grade_level=11", headers=auth_headers(GVCN_11A2)
        ).status_code
        == 403
    )


def test_a_report_the_ai_cannot_write_is_left_for_the_principal(
    api_client: TestClient, auth_headers: Headers, use_llm: UseLlm
) -> None:
    use_llm(FakeWriter(sections={**NEUTRAL, "can_co_gang": "Một số em lười làm bài tập về nhà."}))
    body = {"type": "report", "semester": "1", "grade_level": 12}
    created = api_client.post(REPORTS, json=body, headers=auth_headers(PRINCIPAL))
    assert created.status_code == 201
    assert created.json()["needs_manual"] is True and created.json()["text"] == ""
    assert ReportType.REPORT.value == created.json()["type"]

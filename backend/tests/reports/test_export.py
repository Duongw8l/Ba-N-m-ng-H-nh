"""Xuất PDF (D-108): chỉ bản đã duyệt, đúng nội dung, đúng quyền, không lộ dữ liệu thừa.

Chữ trong PDF được trích lại bằng `pypdf` để kiểm tiếng Việt có dấu hiển thị đúng (phông nhúng).
"""

from collections.abc import Callable
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.config import load_config
from app.auth.models import AuditLog
from app.core.enums import AuditAction, ReportType
from app.reports import export, pdf
from app.reports import facts as report_facts
from tests.reports.conftest import FakeWriter

pytestmark = pytest.mark.db

GVCN_11A2 = "gvcn.11a2@example.com"
GVBM_TOAN_11 = "gv.toan.11@example.com"
GVBM_VAN_11 = "gv.van.11@example.com"
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"
AN = "HS1102001"

REPORTS = "/api/v1/reports"
Headers = Callable[[str], dict[str, str]]
UseLlm = Callable[..., None]
SCHOOL = "Trường THPT Thử Nghiệm"
APPROVED_TEXT = (
    "Em học tập nghiêm túc và hợp tác tốt với thầy cô. Em cần duy trì thói quen ôn bài mỗi ngày."
)


def text_of(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return " ".join(" ".join(page.extract_text().split()) for page in reader.pages)


@pytest.fixture(autouse=True)
def school_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export, "get_settings", lambda: SimpleNamespace(school_name=SCHOOL))


@pytest.fixture
def approved_slip(
    make_slip: Callable[..., dict[str, Any]], api_client: TestClient, auth_headers: Headers
) -> dict[str, Any]:
    created = make_slip()
    response = api_client.put(
        f"{REPORTS}/{created['id']}",
        json={"text": APPROVED_TEXT, "approve": True},
        headers=auth_headers(GVCN_11A2),
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def make_slip(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    student_id_of: Callable[[str], int],
    use_llm: UseLlm,
) -> Callable[..., dict[str, Any]]:
    def make() -> dict[str, Any]:
        use_llm(FakeWriter())
        response = api_client.post(
            REPORTS,
            json={
                "type": "contact_slip",
                "semester": "1",
                "class_id": class_id_of("11A2"),
                "student_id": student_id_of(AN),
            },
            headers=auth_headers(GVCN_11A2),
        )
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    return make


def export_of(client: TestClient, headers: dict[str, str], report_id: int) -> Any:
    return client.get(f"{REPORTS}/{report_id}/export?format=pdf", headers=headers)


# --- Chỉ bản đã duyệt -------------------------------------------------------------------------


def test_a_draft_cannot_be_exported(
    api_client: TestClient, auth_headers: Headers, make_slip: Callable[..., dict[str, Any]]
) -> None:
    created = make_slip()
    response = export_of(api_client, auth_headers(GVCN_11A2), created["id"])
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/json")  # không có PDF nào


def test_a_draft_that_needs_the_teacher_cannot_be_exported_either(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    student_id_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter(bad={"HS_01"}))
    created = api_client.post(
        REPORTS,
        json={
            "type": "contact_slip",
            "semester": "1",
            "class_id": class_id_of("11A2"),
            "student_id": student_id_of(AN),
        },
        headers=auth_headers(GVCN_11A2),
    ).json()
    assert export_of(api_client, auth_headers(GVCN_11A2), created["id"]).status_code == 409


def test_editing_an_approved_text_withdraws_the_export_until_it_is_approved_again(
    api_client: TestClient, auth_headers: Headers, approved_slip: dict[str, Any]
) -> None:
    headers = auth_headers(GVCN_11A2)
    assert export_of(api_client, headers, approved_slip["id"]).status_code == 200
    api_client.put(
        f"{REPORTS}/{approved_slip['id']}",
        json={"text": "Em đã có nhiều tiến bộ rõ rệt trong học kỳ này, mong em tiếp tục cố gắng."},
        headers=headers,
    )
    assert export_of(api_client, headers, approved_slip["id"]).status_code == 409


def test_only_the_format_pdf_exists(
    api_client: TestClient, auth_headers: Headers, approved_slip: dict[str, Any]
) -> None:
    headers = auth_headers(GVCN_11A2)
    url = f"{REPORTS}/{approved_slip['id']}/export"
    assert api_client.get(f"{url}?format=docx", headers=headers).status_code == 422
    assert api_client.get(url, headers=headers).status_code == 200  # mặc định là pdf


# --- Nội dung phiếu liên lạc ------------------------------------------------------------------


def test_the_slip_pdf_has_school_class_term_student_guardian_scores_and_text(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    approved_slip: dict[str, Any],
) -> None:
    response = export_of(api_client, auth_headers(GVCN_11A2), approved_slip["id"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"] == (
        'attachment; filename="phieu-lien-lac-HS1102001-hk1.pdf"'
    )
    text = text_of(response.content)

    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None
    student = next(s for s in repo.class_students(db_session, info.id) if s.student_code == AN)
    guardian_name, guardian_phone = repo.student_guardian(db_session, student.student_id)
    assert guardian_name and guardian_phone
    for expected in (
        SCHOOL,
        "PHIẾU LIÊN LẠC",
        "Học kỳ I · Lớp 11A2",
        "Năm học",
        student.full_name,
        AN,
        f"Kính gửi phụ huynh: {guardian_name}",
        "Giáo viên chủ nhiệm",
        " ".join(APPROVED_TEXT.split()),
    ):
        assert expected in text, expected
    assert guardian_phone not in text  # số điện thoại phụ huynh không in ra phiếu

    # Số trong bảng điểm là số của Analytics, viết kiểu Việt Nam.
    facts = report_facts.student_facts(
        db_session,
        info,
        student.student_id,
        ReportType.CONTACT_SLIP,
        "1",
        load_config(db_session),
    )
    assert facts is not None
    for subject in facts["subjects"]:
        assert subject["name"] in text
        if subject.get("average") is not None:
            assert pdf.format_score(subject["average"]) in text
    away = facts["attendance_since_start_of_year"]
    assert f"Số buổi nghỉ từ đầu năm học: {away['absent_total']}" in text


def test_the_pdf_never_prints_the_date_of_birth_or_the_draft(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    approved_slip: dict[str, Any],
    student_id_of: Callable[[str], int],
) -> None:
    from app.classes.models import Student

    student = db_session.get(Student, student_id_of(AN))
    assert student is not None and student.date_of_birth is not None
    content = export_of(api_client, auth_headers(GVCN_11A2), approved_slip["id"]).content
    text = text_of(content)
    born = student.date_of_birth
    assert born.strftime("%d/%m/%Y") not in text and str(born.year) not in text.split("Năm học")[0]
    assert "Em học tập nghiêm túc và hoà đồng" not in text  # bản nháp AI viết, đã bị thay


def test_export_is_audited_without_the_text(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    approved_slip: dict[str, Any],
) -> None:
    export_of(api_client, auth_headers(GVCN_11A2), approved_slip["id"])
    log = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.EXPORT_REPORT)
    ).one()
    assert log.details == {
        "report_id": approved_slip["id"],
        "type": "contact_slip",
        "semester": "1",
        "format": "pdf",
    }


@pytest.mark.parametrize("email", [ADMIN, PRINCIPAL, GVBM_VAN_11, GVBM_TOAN_11])
def test_nobody_but_the_class_teacher_can_export_the_slip(
    api_client: TestClient, auth_headers: Headers, approved_slip: dict[str, Any], email: str
) -> None:
    assert export_of(api_client, auth_headers(email), approved_slip["id"]).status_code == 403
    assert api_client.get(f"{REPORTS}/{approved_slip['id']}/export").status_code == 401


def test_exporting_an_unknown_report_is_403(api_client: TestClient, auth_headers: Headers) -> None:
    assert export_of(api_client, auth_headers(GVCN_11A2), 999_999).status_code == 403


# --- Các loại khác ----------------------------------------------------------------------------


def create_and_approve(
    client: TestClient, headers: dict[str, str], body: dict[str, Any], approver: dict[str, str]
) -> int:
    created = client.post(REPORTS, json=body, headers=headers)
    assert created.status_code == 201, created.text
    report_id: int = created.json()["id"]
    assert (
        client.put(f"{REPORTS}/{report_id}", json={"approve": True}, headers=approver).status_code
        == 200
    )
    return report_id


def test_a_school_record_and_a_subject_comment_have_their_own_titles_and_signers(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
    student_id_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter())
    base = {"semester": "1", "class_id": class_id_of("11A2"), "student_id": student_id_of(AN)}
    record = create_and_approve(
        api_client,
        auth_headers(GVCN_11A2),
        {"type": "school_record", **base},
        auth_headers(GVCN_11A2),
    )
    comment = create_and_approve(
        api_client,
        auth_headers(GVBM_VAN_11),
        {"type": "subject_comment", "subject_id": subject_id_of("Ngữ văn"), **base},
        auth_headers(GVBM_VAN_11),
    )

    record_text = text_of(export_of(api_client, auth_headers(GVCN_11A2), record).content)
    assert "NHẬN XÉT HỌC BẠ" in record_text and "Giáo viên chủ nhiệm" in record_text
    assert "Kết quả học tập" not in record_text  # bảng điểm chỉ có ở phiếu liên lạc

    comment_text = text_of(export_of(api_client, auth_headers(GVBM_VAN_11), comment).content)
    assert "NHẬN XÉT MÔN HỌC" in comment_text and "Môn học: Ngữ văn" in comment_text
    assert "Giáo viên bộ môn" in comment_text and "Trần Minh An" in comment_text


def test_class_and_grade_reports_are_signed_by_who_approved_them(
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    class_id_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter())
    class_report = create_and_approve(
        api_client,
        auth_headers(GVCN_11A2),
        {"type": "report", "semester": "2", "class_id": class_id_of("11A2")},
        auth_headers(GVCN_11A2),
    )
    grade_report = create_and_approve(
        api_client,
        auth_headers(PRINCIPAL),
        {"type": "report", "semester": "year", "grade_level": 11},
        auth_headers(PRINCIPAL),
    )

    cls = api_client.get(f"{REPORTS}/{class_report}/export", headers=auth_headers(GVCN_11A2))
    assert cls.headers["content-disposition"] == 'attachment; filename="bao-cao-11A2-hk2.pdf"'
    class_text = text_of(cls.content)
    assert "BÁO CÁO LỚP 11A2" in class_text and "Học kỳ II" in class_text
    assert "Giáo viên chủ nhiệm" in class_text

    grade = api_client.get(f"{REPORTS}/{grade_report}/export", headers=auth_headers(PRINCIPAL))
    assert grade.headers["content-disposition"] == (
        'attachment; filename="bao-cao-khoi-11-ca-nam.pdf"'
    )
    grade_text = text_of(grade.content)
    assert "BÁO CÁO KHỐI 11" in grade_text and "Cả năm" in grade_text
    assert "Ban giám hiệu" in grade_text
    assert export_of(api_client, auth_headers(GVCN_11A2), grade_report).status_code == 403


# --- Phông và định dạng -----------------------------------------------------------------------


def test_every_vietnamese_letter_is_printed_with_its_marks() -> None:
    letters = (
        "ăâđêôơư ÁÀẢÃẠ ẮẰẲẴẶ ẤẦẨẪẬ ÉÈẺẼẸ ẾỀỂỄỆ ÍÌỈĨỊ ÓÒỎÕỌ ỐỒỔỖỘ ỚỜỞỠỢ ÚÙỦŨỤ ỨỪỬỮỰ ÝỲỶỸỴ – “” ₫"
    )
    document = pdf.PdfDocument(
        school_name=SCHOOL,
        school_year="2026-2027",
        title="KIỂM TRA PHÔNG",
        subtitle=letters,
        body=letters,
        signer_title="Giáo viên",
        signer_name="Nguyễn Thị Ánh Tuyết",
        approved_on=date(2026, 10, 13),
    )
    text = text_of(pdf.render(document))
    assert letters in text and "Nguyễn Thị Ánh Tuyết" in text and "13/10/2026" in text


def test_scores_are_written_the_vietnamese_way() -> None:
    assert pdf.format_score(6.5) == "6,5"
    assert pdf.format_score(8) == "8,0"
    assert pdf.format_score(10.0) == "10,0"


def test_text_with_markup_characters_is_printed_literally() -> None:
    document = pdf.PdfDocument(
        school_name="A & B <THPT>",
        school_year="2026-2027",
        title="BÁO CÁO",
        subtitle="Học kỳ I",
        body="Điểm <b>cao</b> & ổn định.\n\nĐoạn hai.",
        signer_title="Giáo viên",
        signer_name="X",
        approved_on=date(2026, 10, 13),
    )
    text = text_of(pdf.render(document))
    assert "A & B <THPT>" in text and "Điểm <b>cao</b> & ổn định." in text
    assert "Đoạn hai." in text

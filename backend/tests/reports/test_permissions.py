"""Ai được tạo, sửa, duyệt, xuất nhận xét và báo cáo (D-102): ma trận vai trò × loại × phạm vi."""

from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.authorize import AuthorizationError
from app.core.enums import ReportScope, ReportType
from app.reports.permissions import authorize_report, scope_for

pytestmark = pytest.mark.db

GVCN_11A2 = "gvcn.11a2@example.com"  # chủ nhiệm 11A2, không dạy môn nào
GVBM_VAN_11 = "gv.van.11@example.com"  # dạy Ngữ văn mọi lớp khối 11
GVBM_TOAN_11 = "gv.toan.11@example.com"  # dạy Toán khối 11 và chủ nhiệm 11A1
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"

SUBJECT = ReportType.SUBJECT_COMMENT
RECORD = ReportType.SCHOOL_RECORD
SLIP = ReportType.CONTACT_SLIP
REPORT = ReportType.REPORT

# (email, loại, lớp, môn, khối, được phép)
MATRIX = [
    # Nhận xét môn: chỉ người dạy đúng lớp-môn. GVCN không dạy môn đó, BGH, Admin đều không.
    (GVBM_VAN_11, SUBJECT, "11A2", "Ngữ văn", None, True),
    (GVBM_VAN_11, SUBJECT, "11A2", "Toán", None, False),
    (GVBM_VAN_11, SUBJECT, "10A1", "Ngữ văn", None, False),
    (GVBM_TOAN_11, SUBJECT, "11A1", "Toán", None, True),
    (GVBM_TOAN_11, SUBJECT, "11A1", "Ngữ văn", None, False),  # chủ nhiệm nhưng không dạy môn đó
    (GVCN_11A2, SUBJECT, "11A2", "Ngữ văn", None, False),
    (PRINCIPAL, SUBJECT, "11A2", "Ngữ văn", None, False),
    (ADMIN, SUBJECT, "11A2", "Ngữ văn", None, False),
    # Học bạ và phiếu liên lạc: chỉ GVCN của lớp.
    (GVCN_11A2, RECORD, "11A2", None, None, True),
    (GVCN_11A2, SLIP, "11A2", None, None, True),
    (GVCN_11A2, RECORD, "11A1", None, None, False),
    (GVCN_11A2, SLIP, "10A1", None, None, False),
    (GVBM_TOAN_11, SLIP, "11A1", None, None, True),  # chủ nhiệm 11A1
    (GVBM_TOAN_11, SLIP, "11A2", None, None, False),  # chỉ dạy Toán ở 11A2
    (GVBM_VAN_11, RECORD, "11A2", None, None, False),
    (PRINCIPAL, RECORD, "11A2", None, None, False),  # BGH không viết nhận xét học sinh
    (PRINCIPAL, SLIP, "11A2", None, None, False),
    (ADMIN, RECORD, "11A2", None, None, False),
    (ADMIN, SLIP, "11A2", None, None, False),
    # Báo cáo lớp: GVCN của lớp hoặc BGH.
    (GVCN_11A2, REPORT, "11A2", None, None, True),
    (GVCN_11A2, REPORT, "11A1", None, None, False),
    (GVBM_TOAN_11, REPORT, "11A1", None, None, True),
    (GVBM_TOAN_11, REPORT, "11A2", None, None, False),
    (GVBM_VAN_11, REPORT, "11A2", None, None, False),
    (PRINCIPAL, REPORT, "11A2", None, None, True),
    (PRINCIPAL, REPORT, "10A1", None, None, True),
    (ADMIN, REPORT, "11A2", None, None, False),
    # Báo cáo khối: chỉ BGH.
    (PRINCIPAL, REPORT, None, None, 11, True),
    (GVCN_11A2, REPORT, None, None, 11, False),
    (GVBM_TOAN_11, REPORT, None, None, 11, False),
    (GVBM_VAN_11, REPORT, None, None, 11, False),
    (ADMIN, REPORT, None, None, 11, False),
]


@pytest.mark.parametrize(("email", "report_type", "cls", "subject", "grade", "allowed"), MATRIX)
def test_permission_matrix(
    db_session: Session,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
    email: str,
    report_type: ReportType,
    cls: str | None,
    subject: str | None,
    grade: int | None,
    allowed: bool,
) -> None:
    user = db_session.scalar(select(User).where(func.lower(User.email) == email))
    assert user is not None
    kwargs = {
        "report_type": report_type,
        "class_id": class_id_of(cls) if cls else None,
        "subject_id": subject_id_of(subject) if subject else None,
        "grade_level": grade,
    }
    if allowed:
        authorize_report(db_session, user, **kwargs)  # type: ignore[arg-type]
    else:
        with pytest.raises(AuthorizationError):
            authorize_report(db_session, user, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("report_type", "class_id", "subject_id", "grade"),
    [
        (SUBJECT, 1, None, None),  # nhận xét môn thiếu môn
        (SUBJECT, None, 1, None),  # nhận xét môn thiếu lớp
        (RECORD, None, None, 11),  # học bạ không có phạm vi khối
        (REPORT, None, None, None),  # báo cáo không nói lớp hay khối
    ],
)
def test_a_malformed_target_is_refused_even_for_the_principal(
    db_session: Session,
    report_type: ReportType,
    class_id: int | None,
    subject_id: int | None,
    grade: int | None,
) -> None:
    principal = db_session.scalar(select(User).where(func.lower(User.email) == PRINCIPAL))
    assert principal is not None
    with pytest.raises(AuthorizationError):
        authorize_report(
            db_session,
            principal,
            report_type=report_type,
            class_id=class_id,
            subject_id=subject_id,
            grade_level=grade,
        )


def test_scope_follows_the_type_and_the_target() -> None:
    assert scope_for(SUBJECT, class_id=1) is ReportScope.STUDENT
    assert scope_for(RECORD, class_id=1) is ReportScope.STUDENT
    assert scope_for(SLIP, class_id=1) is ReportScope.STUDENT
    assert scope_for(REPORT, class_id=1) is ReportScope.CLASS
    assert scope_for(REPORT, class_id=None) is ReportScope.GRADE

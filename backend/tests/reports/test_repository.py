"""Lưu bản vào DB (D-102): một dòng mỗi khoá, ghi đè nháp, không bao giờ ghi đè bản đã duyệt."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.enums import ReportScope, ReportStatus, ReportType
from app.reports.generation import Outcome
from app.reports.models import Report
from app.reports.repository import ReportKey, find_report, store_outcome

pytestmark = pytest.mark.db


@pytest.fixture
def key(class_id_of: Callable[[str], int], student_id_of: Callable[[str], int]) -> ReportKey:
    return ReportKey(
        ReportType.CONTACT_SLIP,
        ReportScope.STUDENT,
        student_id_of("HS1102001"),
        "1",
        None,
        class_id_of("11A2"),
    )


@pytest.fixture
def teacher(db_session: Session) -> User:
    user = db_session.scalar(select(User).where(func.lower(User.email) == "gvcn.11a2@example.com"))
    assert user is not None
    return user


def outcome(text: str, *, manual: bool = False, attempts: int = 1) -> Outcome:
    return Outcome(1, text, manual, ("banned_negative",) if manual else (), attempts)


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Report)) or 0


def test_a_new_key_creates_one_draft(db_session: Session, key: ReportKey, teacher: User) -> None:
    report = store_outcome(db_session, key, outcome("Bản một."), user_id=teacher.id, model="m1")
    assert count(db_session) == 1
    assert report.status is ReportStatus.DRAFT and report.draft_text == "Bản một."
    assert report.final_text is None and report.approved_by is None
    assert report.created_by == teacher.id and report.model == "m1"
    assert find_report(db_session, key) is report


def test_a_draft_with_the_same_key_is_overwritten_in_place(
    db_session: Session, key: ReportKey, teacher: User
) -> None:
    first = store_outcome(db_session, key, outcome("Bản một."), user_id=teacher.id, model="m1")
    second = store_outcome(
        db_session, key, outcome("", manual=True, attempts=3), user_id=teacher.id, model="m2"
    )
    assert second.id == first.id and count(db_session) == 1
    assert second.draft_text == "" and second.needs_manual and second.attempts == 3
    assert second.check_notes == ["banned_negative"] and second.model == "m2"


def test_an_approved_report_is_never_overwritten(
    db_session: Session, key: ReportKey, teacher: User
) -> None:
    report = store_outcome(db_session, key, outcome("Bản một."), user_id=teacher.id, model="m1")
    report.status = ReportStatus.APPROVED
    report.final_text = "Bản một."
    report.approved_by = teacher.id
    report.approved_at = datetime.now(UTC)
    db_session.flush()

    again = store_outcome(db_session, key, outcome("Bản hai."), user_id=teacher.id, model="m2")
    assert again.id == report.id and count(db_session) == 1
    assert again.status is ReportStatus.APPROVED
    assert again.draft_text == "Bản một." and again.final_text == "Bản một."
    assert again.model == "m1"


def test_a_key_with_a_subject_is_separate_from_the_one_without(
    db_session: Session,
    key: ReportKey,
    teacher: User,
    subject_id_of: Callable[[str], int],
) -> None:
    store_outcome(db_session, key, outcome("Không môn."), user_id=teacher.id, model="m")
    with_subject = ReportKey(
        ReportType.SUBJECT_COMMENT,
        key.scope,
        key.target_id,
        key.semester,
        subject_id_of("Ngữ văn"),
        key.class_id,
    )
    other_subject = ReportKey(
        ReportType.SUBJECT_COMMENT,
        key.scope,
        key.target_id,
        key.semester,
        subject_id_of("Toán"),
        key.class_id,
    )
    store_outcome(db_session, with_subject, outcome("Văn."), user_id=teacher.id, model="m")
    store_outcome(db_session, other_subject, outcome("Toán."), user_id=teacher.id, model="m")
    assert count(db_session) == 3
    assert find_report(db_session, with_subject) is not find_report(db_session, other_subject)

"""Truy vấn và ghi `reports`, `report_jobs` (Giai đoạn 9). Quyền do service kiểm."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import ReportJobStatus, ReportScope, ReportStatus, ReportType
from app.reports.generation import Outcome
from app.reports.models import Report, ReportJob
from app.reports.prompts import PROMPT_VERSION

# Một lần gọi LLM có thể chờ lâu khi chạm hạn mức theo phút (nhà cung cấp chờ rồi thử lại), nên coi
# job là mất luồng (backend khởi động lại) chỉ sau một khoảng dài không có nhịp.
STALE_AFTER = timedelta(minutes=6)
INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class ReportKey:
    """Khoá duy nhất của một bản: mỗi khoá chỉ có một dòng trong `reports`."""

    type: ReportType
    scope: ReportScope
    target_id: int  # id học sinh, id lớp hoặc số khối
    semester: str
    subject_id: int | None
    class_id: int | None


def key_of(report: Report) -> ReportKey:
    return ReportKey(
        report.type,
        report.scope,
        report.target_id,
        report.semester,
        report.subject_id,
        report.class_id,
    )


def _match(key: ReportKey) -> list[ColumnElement[bool]]:
    return [
        Report.type == key.type,
        Report.scope == key.scope,
        Report.target_id == key.target_id,
        Report.semester == key.semester,
        Report.subject_id.is_(None)
        if key.subject_id is None
        else Report.subject_id == key.subject_id,
    ]


def find_report(session: Session, key: ReportKey) -> Report | None:
    return session.scalar(select(Report).where(*_match(key)))


def reports_for_students(
    session: Session,
    *,
    report_type: ReportType,
    semester: str,
    subject_id: int | None,
    student_ids: Iterable[int],
) -> dict[int, Report]:
    """Bản của từng học sinh (theo id học sinh) cho một loại, kỳ và môn."""
    subject = Report.subject_id.is_(None) if subject_id is None else Report.subject_id == subject_id
    rows = session.scalars(
        select(Report).where(
            Report.type == report_type,
            Report.scope == ReportScope.STUDENT,
            Report.semester == semester,
            subject,
            Report.target_id.in_(list(student_ids)),
        )
    )
    return {report.target_id: report for report in rows}


def apply_outcome(report: Report, outcome: Outcome, model: str) -> None:
    """Ghi kết quả một lần sinh vào bản: luôn về nháp (nguyên tắc 6), xoá dấu vết đã duyệt cũ."""
    report.draft_text = outcome.text
    report.final_text = None
    report.status = ReportStatus.DRAFT
    report.approved_by = None
    report.approved_at = None
    report.needs_manual = outcome.needs_manual
    report.check_notes = list(outcome.notes)
    report.attempts = outcome.attempts
    report.model = model
    report.prompt_version = PROMPT_VERSION


def store_outcome(
    session: Session, key: ReportKey, outcome: Outcome, *, user_id: int, model: str
) -> Report:
    """Tạo bản mới hoặc ghi đè bản nháp cùng khoá. Bản ĐÃ DUYỆT không bao giờ bị ghi đè ở đây:
    trả về nguyên trạng (chặn đã làm ở service, đây là lớp bảo vệ khi hai yêu cầu chạy đua)."""
    existing = find_report(session, key)
    if existing is None:
        report = Report(
            scope=key.scope,
            target_id=key.target_id,
            type=key.type,
            semester=key.semester,
            subject_id=key.subject_id,
            class_id=key.class_id,
            created_by=user_id,
            draft_text="",
        )
        apply_outcome(report, outcome, model)
        try:
            with session.begin_nested():
                session.add(report)
                session.flush()
            return report
        except IntegrityError:  # hai yêu cầu cùng tạo một khoá: lấy bản của yêu cầu kia
            existing = find_report(session, key)
            if existing is None:
                raise
    if existing.status is ReportStatus.APPROVED:
        return existing
    apply_outcome(existing, outcome, model)
    session.flush()
    return existing


# --- Công việc sinh cả lớp --------------------------------------------------------------------


def refresh_stale(session: Session, job: ReportJob) -> ReportJob:
    """Job đang chạy nhưng lâu không có nhịp thì luồng đã mất (khởi động lại): đánh dấu đã dừng."""
    running = job.status is ReportJobStatus.RUNNING
    if running and datetime.now(UTC) - job.heartbeat_at > STALE_AFTER:
        job.status = ReportJobStatus.STOPPED
        job.error_code = INTERRUPTED
        job.finished_at = datetime.now(UTC)
        session.commit()
    return job


def latest_job(
    session: Session,
    *,
    class_id: int,
    report_type: ReportType,
    semester: str,
    subject_id: int | None,
) -> ReportJob | None:
    subject = (
        ReportJob.subject_id.is_(None) if subject_id is None else ReportJob.subject_id == subject_id
    )
    job = session.scalar(
        select(ReportJob)
        .where(
            ReportJob.class_id == class_id,
            ReportJob.type == report_type,
            ReportJob.semester == semester,
            subject,
        )
        .order_by(ReportJob.id.desc())
        .limit(1)
    )
    return None if job is None else refresh_stale(session, job)

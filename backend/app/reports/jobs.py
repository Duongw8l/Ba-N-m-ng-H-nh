"""Sinh nhận xét cho cả lớp, chạy nền và có tiến độ (Giai đoạn 9, D-104).

`POST /reports` không kèm `student_id` tạo một dòng `report_jobs` rồi giao việc cho một luồng riêng
(`start_in_thread`) và trả ngay 202. Luồng chạy từng nhóm `BATCH_SIZE` em (số liệu → LLM → kiểm →
lưu bản nháp), commit sau MỖI em nên tiến độ nhìn thấy ngay và lỗi giữa chừng không làm mất phần đã
viết. Gặp lỗi LLM (hết hạn mức, mạng) thì dừng, giữ phần đã xong; bấm sinh lại (cùng yêu cầu) sẽ bỏ
qua em đã có bản và chỉ viết phần còn thiếu.

Luồng nền chạy trong tiến trình của backend: khởi động lại là mất luồng. Job `running` lâu không có
nhịp được coi là đã dừng khi đọc (`repository.refresh_stale`). Mỗi lớp-loại-kỳ-môn chỉ có một job
đang chạy (khoá tư vấn của PostgreSQL chặn hai yêu cầu cùng lúc).
"""

import logging
import threading
import zlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.config import load_config
from app.analytics.schemas import Period
from app.assistant.llm import LLMError, LLMProvider
from app.assistant.scope import load_roster
from app.auth.audit import record_access
from app.auth.models import User
from app.core.authorize import AuthorizationError
from app.core.db import get_session_factory
from app.core.enums import AuditAction, ReportJobStatus, ReportScope
from app.core.pseudonymize import UnsafePayload
from app.reports import facts as report_facts
from app.reports import repository, service
from app.reports.generation import BATCH_SIZE, Outcome, StudentItem, generate_students
from app.reports.models import ReportJob
from app.reports.permissions import authorize_report
from app.reports.repository import ReportKey, store_outcome
from app.reports.schemas import ReportIn

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractContextManager[Session]]
JobRunner = Callable[[int, LLMProvider], None]  # (job_id, provider)

ERROR_LLM = "llm_error"
ERROR_UNSAFE = "unsafe_payload"
ERROR_FORBIDDEN = "forbidden"
ERROR_INTERNAL = "internal_error"


def _lock_key(class_id: int, report_type: str, semester: str, subject_id: int | None) -> int:
    return zlib.crc32(f"report-job:{class_id}:{report_type}:{semester}:{subject_id}".encode())


def start_class_job(
    session: Session,
    user: User,
    provider_factory: service.ProviderFactory,
    runner: JobRunner,
    body: ReportIn,
) -> ReportJob:
    """Tạo job sinh cả lớp và giao cho `runner`; trả job đang chạy nếu đã có một cái cùng phạm vi.

    Ném AuthorizationError (403), NotFound (404), LLMNotConfigured (503; chỉ SAU khi kiểm quyền).
    """
    info = service.resolve_class_for_list(session, user, body)
    provider = provider_factory()

    # Hai yêu cầu cùng lúc cho cùng phạm vi chỉ tạo một job.
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                _lock_key(info.id, body.type.value, body.semester, body.subject_id)
            )
        )
    )
    current = repository.latest_job(
        session,
        class_id=info.id,
        report_type=body.type,
        semester=body.semester,
        subject_id=body.subject_id,
    )
    if current is not None and current.status is ReportJobStatus.RUNNING:
        session.commit()
        return current

    students = repo.class_students(session, info.id)
    existing = repository.reports_for_students(
        session,
        report_type=body.type,
        semester=body.semester,
        subject_id=body.subject_id,
        student_ids=[s.student_id for s in students],
    )
    pending = [s for s in students if s.student_id not in existing]
    job = ReportJob(
        class_id=info.id,
        type=body.type,
        semester=body.semester,
        subject_id=body.subject_id,
        created_by=user.id,
        total=len(pending),
        status=ReportJobStatus.RUNNING if pending else ReportJobStatus.DONE,
        finished_at=None if pending else datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    if pending:
        runner(job.id, provider)
    return job


def get_job(session: Session, user: User, job_id: int) -> ReportJob:
    """Tiến độ một job. Id lạ cũng là 403, và quyền xem tiến độ giống quyền tạo nó."""
    job = session.get(ReportJob, job_id)
    if job is None:
        raise AuthorizationError
    authorize_report(
        session,
        user,
        report_type=job.type,
        class_id=job.class_id,
        subject_id=job.subject_id,
    )
    return repository.refresh_stale(session, job)


# --- Luồng nền --------------------------------------------------------------------------------


def start_in_thread(job_id: int, provider: LLMProvider) -> None:
    """Chạy job trong một luồng daemon với phiên DB riêng (không dùng phiên của request)."""
    thread = threading.Thread(
        target=run_job,
        args=(job_id, provider, get_session_factory()),
        name=f"report-job-{job_id}",
        daemon=True,
    )
    thread.start()


def run_job(job_id: int, provider: LLMProvider, session_factory: SessionFactory) -> None:
    """Thân luồng nền. Không bao giờ ném lỗi ra ngoài: mọi lỗi thành `stopped` kèm mã lỗi."""
    with session_factory() as session:
        try:
            _run(session, job_id, provider)
        except Exception:  # luồng nền không được làm sập tiến trình hay bỏ job ở "running"
            logger.exception("Job nhận xét %s gặp lỗi bất ngờ", job_id)
            session.rollback()
            _finish(session, job_id, ReportJobStatus.STOPPED, ERROR_INTERNAL)


def _finish(session: Session, job_id: int, status: ReportJobStatus, error: str | None) -> ReportJob:
    job = session.get(ReportJob, job_id)
    assert job is not None
    job.status = status
    job.error_code = error
    job.finished_at = datetime.now(UTC)
    session.commit()
    return job


def _run(session: Session, job_id: int, provider: LLMProvider) -> None:
    job = session.get(ReportJob, job_id)
    assert job is not None
    user = session.get(User, job.created_by)
    info = repo.get_class(session, job.class_id)
    if user is None or not user.is_active or info is None:
        _finish(session, job_id, ReportJobStatus.STOPPED, ERROR_FORBIDDEN)
        return
    try:  # quyền có thể đã đổi từ lúc bấm nút (hạ vai trò, đổi phân công)
        authorize_report(
            session,
            user,
            report_type=job.type,
            class_id=job.class_id,
            subject_id=job.subject_id,
        )
    except AuthorizationError:
        _finish(session, job_id, ReportJobStatus.STOPPED, ERROR_FORBIDDEN)
        return

    config = load_config(session)
    period = cast(Period, job.semester)
    roster = load_roster(session, [info.id])
    who = {r.student_id: r for r in roster}
    students = repo.class_students(session, info.id)
    existing = repository.reports_for_students(
        session,
        report_type=job.type,
        semester=job.semester,
        subject_id=job.subject_id,
        student_ids=[s.student_id for s in students],
    )
    pending = [s for s in students if s.student_id not in existing]
    job.total = job.done + len(pending)
    session.commit()

    def save(outcome: Outcome) -> None:
        key = ReportKey(
            job.type, ReportScope.STUDENT, outcome.key, job.semester, job.subject_id, info.id
        )
        store_outcome(session, key, outcome, user_id=user.id, model=provider.model)
        job.done += 1
        job.needs_manual += 1 if outcome.needs_manual else 0
        job.heartbeat_at = datetime.now(UTC)
        session.commit()

    error: str | None = None
    try:
        for start in range(0, len(pending), BATCH_SIZE):
            items: list[StudentItem] = []
            for student in pending[start : start + BATCH_SIZE]:
                facts = report_facts.student_facts(
                    session,
                    info,
                    student.student_id,
                    job.type,
                    period,
                    config,
                    subject_id=job.subject_id,
                )
                if facts is None:  # em không còn số liệu để viết: bỏ qua nhưng vẫn tính là đã xử lý
                    job.done += 1
                else:
                    items.append(StudentItem(who[student.student_id], facts))
            session.commit()  # nhả giao dịch đọc trước khi chờ LLM
            generate_students(
                provider,
                report_type=job.type,
                items=items,
                roster=roster,
                open_class_id=info.id,
                on_outcome=save,
            )
    except LLMError:
        error = ERROR_LLM
    except UnsafePayload:
        logger.error("Hàng rào ẩn danh chặn job nhận xét %s", job_id)
        error = ERROR_UNSAFE

    finished = _finish(
        session, job_id, ReportJobStatus.STOPPED if error else ReportJobStatus.DONE, error
    )
    record_access(
        session,
        user,
        AuditAction.GENERATE_REPORT,
        class_id=info.id,
        details={
            "job_id": job_id,
            "type": finished.type.value,
            "semester": finished.semester,
            "count": finished.done,
            "needs_manual": finished.needs_manual,
            "status": finished.status.value,
        },
    )

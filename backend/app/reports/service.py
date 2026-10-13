"""Dịch vụ nhận xét và báo cáo (Giai đoạn 9, D-107).

Luồng một bản (FLOWS luồng 5): kiểm quyền → lấy số liệu từ Analytics → LLM viết (ẩn danh, kiểm tự
động, viết lại tối đa 2 lần) → lưu `draft` → giáo viên sửa → duyệt (đổi mã tạm còn sót về tên, lưu
`final_text`) → xuất PDF. Mọi hàm công khai gọi `authorize_report()` TRƯỚC khi đọc dữ liệu học
sinh; bản có id lạ hay của lớp khác đều trả cùng AuthorizationError (403), không lộ id nào có thật.
"""

import json
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.config import load_config
from app.analytics.schemas import Period
from app.assistant.llm import LLMProvider
from app.assistant.scope import load_roster
from app.auth.audit import record_access
from app.auth.models import User
from app.core.authorize import AuthorizationError
from app.core.enums import AuditAction, ReportScope, ReportStatus
from app.core.labels import label_vi
from app.core.pseudonymize import Pseudonymizer, RosterStudent, UnsafePayload
from app.reports import facts as report_facts
from app.reports import generation, repository
from app.reports.checks import check_text
from app.reports.generation import Outcome, StudentItem
from app.reports.models import Report, ReportJob
from app.reports.permissions import STUDENT_TYPES, authorize_report, scope_for
from app.reports.repository import ReportKey, find_report, store_outcome
from app.reports.schemas import (
    JobOut,
    ReportIn,
    ReportItemOut,
    ReportListOut,
    ReportOut,
    ReportTarget,
    ReportUpdateIn,
    StudentRefOut,
)

ProviderFactory = Callable[[], LLMProvider]


class NotFound(LookupError):
    """Lớp, học sinh hoặc số liệu không có (chỉ tới được sau khi kiểm quyền)."""


class Conflict(Exception):
    """Thao tác không hợp lệ ở trạng thái hiện tại (ví dụ sinh lại bản đã duyệt)."""


class GenerationBlocked(RuntimeError):
    """Hàng rào ẩn danh chặn không cho gọi LLM (dữ liệu còn danh tính thật)."""


@dataclass(frozen=True)
class Resolved:
    key: ReportKey
    info: repo.ClassInfo | None  # None với báo cáo khối
    student: repo.StudentInfo | None


# --- Chuyển đổi ra schema ---------------------------------------------------------------------


def student_ref(student: repo.StudentInfo) -> StudentRefOut:
    return StudentRefOut(
        id=student.student_id, student_code=student.student_code, full_name=student.full_name
    )


def to_out(
    report: Report, student: repo.StudentInfo | None = None, warnings: list[str] | None = None
) -> ReportOut:
    approved = report.status is ReportStatus.APPROVED
    return ReportOut(
        id=report.id,
        type=report.type,
        type_label=label_vi(report.type),
        scope=report.scope,
        semester=cast(Period, report.semester),  # CHECK ở DB chỉ cho 1, 2, year
        class_id=report.class_id,
        subject_id=report.subject_id,
        target_id=report.target_id,
        status=report.status,
        status_label=label_vi(report.status),
        text=(report.final_text or "") if approved else report.draft_text,
        needs_manual=report.needs_manual,
        check_notes=list(report.check_notes or []),
        attempts=report.attempts,
        model=report.model,
        created_at=report.created_at,
        updated_at=report.updated_at,
        approved_at=report.approved_at,
        student=None if student is None else student_ref(student),
        warnings=warnings or [],
    )


def job_out(job: ReportJob) -> JobOut:
    return JobOut(
        id=job.id,
        class_id=job.class_id,
        type=job.type,
        semester=job.semester,
        subject_id=job.subject_id,
        status=job.status,
        status_label=label_vi(job.status),
        total=job.total,
        done=job.done,
        needs_manual=job.needs_manual,
        error_code=job.error_code,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


# --- Tra cứu ----------------------------------------------------------------------------------


def _class_or_404(session: Session, class_id: int | None) -> repo.ClassInfo:
    info = None if class_id is None else repo.get_class(session, class_id)
    if info is None:
        raise NotFound("Không có lớp này.")
    return info


def _student_of(session: Session, class_id: int, student_id: int) -> repo.StudentInfo | None:
    return next(
        (s for s in repo.class_students(session, class_id) if s.student_id == student_id), None
    )


def resolve(session: Session, user: User, target: ReportTarget, student_id: int | None) -> Resolved:
    """Kiểm quyền (403) rồi tra lớp, học sinh (404). Trả khoá của bản cần làm việc."""
    authorize_report(
        session,
        user,
        report_type=target.type,
        class_id=target.class_id,
        subject_id=target.subject_id,
        grade_level=target.grade_level,
    )
    scope = scope_for(target.type, class_id=target.class_id)
    if scope is ReportScope.GRADE:
        grade = target.grade_level
        if grade is None or not repo.classes_in_grade(session, grade):
            raise NotFound("Khối này chưa có lớp nào.")
        return Resolved(
            ReportKey(target.type, scope, grade, target.semester, None, None), None, None
        )
    info = _class_or_404(session, target.class_id)
    if scope is ReportScope.CLASS:
        key = ReportKey(target.type, scope, info.id, target.semester, None, info.id)
        return Resolved(key, info, None)
    if student_id is None:
        raise ValueError("Nhận xét học sinh cần student_id.")
    student = _student_of(session, info.id, student_id)
    if student is None:
        raise NotFound("Không có học sinh này trong lớp.")
    key = ReportKey(target.type, scope, student_id, target.semester, target.subject_id, info.id)
    return Resolved(key, info, student)


def load_authorized(session: Session, user: User, report_id: int) -> Report:
    """Bản theo id sau khi kiểm quyền. Id lạ cũng là 403 để không lộ id nào có thật."""
    report = session.get(Report, report_id)
    if report is None:
        raise AuthorizationError
    authorize_report(
        session,
        user,
        report_type=report.type,
        class_id=report.class_id,
        subject_id=report.subject_id,
        grade_level=report.target_id if report.scope is ReportScope.GRADE else None,
    )
    return report


def resolved_of(session: Session, report: Report) -> Resolved:
    """Dựng lại `Resolved` từ một bản đã có (đã qua `load_authorized`)."""
    info = None if report.class_id is None else repo.get_class(session, report.class_id)
    if report.scope is not ReportScope.GRADE and info is None:
        raise NotFound("Không có lớp này.")
    student = None
    if report.scope is ReportScope.STUDENT and info is not None:
        student = _student_of(session, info.id, report.target_id)
    return Resolved(repository.key_of(report), info, student)


# --- Số liệu và viết --------------------------------------------------------------------------


def facts_for(session: Session, resolved: Resolved) -> dict[str, Any]:
    key, info = resolved.key, resolved.info
    config = load_config(session)
    period = cast(Period, key.semester)
    result: dict[str, Any] | None
    if key.scope is ReportScope.GRADE:
        result = report_facts.grade_facts(session, key.target_id, period, config)
    elif info is None:
        result = None
    elif key.scope is ReportScope.CLASS:
        result = report_facts.class_facts(session, info, period, config)
    elif resolved.student is None:
        result = None
    else:
        result = report_facts.student_facts(
            session,
            info,
            resolved.student.student_id,
            key.type,
            period,
            config,
            subject_id=key.subject_id,
        )
    if result is None:
        raise NotFound("Chưa có số liệu để viết bản này.")
    return result


def roster_for(session: Session, resolved: Resolved) -> list[RosterStudent]:
    """Học sinh mà bộ ẩn danh phải biết để bắt họ tên thật lọt vào dữ liệu hoặc văn bản."""
    if resolved.key.scope is ReportScope.GRADE:
        classes = repo.classes_in_grade(session, resolved.key.target_id)
        return load_roster(session, [c.id for c in classes])
    assert resolved.info is not None
    return load_roster(session, [resolved.info.id])


def _scope_label(resolved: Resolved) -> str:
    if resolved.key.scope is ReportScope.GRADE:
        return f"khối {resolved.key.target_id}"
    assert resolved.info is not None
    return f"lớp {resolved.info.name}"


def write(
    session: Session,
    provider: LLMProvider,
    resolved: Resolved,
    facts: dict[str, Any],
    roster: list[RosterStudent],
    feedback: str | None,
) -> Outcome:
    """Nhờ LLM viết một bản. Ném LLMError, FeedbackRejected, GenerationBlocked."""
    key = resolved.key
    open_class = resolved.info.id if resolved.info is not None else None
    try:
        if key.scope is ReportScope.STUDENT:
            assert resolved.student is not None
            who = next(r for r in roster if r.student_id == resolved.student.student_id)
            outcomes: list[Outcome] = []
            generation.generate_students(
                provider,
                report_type=key.type,
                items=[StudentItem(who, facts)],
                roster=roster,
                open_class_id=open_class or 0,
                on_outcome=outcomes.append,
                feedback=feedback,
            )
            return outcomes[0]
        return generation.generate_aggregate(
            provider,
            scope_label=_scope_label(resolved),
            facts=facts,
            roster=roster,
            open_class_id=open_class,
            feedback=feedback,
        )
    except UnsafePayload as error:
        message = "Không thể gửi dữ liệu cho mô hình ngôn ngữ một cách an toàn."
        raise GenerationBlocked(message) from error


def _generate_and_store(
    session: Session,
    user: User,
    provider_factory: ProviderFactory,
    resolved: Resolved,
    feedback: str | None,
) -> Report:
    provider = provider_factory()  # LLMNotConfigured nếu thiếu cấu hình (sau khi kiểm quyền)
    facts = facts_for(session, resolved)
    roster = roster_for(session, resolved)
    session.commit()  # nhả giao dịch đọc trước khi chờ LLM (có thể mất vài chục giây)
    outcome = write(session, provider, resolved, facts, roster, feedback)
    report = store_outcome(session, resolved.key, outcome, user_id=user.id, model=provider.model)
    record_access(
        session,
        user,
        AuditAction.GENERATE_REPORT,
        class_id=resolved.key.class_id,
        details={
            "report_id": report.id,
            "type": resolved.key.type.value,
            "semester": resolved.key.semester,
            "count": 1,
            "needs_manual": outcome.needs_manual,
        },
    )
    return report


# --- API --------------------------------------------------------------------------------------


def generate(
    session: Session, user: User, provider_factory: ProviderFactory, body: ReportIn
) -> ReportOut:
    """Sinh một nhận xét học sinh (có student_id) hoặc một báo cáo lớp / khối."""
    resolved = resolve(session, user, body, body.student_id)
    existing = find_report(session, resolved.key)
    if existing is not None and existing.status is ReportStatus.APPROVED:
        raise Conflict("Bản này đã duyệt. Hãy sửa nội dung để đưa về bản nháp rồi mới sinh lại.")
    report = _generate_and_store(session, user, provider_factory, resolved, body.feedback)
    return to_out(report, resolved.student)


def regenerate(
    session: Session,
    user: User,
    provider_factory: ProviderFactory,
    report_id: int,
    feedback: str | None,
) -> ReportOut:
    report = load_authorized(session, user, report_id)
    if report.status is ReportStatus.APPROVED:
        raise Conflict("Bản này đã duyệt. Hãy sửa nội dung để đưa về bản nháp rồi mới sinh lại.")
    resolved = resolved_of(session, report)
    stored = _generate_and_store(session, user, provider_factory, resolved, feedback)
    return to_out(stored, resolved.student)


def list_reports(session: Session, user: User, target: ReportTarget) -> ReportListOut:
    """Mỗi học sinh của lớp kèm bản (hoặc None), hoặc bản báo cáo lớp / khối."""
    if target.type in STUDENT_TYPES:
        resolved_class = resolve_class_for_list(session, user, target)
        students = repo.class_students(session, resolved_class.id)
        record_access(
            session,
            user,
            AuditAction.VIEW_CLASS_REPORTS,
            class_id=resolved_class.id,
            details={
                "type": target.type.value,
                "semester": target.semester,
                "count": len(students),
            },
        )
        reports = repository.reports_for_students(
            session,
            report_type=target.type,
            semester=target.semester,
            subject_id=target.subject_id,
            student_ids=[s.student_id for s in students],
        )
        items = [
            ReportItemOut(
                student=student_ref(s),
                report=None if s.student_id not in reports else to_out(reports[s.student_id], s),
            )
            for s in students
        ]
        job = repository.latest_job(
            session,
            class_id=resolved_class.id,
            report_type=target.type,
            semester=target.semester,
            subject_id=target.subject_id,
        )
        return ReportListOut(items=items, job=None if job is None else job_out(job))

    resolved = resolve(session, user, target, None)
    report = find_report(session, resolved.key)
    return ReportListOut(
        items=[ReportItemOut(student=None, report=None if report is None else to_out(report))],
        job=None,
    )


def resolve_class_for_list(session: Session, user: User, target: ReportTarget) -> repo.ClassInfo:
    authorize_report(
        session,
        user,
        report_type=target.type,
        class_id=target.class_id,
        subject_id=target.subject_id,
    )
    return _class_or_404(session, target.class_id)


def _clean(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _final_text(report: Report, student: repo.StudentInfo | None) -> str:
    """Đổi mã tạm còn sót về họ tên thật khi duyệt (PROMPTS Giai đoạn 9). Nhận xét gọi học sinh là
    "em" nên thường không có gì để đổi; đây là lớp an toàn."""
    if student is None or report.scope is not ReportScope.STUDENT:
        return report.draft_text
    pseudo = Pseudonymizer()
    pseudo.code_for(
        RosterStudent(
            student.student_id, report.class_id or 0, student.full_name, student.student_code
        )
    )
    return pseudo.depseudonymize(report.draft_text)


def _warnings(session: Session, resolved: Resolved, text: str) -> list[str]:
    """Cảnh báo kiểm tự động cho văn bản giáo viên sửa: nhắc, không chặn."""
    if not text.strip():
        return []
    try:
        facts = facts_for(session, resolved)
    except NotFound:
        return []
    pseudo = Pseudonymizer(roster_for(session, resolved))
    violations = check_text(
        text,
        evidence=json.dumps(facts, ensure_ascii=False, default=str),
        student_scope=resolved.key.scope is ReportScope.STUDENT,
        pseudo=pseudo,
    )
    return [v.notice() for v in violations]


def update_report(session: Session, user: User, report_id: int, body: ReportUpdateIn) -> ReportOut:
    """Giáo viên sửa văn bản và/hoặc duyệt. Sửa bản đã duyệt đưa nó về nháp (D-102)."""
    report = load_authorized(session, user, report_id)
    resolved = resolved_of(session, report)
    details: dict[str, Any] = {
        "report_id": report.id,
        "type": report.type.value,
        "semester": report.semester,
    }

    edited = False
    if body.text is not None:
        text = _clean(body.text)
        if text != report.draft_text:
            edited = True
            report.draft_text = text
            if text:
                report.needs_manual = False
            if report.status is ReportStatus.APPROVED:
                report.status = ReportStatus.DRAFT
                report.final_text = None
                report.approved_by = None
                report.approved_at = None
    approved_now = False
    if body.approve and report.status is not ReportStatus.APPROVED:
        if not report.draft_text.strip():
            raise Conflict("Chưa có nội dung để duyệt. Hãy viết nhận xét trước.")
        report.needs_manual = False
        report.final_text = _final_text(report, resolved.student)
        report.status = ReportStatus.APPROVED
        report.approved_by = user.id
        report.approved_at = datetime.now(UTC)
        approved_now = True
    session.commit()

    if edited:
        record_access(
            session, user, AuditAction.EDIT_REPORT, class_id=report.class_id, details=details
        )
    if approved_now:
        record_access(
            session, user, AuditAction.APPROVE_REPORT, class_id=report.class_id, details=details
        )
    warnings = _warnings(session, resolved, report.draft_text)
    return to_out(report, resolved.student, warnings)

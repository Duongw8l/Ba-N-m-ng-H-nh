"""Luồng nhập tệp: tạo bản xem trước (chưa ghi dữ liệu) và xác nhận (ghi trong một transaction).

Bản xem trước lưu trong bảng import_jobs (D-059): chỉ các giá trị đã chuẩn hoá của dòng hợp lệ, hết
hạn sau 24 giờ. Xác nhận chỉ ghi đúng những gì đã xem; có dòng lỗi thì không ghi gì.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics import repository as analytics_repo
from app.analytics.config import load_config
from app.auth.audit import record_access
from app.auth.models import User
from app.core.authorize import AuthorizationError, authorize_admin, authorize_write
from app.core.enums import (
    AssessmentType,
    AuditAction,
    ConductPeriod,
    ImportKind,
    ImportStatus,
)
from app.imports import mappings as templates
from app.imports import repository as repo
from app.imports import roster, validation
from app.imports.columns import FieldSpec, detect_header_line, fields_for, resolve_mapping
from app.imports.models import ImportJob
from app.imports.parsing import read_grid, table_from_grid
from app.imports.schemas import (
    ClassSubjectRef,
    ConfirmOut,
    FieldOut,
    MessageOut,
    PreviewOut,
    RowOut,
    SummaryOut,
)
from app.imports.validation import RowResult
from app.imports.writer import write_job

JOB_TTL = timedelta(hours=24)
PREVIEW_ROW_LIMIT = 500  # số dòng "bình thường" tối đa trong bản xem trước; dòng lỗi luôn có đủ


class ImportJobNotFound(Exception):
    """Không có bản xem trước này."""


class ImportJobExpired(Exception):
    """Bản xem trước đã quá hạn 24 giờ: phải tải lại tệp."""


class ImportJobInvalid(Exception):
    """Bản xem trước còn dòng lỗi hoặc thiếu cột bắt buộc: không được xác nhận."""


class ImportConflict(Exception):
    """Dữ liệu của lớp đã đổi từ lúc xem trước (ví dụ học sinh đã bị gỡ khỏi lớp)."""


@dataclass(frozen=True)
class PreviewRequest:
    class_id: int
    kind: ImportKind
    filename: str
    data: bytes
    subject: analytics_repo.SubjectInfo | None = None  # chỉ khi nhập điểm
    semester: int | None = None
    period: ConductPeriod | None = None
    header_row: int | None = None
    mapping: Mapping[str, str | None] | None = None
    mapping_name: str | None = None
    save_mapping_as: str | None = None
    allow_partial: bool = False


def purge_expired(session: Session) -> None:
    session.execute(delete(ImportJob).where(ImportJob.expires_at < datetime.now(UTC)))


def _summary(results: Sequence[RowResult]) -> SummaryOut:
    created = sum(r.new_records for r in results)
    updated = sum(r.changed_records for r in results)
    return SummaryOut(
        total_rows=len(results),
        error_rows=sum(1 for r in results if r.status == "error"),
        warning_rows=sum(1 for r in results if r.status == "warning"),
        new_rows=sum(1 for r in results if r.action == "new"),
        changed_rows=sum(1 for r in results if r.action == "changed"),
        unchanged_rows=sum(1 for r in results if r.action == "unchanged"),
        records_to_create=created,
        records_to_update=updated,
        records_unchanged=sum(r.unchanged_records for r in results),
        has_changes=bool(created or updated),
    )


def _row_out(result: RowResult) -> RowOut:
    return RowOut(
        line=result.line,
        student_code=result.student_code,
        full_name=result.full_name,
        status=result.status,
        action=result.action,
        values=result.values,
        existing=result.existing,
        messages=[MessageOut(column=m.column, message=m.message) for m in result.messages],
    )


def _rows_for_preview(results: Sequence[RowResult]) -> tuple[list[RowOut], bool]:
    """Mọi dòng lỗi và cảnh báo, cộng dòng khác cho tới `PREVIEW_ROW_LIMIT`, theo thứ tự dòng."""
    flagged = [r for r in results if r.status != "ok"]
    room = max(0, PREVIEW_ROW_LIMIT - len(flagged))
    chosen = {id(r) for r in flagged}
    for result in results:
        if room == 0:
            break
        if id(result) not in chosen:
            chosen.add(id(result))
            room -= 1
    shown = [r for r in results if id(r) in chosen]
    return [_row_out(r) for r in shown], len(shown) < len(results)


def _validate(
    session: Session,
    request: PreviewRequest,
    table: Any,
    mapping: Mapping[str, str | None],
    fields: Sequence[FieldSpec],
) -> list[RowResult]:
    if request.kind is ImportKind.ROSTER:
        return roster.validate_roster(
            table,
            mapping,
            class_id=request.class_id,
            memberships=roster.class_memberships(session, roster.codes_in(table, mapping)),
        )
    students = repo.students_by_code(session, request.class_id)
    if request.kind is ImportKind.ATTENDANCE:
        start, end = analytics_repo.school_year_range(session, request.class_id)
        return validation.validate_attendance(
            table,
            mapping,
            students=students,
            existing=repo.existing_attendance(session, request.class_id, start, end),
            year_start=start,
            year_end=end,
        )
    if request.kind is ImportKind.CONDUCT:
        assert request.period is not None
        return validation.validate_conduct(
            table,
            mapping,
            students=students,
            existing=repo.existing_conduct(session, request.class_id, request.period),
        )
    assert request.subject is not None and request.semester is not None
    if request.subject.assessment_type is AssessmentType.COMMENT:
        return validation.validate_comments(
            table,
            mapping,
            students=students,
            existing=repo.existing_comments(
                session, request.class_id, request.subject.id, request.semester
            ),
            allow_partial=request.allow_partial,
        )
    return validation.validate_scores(
        table,
        mapping,
        fields,
        students=students,
        existing=repo.existing_scores(
            session, request.class_id, request.subject.id, request.semester
        ),
        allow_partial=request.allow_partial,
    )


def create_preview(session: Session, user: User, request: PreviewRequest) -> PreviewOut:
    """Đọc, ánh xạ, kiểm và so sánh tệp; lưu job. KHÔNG ghi gì vào bảng dữ liệu.

    Ném ImportFileError (parsing.py) khi tệp không đọc được; người gọi đổi thành HTTP.
    """
    purge_expired(session)
    grid = read_grid(request.filename, request.data)

    is_comment = (
        request.subject is not None and request.subject.assessment_type is AssessmentType.COMMENT
    )
    tx_required = 0
    if request.subject is not None and not is_comment:
        tx_required = load_config(session).required_regular(request.subject.periods_per_year)
    fields = fields_for(
        request.kind,
        tx_required=tx_required,
        is_comment_subject=is_comment,
        allow_partial=request.allow_partial,
    )

    notes: list[str] = []
    template = None
    if request.mapping_name:
        template = templates.get_template(session, user.id, request.kind, request.mapping_name)
        if template is None:
            notes.append(f"Không có mẫu ánh xạ tên '{request.mapping_name}'.")
    header_line = (
        request.header_row
        or (template.header_row if template is not None and template.header_row else None)
        or detect_header_line(grid, fields)
    )
    table = table_from_grid(grid, header_line)
    resolution = resolve_mapping(
        table.headers,
        fields,
        template=template.mapping if template is not None else None,
        explicit=request.mapping,
    )
    notes += resolution.notes

    field_out = [
        FieldOut(
            name=spec.name,
            label=spec.label,
            required=spec.required,
            column=resolution.mapping.get(spec.name),
        )
        for spec in fields
    ]
    subject_ref = (
        ClassSubjectRef(id=request.subject.id, name=request.subject.name)
        if request.subject is not None
        else None
    )
    common: dict[str, Any] = {
        "kind": request.kind,
        "class_id": request.class_id,
        "subject": subject_ref,
        "semester": request.semester,
        "period": request.period,
        "file_name": request.filename,
        "header_line": header_line,
        "detected_columns": [h for h in table.headers if h],
        "fields": field_out,
        "missing_required": resolution.missing_required,
        "ignored_columns": resolution.ignored_columns,
        "notes": notes,
    }

    if resolution.missing_required:
        return PreviewOut(
            job_id=None,
            summary=_summary([]),
            can_confirm=False,
            expires_at=None,
            rows=[],
            truncated=False,
            **common,
        )

    results = _validate(session, request, table, resolution.mapping, fields)
    summary = _summary(results)
    records = [] if summary.error_rows else [rec for r in results for rec in r.records]
    job = ImportJob(
        user_id=user.id,
        class_id=request.class_id,
        kind=request.kind,
        subject_id=request.subject.id if request.subject is not None else None,
        semester=request.semester,
        period=request.period,
        status=ImportStatus.PREVIEWED,
        file_name=request.filename[:255],
        mapping=resolution.mapping,
        summary=summary.model_dump(),
        rows=records,
        expires_at=datetime.now(UTC) + JOB_TTL,
    )
    session.add(job)
    if request.save_mapping_as:
        templates.save_template(
            session,
            user.id,
            request.kind,
            request.save_mapping_as[:100],
            {name: header for name, header in resolution.mapping.items() if header},
            header_line,
        )
    session.commit()

    shown, truncated = _rows_for_preview(results)
    return PreviewOut(
        job_id=job.id,
        summary=summary,
        can_confirm=summary.error_rows == 0 and summary.total_rows > 0,
        expires_at=job.expires_at,
        rows=shown,
        truncated=truncated,
        **common,
    )


def _result_of(job: ImportJob, *, already: bool) -> ConfirmOut:
    result = job.summary.get("result", {})
    return ConfirmOut(
        job_id=job.id,
        status=job.status,
        created=result.get("created", 0),
        updated=result.get("updated", 0),
        unchanged=result.get("unchanged", 0),
        already_confirmed=already,
    )


def confirm_job(session: Session, user: User, job_id: uuid.UUID) -> tuple[ConfirmOut, int, bool]:
    """Ghi dữ liệu của một bản xem trước. Trả (kết quả, class_id, dữ liệu có đổi lần này không).

    Chỉ người tạo job được xác nhận, và quyền ghi được kiểm lại. Job được khoá (FOR UPDATE) nên hai
    lần bấm cùng lúc chỉ ghi một lần; xác nhận lại job đã xong trả kết quả cũ, không ghi lần hai.
    """
    job = session.execute(
        select(ImportJob).where(ImportJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    if job is None:
        raise ImportJobNotFound
    if job.user_id != user.id:
        raise AuthorizationError
    if job.kind is ImportKind.ROSTER:
        authorize_admin(user)  # nhập danh sách học sinh chỉ dành cho Admin (D-100)
    else:
        authorize_write(session, user, class_id=job.class_id, subject_id=job.subject_id)

    if job.status is ImportStatus.CONFIRMED:
        return _result_of(job, already=True), job.class_id, False
    if job.expires_at <= datetime.now(UTC):
        raise ImportJobExpired
    if job.summary.get("error_rows", 0) > 0:
        raise ImportJobInvalid

    try:
        created, updated = write_job(session, job)
        unchanged = int(job.summary.get("records_unchanged", 0))
        job.status = ImportStatus.CONFIRMED
        job.confirmed_at = datetime.now(UTC)
        if job.kind is ImportKind.ROSTER:
            job.rows = []  # họ tên, ngày sinh, số điện thoại không nằm lại trong job (D-100)
        job.summary = {
            **job.summary,
            "result": {"created": created, "updated": updated, "unchanged": unchanged},
        }
        record_access(
            session,
            user,
            AuditAction.IMPORT_CONFIRM,
            class_id=job.class_id,
            details={
                "job_id": str(job.id),
                "kind": job.kind.value,
                "subject_id": job.subject_id,
                "semester": job.semester,
                "period": None if job.period is None else job.period.value,
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
            },
            commit=False,
        )
        session.commit()
    except (IntegrityError, roster.RosterConflict) as error:
        session.rollback()
        raise ImportConflict from error
    # Danh sách học sinh chưa có điểm nên không có gì để cảnh báo sớm tính lại.
    written = bool(created or updated) and job.kind is not ImportKind.ROSTER
    return _result_of(job, already=False), job.class_id, written

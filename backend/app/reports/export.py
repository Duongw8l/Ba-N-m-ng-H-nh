"""Dựng và xuất PDF một bản ĐÃ DUYỆT (Giai đoạn 9, D-108; nguyên tắc 6).

Bản nháp không có đường nào ra ngoài: `export_pdf` ném `Conflict` (409) nếu chưa duyệt. Số trong
bảng điểm lấy lại từ Analytics (cùng `facts.py` đã dùng để viết nhận xét); văn bản là `final_text`.
Họ tên học sinh và tên phụ huynh chỉ xuất hiện ở đây, lấy từ DB, không bao giờ đi qua LLM.
"""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.auth.audit import record_access
from app.auth.models import User
from app.classes.models import SchoolClass, SchoolYear
from app.core.config import get_settings
from app.core.enums import AuditAction, ReportScope, ReportStatus, ReportType, UserRole
from app.reports import pdf, service
from app.reports.facts import PERIOD_LABELS
from app.reports.models import Report

VIETNAM_TIME = timezone(timedelta(hours=7))
TITLES = {
    ReportType.SUBJECT_COMMENT: "NHẬN XÉT MÔN HỌC",
    ReportType.SCHOOL_RECORD: "NHẬN XÉT HỌC BẠ",
    ReportType.CONTACT_SLIP: "PHIẾU LIÊN LẠC",
}
SLUGS = {
    ReportType.SUBJECT_COMMENT: "nhan-xet-mon",
    ReportType.SCHOOL_RECORD: "nhan-xet-hoc-ba",
    ReportType.CONTACT_SLIP: "phieu-lien-lac",
    ReportType.REPORT: "bao-cao",
}


def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def _school_year(session: Session) -> str:
    # Hệ thống chỉ có một năm học (D-098).
    return session.scalar(select(SchoolYear.name).order_by(SchoolYear.id.desc()).limit(1)) or ""


def _homeroom_teacher(session: Session, class_id: int) -> str | None:
    return session.scalar(
        select(User.full_name)
        .join(SchoolClass, SchoolClass.homeroom_teacher_id == User.id)
        .where(SchoolClass.id == class_id)
    )


def _signer(session: Session, report: Report) -> tuple[str, str]:
    """(chức danh, họ tên) của người đã duyệt."""
    approver = None if report.approved_by is None else session.get(User, report.approved_by)
    name = "" if approver is None else approver.full_name
    if approver is not None and approver.role is UserRole.PRINCIPAL:
        return "Ban giám hiệu", name
    if report.type is ReportType.SUBJECT_COMMENT:
        return "Giáo viên bộ môn", name
    return "Giáo viên chủ nhiệm", name


def _score_rows(facts: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for subject in facts["subjects"]:
        if "average" in subject:
            value = (
                "Chưa đủ dữ liệu"
                if subject["average"] is None
                else pdf.format_score(subject["average"])
            )
        else:
            value = subject.get("result") or "Chưa có dữ liệu"
        rows.append((subject["name"], value))
    return rows


def _slip_summary(facts: dict[str, Any]) -> list[str]:
    learning = facts["learning_level"] or "chưa đủ dữ liệu"
    conduct = facts["conduct_level"] or "chưa có dữ liệu"
    away = facts["attendance_since_start_of_year"]
    return [
        f"Xếp loại học tập: {learning}. Rèn luyện: {conduct}.",
        (
            f"Số buổi nghỉ từ đầu năm học: {away['absent_total']} "
            f"(có phép {away['absent_excused']}, không phép {away['absent_unexcused']}); "
            f"đi muộn {away['late']} lần."
        ),
    ]


def build_document(session: Session, report: Report) -> pdf.PdfDocument:
    resolved = service.resolved_of(session, report)
    info, student = resolved.info, resolved.student
    period = _capitalized(PERIOD_LABELS[report.semester])
    approved = report.approved_at or datetime.now(VIETNAM_TIME)
    approved_on: date = approved.astimezone(VIETNAM_TIME).date()
    title_role, signer = _signer(session, report)
    common: dict[str, Any] = {
        "school_name": get_settings().school_name,
        "school_year": _school_year(session),
        "body": report.final_text or "",
        "signer_title": title_role,
        "signer_name": signer,
        "approved_on": approved_on,
    }

    if report.scope is ReportScope.GRADE:
        return pdf.PdfDocument(
            title=f"BÁO CÁO KHỐI {report.target_id}",
            subtitle=period,
            info=[("Khối", str(report.target_id))],
            **common,
        )
    assert info is not None
    if report.scope is ReportScope.CLASS:
        return pdf.PdfDocument(
            title=f"BÁO CÁO LỚP {info.name}",
            subtitle=period,
            info=[("Lớp", info.name)],
            **common,
        )

    if student is None:
        raise service.NotFound("Học sinh không còn trong lớp này.")
    info_rows = [
        ("Họ và tên học sinh", student.full_name),
        ("Mã học sinh", student.student_code),
        ("Lớp", info.name),
    ]
    if report.type is ReportType.SUBJECT_COMMENT:
        facts = service.facts_for(session, resolved)
        info_rows.append(("Môn học", str(facts["subject"])))
        return pdf.PdfDocument(
            title=TITLES[report.type],
            subtitle=f"{period} · Lớp {info.name}",
            info=info_rows,
            **common,
        )
    if report.type is ReportType.SCHOOL_RECORD:
        return pdf.PdfDocument(
            title=TITLES[report.type],
            subtitle=f"{period} · Lớp {info.name}",
            info=info_rows,
            **common,
        )

    # Phiếu liên lạc gửi phụ huynh: thêm lời gửi, bảng điểm và tóm tắt chuyên cần.
    facts = service.facts_for(session, resolved)
    guardian_name, _phone = repo.student_guardian(session, student.student_id)
    homeroom = _homeroom_teacher(session, info.id)
    if homeroom:
        info_rows.append(("Giáo viên chủ nhiệm", homeroom))
    return pdf.PdfDocument(
        title=TITLES[report.type],
        subtitle=f"{period} · Lớp {info.name}",
        info=info_rows,
        greeting=(
            f"Kính gửi phụ huynh: {guardian_name}" if guardian_name else "Kính gửi quý phụ huynh"
        ),
        scores=_score_rows(facts),
        summary=_slip_summary(facts),
        **common,
    )


def file_name(report: Report, session: Session) -> str:
    """Tên tệp chỉ gồm ký tự ASCII, để không lỗi tiêu đề Content-Disposition."""
    parts = [SLUGS[report.type]]
    if report.scope is ReportScope.STUDENT:
        resolved = service.resolved_of(session, report)
        if resolved.student is not None:
            parts.append(resolved.student.student_code)
    elif report.scope is ReportScope.CLASS and report.class_id is not None:
        resolved = service.resolved_of(session, report)
        if resolved.info is not None:
            parts.append(resolved.info.name)
    else:
        parts.append(f"khoi-{report.target_id}")
    parts.append("ca-nam" if report.semester == "year" else f"hk{report.semester}")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", "-".join(parts)).strip("-") + ".pdf"


def export_pdf(session: Session, user: User, report_id: int) -> tuple[bytes, str]:
    """PDF của một bản đã duyệt và tên tệp. Ném AuthorizationError (403), Conflict (409: nháp)."""
    report = service.load_authorized(session, user, report_id)
    if report.status is not ReportStatus.APPROVED or not report.final_text:
        raise service.Conflict("Bản này chưa duyệt nên chưa xuất được. Hãy duyệt trước.")
    content = pdf.render(build_document(session, report))
    record_access(
        session,
        user,
        AuditAction.EXPORT_REPORT,
        class_id=report.class_id,
        details={
            "report_id": report.id,
            "type": report.type.value,
            "semester": report.semester,
            "format": "pdf",
        },
    )
    return content, file_name(report, session)

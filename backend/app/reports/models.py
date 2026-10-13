"""Nhận xét và báo cáo. Bản do AI sinh luôn bắt đầu ở trạng thái draft (nguyên tắc 6).

Mỗi bản ứng với một khoá `(type, scope, target_id, semester, subject_id)` và chỉ có một dòng cho mỗi
khoá (hai chỉ mục duy nhất một phần, vì `subject_id` có thể NULL). `target_id` là id học sinh, lớp
hoặc khối (số 10, 11, 12) tuỳ `scope`, nên không có khoá ngoại; `class_id` cho biết lớp của em hoặc
lớp được báo cáo (NULL với báo cáo khối).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import ReportJobStatus, ReportScope, ReportStatus, ReportType


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # Đã duyệt thì phải biết ai duyệt.
        CheckConstraint(
            "status <> 'approved' OR approved_by IS NOT NULL", name="approved_has_approver"
        ),
        CheckConstraint("semester IN ('1', '2', 'year')", name="semester"),
        # AI chưa viết được bản đạt kiểm tra thì chờ giáo viên tự viết, không thể đã duyệt.
        CheckConstraint("NOT needs_manual OR status = 'draft'", name="manual_is_draft"),
        Index("ix_reports_scope_target", "scope", "target_id"),
        # Một bản cho mỗi khoá. Tách hai chỉ mục vì NULL không bằng NULL trong chỉ mục duy nhất.
        Index(
            "uq_reports_key",
            "type",
            "scope",
            "target_id",
            "semester",
            unique=True,
            postgresql_where=text("subject_id IS NULL"),
        ),
        Index(
            "uq_reports_key_subject",
            "type",
            "scope",
            "target_id",
            "semester",
            "subject_id",
            unique=True,
            postgresql_where=text("subject_id IS NOT NULL"),
        ),
    )

    id: Mapped[IntPk]
    scope: Mapped[ReportScope] = mapped_column(enum_type(ReportScope, "scope"))
    target_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[ReportType] = mapped_column(enum_type(ReportType, "type"))
    # Nội dung đang soạn. Rỗng khi `needs_manual` (không lưu văn bản vi phạm ở đâu cả).
    draft_text: Mapped[str] = mapped_column(Text)
    # Chỉ có khi đã duyệt; sửa lại văn bản thì xoá và quay về draft (D-102).
    final_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        enum_type(ReportStatus, "status"), server_default=ReportStatus.DRAFT.value
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    semester: Mapped[str] = mapped_column(String(4))  # "1", "2" hoặc "year"
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Kết quả kiểm tự động của lần sinh gần nhất.
    needs_manual: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    check_notes: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReportJob(Base):
    """Một lần sinh nhận xét cho cả lớp, chạy nền và có tiến độ (D-104)."""

    __tablename__ = "report_jobs"
    __table_args__ = (CheckConstraint("semester IN ('1', '2', 'year')", name="semester"),)

    id: Mapped[IntPk]
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    type: Mapped[ReportType] = mapped_column(enum_type(ReportType, "type"))
    semester: Mapped[str] = mapped_column(String(4))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ReportJobStatus] = mapped_column(
        enum_type(ReportJobStatus, "status"), server_default=ReportJobStatus.RUNNING.value
    )
    total: Mapped[int] = mapped_column(Integer, server_default=text("0"))  # số em cần sinh
    done: Mapped[int] = mapped_column(Integer, server_default=text("0"))  # số em đã xử lý
    needs_manual: Mapped[int] = mapped_column(Integer, server_default=text("0"))  # trong số đó
    error_code: Mapped[str | None] = mapped_column(String(40))
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

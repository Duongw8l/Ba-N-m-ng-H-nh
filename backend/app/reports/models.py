"""Nhận xét và báo cáo. Bản do AI sinh luôn bắt đầu ở trạng thái draft (nguyên tắc 6)."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import ReportScope, ReportStatus, ReportType


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # Đã duyệt thì phải biết ai duyệt.
        CheckConstraint(
            "status <> 'approved' OR approved_by IS NOT NULL", name="approved_has_approver"
        ),
        Index("ix_reports_scope_target", "scope", "target_id"),
    )

    id: Mapped[IntPk]
    scope: Mapped[ReportScope] = mapped_column(enum_type(ReportScope, "scope"))
    # id của học sinh, lớp hoặc khối tuỳ `scope`, nên không có khoá ngoại.
    target_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[ReportType] = mapped_column(enum_type(ReportType, "type"))
    draft_text: Mapped[str] = mapped_column(Text)
    final_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        enum_type(ReportStatus, "status"), server_default=ReportStatus.DRAFT.value
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

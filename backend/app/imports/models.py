"""Bản xem trước nhập tệp (import_jobs) và mẫu ánh xạ cột (import_mappings) của Giai đoạn 4.

Hai bảng nằm ngoài 15 bảng của DESIGN mục 5 (D-059, D-062). Job chỉ lưu giá trị đã chuẩn hoá của
các dòng hợp lệ (mã học sinh, điểm...): không lưu tệp gốc và không lưu họ tên.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import ConductPeriod, ImportKind, ImportStatus


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint("semester IS NULL OR semester IN (1, 2)", name="semester"),
        Index("ix_import_jobs_user_id", "user_id"),
        Index("ix_import_jobs_expires_at", "expires_at"),
    )

    # UUID ngẫu nhiên: job_id nằm trong URL nên không được đoán ra.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    kind: Mapped[ImportKind] = mapped_column(enum_type(ImportKind, "kind"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    semester: Mapped[int | None] = mapped_column(SmallInteger)
    period: Mapped[ConductPeriod | None] = mapped_column(enum_type(ConductPeriod, "period"))
    status: Mapped[ImportStatus] = mapped_column(
        enum_type(ImportStatus, "status"), server_default=ImportStatus.PREVIEWED.value
    )
    file_name: Mapped[str] = mapped_column(String(255))
    mapping: Mapped[Any] = mapped_column(JSONB)  # trường -> tên cột đã dùng
    summary: Mapped[Any] = mapped_column(JSONB)  # các số đếm của bản xem trước (và kết quả ghi)
    rows: Mapped[Any] = mapped_column(JSONB)  # các bản ghi cần ghi, đã chuẩn hoá
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportMapping(Base):
    """Mẫu ánh xạ cột của một người dùng, để dùng lại cho các tệp cùng định dạng."""

    __tablename__ = "import_mappings"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "name", name="uq_import_mappings_user_kind_name"),
    )

    id: Mapped[IntPk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[ImportKind] = mapped_column(enum_type(ImportKind, "kind"))
    name: Mapped[str] = mapped_column(String(100))
    mapping: Mapped[Any] = mapped_column(JSONB)
    header_row: Mapped[int | None] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

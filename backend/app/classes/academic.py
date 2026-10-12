"""Sổ điểm, điểm danh, rèn luyện và đăng ký thi: dữ liệu học vụ gắn với một học sinh trong một lớp.

Bảng con của class_students dùng ON DELETE CASCADE: xoá một lượt xếp lớp thì xoá luôn dữ liệu của
nó. Điểm lưu bằng NUMERIC (Decimal), không dùng float: có học sinh biên đúng 3,5 và 5,0.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import (
    AssessmentKind,
    AttendanceStatus,
    CommentResult,
    ConductLevel,
    ConductPeriod,
)


class Assessment(Base):
    """Một đầu điểm (hoặc một nhận xét Đạt / Chưa đạt) của học sinh trong một học kỳ.

    Môn tính điểm: kind tx (seq 1..n), gk (seq 1), ck (seq 1), có `score`.
    Môn nhận xét: mỗi học kỳ một dòng kind ck, seq 1, `score` NULL, có `comment_result` (D-035).
    """

    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("semester IN (1, 2)", name="semester"),
        CheckConstraint("seq >= 1", name="seq_positive"),
        CheckConstraint("kind = 'tx' OR seq = 1", name="seq_one_unless_tx"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 10)", name="score_range"),
        # Đúng một trong hai: điểm số hoặc nhận xét.
        CheckConstraint("(score IS NULL) <> (comment_result IS NULL)", name="score_xor_comment"),
        UniqueConstraint(
            "class_student_id",
            "subject_id",
            "semester",
            "kind",
            "seq",
            name="uq_assessments_cs_subject_sem_kind_seq",
        ),
        Index("ix_assessments_subject_semester", "subject_id", "semester"),
    )

    id: Mapped[IntPk]
    class_student_id: Mapped[int] = mapped_column(
        ForeignKey("class_students.id", ondelete="CASCADE")
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    semester: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[AssessmentKind] = mapped_column(enum_type(AssessmentKind, "kind"))
    seq: Mapped[int] = mapped_column(SmallInteger)
    score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    comment_result: Mapped[CommentResult | None] = mapped_column(
        enum_type(CommentResult, "comment_result")
    )


class Attendance(Base):
    """Một dòng cho mỗi ngày học của mỗi học sinh. Dòng nghỉ (có phép / không phép) tính là
    1 buổi nghỉ (D-028)."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("class_student_id", "date", name="uq_attendance_cs_date"),
        Index("ix_attendance_date", "date"),
    )

    id: Mapped[IntPk]
    class_student_id: Mapped[int] = mapped_column(
        ForeignKey("class_students.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[AttendanceStatus] = mapped_column(enum_type(AttendanceStatus, "status"))


class ConductResult(Base):
    __tablename__ = "conduct_results"
    __table_args__ = (
        UniqueConstraint("class_student_id", "period", name="uq_conduct_results_cs_period"),
    )

    id: Mapped[IntPk]
    class_student_id: Mapped[int] = mapped_column(
        ForeignKey("class_students.id", ondelete="CASCADE")
    )
    period: Mapped[ConductPeriod] = mapped_column(enum_type(ConductPeriod, "period"))
    level: Mapped[ConductLevel] = mapped_column(enum_type(ConductLevel, "level"))
    comment: Mapped[str | None] = mapped_column(Text)


class ExamRegistration(Base):
    """Môn đăng ký thi tốt nghiệp (khối 12)."""

    __tablename__ = "exam_registrations"
    __table_args__ = (
        UniqueConstraint("class_student_id", "subject_id", name="uq_exam_registrations_cs_subject"),
    )

    id: Mapped[IntPk]
    class_student_id: Mapped[int] = mapped_column(
        ForeignKey("class_students.id", ondelete="CASCADE")
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))

"""Cơ cấu trường và học vụ: năm học, lớp, học sinh, môn học, phân công giảng dạy.

Môn học của một lớp chính là các dòng teaching_assignments của lớp đó (DESIGN không có bảng riêng
cho môn lựa chọn).
"""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, IntPk, enum_type
from app.core.enums import AssessmentType


class SchoolYear(Base):
    __tablename__ = "school_years"
    __table_args__ = (CheckConstraint("start_date < end_date", name="dates_order"),)

    id: Mapped[IntPk]
    name: Mapped[str] = mapped_column(String(20), unique=True)  # ví dụ 2026-2027
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class SchoolClass(Base):
    """Bảng `classes` (đặt tên lớp Python khác vì `class` là từ khoá)."""

    __tablename__ = "classes"
    __table_args__ = (
        CheckConstraint("grade_level IN (10, 11, 12)", name="grade_level"),
        UniqueConstraint("school_year_id", "name", name="uq_classes_year_name"),
        # Một giáo viên chỉ chủ nhiệm một lớp mỗi năm học; NULL (chưa có GVCN) thì không giới hạn.
        UniqueConstraint(
            "school_year_id", "homeroom_teacher_id", name="uq_classes_year_homeroom_teacher"
        ),
        Index("ix_classes_year_grade", "school_year_id", "grade_level"),
    )

    id: Mapped[IntPk]
    school_year_id: Mapped[int] = mapped_column(ForeignKey("school_years.id"))
    grade_level: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(20))  # ví dụ 10A1
    homeroom_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Student(Base):
    __tablename__ = "students"

    id: Mapped[IntPk]
    student_code: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    # Ba cột dưới là dữ liệu nhạy cảm: không bao giờ gửi cho LLM (nguyên tắc 5).
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    guardian_name: Mapped[str | None] = mapped_column(String(100))
    guardian_phone: Mapped[str | None] = mapped_column(String(20))


class ClassStudent(Base):
    __tablename__ = "class_students"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_students_pair"),)

    id: Mapped[IntPk]
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (CheckConstraint("periods_per_year > 0", name="periods_positive"),)

    id: Mapped[IntPk]
    name: Mapped[str] = mapped_column(String(100), unique=True)
    assessment_type: Mapped[AssessmentType] = mapped_column(
        enum_type(AssessmentType, "assessment_type")
    )
    periods_per_year: Mapped[int] = mapped_column(SmallInteger)
    is_elective: Mapped[bool] = mapped_column(Boolean, server_default="false")


class TeachingAssignment(Base):
    __tablename__ = "teaching_assignments"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_teaching_assignments_class_subject"),
    )

    id: Mapped[IntPk]
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

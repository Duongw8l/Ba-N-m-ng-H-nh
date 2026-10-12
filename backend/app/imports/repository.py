"""Truy vấn của module nhập tệp: học sinh của lớp và dữ liệu hiện có để so sánh. Chỉ đọc."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classes.academic import Assessment, Attendance, ConductResult
from app.classes.models import ClassStudent, Student
from app.core.enums import (
    AssessmentKind,
    AttendanceStatus,
    CommentResult,
    ConductLevel,
    ConductPeriod,
)
from app.imports.validation import ScoreKey, StudentRef


def students_by_code(session: Session, class_id: int) -> dict[str, StudentRef]:
    """Học sinh của lớp, khoá là mã viết hoa (so khớp không phân biệt hoa thường)."""
    rows = session.execute(
        select(Student.student_code, ClassStudent.id, Student.full_name)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id == class_id)
    ).all()
    return {
        code.upper(): StudentRef(class_student_id, name) for code, class_student_id, name in rows
    }


def existing_scores(
    session: Session, class_id: int, subject_id: int, semester: int
) -> dict[ScoreKey, Decimal | None]:
    rows = session.execute(
        select(Assessment.class_student_id, Assessment.kind, Assessment.seq, Assessment.score)
        .join(ClassStudent, ClassStudent.id == Assessment.class_student_id)
        .where(
            ClassStudent.class_id == class_id,
            Assessment.subject_id == subject_id,
            Assessment.semester == semester,
        )
    ).all()
    return {(cs_id, kind.value, seq): score for cs_id, kind, seq, score in rows}


def existing_comments(
    session: Session, class_id: int, subject_id: int, semester: int
) -> dict[int, CommentResult | None]:
    rows = session.execute(
        select(Assessment.class_student_id, Assessment.comment_result)
        .join(ClassStudent, ClassStudent.id == Assessment.class_student_id)
        .where(
            ClassStudent.class_id == class_id,
            Assessment.subject_id == subject_id,
            Assessment.semester == semester,
            Assessment.kind == AssessmentKind.CK,
        )
    ).all()
    return {cs_id: result for cs_id, result in rows}


def existing_attendance(
    session: Session, class_id: int, first: date, last: date
) -> dict[tuple[int, date], AttendanceStatus]:
    rows = session.execute(
        select(Attendance.class_student_id, Attendance.date, Attendance.status)
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id, Attendance.date.between(first, last))
    ).all()
    return {(cs_id, day): status for cs_id, day, status in rows}


def existing_conduct(
    session: Session, class_id: int, period: ConductPeriod
) -> dict[int, tuple[ConductLevel, str | None]]:
    rows = session.execute(
        select(ConductResult.class_student_id, ConductResult.level, ConductResult.comment)
        .join(ClassStudent, ClassStudent.id == ConductResult.class_student_id)
        .where(ClassStudent.class_id == class_id, ConductResult.period == period)
    ).all()
    return {cs_id: (level, comment) for cs_id, level, comment in rows}

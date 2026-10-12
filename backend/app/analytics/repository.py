"""Truy vấn dữ liệu cho Analytics. Chỉ đọc; quyền đã được authorize() kiểm trước khi gọi."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.attendance import AttendanceSummary, make_summary
from app.analytics.views import v_subject_average
from app.classes.academic import Assessment, Attendance, ConductResult
from app.classes.models import ClassStudent, SchoolClass, Student, Subject, TeachingAssignment
from app.core.enums import (
    AssessmentKind,
    AssessmentType,
    AttendanceStatus,
    CommentResult,
    ConductLevel,
    ConductPeriod,
)


@dataclass(frozen=True)
class ClassInfo:
    id: int
    name: str
    grade_level: int


@dataclass(frozen=True)
class SubjectInfo:
    id: int
    name: str
    assessment_type: AssessmentType
    periods_per_year: int


@dataclass(frozen=True)
class StudentInfo:
    class_student_id: int
    student_id: int
    student_code: str
    full_name: str


@dataclass(frozen=True)
class SemesterRow:
    """Một dòng của view: tổng hợp đầu điểm của một học sinh, một môn, một học kỳ."""

    class_student_id: int
    subject_id: int
    semester: int
    tx_count: int
    tx_sum: Decimal
    midterm: Decimal | None
    final: Decimal | None
    comment_result: CommentResult | None


@dataclass(frozen=True)
class RawScore:
    class_student_id: int
    semester: int
    kind: AssessmentKind
    seq: int
    score: Decimal | None
    comment_result: CommentResult | None


def get_class(session: Session, class_id: int) -> ClassInfo | None:
    row = session.execute(
        select(SchoolClass.id, SchoolClass.name, SchoolClass.grade_level).where(
            SchoolClass.id == class_id
        )
    ).one_or_none()
    return None if row is None else ClassInfo(row[0], row[1], row[2])


def classes_in_grade(session: Session, grade_level: int) -> list[ClassInfo]:
    rows = session.execute(
        select(SchoolClass.id, SchoolClass.name, SchoolClass.grade_level)
        .where(SchoolClass.grade_level == grade_level)
        .order_by(SchoolClass.name)
    ).all()
    return [ClassInfo(r[0], r[1], r[2]) for r in rows]


def class_subjects(session: Session, class_id: int) -> list[SubjectInfo]:
    """Các môn của lớp = các dòng teaching_assignments của lớp (DESIGN không có bảng riêng)."""
    rows = session.execute(
        select(Subject.id, Subject.name, Subject.assessment_type, Subject.periods_per_year)
        .join(TeachingAssignment, TeachingAssignment.subject_id == Subject.id)
        .where(TeachingAssignment.class_id == class_id)
        .order_by(Subject.id)
    ).all()
    return [SubjectInfo(r[0], r[1], r[2], r[3]) for r in rows]


def class_students(session: Session, class_id: int) -> list[StudentInfo]:
    rows = session.execute(
        select(ClassStudent.id, Student.id, Student.student_code, Student.full_name)
        .join(Student, Student.id == ClassStudent.student_id)
        .where(ClassStudent.class_id == class_id)
        .order_by(Student.student_code)
    ).all()
    return [StudentInfo(r[0], r[1], r[2], r[3]) for r in rows]


def semester_rows(session: Session, class_id: int) -> list[SemesterRow]:
    """Mọi dòng tổng hợp đầu điểm của lớp (cả hai học kỳ) từ view v_subject_average."""
    v = v_subject_average.c
    rows = session.execute(
        select(
            v.class_student_id,
            v.subject_id,
            v.semester,
            v.tx_count,
            v.tx_sum,
            v.gk_score,
            v.ck_score,
            v.comment_result,
        ).where(v.class_id == class_id)
    ).all()
    return [
        SemesterRow(
            class_student_id=r[0],
            subject_id=r[1],
            semester=r[2],
            tx_count=r[3],
            tx_sum=r[4],
            midterm=r[5],
            final=r[6],
            comment_result=None if r[7] is None else CommentResult(r[7]),
        )
        for r in rows
    ]


def conduct_by_student(
    session: Session, class_id: int
) -> dict[int, dict[ConductPeriod, ConductLevel]]:
    rows = session.execute(
        select(ConductResult.class_student_id, ConductResult.period, ConductResult.level)
        .join(ClassStudent, ClassStudent.id == ConductResult.class_student_id)
        .where(ClassStudent.class_id == class_id)
    ).all()
    result: dict[int, dict[ConductPeriod, ConductLevel]] = {}
    for class_student_id, period, level in rows:
        result.setdefault(class_student_id, {})[period] = level
    return result


def absence_by_student(session: Session, class_id: int) -> dict[int, AttendanceSummary]:
    """Số buổi nghỉ cả năm học của từng học sinh (đếm bằng SQL, không kéo 175 dòng mỗi em)."""
    rows = session.execute(
        select(
            Attendance.class_student_id,
            func.count().filter(Attendance.status == AttendanceStatus.ABSENT_EXCUSED),
            func.count().filter(Attendance.status == AttendanceStatus.ABSENT_UNEXCUSED),
            func.count().filter(Attendance.status == AttendanceStatus.LATE),
        )
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id)
        .group_by(Attendance.class_student_id)
    ).all()
    return {r[0]: make_summary(r[1], r[2], r[3]) for r in rows}


def raw_subject_scores(session: Session, class_id: int, subject_id: int) -> list[RawScore]:
    """Từng đầu điểm của một môn trong lớp, cả hai học kỳ."""
    rows = session.execute(
        select(
            Assessment.class_student_id,
            Assessment.semester,
            Assessment.kind,
            Assessment.seq,
            Assessment.score,
            Assessment.comment_result,
        )
        .join(ClassStudent, ClassStudent.id == Assessment.class_student_id)
        .where(ClassStudent.class_id == class_id, Assessment.subject_id == subject_id)
        .order_by(Assessment.class_student_id, Assessment.semester, Assessment.kind, Assessment.seq)
    ).all()
    return [RawScore(*r) for r in rows]

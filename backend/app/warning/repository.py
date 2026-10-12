"""Truy vấn và ghi bảng risk_alerts. Quyền đã được authorize() kiểm trước khi gọi."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, Subquery, exists, func, select
from sqlalchemy.orm import Session

from app.classes.academic import Assessment, Attendance, ExamRegistration
from app.classes.models import ClassStudent, SchoolClass, Student
from app.core.enums import RiskLevel, TeacherStatus
from app.warning.models import RiskAlert


@dataclass(frozen=True)
class AlertRow:
    """Một cảnh báo hiện hành kèm học sinh và lớp."""

    alert: RiskAlert
    student_id: int
    student_code: str
    full_name: str
    class_id: int
    class_name: str


def _latest_ids() -> Subquery:
    """Truy vấn con: id của dòng mới nhất của từng học sinh (cảnh báo hiện hành)."""
    return (
        select(func.max(RiskAlert.id).label("id")).group_by(RiskAlert.class_student_id).subquery()
    )


def latest_by_student(session: Session, class_student_ids: Sequence[int]) -> dict[int, RiskAlert]:
    if not class_student_ids:
        return {}
    latest = _latest_ids()
    rows = session.scalars(
        select(RiskAlert)
        .join(latest, latest.c.id == RiskAlert.id)
        .where(RiskAlert.class_student_id.in_(class_student_ids))
    )
    return {alert.class_student_id: alert for alert in rows}


def insert_alert(
    session: Session,
    *,
    class_student_id: int,
    level: RiskLevel,
    risk_score: Decimal | None,
    reasons: dict[str, Any],
    model_version: str | None,
) -> RiskAlert:
    alert = RiskAlert(
        class_student_id=class_student_id,
        level=level,
        risk_score=risk_score,
        reasons=reasons,
        model_version=model_version,
        teacher_status=TeacherStatus.NEW,
    )
    session.add(alert)
    session.flush()
    session.refresh(alert)  # created_at do DB đặt
    return alert


def _current_query(class_id: int | None, levels: Sequence[RiskLevel] | None) -> Select[Any]:
    latest = _latest_ids()
    query = (
        select(
            RiskAlert,
            Student.id,
            Student.student_code,
            Student.full_name,
            SchoolClass.id,
            SchoolClass.name,
        )
        .join(latest, latest.c.id == RiskAlert.id)
        .join(ClassStudent, ClassStudent.id == RiskAlert.class_student_id)
        .join(Student, Student.id == ClassStudent.student_id)
        .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
    )
    if class_id is not None:
        query = query.where(ClassStudent.class_id == class_id)
    if levels is not None:
        query = query.where(RiskAlert.level.in_(levels))
    return query


def current_alerts(
    session: Session, *, class_id: int | None = None, levels: Sequence[RiskLevel] | None = None
) -> list[AlertRow]:
    """Cảnh báo hiện hành (dòng mới nhất của từng học sinh) của một lớp hoặc toàn trường."""
    rows = session.execute(
        _current_query(class_id, levels).order_by(SchoolClass.name, Student.student_code)
    ).all()
    return [AlertRow(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]


def current_counts(session: Session, *, class_id: int | None = None) -> dict[str, int]:
    latest = _latest_ids()
    query = (
        select(RiskAlert.level, func.count())
        .join(latest, latest.c.id == RiskAlert.id)
        .join(ClassStudent, ClassStudent.id == RiskAlert.class_student_id)
        .group_by(RiskAlert.level)
    )
    if class_id is not None:
        query = query.where(ClassStudent.class_id == class_id)
    found = {level.value: count for level, count in session.execute(query).all()}
    return {level.value: found.get(level.value, 0) for level in RiskLevel}


def alert_scope(session: Session, alert_id: int) -> tuple[RiskAlert, int, bool] | None:
    """(cảnh báo, id lớp, có phải cảnh báo hiện hành không); None nếu không có."""
    alert = session.get(RiskAlert, alert_id)
    if alert is None:
        return None
    class_id = session.scalar(
        select(ClassStudent.class_id).where(ClassStudent.id == alert.class_student_id)
    )
    newest = session.scalar(
        select(func.max(RiskAlert.id)).where(RiskAlert.class_student_id == alert.class_student_id)
    )
    assert class_id is not None
    return alert, class_id, newest == alert.id


def alert_row(session: Session, alert_id: int) -> AlertRow:
    """Một cảnh báo hiện hành kèm học sinh và lớp (đã biết là cảnh báo hiện hành)."""
    r = session.execute(_current_query(None, None).where(RiskAlert.id == alert_id)).one()
    return AlertRow(r[0], r[1], r[2], r[3], r[4], r[5])


def current_for_student(session: Session, class_student_id: int) -> RiskAlert | None:
    return latest_by_student(session, [class_student_id]).get(class_student_id)


# --- Dữ liệu đầu vào của luật ---------------------------------------------------------------------


def last_attendance_date(session: Session, class_id: int) -> date | None:
    """Ngày điểm danh mới nhất của lớp: mốc `as_of` của cảnh báo."""
    return session.scalar(
        select(func.max(Attendance.date))
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id)
    )


def has_semester_two_scores(session: Session, class_id: int) -> bool:
    """Lớp đã có điểm học kỳ II chưa (để chọn kỳ cho luật học tập)."""
    return bool(
        session.scalar(
            select(
                exists().where(
                    Assessment.semester == 2,
                    Assessment.class_student_id.in_(
                        select(ClassStudent.id).where(ClassStudent.class_id == class_id)
                    ),
                )
            )
        )
    )


def exam_subjects(session: Session, class_id: int) -> dict[int, list[int]]:
    """Khối 12: id các môn đăng ký thi tốt nghiệp của từng học sinh (theo class_student_id)."""
    rows = session.execute(
        select(ExamRegistration.class_student_id, ExamRegistration.subject_id)
        .join(ClassStudent, ClassStudent.id == ExamRegistration.class_student_id)
        .where(ClassStudent.class_id == class_id)
        .order_by(ExamRegistration.class_student_id, ExamRegistration.subject_id)
    ).all()
    result: dict[int, list[int]] = {}
    for class_student_id, subject_id in rows:
        result.setdefault(class_student_id, []).append(subject_id)
    return result

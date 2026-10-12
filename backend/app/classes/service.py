"""Truy vấn danh sách lớp, học sinh và phân công. Quyền đã được authorize() kiểm trước khi gọi."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.classes.models import ClassStudent, SchoolClass, Student, Subject, TeachingAssignment
from app.classes.schemas import (
    AssignmentsResponse,
    ClassRef,
    StudentOut,
    StudentWithGuardianOut,
    TeachingItem,
)
from app.core.enums import UserRole


def get_assignments(session: Session, user: User) -> AssignmentsResponse:
    """Lớp chủ nhiệm và lớp-môn được phân công của chính `user`, kèm các khối của BGH."""
    homeroom = session.execute(
        select(SchoolClass.id, SchoolClass.name, SchoolClass.grade_level)
        .where(SchoolClass.homeroom_teacher_id == user.id)
        .order_by(SchoolClass.grade_level, SchoolClass.name)
    ).all()
    teaching = session.execute(
        select(
            SchoolClass.id,
            SchoolClass.name,
            SchoolClass.grade_level,
            Subject.id,
            Subject.name,
        )
        .join(TeachingAssignment, TeachingAssignment.class_id == SchoolClass.id)
        .join(Subject, Subject.id == TeachingAssignment.subject_id)
        .where(TeachingAssignment.teacher_id == user.id)
        .order_by(SchoolClass.grade_level, SchoolClass.name, Subject.id)
    ).all()
    grades: list[int] = []
    if user.role is UserRole.PRINCIPAL:
        grades = list(
            session.scalars(
                select(SchoolClass.grade_level).distinct().order_by(SchoolClass.grade_level)
            )
        )
    return AssignmentsResponse(
        user=user,  # type: ignore[arg-type]  # UserOut đọc từ thuộc tính của User (from_attributes)
        homeroom_classes=[ClassRef(id=r[0], name=r[1], grade_level=r[2]) for r in homeroom],
        teaching=[
            TeachingItem(
                class_id=r[0], class_name=r[1], grade_level=r[2], subject_id=r[3], subject_name=r[4]
            )
            for r in teaching
        ],
        grades=grades,
    )


def class_exists(session: Session, class_id: int) -> bool:
    return session.get(SchoolClass, class_id) is not None


def list_students(
    session: Session, class_id: int, *, with_guardian: bool
) -> list[StudentOut] | list[StudentWithGuardianOut]:
    """Học sinh của lớp, sắp theo mã. Chỉ lấy cột guardian_* khi `with_guardian` (đã được phép)."""
    columns = [Student.id, Student.student_code, Student.full_name]
    if with_guardian:
        columns += [Student.guardian_name, Student.guardian_phone]
    rows = session.execute(
        select(*columns)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id == class_id)
        .order_by(Student.student_code)
    ).all()
    if with_guardian:
        return [
            StudentWithGuardianOut(
                id=r[0], student_code=r[1], full_name=r[2], guardian_name=r[3], guardian_phone=r[4]
            )
            for r in rows
        ]
    return [StudentOut(id=r[0], student_code=r[1], full_name=r[2]) for r in rows]

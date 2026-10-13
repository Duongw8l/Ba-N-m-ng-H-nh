"""Phạm vi của một phiên hỏi đáp: lớp và môn người dùng được phép, và những học sinh hệ thống biết
tên để ẩn danh (D-087). Mọi thứ lấy từ phiên đăng nhập và bảng phân công, không từ LLM."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.schemas import Period
from app.auth.models import User
from app.classes.models import ClassStudent, SchoolClass, Student, Subject
from app.classes.service import get_assignments
from app.core.enums import UserRole
from app.core.labels import label_vi
from app.core.pseudonymize import RosterStudent

PERIOD_VI = {"1": "học kỳ I", "2": "học kỳ II", "year": "cả năm"}


@dataclass(frozen=True)
class ClassItem:
    id: int
    name: str
    grade_level: int


@dataclass(frozen=True)
class TeachingItem:
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str


@dataclass(frozen=True)
class Scope:
    role: UserRole
    homeroom: tuple[ClassItem, ...]
    teaching: tuple[TeachingItem, ...]
    classes: tuple[ClassItem, ...]  # mọi lớp người dùng được hỏi (GVCN, GVBM, hoặc toàn trường)
    subjects: tuple[tuple[int, str], ...]  # (id, tên) mọi môn của trường

    @property
    def class_ids(self) -> list[int]:
        return [c.id for c in self.classes]


def load_scope(session: Session, user: User) -> Scope:
    assignments = get_assignments(session, user)
    homeroom = tuple(ClassItem(c.id, c.name, c.grade_level) for c in assignments.homeroom_classes)
    teaching = tuple(
        TeachingItem(t.class_id, t.class_name, t.subject_id, t.subject_name)
        for t in assignments.teaching
    )
    if user.role is UserRole.PRINCIPAL:
        classes = tuple(
            ClassItem(r[0], r[1], r[2])
            for r in session.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.grade_level).order_by(
                    SchoolClass.grade_level, SchoolClass.name
                )
            )
        )
    else:
        seen: dict[int, ClassItem] = {c.id: c for c in homeroom}
        for t in assignments.teaching:
            seen.setdefault(t.class_id, ClassItem(t.class_id, t.class_name, t.grade_level))
        classes = tuple(sorted(seen.values(), key=lambda c: (c.grade_level, c.name)))
    subjects = tuple(
        (r[0], r[1]) for r in session.execute(select(Subject.id, Subject.name).order_by(Subject.id))
    )
    return Scope(user.role, homeroom, teaching, classes, subjects)


def load_roster(session: Session, class_ids: list[int]) -> list[RosterStudent]:
    """Học sinh của các lớp: để bộ ẩn danh nhận ra họ tên trong câu hỏi."""
    if not class_ids:
        return []
    rows = session.execute(
        select(Student.id, ClassStudent.class_id, Student.full_name, Student.student_code)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id.in_(class_ids))
        .order_by(ClassStudent.class_id, Student.student_code)
    ).all()
    return [RosterStudent(r[0], r[1], r[2], r[3]) for r in rows]


def scope_prompt(
    scope: Scope,
    *,
    open_class: ClassItem | None,
    open_subject: tuple[int, str] | None,
    semester: Period,
    implicit_class: bool = False,
) -> str:
    """Khối "Bối cảnh" nối vào system prompt. Không có tên giáo viên hay học sinh nào."""
    lines = ["# Bối cảnh của phiên này", ""]
    if scope.role is UserRole.PRINCIPAL:
        lines.append(f"- Người hỏi: {label_vi(UserRole.PRINCIPAL)}, xem được toàn trường.")
    else:
        roles = []
        if scope.homeroom:
            roles.append("giáo viên chủ nhiệm")
        if scope.teaching:
            roles.append("giáo viên bộ môn")
        lines.append(f"- Người hỏi: {' và '.join(roles) or 'giáo viên'}.")
    lines.append("- Lớp được hỏi (class_id):")
    lines += [f"  - {c.name} (khối {c.grade_level}): class_id {c.id}" for c in scope.classes]
    if scope.homeroom:
        names = ", ".join(c.name for c in scope.homeroom)
        lines.append(f"- Lớp chủ nhiệm: {names}.")
    if scope.teaching:
        lines.append("- Môn đang dạy (lớp - môn):")
        lines += [
            f"  - {t.class_name} - {t.subject_name} (subject_id {t.subject_id})"
            for t in scope.teaching
        ]
    lines.append(
        "- Mọi môn của trường (subject_id): " + ", ".join(f"{n} {i}" for i, n in scope.subjects)
    )
    where = []
    if open_class is not None:
        where.append(f"lớp {open_class.name} (class_id {open_class.id})")
    if open_subject is not None:
        where.append(f"môn {open_subject[1]} (subject_id {open_subject[0]})")
    label = "Lớp mặc định (người hỏi chỉ có một lớp)" if implicit_class else "Màn hình đang mở"
    lines.append(f"- {label}: {', '.join(where) if where else 'không chọn lớp nào'}.")
    lines.append(f"- Kỳ đang xem: {PERIOD_VI[semester]} (semester = {semester}).")
    lines.append(
        "- Hàm sẽ dùng lớp, môn và kỳ đang mở nếu bạn không nêu; hãy nêu class_id/subject_id khi "
        "người hỏi nhắc tới lớp hay môn khác. Hàm từ chối nếu người hỏi không có quyền."
    )
    return "\n".join(lines)

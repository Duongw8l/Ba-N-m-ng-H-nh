"""Quản trị năm học, lớp, GVCN, phân công giảng dạy, gỡ học sinh khỏi lớp (Admin, D-098, D-099).

Chỉ một năm học (D-098). Mọi hàm ném `AdminNotFound` (404), `AdminConflict` (409) hoặc
`AdminInvalid` (422) kèm thông điệp tiếng Việt để router đổi thẳng thành HTTP. Không hàm nào trả
tên hay mã học sinh.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.audit import record_access
from app.auth.models import User
from app.classes.academic import Assessment, Attendance, ConductResult, ExamRegistration
from app.classes.admin_schemas import (
    AdminClassOut,
    AssignmentRow,
    ClassAssignmentsOut,
    ClassCreateIn,
    ClassUpdateIn,
    SchoolOut,
    SchoolYearIn,
    SchoolYearOut,
    TeacherOut,
    TeacherRef,
)
from app.classes.models import (
    ClassStudent,
    SchoolClass,
    SchoolYear,
    Student,
    Subject,
    TeachingAssignment,
)
from app.core.enums import AuditAction, UserRole
from app.imports.models import ImportJob
from app.warning.models import RiskAlert


class AdminError(Exception):
    """Lỗi nghiệp vụ có sẵn thông điệp tiếng Việt cho người dùng."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AdminNotFound(AdminError):
    """404."""


class AdminConflict(AdminError):
    """409: trạng thái hiện tại không cho phép."""


class AdminInvalid(AdminError):
    """422: giá trị gửi lên không hợp lệ."""


# --- Năm học và danh sách lớp --------------------------------------------------


def _the_school_year(session: Session) -> SchoolYear | None:
    return session.scalars(select(SchoolYear).order_by(SchoolYear.id).limit(1)).first()


def _class_rows(session: Session, class_id: int | None = None) -> list[AdminClassOut]:
    students = (
        select(func.count())
        .select_from(ClassStudent)
        .where(ClassStudent.class_id == SchoolClass.id)
        .scalar_subquery()
    )
    subjects = (
        select(func.count())
        .select_from(TeachingAssignment)
        .where(TeachingAssignment.class_id == SchoolClass.id)
        .scalar_subquery()
    )
    statement = (
        select(SchoolClass, User.full_name, students, subjects)
        .outerjoin(User, User.id == SchoolClass.homeroom_teacher_id)
        .order_by(SchoolClass.grade_level, SchoolClass.name)
    )
    if class_id is not None:
        statement = statement.where(SchoolClass.id == class_id)
    return [
        AdminClassOut(
            id=row[0].id,
            name=row[0].name,
            grade_level=row[0].grade_level,
            homeroom_teacher=(
                None
                if row[0].homeroom_teacher_id is None
                else TeacherRef(id=row[0].homeroom_teacher_id, full_name=row[1])
            ),
            student_count=row[2],
            assigned_subject_count=row[3],
        )
        for row in session.execute(statement)
    ]


def get_school(session: Session) -> SchoolOut:
    year = _the_school_year(session)
    return SchoolOut(
        school_year=None
        if year is None
        else SchoolYearOut(
            id=year.id, name=year.name, start_date=year.start_date, end_date=year.end_date
        ),
        classes=_class_rows(session),
        subject_count=session.scalar(select(func.count()).select_from(Subject)) or 0,
    )


def list_teachers(session: Session) -> list[TeacherOut]:
    """Giáo viên đang hoạt động (cho ô chọn GVCN và người dạy). Tài khoản bị khoá không có mặt."""
    homeroom = (
        select(SchoolClass.name)
        .where(SchoolClass.homeroom_teacher_id == User.id)
        .order_by(SchoolClass.name)
        .limit(1)
        .scalar_subquery()
    )
    rows = session.execute(
        select(User.id, User.full_name, User.email, homeroom)
        .where(User.role == UserRole.TEACHER, User.is_active.is_(True))
        .order_by(User.full_name, User.id)
    )
    return [TeacherOut(id=r[0], full_name=r[1], email=r[2], homeroom_class=r[3]) for r in rows]


def save_school_year(session: Session, admin: User, data: SchoolYearIn) -> SchoolYearOut:
    """Tạo năm học đầu tiên, hoặc sửa năm học duy nhất (D-098)."""
    year = _the_school_year(session)
    if year is None:
        year = SchoolYear(name=data.name, start_date=data.start_date, end_date=data.end_date)
        session.add(year)
        created = True
    else:
        earliest, latest = session.execute(
            select(func.min(Attendance.date), func.max(Attendance.date))
        ).one()
        if earliest is not None and (earliest < data.start_date or latest > data.end_date):
            raise AdminConflict(
                "Đã có dữ liệu điểm danh nằm ngoài khoảng ngày mới. "
                "Hãy chọn khoảng ngày bao trùm các ngày đã điểm danh."
            )
        year.name = data.name
        year.start_date = data.start_date
        year.end_date = data.end_date
        created = False
    session.flush()
    record_access(
        session,
        admin,
        AuditAction.UPDATE_SCHOOL_YEAR,
        class_id=None,
        details={"school_year_id": year.id, "created": created},
        commit=False,
    )
    session.commit()
    return SchoolYearOut(
        id=year.id, name=year.name, start_date=year.start_date, end_date=year.end_date
    )


# --- Lớp và giáo viên chủ nhiệm --------------------------------------------------


def _active_teacher(session: Session, teacher_id: int) -> User:
    teacher = session.get(User, teacher_id)
    if teacher is None or teacher.role is not UserRole.TEACHER or not teacher.is_active:
        raise AdminInvalid("Chỉ chọn được giáo viên đang hoạt động.")
    return teacher


def _check_homeroom(session: Session, teacher_id: int, *, for_class: int | None) -> None:
    _active_teacher(session, teacher_id)
    statement = select(SchoolClass.name).where(SchoolClass.homeroom_teacher_id == teacher_id)
    if for_class is not None:
        statement = statement.where(SchoolClass.id != for_class)
    other = session.scalar(statement.limit(1))
    if other is not None:
        raise AdminConflict(
            f"Giáo viên này đang chủ nhiệm lớp {other}. Mỗi giáo viên chỉ chủ nhiệm một lớp."
        )


def _check_class_name(
    session: Session, name: str, grade_level: int, *, except_id: int | None
) -> None:
    if not name.startswith(str(grade_level)):
        raise AdminInvalid(
            f"Tên lớp khối {grade_level} phải bắt đầu bằng {grade_level} (ví dụ {grade_level}A1)."
        )
    statement = select(SchoolClass.id).where(func.lower(SchoolClass.name) == name.lower())
    if except_id is not None:
        statement = statement.where(SchoolClass.id != except_id)
    if session.scalar(statement.limit(1)) is not None:
        raise AdminConflict(f"Đã có lớp tên {name}.")


def _get_class(session: Session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None:
        raise AdminNotFound("Không có lớp này.")
    return school_class


def create_class(session: Session, admin: User, data: ClassCreateIn) -> AdminClassOut:
    year = _the_school_year(session)
    if year is None:
        raise AdminConflict("Hãy tạo năm học trước khi tạo lớp.")
    _check_class_name(session, data.name, data.grade_level, except_id=None)
    if data.homeroom_teacher_id is not None:
        _check_homeroom(session, data.homeroom_teacher_id, for_class=None)
    school_class = SchoolClass(
        school_year_id=year.id,
        grade_level=data.grade_level,
        name=data.name,
        homeroom_teacher_id=data.homeroom_teacher_id,
    )
    session.add(school_class)
    session.flush()
    record_access(
        session,
        admin,
        AuditAction.CREATE_CLASS,
        class_id=school_class.id,
        details={"grade_level": data.grade_level, "homeroom_teacher_id": data.homeroom_teacher_id},
        commit=False,
    )
    session.commit()
    return _class_rows(session, school_class.id)[0]


def update_class(
    session: Session, admin: User, class_id: int, data: ClassUpdateIn
) -> AdminClassOut:
    school_class = _get_class(session, class_id)
    fields = data.model_fields_set
    details: dict[str, object] = {"fields": sorted(fields)}
    if "name" in fields and data.name is not None:
        _check_class_name(session, data.name, school_class.grade_level, except_id=class_id)
        school_class.name = data.name
    if "homeroom_teacher_id" in fields:
        if data.homeroom_teacher_id is not None:
            _check_homeroom(session, data.homeroom_teacher_id, for_class=class_id)
        details["homeroom_teacher_id"] = [
            school_class.homeroom_teacher_id,
            data.homeroom_teacher_id,
        ]
        school_class.homeroom_teacher_id = data.homeroom_teacher_id
    session.flush()
    record_access(
        session, admin, AuditAction.UPDATE_CLASS, class_id=class_id, details=details, commit=False
    )
    session.commit()
    return _class_rows(session, class_id)[0]


def delete_class(session: Session, admin: User, class_id: int) -> None:
    """Chỉ xoá lớp đã trống: không còn học sinh và không còn phân công."""
    school_class = _get_class(session, class_id)
    has_students = session.scalar(
        select(ClassStudent.id).where(ClassStudent.class_id == class_id).limit(1)
    )
    has_assignments = session.scalar(
        select(TeachingAssignment.id).where(TeachingAssignment.class_id == class_id).limit(1)
    )
    if has_students is not None or has_assignments is not None:
        raise AdminConflict(
            "Lớp còn học sinh hoặc còn phân công giảng dạy. Hãy gỡ hết trước khi xoá lớp."
        )
    # Bản xem trước nhập tệp chưa xác nhận của lớp này (nếu có) cũng bỏ đi.
    session.execute(delete(ImportJob).where(ImportJob.class_id == class_id))
    details = {"grade_level": school_class.grade_level}
    session.delete(school_class)
    session.flush()
    record_access(
        session, admin, AuditAction.DELETE_CLASS, class_id=class_id, details=details, commit=False
    )
    session.commit()


# --- Phân công giảng dạy --------------------------------------------------


def get_class_assignments(session: Session, class_id: int) -> ClassAssignmentsOut:
    school_class = _get_class(session, class_id)
    rows = session.execute(
        select(Subject, User.id, User.full_name)
        .outerjoin(
            TeachingAssignment,
            (TeachingAssignment.subject_id == Subject.id)
            & (TeachingAssignment.class_id == class_id),
        )
        .outerjoin(User, User.id == TeachingAssignment.teacher_id)
        .order_by(Subject.id)
    )
    return ClassAssignmentsOut(
        class_id=school_class.id,
        class_name=school_class.name,
        grade_level=school_class.grade_level,
        subjects=[
            AssignmentRow(
                subject_id=r[0].id,
                subject_name=r[0].name,
                is_elective=r[0].is_elective,
                assessment_type=r[0].assessment_type,
                teacher=None if r[1] is None else TeacherRef(id=r[1], full_name=r[2]),
            )
            for r in rows
        ],
    )


def set_assignment(
    session: Session, admin: User, class_id: int, subject_id: int, teacher_id: int
) -> ClassAssignmentsOut:
    """Gán giáo viên cho cặp lớp-môn, hoặc đổi giáo viên nếu đã có."""
    _get_class(session, class_id)
    if session.get(Subject, subject_id) is None:
        raise AdminNotFound("Không có môn này.")
    _active_teacher(session, teacher_id)
    existing = session.scalar(
        select(TeachingAssignment).where(
            TeachingAssignment.class_id == class_id, TeachingAssignment.subject_id == subject_id
        )
    )
    previous = None if existing is None else existing.teacher_id
    if existing is None:
        session.add(
            TeachingAssignment(class_id=class_id, subject_id=subject_id, teacher_id=teacher_id)
        )
    else:
        existing.teacher_id = teacher_id
    session.flush()
    record_access(
        session,
        admin,
        AuditAction.SET_ASSIGNMENT,
        class_id=class_id,
        details={"subject_id": subject_id, "teacher_id": [previous, teacher_id]},
        commit=False,
    )
    session.commit()
    return get_class_assignments(session, class_id)


def remove_assignment(
    session: Session, admin: User, class_id: int, subject_id: int
) -> ClassAssignmentsOut:
    """Gỡ phân công; từ chối nếu lớp đã có điểm môn đó (điểm sẽ mồ côi, không ai nhập tiếp được)."""
    _get_class(session, class_id)
    existing = session.scalar(
        select(TeachingAssignment).where(
            TeachingAssignment.class_id == class_id, TeachingAssignment.subject_id == subject_id
        )
    )
    if existing is None:
        raise AdminNotFound("Môn này chưa được phân công cho lớp.")
    has_scores = session.scalar(
        select(Assessment.id)
        .join(ClassStudent, ClassStudent.id == Assessment.class_student_id)
        .where(ClassStudent.class_id == class_id, Assessment.subject_id == subject_id)
        .limit(1)
    )
    if has_scores is not None:
        raise AdminConflict(
            "Lớp đã có điểm của môn này nên không gỡ phân công được. Hãy đổi sang giáo viên khác."
        )
    session.delete(existing)
    session.flush()
    record_access(
        session,
        admin,
        AuditAction.REMOVE_ASSIGNMENT,
        class_id=class_id,
        details={"subject_id": subject_id, "teacher_id": existing.teacher_id},
        commit=False,
    )
    session.commit()
    return get_class_assignments(session, class_id)


def copy_assignments(
    session: Session, admin: User, class_id: int, from_class_id: int
) -> tuple[int, ClassAssignmentsOut]:
    """Sao chép giáo viên cho các môn còn trống từ một lớp cùng khối. Không đè phân công có sẵn."""
    target = _get_class(session, class_id)
    if from_class_id == class_id:
        raise AdminInvalid("Hãy chọn lớp khác để sao chép.")
    source = session.get(SchoolClass, from_class_id)
    if source is None:
        raise AdminNotFound("Không có lớp nguồn này.")
    if source.grade_level != target.grade_level:
        raise AdminInvalid("Chỉ sao chép được từ lớp cùng khối.")
    assigned = set(
        session.scalars(
            select(TeachingAssignment.subject_id).where(TeachingAssignment.class_id == class_id)
        )
    )
    copied = 0
    for source_row in session.scalars(
        select(TeachingAssignment)
        .where(TeachingAssignment.class_id == from_class_id)
        .order_by(TeachingAssignment.subject_id)
    ):
        if source_row.subject_id in assigned:
            continue
        # Giáo viên đã bị khoá hoặc đổi vai trò thì bỏ qua, không mang sang lớp mới.
        teacher = session.get(User, source_row.teacher_id)
        if teacher is None or teacher.role is not UserRole.TEACHER or not teacher.is_active:
            continue
        session.add(
            TeachingAssignment(
                class_id=class_id, subject_id=source_row.subject_id, teacher_id=teacher.id
            )
        )
        copied += 1
    session.flush()
    record_access(
        session,
        admin,
        AuditAction.SET_ASSIGNMENT,
        class_id=class_id,
        details={"copied": copied, "from_class_id": from_class_id},
        commit=False,
    )
    session.commit()
    return copied, get_class_assignments(session, class_id)


# --- Gỡ học sinh khỏi lớp --------------------------------------------------


def remove_student(session: Session, admin: User, class_id: int, student_code: str) -> None:
    """Gỡ một học sinh (theo mã Admin gõ vào) khỏi lớp, chỉ khi em chưa có dữ liệu nào.

    Không trả tên hay thông tin học sinh. Em không còn ở lớp nào thì xoá luôn hồ sơ học sinh.
    """
    _get_class(session, class_id)
    code = student_code.strip().upper()
    row = session.execute(
        select(ClassStudent.id, Student.id)
        .join(Student, Student.id == ClassStudent.student_id)
        .where(ClassStudent.class_id == class_id, func.upper(Student.student_code) == code)
    ).first()
    if row is None:
        raise AdminNotFound("Lớp này không có học sinh mã đó.")
    class_student_id, student_id = row
    for model in (Assessment, Attendance, ConductResult, ExamRegistration, RiskAlert):
        found = session.scalar(
            select(model.id).where(model.class_student_id == class_student_id).limit(1)
        )
        if found is not None:
            raise AdminConflict(
                "Em này đã có dữ liệu (điểm, điểm danh, rèn luyện hoặc cảnh báo) "
                "nên không gỡ khỏi lớp được."
            )
    session.execute(delete(ClassStudent).where(ClassStudent.id == class_student_id))
    still_enrolled = session.scalar(
        select(ClassStudent.id).where(ClassStudent.student_id == student_id).limit(1)
    )
    if still_enrolled is None:
        session.execute(delete(Student).where(Student.id == student_id))
    record_access(
        session,
        admin,
        AuditAction.REMOVE_CLASS_STUDENT,
        class_id=class_id,
        details={"student_id": student_id, "student_deleted": still_enrolled is None},
        commit=False,
    )
    session.commit()

"""Quản lý tài khoản của Admin và đổi mật khẩu (D-096, D-097).

Khoá tài khoản thay cho xoá: điểm, nhật ký và phân công còn tham chiếu tới người dùng. Mật khẩu tạm
chỉ được trả về một lần; nhật ký (`audit_logs.details`) không bao giờ chứa mật khẩu.
"""

from sqlalchemy import ColumnElement, ScalarSelect, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.admin_schemas import (
    AdminUserOut,
    ChangePasswordIn,
    CreatedUserOut,
    PasswordResetOut,
    UserCreateIn,
    UserUpdateIn,
)
from app.auth.audit import record_access
from app.auth.models import User
from app.classes.models import SchoolClass, TeachingAssignment
from app.core.enums import AuditAction, UserRole
from app.core.labels import label_vi
from app.core.security import generate_temporary_password, hash_password, verify_password


class UserNotFound(Exception):
    """Không có tài khoản này."""


class EmailTaken(Exception):
    """Email đã được tài khoản khác dùng (không phân biệt hoa thường)."""


class SelfProtected(Exception):
    """Admin không được tự khoá hoặc tự hạ quyền của chính mình.

    Nhờ đó luôn còn ít nhất một Admin đang hoạt động: người thực hiện thay đổi chính là một Admin
    đang hoạt động khác với tài khoản bị đổi, nên không cần kiểm "Admin cuối cùng" riêng (D-097).
    """


class HasAssignments(Exception):
    """Đang chủ nhiệm hoặc được phân công giảng dạy: phải gỡ trước khi đổi sang vai trò khác."""


class WrongPassword(Exception):
    """Mật khẩu hiện tại không đúng."""


class PasswordUnchanged(Exception):
    """Mật khẩu mới trùng mật khẩu hiện tại."""


def _homeroom_name(user_id: ColumnElement[int]) -> ScalarSelect[str]:
    return (
        select(SchoolClass.name)
        .where(SchoolClass.homeroom_teacher_id == user_id)
        .order_by(SchoolClass.name)
        .limit(1)
        .scalar_subquery()
    )


def _assignment_count(user_id: ColumnElement[int]) -> ScalarSelect[int]:
    return (
        select(func.count())
        .select_from(TeachingAssignment)
        .where(TeachingAssignment.teacher_id == user_id)
        .scalar_subquery()
    )


def _out(user: User, homeroom_class: str | None, assignment_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        role_label=label_vi(user.role),
        is_active=user.is_active,
        homeroom_class=homeroom_class,
        assignment_count=assignment_count,
    )


def _load_out(session: Session, user_id: int) -> AdminUserOut:
    row = session.execute(
        select(User, _homeroom_name(User.id), _assignment_count(User.id)).where(User.id == user_id)
    ).one()
    return _out(row[0], row[1], row[2])


def list_users(
    session: Session, *, role: UserRole | None, active: bool | None, query: str | None
) -> list[AdminUserOut]:
    statement = select(User, _homeroom_name(User.id), _assignment_count(User.id)).order_by(
        User.role, User.full_name, User.id
    )
    if role is not None:
        statement = statement.where(User.role == role)
    if active is not None:
        statement = statement.where(User.is_active == active)
    if query and query.strip():
        text = query.strip()
        statement = statement.where(
            User.full_name.icontains(text, autoescape=True)
            | User.email.icontains(text, autoescape=True)
        )
    return [_out(row[0], row[1], row[2]) for row in session.execute(statement)]


def _email_in_use(session: Session, email: str, *, except_id: int | None = None) -> bool:
    statement = select(User.id).where(func.lower(User.email) == email.lower())
    if except_id is not None:
        statement = statement.where(User.id != except_id)
    return session.scalar(statement.limit(1)) is not None


def create_user(session: Session, admin: User, data: UserCreateIn) -> CreatedUserOut:
    email = data.email.lower()
    if _email_in_use(session, email):
        raise EmailTaken
    password = generate_temporary_password()
    user = User(
        email=email,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:  # hai yêu cầu cùng lúc cùng email
        session.rollback()
        raise EmailTaken from None
    record_access(
        session,
        admin,
        AuditAction.CREATE_USER,
        class_id=None,
        details={"user_id": user.id, "role": user.role.value},
        commit=False,
    )
    session.commit()
    return CreatedUserOut(user=_load_out(session, user.id), temporary_password=password)


def _has_teaching_duties(session: Session, user_id: int) -> bool:
    homeroom = session.scalar(
        select(SchoolClass.id).where(SchoolClass.homeroom_teacher_id == user_id).limit(1)
    )
    assigned = session.scalar(
        select(TeachingAssignment.id).where(TeachingAssignment.teacher_id == user_id).limit(1)
    )
    return homeroom is not None or assigned is not None


def update_user(session: Session, admin: User, user_id: int, data: UserUpdateIn) -> AdminUserOut:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFound
    changes = data.model_fields_set
    new_role = data.role if "role" in changes else user.role
    new_active = data.is_active if "is_active" in changes else user.is_active
    assert new_role is not None and new_active is not None  # _no_null_values đã chặn null

    if user.id == admin.id and (new_role is not UserRole.ADMIN or not new_active):
        raise SelfProtected
    leaving_teaching = new_role is not user.role and new_role is not UserRole.TEACHER
    if leaving_teaching and _has_teaching_duties(session, user.id):
        raise HasAssignments
    if "email" in changes and data.email is not None:
        email = data.email.lower()
        if email != user.email.lower() and _email_in_use(session, email, except_id=user.id):
            raise EmailTaken

    details: dict[str, object] = {"user_id": user.id, "fields": sorted(changes)}
    if new_role is not user.role:
        details["role"] = [user.role.value, new_role.value]
    if new_active != user.is_active:
        details["is_active"] = [user.is_active, new_active]
    if "email" in changes and data.email is not None:
        user.email = data.email.lower()
    if "full_name" in changes and data.full_name is not None:
        user.full_name = data.full_name
    user.role = new_role
    user.is_active = new_active
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise EmailTaken from None
    record_access(
        session, admin, AuditAction.UPDATE_USER, class_id=None, details=details, commit=False
    )
    session.commit()
    return _load_out(session, user.id)


def reset_password(session: Session, admin: User, user_id: int) -> PasswordResetOut:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFound
    password = generate_temporary_password()
    user.password_hash = hash_password(password)
    record_access(
        session,
        admin,
        AuditAction.RESET_USER_PASSWORD,
        class_id=None,
        details={"user_id": user.id},
        commit=False,
    )
    session.commit()
    return PasswordResetOut(temporary_password=password)


def change_password(session: Session, user: User, data: ChangePasswordIn) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise WrongPassword
    if data.new_password == data.current_password:
        raise PasswordUnchanged
    user.password_hash = hash_password(data.new_password)
    record_access(
        session, user, AuditAction.CHANGE_PASSWORD, class_id=None, details={}, commit=False
    )
    session.commit()

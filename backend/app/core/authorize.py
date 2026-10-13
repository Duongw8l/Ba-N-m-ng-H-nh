"""authorize(): nơi DUY NHẤT quyết định ai được xem dữ liệu của lớp, môn, khối nào (nguyên tắc 4).

Mọi endpoint và mọi tool của LLM đều gọi hàm này; phạm vi (class_id, subject_id, grade_level) lấy từ
phiên đăng nhập và bảng phân công, không bao giờ do LLM điền (nguyên tắc 3).

Quy tắc (docs/DECISIONS.md, D-039 và D-040):
- Admin: không xem dữ liệu học sinh, luôn bị từ chối.
- BGH (principal): toàn trường, thấy cả thông tin phụ huynh.
- GVCN: lớp mình chủ nhiệm, mọi môn, thấy cả thông tin phụ huynh.
- GVBM: đúng lớp-môn có trong teaching_assignments, không thấy thông tin phụ huynh.
- Một giáo viên có thể vừa GVCN vừa GVBM: quyền cộng dồn, tính riêng cho từng lớp.
- Chưa phân công thì từ chối, kể cả lớp không tồn tại (giáo viên không biết lớp nào có thật).

Hàm ném AuthorizationError (không ném HTTPException) để tool của LLM gọi lại được mà không cần HTTP;
app/main.py chuyển nó thành HTTP 403 với thông điệp chung, không nói lý do.
"""

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.classes.models import SchoolClass, TeachingAssignment
from app.core.enums import UserRole

FORBIDDEN_MESSAGE = "Bạn không có quyền truy cập dữ liệu này."


class AuthorizationError(Exception):
    """Người dùng không được phép truy cập phạm vi đã yêu cầu."""


@dataclass(frozen=True)
class Access:
    """Kết quả của một lần kiểm tra thành công: người dùng được làm gì trong phạm vi đó."""

    role: UserRole
    class_id: int | None
    is_homeroom: bool  # chủ nhiệm đúng lớp này
    subject_ids: frozenset[int] | None  # các môn được xem; None là mọi môn
    can_view_guardian: bool  # được xem guardian_name, guardian_phone của học sinh lớp này

    def allows_subject(self, subject_id: int) -> bool:
        return self.subject_ids is None or subject_id in self.subject_ids

    def require_all_subjects(self) -> None:
        """Cho dữ liệu cả lớp (mọi môn): GVBM chỉ có một số môn nên bị từ chối."""
        if self.subject_ids is not None:
            raise AuthorizationError


def authorize(
    session: Session,
    user: User,
    *,
    class_id: int | None = None,
    subject_id: int | None = None,
    grade_level: int | None = None,
) -> Access:
    """Cho phép hoặc ném AuthorizationError. Phải gọi trước khi đọc bất kỳ dữ liệu nào.

    - class_id: dữ liệu của một lớp; thêm subject_id để chỉ một môn của lớp đó.
    - grade_level: dữ liệu cấp khối (so sánh các lớp trong khối), chỉ BGH.
    """
    if subject_id is not None and class_id is None:
        raise ValueError("subject_id phải đi kèm class_id.")
    if (class_id is None) == (grade_level is None):
        raise ValueError("Cần đúng một trong class_id hoặc grade_level.")

    if user.role is UserRole.PRINCIPAL:
        return Access(user.role, class_id, False, None, True)
    if user.role is not UserRole.TEACHER or class_id is None:
        # Admin, vai trò lạ, hoặc giáo viên hỏi dữ liệu cấp khối.
        raise AuthorizationError

    is_homeroom = (
        session.scalar(
            select(SchoolClass.id).where(
                SchoolClass.id == class_id, SchoolClass.homeroom_teacher_id == user.id
            )
        )
        is not None
    )
    if is_homeroom:
        access = Access(user.role, class_id, True, None, True)
    else:
        taught = frozenset(
            session.scalars(
                select(TeachingAssignment.subject_id).where(
                    TeachingAssignment.class_id == class_id,
                    TeachingAssignment.teacher_id == user.id,
                )
            )
        )
        if not taught:
            raise AuthorizationError
        access = Access(user.role, class_id, False, taught, False)

    if subject_id is not None and not access.allows_subject(subject_id):
        raise AuthorizationError
    return access


def authorize_admin(user: User) -> None:
    """Việc quản trị hệ thống (văn bản quy định cho RAG...): chỉ Admin (D-077)."""
    if user.role is not UserRole.ADMIN:
        raise AuthorizationError


def authorize_school(user: User) -> None:
    """Dữ liệu cấp toàn trường (ví dụ cảnh báo mức Cao của mọi lớp): chỉ BGH (D-072)."""
    if user.role is not UserRole.PRINCIPAL:
        raise AuthorizationError


def authorize_write(
    session: Session, user: User, *, class_id: int, subject_id: int | None = None
) -> Access:
    """Quyền GHI dữ liệu của lớp (nhập từ tệp), hẹp hơn quyền xem (D-058).

    - Có `subject_id` (nhập điểm): phải có phân công đúng lớp-môn đó. GVCN không dạy môn đó, BGH,
      Admin đều bị từ chối.
    - Không có `subject_id` (điểm danh, rèn luyện): phải là GVCN của lớp.
    Người dạy môn ở lớp này và chủ nhiệm lớp kia có quyền cộng dồn, tính riêng từng lớp.
    """
    if user.role is not UserRole.TEACHER:
        raise AuthorizationError
    if subject_id is None:
        is_homeroom = session.scalar(
            select(SchoolClass.id).where(
                SchoolClass.id == class_id, SchoolClass.homeroom_teacher_id == user.id
            )
        )
        if is_homeroom is None:
            raise AuthorizationError
        return Access(user.role, class_id, True, None, True)

    assigned = session.scalar(
        select(TeachingAssignment.id).where(
            TeachingAssignment.class_id == class_id,
            TeachingAssignment.subject_id == subject_id,
            TeachingAssignment.teacher_id == user.id,
        )
    )
    if assigned is None:
        raise AuthorizationError
    is_homeroom_too = (
        session.scalar(
            select(SchoolClass.id).where(
                SchoolClass.id == class_id, SchoolClass.homeroom_teacher_id == user.id
            )
        )
        is not None
    )
    return Access(user.role, class_id, is_homeroom_too, frozenset({subject_id}), is_homeroom_too)


def authorization_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Đăng ký trong app/main.py: AuthorizationError thành HTTP 403."""
    return JSONResponse(status_code=403, content={"detail": FORBIDDEN_MESSAGE})

"""API quản trị năm học, lớp, GVCN, phân công giảng dạy (D-098, D-099): chỉ Admin.

Mọi endpoint qua `AdminUser` (401 rồi 403 trước khi đọc yêu cầu). Admin không xem dữ liệu học sinh
(D-039): phản hồi chỉ có số đếm, và gỡ học sinh theo mã do Admin gõ vào.

DESIGN mục 7 ghi `POST /admin/assignments`; ở đây phân công đi theo từng lớp (`PUT
/admin/classes/{id}/assignments/{subject_id}`) vì mỗi lần là một cặp lớp-môn (D-099).
"""

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import AdminUser
from app.classes import admin_service as service
from app.classes.admin_schemas import (
    AdminClassOut,
    AssignmentIn,
    ClassAssignmentsOut,
    ClassCreateIn,
    ClassUpdateIn,
    CopiedOut,
    CopyAssignmentsIn,
    DeletedOut,
    RemoveStudentIn,
    SchoolOut,
    SchoolYearIn,
    SchoolYearOut,
    TeacherOut,
)
from app.core.db import DbSession

router = APIRouter(prefix="/admin", tags=["admin"])

T = TypeVar("T")


def _run(action: Callable[[], T]) -> T:
    """Đổi lỗi nghiệp vụ của service thành HTTP: 404, 409 hoặc 422 kèm thông điệp tiếng Việt."""
    try:
        return action()
    except service.AdminNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=error.message) from None
    except service.AdminConflict as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error.message) from None
    except service.AdminInvalid as error:
        raise HTTPException(422, detail=error.message) from None


@router.get("/school", response_model=SchoolOut, summary="Năm học và các lớp (chỉ Admin)")
def get_school(admin: AdminUser, session: DbSession) -> SchoolOut:
    return service.get_school(session)


@router.get(
    "/teachers",
    response_model=list[TeacherOut],
    summary="Giáo viên đang hoạt động, để chọn GVCN hoặc người dạy (chỉ Admin)",
)
def list_teachers(admin: AdminUser, session: DbSession) -> list[TeacherOut]:
    return service.list_teachers(session)


@router.put(
    "/school-year",
    response_model=SchoolYearOut,
    summary="Tạo năm học đầu tiên hoặc sửa năm học duy nhất (chỉ Admin)",
)
def save_school_year(admin: AdminUser, session: DbSession, body: SchoolYearIn) -> SchoolYearOut:
    return _run(lambda: service.save_school_year(session, admin, body))


@router.post(
    "/classes",
    response_model=AdminClassOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo lớp trong năm học (chỉ Admin)",
)
def create_class(admin: AdminUser, session: DbSession, body: ClassCreateIn) -> AdminClassOut:
    return _run(lambda: service.create_class(session, admin, body))


@router.patch(
    "/classes/{class_id}",
    response_model=AdminClassOut,
    summary="Đổi tên lớp hoặc giáo viên chủ nhiệm (chỉ Admin)",
)
def update_class(
    class_id: int, admin: AdminUser, session: DbSession, body: ClassUpdateIn
) -> AdminClassOut:
    return _run(lambda: service.update_class(session, admin, class_id, body))


@router.delete(
    "/classes/{class_id}",
    response_model=DeletedOut,
    summary="Xoá lớp đã trống (chỉ Admin)",
)
def delete_class(class_id: int, admin: AdminUser, session: DbSession) -> DeletedOut:
    _run(lambda: service.delete_class(session, admin, class_id))
    return DeletedOut(detail="Đã xoá lớp.")


@router.get(
    "/classes/{class_id}/assignments",
    response_model=ClassAssignmentsOut,
    summary="Môn học của lớp và giáo viên phụ trách (chỉ Admin)",
)
def get_assignments(class_id: int, admin: AdminUser, session: DbSession) -> ClassAssignmentsOut:
    return _run(lambda: service.get_class_assignments(session, class_id))


@router.put(
    "/classes/{class_id}/assignments/{subject_id}",
    response_model=ClassAssignmentsOut,
    summary="Gán hoặc đổi giáo viên của một cặp lớp-môn (chỉ Admin)",
)
def set_assignment(
    class_id: int, subject_id: int, admin: AdminUser, session: DbSession, body: AssignmentIn
) -> ClassAssignmentsOut:
    return _run(
        lambda: service.set_assignment(session, admin, class_id, subject_id, body.teacher_id)
    )


@router.delete(
    "/classes/{class_id}/assignments/{subject_id}",
    response_model=ClassAssignmentsOut,
    summary="Gỡ phân công khi lớp chưa có điểm môn đó (chỉ Admin)",
)
def remove_assignment(
    class_id: int, subject_id: int, admin: AdminUser, session: DbSession
) -> ClassAssignmentsOut:
    return _run(lambda: service.remove_assignment(session, admin, class_id, subject_id))


@router.post(
    "/classes/{class_id}/assignments/copy",
    response_model=CopiedOut,
    summary="Sao chép phân công còn trống từ một lớp cùng khối (chỉ Admin)",
)
def copy_assignments(
    class_id: int, admin: AdminUser, session: DbSession, body: CopyAssignmentsIn
) -> CopiedOut:
    copied, _ = _run(lambda: service.copy_assignments(session, admin, class_id, body.from_class_id))
    return CopiedOut(copied=copied)


@router.post(
    "/classes/{class_id}/students/remove",
    response_model=DeletedOut,
    summary="Gỡ học sinh (theo mã) khỏi lớp khi em chưa có dữ liệu (chỉ Admin)",
)
def remove_student(
    class_id: int, admin: AdminUser, session: DbSession, body: RemoveStudentIn
) -> DeletedOut:
    _run(lambda: service.remove_student(session, admin, class_id, body.student_code))
    return DeletedOut(detail="Đã gỡ học sinh khỏi lớp.")

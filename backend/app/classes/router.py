"""GET /api/v1/me/assignments và GET /api/v1/classes/{class_id}/students.

/me/assignments là ngoại lệ của nguyên tắc 4: chỉ trả dữ liệu của chính người gọi, không có phạm vi
lớp/môn nào để kiểm (D-042). Endpoint danh sách học sinh gọi authorize() TRƯỚC khi đụng tới dữ liệu.
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.audit import record_access
from app.auth.deps import CurrentUser
from app.classes.schemas import AssignmentsResponse, StudentOut, StudentWithGuardianOut
from app.classes.service import class_exists, get_assignments, list_students
from app.core.authorize import authorize
from app.core.db import DbSession
from app.core.enums import AuditAction

router = APIRouter(tags=["classes"])


@router.get(
    "/me/assignments",
    response_model=AssignmentsResponse,
    summary="Lớp chủ nhiệm và lớp-môn được phân công của tôi",
)
def my_assignments(user: CurrentUser, session: DbSession) -> AssignmentsResponse:
    return get_assignments(session, user)


@router.get(
    "/classes/{class_id}/students",
    response_model=list[StudentWithGuardianOut] | list[StudentOut],
    summary="Danh sách học sinh của lớp",
)
def class_students(
    class_id: int, user: CurrentUser, session: DbSession
) -> list[StudentWithGuardianOut] | list[StudentOut]:
    access = authorize(session, user, class_id=class_id)
    if not class_exists(session, class_id):
        # Chỉ BGH tới được đây (giáo viên và Admin đã bị 403 ở trên khi lớp không có thật).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có lớp này.")

    students = list_students(session, class_id, with_guardian=access.can_view_guardian)
    record_access(
        session,
        user,
        AuditAction.VIEW_CLASS_STUDENTS,
        class_id=class_id,
        details={"student_count": len(students), "guardian_included": access.can_view_guardian},
    )
    return students

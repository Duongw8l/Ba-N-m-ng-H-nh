"""Ai được tạo, sửa, duyệt và xuất nhận xét, báo cáo (D-102). Mọi cửa đều qua `authorize()`.

- `subject_comment` (học sinh): GVBM dạy đúng lớp-môn đó (`authorize_write`).
- `school_record`, `contact_slip` (học sinh): GVCN của lớp.
- `report` của một lớp: GVCN của lớp hoặc BGH.
- `report` của một khối: chỉ BGH.

Admin không xem dữ liệu học sinh (D-039) nên bị từ chối ở mọi loại. BGH không viết nhận xét học
sinh. Tạo, sửa, duyệt, xuất cùng một quyền: người viết cũng là người duyệt.
"""

from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.authorize import AuthorizationError, authorize, authorize_write
from app.core.enums import ReportScope, ReportType, UserRole

STUDENT_TYPES = frozenset(
    {ReportType.SUBJECT_COMMENT, ReportType.SCHOOL_RECORD, ReportType.CONTACT_SLIP}
)
GRADE_LEVELS = (10, 11, 12)


def scope_for(report_type: ReportType, *, class_id: int | None) -> ReportScope:
    """Phạm vi của một loại: nhận xét là học sinh; báo cáo là lớp nếu có lớp, ngược lại là khối."""
    if report_type is not ReportType.REPORT:
        return ReportScope.STUDENT
    return ReportScope.CLASS if class_id is not None else ReportScope.GRADE


def authorize_report(
    session: Session,
    user: User,
    *,
    report_type: ReportType,
    class_id: int | None,
    subject_id: int | None = None,
    grade_level: int | None = None,
) -> None:
    """Cho phép hoặc ném AuthorizationError. Gọi trước khi đọc bất kỳ dữ liệu học sinh nào."""
    if report_type is ReportType.SUBJECT_COMMENT:
        if class_id is None or subject_id is None:
            raise AuthorizationError
        authorize_write(session, user, class_id=class_id, subject_id=subject_id)
        return

    if report_type is ReportType.REPORT and class_id is None:
        if grade_level is None:
            raise AuthorizationError
        authorize(session, user, grade_level=grade_level)  # chỉ BGH qua được
        return

    if class_id is None:
        raise AuthorizationError
    access = authorize(session, user, class_id=class_id)
    if report_type is ReportType.REPORT:
        if user.role is not UserRole.PRINCIPAL and not access.is_homeroom:
            raise AuthorizationError
        return
    # Học bạ, phiếu liên lạc: GVCN của lớp (BGH xem được lớp nhưng không viết nhận xét).
    if user.role is not UserRole.TEACHER or not access.is_homeroom:
        raise AuthorizationError

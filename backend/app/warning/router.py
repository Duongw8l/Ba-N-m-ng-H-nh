"""API cảnh báo sớm (D-071, D-072): cảnh báo của lớp, ghi nhận của GVCN, cảnh báo toàn trường.

Mọi endpoint gọi authorize() TRƯỚC khi đọc dữ liệu (nguyên tắc 4). Cảnh báo chỉ GVCN của lớp và BGH
thấy (DESIGN mục 10); GVBM không thấy. Ghi nhận ("đã trao đổi", "báo nhầm") chỉ GVCN của lớp.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.analytics import repository as analytics_repo
from app.auth.audit import record_access
from app.auth.deps import CurrentUser
from app.core.authorize import AuthorizationError, authorize, authorize_school, authorize_write
from app.core.db import DbSession
from app.core.enums import AuditAction, RiskLevel
from app.warning import repository as repo
from app.warning import service
from app.warning.schemas import AlertOut, AlertUpdateIn, ClassAlertsOut, SchoolAlertsOut

router = APIRouter(tags=["warning"])


@router.get(
    "/classes/{class_id}/alerts",
    response_model=ClassAlertsOut,
    summary="Cảnh báo sớm của lớp (GVCN của lớp và BGH)",
)
def class_alerts(
    class_id: int,
    user: CurrentUser,
    session: DbSession,
    include_low: Annotated[
        bool, Query(description="Kèm cả mức Thấp (mặc định: Cao và Trung bình)")
    ] = False,
) -> ClassAlertsOut:
    access = authorize(session, user, class_id=class_id)
    access.require_all_subjects()  # GVBM không thấy cảnh báo
    class_info = analytics_repo.get_class(session, class_id)
    if class_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có lớp này.")

    result = service.class_alerts(session, class_id, class_info.name, include_low=include_low)
    record_access(
        session,
        user,
        AuditAction.VIEW_CLASS_ALERTS,
        class_id=class_id,
        details={"include_low": include_low, "alert_count": len(result.alerts)},
    )
    return result


@router.get(
    "/alerts",
    response_model=SchoolAlertsOut,
    summary="Cảnh báo sớm toàn trường theo mức (chỉ BGH)",
)
def school_alerts(
    user: CurrentUser,
    session: DbSession,
    level: Annotated[RiskLevel, Query(description="Mức cảnh báo cần xem")] = RiskLevel.HIGH,
) -> SchoolAlertsOut:
    authorize_school(user)
    result = service.school_alerts(session, level)
    record_access(
        session,
        user,
        AuditAction.VIEW_SCHOOL_ALERTS,
        class_id=None,
        details={"level": level.value, "alert_count": len(result.alerts)},
    )
    return result


@router.patch(
    "/alerts/{alert_id}",
    response_model=AlertOut,
    summary="GVCN ghi nhận 'đã trao đổi' hoặc 'báo nhầm' cho một cảnh báo",
)
def update_alert(
    alert_id: int, body: AlertUpdateIn, user: CurrentUser, session: DbSession
) -> AlertOut:
    scope = repo.alert_scope(session, alert_id)
    if scope is None:
        # Không nói cảnh báo có tồn tại hay không: cùng 403 với người không có quyền.
        raise AuthorizationError
    alert, class_id, is_current = scope
    authorize_write(session, user, class_id=class_id)  # chỉ GVCN của lớp; BGH chỉ xem
    if not is_current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cảnh báo này đã được thay bằng cảnh báo mới hơn. Hãy tải lại danh sách.",
        )

    alert.teacher_status = body.teacher_status
    record_access(
        session,
        user,
        AuditAction.UPDATE_ALERT,
        class_id=class_id,
        details={"alert_id": alert_id, "teacher_status": body.teacher_status.value},
        commit=False,
    )
    session.commit()
    return service.alert_out(repo.alert_row(session, alert_id))

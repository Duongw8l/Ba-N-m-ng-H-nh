"""Ba endpoint số liệu: dashboard lớp, bảng điểm môn, tổng quan khối.

Mọi endpoint gọi authorize() TRƯỚC khi đọc dữ liệu (nguyên tắc 4). Các con số do service.py và các
hàm thuần trong analytics/ tính; endpoint chỉ kiểm quyền, gọi, ghi nhật ký và trả kết quả.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.analytics import repository as repo
from app.analytics import service
from app.analytics.config import load_config
from app.analytics.schemas import DashboardOut, GradeOverviewOut, Period, SubjectScoresOut
from app.auth.audit import record_access
from app.auth.deps import CurrentUser
from app.core.authorize import authorize
from app.core.db import DbSession
from app.core.enums import AuditAction

router = APIRouter(tags=["analytics"])

PeriodQuery = Annotated[
    Period, Query(description="Kỳ xem: 1 (học kỳ I), 2 (học kỳ II) hoặc year (cả năm).")
]


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


@router.get(
    "/classes/{class_id}/dashboard",
    response_model=DashboardOut,
    summary="Dashboard lớp (GVCN của lớp và BGH)",
)
def class_dashboard(
    class_id: int, user: CurrentUser, session: DbSession, semester: PeriodQuery = "1"
) -> DashboardOut:
    access = authorize(session, user, class_id=class_id)
    access.require_all_subjects()  # dashboard có mọi môn: GVBM không xem được
    class_info = repo.get_class(session, class_id)
    if class_info is None:
        raise _not_found("Không có lớp này.")

    dashboard = service.build_dashboard(session, class_info, semester, load_config(session))
    record_access(
        session,
        user,
        AuditAction.VIEW_CLASS_DASHBOARD,
        class_id=class_id,
        details={"semester": semester, "student_count": dashboard.student_count},
    )
    return dashboard


@router.get(
    "/classes/{class_id}/subjects/{subject_id}/scores",
    response_model=SubjectScoresOut,
    summary="Bảng điểm một môn của lớp (GVBM đúng môn, GVCN, BGH)",
)
def subject_scores(
    class_id: int,
    subject_id: int,
    user: CurrentUser,
    session: DbSession,
    semester: Annotated[int, Query(ge=1, le=2, description="Học kỳ 1 hoặc 2.")] = 1,
) -> SubjectScoresOut:
    authorize(session, user, class_id=class_id, subject_id=subject_id)
    class_info = repo.get_class(session, class_id)
    if class_info is None:
        raise _not_found("Không có lớp này.")
    subject = next((s for s in repo.class_subjects(session, class_id) if s.id == subject_id), None)
    if subject is None:
        raise _not_found("Lớp này không học môn này.")

    scores = service.build_subject_scores(
        session, class_info, subject, semester, load_config(session)
    )
    record_access(
        session,
        user,
        AuditAction.VIEW_SUBJECT_SCORES,
        class_id=class_id,
        details={
            "subject_id": subject_id,
            "semester": semester,
            "student_count": scores.student_count,
        },
    )
    return scores


@router.get(
    "/grades/{level}/overview",
    response_model=GradeOverviewOut,
    summary="So sánh các lớp trong một khối (chỉ BGH)",
)
def grade_overview(
    level: int, user: CurrentUser, session: DbSession, semester: PeriodQuery = "1"
) -> GradeOverviewOut:
    authorize(session, user, grade_level=level)
    classes = repo.classes_in_grade(session, level)
    if not classes:
        raise _not_found("Không có khối này.")
    # Chỉ số liệu gộp theo lớp, không có tên học sinh nên không ghi nhật ký truy cập hồ sơ.
    return service.build_grade_overview(session, level, classes, semester, load_config(session))

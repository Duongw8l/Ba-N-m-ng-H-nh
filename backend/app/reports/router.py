"""API nhận xét và báo cáo (Giai đoạn 9, D-107).

Thứ tự lỗi: 401 chưa đăng nhập, 403 không có quyền (kể cả Admin, id lạ), 404 lớp / học sinh không
có thật (chỉ tới được sau khi qua quyền), 409 sai trạng thái (sinh lại bản đã duyệt, xuất bản
nháp), 422 yêu cầu sai hình dạng, rồi 503 chưa cấu hình LLM (nhà cung cấp chỉ được dựng SAU khi
kiểm quyền), 502 lỗi nhà cung cấp.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.assistant.llm import LLMError, LLMNotConfigured
from app.assistant.router import ProviderFactoryDep
from app.auth.deps import CurrentUser
from app.core.db import DbSession
from app.reports import export, jobs, service
from app.reports.generation import FeedbackRejected
from app.reports.permissions import STUDENT_TYPES
from app.reports.schemas import (
    JobOut,
    RegenerateIn,
    ReportIn,
    ReportListOut,
    ReportOut,
    ReportTarget,
    ReportUpdateIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


def get_job_runner() -> jobs.JobRunner:
    """Dependency để test chạy job ngay trong request (app.dependency_overrides)."""
    return jobs.start_in_thread


JobRunnerDep = Annotated[jobs.JobRunner, Depends(get_job_runner)]


@contextmanager
def _translate_errors() -> Iterator[None]:
    """Đổi lỗi nghiệp vụ thành mã HTTP. AuthorizationError đã có trình xử lý chung (403)."""
    try:
        yield
    except service.NotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except service.Conflict as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    except FeedbackRejected as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except LLMNotConfigured as error:
        logger.warning("Nhận xét AI chưa được cấu hình: %s", error)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ lý AI chưa được cấu hình. Hãy báo quản trị viên.",
        ) from error
    except LLMError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Không gọi được mô hình ngôn ngữ lúc này. Hãy thử lại sau.",
        ) from error
    except service.GenerationBlocked as error:
        logger.error("Hàng rào ẩn danh chặn một lần gọi LLM khi viết nhận xét")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.post(
    "/reports",
    response_model=ReportOut | JobOut,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_202_ACCEPTED: {"model": JobOut, "description": "Đã nhận, chạy nền"}},
    summary="Sinh bản nháp: một em / một báo cáo (201), hoặc cả lớp chạy nền (202)",
)
def create_report(
    body: ReportIn,
    response: Response,
    user: CurrentUser,
    session: DbSession,
    provider_factory: ProviderFactoryDep,
    runner: JobRunnerDep,
) -> ReportOut | JobOut:
    with _translate_errors():
        if body.type in STUDENT_TYPES and body.student_id is None:
            job = jobs.start_class_job(session, user, provider_factory, runner, body)
            response.status_code = status.HTTP_202_ACCEPTED
            return service.job_out(job)
        return service.generate(session, user, provider_factory, body)


@router.get(
    "/reports/jobs/{job_id}",
    response_model=JobOut,
    summary="Tiến độ một lần sinh cả lớp",
)
def get_job(job_id: int, user: CurrentUser, session: DbSession) -> JobOut:
    with _translate_errors():
        return service.job_out(jobs.get_job(session, user, job_id))


@router.get(
    "/reports",
    response_model=ReportListOut,
    summary="Danh sách nhận xét của một lớp, hoặc báo cáo lớp / khối",
)
def list_reports(
    target: Annotated[ReportTarget, Query()], user: CurrentUser, session: DbSession
) -> ReportListOut:
    with _translate_errors():
        return service.list_reports(session, user, target)


@router.put(
    "/reports/{report_id}",
    response_model=ReportOut,
    summary="Giáo viên sửa văn bản và/hoặc duyệt",
)
def update_report(
    report_id: int, body: ReportUpdateIn, user: CurrentUser, session: DbSession
) -> ReportOut:
    with _translate_errors():
        return service.update_report(session, user, report_id, body)


@router.get(
    "/reports/{report_id}/export",
    response_class=Response,
    responses={status.HTTP_200_OK: {"content": {"application/pdf": {}}}},
    summary="Xuất PDF bản đã duyệt (bản nháp: 409)",
)
def export_report(
    report_id: int,
    user: CurrentUser,
    session: DbSession,
    file_format: Annotated[Literal["pdf"], Query(alias="format")] = "pdf",
) -> Response:
    with _translate_errors():
        content, name = export.export_pdf(session, user, report_id)
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post(
    "/reports/{report_id}/regenerate",
    response_model=ReportOut,
    summary="Sinh lại bản nháp, có thể kèm góp ý",
)
def regenerate_report(
    report_id: int,
    body: RegenerateIn,
    user: CurrentUser,
    session: DbSession,
    provider_factory: ProviderFactoryDep,
) -> ReportOut:
    with _translate_errors():
        return service.regenerate(session, user, provider_factory, report_id, body.feedback)

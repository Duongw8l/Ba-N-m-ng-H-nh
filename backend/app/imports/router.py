"""Nhập điểm, điểm danh, rèn luyện từ tệp: xem trước rồi xác nhận mới ghi (D-057 đến D-063).

Quyền ghi kiểm bằng authorize_write() TRƯỚC khi đọc nội dung tệp (nguyên tắc 4). Starlette nhận
trọn thân multipart trước khi gọi hàm xử lý, nên giới hạn dung lượng thật phải đặt thêm ở reverse
proxy (Giai đoạn 11); ở đây chỉ chặn khi đọc nội dung.
"""

import json
import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.analytics import repository as analytics_repo
from app.auth.deps import CurrentUser
from app.classes.service import class_exists
from app.core.authorize import authorize_admin, authorize_write
from app.core.db import DbSession
from app.core.enums import ConductPeriod, ImportKind
from app.imports import hooks, mappings, service
from app.imports.parsing import MAX_UPLOAD_BYTES, ImportFileError
from app.imports.schemas import ConfirmOut, MappingTemplateOut, PreviewOut

router = APIRouter(tags=["imports"])


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _parse_mapping(raw: str | None) -> dict[str, str | None] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise _bad_request('Ánh xạ cột phải là JSON dạng {"trường": "tên cột"}.') from None
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in value.items()
    ):
        raise _bad_request('Ánh xạ cột phải là JSON dạng {"trường": "tên cột"}.')
    return value


@router.post(
    "/classes/{class_id}/import/{kind}",
    response_model=PreviewOut,
    summary=(
        "Tải tệp điểm, điểm danh, rèn luyện hoặc danh sách học sinh (roster, chỉ Admin) "
        "và xem trước (chưa ghi dữ liệu)"
    ),
)
def import_preview(
    class_id: int,
    kind: ImportKind,
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="Tệp .xlsx hoặc .csv")],
    subject_id: Annotated[int | None, Form(description="Môn (khi nhập điểm)")] = None,
    semester: Annotated[int | None, Form(ge=1, le=2, description="Học kỳ 1 hoặc 2")] = None,
    period: Annotated[
        ConductPeriod | None, Form(description="Kỳ rèn luyện: hk1, hk2, year")
    ] = None,
    mapping: Annotated[str | None, Form(description='JSON {"trường": "tên cột"}')] = None,
    mapping_name: Annotated[str | None, Form(description="Dùng mẫu ánh xạ đã lưu")] = None,
    save_mapping_as: Annotated[str | None, Form(description="Lưu ánh xạ thành mẫu")] = None,
    header_row: Annotated[int | None, Form(ge=1, le=50, description="Dòng tiêu đề")] = None,
    allow_partial: Annotated[bool, Form(description="Cho phép nhập thiếu đầu điểm")] = False,
) -> PreviewOut:
    # Kiểm hình dạng yêu cầu (tham số bắt buộc theo loại) rồi mới tới quyền; không lộ dữ liệu.
    if kind is ImportKind.ASSESSMENTS and (subject_id is None or semester is None):
        raise _bad_request("Nhập điểm cần subject_id (môn) và semester (học kỳ 1 hoặc 2).")
    if kind is ImportKind.CONDUCT and period is None:
        raise _bad_request("Nhập rèn luyện cần period (hk1, hk2 hoặc year).")

    if kind is ImportKind.ROSTER:
        # Danh sách học sinh: chỉ Admin (D-100). Kiểm quyền trước, rồi mới tới lớp có thật không.
        authorize_admin(user)
        if not class_exists(session, class_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không có lớp này.")
    else:
        authorize_write(
            session,
            user,
            class_id=class_id,
            subject_id=subject_id if kind is ImportKind.ASSESSMENTS else None,
        )

    subject = None
    if kind is ImportKind.ASSESSMENTS:
        subject = next(
            (s for s in analytics_repo.class_subjects(session, class_id) if s.id == subject_id),
            None,
        )
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lớp này không học môn này."
            )

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    request = service.PreviewRequest(
        class_id=class_id,
        kind=kind,
        filename=PurePath(file.filename or "tep").name,  # chỉ tên tệp, bỏ mọi đường dẫn
        data=data,
        subject=subject,
        semester=semester if kind is ImportKind.ASSESSMENTS else None,
        period=period if kind is ImportKind.CONDUCT else None,
        header_row=header_row,
        mapping=_parse_mapping(mapping),
        mapping_name=mapping_name,
        save_mapping_as=save_mapping_as,
        allow_partial=allow_partial and kind is ImportKind.ASSESSMENTS,
    )
    try:
        return service.create_preview(session, user, request)
    except ImportFileError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post(
    "/imports/{job_id}/confirm",
    response_model=ConfirmOut,
    summary="Xác nhận bản xem trước: ghi dữ liệu trong một transaction",
)
def import_confirm(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> ConfirmOut:
    try:
        result, class_id, written = service.confirm_job(session, user, job_id)
    except service.ImportJobNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không có bản xem trước này."
        ) from None
    except service.ImportJobExpired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Bản xem trước đã hết hạn (24 giờ). Hãy tải lại tệp.",
        ) from None
    except service.ImportJobInvalid:
        raise _bad_request(
            "Tệp còn dòng lỗi nên không thể xác nhận. Hãy sửa tệp rồi tải lại."
        ) from None
    except service.ImportConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dữ liệu của lớp đã thay đổi từ lúc xem trước. Hãy tải lại tệp.",
        ) from None
    if written:
        hooks.on_data_changed(class_id)  # sau khi đã commit
    return result


@router.get(
    "/imports/mappings",
    response_model=list[MappingTemplateOut],
    summary="Các mẫu ánh xạ cột đã lưu của tôi",
)
def import_mappings(
    user: CurrentUser, session: DbSession, kind: Annotated[ImportKind | None, Query()] = None
) -> list[MappingTemplateOut]:
    return [
        MappingTemplateOut(name=t.name, kind=t.kind, mapping=t.mapping, header_row=t.header_row)
        for t in mappings.list_templates(session, user.id, kind)
    ]

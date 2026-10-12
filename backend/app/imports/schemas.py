"""Schema phản hồi của các endpoint nhập tệp."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.enums import ConductPeriod, ImportKind, ImportStatus


class MessageOut(BaseModel):
    column: str | None  # tên cột trong tệp (hoặc tên trường nếu chưa ánh xạ)
    message: str


class RowOut(BaseModel):
    line: int  # số dòng trong tệp
    student_code: str
    full_name: str | None  # họ tên trong hệ thống
    status: Literal["ok", "warning", "error"]
    action: Literal["new", "changed", "unchanged"] | None  # None khi dòng lỗi
    values: dict[str, str | None]  # giá trị trong tệp, đã chuẩn hoá
    existing: dict[str, str | None]  # giá trị cũ của các ô sẽ bị ghi đè
    messages: list[MessageOut]


class FieldOut(BaseModel):
    name: str
    label: str
    required: bool
    column: str | None  # cột của tệp đang được ánh xạ vào trường này


class SummaryOut(BaseModel):
    total_rows: int
    error_rows: int
    warning_rows: int
    new_rows: int
    changed_rows: int
    unchanged_rows: int
    records_to_create: int  # số bản ghi trong DB sẽ được tạo
    records_to_update: int  # số bản ghi đã có sẽ bị ghi đè
    records_unchanged: int
    has_changes: bool


class ClassSubjectRef(BaseModel):
    id: int
    name: str


class PreviewOut(BaseModel):
    # None khi thiếu cột bắt buộc: chưa có bản xem trước nào để xác nhận. Có dòng lỗi thì vẫn có
    # job_id nhưng can_confirm là False và xác nhận bị từ chối.
    job_id: uuid.UUID | None
    kind: ImportKind
    class_id: int
    subject: ClassSubjectRef | None
    semester: int | None
    period: ConductPeriod | None
    file_name: str
    header_line: int
    detected_columns: list[str]
    fields: list[FieldOut]
    missing_required: list[str]
    ignored_columns: list[str]
    notes: list[str]
    summary: SummaryOut
    can_confirm: bool
    expires_at: datetime | None
    rows: list[RowOut]
    truncated: bool  # True: chỉ liệt kê một phần dòng (luôn gồm mọi dòng lỗi và cảnh báo)


class ConfirmOut(BaseModel):
    job_id: uuid.UUID
    status: ImportStatus
    created: int
    updated: int
    unchanged: int
    already_confirmed: bool


class MappingTemplateOut(BaseModel):
    name: str
    kind: ImportKind
    mapping: dict[str, str | None]
    header_row: int | None

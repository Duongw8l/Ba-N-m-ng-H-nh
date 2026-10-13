"""Schema request/response của API nhận xét và báo cáo (Giai đoạn 9, D-107).

Phản hồi KHÔNG bao giờ có văn bản vi phạm: bản AI viết chưa đạt kiểm tra có `text` rỗng và
`needs_manual` = true. `check_notes` chỉ là mã vi phạm (xem `checks.MESSAGES_VI`).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ReportJobStatus, ReportScope, ReportStatus, ReportType
from app.reports.permissions import STUDENT_TYPES

Semester = Literal["1", "2", "year"]
MAX_TEXT_CHARS = 5000


class ReportTarget(BaseModel):
    """Báo cáo nào, của lớp, môn, khối nào. Hình dạng hợp lệ phụ thuộc loại (D-102)."""

    type: ReportType
    semester: Semester
    class_id: int | None = None
    # int có giới hạn (không dùng Literal): tham số truy vấn đến dưới dạng chuỗi "11".
    grade_level: int | None = Field(default=None, ge=10, le=12)
    subject_id: int | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.type is ReportType.SUBJECT_COMMENT:
            if self.class_id is None or self.subject_id is None or self.grade_level is not None:
                raise ValueError("Nhận xét môn cần class_id và subject_id, không có grade_level.")
            if self.semester == "year":
                raise ValueError("Nhận xét môn chỉ viết cho học kỳ I hoặc II.")
        elif self.type in STUDENT_TYPES:
            if self.class_id is None or self.subject_id is not None or self.grade_level is not None:
                raise ValueError("Học bạ và phiếu liên lạc cần class_id, không có môn hay khối.")
        elif (self.class_id is None) == (self.grade_level is None) or self.subject_id is not None:
            raise ValueError("Báo cáo cần đúng một trong class_id hoặc grade_level, không có môn.")
        return self


class ReportIn(ReportTarget):
    model_config = ConfigDict(extra="forbid")

    student_id: int | None = None  # có: sinh cho một em ngay; không: cả lớp, chạy nền
    feedback: str | None = Field(default=None, max_length=300)  # góp ý khi sinh lại

    @model_validator(mode="after")
    def _check_student(self) -> Self:
        if self.student_id is not None and self.type not in STUDENT_TYPES:
            raise ValueError("student_id chỉ dùng cho nhận xét học sinh.")
        if self.feedback and self.type in STUDENT_TYPES and self.student_id is None:
            raise ValueError("Góp ý chỉ dùng khi sinh cho một em hoặc một báo cáo.")
        return self


class StudentRefOut(BaseModel):
    id: int
    student_code: str
    full_name: str


class ReportOut(BaseModel):
    id: int
    type: ReportType
    type_label: str
    scope: ReportScope
    semester: Semester
    class_id: int | None
    subject_id: int | None
    target_id: int
    status: ReportStatus
    status_label: str
    text: str  # bản đã duyệt nếu có, ngược lại là bản nháp
    needs_manual: bool  # AI chưa viết được bản đạt kiểm tra: chờ giáo viên tự viết
    check_notes: list[str]  # mã vi phạm của lần sinh cuối (chỉ có ý nghĩa khi needs_manual)
    attempts: int
    model: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    student: StudentRefOut | None = None
    # Cảnh báo kiểm tự động cho văn bản giáo viên sửa (không chặn việc lưu hay duyệt).
    warnings: list[str] = []


class JobOut(BaseModel):
    id: int
    class_id: int
    type: ReportType
    semester: Semester
    subject_id: int | None
    status: ReportJobStatus
    status_label: str
    total: int
    done: int
    needs_manual: int
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class ReportItemOut(BaseModel):
    """Một dòng của danh sách: học sinh (nhận xét) hoặc chính lớp / khối (báo cáo)."""

    student: StudentRefOut | None
    report: ReportOut | None


class ReportListOut(BaseModel):
    items: list[ReportItemOut]
    job: JobOut | None  # lần sinh cả lớp gần nhất đang chạy (hoặc vừa dừng) cho cùng phạm vi


class ReportUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    approve: bool = False

    @model_validator(mode="after")
    def _needs_something(self) -> Self:
        if self.text is None and not self.approve:
            raise ValueError("Cần text hoặc approve.")
        return self


class RegenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str | None = Field(default=None, max_length=300)

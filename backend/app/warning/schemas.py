"""Schema của cảnh báo sớm. Không phụ thuộc analytics/ để analytics.schemas dùng lại được.

Từ ngữ hướng tới giáo viên là "cần hỗ trợ"; cảnh báo chỉ là gợi ý để giáo viên quyết định, không tự
gửi tới học sinh hay phụ huynh (nguyên tắc 6, DESIGN mục 10).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.enums import TeacherStatus

LevelLiteral = Literal["high", "medium", "low"]


class ReasonOut(BaseModel):
    """Một lý do do luật cứng đưa ra, kèm số liệu trong câu."""

    code: str
    level: LevelLiteral
    message: str


class ModelFactorOut(BaseModel):
    """Một trong các đặc trưng đóng góp nhiều nhất vào xác suất của mô hình."""

    feature: str
    label: str
    value: float  # giá trị của học sinh, đúng đơn vị của đặc trưng
    # Mức xác suất giảm khi thay bằng trung vị tập huấn luyện (dương: làm tăng nguy cơ).
    contribution: float
    message: str


class ModelOut(BaseModel):
    version: str
    probability: float  # xác suất "Chưa đạt cả năm" (0 đến 1)
    factors: list[ModelFactorOut]  # ba đặc trưng đóng góp nhiều nhất


class AlertStudentOut(BaseModel):
    id: int
    student_code: str
    full_name: str


class AlertOut(BaseModel):
    id: int
    student: AlertStudentOut
    class_id: int
    class_name: str
    level: LevelLiteral
    risk_score: float | None
    rules: list[ReasonOut]  # theo thứ tự mức cao trước
    model: ModelOut | None
    top_reasons: list[str]  # tối đa 3 câu: lý do của luật trước, rồi yếu tố của mô hình
    teacher_status: TeacherStatus
    created_at: datetime
    as_of: str | None  # ngày dữ liệu mới nhất được dùng


class AlertCountsOut(BaseModel):
    high: int
    medium: int
    low: int


class ClassAlertsOut(BaseModel):
    class_id: int
    class_name: str
    counts: AlertCountsOut
    alerts: list[AlertOut]  # mặc định chỉ mức Cao và Trung bình, mức Cao trước


class SchoolAlertsOut(BaseModel):
    counts: AlertCountsOut  # đếm trên toàn bộ các lớp đã lọc
    alerts: list[AlertOut]


class AlertUpdateIn(BaseModel):
    teacher_status: TeacherStatus


class ProfileAlertOut(BaseModel):
    """Cảnh báo hiện hành của một học sinh, hiện trong hồ sơ (GVCN, BGH)."""

    id: int
    level: LevelLiteral
    risk_score: float | None
    rules: list[ReasonOut]
    model: ModelOut | None
    top_reasons: list[str]
    teacher_status: TeacherStatus
    created_at: datetime
    as_of: str | None

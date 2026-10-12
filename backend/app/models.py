"""Import mọi model để `Base.metadata` có đủ bảng (Alembic và test dùng).

Mỗi module khai báo model của mình; file này là nơi duy nhất liệt kê tất cả.
"""

from app.assistant.models import AiLog
from app.auth.models import User
from app.classes.academic import Assessment, Attendance, ConductResult, ExamRegistration
from app.classes.models import (
    ClassStudent,
    SchoolClass,
    SchoolYear,
    Student,
    Subject,
    TeachingAssignment,
)
from app.core.base import Base
from app.core.models import Setting
from app.rag.models import RegulationChunk
from app.reports.models import Report
from app.warning.models import RiskAlert

__all__ = [
    "AiLog",
    "Assessment",
    "Attendance",
    "Base",
    "ClassStudent",
    "ConductResult",
    "ExamRegistration",
    "RegulationChunk",
    "Report",
    "RiskAlert",
    "SchoolClass",
    "SchoolYear",
    "Setting",
    "Student",
    "Subject",
    "TeachingAssignment",
    "User",
]

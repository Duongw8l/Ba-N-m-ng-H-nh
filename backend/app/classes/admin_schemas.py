"""Schema của API quản trị năm học, lớp, phân công (Admin, D-098, D-099).

Chỉ có số đếm (sĩ số, số môn đã phân công), không có tên hay mã học sinh: Admin không xem dữ liệu
học sinh (D-039).
"""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, StringConstraints, model_validator

from app.core.enums import AssessmentType

SchoolYearName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]
ClassName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class SchoolYearIn(BaseModel):
    name: SchoolYearName  # ví dụ 2026-2027
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates_in_order(self) -> Self:
        if self.start_date >= self.end_date:
            raise ValueError("Ngày bắt đầu phải trước ngày kết thúc.")
        return self


class SchoolYearOut(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date


class TeacherRef(BaseModel):
    id: int
    full_name: str


class TeacherOut(BaseModel):
    id: int
    full_name: str
    email: str
    homeroom_class: str | None  # lớp đang chủ nhiệm; một giáo viên chỉ chủ nhiệm một lớp


class AdminClassOut(BaseModel):
    id: int
    name: str
    grade_level: int
    homeroom_teacher: TeacherRef | None
    student_count: int
    assigned_subject_count: int


class SchoolOut(BaseModel):
    school_year: SchoolYearOut | None  # null khi chưa tạo năm học
    classes: list[AdminClassOut]
    subject_count: int  # tổng số môn trong danh mục


class ClassCreateIn(BaseModel):
    grade_level: Literal[10, 11, 12]
    name: ClassName
    homeroom_teacher_id: int | None = None


class ClassUpdateIn(BaseModel):
    """Chỉ các trường có gửi lên mới đổi; `homeroom_teacher_id: null` là bỏ chủ nhiệm."""

    name: ClassName | None = None
    homeroom_teacher_id: int | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Không có trường nào để đổi.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Tên lớp không được để trống.")
        return self


class AssignmentRow(BaseModel):
    subject_id: int
    subject_name: str
    is_elective: bool
    assessment_type: AssessmentType
    teacher: TeacherRef | None  # null: môn chưa có giáo viên


class ClassAssignmentsOut(BaseModel):
    class_id: int
    class_name: str
    grade_level: int
    subjects: list[AssignmentRow]


class AssignmentIn(BaseModel):
    teacher_id: int


class CopyAssignmentsIn(BaseModel):
    from_class_id: int


class CopiedOut(BaseModel):
    copied: int


class RemoveStudentIn(BaseModel):
    student_code: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
    ]


class DeletedOut(BaseModel):
    detail: str

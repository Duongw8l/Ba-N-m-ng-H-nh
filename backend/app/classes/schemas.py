from pydantic import BaseModel

from app.auth.schemas import UserOut


class ClassRef(BaseModel):
    id: int
    name: str  # ví dụ 10A1
    grade_level: int


class TeachingItem(BaseModel):
    class_id: int
    class_name: str
    grade_level: int
    subject_id: int
    subject_name: str


class AssignmentsResponse(BaseModel):
    user: UserOut
    homeroom_classes: list[ClassRef]  # lớp chủ nhiệm
    teaching: list[TeachingItem]  # lớp-môn được phân công giảng dạy
    grades: list[int]  # khối xem được (chỉ BGH); giáo viên và Admin để trống


# Hai schema riêng, KHÔNG kế thừa nhau và không dùng trường tuỳ chọn: người không được xem thông
# tin phụ huynh phải nhận về danh sách không có các khoá guardian_* (D-044).
class StudentOut(BaseModel):
    id: int
    student_code: str
    full_name: str


class StudentWithGuardianOut(BaseModel):
    id: int
    student_code: str
    full_name: str
    guardian_name: str | None
    guardian_phone: str | None

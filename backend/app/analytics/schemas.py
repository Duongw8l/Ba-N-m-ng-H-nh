"""Schema phản hồi của ba endpoint Analytics.

Điểm là Decimal trong code; khi ra JSON là số thập phân (một chữ số), hiển thị dấu phẩy là việc của
giao diện. Giao diện không được tự tính lại mức hay ngưỡng: chỉ hiển thị những gì máy chủ trả.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

from app.core.enums import AssessmentType, CommentResult

Score = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

# Kỳ xem: học kỳ I, học kỳ II hoặc cả năm.
Period = Literal["1", "2", "year"]


class ClassRefOut(BaseModel):
    id: int
    name: str
    grade_level: int


class SubjectStatOut(BaseModel):
    """Thống kê một môn của lớp (số mô tả để hiển thị, không phải số của Thông tư)."""

    subject_id: int
    name: str
    assessment_type: AssessmentType
    student_count: int  # số học sinh đã có điểm trung bình
    mean: Score | None  # trung bình lớp, làm tròn 1 chữ số
    below_pass: int  # số học sinh có ĐTB dưới ngưỡng đạt (5,0)
    below_fail: int  # số học sinh có ĐTB dưới 3,5
    comment_fail: int  # môn nhận xét: số học sinh Chưa đạt
    incomplete: int  # số học sinh chưa đủ dữ liệu


class AttentionOut(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    absent_sessions: int  # số buổi nghỉ cả năm học
    # absent_over_limit, absent_notice, subject_below_fail, level_fail
    reasons: list[str]


class PromotionCountsOut(BaseModel):
    eligible: int
    not_eligible: int
    unknown: int


class DashboardOut(BaseModel):
    class_info: ClassRefOut
    period: Period
    student_count: int
    # good, fair, pass, fail, incomplete (chưa đủ dữ liệu)
    learning_levels: dict[str, int]
    # good, fair, pass, fail, missing (chưa có dữ liệu)
    conduct_levels: dict[str, int]
    conduct_derived_count: int  # cả năm: số học sinh có rèn luyện được suy ra từ học kỳ II
    absent_notice_students: int  # nghỉ từ ngưỡng nhắc (30) buổi trong cả năm học
    absent_over_limit_students: int  # nghỉ quá số buổi tối đa (45)
    subjects: list[SubjectStatOut]
    attention: list[AttentionOut]
    promotion: PromotionCountsOut | None  # chỉ khi xem cả năm


# --- Bảng điểm một môn ------------------------------------------------------------------------


class SubjectOut(BaseModel):
    id: int
    name: str
    assessment_type: AssessmentType
    periods_per_year: int
    regular_required: int  # số đầu điểm thường xuyên mỗi học kỳ theo số tiết


class ThresholdsOut(BaseModel):
    fail: Score
    passing: Score
    fair: Score
    good: Score


class ScoreRowOut(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    tx: list[Score]  # các đầu điểm thường xuyên đã có, theo thứ tự
    tx_missing: int  # số đầu điểm thường xuyên còn thiếu
    midterm: Score | None
    final: Score | None
    average: Score | None  # ĐTBmhk của học kỳ đang xem (tạm tính nếu complete = false)
    comment_result: CommentResult | None  # môn nhận xét
    complete: bool
    average_semester1: Score | None
    average_semester2: Score | None
    year_average: Score | None  # ĐTBmcn, khi đủ hai học kỳ


class DistributionOut(BaseModel):
    below_fail: int  # dưới 3,5
    fail_to_pass: int  # từ 3,5 đến dưới 5,0
    pass_to_fair: int  # từ 5,0 đến dưới 6,5
    fair_to_good: int  # từ 6,5 đến dưới 8,0
    at_least_good: int  # từ 8,0


class SubjectScoresOut(BaseModel):
    class_info: ClassRefOut
    subject: SubjectOut
    semester: int  # 1 hoặc 2
    thresholds: ThresholdsOut
    student_count: int
    mean: Score | None
    distribution: DistributionOut
    incomplete_count: int
    comment_fail_count: int
    rows: list[ScoreRowOut]


# --- Tổng quan khối -----------------------------------------------------------------------------


class ClassOverviewOut(BaseModel):
    class_id: int
    name: str
    student_count: int
    learning_levels: dict[str, int]
    conduct_levels: dict[str, int]
    absent_notice_students: int
    absent_over_limit_students: int
    below_fail_students: int  # số học sinh có ít nhất một môn dưới 3,5


class ClassMeanOut(BaseModel):
    class_id: int
    mean: Score | None


class CommonSubjectOut(BaseModel):
    """Môn mà mọi lớp trong khối đều học, để so sánh trung bình giữa các lớp."""

    subject_id: int
    name: str
    class_means: list[ClassMeanOut]


class GradeOverviewOut(BaseModel):
    grade_level: int
    period: Period
    classes: list[ClassOverviewOut]
    common_subjects: list[CommonSubjectOut]

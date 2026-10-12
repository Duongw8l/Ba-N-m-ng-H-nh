"""Điều kiện lên lớp theo Điều 12 Thông tư 22 (D-051).

Đủ điều kiện khi kết quả học tập VÀ rèn luyện cả năm từ Đạt trở lên, và nghỉ không quá
`max_absent_sessions` buổi (45 vẫn đủ, 46 thì không). Chỉ kết luận quyết định cuối cùng khi đủ dữ
liệu; nhưng nghỉ quá mức hay học tập/rèn luyện đã Chưa đạt thì kết luận "không đủ" ngay.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.analytics.conduct import PeriodConduct
from app.analytics.config import AnalyticsConfig
from app.analytics.learning import LEVELS, LearningResult, SubjectResult
from app.core.enums import AssessmentType, CommentResult, LearningLevel


class PromotionReason(StrEnum):
    LEARNING_FAIL = "learning_fail"  # kết quả học tập cả năm Chưa đạt
    CONDUCT_FAIL = "conduct_fail"  # rèn luyện cả năm Chưa đạt
    ABSENT_OVER_LIMIT = "absent_over_limit"  # nghỉ quá số buổi tối đa
    MISSING_DATA = "missing_data"  # thiếu dữ liệu để kết luận


class RetakeReason(StrEnum):
    BELOW_PASS = "below_pass"  # môn điểm số có ĐTB cả năm dưới 5,0 (DESIGN mục 6.2)
    COMMENT_FAIL = "comment_fail"  # môn nhận xét Chưa đạt cả năm (Điều 14)


@dataclass(frozen=True)
class RetakeSubject:
    subject_id: int
    name: str
    reason: RetakeReason


@dataclass(frozen=True)
class PromotionResult:
    eligible: bool | None  # None: chưa đủ dữ liệu để kết luận
    reasons: tuple[PromotionReason, ...]
    retake_subjects: tuple[RetakeSubject, ...]  # môn có thể phải kiểm tra lại trong hè
    conduct_derived: bool  # rèn luyện cả năm được suy ra từ học kỳ II
    absent_sessions: int


def _below_pass(level: LearningLevel | None) -> bool:
    return level is not None and LEVELS.index(level) < LEVELS.index(LearningLevel.PASS)


def promotion_status(
    *,
    learning: LearningResult,
    year_subjects: Sequence[SubjectResult],
    conduct: PeriodConduct,
    absent_sessions: int,
    config: AnalyticsConfig,
) -> PromotionResult:
    """`learning` và `year_subjects` là kết quả CẢ NĂM của học sinh."""
    reasons: list[PromotionReason] = []
    if _below_pass(learning.level):
        reasons.append(PromotionReason.LEARNING_FAIL)
    if _below_pass(conduct.level):
        reasons.append(PromotionReason.CONDUCT_FAIL)
    if absent_sessions > config.max_absent_sessions:
        reasons.append(PromotionReason.ABSENT_OVER_LIMIT)

    missing = learning.level is None or conduct.level is None
    if reasons:
        eligible: bool | None = False
    elif missing:
        eligible = None
        reasons.append(PromotionReason.MISSING_DATA)
    else:
        eligible = True

    retake: list[RetakeSubject] = []
    for result in year_subjects:
        if (
            result.assessment_type is AssessmentType.SCORE
            and result.average is not None
            and result.average < config.score_threshold_pass
        ):
            retake.append(RetakeSubject(result.subject_id, result.name, RetakeReason.BELOW_PASS))
        elif (
            result.assessment_type is AssessmentType.COMMENT
            and result.comment_result is CommentResult.FAIL
        ):
            retake.append(RetakeSubject(result.subject_id, result.name, RetakeReason.COMMENT_FAIL))

    return PromotionResult(
        eligible=eligible,
        reasons=tuple(reasons),
        retake_subjects=tuple(retake),
        conduct_derived=conduct.derived,
        absent_sessions=absent_sessions,
    )

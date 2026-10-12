"""Kết quả học tập (Tốt / Khá / Đạt / Chưa đạt) theo Điều 9 Thông tư 22 (D-048).

Mọi ngưỡng lấy từ AnalyticsConfig (settings): 3,5 / 5,0 / 6,5 / 8,0 và số môn tối thiểu 6. Điểm
đưa vào là ĐTB môn ĐÃ làm tròn, nên 3,4 dưới 3,5 còn 3,5 thì không.

- Tốt: mọi môn nhận xét Đạt; mọi môn điểm số từ 6,5; ít nhất 6 môn từ 8,0.
- Khá: mọi môn nhận xét Đạt; mọi môn điểm số từ 5,0; ít nhất 6 môn từ 6,5.
- Đạt: nhiều nhất 1 môn nhận xét Chưa đạt; ít nhất 6 môn điểm số từ 5,0; không môn nào dưới 3,5.
- Chưa đạt: các trường hợp còn lại.
- Điều chỉnh: mức bị thấp hơn từ 2 mức trở lên so với Tốt/Khá chỉ do duy nhất 1 môn thì nâng 1 mức.

Kết quả chỉ tính khi MỌI môn đều đủ dữ liệu; thiếu thì level là None (chưa đủ dữ liệu).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.analytics.config import AnalyticsConfig
from app.core.enums import AssessmentType, CommentResult, LearningLevel

# Thứ tự từ thấp lên cao; chỉ số trong danh sách là "bậc" dùng để so sánh mức.
LEVELS = (LearningLevel.FAIL, LearningLevel.PASS, LearningLevel.FAIR, LearningLevel.GOOD)

# Mức Đạt chấp nhận nhiều nhất bấy nhiêu môn nhận xét Chưa đạt; từ số này trở lên là Chưa đạt. Cảnh
# báo sớm (warning/rules.py) dùng lại hằng này để số của Thông tư chỉ nằm trong analytics/.
MAX_FAILED_COMMENTS_FOR_PASS = 1


@dataclass(frozen=True)
class SubjectResult:
    """Kết quả một môn của một học sinh trong một kỳ (học kỳ hoặc cả năm)."""

    subject_id: int
    name: str
    assessment_type: AssessmentType
    average: Decimal | None = None  # môn điểm số: ĐTB đã làm tròn
    comment_result: CommentResult | None = None  # môn nhận xét: Đạt / Chưa đạt
    complete: bool = True  # đủ dữ liệu để xếp loại (xem scores.SemesterScore)


@dataclass(frozen=True)
class LearningResult:
    level: LearningLevel | None  # None: chưa đủ dữ liệu
    base_level: LearningLevel | None  # mức trước khi điều chỉnh
    adjusted: bool  # đã nâng 1 mức theo quy định "chỉ do duy nhất 1 môn"
    incomplete_subjects: tuple[int, ...]  # id các môn chưa đủ dữ liệu
    count_pass: int  # số môn điểm số từ ngưỡng đạt (5,0)
    count_fair: int  # từ 6,5
    count_good: int  # từ 8,0
    below_fail_subjects: tuple[int, ...]  # id môn điểm số dưới 3,5
    below_pass_subjects: tuple[int, ...]  # id môn điểm số dưới 5,0
    failed_comment_subjects: tuple[int, ...]  # id môn nhận xét Chưa đạt


def _rank(results: list[SubjectResult], config: AnalyticsConfig, waived_id: int | None) -> int:
    """Bậc cao nhất (0 đến 3) mà học sinh đạt. `waived_id`: bỏ các điều kiện "mọi môn" và
    "không môn nào dưới 3,5" của riêng môn đó; giá trị của môn đó vẫn được đếm vào các điều kiện
    "ít nhất N môn"."""
    scores = [r for r in results if r.assessment_type is AssessmentType.SCORE]
    all_averages = [r.average for r in scores if r.average is not None]
    others = [r.average for r in scores if r.average is not None and r.subject_id != waived_id]
    failed_comments = sum(
        1
        for r in results
        if r.assessment_type is AssessmentType.COMMENT
        and r.comment_result is CommentResult.FAIL
        and r.subject_id != waived_id
    )
    minimum = config.level_min_subjects
    count_good = sum(1 for v in all_averages if v >= config.score_threshold_good)
    count_fair = sum(1 for v in all_averages if v >= config.score_threshold_fair)
    count_pass = sum(1 for v in all_averages if v >= config.score_threshold_pass)

    if (
        failed_comments == 0
        and all(v >= config.score_threshold_fair for v in others)
        and count_good >= minimum
    ):
        return 3
    if (
        failed_comments == 0
        and all(v >= config.score_threshold_pass for v in others)
        and count_fair >= minimum
    ):
        return 2
    if (
        failed_comments <= MAX_FAILED_COMMENTS_FOR_PASS
        and count_pass >= minimum
        and all(v >= config.score_threshold_fail for v in others)
    ):
        return 1
    return 0


def learning_result(results: list[SubjectResult], config: AnalyticsConfig) -> LearningResult:
    scored = [
        (r.subject_id, r.average)
        for r in results
        if r.assessment_type is AssessmentType.SCORE and r.average is not None
    ]
    incomplete = tuple(r.subject_id for r in results if not r.complete)
    details = {
        "incomplete_subjects": incomplete,
        "below_fail_subjects": tuple(i for i, v in scored if v < config.score_threshold_fail),
        "below_pass_subjects": tuple(i for i, v in scored if v < config.score_threshold_pass),
        "failed_comment_subjects": tuple(
            r.subject_id
            for r in results
            if r.assessment_type is AssessmentType.COMMENT
            and r.comment_result is CommentResult.FAIL
        ),
        "count_pass": sum(1 for _, v in scored if v >= config.score_threshold_pass),
        "count_fair": sum(1 for _, v in scored if v >= config.score_threshold_fair),
        "count_good": sum(1 for _, v in scored if v >= config.score_threshold_good),
    }
    if incomplete or not results:
        return LearningResult(level=None, base_level=None, adjusted=False, **details)

    base = _rank(results, config, waived_id=None)
    level, adjusted = base, False
    if config.level_single_subject_adjustment:
        best = max(_rank(results, config, waived_id=r.subject_id) for r in results)
        if best >= base + 2:
            level, adjusted = base + 1, True
    return LearningResult(
        level=LEVELS[level], base_level=LEVELS[base], adjusted=adjusted, **details
    )

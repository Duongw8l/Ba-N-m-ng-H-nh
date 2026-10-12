"""Điều kiện lên lớp (Điều 12 Thông tư 22, D-051): ca biên 45 và 46 buổi nghỉ và các lý do."""

from collections.abc import Callable

import pytest

from app.analytics.conduct import PeriodConduct
from app.analytics.config import AnalyticsConfig
from app.analytics.learning import SubjectResult, learning_result
from app.analytics.promotion import (
    PromotionReason,
    PromotionResult,
    RetakeReason,
    RetakeSubject,
    promotion_status,
)
from app.core.enums import AssessmentType, CommentResult, ConductLevel

Build = Callable[..., list[SubjectResult]]
GOOD_CONDUCT = PeriodConduct(ConductLevel.GOOD)
GOOD_STUDENT = ["7.0"] * 8  # 8 môn 7,0 -> Khá


def status(
    config: AnalyticsConfig,
    subjects: list[SubjectResult],
    *,
    conduct: PeriodConduct = GOOD_CONDUCT,
    absent: int = 0,
) -> PromotionResult:
    return promotion_status(
        learning=learning_result(subjects, config),
        year_subjects=subjects,
        conduct=conduct,
        absent_sessions=absent,
        config=config,
    )


def test_eligible_with_learning_conduct_and_absences_all_ok(
    config: AnalyticsConfig, results: Build
) -> None:
    result = status(config, results(GOOD_STUDENT, ["pass"]), absent=10)

    assert result.eligible is True
    assert result.reasons == () and result.retake_subjects == ()


@pytest.mark.parametrize(
    ("absent", "eligible"),
    [(0, True), (44, True), (45, True), (46, False), (60, False)],
)
def test_absence_limit_boundary_45_is_allowed_46_is_not(
    config: AnalyticsConfig, results: Build, absent: int, eligible: bool
) -> None:
    result = status(config, results(GOOD_STUDENT, ["pass"]), absent=absent)

    assert result.eligible is eligible
    assert (PromotionReason.ABSENT_OVER_LIMIT in result.reasons) is (not eligible)
    assert result.absent_sessions == absent


def test_absence_limit_comes_from_settings(
    make_config: Callable[..., AnalyticsConfig], results: Build
) -> None:
    strict = make_config(max_absent_sessions=10)
    subjects = results(GOOD_STUDENT, ["pass"])

    assert status(strict, subjects, absent=10).eligible is True
    assert status(strict, subjects, absent=11).eligible is False


def test_pass_level_learning_and_conduct_are_enough(
    config: AnalyticsConfig, results: Build
) -> None:
    # Đạt cả hai (không cần Khá hay Tốt): 8×6,0 -> Đạt; rèn luyện Đạt
    result = status(config, results(["6.0"] * 8), conduct=PeriodConduct(ConductLevel.PASS))

    assert result.eligible is True


def test_failed_learning_blocks_promotion_and_lists_subjects_to_retake(
    config: AnalyticsConfig, results: Build
) -> None:
    # 5×6,0 + 4,9 + 4,0 + 3,0: chỉ 5 môn từ 5,0 -> Chưa đạt. Ba môn dưới 5,0 phải kiểm tra lại.
    subjects = results(["6.0"] * 5 + ["4.9", "4.0", "3.0"])

    result = status(config, subjects)

    assert result.eligible is False
    assert result.reasons == (PromotionReason.LEARNING_FAIL,)
    assert [(r.subject_id, r.reason) for r in result.retake_subjects] == [
        (6, RetakeReason.BELOW_PASS),
        (7, RetakeReason.BELOW_PASS),
        (8, RetakeReason.BELOW_PASS),
    ]


def test_exactly_5_0_does_not_need_a_retake(config: AnalyticsConfig, results: Build) -> None:
    result = status(config, results(["5.0"] * 8 + ["4.9"]))

    assert [r.subject_id for r in result.retake_subjects] == [9]  # chỉ môn 4,9


def test_failed_comment_subject_is_listed_for_retake(
    config: AnalyticsConfig, results: Build
) -> None:
    result = status(config, results(GOOD_STUDENT, ["pass", "fail"]))

    assert result.retake_subjects == (
        RetakeSubject(102, "Môn nhận xét 2", RetakeReason.COMMENT_FAIL),
    )


def test_failed_conduct_blocks_promotion(config: AnalyticsConfig, results: Build) -> None:
    result = status(config, results(GOOD_STUDENT), conduct=PeriodConduct(ConductLevel.FAIL))

    assert (result.eligible, result.reasons) == (False, (PromotionReason.CONDUCT_FAIL,))


def test_several_reasons_are_all_reported(config: AnalyticsConfig, results: Build) -> None:
    subjects = results(["6.0"] * 4 + ["4.0"] * 4)  # chỉ 4 môn từ 5,0 -> Chưa đạt

    result = status(config, subjects, conduct=PeriodConduct(ConductLevel.FAIL), absent=46)

    assert result.eligible is False
    assert result.reasons == (
        PromotionReason.LEARNING_FAIL,
        PromotionReason.CONDUCT_FAIL,
        PromotionReason.ABSENT_OVER_LIMIT,
    )


def test_missing_conduct_means_unknown_unless_something_already_fails(
    config: AnalyticsConfig, results: Build
) -> None:
    unknown = status(config, results(GOOD_STUDENT), conduct=PeriodConduct(None))
    assert (unknown.eligible, unknown.reasons) == (None, (PromotionReason.MISSING_DATA,))

    # Nghỉ quá 45 buổi thì kết luận "không đủ" ngay, dù chưa có rèn luyện
    over = status(config, results(GOOD_STUDENT), conduct=PeriodConduct(None), absent=46)
    assert (over.eligible, over.reasons) == (False, (PromotionReason.ABSENT_OVER_LIMIT,))


def test_incomplete_learning_data_means_unknown(config: AnalyticsConfig, results: Build) -> None:
    result = status(config, results(GOOD_STUDENT, incomplete=[2]))

    assert (result.eligible, result.reasons) == (None, (PromotionReason.MISSING_DATA,))


def test_derived_conduct_is_flagged(config: AnalyticsConfig, results: Build) -> None:
    derived = PeriodConduct(ConductLevel.GOOD, derived=True)

    assert status(config, results(GOOD_STUDENT), conduct=derived).conduct_derived is True
    assert status(config, results(GOOD_STUDENT)).conduct_derived is False


def test_subject_without_average_is_not_in_the_retake_list(config: AnalyticsConfig) -> None:
    subjects = [
        SubjectResult(1, "Toán", AssessmentType.SCORE, average=None, complete=False),
        SubjectResult(2, "Âm nhạc", AssessmentType.COMMENT, comment_result=CommentResult.PASS),
    ]

    assert status(config, subjects).retake_subjects == ()

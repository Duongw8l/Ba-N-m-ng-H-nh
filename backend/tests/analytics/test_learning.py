"""Mức học tập Tốt / Khá / Đạt / Chưa đạt: các ca biên tính tay (Điều 9 Thông tư 22, D-048).

Quy ước trong comment: "N×v" là N môn điểm số có ĐTB bằng v; "CĐ" là môn nhận xét Chưa đạt.
"""

from collections.abc import Callable

from app.analytics.config import AnalyticsConfig
from app.analytics.learning import LearningResult, SubjectResult, learning_result
from app.core.enums import LearningLevel as L

Build = Callable[..., list[SubjectResult]]
MakeConfig = Callable[..., AnalyticsConfig]


def level_of(results: list[SubjectResult], config: AnalyticsConfig) -> L | None:
    return learning_result(results, config).level


# --- Tốt ----------------------------------------------------------------------------------------


def test_good_with_exactly_six_subjects_at_8_and_the_rest_at_6_5(
    config: AnalyticsConfig, results: Build
) -> None:
    # 6×8,0 + 2×6,5, mọi môn nhận xét Đạt: đúng 6 môn từ 8,0 và mọi môn từ 6,5 -> Tốt
    subjects = results(["8.0"] * 6 + ["6.5"] * 2, ["pass", "pass"])

    result = learning_result(subjects, config)

    assert (result.level, result.base_level, result.adjusted) == (L.GOOD, L.GOOD, False)
    assert (result.count_good, result.count_fair, result.count_pass) == (6, 8, 8)


def test_five_subjects_at_8_is_fair_not_good(config: AnalyticsConfig, results: Build) -> None:
    # 5×8,0 + 3×6,5: chỉ 5 môn từ 8,0 nên không Tốt; mọi môn từ 5,0 và 8 môn từ 6,5 -> Khá
    assert level_of(results(["8.0"] * 5 + ["6.5"] * 3), config) is L.FAIR


def test_good_needs_every_score_subject_at_least_6_5(
    config: AnalyticsConfig, results: Build
) -> None:
    # 8×8,0 + 1×6,4: không đủ "mọi môn từ 6,5" nên không Tốt; vẫn là Khá. Môn 6,4 chỉ thấp hơn Tốt
    # đúng 1 mức nên không được nâng (quy định điều chỉnh chỉ áp dụng khi tụt từ 2 mức).
    result = learning_result(results(["8.0"] * 8 + ["6.4"]), config)

    assert (result.level, result.adjusted) == (L.FAIR, False)


def test_one_failed_comment_subject_blocks_good_and_fair(
    config: AnalyticsConfig, make_config: MakeConfig, results: Build
) -> None:
    subjects = results(["8.5"] * 8, ["pass", "fail"])  # 8×8,5, 1 môn nhận xét CĐ

    # Không điều chỉnh: CĐ một môn nhận xét thì tụt xuống Đạt
    assert level_of(subjects, make_config(level_single_subject_adjustment=False)) is L.PASS
    # Có điều chỉnh: chỉ do 1 môn (môn CĐ), bỏ môn đó sẽ là Tốt (hơn 2 mức) -> nâng 1 mức lên Khá
    result = learning_result(subjects, config)
    assert (result.base_level, result.level, result.adjusted) == (L.PASS, L.FAIR, True)


# --- Khá ----------------------------------------------------------------------------------------


def test_fair_at_exactly_5_0_and_exactly_six_subjects_at_6_5(
    config: AnalyticsConfig, results: Build
) -> None:
    # 6×6,5 + 2×5,0: mọi môn từ 5,0 (đúng 5,0 vẫn đạt) và đúng 6 môn từ 6,5 -> Khá
    assert level_of(results(["6.5"] * 6 + ["5.0"] * 2, ["pass"]), config) is L.FAIR


def test_all_at_exactly_6_5_is_fair_because_nothing_reaches_8(
    config: AnalyticsConfig, results: Build
) -> None:
    assert level_of(results(["6.5"] * 8), config) is L.FAIR


def test_five_subjects_at_6_5_is_only_pass(config: AnalyticsConfig, results: Build) -> None:
    # 5×6,5 + 3×5,0: mọi môn từ 5,0 nhưng chỉ 5 môn từ 6,5 -> không Khá; 8 môn từ 5,0 -> Đạt
    assert level_of(results(["6.5"] * 5 + ["5.0"] * 3), config) is L.PASS


def test_score_just_below_5_0_drops_fair_to_pass(config: AnalyticsConfig, results: Build) -> None:
    # 8×6,5 + 1×4,9 -> không Khá (4,9 < 5,0). Đạt: 8 môn từ 5,0, không môn nào dưới 3,5.
    # Chỉ thấp hơn Khá 1 mức nên không điều chỉnh.
    result = learning_result(results(["6.5"] * 8 + ["4.9"]), config)

    assert (result.level, result.adjusted) == (L.PASS, False)
    assert result.below_pass_subjects == (9,)


# --- Đạt và Chưa đạt ---------------------------------------------------------------------------


def test_3_5_is_not_below_the_floor_but_3_4_is(config: AnalyticsConfig, results: Build) -> None:
    # 8×6,0 + 1 môn: 3,5 vẫn Đạt (6 môn từ 5,0 trở lên, không môn nào dưới 3,5)...
    at_floor = learning_result(results(["6.0"] * 8 + ["3.5"]), config)
    assert at_floor.level is L.PASS and at_floor.below_fail_subjects == ()
    # ... còn 3,4 thì dưới 3,5 nên Chưa đạt. Bỏ môn 3,4 cũng chỉ lên Đạt (hơn 1 mức) nên không nâng.
    below = learning_result(results(["6.0"] * 8 + ["3.4"]), config)
    assert (below.level, below.adjusted) == (L.FAIL, False)
    assert below.below_fail_subjects == (9,)


def test_comment_failures_one_is_pass_two_is_fail(config: AnalyticsConfig, results: Build) -> None:
    # 8×6,0 (mọi môn từ 5,0 nhưng không môn nào từ 6,5): thêm 1 môn nhận xét CĐ vẫn Đạt
    assert level_of(results(["6.0"] * 8, ["pass", "fail"]), config) is L.PASS
    # 2 môn nhận xét CĐ -> Chưa đạt (bỏ một môn CĐ cũng chỉ lên Đạt nên không nâng)
    two = learning_result(results(["6.0"] * 8, ["fail", "fail"]), config)
    assert (two.level, two.adjusted) == (L.FAIL, False)
    assert two.failed_comment_subjects == (101, 102)


def test_five_subjects_at_pass_is_fail_and_exactly_six_is_pass(
    config: AnalyticsConfig, results: Build
) -> None:
    # 5×6,0 + 3×4,0: chỉ 5 môn từ 5,0 (cần 6) -> Chưa đạt
    assert level_of(results(["6.0"] * 5 + ["4.0"] * 3), config) is L.FAIL
    # 6×6,0 + 2×4,0: đúng 6 môn từ 5,0, không môn nào dưới 3,5 -> Đạt
    assert level_of(results(["6.0"] * 6 + ["4.0"] * 2), config) is L.PASS


def test_only_comment_subjects_is_fail(config: AnalyticsConfig, results: Build) -> None:
    assert level_of(results([], ["pass", "pass", "pass"]), config) is L.FAIL


# --- Điều chỉnh mức khi chỉ do duy nhất 1 môn ---------------------------------------------------


def test_adjustment_single_weak_subject_two_levels_below_good(
    config: AnalyticsConfig, make_config: MakeConfig, results: Build
) -> None:
    # 8×8,5 + 1×4,0: bình thường là Đạt (môn 4,0 chặn Tốt và Khá). Bỏ riêng môn 4,0 là Tốt, hơn Đạt
    # 2 mức -> nâng 1 mức lên Khá.
    subjects = results(["8.5"] * 8 + ["4.0"])
    result = learning_result(subjects, config)
    assert (result.base_level, result.level, result.adjusted) == (L.PASS, L.FAIR, True)
    off = make_config(level_single_subject_adjustment=False)
    assert level_of(subjects, off) is L.PASS


def test_adjustment_single_subject_below_the_floor_lifts_fail_to_pass(
    config: AnalyticsConfig, results: Build
) -> None:
    # 8×8,5 + 1×3,0: môn 3,0 (< 3,5) kéo xuống Chưa đạt. Bỏ riêng môn đó là Tốt, hơn 3 mức -> nâng
    # 1 mức lên Đạt (không nhảy thẳng lên Tốt).
    result = learning_result(results(["8.5"] * 8 + ["3.0"]), config)

    assert (result.base_level, result.level, result.adjusted) == (L.FAIL, L.PASS, True)


def test_no_adjustment_when_two_subjects_cause_the_drop(
    config: AnalyticsConfig, results: Build
) -> None:
    # 6×8,5 + 4,0 + 4,5: hai môn yếu. Bỏ một môn thì môn kia vẫn chặn Tốt và Khá -> không nâng.
    result = learning_result(results(["8.5"] * 6 + ["4.0", "4.5"]), config)

    assert (result.level, result.adjusted) == (L.PASS, False)


def test_no_adjustment_when_the_drop_is_only_one_level(
    config: AnalyticsConfig, results: Build
) -> None:
    # 8×8,5 + 1×6,2: Khá (6,2 < 6,5 chặn Tốt). Bỏ môn 6,2 là Tốt, chỉ hơn 1 mức -> giữ Khá.
    result = learning_result(results(["8.5"] * 8 + ["6.2"]), config)

    assert (result.level, result.adjusted) == (L.FAIR, False)


def test_adjustment_does_not_apply_when_subject_count_is_the_real_cause(
    config: AnalyticsConfig, results: Build
) -> None:
    # 5×6,0 + 3×4,0: thiếu môn đạt (chỉ 5 môn từ 5,0) chứ không phải do một môn đơn lẻ. Bỏ môn nào
    # cũng không tăng mức, vì giá trị môn bị bỏ vẫn được đếm vào điều kiện "ít nhất 6 môn".
    result = learning_result(results(["6.0"] * 5 + ["4.0"] * 3), config)

    assert (result.level, result.adjusted) == (L.FAIL, False)


# --- Cấu hình và dữ liệu thiếu -----------------------------------------------------------------


def test_thresholds_and_minimum_subjects_come_from_settings(
    make_config: MakeConfig, results: Build
) -> None:
    subjects = results(["8.0"] * 6 + ["6.5"] * 2, ["pass"])
    assert level_of(subjects, make_config()) is L.GOOD
    # Đòi 7 môn từ 8,0 thì không còn Tốt; 8 môn từ 6,5 -> Khá
    assert level_of(subjects, make_config(level_min_subjects=7)) is L.FAIR
    # Ngưỡng "giỏi" nâng lên 9,0 thì không môn nào đạt -> Khá
    assert level_of(subjects, make_config(score_threshold_good=9.0)) is L.FAIR
    # Mốc 6,5 nâng lên 7,0 ("mọi môn" của Tốt): 2 môn 6,5 chặn Tốt; vẫn Khá vì có 6 môn từ 7,0
    assert level_of(subjects, make_config(score_threshold_fair=7.0)) is L.FAIR


def test_incomplete_subject_means_no_level(config: AnalyticsConfig, results: Build) -> None:
    subjects = results(["8.5"] * 8, ["pass"], incomplete=[3])

    result: LearningResult = learning_result(subjects, config)

    assert result.level is None and result.base_level is None
    assert result.incomplete_subjects == (3,)


def test_no_subjects_means_no_level(config: AnalyticsConfig) -> None:
    assert learning_result([], config).level is None

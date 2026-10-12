"""Lớp luật cứng, tính tay từng ngưỡng (D-071). Hàm thuần: không cần DB."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from app.analytics.config import AnalyticsConfig, config_from_values
from app.analytics.learning import MAX_FAILED_COMMENTS_FOR_PASS, LearningResult
from app.analytics.promotion import RetakeReason, RetakeSubject
from app.core.enums import ConductLevel, LearningLevel, RiskLevel
from app.warning.rules import RuleHit, RuleInput, evaluate_rules, score_vn, worst
from tests.analytics.conftest import DEFAULT_SETTINGS

NAMES = {1: "Toán", 2: "Ngữ văn", 3: "Vật lí", 101: "Giáo dục thể chất", 102: "Âm nhạc"}


@pytest.fixture
def config() -> AnalyticsConfig:
    return config_from_values(DEFAULT_SETTINGS)


def learning(level: LearningLevel | None = LearningLevel.FAIR, **overrides: Any) -> LearningResult:
    values: dict[str, Any] = {
        "level": level,
        "base_level": level,
        "adjusted": False,
        "incomplete_subjects": (),
        "count_pass": 7,
        "count_fair": 7,
        "count_good": 0,
        "below_fail_subjects": (),
        "below_pass_subjects": (),
        "failed_comment_subjects": (),
    }
    return LearningResult(**(values | overrides))


def make_input(**overrides: Any) -> RuleInput:
    values: dict[str, Any] = {
        "grade_level": 11,
        "period": "1",
        "absent_sessions": 0,
        "learning": learning(),
        "subject_names": NAMES,
        "subject_averages": {1: Decimal("7.0"), 2: Decimal("7.0"), 3: Decimal("7.0")},
        "conduct_hk1": ConductLevel.GOOD,
    }
    return RuleInput(**(values | overrides))


def codes(hits: list[RuleHit]) -> list[str]:
    return [hit.code for hit in hits]


def test_a_student_with_nothing_wrong_has_no_rule_hit(config: AnalyticsConfig) -> None:
    assert evaluate_rules(make_input(), config) == []


# --- Chuyên cần: 30 / 40 / 45 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("absent", "expected", "level"),
    [
        (0, None, None),
        (29, None, None),  # dưới 30: chưa nhắc
        (30, "absent_notice", RiskLevel.MEDIUM),  # đúng 30: bắt đầu nhắc
        (39, "absent_notice", RiskLevel.MEDIUM),
        (40, "absent_high", RiskLevel.HIGH),  # đúng 40: cảnh báo cao
        (44, "absent_high", RiskLevel.HIGH),
        (45, "absent_high", RiskLevel.HIGH),  # đúng 45: chưa vượt
        (46, "absent_over_limit", RiskLevel.HIGH),  # 46 > 45: vượt
    ],
)
def test_absence_thresholds(
    config: AnalyticsConfig, absent: int, expected: str | None, level: RiskLevel | None
) -> None:
    hits = evaluate_rules(make_input(absent_sessions=absent), config)

    if expected is None:
        assert hits == []
        return
    [hit] = hits  # chỉ MỘT luật nghỉ có mức cao nhất được kích hoạt
    assert (hit.code, hit.level) == (expected, level)
    assert str(absent) in hit.message and hit.data["absent_sessions"] == absent


def test_absence_messages_quote_the_numbers_from_settings(config: AnalyticsConfig) -> None:
    [over] = evaluate_rules(make_input(absent_sessions=46), config)
    [notice] = evaluate_rules(make_input(absent_sessions=38), config)

    assert over.message == "Đã nghỉ 46 buổi trong năm học, vượt mức tối đa 45 buổi."
    assert notice.message == "Đã nghỉ 38 buổi trong năm học (từ 30 buổi trở lên cần nhắc)."


def test_thresholds_come_from_the_settings_not_from_the_code() -> None:
    custom = config_from_values(
        DEFAULT_SETTINGS
        | {"absent_warning_notice": 20, "absent_warning_high": 25, "max_absent_sessions": 30}
    )

    assert codes(evaluate_rules(make_input(absent_sessions=19), custom)) == []
    assert codes(evaluate_rules(make_input(absent_sessions=20), custom)) == ["absent_notice"]
    assert codes(evaluate_rules(make_input(absent_sessions=25), custom)) == ["absent_high"]
    assert codes(evaluate_rules(make_input(absent_sessions=31), custom)) == ["absent_over_limit"]


# --- Học tập ------------------------------------------------------------------------------------


def test_level_fail_is_high_and_only_states_the_fact(config: AnalyticsConfig) -> None:
    hits = evaluate_rules(
        make_input(learning=learning(LearningLevel.FAIL, count_pass=7), period="2"), config
    )

    [hit] = hits
    assert (hit.code, hit.level) == ("level_fail", RiskLevel.HIGH)
    assert hit.message == "Kết quả học tập học kỳ II đang ở mức Chưa đạt."
    # D-048: không khẳng định hệ quả "không thể đạt mức Đạt".
    assert "không thể" not in hit.message


def test_subject_below_fail_lists_the_subjects_with_their_averages(config: AnalyticsConfig) -> None:
    hits = evaluate_rules(
        make_input(
            learning=learning(below_fail_subjects=(1, 3)),
            subject_averages={1: Decimal("3.0"), 2: Decimal("7.0"), 3: Decimal("3.4")},
        ),
        config,
    )

    [hit] = hits
    assert (hit.code, hit.level) == ("subject_below_fail", RiskLevel.MEDIUM)
    assert hit.message == "Có 2 môn ĐTB học kỳ I dưới 3,5: Toán (3,0), Vật lí (3,4)."
    assert hit.data["subjects"] == ["Toán", "Vật lí"] and hit.data["threshold"] == 3.5


@pytest.mark.parametrize(
    ("count_pass", "level", "fires"),
    [
        (5, LearningLevel.PASS, True),  # 5 < 6
        (6, LearningLevel.PASS, False),  # đúng 6: đủ
        (0, None, False),  # chưa đủ dữ liệu thì chưa kết luận
    ],
)
def test_few_subjects_pass(
    config: AnalyticsConfig, count_pass: int, level: LearningLevel | None, fires: bool
) -> None:
    hits = evaluate_rules(make_input(learning=learning(level, count_pass=count_pass)), config)

    assert ("few_subjects_pass" in codes(hits)) is fires
    if fires:
        [hit] = [h for h in hits if h.code == "few_subjects_pass"]
        assert hit.message.startswith("Chỉ có 5 môn điểm số đạt từ 5,0")
        assert "ít nhất 6 môn" in hit.message


def test_two_failed_comment_subjects_but_not_one(config: AnalyticsConfig) -> None:
    one = evaluate_rules(make_input(learning=learning(failed_comment_subjects=(101,))), config)
    two = evaluate_rules(make_input(learning=learning(failed_comment_subjects=(101, 102))), config)

    assert MAX_FAILED_COMMENTS_FOR_PASS == 1  # "từ 2 môn" = hơn mức Đạt chấp nhận
    assert codes(one) == []
    [hit] = two
    assert hit.code == "comment_fail_2plus"
    assert hit.message == ("Có 2 môn nhận xét Chưa đạt trong học kỳ I: Giáo dục thể chất, Âm nhạc.")


# --- Rèn luyện, kiểm tra lại, môn thi tốt nghiệp -----------------------------------------------


@pytest.mark.parametrize(
    ("conduct", "fires"),
    [
        (ConductLevel.FAIL, True),
        (ConductLevel.PASS, False),
        (ConductLevel.GOOD, False),
        (None, False),
    ],
)
def test_conduct_semester_one_fail(
    config: AnalyticsConfig, conduct: ConductLevel | None, fires: bool
) -> None:
    hits = evaluate_rules(make_input(conduct_hk1=conduct), config)

    assert (codes(hits) == ["conduct_hk1_fail"]) is fires
    assert all(hit.level is RiskLevel.MEDIUM for hit in hits)


def test_retake_risk_names_the_subjects_and_why(config: AnalyticsConfig) -> None:
    retake = (
        RetakeSubject(1, "Toán", RetakeReason.BELOW_PASS),
        RetakeSubject(101, "Giáo dục thể chất", RetakeReason.COMMENT_FAIL),
    )

    [hit] = evaluate_rules(make_input(retake_subjects=retake), config)

    assert (hit.code, hit.level) == ("retake_risk", RiskLevel.MEDIUM)
    assert hit.message == (
        "Có thể phải kiểm tra lại trong hè: Toán (ĐTB cả năm dưới 5,0), "
        "Giáo dục thể chất (nhận xét cả năm Chưa đạt)."
    )


def test_grade_12_exam_subjects_below_the_pass_threshold(config: AnalyticsConfig) -> None:
    averages = {1: Decimal("4.9"), 2: Decimal("5.0"), 3: Decimal("3.0")}

    hits = evaluate_rules(
        make_input(grade_level=12, subject_averages=averages, exam_subject_ids=(1, 2)), config
    )

    [hit] = hits
    assert hit.code == "grade12_exam_low"
    # Toán 4,9 thấp (dưới 5,0); Ngữ văn đúng 5,0 thì không; Vật lí 3,0 không đăng ký thi nên bỏ qua.
    assert hit.data["subjects"] == ["Toán"]
    assert "Toán (4,9)" in hit.message and "Ngữ văn" not in hit.message


def test_exam_rule_is_for_grade_12_only(config: AnalyticsConfig) -> None:
    averages = {1: Decimal("3.0")}

    hits = evaluate_rules(
        make_input(grade_level=11, subject_averages=averages, exam_subject_ids=(1,)), config
    )

    assert "grade12_exam_low" not in codes(hits)


# --- Gộp mức ------------------------------------------------------------------------------------


def test_hits_are_ordered_high_first_and_worst_level_wins(config: AnalyticsConfig) -> None:
    hits = evaluate_rules(
        make_input(
            absent_sessions=38,  # Trung bình
            conduct_hk1=ConductLevel.FAIL,  # Trung bình
            learning=learning(LearningLevel.FAIL),  # Cao
        ),
        config,
    )

    assert codes(hits) == ["level_fail", "absent_notice", "conduct_hk1_fail"]
    assert worst([hit.level for hit in hits]) is RiskLevel.HIGH


@pytest.mark.parametrize(
    ("levels", "expected"),
    [
        ([], RiskLevel.LOW),
        ([RiskLevel.LOW], RiskLevel.LOW),
        ([RiskLevel.LOW, RiskLevel.MEDIUM], RiskLevel.MEDIUM),
        ([RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.LOW], RiskLevel.HIGH),
    ],
)
def test_worst_level(levels: list[RiskLevel], expected: RiskLevel) -> None:
    assert worst(levels) is expected


@pytest.mark.parametrize(
    ("value", "text"),
    [("3", "3,0"), ("3.5", "3,5"), ("10", "10,0"), ("0.1", "0,1"), ("4.95", "5,0")],
)
def test_scores_are_written_the_vietnamese_way(value: str, text: str) -> None:
    assert score_vn(Decimal(value)) == text


def test_rule_inputs_are_plain_data(
    make_config: Callable[..., AnalyticsConfig] | None = None,
) -> None:
    """Luật không nhận họ tên, mã học sinh hay thông tin phụ huynh: chỉ số liệu và tên môn."""
    fields = set(RuleInput.__dataclass_fields__)

    assert (
        not {"full_name", "student_code", "guardian_name", "guardian_phone", "date_of_birth"}
        & fields
    )

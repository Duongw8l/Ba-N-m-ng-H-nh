"""Công thức ĐTBmhk và ĐTBmcn với số liệu tính tay (Thông tư 22, D-047)."""

from collections.abc import Callable
from decimal import Decimal as D

import pytest

from app.analytics.config import AnalyticsConfig
from app.analytics.scores import (
    evaluate_semester,
    round_score,
    semester_average_from_scores,
    year_average,
)


def avg(tx: list[str], gk: str | None, ck: str | None, config: AnalyticsConfig) -> D | None:
    return semester_average_from_scores(
        [D(v) for v in tx], None if gk is None else D(gk), None if ck is None else D(ck), config
    )


@pytest.mark.parametrize(
    ("tx", "gk", "ck", "expected"),
    [
        # Ví dụ PROMPTS, môn 105 tiết: (8+7+9+6 + 2×7 + 3×8) / (4+5) = 68/9 = 7,5556 -> 7,6
        (["8", "7", "9", "6"], "7", "8", "7.6"),
        # Đúng nửa: (6+6+6 + 2×7 + 3×6) / (3+5) = 50/8 = 6,25 -> 6,3 (kiểu ngân hàng sẽ ra 6,2)
        (["6", "6", "6"], "7", "6", "6.3"),
        # Môn 35 tiết, 2 đầu điểm: (5+6 + 2×4 + 3×7) / (2+5) = 40/7 = 5,714 -> 5,7
        (["5", "6"], "4", "7", "5.7"),
        # Chưa có đầu điểm thường xuyên nào: (0 + 2×8 + 3×6) / 5 = 34/5 = 6,8
        ([], "8", "6", "6.8"),
        # Toàn điểm 10 và toàn điểm 0 (0,0 không bị coi là "không có điểm")
        (["10", "10", "10", "10"], "10", "10", "10.0"),
        (["0", "0"], "0", "0", "0.0"),
        # Đúng nửa ở mức 3,5: (3,4+3,4+3,5 + 2×3,4 + 3×3,5) / 8 = 27,6/8 = 3,45 -> 3,5
        (["3.4", "3.4", "3.5"], "3.4", "3.5", "3.5"),
        # Ngay dưới nửa: (3,4+3,4+3,4 + 2×3,4 + 3×3,5) / 8 = 27,5/8 = 3,4375 -> 3,4
        (["3.4", "3.4", "3.4"], "3.4", "3.5", "3.4"),
        # Mọi đầu điểm bằng nhau thì trung bình bằng chính giá trị đó, với mọi số đầu điểm
        (["5", "5", "5", "5"], "5", "5", "5.0"),
        (["3.5", "3.5"], "3.5", "3.5", "3.5"),
    ],
)
def test_semester_average_by_hand(
    config: AnalyticsConfig, tx: list[str], gk: str, ck: str, expected: str
) -> None:
    assert avg(tx, gk, ck, config) == D(expected)


def test_missing_midterm_or_final_gives_no_average(config: AnalyticsConfig) -> None:
    assert avg(["8", "9"], None, "7", config) is None
    assert avg(["8", "9"], "7", None, config) is None
    assert avg([], None, None, config) is None


def test_round_score_rounds_half_up_not_to_even() -> None:
    assert round_score(D("6.25")) == D("6.3")
    assert round_score(D("6.35")) == D("6.4")
    assert round_score(D("6.24999")) == D("6.2")
    assert round_score(D("7.55")) == D("7.6")
    assert round_score(D("10")) == D("10.0")


def test_coefficients_come_from_settings_not_from_the_code(
    make_config: Callable[..., AnalyticsConfig],
) -> None:
    # Hệ số giữa kỳ 1 và cuối kỳ 1: (8+7+9+6 + 7 + 8) / (4+2) = 45/6 = 7,5
    equal_weights = make_config(coef_midterm=1, coef_final=1)
    assert avg(["8", "7", "9", "6"], "7", "8", equal_weights) == D("7.5")
    # Hệ số 3 và 4: (8 + 3×7 + 4×8) / (1+3+4) = 61/8 = 7,625 -> 7,6
    heavy = make_config(coef_midterm=3, coef_final=4)
    assert avg(["8"], "7", "8", heavy) == D("7.6")


# --- Đủ đầu điểm thường xuyên theo số tiết ---------------------------------------------------


@pytest.mark.parametrize(
    ("periods", "tx_count", "required", "complete"),
    [
        (105, 4, 4, True),
        (105, 3, 4, False),  # thiếu 1 đầu điểm thường xuyên
        (70, 3, 3, True),  # đúng 70 tiết vẫn là nhóm 3 lần
        (52, 3, 3, True),
        (35, 2, 2, True),  # đúng 35 tiết vẫn là nhóm 2 lần
        (35, 1, 2, False),
        (35, 5, 2, True),  # nhiều hơn mức yêu cầu vẫn đủ
    ],
)
def test_semester_score_is_complete_only_with_enough_regular_scores(
    config: AnalyticsConfig, periods: int, tx_count: int, required: int, complete: bool
) -> None:
    result = evaluate_semester(D(7) * tx_count, tx_count, D(7), D(7), periods, config)

    assert (result.tx_required, result.complete) == (required, complete)
    assert result.average == D("7.0")  # có đủ giữa kỳ và cuối kỳ nên vẫn có điểm trung bình tạm


def test_semester_score_without_final_is_never_complete(config: AnalyticsConfig) -> None:
    result = evaluate_semester(D(28), 4, D(7), None, 105, config)

    assert result.average is None
    assert result.complete is False


# --- ĐTBmcn --------------------------------------------------------------------------------------


def test_year_average_by_hand(config: AnalyticsConfig) -> None:
    # (6,5 + 2×7,0) / 3 = 20,5/3 = 6,8333 -> 6,8
    assert year_average(D("6.5"), D("7.0"), config) == D("6.8")
    # Học kỳ II cao hơn thì kéo điểm lên nhiều hơn: (5,0 + 2×9,0) / 3 = 23/3 = 7,667 -> 7,7
    assert year_average(D("5.0"), D("9.0"), config) == D("7.7")
    # Hai học kỳ bằng nhau thì bằng chính giá trị đó (với mọi hệ số)
    assert year_average(D("3.5"), D("3.5"), config) == D("3.5")
    assert year_average(D("5.0"), D("5.0"), config) == D("5.0")


def test_year_average_uses_the_rounded_semester_averages(config: AnalyticsConfig) -> None:
    # ĐTBmhkI 6,14 làm tròn thành 6,1 và ĐTBmhkII 6,04 thành 6,0 (D-047). Từ số đã làm tròn:
    # (6,1 + 2×6,0) / 3 = 18,1/3 = 6,0333 -> 6,0. (Nếu dùng số chưa làm tròn sẽ ra 6,1.)
    semester1 = round_score(D("6.14"))
    semester2 = round_score(D("6.04"))

    assert (semester1, semester2) == (D("6.1"), D("6.0"))
    assert year_average(semester1, semester2, config) == D("6.0")


def test_year_average_needs_both_semesters(config: AnalyticsConfig) -> None:
    assert year_average(None, D("7.0"), config) is None
    assert year_average(D("7.0"), None, config) is None


def test_year_coefficient_comes_from_settings(make_config: Callable[..., AnalyticsConfig]) -> None:
    # Hệ số học kỳ II bằng 1: (6,1 + 6,4) / 2 = 6,25 -> 6,3 (làm tròn nửa lên)
    assert year_average(D("6.1"), D("6.4"), make_config(coef_year_semester2=1)) == D("6.3")
    # Hệ số 3: (6,1 + 3×6,4) / 4 = 25,3/4 = 6,325 -> 6,3
    assert year_average(D("6.1"), D("6.4"), make_config(coef_year_semester2=3)) == D("6.3")

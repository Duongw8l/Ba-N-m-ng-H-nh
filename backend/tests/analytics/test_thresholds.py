import pytest

from app.analytics.thresholds import required_regular_count

# Giá trị mặc định của settings.regular_assessment_count (DESIGN mục 5):
# đến 35 tiết: 2 lần; trên 35 đến 70: 3 lần; trên 70: 4 lần.
RULES = [
    {"max_periods": 35, "count": 2},
    {"max_periods": 70, "count": 3},
    {"max_periods": None, "count": 4},
]


@pytest.mark.parametrize(
    ("periods", "expected"),
    [
        (1, 2),
        (35, 2),  # ranh giới: đúng 35 tiết vẫn là nhóm "đến 35"
        (36, 3),
        (52, 3),  # Lịch sử
        (70, 3),  # ranh giới: đúng 70 tiết vẫn là nhóm "đến 70"
        (71, 4),
        (105, 4),  # Ngữ văn, Toán, Ngoại ngữ
    ],
)
def test_required_regular_count_follows_period_boundaries(periods: int, expected: int) -> None:
    assert required_regular_count(periods, RULES) == expected


def test_rule_order_in_settings_does_not_matter() -> None:
    assert required_regular_count(105, list(reversed(RULES))) == 4
    assert required_regular_count(35, list(reversed(RULES))) == 2


def test_no_matching_rule_is_an_error() -> None:
    with pytest.raises(ValueError, match="tiết/năm"):
        required_regular_count(100, [{"max_periods": 35, "count": 2}])

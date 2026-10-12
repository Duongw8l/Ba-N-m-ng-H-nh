"""Điểm trung bình môn theo Thông tư 22: ĐTBmhk (học kỳ) và ĐTBmcn (cả năm).

Đây là nơi duy nhất cài đặt công thức (nguyên tắc 2). Hệ số lấy từ AnalyticsConfig. Làm tròn nửa
lên đến 1 chữ số thập phân; ĐTBmcn tính từ ĐTBmhk ĐÃ làm tròn (D-047), nên con số khớp với sổ điểm.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.analytics.config import AnalyticsConfig

ONE_DECIMAL = Decimal("0.1")
# Hệ số của ĐTBmhk học kỳ I trong ĐTBmcn là 1 (đơn vị); chỉ hệ số học kỳ II nằm trong settings.
YEAR_SEMESTER1_COEF = Decimal(1)


def round_score(value: Decimal) -> Decimal:
    """Làm tròn nửa lên đến 1 chữ số thập phân: 6,25 thành 6,3 (không làm tròn kiểu ngân hàng)."""
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SemesterScore:
    average: Decimal | None  # ĐTBmhk; None nếu thiếu điểm giữa kỳ hoặc cuối kỳ
    tx_count: int  # số đầu điểm thường xuyên đã có
    tx_required: int  # số đầu điểm thường xuyên theo số tiết của môn
    # Có điểm trung bình và đủ số đầu điểm thường xuyên. Chưa đủ thì điểm trung bình (nếu có)
    # chỉ là tạm tính và không dùng để xếp loại.
    complete: bool


def semester_average(
    tx_sum: Decimal,
    tx_count: int,
    midterm: Decimal | None,
    final: Decimal | None,
    config: AnalyticsConfig,
) -> Decimal | None:
    """ĐTBmhk = (Tổng ĐĐGtx + hệ số giữa kỳ × ĐĐGgk + hệ số cuối kỳ × ĐĐGck) /
    (Số ĐĐGtx + hệ số giữa kỳ + hệ số cuối kỳ), với hệ số 2 và 3 thì mẫu số là Số ĐĐGtx + 5."""
    if midterm is None or final is None:
        return None
    numerator = tx_sum + config.coef_midterm * midterm + config.coef_final * final
    denominator = tx_count + config.coef_midterm + config.coef_final
    return round_score(numerator / denominator)


def semester_average_from_scores(
    tx: Sequence[Decimal],
    midterm: Decimal | None,
    final: Decimal | None,
    config: AnalyticsConfig,
) -> Decimal | None:
    return semester_average(sum(tx, Decimal(0)), len(tx), midterm, final, config)


def evaluate_semester(
    tx_sum: Decimal,
    tx_count: int,
    midterm: Decimal | None,
    final: Decimal | None,
    periods_per_year: int,
    config: AnalyticsConfig,
) -> SemesterScore:
    average = semester_average(tx_sum, tx_count, midterm, final, config)
    required = config.required_regular(periods_per_year)
    return SemesterScore(
        average=average,
        tx_count=tx_count,
        tx_required=required,
        complete=average is not None and tx_count >= required,
    )


def year_average(
    semester1: Decimal | None, semester2: Decimal | None, config: AnalyticsConfig
) -> Decimal | None:
    """ĐTBmcn = (ĐTBmhkI + hệ số HK2 × ĐTBmhkII) / (1 + hệ số HK2).

    Với hệ số HK2 bằng 2 thì là (ĐTBmhkI + 2 × ĐTBmhkII) / 3.
    """
    if semester1 is None or semester2 is None:
        return None
    coef = config.coef_year_semester2
    return round_score(
        (YEAR_SEMESTER1_COEF * semester1 + coef * semester2) / (YEAR_SEMESTER1_COEF + coef)
    )

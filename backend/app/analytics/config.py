"""Hệ số và ngưỡng của Thông tư 22, đọc từ bảng `settings` (nguyên tắc 2 của CLAUDE.md).

Mọi hàm trong analytics/ nhận một `AnalyticsConfig` thay vì tự đọc DB hay viết số cứng, nên đổi
hệ số hay ngưỡng trong `settings` là công thức đổi theo, và test không cần DB.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.thresholds import required_regular_count
from app.core.models import Setting


class MissingSettingError(RuntimeError):
    """Bảng `settings` thiếu khoá cần cho Analytics (chưa chạy migration?)."""


@dataclass(frozen=True)
class AnalyticsConfig:
    coef_midterm: Decimal  # hệ số điểm giữa kỳ
    coef_final: Decimal  # hệ số điểm cuối kỳ
    coef_year_semester2: Decimal  # hệ số ĐTBmhk học kỳ II trong ĐTBmcn (học kỳ I hệ số 1)
    score_threshold_fail: Decimal  # dưới mức này là quá thấp (3,5)
    score_threshold_pass: Decimal  # mức đạt (5,0)
    score_threshold_fair: Decimal  # 6,5
    score_threshold_good: Decimal  # 8,0
    level_min_subjects: int  # số môn tối thiểu đạt ngưỡng khi xét mức học tập (6)
    max_absent_sessions: int  # nghỉ quá mức này thì không đủ điều kiện lên lớp (45)
    absent_warning_notice: int  # bắt đầu nhắc (30)
    absent_warning_high: int  # cảnh báo mức cao (40)
    regular_assessment_count: tuple[Mapping[str, Any], ...]  # luật số đầu điểm thường xuyên
    level_single_subject_adjustment: bool  # Điều 9: nâng mức khi chỉ do duy nhất 1 môn

    def required_regular(self, periods_per_year: int) -> int:
        """Số đầu điểm thường xuyên mỗi học kỳ của một môn theo số tiết/năm."""
        return required_regular_count(periods_per_year, self.regular_assessment_count)


DECIMAL_KEYS = (
    "coef_midterm",
    "coef_final",
    "coef_year_semester2",
    "score_threshold_fail",
    "score_threshold_pass",
    "score_threshold_fair",
    "score_threshold_good",
)
INT_KEYS = (
    "level_min_subjects",
    "max_absent_sessions",
    "absent_warning_notice",
    "absent_warning_high",
)
OTHER_KEYS = ("regular_assessment_count", "level_single_subject_adjustment")
REQUIRED_KEYS = (*DECIMAL_KEYS, *INT_KEYS, *OTHER_KEYS)


def config_from_values(values: Mapping[str, Any]) -> AnalyticsConfig:
    """Dựng cấu hình từ các giá trị JSON của `settings`. Số thập phân qua `Decimal(str(v))`."""
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise MissingSettingError(
            f"Bảng settings thiếu khoá: {', '.join(missing)}. Chạy make migrate."
        )
    rules: Sequence[Mapping[str, Any]] = values["regular_assessment_count"]
    return AnalyticsConfig(
        **{key: Decimal(str(values[key])) for key in DECIMAL_KEYS},
        **{key: int(values[key]) for key in INT_KEYS},
        regular_assessment_count=tuple(rules),
        level_single_subject_adjustment=bool(values["level_single_subject_adjustment"]),
    )


def load_config(session: Session) -> AnalyticsConfig:
    """Đọc cấu hình hiện hành từ bảng `settings`."""
    values = {key: value for key, value in session.execute(select(Setting.key, Setting.value))}
    return config_from_values(values)

"""Tra cứu quy tắc từ bảng `settings`.

Chỉ đọc bảng quy tắc (dữ liệu), không phải công thức Thông tư 22: công thức tính điểm, mức học
tập và điều kiện lên lớp được viết ở Giai đoạn 3 trong module này.
"""

from collections.abc import Mapping, Sequence
from typing import Any


def required_regular_count(periods_per_year: int, rules: Sequence[Mapping[str, Any]]) -> int:
    """Số lần đánh giá thường xuyên mỗi học kỳ của một môn, theo số tiết trong năm.

    `rules` là giá trị của khoá `regular_assessment_count` trong `settings`: danh sách
    {"max_periods": số tiết tối đa hoặc None, "count": số lần}. `max_periods` là ngưỡng bao gồm
    (35 tiết vẫn thuộc nhóm "đến 35"); None là nhóm không giới hạn trên.
    """
    ordered = sorted(
        rules, key=lambda rule: (rule["max_periods"] is None, rule["max_periods"] or 0)
    )
    for rule in ordered:
        max_periods = rule["max_periods"]
        if max_periods is None or periods_per_year <= max_periods:
            return int(rule["count"])
    raise ValueError(f"Không có quy tắc nào áp dụng cho {periods_per_year} tiết/năm.")

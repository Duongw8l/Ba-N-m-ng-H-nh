"""Lịch năm học 2026-2027 của dữ liệu giả lập (D-030).

Năm học được mô phỏng đầy đủ hai học kỳ như một năm đã hoàn tất, dù ngày chạy seed có thể mới đầu
năm học. Ngày nghỉ chỉ để mô phỏng, không phải lịch chính thức.
"""

from dataclasses import dataclass
from datetime import date, timedelta

SCHOOL_YEAR_NAME = "2026-2027"
SCHOOL_YEAR_START = date(2026, 9, 5)
SCHOOL_YEAR_END = date(2027, 5, 31)

SEMESTER_1_FIRST_MONDAY = date(2026, 9, 7)
SEMESTER_1_WEEKS = 18
SEMESTER_2_FIRST_MONDAY = date(2027, 1, 18)
SEMESTER_2_WEEKS = 17
# Hai tuần nghỉ Tết trong học kỳ II (thứ Hai của mỗi tuần nghỉ).
HOLIDAY_WEEK_MONDAYS = frozenset({date(2027, 2, 1), date(2027, 2, 8)})


@dataclass(frozen=True)
class SchoolDay:
    day: date
    semester: int


def _weekdays(monday: date) -> list[date]:
    return [monday + timedelta(days=offset) for offset in range(5)]


def school_days() -> list[SchoolDay]:
    """Mọi ngày học (thứ Hai đến thứ Sáu) của cả năm, theo thứ tự thời gian: 175 ngày."""
    days: list[SchoolDay] = []

    for week in range(SEMESTER_1_WEEKS):
        monday = SEMESTER_1_FIRST_MONDAY + timedelta(weeks=week)
        days.extend(SchoolDay(day, 1) for day in _weekdays(monday))

    taught_weeks = 0
    monday = SEMESTER_2_FIRST_MONDAY
    while taught_weeks < SEMESTER_2_WEEKS:
        if monday not in HOLIDAY_WEEK_MONDAYS:
            days.extend(SchoolDay(day, 2) for day in _weekdays(monday))
            taught_weeks += 1
        monday += timedelta(weeks=1)

    return days

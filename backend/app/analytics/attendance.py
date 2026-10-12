"""Tổng hợp số buổi nghỉ (D-028).

Mỗi dòng nghỉ có phép hoặc không phép là 1 buổi; đi muộn không tính là nghỉ.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.core.enums import ABSENT_STATUSES, AttendanceStatus


@dataclass(frozen=True)
class AttendanceSummary:
    excused: int  # nghỉ có phép
    unexcused: int  # nghỉ không phép
    late: int  # đi muộn (không tính là nghỉ)
    absent_total: int  # nghỉ có phép + không phép


@dataclass(frozen=True)
class PeriodAbsence:
    period: str  # tuần: ngày thứ Hai của tuần (YYYY-MM-DD); tháng: YYYY-MM
    excused: int
    unexcused: int
    absent_total: int


def make_summary(excused: int, unexcused: int, late: int) -> AttendanceSummary:
    return AttendanceSummary(excused, unexcused, late, excused + unexcused)


def attendance_summary(rows: Iterable[tuple[date, AttendanceStatus]]) -> AttendanceSummary:
    excused = unexcused = late = 0
    for _day, status in rows:
        if status is AttendanceStatus.ABSENT_EXCUSED:
            excused += 1
        elif status is AttendanceStatus.ABSENT_UNEXCUSED:
            unexcused += 1
        elif status is AttendanceStatus.LATE:
            late += 1
    return make_summary(excused, unexcused, late)


def _bucket(day: date, granularity: Literal["week", "month"]) -> str:
    if granularity == "week":
        return (day - timedelta(days=day.weekday())).isoformat()
    return f"{day.year:04d}-{day.month:02d}"


def absences_by_period(
    rows: Iterable[tuple[date, AttendanceStatus]], granularity: Literal["week", "month"]
) -> list[PeriodAbsence]:
    """Số buổi nghỉ gom theo tuần hoặc tháng, sắp theo thời gian; chỉ liệt kê kỳ có buổi nghỉ."""
    buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for day, status in rows:
        if status in ABSENT_STATUSES:
            slot = 0 if status is AttendanceStatus.ABSENT_EXCUSED else 1
            buckets[_bucket(day, granularity)][slot] += 1
    return [
        PeriodAbsence(period, excused, unexcused, excused + unexcused)
        for period, (excused, unexcused) in sorted(buckets.items())
    ]

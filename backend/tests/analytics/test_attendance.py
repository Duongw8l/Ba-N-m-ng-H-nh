from datetime import date

from app.analytics.attendance import (
    absences_by_month_in_range,
    absences_by_period,
    attendance_summary,
)
from app.core.enums import AttendanceStatus as S

ROWS = [
    (date(2026, 9, 7), S.ABSENT_EXCUSED),  # thứ Hai, tuần bắt đầu 07/09
    (date(2026, 9, 8), S.ABSENT_UNEXCUSED),
    (date(2026, 9, 9), S.LATE),  # muộn: không tính là nghỉ
    (date(2026, 9, 10), S.PRESENT),
    (date(2026, 9, 14), S.ABSENT_EXCUSED),  # thứ Hai tuần sau
    (date(2026, 9, 27), S.ABSENT_EXCUSED),  # Chủ nhật, thuộc tuần bắt đầu thứ Hai 21/09
    (date(2026, 10, 1), S.ABSENT_UNEXCUSED),  # sang tháng 10
]


def test_summary_counts_excused_unexcused_and_total_but_not_late() -> None:
    summary = attendance_summary(ROWS)

    assert (summary.excused, summary.unexcused, summary.late) == (3, 2, 1)
    assert summary.absent_total == 5  # 3 có phép + 2 không phép; muộn và có mặt không tính


def test_summary_of_nothing_is_zero() -> None:
    summary = attendance_summary([])

    assert (summary.excused, summary.unexcused, summary.late, summary.absent_total) == (0, 0, 0, 0)


def test_absences_by_week_start_on_monday_and_skip_weeks_without_absence() -> None:
    weeks = absences_by_period(ROWS, "week")

    assert [(w.period, w.excused, w.unexcused, w.absent_total) for w in weeks] == [
        ("2026-09-07", 1, 1, 2),
        ("2026-09-14", 1, 0, 1),
        ("2026-09-21", 1, 0, 1),  # Chủ nhật 27/09 thuộc tuần của thứ Hai 21/09
        ("2026-09-28", 0, 1, 1),  # thứ Năm 01/10
    ]


def test_absences_by_month() -> None:
    months = absences_by_period(ROWS, "month")

    assert [(m.period, m.excused, m.unexcused, m.absent_total) for m in months] == [
        ("2026-09", 3, 1, 4),
        ("2026-10", 0, 1, 1),
    ]
    assert sum(m.absent_total for m in months) == attendance_summary(ROWS).absent_total


def test_order_of_rows_does_not_matter() -> None:
    assert absences_by_period(list(reversed(ROWS)), "month") == absences_by_period(ROWS, "month")


def months(rows: list[tuple[date, S]], first: date, last: date) -> list[tuple[str, int, int, int]]:
    return [
        (m.period, m.excused, m.unexcused, m.absent_total)
        for m in absences_by_month_in_range(rows, first, last)
    ]


def test_months_in_range_are_all_listed_and_empty_months_are_zero() -> None:
    result = months(ROWS, date(2026, 9, 5), date(2026, 11, 30))

    assert result == [
        ("2026-09", 3, 1, 4),
        ("2026-10", 0, 1, 1),
        ("2026-11", 0, 0, 0),  # tháng không ai nghỉ vẫn có mặt, ghi 0
    ]


def test_months_in_range_cross_the_new_year_and_work_without_any_absence() -> None:
    result = months([], date(2026, 12, 20), date(2027, 2, 10))

    assert result == [("2026-12", 0, 0, 0), ("2027-01", 0, 0, 0), ("2027-02", 0, 0, 0)]


def test_months_in_range_for_a_single_month_and_nothing_else() -> None:
    assert months([], date(2027, 3, 1), date(2027, 3, 31)) == [("2027-03", 0, 0, 0)]


def test_a_month_outside_the_range_is_kept_so_totals_never_lose_an_absence() -> None:
    rows = [(date(2026, 8, 31), S.ABSENT_UNEXCUSED), *ROWS]

    result = months(rows, date(2026, 9, 5), date(2026, 10, 31))

    assert [m[0] for m in result] == ["2026-08", "2026-09", "2026-10"]
    assert sum(m[3] for m in result) == attendance_summary(rows).absent_total == 6

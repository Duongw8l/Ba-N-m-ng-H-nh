from datetime import date

from app.analytics.attendance import absences_by_period, attendance_summary
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

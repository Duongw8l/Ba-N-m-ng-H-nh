"""Phép tính Analytics dành cho trợ lý AI (D-088): số tính tay trên dữ liệu nhỏ, và kiểm chéo bằng
SQL thô trên dữ liệu seed (độc lập với mã Analytics)."""

from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics import service
from app.analytics.config import load_config
from app.analytics.queries import (
    InvalidRange,
    attendance_range,
    build_attendance_range,
    class_summary,
    filter_students,
)
from app.analytics.schemas import Period
from app.analytics.service import ClassResults
from app.core.enums import AttendanceStatus as A

E, U, L = A.ABSENT_EXCUSED, A.ABSENT_UNEXCUSED, A.LATE

CLASS_INFO = repo.ClassInfo(1, "11A2", 11)
STUDENTS = [
    repo.StudentInfo(101, 1, "HS001", "Học Sinh Một"),
    repo.StudentInfo(102, 2, "HS002", "Học Sinh Hai"),
    repo.StudentInfo(103, 3, "HS003", "Học Sinh Ba"),
]


# --- attendance_range: số tính tay --------------------------------------------------------------
# 2027-03-01 là thứ Hai. Trong khoảng 01/03 đến 31/03/2027:
#   em 1: 02/03 nghỉ có phép, 03/03 nghỉ không phép, 10/03 đi muộn -> nghỉ 2 (1 phép, 1 không)
#   em 2: 03/03 nghỉ không phép                                          -> nghỉ 1
#   em 3: 31/03 đi muộn                                                  -> nghỉ 0
# Ngoài khoảng (không tính): em 2 ngày 05/04 nghỉ có phép, em 3 ngày 27/02 nghỉ có phép.
ROWS = [
    (101, date(2027, 3, 2), E),
    (101, date(2027, 3, 3), U),
    (101, date(2027, 3, 10), L),
    (102, date(2027, 3, 3), U),
    (102, date(2027, 4, 5), E),
    (103, date(2027, 2, 27), E),
    (103, date(2027, 3, 31), L),
]
MARCH = (date(2027, 3, 1), date(2027, 3, 31))


def test_attendance_range_totals_by_hand() -> None:
    result = attendance_range(CLASS_INFO, STUDENTS, ROWS, *MARCH, "month", top_n=5)

    assert (result.excused, result.unexcused, result.late) == (1, 2, 2)
    assert result.absent_total == 3
    assert result.absent_students == 2  # em 3 chỉ đi muộn
    assert [
        (a.student.student_code, a.excused, a.unexcused, a.absent_total) for a in result.top_absent
    ] == [
        ("HS001", 1, 1, 2),
        ("HS002", 0, 1, 1),
    ]


def test_attendance_range_groups_absences_by_month_and_week() -> None:
    by_month = attendance_range(CLASS_INFO, STUDENTS, ROWS, *MARCH, "month", 5).by_period
    by_week = attendance_range(CLASS_INFO, STUDENTS, ROWS, *MARCH, "week", 5).by_period

    assert [(p.period, p.excused, p.unexcused, p.absent_total) for p in by_month] == [
        ("2027-03", 1, 2, 3)
    ]
    # Cả ba buổi nghỉ rơi vào tuần bắt đầu thứ Hai 01/03 (đi muộn 10/03 không tính là nghỉ).
    assert [(p.period, p.absent_total) for p in by_week] == [("2027-03-01", 3)]


def test_attendance_range_includes_both_end_days_and_excludes_outside() -> None:
    one_day = attendance_range(
        CLASS_INFO, STUDENTS, ROWS, date(2027, 3, 3), date(2027, 3, 3), "month", 5
    )
    wide = attendance_range(
        CLASS_INFO, STUDENTS, ROWS, date(2027, 2, 1), date(2027, 4, 30), "month", 5
    )

    assert (one_day.excused, one_day.unexcused) == (0, 2)  # em 1 và em 2 cùng nghỉ không phép
    assert wide.absent_total == 5  # thêm 05/04 (em 2) và 27/02 (em 3)
    assert [p.period for p in wide.by_period] == ["2027-02", "2027-03", "2027-04"]


def test_attendance_range_top_n_limits_and_breaks_ties_by_student_code() -> None:
    tied = [(102, date(2027, 3, 2), E), (101, date(2027, 3, 3), U)]  # mỗi em nghỉ 1 buổi

    result = attendance_range(CLASS_INFO, STUDENTS, tied, *MARCH, "month", top_n=1)

    assert [a.student.student_code for a in result.top_absent] == ["HS001"]
    assert result.absent_students == 2  # đếm đủ dù chỉ trả top_n


def test_attendance_range_with_no_rows_is_all_zero() -> None:
    result = attendance_range(CLASS_INFO, STUDENTS, [], *MARCH, "month", 5)

    assert (result.absent_total, result.late, result.absent_students) == (0, 0, 0)
    assert result.by_period == () and result.top_absent == ()


def test_attendance_range_rejects_reversed_dates() -> None:
    with pytest.raises(InvalidRange):
        attendance_range(CLASS_INFO, STUDENTS, ROWS, MARCH[1], MARCH[0], "month", 5)


# --- Trên dữ liệu seed, đối chiếu SQL thô --------------------------------------------------------


@pytest.fixture
def results_of(
    db_session: Session, class_id_of: Callable[[str], int]
) -> Callable[[str, Period], ClassResults]:
    def run(class_name: str, period: Period) -> ClassResults:
        info = repo.get_class(db_session, class_id_of(class_name))
        assert info is not None
        return service.build_class_results(db_session, info, period, load_config(db_session))

    return run


def absences_by_code(db_session: Session, class_id: int) -> dict[str, int]:
    rows = db_session.execute(
        text(
            """
            SELECT s.student_code, count(*)
            FROM attendance a
            JOIN class_students cs ON cs.id = a.class_student_id
            JOIN students s ON s.id = cs.student_id
            WHERE cs.class_id = :class_id
              AND a.status IN ('absent_excused', 'absent_unexcused')
            GROUP BY s.student_code
            """
        ),
        {"class_id": class_id},
    ).all()
    return {code: count for code, count in rows}


@pytest.mark.db
def test_class_summary_matches_raw_sql(
    db_session: Session,
    class_id_of: Callable[[str], int],
    results_of: Callable[[str, Period], ClassResults],
) -> None:
    class_id = class_id_of("11A2")
    per_student = absences_by_code(db_session, class_id)
    students = 40
    expected_mean = (Decimal(sum(per_student.values())) / students).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    summary = class_summary(results_of("11A2", "year"), load_config(db_session))

    assert summary.student_count == students
    assert summary.mean_absent_sessions == expected_mean
    assert summary.absent_notice_students == sum(1 for n in per_student.values() if n >= 30)
    assert summary.absent_over_limit_students == sum(1 for n in per_student.values() if n > 45)
    assert (summary.absence_limits.notice, summary.absence_limits.maximum) == (30, 45)
    assert sum(summary.learning_levels.values()) == students


@pytest.mark.db
def test_filter_by_absence_matches_raw_sql_and_is_sorted(
    db_session: Session,
    class_id_of: Callable[[str], int],
    results_of: Callable[[str, Period], ClassResults],
) -> None:
    per_student = absences_by_code(db_session, class_id_of("11A2"))

    rows = filter_students(results_of("11A2", "year"), min_absent=30)

    assert {r.student.student_code for r in rows} == {c for c, n in per_student.items() if n >= 30}
    assert "HS1102001" in {r.student.student_code for r in rows}  # nhân vật demo: nghỉ 38 buổi
    assert [r.absent_total for r in rows] == sorted((r.absent_total for r in rows), reverse=True)
    assert next(r for r in rows if r.student.student_code == "HS1102001").absent_total == 38


@pytest.mark.db
def test_filter_by_subject_below_finds_the_demo_student_and_respects_subject_scope(
    db_session: Session,
    class_id_of: Callable[[str], int],
    results_of: Callable[[str, Period], ClassResults],
) -> None:
    results = results_of("11A2", "1")
    toan = next(s for s in results.subjects if s.name == "Toán")
    others = frozenset(s.id for s in results.subjects if s.id != toan.id)

    everyone = filter_students(results, subject_below=Decimal("3.5"))
    only_toan = filter_students(
        results, subject_below=Decimal("3.5"), subject_ids=frozenset({toan.id})
    )
    not_toan = filter_students(results, subject_below=Decimal("3.5"), subject_ids=others)

    demo = next(r for r in everyone if r.student.student_code == "HS1102002")
    assert ("Toán", Decimal("3.0")) in demo.low_subjects
    assert all(name == "Toán" for r in only_toan for name, _ in r.low_subjects)
    assert "HS1102002" in {r.student.student_code for r in only_toan}
    assert "HS1102002" not in {r.student.student_code for r in not_toan}
    # Mọi điểm trong kết quả đều dưới ngưỡng, tăng dần.
    for row in everyone:
        values = [v for _n, v in row.low_subjects]
        assert all(v < Decimal("3.5") for v in values) and values == sorted(values)


@pytest.mark.db
def test_filter_conditions_combine_with_and_and_unset_conditions_are_ignored(
    results_of: Callable[[str, Period], ClassResults],
) -> None:
    results = results_of("11A2", "1")

    everyone = filter_students(results)
    both = filter_students(results, min_absent=30, subject_below=Decimal("5.0"))
    absent = {r.student.student_code for r in filter_students(results, min_absent=30)}
    low = {r.student.student_code for r in filter_students(results, subject_below=Decimal("5.0"))}

    assert len(everyone) == 40
    assert {r.student.student_code for r in both} == absent & low


@pytest.mark.db
def test_filter_only_class_student_ids_restricts_the_pool(
    results_of: Callable[[str, Period], ClassResults],
) -> None:
    results = results_of("11A2", "1")
    first_two = frozenset(s.student.class_student_id for s in results.students[:2])

    rows = filter_students(results, only_class_student_ids=first_two)

    assert {r.student.class_student_id for r in rows} == first_two


@pytest.mark.db
def test_build_attendance_range_matches_raw_sql_for_a_month(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    class_id = class_id_of("11A2")
    info = repo.get_class(db_session, class_id)
    assert info is not None
    start, end = date(2027, 3, 1), date(2027, 3, 31)
    expected = db_session.execute(
        text(
            """
            SELECT
              count(*) FILTER (WHERE a.status = 'absent_excused'),
              count(*) FILTER (WHERE a.status = 'absent_unexcused'),
              count(*) FILTER (WHERE a.status = 'late'),
              count(DISTINCT cs.id) FILTER (
                WHERE a.status IN ('absent_excused', 'absent_unexcused')
              )
            FROM attendance a JOIN class_students cs ON cs.id = a.class_student_id
            WHERE cs.class_id = :class_id AND a.date BETWEEN :start AND :end
            """
        ),
        {"class_id": class_id, "start": start, "end": end},
    ).one()

    result = build_attendance_range(db_session, info, start, end, "month", top_n=3)

    assert (result.excused, result.unexcused, result.late, result.absent_students) == tuple(
        expected
    )
    assert result.absent_total == result.excused + result.unexcused
    assert sum(p.absent_total for p in result.by_period) == result.absent_total
    assert len(result.top_absent) <= 3


@pytest.mark.db
def test_build_attendance_range_defaults_to_the_whole_school_year(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    class_id = class_id_of("11A2")
    info = repo.get_class(db_session, class_id)
    assert info is not None

    result = build_attendance_range(db_session, info, None, None, "month", top_n=1)

    assert result.absent_total == sum(absences_by_code(db_session, class_id).values())
    assert (result.start, result.end) == repo.school_year_range(db_session, class_id)
    per_student = absences_by_code(db_session, class_id)
    assert result.top_absent[0].absent_total == max(per_student.values())
    assert per_student[result.top_absent[0].student.student_code] == max(per_student.values())


@pytest.mark.db
def test_build_attendance_range_rejects_reversed_dates(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None

    with pytest.raises(InvalidRange):
        build_attendance_range(
            db_session, info, date(2027, 3, 31), date(2027, 3, 1), "month", top_n=1
        )

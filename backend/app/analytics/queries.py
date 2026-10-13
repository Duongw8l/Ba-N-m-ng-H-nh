"""Các phép tính Analytics dành cho trợ lý AI (Giai đoạn 8, D-088).

Trợ lý chỉ được nói những con số do code tính (nguyên tắc 1), nên ba phép tính mà dashboard chưa
có nằm ở đây, cùng nơi với mọi số liệu khác của Analytics: số buổi nghỉ trung bình của lớp, lọc
học sinh theo điều kiện, và số buổi nghỉ trong một khoảng ngày kèm học sinh nghỉ nhiều nhất. Hệ
số và ngưỡng đọc từ `settings` qua `AnalyticsConfig`; hàm thuần nhận dữ liệu đã nạp nên test bằng
số tính tay.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.attendance import PeriodAbsence, absences_by_period
from app.analytics.config import AnalyticsConfig
from app.analytics.schemas import AbsenceLimitsOut, ClassRefOut, Period
from app.analytics.service import (
    ClassResults,
    _absence_counts,
    _class_ref,
    _conduct_counts,
    _learning_counts,
    _mean,
)
from app.core.enums import ABSENT_STATUSES, AssessmentType, AttendanceStatus, ConductLevel

Granularity = Literal["week", "month"]


# --- Tổng hợp một lớp -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassSummary:
    class_info: ClassRefOut
    period: Period
    student_count: int
    learning_levels: dict[str, int]  # good, fair, pass, fail, incomplete
    conduct_levels: dict[str, int]  # good, fair, pass, fail, missing
    absent_notice_students: int  # nghỉ từ ngưỡng nhắc (settings) trở lên, cả năm học
    absent_over_limit_students: int  # nghỉ quá số buổi tối đa
    mean_absent_sessions: Decimal | None  # trung bình số buổi nghỉ mỗi học sinh, làm tròn 1 chữ số
    absence_limits: AbsenceLimitsOut


def class_summary(results: ClassResults, config: AnalyticsConfig) -> ClassSummary:
    notice, over = _absence_counts(results, config)
    return ClassSummary(
        class_info=_class_ref(results.class_info),
        period=results.period,
        student_count=len(results.students),
        learning_levels=_learning_counts(results),
        conduct_levels=_conduct_counts(results),
        absent_notice_students=notice,
        absent_over_limit_students=over,
        mean_absent_sessions=_mean([Decimal(s.absence.absent_total) for s in results.students]),
        absence_limits=AbsenceLimitsOut(
            notice=config.absent_warning_notice, maximum=config.max_absent_sessions
        ),
    )


# --- Lọc học sinh theo điều kiện ------------------------------------------------------------------


@dataclass(frozen=True)
class StudentFilterRow:
    student: repo.StudentInfo
    absent_total: int  # nghỉ có phép + không phép, cả năm học
    learning_level: ConductLevel | None  # mức học tập của kỳ đang xem (LearningLevel)
    # Các môn điểm số có ĐTB dưới ngưỡng `subject_below` (đã giới hạn theo môn được xem), tăng dần.
    low_subjects: tuple[tuple[str, Decimal], ...]


def filter_students(
    results: ClassResults,
    *,
    min_absent: int | None = None,
    subject_below: Decimal | None = None,
    subject_ids: frozenset[int] | None = None,
    only_class_student_ids: frozenset[int] | None = None,
) -> list[StudentFilterRow]:
    """Học sinh thoả MỌI điều kiện được đặt (điều kiện None thì bỏ qua).

    - `min_absent`: số buổi nghỉ cả năm học từ mức này trở lên.
    - `subject_below`: có ít nhất một môn điểm số với ĐTB (kỳ đang xem) dưới mức này; chỉ xét các
      môn trong `subject_ids` (None: mọi môn). Môn chưa có ĐTB không được coi là dưới mức.
    - `only_class_student_ids`: chỉ xét các học sinh này (để lọc theo mức cảnh báo ở tầng gọi).

    Sắp theo số buổi nghỉ giảm dần, rồi ĐTB thấp nhất tăng dần, rồi mã học sinh.
    """
    rows: list[StudentFilterRow] = []
    for result in results.students:
        if only_class_student_ids is not None and (
            result.student.class_student_id not in only_class_student_ids
        ):
            continue
        absent = result.absence.absent_total
        if min_absent is not None and absent < min_absent:
            continue
        low: list[tuple[str, Decimal]] = []
        if subject_below is not None:
            for subject in result.subjects:
                if subject.assessment_type is not AssessmentType.SCORE or subject.average is None:
                    continue
                if subject_ids is not None and subject.subject_id not in subject_ids:
                    continue
                if subject.average < subject_below:
                    low.append((subject.name, subject.average))
            if not low:
                continue
        low.sort(key=lambda item: (item[1], item[0]))
        rows.append(StudentFilterRow(result.student, absent, result.learning.level, tuple(low)))
    rows.sort(
        key=lambda r: (
            -r.absent_total,
            r.low_subjects[0][1] if r.low_subjects else Decimal(99),
            r.student.student_code,
        )
    )
    return rows


# --- Nghỉ học trong một khoảng ngày ---------------------------------------------------------------


@dataclass(frozen=True)
class AbsentStudent:
    student: repo.StudentInfo
    excused: int
    unexcused: int
    absent_total: int


@dataclass(frozen=True)
class AttendanceRange:
    class_info: ClassRefOut
    start: date
    end: date
    granularity: Granularity
    excused: int  # tổng của cả lớp trong khoảng
    unexcused: int
    late: int
    absent_total: int
    absent_students: int  # số học sinh có ít nhất một buổi nghỉ trong khoảng
    by_period: tuple[PeriodAbsence, ...]  # chỉ liệt kê tuần/tháng có buổi nghỉ
    top_absent: tuple[AbsentStudent, ...]  # nhiều nhất trước, tối đa `top_n`


class InvalidRange(ValueError):
    """Khoảng ngày không hợp lệ (ngày bắt đầu sau ngày kết thúc)."""


def attendance_range(
    class_info: repo.ClassInfo,
    students: Sequence[repo.StudentInfo],
    rows: Iterable[tuple[int, date, AttendanceStatus]],
    start: date,
    end: date,
    granularity: Granularity,
    top_n: int,
) -> AttendanceRange:
    """Hàm thuần: gom các dòng điểm danh (class_student_id, ngày, trạng thái) trong [start, end].

    Nghỉ có phép và không phép mỗi dòng là 1 buổi nghỉ; đi muộn đếm riêng, không tính là nghỉ
    (D-028).
    """
    if start > end:
        raise InvalidRange("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    rows = [r for r in rows if start <= r[1] <= end]
    by_student: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    late = 0
    for class_student_id, _day, status in rows:
        if status is AttendanceStatus.ABSENT_EXCUSED:
            by_student[class_student_id][0] += 1
        elif status is AttendanceStatus.ABSENT_UNEXCUSED:
            by_student[class_student_id][1] += 1
        elif status is AttendanceStatus.LATE:
            late += 1
    excused = sum(v[0] for v in by_student.values())
    unexcused = sum(v[1] for v in by_student.values())

    by_id = {s.class_student_id: s for s in students}
    ranked = sorted(
        (
            AbsentStudent(by_id[cs_id], counts[0], counts[1], counts[0] + counts[1])
            for cs_id, counts in by_student.items()
            if cs_id in by_id and counts[0] + counts[1] > 0
        ),
        key=lambda a: (-a.absent_total, a.student.student_code),
    )
    return AttendanceRange(
        class_info=_class_ref(class_info),
        start=start,
        end=end,
        granularity=granularity,
        excused=excused,
        unexcused=unexcused,
        late=late,
        absent_total=excused + unexcused,
        absent_students=len(ranked),
        by_period=tuple(
            absences_by_period(
                [(day, status) for _cs, day, status in rows if status in ABSENT_STATUSES],
                granularity,
            )
        ),
        top_absent=tuple(ranked[: max(top_n, 0)]),
    )


def build_attendance_range(
    session: Session,
    class_info: repo.ClassInfo,
    start: date | None,
    end: date | None,
    granularity: Granularity,
    top_n: int,
) -> AttendanceRange:
    """Như `attendance_range`, nạp dữ liệu từ DB. Mặc định cả năm học của lớp."""
    year_start, year_end = repo.school_year_range(session, class_info.id)
    first, last = start or year_start, end or year_end
    if first > last:
        raise InvalidRange("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    return attendance_range(
        class_info,
        repo.class_students(session, class_info.id),
        repo.attendance_rows_in_range(session, class_info.id, first, last),
        first,
        last,
        granularity,
        top_n,
    )

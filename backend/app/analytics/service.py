"""Ghép dữ liệu từ DB và các hàm thuần thành kết quả cho lớp, môn và khối.

Mọi con số đi ra từ đây đều do scores.py, learning.py, promotion.py... tính (nguyên tắc 1): code này
chỉ gom dữ liệu, gọi hàm, đếm và định dạng.
"""

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.attendance import AttendanceSummary, absences_by_month_in_range, make_summary
from app.analytics.conduct import PeriodConduct, conduct_for_period, year_comment_result
from app.analytics.config import AnalyticsConfig
from app.analytics.learning import LearningResult, SubjectResult, learning_result
from app.analytics.promotion import PromotionResult, promotion_status
from app.analytics.schemas import (
    AbsenceLimitsOut,
    AttentionOut,
    ClassMeanOut,
    ClassOverviewOut,
    ClassRefOut,
    CommonSubjectOut,
    DashboardOut,
    DistributionOut,
    GradeOverviewOut,
    MonthAbsenceOut,
    Period,
    ProfileAttendanceOut,
    ProfileConductOut,
    ProfileLearningOut,
    ProfilePromotionOut,
    ProfileSemesterOut,
    ProfileStudentOut,
    ProfileSubjectOut,
    PromotionCountsOut,
    RetakeSubjectOut,
    ScoreRowOut,
    StudentProfileFullOut,
    StudentProfileSubjectsOut,
    SubjectOut,
    SubjectScoresOut,
    SubjectStatOut,
    ThresholdsOut,
)
from app.analytics.scores import (
    SemesterScore,
    evaluate_semester,
    round_score,
    year_average,
)
from app.core.enums import (
    AssessmentKind,
    AssessmentType,
    AttendanceStatus,
    CommentResult,
    ConductPeriod,
    LearningLevel,
)
from app.warning.schemas import AlertCountsOut, ProfileAlertOut

CONDUCT_PERIOD = {
    "1": ConductPeriod.HK1,
    "2": ConductPeriod.HK2,
    "year": ConductPeriod.YEAR,
}
# good, fair, pass, fail (thứ tự khai báo của enum)
LEVEL_KEYS = tuple(level.value for level in LearningLevel)


@dataclass(frozen=True)
class StudentResult:
    student: repo.StudentInfo
    subjects: tuple[SubjectResult, ...]  # cùng thứ tự với ClassResults.subjects
    learning: LearningResult
    conduct: PeriodConduct
    absence: AttendanceSummary  # cả năm học
    promotion: PromotionResult | None  # chỉ khi xem cả năm


@dataclass(frozen=True)
class ClassResults:
    class_info: repo.ClassInfo
    period: Period
    subjects: tuple[repo.SubjectInfo, ...]
    students: tuple[StudentResult, ...]


@dataclass(frozen=True)
class _Outcome:
    score: SemesterScore | None  # môn điểm số
    comment: CommentResult | None  # môn nhận xét


def _outcome(
    subject: repo.SubjectInfo, row: repo.SemesterRow | None, config: AnalyticsConfig
) -> _Outcome:
    if subject.assessment_type is AssessmentType.COMMENT:
        return _Outcome(None, None if row is None else row.comment_result)
    if row is None:
        required = config.required_regular(subject.periods_per_year)
        return _Outcome(SemesterScore(None, 0, required, False), None)
    score = evaluate_semester(
        row.tx_sum, row.tx_count, row.midterm, row.final, subject.periods_per_year, config
    )
    return _Outcome(score, None)


def _subject_result(
    subject: repo.SubjectInfo,
    outcomes: dict[int, _Outcome],
    period: Period,
    config: AnalyticsConfig,
) -> SubjectResult:
    if subject.assessment_type is AssessmentType.COMMENT:
        comment = (
            year_comment_result(outcomes[2].comment)
            if period == "year"
            else outcomes[int(period)].comment
        )
        return SubjectResult(
            subject.id,
            subject.name,
            AssessmentType.COMMENT,
            comment_result=comment,
            complete=comment is not None,
        )

    if period == "year":
        first, second = outcomes[1].score, outcomes[2].score
        assert first is not None and second is not None
        average = year_average(first.average, second.average, config)
        complete = first.complete and second.complete and average is not None
    else:
        score = outcomes[int(period)].score
        assert score is not None
        average, complete = score.average, score.complete
    return SubjectResult(
        subject.id, subject.name, AssessmentType.SCORE, average=average, complete=complete
    )


def build_class_results(
    session: Session, class_info: repo.ClassInfo, period: Period, config: AnalyticsConfig
) -> ClassResults:
    subjects = repo.class_subjects(session, class_info.id)
    students = repo.class_students(session, class_info.id)
    rows = {
        (r.class_student_id, r.subject_id, r.semester): r
        for r in repo.semester_rows(session, class_info.id)
    }
    conduct = repo.conduct_by_student(session, class_info.id)
    absence = repo.absence_by_student(session, class_info.id)
    semesters = (1, 2) if period == "year" else (int(period),)
    no_absence = make_summary(0, 0, 0)

    results: list[StudentResult] = []
    for student in students:
        subject_results = [
            _subject_result(
                subject,
                {
                    s: _outcome(
                        subject, rows.get((student.class_student_id, subject.id, s)), config
                    )
                    for s in semesters
                },
                period,
                config,
            )
            for subject in subjects
        ]
        learning = learning_result(subject_results, config)
        period_conduct = conduct_for_period(
            conduct.get(student.class_student_id, {}), CONDUCT_PERIOD[period]
        )
        absent = absence.get(student.class_student_id, no_absence)
        promotion = (
            promotion_status(
                learning=learning,
                year_subjects=subject_results,
                conduct=period_conduct,
                absent_sessions=absent.absent_total,
                config=config,
            )
            if period == "year"
            else None
        )
        results.append(
            StudentResult(
                student, tuple(subject_results), learning, period_conduct, absent, promotion
            )
        )
    return ClassResults(class_info, period, tuple(subjects), tuple(results))


# --- Thống kê chung -------------------------------------------------------------------------------


def _learning_counts(results: ClassResults) -> dict[str, int]:
    counts = Counter(
        "incomplete" if s.learning.level is None else s.learning.level.value
        for s in results.students
    )
    return {key: counts.get(key, 0) for key in (*LEVEL_KEYS, "incomplete")}


def _conduct_counts(results: ClassResults) -> dict[str, int]:
    counts = Counter(
        "missing" if s.conduct.level is None else s.conduct.level.value for s in results.students
    )
    return {key: counts.get(key, 0) for key in (*LEVEL_KEYS, "missing")}


def _mean(values: list[Decimal]) -> Decimal | None:
    return round_score(sum(values, Decimal(0)) / len(values)) if values else None


def subject_stats(results: ClassResults, config: AnalyticsConfig) -> list[SubjectStatOut]:
    stats: list[SubjectStatOut] = []
    for index, subject in enumerate(results.subjects):
        per_student = [s.subjects[index] for s in results.students]
        averages = [r.average for r in per_student if r.average is not None]
        stats.append(
            SubjectStatOut(
                subject_id=subject.id,
                name=subject.name,
                assessment_type=subject.assessment_type,
                student_count=len(averages),
                mean=_mean(averages),
                below_pass=sum(1 for v in averages if v < config.score_threshold_pass),
                below_fail=sum(1 for v in averages if v < config.score_threshold_fail),
                comment_fail=sum(1 for r in per_student if r.comment_result is CommentResult.FAIL),
                incomplete=sum(1 for r in per_student if not r.complete),
            )
        )
    return stats


def _absence_counts(results: ClassResults, config: AnalyticsConfig) -> tuple[int, int]:
    notice = sum(
        1 for s in results.students if s.absence.absent_total >= config.absent_warning_notice
    )
    over = sum(1 for s in results.students if s.absence.absent_total > config.max_absent_sessions)
    return notice, over


def _attention_reasons(s: StudentResult, config: AnalyticsConfig) -> list[str]:
    """Lý do một học sinh cần quan tâm (dùng chung cho dashboard lớp và hồ sơ học sinh)."""
    reasons: list[str] = []
    if s.absence.absent_total > config.max_absent_sessions:
        reasons.append("absent_over_limit")
    elif s.absence.absent_total >= config.absent_warning_notice:
        reasons.append("absent_notice")
    if s.learning.below_fail_subjects:
        reasons.append("subject_below_fail")
    if s.learning.level is LearningLevel.FAIL:
        reasons.append("level_fail")
    return reasons


def _attention(results: ClassResults, config: AnalyticsConfig) -> list[AttentionOut]:
    """Học sinh cần quan tâm, đọc từ kết quả Analytics. Chưa phải cảnh báo sớm (Giai đoạn 6)."""
    attention: list[AttentionOut] = []
    for s in results.students:
        reasons = _attention_reasons(s, config)
        if reasons:
            attention.append(
                AttentionOut(
                    student_id=s.student.student_id,
                    student_code=s.student.student_code,
                    full_name=s.student.full_name,
                    absent_sessions=s.absence.absent_total,
                    reasons=reasons,
                )
            )
    attention.sort(key=lambda a: (-len(a.reasons), -a.absent_sessions, a.student_code))
    return attention


def _class_ref(info: repo.ClassInfo) -> ClassRefOut:
    return ClassRefOut(id=info.id, name=info.name, grade_level=info.grade_level)


# --- Dashboard lớp ------------------------------------------------------------------------------


def build_dashboard(
    session: Session,
    class_info: repo.ClassInfo,
    period: Period,
    config: AnalyticsConfig,
    alert_counts: AlertCountsOut | None = None,
) -> DashboardOut:
    results = build_class_results(session, class_info, period, config)
    notice, over = _absence_counts(results, config)
    promotion = None
    if period == "year":
        statuses = [s.promotion.eligible for s in results.students if s.promotion is not None]
        promotion = PromotionCountsOut(
            eligible=sum(1 for e in statuses if e is True),
            not_eligible=sum(1 for e in statuses if e is False),
            unknown=sum(1 for e in statuses if e is None),
        )
    return DashboardOut(
        class_info=_class_ref(class_info),
        period=period,
        student_count=len(results.students),
        learning_levels=_learning_counts(results),
        conduct_levels=_conduct_counts(results),
        conduct_derived_count=sum(1 for s in results.students if s.conduct.derived),
        absent_notice_students=notice,
        absent_over_limit_students=over,
        subjects=subject_stats(results, config),
        attention=_attention(results, config),
        promotion=promotion,
        absences_by_month=_absences_by_month(
            repo.attendance_days(session, class_info.id),
            *repo.school_year_range(session, class_info.id),
        ),
        absence_limits=_absence_limits(config),
        thresholds=_thresholds(config),
        alert_counts=alert_counts or AlertCountsOut(high=0, medium=0, low=0),
    )


def _absences_by_month(
    rows: list[tuple[date, AttendanceStatus]], first: date, last: date
) -> list[MonthAbsenceOut]:
    return [
        MonthAbsenceOut(
            month=item.period,
            excused=item.excused,
            unexcused=item.unexcused,
            total=item.absent_total,
        )
        for item in absences_by_month_in_range(rows, first, last)
    ]


def _thresholds(config: AnalyticsConfig) -> ThresholdsOut:
    return ThresholdsOut(
        fail=config.score_threshold_fail,
        passing=config.score_threshold_pass,
        fair=config.score_threshold_fair,
        good=config.score_threshold_good,
    )


def _absence_limits(config: AnalyticsConfig) -> AbsenceLimitsOut:
    return AbsenceLimitsOut(notice=config.absent_warning_notice, maximum=config.max_absent_sessions)


# --- Tổng quan khối -----------------------------------------------------------------------------


def build_grade_overview(
    session: Session,
    grade_level: int,
    classes: list[repo.ClassInfo],
    period: Period,
    config: AnalyticsConfig,
) -> GradeOverviewOut:
    per_class = [build_class_results(session, info, period, config) for info in classes]
    overviews: list[ClassOverviewOut] = []
    for results in per_class:
        notice, over = _absence_counts(results, config)
        overviews.append(
            ClassOverviewOut(
                class_id=results.class_info.id,
                name=results.class_info.name,
                student_count=len(results.students),
                learning_levels=_learning_counts(results),
                conduct_levels=_conduct_counts(results),
                absent_notice_students=notice,
                absent_over_limit_students=over,
                below_fail_students=sum(
                    1 for s in results.students if s.learning.below_fail_subjects
                ),
            )
        )

    common_ids = (
        set.intersection(*({s.id for s in r.subjects} for r in per_class)) if per_class else set()
    )
    means: dict[int, list[ClassMeanOut]] = defaultdict(list)
    names: dict[int, str] = {}
    for results in per_class:
        for stat in subject_stats(results, config):
            if stat.subject_id in common_ids and stat.assessment_type is AssessmentType.SCORE:
                names[stat.subject_id] = stat.name
                means[stat.subject_id].append(
                    ClassMeanOut(class_id=results.class_info.id, mean=stat.mean)
                )
    return GradeOverviewOut(
        grade_level=grade_level,
        period=period,
        classes=overviews,
        common_subjects=[
            CommonSubjectOut(subject_id=sid, name=names[sid], class_means=means[sid])
            for sid in sorted(means)
        ],
    )


# --- Bảng điểm một môn ---------------------------------------------------------------------------


@dataclass
class _SemesterRaw:
    tx: list[Decimal]
    midterm: Decimal | None = None
    final: Decimal | None = None
    comment: CommentResult | None = None


def _group_raw(raw: list[repo.RawScore]) -> dict[tuple[int, int], _SemesterRaw]:
    grouped: dict[tuple[int, int], _SemesterRaw] = {}
    for item in raw:
        entry = grouped.setdefault((item.class_student_id, item.semester), _SemesterRaw(tx=[]))
        if item.kind is AssessmentKind.TX and item.score is not None:
            entry.tx.append(item.score)
        elif item.kind is AssessmentKind.GK:
            entry.midterm = item.score
        elif item.kind is AssessmentKind.CK:
            entry.final = item.score
            entry.comment = item.comment_result
    return grouped


def _evaluate_raw(
    raw: _SemesterRaw, periods_per_year: int, config: AnalyticsConfig
) -> SemesterScore:
    return evaluate_semester(
        sum(raw.tx, Decimal(0)), len(raw.tx), raw.midterm, raw.final, periods_per_year, config
    )


def _bucket(value: Decimal, config: AnalyticsConfig) -> str:
    if value < config.score_threshold_fail:
        return "below_fail"
    if value < config.score_threshold_pass:
        return "fail_to_pass"
    if value < config.score_threshold_fair:
        return "pass_to_fair"
    if value < config.score_threshold_good:
        return "fair_to_good"
    return "at_least_good"


def build_subject_scores(
    session: Session,
    class_info: repo.ClassInfo,
    subject: repo.SubjectInfo,
    semester: int,
    config: AnalyticsConfig,
) -> SubjectScoresOut:
    students = repo.class_students(session, class_info.id)
    grouped = _group_raw(repo.raw_subject_scores(session, class_info.id, subject.id))
    is_score = subject.assessment_type is AssessmentType.SCORE
    required = config.required_regular(subject.periods_per_year)

    def evaluate(student: repo.StudentInfo, sem: int) -> SemesterScore:
        raw = grouped.get((student.class_student_id, sem), _SemesterRaw(tx=[]))
        return _evaluate_raw(raw, subject.periods_per_year, config)

    rows: list[ScoreRowOut] = []
    selected_averages: list[Decimal] = []
    distribution: Counter[str] = Counter()
    for student in students:
        raw = grouped.get((student.class_student_id, semester), _SemesterRaw(tx=[]))
        chosen = evaluate(student, semester)
        first, second = evaluate(student, 1), evaluate(student, 2)
        if is_score:
            complete = chosen.complete
            average = chosen.average
            if average is not None:
                selected_averages.append(average)
                distribution[_bucket(average, config)] += 1
        else:
            complete = raw.comment is not None
            average = None
        rows.append(
            ScoreRowOut(
                student_id=student.student_id,
                student_code=student.student_code,
                full_name=student.full_name,
                tx=list(raw.tx) if is_score else [],
                tx_missing=max(0, required - len(raw.tx)) if is_score else 0,
                midterm=raw.midterm if is_score else None,
                final=raw.final if is_score else None,
                average=average,
                comment_result=None if is_score else raw.comment,
                complete=complete,
                average_semester1=first.average if is_score else None,
                average_semester2=second.average if is_score else None,
                year_average=year_average(first.average, second.average, config)
                if is_score
                else None,
            )
        )

    return SubjectScoresOut(
        class_info=_class_ref(class_info),
        subject=SubjectOut(
            id=subject.id,
            name=subject.name,
            assessment_type=subject.assessment_type,
            periods_per_year=subject.periods_per_year,
            regular_required=required,
        ),
        semester=semester,
        thresholds=_thresholds(config),
        student_count=len(rows),
        mean=_mean(selected_averages),
        distribution=DistributionOut(
            below_fail=distribution["below_fail"],
            fail_to_pass=distribution["fail_to_pass"],
            pass_to_fair=distribution["pass_to_fair"],
            fair_to_good=distribution["fair_to_good"],
            at_least_good=distribution["at_least_good"],
        ),
        incomplete_count=sum(1 for r in rows if not r.complete),
        comment_fail_count=sum(1 for r in rows if r.comment_result is CommentResult.FAIL),
        rows=rows,
    )


# --- Hồ sơ học sinh -------------------------------------------------------------------------------


def _profile_subject(
    subject: repo.SubjectInfo,
    class_student_id: int,
    raw: list[repo.RawScore],
    config: AnalyticsConfig,
) -> ProfileSubjectOut:
    """Đầu điểm và ĐTB hai học kỳ của một môn, cùng hàm tính với bảng điểm môn."""
    grouped = _group_raw(raw)
    is_score = subject.assessment_type is AssessmentType.SCORE
    required = config.required_regular(subject.periods_per_year)
    semesters: list[ProfileSemesterOut] = []
    evaluated: dict[int, SemesterScore] = {}
    comments: dict[int, CommentResult | None] = {}
    for semester in (1, 2):
        part = grouped.get((class_student_id, semester), _SemesterRaw(tx=[]))
        score = _evaluate_raw(part, subject.periods_per_year, config)
        evaluated[semester] = score
        comments[semester] = part.comment
        semesters.append(
            ProfileSemesterOut(
                semester=semester,
                tx=list(part.tx) if is_score else [],
                tx_missing=max(0, required - len(part.tx)) if is_score else 0,
                midterm=part.midterm if is_score else None,
                final=part.final if is_score else None,
                average=score.average if is_score else None,
                comment_result=None if is_score else part.comment,
                complete=score.complete if is_score else part.comment is not None,
            )
        )
    return ProfileSubjectOut(
        subject_id=subject.id,
        name=subject.name,
        assessment_type=subject.assessment_type,
        periods_per_year=subject.periods_per_year,
        regular_required=required,
        semesters=semesters,
        year_average=(
            year_average(evaluated[1].average, evaluated[2].average, config) if is_score else None
        ),
        year_comment_result=None if is_score else year_comment_result(comments[2]),
    )


def build_student_profile(
    session: Session,
    class_info: repo.ClassInfo,
    student_id: int,
    period: Period,
    config: AnalyticsConfig,
    *,
    subject_ids: frozenset[int] | None,
    alert_lookup: Callable[[int], ProfileAlertOut | None] | None = None,
) -> StudentProfileFullOut | StudentProfileSubjectsOut | None:
    """Hồ sơ một học sinh; None nếu em không thuộc lớp.

    `subject_ids` là các môn người xem được phép xem (None: mọi môn, tức GVCN và BGH). Người chỉ xem
    một số môn (GVBM) nhận hồ sơ chỉ có các môn đó, không có xếp loại, rèn luyện, chuyên cần, phụ
    huynh. Học tập, rèn luyện, nghỉ, lên lớp lấy từ `build_class_results` (cùng nguồn với dashboard
    lớp nên hai màn hình không bao giờ lệch nhau).
    """
    student = next(
        (s for s in repo.class_students(session, class_info.id) if s.student_id == student_id),
        None,
    )
    if student is None:
        return None
    subjects = repo.class_subjects(session, class_info.id)
    if subject_ids is not None:
        subjects = [s for s in subjects if s.id in subject_ids]
    raw_by_subject = repo.raw_student_scores(session, student.class_student_id)
    profile_subjects = [
        _profile_subject(s, student.class_student_id, raw_by_subject.get(s.id, []), config)
        for s in subjects
    ]
    identity = ProfileStudentOut(
        id=student.student_id, student_code=student.student_code, full_name=student.full_name
    )
    if subject_ids is not None:
        return StudentProfileSubjectsOut(
            class_info=_class_ref(class_info),
            student=identity,
            subjects=profile_subjects,
            thresholds=_thresholds(config),
        )

    results = build_class_results(session, class_info, period, config)
    result = next(r for r in results.students if r.student.student_id == student_id)
    names = {s.id: s.name for s in results.subjects}
    learning = result.learning
    promotion = result.promotion
    first_day, last_day = repo.school_year_range(session, class_info.id)
    guardian_name, guardian_phone = repo.student_guardian(session, student_id)
    return StudentProfileFullOut(
        class_info=_class_ref(class_info),
        period=period,
        student=identity,
        guardian_name=guardian_name,
        guardian_phone=guardian_phone,
        subjects=profile_subjects,
        learning=ProfileLearningOut(
            level=None if learning.level is None else learning.level.value,
            base_level=None if learning.base_level is None else learning.base_level.value,
            adjusted=learning.adjusted,
            incomplete_subjects=[names[i] for i in learning.incomplete_subjects],
            below_fail_subjects=[names[i] for i in learning.below_fail_subjects],
            below_pass_subjects=[names[i] for i in learning.below_pass_subjects],
            failed_comment_subjects=[names[i] for i in learning.failed_comment_subjects],
        ),
        conduct=ProfileConductOut(
            level=None if result.conduct.level is None else result.conduct.level.value,
            derived=result.conduct.derived,
        ),
        attendance=ProfileAttendanceOut(
            excused=result.absence.excused,
            unexcused=result.absence.unexcused,
            late=result.absence.late,
            absent_total=result.absence.absent_total,
            limits=_absence_limits(config),
            by_month=_absences_by_month(
                repo.attendance_days(session, class_info.id, student.class_student_id),
                first_day,
                last_day,
            ),
        ),
        promotion=(
            None
            if promotion is None
            else ProfilePromotionOut(
                eligible=promotion.eligible,
                reasons=[reason.value for reason in promotion.reasons],
                retake_subjects=[
                    RetakeSubjectOut(
                        subject_id=item.subject_id, name=item.name, reason=item.reason.value
                    )
                    for item in promotion.retake_subjects
                ],
            )
        ),
        attention_reasons=_attention_reasons(result, config),
        thresholds=_thresholds(config),
        alert=None if alert_lookup is None else alert_lookup(student.class_student_id),
    )

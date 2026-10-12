"""Ghép dữ liệu từ DB và các hàm thuần thành kết quả cho lớp, môn và khối.

Mọi con số đi ra từ đây đều do scores.py, learning.py, promotion.py... tính (nguyên tắc 1): code này
chỉ gom dữ liệu, gọi hàm, đếm và định dạng.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics.attendance import AttendanceSummary, make_summary
from app.analytics.conduct import PeriodConduct, conduct_for_period, year_comment_result
from app.analytics.config import AnalyticsConfig
from app.analytics.learning import LearningResult, SubjectResult, learning_result
from app.analytics.promotion import PromotionResult, promotion_status
from app.analytics.schemas import (
    AttentionOut,
    ClassMeanOut,
    ClassOverviewOut,
    ClassRefOut,
    CommonSubjectOut,
    DashboardOut,
    DistributionOut,
    GradeOverviewOut,
    Period,
    PromotionCountsOut,
    ScoreRowOut,
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
    CommentResult,
    ConductPeriod,
    LearningLevel,
)

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


def _attention(results: ClassResults, config: AnalyticsConfig) -> list[AttentionOut]:
    """Học sinh cần quan tâm, đọc từ kết quả Analytics. Chưa phải cảnh báo sớm (Giai đoạn 6)."""
    attention: list[AttentionOut] = []
    for s in results.students:
        reasons: list[str] = []
        if s.absence.absent_total > config.max_absent_sessions:
            reasons.append("absent_over_limit")
        elif s.absence.absent_total >= config.absent_warning_notice:
            reasons.append("absent_notice")
        if s.learning.below_fail_subjects:
            reasons.append("subject_below_fail")
        if s.learning.level is LearningLevel.FAIL:
            reasons.append("level_fail")
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
    session: Session, class_info: repo.ClassInfo, period: Period, config: AnalyticsConfig
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
    )


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
        return evaluate_semester(
            sum(raw.tx, Decimal(0)),
            len(raw.tx),
            raw.midterm,
            raw.final,
            subject.periods_per_year,
            config,
        )

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
        thresholds=ThresholdsOut(
            fail=config.score_threshold_fail,
            passing=config.score_threshold_pass,
            fair=config.score_threshold_fair,
            good=config.score_threshold_good,
        ),
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

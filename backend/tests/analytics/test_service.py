"""Service Analytics trên dữ liệu seed: kiểm chéo với tính độc lập từ bảng điểm thô, học sinh biên
và nhân vật demo (D-032), tính nhất quán của các con số tổng hợp."""

from collections import defaultdict
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics import service
from app.analytics.config import AnalyticsConfig, load_config
from app.analytics.promotion import PromotionReason
from app.analytics.schemas import Period
from app.analytics.service import ClassResults, StudentResult
from app.core.enums import LearningLevel as L

pytestmark = pytest.mark.db

PERIODS: tuple[Period, ...] = ("1", "2", "year")


@pytest.fixture
def build(
    db_session: Session, class_id_of: Callable[[str], int]
) -> Callable[[str, Period], ClassResults]:
    def run(class_name: str, period: Period) -> ClassResults:
        info = repo.get_class(db_session, class_id_of(class_name))
        assert info is not None
        return service.build_class_results(db_session, info, period, load_config(db_session))

    return run


def student(results: ClassResults, code: str) -> StudentResult:
    return next(s for s in results.students if s.student.student_code == code)


def subject_of(result: StudentResult, name: str):  # noqa: ANN201
    return next(r for r in result.subjects if r.name == name)


# --- Kiểm chéo với tính độc lập từ bảng điểm thô -------------------------------------------------


def test_semester_averages_match_an_independent_calculation_from_raw_scores(
    db_session: Session, build: Callable[[str, Period], ClassResults]
) -> None:
    """Với cả lớp 10A1, môn Toán, hai học kỳ: tính lại từ từng dòng `assessments` bằng công thức
    (Σtx + 2×gk + 3×ck) / (n + 5) viết thẳng trong test, độc lập với mã Analytics."""
    raw = defaultdict(lambda: {"tx": [], "gk": None, "ck": None})
    rows = db_session.execute(
        text(
            """
            SELECT s.student_code, a.semester, a.kind, a.score
            FROM assessments a
            JOIN class_students cs ON cs.id = a.class_student_id
            JOIN students s ON s.id = cs.student_id
            JOIN classes c ON c.id = cs.class_id
            JOIN subjects j ON j.id = a.subject_id
            WHERE c.name = '10A1' AND j.name = 'Toán'
            """
        )
    ).all()
    for code, semester, kind, score in rows:
        entry = raw[(code, semester)]
        if kind == "tx":
            entry["tx"].append(score)
        else:
            entry[kind] = score

    for period in ("1", "2"):
        results = build("10A1", period)
        assert len(results.students) == 40
        for result in results.students:
            entry = raw[(result.student.student_code, int(period))]
            numerator = sum(entry["tx"]) + 2 * entry["gk"] + 3 * entry["ck"]
            expected = (numerator / (len(entry["tx"]) + 5)).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            assert subject_of(result, "Toán").average == expected, result.student.student_code


def test_year_average_is_computed_from_the_two_rounded_semester_averages(
    build: Callable[[str, Period], ClassResults],
) -> None:
    first, second, year = build("10A1", "1"), build("10A1", "2"), build("10A1", "year")

    for a, b, y in zip(first.students, second.students, year.students, strict=True):
        for index, subject in enumerate(year.subjects):
            if subject.assessment_type.value != "score":
                continue
            s1, s2 = a.subjects[index].average, b.subjects[index].average
            assert s1 is not None and s2 is not None
            expected = ((s1 + 2 * s2) / 3).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            assert y.subjects[index].average == expected, (a.student.student_code, subject.name)


# --- Học sinh biên và nhân vật -----------------------------------------------------------------


@pytest.mark.parametrize("period", PERIODS)
def test_boundary_students_have_exact_toan_averages_for_every_period(
    build: Callable[[str, Period], ClassResults], period: Period
) -> None:
    results = build("12A1", period)

    # Mọi đầu điểm Toán bằng nhau nên ĐTBmhk và ĐTBmcn bằng đúng giá trị đó (với mọi hệ số).
    assert subject_of(student(results, "HS1201004"), "Toán").average == Decimal("3.4")
    assert subject_of(student(results, "HS1201005"), "Toán").average == Decimal("3.5")
    assert subject_of(student(results, "HS1201006"), "Toán").average == Decimal("5.0")


@pytest.mark.parametrize("period", PERIODS)
def test_thresholds_treat_3_4_as_below_and_3_5_and_5_0_as_not_below(
    build: Callable[[str, Period], ClassResults],
    subject_id_of: Callable[[str], int],
    period: Period,
) -> None:
    results = build("12A1", period)
    toan = subject_id_of("Toán")

    just_below = student(results, "HS1201004").learning
    assert just_below.below_fail_subjects == (toan,)
    assert just_below.base_level is L.FAIL  # 3,4 dưới 3,5 chặn mức Đạt

    at_floor = student(results, "HS1201005").learning
    assert toan not in at_floor.below_fail_subjects  # đúng 3,5 thì không dưới 3,5
    assert toan in at_floor.below_pass_subjects  # nhưng dưới 5,0

    at_pass = student(results, "HS1201006").learning
    assert toan not in at_pass.below_fail_subjects
    assert toan not in at_pass.below_pass_subjects  # đúng 5,0 thì không dưới 5,0


def test_single_weak_subject_is_lifted_one_level_by_the_adjustment_rule(
    build: Callable[[str, Period], ClassResults],
) -> None:
    learning = student(build("12A1", "year"), "HS1201004").learning

    # Gốc Chưa đạt vì môn 3,4. Các môn còn lại đủ tốt (bỏ môn này thì từ Khá trở lên) nên mức được
    # nâng đúng 1 mức, lên Đạt (không nhảy thẳng lên mức cao hơn).
    assert learning.base_level is L.FAIL
    assert learning.adjusted is True
    assert learning.level is L.PASS


def test_character_with_toan_3_0_cannot_be_above_pass(
    build: Callable[[str, Period], ClassResults],
) -> None:
    for period in PERIODS:
        result = student(build("11A2", period), "HS1102002")
        assert subject_of(result, "Toán").average == Decimal("3.0")
        assert result.learning.level in (L.FAIL, L.PASS)
        assert result.learning.base_level is L.FAIL


def test_absence_boundary_45_is_eligible_and_46_is_not(
    build: Callable[[str, Period], ClassResults],
) -> None:
    results = build("12A1", "year")
    a44, a45, a46 = (student(results, c) for c in ("HS1201001", "HS1201002", "HS1201003"))

    assert [s.absence.absent_total for s in (a44, a45, a46)] == [44, 45, 46]
    assert a44.promotion is not None and a44.promotion.eligible is True
    assert a45.promotion is not None and a45.promotion.eligible is True
    assert a46.promotion is not None
    assert a46.promotion.eligible is False
    assert a46.promotion.reasons == (PromotionReason.ABSENT_OVER_LIMIT,)


def test_demo_character_an_has_38_absences_over_the_notice_but_under_the_limit(
    build: Callable[[str, Period], ClassResults], config: AnalyticsConfig
) -> None:
    an = student(build("11A2", "year"), "HS1102001")

    assert an.student.full_name == "Trần Minh An"
    assert an.absence.absent_total == 38
    assert config.absent_warning_notice <= 38 <= config.max_absent_sessions


# --- Tính nhất quán -------------------------------------------------------------------------------


@pytest.mark.parametrize("period", PERIODS)
def test_every_student_is_counted_exactly_once_in_the_totals(
    db_session: Session, class_id_of: Callable[[str], int], period: Period
) -> None:
    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None

    dashboard = service.build_dashboard(db_session, info, period, load_config(db_session))

    assert dashboard.student_count == 40
    assert sum(dashboard.learning_levels.values()) == 40
    assert sum(dashboard.conduct_levels.values()) == 40
    assert dashboard.learning_levels["incomplete"] == 0  # seed có đủ đầu điểm
    assert dashboard.absent_notice_students >= dashboard.absent_over_limit_students
    if period == "year":
        assert dashboard.promotion is not None
        assert (
            dashboard.promotion.eligible
            + dashboard.promotion.not_eligible
            + dashboard.promotion.unknown
            == 40
        )
        # Seed không có kết quả rèn luyện "cả năm": cả 40 em được suy ra từ học kỳ II.
        assert dashboard.conduct_derived_count == 40
    else:
        assert dashboard.promotion is None
        assert dashboard.conduct_derived_count == 0


def test_dashboard_attention_lists_the_demo_characters_with_reasons(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None

    dashboard = service.build_dashboard(db_session, info, "1", load_config(db_session))
    by_code = {a.student_code: a for a in dashboard.attention}

    assert "absent_notice" in by_code["HS1102001"].reasons  # An: 38 buổi
    assert "absent_over_limit" not in by_code["HS1102001"].reasons
    assert by_code["HS1102001"].absent_sessions == 38
    assert "subject_below_fail" in by_code["HS1102002"].reasons  # Toán 3,0


def test_subject_stats_count_students_below_the_thresholds(
    build: Callable[[str, Period], ClassResults], config: AnalyticsConfig
) -> None:
    results = build("11A2", "1")
    stats = {s.name: s for s in service.subject_stats(results, config)}

    toan = stats["Toán"]
    assert toan.student_count == 40 and toan.incomplete == 0
    assert toan.below_fail >= 1  # em có Toán 3,0
    assert toan.below_fail <= toan.below_pass <= 40
    assert toan.mean is not None and Decimal(0) <= toan.mean <= Decimal(10)
    assert stats["Giáo dục thể chất"].mean is None  # môn nhận xét không có điểm trung bình

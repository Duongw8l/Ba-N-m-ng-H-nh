"""Số liệu đưa cho LLM (D-103): đúng với Analytics, không có danh tính, không có so sánh với bạn."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics import service as analytics
from app.analytics.config import AnalyticsConfig, load_config
from app.analytics.schemas import Period
from app.core.enums import ReportType
from app.reports import facts
from app.reports.facts import _best_subjects, _subject_summary

pytestmark = pytest.mark.db

AN_CODE = "HS1102001"  # Trần Minh An, lớp 11A2


@pytest.fixture
def config(db_session: Session) -> AnalyticsConfig:
    return load_config(db_session)


@pytest.fixture
def an(
    db_session: Session, class_id_of: Callable[[str], int]
) -> tuple[repo.ClassInfo, repo.StudentInfo]:
    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None
    student = next(s for s in repo.class_students(db_session, info.id) if s.student_code == AN_CODE)
    return info, student


def student_facts(
    session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
    report_type: ReportType,
    period: Period = "1",
    **kwargs: Any,
) -> dict[str, Any] | None:
    info, student = an
    return facts.student_facts(
        session, info, student.student_id, report_type, period, config, **kwargs
    )


# --- Hàm thuần --------------------------------------------------------------------------------


def test_best_subjects_are_the_two_highest_averages_without_below_pass_ones() -> None:
    subjects = [
        {"name": "Toán", "average": 6.7},
        {"name": "Văn", "average": 8.1},
        {"name": "Hóa", "average": 4.0},  # Analytics xếp dưới mức đạt
        {"name": "Lý", "average": 7.4},
        {"name": "Thể dục", "result": "Đạt"},  # môn nhận xét không có điểm
        {"name": "Sử", "average": None, "note": "chưa đủ dữ liệu"},
    ]
    assert _best_subjects(subjects, excluded=["Hóa"]) == ["Văn", "Lý"]
    assert _best_subjects(subjects, excluded=[]) == ["Văn", "Lý"]
    assert _best_subjects([], excluded=[]) == []


def test_best_subjects_break_ties_by_name_so_the_choice_is_stable() -> None:
    subjects = [{"name": n, "average": 8.0} for n in ("Sinh", "Anh", "Toán")]
    assert _best_subjects(subjects, excluded=[]) == ["Anh", "Sinh"]


def test_subject_summary_picks_the_semester_or_the_year() -> None:
    subject = {
        "name": "Toán",
        "assessment_type": "score",
        "year_average": 7.1,
        "year_comment_result": None,
        "semesters": [
            {"semester": 1, "average": 6.8, "comment_result": None},
            {"semester": 2, "average": 7.4, "comment_result": None},
        ],
    }
    assert _subject_summary(subject, "1") == {"name": "Toán", "average": 6.8}
    assert _subject_summary(subject, "2") == {"name": "Toán", "average": 7.4}
    assert _subject_summary(subject, "year") == {"name": "Toán", "average": 7.1}


def test_subject_summary_reports_pass_fail_for_comment_subjects_and_missing_data() -> None:
    comment = {
        "name": "Thể dục",
        "assessment_type": "comment",
        "year_average": None,
        "year_comment_result": "fail",
        "semesters": [{"semester": 1, "average": None, "comment_result": "pass"}],
    }
    assert _subject_summary(comment, "1") == {"name": "Thể dục", "result": "Đạt"}
    assert _subject_summary(comment, "year") == {"name": "Thể dục", "result": "Chưa đạt"}
    empty = {
        "name": "Sử",
        "assessment_type": "score",
        "year_average": None,
        "year_comment_result": None,
        "semesters": [{"semester": 1, "average": None, "comment_result": None}],
    }
    assert _subject_summary(empty, "1") == {
        "name": "Sử",
        "average": None,
        "note": "chưa đủ dữ liệu",
    }


# --- Học bạ và phiếu liên lạc -----------------------------------------------------------------


@pytest.mark.parametrize("report_type", [ReportType.SCHOOL_RECORD, ReportType.CONTACT_SLIP])
def test_student_facts_match_the_analytics_profile(
    db_session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
    report_type: ReportType,
) -> None:
    info, student = an
    result = student_facts(db_session, config, an, report_type)
    profile = analytics.build_student_profile(
        db_session, info, student.student_id, "1", config, subject_ids=None
    )
    assert result is not None and profile is not None and profile.scope == "full"

    assert result["period"] == "học kỳ I"
    attendance = result["attendance_since_start_of_year"]
    assert attendance["absent_total"] == profile.attendance.absent_total
    assert attendance["absent_excused"] == profile.attendance.excused
    assert attendance["absent_unexcused"] == profile.attendance.unexcused
    assert attendance["maximum_allowed"] == config.max_absent_sessions  # từ settings, không cứng
    assert attendance["warning_from"] == config.absent_warning_notice

    averages = {s["name"]: s["average"] for s in result["subjects"] if "average" in s}
    for subject in profile.subjects:
        if subject.assessment_type.value == "score":
            semester = next(s for s in subject.semesters if s.semester == 1)
            expected = None if semester.average is None else float(semester.average)
            assert averages[subject.name] == expected
    assert len(result["best_subjects"]) <= 2
    assert all(name in averages for name in result["best_subjects"])


def test_student_facts_have_no_identity_guardian_alert_or_promotion(
    db_session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    _info, student = an
    guardian_name, guardian_phone = repo.student_guardian(db_session, student.student_id)
    assert guardian_name and guardian_phone  # seed có thông tin phụ huynh để so
    for report_type in (ReportType.SCHOOL_RECORD, ReportType.CONTACT_SLIP):
        result = student_facts(db_session, config, an, report_type, "year")
        assert result is not None
        dumped = json.dumps(result, ensure_ascii=False)
        for secret in (student.full_name, student.student_code, guardian_name, guardian_phone):
            assert secret not in dumped
        assert not {"alert", "promotion", "date_of_birth", "full_name"} & set(result)


def test_student_facts_for_the_whole_year_use_the_year_average(
    db_session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    info, student = an
    result = student_facts(db_session, config, an, ReportType.SCHOOL_RECORD, "year")
    profile = analytics.build_student_profile(
        db_session, info, student.student_id, "year", config, subject_ids=None
    )
    assert result is not None and profile is not None and profile.scope == "full"
    assert result["period"] == "cả năm"
    year = {s.name: s.year_average for s in profile.subjects if s.year_average is not None}
    shown = {s["name"]: s["average"] for s in result["subjects"] if s.get("average") is not None}
    assert shown == {name: float(value) for name, value in year.items()}


def test_a_student_outside_the_class_has_no_facts(
    db_session: Session,
    config: AnalyticsConfig,
    class_id_of: Callable[[str], int],
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    other = repo.get_class(db_session, class_id_of("11A1"))
    assert other is not None
    _info, student = an
    assert (
        facts.student_facts(
            db_session, other, student.student_id, ReportType.CONTACT_SLIP, "1", config
        )
        is None
    )


# --- Nhận xét môn -----------------------------------------------------------------------------


def test_subject_comment_facts_cover_only_the_one_subject_and_no_class_mean(
    db_session: Session,
    config: AnalyticsConfig,
    subject_id_of: Callable[[str], int],
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    info, student = an
    van = subject_id_of("Ngữ văn")
    result = student_facts(db_session, config, an, ReportType.SUBJECT_COMMENT, "1", subject_id=van)
    assert result is not None
    profile = analytics.build_student_profile(
        db_session, info, student.student_id, "1", config, subject_ids=frozenset({van})
    )
    assert profile is not None
    semester = profile.subjects[0].semesters[0]

    assert result["subject"] == "Ngữ văn" and result["kind"] == "môn tính điểm"
    assert result["average"] == (None if semester.average is None else float(semester.average))
    assert result["regular_scores"] == [float(x) for x in semester.tx]
    assert result["midterm"] == (None if semester.midterm is None else float(semester.midterm))
    # Không có dữ liệu của môn khác, của cả lớp, chuyên cần hay rèn luyện.
    assert set(result) == {
        "period",
        "subject",
        "kind",
        "complete",
        "regular_scores",
        "regular_scores_missing",
        "midterm",
        "final",
        "average",
    }
    dumped = json.dumps(result, ensure_ascii=False)
    assert student.full_name not in dumped and student.student_code not in dumped


def test_subject_comment_of_a_comment_subject_has_a_pass_fail_result(
    db_session: Session,
    config: AnalyticsConfig,
    subject_id_of: Callable[[str], int],
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    result = student_facts(
        db_session,
        config,
        an,
        ReportType.SUBJECT_COMMENT,
        "1",
        subject_id=subject_id_of("Giáo dục thể chất"),
    )
    assert result is not None
    assert result["kind"] == "môn nhận xét" and result["result"] in {"Đạt", "Chưa đạt", None}
    assert "average" not in result


def test_subject_comment_needs_a_taught_subject_and_a_single_semester(
    db_session: Session,
    config: AnalyticsConfig,
    subject_id_of: Callable[[str], int],
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    van = subject_id_of("Ngữ văn")
    assert student_facts(db_session, config, an, ReportType.SUBJECT_COMMENT, "1") is None
    assert (
        student_facts(db_session, config, an, ReportType.SUBJECT_COMMENT, "year", subject_id=van)
        is None
    )
    assert (
        student_facts(db_session, config, an, ReportType.SUBJECT_COMMENT, "1", subject_id=999_999)
        is None
    )


# --- Báo cáo lớp và khối ----------------------------------------------------------------------


def test_class_facts_match_the_dashboard_and_name_no_student(
    db_session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    info, _student = an
    result = facts.class_facts(db_session, info, "1", config)
    dashboard = analytics.build_dashboard(db_session, info, "1", config)

    assert result["class"] == "11A2" and result["grade"] == 11
    assert result["student_count"] == dashboard.student_count == 40
    assert result["students_absent_from_warning_level"] == dashboard.absent_notice_students
    assert result["students_absent_over_maximum"] == dashboard.absent_over_limit_students
    total = sum(result["learning_levels"].values())
    assert total == dashboard.student_count
    assert [s["name"] for s in result["subjects"]] == [s.name for s in dashboard.subjects]

    dumped = json.dumps(result, ensure_ascii=False)
    for row in repo.class_students(db_session, info.id):
        assert row.full_name not in dumped and row.student_code not in dumped
    assert "attention" not in result and "promotion_counts" not in result  # chỉ có khi cả năm


def test_class_facts_for_the_whole_year_add_promotion_counts(
    db_session: Session,
    config: AnalyticsConfig,
    an: tuple[repo.ClassInfo, repo.StudentInfo],
) -> None:
    info, _student = an
    result = facts.class_facts(db_session, info, "year", config)
    counts = result["promotion_counts"]
    assert counts["eligible"] + counts["not_eligible"] + counts["unknown"] == 40


def test_grade_facts_compare_the_classes_of_the_grade(
    db_session: Session, config: AnalyticsConfig
) -> None:
    result = facts.grade_facts(db_session, 11, "1", config)
    overview = analytics.build_grade_overview(
        db_session, 11, repo.classes_in_grade(db_session, 11), "1", config
    )
    assert result["grade"] == 11
    assert [c["class"] for c in result["classes"]] == [c.name for c in overview.classes]
    assert [c["student_count"] for c in result["classes"]] == [
        c.student_count for c in overview.classes
    ]
    means = {
        s["subject"]: {m["class"]: m["mean"] for m in s["class_means"]}
        for s in result["common_subject_means"]
    }
    assert means  # có môn chung để so sánh
    for subject in overview.common_subjects:
        for item in subject.class_means:
            name = next(c.name for c in overview.classes if c.class_id == item.class_id)
            expected = None if item.mean is None else float(item.mean)
            assert means[subject.name][name] == expected

"""Bảy hàm LLM được gọi (D-087): phân quyền, không rò danh tính, số khớp Analytics, chỉ đọc."""

import json
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.analytics import service
from app.analytics.schemas import StudentProfileSubjectsOut
from app.assistant.tools import (
    MAX_LIST_ROWS,
    TOOLS,
    ToolContext,
    ToolOutcome,
    run_tool,
    tool_specs,
)
from app.core.pseudonymize import FORBIDDEN_KEYS

pytestmark = pytest.mark.db

MakeCtx = Callable[..., ToolContext]

GVCN_11A2 = "gvcn.11a2@example.com"
GVBM_TOAN_11 = "gv.toan.11@example.com"  # dạy Toán mọi lớp khối 11, chủ nhiệm 11A1
GVBM_VAN_11 = "gv.van.11@example.com"
GVCN_10A2 = "gvcn.10a2@example.com"
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"

DEMO_ABSENT = "HS1102001"  # nghỉ 38 buổi
DEMO_LOW_MATH = "HS1102002"  # Toán 3,0 học kỳ I


def code_of(ctx: ToolContext, real_code: str) -> str:
    student = next(s for s in ctx.pseudo.known_students() if s.student_code == real_code)
    return ctx.pseudo.code_for(student)


def run(ctx: ToolContext, name: str, **arguments: Any) -> ToolOutcome:
    ctx.begin_read_only()
    try:
        return run_tool(ctx, name, arguments)
    finally:
        ctx.end_read_only()


def assert_clean(ctx: ToolContext, outcome: ToolOutcome) -> None:
    """Kết quả không có khoá cấm, họ tên hay mã học sinh thật."""
    ctx.pseudo.assert_safe(outcome.result)
    dumped = json.dumps(outcome.result, ensure_ascii=False).casefold()
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in dumped


def is_blocked(outcome: ToolOutcome) -> bool:
    return outcome.blocked and outcome.result["error"] == "forbidden" and not outcome.ok


# --- Đăng ký ------------------------------------------------------------------------------------


def test_exactly_seven_tools_with_the_designed_names() -> None:
    assert sorted(TOOLS) == [
        "get_attendance_summary",
        "get_class_summary",
        "get_grade_overview",
        "get_student_detail",
        "get_subject_scores",
        "list_students",
        "search_regulation",
    ]
    assert [spec.name for spec in tool_specs()] == list(TOOLS)


def test_every_schema_matches_its_argument_model_and_is_documented_in_vietnamese() -> None:
    for name, tool in TOOLS.items():
        schema = tool.spec.input_schema
        fields = tool.args_model.model_fields
        assert set(schema["properties"]) == set(fields), name
        required = {key for key, f in fields.items() if f.is_required()}
        assert set(schema["required"]) == required, name
        assert schema["additionalProperties"] is False
        assert tool.spec.description.strip().endswith((".", "dụng được.")), name
        for prop_name, prop in schema["properties"].items():
            assert prop["description"], f"{name}.{prop_name} thiếu mô tả"


def test_no_tool_accepts_identity_fields_as_arguments() -> None:
    for tool in TOOLS.values():
        assert not set(tool.args_model.model_fields) & FORBIDDEN_KEYS


# --- Chỉ đọc ------------------------------------------------------------------------------------


def test_read_only_mode_makes_the_database_refuse_writes_and_is_then_lifted(
    make_ctx: MakeCtx, db_session: Session
) -> None:
    ctx = make_ctx(GVCN_11A2)
    insert = "INSERT INTO ai_logs (user_id, question) VALUES (1, 'thử')"

    ctx.begin_read_only()
    with pytest.raises(DBAPIError):
        db_session.execute(text(insert))
    ctx.end_read_only()  # rollback savepoint: phiên về đọc-ghi

    db_session.execute(text(insert))  # ghi lại được (và hết test thì rollback)


def test_a_tool_that_fails_internally_leaves_a_working_read_only_session(
    make_ctx: MakeCtx, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("lỗi bất ngờ")

    monkeypatch.setattr("app.assistant.tools.service.build_class_results", boom)
    broken = run(ctx, "get_class_summary")
    monkeypatch.undo()
    ok = run(ctx, "get_class_summary")

    assert broken.result["error"] == "internal_error" and not broken.ok and not broken.blocked
    assert "lỗi bất ngờ" not in json.dumps(broken.result)  # không lộ chi tiết
    assert ok.ok


def test_unknown_tool_and_bad_arguments_are_errors_not_exceptions(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    unknown = run(ctx, "run_sql", query="select * from students")
    extra = run(ctx, "get_class_summary", class_id=1, date_of_birth="2010-01-01")
    wrong_type = run(ctx, "list_students", min_absent_days="nhiều")

    for outcome, error in ((unknown, "unknown_tool"), (extra, "invalid_arguments")):
        assert not outcome.ok and outcome.result["error"] == error
    assert wrong_type.result["error"] == "invalid_arguments"
    assert not any(o.blocked for o in (unknown, extra, wrong_type))


def test_semester_may_be_sent_as_a_number(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "get_class_summary", semester=2)

    assert outcome.ok and outcome.result["semester"] == "học kỳ II"


# --- 1. get_class_summary ----------------------------------------------------------------------


def test_class_summary_matches_the_dashboard(
    make_ctx: MakeCtx, db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2", semester="year")

    outcome = run(ctx, "get_class_summary")

    dashboard = service.build_dashboard(
        db_session,
        repo.get_class(db_session, class_id_of("11A2")),  # type: ignore[arg-type]
        "year",
        ctx.config,
    )
    result = outcome.result
    assert outcome.ok and result["class"] == {"name": "11A2", "grade_level": 11}
    assert result["student_count"] == dashboard.student_count == 40
    assert result["absent_notice_students"] == dashboard.absent_notice_students
    assert result["absent_over_limit_students"] == dashboard.absent_over_limit_students
    assert result["absence_limits"] == {"notice": 30, "maximum": 45}
    assert result["semester"] == "cả năm"
    labels = {
        "good": "Tốt",
        "fair": "Khá",
        "pass": "Đạt",
        "fail": "Chưa đạt",
        "incomplete": "Chưa đủ dữ liệu",
    }
    assert result["learning_levels"] == {
        labels[key]: value for key, value in dashboard.learning_levels.items()
    }
    assert isinstance(result["mean_absent_sessions"], float)
    assert set(result["alert_counts"]) == {"high", "medium", "low"}
    assert outcome.sources[0]["tool"] == "get_class_summary"
    assert_clean(ctx, outcome)


def test_class_summary_uses_the_open_class_unless_the_llm_names_a_class(
    make_ctx: MakeCtx, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(PRINCIPAL, open_class="11A2")

    default = run(ctx, "get_class_summary")
    other = run(ctx, "get_class_summary", class_id=class_id_of("10A1"))

    assert default.result["class"]["name"] == "11A2"
    assert other.result["class"]["name"] == "10A1"


def test_class_summary_without_any_class_asks_which_one(make_ctx: MakeCtx) -> None:
    outcome = run(make_ctx(PRINCIPAL), "get_class_summary")

    assert outcome.result["error"] == "missing_class" and not outcome.blocked


@pytest.mark.parametrize(
    ("email", "target_class", "allowed"),
    [
        (GVCN_11A2, "11A2", True),
        (GVCN_11A2, "11A1", False),  # lớp khác cùng khối
        (GVCN_10A2, "11A2", False),
        (GVBM_VAN_11, "11A2", False),  # GVBM không xem dữ liệu cả lớp
        (GVBM_TOAN_11, "11A2", False),  # dạy Toán lớp 11A2 nhưng không chủ nhiệm
        (GVBM_TOAN_11, "11A1", True),  # nhưng chủ nhiệm 11A1
        (PRINCIPAL, "11A2", True),
        (ADMIN, "11A2", False),
    ],
)
def test_class_summary_permission_matrix(
    make_ctx: MakeCtx,
    class_id_of: Callable[[str], int],
    email: str,
    target_class: str,
    allowed: bool,
) -> None:
    ctx = make_ctx(email, roster=())

    outcome = run(ctx, "get_class_summary", class_id=class_id_of(target_class))

    assert outcome.ok is allowed
    assert outcome.blocked is (not allowed)
    if not allowed:
        assert is_blocked(outcome)
        assert "student_count" not in outcome.result  # không đọc, không trả dữ liệu nào


def test_class_summary_for_a_missing_class_is_not_found_for_principal_and_forbidden_for_teachers(
    make_ctx: MakeCtx,
) -> None:
    assert run(make_ctx(PRINCIPAL), "get_class_summary", class_id=999_999).result["error"] == (
        "not_found"
    )
    assert is_blocked(run(make_ctx(GVCN_11A2), "get_class_summary", class_id=999_999))


# --- 2. get_student_detail ---------------------------------------------------------------------


@pytest.mark.usefixtures("alerts")
def test_student_detail_for_homeroom_teacher_matches_the_profile(
    make_ctx: MakeCtx, db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")
    code = code_of(ctx, DEMO_ABSENT)

    outcome = run(ctx, "get_student_detail", student_code=code, semester="year")

    info = repo.get_class(db_session, class_id_of("11A2"))
    assert info is not None
    student = ctx.pseudo.resolve(code)
    assert student is not None
    profile = service.build_student_profile(
        db_session, info, student.student_id, "year", ctx.config, subject_ids=None
    )
    assert profile is not None and not isinstance(profile, StudentProfileSubjectsOut)
    result = outcome.result
    assert outcome.ok and result["student"] == code
    assert result["attendance"]["absent_total"] == profile.attendance.absent_total == 38
    assert result["attendance"]["excused"] == profile.attendance.excused
    assert result["attendance"]["unexcused"] == profile.attendance.unexcused
    assert {s["name"] for s in result["subjects"]} == {s.name for s in profile.subjects}
    assert result["learning"]["level"] in {"Tốt", "Khá", "Đạt", "Chưa đạt", None}
    assert result["promotion"]["reasons"] is not None
    assert result["alert"] is not None  # em An có cảnh báo
    assert any("38" in message for message in result["alert"]["top_reasons"])
    assert "guardian_name" not in json.dumps(result)
    assert_clean(ctx, outcome)


def test_student_detail_for_subject_teacher_has_only_own_subject_and_no_private_sections(
    make_ctx: MakeCtx,
) -> None:
    ctx = make_ctx(GVBM_VAN_11, open_class="11A2", open_subject="Ngữ văn")
    code = code_of(ctx, DEMO_ABSENT)

    outcome = run(ctx, "get_student_detail", student_code=code)

    assert outcome.ok
    assert [s["name"] for s in outcome.result["subjects"]] == ["Ngữ văn"]
    for private in ("attendance", "conduct", "learning", "promotion", "alert", "attention_reasons"):
        assert private not in outcome.result
    assert_clean(ctx, outcome)


def test_student_detail_blocks_teachers_of_other_classes(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_10A2, roster=("11A2",))
    code = code_of(ctx, DEMO_ABSENT)

    outcome = run(ctx, "get_student_detail", student_code=code)

    assert is_blocked(outcome)
    assert "subjects" not in outcome.result


def test_student_detail_for_principal_is_full_but_never_has_guardian(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(PRINCIPAL, open_class="11A2")

    outcome = run(ctx, "get_student_detail", student_code=code_of(ctx, DEMO_ABSENT))

    assert outcome.ok and "attendance" in outcome.result
    assert_clean(ctx, outcome)


def test_student_detail_rejects_codes_that_were_never_issued(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")
    code_of(ctx, DEMO_ABSENT)  # đã cấp HS_01

    for bogus in ("HS_02", "HS_99", DEMO_ABSENT, "Trần Minh An", "1 OR 1=1"):
        outcome = run(ctx, "get_student_detail", student_code=bogus)
        assert outcome.result["error"] == "unknown_student", bogus
        assert not outcome.blocked


# --- 3. list_students --------------------------------------------------------------------------


def test_list_students_by_absence_returns_pseudonyms_and_matches_the_data(
    make_ctx: MakeCtx, db_session: Session
) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "list_students", min_absent_days=30)

    expected = db_session.scalar(
        text(
            """
            SELECT count(*) FROM (
              SELECT cs.id FROM attendance a
              JOIN class_students cs ON cs.id = a.class_student_id
              WHERE cs.class_id = :class_id
                AND a.status IN ('absent_excused', 'absent_unexcused')
              GROUP BY cs.id HAVING count(*) >= 30
            ) t
            """
        ),
        {"class_id": ctx.class_id},
    )
    result = outcome.result
    assert outcome.ok and result["total_matches"] == expected and expected >= 1
    assert result["returned"] == len(result["students"]) == min(expected, MAX_LIST_ROWS)
    assert all(row["absent_total"] >= 30 for row in result["students"])
    assert all(row["student"].startswith("HS_") for row in result["students"])
    demo = code_of(ctx, DEMO_ABSENT)
    assert next(r for r in result["students"] if r["student"] == demo)["absent_total"] == 38
    assert_clean(ctx, outcome)


@pytest.mark.usefixtures("alerts")
def test_list_students_by_low_subject_and_alert_level(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    low = run(ctx, "list_students", subject_below=3.5)
    high = run(ctx, "list_students", alert_level="high")

    demo = code_of(ctx, DEMO_LOW_MATH)
    row = next(r for r in low.result["students"] if r["student"] == demo)
    assert {"name": "Toán", "average": 3.0} in row["low_subjects"]
    assert high.ok and high.result["total_matches"] >= 1
    assert all(r["alert_level"] == "Cao" for r in high.result["students"])
    assert_clean(ctx, low)
    assert_clean(ctx, high)


def test_list_students_is_capped_and_says_so(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "list_students")  # không lọc: cả 40 em

    assert outcome.result["total_matches"] == 40
    assert outcome.result["returned"] == 40 and outcome.result["truncated"] is False
    assert MAX_LIST_ROWS >= 40  # lớp 40 em không bị cắt; trần chỉ để chặn kết quả khổng lồ


def test_subject_teacher_may_filter_by_own_subject_only(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVBM_TOAN_11, open_class="11A2", open_subject="Toán")

    by_score = run(ctx, "list_students", subject_below=3.5)
    by_absence = run(ctx, "list_students", min_absent_days=30)
    by_alert = run(ctx, "list_students", alert_level="high")

    assert by_score.ok
    assert code_of(ctx, DEMO_LOW_MATH) in {r["student"] for r in by_score.result["students"]}
    for row in by_score.result["students"]:
        assert set(row) == {"student", "low_subjects"}  # không có nghỉ, mức học tập, cảnh báo
        assert all(s["name"] == "Toán" for s in row["low_subjects"])
    assert is_blocked(by_absence) and is_blocked(by_alert)
    assert_clean(ctx, by_score)


def test_subject_teacher_cannot_list_a_class_they_do_not_teach(
    make_ctx: MakeCtx, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(GVBM_VAN_11, roster=())

    assert is_blocked(run(ctx, "list_students", class_id=class_id_of("10A1")))


# --- 4. get_subject_scores ---------------------------------------------------------------------


def test_subject_scores_match_the_score_table(
    make_ctx: MakeCtx, db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(GVBM_TOAN_11, open_class="11A2", open_subject="Toán")

    outcome = run(ctx, "get_subject_scores")

    info = repo.get_class(db_session, class_id_of("11A2"))
    subject = next(s for s in repo.class_subjects(db_session, info.id) if s.name == "Toán")  # type: ignore[union-attr]
    expected = service.build_subject_scores(db_session, info, subject, 1, ctx.config)  # type: ignore[arg-type]
    result = outcome.result
    assert outcome.ok and result["subject"]["name"] == "Toán" and result["semester"] == "học kỳ I"
    assert result["mean"] == float(expected.mean)  # type: ignore[arg-type]
    assert result["distribution"]["below_fail"] == expected.distribution.below_fail
    assert result["student_count"] == expected.student_count
    demo = next(r for r in result["students"] if r["student"] == code_of(ctx, DEMO_LOW_MATH))
    assert demo["average"] == 3.0
    assert_clean(ctx, outcome)


def test_subject_scores_permission_matrix(
    make_ctx: MakeCtx,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    toan, van = subject_id_of("Toán"), subject_id_of("Ngữ văn")
    c11a2, c11a1, c10a1 = class_id_of("11A2"), class_id_of("11A1"), class_id_of("10A1")

    def ask(email: str, **args: Any) -> ToolOutcome:
        return run(make_ctx(email, roster=()), "get_subject_scores", **args)

    assert ask(GVBM_TOAN_11, class_id=c11a2, subject_id=toan).ok
    assert ask(GVBM_TOAN_11, class_id=c11a1, subject_id=toan).ok  # dạy mọi lớp khối 11
    assert is_blocked(ask(GVBM_TOAN_11, class_id=c11a2, subject_id=van))  # môn khác
    assert is_blocked(ask(GVBM_VAN_11, class_id=c11a2, subject_id=toan))
    assert is_blocked(ask(GVBM_TOAN_11, class_id=c10a1, subject_id=toan))  # khối khác
    assert ask(GVCN_11A2, class_id=c11a2, subject_id=van).ok  # GVCN xem mọi môn của lớp
    assert is_blocked(ask(GVCN_11A2, class_id=c11a1, subject_id=van))
    assert ask(PRINCIPAL, class_id=c10a1, subject_id=van).ok
    assert is_blocked(ask(ADMIN, class_id=c11a2, subject_id=toan))


def test_subject_scores_needs_a_subject_and_rejects_a_subject_the_class_does_not_have(
    make_ctx: MakeCtx, class_id_of: Callable[[str], int]
) -> None:
    ctx = make_ctx(PRINCIPAL, open_class="11A2")

    assert run(ctx, "get_subject_scores").result["error"] == "missing_subject"
    assert run(ctx, "get_subject_scores", subject_id=999_999).result["error"] == "not_found"


def test_subject_scores_rejects_a_year_view(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(PRINCIPAL, open_class="11A2", open_subject="Toán")

    assert run(ctx, "get_subject_scores", semester="year").result["error"] == "invalid_arguments"
    assert run(ctx, "get_subject_scores", semester=2).ok


def test_subject_scores_falls_back_to_semester_one_when_the_screen_shows_the_whole_year(
    make_ctx: MakeCtx,
) -> None:
    ctx = make_ctx(PRINCIPAL, open_class="11A2", open_subject="Toán", semester="year")

    assert run(ctx, "get_subject_scores").result["semester"] == "học kỳ I"


# --- 5. get_grade_overview ---------------------------------------------------------------------


def test_grade_overview_for_principal_matches_the_service(
    make_ctx: MakeCtx, db_session: Session
) -> None:
    ctx = make_ctx(PRINCIPAL)

    outcome = run(ctx, "get_grade_overview", grade_level=11, semester="1")

    expected = service.build_grade_overview(
        db_session, 11, repo.classes_in_grade(db_session, 11), "1", ctx.config
    )
    result = outcome.result
    assert outcome.ok and result["grade_level"] == 11
    assert [c["name"] for c in result["classes"]] == [c.name for c in expected.classes]
    assert [c["student_count"] for c in result["classes"]] == [
        c.student_count for c in expected.classes
    ]
    first = result["common_subject_means"][0]
    assert {m["class"] for m in first["by_class"]} == {c.name for c in expected.classes}
    assert_clean(ctx, outcome)


@pytest.mark.parametrize("email", [GVCN_11A2, GVBM_TOAN_11, GVBM_VAN_11, ADMIN])
def test_grade_overview_is_for_principal_only(make_ctx: MakeCtx, email: str) -> None:
    outcome = run(make_ctx(email, roster=()), "get_grade_overview", grade_level=11)

    assert is_blocked(outcome)
    assert "classes" not in outcome.result


def test_grade_overview_validates_the_grade(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(PRINCIPAL)

    for bad in (9, 13, 0):
        assert run(ctx, "get_grade_overview", grade_level=bad).result["error"] == (
            "invalid_arguments"
        )
    assert run(ctx, "get_grade_overview").result["error"] == "invalid_arguments"


# --- 6. get_attendance_summary -----------------------------------------------------------------


def test_attendance_summary_matches_the_data_and_the_profile(
    make_ctx: MakeCtx, db_session: Session
) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "get_attendance_summary", top_n=3)

    result = outcome.result
    expected_total = db_session.scalar(
        text(
            """
            SELECT count(*) FROM attendance a
            JOIN class_students cs ON cs.id = a.class_student_id
            WHERE cs.class_id = :class_id AND a.status IN ('absent_excused', 'absent_unexcused')
            """
        ),
        {"class_id": ctx.class_id},
    )
    assert outcome.ok and result["absent_total"] == expected_total
    assert result["excused"] + result["unexcused"] == result["absent_total"]
    assert sum(p["absent_total"] for p in result["by_period"]) == result["absent_total"]
    assert 1 <= len(result["top_absent"]) <= 3
    totals = [t["absent_total"] for t in result["top_absent"]]
    assert totals == sorted(totals, reverse=True)
    assert result["granularity"] == "month"
    assert_clean(ctx, outcome)


def test_attendance_summary_for_a_date_range_and_by_week(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    month = run(ctx, "get_attendance_summary", from_date="2027-03-01", to_date="2027-03-31")
    week = run(
        ctx,
        "get_attendance_summary",
        from_date="2027-03-01",
        to_date="2027-03-31",
        granularity="week",
    )

    assert month.ok and month.result["from"] == "2027-03-01" and month.result["to"] == "2027-03-31"
    assert all(p["period"] == "2027-03" for p in month.result["by_period"])
    assert all(date.fromisoformat(p["period"]).weekday() == 0 for p in week.result["by_period"])
    assert week.result["absent_total"] == month.result["absent_total"]


def test_attendance_summary_rejects_a_reversed_range(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "get_attendance_summary", from_date="2027-04-01", to_date="2027-03-01")

    assert outcome.result["error"] == "invalid_range" and not outcome.blocked


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        (GVCN_11A2, True),
        (PRINCIPAL, True),
        (GVBM_TOAN_11, False),
        (GVBM_VAN_11, False),
        (ADMIN, False),
    ],
)
def test_attendance_summary_permission_matrix(
    make_ctx: MakeCtx, class_id_of: Callable[[str], int], email: str, allowed: bool
) -> None:
    outcome = run(
        make_ctx(email, roster=()), "get_attendance_summary", class_id=class_id_of("11A2")
    )

    assert outcome.ok is allowed and outcome.blocked is (not allowed)


# --- 7. search_regulation ----------------------------------------------------------------------


def test_search_regulation_returns_cited_passages(
    make_ctx: MakeCtx, add_regulation: Callable[..., Any]
) -> None:
    add_regulation()
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "search_regulation", query="đơn xin phép nghỉ học của cha mẹ học sinh")

    result = outcome.result
    assert outcome.ok and result["found"] is True
    top = result["hits"][0]
    assert (
        top["article"] == "Điều 1"
        and top["clause"] == "Khoản 1"
        and "đơn xin phép" in top["content"]
    )
    assert outcome.sources[0]["type"] == "regulation"
    assert outcome.sources[0]["document"] == "Quy chế thử (VĂN BẢN GIẢ)"
    assert outcome.sources[0]["article"] == "Điều 1"


def test_search_regulation_says_not_found_instead_of_guessing(
    make_ctx: MakeCtx, add_regulation: Callable[..., Any]
) -> None:
    add_regulation()
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    outcome = run(ctx, "search_regulation", query="giá vàng hôm nay tăng bao nhiêu")

    assert outcome.ok and outcome.result["found"] is False
    assert outcome.result["hits"] == [] and outcome.sources == []
    assert outcome.result["message"] == "Không tìm thấy trong văn bản quy định"


def test_search_regulation_never_returns_an_expired_document(
    make_ctx: MakeCtx, add_regulation: Callable[..., Any], db_session: Session
) -> None:
    from app.core.enums import RegulationStatus
    from app.rag.service import change_status

    result = add_regulation()
    ctx = make_ctx(GVCN_11A2, open_class="11A2")
    change_status(db_session, ctx.user, result.document.id, RegulationStatus.EXPIRED)

    outcome = run(ctx, "search_regulation", query="đơn xin phép nghỉ học của cha mẹ học sinh")

    assert outcome.result["found"] is False


def test_search_regulation_requires_a_real_query(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(GVCN_11A2, open_class="11A2")

    assert run(ctx, "search_regulation", query="").result["error"] == "invalid_arguments"
    assert run(ctx, "search_regulation").result["error"] == "invalid_arguments"
    assert run(ctx, "search_regulation", query="x" * 600).result["error"] == "invalid_arguments"


# --- Không có hàm nào ghi dữ liệu --------------------------------------------------------------


@pytest.mark.usefixtures("alerts")
def test_running_every_tool_changes_nothing_in_the_database(
    make_ctx: MakeCtx, db_session: Session, add_regulation: Callable[..., Any]
) -> None:
    add_regulation()
    tables = ("students", "assessments", "attendance", "risk_alerts", "audit_logs", "ai_logs")

    def counts() -> list[int]:
        return [db_session.scalar(text(f"SELECT count(*) FROM {t}")) or 0 for t in tables]

    before = counts()
    ctx = make_ctx(PRINCIPAL, open_class="11A2", open_subject="Toán")
    code = code_of(ctx, DEMO_ABSENT)
    calls = [
        ("get_class_summary", {}),
        ("get_student_detail", {"student_code": code}),
        ("list_students", {"min_absent_days": 30}),
        ("get_subject_scores", {}),
        ("get_grade_overview", {"grade_level": 11}),
        ("get_attendance_summary", {}),
        ("search_regulation", {"query": "nghỉ học cần đơn xin phép"}),
    ]
    for name, arguments in calls:
        assert run(ctx, name, **arguments).ok, name

    assert counts() == before

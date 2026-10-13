"""Bộ đánh giá eval/assistant_eval.py (D-092): khung câu hỏi hợp lệ, và đáp án tính bằng SQL độc lập
khớp với kết quả các hàm Analytics trên dữ liệu seed (nên một lệch pha sẽ lộ ra ngay ở đây)."""

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.orm import Session

from app.assistant.tools import TOOLS, ToolContext, run_tool

pytestmark = pytest.mark.db

EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
MakeCtx = Callable[..., ToolContext]


@pytest.fixture(scope="module")
def ev() -> ModuleType:
    spec = importlib.util.spec_from_file_location("assistant_eval", EVAL_DIR / "assistant_eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def questions() -> dict:
    return json.loads((EVAL_DIR / "assistant_questions.json").read_text(encoding="utf-8"))


def run(ctx: ToolContext, name: str, **arguments: object) -> dict:
    ctx.begin_read_only()
    try:
        return run_tool(ctx, name, arguments).result
    finally:
        ctx.end_read_only()


def test_question_set_is_well_formed(questions: dict) -> None:
    items = questions["questions"]

    assert len(items) == 15
    assert len({q["id"] for q in items}) == 15
    refusals = [q for q in items if "refusal" in q]
    positives = [q for q in items if "refusal" not in q]
    assert (len(positives), len(refusals)) == (12, 3)
    for question in positives:
        assert question["tools_any"] and set(question["tools_any"]) <= set(TOOLS)
        assert question.get("numbers") or question.get("text")
    for question in items:
        assert question["semester"] in ("1", "2", "year")
        assert question["question"].strip().endswith(("?", "."))


def test_every_question_resolves_against_the_seed(
    ev: ModuleType, questions: dict, db_session: Session
) -> None:
    for item in questions["questions"]:
        user = ev.find_user(db_session, item.get("user", questions["default_user"]))
        class_id, subject_id = ev.screen_ids(db_session, item)
        assert user.id and (class_id is not None or "class" not in item)
        assert subject_id is not None or "subject" not in item
        for spec in item.get("numbers", []):
            assert ev.calc(db_session, spec), item["id"]


def test_sql_answers_agree_with_the_analytics_tools(
    ev: ModuleType, make_ctx: MakeCtx, db_session: Session
) -> None:
    gvcn = make_ctx("gvcn.11a2@example.com", open_class="11A2", semester="year")
    summary = run(gvcn, "get_class_summary")
    attendance = run(gvcn, "get_attendance_summary", top_n=1)
    toan = make_ctx("gv.toan.11@example.com", open_class="11A2", open_subject="Toán")
    scores = run(toan, "get_subject_scores")
    bgh = make_ctx("bgh1@example.com", roster=(), semester="year")
    grade_11 = run(bgh, "get_grade_overview", grade_level=11)
    grade_12 = run(bgh, "get_grade_overview", grade_level=12, semester="1")

    def sql(**spec: object) -> list[str]:
        return ev.calc(db_session, spec)

    assert sql(calc="absent_at_least", **{"class": "11A2", "n": 30}) == [
        ev.norm(summary["absent_notice_students"])
    ]
    assert sql(calc="class_size", **{"class": "11A2"}) == [ev.norm(summary["student_count"])]
    assert sql(calc="mean_absent", **{"class": "11A2"}) == [
        ev.norm(summary["mean_absent_sessions"])
    ]
    assert sql(calc="max_absent", **{"class": "11A2"}) == [
        ev.norm(attendance["top_absent"][0]["absent_total"])
    ]
    assert sql(calc="student_absent_total", student_code="HS1102001") == ["38"]
    assert sql(calc="subject_mean", subject="Toán", semester=1, **{"class": "11A2"}) == [
        ev.norm(scores["mean"])
    ]
    assert sql(
        calc="subject_below_count", subject="Toán", semester=1, below=3.5, **{"class": "11A2"}
    ) == [ev.norm(scores["distribution"]["below_fail"])]
    assert sql(calc="absent_at_least_per_class", grade=11, n=30) == sorted(
        {ev.norm(c["absent_notice_students"]) for c in grade_11["classes"]}
    )
    assert sql(calc="class_size_per_class", grade=12) == sorted(
        {ev.norm(c["student_count"]) for c in grade_12["classes"]}
    )


def test_dry_run_prints_expected_answers_without_an_llm(
    ev: ModuleType,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Borrowed:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(ev, "get_session_factory", lambda: lambda: Borrowed())

    assert ev.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "A01:" in out and "N03:" in out and "số kỳ vọng: 38" in out
    assert "chưa gọi LLM" in out


def test_without_an_llm_the_eval_stops_with_exit_code_2(
    ev: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.assistant.llm import LLMNotConfigured

    def not_configured() -> None:
        raise LLMNotConfigured("thiếu khoá")

    monkeypatch.setattr(ev, "get_llm_provider", not_configured)

    assert ev.main([]) == 2
    assert "Chưa cấu hình LLM" in capsys.readouterr().err

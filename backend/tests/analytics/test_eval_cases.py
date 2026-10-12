"""Chạy bộ 30 ca tính tay `eval/analytics_cases.json` qua mã Analytics (D-047 đến D-051).

Mỗi ca có lời giải tay trong trường `note`; kết quả mong đợi cũng đã được đối chiếu bằng một bản
tính độc lập bằng phân số trước khi chốt. Thêm ca mới: sửa file JSON, không sửa test này.
"""

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.analytics.conduct import PeriodConduct
from app.analytics.config import AnalyticsConfig
from app.analytics.learning import SubjectResult, learning_result
from app.analytics.promotion import promotion_status
from app.analytics.scores import semester_average_from_scores, year_average
from app.core.enums import ConductLevel

CASES_FILE = Path(__file__).resolve().parents[3] / "eval" / "analytics_cases.json"
CASES: dict[str, Any] = json.loads(CASES_FILE.read_text(encoding="utf-8"))

Build = Callable[..., list[SubjectResult]]


def ids(group: str) -> list[str]:
    return [case["id"] for case in CASES[group]]


def test_the_file_has_exactly_30_cases_with_unique_ids() -> None:
    groups = ("semester_average", "year_average", "learning_level", "promotion")
    all_ids = [case["id"] for group in groups for case in CASES[group]]

    assert len(all_ids) == 30
    assert len(set(all_ids)) == 30
    assert all(case["note"].strip() for group in groups for case in CASES[group])


@pytest.mark.parametrize("case", CASES["semester_average"], ids=ids("semester_average"))
def test_semester_average_case(config: AnalyticsConfig, case: dict[str, Any]) -> None:
    result = semester_average_from_scores(
        [Decimal(v) for v in case["tx"]],
        Decimal(case["midterm"]),
        Decimal(case["final"]),
        config,
    )

    assert result == Decimal(case["expected"]), case["note"]


@pytest.mark.parametrize("case", CASES["year_average"], ids=ids("year_average"))
def test_year_average_case(config: AnalyticsConfig, case: dict[str, Any]) -> None:
    result = year_average(Decimal(case["semester1"]), Decimal(case["semester2"]), config)

    assert result == Decimal(case["expected"]), case["note"]


@pytest.mark.parametrize("case", CASES["learning_level"], ids=ids("learning_level"))
def test_learning_level_case(config: AnalyticsConfig, results: Build, case: dict[str, Any]) -> None:
    result = learning_result(results(case["scores"], case["comments"]), config)

    assert result.level is not None and result.base_level is not None
    assert result.level.value == case["expected_level"], case["note"]
    assert result.base_level.value == case["expected_base_level"], case["note"]
    assert result.adjusted is case["expected_adjusted"], case["note"]


@pytest.mark.parametrize("case", CASES["promotion"], ids=ids("promotion"))
def test_promotion_case(config: AnalyticsConfig, results: Build, case: dict[str, Any]) -> None:
    subjects = results(case["scores"], case["comments"])
    level = None if case["conduct"] is None else ConductLevel(case["conduct"])

    result = promotion_status(
        learning=learning_result(subjects, config),
        year_subjects=subjects,
        conduct=PeriodConduct(level, derived=case["conduct_derived"]),
        absent_sessions=case["absent"],
        config=config,
    )

    assert result.eligible is case["expected_eligible"], case["note"]
    assert [r.value for r in result.reasons] == case["expected_reasons"], case["note"]
    assert [
        {"subject_id": r.subject_id, "reason": r.reason.value} for r in result.retake_subjects
    ] == case["expected_retake"], case["note"]

"""Fixture cho test Analytics: cấu hình mặc định và cách dựng nhanh kết quả các môn."""

from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

import pytest

from app.analytics.config import AnalyticsConfig, config_from_values
from app.analytics.learning import SubjectResult
from app.core.enums import AssessmentType, CommentResult

# Giá trị mặc định của bảng settings sau mọi migration (test_config.py kiểm khớp với DB).
DEFAULT_SETTINGS: dict[str, Any] = {
    "coef_midterm": 2,
    "coef_final": 3,
    "coef_year_semester2": 2,
    "max_absent_sessions": 45,
    "absent_warning_notice": 30,
    "absent_warning_high": 40,
    "score_threshold_fail": 3.5,
    "score_threshold_pass": 5.0,
    "score_threshold_fair": 6.5,
    "score_threshold_good": 8.0,
    "level_min_subjects": 6,
    "regular_assessment_count": [
        {"max_periods": 35, "count": 2},
        {"max_periods": 70, "count": 3},
        {"max_periods": None, "count": 4},
    ],
    "level_single_subject_adjustment": True,
}


@pytest.fixture
def default_settings() -> dict[str, Any]:
    return dict(DEFAULT_SETTINGS)


@pytest.fixture
def config() -> AnalyticsConfig:
    return config_from_values(DEFAULT_SETTINGS)


@pytest.fixture
def make_config() -> Callable[..., AnalyticsConfig]:
    """Cấu hình mặc định với một vài khoá `settings` bị thay: make_config(level_min_subjects=7)."""

    def build(**overrides: Any) -> AnalyticsConfig:
        return config_from_values(DEFAULT_SETTINGS | overrides)

    return build


@pytest.fixture
def results() -> Callable[..., list[SubjectResult]]:
    """Dựng danh sách kết quả các môn: môn điểm số có ĐTB (chuỗi, ví dụ "8.0"), môn nhận xét có
    "pass" hoặc "fail". Id môn điểm số từ 1, môn nhận xét từ 101."""

    def build(
        scores: Sequence[str] = (),
        comments: Sequence[str] = (),
        incomplete: Sequence[int] = (),
    ) -> list[SubjectResult]:
        built = [
            SubjectResult(
                subject_id=index,
                name=f"Môn điểm {index}",
                assessment_type=AssessmentType.SCORE,
                average=Decimal(value),
                complete=index not in incomplete,
            )
            for index, value in enumerate(scores, start=1)
        ]
        built += [
            SubjectResult(
                subject_id=100 + index,
                name=f"Môn nhận xét {index}",
                assessment_type=AssessmentType.COMMENT,
                comment_result=CommentResult(value),
                complete=100 + index not in incomplete,
            )
            for index, value in enumerate(comments, start=1)
        ]
        return built

    return build

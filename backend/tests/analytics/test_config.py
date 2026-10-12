from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.analytics.config import (
    REQUIRED_KEYS,
    AnalyticsConfig,
    MissingSettingError,
    config_from_values,
    load_config,
)


def test_values_become_exact_decimals_and_ints(default_settings: dict[str, Any]) -> None:
    config = config_from_values(default_settings)

    assert config.score_threshold_fail == Decimal("3.5")  # 3.5 từ JSON không thành 3.4999...
    assert config.score_threshold_pass == Decimal("5.0")
    assert config.score_threshold_fair == Decimal("6.5")
    assert config.score_threshold_good == Decimal("8.0")
    assert config.coef_midterm == Decimal(2) and config.coef_final == Decimal(3)
    assert config.coef_year_semester2 == Decimal(2)
    assert (config.level_min_subjects, config.max_absent_sessions) == (6, 45)
    assert (config.absent_warning_notice, config.absent_warning_high) == (30, 40)
    assert config.level_single_subject_adjustment is True


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_a_missing_key_is_reported_by_name(default_settings: dict[str, Any], key: str) -> None:
    del default_settings[key]

    with pytest.raises(MissingSettingError, match=key):
        config_from_values(default_settings)


def test_regular_assessment_rule_follows_the_settings(config: AnalyticsConfig) -> None:
    assert [config.required_regular(p) for p in (35, 36, 52, 70, 71, 105)] == [2, 3, 3, 3, 4, 4]


def test_config_is_immutable(config: AnalyticsConfig) -> None:
    with pytest.raises(AttributeError):
        config.coef_final = Decimal(9)  # type: ignore[misc]


@pytest.mark.db
def test_defaults_used_by_the_tests_match_the_database(
    db_session: Session, config: AnalyticsConfig
) -> None:
    # Giữ bộ giá trị mặc định trong tests/analytics/conftest.py khớp với migration.
    assert load_config(db_session) == config

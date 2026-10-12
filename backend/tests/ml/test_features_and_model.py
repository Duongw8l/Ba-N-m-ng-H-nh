"""Đặc trưng giữa học kỳ I, mô hình đã lưu, giải thích và đường lùi khi thiếu mô hình (D-072)."""

import json
import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics.config import load_config
from app.classes.academic import Attendance
from app.classes.models import ClassStudent, Student
from app.core.enums import AttendanceStatus as S
from app.core.enums import RiskLevel
from app.warning import features, model, service
from app.warning import repository as repo
from app.warning.features import FEATURE_NAMES, FORBIDDEN_FEATURE_WORDS
from app.warning.model import ForestPredictor, load_predictor
from app.warning.models import RiskAlert

D = Decimal
PASS = D("5.0")


# --- Đặc trưng: hàm thuần, tính tay -----------------------------------------------------------


def test_features_are_computed_by_hand() -> None:
    cutoff = date(2026, 11, 7)  # = 05/09/2026 + 9 tuần
    attendance = [
        (date(2026, 9, 10), S.ABSENT_EXCUSED),
        (
            date(2026, 10, 10),
            S.ABSENT_UNEXCUSED,
        ),  # đúng 28 ngày trước ngày cắt: ngoài 4 tuần gần nhất
        (date(2026, 10, 12), S.ABSENT_EXCUSED),
        (date(2026, 11, 7), S.ABSENT_UNEXCUSED),  # đúng ngày cắt: được tính
        (date(2026, 11, 8), S.ABSENT_UNEXCUSED),  # sau ngày cắt: không tính
        (date(2026, 9, 20), S.LATE),  # muộn không phải nghỉ
        (date(2026, 9, 21), S.PRESENT),
    ]

    result = features.build_features(
        {1: [D("6"), D("7"), D("8")], 2: [D("4"), D("5")]},
        {1: D("7"), 2: D("4.0")},
        attendance,
        cutoff,
        PASS,
    )

    assert result == {
        "tx_mean": 6.0,  # (6 + 7 + 8 + 4 + 5) / 5
        "tx_min_subject": 4.5,  # môn 2: (4 + 5) / 2
        "n_tx_below_pass": 1.0,  # chỉ môn 2 (4,5 < 5,0)
        "gk_mean": 5.5,
        "gk_min": 4.0,
        "n_gk_below_pass": 1.0,
        "absent_total": 4.0,  # 10/09, 10/10, 12/10, 07/11
        "absent_last_4_weeks": 2.0,  # 12/10 và 07/11
        "late_total": 1.0,
    }


def test_exactly_the_pass_threshold_is_not_below_it() -> None:
    result = features.build_features({1: [D("5.0")]}, {1: D("5.0")}, [], date(2026, 11, 7), PASS)

    assert result is not None
    assert result["n_tx_below_pass"] == 0.0 and result["n_gk_below_pass"] == 0.0


@pytest.mark.parametrize(
    ("tx", "gk"),
    [({}, {1: D("7")}), ({1: []}, {1: D("7")}), ({1: [D("7")]}, {})],
)
def test_a_student_without_scores_has_no_features(
    tx: dict[int, list[Decimal]], gk: dict[int, Decimal]
) -> None:
    assert features.build_features(tx, gk, [], date(2026, 11, 7), PASS) is None


def test_the_cutoff_is_nine_weeks_after_the_school_year_starts() -> None:
    assert features.snapshot_date(date(2026, 9, 5)) == date(2026, 11, 7)


def test_no_protected_attribute_is_a_feature() -> None:
    """DESIGN mục 10: không giới tính, dân tộc, nơi ở, hoàn cảnh gia đình, họ tên."""
    text = " ".join(FEATURE_NAMES + tuple(spec.label.lower() for spec in features.FEATURES))

    assert not [word for word in FORBIDDEN_FEATURE_WORDS if word in text]
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES)) == 9


# --- Đặc trưng từ DB seed ---------------------------------------------------------------------


@pytest.mark.db
def test_extract_class_matches_the_database(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    class_id = class_id_of("11A2")
    ready, cutoff = features.snapshot_ready(db_session, class_id)
    assert ready and cutoff == date(2026, 11, 7)

    rows = features.extract_class(db_session, class_id, load_config(db_session), cutoff=cutoff)

    assert len(rows) == 40 and all(set(r) == set(FEATURE_NAMES) for r in rows.values())
    by_code = {
        code: rows[cs_id]
        for code, cs_id in db_session.execute(
            select(Student.student_code, ClassStudent.id)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .where(ClassStudent.class_id == class_id)
        )
    }
    toan_3 = by_code["HS1102002"]  # mọi đầu điểm Toán bằng 3,0
    assert toan_3["tx_min_subject"] == 3.0 and toan_3["gk_min"] == 3.0
    assert toan_3["n_tx_below_pass"] >= 1 and toan_3["n_gk_below_pass"] >= 1
    an = by_code["HS1102001"]
    # Em An nghỉ 38 buổi cả năm; tới giữa kỳ I chỉ một phần (số tính độc lập bằng SQL).
    expected = db_session.scalar(
        select(func.count())
        .select_from(Attendance)
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .join(Student, Student.id == ClassStudent.student_id)
        .where(
            Student.student_code == "HS1102001",
            Attendance.date <= cutoff,
            Attendance.status.in_((S.ABSENT_EXCUSED, S.ABSENT_UNEXCUSED)),
        )
    )
    assert an["absent_total"] == expected and 0 < expected < 38


@pytest.mark.db
def test_a_class_not_yet_at_mid_semester_one_has_no_snapshot(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    class_id = class_id_of("11A2")
    db_session.execute(
        delete(Attendance).where(
            Attendance.date > date(2026, 10, 30),
            Attendance.class_student_id.in_(
                select(ClassStudent.id).where(ClassStudent.class_id == class_id)
            ),
        )
    )

    ready, _ = features.snapshot_ready(db_session, class_id)

    assert ready is False


# --- Mô hình đã lưu ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def predictor() -> ForestPredictor:
    loaded = load_predictor()
    assert isinstance(loaded, ForestPredictor), "Thiếu mô hình: chạy make train"
    return loaded


def metadata_file() -> dict[str, object]:
    [path] = sorted(model.MODELS_DIR.glob("early-warning-*.json"))
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_the_committed_model_meets_the_recall_target_on_the_held_out_test_set() -> None:
    meta = metadata_file()

    assert meta["test_recall"] >= meta["recall_target"] == 0.75  # type: ignore[operator]
    thresholds = meta["thresholds"]
    assert 0 < thresholds["medium"] <= thresholds["high"] < 1  # type: ignore[index,operator]
    names = [f["name"] for f in meta["features"]]  # type: ignore[attr-defined]
    assert names == list(FEATURE_NAMES)
    data = meta["data"]
    assert data["test_positives"] > 100  # type: ignore[index,operator]
    assert 2026 not in data["seeds"]  # type: ignore[index,operator]


def good_student() -> dict[str, float]:
    return {
        "tx_mean": 8.6,
        "tx_min_subject": 7.5,
        "n_tx_below_pass": 0,
        "gk_mean": 8.4,
        "gk_min": 7.0,
        "n_gk_below_pass": 0,
        "absent_total": 0,
        "absent_last_4_weeks": 0,
        "late_total": 0,
    }


def struggling_student() -> dict[str, float]:
    return {
        "tx_mean": 4.2,
        "tx_min_subject": 2.5,
        "n_tx_below_pass": 6,
        "gk_mean": 4.0,
        "gk_min": 2.0,
        "n_gk_below_pass": 6,
        "absent_total": 12,
        "absent_last_4_weeks": 6,
        "late_total": 3,
    }


def test_a_clearly_fine_student_is_low_and_a_clearly_struggling_one_is_high(
    predictor: ForestPredictor,
) -> None:
    result = predictor.predict_rows({1: good_student(), 2: struggling_student()})

    assert result[1].level is RiskLevel.LOW and result[1].probability < predictor.medium
    assert result[2].level is RiskLevel.HIGH and result[2].probability >= predictor.high
    assert 0 <= result[1].probability <= 1 and 0 <= result[2].probability <= 1


def test_the_explanation_gives_at_most_three_factors_that_raise_the_risk(
    predictor: ForestPredictor,
) -> None:
    prediction = predictor.predict_rows({1: struggling_student()})[1]

    factors = prediction.factors
    assert 1 <= len(factors) <= 3
    assert all(f.contribution > 0 for f in factors)
    assert [f.contribution for f in factors] == sorted(
        (f.contribution for f in factors), reverse=True
    )
    assert {f.feature for f in factors} <= set(FEATURE_NAMES)
    assert all(f.message and f.label for f in factors)
    assert prediction.version == predictor.version


def test_a_student_with_nothing_worrying_has_no_factor_to_show(
    predictor: ForestPredictor,
) -> None:
    prediction = predictor.predict_rows({1: good_student()})[1]

    assert prediction.factors == ()


def test_levels_follow_the_two_thresholds(predictor: ForestPredictor) -> None:
    assert predictor.level_for(predictor.high) is RiskLevel.HIGH
    assert predictor.level_for(predictor.medium) is RiskLevel.MEDIUM
    assert predictor.level_for(predictor.medium - 0.001) is RiskLevel.LOW
    assert predictor.level_for(1.0) is RiskLevel.HIGH and predictor.level_for(0.0) is RiskLevel.LOW


def test_the_local_explanation_is_the_drop_when_a_feature_goes_back_to_the_median(
    predictor: ForestPredictor,
) -> None:
    row = struggling_student()
    names = predictor.names
    matrix = np.array([[row[n] for n in names]], dtype=float)
    base = predictor.model.predict_proba(matrix)[:, 1]

    contribution = predictor.explain(matrix, base)[0]

    for j, name in enumerate(names):
        replaced = matrix.copy()
        replaced[0, j] = predictor.medians[j]
        expected = base[0] - predictor.model.predict_proba(replaced)[0, 1]
        assert contribution[j] == pytest.approx(expected), name


def test_no_row_means_no_prediction(predictor: ForestPredictor) -> None:
    assert predictor.predict_rows({}) == {}


# --- Ghép với dịch vụ cảnh báo trên dữ liệu seed -------------------------------------------------


@pytest.mark.db
def test_the_service_merges_rules_and_model(
    db_session: Session, class_id_of: Callable[[str], int], predictor: ForestPredictor
) -> None:
    class_id = class_id_of("11A2")

    first = service.refresh_class(db_session, class_id, predictor=predictor)
    again = service.refresh_class(db_session, class_id, predictor=predictor)

    assert first.inserted == 40 and (again.inserted, again.unchanged) == (0, 40)  # tất định
    alerts = {r.student_code: r.alert for r in repo.current_alerts(db_session, class_id=class_id)}
    toan_3 = alerts["HS1102002"]
    assert toan_3.level is RiskLevel.HIGH and toan_3.model_version == predictor.version
    assert float(toan_3.risk_score) >= predictor.high  # type: ignore[arg-type]
    assert toan_3.reasons["model"]["version"] == predictor.version
    assert 1 <= len(toan_3.reasons["model"]["factors"]) <= 3
    assert all(a.risk_score is not None for a in alerts.values())
    # Mức cuối là mức cao nhất giữa luật và mô hình: em An nghỉ 38 buổi (luật Trung bình) và xác
    # suất của mô hình dưới ngưỡng Trung bình nên vẫn là Trung bình.
    an = alerts["HS1102001"]
    assert an.level is RiskLevel.MEDIUM
    assert float(an.risk_score) < predictor.medium  # type: ignore[arg-type]


@pytest.mark.db
def test_before_mid_semester_one_only_the_rules_run(
    db_session: Session, class_id_of: Callable[[str], int], predictor: ForestPredictor
) -> None:
    class_id = class_id_of("11A2")
    db_session.execute(
        delete(Attendance).where(
            Attendance.date > date(2026, 10, 30),
            Attendance.class_student_id.in_(
                select(ClassStudent.id).where(ClassStudent.class_id == class_id)
            ),
        )
    )

    service.refresh_class(db_session, class_id, predictor=predictor)

    rows = list(db_session.scalars(select(RiskAlert)))
    assert len(rows) == 40 and all(r.risk_score is None and r.model_version is None for r in rows)


# --- Đường lùi: thiếu hoặc hỏng mô hình ----------------------------------------------------------


def test_without_a_model_file_there_is_no_predictor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(model, "MODELS_DIR", tmp_path)
    model._load.cache_clear()
    try:
        assert load_predictor() is None
    finally:
        model._load.cache_clear()


def test_a_corrupt_model_file_is_ignored_and_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "early-warning-rf-xxxx.joblib").write_bytes(b"khong phai mo hinh")
    (tmp_path / "early-warning-rf-xxxx.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(model, "MODELS_DIR", tmp_path)
    model._load.cache_clear()
    try:
        with caplog.at_level(logging.ERROR, logger="app.warning.model"):
            assert load_predictor() is None
        assert any("Không nạp được mô hình" in r.getMessage() for r in caplog.records)
    finally:
        model._load.cache_clear()


@pytest.mark.db
def test_the_warning_still_runs_with_rules_only_when_there_is_no_model(
    db_session: Session, class_id_of: Callable[[str], int]
) -> None:
    result = service.refresh_class(db_session, class_id_of("11A2"), predictor=None)

    assert result.inserted == 40
    assert all(a.risk_score is None for a in db_session.scalars(select(RiskAlert)))

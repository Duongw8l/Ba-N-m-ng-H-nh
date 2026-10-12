"""Huấn luyện: chọn ngưỡng tính tay, quy trình trên dữ liệu tổng hợp, một khoá thật (D-072)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sqlalchemy import Engine

import ml.train as train_module
from app.warning.features import FEATURE_NAMES
from ml.cohorts import DEMO_SEED, collect, collect_cohort
from ml.train import pick_thresholds, train, write_artifacts, write_report

# --- Chọn ngưỡng (tính tay) ----------------------------------------------------------------------


def test_thresholds_are_picked_from_recall_and_precision_on_the_training_folds() -> None:
    # 10 dương tính có xác suất 0,50 đến 0,95; 90 âm tính có xác suất 0,01 đến 0,45.
    positives = np.linspace(0.50, 0.95, 10)
    negatives = np.linspace(0.01, 0.45, 90)
    proba = np.concatenate([positives, negatives])
    labels = np.concatenate([np.ones(10, dtype=int), np.zeros(90, dtype=int)])

    medium, high = pick_thresholds(labels, proba)

    # Recall >= 0,90 nghĩa là bắt được ít nhất 9/10 dương tính: ngưỡng lớn nhất còn thoả là 0,55.
    assert medium == pytest.approx(0.55)
    assert medium <= high <= 0.95
    # Từ 0,55 không âm tính nào vượt (cao nhất 0,45): Precision đã đạt 1, ngưỡng Cao = Trung bình.
    assert high == pytest.approx(medium)


def test_when_no_threshold_reaches_the_precision_target_high_sits_between_medium_and_one() -> None:
    # Dương tính và âm tính trộn lẫn hoàn toàn: Precision không bao giờ đạt 0,95.
    proba = np.tile(np.linspace(0.05, 0.95, 10), 10)
    labels = np.tile(np.array([1, 0] * 5), 10)

    medium, high = pick_thresholds(labels, proba)

    assert medium < high < 1.0
    assert high == pytest.approx(min(0.95, medium + (1 - medium) / 2))


# --- Quy trình trên dữ liệu tổng hợp ---------------------------------------------------------


def synthetic_rows(n: int = 1200) -> list[dict[str, Any]]:
    rng = np.random.default_rng(7)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        tx_min = float(rng.uniform(2, 9))
        gk_min = float(np.clip(tx_min + rng.normal(0, 0.8), 1, 10))
        absent = float(rng.integers(0, 15))
        row = {
            "cohort": 1,
            "student_code": f"HS{i:04d}",
            "grade": 10,
            "tx_mean": float(np.clip(tx_min + rng.uniform(0.5, 2.5), 0, 10)),
            "tx_min_subject": tx_min,
            "n_tx_below_pass": float(int(tx_min < 5) * rng.integers(1, 5)),
            "gk_mean": float(np.clip(gk_min + rng.uniform(0.5, 2.0), 0, 10)),
            "gk_min": gk_min,
            "n_gk_below_pass": float(int(gk_min < 5) * rng.integers(1, 5)),
            "absent_total": absent,
            "absent_last_4_weeks": float(min(absent, rng.integers(0, 6))),
            "late_total": float(rng.integers(0, 4)),
        }
        row["label"] = int(tx_min < 4.0 or gk_min < 3.5)
        rows.append(row)
    return rows


@pytest.fixture(scope="module")
def trained() -> dict[str, Any]:
    return train(synthetic_rows())


def test_training_gives_both_models_a_threshold_and_a_report_of_the_test_set(
    trained: dict[str, Any],
) -> None:
    meta = trained["metadata"]

    assert set(meta["metrics"]) == {"logistic_regression", "random_forest"}
    for name, result in meta["metrics"].items():
        for key in ("test_at_medium", "test_at_0.5", "train_cv_at_medium"):
            m = result[key]
            assert 0 <= m["recall"] <= 1 and 0 <= m["precision"] <= 1, (name, key)
            assert m["tp"] + m["fn"] > 0 and m["tp"] + m["fp"] + m["fn"] + m["tn"] > 0
    assert meta["thresholds"]["medium"] <= meta["thresholds"]["high"]
    assert meta["data"]["train"] + meta["data"]["test"] == 1200
    assert meta["data"]["test"] == 240  # 20%
    assert [f["name"] for f in meta["features"]] == list(FEATURE_NAMES)
    assert set(meta["medians"]) == set(FEATURE_NAMES)
    # Quy luật đơn giản của dữ liệu tổng hợp thì mô hình chính học được.
    assert meta["test_recall"] >= 0.75


def test_the_split_keeps_every_student_in_only_one_side(trained: dict[str, Any]) -> None:
    data = trained["metadata"]["data"]

    assert data["train"] == 960 and data["test"] == 240
    assert data["test_positives"] > 0


def test_artifacts_keep_only_the_latest_model_and_the_report_says_pass_or_fail(
    trained: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(train_module, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(train_module, "REPORT_PATH", tmp_path / "REPORT.md")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "early-warning-rf-cu.joblib").write_bytes(b"cu")

    path = write_artifacts(trained["model"], trained["metadata"])
    write_report(trained["metadata"])

    files = sorted(p.name for p in (tmp_path / "models").iterdir())
    assert files == [path.name, path.with_suffix(".json").name]  # bản cũ đã bị xoá
    saved = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert saved["version"] == trained["metadata"]["version"]
    report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "Recall" in report and "Precision" in report and "F1" in report
    assert "Logistic Regression" in report and "Random Forest" in report
    assert "ĐẠT" in report and "chưa chứng minh" in report  # nói rõ giới hạn của dữ liệu tự sinh


# --- Một khoá thật ---------------------------------------------------------------------------


def test_the_demo_seed_is_never_used_for_training() -> None:
    with pytest.raises(ValueError, match="2026"):
        collect([1, DEMO_SEED])


@pytest.mark.db
def test_one_real_cohort_gives_features_and_labels_for_every_student(
    fresh_database: Callable[[], Engine], upgrade_db: Callable[[Engine], None]
) -> None:
    engine = fresh_database()
    upgrade_db(engine)

    rows = collect_cohort(engine, 1)

    assert len(rows) == 360  # mọi học sinh của khoá có đặc trưng và nhãn
    assert {r["cohort"] for r in rows} == {1}
    assert {r["grade"] for r in rows} == {10, 11, 12}
    assert all(set(FEATURE_NAMES) <= set(r) for r in rows)
    positives = sum(r["label"] for r in rows)
    assert 0.03 * 360 < positives < 0.25 * 360  # vài chục em Chưa đạt cả năm
    codes = [(r["grade"], r["student_code"]) for r in rows]
    assert len(set(codes)) == 360

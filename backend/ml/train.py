"""Huấn luyện mô hình dự báo nguy cơ "Chưa đạt cả năm" từ giữa học kỳ I (DESIGN mục 6.2, D-072).

Chạy bằng `make train` (vài phút, cần PostgreSQL đang chạy: dùng một database tạm). Việc làm:
1. Dựng dữ liệu từ nhiều khoá giả lập (ml/cohorts.py), không dùng seed 2026 của DB demo.
2. Chia 80/20 theo học sinh (mỗi dòng là một học sinh), tập test chỉ dùng MỘT lần ở cuối.
3. Logistic Regression làm mốc, Random Forest làm mô hình chính (CPU).
4. Ngưỡng Trung bình/Cao chọn bằng cross-validation TRÊN TẬP TRAIN (ưu tiên Recall), không nhìn test.
5. Ghi mô hình, metadata và báo cáo (backend/ml/models/, backend/ml/REPORT.md).

Mục tiêu Recall >= 0,75 trên tập test. Không đạt thì báo cáo đúng kết quả; không chỉnh dữ liệu test.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.warning.features import FEATURE_NAMES, FEATURES, SNAPSHOT_WEEKS, TREND_WEEKS
from ml.cohorts import DEMO_SEED, collect

MODELS_DIR = Path(__file__).resolve().parent / "models"
REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"
SEEDS = tuple(seed for seed in range(1, 21) if seed != DEMO_SEED)  # 20 khoá x 360 học sinh
RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
# Ngưỡng Trung bình: lớn nhất mà Recall (trên CV của tập train) vẫn >= mức này (ưu tiên Recall).
RECALL_FOR_MEDIUM = 0.90
# Ngưỡng Cao: nhỏ nhất (từ ngưỡng Trung bình) mà Precision (trên CV của tập train) >= mức này.
PRECISION_FOR_HIGH = 0.95
RECALL_TARGET = 0.75  # tiêu chí của PROMPTS Giai đoạn 6 / DESIGN mục 12


def vn(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def pick_thresholds(y_true: np.ndarray, proba: np.ndarray) -> tuple[float, float]:
    """(ngưỡng Trung bình, ngưỡng Cao) từ xác suất cross-validation của tập train."""
    candidates = np.round(np.arange(0.05, 0.96, 0.01), 2)
    recall = {t: recall_score(y_true, proba >= t, zero_division=0) for t in candidates}
    precision = {t: precision_score(y_true, proba >= t, zero_division=0) for t in candidates}

    eligible = [t for t in candidates if recall[t] >= RECALL_FOR_MEDIUM]
    medium = float(max(eligible)) if eligible else float(min(candidates))
    high_candidates = [t for t in candidates if t >= medium and precision[t] >= PRECISION_FOR_HIGH]
    high = float(min(high_candidates)) if high_candidates else min(0.95, medium + (1 - medium) / 2)
    return medium, max(high, medium)


def metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = proba >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "average_precision": float(average_precision_score(y_true, proba)),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
    }


def build_models() -> dict[str, Any]:
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def train(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Huấn luyện và đánh giá; trả mô hình chính, metadata và số liệu."""
    frame = pd.DataFrame(rows)
    x = frame[list(FEATURE_NAMES)].to_numpy(dtype=float)
    y = frame["label"].to_numpy(dtype=int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    results: dict[str, dict[str, Any]] = {}
    fitted: dict[str, Any] = {}
    for name, model in build_models().items():
        cv_proba = cross_val_predict(model, x_train, y_train, cv=folds, method="predict_proba")[
            :, 1
        ]
        medium, high = pick_thresholds(y_train, cv_proba)
        model.fit(x_train, y_train)
        test_proba = model.predict_proba(x_test)[:, 1]
        results[name] = {
            "thresholds": {"medium": medium, "high": high},
            "test_at_medium": metrics(y_test, test_proba, medium),
            "test_at_0.5": metrics(y_test, test_proba, 0.5),
            "train_cv_at_medium": metrics(y_train, cv_proba, medium),
        }
        fitted[name] = model

    forest = fitted["random_forest"]
    importances = sorted(
        zip(FEATURE_NAMES, forest.feature_importances_, strict=True), key=lambda p: -p[1]
    )
    version = f"rf-{datetime.now(UTC):%Y%m%d}"
    metadata = {
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": "RandomForestClassifier",
        "sklearn_version": sklearn.__version__,
        "snapshot_weeks": SNAPSHOT_WEEKS,
        "trend_weeks": TREND_WEEKS,
        "features": [{"name": spec.name, "label": spec.label} for spec in FEATURES],
        "medians": {name: float(np.median(x_train[:, i])) for i, name in enumerate(FEATURE_NAMES)},
        "thresholds": results["random_forest"]["thresholds"],
        "data": {
            "cohorts": len(SEEDS),
            "seeds": list(SEEDS),
            "students": int(len(frame)),
            "positives": int(y.sum()),
            "train": int(len(y_train)),
            "test": int(len(y_test)),
            "test_positives": int(y_test.sum()),
            "source": "dữ liệu giả lập sinh bằng data/seed (không dùng UCI, không dùng seed 2026)",
        },
        "metrics": results,
        "recall_target": RECALL_TARGET,
        "test_recall": results["random_forest"]["test_at_medium"]["recall"],
        "feature_importances": [{"feature": n, "importance": float(v)} for n, v in importances],
    }
    return {"model": forest, "metadata": metadata}


def write_artifacts(model: Any, metadata: dict[str, Any]) -> Path:
    """Ghi mô hình và metadata, xoá các phiên bản cũ để chỉ còn một mô hình hiện hành."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for old in MODELS_DIR.glob("early-warning-*"):
        old.unlink()
    path = MODELS_DIR / f"early-warning-{metadata['version']}.joblib"
    joblib.dump(model, path, compress=3)
    (MODELS_DIR / f"early-warning-{metadata['version']}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def metric_row(name: str, m: dict[str, Any]) -> str:
    return (
        f"| {name} | {vn(m['threshold'])} | {vn(m['recall'])} | {vn(m['precision'])} | "
        f"{vn(m['f1'])} | {vn(m['roc_auc'], 3)} | {vn(m['average_precision'], 3)} |"
    )


def write_report(metadata: dict[str, Any]) -> None:
    data = metadata["data"]
    rf = metadata["metrics"]["random_forest"]
    lr = metadata["metrics"]["logistic_regression"]
    main = rf["test_at_medium"]
    verdict = "ĐẠT" if main["recall"] >= RECALL_TARGET else "KHÔNG ĐẠT"
    lines = [
        "# Báo cáo mô hình cảnh báo sớm",
        "",
        f"Tạo tự động bởi `make train` lúc {metadata['trained_at']} (phiên bản `{metadata['version']}`, "
        f"scikit-learn {metadata['sklearn_version']}). **Đừng sửa tay**: chạy lại `make train` để cập nhật.",
        "",
        "## Mục tiêu",
        "",
        "Dự báo học sinh có nguy cơ kết quả học tập cả năm **Chưa đạt** từ dữ liệu **giữa học kỳ I** "
        "(sớm hơn các luật cứng), để giáo viên chủ nhiệm hỗ trợ sớm. Mô hình chỉ là gợi ý: mức cảnh báo "
        "cuối cùng gộp với lớp luật, và giáo viên quyết định.",
        "",
        "## Dữ liệu",
        "",
        f"- **{data['cohorts']} khoá giả lập** × 360 học sinh = **{data['students']}** học sinh, sinh bằng "
        "chính bộ sinh của seed (`data/seed/`) với các số ngẫu nhiên khác nhau; không dùng seed 2026 của DB "
        "demo nên học sinh demo là dữ liệu chưa từng thấy.",
        f"- Nhãn: kết quả học tập cả năm Chưa đạt, do `analytics/` tính. **{data['positives']}** học sinh "
        f"dương tính ({vn(100 * data['positives'] / data['students'], 1)}%).",
        f"- Chia {int((1 - TEST_SIZE) * 100)}/{int(TEST_SIZE * 100)} theo học sinh (phân tầng theo nhãn): "
        f"train {data['train']}, test {data['test']} (dương tính trong test: {data['test_positives']}). "
        "Tập test chỉ dùng một lần ở cuối.",
        "- **Không dùng UCI Student Performance** (chưa có `data/external/`, và thang điểm 0 đến 20 của Bồ Đào "
        "Nha khó ánh xạ sang Thông tư 22).",
        "",
        "## Đặc trưng (chụp tại giữa học kỳ I)",
        "",
        f"Ngày cắt là `start_date + {metadata['snapshot_weeks']} tuần` của năm học. Chỉ dùng điểm và chuyên cần; "
        "**không** dùng giới tính, dân tộc, nơi ở, hoàn cảnh gia đình (DESIGN mục 10).",
        "",
        "| Đặc trưng | Ý nghĩa |",
        "| --- | --- |",
        *[f"| `{f['name']}` | {f['label']} |" for f in metadata["features"]],
        "",
        "Không có: kết quả năm trước và rèn luyện kỳ trước (DB chỉ có một năm học), xu hướng điểm theo thời "
        'gian (điểm không có ngày). Với điểm không có ngày, "đã có tới giữa kỳ I" được xấp xỉ bằng toàn bộ '
        "đầu điểm thường xuyên và điểm giữa kỳ của học kỳ I.",
        "",
        "## Kết quả trên tập test",
        "",
        "Ngưỡng của từng mô hình chọn bằng cross-validation trên tập train: lớn nhất mà Recall >= "
        f"{vn(RECALL_FOR_MEDIUM)}. Các cột Recall, Precision, F1 là của lớp dương tính (Chưa đạt cả năm).",
        "",
        "| Mô hình | Ngưỡng | Recall | Precision | F1 | ROC-AUC | AP |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        metric_row("Logistic Regression (mốc)", lr["test_at_medium"]),
        metric_row("**Random Forest (chính)**", main),
        "",
        "Cùng hai mô hình ở ngưỡng mặc định 0,5 (để tham khảo):",
        "",
        "| Mô hình | Ngưỡng | Recall | Precision | F1 | ROC-AUC | AP |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        metric_row("Logistic Regression", lr["test_at_0.5"]),
        metric_row("Random Forest", rf["test_at_0.5"]),
        "",
        f"**Tiêu chí Recall >= {vn(RECALL_TARGET)} của mô hình chính: {verdict}** "
        f"(Recall {vn(main['recall'])}).",
        "",
        f"Ma trận nhầm lẫn của Random Forest trên tập test (ngưỡng {vn(main['threshold'])}):",
        "",
        "| | Dự báo Chưa đạt | Dự báo không |",
        "| --- | --- | --- |",
        f"| **Thực tế Chưa đạt** | {main['tp']} | {main['fn']} |",
        f"| **Thực tế không** | {main['fp']} | {main['tn']} |",
        "",
        "## Ngưỡng chuyển xác suất thành mức",
        "",
        f"- Trung bình: xác suất >= {vn(metadata['thresholds']['medium'])}",
        f"- Cao: xác suất >= {vn(metadata['thresholds']['high'])} (nhỏ nhất, từ ngưỡng Trung bình, mà "
        f"Precision trên CV của train >= {vn(PRECISION_FOR_HIGH)}; nếu không có thì lấy điểm giữa ngưỡng "
        "Trung bình và 1)",
        "",
        "## Đặc trưng quan trọng (Random Forest, độ giảm tạp chất)",
        "",
        "| Đặc trưng | Tầm quan trọng |",
        "| --- | --- |",
        *[
            f"| `{item['feature']}` | {vn(item['importance'], 3)} |"
            for item in metadata["feature_importances"]
        ],
        "",
        "Giải thích cho từng học sinh dùng đóng góp cục bộ: với mỗi đặc trưng, mức xác suất giảm khi thay giá "
        "trị của em bằng trung vị của tập huấn luyện; lấy ba đặc trưng lớn nhất (`app/warning/model.py`).",
        "",
        "## Giới hạn (đọc trước khi tin các con số)",
        "",
        '1. **Dữ liệu tự sinh.** Nhãn và đặc trưng cùng do một bộ sinh tạo ra từ "năng lực" và số buổi nghỉ của '
        "từng em, nên mô hình chủ yếu học lại cách bộ sinh tạo số. Recall cao ở đây **chưa chứng minh** mô hình "
        "dùng được với dữ liệu thật; cần thử lại bằng dữ liệu thật đã ẩn danh của một trường.",
        "2. **Một thời điểm duy nhất** (giữa học kỳ I). Sau thời điểm đó phần ML không đổi theo dữ liệu mới; "
        "lớp luật cứng mới là phần cập nhật.",
        f"3. **Ít dương tính** ({vn(100 * data['positives'] / data['students'], 1)}%): Recall trên tập test "
        "dao động theo cách chia; số trên là một lần chia.",
        "",
        "## Cách cải thiện",
        "",
        "- Thêm dữ liệu thật đã ẩn danh (hoặc UCI sau khi ánh xạ thang điểm) và đặc trưng năm trước, rèn luyện kỳ "
        "trước khi nhà trường có.",
        "- Huấn luyện thêm các thời điểm khác (cuối học kỳ I, giữa học kỳ II) nếu điểm có ngày.",
        '- Dùng phản hồi "báo nhầm" của giáo viên (lưu trong `risk_alerts.teacher_status`) để đánh giá lại ngưỡng.',
        "",
        "## Chạy lại",
        "",
        "```bash",
        "make db && make migrate",
        "make train   # vài phút; ghi backend/ml/models/ và file này",
        "make warn    # tính lại cảnh báo cho cả trường với mô hình mới",
        "```",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "cohorts.pkl"  # bị .gitignore chặn


def load_rows(use_cache: bool) -> list[dict[str, Any]]:
    if use_cache and CACHE_PATH.exists():
        print(f"Dùng dữ liệu đã lưu ở ml/.cache/{CACHE_PATH.name} (--cache).", flush=True)
        return joblib.load(CACHE_PATH)  # type: ignore[no-any-return]
    print(f"Dựng dữ liệu từ {len(SEEDS)} khoá giả lập (có thể mất vài phút)…", flush=True)
    rows = collect(SEEDS)
    if use_cache:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(rows, CACHE_PATH)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(
        prog="make train", description="Huấn luyện mô hình cảnh báo sớm."
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="lưu và dùng lại dữ liệu các khoá ở ml/.cache để thử nhanh khi chỉ đổi mô hình hoặc ngưỡng",
    )
    args = parser.parse_args(argv)
    rows = load_rows(args.cache)
    print(f"Huấn luyện trên {len(rows)} học sinh…", flush=True)
    outcome = train(rows)
    path = write_artifacts(outcome["model"], outcome["metadata"])
    write_report(outcome["metadata"])
    main_metrics = outcome["metadata"]["metrics"]["random_forest"]["test_at_medium"]
    print(
        f"Xong: {path.name}. Recall trên tập test {vn(main_metrics['recall'])} "
        f"(mục tiêu >= {vn(RECALL_TARGET)}), Precision {vn(main_metrics['precision'])}, "
        f"F1 {vn(main_metrics['f1'])}. Báo cáo: ml/REPORT.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

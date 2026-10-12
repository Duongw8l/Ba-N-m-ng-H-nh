"""Lớp ML của cảnh báo sớm: nạp mô hình đã huấn luyện, dự đoán và giải thích (D-072).

Chỗ này chỉ DÙNG mô hình đã lưu (backend/ml/models/); huấn luyện ở backend/ml/train.py, đặc trưng ở
features.py (dùng chung nên không lệch). Thiếu tệp mô hình hoặc nạp lỗi (ví dụ lệch phiên bản
scikit-learn) thì `load_predictor()` trả None và hệ thống chạy tiếp bằng lớp luật.

Giải thích cho từng học sinh: với mỗi đặc trưng, đo mức xác suất giảm khi thay giá trị của em bằng
trung vị của tập huấn luyện; ba đặc trưng đóng góp lớn nhất (làm tăng nguy cơ) là "ba yếu tố".
Không cần thư viện ngoài scikit-learn.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
import sklearn
from sqlalchemy.orm import Session

from app.analytics.config import AnalyticsConfig
from app.analytics.repository import ClassInfo
from app.core.enums import RiskLevel
from app.warning import features

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
TOP_FACTORS = 3


@dataclass(frozen=True)
class Factor:
    """Một đặc trưng đóng góp vào xác suất của một học sinh."""

    feature: str
    label: str
    value: float
    contribution: float  # mức xác suất giảm khi thay bằng trung vị tập huấn luyện
    message: str

    def to_json(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "label": self.label,
            "value": round(self.value, 2),
            "contribution": round(self.contribution, 4),
            "message": self.message,
        }


@dataclass(frozen=True)
class Prediction:
    version: str
    probability: float  # xác suất "Chưa đạt cả năm", 0 đến 1
    level: RiskLevel  # mức do ngưỡng của mô hình quy ra (Thấp nếu dưới ngưỡng Trung bình)
    factors: tuple[Factor, ...]  # ba đặc trưng đóng góp nhiều nhất

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "probability": round(self.probability, 4),
            "factors": [factor.to_json() for factor in self.factors],
        }


class Predictor(Protocol):
    version: str

    def predict_class(
        self, session: Session, class_info: ClassInfo, config: AnalyticsConfig
    ) -> dict[int, Prediction]:
        """Dự đoán cho từng học sinh của lớp, khoá là class_student_id. Học sinh chưa đủ dữ liệu
        (lớp chưa tới ngày cắt "giữa học kỳ I", hoặc em chưa có điểm) không có trong kết quả."""
        ...


def _score(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _count(value: float) -> str:
    return str(round(value))


# Câu mô tả giá trị của học sinh cho từng đặc trưng; trung tính, không so sánh với bạn khác.
MESSAGES: dict[str, Callable[[float], str]] = {
    "tx_mean": lambda v: f"Điểm thường xuyên học kỳ I trung bình {_score(v)}",
    "tx_min_subject": lambda v: f"Có môn điểm thường xuyên học kỳ I chỉ đạt {_score(v)}",
    "n_tx_below_pass": lambda v: f"{_count(v)} môn có điểm thường xuyên học kỳ I dưới mức Đạt",
    "gk_mean": lambda v: f"Điểm giữa kỳ học kỳ I trung bình {_score(v)}",
    "gk_min": lambda v: f"Có môn điểm giữa kỳ học kỳ I chỉ đạt {_score(v)}",
    "n_gk_below_pass": lambda v: f"{_count(v)} môn có điểm giữa kỳ học kỳ I dưới mức Đạt",
    "absent_total": lambda v: f"Đã nghỉ {_count(v)} buổi tới giữa học kỳ I",
    "absent_last_4_weeks": lambda v: f"Nghỉ {_count(v)} buổi trong 4 tuần gần nhất",
    "late_total": lambda v: f"Đi muộn {_count(v)} buổi tới giữa học kỳ I",
}


class ForestPredictor:
    """Random Forest đã huấn luyện cùng metadata (đặc trưng, trung vị, ngưỡng)."""

    def __init__(self, model: Any, metadata: dict[str, Any]) -> None:
        model.set_params(n_jobs=1)  # máy chủ phục vụ nhiều yêu cầu: không tự chia luồng
        self.model = model
        self.metadata = metadata
        self.version: str = metadata["version"]
        self.names: list[str] = [item["name"] for item in metadata["features"]]
        self.labels = {item["name"]: item["label"] for item in metadata["features"]}
        self.medians = np.array([metadata["medians"][name] for name in self.names], dtype=float)
        self.medium: float = metadata["thresholds"]["medium"]
        self.high: float = metadata["thresholds"]["high"]
        if self.names != list(features.FEATURE_NAMES):
            raise ValueError("Danh sách đặc trưng của mô hình không khớp features.py")

    def level_for(self, probability: float) -> RiskLevel:
        if probability >= self.high:
            return RiskLevel.HIGH
        if probability >= self.medium:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def explain(self, matrix: np.ndarray, base: np.ndarray) -> np.ndarray:
        """Đóng góp cục bộ: base - xác suất khi thay từng đặc trưng bằng trung vị. Hình (n, m)."""
        n, m = matrix.shape
        stacked = np.repeat(matrix, m, axis=0).reshape(n, m, m).copy()
        for j in range(m):
            stacked[:, j, j] = self.medians[j]
        replaced = self.model.predict_proba(stacked.reshape(n * m, m))[:, 1].reshape(n, m)
        return base[:, None] - replaced

    def predict_rows(self, rows: dict[int, dict[str, float]]) -> dict[int, Prediction]:
        if not rows:
            return {}
        ids = list(rows)
        matrix = np.array([[rows[i][name] for name in self.names] for i in ids], dtype=float)
        probability = self.model.predict_proba(matrix)[:, 1]
        contribution = self.explain(matrix, probability)
        result: dict[int, Prediction] = {}
        for index, cs_id in enumerate(ids):
            order = np.argsort(-contribution[index])[:TOP_FACTORS]
            factors = tuple(
                Factor(
                    feature=self.names[j],
                    label=self.labels[self.names[j]],
                    value=float(matrix[index, j]),
                    contribution=float(contribution[index, j]),
                    message=MESSAGES[self.names[j]](float(matrix[index, j])),
                )
                for j in order
                if contribution[index, j] > 0  # chỉ các yếu tố làm TĂNG nguy cơ
            )
            p = float(probability[index])
            result[cs_id] = Prediction(self.version, p, self.level_for(p), factors)
        return result

    def predict_class(
        self, session: Session, class_info: ClassInfo, config: AnalyticsConfig
    ) -> dict[int, Prediction]:
        ready, cutoff = features.snapshot_ready(session, class_info.id)
        if not ready:
            return {}  # chưa tới giữa học kỳ I: chỉ có lớp luật
        return self.predict_rows(
            features.extract_class(session, class_info.id, config, cutoff=cutoff)
        )


@lru_cache(maxsize=1)
def _load(directory: str) -> ForestPredictor | None:
    models = sorted(Path(directory).glob("early-warning-*.joblib"))
    if not models:
        logger.info("Chưa có mô hình ML trong %s: cảnh báo chỉ dùng lớp luật.", directory)
        return None
    path = models[-1]
    try:
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if metadata.get("sklearn_version") != sklearn.__version__:
            logger.warning(
                "Mô hình huấn luyện bằng scikit-learn %s, đang chạy %s: có thể nạp lỗi.",
                metadata.get("sklearn_version"),
                sklearn.__version__,
            )
        return ForestPredictor(joblib.load(path), metadata)
    except Exception:  # noqa: BLE001 - mô hình hỏng không được làm hỏng cảnh báo
        logger.exception("Không nạp được mô hình %s: cảnh báo chỉ dùng lớp luật.", path.name)
        return None


def load_predictor() -> Predictor | None:
    """Mô hình đã lưu (nạp một lần), hoặc None nếu chưa có hoặc nạp lỗi."""
    return _load(str(MODELS_DIR))

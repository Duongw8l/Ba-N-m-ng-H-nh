"""Lớp luật cứng của cảnh báo sớm (DESIGN mục 6.2, D-071). Hàm thuần, không đụng DB.

Đầu vào là kết quả Analytics đã tính (mức học tập, môn dưới ngưỡng, số buổi nghỉ...); ở đây không có
công thức Thông tư 22. Mọi ngưỡng đọc từ AnalyticsConfig (bảng settings), riêng số môn nhận xét Chưa
đạt tối đa của mức Đạt lấy từ analytics.learning (số của Thông tư chỉ nằm trong analytics/).

Mỗi luật trả mã, mức và một câu tiếng Việt kèm số liệu. Theo D-048, các câu chỉ nêu số liệu: không
khẳng định "không thể đạt mức Đạt" vì mức cuối cùng do Analytics tính (có điều chỉnh mức).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.analytics.config import AnalyticsConfig
from app.analytics.learning import MAX_FAILED_COMMENTS_FOR_PASS, LearningResult
from app.analytics.promotion import RetakeReason, RetakeSubject
from app.core.enums import ConductLevel, LearningLevel, RiskLevel

LEVEL_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
PERIOD_NAMES = {"1": "học kỳ I", "2": "học kỳ II"}


def worst(levels: Sequence[RiskLevel]) -> RiskLevel:
    """Mức cao nhất trong danh sách; danh sách rỗng là mức Thấp."""
    return max(levels, key=LEVEL_ORDER.__getitem__, default=RiskLevel.LOW)


@dataclass(frozen=True)
class RuleHit:
    code: str
    level: RiskLevel
    message: str
    data: dict[str, Any] = field(default_factory=dict)  # số liệu của câu, để giao diện và LLM dùng


@dataclass(frozen=True)
class RuleInput:
    """Những gì luật cần biết về một học sinh. Mọi số liệu đều từ Analytics."""

    grade_level: int
    period: str  # kỳ của kết quả học tập: "1" hoặc "2"
    absent_sessions: int  # số buổi nghỉ tích luỹ trong năm học (có phép và không phép)
    learning: LearningResult  # kết quả học tập của `period`
    subject_names: Mapping[int, str]  # id môn -> tên môn
    subject_averages: Mapping[int, Decimal]  # id môn điểm số -> ĐTB của `period`
    conduct_hk1: ConductLevel | None
    retake_subjects: Sequence[RetakeSubject] = ()  # môn có thể kiểm tra lại (kết quả cả năm)
    exam_subject_ids: Sequence[int] = ()  # khối 12: các môn đăng ký thi tốt nghiệp


def score_vn(value: Decimal) -> str:
    """Điểm luôn có một chữ số thập phân: 3 thành "3,0"."""
    return f"{value:.1f}".replace(".", ",")


def _names(ids: Sequence[int], names: Mapping[int, str]) -> list[str]:
    return [names.get(subject_id, f"môn {subject_id}") for subject_id in ids]


def _absence(rule: RuleInput, config: AnalyticsConfig) -> list[RuleHit]:
    n = rule.absent_sessions
    data = {
        "absent_sessions": n,
        "notice": config.absent_warning_notice,
        "high": config.absent_warning_high,
        "maximum": config.max_absent_sessions,
    }
    if n > config.max_absent_sessions:
        message = (
            f"Đã nghỉ {n} buổi trong năm học, vượt mức tối đa {config.max_absent_sessions} buổi."
        )
        return [RuleHit("absent_over_limit", RiskLevel.HIGH, message, data)]
    if n >= config.absent_warning_high:
        message = (
            f"Đã nghỉ {n} buổi trong năm học, gần mức tối đa {config.max_absent_sessions} buổi "
            f"(từ {config.absent_warning_high} buổi trở lên cần chú ý nhiều)."
        )
        return [RuleHit("absent_high", RiskLevel.HIGH, message, data)]
    if n >= config.absent_warning_notice:
        message = (
            f"Đã nghỉ {n} buổi trong năm học (từ {config.absent_warning_notice} buổi trở lên "
            "cần nhắc)."
        )
        return [RuleHit("absent_notice", RiskLevel.MEDIUM, message, data)]
    return []


def _learning(rule: RuleInput, config: AnalyticsConfig) -> list[RuleHit]:
    hits: list[RuleHit] = []
    learning = rule.learning
    period = PERIOD_NAMES[rule.period]

    if learning.level is LearningLevel.FAIL:
        hits.append(
            RuleHit(
                "level_fail",
                RiskLevel.HIGH,
                f"Kết quả học tập {period} đang ở mức Chưa đạt.",
                {"period": rule.period},
            )
        )

    if learning.below_fail_subjects:
        parts = [
            f"{rule.subject_names.get(i, f'môn {i}')} ({score_vn(rule.subject_averages[i])})"
            for i in learning.below_fail_subjects
            if i in rule.subject_averages
        ]
        hits.append(
            RuleHit(
                "subject_below_fail",
                RiskLevel.MEDIUM,
                f"Có {len(learning.below_fail_subjects)} môn ĐTB {period} dưới "
                f"{score_vn(config.score_threshold_fail)}: {', '.join(parts)}.",
                {
                    "subjects": _names(learning.below_fail_subjects, rule.subject_names),
                    "threshold": float(config.score_threshold_fail),
                },
            )
        )

    # Thiếu dữ liệu ở môn nào đó thì số môn đạt chưa đầy đủ: chưa kết luận.
    if learning.level is not None and learning.count_pass < config.level_min_subjects:
        hits.append(
            RuleHit(
                "few_subjects_pass",
                RiskLevel.MEDIUM,
                f"Chỉ có {learning.count_pass} môn điểm số đạt từ "
                f"{score_vn(config.score_threshold_pass)} trong {period}; mức Đạt cần ít nhất "
                f"{config.level_min_subjects} môn.",
                {
                    "count_pass": learning.count_pass,
                    "minimum": config.level_min_subjects,
                    "threshold": float(config.score_threshold_pass),
                },
            )
        )

    if len(learning.failed_comment_subjects) > MAX_FAILED_COMMENTS_FOR_PASS:
        names = _names(learning.failed_comment_subjects, rule.subject_names)
        hits.append(
            RuleHit(
                "comment_fail_2plus",
                RiskLevel.MEDIUM,
                f"Có {len(names)} môn nhận xét Chưa đạt trong {period}: {', '.join(names)}.",
                {"subjects": names},
            )
        )
    return hits


def _conduct(rule: RuleInput) -> list[RuleHit]:
    if rule.conduct_hk1 is ConductLevel.FAIL:
        return [
            RuleHit(
                "conduct_hk1_fail",
                RiskLevel.MEDIUM,
                "Rèn luyện học kỳ I xếp Chưa đạt; cần giáo viên chủ nhiệm theo dõi ở học kỳ II.",
            )
        ]
    return []


def _retake(rule: RuleInput, config: AnalyticsConfig) -> list[RuleHit]:
    if not rule.retake_subjects:
        return []
    parts: list[str] = []
    for item in rule.retake_subjects:
        why = (
            f"ĐTB cả năm dưới {score_vn(config.score_threshold_pass)}"
            if item.reason is RetakeReason.BELOW_PASS
            else "nhận xét cả năm Chưa đạt"
        )
        parts.append(f"{item.name} ({why})")
    return [
        RuleHit(
            "retake_risk",
            RiskLevel.MEDIUM,
            f"Có thể phải kiểm tra lại trong hè: {', '.join(parts)}.",
            {"subjects": [item.name for item in rule.retake_subjects]},
        )
    ]


def _exam(rule: RuleInput, config: AnalyticsConfig) -> list[RuleHit]:
    if rule.grade_level != 12:
        return []
    low = [
        (rule.subject_names.get(i, f"môn {i}"), rule.subject_averages[i])
        for i in rule.exam_subject_ids
        if i in rule.subject_averages and rule.subject_averages[i] < config.score_threshold_pass
    ]
    if not low:
        return []
    parts = [f"{name} ({score_vn(average)})" for name, average in low]
    return [
        RuleHit(
            "grade12_exam_low",
            RiskLevel.MEDIUM,
            f"Môn đăng ký thi tốt nghiệp có ĐTB dưới {score_vn(config.score_threshold_pass)}: "
            f"{', '.join(parts)}. Cần xếp lớp phụ đạo.",
            {
                "subjects": [name for name, _ in low],
                "threshold": float(config.score_threshold_pass),
            },
        )
    ]


def evaluate_rules(rule: RuleInput, config: AnalyticsConfig) -> list[RuleHit]:
    """Mọi luật đang kích hoạt, mức cao trước (cùng mức giữ thứ tự khai báo)."""
    hits = [
        *_absence(rule, config),
        *_learning(rule, config),
        *_conduct(rule),
        *_retake(rule, config),
        *_exam(rule, config),
    ]
    return sorted(hits, key=lambda hit: -LEVEL_ORDER[hit.level])

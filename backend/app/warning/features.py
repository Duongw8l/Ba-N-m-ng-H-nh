"""Đặc trưng của mô hình ML cảnh báo sớm (DESIGN mục 6.2, D-072).

MỘT nơi duy nhất tính đặc trưng cho cả huấn luyện (backend/ml/) lẫn phục vụ (model.py), nên hai bên
không thể lệch nhau. Đặc trưng chụp dữ liệu "giữa học kỳ I": ngày cắt là `start_date + 9 tuần` của
năm học (học kỳ I dài 18 tuần). Điểm trong DB không có ngày, nên "đã có tới giữa kỳ I" được xấp xỉ
bằng toàn bộ đầu điểm thường xuyên và điểm giữa kỳ của học kỳ I.

Chỉ dùng điểm và chuyên cần (DESIGN mục 10): không có giới tính, dân tộc, nơi ở, hoàn cảnh gia
đình, và không có họ tên hay mã học sinh. Đặc trưng gom theo toàn bộ môn điểm số (không theo từng
môn) vì tổ hợp môn mỗi lớp khác nhau. Các giá trị trung bình ở đây là số mô tả cho mô hình, không
phải ĐTB của Thông tư 22 (cái đó chỉ tính trong analytics/).
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import repository as analytics_repo
from app.analytics.config import AnalyticsConfig
from app.classes.academic import Assessment, Attendance
from app.classes.models import ClassStudent
from app.core.enums import ABSENT_STATUSES, AssessmentKind, AssessmentType, AttendanceStatus

SNAPSHOT_WEEKS = 9  # giữa học kỳ I (học kỳ I dài 18 tuần)
TREND_WEEKS = 4  # xu hướng nghỉ: 4 tuần gần nhất tới ngày cắt


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    label: str  # nhãn tiếng Việt, dùng khi giải thích cho giáo viên


FEATURES = (
    FeatureSpec("tx_mean", "Điểm thường xuyên học kỳ I (trung bình các môn)"),
    FeatureSpec("tx_min_subject", "Điểm thường xuyên thấp nhất của một môn"),
    FeatureSpec("n_tx_below_pass", "Số môn có điểm thường xuyên dưới mức Đạt"),
    FeatureSpec("gk_mean", "Điểm giữa kỳ học kỳ I (trung bình các môn)"),
    FeatureSpec("gk_min", "Điểm giữa kỳ thấp nhất của một môn"),
    FeatureSpec("n_gk_below_pass", "Số môn có điểm giữa kỳ dưới mức Đạt"),
    FeatureSpec("absent_total", "Số buổi nghỉ tới giữa học kỳ I"),
    FeatureSpec("absent_last_4_weeks", "Số buổi nghỉ trong 4 tuần gần nhất"),
    FeatureSpec("late_total", "Số buổi đi muộn tới giữa học kỳ I"),
)
FEATURE_NAMES = tuple(spec.name for spec in FEATURES)

# Tên đặc trưng không bao giờ được xuất hiện (nhóm bảo vệ, DESIGN mục 10); test kiểm.
FORBIDDEN_FEATURE_WORDS = (
    "gender",
    "sex",
    "ethnic",
    "address",
    "residence",
    "family",
    "guardian",
    "parent",
    "name",
    "birth",
)


def snapshot_date(year_start: date) -> date:
    """Ngày cắt dữ liệu của mô hình: giữa học kỳ I."""
    return year_start + timedelta(weeks=SNAPSHOT_WEEKS)


def build_features(
    tx_by_subject: Mapping[int, Sequence[Decimal]],
    gk_by_subject: Mapping[int, Decimal],
    attendance: Sequence[tuple[date, AttendanceStatus]],
    cutoff: date,
    pass_threshold: Decimal,
) -> dict[str, float] | None:
    """Đặc trưng của một học sinh tại ngày cắt; None nếu chưa có điểm thường xuyên hoặc giữa kỳ.

    `attendance` có thể gồm cả ngày sau ngày cắt: chỉ các ngày không muộn hơn `cutoff` được tính.
    """
    subject_tx_means = [float(fmean(v)) for v in tx_by_subject.values() if v]
    gk_scores = [float(v) for v in gk_by_subject.values()]
    if not subject_tx_means or not gk_scores:
        return None
    all_tx = [float(x) for v in tx_by_subject.values() for x in v]
    pass_value = float(pass_threshold)

    until = [(day, status) for day, status in attendance if day <= cutoff]
    recent_from = cutoff - timedelta(weeks=TREND_WEEKS)
    absent = [day for day, status in until if status in ABSENT_STATUSES]
    return {
        "tx_mean": fmean(all_tx),
        "tx_min_subject": min(subject_tx_means),
        "n_tx_below_pass": float(sum(1 for m in subject_tx_means if m < pass_value)),
        "gk_mean": fmean(gk_scores),
        "gk_min": min(gk_scores),
        "n_gk_below_pass": float(sum(1 for g in gk_scores if g < pass_value)),
        "absent_total": float(len(absent)),
        "absent_last_4_weeks": float(sum(1 for day in absent if day > recent_from)),
        "late_total": float(sum(1 for _, status in until if status is AttendanceStatus.LATE)),
    }


def snapshot_ready(session: Session, class_id: int) -> tuple[bool, date]:
    """(đã có dữ liệu tới ngày cắt chưa, ngày cắt). Chưa tới giữa học kỳ I thì ML chưa chạy."""
    year_start, _ = analytics_repo.school_year_range(session, class_id)
    cutoff = snapshot_date(year_start)
    last = session.scalar(
        select(Attendance.date)
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id)
        .order_by(Attendance.date.desc())
        .limit(1)
    )
    return (last is not None and last >= cutoff), cutoff


def extract_class(
    session: Session, class_id: int, config: AnalyticsConfig, *, cutoff: date
) -> dict[int, dict[str, float]]:
    """Đặc trưng của mọi học sinh của lớp (khoá là class_student_id); em chưa đủ điểm bị bỏ."""
    score_subjects = [
        s.id
        for s in analytics_repo.class_subjects(session, class_id)
        if s.assessment_type is AssessmentType.SCORE
    ]
    members = [s.class_student_id for s in analytics_repo.class_students(session, class_id)]

    tx: dict[int, dict[int, list[Decimal]]] = defaultdict(lambda: defaultdict(list))
    gk: dict[int, dict[int, Decimal]] = defaultdict(dict)
    rows = session.execute(
        select(
            Assessment.class_student_id, Assessment.subject_id, Assessment.kind, Assessment.score
        )
        .join(ClassStudent, ClassStudent.id == Assessment.class_student_id)
        .where(
            ClassStudent.class_id == class_id,
            Assessment.semester == 1,
            Assessment.kind.in_((AssessmentKind.TX, AssessmentKind.GK)),
            Assessment.subject_id.in_(score_subjects),
            Assessment.score.is_not(None),
        )
        .order_by(Assessment.class_student_id, Assessment.subject_id, Assessment.seq)
    ).all()
    for cs_id, subject_id, kind, score in rows:
        if kind is AssessmentKind.TX:
            tx[cs_id][subject_id].append(score)
        else:
            gk[cs_id][subject_id] = score

    days: dict[int, list[tuple[date, AttendanceStatus]]] = defaultdict(list)
    for cs_id, day, status in session.execute(
        select(Attendance.class_student_id, Attendance.date, Attendance.status)
        .join(ClassStudent, ClassStudent.id == Attendance.class_student_id)
        .where(ClassStudent.class_id == class_id, Attendance.date <= cutoff)
    ):
        days[cs_id].append((day, status))

    result: dict[int, dict[str, float]] = {}
    for cs_id in members:
        features = build_features(
            tx.get(cs_id, {}),
            gk.get(cs_id, {}),
            days.get(cs_id, []),
            cutoff,
            config.score_threshold_pass,
        )
        if features is not None:
            result[cs_id] = features
    return result

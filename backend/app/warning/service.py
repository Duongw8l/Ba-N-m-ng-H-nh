"""Chạy cảnh báo sớm cho một lớp và dựng dữ liệu trả về (D-071).

Gộp hai lớp: luật cứng (rules.py) và mô hình ML (model.py, tuỳ chọn). Mỗi lần chạy chỉ THÊM dòng mới
vào risk_alerts khi nội dung đổi so với dòng mới nhất của học sinh đó, nên `teacher_status` mà GVCN
đã ghi không bị mất khi chạy lại cùng dữ liệu; cảnh báo hiện hành là dòng mới nhất, các dòng cũ là
lịch sử. Hàm ở đây chỉ flush, người gọi commit.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import repository as analytics_repo
from app.analytics import service as analytics_service
from app.analytics.config import load_config
from app.analytics.service import ClassResults
from app.classes.models import SchoolClass
from app.core.enums import AssessmentType, ConductPeriod, RiskLevel
from app.warning import repository as repo
from app.warning.model import Predictor, load_predictor
from app.warning.rules import LEVEL_ORDER, RuleHit, RuleInput, evaluate_rules, worst
from app.warning.schemas import (
    AlertCountsOut,
    AlertOut,
    AlertStudentOut,
    ClassAlertsOut,
    ModelFactorOut,
    ModelOut,
    ProfileAlertOut,
    ReasonOut,
    SchoolAlertsOut,
)

logger = logging.getLogger(__name__)

TOP_REASONS = 3


@dataclass(frozen=True)
class RefreshResult:
    inserted: int
    unchanged: int
    counts: dict[str, int]  # số cảnh báo hiện hành của lớp theo mức, sau lần chạy


def _hit_json(hit: RuleHit) -> dict[str, Any]:
    return {"code": hit.code, "level": hit.level.value, "message": hit.message, "data": hit.data}


def _comparable(reasons: dict[str, Any]) -> dict[str, Any]:
    """Phần của `reasons` dùng để so sánh "có đổi không": bỏ `as_of` (đổi theo ngày dữ liệu)."""
    return {key: value for key, value in reasons.items() if key != "as_of"}


def _score(value: Decimal | float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(Decimal("0.0001"))


def refresh_class(
    session: Session, class_id: int, *, predictor: Predictor | None = None
) -> RefreshResult:
    """Đánh giá mọi học sinh của lớp và ghi cảnh báo mới nếu nội dung đổi.

    `predictor=None` là chỉ chạy lớp luật; truyền `load_predictor()` để thêm mô hình ML.
    """
    class_info = analytics_repo.get_class(session, class_id)
    if class_info is None:
        raise LookupError(f"Không có lớp {class_id}")
    config = load_config(session)
    period = "2" if repo.has_semester_two_scores(session, class_id) else "1"
    results = analytics_service.build_class_results(session, class_info, period, config)
    year_results: ClassResults | None = (
        analytics_service.build_class_results(session, class_info, "year", config)
        if period == "2"
        else None
    )
    year_by_student = (
        {r.student.class_student_id: r for r in year_results.students} if year_results else {}
    )
    conduct = analytics_repo.conduct_by_student(session, class_id)
    exams = repo.exam_subjects(session, class_id) if class_info.grade_level == 12 else {}
    as_of = repo.last_attendance_date(session, class_id)
    names = {subject.id: subject.name for subject in results.subjects}
    predictions = predictor.predict_class(session, class_info, config) if predictor else {}

    latest = repo.latest_by_student(session, [r.student.class_student_id for r in results.students])
    inserted = unchanged = 0
    for result in results.students:
        cs_id = result.student.class_student_id
        year_result = year_by_student.get(cs_id)
        hits = evaluate_rules(
            RuleInput(
                grade_level=class_info.grade_level,
                period=period,
                absent_sessions=result.absence.absent_total,
                learning=result.learning,
                subject_names=names,
                subject_averages={
                    r.subject_id: r.average
                    for r in result.subjects
                    if r.assessment_type is AssessmentType.SCORE and r.average is not None
                },
                conduct_hk1=conduct.get(cs_id, {}).get(ConductPeriod.HK1),
                retake_subjects=(
                    year_result.promotion.retake_subjects
                    if year_result is not None and year_result.promotion is not None
                    else ()
                ),
                exam_subject_ids=exams.get(cs_id, ()),
            ),
            config,
        )
        prediction = predictions.get(cs_id)
        level = worst([hit.level for hit in hits] + ([prediction.level] if prediction else []))
        reasons: dict[str, Any] = {
            "period": period,
            "as_of": None if as_of is None else as_of.isoformat(),
            "rules": [_hit_json(hit) for hit in hits],
            "model": None if prediction is None else prediction.to_json(),
        }
        risk_score = _score(prediction.probability) if prediction else None
        version = predictor.version if prediction and predictor else None

        current = latest.get(cs_id)
        if (
            current is not None
            and current.level is level
            and current.risk_score == risk_score
            and current.model_version == version
            and _comparable(current.reasons) == _comparable(reasons)
        ):
            unchanged += 1
            continue
        repo.insert_alert(
            session,
            class_student_id=cs_id,
            level=level,
            risk_score=risk_score,
            reasons=reasons,
            model_version=version,
        )
        inserted += 1
    return RefreshResult(inserted, unchanged, repo.current_counts(session, class_id=class_id))


def refresh_all(session: Session, *, predictor: Predictor | None = None) -> RefreshResult:
    """Chạy cho mọi lớp (dùng cho `make warn` và sau `make seed`)."""
    inserted = unchanged = 0
    for class_id in session.scalars(select(SchoolClass.id).order_by(SchoolClass.id)):
        outcome = refresh_class(session, class_id, predictor=predictor)
        inserted, unchanged = inserted + outcome.inserted, unchanged + outcome.unchanged
    return RefreshResult(inserted, unchanged, repo.current_counts(session))


def refresh_after_import(session: Session, class_id: int) -> None:
    """Gọi từ hook `on_data_changed`: chạy cho lớp rồi commit. Mọi lỗi chỉ ghi log (D-063)."""
    try:
        refresh_class(session, class_id, predictor=load_predictor())
        session.commit()
    except Exception:  # noqa: BLE001 - việc nhập đã commit, cảnh báo lỗi không được làm hỏng nó
        session.rollback()
        logger.exception("Không chạy được cảnh báo sớm cho lớp %s sau khi nhập dữ liệu", class_id)


# --- Dữ liệu trả về cho API -----------------------------------------------------------------------


def _model_out(raw: dict[str, Any] | None) -> ModelOut | None:
    if not raw:
        return None
    return ModelOut(
        version=raw["version"],
        probability=raw["probability"],
        factors=[ModelFactorOut(**factor) for factor in raw["factors"]],
    )


def _top_reasons(rules: list[ReasonOut], model: ModelOut | None) -> list[str]:
    """Tối đa 3 câu: lý do của luật trước (đã sắp theo mức), rồi các yếu tố của mô hình."""
    texts = [rule.message for rule in rules]
    if model is not None:
        texts += [f.message for f in model.factors if f.contribution > 0]
    return texts[:TOP_REASONS]


def _parts(alert: Any) -> tuple[list[ReasonOut], ModelOut | None, str | None]:
    reasons: dict[str, Any] = alert.reasons or {}
    rules = [ReasonOut(**rule) for rule in reasons.get("rules", [])]
    return rules, _model_out(reasons.get("model")), reasons.get("as_of")


def alert_out(row: repo.AlertRow) -> AlertOut:
    rules, model, as_of = _parts(row.alert)
    return AlertOut(
        id=row.alert.id,
        student=AlertStudentOut(
            id=row.student_id, student_code=row.student_code, full_name=row.full_name
        ),
        class_id=row.class_id,
        class_name=row.class_name,
        level=row.alert.level.value,
        risk_score=None if row.alert.risk_score is None else float(row.alert.risk_score),
        rules=rules,
        model=model,
        top_reasons=_top_reasons(rules, model),
        teacher_status=row.alert.teacher_status,
        created_at=row.alert.created_at,
        as_of=as_of,
    )


def profile_alert(session: Session, class_student_id: int) -> ProfileAlertOut | None:
    alert = repo.current_for_student(session, class_student_id)
    if alert is None:
        return None
    rules, model, as_of = _parts(alert)
    return ProfileAlertOut(
        id=alert.id,
        level=alert.level.value,
        risk_score=None if alert.risk_score is None else float(alert.risk_score),
        rules=rules,
        model=model,
        top_reasons=_top_reasons(rules, model),
        teacher_status=alert.teacher_status,
        created_at=alert.created_at,
        as_of=as_of,
    )


def _sorted(rows: list[repo.AlertRow]) -> list[repo.AlertRow]:
    return sorted(
        rows,
        key=lambda r: (
            -LEVEL_ORDER[r.alert.level],
            -float(r.alert.risk_score or 0),
            r.class_name,
            r.student_code,
        ),
    )


def counts_out(counts: dict[str, int]) -> AlertCountsOut:
    return AlertCountsOut(high=counts["high"], medium=counts["medium"], low=counts["low"])


def class_alerts(
    session: Session, class_id: int, class_name: str, *, include_low: bool
) -> ClassAlertsOut:
    levels = [RiskLevel.HIGH, RiskLevel.MEDIUM] + ([RiskLevel.LOW] if include_low else [])
    rows = _sorted(repo.current_alerts(session, class_id=class_id, levels=levels))
    return ClassAlertsOut(
        class_id=class_id,
        class_name=class_name,
        counts=counts_out(repo.current_counts(session, class_id=class_id)),
        alerts=[alert_out(row) for row in rows],
    )


def school_alerts(session: Session, level: RiskLevel) -> SchoolAlertsOut:
    rows = _sorted(repo.current_alerts(session, levels=[level]))
    return SchoolAlertsOut(
        counts=counts_out(repo.current_counts(session)), alerts=[alert_out(r) for r in rows]
    )

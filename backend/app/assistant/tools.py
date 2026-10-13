"""Bảy hàm LLM được gọi (Giai đoạn 8, D-087; nguyên tắc 1, 3, 4, 5).

- Đúng 7 hàm, tất cả CHỈ ĐỌC (service chạy chúng trong transaction `READ ONLY`).
- Mỗi hàm qua `authorize()`. Phạm vi lấy từ phiên: `class_id`/`subject_id`/kỳ của màn hình đang mở
  là mặc định; nếu LLM tự điền giá trị khác thì giá trị đó vẫn phải qua `authorize()`. Ngoài quyền
  thì trả `{"error": "forbidden"}` và không đọc dữ liệu nào (không lặng lẽ thay bằng lớp khác).
- Số liệu lấy từ Analytics (`service`, `queries`, `warning`); hàm ở đây chỉ nạp, gọi, và đổi dạng
  (nhãn tiếng Việt, mã tạm thay cho danh tính học sinh).
- Đầu ra KHÔNG có họ tên, mã học sinh thật, `date_of_birth`, `guardian_*` hay nhận xét tự do:
  học sinh chỉ là `HS_01`... do `Pseudonymizer` cấp.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session, SessionTransaction

from app.analytics import repository as repo
from app.analytics import service
from app.analytics.config import AnalyticsConfig
from app.analytics.queries import (
    InvalidRange,
    build_attendance_range,
    class_summary,
    filter_students,
)
from app.analytics.schemas import Period
from app.assistant.llm import ToolSpec
from app.auth.models import User
from app.core.authorize import FORBIDDEN_MESSAGE, AuthorizationError, authorize
from app.core.enums import CommentResult, ConductLevel, RiskLevel
from app.core.labels import label_vi
from app.core.pseudonymize import Pseudonymizer, RosterStudent
from app.rag.embedding import Embedder, EmbeddingUnavailable
from app.rag.search import search_regulation as rag_search
from app.warning import repository as warning_repo
from app.warning import service as warning_service

logger = logging.getLogger(__name__)

MAX_LIST_ROWS = 50  # trần số học sinh trong một kết quả danh sách
RAG_HITS = 4

PERIOD_LABELS = {"1": "học kỳ I", "2": "học kỳ II", "year": "cả năm"}
LEVEL_LABELS = {
    **{level.value: label_vi(level) for level in ConductLevel},
    "incomplete": "Chưa đủ dữ liệu",
    "missing": "Chưa có dữ liệu",
}
PROMOTION_REASONS = {
    "learning_fail": "kết quả học tập cả năm Chưa đạt",
    "conduct_fail": "rèn luyện cả năm Chưa đạt",
    "absent_over_limit": "nghỉ quá số buổi tối đa",
    "missing_data": "chưa đủ dữ liệu để kết luận",
}
RETAKE_REASONS = {
    "below_pass": "ĐTB cả năm dưới mức đạt",
    "comment_fail": "môn nhận xét Chưa đạt cả năm",
}
ATTENTION_REASONS = {
    "absent_over_limit": "nghỉ quá số buổi tối đa",
    "absent_notice": "nghỉ từ mức nhắc nhở",
    "subject_below_fail": "có môn điểm quá thấp",
    "level_fail": "mức học tập Chưa đạt",
}


class ToolFailure(Exception):
    """Lỗi nghiệp vụ của một hàm (thiếu tham số, không có lớp...): trả cho LLM dưới dạng lỗi."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ToolContext:
    """Những gì một hàm cần: phiên DB, người dùng, bộ ẩn danh, và màn hình đang mở."""

    session: Session
    user: User
    pseudo: Pseudonymizer
    config: AnalyticsConfig
    class_id: int | None = None  # lớp đang mở trên màn hình (mặc định khi LLM không nêu lớp)
    subject_id: int | None = None
    semester: Period = "1"
    embedder: Embedder | None = None

    _savepoint: SessionTransaction | None = field(default=None, init=False, repr=False)

    def begin_read_only(self) -> None:
        """Từ đây tới `end_read_only()` DB chỉ cho đọc: hàm nào lỡ ghi sẽ bị chính DB từ chối.

        Dùng SAVEPOINT + `SET LOCAL transaction_read_only`: rollback savepoint trả phiên về đọc-ghi
        (SET TRANSACTION READ WRITE thì không làm được sau khi đã có truy vấn trong transaction).
        """
        self.end_read_only()
        self._savepoint = self.session.begin_nested()
        self.session.execute(text("SET LOCAL transaction_read_only = on"))

    def end_read_only(self) -> None:
        savepoint, self._savepoint = self._savepoint, None
        if savepoint is not None and savepoint.is_active:
            savepoint.rollback()


@dataclass
class ToolOutcome:
    result: dict[str, Any]
    ok: bool = True
    blocked: bool = False  # bị `authorize()` chặn
    sources: list[dict[str, Any]] = field(default_factory=list)


# --- Tham số -----------------------------------------------------------------------------------


def _coerce_period(value: Any) -> Any:
    """LLM hay gửi học kỳ là số nguyên (1, 2) thay vì chuỗi."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value.strip() if isinstance(value, str) else value


PeriodArg = Annotated[Period, BeforeValidator(_coerce_period)]
TermArg = Annotated[Literal["1", "2"], BeforeValidator(_coerce_period)]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClassSummaryArgs(_Args):
    class_id: int | None = None
    semester: PeriodArg | None = None


class StudentDetailArgs(_Args):
    student_code: str = Field(min_length=1, max_length=20)
    semester: PeriodArg | None = None


class ListStudentsArgs(_Args):
    class_id: int | None = None
    semester: PeriodArg | None = None
    min_absent_days: int | None = Field(default=None, ge=0, le=400)
    subject_below: float | None = Field(default=None, ge=0, le=10)
    alert_level: Literal["high", "medium", "low"] | None = None


class SubjectScoresArgs(_Args):
    class_id: int | None = None
    subject_id: int | None = None
    semester: TermArg | None = None


class GradeOverviewArgs(_Args):
    grade_level: int = Field(ge=10, le=12)
    semester: PeriodArg | None = None


class AttendanceSummaryArgs(_Args):
    class_id: int | None = None
    from_date: date | None = None
    to_date: date | None = None
    granularity: Literal["week", "month"] = "month"
    top_n: int = Field(default=5, ge=1, le=20)


class SearchRegulationArgs(_Args):
    query: str = Field(min_length=2, max_length=500)


# --- Tiện ích ----------------------------------------------------------------------------------


def _f(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _levels(counts: dict[str, int]) -> dict[str, int]:
    return {LEVEL_LABELS[key]: value for key, value in counts.items()}


def _level(value: str | None) -> str | None:
    return None if value is None else LEVEL_LABELS.get(value, value)


def _comment(value: str | None) -> str | None:
    return None if value is None else label_vi(CommentResult(value))


def _roster(info: repo.StudentInfo, class_id: int) -> RosterStudent:
    return RosterStudent(info.student_id, class_id, info.full_name, info.student_code)


def _register_class(ctx: ToolContext, students: list[repo.StudentInfo], class_id: int) -> None:
    """Cho bộ ẩn danh biết mọi học sinh của lớp (để hàng rào bắt được họ tên thật)."""
    for info in students:
        ctx.pseudo.register(_roster(info, class_id))


def _class_id(ctx: ToolContext, requested: int | None) -> int:
    class_id = requested if requested is not None else ctx.class_id
    if class_id is None:
        raise ToolFailure("missing_class", "Chưa biết hỏi về lớp nào: hãy nêu lớp (class_id).")
    return class_id


def _class_info(ctx: ToolContext, class_id: int) -> repo.ClassInfo:
    info = repo.get_class(ctx.session, class_id)
    if info is None:
        raise ToolFailure("not_found", "Không có lớp này.")
    return info


def _period(ctx: ToolContext, requested: str | None) -> Period:
    return requested or ctx.semester  # type: ignore[return-value]


def _data_source(tool: str, description: str) -> dict[str, Any]:
    return {"type": "data", "tool": tool, "description": description}


def _thresholds(config: AnalyticsConfig) -> dict[str, float]:
    return {
        "below_this_is_very_low": float(config.score_threshold_fail),
        "pass": float(config.score_threshold_pass),
        "fair": float(config.score_threshold_fair),
        "good": float(config.score_threshold_good),
    }


# --- 1. get_class_summary ----------------------------------------------------------------------


def _get_class_summary(ctx: ToolContext, args: ClassSummaryArgs) -> ToolOutcome:
    class_id = _class_id(ctx, args.class_id)
    access = authorize(ctx.session, ctx.user, class_id=class_id)
    access.require_all_subjects()  # dữ liệu cả lớp (mọi môn): GVBM không xem được
    info = _class_info(ctx, class_id)
    period = _period(ctx, args.semester)

    results = service.build_class_results(ctx.session, info, period, ctx.config)
    summary = class_summary(results, ctx.config)
    counts = warning_service.counts_out(warning_repo.current_counts(ctx.session, class_id=class_id))
    result = {
        "class": {"name": info.name, "grade_level": info.grade_level},
        "semester": PERIOD_LABELS[period],
        "student_count": summary.student_count,
        "learning_levels": _levels(summary.learning_levels),
        "conduct_levels": _levels(summary.conduct_levels),
        # Số học sinh nghỉ từ ngưỡng nhắc / quá ngưỡng tối đa (tính cả năm học).
        "absent_notice_students": summary.absent_notice_students,
        "absent_over_limit_students": summary.absent_over_limit_students,
        "mean_absent_sessions": _f(summary.mean_absent_sessions),
        "absence_limits": {
            "notice": summary.absence_limits.notice,
            "maximum": summary.absence_limits.maximum,
        },
        "alert_counts": {"high": counts.high, "medium": counts.medium, "low": counts.low},
    }
    source = _data_source("get_class_summary", f"Tổng hợp lớp {info.name}, {PERIOD_LABELS[period]}")
    return ToolOutcome(result, sources=[source])


# --- 2. get_student_detail ---------------------------------------------------------------------


def _student_alert(alert: dict[str, Any] | None) -> dict[str, Any] | None:
    if alert is None:
        return None
    model = alert.get("model")
    return {
        "level": label_vi(RiskLevel(alert["level"])),
        "risk_score": alert["risk_score"],
        "rules": [
            {"level": label_vi(RiskLevel(r["level"])), "message": r["message"]}
            for r in alert["rules"]
        ],
        "top_reasons": alert["top_reasons"],
        "model": None
        if model is None
        else {
            "probability": model["probability"],
            "factors": [
                {"label": f["label"], "value": f["value"], "message": f["message"]}
                for f in model["factors"]
            ],
        },
        "as_of": alert["as_of"],
    }


def _student_subject(subject: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": subject["name"],
        "type": subject["assessment_type"],
        "regular_required": subject["regular_required"],
        "semesters": [
            {
                "semester": s["semester"],
                "tx": s["tx"],
                "tx_missing": s["tx_missing"],
                "midterm": s["midterm"],
                "final": s["final"],
                "average": s["average"],
                "comment_result": _comment(s["comment_result"]),
                "complete": s["complete"],
            }
            for s in subject["semesters"]
        ],
        "year_average": subject["year_average"],
        "year_comment_result": _comment(subject["year_comment_result"]),
    }


def _get_student_detail(ctx: ToolContext, args: StudentDetailArgs) -> ToolOutcome:
    student = ctx.pseudo.resolve(args.student_code)
    if student is None:
        raise ToolFailure(
            "unknown_student",
            "Mã học sinh không hợp lệ: chỉ dùng mã dạng HS_01 có trong câu hỏi hoặc kết quả hàm.",
        )
    access = authorize(ctx.session, ctx.user, class_id=student.class_id)
    info = _class_info(ctx, student.class_id)
    period = _period(ctx, args.semester)

    profile = service.build_student_profile(
        ctx.session,
        info,
        student.student_id,
        period,
        ctx.config,
        subject_ids=access.subject_ids,
        alert_lookup=lambda class_student_id: warning_service.profile_alert(
            ctx.session, class_student_id
        ),
    )
    if profile is None:
        raise ToolFailure("not_found", "Không có học sinh này trong lớp.")
    code = ctx.pseudo.code_for(student)
    data = profile.model_dump(mode="json")  # guardian_*, danh tính: không chép sang kết quả
    result: dict[str, Any] = {
        "student": code,
        "class": {"name": info.name, "grade_level": info.grade_level},
        "subjects": [_student_subject(s) for s in data["subjects"]],
        "thresholds": _thresholds(ctx.config),
    }
    if data["scope"] == "full":
        learning, attendance = data["learning"], data["attendance"]
        result["semester"] = PERIOD_LABELS[period]
        result["learning"] = {
            "level": _level(learning["level"]),
            "adjusted_up_one_level": learning["adjusted"],
            "incomplete_subjects": learning["incomplete_subjects"],
            "below_very_low_subjects": learning["below_fail_subjects"],
            "below_pass_subjects": learning["below_pass_subjects"],
            "failed_comment_subjects": learning["failed_comment_subjects"],
        }
        result["conduct"] = {
            "level": _level(data["conduct"]["level"]),
            "derived_from_semester_2": data["conduct"]["derived"],
        }
        result["attendance"] = {
            "excused": attendance["excused"],
            "unexcused": attendance["unexcused"],
            "late": attendance["late"],
            "absent_total": attendance["absent_total"],
            "limits": attendance["limits"],
            "by_month": attendance["by_month"],
        }
        promotion = data["promotion"]
        if promotion is not None:
            result["promotion"] = {
                "eligible": promotion["eligible"],
                "reasons": [PROMOTION_REASONS.get(r, r) for r in promotion["reasons"]],
                "retake_subjects": [
                    {"name": s["name"], "reason": RETAKE_REASONS.get(s["reason"], s["reason"])}
                    for s in promotion["retake_subjects"]
                ],
            }
        result["attention_reasons"] = [
            ATTENTION_REASONS.get(r, r) for r in data["attention_reasons"]
        ]
        result["alert"] = _student_alert(data["alert"])
    source = _data_source("get_student_detail", f"Hồ sơ {code}, lớp {info.name}")
    return ToolOutcome(result, sources=[source])


# --- 3. list_students --------------------------------------------------------------------------


def _list_students(ctx: ToolContext, args: ListStudentsArgs) -> ToolOutcome:
    class_id = _class_id(ctx, args.class_id)
    access = authorize(ctx.session, ctx.user, class_id=class_id)
    restricted = access.subject_ids is not None  # GVBM
    if restricted and (args.min_absent_days is not None or args.alert_level is not None):
        raise AuthorizationError  # chuyên cần và cảnh báo: chỉ GVCN của lớp và BGH
    info = _class_info(ctx, class_id)
    period = _period(ctx, args.semester)

    results = service.build_class_results(ctx.session, info, period, ctx.config)
    _register_class(ctx, [s.student for s in results.students], class_id)

    alert_by_student: dict[int, RiskLevel] = {}
    only: frozenset[int] | None = None
    if not restricted:
        alert_by_student = {
            row.alert.class_student_id: row.alert.level
            for row in warning_repo.current_alerts(ctx.session, class_id=class_id)
        }
        if args.alert_level is not None:
            wanted = RiskLevel(args.alert_level)
            only = frozenset(cs for cs, level in alert_by_student.items() if level is wanted)

    rows = filter_students(
        results,
        min_absent=args.min_absent_days,
        subject_below=None if args.subject_below is None else Decimal(str(args.subject_below)),
        subject_ids=access.subject_ids,
        only_class_student_ids=only,
    )
    students: list[dict[str, Any]] = []
    for row in rows[:MAX_LIST_ROWS]:
        entry: dict[str, Any] = {
            "student": ctx.pseudo.code_for(_roster(row.student, class_id)),
            "low_subjects": [{"name": n, "average": _f(v)} for n, v in row.low_subjects],
        }
        if not restricted:
            entry["absent_total"] = row.absent_total
            entry["learning_level"] = _level(
                None if row.learning_level is None else row.learning_level.value
            )
            level = alert_by_student.get(row.student.class_student_id)
            entry["alert_level"] = None if level is None else label_vi(level)
        students.append(entry)

    conditions = []
    if args.min_absent_days is not None:
        conditions.append(f"nghỉ từ {args.min_absent_days} buổi")
    if args.subject_below is not None:
        conditions.append(f"có môn dưới {args.subject_below}")
    if args.alert_level is not None:
        conditions.append(f"cảnh báo mức {label_vi(RiskLevel(args.alert_level))}")
    result = {
        "class": {"name": info.name, "grade_level": info.grade_level},
        "semester": PERIOD_LABELS[period],
        "total_matches": len(rows),
        "returned": len(students),
        "truncated": len(rows) > len(students),
        "students": students,
    }
    description = f"Danh sách học sinh lớp {info.name}" + (
        f" ({', '.join(conditions)})" if conditions else ""
    )
    return ToolOutcome(result, sources=[_data_source("list_students", description)])


# --- 4. get_subject_scores ---------------------------------------------------------------------


def _get_subject_scores(ctx: ToolContext, args: SubjectScoresArgs) -> ToolOutcome:
    class_id = _class_id(ctx, args.class_id)
    subject_id = args.subject_id if args.subject_id is not None else ctx.subject_id
    if subject_id is None:
        raise ToolFailure("missing_subject", "Chưa biết hỏi về môn nào: hãy nêu môn (subject_id).")
    authorize(ctx.session, ctx.user, class_id=class_id, subject_id=subject_id)
    info = _class_info(ctx, class_id)
    subject = next(
        (s for s in repo.class_subjects(ctx.session, class_id) if s.id == subject_id), None
    )
    if subject is None:
        raise ToolFailure("not_found", "Lớp này không học môn đó.")
    term = args.semester or (ctx.semester if ctx.semester in ("1", "2") else "1")

    out = service.build_subject_scores(ctx.session, info, subject, int(term), ctx.config)
    data = out.model_dump(mode="json")
    students = []
    for row in data["rows"][:MAX_LIST_ROWS]:
        student = RosterStudent(row["student_id"], class_id, row["full_name"], row["student_code"])
        students.append(
            {
                "student": ctx.pseudo.code_for(student),
                "tx": row["tx"],
                "tx_missing": row["tx_missing"],
                "midterm": row["midterm"],
                "final": row["final"],
                "average": row["average"],
                "comment_result": _comment(row["comment_result"]),
                "complete": row["complete"],
                "year_average": row["year_average"],
            }
        )
    for row in data["rows"][MAX_LIST_ROWS:]:  # lớp quá đông: vẫn cho hàng rào biết tên
        ctx.pseudo.register(
            RosterStudent(row["student_id"], class_id, row["full_name"], row["student_code"])
        )
    result = {
        "class": {"name": info.name, "grade_level": info.grade_level},
        "subject": {
            "name": subject.name,
            "type": data["subject"]["assessment_type"],
            "regular_required": data["subject"]["regular_required"],
        },
        "semester": PERIOD_LABELS[term],
        "student_count": data["student_count"],
        "mean": data["mean"],
        "distribution": data["distribution"],
        "incomplete_count": data["incomplete_count"],
        "comment_fail_count": data["comment_fail_count"],
        "thresholds": _thresholds(ctx.config),
        "students": students,
        "truncated": len(data["rows"]) > len(students),
    }
    description = f"Bảng điểm {subject.name} lớp {info.name}, {PERIOD_LABELS[term]}"
    return ToolOutcome(result, sources=[_data_source("get_subject_scores", description)])


# --- 5. get_grade_overview ---------------------------------------------------------------------


def _get_grade_overview(ctx: ToolContext, args: GradeOverviewArgs) -> ToolOutcome:
    authorize(ctx.session, ctx.user, grade_level=args.grade_level)  # chỉ BGH
    classes = repo.classes_in_grade(ctx.session, args.grade_level)
    if not classes:
        raise ToolFailure("not_found", "Không có lớp nào ở khối này.")
    period = _period(ctx, args.semester)

    data = service.build_grade_overview(
        ctx.session, args.grade_level, classes, period, ctx.config
    ).model_dump(mode="json")
    names = {c.id: c.name for c in classes}
    result = {
        "grade_level": args.grade_level,
        "semester": PERIOD_LABELS[period],
        "classes": [
            {
                "name": c["name"],
                "student_count": c["student_count"],
                "learning_levels": _levels(c["learning_levels"]),
                "conduct_levels": _levels(c["conduct_levels"]),
                "absent_notice_students": c["absent_notice_students"],
                "absent_over_limit_students": c["absent_over_limit_students"],
                "students_with_a_very_low_subject": c["below_fail_students"],
            }
            for c in data["classes"]
        ],
        "common_subject_means": [
            {
                "subject": s["name"],
                "by_class": [
                    {"class": names[m["class_id"]], "mean": m["mean"]} for m in s["class_means"]
                ],
            }
            for s in data["common_subjects"]
        ],
    }
    description = f"So sánh các lớp khối {args.grade_level}, {PERIOD_LABELS[period]}"
    return ToolOutcome(result, sources=[_data_source("get_grade_overview", description)])


# --- 6. get_attendance_summary -----------------------------------------------------------------


def _get_attendance_summary(ctx: ToolContext, args: AttendanceSummaryArgs) -> ToolOutcome:
    class_id = _class_id(ctx, args.class_id)
    access = authorize(ctx.session, ctx.user, class_id=class_id)
    access.require_all_subjects()  # chuyên cần: GVCN của lớp và BGH
    info = _class_info(ctx, class_id)
    try:
        summary = build_attendance_range(
            ctx.session, info, args.from_date, args.to_date, args.granularity, args.top_n
        )
    except InvalidRange as error:
        raise ToolFailure("invalid_range", str(error)) from error

    students = repo.class_students(ctx.session, class_id)
    _register_class(ctx, students, class_id)
    result = {
        "class": {"name": info.name, "grade_level": info.grade_level},
        "from": summary.start.isoformat(),
        "to": summary.end.isoformat(),
        "granularity": args.granularity,
        "excused": summary.excused,
        "unexcused": summary.unexcused,
        "late": summary.late,
        "absent_total": summary.absent_total,
        "absent_students": summary.absent_students,
        "by_period": [
            {
                "period": p.period,
                "excused": p.excused,
                "unexcused": p.unexcused,
                "absent_total": p.absent_total,
            }
            for p in summary.by_period
        ],
        "top_absent": [
            {
                "student": ctx.pseudo.code_for(_roster(a.student, class_id)),
                "excused": a.excused,
                "unexcused": a.unexcused,
                "absent_total": a.absent_total,
            }
            for a in summary.top_absent
        ],
    }
    description = (
        f"Nghỉ học lớp {info.name} từ {summary.start.isoformat()} đến {summary.end.isoformat()}"
    )
    return ToolOutcome(result, sources=[_data_source("get_attendance_summary", description)])


# --- 7. search_regulation ----------------------------------------------------------------------


def _search_regulation(ctx: ToolContext, args: SearchRegulationArgs) -> ToolOutcome:
    # Văn bản quy định là dữ liệu chung của trường, không có lớp/môn nào để authorize (D-077);
    # endpoint đã chỉ cho giáo viên và BGH dùng trợ lý.
    try:
        found = rag_search(ctx.session, args.query, RAG_HITS, embedder=ctx.embedder)
    except EmbeddingUnavailable as error:
        raise ToolFailure(
            "regulation_unavailable", "Không tra được văn bản quy định lúc này."
        ) from error
    result = {
        "found": found.found,
        "message": found.message,
        "hits": [
            {
                "document": h.document_name,
                "article": h.article,
                "clause": h.clause,
                "content": h.content,
                "similarity": round(h.similarity, 2),
            }
            for h in found.hits
        ],
    }
    sources = [
        {
            "type": "regulation",
            "document": h.document_name,
            "article": h.article,
            "clause": h.clause,
            "similarity": round(h.similarity, 2),
        }
        for h in found.hits
    ]
    return ToolOutcome(result, sources=sources)


# --- Đăng ký: đúng 7 hàm -----------------------------------------------------------------------


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_CLASS_ID = {
    "type": "integer",
    "description": "Id lớp (xem danh sách lớp ở phần Bối cảnh). Bỏ trống thì dùng lớp đang mở.",
}
_SEMESTER = {
    "type": "string",
    "enum": ["1", "2", "year"],
    "description": (
        "Kỳ: 1 (học kỳ I), 2 (học kỳ II) hoặc year (cả năm). Bỏ trống thì dùng kỳ đang xem."
    ),
}


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    args_model: type[_Args]
    handler: Callable[[ToolContext, Any], ToolOutcome]


TOOLS: dict[str, Tool] = {
    tool.spec.name: tool
    for tool in (
        Tool(
            ToolSpec(
                "get_class_summary",
                "Tổng hợp một lớp: sĩ số, số học sinh theo mức học tập và rèn luyện, số buổi nghỉ "
                "trung bình, số học sinh nghỉ từ ngưỡng nhắc nhở và quá số buổi tối đa, số cảnh "
                "báo sớm theo mức. Chỉ giáo viên chủ nhiệm của lớp và Ban giám hiệu dùng được.",
                _schema({"class_id": _CLASS_ID, "semester": _SEMESTER}),
            ),
            ClassSummaryArgs,
            _get_class_summary,
        ),
        Tool(
            ToolSpec(
                "get_student_detail",
                "Hồ sơ một học sinh: điểm và ĐTB từng môn, mức học tập, rèn luyện, số buổi nghỉ có "
                "phép và không phép, cảnh báo sớm kèm lý do, điều kiện lên lớp (khi kỳ là year). "
                "Giáo viên bộ môn chỉ nhận các môn mình dạy. `student_code` là mã tạm dạng HS_01 "
                "có trong câu hỏi hoặc trong kết quả của hàm khác.",
                _schema(
                    {
                        "student_code": {
                            "type": "string",
                            "description": "Mã tạm của học sinh, ví dụ HS_01.",
                        },
                        "semester": _SEMESTER,
                    },
                    ["student_code"],
                ),
            ),
            StudentDetailArgs,
            _get_student_detail,
        ),
        Tool(
            ToolSpec(
                "list_students",
                "Liệt kê học sinh của một lớp theo điều kiện: nghỉ từ n buổi trở lên (cả năm học), "
                "có môn điểm số với ĐTB dưới x, mức cảnh báo sớm. Điều kiện bỏ trống là không lọc. "
                f"Trả tối đa {MAX_LIST_ROWS} học sinh kèm tổng số học sinh khớp. Giáo viên bộ môn "
                "chỉ lọc được theo điểm của môn mình dạy.",
                _schema(
                    {
                        "class_id": _CLASS_ID,
                        "semester": _SEMESTER,
                        "min_absent_days": {
                            "type": "integer",
                            "description": "Chỉ lấy học sinh nghỉ từ số buổi này trở lên.",
                        },
                        "subject_below": {
                            "type": "number",
                            "description": "Chỉ lấy học sinh có môn với ĐTB dưới mức điểm này.",
                        },
                        "alert_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Mức cảnh báo sớm: high (Cao), medium, low.",
                        },
                    }
                ),
            ),
            ListStudentsArgs,
            _list_students,
        ),
        Tool(
            ToolSpec(
                "get_subject_scores",
                "Bảng điểm một môn của lớp: ĐTB lớp, phân bố điểm, số học sinh thiếu đầu điểm, "
                "điểm từng học sinh. Học kỳ 1 hoặc 2.",
                _schema(
                    {
                        "class_id": _CLASS_ID,
                        "subject_id": {
                            "type": "integer",
                            "description": "Id môn (xem Bối cảnh). Bỏ trống thì dùng môn đang mở.",
                        },
                        "semester": {
                            "type": "string",
                            "enum": ["1", "2"],
                            "description": "Học kỳ 1 hoặc 2.",
                        },
                    }
                ),
            ),
            SubjectScoresArgs,
            _get_subject_scores,
        ),
        Tool(
            ToolSpec(
                "get_grade_overview",
                "So sánh các lớp trong một khối (10, 11 hoặc 12): số học sinh theo mức học tập và "
                "rèn luyện, số học sinh nghỉ nhiều, số học sinh có môn điểm quá thấp mỗi lớp, ĐTB "
                "các môn chung. Chỉ Ban giám hiệu dùng được.",
                _schema(
                    {
                        "grade_level": {
                            "type": "integer",
                            "enum": [10, 11, 12],
                            "description": "Khối lớp.",
                        },
                        "semester": _SEMESTER,
                    },
                    ["grade_level"],
                ),
            ),
            GradeOverviewArgs,
            _get_grade_overview,
        ),
        Tool(
            ToolSpec(
                "get_attendance_summary",
                "Số buổi nghỉ của một lớp theo tuần hoặc tháng trong một khoảng ngày (mặc định cả "
                "năm học) và các học sinh nghỉ nhiều nhất. Ngày dạng YYYY-MM-DD. Chỉ giáo viên "
                "chủ nhiệm của lớp và Ban giám hiệu dùng được.",
                _schema(
                    {
                        "class_id": _CLASS_ID,
                        "from_date": {
                            "type": "string",
                            "description": "Ngày bắt đầu, YYYY-MM-DD. Bỏ trống: đầu năm học.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "Ngày kết thúc, YYYY-MM-DD. Bỏ trống: cuối năm học.",
                        },
                        "granularity": {
                            "type": "string",
                            "enum": ["week", "month"],
                            "description": "Gom theo tuần (week) hoặc tháng (month).",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "Số học sinh nghỉ nhiều nhất cần liệt kê (1 đến 20).",
                        },
                    }
                ),
            ),
            AttendanceSummaryArgs,
            _get_attendance_summary,
        ),
        Tool(
            ToolSpec(
                "search_regulation",
                "Tìm điều khoản trong các văn bản quy định còn hiệu lực (Thông tư 22/2021, quy chế "
                "thi, nội quy trường...). Trả `found: false` khi không có điều khoản đủ liên quan; "
                "khi đó không được tự trả lời quy định.",
                _schema(
                    {
                        "query": {
                            "type": "string",
                            "description": "Câu hỏi hoặc từ khoá về quy định, tiếng Việt.",
                        }
                    },
                    ["query"],
                ),
            ),
            SearchRegulationArgs,
            _search_regulation,
        ),
    )
}


def tool_specs() -> list[ToolSpec]:
    return [tool.spec for tool in TOOLS.values()]


def _describe_errors(error: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in item['loc']) or 'tham số'}: {item['msg']}"
        for item in error.errors(include_input=False, include_url=False, include_context=False)
    ]
    return "Tham số không hợp lệ: " + "; ".join(parts)[:300]


def run_tool(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> ToolOutcome:
    """Chạy một hàm LLM đòi. Không bao giờ ném lỗi ra ngoài: mọi sự cố thành kết quả lỗi cho LLM."""
    tool = TOOLS.get(name)
    if tool is None:
        return ToolOutcome({"error": "unknown_tool", "message": "Không có hàm này."}, ok=False)
    try:
        args = tool.args_model.model_validate(arguments)
    except ValidationError as error:
        return ToolOutcome(
            {"error": "invalid_arguments", "message": _describe_errors(error)}, ok=False
        )
    try:
        return tool.handler(ctx, args)
    except AuthorizationError:
        return ToolOutcome(
            {"error": "forbidden", "message": FORBIDDEN_MESSAGE}, ok=False, blocked=True
        )
    except ToolFailure as failure:
        return ToolOutcome({"error": failure.code, "message": str(failure)}, ok=False)
    except Exception:
        logger.exception("Hàm %s gặp lỗi", name)
        ctx.begin_read_only()  # savepoint có thể đã hỏng: làm lại, vẫn chỉ đọc
        return ToolOutcome(
            {"error": "internal_error", "message": "Hàm gặp lỗi, hãy báo người dùng thử lại."},
            ok=False,
        )

"""Ghi các bản ghi của một job vào bảng dữ liệu bằng upsert (D-060).

Chạy trong transaction của người gọi. Khoá duy nhất của Giai đoạn 1 làm chỗ dựa cho
`INSERT … ON CONFLICT DO UPDATE`, nên nhập lại cùng dữ liệu không bao giờ nhân đôi bản ghi. Đếm số
bản ghi thực sự được tạo và được sửa bằng `xmax = 0` (chỉ đúng với dòng vừa được chèn).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.classes.academic import Assessment, Attendance, ConductResult
from app.core.enums import (
    AssessmentKind,
    AttendanceStatus,
    CommentResult,
    ConductLevel,
    ImportKind,
)
from app.imports.models import ImportJob

CHUNK = 1000
INSERTED = literal_column("(xmax = 0)")  # True khi dòng vừa được chèn, False khi bị ghi đè


def _upsert(session: Session, statement: Any, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Chạy upsert theo từng đợt, trả (số bản ghi tạo mới, số bản ghi bị ghi đè)."""
    created = 0
    total = 0
    for start in range(0, len(rows), CHUNK):
        batch = rows[start : start + CHUNK]
        flags = session.execute(statement.returning(INSERTED), batch).all()
        created += sum(1 for (inserted,) in flags if inserted)
        total += len(flags)
    return created, total - created


def _write_assessments(session: Session, job: ImportJob) -> tuple[int, int]:
    rows = [
        {
            "class_student_id": record["class_student_id"],
            "subject_id": job.subject_id,
            "semester": job.semester,
            "kind": AssessmentKind(item["kind"]),
            "seq": item["seq"],
            "score": Decimal(item["score"]) if "score" in item else None,
            "comment_result": CommentResult(item["comment_result"])
            if "comment_result" in item
            else None,
        }
        for record in job.rows
        for item in record["items"]
    ]
    statement = insert(Assessment)
    statement = statement.on_conflict_do_update(
        index_elements=["class_student_id", "subject_id", "semester", "kind", "seq"],
        set_={
            "score": statement.excluded.score,
            "comment_result": statement.excluded.comment_result,
        },
    )
    return _upsert(session, statement, rows)


def _write_attendance(session: Session, job: ImportJob) -> tuple[int, int]:
    rows = [
        {
            "class_student_id": record["class_student_id"],
            "date": date.fromisoformat(record["date"]),
            "status": AttendanceStatus(record["status"]),
        }
        for record in job.rows
    ]
    statement = insert(Attendance)
    statement = statement.on_conflict_do_update(
        index_elements=["class_student_id", "date"], set_={"status": statement.excluded.status}
    )
    return _upsert(session, statement, rows)


def _write_conduct(session: Session, job: ImportJob) -> tuple[int, int]:
    def rows_for(with_comment: bool) -> list[dict[str, Any]]:
        return [
            {
                "class_student_id": record["class_student_id"],
                "period": job.period,
                "level": ConductLevel(record["level"]),
                **({"comment": record["comment"]} if with_comment else {}),
            }
            for record in job.rows
            if (record.get("comment") is not None) is with_comment
        ]

    created = updated = 0
    # Có nhận xét trong tệp thì ghi đè cả nhận xét; không có thì giữ nhận xét hiện có.
    for with_comment in (True, False):
        rows = rows_for(with_comment)
        if not rows:
            continue
        statement = insert(ConductResult)
        columns = {"level": statement.excluded.level}
        if with_comment:
            columns["comment"] = statement.excluded.comment
        statement = statement.on_conflict_do_update(
            index_elements=["class_student_id", "period"], set_=columns
        )
        made, changed = _upsert(session, statement, rows)
        created, updated = created + made, updated + changed
    return created, updated


def write_job(session: Session, job: ImportJob) -> tuple[int, int]:
    """Ghi mọi bản ghi của job; trả (đã tạo, đã sửa)."""
    if not job.rows:
        return 0, 0
    if job.kind is ImportKind.ASSESSMENTS:
        return _write_assessments(session, job)
    if job.kind is ImportKind.ATTENDANCE:
        return _write_attendance(session, job)
    return _write_conduct(session, job)

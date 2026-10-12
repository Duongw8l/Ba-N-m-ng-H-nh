"""Công cụ cho test nhập tệp: dựng tệp .xlsx/.csv và gọi API nhập trên DB seed."""

import csv
import io
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classes.academic import Assessment, Attendance, ConductResult
from app.classes.models import ClassStudent, Student

Cell = Any
Rows = Sequence[Sequence[Cell]]


def build_xlsx(rows: Rows, *, sheet_title: str = "Sheet1") -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = sheet_title
    for row in rows:
        sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_csv(
    rows: Rows, *, delimiter: str = ",", bom: bool = False, encoding: str = "utf-8"
) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n").writerows(rows)
    data = buffer.getvalue().encode(encoding)
    return b"\xef\xbb\xbf" + data if bom else data


@pytest.fixture
def xlsx() -> Callable[..., bytes]:
    return build_xlsx


@pytest.fixture
def csv_bytes() -> Callable[..., bytes]:
    return build_csv


# --- API nhập tệp trên dữ liệu seed -------------------------------------------------------------


@dataclass
class ScoreSheet:
    """Điểm của một môn trong DB, dưới dạng bảng "rộng" như sổ điểm điện tử."""

    headers: list[str]
    rows: list[list[Any]]  # STT, mã, họ tên, TX1..TXn, GK, CK, ĐTB
    tx_count: int

    def column(self, name: str) -> int:
        return self.headers.index(name)

    def to_xlsx(self, *, title_rows: int = 0) -> bytes:
        titles: list[list[Any]] = [["BẢNG ĐIỂM"] if i == 0 else [] for i in range(title_rows)]
        return build_xlsx([*titles, self.headers, *self.rows])


class ImportApi:
    """Gọi các endpoint nhập tệp bằng tài khoản seed và đọc dữ liệu hiện có để dựng tệp khớp DB."""

    def __init__(
        self,
        client: TestClient,
        session: Session,
        auth_headers: Callable[[str], dict[str, str]],
        class_id_of: Callable[[str], int],
        subject_id_of: Callable[[str], int],
    ) -> None:
        self.client = client
        self.session = session
        self.auth_headers = auth_headers
        self.class_id_of = class_id_of
        self.subject_id_of = subject_id_of

    # -- Gọi API --

    def upload(
        self,
        email: str | None,
        class_ref: str | int,
        kind: str,
        data: bytes,
        filename: str = "tep.xlsx",
        **form: Any,
    ) -> Any:
        class_id = class_ref if isinstance(class_ref, int) else self.class_id_of(class_ref)
        fields = {
            key: (
                "true"
                if value is True
                else json.dumps(value)
                if isinstance(value, dict)
                else str(value)
            )
            for key, value in form.items()
            if value is not None
        }
        headers = {} if email is None else self.auth_headers(email)
        return self.client.post(
            f"/api/v1/classes/{class_id}/import/{kind}",
            headers=headers,
            files={"file": (filename, data, "application/octet-stream")},
            data=fields,
        )

    def upload_scores(
        self,
        email: str,
        sheet: ScoreSheet,
        *,
        class_name: str = "11A2",
        subject: str = "Toán",
        semester: int = 1,
        **form: Any,
    ) -> Any:
        return self.upload(
            email,
            class_name,
            "assessments",
            sheet.to_xlsx(),
            subject_id=self.subject_id_of(subject),
            semester=semester,
            **form,
        )

    def confirm(self, email: str | None, job_id: Any) -> Any:
        headers = {} if email is None else self.auth_headers(email)
        return self.client.post(f"/api/v1/imports/{job_id}/confirm", headers=headers)

    # -- Dữ liệu hiện có trong DB --

    def score_sheet(
        self, class_name: str = "11A2", subject: str = "Toán", semester: int = 1
    ) -> ScoreSheet:
        class_id, subject_id = self.class_id_of(class_name), self.subject_id_of(subject)
        found = self.session.execute(
            select(
                Student.student_code,
                Student.full_name,
                Assessment.kind,
                Assessment.seq,
                Assessment.score,
            )
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .join(Assessment, Assessment.class_student_id == ClassStudent.id)
            .where(
                ClassStudent.class_id == class_id,
                Assessment.subject_id == subject_id,
                Assessment.semester == semester,
            )
            .order_by(Student.student_code)
        ).all()
        tx_count = max((seq for _, _, kind, seq, _ in found if kind.value == "tx"), default=0)
        per_student: dict[str, dict[str, Any]] = {}
        for code, name, kind, seq, score in found:
            entry = per_student.setdefault(code, {"name": name})
            key = f"tx{seq}" if kind.value == "tx" else kind.value
            entry[key] = None if score is None else float(score)
        headers = [
            "STT",
            "Mã HS",
            "Họ và tên",
            *(f"TX{i}" for i in range(1, tx_count + 1)),
            "GK",
            "CK",
            "ĐTB",
        ]
        rows = [
            [
                index,
                code,
                entry["name"],
                *(entry.get(f"tx{i}") for i in range(1, tx_count + 1)),
                entry.get("gk"),
                entry.get("ck"),
                "",
            ]
            for index, (code, entry) in enumerate(per_student.items(), start=1)
        ]
        return ScoreSheet(headers, rows, tx_count)

    def score_snapshot(
        self, class_name: str = "11A2", subject: str = "Toán", semester: int = 1
    ) -> dict[tuple[str, str, int], Decimal | None]:
        """(mã học sinh, kind, seq) -> điểm, đọc thẳng từ DB."""
        self.session.expire_all()
        found = self.session.execute(
            select(Student.student_code, Assessment.kind, Assessment.seq, Assessment.score)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .join(Assessment, Assessment.class_student_id == ClassStudent.id)
            .where(
                ClassStudent.class_id == self.class_id_of(class_name),
                Assessment.subject_id == self.subject_id_of(subject),
                Assessment.semester == semester,
            )
        ).all()
        return {(code, kind.value, seq): score for code, kind, seq, score in found}

    def attendance_rows(self, class_name: str = "11A2") -> list[tuple[str, date, str]]:
        found = self.session.execute(
            select(Student.student_code, Attendance.date, Attendance.status)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .join(Attendance, Attendance.class_student_id == ClassStudent.id)
            .where(ClassStudent.class_id == self.class_id_of(class_name))
            .order_by(Attendance.date, Student.student_code)
        ).all()
        return [(code, day, status.value) for code, day, status in found]

    def attendance_snapshot(self, class_name: str = "11A2") -> dict[tuple[str, date], str]:
        self.session.expire_all()
        return {(code, day): status for code, day, status in self.attendance_rows(class_name)}

    def conduct_rows(self, class_name: str = "11A2", period: str = "hk1") -> list[list[str]]:
        found = self.session.execute(
            select(Student.student_code, ConductResult.level, ConductResult.comment)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .join(ConductResult, ConductResult.class_student_id == ClassStudent.id)
            .where(
                ClassStudent.class_id == self.class_id_of(class_name),
                ConductResult.period == period,
            )
            .order_by(Student.student_code)
        ).all()
        return [[code, level.value, comment or ""] for code, level, comment in found]

    def conduct_snapshot(
        self, class_name: str = "11A2", period: str = "hk1"
    ) -> dict[str, tuple[str, str | None]]:
        self.session.expire_all()
        found = self.session.execute(
            select(Student.student_code, ConductResult.level, ConductResult.comment)
            .join(ClassStudent, ClassStudent.student_id == Student.id)
            .join(ConductResult, ConductResult.class_student_id == ClassStudent.id)
            .where(
                ClassStudent.class_id == self.class_id_of(class_name),
                ConductResult.period == period,
            )
        ).all()
        return {code: (level.value, comment) for code, level, comment in found}


@pytest.fixture
def imp(
    api_client: TestClient,
    db_session: Session,
    auth_headers: Callable[[str], dict[str, str]],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> ImportApi:
    return ImportApi(api_client, db_session, auth_headers, class_id_of, subject_id_of)

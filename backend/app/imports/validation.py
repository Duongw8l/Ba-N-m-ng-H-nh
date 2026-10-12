"""Kiểm từng dòng và so với dữ liệu hiện có (D-057, D-060, D-061).

Mỗi hàm nhận bảng đã đọc, ánh xạ cột và dữ liệu hiện có trong DB (đã tải sẵn), và trả một RowResult
cho mỗi dòng: lỗi (chặn xác nhận), cảnh báo (không chặn), và nếu có giá trị cần ghi thì kèm bản ghi
đã chuẩn hoá. Không đụng DB và không ghi gì ở đây, nên test được bằng dữ liệu dựng tay.

Quy tắc chung: ô trống không bao giờ xoá dữ liệu có sẵn; chỉ giá trị MỚI hoặc ĐỔI mới được ghi.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.core.enums import AttendanceStatus, CommentResult, ConductLevel
from app.imports.columns import FieldSpec
from app.imports.parsing import RawRow, RawTable
from app.imports.values import (
    CellError,
    format_score,
    parse_attendance_status,
    parse_comment_result,
    parse_conduct_level,
    parse_date,
    parse_note,
    parse_score,
)

RowStatus = Literal["ok", "warning", "error"]
RowAction = Literal["new", "changed", "unchanged"]


@dataclass(frozen=True)
class StudentRef:
    class_student_id: int
    full_name: str


@dataclass
class Message:
    column: str | None
    message: str


@dataclass
class RowResult:
    line: int
    student_code: str
    full_name: str | None = None  # họ tên trong hệ thống (không phải trong tệp)
    status: RowStatus = "ok"
    action: RowAction | None = None
    values: dict[str, str | None] = field(default_factory=dict)  # giá trị trong tệp, đã chuẩn hoá
    existing: dict[str, str | None] = field(default_factory=dict)  # giá trị cũ của ô sẽ đổi
    messages: list[Message] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)  # cái cần ghi (mới hoặc đổi)
    new_records: int = 0  # số bản ghi DB sẽ được tạo
    changed_records: int = 0  # số bản ghi DB đã có sẽ được sửa
    unchanged_records: int = 0

    def error(self, column: str | None, message: str) -> None:
        self.status = "error"
        self.messages.append(Message(column, message))

    def warn(self, column: str | None, message: str) -> None:
        if self.status != "error":
            self.status = "warning"
        self.messages.append(Message(column, message))

    def finish(self) -> "RowResult":
        if self.status == "error":
            self.records = []
            self.new_records = self.changed_records = self.unchanged_records = 0
            return self
        if self.changed_records:
            self.action = "changed"
        elif self.new_records:
            self.action = "new"
        else:
            self.action = "unchanged"
        return self


Index = dict[str, int | None]


def column_index(headers: Sequence[str], mapping: Mapping[str, str | None]) -> Index:
    """Trường -> chỉ số cột trong tệp (cột đầu tiên mang đúng tên đã ánh xạ)."""
    return {
        name: (list(headers).index(header) if header and header in headers else None)
        for name, header in mapping.items()
    }


def _cell(row: RawRow, index: Index, name: str) -> str:
    position = index.get(name)
    return "" if position is None else row.cells[position].strip()


def _header(headers: Sequence[str], index: Index, name: str, fallback: str) -> str:
    position = index.get(name)
    return fallback if position is None else headers[position]


def _identify(
    row: RawRow,
    table: RawTable,
    index: Index,
    students: Mapping[str, StudentRef],
    result: RowResult,
) -> StudentRef | None:
    """Tìm học sinh theo mã (không phân biệt hoa thường) và đối chiếu họ tên nếu tệp có cột tên."""
    code_header = _header(table.headers, index, "student_code", "Mã học sinh")
    code = result.student_code
    if not code:
        result.error(code_header, "Thiếu mã học sinh.")
        return None
    student = students.get(code.upper())
    if student is None:
        result.error(code_header, f"Mã học sinh '{code}' không có trong lớp.")
        return None
    result.full_name = student.full_name
    in_file = _cell(row, index, "full_name")
    if in_file and in_file.casefold() != student.full_name.casefold():
        result.warn(
            _header(table.headers, index, "full_name", "Họ và tên"),
            f"Họ tên trong tệp ('{in_file}') khác họ tên trong hệ thống ('{student.full_name}'). "
            "Hãy kiểm tra lại mã học sinh.",
        )
    return student


def _new_result(row: RawRow, index: Index) -> RowResult:
    return RowResult(line=row.line, student_code=_cell(row, index, "student_code"))


def _check_duplicate(
    result: RowResult, seen: dict[Any, int], key: Any, column: str, what: str
) -> None:
    if key in seen:
        result.error(column, f"{what} trùng với dòng {seen[key]}.")
    else:
        seen[key] = result.line


# --- Điểm ---------------------------------------------------------------------------------------

ScoreKey = tuple[int, str, int]  # (class_student_id, kind, seq)


def validate_scores(
    table: RawTable,
    mapping: Mapping[str, str | None],
    fields: Sequence[FieldSpec],
    *,
    students: Mapping[str, StudentRef],
    existing: Mapping[ScoreKey, Decimal | None],
    allow_partial: bool,
) -> list[RowResult]:
    """Môn điểm số: các cột tx1..txN, midterm, final của `fields` thành bản ghi `assessments`."""
    index = column_index(table.headers, mapping)
    # Trường điểm -> (kind, seq) trong bảng assessments.
    slots: dict[str, tuple[str, int]] = {}
    for spec in fields:
        if spec.name.startswith("tx"):
            slots[spec.name] = ("tx", int(spec.name[2:]))
        elif spec.name == "midterm":
            slots[spec.name] = ("gk", 1)
        elif spec.name == "final":
            slots[spec.name] = ("ck", 1)
    labels = {spec.name: spec.label for spec in fields}

    seen: dict[str, int] = {}
    results: list[RowResult] = []
    for row in table.rows:
        result = _new_result(row, index)
        student = _identify(row, table, index, students, result)
        if student is not None:
            _check_duplicate(
                result,
                seen,
                result.student_code.upper(),
                _header(table.headers, index, "student_code", "Mã học sinh"),
                "Mã học sinh",
            )
        items: list[dict[str, Any]] = []
        provided = 0
        for name, (kind, seq) in slots.items():
            if index.get(name) is None:
                continue  # trường không có trong tệp (chỉ xảy ra khi cho phép nhập dở)
            column = _header(table.headers, index, name, labels[name])
            text = _cell(row, index, name)
            result.values[name] = None
            if not text:
                if allow_partial:
                    result.warn(column, f"Thiếu {labels[name].lower()} (được phép nhập dở).")
                else:
                    result.error(column, f"Thiếu {labels[name].lower()}.")
                continue
            try:
                score = parse_score(text)
            except CellError as error:
                result.values[name] = text
                result.error(column, str(error))
                continue
            provided += 1
            result.values[name] = str(score)
            if student is None:
                continue
            old = existing.get((student.class_student_id, kind, seq))
            if (student.class_student_id, kind, seq) not in existing:
                result.new_records += 1
                items.append({"kind": kind, "seq": seq, "score": str(score)})
            elif old != score:
                result.changed_records += 1
                result.existing[name] = None if old is None else format_score(old)
                items.append({"kind": kind, "seq": seq, "score": str(score)})
            else:
                result.unchanged_records += 1
        if student is not None and items:
            result.records.append({"class_student_id": student.class_student_id, "items": items})
        if provided == 0 and result.status != "error":
            result.warn(None, "Dòng không có điểm nào.")
        results.append(result.finish())
    return results


def validate_comments(
    table: RawTable,
    mapping: Mapping[str, str | None],
    *,
    students: Mapping[str, StudentRef],
    existing: Mapping[int, CommentResult | None],
    allow_partial: bool,
) -> list[RowResult]:
    """Môn đánh giá bằng nhận xét: mỗi học kỳ một dòng `ck` với Đạt / Chưa đạt (D-035)."""
    index = column_index(table.headers, mapping)
    column = _header(table.headers, index, "comment_result", "Nhận xét")
    seen: dict[str, int] = {}
    results: list[RowResult] = []
    for row in table.rows:
        result = _new_result(row, index)
        student = _identify(row, table, index, students, result)
        if student is not None:
            _check_duplicate(
                result,
                seen,
                result.student_code.upper(),
                _header(table.headers, index, "student_code", "Mã học sinh"),
                "Mã học sinh",
            )
        text = _cell(row, index, "comment_result")
        result.values["comment_result"] = None
        if not text:
            if allow_partial:
                result.warn(column, "Thiếu kết quả nhận xét (được phép nhập dở).")
            else:
                result.error(column, "Thiếu kết quả nhận xét (Đạt hoặc Chưa đạt).")
        else:
            try:
                value = parse_comment_result(text)
            except CellError as error:
                result.values["comment_result"] = text
                result.error(column, str(error))
            else:
                result.values["comment_result"] = value.value
                if student is not None:
                    old = existing.get(student.class_student_id)
                    record = {
                        "class_student_id": student.class_student_id,
                        "items": [{"kind": "ck", "seq": 1, "comment_result": value.value}],
                    }
                    if student.class_student_id not in existing:
                        result.new_records += 1
                        result.records.append(record)
                    elif old is not value:
                        result.changed_records += 1
                        result.existing["comment_result"] = None if old is None else old.value
                        result.records.append(record)
                    else:
                        result.unchanged_records += 1
        results.append(result.finish())
    return results


# --- Điểm danh ----------------------------------------------------------------------------------


def validate_attendance(
    table: RawTable,
    mapping: Mapping[str, str | None],
    *,
    students: Mapping[str, StudentRef],
    existing: Mapping[tuple[int, date], AttendanceStatus],
    year_start: date,
    year_end: date,
) -> list[RowResult]:
    index = column_index(table.headers, mapping)
    date_column = _header(table.headers, index, "date", "Ngày")
    status_column = _header(table.headers, index, "status", "Trạng thái")
    seen: dict[tuple[str, date], int] = {}
    results: list[RowResult] = []
    for row in table.rows:
        result = _new_result(row, index)
        student = _identify(row, table, index, students, result)
        day: date | None = None
        status: AttendanceStatus | None = None

        date_text = _cell(row, index, "date")
        result.values["date"] = date_text or None
        if not date_text:
            result.error(date_column, "Thiếu ngày.")
        else:
            try:
                day = parse_date(date_text)
            except CellError as error:
                result.error(date_column, str(error))
            else:
                result.values["date"] = day.isoformat()
                if not year_start <= day <= year_end:
                    result.error(
                        date_column,
                        f"Ngày {day.strftime('%d/%m/%Y')} nằm ngoài năm học "
                        f"({year_start.strftime('%d/%m/%Y')} đến {year_end.strftime('%d/%m/%Y')}).",
                    )
                    day = None

        status_text = _cell(row, index, "status")
        result.values["status"] = status_text or None
        if not status_text:
            result.error(status_column, "Thiếu trạng thái.")
        else:
            try:
                status = parse_attendance_status(status_text)
            except CellError as error:
                result.error(status_column, str(error))
            else:
                result.values["status"] = status.value

        if student is not None and day is not None:
            _check_duplicate(
                result,
                seen,
                (result.student_code.upper(), day),
                date_column,
                "Ngày điểm danh của học sinh này",
            )
        if student is not None and day is not None and status is not None:
            key = (student.class_student_id, day)
            old = existing.get(key)
            record = {
                "class_student_id": student.class_student_id,
                "date": day.isoformat(),
                "status": status.value,
            }
            if old is None:
                result.new_records += 1
                result.records.append(record)
            elif old is not status:
                result.changed_records += 1
                result.existing["status"] = old.value
                result.records.append(record)
            else:
                result.unchanged_records += 1
        results.append(result.finish())
    return results


# --- Rèn luyện ----------------------------------------------------------------------------------


def validate_conduct(
    table: RawTable,
    mapping: Mapping[str, str | None],
    *,
    students: Mapping[str, StudentRef],
    existing: Mapping[int, tuple[ConductLevel, str | None]],
) -> list[RowResult]:
    index = column_index(table.headers, mapping)
    level_column = _header(table.headers, index, "level", "Mức rèn luyện")
    note_column = _header(table.headers, index, "comment", "Nhận xét")
    seen: dict[str, int] = {}
    results: list[RowResult] = []
    for row in table.rows:
        result = _new_result(row, index)
        student = _identify(row, table, index, students, result)
        if student is not None:
            _check_duplicate(
                result,
                seen,
                result.student_code.upper(),
                _header(table.headers, index, "student_code", "Mã học sinh"),
                "Mã học sinh",
            )
        level: ConductLevel | None = None
        level_text = _cell(row, index, "level")
        result.values["level"] = level_text or None
        if not level_text:
            result.error(level_column, "Thiếu mức rèn luyện.")
        else:
            try:
                level = parse_conduct_level(level_text)
            except CellError as error:
                result.error(level_column, str(error))
            else:
                result.values["level"] = level.value

        note: str | None = None
        note_text = _cell(row, index, "comment")
        result.values["comment"] = note_text or None
        if note_text:
            try:
                note = parse_note(note_text)
            except CellError as error:
                result.error(note_column, str(error))

        if student is not None and level is not None and result.status != "error":
            old = existing.get(student.class_student_id)
            record = {
                "class_student_id": student.class_student_id,
                "level": level.value,
                "comment": note,
            }
            if old is None:
                result.new_records += 1
                result.records.append(record)
            elif old[0] is not level or (note is not None and note != old[1]):
                result.changed_records += 1
                result.existing["level"] = old[0].value
                if note is not None and note != old[1]:
                    result.existing["comment"] = old[1]
                result.records.append(record)
            else:
                result.unchanged_records += 1
        results.append(result.finish())
    return results

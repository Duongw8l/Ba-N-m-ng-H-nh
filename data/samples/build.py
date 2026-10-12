"""Sinh ba tệp mẫu để thử luồng nhập dữ liệu (Giai đoạn 4) từ chính bộ sinh của seed.

Mã học sinh, họ tên và điểm lấy từ `generate()` với tham số mặc định, nên khớp DB sau `make seed`.
Chỉ dữ liệu giả lập (nguyên tắc 7). ĐTB trong tệp điểm tính bằng `app.analytics.scores` với hệ số
đọc từ bảng `settings` (nguyên tắc 2), nên đây không phải nơi thứ hai cài công thức.

Ba tệp (xem data/samples/README.md):
- diem-toan-11a2-hk1.xlsx: sổ điểm Toán 11A2 học kỳ I, đúng; khác DB ở 3 học sinh.
- diem-toan-11a2-hk1-loi.xlsx: cùng sổ điểm nhưng có lỗi cài sẵn (danh sách FAULTS).
- diem-danh-11a2-2027-03.csv: điểm danh cả lớp 11A2 tháng 3/2027 (UTF-8 có BOM).
"""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from openpyxl import Workbook

from app.analytics.config import AnalyticsConfig
from app.analytics.scores import semester_average_from_scores
from app.core.enums import AttendanceStatus
from app.core.labels import label_vi
from data.seed.generate import TableRows, generate
from data.seed.params import SeedParams

CLASS_NAME = "11A2"
SUBJECT_NAME = "Toán"
SEMESTER = 1
ATTENDANCE_MONTH = (2027, 3)

CORRECT_XLSX = "diem-toan-11a2-hk1.xlsx"
FAULTY_XLSX = "diem-toan-11a2-hk1-loi.xlsx"
ATTENDANCE_CSV = "diem-danh-11a2-2027-03.csv"

TITLE_ROWS = 3  # hai dòng tiêu đề lớn và một dòng trống phía trên bảng, như sổ điểm xuất ra
HEADER_LINE = TITLE_ROWS + 1
FIRST_DATA_LINE = HEADER_LINE + 1

# Học sinh (vị trí trong lớp, xếp theo mã) bị sửa một điểm so với DB: (vị trí, loại, số thứ tự).
CHANGED = ((4, "tx", 2), (17, "gk", 1), (30, "ck", 1))
BUMP = Decimal("0.5")

Severity = Literal["error", "warning", "ok"]


@dataclass(frozen=True)
class Fault:
    """Lỗi cài sẵn ở một học sinh của tệp `FAULTY_XLSX`: dòng, cột và đoạn thông điệp phải thấy."""

    index: int  # vị trí học sinh trong lớp, từ 0; dòng trong tệp = FIRST_DATA_LINE + index
    column: str
    severity: Severity
    fragment: str

    @property
    def line(self) -> int:
        return FIRST_DATA_LINE + self.index


FAULTS = (
    Fault(2, "Mã HS", "error", "không có trong lớp"),
    Fault(5, "ĐĐGgk", "error", "nằm ngoài khoảng từ 0 đến 10"),
    Fault(8, "ĐĐGtx 1", "error", "không phải là số"),
    Fault(11, "Mã HS", "error", f"trùng với dòng {FIRST_DATA_LINE + 10}"),
    Fault(14, "ĐĐGtx 3", "error", "Thiếu"),
    Fault(17, "ĐĐGck", "error", "quá 1 chữ số thập phân"),
    Fault(23, "Họ và tên", "warning", "khác họ tên"),
)
COMMA_STUDENT = 20  # điểm viết "7,5" kiểu Việt Nam: hợp lệ, không lỗi, không cảnh báo
UNKNOWN_CODE = "HS1102999"
WRONG_NAME = "Nguyễn Văn Khác"


@dataclass(frozen=True)
class _Member:
    class_student_id: int
    code: str
    full_name: str


def _members(data: TableRows) -> list[_Member]:
    class_id = next(row["id"] for row in data["classes"] if row["name"] == CLASS_NAME)
    students = {row["id"]: row for row in data["students"]}
    members = [
        _Member(
            link["id"],
            students[link["student_id"]]["student_code"],
            students[link["student_id"]]["full_name"],
        )
        for link in data["class_students"]
        if link["class_id"] == class_id
    ]
    return sorted(members, key=lambda member: member.code)


def headers(tx_count: int) -> list[str]:
    return [
        "STT",
        "Mã HS",
        "Họ và tên",
        *(f"ĐĐGtx {i}" for i in range(1, tx_count + 1)),
        "ĐĐGgk",
        "ĐĐGck",
        "ĐTB",
    ]


@dataclass
class _Scores:
    tx: list[Decimal]
    gk: Decimal
    ck: Decimal

    def set(self, kind: str, seq: int, value: Decimal) -> None:
        if kind == "tx":
            self.tx[seq - 1] = value
        elif kind == "gk":
            self.gk = value
        else:
            self.ck = value

    def get(self, kind: str, seq: int) -> Decimal:
        return self.tx[seq - 1] if kind == "tx" else (self.gk if kind == "gk" else self.ck)


def _scores(data: TableRows, members: list[_Member], tx_count: int) -> dict[int, _Scores]:
    subject_id = next(row["id"] for row in data["subjects"] if row["name"] == SUBJECT_NAME)
    found: dict[int, dict[tuple[str, int], Decimal]] = defaultdict(dict)
    for row in data["assessments"]:
        if row["subject_id"] == subject_id and row["semester"] == SEMESTER:
            found[row["class_student_id"]][(row["kind"].value, row["seq"])] = row["score"]
    return {
        member.class_student_id: _Scores(
            tx=[found[member.class_student_id][("tx", seq)] for seq in range(1, tx_count + 1)],
            gk=found[member.class_student_id][("gk", 1)],
            ck=found[member.class_student_id][("ck", 1)],
        )
        for member in members
    }


def _tx_count(data: TableRows, config: AnalyticsConfig) -> int:
    periods = next(
        row["periods_per_year"] for row in data["subjects"] if row["name"] == SUBJECT_NAME
    )
    return config.required_regular(periods)


def _score_cells(scores: _Scores, config: AnalyticsConfig) -> list[Any]:
    average = semester_average_from_scores(scores.tx, scores.gk, scores.ck, config)
    return [*(float(v) for v in scores.tx), float(scores.gk), float(scores.ck), float(average or 0)]


def _workbook_bytes(grid: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Bảng điểm"
    for row in grid:
        sheet.append(row)
    sheet.column_dimensions["C"].width = 28
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _title_rows() -> list[list[Any]]:
    return [
        ["SỞ GIÁO DỤC VÀ ĐÀO TẠO (DỮ LIỆU GIẢ LẬP)"],
        [
            f"BẢNG ĐIỂM MÔN {SUBJECT_NAME.upper()} - LỚP {CLASS_NAME} - HỌC KỲ {SEMESTER} "
            "- NĂM HỌC 2026-2027"
        ],
        [],
    ]


def _comma(value: float) -> str:
    return str(value).replace(".", ",")


def correct_score_grid(data: TableRows, config: AnalyticsConfig) -> list[list[Any]]:
    """Sổ điểm đúng: điểm như DB, trừ ba điểm bị sửa (`CHANGED`)."""
    members = _members(data)
    tx_count = _tx_count(data, config)
    scores = _scores(data, members, tx_count)
    for position, kind, seq in CHANGED:
        current = scores[members[position].class_student_id]
        old = current.get(kind, seq)
        current.set(kind, seq, old + BUMP if old <= Decimal("9.5") else old - BUMP)
    rows = [
        [
            index,
            member.code,
            member.full_name,
            *_score_cells(scores[member.class_student_id], config),
        ]
        for index, member in enumerate(members, start=1)
    ]
    return [*_title_rows(), headers(tx_count), *rows]


def faulty_score_grid(data: TableRows, config: AnalyticsConfig) -> list[list[Any]]:
    """Sổ điểm đúng như DB nhưng có các lỗi cài sẵn trong `FAULTS` và một dòng dấu phẩy hợp lệ."""
    members = _members(data)
    tx_count = _tx_count(data, config)
    scores = _scores(data, members, tx_count)
    head = headers(tx_count)
    column = {name: head.index(name) for name in head}
    rows = [
        [
            index,
            member.code,
            member.full_name,
            *_score_cells(scores[member.class_student_id], config),
        ]
        for index, member in enumerate(members, start=1)
    ]

    rows[2][column["Mã HS"]] = UNKNOWN_CODE
    rows[5][column["ĐĐGgk"]] = 11
    rows[8][column["ĐĐGtx 1"]] = "tám"
    rows[11][column["Mã HS"]] = rows[10][column["Mã HS"]]
    rows[11][column["Họ và tên"]] = rows[10][column["Họ và tên"]]
    rows[14][column["ĐĐGtx 3"]] = None
    rows[17][column["ĐĐGck"]] = "8,25"
    rows[23][column["Họ và tên"]] = WRONG_NAME
    rows[COMMA_STUDENT][column["ĐĐGtx 1"]] = _comma(rows[COMMA_STUDENT][column["ĐĐGtx 1"]])
    return [*_title_rows(), head, *rows]


def attendance_grid(data: TableRows) -> list[list[str]]:
    """Điểm danh cả lớp trong tháng `ATTENDANCE_MONTH`, mỗi dòng một học sinh một ngày."""
    members = {member.class_student_id: member for member in _members(data)}
    month_rows = [
        row
        for row in data["attendance"]
        if row["class_student_id"] in members
        and (row["date"].year, row["date"].month) == ATTENDANCE_MONTH
    ]
    month_rows.sort(key=lambda row: (row["date"], members[row["class_student_id"]].code))
    return [
        ["Mã HS", "Họ và tên", "Ngày", "Trạng thái"],
        *(
            [
                members[row["class_student_id"]].code,
                members[row["class_student_id"]].full_name,
                row["date"].strftime("%d/%m/%Y"),
                label_vi(AttendanceStatus(row["status"])),
            ]
            for row in month_rows
        ),
    ]


def _csv_bytes(grid: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerows(grid)
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")  # BOM để Excel mở đúng tiếng Việt


def build_samples(config: AnalyticsConfig) -> dict[str, bytes]:
    """Tên tệp -> nội dung. Dữ liệu sinh với tham số mặc định (không --hold-out)."""
    data = generate(SeedParams(), config.regular_assessment_count, "khong-dung-mat-khau")
    return {
        CORRECT_XLSX: _workbook_bytes(correct_score_grid(data, config)),
        FAULTY_XLSX: _workbook_bytes(faulty_score_grid(data, config)),
        ATTENDANCE_CSV: _csv_bytes(attendance_grid(data)),
    }

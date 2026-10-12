"""Đổi từng ô (chuỗi) sang giá trị đã chuẩn hoá, hoặc báo lỗi bằng tiếng Việt (D-057, D-061).

Điểm đi qua Decimal, không qua số thực. Điểm có hơn 1 chữ số thập phân là LỖI, không tự làm tròn:
tự làm tròn âm thầm sẽ đổi điểm của học sinh (thay phần "chuẩn hoá về 1 chữ số" của D-035).
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypeVar

from app.core.enums import AttendanceStatus, CommentResult, ConductLevel
from app.imports.columns import normalize_header

ONE_DECIMAL = Decimal("0.1")
MAX_COMMENT_LENGTH = 500


class CellError(ValueError):
    """Giá trị của một ô không hợp lệ; thông điệp đã là tiếng Việt, hiển thị cho giáo viên."""


PLAIN_NUMBER = re.compile(r"-?(\d+([.,]\d*)?|[.,]\d+)")


def parse_score(text: str) -> Decimal:
    """Điểm 0 đến 10, tối đa 1 chữ số thập phân; chấp nhận "7,5" và "7.5".

    Chỉ nhận số viết thường ("1e1", "NaN", "Infinity" mà Decimal chấp nhận đều bị từ chối).
    """
    cleaned = text.strip().replace(",", ".")
    if not PLAIN_NUMBER.fullmatch(text.strip()):
        raise CellError(f"'{text}' không phải là số.")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise CellError(f"'{text}' không phải là số.") from None
    if value < 0 or value > 10:
        raise CellError(f"Điểm {text} nằm ngoài khoảng từ 0 đến 10.")
    rounded = value.quantize(ONE_DECIMAL)
    if rounded != value:
        raise CellError(f"Điểm {text} có quá 1 chữ số thập phân.")
    return rounded


def format_score(score: Decimal) -> str:
    """Điểm để hiển thị: tối thiểu 1 chữ số thập phân, bỏ số 0 thừa ("4.70" thành "4.7")."""
    trimmed = score.normalize()
    exponent = trimmed.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= 0:
        return str(trimmed.quantize(ONE_DECIMAL))
    return format(trimmed, "f")


_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S")


def parse_date(text: str) -> date:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise CellError(f"'{text}' không phải là ngày (dùng dd/mm/yyyy hoặc yyyy-mm-dd).")


T = TypeVar("T")


def _lookup(text: str, table: dict[str, T], what: str) -> T:
    key = normalize_header(text)
    if key not in table:
        raise CellError(f"{what} '{text}' không hợp lệ.")
    return table[key]


_ATTENDANCE: dict[str, AttendanceStatus] = {
    "comat": AttendanceStatus.PRESENT,
    "present": AttendanceStatus.PRESENT,
    "nghicophep": AttendanceStatus.ABSENT_EXCUSED,
    "vangcophep": AttendanceStatus.ABSENT_EXCUSED,
    "absentexcused": AttendanceStatus.ABSENT_EXCUSED,
    "cp": AttendanceStatus.ABSENT_EXCUSED,
    "p": AttendanceStatus.ABSENT_EXCUSED,
    "nghikhongphep": AttendanceStatus.ABSENT_UNEXCUSED,
    "vangkhongphep": AttendanceStatus.ABSENT_UNEXCUSED,
    "absentunexcused": AttendanceStatus.ABSENT_UNEXCUSED,
    "kp": AttendanceStatus.ABSENT_UNEXCUSED,
    "k": AttendanceStatus.ABSENT_UNEXCUSED,
    "muon": AttendanceStatus.LATE,
    "dimuon": AttendanceStatus.LATE,
    "late": AttendanceStatus.LATE,
    "m": AttendanceStatus.LATE,
}


def parse_attendance_status(text: str) -> AttendanceStatus:
    return _lookup(text, _ATTENDANCE, "Trạng thái")


_CONDUCT: dict[str, ConductLevel] = {
    "tot": ConductLevel.GOOD,
    "good": ConductLevel.GOOD,
    "t": ConductLevel.GOOD,
    "kha": ConductLevel.FAIR,
    "fair": ConductLevel.FAIR,
    "k": ConductLevel.FAIR,
    "dat": ConductLevel.PASS,
    "pass": ConductLevel.PASS,
    "d": ConductLevel.PASS,
    "chuadat": ConductLevel.FAIL,
    "fail": ConductLevel.FAIL,
    "cd": ConductLevel.FAIL,
}


def parse_conduct_level(text: str) -> ConductLevel:
    return _lookup(text, _CONDUCT, "Mức rèn luyện")


_COMMENT_RESULT: dict[str, CommentResult] = {
    "dat": CommentResult.PASS,
    "pass": CommentResult.PASS,
    "d": CommentResult.PASS,
    "chuadat": CommentResult.FAIL,
    "fail": CommentResult.FAIL,
    "cd": CommentResult.FAIL,
}


def parse_comment_result(text: str) -> CommentResult:
    return _lookup(text, _COMMENT_RESULT, "Kết quả nhận xét")


def parse_note(text: str) -> str:
    if len(text) > MAX_COMMENT_LENGTH:
        raise CellError(f"Nhận xét dài quá {MAX_COMMENT_LENGTH} ký tự.")
    return text

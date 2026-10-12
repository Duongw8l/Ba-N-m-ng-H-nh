"""Đổi từng ô sang giá trị chuẩn hoá: điểm, ngày, trạng thái, mức rèn luyện, nhận xét (D-061)."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.enums import AttendanceStatus, CommentResult, ConductLevel
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", "0.0"),
        ("10", "10.0"),
        ("7", "7.0"),
        ("7.5", "7.5"),
        ("7,5", "7.5"),  # dấu phẩy kiểu Việt Nam
        (" 8.0 ", "8.0"),
        ("8.70", "8.7"),  # số 0 thừa không phải chữ số thập phân thật
        ("0,1", "0.1"),
    ],
)
def test_valid_scores(text: str, expected: str) -> None:
    assert parse_score(text) == Decimal(expected)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ("4.70", "4.7"),
        ("8.00", "8.0"),
        ("10.00", "10.0"),
        ("0.00", "0.0"),
        ("0", "0.0"),
        ("7.5", "7.5"),
        ("4.75", "4.75"),  # không làm tròn che mất chữ số thật
    ],
)
def test_format_score_shows_at_least_one_decimal_without_trailing_zeros(
    score: str, expected: str
) -> None:
    assert format_score(Decimal(score)) == expected


@pytest.mark.parametrize("text", ["10.1", "10,1", "11", "100", "-1", "-0.1", "-5"])
def test_score_outside_0_to_10_is_an_error(text: str) -> None:
    with pytest.raises(CellError, match="khoảng từ 0 đến 10"):
        parse_score(text)


@pytest.mark.parametrize("text", ["7.25", "7,25", "8.55", "9.99", "0.05"])
def test_score_with_more_than_one_decimal_is_an_error_not_rounded(text: str) -> None:
    with pytest.raises(CellError, match="1 chữ số thập phân"):
        parse_score(text)


@pytest.mark.parametrize("text", ["abc", "8 điểm", "x", "--", "NaN", "Infinity", "1e1", "8..5"])
def test_score_that_is_not_a_number(text: str) -> None:
    with pytest.raises(CellError):
        parse_score(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("04/03/2027", date(2027, 3, 4)),
        ("4/3/2027", date(2027, 3, 4)),
        ("04-03-2027", date(2027, 3, 4)),
        ("2027-03-04", date(2027, 3, 4)),
        ("2027-03-04 00:00:00", date(2027, 3, 4)),
        ("  04/03/2027 ", date(2027, 3, 4)),
    ],
)
def test_valid_dates_are_day_first(text: str, expected: date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize("text", ["31/02/2027", "2027/13/01", "hôm qua", "03/04", "13/13/2027"])
def test_invalid_dates(text: str) -> None:
    with pytest.raises(CellError, match="không phải là ngày"):
        parse_date(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có mặt", AttendanceStatus.PRESENT),
        ("co mat", AttendanceStatus.PRESENT),
        ("present", AttendanceStatus.PRESENT),
        ("Nghỉ có phép", AttendanceStatus.ABSENT_EXCUSED),
        ("CP", AttendanceStatus.ABSENT_EXCUSED),
        ("absent_excused", AttendanceStatus.ABSENT_EXCUSED),
        ("Nghỉ không phép", AttendanceStatus.ABSENT_UNEXCUSED),
        ("KP", AttendanceStatus.ABSENT_UNEXCUSED),
        ("kp", AttendanceStatus.ABSENT_UNEXCUSED),
        ("Muộn", AttendanceStatus.LATE),
        ("M", AttendanceStatus.LATE),
        ("late", AttendanceStatus.LATE),
    ],
)
def test_attendance_status(text: str, expected: AttendanceStatus) -> None:
    assert parse_attendance_status(text) is expected


@pytest.mark.parametrize("text", ["Vắng", "nghỉ", "x", "1", "có phép"])
def test_unknown_attendance_status(text: str) -> None:
    with pytest.raises(CellError, match="Trạng thái"):
        parse_attendance_status(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tốt", ConductLevel.GOOD),
        ("tot", ConductLevel.GOOD),
        ("Khá", ConductLevel.FAIR),
        ("Đạt", ConductLevel.PASS),
        ("Dat", ConductLevel.PASS),
        ("Chưa đạt", ConductLevel.FAIL),
        ("chua dat", ConductLevel.FAIL),
        ("CĐ", ConductLevel.FAIL),
        ("good", ConductLevel.GOOD),
        ("fair", ConductLevel.FAIR),
        ("pass", ConductLevel.PASS),
        ("fail", ConductLevel.FAIL),
    ],
)
def test_conduct_level(text: str, expected: ConductLevel) -> None:
    assert parse_conduct_level(text) is expected


@pytest.mark.parametrize("text", ["Xuất sắc", "Yếu", "Trung bình", "A", ""])
def test_unknown_conduct_level(text: str) -> None:
    with pytest.raises(CellError, match="Mức rèn luyện"):
        parse_conduct_level(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Đạt", CommentResult.PASS),
        ("Đ", CommentResult.PASS),
        ("pass", CommentResult.PASS),
        ("Chưa đạt", CommentResult.FAIL),
        ("CĐ", CommentResult.FAIL),
        ("fail", CommentResult.FAIL),
    ],
)
def test_comment_result(text: str, expected: CommentResult) -> None:
    assert parse_comment_result(text) is expected


@pytest.mark.parametrize("text", ["Tốt", "8", "Khá"])
def test_comment_result_does_not_accept_conduct_levels_or_numbers(text: str) -> None:
    with pytest.raises(CellError):
        parse_comment_result(text)


def test_note_length_limit() -> None:
    assert parse_note("a" * 500) == "a" * 500
    with pytest.raises(CellError, match="500"):
        parse_note("a" * 501)

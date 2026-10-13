"""Kiểm từng dòng của danh sách học sinh (D-100), tính tay từng quy tắc. Không cần DB."""

from datetime import date

import pytest

from app.imports.columns import ROSTER_FIELDS, auto_map
from app.imports.parsing import RawRow, RawTable
from app.imports.roster import Memberships, codes_in, validate_roster
from app.imports.validation import RowResult
from app.imports.values import CellError, parse_phone

TODAY = date(2026, 10, 13)
CLASS_ID = 7
HEADERS = ["Mã HS", "Họ và tên", "Ngày sinh", "Phụ huynh", "SĐT phụ huynh"]
MAPPING: dict[str, str | None] = {
    "student_code": "Mã HS",
    "full_name": "Họ và tên",
    "date_of_birth": "Ngày sinh",
    "guardian_name": "Phụ huynh",
    "guardian_phone": "SĐT phụ huynh",
}


def table(rows: list[list[str]], headers: list[str] = HEADERS) -> RawTable:
    return RawTable(
        headers=tuple(headers),
        header_line=1,
        rows=tuple(RawRow(line=2 + i, cells=tuple(row)) for i, row in enumerate(rows)),
    )


def check(rows: list[list[str]], memberships: Memberships | None = None) -> list[RowResult]:
    return validate_roster(
        table(rows), MAPPING, class_id=CLASS_ID, memberships=memberships or {}, today=TODAY
    )


def messages(result: RowResult) -> list[tuple[str | None, str]]:
    return [(m.column, m.message) for m in result.messages]


GOOD = ["HS2001", "Nguyễn  Văn   An", "05/03/2011", "Nguyễn Văn Bình", "0912 345 678"]


# --- Một dòng hợp lệ ---------------------------------------------------------------------------


def test_a_good_row_is_normalised_and_becomes_a_new_record() -> None:
    [result] = check([GOOD])

    assert (result.status, result.action) == ("ok", "new")
    assert result.student_code == "HS2001"
    assert result.full_name == "Nguyễn Văn An"  # khoảng trắng thừa gộp lại, tên lấy từ TỆP
    assert result.values == {
        "date_of_birth": "2011-03-05",
        "guardian_name": "Nguyễn Văn Bình",
        "guardian_phone": "0912345678",
    }
    assert result.records == [
        {
            "student_code": "HS2001",
            "full_name": "Nguyễn Văn An",
            "date_of_birth": "2011-03-05",
            "guardian_name": "Nguyễn Văn Bình",
            "guardian_phone": "0912345678",
        }
    ]
    assert (result.new_records, result.changed_records) == (1, 0)
    assert result.existing == {}  # không bao giờ có giá trị cũ


def test_the_code_is_upper_cased_and_optional_columns_may_be_empty() -> None:
    [result] = check([["hs2002", "Lê Thị Bích", "", "", ""]])

    assert (result.status, result.action) == ("ok", "new")
    assert result.student_code == "HS2002"
    assert result.records[0]["date_of_birth"] is None
    assert result.records[0]["guardian_phone"] is None


def test_a_student_already_in_this_class_is_an_update_without_showing_old_values() -> None:
    [result] = check([GOOD], memberships={"HS2001": [(CLASS_ID, "11A9")]})

    assert (result.status, result.action) == ("ok", "changed")
    assert (result.new_records, result.changed_records) == (0, 1)
    assert result.existing == {}


# --- Lỗi chặn xác nhận ---------------------------------------------------------------------------


def test_a_student_of_another_class_is_an_error_naming_the_class() -> None:
    [result] = check([GOOD], memberships={"HS2001": [(3, "11A2")]})

    assert result.status == "error"
    assert messages(result) == [("Mã HS", "Mã học sinh 'HS2001' đã thuộc lớp 11A2.")]
    assert result.records == [] and result.action is None


def test_a_student_in_this_class_and_another_is_still_an_error() -> None:
    [result] = check([GOOD], memberships={"HS2001": [(CLASS_ID, "11A9"), (3, "11A2")]})

    assert result.status == "error"


@pytest.mark.parametrize(
    ("row", "column", "fragment"),
    [
        (["", "An", "", "", ""], "Mã HS", "Thiếu mã"),
        (["HS 01", "An", "", "", ""], "Mã HS", "không hợp lệ"),
        (["H" * 21, "An", "", "", ""], "Mã HS", "tối đa 20"),
        (["HS01", "", "", "", ""], "Họ và tên", "Thiếu họ"),
        (["HS01", "x" * 101, "", "", ""], "Họ và tên", "dài quá 100"),
        (["HS01", "An", "31/02/2011", "", ""], "Ngày sinh", "không phải là ngày"),
        (["HS01", "An", "01/01/2030", "", ""], "Ngày sinh", "ở tương lai"),
        (["HS01", "An", "", "x" * 101, ""], "Phụ huynh", "dài quá 100"),
        (["HS01", "An", "", "", "abc"], "SĐT phụ huynh", "không phải là số điện thoại"),
        (["HS01", "An", "", "", "012345"], "SĐT phụ huynh", "không hợp lệ"),
    ],
)
def test_each_invalid_cell_is_an_error_on_its_own_column(
    row: list[str], column: str, fragment: str
) -> None:
    [result] = check([row])

    assert result.status == "error", row
    assert [c for c, _ in messages(result)] == [column]
    assert fragment in messages(result)[0][1]
    assert result.records == []


def test_a_code_repeated_in_the_file_is_an_error_on_the_second_row_only() -> None:
    first, second = check([GOOD, [*GOOD[:1], "Người khác", "", "", ""]])
    lower_case_again = check([GOOD, ["hs2001", "Người khác", "", "", ""]])[1]

    assert first.status == "ok"
    assert second.status == "error" and "trùng với dòng 2" in messages(second)[0][1]
    assert lower_case_again.status == "error"  # không phân biệt hoa thường


# --- Cảnh báo không chặn -----------------------------------------------------------------------


def test_an_odd_age_is_only_a_warning() -> None:
    old, young = check(
        [
            ["HS01", "An", "01/01/1990", "", ""],  # 36 tuổi
            ["HS02", "Bình", "01/01/2020", "", ""],  # 6 tuổi
        ]
    )

    for result in (old, young):
        assert result.status == "warning" and result.action == "new"
        assert "bất thường" in messages(result)[0][1]
        assert result.records  # vẫn ghi được


def test_age_is_counted_by_whole_years_on_the_birthday() -> None:
    # Hôm nay 13/10/2026: sinh 13/10/2013 vừa đủ 13 tuổi (được); sinh 14/10/2013 mới 12 tuổi.
    exactly, day_short = check(
        [["HS01", "An", "13/10/2013", "", ""], ["HS02", "Bình", "14/10/2013", "", ""]]
    )

    assert exactly.status == "ok"
    assert day_short.status == "warning"


def test_a_phone_that_lost_its_leading_zero_is_fixed_with_a_warning() -> None:
    [result] = check([["HS01", "An", "", "", "912345678"]])

    assert result.status == "warning"
    assert result.values["guardian_phone"] == "0912345678"
    assert "số 0 đầu" in messages(result)[0][1]


def test_errors_do_not_hide_the_other_rows() -> None:
    results = check([GOOD, ["", "x", "", "", ""], ["HS2003", "Võ Thị Cúc", "", "", ""]])

    assert [r.status for r in results] == ["ok", "error", "ok"]


# --- Các hàm phụ --------------------------------------------------


def test_codes_in_collects_distinct_upper_case_codes_without_blanks() -> None:
    rows = [
        ["hs2", "a", "", "", ""],
        ["HS1", "b", "", "", ""],
        ["HS2", "c", "", "", ""],
        ["", "d", "", "", ""],
    ]

    assert codes_in(table(rows), MAPPING) == ["HS1", "HS2"]


def test_common_roster_headers_are_recognised() -> None:
    headers = ["STT", "Mã học sinh", "Họ tên", "Ngày sinh", "Họ tên phụ huynh", "Số điện thoại"]

    assert auto_map(headers, ROSTER_FIELDS) == {
        "student_code": "Mã học sinh",
        "full_name": "Họ tên",
        "date_of_birth": "Ngày sinh",
        "guardian_name": "Họ tên phụ huynh",
        "guardian_phone": "Số điện thoại",
    }


def test_only_code_and_name_are_required() -> None:
    assert [f.name for f in ROSTER_FIELDS if f.required] == ["student_code", "full_name"]


@pytest.mark.parametrize(
    ("text", "expected", "padded"),
    [
        ("0912345678", "0912345678", False),
        ("0912 345 678", "0912345678", False),
        ("091.234.5678", "0912345678", False),
        ("(091) 234-5678", "0912345678", False),
        ("+84 912 345 678", "0912345678", False),
        ("84912345678", "0912345678", False),
        ("02838123456", "02838123456", False),  # máy bàn 11 số
        ("912345678", "0912345678", True),  # Excel mất số 0
        ("912345678.0", "0912345678", True),  # ô số của Excel đọc ra chuỗi
    ],
)
def test_parse_phone_accepts_common_vietnamese_formats(
    text: str, expected: str, padded: bool
) -> None:
    assert parse_phone(text) == (expected, padded)


@pytest.mark.parametrize(
    "text", ["abc", "0912a45678", "12345", "9123456789012", "1912345678", "+1 555 123 4567"]
)
def test_parse_phone_rejects_the_rest(text: str) -> None:
    with pytest.raises(CellError):
        parse_phone(text)

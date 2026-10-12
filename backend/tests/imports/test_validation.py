"""Kiểm từng dòng, tính tay từng quy tắc. Không cần DB: học sinh và dữ liệu hiện có dựng sẵn."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.enums import AttendanceStatus, CommentResult, ConductLevel
from app.imports.columns import score_fields
from app.imports.parsing import RawRow, RawTable
from app.imports.validation import (
    RowResult,
    StudentRef,
    validate_attendance,
    validate_comments,
    validate_conduct,
    validate_scores,
)

STUDENTS = {
    "HS001": StudentRef(101, "Nguyễn Văn An"),
    "HS002": StudentRef(102, "Trần Thị Bình"),
    "HS003": StudentRef(103, "Lê Văn Cường"),
}


def make_table(headers: list[str], rows: list[list[str]], *, first_line: int = 2) -> RawTable:
    return RawTable(
        headers=tuple(headers),
        header_line=first_line - 1,
        rows=tuple(RawRow(line=first_line + i, cells=tuple(row)) for i, row in enumerate(rows)),
    )


def messages(result: RowResult) -> list[tuple[str | None, str]]:
    return [(m.column, m.message) for m in result.messages]


# --- Điểm ---------------------------------------------------------------------------------------

SCORE_HEADERS = ["Mã HS", "Họ và tên", "TX1", "TX2", "GK", "CK"]
SCORE_MAPPING: dict[str, str | None] = {
    "student_code": "Mã HS",
    "full_name": "Họ và tên",
    "tx1": "TX1",
    "tx2": "TX2",
    "midterm": "GK",
    "final": "CK",
}
FIELDS = score_fields(2, allow_partial=False)
FIELDS_PARTIAL = score_fields(2, allow_partial=True)


def scores(
    rows: list[list[str]],
    existing: dict[tuple[int, str, int], Decimal | None] | None = None,
    *,
    allow_partial: bool = False,
) -> list[RowResult]:
    return validate_scores(
        make_table(SCORE_HEADERS, rows),
        SCORE_MAPPING,
        FIELDS_PARTIAL if allow_partial else FIELDS,
        students=STUDENTS,
        existing=existing or {},
        allow_partial=allow_partial,
    )


def test_a_valid_new_row_produces_four_records_and_no_message() -> None:
    [row] = scores([["HS001", "Nguyễn Văn An", "8", "9,5", "7", "6.5"]])

    assert row.status == "ok" and row.action == "new"
    assert row.new_records == 4 and row.changed_records == 0 and row.unchanged_records == 0
    assert row.records == [
        {
            "class_student_id": 101,
            "items": [
                {"kind": "tx", "seq": 1, "score": "8.0"},
                {"kind": "tx", "seq": 2, "score": "9.5"},
                {"kind": "gk", "seq": 1, "score": "7.0"},
                {"kind": "ck", "seq": 1, "score": "6.5"},
            ],
        }
    ]
    assert row.full_name == "Nguyễn Văn An"
    assert row.messages == []


def test_row_numbers_are_the_line_numbers_of_the_file() -> None:
    results = scores([["HS001", "", "8", "8", "8", "8"], ["HS002", "", "7", "7", "7", "7"]])

    assert [r.line for r in results] == [2, 3]


def test_codes_are_matched_regardless_of_case_and_spaces() -> None:
    [row] = scores([["hs001", "", "8", "8", "8", "8"]])

    assert row.status == "ok" and row.records[0]["class_student_id"] == 101


def test_unknown_student_code_is_an_error_naming_the_column() -> None:
    [row] = scores([["HS999", "", "8", "8", "8", "8"]])

    assert row.status == "error" and row.action is None
    assert row.records == [] and row.new_records == 0
    assert messages(row) == [("Mã HS", "Mã học sinh 'HS999' không có trong lớp.")]


def test_blank_student_code_is_an_error() -> None:
    [row] = scores([["", "An", "8", "8", "8", "8"]])

    assert row.status == "error"
    assert messages(row) == [("Mã HS", "Thiếu mã học sinh.")]


def test_duplicate_student_code_is_an_error_pointing_to_the_first_line() -> None:
    first, second = scores([["HS001", "", "8", "8", "8", "8"], ["hs001", "", "7", "7", "7", "7"]])

    assert first.status == "ok"
    assert second.status == "error"
    assert messages(second) == [("Mã HS", "Mã học sinh trùng với dòng 2.")]


@pytest.mark.parametrize(
    ("cell", "fragment"),
    [
        ("10", None),  # đúng biên trên
        ("0", None),  # đúng biên dưới
        ("10,1", "khoảng từ 0 đến 10"),
        ("10.1", "khoảng từ 0 đến 10"),
        ("-1", "khoảng từ 0 đến 10"),
        ("11", "khoảng từ 0 đến 10"),
        ("7,25", "1 chữ số thập phân"),
        ("abc", "không phải là số"),
        ("8 điểm", "không phải là số"),
    ],
)
def test_each_score_rule(cell: str, fragment: str | None) -> None:
    [row] = scores([["HS001", "", cell, "8", "8", "8"]])

    if fragment is None:
        assert row.status == "ok"
        return
    assert row.status == "error"
    [(column, message)] = messages(row)
    assert column == "TX1" and fragment in message  # báo đúng cột
    assert row.records == []  # một ô sai thì cả dòng không ghi


def test_every_bad_cell_of_a_row_is_reported_not_only_the_first() -> None:
    [row] = scores([["HS001", "", "11", "abc", "8", "7,25"]])

    assert [column for column, _ in messages(row)] == ["TX1", "TX2", "CK"]


def test_missing_score_is_an_error_by_default() -> None:
    [row] = scores([["HS001", "", "8", "", "8", "8"]])

    assert row.status == "error"
    assert messages(row) == [("TX2", "Thiếu điểm thường xuyên 2.")]


def test_missing_score_is_only_a_warning_with_allow_partial_and_is_not_written() -> None:
    [row] = scores([["HS001", "", "8", "", "", "8"]], allow_partial=True)

    assert row.status == "warning" and row.action == "new"
    assert row.new_records == 2  # chỉ TX1 và CK
    assert [(i["kind"], i["seq"]) for i in row.records[0]["items"]] == [("tx", 1), ("ck", 1)]
    assert [column for column, _ in messages(row)] == ["TX2", "GK"]


def test_a_row_without_any_score_is_a_warning_with_allow_partial() -> None:
    [row] = scores([["HS001", "An", "", "", "", ""]], allow_partial=True)

    assert row.status == "warning" and row.records == []
    assert messages(row)[-1] == (None, "Dòng không có điểm nào.")


def test_name_mismatch_is_a_warning_that_does_not_block() -> None:
    [row] = scores([["HS001", "Nguyễn Văn Ba", "8", "8", "8", "8"]])

    assert row.status == "warning" and row.action == "new"
    assert len(row.records) == 1  # vẫn ghi
    [(column, message)] = messages(row)
    assert column == "Họ và tên" and "Nguyễn Văn Ba" in message and "Nguyễn Văn An" in message


def test_name_comparison_ignores_case() -> None:
    [row] = scores([["HS001", "NGUYỄN VĂN AN", "8", "8", "8", "8"]])

    assert row.status == "ok"


def test_unchanged_changed_and_new_scores_are_told_apart() -> None:
    existing: dict[tuple[int, str, int], Decimal | None] = {
        (101, "tx", 1): Decimal("8.0"),  # giống tệp
        (101, "tx", 2): Decimal("6.0"),  # tệp ghi 9 -> đổi
        (101, "gk", 1): Decimal("7.0"),  # giống tệp
        # (101, "ck", 1) chưa có -> mới
    }

    [row] = scores([["HS001", "", "8", "9", "7", "5"]], existing)

    assert row.action == "changed"
    assert (row.new_records, row.changed_records, row.unchanged_records) == (1, 1, 2)
    assert row.existing == {"tx2": "6.0"}  # chỉ ô đổi mới hiện giá trị cũ
    assert [(i["kind"], i["seq"], i["score"]) for i in row.records[0]["items"]] == [
        ("tx", 2, "9.0"),
        ("ck", 1, "5.0"),
    ]


def test_identical_row_is_unchanged_and_writes_nothing() -> None:
    existing: dict[tuple[int, str, int], Decimal | None] = {
        (101, "tx", 1): Decimal("8.0"),
        (101, "tx", 2): Decimal("8.0"),
        (101, "gk", 1): Decimal("8.0"),
        (101, "ck", 1): Decimal("8.0"),
    }

    [row] = scores([["HS001", "", "8", "8,0", "8", "8.0"]], existing)

    assert row.status == "ok" and row.action == "unchanged"
    assert row.records == [] and row.unchanged_records == 4


def test_blank_cell_never_clears_an_existing_score() -> None:
    existing: dict[tuple[int, str, int], Decimal | None] = {(101, "tx", 2): Decimal("6.0")}

    [row] = scores([["HS001", "", "8", "", "8", "8"]], existing, allow_partial=True)

    assert all(i["seq"] != 2 or i["kind"] != "tx" for i in row.records[0]["items"])
    assert row.existing == {}  # không có gì bị ghi đè


def test_an_existing_null_score_counts_as_changed() -> None:
    [row] = scores([["HS001", "", "8", "8", "8", "8"]], {(101, "tx", 1): None})

    assert row.changed_records == 1 and row.existing == {"tx1": None}


def test_error_rows_carry_no_records_and_counts_are_zero() -> None:
    [row] = scores([["HS001", "", "8", "8", "8", "99"]])

    assert (row.new_records, row.changed_records, row.unchanged_records) == (0, 0, 0)
    assert row.records == []


# --- Môn nhận xét -------------------------------------------------------------------------------

COMMENT_HEADERS = ["Mã HS", "Họ và tên", "Nhận xét"]
COMMENT_MAPPING: dict[str, str | None] = {
    "student_code": "Mã HS",
    "full_name": "Họ và tên",
    "comment_result": "Nhận xét",
}


def comments(
    rows: list[list[str]],
    existing: dict[int, CommentResult | None] | None = None,
    *,
    allow_partial: bool = False,
) -> list[RowResult]:
    return validate_comments(
        make_table(COMMENT_HEADERS, rows),
        COMMENT_MAPPING,
        students=STUDENTS,
        existing=existing or {},
        allow_partial=allow_partial,
    )


def test_comment_subject_accepts_pass_and_fail_in_several_spellings() -> None:
    rows = comments([["HS001", "", "Đạt"], ["HS002", "", "Chưa đạt"], ["HS003", "", "CĐ"]])

    assert [r.values["comment_result"] for r in rows] == ["pass", "fail", "fail"]
    assert rows[0].records == [
        {"class_student_id": 101, "items": [{"kind": "ck", "seq": 1, "comment_result": "pass"}]}
    ]


def test_comment_subject_rejects_other_words_and_blank_cells() -> None:
    bad, blank = comments([["HS001", "", "Khá"], ["HS002", "", ""]])

    assert bad.status == "error" and messages(bad)[0][0] == "Nhận xét"
    assert blank.status == "error"
    [partial] = comments([["HS002", "", ""]], allow_partial=True)
    assert partial.status == "warning" and partial.records == []


def test_comment_subject_compares_with_existing_result() -> None:
    existing: dict[int, CommentResult | None] = {
        101: CommentResult.PASS,
        102: CommentResult.PASS,
    }

    same, changed, new = comments(
        [["HS001", "", "Đạt"], ["HS002", "", "Chưa đạt"], ["HS003", "", "Đạt"]], existing
    )

    assert same.action == "unchanged" and same.records == []
    assert changed.action == "changed" and changed.existing == {"comment_result": "pass"}
    assert new.action == "new"


# --- Điểm danh ----------------------------------------------------------------------------------

ATT_HEADERS = ["Mã HS", "Ngày", "Trạng thái"]
ATT_MAPPING: dict[str, str | None] = {
    "student_code": "Mã HS",
    "date": "Ngày",
    "status": "Trạng thái",
}
YEAR_START, YEAR_END = date(2026, 9, 5), date(2027, 5, 31)


def attendance(
    rows: list[list[str]], existing: dict[tuple[int, date], AttendanceStatus] | None = None
) -> list[RowResult]:
    return validate_attendance(
        make_table(ATT_HEADERS, rows),
        ATT_MAPPING,
        students=STUDENTS,
        existing=existing or {},
        year_start=YEAR_START,
        year_end=YEAR_END,
    )


def test_attendance_row_is_normalised() -> None:
    [row] = attendance([["HS001", "04/03/2027", "KP"]])

    assert row.status == "ok" and row.action == "new"
    assert row.values == {"date": "2027-03-04", "status": "absent_unexcused"}
    assert row.records == [
        {"class_student_id": 101, "date": "2027-03-04", "status": "absent_unexcused"}
    ]


@pytest.mark.parametrize(
    ("day", "ok"),
    [
        ("05/09/2026", True),  # đúng ngày đầu năm học
        ("31/05/2027", True),  # đúng ngày cuối năm học
        ("04/09/2026", False),
        ("01/06/2027", False),
        ("04/03/2020", False),
    ],
)
def test_attendance_date_must_be_inside_the_school_year(day: str, ok: bool) -> None:
    [row] = attendance([["HS001", day, "M"]])

    assert (row.status == "ok") is ok
    if not ok:
        assert messages(row)[0][0] == "Ngày" and "ngoài năm học" in messages(row)[0][1]


def test_attendance_reports_bad_date_and_bad_status_together() -> None:
    [row] = attendance([["HS001", "không biết", "ốm"]])

    assert [column for column, _ in messages(row)] == ["Ngày", "Trạng thái"]


def test_attendance_missing_date_or_status() -> None:
    no_date, no_status = attendance([["HS001", "", "M"], ["HS001", "04/03/2027", ""]])

    assert messages(no_date) == [("Ngày", "Thiếu ngày.")]
    assert messages(no_status) == [("Trạng thái", "Thiếu trạng thái.")]


def test_attendance_same_student_and_day_twice_is_an_error() -> None:
    first, second, other_day = attendance(
        [
            ["HS001", "04/03/2027", "CP"],
            ["HS001", "2027-03-04", "KP"],  # cùng ngày viết kiểu khác
            ["HS001", "05/03/2027", "KP"],
        ]
    )

    assert first.status == "ok"
    assert second.status == "error" and "trùng với dòng 2" in messages(second)[0][1]
    assert other_day.status == "ok"


def test_attendance_two_students_on_the_same_day_is_fine() -> None:
    results = attendance([["HS001", "04/03/2027", "CP"], ["HS002", "04/03/2027", "CP"]])

    assert [r.status for r in results] == ["ok", "ok"]


def test_attendance_compares_with_existing_status() -> None:
    existing = {
        (101, date(2027, 3, 4)): AttendanceStatus.PRESENT,
        (102, date(2027, 3, 4)): AttendanceStatus.LATE,
    }

    changed, same, new = attendance(
        [
            ["HS001", "04/03/2027", "KP"],
            ["HS002", "04/03/2027", "Muộn"],
            ["HS003", "04/03/2027", "Có mặt"],
        ],
        existing,
    )

    assert changed.action == "changed" and changed.existing == {"status": "present"}
    assert same.action == "unchanged" and same.records == []
    assert new.action == "new"


# --- Rèn luyện ----------------------------------------------------------------------------------

CONDUCT_HEADERS = ["Mã HS", "Xếp loại", "Nhận xét"]
CONDUCT_MAPPING: dict[str, str | None] = {
    "student_code": "Mã HS",
    "level": "Xếp loại",
    "comment": "Nhận xét",
}


def conduct(
    rows: list[list[str]], existing: dict[int, tuple[ConductLevel, str | None]] | None = None
) -> list[RowResult]:
    return validate_conduct(
        make_table(CONDUCT_HEADERS, rows),
        CONDUCT_MAPPING,
        students=STUDENTS,
        existing=existing or {},
    )


def test_conduct_row_with_and_without_comment() -> None:
    with_note, without_note = conduct([["HS001", "Tốt", "Chăm ngoan"], ["HS002", "Khá", ""]])

    assert with_note.records == [
        {"class_student_id": 101, "level": "good", "comment": "Chăm ngoan"}
    ]
    assert without_note.records == [{"class_student_id": 102, "level": "fair", "comment": None}]


def test_conduct_level_is_required_and_must_be_known() -> None:
    blank, unknown = conduct([["HS001", "", ""], ["HS002", "Xuất sắc", ""]])

    assert messages(blank) == [("Xếp loại", "Thiếu mức rèn luyện.")]
    assert unknown.status == "error" and messages(unknown)[0][0] == "Xếp loại"


def test_conduct_one_row_per_student() -> None:
    first, second = conduct([["HS001", "Tốt", ""], ["HS001", "Khá", ""]])

    assert first.status == "ok" and second.status == "error"


def test_conduct_compares_level_and_comment_with_existing() -> None:
    existing = {
        101: (ConductLevel.GOOD, "Cũ"),
        102: (ConductLevel.FAIR, "Giữ nguyên"),
        103: (ConductLevel.PASS, None),
    }

    same, keep_note, new_level = conduct(
        [
            ["HS001", "Tốt", "Cũ"],  # y hệt
            ["HS002", "Khá", ""],  # nhận xét trống không xoá nhận xét cũ
            ["HS003", "Khá", "Mới"],  # đổi mức và có nhận xét
        ],
        existing,
    )

    assert same.action == "unchanged"
    assert keep_note.action == "unchanged"
    assert new_level.action == "changed"
    # Mức cũ "pass"; nhận xét cũ trống nên giá trị cũ của ô nhận xét là None (trống -> "Mới").
    assert new_level.existing == {"level": "pass", "comment": None}


def test_conduct_comment_over_500_characters_is_an_error() -> None:
    [row] = conduct([["HS001", "Tốt", "a" * 501]])

    assert row.status == "error" and messages(row)[0][0] == "Nhận xét"

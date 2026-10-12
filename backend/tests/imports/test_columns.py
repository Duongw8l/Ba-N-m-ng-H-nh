"""Chuẩn hoá tên cột, bí danh, thứ tự ưu tiên ánh xạ và dò dòng tiêu đề (D-057, D-062)."""

import pytest

from app.core.enums import ImportKind
from app.imports.columns import (
    ATTENDANCE_FIELDS,
    CONDUCT_FIELDS,
    auto_map,
    detect_header_line,
    fields_for,
    normalize_header,
    resolve_mapping,
    score_fields,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mã HS", "mahs"),
        ("MÃ_HS", "mahs"),
        ("mã học sinh", "mahocsinh"),
        ("ĐĐGtx 1", "ddgtx1"),
        ("Giữa kỳ", "giuaky"),
        ("Điểm cuối kì", "diemcuoiki"),
        ("  Họ và tên  ", "hovaten"),
        ("", ""),
        ("---", ""),
    ],
)
def test_normalize_header(text: str, expected: str) -> None:
    assert normalize_header(text) == expected


SCORE_HEADERS = ["STT", "Mã HS", "Họ và tên", "TX1", "TX2", "TX3", "TX4", "GK", "CK", "ĐTB"]


def test_auto_map_recognises_common_names_of_an_electronic_gradebook() -> None:
    fields = score_fields(4, allow_partial=False)

    mapping = auto_map(SCORE_HEADERS, fields)

    assert mapping == {
        "student_code": "Mã HS",
        "full_name": "Họ và tên",
        "tx1": "TX1",
        "tx2": "TX2",
        "tx3": "TX3",
        "tx4": "TX4",
        "midterm": "GK",
        "final": "CK",
    }


def test_auto_map_accepts_alternative_wordings() -> None:
    headers = ["Mã học sinh", "Họ tên", "ĐĐGtx 1", "ĐĐGtx 2", "Điểm giữa kỳ", "Điểm cuối kỳ"]

    mapping = auto_map(headers, score_fields(2, allow_partial=False))

    assert mapping["student_code"] == "Mã học sinh"
    assert mapping["tx1"] == "ĐĐGtx 1" and mapping["tx2"] == "ĐĐGtx 2"
    assert mapping["midterm"] == "Điểm giữa kỳ" and mapping["final"] == "Điểm cuối kỳ"


def test_only_as_many_regular_columns_as_the_subject_needs() -> None:
    """Môn 2 đầu điểm thường xuyên: cột TX3, TX4 của tệp là cột thừa."""
    fields = score_fields(2, allow_partial=False)

    resolution = resolve_mapping(SCORE_HEADERS, fields)

    assert resolution.missing_required == []
    assert set(resolution.ignored_columns) == {"STT", "TX3", "TX4", "ĐTB"}


def test_each_file_column_is_given_to_at_most_one_field() -> None:
    mapping = auto_map(["Mã HS", "Nhận xét"], CONDUCT_FIELDS)

    assert mapping["comment"] == "Nhận xét"
    assert mapping["level"] is None  # "Nhận xét" không bị gán hai lần


def test_missing_required_columns_are_listed_by_label() -> None:
    resolution = resolve_mapping(["Mã HS", "TX1"], score_fields(2, allow_partial=False))

    assert resolution.missing_required == [
        "Điểm thường xuyên 2",
        "Điểm giữa kỳ",
        "Điểm cuối kỳ",
    ]


def test_allow_partial_makes_score_columns_optional_but_not_the_student_code() -> None:
    resolution = resolve_mapping(["Mã HS", "TX1"], score_fields(2, allow_partial=True))
    assert resolution.missing_required == []

    resolution = resolve_mapping(["TX1", "GK"], score_fields(2, allow_partial=True))
    assert resolution.missing_required == ["Mã học sinh"]


def test_priority_explicit_beats_template_beats_auto() -> None:
    headers = ["Mã HS", "Cột A", "Cột B", "Cột C"]
    fields = CONDUCT_FIELDS

    auto = resolve_mapping(headers, fields)
    template = resolve_mapping(headers, fields, template={"level": "Cột A"})
    explicit = resolve_mapping(
        headers, fields, template={"level": "Cột A"}, explicit={"level": "Cột B"}
    )

    assert auto.mapping["level"] is None
    assert template.mapping["level"] == "Cột A"
    assert explicit.mapping["level"] == "Cột B"
    assert explicit.mapping["student_code"] == "Mã HS"  # phần tự khớp vẫn còn


def test_explicit_none_removes_an_auto_matched_field() -> None:
    resolution = resolve_mapping(
        ["Mã HS", "Họ và tên", "Xếp loại"], CONDUCT_FIELDS, explicit={"full_name": None}
    )

    assert resolution.mapping["full_name"] is None
    assert "Họ và tên" in resolution.ignored_columns


def test_mapping_to_a_column_that_is_not_in_the_file_is_noted_and_ignored() -> None:
    resolution = resolve_mapping(
        ["Mã HS", "Xếp loại"], CONDUCT_FIELDS, explicit={"level": "Cột không có"}
    )

    assert resolution.mapping["level"] == "Xếp loại"  # giữ kết quả tự khớp
    assert any("Cột không có" in note for note in resolution.notes)


def test_mapping_an_unknown_field_is_noted() -> None:
    resolution = resolve_mapping(["Mã HS", "Xếp loại"], CONDUCT_FIELDS, explicit={"điểm": "Mã HS"})

    assert any("điểm" in note for note in resolution.notes)


def test_mapping_matches_header_names_after_normalising() -> None:
    resolution = resolve_mapping(
        ["MÃ HS", "xếp loại"], CONDUCT_FIELDS, explicit={"level": "Xếp Loại"}
    )

    assert resolution.mapping["level"] == "xếp loại"


def test_detect_header_line_skips_the_big_title_rows_of_a_gradebook() -> None:
    grid = [
        ["SỞ GIÁO DỤC VÀ ĐÀO TẠO", "", "", ""],
        ["BẢNG ĐIỂM MÔN TOÁN - LỚP 11A2", "", "", ""],
        ["", "", "", ""],
        ["STT", "Mã HS", "Họ và tên", "GK"],
        ["1", "HS001", "An", "8"],
    ]

    assert detect_header_line(grid, score_fields(1, allow_partial=True)) == 4


def test_detect_header_line_defaults_to_the_first_line_when_nothing_matches() -> None:
    assert detect_header_line([["x", "y"], ["1", "2"]], ATTENDANCE_FIELDS) == 1


def test_fields_for_each_kind() -> None:
    assert fields_for(ImportKind.ATTENDANCE, allow_partial=False) is ATTENDANCE_FIELDS
    assert fields_for(ImportKind.CONDUCT, allow_partial=False) is CONDUCT_FIELDS

    scores = fields_for(ImportKind.ASSESSMENTS, tx_required=3, allow_partial=False)
    assert [f.name for f in scores] == [
        "student_code",
        "full_name",
        "tx1",
        "tx2",
        "tx3",
        "midterm",
        "final",
    ]

    comments = fields_for(ImportKind.ASSESSMENTS, is_comment_subject=True, allow_partial=False)
    assert [f.name for f in comments] == ["student_code", "full_name", "comment_result"]
    assert comments[2].required is True
    partial = fields_for(ImportKind.ASSESSMENTS, is_comment_subject=True, allow_partial=True)
    assert partial[2].required is False

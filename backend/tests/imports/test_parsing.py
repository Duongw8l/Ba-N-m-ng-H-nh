"""Đọc tệp .xlsx và .csv thành lưới chuỗi (D-057): đúng định dạng, đúng giá trị, từ chối tệp xấu."""

import io
import zipfile
from collections.abc import Callable
from datetime import date, datetime

import pytest
from openpyxl import Workbook

from app.imports.parsing import (
    MAX_COLUMNS,
    MAX_UPLOAD_BYTES,
    ImportFileError,
    read_grid,
    table_from_grid,
)

Build = Callable[..., bytes]

HEADER = ["Mã HS", "Họ và tên", "Điểm"]
BODY = [["HS001", "Nguyễn Văn An", "8,5"], ["HS002", "Trần Thị Bình", "7"]]


def test_reads_xlsx_cells_as_text(xlsx: Build) -> None:
    grid = read_grid("diem.xlsx", xlsx([HEADER, *BODY]))

    assert grid == [HEADER, *BODY]


def test_xlsx_number_cells_keep_their_text_not_float_noise(xlsx: Build) -> None:
    """Ô số 8.7 phải đọc thành "8.7" chứ không thành 8.700000000000001 (điểm đi qua Decimal)."""
    grid = read_grid("diem.xlsx", xlsx([["Điểm"], [8.7], [7], [0.1], [10]]))

    assert [row[0] for row in grid[1:]] == ["8.7", "7", "0.1", "10"]


def test_xlsx_date_cells_become_iso_text(xlsx: Build) -> None:
    grid = read_grid("dd.xlsx", xlsx([["Ngày"], [date(2027, 3, 4)], [datetime(2027, 3, 5, 0, 0)]]))

    assert grid[1][0].startswith("2027-03-04")
    assert grid[2][0].startswith("2027-03-05")


def test_xlsx_reads_only_the_first_sheet(xlsx: Build) -> None:
    workbook = Workbook()
    first = workbook.active
    assert first is not None
    first.append(["a"])
    workbook.create_sheet("Hai").append(["b"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    assert read_grid("x.xlsx", buffer.getvalue()) == [["a"]]


def test_reads_csv_with_and_without_bom(csv_bytes: Build) -> None:
    rows = [HEADER, *BODY]

    assert read_grid("d.csv", csv_bytes(rows)) == rows
    assert read_grid("d.csv", csv_bytes(rows, bom=True)) == rows


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_csv_delimiter_is_detected(csv_bytes: Build, delimiter: str) -> None:
    rows = [["Mã HS", "Họ và tên", "Điểm"], ["HS001", "An", "8"], ["HS002", "Bình", "7"]]

    assert read_grid("d.csv", csv_bytes(rows, delimiter=delimiter)) == rows


def test_csv_with_quoted_comma_decimals(csv_bytes: Build) -> None:
    grid = read_grid("d.csv", csv_bytes([["Mã", "Điểm"], ["HS1", "8,5"]]))

    assert grid[1] == ["HS1", "8,5"]


def test_cells_are_trimmed_and_ragged_rows_are_padded(csv_bytes: Build) -> None:
    data = "Mã,Họ tên,Điểm\r\n  HS1 , An \r\nHS2,Bình,7\r\n".encode()

    assert read_grid("d.csv", data) == [
        ["Mã", "Họ tên", "Điểm"],
        ["HS1", "An", ""],
        ["HS2", "Bình", "7"],
    ]


@pytest.mark.parametrize("name", ["d.xls", "d.xlsm", "d.xlsb", "d.ods", "d.txt", "d", "d.xlsx.exe"])
def test_other_extensions_are_rejected(name: str) -> None:
    with pytest.raises(ImportFileError) as error:
        read_grid(name, b"abc")

    assert error.value.status_code == 415


def test_extension_check_ignores_case(xlsx: Build) -> None:
    assert read_grid("DIEM.XLSX", xlsx([HEADER, *BODY]))[0] == HEADER


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ImportFileError, match="rỗng"):
        read_grid("d.csv", b"")


def test_file_with_only_blank_cells_is_rejected(csv_bytes: Build) -> None:
    with pytest.raises(ImportFileError, match="không có dữ liệu"):
        read_grid("d.csv", csv_bytes([["", ""], ["", ""]]))


def test_oversized_upload_is_413() -> None:
    with pytest.raises(ImportFileError) as error:
        read_grid("d.csv", b"a,b\n" + b"x" * MAX_UPLOAD_BYTES)

    assert error.value.status_code == 413


def test_garbage_named_xlsx_is_rejected() -> None:
    with pytest.raises(ImportFileError, match="không hợp lệ"):
        read_grid("d.xlsx", b"day khong phai la tep excel")


def test_corrupted_xlsx_is_rejected(xlsx: Build) -> None:
    broken = xlsx([HEADER, *BODY])[:200]

    with pytest.raises(ImportFileError):
        read_grid("d.xlsx", broken)


def test_zip_that_is_not_a_workbook_is_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "khong phai excel")

    with pytest.raises(ImportFileError):
        read_grid("d.xlsx", buffer.getvalue())


def test_zip_bomb_is_rejected_before_it_is_unpacked() -> None:
    """Nén mạnh: tệp nhỏ nhưng khi giải nén vượt 50 MB."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (60 * 1024 * 1024))
    data = buffer.getvalue()
    assert len(data) < MAX_UPLOAD_BYTES  # qua được giới hạn dung lượng tải lên

    with pytest.raises(ImportFileError) as error:
        read_grid("d.xlsx", data)

    assert error.value.status_code == 413


def test_workbook_with_macros_is_rejected(xlsx: Build) -> None:
    source = zipfile.ZipFile(io.BytesIO(xlsx([HEADER, *BODY])))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr("xl/vbaProject.bin", b"macro")

    with pytest.raises(ImportFileError, match="macro"):
        read_grid("d.xlsx", buffer.getvalue())


def test_too_many_columns_is_rejected(csv_bytes: Build) -> None:
    row = [str(i) for i in range(MAX_COLUMNS + 1)]

    with pytest.raises(ImportFileError, match="cột"):
        read_grid("d.csv", csv_bytes([row, row]))


@pytest.mark.parametrize(
    "data",
    [
        b"M\xe3,\xc4i\xe9m\nHS1,8\n",  # Windows-1252: "ã" là một byte, không phải UTF-8
        "﻿Mã,Điểm\nHS1,8\n".encode("utf-16"),  # "Unicode Text" của Excel
    ],
)
def test_csv_that_is_not_utf8_is_rejected_with_a_hint(data: bytes) -> None:
    with pytest.raises(ImportFileError, match="UTF-8"):
        read_grid("d.csv", data)


def test_csv_with_binary_content_is_rejected() -> None:
    with pytest.raises(ImportFileError, match="nhị phân"):
        read_grid("d.csv", b"a,b\x00,c\n1,2,3\n")


# --- Dựng bảng từ lưới --------------------------------------------------------------------------


def test_table_uses_the_given_header_line_and_numbers_rows_like_the_file(xlsx: Build) -> None:
    grid = read_grid(
        "d.xlsx",
        xlsx([["SỔ ĐIỂM LỚP 11A2"], [], HEADER, *BODY, [], ["HS003", "Lê Văn Cường", "9"]]),
    )

    table = table_from_grid(grid, 3)

    assert table.headers == tuple(HEADER)
    assert table.header_line == 3
    # Dòng trống hoàn toàn bị bỏ, số dòng vẫn là số dòng trong tệp (dòng 4, 5, 7).
    assert [row.line for row in table.rows] == [4, 5, 7]
    assert table.rows[2].cells == ("HS003", "Lê Văn Cường", "9")


@pytest.mark.parametrize("line", [0, -1, 99])
def test_table_header_line_must_be_inside_the_file(line: int) -> None:
    with pytest.raises(ImportFileError, match="ngoài tệp"):
        table_from_grid([["a"], ["b"]], line)

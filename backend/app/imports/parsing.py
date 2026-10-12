"""Đọc tệp .xlsx và .csv thành một lưới chuỗi (D-057).

Mọi ô được đọc dưới dạng CHUỖI (`dtype=str`), không bao giờ để pandas đổi điểm thành số thực: điểm
được đổi sang Decimal ở bước kiểm dòng. Có giới hạn kích thước, số dòng, số cột và chống zip bomb.
"""

import csv
import io
import zipfile
from dataclasses import dataclass

import pandas as pd

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 60
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # tổng dung lượng sau khi giải nén của tệp xlsx

ALLOWED_EXTENSIONS = (".xlsx", ".csv")
DELIMITERS = ",;\t"
XLSX_MAGIC = b"PK\x03\x04"


class ImportFileError(Exception):
    """Tệp không dùng được; `status_code` là mã HTTP nên trả về."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RawRow:
    line: int  # số dòng trong tệp (bắt đầu từ 1), để báo lỗi đúng chỗ giáo viên nhìn thấy
    cells: tuple[str, ...]


@dataclass(frozen=True)
class RawTable:
    headers: tuple[str, ...]  # tên cột nguyên văn ở dòng tiêu đề
    header_line: int
    rows: tuple[RawRow, ...]  # các dòng sau dòng tiêu đề, bỏ dòng trống hoàn toàn


def _clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "<na>") else text


def _read_xlsx(data: bytes) -> list[list[str]]:
    if not data.startswith(XLSX_MAGIC) or not zipfile.is_zipfile(io.BytesIO(data)):
        raise ImportFileError("Tệp .xlsx không hợp lệ hoặc bị hỏng.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        total = sum(info.file_size for info in archive.infolist())
        names = archive.namelist()
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ImportFileError("Tệp quá lớn sau khi giải nén.", status_code=413)
    if "xl/vbaProject.bin" in names:
        raise ImportFileError("Không nhận tệp có macro. Hãy lưu lại dưới dạng .xlsx thường.")
    try:
        frame = pd.read_excel(
            io.BytesIO(data),
            header=None,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            engine="openpyxl",
            sheet_name=0,
        )
    except Exception as error:  # openpyxl và pandas ném nhiều loại ngoại lệ khác nhau
        raise ImportFileError("Không đọc được tệp Excel. Hãy kiểm tra tệp rồi tải lại.") from error
    return [[_clean(cell) for cell in row] for row in frame.itertuples(index=False, name=None)]


NOT_UTF8_MESSAGE = (
    "Tệp CSV phải mã hoá UTF-8. Trong Excel hãy lưu bằng 'CSV UTF-8 (phân tách bằng dấu phẩy)'."
)


def _read_csv(data: bytes) -> list[list[str]]:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):  # "Unicode Text" của Excel là UTF-16
        raise ImportFileError(NOT_UTF8_MESSAGE)
    if b"\x00" in data:
        raise ImportFileError("Tệp CSV không hợp lệ (chứa ký tự nhị phân).")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportFileError(NOT_UTF8_MESSAGE) from error
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=DELIMITERS)
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    try:
        return [
            [_clean(cell) for cell in row]
            for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        ]
    except csv.Error as error:
        raise ImportFileError("Không đọc được tệp CSV.") from error


def read_grid(filename: str, data: bytes) -> list[list[str]]:
    """Đọc toàn bộ tệp thành lưới chuỗi đã cắt khoảng trắng, các dòng cùng độ rộng."""
    name = filename.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise ImportFileError("Chỉ nhận tệp .xlsx hoặc .csv.", status_code=415)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImportFileError(
            f"Tệp lớn hơn {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", status_code=413
        )
    if not data:
        raise ImportFileError("Tệp rỗng.")

    grid = _read_xlsx(data) if name.endswith(".xlsx") else _read_csv(data)
    if len(grid) > MAX_ROWS + 50:
        raise ImportFileError(f"Tệp có hơn {MAX_ROWS} dòng.", status_code=413)
    width = max((len(row) for row in grid), default=0)
    if width > MAX_COLUMNS:
        raise ImportFileError(f"Tệp có hơn {MAX_COLUMNS} cột.", status_code=413)
    if width == 0 or not any(any(cell for cell in row) for row in grid):
        raise ImportFileError("Tệp không có dữ liệu.")
    return [row + [""] * (width - len(row)) for row in grid]


def table_from_grid(grid: list[list[str]], header_line: int) -> RawTable:
    """Dựng bảng từ lưới, với `header_line` (đếm từ 1) là dòng tiêu đề."""
    if not 1 <= header_line <= len(grid):
        raise ImportFileError(f"Dòng tiêu đề {header_line} nằm ngoài tệp ({len(grid)} dòng).")
    headers = tuple(grid[header_line - 1])
    rows = tuple(
        RawRow(line=index, cells=tuple(row))
        for index, row in enumerate(grid[header_line:], start=header_line + 1)
        if any(row)
    )
    return RawTable(headers=headers, header_line=header_line, rows=rows)

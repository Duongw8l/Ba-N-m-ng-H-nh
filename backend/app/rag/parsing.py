"""Đọc tệp văn bản quy định (PDF, DOCX, TXT) thành chữ thuần (Giai đoạn 7, D-079).

Chỉ đọc chữ, chưa tách Điều/Khoản (việc của `chunking.py`). Lỗi do tệp (sai định dạng, hỏng, rỗng,
bản quét ảnh, quá lớn) ném `DocumentError` với thông điệp tiếng Việt cho Admin đọc; router đổi thành
HTTP 422 (quá lớn: 413).

Giới hạn đã biết:
- PDF: chỉ đọc lớp chữ. Bản quét ảnh không có lớp chữ nên bị từ chối (cần OCR, chưa làm).
- DOCX: số thứ tự TỰ ĐỘNG của Word ("1.", "a)" do danh sách đánh số sinh ra) không nằm trong tệp
  dưới dạng chữ nên mất; văn bản cần có số khoản/điểm gõ thẳng thì mới tách được theo khoản.
- Không đọc đầu trang/chân trang, chú thích cuối trang, hộp văn bản trong DOCX.
"""

import io
import math
import re
import zipfile
from collections import Counter
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from app.rag.chunking import normalize_text

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 400
MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
# Dưới mức này coi như tệp không có chữ.
MIN_TEXT_CHARS = 20

_PAGE_NUMBER = re.compile(
    r"^(?:(?:trang|page)\s*)?\d{1,4}(?:\s*(?:/|of|trên)\s*\d{1,4})?$|^[-–—]\s*\d{1,4}\s*[-–—]$",
    re.IGNORECASE,
)
# Đầu/chân trang lặp lại ở ít nhất chừng này số trang (và từ 3 trang trở lên) thì bỏ.
_REPEATED_MARGIN_RATIO = 0.6
_REPEATED_MARGIN_MIN_PAGES = 3


class DocumentError(ValueError):
    """Tệp không dùng được. Thông điệp tiếng Việt, hiển thị nguyên văn cho người tải lên."""


class DocumentTooLarge(DocumentError):
    pass


def extract_text(file_name: str, data: bytes) -> str:
    """Đọc nội dung chữ của tệp theo đuôi tệp, đã chuẩn hoá (NFC, bỏ ký tự vô hình)."""
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        accepted = ", ".join(SUPPORTED_EXTENSIONS)
        raise DocumentError(f'Chỉ nhận tệp {accepted}. Tệp "{file_name}" không được hỗ trợ.')
    if not data:
        raise DocumentError("Tệp rỗng.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentTooLarge(f"Tệp lớn hơn {MAX_FILE_BYTES // (1024 * 1024)} MB.")

    readers = {".pdf": _read_pdf, ".docx": _read_docx, ".txt": _read_txt}
    text = normalize_text(readers[extension](data))
    if len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
        raise DocumentError("Tệp không có nội dung chữ để đọc.")
    return text


def _read_txt(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentError("Tệp .txt phải mã hoá UTF-8. Hãy lưu lại tệp bằng UTF-8.") from error
    if "\x00" in text:
        raise DocumentError("Tệp không phải văn bản thuần (có byte nhị phân).")
    return text


def _read_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentError("PDF được đặt mật khẩu. Hãy gỡ mật khẩu rồi tải lại.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentError(f"PDF có quá {MAX_PDF_PAGES} trang. Hãy chia nhỏ tệp.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except DocumentError:
        raise
    except Exception as error:  # pypdf ném nhiều loại lỗi khác nhau trên tệp hỏng
        raise DocumentError("Không đọc được tệp PDF (tệp hỏng hoặc không phải PDF).") from error

    text = "\n".join(strip_page_noise([normalize_text(page) for page in pages]))
    if len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
        raise DocumentError(
            "PDF không có lớp chữ (có thể là bản quét ảnh). Hệ thống chưa đọc được bản quét: "
            "hãy dùng bản PDF có thể chọn chữ, hoặc tải bản DOCX/TXT."
        )
    return text


def _read_docx(data: bytes) -> str:
    try:
        # DOCX là tệp zip: chặn tệp nén nhỏ nhưng giải nén ra hàng GB trước khi nạp vào bộ nhớ.
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise DocumentError("Tệp DOCX giải nén ra quá lớn.")
        document = Document(io.BytesIO(data))
        lines: list[str] = []
        # Đi theo đúng thứ tự trong tệp: đoạn văn và bảng xen kẽ nhau.
        for child in document.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                lines.append(Paragraph(child, document).text)
            elif tag == "tbl":
                lines.extend(_table_rows(Table(child, document)))
    except DocumentError:
        raise
    except Exception as error:  # python-docx ném nhiều loại lỗi khác nhau trên tệp hỏng
        raise DocumentError("Không đọc được tệp DOCX (tệp hỏng hoặc không phải DOCX).") from error
    return "\n".join(lines)


def _table_rows(table: Table) -> list[str]:
    """Mỗi hàng của bảng thành một dòng "ô 1 | ô 2 | ...". Ô gộp chỉ tính một lần."""
    rows: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        seen: set[int] = set()
        for cell in row.cells:
            if id(cell._tc) in seen:
                continue
            seen.add(id(cell._tc))
            text = " ".join(cell.text.split())
            if text:
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))
    return rows


def strip_page_noise(pages: list[str]) -> list[str]:
    """Bỏ số trang ở dòng đầu/cuối mỗi trang, và đầu/chân trang lặp lại ở hầu hết các trang.

    Chỉ xét dòng đầu và dòng cuối của từng trang: số đứng một mình ở giữa trang là nội dung.
    Nhận vào danh sách chữ từng trang, trả về danh sách các dòng đã làm sạch (mọi trang nối nhau).
    """
    page_lines = [[line for line in page.split("\n") if line.strip()] for page in pages]
    for lines in page_lines:
        if lines and _PAGE_NUMBER.match(lines[-1].strip()):
            lines.pop()
        if lines and _PAGE_NUMBER.match(lines[0].strip()):
            lines.pop(0)

    if len(page_lines) >= _REPEATED_MARGIN_MIN_PAGES:
        needed = max(_REPEATED_MARGIN_MIN_PAGES, math.ceil(_REPEATED_MARGIN_RATIO * len(pages)))
        headers = Counter(_margin_key(lines[0]) for lines in page_lines if lines)
        footers = Counter(_margin_key(lines[-1]) for lines in page_lines if lines)
        for lines in page_lines:
            if lines and footers[_margin_key(lines[-1])] >= needed:
                lines.pop()
            if lines and headers[_margin_key(lines[0])] >= needed:
                lines.pop(0)
    return [line for lines in page_lines for line in lines]


def _margin_key(line: str) -> str:
    """Số trang đổi theo từng trang, nên so sánh đầu/chân trang sau khi thay mọi số bằng '#'."""
    return re.sub(r"\d+", "#", line.strip().lower())

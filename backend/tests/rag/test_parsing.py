import io
import unicodedata
import zipfile
from collections.abc import Callable

import pytest
from docx import Document
from docx.document import Document as DocxDocument
from pypdf import PdfWriter

from app.rag import parsing
from app.rag.chunking import split_into_chunks
from app.rag.parsing import DocumentError, DocumentTooLarge, extract_text, strip_page_noise


def make_pdf(pages: list[list[str]]) -> bytes:
    """PDF tối thiểu, mỗi trang là danh sách dòng. Chỉ ASCII (phông Helvetica chuẩn)."""

    def escape(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    count = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(count))
    objects: dict[int, str] = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, lines in enumerate(pages):
        page_id, content_id = 4 + 2 * index, 5 + 2 * index
        shown = [f"({escape(line)}) Tj T*" for line in lines]
        stream = "\n".join(["BT", "/F1 12 Tf", "14 TL", "50 750 Td", *shown, "ET"])
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"

    out = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n{objects[number]}\nendobj\n".encode("latin-1")
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for number in sorted(objects):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return out


def docx_bytes(build: Callable[[DocxDocument], None]) -> bytes:
    document = Document()
    build(document)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# --- TXT -----------------------------------------------------------------------------------------


def test_txt_is_decoded_as_utf8_and_normalised_to_nfc() -> None:
    text = unicodedata.normalize("NFD", "Điều 1. Phạm vi áp dụng\nNội dung của điều một.")
    data = b"\xef\xbb\xbf" + text.encode("utf-8")  # có BOM

    result = extract_text("quy-che.txt", data)

    assert result == "Điều 1. Phạm vi áp dụng\nNội dung của điều một."


def test_extension_is_case_insensitive() -> None:
    data = "Điều 1. Một\nNội dung của điều một.".encode()

    assert extract_text("QUY-CHE.TXT", data).startswith("Điều 1")


def test_txt_in_another_encoding_is_rejected_with_a_clear_message() -> None:
    data = "Điều 1. Phạm vi áp dụng của quy chế".encode("utf-16")

    with pytest.raises(DocumentError, match="UTF-8"):
        extract_text("quy-che.txt", data)


def test_binary_file_named_txt_is_rejected() -> None:
    with pytest.raises(DocumentError, match="nhị phân"):
        extract_text("quy-che.txt", b"abc\x00def" * 20)


@pytest.mark.parametrize("data", [b"", b"   \n\t\n  ", b"Dieu 1."])
def test_empty_or_almost_empty_file_is_rejected(data: bytes) -> None:
    with pytest.raises(DocumentError):
        extract_text("quy-che.txt", data)


@pytest.mark.parametrize(
    "name", ["quy-che.doc", "bang-diem.xlsx", "quy-che", "anh.png", ".txt.exe"]
)
def test_unsupported_extension_is_rejected_and_lists_what_is_accepted(name: str) -> None:
    with pytest.raises(DocumentError, match=r"\.pdf, \.docx, \.txt"):
        extract_text(name, b"noi dung van ban rat dai de du ky tu")


def test_file_over_the_size_limit_is_rejected_as_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parsing, "MAX_FILE_BYTES", 100)

    with pytest.raises(DocumentTooLarge):
        extract_text("quy-che.txt", b"a" * 101)
    assert extract_text("quy-che.txt", b"Dieu 1. " + b"a" * 90)  # đúng giới hạn thì qua


# --- PDF -----------------------------------------------------------------------------------------


def test_pdf_text_is_extracted_and_page_numbers_are_removed() -> None:
    pdf = make_pdf(
        [
            ["Dieu 1. Pham vi", "1. Noi dung khoan mot cua dieu mot.", "1"],
            ["2. Noi dung khoan hai cua dieu mot.", "Dieu 2. Hieu luc", "2"],
        ]
    )

    text = extract_text("quy-che.pdf", pdf)

    assert text.split("\n") == [
        "Dieu 1. Pham vi",
        "1. Noi dung khoan mot cua dieu mot.",
        "2. Noi dung khoan hai cua dieu mot.",
        "Dieu 2. Hieu luc",
    ]


def test_pdf_without_a_text_layer_is_reported_as_a_scan() -> None:
    with pytest.raises(DocumentError, match="bản quét"):
        extract_text("quet.pdf", make_pdf([[], []]))


def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(DocumentError, match="PDF"):
        extract_text("hong.pdf", b"%PDF-1.4\nkhong phai pdf that su, hong het roi" * 5)


def test_text_file_renamed_to_pdf_is_rejected() -> None:
    with pytest.raises(DocumentError, match="PDF"):
        extract_text("gia.pdf", "Điều 1. Đây là tệp văn bản thường, không phải PDF.".encode())


def test_password_protected_pdf_is_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("bi-mat")
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(DocumentError, match="mật khẩu"):
        extract_text("khoa.pdf", buffer.getvalue())


def test_pdf_with_too_many_pages_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parsing, "MAX_PDF_PAGES", 2)
    pdf = make_pdf([["Dieu 1. Mot", "Noi dung cua trang so mot"]] * 3)

    with pytest.raises(DocumentError, match="quá 2 trang"):
        extract_text("dai.pdf", pdf)


# --- Số trang và đầu/chân trang ------------------------------------------------------------------


@pytest.mark.parametrize(
    "footer", ["3", "Trang 3", "trang 3/10", "Page 3 of 10", "- 3 -", "– 12 –", "3 / 10"]
)
def test_page_number_forms_are_removed_from_the_end_of_a_page(footer: str) -> None:
    assert strip_page_noise([f"Dòng một\nDòng hai\n{footer}"]) == ["Dòng một", "Dòng hai"]


def test_page_number_at_the_top_of_a_page_is_removed_too() -> None:
    assert strip_page_noise(["7\nDòng một\nDòng hai"]) == ["Dòng một", "Dòng hai"]


def test_a_number_in_the_middle_of_a_page_is_content_and_is_kept() -> None:
    page = "Dòng một\n45\nDòng hai\n3"

    assert strip_page_noise([page]) == ["Dòng một", "45", "Dòng hai"]


def test_a_clause_marker_alone_on_the_last_line_is_not_a_page_number() -> None:
    assert strip_page_noise(["Điều 1. Một\n2."]) == ["Điều 1. Một", "2."]


def test_repeated_header_and_footer_are_removed_when_most_pages_have_them() -> None:
    pages = [f"THÔNG TƯ MẪU\nNội dung trang {n}\nBộ Giáo dục - Trang {n}" for n in range(1, 6)]

    assert strip_page_noise(pages) == [f"Nội dung trang {n}" for n in range(1, 6)]


def test_a_line_repeated_on_only_a_few_pages_is_kept() -> None:
    pages = ["Tiêu đề\nA\nx", "B\nC\ny", "D\nE\nz", "F\nG\nw", "Tiêu đề\nH\nv"]

    lines = strip_page_noise(pages)

    assert lines.count("Tiêu đề") == 2


def test_repeated_margin_removal_needs_at_least_three_pages() -> None:
    pages = ["THÔNG TƯ MẪU\nA", "THÔNG TƯ MẪU\nB"]

    assert strip_page_noise(pages) == ["THÔNG TƯ MẪU", "A", "THÔNG TƯ MẪU", "B"]


def test_blank_pages_do_not_break_the_cleaning() -> None:
    assert strip_page_noise(["", "  \n ", "Nội dung\n1"]) == ["Nội dung"]


# --- DOCX ----------------------------------------------------------------------------------------


def test_docx_paragraphs_and_tables_are_read_in_document_order() -> None:
    def build(document: DocxDocument) -> None:
        document.add_paragraph("Điều 3. Nghỉ học")
        document.add_paragraph("1. Học sinh nghỉ học phải có đơn xin phép.")
        table = document.add_table(rows=3, cols=2)
        table.cell(0, 0).text = "Số buổi nghỉ"
        table.cell(0, 1).text = "Xử lý"
        table.cell(1, 0).text = "Từ 12 buổi"
        table.cell(1, 1).text = "Nhắc nhở"
        document.add_paragraph("2. Đoạn sau bảng.")

    text = extract_text("quy-che.docx", docx_bytes(build))

    assert text.split("\n") == [
        "Điều 3. Nghỉ học",
        "1. Học sinh nghỉ học phải có đơn xin phép.",
        "Số buổi nghỉ | Xử lý",
        "Từ 12 buổi | Nhắc nhở",
        "2. Đoạn sau bảng.",
    ]


def test_docx_merged_cell_is_read_once() -> None:
    def build(document: DocxDocument) -> None:
        document.add_paragraph("Phụ lục I")
        table = document.add_table(rows=2, cols=3)
        merged = table.cell(0, 0).merge(table.cell(0, 2))
        merged.text = "Bảng quy đổi điểm"
        for column, value in enumerate(["Giỏi", "Khá", "Đạt"]):
            table.cell(1, column).text = value

    text = extract_text("phu-luc.docx", docx_bytes(build))

    assert text.split("\n") == ["Phụ lục I", "Bảng quy đổi điểm", "Giỏi | Khá | Đạt"]


def test_docx_text_can_be_split_into_articles_and_clauses() -> None:
    def build(document: DocxDocument) -> None:
        for line in ["Điều 1. Phạm vi", "1. Khoản một.", "2. Khoản hai."]:
            document.add_paragraph(line)

    chunks = split_into_chunks(extract_text("quy-che.docx", docx_bytes(build)))

    assert [(c.article, c.clause) for c in chunks] == [("Điều 1", "Khoản 1"), ("Điều 1", "Khoản 2")]


def test_corrupt_docx_is_rejected() -> None:
    with pytest.raises(DocumentError, match="DOCX"):
        extract_text("hong.docx", b"PK\x03\x04 khong phai docx" * 10)


def test_docx_that_inflates_far_beyond_its_size_is_rejected_before_it_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parsing, "MAX_DOCX_UNCOMPRESSED_BYTES", 10_000)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"\0" * 1_000_000)  # nén còn vài KB

    assert len(buffer.getvalue()) < 5_000
    with pytest.raises(DocumentError, match="giải nén ra quá lớn"):
        extract_text("bom.docx", buffer.getvalue())


def test_docx_without_text_is_rejected() -> None:
    def build(document: DocxDocument) -> None:
        document.add_paragraph("")

    with pytest.raises(DocumentError, match="không có nội dung"):
        extract_text("trong.docx", docx_bytes(build))

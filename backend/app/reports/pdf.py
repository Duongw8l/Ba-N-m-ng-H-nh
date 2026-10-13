"""Xuất PDF nhận xét và báo cáo ĐÃ DUYỆT (Giai đoạn 9, D-108).

Dùng `reportlab` và phông Noto Sans nhúng sẵn (`assets/`, giấy phép OFL, đã cắt còn Latin + tiếng
Việt) nên chạy được trên Windows, Docker và CI mà không cần thư viện hệ thống. Module này chỉ dàn
trang một `PdfDocument` đã dựng sẵn: mọi số trong bảng lấy từ Analytics, định dạng kiểu Việt Nam
(`6,5`); không tính toán gì ở đây. Văn bản nhận xét là bản đã duyệt (`final_text`).
"""

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ASSETS = Path(__file__).with_name("assets")
REGULAR, BOLD = "NotoSans", "NotoSans-Bold"
BRAND = colors.HexColor("#0F766E")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
TINT = colors.HexColor("#F0FDFA")


@dataclass(frozen=True)
class PdfDocument:
    """Mọi thứ trên một trang, đã định dạng sẵn thành chuỗi hiển thị."""

    school_name: str
    school_year: str
    title: str  # ví dụ "PHIẾU LIÊN LẠC"
    subtitle: str  # ví dụ "Học kỳ I · Lớp 11A2"
    body: str  # nhận xét hoặc báo cáo đã duyệt; dòng trống ngăn các đoạn
    signer_title: str  # ví dụ "Giáo viên chủ nhiệm"
    signer_name: str
    approved_on: date
    # Khối thông tin (nhãn, giá trị) dưới tiêu đề: họ tên em, mã học sinh, môn...
    info: list[tuple[str, str]] = field(default_factory=list)
    greeting: str | None = None  # ví dụ "Kính gửi phụ huynh: Nguyễn Văn B"
    scores: list[tuple[str, str]] = field(default_factory=list)  # (môn, điểm hoặc Đạt / Chưa đạt)
    summary: list[str] = field(default_factory=list)  # các dòng tóm tắt dưới bảng điểm


@lru_cache
def register_fonts() -> None:
    """Đăng ký phông một lần cho cả tiến trình."""
    pdfmetrics.registerFont(TTFont(REGULAR, str(ASSETS / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(ASSETS / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(
        REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD
    )


def format_score(value: float | int) -> str:
    """Điểm kiểu Việt Nam: 6.5 thành "6,5", 8 thành "8,0"."""
    return f"{float(value):.1f}".replace(".", ",")


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=REGULAR, fontSize=10.5, leading=15, textColor=INK)
    return {
        "school": ParagraphStyle("school", parent=base, fontName=BOLD, fontSize=11.5, leading=15),
        "year": ParagraphStyle("year", parent=base, alignment=TA_RIGHT, textColor=MUTED),
        "title": ParagraphStyle(
            "title",
            parent=base,
            fontName=BOLD,
            fontSize=18,
            leading=24,
            alignment=TA_CENTER,
            textColor=BRAND,
            spaceBefore=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base, alignment=TA_CENTER, textColor=MUTED, spaceAfter=10
        ),
        "info": base,
        "greeting": ParagraphStyle("greeting", parent=base, fontName=BOLD, spaceBefore=8),
        "heading": ParagraphStyle(
            "heading",
            parent=base,
            fontName=BOLD,
            fontSize=11.5,
            textColor=BRAND,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base, fontSize=11, leading=17, alignment=TA_JUSTIFY, spaceAfter=6
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=10, leading=13),
        "cellb": ParagraphStyle("cellb", parent=base, fontName=BOLD, fontSize=10, leading=13),
        "cellr": ParagraphStyle("cellr", parent=base, fontSize=10, leading=13, alignment=TA_RIGHT),
        "cellbr": ParagraphStyle(
            "cellbr", parent=base, fontName=BOLD, fontSize=10, leading=13, alignment=TA_RIGHT
        ),
        "small": ParagraphStyle("small", parent=base, fontSize=10, textColor=MUTED),
        "sign": ParagraphStyle("sign", parent=base, alignment=TA_CENTER),
        "signb": ParagraphStyle("signb", parent=base, alignment=TA_CENTER, fontName=BOLD),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _score_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    data: list[list[Any]] = [[_p("Môn học", styles["cellb"]), _p("Kết quả", styles["cellbr"])]]
    data += [[_p(name, styles["cell"]), _p(value, styles["cellr"])] for name, value in rows]
    table = Table(data, colWidths=[None, 32 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TINT),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def render(document: PdfDocument) -> bytes:
    """Dàn trang một tài liệu A4 và trả về nội dung PDF."""
    register_fonts()
    styles = _styles()
    buffer = BytesIO()
    page = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{document.title} – {document.subtitle}",
        author=document.school_name,
    )

    header = Table(
        [
            [
                _p(document.school_name, styles["school"]),
                _p(f"Năm học {document.school_year}", styles["year"]),
            ]
        ],
        colWidths=[None, 55 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRAND),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story: list[Any] = [
        header,
        _p(document.title, styles["title"]),
        _p(document.subtitle, styles["subtitle"]),
    ]
    for label, value in document.info:
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(value)}", styles["info"]))
    if document.greeting:
        story.append(_p(document.greeting, styles["greeting"]))
    if document.scores:
        story += [_p("Kết quả học tập", styles["heading"]), _score_table(document.scores, styles)]
    for line in document.summary:
        story += [Spacer(1, 3), _p(line, styles["small"])]

    story.append(_p("Nhận xét", styles["heading"]))
    paragraphs = [chunk.strip() for chunk in document.body.split("\n") if chunk.strip()]
    story += [_p(chunk, styles["body"]) for chunk in paragraphs]

    signature = Table(
        [
            [
                "",
                [
                    _p(f"Ngày {format_date(document.approved_on)}", styles["sign"]),
                    _p(document.signer_title, styles["signb"]),
                    Spacer(1, 18 * mm),
                    _p(document.signer_name, styles["sign"]),
                ],
            ]
        ],
        colWidths=[None, 70 * mm],
    )
    signature.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Spacer(1, 12), KeepTogether(signature)]

    page.build(story)
    return buffer.getvalue()

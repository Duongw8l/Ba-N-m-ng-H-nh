"""Kiểm số liệu sau khi trợ lý trả lời (nguyên tắc 1, D-090).

Mọi con số trong câu trả lời phải đến từ kết quả của một hàm (hoặc nằm sẵn trong câu hỏi). Số nào
không tìm thấy trong các bằng chứng đó được trả về để giao diện cảnh báo người dùng: có thể là LLM
tự cộng, tự tính phần trăm, hay bịa; cũng có thể là dương tính giả (ví dụ viết số theo kiểu khác).
Đây là cảnh báo, không chặn câu trả lời.
"""

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

# Số nguyên hoặc thập phân (dấu . hoặc ,) đứng riêng: không dính vào chữ ("10A1") hay mã ("HS_01").
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")
# Số thứ tự đầu dòng của danh sách ("1. ", "2) ") chỉ là định dạng, không phải số liệu.
_LIST_MARKER = re.compile(r"^[ \t]*\d{1,2}[.)]\s", re.MULTILINE)


def _normalize(token: str) -> str:
    """Dạng chuẩn để so sánh: 6,5 và 6.50 cùng là 6.5; 7.0 là 7."""
    try:
        value = Decimal(token.replace(",", "."))
    except InvalidOperation:  # không xảy ra với _NUMBER; giữ nguyên cho chắc
        return token
    return format(value.normalize(), "f")


def numbers_in(text: str) -> list[str]:
    """Các số trong văn bản, đã chuẩn hoá, theo thứ tự xuất hiện (có lặp)."""
    return [_normalize(match) for match in _NUMBER.findall(text)]


def ungrounded_numbers(answer: str, evidence: Iterable[str]) -> list[str]:
    """Các số trong `answer` không xuất hiện trong bất kỳ đoạn bằng chứng nào, đúng như được viết
    trong câu trả lời (không trùng lặp, theo thứ tự xuất hiện)."""
    known: set[str] = set()
    for chunk in evidence:
        known.update(numbers_in(chunk))
    body = _LIST_MARKER.sub("", answer)
    missing: list[str] = []
    for match in _NUMBER.finditer(body):
        raw = match.group(0)
        if _normalize(raw) not in known and raw not in missing:
            missing.append(raw)
    return missing

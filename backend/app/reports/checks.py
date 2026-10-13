"""Kiểm tự động văn bản do AI viết, trước khi lưu thành bản nháp (D-105; nguyên tắc 1 và 6).

Hàm thuần, không đụng DB. Một văn bản chỉ được lưu khi không có vi phạm nào:
- mọi con số phải có trong dữ liệu đã đưa cho LLM (tái dùng `assistant.grounding`; ở trợ lý chỉ
  cảnh báo, ở đây chặn vì văn bản sẽ gửi tới phụ huynh);
- không có từ ngữ trong `banned_words.txt` (gắn nhãn tiêu cực, so sánh với bạn khác, hoàn cảnh gia
  đình);
- không có mã tạm `HS_xx` hay họ tên, mã học sinh thật (nhận xét gọi học sinh là "em");
- không có Markdown; độ dài hợp lý.

Mã vi phạm (`Violation.code`) là thứ duy nhất được lưu và gửi lại cho LLM khi viết lại: không bao
giờ lưu hay gửi lại chính văn bản vi phạm.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.assistant.grounding import ungrounded_numbers
from app.core.pseudonymize import Pseudonymizer, UnsafePayload

BANNED_WORDS_FILE = Path(__file__).with_name("banned_words.txt")
GROUP_CODES = {
    "tieu_cuc": "banned_negative",
    "so_sanh": "banned_comparison",
    "gia_dinh": "banned_family",
}
STUDENT_GROUPS = ("tieu_cuc", "so_sanh", "gia_dinh")  # nhận xét học sinh
AGGREGATE_GROUPS = ("tieu_cuc",)  # báo cáo lớp / khối: so sánh các lớp là đúng mục đích

STUDENT_LENGTH = (40, 900)  # số ký tự của cả đoạn nhận xét học sinh
AGGREGATE_LENGTH = (80, 2500)

# Lời dặn gửi lại LLM khi viết lại, theo mã vi phạm. Không chép lại văn bản vi phạm.
MESSAGES_VI = {
    "bad_format": "Phản hồi không đúng định dạng JSON được yêu cầu.",
    "missing_section": (
        "Thiếu một trong ba phần diem_manh, can_co_gang, goi_y, hoặc có phần để trống."
    ),
    "number_not_in_data": (
        "Có số không nằm trong dữ liệu: {detail}. Chỉ dùng số có sẵn trong dữ liệu, "
        "không tự tính, không làm tròn lại, không thêm số mới."
    ),
    "banned_negative": (
        "Có từ ngữ gắn nhãn tiêu cực. Hãy viết tích cực và nêu việc cần cố gắng một cách cụ thể."
    ),
    "banned_comparison": "Có so sánh với bạn khác hoặc với lớp. Chỉ nói về chính em.",
    "banned_family": "Có nhắc tới hoàn cảnh gia đình. Không được nhắc.",
    "student_identity": 'Có mã tạm hoặc tên học sinh trong văn bản. Hãy gọi học sinh là "em".',
    "markdown": "Có định dạng Markdown. Chỉ viết chữ thuần.",
    "too_short": "Văn bản quá ngắn.",
    "too_long": "Văn bản quá dài.",
}

# Lời báo cho GIÁO VIÊN khi văn bản họ sửa có điểm cần xem lại (khác lời dặn gửi LLM ở trên).
NOTICES_VI = {
    "bad_format": "Định dạng văn bản không hợp lệ.",
    "missing_section": "Thiếu một phần của nhận xét.",
    "number_not_in_data": "Số {detail} không có trong dữ liệu của hệ thống, hãy kiểm tra lại.",
    "banned_negative": "Có từ ngữ gắn nhãn tiêu cực với học sinh.",
    "banned_comparison": "Có so sánh với bạn khác hoặc với cả lớp.",
    "banned_family": "Có nhắc tới hoàn cảnh gia đình.",
    "student_identity": "Có tên hoặc mã của học sinh trong văn bản.",
    "markdown": "Có ký hiệu định dạng (như ** hoặc #) sẽ in ra nguyên văn.",
    "too_short": "Văn bản quá ngắn.",
    "too_long": "Văn bản quá dài.",
}

_MARKDOWN = re.compile(r"\*\*|__|`|^\s{0,3}#{1,6}\s|^\s*[-*•]\s|\[[^\]]+\]\([^)]+\)", re.MULTILINE)
_TEMP_CODE = re.compile(r"(?<!\w)HS_\d+(?!\w)", re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str | None = None  # chỉ dùng cho số ngoài dữ liệu (để LLM biết số nào phải bỏ)

    def message(self) -> str:
        """Lời dặn gửi LLM khi viết lại."""
        return MESSAGES_VI[self.code].format(detail=self.detail or "")

    def notice(self) -> str:
        """Lời báo cho giáo viên về văn bản họ vừa sửa."""
        return NOTICES_VI[self.code].format(detail=self.detail or "")


@dataclass(frozen=True)
class BannedRules:
    patterns: dict[str, tuple[re.Pattern[str], ...]]

    def groups_found(self, text: str, groups: tuple[str, ...]) -> list[str]:
        """Tên các nhóm có ít nhất một cụm khớp trong `text`."""
        normalized = unicodedata.normalize("NFC", text)
        return [
            group
            for group in groups
            if any(pattern.search(normalized) for pattern in self.patterns.get(group, ()))
        ]


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    words = unicodedata.normalize("NFC", phrase).split()
    body = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def parse_banned_words(content: str) -> BannedRules:
    """Đọc nội dung `banned_words.txt`. Tên nhóm lạ là lỗi (gõ nhầm sẽ làm mất một nhóm kiểm)."""
    groups: dict[str, list[re.Pattern[str]]] = {}
    current: str | None = None
    for number, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            if current not in GROUP_CODES:
                raise ValueError(f"banned_words.txt dòng {number}: nhóm lạ [{current}].")
            groups.setdefault(current, [])
            continue
        if current is None:
            raise ValueError(f"banned_words.txt dòng {number}: cụm từ nằm ngoài mọi nhóm.")
        groups[current].append(_phrase_pattern(line))
    return BannedRules({group: tuple(patterns) for group, patterns in groups.items()})


@lru_cache
def load_banned_rules() -> BannedRules:
    return parse_banned_words(BANNED_WORDS_FILE.read_text(encoding="utf-8"))


def check_text(
    text: str,
    *,
    evidence: str,
    student_scope: bool,
    pseudo: Pseudonymizer | None = None,
    rules: BannedRules | None = None,
) -> list[Violation]:
    """Mọi vi phạm của `text`; rỗng nghĩa là đạt.

    `evidence` là dữ liệu JSON đã đưa cho LLM: số trong văn bản phải nằm trong đó. `pseudo` biết
    họ tên và mã thật của học sinh trong lớp để bắt chúng lọt vào văn bản.
    """
    rules = rules or load_banned_rules()
    violations: list[Violation] = []

    low, high = STUDENT_LENGTH if student_scope else AGGREGATE_LENGTH
    if len(text.strip()) < low:
        violations.append(Violation("too_short"))
    elif len(text) > high:
        violations.append(Violation("too_long"))

    if _MARKDOWN.search(text):
        violations.append(Violation("markdown"))

    missing = ungrounded_numbers(text, [evidence])
    if missing:
        violations.append(Violation("number_not_in_data", ", ".join(missing[:5])))

    groups = STUDENT_GROUPS if student_scope else AGGREGATE_GROUPS
    violations += [Violation(GROUP_CODES[g]) for g in rules.groups_found(text, groups)]

    if _TEMP_CODE.search(text) or _reveals_identity(text, pseudo):
        violations.append(Violation("student_identity"))
    return violations


def _reveals_identity(text: str, pseudo: Pseudonymizer | None) -> bool:
    if pseudo is None:
        return False
    try:
        pseudo.assert_safe(text)
    except UnsafePayload:
        return True
    return False

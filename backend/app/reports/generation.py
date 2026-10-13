"""Sinh nhận xét và báo cáo bằng LLM (Giai đoạn 9, D-106; nguyên tắc 1, 3, 5 và 6).

LLM ở đây KHÔNG được gọi hàm nào (`tools=[]`): số liệu do code lấy từ Analytics (`facts.py`) rồi đưa
vào lời nhắc, nên LLM chỉ diễn giải. Luồng của một nhóm tối đa `BATCH_SIZE` học sinh:

1. ẩn danh: mỗi em một mã tạm `HS_01`...; hàng rào `assert_safe` chạy trước MỖI lần gọi LLM;
2. LLM trả JSON `{"HS_01": {"diem_manh", "can_co_gang", "goi_y"}}`; thiếu khoá hoặc để trống là lỗi;
3. mỗi em được kiểm riêng (`checks.check_text`, số liệu của chính em đó). Em nào không đạt thì viết
   lại RIÊNG từng em, tối đa `MAX_REWRITES` lần, kèm lý do bằng lời (không chép lại văn bản lỗi);
4. vẫn không đạt thì trả `needs_manual` với văn bản rỗng để giáo viên tự viết.

Gộp nhóm để tiết kiệm yêu cầu (gói Gemini miễn phí chỉ 20 yêu cầu mỗi ngày mỗi mô hình): một lớp 40
em cần khoảng 8 lần gọi. Em nào xong thì `on_outcome` được gọi NGAY, nên lỗi LLM giữa chừng (ném
`LLMError`) không làm mất phần đã viết.
"""

import json
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.assistant.llm import LLMProvider, Message
from app.core.enums import ReportType
from app.core.pseudonymize import Pseudonymizer, RosterStudent
from app.reports.checks import Violation, check_text
from app.reports.prompts import PromptKind, load_prompt

BATCH_SIZE = 5
MAX_REWRITES = 2  # số lần viết lại tối đa sau lần đầu (PROMPTS Giai đoạn 9)
MAX_FEEDBACK_CHARS = 300
SECTIONS = ("diem_manh", "can_co_gang", "goi_y")

TYPE_GUIDE = {
    ReportType.SCHOOL_RECORD: (
        "Loại cần viết: nhận xét chung trong học bạ cuối học kỳ. Giọng trang trọng, ngắn gọn; nhận "
        "xét chung về học tập, rèn luyện và chuyên cần của em trong kỳ."
    ),
    ReportType.CONTACT_SLIP: (
        "Loại cần viết: nhận xét trong phiếu liên lạc gửi phụ huynh. Giọng lịch sự, thân thiện, "
        "người viết là giáo viên chủ nhiệm. Nếu em có nghỉ học thì nêu số buổi nghỉ trong dữ liệu; "
        "gợi ý một việc gia đình có thể phối hợp. Không nhắc cảnh báo hay khả năng lên lớp."
    ),
    ReportType.SUBJECT_COMMENT: (
        "Loại cần viết: nhận xét một môn học của giáo viên bộ môn. Chỉ nói về môn trong dữ liệu "
        "(các đầu điểm, mức độ hoàn thành, kết quả); gợi ý cách học hoặc ôn tập môn này."
    ),
}
TYPE_LABELS = {
    ReportType.SCHOOL_RECORD: "nhận xét học bạ",
    ReportType.CONTACT_SLIP: "nhận xét phiếu liên lạc",
    ReportType.SUBJECT_COMMENT: "nhận xét môn",
    ReportType.REPORT: "báo cáo",
}

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class FeedbackRejected(ValueError):
    """Góp ý của giáo viên không dùng được (ví dụ nêu tên trùng với nhiều học sinh)."""


@dataclass(frozen=True)
class StudentItem:
    student: RosterStudent
    facts: dict[str, Any]


@dataclass(frozen=True)
class Outcome:
    """Kết quả cuối của một em (hoặc một báo cáo). `text` rỗng khi cần giáo viên tự viết."""

    key: int  # id học sinh; 0 với báo cáo lớp / khối
    text: str
    needs_manual: bool
    notes: tuple[str, ...]  # mã vi phạm của lần viết cuối cùng khi needs_manual; rỗng nếu đạt
    attempts: int


OutcomeSink = Callable[[Outcome], None]


# --- Dựng và đọc tin nhắn ---------------------------------------------------------------------


def parse_json_object(text: str | None) -> dict[str, Any] | None:
    """Đối tượng JSON trong phản hồi của LLM (chịu được khối ```json và chữ thừa quanh nó)."""
    if not text:
        return None
    body = _FENCE.sub("", text.strip()).strip()
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def extract_sections(entry: Any) -> list[str] | None:
    """Ba phần của một nhận xét đã gọn khoảng trắng; None nếu thiếu khoá hoặc có phần rỗng."""
    if not isinstance(entry, dict):
        return None
    parts: list[str] = []
    for key in SECTIONS:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        parts.append(" ".join(unicodedata.normalize("NFC", value).split()))
    return parts


def _data_block(payload: Any) -> str:
    """Dữ liệu trong thẻ <du_lieu>; chuỗi "</" bị vô hiệu để dữ liệu không đóng thẻ sớm."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    body = body.replace("</", "<\\/")
    return f"<du_lieu>{body}</du_lieu>"


def prepare_feedback(pseudo: Pseudonymizer, feedback: str | None) -> str | None:
    """Góp ý của giáo viên khi sinh lại: cắt độ dài, ẩn danh họ tên, vô hiệu thẻ đóng."""
    text = (feedback or "").strip()[:MAX_FEEDBACK_CHARS]
    if not text:
        return None
    question = pseudo.pseudonymize_question(text)
    if question.ambiguous is not None:
        raise FeedbackRejected(
            f'Có {question.ambiguous.count} học sinh khớp "{question.ambiguous.name}". '
            "Hãy viết góp ý không nêu tên em."
        )
    return question.text.replace("</", "<\\/")


def _notes_block(violations: Sequence[Violation]) -> str:
    lines = "; ".join(v.message() for v in violations)
    return f"Bản viết trước không đạt kiểm tra vì: {lines} Hãy viết lại, sửa các lỗi này."


def _student_message(
    report_type: ReportType,
    entries: dict[str, dict[str, Any]],
    *,
    violations: Sequence[Violation] = (),
    feedback: str | None = None,
) -> str:
    parts = [
        f"Loại cần viết: {TYPE_LABELS[report_type]}.",
        "Dữ liệu của các học sinh (mỗi mã là một học sinh):",
        _data_block(entries),
    ]
    if feedback:
        parts.append(f"Góp ý của giáo viên cho lần viết này:\n<gop_y>{feedback}</gop_y>")
    if violations:
        parts.append(_notes_block(violations))
    codes = ", ".join(entries)
    parts.append(f"Hãy viết nhận xét cho đủ các mã: {codes}. Chỉ trả về JSON.")
    return "\n".join(parts)


def _ask(
    provider: LLMProvider, pseudo: Pseudonymizer, system: str, user: str, payload: Any
) -> dict[str, Any] | None:
    messages = [Message("system", system), Message("user", user)]
    # Hàng rào ẩn danh trước MỖI lần gọi LLM (nguyên tắc 5). Quét cả `payload` (dữ liệu còn ở dạng
    # dict) vì khoá cấm như `full_name` chỉ bắt được khi chưa bị nhét vào một chuỗi JSON.
    pseudo.assert_safe([messages, payload])
    reply = provider.chat(messages, [])
    return parse_json_object(reply.text)


def _system_prompt(kind: PromptKind, report_type: ReportType | None) -> str:
    base = load_prompt(kind)
    if report_type is None or report_type not in TYPE_GUIDE:
        return base
    return f"{base}\n\n# Loại nhận xét lần này\n\n{TYPE_GUIDE[report_type]}"


# --- Nhận xét học sinh ------------------------------------------------------------------------


def _judge(
    data: dict[str, Any] | None, code: str, item: StudentItem, pseudo: Pseudonymizer
) -> tuple[str, list[Violation]]:
    """Văn bản của một em trong phản hồi và các vi phạm của nó (rỗng nghĩa là đạt)."""
    entries = {str(key).strip().upper(): value for key, value in (data or {}).items()}
    if code not in entries:
        return "", [Violation("bad_format")]
    sections = extract_sections(entries[code])
    if sections is None:
        return "", [Violation("missing_section")]
    text = " ".join(sections)
    evidence = json.dumps(item.facts, ensure_ascii=False, default=str)
    return text, check_text(text, evidence=evidence, student_scope=True, pseudo=pseudo)


def generate_students(
    provider: LLMProvider,
    *,
    report_type: ReportType,
    items: Sequence[StudentItem],
    roster: Sequence[RosterStudent],
    open_class_id: int,
    on_outcome: OutcomeSink,
    feedback: str | None = None,
) -> None:
    """Viết nhận xét cho các em trong `items`, từng nhóm `BATCH_SIZE` em. Mỗi em xong là gọi ngay
    `on_outcome`. Ném `LLMError` (hết hạn mức, mạng...) hoặc `UnsafePayload` (hàng rào ẩn danh)."""
    system = _system_prompt("comment", report_type)
    for start in range(0, len(items), BATCH_SIZE):
        _generate_batch(
            provider,
            system,
            report_type,
            items[start : start + BATCH_SIZE],
            roster,
            open_class_id,
            on_outcome,
            feedback,
        )


def _generate_batch(
    provider: LLMProvider,
    system: str,
    report_type: ReportType,
    batch: Sequence[StudentItem],
    roster: Sequence[RosterStudent],
    open_class_id: int,
    on_outcome: OutcomeSink,
    raw_feedback: str | None,
) -> None:
    pseudo = Pseudonymizer(roster, open_class_id)
    feedback = prepare_feedback(pseudo, raw_feedback)
    code_of = {item.student.student_id: pseudo.code_for(item.student) for item in batch}

    entries = {code_of[item.student.student_id]: item.facts for item in batch}
    message = _student_message(report_type, entries, feedback=feedback)
    data = _ask(provider, pseudo, system, message, entries)
    failed: list[tuple[StudentItem, list[Violation]]] = []
    for item in batch:
        text, violations = _judge(data, code_of[item.student.student_id], item, pseudo)
        if violations:
            failed.append((item, violations))
        else:
            on_outcome(Outcome(item.student.student_id, text, False, (), 1))

    for item, violations in failed:
        _rewrite_one(
            provider, system, report_type, item, violations, pseudo, code_of, on_outcome, feedback
        )


def _rewrite_one(
    provider: LLMProvider,
    system: str,
    report_type: ReportType,
    item: StudentItem,
    violations: list[Violation],
    pseudo: Pseudonymizer,
    code_of: dict[int, str],
    on_outcome: OutcomeSink,
    feedback: str | None,
) -> None:
    code = code_of[item.student.student_id]
    for attempt in range(2, MAX_REWRITES + 2):
        message = _student_message(
            report_type, {code: item.facts}, violations=violations, feedback=feedback
        )
        data = _ask(provider, pseudo, system, message, {code: item.facts})
        text, violations = _judge(data, code, item, pseudo)
        if not violations:
            on_outcome(Outcome(item.student.student_id, text, False, (), attempt))
            return
    codes = tuple(dict.fromkeys(v.code for v in violations))
    on_outcome(Outcome(item.student.student_id, "", True, codes, MAX_REWRITES + 1))


# --- Báo cáo lớp và khối ----------------------------------------------------------------------


def generate_aggregate(
    provider: LLMProvider,
    *,
    scope_label: str,
    facts: dict[str, Any],
    roster: Sequence[RosterStudent],
    open_class_id: int | None,
    feedback: str | None = None,
) -> Outcome:
    """Viết báo cáo một lớp hoặc một khối (`scope_label` như "lớp 11A2"). Không nêu học sinh nào."""
    pseudo = Pseudonymizer(roster, open_class_id)
    note = prepare_feedback(pseudo, feedback)
    system = _system_prompt("aggregate", None)
    evidence = json.dumps(facts, ensure_ascii=False, default=str)
    violations: list[Violation] = []
    for attempt in range(1, MAX_REWRITES + 2):
        parts = [f"Báo cáo cho {scope_label}.", "Dữ liệu:", _data_block(facts)]
        if note:
            parts.append(f"Góp ý của người dùng cho lần viết này:\n<gop_y>{note}</gop_y>")
        if violations:
            parts.append(_notes_block(violations))
        parts.append("Chỉ trả về JSON.")
        data = _ask(provider, pseudo, system, "\n".join(parts), facts)
        sections = extract_sections(data)
        if sections is None:
            violations = [Violation("bad_format" if data is None else "missing_section")]
            continue
        text = "\n\n".join(sections)
        violations = check_text(text, evidence=evidence, student_scope=False, pseudo=pseudo)
        if not violations:
            return Outcome(0, text, False, (), attempt)
    codes = tuple(dict.fromkeys(v.code for v in violations))
    return Outcome(0, "", True, codes, MAX_REWRITES + 1)

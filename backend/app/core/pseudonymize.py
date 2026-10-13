"""pseudonymize / depseudonymize: ẩn danh học sinh trước khi dữ liệu sang LLM (nguyên tắc 5, D-086).

Họ tên và mã học sinh thật được đổi thành mã tạm `HS_01`, `HS_02`... trước khi gửi LLM, và đổi lại
khi hiển thị cho người dùng. Không bao giờ đưa `date_of_birth`, `guardian_name`, `guardian_phone`
vào ngữ cảnh LLM.

`Pseudonymizer` chỉ sống trong MỘT request (không có bảng giải mã, không lưu ở đâu): mã `HS_01` của
request này là một em khác ở request sau. Mã cấp theo thứ tự xuất hiện, cùng một em luôn cùng một mã
trong request.

Ba việc:
- `pseudonymize_question`: đổi họ tên đầy đủ và mã học sinh thật trong câu hỏi của người dùng. Tên
  gọi riêng ("An") chỉ khớp phân biệt hoa thường, trong lớp đang mở, và khi chỉ có một em; trùng
  tên thì báo `AmbiguousName` để hỏi lại, không đoán.
- `code_for` / `resolve`: các hàm tra cứu cấp mã khi dựng kết quả; LLM gọi hàm bằng mã tạm và chỉ
  giải được mã đã cấp trong request này.
- `assert_safe`: hàng rào cuối, chạy trước MỖI lần gọi LLM: quét sâu khoá cấm và mọi họ tên/mã thật
  đã biết; có thì ném `UnsafePayload` và không gọi LLM.
"""

import dataclasses
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

# Khoá không bao giờ được xuất hiện trong dữ liệu gửi LLM. `full_name` là khoá của danh tính thật:
# kết quả hàm chỉ có mã tạm. (`student_code` KHÔNG cấm: đó là tên tham số của get_student_detail
# theo DESIGN, giá trị là mã tạm; mã học sinh thật bị bắt bằng quét giá trị.)
FORBIDDEN_KEYS = frozenset({"date_of_birth", "guardian_name", "guardian_phone", "full_name"})

_CODE = re.compile(r"(?<![\w])HS_(\d+)(?![\w])", re.IGNORECASE)


class PseudonymError(Exception):
    pass


class UnsafePayload(PseudonymError):
    """Dữ liệu định gửi LLM còn chứa danh tính thật hoặc khoá cấm."""


@dataclass(frozen=True)
class RosterStudent:
    student_id: int
    class_id: int
    full_name: str
    student_code: str


@dataclass(frozen=True)
class AmbiguousName:
    """Tên gọi riêng khớp nhiều hơn một học sinh trong lớp đang mở."""

    name: str
    count: int


@dataclass(frozen=True)
class PseudonymizedQuestion:
    text: str
    ambiguous: AmbiguousName | None = None


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _fold(text: str) -> str:
    return " ".join(_norm(text).casefold().split())


def given_name(full_name: str) -> str:
    """Tên gọi: từ cuối của họ tên (Trần Minh An -> An)."""
    parts = _norm(full_name).split()
    return parts[-1] if parts else ""


def _word_pattern(literal: str, *, ignore_case: bool) -> re.Pattern[str]:
    # Cho phép khoảng trắng bất kỳ giữa các từ của họ tên; biên từ theo Unicode.
    body = r"\s+".join(re.escape(part) for part in _norm(literal).split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE if ignore_case else 0)


class Pseudonymizer:
    def __init__(self, roster: Iterable[RosterStudent] = (), open_class_id: int | None = None):
        self._open_class_id = open_class_id
        self._students: dict[int, RosterStudent] = {}
        self._code_of: dict[int, str] = {}
        self._student_of_code: dict[str, int] = {}
        for student in roster:
            self.register(student)

    # --- Danh sách học sinh đã biết ----------------------------------------------------------

    def register(self, student: RosterStudent) -> None:
        """Ghi nhận một học sinh (để hàng rào và việc khớp tên biết danh tính thật của em)."""
        self._students.setdefault(student.student_id, student)

    def known_students(self) -> Sequence[RosterStudent]:
        return list(self._students.values())

    # --- Cấp và giải mã ----------------------------------------------------------------------

    def code_for(self, student: RosterStudent) -> str:
        """Mã tạm của học sinh; cấp mới (theo thứ tự xuất hiện) nếu chưa có trong request này."""
        self.register(student)
        code = self._code_of.get(student.student_id)
        if code is None:
            code = f"HS_{len(self._code_of) + 1:02d}"
            self._code_of[student.student_id] = code
            self._student_of_code[code] = student.student_id
        return code

    def resolve(self, code: str) -> RosterStudent | None:
        """Học sinh ứng với mã tạm; None nếu mã chưa được cấp trong request này."""
        match = _CODE.fullmatch(code.strip())
        if match is None:
            return None
        normalized = f"HS_{int(match.group(1)):02d}"
        student_id = self._student_of_code.get(normalized)
        return None if student_id is None else self._students[student_id]

    def depseudonymize(self, text: str) -> str:
        """Đổi mã tạm đã cấp về họ tên thật. Mã chưa cấp (LLM bịa) được để nguyên."""

        def replace(match: re.Match[str]) -> str:
            student = self.resolve(match.group(0))
            return match.group(0) if student is None else student.full_name

        return _CODE.sub(replace, text)

    # --- Câu hỏi của người dùng -------------------------------------------------------------

    def pseudonymize_question(self, text: str) -> PseudonymizedQuestion:
        text = _norm(text)
        # 1) Mã học sinh thật (ví dụ HS1102001).
        for student in sorted(self._students.values(), key=lambda s: -len(s.student_code)):
            if student.student_code:
                pattern = _word_pattern(student.student_code, ignore_case=True)
                text = pattern.sub(lambda _m, s=student: self.code_for(s), text)

        # 2) Họ tên đầy đủ, tên dài trước. Hai em trùng họ tên đầy đủ thì không đoán.
        by_name: dict[str, list[RosterStudent]] = {}
        for student in self._students.values():
            by_name.setdefault(_fold(student.full_name), []).append(student)
        for key in sorted(by_name, key=len, reverse=True):
            candidates = by_name[key]
            pattern = _word_pattern(candidates[0].full_name, ignore_case=True)
            if not pattern.search(text):
                continue
            if len(candidates) > 1:
                return PseudonymizedQuestion(
                    text, AmbiguousName(candidates[0].full_name, len(candidates))
                )
            text = pattern.sub(lambda _m, s=candidates[0]: self.code_for(s), text)

        # 3) Tên gọi riêng: chỉ trong lớp đang mở, phân biệt hoa thường, và phải duy nhất.
        if self._open_class_id is not None:
            by_given: dict[str, list[RosterStudent]] = {}
            for student in self._students.values():
                if student.class_id == self._open_class_id and given_name(student.full_name):
                    by_given.setdefault(given_name(student.full_name), []).append(student)
            for name in sorted(by_given, key=len, reverse=True):
                pattern = _word_pattern(name, ignore_case=False)
                if not pattern.search(text):
                    continue
                candidates = by_given[name]
                if len(candidates) > 1:
                    return PseudonymizedQuestion(text, AmbiguousName(name, len(candidates)))
                text = pattern.sub(lambda _m, s=candidates[0]: self.code_for(s), text)
        return PseudonymizedQuestion(text)

    # --- Hàng rào cuối ----------------------------------------------------------------------

    def assert_safe(self, payload: Any) -> None:
        """Ném `UnsafePayload` nếu `payload` (tin nhắn, kết quả hàm...) còn khoá cấm hoặc danh tính
        thật của bất kỳ học sinh nào đã biết."""
        names = [_fold(s.full_name) for s in self._students.values() if s.full_name]
        codes = [
            _word_pattern(s.student_code, ignore_case=True)
            for s in self._students.values()
            if s.student_code
        ]
        for text in _strings(payload):
            folded = _fold(text)
            for name in names:
                if name and name in folded:
                    raise UnsafePayload("Dữ liệu gửi LLM còn chứa họ tên học sinh thật.")
            for pattern in codes:
                if pattern.search(text):
                    raise UnsafePayload("Dữ liệu gửi LLM còn chứa mã học sinh thật.")


def _strings(payload: Any) -> Iterable[str]:
    """Mọi chuỗi (khoá và giá trị) trong cấu trúc lồng nhau; ném UnsafePayload nếu gặp khoá cấm."""
    if dataclasses.is_dataclass(payload) and not isinstance(payload, type):
        payload = dataclasses.asdict(payload)
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str):
                if key.casefold() in FORBIDDEN_KEYS:
                    raise UnsafePayload(f'Dữ liệu gửi LLM có khoá bị cấm "{key}".')
                yield key
            yield from _strings(value)
    elif isinstance(payload, (list, tuple, set, frozenset)):
        for item in payload:
            yield from _strings(item)

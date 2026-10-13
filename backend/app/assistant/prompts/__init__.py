"""System prompt của trợ lý, lưu ở file riêng và có phiên bản (D-089).

Đổi nội dung prompt thì thêm file mới `system_v2.vi.md` và đổi `PROMPT_VERSION`; mỗi dòng
`ai_logs` ghi phiên bản prompt đã dùng để truy vết.
"""

from functools import lru_cache
from pathlib import Path

PROMPT_VERSION = "v1"
PROMPT_FILE = Path(__file__).with_name(f"system_{PROMPT_VERSION}.vi.md")


@lru_cache
def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8").strip()

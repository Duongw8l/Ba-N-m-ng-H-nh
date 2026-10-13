"""Lời nhắc viết nhận xét và báo cáo, lưu ở file riêng và có phiên bản (D-106).

Đổi nội dung thì thêm file mới (`comment_v2.vi.md`...) và đổi `PROMPT_VERSION`; mỗi bản nhận xét ghi
phiên bản lời nhắc đã dùng để truy vết.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

PROMPT_VERSION = "reports-v1"
_FILE_VERSION = "v1"

PromptKind = Literal["comment", "aggregate"]


@lru_cache
def load_prompt(kind: PromptKind) -> str:
    path = Path(__file__).with_name(f"{kind}_{_FILE_VERSION}.vi.md")
    return path.read_text(encoding="utf-8").strip()

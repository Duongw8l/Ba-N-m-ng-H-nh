"""Bộ khởi chạy của seed, thường gọi qua `make seed`.

Cú pháp: `python data/seed/run.py [--seed N] [--classes-per-grade N] [--class-size N]`.
Chạy từ thư mục nào cũng được. Việc ở đây chỉ là sửa sys.path trước khi import:
- bỏ thư mục data/seed (Python tự thêm khi chạy script) để tên file trong đó không che module khác;
- thêm backend/ (gói app) và thư mục gốc repo (gói data.seed).
"""

import sys
from pathlib import Path

_SEED_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SEED_DIR.parents[1]

sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != _SEED_DIR]
for _entry in (_REPO_ROOT, _REPO_ROOT / "backend"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from data.seed.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

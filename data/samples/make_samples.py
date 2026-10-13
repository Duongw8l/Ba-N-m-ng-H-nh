"""Sinh lại các tệp mẫu trong data/samples/, thường gọi qua `make samples`.

Cú pháp: `python data/samples/make_samples.py`. Chạy từ thư mục nào cũng được. Cần DB đã migrate
(make db, make migrate) vì hệ số tính ĐTB đọc từ bảng settings; không cần đã seed.
Việc đầu tiên là sửa sys.path trước khi import, giống data/seed/run.py.
"""

import sys
from pathlib import Path

_SAMPLES_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SAMPLES_DIR.parents[1]

sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != _SAMPLES_DIR]
for _entry in (_REPO_ROOT, _REPO_ROOT / "backend"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.analytics.config import MissingSettingError, load_config  # noqa: E402
from app.core.db import get_engine  # noqa: E402
from data.samples.build import build_samples  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    try:
        with Session(get_engine()) as session:
            config = load_config(session)
    except OperationalError:
        print(
            "Không kết nối được PostgreSQL. Chạy make db rồi make migrate trước "
            "(DATABASE_URL trong .env, host 127.0.0.1).",
            file=sys.stderr,
        )
        return 1
    except MissingSettingError as error:
        print(str(error), file=sys.stderr)
        return 1

    for name, content in build_samples(config).items():
        (_SAMPLES_DIR / name).write_bytes(content)
        print(f"Đã ghi data/samples/{name} ({len(content):,} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

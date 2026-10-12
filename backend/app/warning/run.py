"""Chạy cảnh báo sớm từ dòng lệnh: `make warn` hoặc `python -m app.warning.run [--class-id N]`.

Dùng sau `make seed` (seed tự gọi) hoặc khi muốn tính lại cho cả trường, ví dụ sau khi thay mô hình.
Chỉ thêm dòng mới vào risk_alerts khi nội dung đổi nên chạy lại bao nhiêu lần cũng an toàn.
"""

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy.exc import OperationalError

from app.core.db import get_session_factory
from app.warning.model import load_predictor
from app.warning.service import refresh_all, refresh_class


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(prog="make warn", description="Chạy cảnh báo sớm.")
    parser.add_argument("--class-id", type=int, default=None, help="chỉ chạy cho một lớp")
    args = parser.parse_args(argv)

    predictor = load_predictor()
    mode = f"luật + mô hình {predictor.version}" if predictor else "chỉ lớp luật (chưa có mô hình)"
    try:
        with get_session_factory()() as session:
            if args.class_id is None:
                result = refresh_all(session, predictor=predictor)
            else:
                result = refresh_class(session, args.class_id, predictor=predictor)
            session.commit()
    except OperationalError:
        print(
            "Không kết nối được PostgreSQL. Chạy make db rồi make migrate trước "
            "(DATABASE_URL trong .env, host 127.0.0.1).",
            file=sys.stderr,
        )
        return 1
    except LookupError as error:
        print(str(error), file=sys.stderr)
        return 1

    counts = result.counts
    print(f"Cảnh báo sớm ({mode}): thêm {result.inserted} dòng mới, giữ nguyên {result.unchanged}.")
    print(
        f"Hiện hành: mức Cao {counts['high']}, Trung bình {counts['medium']}, Thấp {counts['low']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

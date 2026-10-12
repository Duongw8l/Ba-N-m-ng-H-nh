"""Dòng lệnh của seed: `make seed` (xem data/seed/run.py)."""

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy.exc import OperationalError

from app.core.db import get_engine
from data.seed.load import (
    SeedPrerequisiteMissing,
    SeedRefused,
    SeedSummary,
    seed_database,
    table_order,
)
from data.seed.params import (
    DEFAULT_CLASS_SIZE,
    DEFAULT_CLASSES_PER_GRADE,
    DEFAULT_SEED,
    SeedParams,
)
from data.seed.people import EMAIL_DOMAIN


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="make seed",
        description="Sinh dữ liệu giả lập (xoá dữ liệu cũ trong DB phát triển rồi nạp lại).",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="số ngẫu nhiên (lặp lại được)"
    )
    parser.add_argument(
        "--classes-per-grade", type=int, default=DEFAULT_CLASSES_PER_GRADE, help="số lớp mỗi khối"
    )
    parser.add_argument("--class-size", type=int, default=DEFAULT_CLASS_SIZE, help="sĩ số mỗi lớp")
    return parser.parse_args(argv)


def format_summary(summary: SeedSummary, params: SeedParams) -> str:
    lines = [
        "",
        f"Đã nạp dữ liệu giả lập (seed={params.seed}, {params.classes_per_grade} lớp/khối, "
        f"sĩ số {params.class_size}).",
        "",
        "Số dòng mỗi bảng:",
    ]
    lines += [f"  {name:<22}{summary.row_counts[name]:>8}" for name in table_order()]
    lines += [
        "",
        f"Học sinh: {summary.row_counts['students']}",
        f"  nghỉ từ 30 buổi:                          {summary.heavy_absence_students}",
        f"  có đầu điểm dưới 3,5:                     {summary.low_score_students}",
        f"  biên, đúng 45 buổi nghỉ:                  {summary.boundary_absence_45}",
        f"  biên, có môn mọi đầu điểm đúng 3,5:       {summary.boundary_score_3_5}",
        f"  biên, có môn mọi đầu điểm đúng 5,0:       {summary.boundary_score_5_0}",
        "",
        f"Đăng nhập thử: admin@{EMAIL_DOMAIN}, bgh1@{EMAIL_DOMAIN}, gvcn.10a2@{EMAIL_DOMAIN}, "
        f"gv.toan.10@{EMAIL_DOMAIN}",
        "Mật khẩu dev dùng chung cho mọi tài khoản: xem README (mục tài khoản dev).",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    # Windows: console mặc định không phải UTF-8 (xem D-020).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    args = _parse_args(argv)
    try:
        params = SeedParams(
            seed=args.seed, classes_per_grade=args.classes_per_grade, class_size=args.class_size
        )
    except ValueError as error:
        print(f"Tham số không hợp lệ: {error}", file=sys.stderr)
        return 2

    print("Cảnh báo: seed xoá MỌI dữ liệu trường học trong DB phát triển rồi nạp lại.")
    try:
        summary = seed_database(get_engine(), params)
    except SeedRefused as error:
        print(str(error), file=sys.stderr)
        return 1
    except SeedPrerequisiteMissing as error:
        print(str(error), file=sys.stderr)
        return 1
    except OperationalError:
        print(
            "Không kết nối được PostgreSQL. Chạy make db rồi make migrate trước "
            "(DATABASE_URL trong .env, host 127.0.0.1).",
            file=sys.stderr,
        )
        return 1

    print(format_summary(summary, params))
    return 0

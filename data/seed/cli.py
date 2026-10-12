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

SAMPLE_ATTENDANCE_MONTH = (2027, 3)  # tháng của data/samples/diem-danh-11a2-2027-03.csv


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
    parser.add_argument(
        "--hold-out",
        type=_parse_month,
        default=None,
        metavar="YYYY-MM",
        help="bỏ điểm danh của tháng này khỏi DB để nhập lại từ tệp mẫu data/samples/ "
        "(kịch bản demo: --hold-out 2027-03). Mặc định: đủ cả năm học",
    )
    parser.add_argument(
        "--no-warn",
        action="store_true",
        help="không chạy cảnh báo sớm sau khi nạp (mặc định có chạy)",
    )
    return parser.parse_args(argv)


def _parse_month(text: str) -> tuple[int, int]:
    try:
        year_text, month_text = text.split("-")
        year, month = int(year_text), int(month_text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' không phải tháng dạng YYYY-MM.") from None
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError(f"'{text}' không phải tháng dạng YYYY-MM.")
    return year, month


def format_summary(summary: SeedSummary, params: SeedParams) -> str:
    lines = [
        "",
        f"Đã nạp dữ liệu giả lập (seed={params.seed}, {params.classes_per_grade} lớp/khối, "
        f"sĩ số {params.class_size}).",
        "",
        "Số dòng mỗi bảng:",
    ]
    lines += [f"  {name:<22}{summary.row_counts[name]:>8}" for name in table_order()]
    if params.hold_out_month is not None:
        year, month = params.hold_out_month
        lines += ["", f"Đã bỏ điểm danh tháng {month:02d}/{year} khỏi DB (--hold-out)."]
        if (year, month) == SAMPLE_ATTENDANCE_MONTH:
            lines.append(
                "Nhập lại bằng tệp data/samples/diem-danh-11a2-2027-03.csv (xem "
                "data/samples/README.md)."
            )
        lines.append("Số buổi nghỉ trong thống kê dưới đây chưa tính tháng đó.")
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
            seed=args.seed,
            classes_per_grade=args.classes_per_grade,
            class_size=args.class_size,
            hold_out_month=args.hold_out,
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
    if not args.no_warn:
        print(_run_early_warning())
    return 0


def _run_early_warning() -> str:
    """Chạy cảnh báo sớm cho mọi lớp vừa nạp (Giai đoạn 6) để demo có cảnh báo ngay.

    Lỗi ở bước này không làm hỏng việc nạp dữ liệu giả: chỉ báo và hướng dẫn chạy `make warn`.
    """
    from app.core.db import get_session_factory
    from app.warning.model import load_predictor
    from app.warning.service import refresh_all

    try:
        predictor = load_predictor()
        with get_session_factory()() as session:
            result = refresh_all(session, predictor=predictor)
            session.commit()
    except Exception as error:  # noqa: BLE001
        return f"Chưa chạy được cảnh báo sớm ({error}). Chạy lại bằng make warn."
    counts = result.counts
    mode = f"luật + mô hình {predictor.version}" if predictor else "chỉ lớp luật"
    return (
        f"Cảnh báo sớm ({mode}): mức Cao {counts['high']}, Trung bình {counts['medium']}, "
        f"Thấp {counts['low']}."
    )

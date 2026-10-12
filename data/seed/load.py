"""Nạp dữ liệu giả vào PostgreSQL và thống kê kết quả.

Nạp trong MỘT transaction: xoá dữ liệu cũ (TRUNCATE ... RESTART IDENTITY, nên id giống nhau giữa
các lần chạy) rồi chèn lại. Hệ quả: seed xoá mọi dữ liệu trong DB phát triển, trừ `settings` (cấu
hình, do migration nạp) và `regulation_chunks` (văn bản quy định và vector, nạp ở Giai đoạn 7, tính
lại tốn công). Seed bị chặn khi APP_ENV=production.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, Engine, insert, select, text
from sqlalchemy.exc import ProgrammingError

import app.models  # noqa: F401  (đăng ký mọi model vào Base.metadata)
from app.core.base import Base
from app.core.config import get_settings
from app.core.models import Setting
from app.core.security import hash_password
from data.seed.generate import generate
from data.seed.params import SeedParams
from data.seed.people import DEV_PASSWORD
from data.seed.scenarios import HEAVY_ABSENCE_MIN, LOW_SCORE_BELOW

# Bảng không bị xoá khi seed.
KEPT_TABLES = frozenset({"settings", "regulation_chunks"})
INSERT_CHUNK = 5000


class SeedRefused(RuntimeError):
    """Seed từ chối chạy (đang ở production)."""


class SeedPrerequisiteMissing(RuntimeError):
    """Chưa chạy migration nên thiếu bảng hoặc giá trị mặc định của settings."""


@dataclass(frozen=True)
class SeedSummary:
    row_counts: dict[str, int]
    heavy_absence_students: int  # nghỉ từ 30 buổi
    low_score_students: int  # có ít nhất một đầu điểm dưới 3,5
    boundary_absence_45: int  # đúng 45 buổi nghỉ
    boundary_score_3_5: int  # có môn mà mọi đầu điểm đúng 3,5
    boundary_score_5_0: int  # có môn mà mọi đầu điểm đúng 5,0


def seed_database(engine: Engine, params: SeedParams, *, app_env: str | None = None) -> SeedSummary:
    """Xoá dữ liệu giả cũ, sinh dữ liệu mới theo `params`, nạp vào DB và trả bảng thống kê."""
    environment = app_env if app_env is not None else get_settings().app_env
    if environment == "production":
        raise SeedRefused(
            "Từ chối chạy seed khi APP_ENV=production: dữ liệu giả không vào production."
        )

    try:
        with engine.connect() as conn:
            rules = conn.execute(
                select(Setting.value).where(Setting.key == "regular_assessment_count")
            ).scalar_one_or_none()
    except ProgrammingError as error:  # bảng settings chưa có
        raise SeedPrerequisiteMissing("Chưa có bảng settings. Chạy make migrate trước.") from error
    if rules is None:
        raise SeedPrerequisiteMissing(
            "Không thấy settings.regular_assessment_count. Chạy make migrate trước."
        )

    # Băm một lần dùng chung cho mọi tài khoản (cùng mật khẩu dev): tránh băm hàng chục lần.
    data = generate(params, rules, hash_password(DEV_PASSWORD))

    with engine.begin() as conn:
        _truncate(conn)
        for table_name, rows in data.items():
            table = Base.metadata.tables[table_name]
            for start in range(0, len(rows), INSERT_CHUNK):
                conn.execute(insert(table), rows[start : start + INSERT_CHUNK])
            if rows:
                _advance_sequence(conn, table_name)
        return summarize(conn)


def _truncate(conn: Connection) -> None:
    names = [t.name for t in Base.metadata.sorted_tables if t.name not in KEPT_TABLES]
    if not names:
        raise RuntimeError("Base.metadata rỗng: chưa import app.models.")
    conn.execute(text(f"TRUNCATE TABLE {', '.join(names)} RESTART IDENTITY CASCADE"))


def _advance_sequence(conn: Connection, table_name: str) -> None:
    """Id được gán sẵn khi chèn, nên đưa sequence lên để lần chèn sau không trùng."""
    conn.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"(SELECT max(id) FROM {table_name}))"
        )
    )


def _count(conn: Connection, sql: str, **params: Any) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def _flat_subject_students(conn: Connection, value: Decimal) -> int:
    return _count(
        conn,
        """
        SELECT count(DISTINCT class_student_id) FROM (
            SELECT class_student_id FROM assessments
            WHERE score IS NOT NULL
            GROUP BY class_student_id, subject_id
            HAVING min(score) = :value AND max(score) = :value
        ) AS flat_subjects
        """,
        value=value,
    )


def _absence_students(conn: Connection, *, at_least: int, at_most: int | None = None) -> int:
    upper = "" if at_most is None else " AND count(*) <= :at_most"
    return _count(
        conn,
        f"""
        SELECT count(*) FROM (
            SELECT class_student_id FROM attendance
            WHERE status IN ('absent_excused', 'absent_unexcused')
            GROUP BY class_student_id
            HAVING count(*) >= :at_least{upper}
        ) AS absentees
        """,
        at_least=at_least,
        at_most=at_most,
    )


def summarize(conn: Connection) -> SeedSummary:
    """Bảng thống kê của dữ liệu đang có trong DB (chỉ đếm, không tính điểm trung bình)."""
    counts = {
        table.name: _count(conn, f"SELECT count(*) FROM {table.name}")
        for table in Base.metadata.sorted_tables
    }
    return SeedSummary(
        row_counts=counts,
        heavy_absence_students=_absence_students(conn, at_least=HEAVY_ABSENCE_MIN),
        low_score_students=_count(
            conn,
            "SELECT count(DISTINCT class_student_id) FROM assessments WHERE score < :below",
            below=LOW_SCORE_BELOW,
        ),
        boundary_absence_45=_absence_students(conn, at_least=45, at_most=45),
        boundary_score_3_5=_flat_subject_students(conn, Decimal("3.5")),
        boundary_score_5_0=_flat_subject_students(conn, Decimal("5.0")),
    )


def table_order() -> Sequence[str]:
    """Tên bảng theo thứ tự phụ thuộc (dùng để in thống kê)."""
    return [table.name for table in Base.metadata.sorted_tables]

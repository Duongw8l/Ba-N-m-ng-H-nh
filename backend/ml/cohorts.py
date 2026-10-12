"""Dựng dữ liệu huấn luyện từ nhiều khoá giả lập (D-072).

Mỗi khoá là 360 học sinh sinh bằng chính bộ sinh của seed (`data.seed`) với một số ngẫu nhiên khác
nhau. Các khoá được nạp lần lượt vào MỘT database tạm (tạo rồi xoá, không đụng DB phát triển), rồi
đặc trưng và nhãn được trích bằng đúng mã của sản phẩm:
- đặc trưng: `app.warning.features` (cùng hàm với lúc phục vụ);
- nhãn "kết quả học tập cả năm Chưa đạt": `analytics.service.build_class_results(..., "year")`.
Nhờ vậy nhãn và đặc trưng lúc huấn luyện đi đúng đường tính của sản phẩm.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command
from app.analytics import repository as analytics_repo
from app.analytics import service as analytics_service
from app.analytics.config import load_config
from app.classes.models import SchoolClass
from app.core.config import get_settings
from app.core.enums import LearningLevel
from app.warning import features
from data.seed.load import seed_database
from data.seed.params import SeedParams

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRATCH_DATABASE = "classroom_ml_train"
DEMO_SEED = (
    2026  # seed của DB demo: không dùng để huấn luyện, để học sinh demo là dữ liệu chưa từng thấy
)


def _admin_engine(url: URL) -> Engine:
    return create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
        connect_args={"connect_timeout": 3},
    )


@contextmanager
def scratch_database() -> Iterator[Engine]:
    """Tạo database tạm đã migrate; xoá khi xong (kể cả khi lỗi)."""
    base = make_url(get_settings().database_url)
    url = base.set(database=SCRATCH_DATABASE)
    with _admin_engine(base).connect() as admin:
        admin.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DATABASE}" WITH (FORCE)'))
        admin.execute(text(f'CREATE DATABASE "{SCRATCH_DATABASE}"'))
    engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        with engine.begin() as connection:
            config = Config(str(BACKEND_DIR / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with _admin_engine(base).connect() as admin:
            admin.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DATABASE}" WITH (FORCE)'))


def collect_cohort(engine: Engine, seed: int) -> list[dict[str, Any]]:
    """Nạp một khoá rồi trả về một dòng cho mỗi học sinh: đặc trưng giữa học kỳ I và nhãn cả năm."""
    seed_database(engine, SeedParams(seed=seed))
    rows: list[dict[str, Any]] = []
    with Session(engine) as session:
        config = load_config(session)
        for class_id in session.scalars(select(SchoolClass.id).order_by(SchoolClass.id)):
            class_info = analytics_repo.get_class(session, class_id)
            assert class_info is not None
            ready, cutoff = features.snapshot_ready(session, class_id)
            if not ready:
                raise RuntimeError(
                    f"Khoá {seed}, lớp {class_info.name}: chưa có dữ liệu tới {cutoff}"
                )
            snapshot = features.extract_class(session, class_id, config, cutoff=cutoff)
            year = analytics_service.build_class_results(session, class_info, "year", config)
            for result in year.students:
                cs_id = result.student.class_student_id
                if cs_id not in snapshot or result.learning.level is None:
                    continue  # chưa đủ dữ liệu để có đặc trưng hoặc nhãn
                rows.append(
                    {
                        "cohort": seed,
                        "student_code": result.student.student_code,
                        "grade": class_info.grade_level,
                        **snapshot[cs_id],
                        "label": int(result.learning.level is LearningLevel.FAIL),
                    }
                )
    return rows


def collect(seeds: Sequence[int], *, log: bool = True) -> list[dict[str, Any]]:
    """Dữ liệu của nhiều khoá. Các khoá chạy tuần tự trên cùng một database tạm."""
    if DEMO_SEED in seeds:
        raise ValueError(f"Không dùng seed {DEMO_SEED} (DB demo) để huấn luyện")
    rows: list[dict[str, Any]] = []
    with scratch_database() as engine:
        for index, seed in enumerate(seeds, start=1):
            rows += collect_cohort(engine, seed)
            if log:
                print(
                    f"  khoá {index}/{len(seeds)} (seed {seed}): tổng {len(rows)} học sinh",
                    flush=True,
                )
    return rows

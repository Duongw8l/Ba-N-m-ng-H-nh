"""Base chung của mọi model SQLAlchemy, và các hàm dựng cột dùng lại.

Mỗi module (auth, classes, warning, reports, rag, assistant) khai báo model của mình trong
`models.py` và kế thừa `Base` ở đây; `app/models.py` import tất cả để `Base.metadata` đủ bảng.
"""

from enum import StrEnum
from typing import Annotated

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Tên ràng buộc ổn định để Alembic autogenerate và downgrade chính xác (không dựa vào tên PostgreSQL
# tự đặt). Ràng buộc nhiều cột được đặt tên tường minh trong model nên tên ở đây chỉ là mặc định.
# "ck" dùng constraint_name: mọi CheckConstraint (kể cả Enum) phải có name ngắn, tên đầy đủ là
# ck_<bảng>_<name>.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Khoá chính số nguyên tự tăng (SERIAL; TRUNCATE ... RESTART IDENTITY đặt lại được).
IntPk = Annotated[int, mapped_column(primary_key=True)]


def enum_type(enum_cls: type[StrEnum], name: str) -> Enum:
    """Cột liệt kê: VARCHAR + CHECK (IN ...), không dùng enum gốc của PostgreSQL (D-025).

    Lưu giá trị (`member.value`) chứ không lưu tên thành viên. `name` là tên ngắn của ràng buộc
    CHECK, ví dụ name="status" ở bảng attendance cho ra ck_attendance_status.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum_cls),
        values_callable=lambda cls: [member.value for member in cls],
    )

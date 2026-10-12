"""Mẫu ánh xạ cột đã lưu của từng người dùng (D-062)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import ImportKind
from app.imports.models import ImportMapping


def get_template(
    session: Session, user_id: int, kind: ImportKind, name: str
) -> ImportMapping | None:
    return session.scalar(
        select(ImportMapping).where(
            ImportMapping.user_id == user_id,
            ImportMapping.kind == kind,
            ImportMapping.name == name,
        )
    )


def list_templates(
    session: Session, user_id: int, kind: ImportKind | None = None
) -> list[ImportMapping]:
    query = select(ImportMapping).where(ImportMapping.user_id == user_id)
    if kind is not None:
        query = query.where(ImportMapping.kind == kind)
    return list(session.scalars(query.order_by(ImportMapping.kind, ImportMapping.name)))


def save_template(
    session: Session,
    user_id: int,
    kind: ImportKind,
    name: str,
    mapping: dict[str, Any],
    header_row: int | None,
) -> None:
    """Tạo mẫu, hoặc ghi đè mẫu cùng tên của chính người dùng này."""
    statement = insert(ImportMapping).values(
        user_id=user_id, kind=kind, name=name, mapping=mapping, header_row=header_row
    )
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_import_mappings_user_kind_name",
            set_={"mapping": mapping, "header_row": header_row, "updated_at": func.now()},
        )
    )

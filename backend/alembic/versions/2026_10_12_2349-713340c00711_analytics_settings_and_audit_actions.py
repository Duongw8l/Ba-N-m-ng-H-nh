"""analytics settings and audit actions: khoá điều chỉnh mức và hai hành động nhật ký mới

Revision ID: 713340c00711
Revises: 4d0c452b2002
Create Date: 2026-10-12 23:49:00.000000

Giai đoạn 3:
- Khoá settings `level_single_subject_adjustment` (Điều 9 Thông tư 22: nâng 1 mức khi mức học tập
  bị thấp hơn từ 2 mức chỉ do duy nhất 1 môn). Mặc định bật; tắt được nếu cách hiểu khác.
- CHECK của audit_logs.action thêm `view_class_dashboard` và `view_subject_scores`.

Tên ràng buộc đi qua op.f() vì naming_convention của Base.metadata có token %(constraint_name)s
(nếu không sẽ bị thêm tiền tố lần thứ hai).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "713340c00711"
down_revision: str | Sequence[str] | None = "4d0c452b2002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADJUSTMENT_KEY = "level_single_subject_adjustment"
ADJUSTMENT_DESCRIPTION = (
    "Bật (true) thì mức học tập bị thấp hơn từ 2 mức trở lên so với Tốt hoặc Khá chỉ do duy nhất "
    "1 môn được nâng lên 1 mức (Điều 9 Thông tư 22)."
)

OLD_ACTIONS = ("view_class_students", "view_student_profile")
NEW_ACTIONS = ("view_class_dashboard", "view_subject_scores")

settings_table = sa.table(
    "settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
    sa.column("description", sa.Text),
)


def _replace_action_check(actions: Sequence[str]) -> None:
    values = ", ".join(f"'{action}'" for action in actions)
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({values})")


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        settings_table,
        [{"key": ADJUSTMENT_KEY, "value": True, "description": ADJUSTMENT_DESCRIPTION}],
    )
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))


def downgrade() -> None:
    """Downgrade schema. Xoá các dòng nhật ký dùng hành động mới để khôi phục được CHECK cũ."""
    audit_logs = sa.table("audit_logs", sa.column("action", sa.String))
    op.execute(audit_logs.delete().where(audit_logs.c.action.in_(NEW_ACTIONS)))
    _replace_action_check(OLD_ACTIONS)
    op.execute(settings_table.delete().where(settings_table.c.key == ADJUSTMENT_KEY))

"""alerts audit actions and latest index: nhật ký cảnh báo sớm, chỉ mục dòng mới nhất

Revision ID: e04f0ffe691c
Revises: 2e5c2711795f
Create Date: 2026-10-13 04:17:00.000000

Giai đoạn 6 (cảnh báo sớm):
- CHECK của audit_logs.action thêm view_class_alerts, view_school_alerts, update_alert (cách làm
  như migration trước, tên đi qua op.f).
- Chỉ mục (class_student_id, id) trên risk_alerts cho truy vấn "dòng mới nhất của từng học sinh".
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e04f0ffe691c"
down_revision: str | Sequence[str] | None = "2e5c2711795f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIONS = (
    "view_class_students",
    "view_student_profile",
    "view_class_dashboard",
    "view_subject_scores",
    "import_confirm",
)
NEW_ACTIONS = ("view_class_alerts", "view_school_alerts", "update_alert")


def _replace_action_check(actions: Sequence[str]) -> None:
    values = ", ".join(f"'{action}'" for action in actions)
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({values})")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_risk_alerts_cs_latest", "risk_alerts", ["class_student_id", "id"], unique=False
    )
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))


def downgrade() -> None:
    """Downgrade schema. Xoá các dòng nhật ký dùng hành động mới để khôi phục được CHECK cũ."""
    audit_logs = sa.table("audit_logs", sa.column("action", sa.String))
    op.execute(audit_logs.delete().where(audit_logs.c.action.in_(NEW_ACTIONS)))
    _replace_action_check(OLD_ACTIONS)
    op.drop_index("ix_risk_alerts_cs_latest", table_name="risk_alerts")

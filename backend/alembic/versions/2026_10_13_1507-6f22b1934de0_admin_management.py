"""admin management: tài khoản bị khoá, hành động quản trị, loại nhập danh sách học sinh

Revision ID: 6f22b1934de0
Revises: 0ad44950fb6b
Create Date: 2026-10-13 15:07:10.758328

Chức năng Admin (D-096 đến D-101):
- users.is_active: tài khoản bị khoá không đăng nhập được, token cũ bị từ chối (không xoá tài khoản
  vì điểm, nhật ký, phân công còn tham chiếu tới người dùng). Mặc định true cho mọi dòng có sẵn.
- CHECK của audit_logs.action thêm các hành động quản trị. Độ dài lớn nhất vẫn là 20 ký tự nên
  không phải đổi kiểu cột.
- CHECK `kind` của import_jobs và import_mappings thêm 'roster' (nhập danh sách học sinh).
- Hạ cấp xoá các dòng dùng giá trị mới (nhật ký quản trị, job và mẫu ánh xạ roster) trước khi đặt
  lại CHECK cũ, vì nếu không CHECK cũ không thể tạo lại.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f22b1934de0"
down_revision: str | Sequence[str] | None = "0ad44950fb6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIONS = (
    "view_class_students",
    "view_student_profile",
    "view_class_dashboard",
    "view_subject_scores",
    "import_confirm",
    "view_class_alerts",
    "view_school_alerts",
    "update_alert",
    "upload_regulation",
    "update_regulation",
)
NEW_ACTIONS = (
    "create_user",
    "update_user",
    "reset_user_password",
    "change_password",
    "update_school_year",
    "create_class",
    "update_class",
    "delete_class",
    "set_assignment",
    "remove_assignment",
    "remove_class_student",
)
OLD_KINDS = ("assessments", "attendance", "conduct")
NEW_KINDS = (*OLD_KINDS, "roster")
KIND_TABLES = ("import_jobs", "import_mappings")


def _quote(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_action_check(actions: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({_quote(actions)})"
    )


def _replace_kind_check(table: str, kinds: Sequence[str]) -> None:
    name = op.f(f"ck_{table}_kind")
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, f"kind IN ({_quote(kinds)})")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))
    for table in KIND_TABLES:
        _replace_kind_check(table, NEW_KINDS)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DELETE FROM audit_logs WHERE action IN ({_quote(NEW_ACTIONS)})")
    _replace_action_check(OLD_ACTIONS)
    for table in KIND_TABLES:
        op.execute(f"DELETE FROM {table} WHERE kind = 'roster'")
        _replace_kind_check(table, OLD_KINDS)
    op.drop_column("users", "is_active")

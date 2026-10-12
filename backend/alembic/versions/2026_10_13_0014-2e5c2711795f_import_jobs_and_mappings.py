"""import jobs and mappings: bảng xem trước nhập tệp, mẫu ánh xạ cột, hành động nhật ký mới

Revision ID: 2e5c2711795f
Revises: 713340c00711
Create Date: 2026-10-13 00:14:19.089099

Giai đoạn 4 (nhập Excel/CSV):
- import_jobs: bản xem trước chờ xác nhận, chỉ lưu giá trị đã chuẩn hoá (không lưu tệp gốc, không
  lưu họ tên). id là UUID ngẫu nhiên vì nằm trong URL.
- import_mappings: mẫu ánh xạ cột của từng người dùng.
- CHECK của audit_logs.action thêm `import_confirm` (cách làm như migration trước, tên đi qua op.f).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e5c2711795f"
down_revision: str | Sequence[str] | None = "713340c00711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIONS = (
    "view_class_students",
    "view_student_profile",
    "view_class_dashboard",
    "view_subject_scores",
)
NEW_ACTIONS = ("import_confirm",)


def _kind() -> sa.Enum:
    return sa.Enum(
        "assessments",
        "attendance",
        "conduct",
        name="kind",
        native_enum=False,
        create_constraint=True,
    )


def _replace_action_check(actions: Sequence[str]) -> None:
    values = ", ".join(f"'{action}'" for action in actions)
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({values})")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "import_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", _kind(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("header_row", sa.SmallInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_import_mappings_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_mappings")),
        sa.UniqueConstraint("user_id", "kind", "name", name="uq_import_mappings_user_kind_name"),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("kind", _kind(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("semester", sa.SmallInteger(), nullable=True),
        sa.Column(
            "period",
            sa.Enum("hk1", "hk2", "year", name="period", native_enum=False, create_constraint=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "previewed", "confirmed", name="status", native_enum=False, create_constraint=True
            ),
            server_default="previewed",
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rows", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "semester IS NULL OR semester IN (1, 2)", name=op.f("ck_import_jobs_semester")
        ),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], name=op.f("fk_import_jobs_class_id_classes")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_import_jobs_subject_id_subjects")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_import_jobs_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )
    op.create_index("ix_import_jobs_expires_at", "import_jobs", ["expires_at"], unique=False)
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"], unique=False)
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))


def downgrade() -> None:
    """Downgrade schema. Xoá các dòng nhật ký dùng hành động mới để khôi phục được CHECK cũ."""
    audit_logs = sa.table("audit_logs", sa.column("action", sa.String))
    op.execute(audit_logs.delete().where(audit_logs.c.action.in_(NEW_ACTIONS)))
    _replace_action_check(OLD_ACTIONS)
    op.drop_table("import_jobs")
    op.drop_table("import_mappings")

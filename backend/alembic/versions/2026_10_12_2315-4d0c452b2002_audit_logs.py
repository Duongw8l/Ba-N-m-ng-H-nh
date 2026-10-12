"""audit logs: bảng nhật ký truy cập dữ liệu học sinh

Revision ID: 4d0c452b2002
Revises: 83cbfcae5ae4
Create Date: 2026-10-12 23:15:02.000000

Bảng thứ 16 ngoài 15 bảng của DESIGN mục 5 và bảng settings, do Giai đoạn 2 yêu cầu (nhật ký mỗi
lần mở hồ sơ học sinh, DESIGN mục 10). `class_id` không có khoá ngoại để nhật ký còn lại khi lớp
bị xoá.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d0c452b2002"
down_revision: str | Sequence[str] | None = "83cbfcae5ae4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "view_class_students",
                "view_student_profile",
                name="action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_class_id", "audit_logs", ["class_id"], unique=False)
    op.create_index(
        "ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema. Index đi cùng bảng."""
    op.drop_table("audit_logs")

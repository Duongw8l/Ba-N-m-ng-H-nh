"""reports generation: cột mới cho reports, bảng report_jobs, hành động nhật ký

Revision ID: 664e18a9fcd3
Revises: 6f22b1934de0
Create Date: 2026-10-13 17:53:41.114832

Giai đoạn 9, nhận xét và báo cáo (D-102 trở đi):
- reports: thêm lớp, môn, học kỳ, người tạo, kết quả kiểm tự động (needs_manual, check_notes,
  attempts), mô hình và phiên bản lời nhắc, thời điểm tạo / sửa / duyệt. Bảng chưa từng có dòng nào
  (trước đây không có đường nào ghi vào) nên các cột NOT NULL không cần giá trị cũ; nếu có dòng lạ
  thì migration dừng với lỗi thay vì tự bịa dữ liệu.
- reports.type thêm 'subject_comment' (15 ký tự, rộng hơn cột VARCHAR(13) cũ).
- Một bản cho mỗi khoá: hai chỉ mục duy nhất một phần (subject_id NULL / không NULL).
- report_jobs: tiến độ sinh nhận xét cả lớp chạy nền.
- CHECK của audit_logs.action thêm 5 hành động. Độ dài lớn nhất vẫn là 20 ký tự.
- Hạ cấp xoá các dòng dùng giá trị mới (nhận xét môn, nhật ký) trước khi đặt lại CHECK cũ.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "664e18a9fcd3"
down_revision: str | Sequence[str] | None = "6f22b1934de0"
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
NEW_ACTIONS = (
    "generate_report",
    "edit_report",
    "approve_report",
    "export_report",
    "view_class_reports",
)
OLD_TYPES = ("school_record", "contact_slip", "report")
NEW_TYPES = ("subject_comment", *OLD_TYPES)

REPORT_COLUMNS = (
    "approved_at",
    "class_id",
    "subject_id",
    "semester",
    "created_by",
    "needs_manual",
    "check_notes",
    "attempts",
    "model",
    "prompt_version",
    "created_at",
    "updated_at",
)


def _quote(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_action_check(actions: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({_quote(actions)})"
    )


def _replace_type_check(types: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_reports_type"), "reports", type_="check")
    op.create_check_constraint(op.f("ck_reports_type"), "reports", f"type IN ({_quote(types)})")


def upgrade() -> None:
    """Upgrade schema."""
    # --- reports ---
    op.alter_column(
        "reports",
        "type",
        existing_type=sa.String(length=13),
        type_=sa.String(length=15),
        existing_nullable=False,
    )
    _replace_type_check(NEW_TYPES)
    op.add_column("reports", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column("class_id", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("subject_id", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("semester", sa.String(length=4), nullable=False))
    op.add_column("reports", sa.Column("created_by", sa.Integer(), nullable=False))
    op.add_column(
        "reports",
        sa.Column("needs_manual", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "reports",
        sa.Column(
            "check_notes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "reports",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("reports", sa.Column("model", sa.String(length=100), nullable=True))
    op.add_column("reports", sa.Column("prompt_version", sa.String(length=20), nullable=True))
    op.add_column(
        "reports",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_reports_class_id_classes"), "reports", "classes", ["class_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("fk_reports_subject_id_subjects"), "reports", "subjects", ["subject_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("fk_reports_created_by_users"), "reports", "users", ["created_by"], ["id"]
    )
    op.create_check_constraint(
        op.f("ck_reports_semester"), "reports", "semester IN ('1', '2', 'year')"
    )
    op.create_check_constraint(
        op.f("ck_reports_manual_is_draft"), "reports", "NOT needs_manual OR status = 'draft'"
    )
    op.create_index(
        "uq_reports_key",
        "reports",
        ["type", "scope", "target_id", "semester"],
        unique=True,
        postgresql_where=sa.text("subject_id IS NULL"),
    )
    op.create_index(
        "uq_reports_key_subject",
        "reports",
        ["type", "scope", "target_id", "semester", "subject_id"],
        unique=True,
        postgresql_where=sa.text("subject_id IS NOT NULL"),
    )

    # --- report_jobs ---
    op.create_table(
        "report_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                *NEW_TYPES,
                name="type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("semester", sa.String(length=4), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "done",
                "stopped",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="running",
            nullable=False,
        ),
        sa.Column("total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("done", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("needs_manual", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("semester IN ('1', '2', 'year')", name=op.f("ck_report_jobs_semester")),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], name=op.f("fk_report_jobs_class_id_classes")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_report_jobs_subject_id_subjects")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_report_jobs_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_jobs")),
    )

    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DELETE FROM audit_logs WHERE action IN ({_quote(NEW_ACTIONS)})")
    _replace_action_check(OLD_ACTIONS)

    op.drop_table("report_jobs")

    op.drop_index("uq_reports_key_subject", table_name="reports")
    op.drop_index("uq_reports_key", table_name="reports")
    op.drop_constraint(op.f("ck_reports_manual_is_draft"), "reports", type_="check")
    op.drop_constraint(op.f("ck_reports_semester"), "reports", type_="check")
    op.drop_constraint(op.f("fk_reports_created_by_users"), "reports", type_="foreignkey")
    op.drop_constraint(op.f("fk_reports_subject_id_subjects"), "reports", type_="foreignkey")
    op.drop_constraint(op.f("fk_reports_class_id_classes"), "reports", type_="foreignkey")
    for column in reversed(REPORT_COLUMNS):
        op.drop_column("reports", column)
    op.execute("DELETE FROM reports WHERE type = 'subject_comment'")
    _replace_type_check(OLD_TYPES)
    op.alter_column(
        "reports",
        "type",
        existing_type=sa.String(length=15),
        type_=sa.String(length=13),
        existing_nullable=False,
    )

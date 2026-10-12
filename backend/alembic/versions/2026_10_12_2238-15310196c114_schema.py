"""schema: extension vector, 15 bảng nghiệp vụ và bảng settings

Revision ID: 15310196c114
Revises:
Create Date: 2026-10-12 22:38:59.703986

Sinh bằng autogenerate rồi sửa tay: thêm CREATE EXTENSION, lấy số chiều vector từ cấu hình.
Tên ràng buộc CHECK của cột liệt kê (sa.Enum ... create_constraint) được đặt theo
naming_convention của Base.metadata (ck_<bảng>_<name>), nên env.py phải đặt target_metadata.

downgrade() không DROP EXTENSION vector: không biết extension do migration này tạo hay có sẵn,
để lại vô hại.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "15310196c114"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )
    op.create_table(
        "regulation_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_name", sa.String(length=200), nullable=False),
        sa.Column("article", sa.String(length=100), nullable=True),
        sa.Column("clause", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        # Số chiều lấy từ cấu hình (EMBEDDING_DIM) lúc chạy migration và cố định vào cột.
        sa.Column("embedding", Vector(get_settings().embedding_dim), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regulation_chunks")),
    )
    op.create_table(
        "school_years",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.CheckConstraint("start_date < end_date", name=op.f("ck_school_years_dates_order")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school_years")),
        sa.UniqueConstraint("name", name=op.f("uq_school_years_name")),
    )
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_code", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("guardian_name", sa.String(length=100), nullable=True),
        sa.Column("guardian_phone", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("student_code", name=op.f("uq_students_student_code")),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "assessment_type",
            sa.Enum(
                "score",
                "comment",
                name="assessment_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("periods_per_year", sa.SmallInteger(), nullable=False),
        sa.Column("is_elective", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint("periods_per_year > 0", name=op.f("ck_subjects_periods_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("name", name=op.f("uq_subjects_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "teacher",
                "principal",
                "admin",
                name="role",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "ai_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "tools_called",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_ai_logs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_logs")),
    )
    op.create_index(op.f("ix_ai_logs_user_id"), "ai_logs", ["user_id"], unique=False)
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_year_id", sa.Integer(), nullable=False),
        sa.Column("grade_level", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("homeroom_teacher_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("grade_level IN (10, 11, 12)", name=op.f("ck_classes_grade_level")),
        sa.ForeignKeyConstraint(
            ["homeroom_teacher_id"], ["users.id"], name=op.f("fk_classes_homeroom_teacher_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["school_year_id"],
            ["school_years.id"],
            name=op.f("fk_classes_school_year_id_school_years"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classes")),
        sa.UniqueConstraint(
            "school_year_id", "homeroom_teacher_id", name="uq_classes_year_homeroom_teacher"
        ),
        sa.UniqueConstraint("school_year_id", "name", name="uq_classes_year_name"),
    )
    op.create_index(
        "ix_classes_year_grade", "classes", ["school_year_id", "grade_level"], unique=False
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "student", "class", "grade", name="scope", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "school_record",
                "contact_slip",
                "report",
                name="type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "approved", name="status", native_enum=False, create_constraint=True),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status <> 'approved' OR approved_by IS NOT NULL",
            name=op.f("ck_reports_approved_has_approver"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_reports_approved_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index("ix_reports_scope_target", "reports", ["scope", "target_id"], unique=False)
    op.create_table(
        "class_students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], name=op.f("fk_class_students_class_id_classes")
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_class_students_student_id_students")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_students")),
        sa.UniqueConstraint("class_id", "student_id", name="uq_class_students_pair"),
    )
    op.create_index(
        op.f("ix_class_students_student_id"), "class_students", ["student_id"], unique=False
    )
    op.create_table(
        "teaching_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], name=op.f("fk_teaching_assignments_class_id_classes")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_teaching_assignments_subject_id_subjects"),
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["users.id"], name=op.f("fk_teaching_assignments_teacher_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teaching_assignments")),
        sa.UniqueConstraint("class_id", "subject_id", name="uq_teaching_assignments_class_subject"),
    )
    op.create_index(
        op.f("ix_teaching_assignments_teacher_id"),
        "teaching_assignments",
        ["teacher_id"],
        unique=False,
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_student_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("semester", sa.SmallInteger(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("tx", "gk", "ck", name="kind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("seq", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column(
            "comment_result",
            sa.Enum(
                "pass", "fail", name="comment_result", native_enum=False, create_constraint=True
            ),
            nullable=True,
        ),
        sa.CheckConstraint("kind = 'tx' OR seq = 1", name=op.f("ck_assessments_seq_one_unless_tx")),
        sa.CheckConstraint(
            "(score IS NULL) <> (comment_result IS NULL)",
            name=op.f("ck_assessments_score_xor_comment"),
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 10)",
            name=op.f("ck_assessments_score_range"),
        ),
        sa.CheckConstraint("semester IN (1, 2)", name=op.f("ck_assessments_semester")),
        sa.CheckConstraint("seq >= 1", name=op.f("ck_assessments_seq_positive")),
        sa.ForeignKeyConstraint(
            ["class_student_id"],
            ["class_students.id"],
            name=op.f("fk_assessments_class_student_id_class_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_assessments_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
        sa.UniqueConstraint(
            "class_student_id",
            "subject_id",
            "semester",
            "kind",
            "seq",
            name="uq_assessments_cs_subject_sem_kind_seq",
        ),
    )
    op.create_index(
        "ix_assessments_subject_semester", "assessments", ["subject_id", "semester"], unique=False
    )
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_student_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "present",
                "absent_excused",
                "absent_unexcused",
                "late",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["class_student_id"],
            ["class_students.id"],
            name=op.f("fk_attendance_class_student_id_class_students"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance")),
        sa.UniqueConstraint("class_student_id", "date", name="uq_attendance_cs_date"),
    )
    op.create_index("ix_attendance_date", "attendance", ["date"], unique=False)
    op.create_table(
        "conduct_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_student_id", sa.Integer(), nullable=False),
        sa.Column(
            "period",
            sa.Enum("hk1", "hk2", "year", name="period", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "level",
            sa.Enum(
                "good",
                "fair",
                "pass",
                "fail",
                name="level",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["class_student_id"],
            ["class_students.id"],
            name=op.f("fk_conduct_results_class_student_id_class_students"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conduct_results")),
        sa.UniqueConstraint("class_student_id", "period", name="uq_conduct_results_cs_period"),
    )
    op.create_table(
        "exam_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_student_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_student_id"],
            ["class_students.id"],
            name=op.f("fk_exam_registrations_class_student_id_class_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_exam_registrations_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_registrations")),
        sa.UniqueConstraint(
            "class_student_id", "subject_id", name="uq_exam_registrations_cs_subject"
        ),
    )
    op.create_table(
        "risk_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_student_id", sa.Integer(), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "high", "medium", "low", name="level", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "teacher_status",
            sa.Enum(
                "new",
                "contacted",
                "false_alarm",
                name="teacher_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="new",
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
            name=op.f("ck_risk_alerts_risk_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["class_student_id"],
            ["class_students.id"],
            name=op.f("fk_risk_alerts_class_student_id_class_students"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_alerts")),
    )
    op.create_index(
        op.f("ix_risk_alerts_class_student_id"), "risk_alerts", ["class_student_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema. Xoá bảng theo thứ tự ngược phụ thuộc (index đi cùng bảng)."""
    for table in (
        "risk_alerts",
        "exam_registrations",
        "conduct_results",
        "attendance",
        "assessments",
        "teaching_assignments",
        "class_students",
        "reports",
        "classes",
        "ai_logs",
        "users",
        "subjects",
        "students",
        "school_years",
        "regulation_chunks",
        "settings",
    ):
        op.drop_table(table)

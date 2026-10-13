"""regulation documents: văn bản quy định cho RAG, chỉ mục HNSW, ngưỡng tìm kiếm, nhật ký Admin

Revision ID: f1f878eee239
Revises: e04f0ffe691c
Create Date: 2026-10-13 05:16:13.200223

Giai đoạn 7 (RAG văn bản quy định, D-076):
- regulation_documents: một dòng mỗi văn bản (tên, tệp, hiệu lực). `uploaded_by` cố ý KHÔNG có khoá
  ngoại tới users: make seed chạy TRUNCATE users ... CASCADE, khoá ngoại sẽ xoá luôn văn bản đã nạp.
  Chỉ mục duy nhất từng phần: mỗi tên chỉ có một bản còn hiệu lực.
- regulation_chunks.document_id (bắt buộc, ON DELETE CASCADE) và chỉ mục HNSW cosine trên embedding.
  Dòng chunk có sẵn (nếu có) được gom theo document_name thành các văn bản còn hiệu lực.
- Khoá settings `rag_min_similarity`: dưới ngưỡng này thì trả "không tìm thấy" thay vì đoán.
- CHECK của audit_logs.action thêm upload_regulation, update_regulation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1f878eee239"
down_revision: str | Sequence[str] | None = "e04f0ffe691c"
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
)
NEW_ACTIONS = ("upload_regulation", "update_regulation")

SIMILARITY_KEY = "rag_min_similarity"
# Điểm khởi đầu, đo bằng bge-m3 trên văn bản mẫu giả (data/regulations/) với một bộ 30 câu tạm: 16
# câu trong phạm vi có độ tương đồng top-1 từ 0,582 tới 0,751, 14 câu ngoài phạm vi từ 0,259 tới
# 0,545. Bộ 30 câu đó không được lưu lại nên chưa tái lập được. Bộ eval/rag_questions.json (đo sau,
# không dùng để chọn ngưỡng) cho thấy hai nhóm CHỒNG NHAU: câu trong phạm vi thấp nhất 0,520, câu
# ngoài phạm vi cao nhất 0,568. Không có ngưỡng nào tách sạch; phải đo lại khi nạp văn bản thật
# (xem D-082, Giai đoạn 10).
SIMILARITY_VALUE = 0.56
SIMILARITY_DESCRIPTION = (
    "Độ tương đồng cosine tối thiểu (0 đến 1) để một đoạn văn bản quy định được coi là liên quan. "
    "Đoạn tốt nhất dưới mức này thì RAG trả 'không tìm thấy trong văn bản quy định'. Phụ thuộc mô "
    "hình embedding; hiệu chỉnh lại khi đổi mô hình hoặc nạp văn bản thật."
)

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
    op.create_table(
        "regulation_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "expired", name="status", native_enum=False, create_constraint=True),
            server_default="active",
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regulation_documents")),
    )
    op.create_index(
        "uq_regulation_documents_active_name",
        "regulation_documents",
        ["name"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column("regulation_chunks", sa.Column("document_id", sa.Integer(), nullable=True))
    op.execute(
        "INSERT INTO regulation_documents (name, file_name, status) "
        "SELECT DISTINCT document_name, 'không rõ (có trước Giai đoạn 7)', 'active' "
        "FROM regulation_chunks"
    )
    op.execute(
        "UPDATE regulation_chunks c SET document_id = d.id "
        "FROM regulation_documents d WHERE d.name = c.document_name"
    )
    op.alter_column("regulation_chunks", "document_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_regulation_chunks_document_id_regulation_documents"),
        "regulation_chunks",
        "regulation_documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_regulation_chunks_document_id"), "regulation_chunks", ["document_id"], unique=False
    )
    op.create_index(
        "ix_regulation_chunks_embedding",
        "regulation_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.bulk_insert(
        settings_table,
        [{"key": SIMILARITY_KEY, "value": SIMILARITY_VALUE, "description": SIMILARITY_DESCRIPTION}],
    )
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))


def downgrade() -> None:
    """Downgrade schema. Xoá các dòng nhật ký dùng hành động mới để khôi phục được CHECK cũ."""
    audit_logs = sa.table("audit_logs", sa.column("action", sa.String))
    op.execute(audit_logs.delete().where(audit_logs.c.action.in_(NEW_ACTIONS)))
    _replace_action_check(OLD_ACTIONS)
    op.execute(settings_table.delete().where(settings_table.c.key == SIMILARITY_KEY))

    op.drop_index(
        "ix_regulation_chunks_embedding",
        table_name="regulation_chunks",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_regulation_chunks_document_id"), table_name="regulation_chunks")
    op.drop_constraint(
        op.f("fk_regulation_chunks_document_id_regulation_documents"),
        "regulation_chunks",
        type_="foreignkey",
    )
    op.drop_column("regulation_chunks", "document_id")
    op.drop_index(
        "uq_regulation_documents_active_name",
        table_name="regulation_documents",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_table("regulation_documents")

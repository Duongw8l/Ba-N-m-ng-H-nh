"""ai_logs: thời điểm, mô hình, phiên bản prompt, số vòng, lỗi, phản hồi đúng/sai

Revision ID: 0ad44950fb6b
Revises: f1f878eee239
Create Date: 2026-10-13 11:15:18.965959

Giai đoạn 8 (Trợ lý AI, D-091):
- ai_logs.created_at: bắt buộc cho giới hạn "số câu hỏi mỗi phút" (đếm dòng của tài khoản trong
  60 giây gần nhất) và cho việc truy vết (D-035 đã hẹn thêm cột này ở Giai đoạn 8).
- model, prompt_version, rounds, error: để biết câu trả lời do mô hình nào, prompt phiên bản nào,
  mất mấy vòng gọi hàm, hay lỗi gì khi gọi LLM.
- feedback: từ TEXT tự do thành VARCHAR + CHECK ('correct', 'incorrect'). Alembic không tự tạo
  CHECK khi đổi kiểu sang Enum không gốc, nên tạo tường minh. Giá trị lạ (nếu có) được xoá trước.
- Chỉ mục (user_id, created_at) thay cho chỉ mục user_id (đủ cho cả truy vấn theo user_id).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0ad44950fb6b"
down_revision: str | Sequence[str] | None = "f1f878eee239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEEDBACK_VALUES = ("correct", "incorrect")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ai_logs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column("ai_logs", sa.Column("model", sa.String(length=100), nullable=True))
    op.add_column("ai_logs", sa.Column("prompt_version", sa.String(length=20), nullable=True))
    op.add_column("ai_logs", sa.Column("rounds", sa.Integer(), nullable=True))
    op.add_column("ai_logs", sa.Column("error", sa.Text(), nullable=True))

    values = ", ".join(f"'{value}'" for value in FEEDBACK_VALUES)
    op.execute(f"UPDATE ai_logs SET feedback = NULL WHERE feedback NOT IN ({values})")
    op.alter_column(
        "ai_logs",
        "feedback",
        existing_type=sa.TEXT(),
        type_=sa.String(length=9),
        existing_nullable=True,
    )
    op.create_check_constraint(op.f("ck_ai_logs_feedback"), "ai_logs", f"feedback IN ({values})")

    op.drop_index(op.f("ix_ai_logs_user_id"), table_name="ai_logs")
    op.create_index("ix_ai_logs_user_created", "ai_logs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ai_logs_user_created", table_name="ai_logs")
    op.create_index(op.f("ix_ai_logs_user_id"), "ai_logs", ["user_id"], unique=False)

    op.drop_constraint(op.f("ck_ai_logs_feedback"), "ai_logs", type_="check")
    op.alter_column(
        "ai_logs",
        "feedback",
        existing_type=sa.String(length=9),
        type_=sa.TEXT(),
        existing_nullable=True,
    )

    op.drop_column("ai_logs", "error")
    op.drop_column("ai_logs", "rounds")
    op.drop_column("ai_logs", "prompt_version")
    op.drop_column("ai_logs", "model")
    op.drop_column("ai_logs", "created_at")

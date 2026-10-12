"""default settings: giá trị mặc định của bảng settings

Revision ID: c037f9f86a54
Revises: 15310196c114
Create Date: 2026-10-12 22:39:52.271879

Nạp trong migration (không trong seed) vì seed bị chặn ở production mà production vẫn cần hệ số và
ngưỡng. Chỉ lưu GIÁ TRỊ; công thức Thông tư 22 nằm trong backend/app/analytics/ (nguyên tắc 2).
Số đọc ra bằng Decimal(str(giá trị)). Migration chạy một lần, nên giá trị admin sửa về sau không
bị ghi đè.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c037f9f86a54"
down_revision: str | Sequence[str] | None = "15310196c114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, value, description). max_periods là ngưỡng bao gồm: ≤35 tiết → 2, trên 35 đến 70 → 3,
# trên 70 → 4 (DESIGN mục 5); null là không giới hạn trên.
DEFAULT_SETTINGS: list[tuple[str, object, str]] = [
    ("coef_midterm", 2, "Hệ số của điểm đánh giá giữa kỳ khi tính điểm trung bình môn học kỳ."),
    ("coef_final", 3, "Hệ số của điểm đánh giá cuối kỳ khi tính điểm trung bình môn học kỳ."),
    (
        "coef_year_semester2",
        2,
        "Hệ số của điểm trung bình môn học kỳ II khi tính điểm trung bình môn cả năm.",
    ),
    (
        "max_absent_sessions",
        45,
        "Số buổi nghỉ tối đa trong năm học (có phép và không phép); nghỉ quá mức này thì không "
        "đủ điều kiện lên lớp.",
    ),
    ("absent_warning_notice", 30, "Từ số buổi nghỉ này hệ thống bắt đầu nhắc (mức thấp)."),
    ("absent_warning_high", 40, "Từ số buổi nghỉ này hệ thống cảnh báo mức cao."),
    ("score_threshold_fail", 3.5, "Mốc điểm môn thấp nhất: môn dưới mốc này bị cảnh báo."),
    ("score_threshold_pass", 5.0, "Mốc điểm môn đạt."),
    ("score_threshold_fair", 6.5, "Mốc điểm môn dùng xét mức học tập (Giai đoạn 3 gắn với mức)."),
    ("score_threshold_good", 8.0, "Mốc điểm môn dùng xét mức học tập (Giai đoạn 3 gắn với mức)."),
    ("level_min_subjects", 6, "Số môn tối thiểu đạt mốc điểm khi xét mức học tập."),
    (
        "regular_assessment_count",
        [
            {"max_periods": 35, "count": 2},
            {"max_periods": 70, "count": 3},
            {"max_periods": None, "count": 4},
        ],
        "Số lần đánh giá thường xuyên mỗi học kỳ theo số tiết/năm của môn. max_periods là ngưỡng "
        "bao gồm; null là không giới hạn trên.",
    ),
]

settings_table = sa.table(
    "settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        settings_table,
        [
            {"key": key, "value": value, "description": desc}
            for key, value, desc in DEFAULT_SETTINGS
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    keys = [key for key, _value, _desc in DEFAULT_SETTINGS]
    op.execute(settings_table.delete().where(settings_table.c.key.in_(keys)))

"""view subject average: khung view v_subject_average

Revision ID: 83cbfcae5ae4
Revises: c037f9f86a54
Create Date: 2026-10-12 22:40:53.871973

Đây là KHUNG gom dữ liệu, cố ý không có công thức và không có hệ số (D-026): mỗi dòng ứng với
(học sinh trong lớp, môn, học kỳ) với số lần và tổng điểm thường xuyên, điểm giữa kỳ, điểm cuối kỳ
và kết quả nhận xét. Chỉ có COUNT, SUM và lọc theo kind; không chia, không nhân hệ số.
Công thức điểm trung bình môn của Thông tư 22 chỉ nằm trong backend/app/analytics/ (Giai đoạn 3),
đọc hệ số từ bảng settings. Tên view giữ theo DESIGN mục 5.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83cbfcae5ae4"
down_revision: str | Sequence[str] | None = "c037f9f86a54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_VIEW = """
CREATE VIEW v_subject_average AS
SELECT
    a.class_student_id,
    cs.class_id,
    cs.student_id,
    a.subject_id,
    s.assessment_type,
    s.periods_per_year,
    a.semester,
    COUNT(*) FILTER (WHERE a.kind = 'tx') AS tx_count,
    COALESCE(SUM(a.score) FILTER (WHERE a.kind = 'tx'), 0) AS tx_sum,
    MAX(a.score) FILTER (WHERE a.kind = 'gk') AS gk_score,
    MAX(a.score) FILTER (WHERE a.kind = 'ck') AS ck_score,
    MAX(a.comment_result) AS comment_result
FROM assessments a
JOIN class_students cs ON cs.id = a.class_student_id
JOIN subjects s ON s.id = a.subject_id
GROUP BY
    a.class_student_id,
    cs.class_id,
    cs.student_id,
    a.subject_id,
    s.assessment_type,
    s.periods_per_year,
    a.semester
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(CREATE_VIEW)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW IF EXISTS v_subject_average")

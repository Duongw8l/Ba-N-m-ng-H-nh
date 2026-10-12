"""Khai báo `Table` để truy vấn view `v_subject_average` (D-026).

View do migration tạo, không do model, nên Table này nằm trong `MetaData` riêng: nếu để chung với
`Base.metadata` thì Alembic sẽ cố tạo nó thành bảng. View chỉ gom `COUNT`/`SUM`; công thức ĐTB ở
scores.py.
"""

from sqlalchemy import Column, Integer, MetaData, Numeric, SmallInteger, String, Table

_view_metadata = MetaData()

v_subject_average = Table(
    "v_subject_average",
    _view_metadata,
    Column("class_student_id", Integer),
    Column("class_id", Integer),
    Column("student_id", Integer),
    Column("subject_id", Integer),
    Column("assessment_type", String),
    Column("periods_per_year", SmallInteger),
    Column("semester", SmallInteger),
    Column("tx_count", Integer),  # số đầu điểm thường xuyên đã có
    Column("tx_sum", Numeric(12, 2)),  # tổng các đầu điểm thường xuyên (0 nếu chưa có)
    Column("gk_score", Numeric(4, 2)),
    Column("ck_score", Numeric(4, 2)),
    Column("comment_result", String),
)

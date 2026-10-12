"""Móc gọi sau khi dữ liệu của một lớp đã đổi (D-063, D-071)."""

from app.core.db import get_session_factory
from app.warning.service import refresh_after_import


def on_data_changed(class_id: int) -> None:
    """Gọi MỘT LẦN sau khi nhập tệp được ghi và commit thành công (và chỉ khi dữ liệu thật sự đổi).

    Chạy lại cảnh báo sớm của lớp trong một phiên DB riêng. Mọi lỗi chỉ được ghi log, không bao giờ
    làm hỏng việc nhập đã commit (hợp đồng của D-063). Analytics tính khi đọc (D-052) nên không có
    gì khác để "tính lại".
    """
    with get_session_factory()() as session:
        refresh_after_import(session, class_id)

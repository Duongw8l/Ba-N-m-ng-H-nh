"""Móc gọi sau khi dữ liệu của một lớp đã đổi (D-063)."""


def on_data_changed(class_id: int) -> None:
    """Gọi MỘT LẦN sau khi nhập tệp được ghi và commit thành công.

    Hiện để rỗng. Analytics tính khi đọc nên không có gì để "tính lại"; Giai đoạn 6 sẽ gắn Early
    Warning chạy lại cho lớp này vào đây. Hàm này không được làm hỏng việc nhập đã commit: nếu
    sau này nó có thể ném lỗi thì người gọi phải bắt và ghi log, không trả lỗi cho giáo viên.
    """

# Văn bản quy định cho RAG

Thư mục này chứa các văn bản quy định mà Trợ lý AI được phép trích dẫn (Thông tư 22/2021/TT-BGDĐT,
quy chế thi tốt nghiệp, nội quy trường...). Hệ thống tách văn bản theo **Điều/Khoản**, tính vector rồi
lưu vào bảng `regulation_chunks` (xem `docs/DECISIONS.md`, mục RAG).

## Có gì sẵn

- `van-ban-mau-gia.txt`: **văn bản GIẢ** dùng để thử nghiệm (8 điều có khoản và điểm). Mọi con số trong
  đó đều bịa ra, khác Thông tư 22 thật để không bị nhầm. Không dùng để tư vấn cho ai.
- `manifest.json`: ánh xạ tên tệp sang **tên hiển thị** của văn bản (tên này hiện trong trích dẫn).

## Nạp văn bản

```
make regulations        # nạp mọi .txt/.pdf/.docx trong thư mục này
```

Cách khác: đăng nhập Admin, vào trang **Quản lý văn bản quy định** (`/admin/regulations`) và tải tệp lên.

- Tệp không có trong `manifest.json` thì tên hiển thị là tên tệp bỏ đuôi.
- Mỗi tên chỉ có **một bản còn hiệu lực**. Nạp lại tên đã có thì bị từ chối (409): đánh dấu bản cũ là
  "hết hiệu lực" trước. Chạy `make regulations` nhiều lần là an toàn, tệp đã nạp được bỏ qua.
- Văn bản hết hiệu lực không bao giờ được AI trích dẫn.

## Thêm văn bản thật

1. Chép tệp `.pdf`, `.docx` hoặc `.txt` (UTF-8) vào thư mục này. PDF phải có lớp chữ; **bản quét ảnh
   chưa được hỗ trợ** (cần OCR) và sẽ bị từ chối với thông báo rõ ràng.
2. (Tuỳ chọn) thêm một dòng vào `manifest.json` để đặt tên hiển thị.
3. `make regulations`.
4. Chạy `make eval-rag` (hoặc `python eval/rag_eval.py`) để kiểm tra truy xuất, và **hiệu chỉnh lại
   ngưỡng** `rag_min_similarity` trong bảng `settings` nếu cần (ngưỡng hiện tại chỉ đo trên văn bản
   mẫu giả và chưa tách sạch câu trong phạm vi khỏi câu ngoài phạm vi, xem D-082).

## Về dữ liệu thật

Nguyên tắc 7 của dự án: không commit dữ liệu thật. Văn bản pháp quy công khai thì không nhạy cảm, nhưng
nội quy riêng của trường có thể có. Vì vậy `.gitignore` chỉ cho commit tệp mẫu giả, README và manifest;
văn bản bạn chép vào đây mặc định **không** bị commit. Muốn commit một văn bản công khai thì thêm dòng
ngoại lệ vào `.gitignore` một cách có chủ đích.

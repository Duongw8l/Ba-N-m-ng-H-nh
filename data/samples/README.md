# Tệp mẫu nhập dữ liệu

Bốn tệp để thử luồng nhập tệp (ba tệp đầu của Giai đoạn 4, tệp thứ tư của chức năng Admin) (xem [README gốc](../../README.md), mục "Nhập điểm, điểm danh, rèn luyện từ tệp"). **Toàn bộ là dữ liệu giả lập** do chính bộ sinh của seed tạo ra (`data/seed/`), nên mã học sinh khớp với DB sau `make seed`. Không bao giờ đặt sổ điểm thật vào thư mục này (nguyên tắc 7 của CLAUDE.md).

Sinh lại bằng `make samples` (script `make_samples.py`, logic ở `build.py`; cần DB đã migrate vì hệ số tính ĐTB đọc từ bảng `settings`). Test `tests/imports/test_samples.py` so nội dung các tệp đã commit với bộ sinh, nên đổi seed mà quên chạy lại `make samples` thì test đỏ.

| Tệp | Dùng với | Nội dung |
| --- | --- | --- |
| `diem-toan-11a2-hk1.xlsx` | `gv.toan.11@example.com`, lớp 11A2, môn Toán, học kỳ I | Sổ điểm đúng định dạng "xuất từ sổ điểm điện tử" (xem bên dưới). Khác DB ở **3 học sinh** nên xem trước có 3 dòng "Đổi" và 37 dòng "Giữ nguyên" |
| `diem-toan-11a2-hk1-loi.xlsx` | như trên | Cùng sổ điểm nhưng có lỗi cài sẵn; **không thể xác nhận**, hệ thống không ghi gì |
| `diem-danh-11a2-2027-03.csv` | `gvcn.11a2@example.com`, lớp 11A2 | Điểm danh cả lớp tháng 3/2027: 40 học sinh × 23 ngày học = 920 dòng. UTF-8 có BOM |
| `danh-sach-hoc-sinh-11a9.xlsx` | `admin@example.com`, một lớp **11A9 mới** | Danh sách 30 học sinh (mã `HS1109001` đến `HS1109030`): `STT`, `Mã HS`, `Họ và tên`, `Ngày sinh`, `Họ tên phụ huynh`, `Số điện thoại`. Tạo lớp 11A9 ở "Năm học & lớp" rồi nhập từ trang quản trị của lớp. Họ tên và số điện thoại giả (đầu số `0000`), không trùng học sinh nào của seed |

## `diem-toan-11a2-hk1.xlsx`

Ba dòng đầu là tiêu đề lớn và một dòng trống (hệ thống tự dò dòng tiêu đề, ở đây là dòng 4). Các cột: `STT`, `Mã HS`, `Họ và tên`, `ĐĐGtx 1` đến `ĐĐGtx 4`, `ĐĐGgk`, `ĐĐGck`, `ĐTB`. Cột `STT` và `ĐTB` được bỏ qua (ĐTB do hệ thống tự tính bằng Analytics, không lấy từ tệp).

Ba học sinh có điểm khác DB (đều lệch 0,5): `HS1102005` (ĐĐGtx 2: 6,1 thành 6,6), `HS1102018` (ĐĐGgk: 4,8 thành 5,3), `HS1102031` (ĐĐGck: 5,8 thành 6,3).

## `diem-toan-11a2-hk1-loi.xlsx`

Số dòng là số dòng trong tệp Excel (dòng 5 là học sinh đầu tiên).

| Dòng | Cột | Lỗi | Kết quả mong đợi |
| --- | --- | --- | --- |
| 7 | Mã HS | `HS1102999` không có trong lớp | Lỗi |
| 10 | ĐĐGgk | điểm 11 | Lỗi (ngoài khoảng 0 đến 10) |
| 13 | ĐĐGtx 1 | chữ "tám" | Lỗi (không phải số) |
| 16 | Mã HS | trùng mã với dòng 15 | Lỗi |
| 19 | ĐĐGtx 3 | để trống | Lỗi (thiếu đầu điểm; có thể bật "Cho phép nhập dở") |
| 22 | ĐĐGck | `8,25` | Lỗi (quá 1 chữ số thập phân; hệ thống không tự làm tròn) |
| 25 | ĐĐGtx 1 | giữ giá trị trong DB nhưng viết dấu phẩy kiểu Việt Nam, dạng chữ (ví dụ `7,5`) | Hợp lệ: không lỗi, không cảnh báo, "Giữ nguyên" |
| 28 | Họ và tên | tên khác hệ thống | Cảnh báo (không chặn) |

Kết quả: 6 dòng lỗi, 1 cảnh báo, nút "Xác nhận nhập" bị khoá; gọi thẳng API xác nhận cũng bị từ chối (422).

## `diem-danh-11a2-2027-03.csv`

Cột: `Mã HS`, `Họ và tên`, `Ngày` (dd/mm/yyyy), `Trạng thái` (Có mặt, Nghỉ có phép, Nghỉ không phép, Muộn).

- Với DB mặc định (`make seed`) tháng 3/2027 đã có đúng dữ liệu này: xem trước báo 920 dòng "Giữ nguyên".
- Với `make seed SEED_ARGS="--hold-out 2027-03"` (bỏ điểm danh tháng 3 khỏi DB) tệp là **dữ liệu mới**: 920 dòng "Mới". Xác nhận xong, em An (`HS1102001`) nghỉ 38 buổi như seed đầy đủ và dashboard lớp 11A2 đổi theo. Các lớp khác vẫn thiếu tháng 3 cho tới khi chạy lại `make seed`.

## Thử bằng dòng lệnh

```bash
# Đăng nhập, lấy access_token (mật khẩu dev: xem README gốc, mục tài khoản dev)
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email": "gv.toan.11@example.com", "password": "<mật khẩu dev>"}'

# Xem trước (chưa ghi gì): lớp 11A2 có id 5, môn Toán có id 2
curl -s -X POST http://localhost:8000/api/v1/classes/5/import/assessments \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@data/samples/diem-toan-11a2-hk1.xlsx" -F "subject_id=2" -F "semester=1"

# Xác nhận (ghi dữ liệu); job_id lấy từ bước xem trước
curl -s -X POST http://localhost:8000/api/v1/imports/<job_id>/confirm -H "Authorization: Bearer <access_token>"
```

Thử quyền: `gv.van.11@example.com` nhập điểm Toán bị 403; `gv.toan.11@example.com` nhập điểm danh 11A2 bị 403 (dạy Toán ở đó nhưng không chủ nhiệm); `bgh1@example.com` và `admin@example.com` luôn bị 403.

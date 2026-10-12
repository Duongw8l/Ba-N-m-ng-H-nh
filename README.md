# Trợ lý AI quản lý lớp học THPT

Web app cho trường THPT (khối 10, 11, 12): theo dõi điểm, chuyên cần, rèn luyện; cảnh báo sớm học sinh có nguy cơ không được lên lớp; AI hỗ trợ hỏi đáp và sinh nhận xét (luôn là bản nháp, giáo viên duyệt). Chỉ dùng dữ liệu giả lập.

Tài liệu: [CLAUDE.md](CLAUDE.md) (nguyên tắc, quy ước) · [docs/DESIGN.md](docs/DESIGN.md) (thiết kế đầy đủ) · [docs/FLOWS.md](docs/FLOWS.md) (sơ đồ) · [docs/PROGRESS.md](docs/PROGRESS.md) (tiến độ) · [docs/DECISIONS.md](docs/DECISIONS.md) (quyết định thiết kế) · [docs/PROMPTS.md](docs/PROMPTS.md) (bộ prompt các giai đoạn).

## Yêu cầu

- Docker Desktop (Compose v2 trở lên) và GNU make. Trên Windows cài make bằng `winget install ezwinports.make`, rồi mở lại terminal.
- Chỉ khi chạy ngoài Docker (lint, test, phát triển): Python 3.11+ và Node 22.

## Chạy nhanh bằng Docker

```bash
cp .env.example .env     # PowerShell: Copy-Item .env.example .env
make up
```

Mở <http://localhost:5173/login>: trang đăng nhập hiện "Máy chủ: ok" và "Cơ sở dữ liệu: ok" (trang chủ `/` cần đăng nhập). Swagger: <http://localhost:8000/api/docs>. Tắt bằng `make down` (dữ liệu DB vẫn nằm trong volume).

Muốn đăng nhập cần có dữ liệu mẫu: `make migrate` rồi `make seed` (xem mục "Dữ liệu giả lập và tài khoản dev"). `JWT_SECRET` trong `.env` phải dài từ 32 ký tự.

`.env` chứa giá trị mẫu cho môi trường phát triển và không bao giờ được commit. Khoá API của LLM (nếu dùng) chỉ điền vào `.env`.

## Phát triển ngoài Docker

```bash
python -m venv backend/.venv
# Kích hoạt: Windows  backend\.venv\Scripts\Activate.ps1   |   Linux/macOS  source backend/.venv/bin/activate
make install             # cài dependency back-end và front-end
make db                  # chỉ chạy PostgreSQL
make migrate             # tạo bảng, view v_subject_average, extension vector, giá trị mặc định của settings
make seed                # nạp dữ liệu giả lập (xem mục bên dưới)
make dev-be              # terminal 1: API tại http://localhost:8000
make dev-fe              # terminal 2: giao diện tại http://localhost:5173
```

## Lệnh make

| Lệnh | Việc làm |
| --- | --- |
| `make up` / `make down` | Dựng và chạy / tắt db + backend + frontend trong Docker |
| `make db` | Chỉ chạy PostgreSQL |
| `make install` | Cài dependency ngoài Docker |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Sinh dữ liệu giả lập vào DB (cần `make db` và `make migrate` trước) |
| `make dev-be` / `make dev-fe` | Chạy back-end (uvicorn) / front-end (Vite) với tự nạp lại |
| `make test` | pytest. Gồm test cần PostgreSQL thật nên phải `make db` trước; chỉ chạy test không cần DB: `cd backend && python -m pytest -m "not db"` |
| `make lint` | ruff check, ruff format --check (cả `backend/` và `data/`), eslint, tsc |
| `make eval` | Chưa triển khai (in thông báo, thoát mã 0) |

## Dữ liệu giả lập và tài khoản dev

`make seed` tạo 1 trường, năm học 2026-2027 (đủ hai học kỳ, mô phỏng một năm đã hoàn tất), khối 10/11/12 mỗi khối 3 lớp, mỗi lớp 40 học sinh (360 học sinh), 17 môn theo Chương trình GDPT 2018 và tài khoản mẫu. Toàn bộ là dữ liệu giả: tên ghép ngẫu nhiên, email `@example.com`, số điện thoại phụ huynh bắt đầu bằng `0000` (không hợp lệ).

**Cảnh báo:** `make seed` xoá **mọi** dữ liệu trường học trong DB (điểm, điểm danh, học sinh, lớp, tài khoản, nhật ký AI...) rồi nạp lại; chỉ giữ bảng `settings` và `regulation_chunks`. Từ chối chạy khi `APP_ENV=production`. Chạy lại với cùng tham số cho đúng cùng dữ liệu.

```bash
make seed                                                   # mặc định: --seed 2026, 3 lớp/khối, sĩ số 40
make seed SEED_ARGS="--seed 7 --classes-per-grade 2 --class-size 30"
```

Mật khẩu dev dùng chung cho mọi tài khoản (chỉ dành cho môi trường phát triển): `ThdaDev#2026`

| Vai trò | Email | Ghi chú |
| --- | --- | --- |
| Admin | `admin@example.com` | cấu hình hệ thống |
| Ban giám hiệu | `bgh1@example.com`, `bgh2@example.com` | toàn trường |
| GVCN (chỉ chủ nhiệm) | `gvcn.10a2@example.com`, `gvcn.10a3@example.com`, ... `gvcn.12a3@example.com` | một người cho mỗi lớp từ A2 |
| GVBM | `gv.<môn>.<khối>@example.com`, ví dụ `gv.van.11@example.com`, `gv.ly.12@example.com` | một giáo viên cho mỗi cặp môn-khối, dạy mọi lớp của khối có học môn đó |
| Vừa GVCN vừa GVBM | `gv.toan.10@example.com`, `gv.toan.11@example.com`, `gv.toan.12@example.com` | chủ nhiệm lớp A1 của khối và dạy Toán cả khối (để thử quyền cộng dồn) |

Thử API: mở Swagger, gọi `POST /api/v1/auth/login` với email và mật khẩu ở trên, bấm **Authorize** và dán `access_token`, rồi thử `GET /api/v1/me/assignments` và `GET /api/v1/classes/{id}/students`. Admin bị 403 ở danh sách lớp; GVBM chỉ vào được lớp mình dạy và không thấy thông tin phụ huynh; GVCN và BGH thấy thông tin phụ huynh. Mỗi lần mở danh sách lớp được ghi vào bảng `audit_logs`.

Mã môn trong email: `van` `toan` `anh` `su` `gdtc` `gdqp` `hdtn` `gddp` `dia` `gdktpl` `ly` `hoa` `sinh` `cn` `tin` `nhac` `mt`.

Học sinh dùng cho kịch bản demo và test biên: `HS1102001` (11A2, em An nghỉ 38 buổi), `HS1102002` (11A2, môn Toán dưới 3,5), `HS1201001` đến `HS1201003` (12A1, nghỉ 44, 45, 46 buổi), `HS1201004` đến `HS1201006` (12A1, mọi đầu điểm Toán đúng 3,4 / 3,5 / 5,0). Mã học sinh có dạng `HS` + khối + lớp (2 chữ số) + số thứ tự (3 chữ số).

## Test có PostgreSQL thật

Test trong `backend/tests/db/` cần PostgreSQL có pgvector (`make db`). Chúng dùng database riêng `classroom_test` trên cùng máy chủ với `DATABASE_URL` (hoặc `TEST_DATABASE_URL` nếu đặt): mỗi lần chạy xoá và dựng lại bằng Alembic rồi seed, nên không đụng DB phát triển `classroom`. Thiếu DB thì `make test` dừng và báo "Chạy make db trước".

# Tiến độ

Cập nhật lần cuối: 2026-10-12. Tên và thứ tự giai đoạn lấy từ bộ prompt [PROMPTS.md](PROMPTS.md).

## Bảng 12 giai đoạn

| Giai đoạn | Nội dung | Trạng thái |
| --- | --- | --- |
| 0 | Khởi tạo dự án | Xong (còn chờ kiểm: CI trên GitHub, cần đẩy lên GitHub, xem bên dưới) |
| 1 | Cơ sở dữ liệu + dữ liệu giả lập | Chưa làm |
| 2 | Xác thực và phân quyền | Chưa làm |
| 3 | Analytics theo Thông tư 22 | Chưa làm |
| 4 | Import Excel/CSV | Chưa làm |
| 5 | Dashboard và giao diện chính | Chưa làm |
| 6 | Cảnh báo sớm (luật + ML) | Chưa làm |
| 7 | RAG văn bản quy định | Chưa làm |
| 8 | Trợ lý AI gọi hàm | Chưa làm |
| 9 | Nhận xét và báo cáo | Chưa làm |
| 10 | Đánh giá AI | Chưa làm |
| 11 | Bảo mật, triển khai, demo | Chưa làm |

## Giai đoạn 0: Khởi tạo dự án

### Đã làm

- Cấu trúc thư mục đúng theo CLAUDE.md; thư mục chưa dùng có `.gitkeep`.
- Back-end FastAPI: `GET /api/v1/health` trả `{"status":"ok","db":true|false}`; cấu hình bằng Pydantic Settings; SQLAlchemy 2.0 + psycopg 3; Alembic đã khởi tạo (chưa có migration; DB chỉ có bảng `alembic_version` do Alembic tự tạo, chưa có bảng nghiệp vụ); ruff, pytest, 1 test cho `/health`.
- Front-end React + Vite + TypeScript, Tailwind v4, React Router, TanStack Query: trang chủ hiển thị trạng thái health bằng tiếng Việt, trang 404; ESLint và `tsc`.
- Hạ tầng: `docker-compose.yml` (db `pgvector/pgvector:pg16`, backend, frontend), `.env.example`, `.gitignore`, `.gitattributes`, Makefile, CI GitHub Actions.
- Tài liệu: README, PROGRESS (file này), DECISIONS.

### Chưa làm (thuộc các giai đoạn sau)

- Bảng nghiệp vụ, migration đầu tiên, bật extension `vector` (Giai đoạn 1 hoặc 7); công thức Thông tư 22; gọi LLM; xác thực.
- Vitest/Playwright, image triển khai (nginx, không reload), tắt Swagger trên môi trường thật (đã có công tắc `APP_ENV=production`).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `ruff check`, `ruff format --check`, `pytest` (trên máy và trong container backend) | Đã chạy, qua |
| `eslint`, `tsc -b`, `vite build` (front-end) | Đã chạy, qua |
| `docker compose up -d --build --renew-anon-volumes --wait` (đúng lệnh của `make up`): build 3 image, 3 dịch vụ `healthy` | Đã chạy, qua |
| Trang chủ trong trình duyệt: "Máy chủ: ok" và "Cơ sở dữ liệu: ok" (`/health` trả `{"status":"ok","db":true}`) | Đã kiểm, đúng |
| Tắt rồi bật lại container db: trang chủ báo "lỗi" rồi tự phục hồi; backend không bị khởi động lại, vẫn `healthy` | Đã kiểm, đúng |
| `alembic upgrade head` trên DB thật, từ máy host qua `127.0.0.1:5432` | Đã chạy, qua |
| Tự nạp lại (hot reload) của backend và frontend trên bind mount Windows | Đã kiểm, đúng |
| Chạy chính `make` (GNU make 4.4.1, shell cmd.exe): `up`, `down`, `db`, `migrate`, `seed`, `eval`, `install`, `lint`, `test`, `dev-be`, `dev-fe` | Đã chạy cả 11 mục tiêu, qua (phát hiện và sửa 1 lỗi font của `seed`/`eval`, xem D-020) |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub. Cú pháp YAML hợp lệ |

### Cách kiểm tra

1. `cp .env.example .env` (PowerShell: `Copy-Item .env.example .env`).
2. `make up`: cả 3 dịch vụ lên và khoẻ (`docker compose ps`).
3. Mở <http://localhost:5173>: "Máy chủ: ok", "Cơ sở dữ liệu: ok". Hoặc `curl http://localhost:8000/api/v1/health` trả `{"status":"ok","db":true}`.
4. `docker compose stop db`, chờ tối đa 15 giây (trang tự làm mới khi tab đang hiển thị): "Cơ sở dữ liệu: lỗi", còn backend vẫn `healthy`. `docker compose start db`: trở lại "ok".
5. Ngoài Docker, trong venv đã kích hoạt: `make install`, rồi `make lint` và `make test` đều qua.
6. `make db` rồi `make migrate`: chạy không lỗi (chỉ tạo bảng `alembic_version` rỗng, chưa có bảng nghiệp vụ).
7. `make seed` và `make eval`: in "chưa triển khai", thoát mã 0.
8. `make down`.

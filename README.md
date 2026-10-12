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

Mở <http://localhost:5173>: trang chủ hiện "Máy chủ: ok" và "Cơ sở dữ liệu: ok". Swagger: <http://localhost:8000/api/docs>. Tắt bằng `make down` (dữ liệu DB vẫn nằm trong volume).

`.env` chứa giá trị mẫu cho môi trường phát triển và không bao giờ được commit. Khoá API của LLM (nếu dùng) chỉ điền vào `.env`.

## Phát triển ngoài Docker

```bash
python -m venv backend/.venv
# Kích hoạt: Windows  backend\.venv\Scripts\Activate.ps1   |   Linux/macOS  source backend/.venv/bin/activate
make install             # cài dependency back-end và front-end
make db                  # chỉ chạy PostgreSQL
make migrate
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
| `make dev-be` / `make dev-fe` | Chạy back-end (uvicorn) / front-end (Vite) với tự nạp lại |
| `make test` | pytest |
| `make lint` | ruff check, ruff format --check, eslint, tsc |
| `make seed`, `make eval` | Chưa triển khai (in thông báo, thoát mã 0) |

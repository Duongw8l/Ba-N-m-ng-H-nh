# Các lệnh thường dùng của dự án (xem CLAUDE.md).
#
# Makefile chạy được với GNU make trên Windows (cmd.exe), Linux và macOS (sh), nên chỉ dùng
# cú pháp chung của cả hai shell: "cd dir && lệnh", không dùng bash-ism.
# Python (venv đã kích hoạt, xem README) và Node phải có sẵn trên PATH khi chạy ngoài Docker.

.PHONY: install up down db migrate seed samples warn train regulations rag-model dev-be dev-fe test lint eval eval-rag eval-assistant

# In "chưa triển khai: <lệnh>". Dòng lệnh Python dưới đây cố ý thuần ASCII (dùng chr() cho hai chữ
# có dấu): nếu để chữ có dấu trong Makefile, make trên Windows chuyển byte UTF-8 cho cmd.exe theo
# bảng mã ANSI và chữ bị lỗi font. Cách này hiện đúng trên cả cmd.exe lẫn sh. Thoát với mã 0.
NOT_IMPLEMENTED = python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); print('ch' + chr(0x1b0) + 'a tri' + chr(0x1ec3) + 'n khai: $(1)')"

# Cài dependency để chạy, lint, test ngoài Docker. torch bản CPU cài trước: bản mặc định trên PyPI
# cho Linux kéo theo CUDA (vài GB), không cần vì hệ thống chạy không GPU.
install:
	cd backend && python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
	cd backend && python -m pip install -e ".[dev]"
	npm --prefix frontend ci

# Dựng và chạy db + backend + frontend trong Docker, chờ tới khi cả ba khoẻ.
# --renew-anon-volumes: nạp lại node_modules của frontend sau khi đổi dependency
# (không đụng tới dữ liệu PostgreSQL, vì đó là volume có tên).
up:
	docker compose up -d --build --renew-anon-volumes --wait
	@echo Front-end: http://localhost:5173
	@echo Swagger:   http://localhost:8000/api/docs

down:
	docker compose down

# Chỉ chạy PostgreSQL (để dev-be, migrate chạy ngoài Docker).
db:
	docker compose up -d --wait db

migrate:
	cd backend && python -m alembic upgrade head

# Sinh dữ liệu giả lập (data/seed/), cần DB đã migrate (make db, make migrate). Xoá dữ liệu cũ rồi
# nạp lại. Tham số tuỳ chọn: make seed SEED_ARGS="--seed 7 --classes-per-grade 2 --class-size 30"
seed:
	python data/seed/run.py $(SEED_ARGS)

# Sinh lại 3 tep mau nhap du lieu trong data/samples/ (cung bo sinh voi seed; can DB da migrate).
# Dong nay cung thuan ASCII vi make tren Windows chuyen byte cho cmd.exe theo bang ma ANSI.
samples:
	python data/samples/make_samples.py

# Chay canh bao som cho ca truong (them dong moi vao risk_alerts neu noi dung doi). Can DB da migrate.
warn:
	cd backend && python -m app.warning.run

# Huan luyen lai mo hinh ML canh bao som (vai phut): dung database tam, ghi backend/ml/models/ va
# backend/ml/REPORT.md. Can PostgreSQL dang chay (make db).
train:
	cd backend && python -m ml.train

# Nap van ban quy dinh trong data/regulations/ (tach Dieu/Khoan, tinh vector, luu pgvector). Van ban
# da nap thi bo qua. Can DB da migrate; lan dau tai mo hinh bge-m3 (~2,3 GB, xem make rag-model).
regulations:
	cd backend && python -m app.rag.ingest

# Tai san mo hinh embedding (bge-m3) va kiem tra so chieu, de lan nap dau khong phai cho.
rag-model:
	cd backend && python -m app.rag.ingest --download-model

dev-be:
	cd backend && python -m uvicorn app.main:app --reload --reload-dir app

dev-fe:
	npm --prefix frontend run dev

test:
	cd backend && python -m pytest

# ruff lint cả ../data (script seed); --config để data/ dùng đúng cấu hình của backend/pyproject.toml.
lint:
	cd backend && python -m ruff check --config pyproject.toml . ../data ../eval
	cd backend && python -m ruff format --check --config pyproject.toml . ../data ../eval
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck

eval:
	@$(call NOT_IMPLEMENTED,eval)

# Danh gia RAG van ban quy dinh bang mo hinh that (Hit@4, ti le tu choi dung). Can DB da migrate,
# da nap van ban (make regulations) va da tai mo hinh (make rag-model). Thu nguong khac:
# make eval-rag RAG_ARGS="--threshold 0.6"
eval-rag:
	python eval/rag_eval.py $(RAG_ARGS)

# Danh gia Tro ly AI goi ham bang LLM that (chon dung ham, dung so lieu, tu choi dung; 15 cau mau).
# Can DB da migrate va seed, LLM_PROVIDER + LLM_API_KEY trong .env, va make regulations cho cau ve
# quy dinh. Chi in dap an ky vong, khong goi LLM: make eval-assistant ASSISTANT_ARGS=--dry-run
eval-assistant:
	python eval/assistant_eval.py $(ASSISTANT_ARGS)

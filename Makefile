# Các lệnh thường dùng của dự án (xem CLAUDE.md).
#
# Makefile chạy được với GNU make trên Windows (cmd.exe), Linux và macOS (sh), nên chỉ dùng
# cú pháp chung của cả hai shell: "cd dir && lệnh", không dùng bash-ism.
# Python (venv đã kích hoạt, xem README) và Node phải có sẵn trên PATH khi chạy ngoài Docker.

.PHONY: install up down db migrate seed dev-be dev-fe test lint eval

# In "chưa triển khai: <lệnh>". Dòng lệnh Python dưới đây cố ý thuần ASCII (dùng chr() cho hai chữ
# có dấu): nếu để chữ có dấu trong Makefile, make trên Windows chuyển byte UTF-8 cho cmd.exe theo
# bảng mã ANSI và chữ bị lỗi font. Cách này hiện đúng trên cả cmd.exe lẫn sh. Thoát với mã 0.
NOT_IMPLEMENTED = python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); print('ch' + chr(0x1b0) + 'a tri' + chr(0x1ec3) + 'n khai: $(1)')"

# Cài dependency để chạy, lint, test ngoài Docker.
install:
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

seed:
	@$(call NOT_IMPLEMENTED,seed)

dev-be:
	cd backend && python -m uvicorn app.main:app --reload --reload-dir app

dev-fe:
	npm --prefix frontend run dev

test:
	cd backend && python -m pytest

lint:
	cd backend && python -m ruff check .
	cd backend && python -m ruff format --check .
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck

eval:
	@$(call NOT_IMPLEMENTED,eval)

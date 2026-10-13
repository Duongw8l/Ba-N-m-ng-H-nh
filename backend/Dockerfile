# Image phát triển: uvicorn --reload, mã nguồn được mount từ máy host (xem docker-compose.yml).
# Image triển khai (không reload, không dev-dependency) làm ở Giai đoạn 11.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Chỉ cần pyproject.toml để cài dependency (packages = [] nên không cần mã nguồn),
# nhờ vậy Docker giữ cache lớp này khi chỉ đổi mã nguồn.
COPY pyproject.toml ./
# torch bản CPU: bản mặc định trên PyPI cho Linux kéo theo CUDA (vài GB), không cần vì hệ thống chạy
# không GPU. Cài trước để pip thấy yêu cầu torch trong pyproject đã được thoả.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install -e ".[dev]"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

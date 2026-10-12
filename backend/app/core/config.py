"""Cấu hình ứng dụng, đọc từ biến môi trường (và file .env ở thư mục gốc repo khi chạy cục bộ).

Danh sách biến phải khớp .env.example. Biến môi trường thật luôn thắng giá trị trong .env.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> thư mục gốc repo là parents[3].
# Trong Docker (/app/app/core/config.py) đường dẫn này trỏ tới "/" và không có .env:
# biến môi trường do Docker Compose truyền vào.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production"] = "development"

    # Bắt buộc, không có giá trị mặc định: thiếu thì ứng dụng báo lỗi ngay khi khởi động.
    database_url: str
    jwt_secret: SecretStr

    # Chưa dùng ở Giai đoạn 0. Khai báo sẵn để .env.example và Settings luôn đồng bộ.
    llm_provider: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = ""
    # Số chiều vector của regulation_chunks.embedding. Migration đọc giá trị này lúc chạy và cố định
    # vào cột; đổi về sau cần migration mới (ALTER COLUMN ... TYPE vector(N)) và tính lại vector.
    # 1024 là số chiều của bge-m3 và multilingual-e5-large. Trần 2000 là giới hạn chỉ mục pgvector.
    embedding_dim: int = Field(default=1024, ge=1, le=2000)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # các trường bắt buộc được đọc từ môi trường

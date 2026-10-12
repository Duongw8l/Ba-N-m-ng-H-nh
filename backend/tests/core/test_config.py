import pytest
from pydantic import ValidationError

from app.core.config import JWT_SECRET_MIN_LENGTH, Settings


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@127.0.0.1:5432/x",
        "jwt_secret": "x" * JWT_SECRET_MIN_LENGTH,
    }
    # _env_file=None: không đọc .env của người chạy.
    return Settings(_env_file=None, **(values | overrides))  # type: ignore[arg-type]


def test_jwt_secret_shorter_than_32_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="32 ký tự"):
        settings(jwt_secret="x" * (JWT_SECRET_MIN_LENGTH - 1))


def test_jwt_secret_of_32_characters_is_accepted_and_expiry_defaults_to_two_hours() -> None:
    config = settings()

    assert len(config.jwt_secret.get_secret_value()) == 32
    assert config.jwt_expire_minutes == 120


@pytest.mark.parametrize("minutes", [0, 4, 1441])
def test_jwt_expiry_must_be_between_5_minutes_and_one_day(minutes: int) -> None:
    with pytest.raises(ValidationError):
        settings(jwt_expire_minutes=minutes)

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.tokens import ALGORITHM, InvalidTokenError, create_access_token, decode_access_token
from app.core.config import get_settings


def secret() -> str:
    return get_settings().jwt_secret.get_secret_value()


def forge(payload: dict[str, object], key: str | None = None, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(payload, secret() if key is None else key, algorithm=algorithm)


def future() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


def test_token_round_trips_the_user_id_and_expires_after_configured_minutes() -> None:
    token, expires_in = create_access_token(42)

    assert decode_access_token(token) == 42
    assert expires_in == get_settings().jwt_expire_minutes * 60 == 7200
    claims = jwt.decode(token, secret(), algorithms=[ALGORITHM])
    assert set(claims) == {"sub", "iat", "exp"}  # không có vai trò trong token
    assert claims["exp"] - claims["iat"] == expires_in


def test_expired_token_is_rejected() -> None:
    issued_long_ago = datetime.now(UTC) - timedelta(hours=3)
    token, _ = create_access_token(1, now=issued_long_ago)  # hết hạn sau 2 giờ

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = forge({"sub": "1", "exp": future()}, key="mot-khoa-khac-dai-hon-ba-muoi-hai-ky-tu-xyz")

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    token, _ = create_access_token(1)
    header, payload, signature = token.split(".")
    swapped = "A" if signature[0] != "A" else "B"

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{payload}.{swapped}{signature[1:]}")


def test_unsigned_alg_none_token_is_rejected() -> None:
    token = jwt.encode({"sub": "1", "exp": future()}, key=None, algorithm="none")

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "payload",
    [
        {"exp": future()},  # thiếu sub
        {"sub": "1"},  # thiếu exp
        {"sub": "khong-phai-so", "exp": future()},
    ],
    ids=["thieu-sub", "thieu-exp", "sub-khong-phai-so"],
)
def test_token_with_missing_or_malformed_claims_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(forge(payload))


def test_garbage_is_rejected() -> None:
    for garbage in ("", "abc", "a.b.c", "Bearer x"):
        with pytest.raises(InvalidTokenError):
            decode_access_token(garbage)

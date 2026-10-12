import pytest

from app.core.security import MAX_PASSWORD_BYTES, hash_password, verify_password


def test_hash_then_verify_accepts_right_password_and_rejects_wrong_one() -> None:
    hashed = hash_password("Mat-khau-dev-1")

    assert hashed.startswith("$2b$")
    assert verify_password("Mat-khau-dev-1", hashed)
    assert not verify_password("mat-khau-dev-1", hashed)


def test_hash_is_salted() -> None:
    assert hash_password("giong-nhau") != hash_password("giong-nhau")


def test_vietnamese_password_round_trips() -> None:
    hashed = hash_password("Mật khẩu có dấu 123")

    assert verify_password("Mật khẩu có dấu 123", hashed)


def test_hash_rejects_password_longer_than_72_bytes() -> None:
    with pytest.raises(ValueError, match="72"):
        hash_password("a" * (MAX_PASSWORD_BYTES + 1))


def test_verify_returns_false_instead_of_raising_for_bad_input() -> None:
    hashed = hash_password("ok")

    assert not verify_password("a" * (MAX_PASSWORD_BYTES + 1), hashed)
    assert not verify_password("ok", "khong-phai-hash-bcrypt")

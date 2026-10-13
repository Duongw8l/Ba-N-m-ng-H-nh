import pytest

from app.core.security import (
    MAX_PASSWORD_BYTES,
    TEMPORARY_PASSWORD_LENGTH,
    generate_temporary_password,
    hash_password,
    verify_password,
)


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


def test_temporary_password_is_long_random_and_hashable() -> None:
    passwords = {generate_temporary_password() for _ in range(200)}

    assert len(passwords) == 200  # không trùng nhau
    for password in passwords:
        assert len(password) == TEMPORARY_PASSWORD_LENGTH
        assert any(ch.islower() for ch in password)
        assert any(ch.isupper() for ch in password)
        assert any(ch.isdigit() for ch in password)
        assert not set(password) & set("ilIO01")  # không có ký tự dễ nhầm
    assert len(next(iter(passwords)).encode()) <= MAX_PASSWORD_BYTES

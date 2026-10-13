"""Băm và kiểm tra mật khẩu bằng bcrypt (DESIGN mục 10). Giai đoạn 2 dùng lại ở đăng nhập.

Dùng thư viện `bcrypt` trực tiếp (D-033). Không thuộc module nào nên đặt ở core/; JWT và
get_current_user nằm ở app/auth/ (Giai đoạn 2).
"""

import secrets

import bcrypt

# Hệ số chi phí: mỗi lần tăng 1 là chậm gấp đôi. 12 là mức phổ biến hiện nay (~0,25 giây).
BCRYPT_ROUNDS = 12
# bcrypt chỉ dùng 72 byte đầu của mật khẩu; bcrypt 5 từ chối mật khẩu dài hơn thay vì cắt lặng lẽ.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    """Băm mật khẩu (có muối ngẫu nhiên). Ném ValueError nếu quá 72 byte UTF-8."""
    data = plain.encode("utf-8")
    if len(data) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Mật khẩu dài quá {MAX_PASSWORD_BYTES} byte (UTF-8).")
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Đúng mật khẩu thì True. Mật khẩu quá dài hoặc hash hỏng thì False (đăng nhập trả 401)."""
    data = plain.encode("utf-8")
    if len(data) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(data, hashed.encode("ascii"))
    except ValueError:
        return False


# Bỏ các ký tự dễ nhầm khi đọc hoặc chép tay: i, l, o, I, O, 0, 1.
_TEMP_LOWER = "abcdefghjkmnpqrstuvwxyz"
_TEMP_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_TEMP_DIGITS = "23456789"
TEMPORARY_PASSWORD_LENGTH = 12


def generate_temporary_password() -> str:
    """Mật khẩu tạm ngẫu nhiên (`secrets`) cho tài khoản mới hoặc được đặt lại (D-097).

    Luôn có chữ thường, chữ hoa và chữ số. Chỉ hiện cho Admin một lần; nơi duy nhất còn lại là
    bản băm bcrypt.
    """
    alphabet = _TEMP_LOWER + _TEMP_UPPER + _TEMP_DIGITS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(TEMPORARY_PASSWORD_LENGTH))
        if (
            any(ch in _TEMP_LOWER for ch in password)
            and any(ch in _TEMP_UPPER for ch in password)
            and any(ch in _TEMP_DIGITS for ch in password)
        ):
            return password

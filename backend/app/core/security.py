"""Băm và kiểm tra mật khẩu bằng bcrypt (DESIGN mục 10). Giai đoạn 2 dùng lại ở đăng nhập.

Dùng thư viện `bcrypt` trực tiếp (D-033). Không thuộc module nào nên đặt ở core/; JWT và
get_current_user nằm ở app/auth/ (Giai đoạn 2).
"""

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

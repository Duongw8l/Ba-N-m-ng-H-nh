"""Tên người giả lập: ghép ngẫu nhiên từ danh sách họ, đệm, tên phổ biến.

Không dùng tên người thật cụ thể. Giới tính chỉ dùng nội bộ để ghép tên cho hợp lý, không lưu vào
DB (và theo DESIGN mục 10 không bao giờ dùng làm đặc trưng cho mô hình).
"""

import random

# Miền dành riêng cho ví dụ (RFC 2606). Không dùng ".test": email-validator (Pydantic EmailStr, dùng
# ở Giai đoạn 2) từ chối tên miền đặc biệt.
EMAIL_DOMAIN = "example.com"

# Mật khẩu dev dùng chung cho mọi tài khoản seed. Chỉ dùng ở môi trường phát triển (xem README).
DEV_PASSWORD = "ThdaDev#2026"

# (họ, trọng số) theo mức phổ biến tương đối.
SURNAMES: tuple[tuple[str, int], ...] = (
    ("Nguyễn", 36),
    ("Trần", 11),
    ("Lê", 10),
    ("Phạm", 7),
    ("Hoàng", 5),
    ("Huỳnh", 3),
    ("Phan", 3),
    ("Vũ", 3),
    ("Võ", 3),
    ("Đặng", 3),
    ("Bùi", 3),
    ("Đỗ", 2),
    ("Hồ", 2),
    ("Ngô", 2),
    ("Dương", 2),
    ("Lý", 1),
)

MIDDLE_MALE = ("Văn", "Đức", "Minh", "Quang", "Hữu", "Gia", "Thành", "Quốc", "Xuân", "Công", "Anh")
MIDDLE_FEMALE = (
    "Thị",
    "Ngọc",
    "Thu",
    "Thanh",
    "Bảo",
    "Khánh",
    "Phương",
    "Hồng",
    "Diệu",
    "Kim",
    "Tuyết",
)

# Cố ý không có "An": kịch bản demo cần đúng một em tên An trong lớp 11A2 (scenarios.py).
# fmt: off
GIVEN_MALE = (
    "Bảo", "Cường", "Dũng", "Duy", "Đạt", "Hải", "Hiếu", "Hưng", "Huy", "Khang", "Khoa", "Kiên",
    "Lâm", "Long", "Minh", "Nam", "Nghĩa", "Phúc", "Quân", "Sơn", "Thắng", "Tín", "Trung",
    "Tuấn", "Việt", "Vinh",
)
GIVEN_FEMALE = (
    "Anh", "Ánh", "Châu", "Chi", "Dung", "Giang", "Hà", "Hân", "Hạnh", "Hoa", "Hương", "Lan",
    "Linh", "Mai", "My", "Ngân", "Nhi", "Như", "Oanh", "Phương", "Quỳnh", "Thảo", "Trang",
    "Trinh", "Vy", "Yến",
)
# fmt: on


def random_surname(rng: random.Random) -> str:
    names, weights = zip(*SURNAMES, strict=True)
    return rng.choices(names, weights=weights, k=1)[0]


def random_full_name(rng: random.Random, surname: str | None = None) -> str:
    """Họ + đệm + tên, ví dụ "Nguyễn Văn Khoa". `surname` cho trước thì dùng lại họ đó."""
    male = rng.random() < 0.5
    middle = rng.choice(MIDDLE_MALE if male else MIDDLE_FEMALE)
    given = rng.choice(GIVEN_MALE if male else GIVEN_FEMALE)
    return f"{surname or random_surname(rng)} {middle} {given}"


def random_phone(rng: random.Random) -> str:
    """Số điện thoại KHÔNG hợp lệ: đầu số 0000 không tồn tại, nên không trùng số thật nào."""
    return "0000" + "".join(str(rng.randrange(10)) for _ in range(6))

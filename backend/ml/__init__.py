"""Huấn luyện mô hình ML cảnh báo sớm (Giai đoạn 6). Chạy: `make train` (xem ml/train.py).

Phần phục vụ (nạp mô hình, dự đoán, giải thích) nằm ở app/warning/model.py; đặc trưng dùng chung ở
app/warning/features.py nên huấn luyện và phục vụ không lệch nhau.
"""

import sys
from pathlib import Path

# Thư mục gốc repo: để import được gói data.seed (sinh dữ liệu giả) khi chạy `python -m ml.train`.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

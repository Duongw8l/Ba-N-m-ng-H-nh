"""Học sinh "nhân vật" cho kịch bản demo và học sinh "biên" cho test (D-032).

KHÔNG viết lại công thức Thông tư 22 ở đây. Học sinh biên được tạo bằng cách đặt MỌI đầu điểm của
một môn, cả hai học kỳ, bằng đúng một giá trị. Trung bình có trọng số của các giá trị bằng nhau
luôn bằng chính giá trị đó, nên đúng với mọi hệ số: ĐTB môn học kỳ và cả năm đều bằng giá trị biên.

Mã học sinh: HS + khối (2) + lớp (2) + số thứ tự (3), nên HS1102001 là em thứ nhất lớp 11A2.
Kịch bản chỉ áp dụng khi lớp và số thứ tự đó tồn tại (tham số seed đủ lớn).

Các hằng số 30 buổi, 3,5 ở đây là HÌNH DẠNG của dữ liệu mẫu (nhóm nghỉ nhiều, nhóm điểm thấp), không
phải ngưỡng cảnh báo: không đọc từ `settings` và không đổi khi admin sửa `settings`.
"""

from dataclasses import dataclass
from decimal import Decimal

# Ngưỡng nhóm "nghỉ nhiều" dùng để thống kê chỉ tiêu 5% (không phải ngưỡng cảnh báo của Thông tư).
HEAVY_ABSENCE_MIN = 30
LOW_SCORE_BELOW = Decimal("3.5")


@dataclass(frozen=True)
class StudentScenario:
    full_name: str | None = None  # tên cố định (nhân vật demo)
    absences: int | None = None  # số buổi nghỉ cố định
    flat_subject: str | None = None  # môn mà mọi đầu điểm bằng một giá trị
    flat_score: Decimal | None = None

    @property
    def is_heavy_absence(self) -> bool:
        return self.absences is not None and self.absences >= HEAVY_ABSENCE_MIN

    @property
    def is_low_score(self) -> bool:
        return self.flat_score is not None and self.flat_score < LOW_SCORE_BELOW


SCENARIOS: dict[str, StudentScenario] = {
    # Lớp 11A2, kịch bản demo (DESIGN mục 12): em An nghỉ 38 buổi; một em có môn dưới 3,5.
    "HS1102001": StudentScenario(full_name="Trần Minh An", absences=38),
    "HS1102002": StudentScenario(
        full_name="Lê Hoàng Bảo", flat_subject="Toán", flat_score=Decimal("3.0")
    ),
    # Lớp 12A1, học sinh biên: nghỉ 44, 45, 46 buổi (quanh mức 45); môn Toán đúng 3,4 / 3,5 / 5,0.
    "HS1201001": StudentScenario(absences=44),
    "HS1201002": StudentScenario(absences=45),
    "HS1201003": StudentScenario(absences=46),
    "HS1201004": StudentScenario(flat_subject="Toán", flat_score=Decimal("3.4")),
    "HS1201005": StudentScenario(flat_subject="Toán", flat_score=Decimal("3.5")),
    "HS1201006": StudentScenario(flat_subject="Toán", flat_score=Decimal("5.0")),
}

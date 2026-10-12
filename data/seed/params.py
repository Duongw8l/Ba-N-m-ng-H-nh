"""Tham số của lần chạy seed."""

from dataclasses import dataclass

DEFAULT_SEED = 2026
DEFAULT_CLASSES_PER_GRADE = 3
DEFAULT_CLASS_SIZE = 40

GRADES = (10, 11, 12)

# Tỷ lệ mục tiêu (DESIGN mục 6.2 / PROMPTS Giai đoạn 1). Số lượng là số chính xác
# round(tỷ lệ × tổng số học sinh), không phải xác suất từng em.
HEAVY_ABSENCE_RATE = 0.05  # nghỉ 30-50 buổi
LOW_SCORE_RATE = 0.08  # có ít nhất một môn dưới 3,5


@dataclass(frozen=True)
class SeedParams:
    seed: int = DEFAULT_SEED
    classes_per_grade: int = DEFAULT_CLASSES_PER_GRADE
    class_size: int = DEFAULT_CLASS_SIZE

    def __post_init__(self) -> None:
        if not 1 <= self.classes_per_grade <= 9:
            raise ValueError("classes_per_grade phải từ 1 đến 9 (tên lớp dạng 10A1 đến 10A9).")
        if not 1 <= self.class_size <= 999:
            raise ValueError("class_size phải từ 1 đến 999 (mã học sinh có 3 chữ số thứ tự).")

    @property
    def student_count(self) -> int:
        return len(GRADES) * self.classes_per_grade * self.class_size

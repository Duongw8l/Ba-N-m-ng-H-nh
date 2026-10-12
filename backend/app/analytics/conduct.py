"""Rèn luyện theo kỳ và kết quả CẢ NĂM của rèn luyện và của môn nhận xét (D-049).

Cả năm: dùng bản ghi `year` nếu giáo viên đã nhập; chưa có thì lấy kết quả học kỳ II và đánh dấu
`derived=True` ("suy ra") để không nhầm với kết quả chính thức. Quy tắc kết hợp HK1 và HK2 của
Thông tư (nếu có) chưa kiểm được với văn bản gốc.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.core.enums import CommentResult, ConductLevel, ConductPeriod


@dataclass(frozen=True)
class PeriodConduct:
    level: ConductLevel | None  # None: chưa có dữ liệu
    derived: bool = False  # True: cả năm được suy ra từ học kỳ II


def conduct_for_period(
    records: Mapping[ConductPeriod, ConductLevel], period: ConductPeriod
) -> PeriodConduct:
    """Rèn luyện của một kỳ từ các bản ghi `conduct_results` của học sinh."""
    if period is not ConductPeriod.YEAR:
        return PeriodConduct(records.get(period))
    if ConductPeriod.YEAR in records:
        return PeriodConduct(records[ConductPeriod.YEAR])
    if ConductPeriod.HK2 in records:
        return PeriodConduct(records[ConductPeriod.HK2], derived=True)
    return PeriodConduct(None)


def year_comment_result(semester2: CommentResult | None) -> CommentResult | None:
    """Môn đánh giá bằng nhận xét: kết quả cả năm là kết quả học kỳ II."""
    return semester2

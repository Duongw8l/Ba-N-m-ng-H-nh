"""Môn học theo Chương trình GDPT 2018 cấp THPT và tổ hợp môn lựa chọn của từng lớp (D-031).

Số tiết/năm lấy từ bảng kế hoạch giáo dục cấp THPT (nguồn thứ cấp, cần đối chiếu với Thông tư
32/2018 và 13/2022). Chuyên đề học tập không đưa vào. Mỗi lớp học 8 môn bắt buộc và 4 môn lựa chọn.
Môn của một lớp chính là các dòng teaching_assignments của lớp đó.
"""

from dataclasses import dataclass

from app.core.enums import AssessmentType

SCORE = AssessmentType.SCORE
COMMENT = AssessmentType.COMMENT


@dataclass(frozen=True)
class SubjectSpec:
    code: str  # ASCII, dùng trong email giáo viên
    name: str
    assessment_type: AssessmentType
    periods_per_year: int
    is_elective: bool = False


SUBJECTS: tuple[SubjectSpec, ...] = (
    # 8 môn bắt buộc
    SubjectSpec("van", "Ngữ văn", SCORE, 105),
    SubjectSpec("toan", "Toán", SCORE, 105),
    SubjectSpec("anh", "Tiếng Anh", SCORE, 105),
    SubjectSpec("su", "Lịch sử", SCORE, 52),
    SubjectSpec("gdtc", "Giáo dục thể chất", COMMENT, 70),
    SubjectSpec("gdqp", "Giáo dục quốc phòng và an ninh", SCORE, 35),
    SubjectSpec("hdtn", "Hoạt động trải nghiệm, hướng nghiệp", COMMENT, 105),
    SubjectSpec("gddp", "Nội dung giáo dục địa phương", COMMENT, 35),
    # 9 môn lựa chọn (Âm nhạc và Mĩ thuật thuộc nhóm Nghệ thuật, đánh giá bằng nhận xét)
    SubjectSpec("dia", "Địa lí", SCORE, 70, is_elective=True),
    SubjectSpec("gdktpl", "Giáo dục kinh tế và pháp luật", SCORE, 70, is_elective=True),
    SubjectSpec("ly", "Vật lí", SCORE, 70, is_elective=True),
    SubjectSpec("hoa", "Hóa học", SCORE, 70, is_elective=True),
    SubjectSpec("sinh", "Sinh học", SCORE, 70, is_elective=True),
    SubjectSpec("cn", "Công nghệ", SCORE, 70, is_elective=True),
    SubjectSpec("tin", "Tin học", SCORE, 70, is_elective=True),
    SubjectSpec("nhac", "Âm nhạc", COMMENT, 70, is_elective=True),
    SubjectSpec("mt", "Mĩ thuật", COMMENT, 70, is_elective=True),
)

SUBJECT_BY_NAME: dict[str, SubjectSpec] = {subject.name: subject for subject in SUBJECTS}
COMPULSORY: tuple[SubjectSpec, ...] = tuple(s for s in SUBJECTS if not s.is_elective)

# Tổ hợp 4 môn lựa chọn (minh hoạ): ba tổ hợp dùng chung cho mọi khối, đủ 9 môn lựa chọn, mỗi tổ hợp
# có ít nhất một môn ở mỗi nhóm KHXH, KHTN, Công nghệ - Nghệ thuật. Lớp thứ 4 trở lên quay vòng.
ELECTIVE_COMBOS: tuple[tuple[str, str, str, str], ...] = (
    ("Vật lí", "Hóa học", "Địa lí", "Tin học"),
    ("Hóa học", "Sinh học", "Giáo dục kinh tế và pháp luật", "Công nghệ"),
    ("Sinh học", "Giáo dục kinh tế và pháp luật", "Âm nhạc", "Mĩ thuật"),
)


def class_subjects(class_index: int) -> tuple[SubjectSpec, ...]:
    """12 môn của lớp thứ `class_index` (đếm từ 1) trong khối: 8 bắt buộc + 4 lựa chọn."""
    combo = ELECTIVE_COMBOS[(class_index - 1) % len(ELECTIVE_COMBOS)]
    return COMPULSORY + tuple(SUBJECT_BY_NAME[name] for name in combo)

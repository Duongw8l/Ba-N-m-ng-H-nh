"""Giá trị lưu trong DB của các cột liệt kê: mã tiếng Anh ổn định (D-025).

Nhãn tiếng Việt hiển thị cho người dùng nằm riêng ở `app/core/labels.py`.
"""

from enum import StrEnum


class UserRole(StrEnum):
    TEACHER = "teacher"  # GVBM hoặc GVCN, suy ra từ phân công, không phải cột riêng
    PRINCIPAL = "principal"  # Ban giám hiệu
    ADMIN = "admin"


class AssessmentType(StrEnum):
    SCORE = "score"
    COMMENT = "comment"


class AssessmentKind(StrEnum):
    TX = "tx"  # đánh giá thường xuyên
    GK = "gk"  # giữa kỳ
    CK = "ck"  # cuối kỳ


class CommentResult(StrEnum):
    PASS = "pass"  # Đạt
    FAIL = "fail"  # Chưa đạt


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT_EXCUSED = "absent_excused"
    ABSENT_UNEXCUSED = "absent_unexcused"
    LATE = "late"


# Hai trạng thái tính là 1 buổi nghỉ (D-028). "late" và "present" không tính.
ABSENT_STATUSES = (AttendanceStatus.ABSENT_EXCUSED, AttendanceStatus.ABSENT_UNEXCUSED)


class ConductPeriod(StrEnum):
    HK1 = "hk1"
    HK2 = "hk2"
    YEAR = "year"  # DESIGN có "cả năm"; kết quả cả năm là luật Thông tư 22, seed không sinh


class ConductLevel(StrEnum):
    GOOD = "good"  # Tốt
    FAIR = "fair"  # Khá
    PASS = "pass"  # Đạt
    FAIL = "fail"  # Chưa đạt


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TeacherStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"  # đã trao đổi với học sinh / phụ huynh
    FALSE_ALARM = "false_alarm"  # báo nhầm


class ReportScope(StrEnum):
    STUDENT = "student"
    CLASS = "class"
    GRADE = "grade"


class ReportType(StrEnum):
    SCHOOL_RECORD = "school_record"  # học bạ
    CONTACT_SLIP = "contact_slip"  # phiếu liên lạc
    REPORT = "report"  # báo cáo


class ReportStatus(StrEnum):
    DRAFT = "draft"  # mọi bản AI sinh ra bắt đầu ở đây (nguyên tắc 6)
    APPROVED = "approved"


class AuditAction(StrEnum):
    VIEW_CLASS_STUDENTS = "view_class_students"  # mở danh sách học sinh của một lớp
    VIEW_STUDENT_PROFILE = "view_student_profile"  # mở hồ sơ một học sinh (màn hình ở Giai đoạn 5)

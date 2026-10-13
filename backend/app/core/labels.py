"""Nhãn tiếng Việt cho các giá trị liệt kê (D-025): đổi cách gọi trên giao diện chỉ sửa ở đây.

Khoá là lớp enum rồi mới tới thành viên, vì StrEnum so sánh bằng giá trị chuỗi nên hai enum khác
nhau có cùng giá trị (ví dụ "pass") sẽ đè nhau nếu gộp chung một dict.
"""

from enum import StrEnum

from app.core.enums import (
    AssessmentKind,
    AssessmentType,
    AssistantFeedback,
    AttendanceStatus,
    AuditAction,
    CommentResult,
    ConductLevel,
    ConductPeriod,
    ImportKind,
    ImportStatus,
    RegulationStatus,
    ReportScope,
    ReportStatus,
    ReportType,
    RiskLevel,
    TeacherStatus,
    UserRole,
)

LABELS_VI: dict[type[StrEnum], dict[StrEnum, str]] = {
    UserRole: {
        UserRole.TEACHER: "Giáo viên",
        UserRole.PRINCIPAL: "Ban giám hiệu",
        UserRole.ADMIN: "Quản trị viên",
    },
    AssessmentType: {
        AssessmentType.SCORE: "Tính điểm",
        AssessmentType.COMMENT: "Nhận xét",
    },
    AssessmentKind: {
        AssessmentKind.TX: "Thường xuyên",
        AssessmentKind.GK: "Giữa kỳ",
        AssessmentKind.CK: "Cuối kỳ",
    },
    CommentResult: {
        CommentResult.PASS: "Đạt",
        CommentResult.FAIL: "Chưa đạt",
    },
    AttendanceStatus: {
        AttendanceStatus.PRESENT: "Có mặt",
        AttendanceStatus.ABSENT_EXCUSED: "Nghỉ có phép",
        AttendanceStatus.ABSENT_UNEXCUSED: "Nghỉ không phép",
        AttendanceStatus.LATE: "Muộn",
    },
    ConductPeriod: {
        ConductPeriod.HK1: "Học kỳ I",
        ConductPeriod.HK2: "Học kỳ II",
        ConductPeriod.YEAR: "Cả năm",
    },
    ConductLevel: {
        ConductLevel.GOOD: "Tốt",
        ConductLevel.FAIR: "Khá",
        ConductLevel.PASS: "Đạt",
        ConductLevel.FAIL: "Chưa đạt",
    },
    RiskLevel: {
        RiskLevel.HIGH: "Cao",
        RiskLevel.MEDIUM: "Trung bình",
        RiskLevel.LOW: "Thấp",
    },
    TeacherStatus: {
        TeacherStatus.NEW: "Chưa xử lý",
        TeacherStatus.CONTACTED: "Đã trao đổi",
        TeacherStatus.FALSE_ALARM: "Báo nhầm",
    },
    ReportScope: {
        ReportScope.STUDENT: "Học sinh",
        ReportScope.CLASS: "Lớp",
        ReportScope.GRADE: "Khối",
    },
    ReportType: {
        ReportType.SCHOOL_RECORD: "Học bạ",
        ReportType.CONTACT_SLIP: "Phiếu liên lạc",
        ReportType.REPORT: "Báo cáo",
    },
    ReportStatus: {
        ReportStatus.DRAFT: "Bản nháp",
        ReportStatus.APPROVED: "Đã duyệt",
    },
    AuditAction: {
        AuditAction.VIEW_CLASS_STUDENTS: "Xem danh sách học sinh của lớp",
        AuditAction.VIEW_STUDENT_PROFILE: "Xem hồ sơ học sinh",
        AuditAction.VIEW_CLASS_DASHBOARD: "Xem dashboard lớp",
        AuditAction.VIEW_SUBJECT_SCORES: "Xem bảng điểm môn",
        AuditAction.IMPORT_CONFIRM: "Xác nhận nhập dữ liệu từ tệp",
        AuditAction.VIEW_CLASS_ALERTS: "Xem cảnh báo sớm của lớp",
        AuditAction.VIEW_SCHOOL_ALERTS: "Xem cảnh báo mức cao toàn trường",
        AuditAction.UPDATE_ALERT: "Ghi nhận cảnh báo sớm",
        AuditAction.UPLOAD_REGULATION: "Tải văn bản quy định lên",
        AuditAction.UPDATE_REGULATION: "Đổi hiệu lực văn bản quy định",
        AuditAction.CREATE_USER: "Tạo tài khoản",
        AuditAction.UPDATE_USER: "Sửa tài khoản",
        AuditAction.RESET_USER_PASSWORD: "Đặt lại mật khẩu",
        AuditAction.CHANGE_PASSWORD: "Đổi mật khẩu",
        AuditAction.UPDATE_SCHOOL_YEAR: "Tạo hoặc sửa năm học",
        AuditAction.CREATE_CLASS: "Tạo lớp",
        AuditAction.UPDATE_CLASS: "Sửa lớp",
        AuditAction.DELETE_CLASS: "Xoá lớp",
        AuditAction.SET_ASSIGNMENT: "Phân công giảng dạy",
        AuditAction.REMOVE_ASSIGNMENT: "Gỡ phân công giảng dạy",
        AuditAction.REMOVE_CLASS_STUDENT: "Gỡ học sinh khỏi lớp",
    },
    ImportKind: {
        ImportKind.ASSESSMENTS: "Điểm",
        ImportKind.ATTENDANCE: "Điểm danh",
        ImportKind.CONDUCT: "Rèn luyện",
        ImportKind.ROSTER: "Danh sách học sinh",
    },
    RegulationStatus: {
        RegulationStatus.ACTIVE: "Còn hiệu lực",
        RegulationStatus.EXPIRED: "Hết hiệu lực",
    },
    AssistantFeedback: {
        AssistantFeedback.CORRECT: "Đúng",
        AssistantFeedback.INCORRECT: "Sai",
    },
    ImportStatus: {
        ImportStatus.PREVIEWED: "Đã xem trước",
        ImportStatus.CONFIRMED: "Đã xác nhận",
    },
}


def label_vi(member: StrEnum) -> str:
    """Nhãn tiếng Việt của một giá trị liệt kê."""
    return LABELS_VI[type(member)][member]

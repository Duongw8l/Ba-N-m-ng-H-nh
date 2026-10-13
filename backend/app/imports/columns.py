"""Trường cần nhập, bí danh tên cột và ánh xạ cột của tệp vào trường (D-057, D-062).

Tên cột được chuẩn hoá (bỏ dấu, chữ thường, bỏ khoảng trắng và dấu câu) rồi khớp với bí danh, nên
"Mã HS", "mã học sinh" và "MA_HS" là một. Thứ tự ưu tiên khi ánh xạ: lựa chọn tay của người dùng,
rồi mẫu đã lưu, rồi tự khớp theo bí danh.
"""

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.enums import ImportKind


def normalize_header(text: str) -> str:
    """ "ĐĐGtx 1" thành "ddgtx1"; "Giữa kỳ" thành "giuaky"."""
    folded = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in folded if ch.isalnum() and not unicodedata.combining(ch))


@dataclass(frozen=True)
class FieldSpec:
    name: str  # tên trường trong code và trong ánh xạ
    label: str  # tên hiển thị tiếng Việt
    aliases: frozenset[str]  # các tên cột đã chuẩn hoá được nhận
    required: bool = True


STUDENT_CODE = FieldSpec(
    "student_code",
    "Mã học sinh",
    frozenset({"mahs", "mahocsinh", "mshs", "masohs", "masohocsinh", "studentcode", "ma"}),
)
FULL_NAME = FieldSpec(
    "full_name",
    "Họ và tên",
    frozenset({"hovaten", "hoten", "tenhocsinh", "hotenhocsinh", "fullname", "ten"}),
    required=False,
)


def _tx_field(index: int, required: bool) -> FieldSpec:
    aliases = {f"{prefix}{index}" for prefix in ("tx", "dgtx", "ddgtx", "kttx", "diemtx")}
    aliases |= {f"thuongxuyen{index}", f"diemthuongxuyen{index}", f"danhgiathuongxuyen{index}"}
    return FieldSpec(f"tx{index}", f"Điểm thường xuyên {index}", frozenset(aliases), required)


def _midterm(required: bool) -> FieldSpec:
    aliases = {"gk", "dggk", "ddggk", "ktgk", "diemgk", "giuaky", "giuaki", "diemgiuaky"}
    aliases |= {"kiemtragiuaky", "kiemtragiuaki"}
    return FieldSpec("midterm", "Điểm giữa kỳ", frozenset(aliases), required)


def _final(required: bool) -> FieldSpec:
    aliases = {"ck", "dgck", "ddgck", "ktck", "diemck", "cuoiky", "cuoiki", "diemcuoiky"}
    aliases |= {"kiemtracuoiky", "kiemtracuoiki"}
    return FieldSpec("final", "Điểm cuối kỳ", frozenset(aliases), required)


def score_fields(tx_required: int, *, allow_partial: bool) -> list[FieldSpec]:
    """Môn điểm số: mã học sinh, N điểm thường xuyên, giữa kỳ, cuối kỳ (N theo số tiết của môn)."""
    required = not allow_partial
    return [
        STUDENT_CODE,
        FULL_NAME,
        *(_tx_field(i, required) for i in range(1, tx_required + 1)),
        _midterm(required),
        _final(required),
    ]


def comment_subject_fields(*, allow_partial: bool) -> list[FieldSpec]:
    result = FieldSpec(
        "comment_result",
        "Nhận xét (Đạt / Chưa đạt)",
        frozenset({"nhanxet", "ketqua", "danhgia", "datchuadat", "ketquadanhgia"}),
        required=not allow_partial,
    )
    return [STUDENT_CODE, FULL_NAME, result]


ATTENDANCE_FIELDS = [
    STUDENT_CODE,
    FULL_NAME,
    FieldSpec(
        "date",
        "Ngày",
        frozenset({"ngay", "ngayhoc", "ngaydiemdanh", "date", "thoigian"}),
    ),
    FieldSpec(
        "status",
        "Trạng thái",
        frozenset({"trangthai", "diemdanh", "tinhtrang", "status", "kyhieu"}),
    ),
]

CONDUCT_FIELDS = [
    STUDENT_CODE,
    FULL_NAME,
    FieldSpec(
        "level",
        "Mức rèn luyện",
        frozenset(
            {"xeploai", "muc", "renluyen", "ketquarenluyen", "xeploairenluyen", "hanhkiem", "level"}
        ),
    ),
    FieldSpec(
        "comment",
        "Nhận xét",
        frozenset({"nhanxet", "ghichu", "comment", "nhanxetrenluyen"}),
        required=False,
    ),
]


# Nhập danh sách học sinh của một lớp (Admin, D-100). Họ tên bắt buộc (khác các loại nhập khác, nơi
# học sinh đã có sẵn trong hệ thống nên cột tên chỉ để đối chiếu).
ROSTER_FIELDS = [
    STUDENT_CODE,
    FieldSpec(
        "full_name",
        "Họ và tên",
        frozenset({"hovaten", "hoten", "tenhocsinh", "hotenhocsinh", "fullname", "ten"}),
    ),
    FieldSpec(
        "date_of_birth",
        "Ngày sinh",
        frozenset({"ngaysinh", "ns", "dateofbirth", "dob", "sinhngay", "ngaythangnamsinh"}),
        required=False,
    ),
    FieldSpec(
        "guardian_name",
        "Họ tên phụ huynh",
        frozenset(
            {
                "hotenphuhuynh",
                "tenphuhuynh",
                "phuhuynh",
                "nguoigiamho",
                "hotennguoigiamho",
                "guardian",
                "guardianname",
            }
        ),
        required=False,
    ),
    FieldSpec(
        "guardian_phone",
        "Số điện thoại phụ huynh",
        frozenset(
            {
                "sdt",
                "sodienthoai",
                "dienthoai",
                "sdtphuhuynh",
                "sodienthoaiphuhuynh",
                "dienthoaiphuhuynh",
                "guardianphone",
                "phone",
                "sodt",
            }
        ),
        required=False,
    ),
]


@dataclass(frozen=True)
class MappingResolution:
    mapping: dict[str, str | None]  # trường -> tên cột trong tệp (None: chưa có)
    missing_required: list[str]  # nhãn các trường bắt buộc còn thiếu
    ignored_columns: list[str]  # cột của tệp không dùng
    notes: list[str]  # ví dụ: ánh xạ trỏ tới cột không có trong tệp


def _find_header(headers: Sequence[str], wanted: str) -> str | None:
    """Tên cột trong tệp khớp `wanted`: ưu tiên khớp nguyên văn, rồi khớp sau chuẩn hoá."""
    if wanted in headers:
        return wanted
    target = normalize_header(wanted)
    if not target:
        return None
    return next((h for h in headers if normalize_header(h) == target), None)


def auto_map(headers: Sequence[str], fields: Sequence[FieldSpec]) -> dict[str, str | None]:
    """Tự khớp theo bí danh; mỗi cột của tệp chỉ gán cho tối đa một trường."""
    used: set[int] = set()
    result: dict[str, str | None] = {}
    for spec in fields:
        match = next(
            (
                index
                for index, header in enumerate(headers)
                if index not in used and header and normalize_header(header) in spec.aliases
            ),
            None,
        )
        result[spec.name] = None if match is None else headers[match]
        if match is not None:
            used.add(match)
    return result


def resolve_mapping(
    headers: Sequence[str],
    fields: Sequence[FieldSpec],
    *,
    template: Mapping[str, str | None] | None = None,
    explicit: Mapping[str, str | None] | None = None,
) -> MappingResolution:
    mapping = auto_map(headers, fields)
    notes: list[str] = []
    known = {spec.name for spec in fields}
    for source, label in ((template, "mẫu đã lưu"), (explicit, "lựa chọn của bạn")):
        for field, wanted in (source or {}).items():
            if field not in known:
                notes.append(
                    f"Bỏ qua trường '{field}' trong {label}: loại nhập này không có trường đó."
                )
            elif not wanted:
                mapping[field] = None  # bỏ ánh xạ chủ động
            elif (header := _find_header(headers, wanted)) is None:
                notes.append(f"Cột '{wanted}' trong {label} không có trong tệp.")
            else:
                mapping[field] = header

    used = {value for value in mapping.values() if value}
    return MappingResolution(
        mapping=mapping,
        missing_required=[
            spec.label for spec in fields if spec.required and not mapping[spec.name]
        ],
        ignored_columns=[h for h in headers if h and h not in used],
        notes=notes,
    )


def detect_header_line(
    grid: Sequence[Sequence[str]], fields: Sequence[FieldSpec], scan_rows: int = 15
) -> int:
    """Dòng tiêu đề (đếm từ 1): dòng trong `scan_rows` dòng đầu khớp được nhiều trường nhất.

    Sổ điểm xuất ra thường có vài dòng tiêu đề lớn phía trên. Không dòng nào khớp thì lấy dòng đầu.
    """
    best_line, best_score = 1, 0
    for line, row in enumerate(grid[:scan_rows], start=1):
        score = len([value for value in auto_map(list(row), fields).values() if value is not None])
        if score > best_score:
            best_line, best_score = line, score
    return best_line


def fields_for(
    kind: ImportKind, *, tx_required: int = 0, is_comment_subject: bool = False, allow_partial: bool
) -> list[FieldSpec]:
    if kind is ImportKind.ATTENDANCE:
        return ATTENDANCE_FIELDS
    if kind is ImportKind.CONDUCT:
        return CONDUCT_FIELDS
    if kind is ImportKind.ROSTER:
        return ROSTER_FIELDS
    if is_comment_subject:
        return comment_subject_fields(allow_partial=allow_partial)
    return score_fields(tx_required, allow_partial=allow_partial)

"""Nhập danh sách học sinh của một lớp (Admin, D-100): kiểm từng dòng và ghi.

`validate_roster` thuần (không đụng DB) như các hàm trong validation.py: nhận sẵn các lớp mà mỗi
mã học sinh đang thuộc. Bản xem trước KHÔNG trả giá trị cũ của học sinh đã có (Admin không xem dữ
liệu học sinh, D-039): chỉ báo dòng sẽ thêm vào lớp, dòng đã ở trong lớp sẽ được cập nhật theo tệp,
hoặc dòng lỗi.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import Date as SqlDate
from sqlalchemy import bindparam, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.classes.models import ClassStudent, SchoolClass, Student
from app.imports.models import ImportJob
from app.imports.parsing import RawTable
from app.imports.validation import (
    RowResult,
    _cell,
    _check_duplicate,
    _header,
    _new_result,
    column_index,
)
from app.imports.values import CellError, parse_date, parse_phone

MAX_CODE_LENGTH = 20  # khớp students.student_code
MAX_NAME_LENGTH = 100  # khớp students.full_name và guardian_name
CODE_PATTERN = re.compile(r"[A-Za-z0-9._\-]+")
MIN_AGE, MAX_AGE = 13, 22  # ngoài khoảng này chỉ cảnh báo: học sinh THPT thường 15 đến 19 tuổi


class RosterConflict(Exception):
    """Từ lúc xem trước, một học sinh trong danh sách đã vào lớp khác: không ghi gì (409)."""


Memberships = Mapping[str, Sequence[tuple[int, str]]]  # mã viết hoa -> [(class_id, tên lớp)]


def codes_in(table: RawTable, mapping: Mapping[str, str | None]) -> list[str]:
    """Các mã học sinh (viết hoa) có trong tệp, để tra lớp đang thuộc."""
    index = column_index(table.headers, mapping)
    codes = (_cell(row, index, "student_code").upper() for row in table.rows)
    return sorted({code for code in codes if code})


def _squash(text: str) -> str:
    return " ".join(text.split())


def _age(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def validate_roster(
    table: RawTable,
    mapping: Mapping[str, str | None],
    *,
    class_id: int,
    memberships: Memberships,
    today: date | None = None,
) -> list[RowResult]:
    today = today or date.today()
    index = column_index(table.headers, mapping)
    code_column = _header(table.headers, index, "student_code", "Mã học sinh")
    name_column = _header(table.headers, index, "full_name", "Họ và tên")
    dob_column = _header(table.headers, index, "date_of_birth", "Ngày sinh")
    guardian_column = _header(table.headers, index, "guardian_name", "Họ tên phụ huynh")
    phone_column = _header(table.headers, index, "guardian_phone", "Số điện thoại phụ huynh")
    seen: dict[str, int] = {}
    results: list[RowResult] = []
    for row in table.rows:
        result = _new_result(row, index)
        code = result.student_code.upper()
        result.student_code = code
        name = _squash(_cell(row, index, "full_name"))
        result.full_name = name or None  # họ tên trong TỆP (không đọc từ hệ thống)

        if not code:
            result.error(code_column, "Thiếu mã học sinh.")
        elif len(code) > MAX_CODE_LENGTH or not CODE_PATTERN.fullmatch(code):
            result.error(
                code_column,
                f"Mã học sinh '{code}' không hợp lệ (tối đa {MAX_CODE_LENGTH} ký tự, "
                "chỉ gồm chữ, số, dấu chấm, gạch ngang, gạch dưới).",
            )
        else:
            _check_duplicate(result, seen, code, code_column, "Mã học sinh")
            others = [label for id_, label in memberships.get(code, ()) if id_ != class_id]
            if others:
                result.error(code_column, f"Mã học sinh '{code}' đã thuộc lớp {others[0]}.")

        if not name:
            result.error(name_column, "Thiếu họ và tên.")
        elif len(name) > MAX_NAME_LENGTH:
            result.error(name_column, f"Họ và tên dài quá {MAX_NAME_LENGTH} ký tự.")

        birth: date | None = None
        dob_text = _cell(row, index, "date_of_birth")
        if dob_text:
            try:
                birth = parse_date(dob_text)
            except CellError as error:
                result.error(dob_column, str(error))
            else:
                if birth > today:
                    result.error(dob_column, f"Ngày sinh {dob_text} ở tương lai.")
                    birth = None
                elif not MIN_AGE <= _age(birth, today) <= MAX_AGE:
                    result.warn(
                        dob_column,
                        f"Ngày sinh {dob_text} cho tuổi {_age(birth, today)}, "
                        "bất thường với học sinh THPT.",
                    )

        guardian = _squash(_cell(row, index, "guardian_name"))
        if len(guardian) > MAX_NAME_LENGTH:
            result.error(guardian_column, f"Họ tên phụ huynh dài quá {MAX_NAME_LENGTH} ký tự.")

        phone: str | None = None
        phone_text = _cell(row, index, "guardian_phone")
        if phone_text:
            try:
                phone, padded = parse_phone(phone_text)
            except CellError as error:
                result.error(phone_column, str(error))
            else:
                if padded:
                    result.warn(
                        phone_column,
                        f"Đã thêm số 0 đầu cho '{phone_text}' (Excel hay làm mất số 0): {phone}.",
                    )

        result.values["date_of_birth"] = None if birth is None else birth.isoformat()
        result.values["guardian_name"] = guardian or None
        result.values["guardian_phone"] = phone
        if result.status != "error":
            result.records.append(
                {
                    "student_code": code,
                    "full_name": name,
                    "date_of_birth": result.values["date_of_birth"],
                    "guardian_name": guardian or None,
                    "guardian_phone": phone,
                }
            )
            if any(id_ == class_id for id_, _ in memberships.get(code, ())):
                result.changed_records += 1  # đã ở trong lớp: cập nhật thông tin theo tệp
            else:
                result.new_records += 1  # thêm vào lớp (học sinh mới, hoặc đã có hồ sơ chưa có lớp)
        results.append(result.finish())
    return results


def class_memberships(session: Session, codes: Sequence[str]) -> dict[str, list[tuple[int, str]]]:
    """Với mỗi mã (viết hoa) đã có trong hệ thống: các lớp em đang thuộc. Chỉ đọc."""
    if not codes:
        return {}
    rows = session.execute(
        select(Student.student_code, SchoolClass.id, SchoolClass.name)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
        .where(func.upper(Student.student_code).in_(list(codes)))
    )
    result: dict[str, list[tuple[int, str]]] = {}
    for code, class_id, class_name in rows:
        result.setdefault(code.upper(), []).append((class_id, class_name))
    return result


def _date_of(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def write_roster(session: Session, job: ImportJob) -> tuple[int, int]:
    """Ghi danh sách vào lớp; trả (số học sinh được thêm vào lớp, số học sinh đã ở lớp được sửa).

    Học sinh đã có hồ sơ (so mã không phân biệt hoa thường) được cập nhật, chưa có thì tạo. Ô trống
    trong tệp KHÔNG xoá thông tin có sẵn. Sau đó gắn vào lớp, bỏ qua nếu đã gắn.
    """
    records = job.rows
    if not records:
        return 0, 0
    codes = [record["student_code"] for record in records]
    existing = {
        code.upper(): student_id
        for student_id, code in session.execute(
            select(Student.id, Student.student_code).where(
                func.upper(Student.student_code).in_(codes)
            )
        )
    }
    if existing:
        elsewhere = session.scalar(
            select(ClassStudent.id)
            .where(
                ClassStudent.student_id.in_(list(existing.values())),
                ClassStudent.class_id != job.class_id,
            )
            .limit(1)
        )
        if elsewhere is not None:
            raise RosterConflict
    updates = [
        {
            "sid": existing[r["student_code"]],
            "new_name": r["full_name"],
            "new_dob": _date_of(r["date_of_birth"]),
            "new_guardian": r["guardian_name"],
            "new_phone": r["guardian_phone"],
        }
        for r in records
        if r["student_code"] in existing
    ]
    if updates:
        table = Student.__table__  # Core, không qua ORM: executemany theo bindparam
        session.execute(
            update(table)
            .where(table.c.id == bindparam("sid"))
            .values(
                full_name=bindparam("new_name"),
                date_of_birth=func.coalesce(
                    bindparam("new_dob", type_=SqlDate()), table.c.date_of_birth
                ),
                guardian_name=func.coalesce(bindparam("new_guardian"), table.c.guardian_name),
                guardian_phone=func.coalesce(bindparam("new_phone"), table.c.guardian_phone),
            ),
            updates,
        )
    new_rows = [
        {
            "student_code": r["student_code"],
            "full_name": r["full_name"],
            "date_of_birth": _date_of(r["date_of_birth"]),
            "guardian_name": r["guardian_name"],
            "guardian_phone": r["guardian_phone"],
        }
        for r in records
        if r["student_code"] not in existing
    ]
    if new_rows:
        for student_id, code in session.execute(
            insert(Student).returning(Student.id, Student.student_code), new_rows
        ):
            existing[code.upper()] = student_id
    linked = session.execute(
        pg_insert(ClassStudent)
        .on_conflict_do_nothing(index_elements=["class_id", "student_id"])
        .returning(ClassStudent.id),
        [{"class_id": job.class_id, "student_id": existing[code]} for code in codes],
    ).all()
    added = len(linked)
    return added, len(records) - added

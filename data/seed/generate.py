"""Sinh dữ liệu giả lập trong bộ nhớ: hàm thuần, không đụng DB, cùng tham số thì cùng kết quả.

Mỗi học sinh có các bộ sinh số ngẫu nhiên riêng (hạt giống = seed + mã học sinh + mục đích), nên kết
quả của một em không phụ thuộc thứ tự sinh. Chỉ tiêu theo nhóm (nghỉ nhiều, môn dưới 3,5) dùng một
bộ sinh riêng và là số chính xác `round(tỷ lệ × tổng)`.

KHÔNG có công thức Thông tư 22 ở đây: điểm của học sinh thường đều ≥ 4,0, còn học sinh "môn dưới
3,5" và học sinh biên có mọi đầu điểm của môn đó bằng đúng một giá trị (xem scenarios.py).
"""

import itertools
import math
import random
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.analytics.thresholds import required_regular_count
from app.core.enums import (
    AssessmentKind,
    AssessmentType,
    AttendanceStatus,
    CommentResult,
    ConductLevel,
    ConductPeriod,
    UserRole,
)
from data.seed.curriculum import SUBJECTS, SubjectSpec, class_subjects
from data.seed.params import GRADES, HEAVY_ABSENCE_RATE, LOW_SCORE_RATE, SeedParams
from data.seed.people import EMAIL_DOMAIN, random_full_name, random_phone
from data.seed.scenarios import SCENARIOS, StudentScenario
from data.seed.school_calendar import (
    SCHOOL_YEAR_END,
    SCHOOL_YEAR_NAME,
    SCHOOL_YEAR_START,
    SchoolDay,
    school_days,
)

Row = dict[str, Any]
# Tên bảng -> các dòng, theo thứ tự phụ thuộc khoá ngoại (bảng cha trước bảng con).
TableRows = dict[str, list[Row]]

MIN_SCORE_TENTHS = 40  # học sinh thường: mọi đầu điểm từ 4,0 (nên không bao giờ dưới 3,5)
MAX_SCORE_TENTHS = 100
EXAM_COMPULSORY = ("Ngữ văn", "Toán")  # môn thi tốt nghiệp bắt buộc, cộng 2 môn tự chọn
EXAM_EXCLUDED = ("Giáo dục quốc phòng và an ninh",)  # không phải môn thi tốt nghiệp


@dataclass
class _Student:
    id: int
    code: str
    grade: int
    class_index: int
    class_id: int
    ability: float
    scenario: StudentScenario | None
    absences: int | None = None  # None: sinh theo phân bố thường
    flat: tuple[str, Decimal] | None = None  # (tên môn, giá trị của mọi đầu điểm môn đó)


def _rng(seed: int, *parts: object) -> random.Random:
    """Bộ sinh số riêng, tất định theo (seed, ...). random.Random(str) dùng SHA-512 nên ổn định."""
    return random.Random(":".join(str(part) for part in (seed, *parts)))


def _score(tenths: int) -> Decimal:
    return Decimal(tenths).scaleb(-1)  # 65 -> Decimal("6.5")


def generate(
    params: SeedParams,
    rules: Sequence[Mapping[str, Any]],
    password_hash: str,
) -> TableRows:
    """Toàn bộ dữ liệu giả lập. `rules` là settings.regular_assessment_count."""
    subject_ids = {subject.name: index for index, subject in enumerate(SUBJECTS, start=1)}
    users, subject_teachers, homeroom_teachers = _build_staff(params, password_hash)

    class_rows: list[Row] = []
    student_rows: list[Row] = []
    class_student_rows: list[Row] = []
    assignment_rows: list[Row] = []
    students: list[_Student] = []

    for grade in GRADES:
        for class_index in range(1, params.classes_per_grade + 1):
            class_id = len(class_rows) + 1
            class_rows.append(
                {
                    "id": class_id,
                    "school_year_id": 1,
                    "grade_level": grade,
                    "name": f"{grade}A{class_index}",
                    "homeroom_teacher_id": homeroom_teachers[(grade, class_index)],
                }
            )
            for subject in class_subjects(class_index):
                assignment_rows.append(
                    {
                        "id": len(assignment_rows) + 1,
                        "class_id": class_id,
                        "subject_id": subject_ids[subject.name],
                        "teacher_id": subject_teachers[(subject.name, grade)],
                    }
                )
            for number in range(1, params.class_size + 1):
                student = _new_student(
                    params, len(students) + 1, grade, class_index, class_id, number
                )
                students.append(student)
                student_rows.append(_student_row(params, student))
                class_student_rows.append(
                    {"id": student.id, "class_id": class_id, "student_id": student.id}
                )

    _plan_special_groups(params, students)

    days = school_days()
    assessment_ids = itertools.count(1)
    assessment_rows: list[Row] = []
    attendance_rows: list[Row] = []
    conduct_rows: list[Row] = []
    exam_rows: list[Row] = []
    attendance_first_id = 1  # đếm theo số ngày học, không theo số dòng còn lại sau khi bỏ tháng
    for student in students:
        subjects = class_subjects(student.class_index)
        if student.absences is None:
            student.absences = _normal_absences(params, student)
        assessment_rows.extend(
            _assessments(params, student, subjects, subject_ids, rules, assessment_ids)
        )
        attendance_rows.extend(
            row
            for row in _attendance(params, student, days, attendance_first_id)
            if not _is_held_out(params, row["date"])
        )
        attendance_first_id += len(days)
        conduct_rows.extend(_conduct(params, student, len(conduct_rows) + 1))
        if student.grade == 12:
            exam_rows.extend(
                _exam_registrations(params, student, subjects, subject_ids, len(exam_rows) + 1)
            )

    return {
        "school_years": [
            {
                "id": 1,
                "name": SCHOOL_YEAR_NAME,
                "start_date": SCHOOL_YEAR_START,
                "end_date": SCHOOL_YEAR_END,
            }
        ],
        "subjects": [
            {
                "id": subject_ids[subject.name],
                "name": subject.name,
                "assessment_type": subject.assessment_type,
                "periods_per_year": subject.periods_per_year,
                "is_elective": subject.is_elective,
            }
            for subject in SUBJECTS
        ],
        "users": users,
        "classes": class_rows,
        "students": student_rows,
        "class_students": class_student_rows,
        "teaching_assignments": assignment_rows,
        "assessments": assessment_rows,
        "attendance": attendance_rows,
        "conduct_results": conduct_rows,
        "exam_registrations": exam_rows,
    }


# --- Giáo viên và tài khoản -------------------------------------------------------------------


def _build_staff(
    params: SeedParams, password_hash: str
) -> tuple[list[Row], dict[tuple[str, int], int], dict[tuple[int, int], int]]:
    """Admin, BGH, giáo viên bộ môn (một người cho mỗi cặp môn-khối), giáo viên chủ nhiệm.

    GVCN của lớp xA1 mỗi khối cũng là GV Toán của khối đó: vừa chủ nhiệm vừa dạy bộ môn, có cả lớp
    khác ngoài lớp mình, để test quyền cộng dồn (Giai đoạn 2). Các lớp còn lại có GVCN riêng.
    """
    rng = _rng(params.seed, "staff")
    users: list[Row] = []

    def add_user(email: str, full_name: str, role: UserRole) -> int:
        user_id = len(users) + 1
        users.append(
            {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
            }
        )
        return user_id

    add_user(f"admin@{EMAIL_DOMAIN}", "Quản trị viên", UserRole.ADMIN)
    for number in (1, 2):
        add_user(f"bgh{number}@{EMAIL_DOMAIN}", random_full_name(rng), UserRole.PRINCIPAL)

    subject_teachers: dict[tuple[str, int], int] = {}
    for subject in SUBJECTS:
        taught = any(
            subject in class_subjects(index) for index in range(1, params.classes_per_grade + 1)
        )
        if not taught:
            continue
        for grade in GRADES:
            subject_teachers[(subject.name, grade)] = add_user(
                f"gv.{subject.code}.{grade}@{EMAIL_DOMAIN}", random_full_name(rng), UserRole.TEACHER
            )

    homeroom_teachers: dict[tuple[int, int], int] = {}
    for grade in GRADES:
        for index in range(1, params.classes_per_grade + 1):
            if index == 1:
                homeroom_teachers[(grade, index)] = subject_teachers[("Toán", grade)]
            else:
                homeroom_teachers[(grade, index)] = add_user(
                    f"gvcn.{grade}a{index}@{EMAIL_DOMAIN}", random_full_name(rng), UserRole.TEACHER
                )
    return users, subject_teachers, homeroom_teachers


# --- Học sinh ---------------------------------------------------------------------------------


def _new_student(
    params: SeedParams, student_id: int, grade: int, class_index: int, class_id: int, number: int
) -> _Student:
    code = f"HS{grade}{class_index:02d}{number:03d}"
    scenario = SCENARIOS.get(code)
    if scenario is not None and scenario.ability is not None:
        ability = scenario.ability
    else:
        ability = max(-2.5, min(2.5, _rng(params.seed, code, "ability").gauss(0.0, 1.0)))
    return _Student(
        id=student_id,
        code=code,
        grade=grade,
        class_index=class_index,
        class_id=class_id,
        ability=ability,
        scenario=scenario,
    )


def _student_row(params: SeedParams, student: _Student) -> Row:
    name_rng = _rng(params.seed, student.code, "name")
    profile_rng = _rng(params.seed, student.code, "profile")
    scenario = student.scenario
    full_name = (
        scenario.full_name if scenario and scenario.full_name else random_full_name(name_rng)
    )
    birth_year = 2011 - (student.grade - 10)  # lớp 10 sinh 2011, lớp 11 sinh 2010, lớp 12 sinh 2009
    surname = full_name.split()[0]
    # Phụ huynh thường cùng họ với con.
    guardian_surname = surname if profile_rng.random() < 0.8 else None
    return {
        "id": student.id,
        "student_code": student.code,
        "full_name": full_name,
        "date_of_birth": date(birth_year, 1, 1) + timedelta(days=profile_rng.randrange(365)),
        "guardian_name": random_full_name(profile_rng, guardian_surname),
        "guardian_phone": random_phone(profile_rng),
    }


def _weighted_sample(
    rng: random.Random, pool: Sequence[_Student], count: int, slope: float
) -> list[_Student]:
    """Chọn `count` em không lặp, em năng lực thấp có xác suất cao hơn (Efraimidis-Spirakis)."""
    keyed = [(rng.random() ** (1.0 / math.exp(-slope * s.ability)), s) for s in pool]
    keyed.sort(key=lambda item: (-item[0], item[1].id))
    return [student for _key, student in keyed[:count]]


def _plan_special_groups(params: SeedParams, students: list[_Student]) -> None:
    """Chọn nhóm nghỉ 30-50 buổi (≈5%) và nhóm có môn dưới 3,5 (≈8%), có tương quan với năng lực.

    Học sinh kịch bản (nhân vật và biên) tính vào chỉ tiêu và không bị chọn lại. Khoảng nửa nhóm
    điểm thấp được lấy từ nhóm nghỉ nhiều, phần còn lại từ các em năng lực thấp.
    """
    rng = _rng(params.seed, "quota")
    total = len(students)
    scripted = [s for s in students if s.scenario is not None]
    for student in scripted:
        assert student.scenario is not None
        student.absences = student.scenario.absences
        if student.scenario.flat_subject and student.scenario.flat_score is not None:
            student.flat = (student.scenario.flat_subject, student.scenario.flat_score)
    pool = [s for s in students if s.scenario is None]

    heavy_quota = math.floor(HEAVY_ABSENCE_RATE * total + 0.5)
    heavy_scripted = sum(1 for s in scripted if s.scenario and s.scenario.is_heavy_absence)
    heavy = _weighted_sample(rng, pool, max(0, heavy_quota - heavy_scripted), slope=0.8)
    for student in heavy:
        student.absences = rng.randint(30, 50)

    low_quota = math.floor(LOW_SCORE_RATE * total + 0.5)
    low_scripted = sum(1 for s in scripted if s.scenario and s.scenario.is_low_score)
    low_needed = max(0, low_quota - low_scripted)
    from_heavy = min(len(heavy), low_needed // 2)
    low = rng.sample(heavy, from_heavy)
    heavy_ids = {s.id for s in heavy}
    rest = [s for s in pool if s.id not in heavy_ids]
    low += _weighted_sample(rng, rest, min(len(rest), low_needed - from_heavy), slope=1.0)
    for student in low:
        score_subjects = [
            s
            for s in class_subjects(student.class_index)
            if s.assessment_type is AssessmentType.SCORE
        ]
        subject = rng.choice(score_subjects)
        student.flat = (subject.name, _score(rng.randint(20, 34)))  # 2,0 đến 3,4


def _normal_absences(params: SeedParams, student: _Student) -> int:
    """Phần lớn nghỉ 0-10 buổi; năng lực thấp thì nghỉ nhiều hơn một chút."""
    rng = _rng(params.seed, student.code, "absences")
    scale = 3.0 * math.exp(-0.25 * student.ability)
    return min(10, int(rng.expovariate(1.0 / scale)))


# --- Điểm -------------------------------------------------------------------------------------


def _draw_score(rng: random.Random, mean: float, flat: Decimal | None) -> Decimal:
    if flat is not None:
        return flat
    tenths = round(10 * (mean + rng.gauss(0.0, 0.8)))
    return _score(max(MIN_SCORE_TENTHS, min(MAX_SCORE_TENTHS, tenths)))


def _assessments(
    params: SeedParams,
    student: _Student,
    subjects: Sequence[SubjectSpec],
    subject_ids: Mapping[str, int],
    rules: Sequence[Mapping[str, Any]],
    ids: Iterator[int],
) -> list[Row]:
    rng = _rng(params.seed, student.code, "scores")
    absences = student.absences or 0
    level = 6.9 + 1.1 * student.ability - 0.03 * max(0, absences - 10)
    rows: list[Row] = []

    def add(
        subject: SubjectSpec, semester: int, kind: AssessmentKind, seq: int, **result: Any
    ) -> None:
        rows.append(
            {
                "id": next(ids),
                "class_student_id": student.id,
                "subject_id": subject_ids[subject.name],
                "semester": semester,
                "kind": kind,
                "seq": seq,
                "score": result.get("score"),
                "comment_result": result.get("comment_result"),
            }
        )

    fail_chance = 0.02 + (0.10 if absences >= 30 else 0.0)
    for subject in subjects:
        if subject.assessment_type is AssessmentType.COMMENT:
            for semester in (1, 2):
                failed = rng.random() < fail_chance
                add(
                    subject,
                    semester,
                    AssessmentKind.CK,
                    1,
                    comment_result=CommentResult.FAIL if failed else CommentResult.PASS,
                )
            continue

        flat = student.flat[1] if student.flat and student.flat[0] == subject.name else None
        regular_count = required_regular_count(subject.periods_per_year, rules)
        subject_mean = level + rng.gauss(0.0, 0.35)
        for semester in (1, 2):
            mean = subject_mean + (rng.gauss(0.0, 0.25) if semester == 2 else 0.0)
            for seq in range(1, regular_count + 1):
                add(subject, semester, AssessmentKind.TX, seq, score=_draw_score(rng, mean, flat))
            add(subject, semester, AssessmentKind.GK, 1, score=_draw_score(rng, mean, flat))
            add(subject, semester, AssessmentKind.CK, 1, score=_draw_score(rng, mean, flat))
    return rows


# --- Điểm danh, rèn luyện, đăng ký thi --------------------------------------------------------


def _pick_absent_days(rng: random.Random, day_count: int, absences: int) -> set[int]:
    """Chọn ngày nghỉ. Nghỉ nhiều thì nghỉ theo chuỗi 1-4 ngày liên tiếp cho giống thực tế."""
    if absences >= day_count:
        return set(range(day_count))
    if absences < 20:
        return set(rng.sample(range(day_count), absences))
    chosen: set[int] = set()
    while len(chosen) < absences:
        start = rng.randrange(day_count)
        for offset in range(rng.randint(1, 4)):
            if len(chosen) < absences and start + offset < day_count:
                chosen.add(start + offset)
    return chosen


def _is_held_out(params: SeedParams, day: date) -> bool:
    return params.hold_out_month == (day.year, day.month)


def _attendance(
    params: SeedParams, student: _Student, days: Sequence[SchoolDay], first_id: int
) -> list[Row]:
    """Một dòng cho mọi ngày học. Mỗi dòng nghỉ (có phép hoặc không phép) tính là 1 buổi (D-028)."""
    rng = _rng(params.seed, student.code, "attendance")
    absent_days = _pick_absent_days(rng, len(days), student.absences or 0)
    rows: list[Row] = []
    for index, school_day in enumerate(days):
        if index in absent_days:
            excused = rng.random() < 0.65
            status = (
                AttendanceStatus.ABSENT_EXCUSED if excused else AttendanceStatus.ABSENT_UNEXCUSED
            )
        elif rng.random() < 0.02:
            status = AttendanceStatus.LATE
        else:
            status = AttendanceStatus.PRESENT
        rows.append(
            {
                "id": first_id + index,
                "class_student_id": student.id,
                "date": school_day.day,
                "status": status,
            }
        )
    return rows


def _conduct(params: SeedParams, student: _Student, first_id: int) -> list[Row]:
    """Rèn luyện từng học kỳ (HK1, HK2); không sinh kết quả "cả năm" (đó là luật Thông tư 22)."""
    rng = _rng(params.seed, student.code, "conduct")
    base = 0.6 * student.ability - 0.04 * (student.absences or 0)
    rows: list[Row] = []
    for offset, period in enumerate((ConductPeriod.HK1, ConductPeriod.HK2)):
        x = base + rng.gauss(0.0, 0.7)
        if x > -0.4:
            level = ConductLevel.GOOD
        elif x > -1.3:
            level = ConductLevel.FAIR
        elif x > -2.5:
            level = ConductLevel.PASS
        else:
            level = ConductLevel.FAIL
        rows.append(
            {
                "id": first_id + offset,
                "class_student_id": student.id,
                "period": period,
                "level": level,
                "comment": None,
            }
        )
    return rows


def _exam_registrations(
    params: SeedParams,
    student: _Student,
    subjects: Sequence[SubjectSpec],
    subject_ids: Mapping[str, int],
    first_id: int,
) -> list[Row]:
    """Khối 12: Ngữ văn, Toán, cộng 2 môn tính điểm bất kỳ trong các môn lớp đang học."""
    rng = _rng(params.seed, student.code, "exam")
    optional = [
        s.name
        for s in subjects
        if s.assessment_type is AssessmentType.SCORE
        and s.name not in EXAM_COMPULSORY
        and s.name not in EXAM_EXCLUDED
    ]
    chosen = [*EXAM_COMPULSORY, *rng.sample(optional, 2)]
    return [
        {
            "id": first_id + offset,
            "class_student_id": student.id,
            "subject_id": subject_ids[name],
        }
        for offset, name in enumerate(chosen)
    ]

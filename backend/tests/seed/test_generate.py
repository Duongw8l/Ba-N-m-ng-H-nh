"""Kiểm tra bộ sinh dữ liệu giả trong bộ nhớ (không cần DB)."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.core.enums import AssessmentKind, AttendanceStatus
from data.seed.curriculum import ELECTIVE_COMBOS, SUBJECTS, class_subjects
from data.seed.generate import TableRows, generate
from data.seed.params import SeedParams
from data.seed.people import EMAIL_DOMAIN
from data.seed.school_calendar import school_days

# Giá trị mặc định của settings.regular_assessment_count (DESIGN mục 5).
RULES = [
    {"max_periods": 35, "count": 2},
    {"max_periods": 70, "count": 3},
    {"max_periods": None, "count": 4},
]
# Bảng tính tay: số đầu điểm thường xuyên mỗi học kỳ của từng môn tính điểm.
EXPECTED_TX = {
    "Ngữ văn": 4,  # 105 tiết
    "Toán": 4,
    "Tiếng Anh": 4,
    "Lịch sử": 3,  # 52 tiết
    "Giáo dục quốc phòng và an ninh": 2,  # 35 tiết
    "Địa lí": 3,  # 70 tiết
    "Giáo dục kinh tế và pháp luật": 3,
    "Vật lí": 3,
    "Hóa học": 3,
    "Sinh học": 3,
    "Công nghệ": 3,
    "Tin học": 3,
}
COMMENT_SUBJECTS = {
    "Giáo dục thể chất",
    "Hoạt động trải nghiệm, hướng nghiệp",
    "Nội dung giáo dục địa phương",
    "Âm nhạc",
    "Mĩ thuật",
}
ABSENT = {AttendanceStatus.ABSENT_EXCUSED, AttendanceStatus.ABSENT_UNEXCUSED}


@pytest.fixture(scope="module")
def data() -> TableRows:
    return generate(SeedParams(), RULES, "bcrypt-hash-gia")


def students_by_code(data: TableRows) -> dict[str, dict[str, Any]]:
    return {row["student_code"]: row for row in data["students"]}


def absences_by_student(data: TableRows) -> Counter[int]:
    return Counter(row["class_student_id"] for row in data["attendance"] if row["status"] in ABSENT)


def test_params_are_validated() -> None:
    with pytest.raises(ValueError, match="classes_per_grade"):
        SeedParams(classes_per_grade=0)
    with pytest.raises(ValueError, match="class_size"):
        SeedParams(class_size=0)
    assert SeedParams().student_count == 360


def test_same_params_give_identical_data_and_other_seed_differs(data: TableRows) -> None:
    assert generate(SeedParams(), RULES, "bcrypt-hash-gia") == data
    assert generate(SeedParams(seed=7), RULES, "bcrypt-hash-gia") != data


def test_school_calendar_has_175_weekdays_in_two_semesters() -> None:
    days = school_days()

    assert len(days) == 175
    assert Counter(d.semester for d in days) == {1: 90, 2: 85}
    assert all(d.day.weekday() < 5 for d in days)
    assert days[0].day == date(2026, 9, 7)
    assert days[-1].day == date(2027, 5, 28)
    assert len({d.day for d in days}) == 175
    # Hai tuần nghỉ Tết (01-12/02/2027) không có ngày học.
    assert not any(date(2027, 2, 1) <= d.day <= date(2027, 2, 12) for d in days)
    assert all(b.day > a.day for a, b in zip(days, days[1:], strict=False))


def test_curriculum_matches_the_plan() -> None:
    assert len(SUBJECTS) == 17
    assert sum(1 for s in SUBJECTS if s.is_elective) == 9
    assert all(len(set(combo)) == 4 for combo in ELECTIVE_COMBOS)
    assert {name for combo in ELECTIVE_COMBOS for name in combo} == {
        s.name for s in SUBJECTS if s.is_elective
    }
    assert all(len(class_subjects(index)) == 12 for index in (1, 2, 3, 4))


def test_row_counts_for_default_params(data: TableRows) -> None:
    assert len(data["students"]) == len(data["class_students"]) == 360
    assert len(data["classes"]) == 9
    assert len(data["teaching_assignments"]) == 9 * 12
    assert len(data["attendance"]) == 360 * 175
    assert len(data["conduct_results"]) == 360 * 2
    assert len(data["exam_registrations"]) == 120 * 4
    # Cả 9 lớp đều có 12 môn: 360 học sinh × 12 môn, mỗi môn đủ hai học kỳ.
    assert len({(r["class_student_id"], r["subject_id"]) for r in data["assessments"]}) == 360 * 12


def test_every_student_subject_has_all_scores_by_hand_table(data: TableRows) -> None:
    names = {row["id"]: row["name"] for row in data["subjects"]}
    kinds: dict[tuple[int, int, int], Counter[AssessmentKind]] = defaultdict(Counter)
    for row in data["assessments"]:
        key = (row["class_student_id"], row["subject_id"], row["semester"])
        kinds[key][row["kind"]] += 1

    for (_student, subject_id, _semester), counter in kinds.items():
        name = names[subject_id]
        if name in EXPECTED_TX:
            assert counter == {
                AssessmentKind.TX: EXPECTED_TX[name],
                AssessmentKind.GK: 1,
                AssessmentKind.CK: 1,
            }, name
        else:
            assert name in COMMENT_SUBJECTS
            assert counter == {AssessmentKind.CK: 1}, name


def test_comment_subjects_have_only_a_result_and_score_subjects_only_a_score(
    data: TableRows,
) -> None:
    comment_ids = {r["id"] for r in data["subjects"] if r["name"] in COMMENT_SUBJECTS}

    for row in data["assessments"]:
        if row["subject_id"] in comment_ids:
            assert row["score"] is None and row["comment_result"] is not None
        else:
            assert row["comment_result"] is None
            assert Decimal(0) <= row["score"] <= Decimal(10)
            assert row["score"] == row["score"].quantize(Decimal("0.1"))  # 1 chữ số thập phân


def test_quotas_five_percent_heavy_absence_and_eight_percent_low_score(data: TableRows) -> None:
    absences = absences_by_student(data)
    heavy = [sid for sid, n in absences.items() if n >= 30]
    low = {
        r["class_student_id"]
        for r in data["assessments"]
        if r["score"] is not None and r["score"] < Decimal("3.5")
    }

    assert len(heavy) == 18  # round(5% × 360)
    assert all(30 <= absences[sid] <= 50 for sid in heavy)
    assert len(low) == 29  # round(8% × 360)
    ordinary = [absences.get(row["id"], 0) for row in data["students"]]
    assert sum(1 for n in ordinary if n <= 10) >= 0.9 * 360  # phần lớn nghỉ 0-10 buổi


def test_ordinary_students_never_score_below_four(data: TableRows) -> None:
    def students_with_score_below(limit: str) -> set[int]:
        return {
            r["class_student_id"]
            for r in data["assessments"]
            if r["score"] is not None and r["score"] < Decimal(limit)
        }

    boundary_3_5 = students_by_code(data)["HS1201005"]["id"]  # mọi đầu điểm Toán bằng 3,5

    # Chỉ nhóm "môn dưới 3,5" và học sinh biên 3,5 mới có đầu điểm dưới 4,0.
    assert students_with_score_below("4.0") == students_with_score_below("3.5") | {boundary_3_5}


def test_low_score_students_have_every_score_of_one_subject_below_threshold(
    data: TableRows,
) -> None:
    per_subject: dict[tuple[int, int], list[Decimal]] = defaultdict(list)
    for row in data["assessments"]:
        if row["score"] is not None:
            per_subject[(row["class_student_id"], row["subject_id"])].append(row["score"])
    low_students = {sid for (sid, _), scores in per_subject.items() if min(scores) < Decimal("3.5")}

    for student_id in low_students:
        flat = [
            s
            for (sid, _), s in per_subject.items()
            if sid == student_id and max(s) < Decimal("3.5")
        ]
        assert flat, student_id
        assert all(len(set(scores)) == 1 for scores in flat)  # mọi đầu điểm của môn bằng nhau


def test_low_scores_correlate_with_absences(data: TableRows) -> None:
    absences = absences_by_student(data)
    total: dict[int, list[Decimal]] = defaultdict(list)
    for row in data["assessments"]:
        if row["score"] is not None:
            total[row["class_student_id"]].append(row["score"])
    average = {sid: sum(v) / len(v) for sid, v in total.items()}
    heavy = [average[sid] for sid, n in absences.items() if n >= 30]
    rest = [average[sid] for sid in average if absences.get(sid, 0) < 30]

    assert sum(heavy) / len(heavy) < sum(rest) / len(rest) - 1  # nghỉ nhiều thì điểm thấp hơn


def test_demo_characters_and_boundary_students(data: TableRows) -> None:
    students = students_by_code(data)
    absences = absences_by_student(data)
    scores: dict[tuple[str, str], set[Decimal]] = defaultdict(set)
    code_of = {row["id"]: row["student_code"] for row in data["students"]}
    subject_name = {row["id"]: row["name"] for row in data["subjects"]}
    for row in data["assessments"]:
        if row["score"] is not None:
            key = (code_of[row["class_student_id"]], subject_name[row["subject_id"]])
            scores[key].add(row["score"])

    assert students["HS1102001"]["full_name"] == "Trần Minh An"
    assert absences[students["HS1102001"]["id"]] == 38
    assert students["HS1102002"]["full_name"] == "Lê Hoàng Bảo"
    assert scores[("HS1102002", "Toán")] == {Decimal("3.0")}
    for code, expected in (("HS1201001", 44), ("HS1201002", 45), ("HS1201003", 46)):
        assert absences[students[code]["id"]] == expected
    assert scores[("HS1201004", "Toán")] == {Decimal("3.4")}
    assert scores[("HS1201005", "Toán")] == {Decimal("3.5")}
    assert scores[("HS1201006", "Toán")] == {Decimal("5.0")}


def test_only_one_student_is_called_an_in_class_11a2(data: TableRows) -> None:
    class_11a2 = next(row["id"] for row in data["classes"] if row["name"] == "11A2")
    ids = {row["student_id"] for row in data["class_students"] if row["class_id"] == class_11a2}

    given_names = [row["full_name"].split()[-1] for row in data["students"] if row["id"] in ids]

    assert given_names.count("An") == 1


def test_conduct_is_per_semester_only_and_grade_12_registers_four_exam_subjects(
    data: TableRows,
) -> None:
    assert Counter(row["period"].value for row in data["conduct_results"]) == {
        "hk1": 360,
        "hk2": 360,
    }
    per_student = Counter(row["class_student_id"] for row in data["exam_registrations"])
    grade_12_ids = {row["id"] for row in data["students"] if row["student_code"].startswith("HS12")}
    assert set(per_student) == grade_12_ids
    assert set(per_student.values()) == {4}


def test_attendance_has_one_row_per_school_day_and_late_is_not_an_absence(
    data: TableRows,
) -> None:
    days = school_days()
    rows = [r for r in data["attendance"] if r["class_student_id"] == 1]

    assert [r["date"] for r in rows] == [d.day for d in days]
    statuses = Counter(r["status"] for r in data["attendance"])
    assert statuses[AttendanceStatus.LATE] > 0
    assert statuses[AttendanceStatus.PRESENT] > statuses[AttendanceStatus.LATE]


def test_default_attendance_ids_are_one_to_n_without_gaps(data: TableRows) -> None:
    """Mặc định (không --hold-out) dữ liệu y hệt các giai đoạn trước: id điểm danh liên tục."""
    assert [r["id"] for r in data["attendance"]] == list(range(1, 360 * 175 + 1))


def test_hold_out_removes_exactly_that_months_attendance_and_nothing_else(
    data: TableRows,
) -> None:
    held = generate(SeedParams(hold_out_month=(2027, 3)), RULES, "bcrypt-hash-gia")
    march_days = [d.day for d in school_days() if (d.day.year, d.day.month) == (2027, 3)]
    assert len(march_days) == 23  # tính tay: tháng 3/2027 có 23 ngày thứ Hai đến thứ Sáu

    assert len(held["attendance"]) == 360 * (175 - 23)
    assert not any(r["date"].month == 3 and r["date"].year == 2027 for r in held["attendance"])
    # Dòng còn lại giống hệt dữ liệu mặc định (cùng id, cùng trạng thái): chỉ thiếu tháng 3.
    kept = [r for r in data["attendance"] if (r["date"].year, r["date"].month) != (2027, 3)]
    assert held["attendance"] == kept
    assert len({r["id"] for r in held["attendance"]}) == len(held["attendance"])
    # Mọi bảng khác không đổi.
    assert {name: rows for name, rows in held.items() if name != "attendance"} == {
        name: rows for name, rows in data.items() if name != "attendance"
    }


def test_hold_out_month_must_be_a_month_with_school_days() -> None:
    SeedParams(hold_out_month=(2026, 9))
    SeedParams(hold_out_month=(2027, 5))
    SeedParams(hold_out_month=(2027, 2))  # nghỉ Tết hai tuần nhưng vẫn có 10 ngày học
    for month in [(2026, 8), (2027, 6), (2027, 13), (2027, 0), (1999, 3)]:
        with pytest.raises(ValueError, match="hold_out"):
            SeedParams(hold_out_month=month)


def test_accounts_are_fake_and_follow_the_roles(data: TableRows) -> None:
    users = data["users"]
    roles = Counter(u["role"].value for u in users)

    assert roles == {"admin": 1, "principal": 2, "teacher": 57}
    assert all(u["email"].endswith(f"@{EMAIL_DOMAIN}") for u in users)
    assert len({u["email"] for u in users}) == len(users)
    assert {u["password_hash"] for u in users} == {"bcrypt-hash-gia"}
    # Mỗi lớp có GVCN; ít nhất một GVCN cũng là GVBM, dạy cả lớp khác ngoài lớp chủ nhiệm.
    homeroom = {c["homeroom_teacher_id"]: c["id"] for c in data["classes"]}
    assert len(homeroom) == 9 and None not in homeroom
    both = [
        a
        for a in data["teaching_assignments"]
        if a["teacher_id"] in homeroom and a["class_id"] != homeroom[a["teacher_id"]]
    ]
    assert both


def test_student_personal_data_is_fake(data: TableRows) -> None:
    for row in data["students"]:
        assert row["guardian_phone"].startswith("0000") and len(row["guardian_phone"]) == 10
        grade = int(row["student_code"][2:4])
        assert row["date_of_birth"].year == 2011 - (grade - 10)
        assert date(2009, 1, 1) <= row["date_of_birth"] <= date(2011, 12, 31)
    assert len({row["student_code"] for row in data["students"]}) == 360


def test_small_params_still_generate_consistent_data() -> None:
    small = generate(SeedParams(seed=3, classes_per_grade=1, class_size=5), RULES, "x")

    assert len(small["students"]) == 15
    assert len(small["classes"]) == 3
    # Chỉ có lớp A1 mỗi khối: không có 11A2 nên không có nhân vật demo; vẫn sinh đủ dữ liệu.
    assert "HS1102001" not in students_by_code(small)
    assert len(small["attendance"]) == 15 * 175
    homeroom_teachers = {c["homeroom_teacher_id"] for c in small["classes"]}
    assert len(homeroom_teachers) == 3

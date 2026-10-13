"""Hàng rào kiểm văn bản AI viết (D-105): số ngoài dữ liệu, từ cấm, tên học sinh, định dạng."""

import json

import pytest

from app.core.pseudonymize import Pseudonymizer, RosterStudent
from app.reports import checks
from app.reports.checks import Violation, check_text, parse_banned_words

# Dữ liệu mẫu đã đưa cho LLM: ĐTB Toán 7,5 và 8, nghỉ 12 buổi.
EVIDENCE = json.dumps(
    {"subjects": [{"name": "Toán", "average": 7.5}, {"name": "Văn", "average": 8.0}], "absent": 12}
)
GOOD = (
    "Em học tốt môn Toán với điểm trung bình 7,5 và môn Văn đạt 8. Em cần chú ý hơn việc đi học "
    "đều vì đã nghỉ 12 buổi. Gia đình nhắc em sắp xếp thời gian ôn bài mỗi tối."
)


def codes(text: str, *, student: bool = True, pseudo: Pseudonymizer | None = None) -> list[str]:
    return [
        v.code for v in check_text(text, evidence=EVIDENCE, student_scope=student, pseudo=pseudo)
    ]


def test_a_clean_grounded_comment_passes() -> None:
    assert codes(GOOD) == []


# --- Con số phải có trong dữ liệu ------------------------------------------------------------


def test_a_number_missing_from_the_data_is_blocked_and_named() -> None:
    violations = check_text(
        GOOD.replace("7,5", "7,8"), evidence=EVIDENCE, student_scope=True, pseudo=None
    )
    assert violations == [Violation("number_not_in_data", "7,8")]


@pytest.mark.parametrize("written", ["7,5", "7.5", "7,50"])
def test_the_same_number_written_differently_is_still_grounded(written: str) -> None:
    assert codes(GOOD.replace("7,5", written)) == []


def test_a_computed_number_is_blocked() -> None:
    # (7,5 + 8) / 2 = 7,75: LLM tự tính trung bình thì không có trong dữ liệu.
    assert "number_not_in_data" in codes(GOOD + " Trung bình hai môn khoảng 7,75.")


def test_a_percentage_or_count_invented_by_the_model_is_blocked() -> None:
    assert "number_not_in_data" in codes(GOOD + " Em đứng trong top 10% của khối.")
    assert "number_not_in_data" in codes(GOOD.replace("12 buổi", "13 buổi"))


def test_class_names_and_codes_do_not_count_as_numbers() -> None:
    assert codes(GOOD + " Em học lớp 11A2 rất nề nếp.") == []


# --- Từ ngữ cấm ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Em còn lười học bài.", "banned_negative"),
        ("Kết quả học yếu ở môn Hóa.", "banned_negative"),
        ("Em là học sinh CÁ BIỆT của lớp.", "banned_negative"),
        ("Em còn kém cỏi ở môn Lý.", "banned_negative"),
        ("Em học tốt hơn các bạn trong tổ.", "banned_comparison"),
        ("Điểm của em thấp hơn so với bạn bè cùng lớp.", "banned_comparison"),
        ("Em xếp thứ năm trong lớp.", "banned_comparison"),
        ("Em chưa bằng bạn cùng bàn.", "banned_comparison"),
        ("Do hoàn cảnh gia đình khó khăn nên em hay nghỉ.", "banned_family"),
        ("Bố mẹ ly hôn khiến em mất tập trung.", "banned_family"),
    ],
)
def test_banned_phrases_are_blocked_in_a_student_comment(phrase: str, expected: str) -> None:
    assert expected in codes(GOOD + " " + phrase)


def test_banned_words_ignore_case_and_stop_at_word_boundaries() -> None:
    assert "banned_negative" in codes(GOOD + " EM LƯỜI HỌC.")
    assert "banned_negative" in codes(GOOD + " Em ngu dốt.")
    # "ngu" là cụm bị cấm nhưng không được khớp bên trong từ khác.
    assert codes(GOOD + " Em nắm vững nguyên tắc và biết tìm nguồn kiến thức.") == []


def test_a_plain_word_family_is_allowed_only_the_circumstances_are_banned() -> None:
    assert codes(GOOD + " Mong gia đình phối hợp cùng nhà trường.") == []


def test_comparison_is_allowed_in_class_and_grade_reports_but_labels_are_not() -> None:
    comparison = "Lớp 11A1 có điểm trung bình môn Toán cao hơn so với lớp 11A2, mức 8 so với 7,5. "
    text = comparison + "Nhìn chung các em học tập nghiêm túc, đi học đều và tích cực xây dựng bài."
    assert codes(text, student=False) == []
    assert "banned_comparison" in codes(text, student=True)
    assert "banned_negative" in codes(text + " Một số em lười.", student=False)


# --- Tên và mã học sinh ----------------------------------------------------------------------


def test_temporary_codes_are_blocked_in_the_text() -> None:
    assert "student_identity" in codes(GOOD + " HS_01 cần cố gắng thêm.")
    assert "student_identity" in codes(GOOD + " hs_12 tiến bộ.")


def test_real_names_and_codes_are_blocked_when_the_roster_is_known() -> None:
    pseudo = Pseudonymizer([RosterStudent(1, 5, "Trần Minh An", "HS1102001")], open_class_id=5)
    assert "student_identity" in codes(GOOD + " Em Trần Minh An rất chăm.", pseudo=pseudo)
    assert "student_identity" in codes(GOOD + " Mã hs1102001 chưa nộp bài.", pseudo=pseudo)
    assert codes(GOOD, pseudo=pseudo) == []


# --- Định dạng và độ dài ---------------------------------------------------------------------


@pytest.mark.parametrize("fragment", ["**Điểm mạnh**: tốt.", "# Nhận xét", "- Toán tốt", "`code`"])
def test_markdown_is_blocked(fragment: str) -> None:
    assert "markdown" in codes(GOOD + "\n" + fragment)


def test_too_short_and_too_long_texts_are_blocked() -> None:
    assert codes("Em học tốt.") == ["too_short"]
    assert "too_long" in codes("Em học tập tích cực. " * 100)
    # Báo cáo lớp / khối được dài hơn nhận xét một học sinh.
    assert "too_long" not in codes("Lớp học tập nghiêm túc. " * 40, student=False)


def test_every_violation_has_a_message_for_the_rewrite_and_a_notice_for_the_teacher() -> None:
    assert set(checks.NOTICES_VI) == set(checks.MESSAGES_VI)
    for code in checks.MESSAGES_VI:
        assert Violation(code, "9,9").message()
        assert Violation(code, "9,9").notice()
    assert "9,9" in Violation("number_not_in_data", "9,9").message()
    assert "9,9" in Violation("number_not_in_data", "9,9").notice()
    # Lời báo cho giáo viên không mang giọng ra lệnh với AI.
    assert all("Hãy" not in notice for notice in checks.NOTICES_VI.values())


# --- Tệp banned_words.txt --------------------------------------------------------------------


def test_the_shipped_banned_words_file_loads_with_all_three_groups() -> None:
    rules = checks.load_banned_rules()
    assert set(rules.patterns) == set(checks.GROUP_CODES)
    assert all(rules.patterns[group] for group in checks.GROUP_CODES)


def test_the_example_words_of_the_spec_are_in_the_file() -> None:
    rules = checks.load_banned_rules()
    for word in ("học yếu", "lười", "kém cỏi"):  # PROMPTS Giai đoạn 9
        assert rules.groups_found(word, checks.STUDENT_GROUPS) == ["tieu_cuc"], word


def test_parse_banned_words_skips_comments_and_blank_lines() -> None:
    rules = parse_banned_words("# ghi chú\n\n[tieu_cuc]\n  quá dở  \n# hết\n")
    assert rules.groups_found("Bài làm quá dở", ("tieu_cuc",)) == ["tieu_cuc"]
    assert rules.groups_found("Bài làm khá tốt", ("tieu_cuc",)) == []


def test_parse_banned_words_rejects_an_unknown_group_and_a_phrase_outside_any_group() -> None:
    with pytest.raises(ValueError, match="nhóm lạ"):
        parse_banned_words("[tieu_cucc]\nlười\n")
    with pytest.raises(ValueError, match="ngoài mọi nhóm"):
        parse_banned_words("lười\n")

"""pseudonymize: ẩn danh học sinh trước khi sang LLM (nguyên tắc 5, D-086). Hàm thuần."""

import pytest

from app.core.pseudonymize import (
    AmbiguousName,
    Pseudonymizer,
    RosterStudent,
    UnsafePayload,
    given_name,
)

AN = RosterStudent(1, 5, "Trần Minh An", "HS1102001")
BINH = RosterStudent(2, 5, "Lê Thị Bình", "HS1102002")
CHI = RosterStudent(3, 5, "Phạm Quỳnh Chi", "HS1102003")
AN_OTHER = RosterStudent(4, 5, "Nguyễn Hoài An", "HS1102004")
AN_OTHER_CLASS = RosterStudent(5, 6, "Đỗ Gia An", "HS1103001")


def pseudo(*students: RosterStudent, open_class_id: int | None = 5) -> Pseudonymizer:
    return Pseudonymizer(students, open_class_id)


def test_given_name_is_the_last_word_of_the_full_name() -> None:
    assert given_name("Trần Minh An") == "An"
    assert given_name("  Lê   Thị Bình ") == "Bình"
    assert given_name("") == ""


# --- Cấp mã -------------------------------------------------------------------------------------


def test_codes_are_issued_in_order_of_first_use_and_are_stable_for_the_same_student() -> None:
    p = pseudo(AN, BINH)

    assert p.code_for(BINH) == "HS_01"
    assert p.code_for(AN) == "HS_02"
    assert p.code_for(BINH) == "HS_01"


def test_mapping_lives_in_one_request_only() -> None:
    first, second = pseudo(AN, BINH), pseudo(AN, BINH)
    first.code_for(AN)
    second.code_for(BINH)

    assert first.code_for(AN) == "HS_01"
    assert second.code_for(BINH) == "HS_01"  # cùng mã, hai em khác nhau ở hai request
    assert second.resolve("HS_01") == BINH
    assert first.resolve("HS_01") == AN


def test_only_codes_issued_in_this_request_can_be_resolved() -> None:
    p = pseudo(AN, BINH)
    p.code_for(AN)

    assert p.resolve("HS_01") == AN
    assert p.resolve("hs_01") == AN
    assert p.resolve("HS_1") == AN  # LLM viết thiếu số 0
    assert p.resolve("HS_02") is None  # chưa cấp
    assert p.resolve("HS1102001") is None  # mã thật không phải mã tạm
    assert p.resolve("bất kỳ chữ gì") is None


# --- Đổi lại khi hiển thị -----------------------------------------------------------------------


def test_depseudonymize_restores_real_names() -> None:
    p = pseudo(AN, BINH)
    a, b = p.code_for(AN), p.code_for(BINH)

    text = f"{a} nghỉ 38 buổi, còn {b} nghỉ 2 buổi."

    assert p.depseudonymize(text) == "Trần Minh An nghỉ 38 buổi, còn Lê Thị Bình nghỉ 2 buổi."


def test_depseudonymize_does_not_confuse_hs_1_with_hs_10() -> None:
    students = [RosterStudent(i, 5, f"Học Sinh {chr(65 + i)}", f"HS{i:07d}") for i in range(12)]
    p = pseudo(*students)
    for student in students:
        p.code_for(student)

    out = p.depseudonymize("HS_01 và HS_10 và HS_11")

    assert out == "Học Sinh A và Học Sinh J và Học Sinh K"


def test_depseudonymize_leaves_invented_codes_alone() -> None:
    p = pseudo(AN)
    p.code_for(AN)

    assert p.depseudonymize("HS_01 và HS_77") == "Trần Minh An và HS_77"


# --- Câu hỏi của người dùng ---------------------------------------------------------------------


def test_full_name_in_question_is_replaced() -> None:
    p = pseudo(AN, BINH)

    result = p.pseudonymize_question("Vì sao Trần Minh An bị cảnh báo?")

    assert result.text == "Vì sao HS_01 bị cảnh báo?"
    assert result.ambiguous is None


def test_full_name_match_ignores_case_and_extra_spaces() -> None:
    p = pseudo(AN)

    assert p.pseudonymize_question("điểm của trần   minh an").text == "điểm của HS_01"


def test_real_student_code_in_question_is_replaced() -> None:
    p = pseudo(AN, BINH)

    result = p.pseudonymize_question("Xem hs1102002 và HS1102001")

    assert "HS11" not in result.text  # không còn mã thật
    assert {p.resolve("HS_01"), p.resolve("HS_02")} == {AN, BINH}
    assert result.text.count("HS_") == 2


def test_a_unique_given_name_in_the_open_class_is_resolved() -> None:
    p = pseudo(AN, BINH, CHI)

    result = p.pseudonymize_question("Vì sao em Bình bị cảnh báo?")

    assert result.text == "Vì sao em HS_01 bị cảnh báo?"
    assert p.resolve("HS_01") == BINH


def test_given_name_match_is_case_sensitive_so_common_words_survive() -> None:
    p = pseudo(AN, BINH)

    result = p.pseudonymize_question("Điểm bình thường và an toàn của lớp thế nào?")

    assert result.text == "Điểm bình thường và an toàn của lớp thế nào?"
    assert result.ambiguous is None


def test_given_name_matches_whole_words_only() -> None:
    p = pseudo(AN)

    assert p.pseudonymize_question("Anh Ân nói gì?").text == "Anh Ân nói gì?"


def test_two_students_with_the_same_given_name_are_not_guessed() -> None:
    p = pseudo(AN, BINH, AN_OTHER)

    result = p.pseudonymize_question("Vì sao em An bị cảnh báo?")

    assert result.ambiguous == AmbiguousName("An", 2)


def test_given_name_in_another_class_is_not_matched() -> None:
    p = pseudo(AN, BINH, AN_OTHER_CLASS, open_class_id=5)

    result = p.pseudonymize_question("Vì sao em An bị cảnh báo?")

    assert result.text == "Vì sao em HS_01 bị cảnh báo?"  # chỉ Trần Minh An (lớp đang mở)
    assert p.resolve("HS_01") == AN


def test_without_an_open_class_given_names_are_not_resolved() -> None:
    p = pseudo(AN, BINH, open_class_id=None)

    result = p.pseudonymize_question("Vì sao em An bị cảnh báo?")

    assert result.text == "Vì sao em An bị cảnh báo?"
    assert result.ambiguous is None


def test_full_name_disambiguates_students_who_share_a_given_name() -> None:
    p = pseudo(AN, BINH, AN_OTHER)

    result = p.pseudonymize_question("So sánh Nguyễn Hoài An với Trần Minh An")

    assert result.ambiguous is None
    assert result.text == "So sánh HS_01 với HS_02"
    assert p.resolve("HS_01") == AN_OTHER
    assert p.resolve("HS_02") == AN


def test_two_students_with_the_identical_full_name_are_not_guessed() -> None:
    twin = RosterStudent(9, 6, "Trần Minh An", "HS1103009")
    p = pseudo(AN, twin)

    result = p.pseudonymize_question("Điểm của Trần Minh An")

    assert result.ambiguous == AmbiguousName("Trần Minh An", 2)


def test_longer_names_win_over_their_substrings() -> None:
    long_name = RosterStudent(7, 5, "Trần Minh An Khang", "HS1102007")
    p = pseudo(AN, long_name)

    result = p.pseudonymize_question("Hỏi về Trần Minh An Khang")

    assert p.resolve("HS_01") == long_name
    assert result.text == "Hỏi về HS_01"


def test_question_without_names_is_unchanged() -> None:
    p = pseudo(AN, BINH)

    result = p.pseudonymize_question("Lớp 10A1 em nào đã nghỉ từ 30 buổi?")

    assert result.text == "Lớp 10A1 em nào đã nghỉ từ 30 buổi?"


def test_decomposed_unicode_names_still_match() -> None:
    import unicodedata

    p = pseudo(AN)
    decomposed = unicodedata.normalize("NFD", "Trần Minh An")

    assert p.pseudonymize_question(f"Điểm của {decomposed}").text == "Điểm của HS_01"


# --- Hàng rào cuối ------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["date_of_birth", "guardian_name", "guardian_phone", "full_name"])
def test_forbidden_keys_anywhere_in_the_payload_are_rejected(key: str) -> None:
    p = pseudo(AN)

    with pytest.raises(UnsafePayload):
        p.assert_safe({"data": [{"x": 1, key: "bất kỳ"}]})


def test_forbidden_key_check_ignores_case() -> None:
    with pytest.raises(UnsafePayload):
        pseudo(AN).assert_safe({"Guardian_Phone": "0000"})


def test_a_real_full_name_anywhere_in_the_payload_is_rejected() -> None:
    p = pseudo(AN, BINH)

    with pytest.raises(UnsafePayload):
        p.assert_safe([{"role": "user", "content": "Điểm của trần minh an thế nào?"}])


def test_a_real_student_code_in_the_payload_is_rejected() -> None:
    with pytest.raises(UnsafePayload):
        pseudo(AN).assert_safe({"note": "em hs1102001 nghỉ nhiều"})


def test_students_registered_later_are_also_protected() -> None:
    p = pseudo(AN)
    p.register(RosterStudent(8, 6, "Vũ Ngọc Lan", "HS1103008"))

    with pytest.raises(UnsafePayload):
        p.assert_safe("Vũ Ngọc Lan nghỉ 3 buổi")


def test_clean_payload_passes_including_nested_dataclasses_and_pseudonyms() -> None:
    from app.assistant.llm import Message, ToolCall

    p = pseudo(AN, BINH)
    code = p.code_for(AN)
    payload = [
        Message("system", "Bạn là trợ lý."),
        Message("user", f"Vì sao {code} bị cảnh báo?"),
        Message("assistant", "", (ToolCall("1", "get_student_detail", {"student_code": code}),)),
        Message("tool", '{"absent_total": 38}', tool_call_id="1", tool_name="get_student_detail"),
    ]

    p.assert_safe(payload)  # không ném


def test_nested_dataclass_with_a_real_name_is_caught() -> None:
    from app.assistant.llm import Message

    with pytest.raises(UnsafePayload):
        pseudo(AN).assert_safe([Message("user", "Trần Minh An nghỉ mấy buổi?")])

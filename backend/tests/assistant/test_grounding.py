"""Kiểm số liệu sau khi trợ lý trả lời (D-090): số trong câu trả lời phải có trong kết quả hàm."""

import json

from app.assistant.grounding import numbers_in, ungrounded_numbers


def tool_json(**data: object) -> str:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f'<du_lieu ham="x">{body}</du_lieu>'


def test_numbers_are_normalized_so_comma_and_point_and_trailing_zeros_agree() -> None:
    assert numbers_in("ĐTB 6,5 và 6.50, nghỉ 38 buổi, điểm 7.0") == ["6.5", "6.5", "38", "7"]


def test_codes_class_names_and_words_with_digits_are_not_numbers() -> None:
    assert numbers_in("HS_01 lớp 10A1 thuộc 11A2, mã HS1102001") == []


def test_a_number_that_is_in_the_tool_result_is_grounded() -> None:
    evidence = [tool_json(absent_total=38, mean=6.5, subjects=[3.0, 4.5])]

    assert (
        ungrounded_numbers("Em nghỉ 38 buổi; ĐTB lớp 6,5; có hai môn 3,0 và 4,5.", evidence) == []
    )


def test_compact_json_without_spaces_still_counts() -> None:
    evidence = [tool_json(by_class=[{"mean": 7.2}, {"mean": 6.8}])]

    assert ungrounded_numbers("Lớp A 7,2 và lớp B 6,8.", evidence) == []


def test_numbers_the_llm_computed_or_invented_are_flagged_in_order_without_repeats() -> None:
    evidence = [tool_json(excused=25, unexcused=13, absent_total=38)]

    flagged = ungrounded_numbers(
        "Em nghỉ 25 buổi có phép và 13 không phép, tổng 38 buổi, tương đương 84% và 99 tiết; 99.",
        evidence,
    )

    assert flagged == ["84", "99"]


def test_a_number_in_the_question_is_allowed() -> None:
    assert ungrounded_numbers("Có 3 em nghỉ từ 30 buổi.", ["Lớp 10A1 em nào nghỉ từ 30 buổi?"]) == [
        "3"
    ]
    assert ungrounded_numbers("Từ 30 buổi trở lên.", ["Lớp 10A1 em nào nghỉ từ 30 buổi?"]) == []


def test_list_markers_are_formatting_not_data() -> None:
    answer = "Các em cần hỗ trợ:\n1. HS_01 nghỉ 38 buổi\n2) HS_02 có Toán 3,0\n  3. HS_03"

    assert ungrounded_numbers(answer, [tool_json(a=38, b=3.0)]) == []


def test_citation_numbers_must_come_from_a_retrieved_article() -> None:
    cited = [tool_json(hits=[{"article": "Điều 12", "content": "Nghỉ quá 45 buổi"}])]

    assert ungrounded_numbers("Theo Điều 12, nghỉ quá 45 buổi.", cited) == []
    assert ungrounded_numbers("Theo Điều 14, nghỉ quá 45 buổi.", cited) == ["14"]


def test_dates_are_compared_by_their_numeric_parts() -> None:
    evidence = [tool_json(**{"from": "2027-03-01", "to": "2027-03-31"})]

    assert ungrounded_numbers("Từ 2027-03-01 đến 2027-03-31.", evidence) == []


def test_no_numbers_means_nothing_flagged() -> None:
    assert ungrounded_numbers("Hệ thống chưa có số liệu này.", []) == []

import unicodedata
from pathlib import Path

import pytest

from app.rag.chunking import (
    LEAD_IN_OWN_CHUNK_CHARS,
    LOOSE_MIN_CHARS,
    MAX_CHUNK_CHARS,
    Chunk,
    count_articles,
    normalize_text,
    split_into_chunks,
)

SAMPLE = Path(__file__).resolve().parents[3] / "data" / "regulations" / "van-ban-mau-gia.txt"


def labels(chunks: list[Chunk]) -> list[tuple[str | None, str | None]]:
    return [(chunk.article, chunk.clause) for chunk in chunks]


def words(text: str) -> list[str]:
    return text.split()


# --- Văn bản mẫu ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_chunks() -> list[Chunk]:
    return split_into_chunks(SAMPLE.read_text(encoding="utf-8"))


def test_sample_document_is_split_by_article_and_clause(sample_chunks: list[Chunk]) -> None:
    assert labels(sample_chunks) == [
        (None, None),  # phần đầu: nhãn và lời cảnh báo văn bản giả
        ("Điều 1", "Khoản 1"),
        ("Điều 1", "Khoản 2"),
        ("Điều 2", "Khoản 1"),
        ("Điều 2", "Khoản 2"),
        ("Điều 3", "Khoản 1"),
        ("Điều 3", "Khoản 2"),
        ("Điều 3", "Khoản 3"),
        ("Điều 4", "Khoản 1"),
        ("Điều 4", "Khoản 2"),
        ("Điều 4", "Khoản 3"),
        ("Điều 5", "Khoản 1"),
        ("Điều 5", "Khoản 2"),
        ("Điều 5", "Khoản 3"),
        ("Điều 6", "Khoản 1"),
        ("Điều 6", "Khoản 2"),
        ("Điều 7", None),
        ("Điều 8", None),
    ]
    assert count_articles(sample_chunks) == 8


def test_clause_chunk_carries_the_article_heading_and_its_points(
    sample_chunks: list[Chunk],
) -> None:
    [chunk] = [c for c in sample_chunks if (c.article, c.clause) == ("Điều 3", "Khoản 2")]

    assert chunk.content.startswith("Điều 3. Nghỉ học và xử lý số buổi nghỉ\n2. Số buổi nghỉ")
    # Ba điểm a, b, c nằm cùng đoạn với khoản; không lẫn khoản kế tiếp.
    assert "a) Từ 12 buổi" in chunk.content
    assert "c) Quá 25 buổi" in chunk.content
    assert "3. Buổi nghỉ có lý do" not in chunk.content


def test_short_lead_in_is_prefixed_to_every_clause_of_the_article(
    sample_chunks: list[Chunk],
) -> None:
    clauses = [c for c in sample_chunks if c.article == "Điều 2"]

    assert len(clauses) == 2
    for chunk in clauses:
        assert chunk.content.startswith("Điều 2. Giải thích từ ngữ\nTrong quy chế mẫu này")
    assert "a) Nghỉ có phép" in clauses[0].content
    assert "b) Nghỉ không phép" in clauses[0].content


def test_chapter_lines_and_titles_never_become_content(sample_chunks: list[Chunk]) -> None:
    text = "\n".join(chunk.content for chunk in sample_chunks)

    for chapter_line in (
        "Chương I",
        "QUY ĐỊNH CHUNG",
        "NỀ NẾP VÀ KỶ LUẬT",
        "KHEN THƯỞNG VÀ HIỆU LỰC",
    ):
        assert chapter_line not in text


def test_no_text_of_the_sample_is_lost_except_chapter_lines_and_repeated_headings(
    sample_chunks: list[Chunk],
) -> None:
    original = SAMPLE.read_text(encoding="utf-8")
    kept = " ".join(chunk.content for chunk in sample_chunks)

    for line in original.splitlines():
        if line and not line.startswith(("Chương", "Điều")) and not line.isupper():
            assert line in kept, line


def test_every_chunk_of_the_sample_fits_the_limit(sample_chunks: list[Chunk]) -> None:
    assert all(len(chunk.content) <= MAX_CHUNK_CHARS for chunk in sample_chunks)


def test_article_without_clauses_is_a_single_chunk(sample_chunks: list[Chunk]) -> None:
    [chunk] = [c for c in sample_chunks if c.article == "Điều 7"]

    assert chunk.clause is None
    assert chunk.content.startswith("Điều 7. Khen thưởng\nHọc sinh có tiến bộ")


# --- Nhận dạng cấu trúc --------------------------------------------------------------------------


def test_empty_or_blank_text_gives_no_chunks() -> None:
    assert split_into_chunks("") == []
    assert split_into_chunks("\n  \n\t\n") == []


def test_article_number_with_letter_suffix_and_uppercase_keyword() -> None:
    text = "Điều 12a. Bổ sung\nNội dung điều mười hai a.\nĐIỀU 13: Quy định khác\nNội dung điều 13."

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 12a", None), ("Điều 13", None)]
    assert chunks[1].content == "Điều 13. Quy định khác\nNội dung điều 13."


def test_title_containing_numbers_does_not_confuse_the_parser() -> None:
    text = "Điều 5. Thời hạn 30 ngày và 2 lần\n1. Trong 30 ngày.\n2. Tối đa 2 lần."

    assert labels(split_into_chunks(text)) == [("Điều 5", "Khoản 1"), ("Điều 5", "Khoản 2")]


def test_reference_to_an_article_inside_a_wrapped_line_is_not_a_new_article() -> None:
    text = (
        "Điều 4. Áp dụng\n"
        "1. Việc này thực hiện theo\n"
        "Điều 5 của Thông tư này và các quy định liên quan.\n"
        "2. Hết."
    )

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 4", "Khoản 1"), ("Điều 4", "Khoản 2")]
    assert "Điều 5 của Thông tư này" in chunks[0].content


def test_out_of_sequence_number_is_a_continuation_not_a_new_clause() -> None:
    text = "Điều 6. Thời gian\n1. Học sinh học\n5. buổi mỗi tuần\n2. Giáo viên dạy."

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 6", "Khoản 1"), ("Điều 6", "Khoản 2")]
    assert "5. buổi mỗi tuần" in chunks[0].content


def test_decimal_numbers_are_not_clause_markers() -> None:
    text = "Điều 7. Điểm số\n1. Điểm đạt là\n3.5 điểm trở lên.\n2. Hết."

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 7", "Khoản 1"), ("Điều 7", "Khoản 2")]
    assert "3.5 điểm trở lên" in chunks[0].content


def test_article_with_only_a_heading_keeps_the_heading() -> None:
    text = "Điều 9. (Được bãi bỏ)\nĐiều 10. Có hiệu lực\nKể từ ngày ký."

    assert labels(split_into_chunks(text)) == [("Điều 9", None), ("Điều 10", None)]
    assert split_into_chunks(text)[0].content == "Điều 9. (Được bãi bỏ)"


def test_chapter_and_section_lines_close_the_previous_article() -> None:
    text = (
        "Điều 1. Một\nNội dung một.\n"
        "Chương II\nQUY ĐỊNH RIÊNG\nVỀ LỚP HỌC\n"
        "Mục 1. Lớp thường\n"
        "Điều 2. Hai\nNội dung hai."
    )

    chunks = split_into_chunks(text)

    assert [chunk.content for chunk in chunks] == [
        "Điều 1. Một\nNội dung một.",
        "Điều 2. Hai\nNội dung hai.",
    ]


def test_chapter_title_on_the_same_line_is_not_followed_by_a_swallowed_line() -> None:
    text = "Điều 1. Một\nNội dung một.\nChương II: QUY ĐỊNH RIÊNG\nĐiều 2. Hai\nNội dung hai."

    assert labels(split_into_chunks(text)) == [("Điều 1", None), ("Điều 2", None)]


def test_appendix_is_its_own_section_with_its_own_label() -> None:
    text = (
        "Điều 1. Một\nNội dung một.\n"
        "PHỤ LỤC I\nDANH MỤC MẪU\nMẫu đơn xin nghỉ học gồm họ tên và lý do.\n"
        "Phụ lục 2: Biểu mẫu\nBiểu mẫu thứ hai."
    )

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 1", None), ("Phụ lục I", None), ("Phụ lục 2", None)]
    assert chunks[1].content.startswith("PHỤ LỤC I\nDANH MỤC MẪU")
    assert "Phụ lục" not in chunks[0].content
    assert count_articles(chunks) == 1


def test_sentence_starting_with_appendix_word_is_not_an_appendix() -> None:
    text = "Điều 3. Mẫu\n1. Xem\nPhụ lục này quy định mẫu đơn.\n2. Hết."

    assert labels(split_into_chunks(text)) == [("Điều 3", "Khoản 1"), ("Điều 3", "Khoản 2")]


def test_sign_off_block_is_dropped_and_the_next_document_resumes() -> None:
    text = (
        "Điều 1. Một\nNội dung một.\n"
        "Nơi nhận:\n- Như Điều 3;\n- Lưu: VT.\n"
        "TM. HỘI ĐỒNG\nHIỆU TRƯỞNG\n"
        "Điều 1. Một khác\nNội dung của văn bản sau."
    )

    chunks = split_into_chunks(text)

    assert [chunk.content for chunk in chunks] == [
        "Điều 1. Một\nNội dung một.",
        "Điều 1. Một khác\nNội dung của văn bản sau.",
    ]


def test_two_documents_joined_restart_numbering_without_merging_or_losing_text() -> None:
    first = (
        "Điều 1. Phạm vi\n1. Văn bản A khoản một.\n2. Văn bản A khoản hai.\nĐiều 2. Hết A\nHết A."
    )
    second = "Điều 1. Phạm vi B\n1. Văn bản B khoản một.\nĐiều 2. Hết B\nHết B."

    chunks = split_into_chunks(f"{first}\n{second}")

    assert labels(chunks) == [
        ("Điều 1", "Khoản 1"),
        ("Điều 1", "Khoản 2"),
        ("Điều 2", None),
        ("Điều 1", "Khoản 1"),
        ("Điều 2", None),
    ]
    assert "Văn bản B khoản một" in chunks[3].content
    assert "Văn bản A" not in chunks[3].content


# --- Phần đầu và dòng dẫn ------------------------------------------------------------------------


def test_preamble_is_kept_only_when_long_enough() -> None:
    short = "Căn cứ Luật Giáo dục.\nĐiều 1. Một\nNội dung."
    long_preamble = "Căn cứ " + "Luật Giáo dục và các văn bản hướng dẫn thi hành. " * 6

    assert labels(split_into_chunks(short)) == [("Điều 1", None)]
    assert len(long_preamble) >= LOOSE_MIN_CHARS
    chunks = split_into_chunks(f"{long_preamble}\nĐiều 1. Một\nNội dung.")
    assert labels(chunks) == [(None, None), ("Điều 1", None)]
    assert chunks[0].content.startswith("Căn cứ Luật Giáo dục")


def test_long_lead_in_becomes_its_own_chunk() -> None:
    lead = "Trong văn bản này các từ ngữ được hiểu như sau, " + "chi tiết và đầy đủ " * 20 + ":"
    assert len(lead) >= LEAD_IN_OWN_CHUNK_CHARS
    text = f"Điều 2. Giải thích\n{lead}\n1. Từ một.\n2. Từ hai."

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 2", None), ("Điều 2", "Khoản 1"), ("Điều 2", "Khoản 2")]
    assert chunks[0].content == f"Điều 2. Giải thích\n{lead}"
    assert chunks[1].content == "Điều 2. Giải thích\n1. Từ một."


# --- Đoạn quá dài --------------------------------------------------------------------------------


def long_point(letter: str, sentences: int) -> str:
    body = " ".join(
        f"Câu {i} của điểm {letter} nói về quy định chi tiết." for i in range(sentences)
    )
    return f"{letter}) {body}"


def test_overlong_clause_is_split_by_point_and_keeps_heading_intro_and_metadata() -> None:
    points = "\n".join(long_point(letter, 22) for letter in "abc")
    text = f"Điều 8. Xử lý\n1. Việc xử lý gồm các điểm sau:\n{points}\n2. Khoản hai ngắn."

    chunks = split_into_chunks(text)

    assert [c.clause for c in chunks] == [
        "Khoản 1, điểm a",
        "Khoản 1, điểm b",
        "Khoản 1, điểm c",
        "Khoản 2",
    ]
    for chunk in chunks[:3]:
        assert chunk.article == "Điều 8"
        assert chunk.content.startswith("Điều 8. Xử lý\n1. Việc xử lý gồm các điểm sau:\n")
        assert len(chunk.content) <= MAX_CHUNK_CHARS
    assert "b) Câu 0" in chunks[1].content
    assert "a) Câu" not in chunks[1].content


def test_overlong_clause_without_points_is_split_by_sentence_without_losing_words() -> None:
    sentences = [f"Câu số {i} quy định một nghĩa vụ riêng của học sinh." for i in range(80)]
    body = " ".join(sentences)
    text = f"Điều 9. Nghĩa vụ\n1. {body}"

    chunks = split_into_chunks(text)

    assert len(chunks) > 1
    assert {(c.article, c.clause) for c in chunks} == {("Điều 9", "Khoản 1")}
    assert all(c.content.startswith("Điều 9. Nghĩa vụ\n") for c in chunks)
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    rebuilt = [w for c in chunks for w in words(c.content.removeprefix("Điều 9. Nghĩa vụ\n"))]
    assert rebuilt == words(f"1. {body}")
    # Cắt ở ranh giới câu: mọi đoạn đều kết thúc bằng dấu chấm.
    assert all(c.content.endswith(".") for c in chunks)


def test_single_overlong_sentence_without_punctuation_is_still_split_and_terminates() -> None:
    body = " ".join(f"từ{i}" for i in range(2500))
    text = f"Điều 9. Dài\n1. {body}"

    chunks = split_into_chunks(text)

    assert len(chunks) > 2
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)
    rebuilt = [w for c in chunks for w in words(c.content.removeprefix("Điều 9. Dài\n"))]
    assert rebuilt == words(f"1. {body}")


def test_overlong_article_without_clauses_is_split_by_point_with_point_label() -> None:
    points = "\n".join(long_point(letter, 22) for letter in "abc")
    text = f"Điều 10. Danh mục\nGồm các mục sau:\n{points}"

    chunks = split_into_chunks(text)

    assert [(c.article, c.clause) for c in chunks] == [
        ("Điều 10", "Điểm a"),
        ("Điều 10", "Điểm b"),
        ("Điều 10", "Điểm c"),
    ]
    assert all(c.content.startswith("Điều 10. Danh mục\nGồm các mục sau:\n") for c in chunks)


def test_first_point_must_be_a_so_a_stray_letter_line_does_not_split() -> None:
    points = "\n".join(long_point(letter, 30) for letter in "bc")
    text = f"Điều 11. Lẻ\n1. Phần dẫn:\n{points}"
    assert len(text) > MAX_CHUNK_CHARS

    chunks = split_into_chunks(text)

    # Không có điểm a): không tách theo điểm, chỉ tách theo câu và vẫn mang nhãn khoản.
    assert len(chunks) > 1
    assert {c.clause for c in chunks} == {"Khoản 1"}


# --- Chuẩn hoá -----------------------------------------------------------------------------------


def test_normalize_text_composes_unicode_and_cleans_invisible_characters() -> None:
    decomposed = unicodedata.normalize("NFD", "Điều 3. Nghỉ học")
    zero_width, nbsp, soft_hyphen = "\N{ZERO WIDTH SPACE}", "\N{NO-BREAK SPACE}", "\N{SOFT HYPHEN}"
    messy = f"  {decomposed}{zero_width}\r\n{nbsp}Nội\t\tdung   hai{soft_hyphen} \r"

    assert decomposed != "Điều 3. Nghỉ học"
    assert normalize_text(messy) == "Điều 3. Nghỉ học\nNội dung hai\n"


def test_decomposed_vietnamese_headings_are_recognised() -> None:
    text = unicodedata.normalize("NFD", "Điều 1. Một\n1. Nội dung một.\n2. Nội dung hai.")

    chunks = split_into_chunks(text)

    assert labels(chunks) == [("Điều 1", "Khoản 1"), ("Điều 1", "Khoản 2")]
    assert chunks[0].content == "Điều 1. Một\n1. Nội dung một."

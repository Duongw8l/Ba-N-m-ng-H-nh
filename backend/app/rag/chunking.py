"""Tách văn bản quy định thành các đoạn theo cấu trúc Điều/Khoản (Giai đoạn 7, D-078).

Hàm thuần: nhận văn bản đã đọc ra chữ, trả về danh sách `Chunk`. Không đụng DB, không đụng mô hình.

Quy tắc (chi tiết và lý do trong docs/DECISIONS.md):
- Không cắt theo số ký tự cố định. Ranh giới đoạn là ranh giới pháp lý: mỗi KHOẢN là một đoạn, kèm
  dòng tiêu đề của điều ("Điều 3. Nghỉ học...") để trích dẫn và để vector hiểu ngữ cảnh. Điều không
  có khoản là một đoạn. Điểm (a, b, c) nằm trong đoạn của khoản.
- Chỉ khoản/điều quá dài (> MAX_CHUNK_CHARS) mới bị tách tiếp: trước hết theo điểm, rồi theo câu.
  Mọi đoạn tách ra vẫn mang tiêu đề điều, dòng dẫn của khoản và metadata (Điều, Khoản, điểm).
- Dòng dẫn trước khoản 1 ("Trong quy chế này...:") ngắn thì ghép vào đầu mỗi khoản; dài thì là một
  đoạn riêng.
- "Chương", "Mục" (và dòng tên chương đi kèm) chỉ là ranh giới, không thành đoạn. "Phụ lục" là một
  mục riêng. Phần trước Điều 1 (căn cứ...) là một đoạn không có Điều nếu đủ dài.
- Số khoản phải liên tiếp (1, 2, 3...) mới được coi là khoản mới: dòng bị ngắt có thể bắt đầu bằng
  "2." mà không phải khoản. Điểm đầu tiên phải là "a)".
- Phần "Nơi nhận:" và khối chữ ký cuối văn bản bị bỏ.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

# Khoản/điều dài hơn mức này mới bị tách tiếp (khoảng 500 token tiếng Việt).
MAX_CHUNK_CHARS = 2000
# Mức tối thiểu của phần thân khi tách theo câu, kể cả khi tiêu đề + dòng dẫn đã dài.
MIN_PIECE_CHARS = 400
# Dòng dẫn trước khoản 1 từ mức này trở lên thì thành đoạn riêng thay vì ghép vào từng khoản.
LEAD_IN_OWN_CHUNK_CHARS = 300
# Phần không thuộc Điều nào (căn cứ...) ngắn hơn mức này thì bỏ.
LOOSE_MIN_CHARS = 200

_ARTICLE = re.compile(r"^điều\s+(?P<number>\d+[a-z]?)\s*[.:]\s*(?P<title>.*)$", re.IGNORECASE)
_CHAPTER = re.compile(r"^(?P<kind>chương|mục)\s+(?:[ivxlcdm]+|\d+)\b(?P<rest>.*)$", re.IGNORECASE)
_APPENDIX = re.compile(
    r"^phụ\s+lục\s*(?P<id>[ivxlcdm]+|\d+|[a-z])?\s*(?:[.:–—-].*)?$", re.IGNORECASE
)
_CLAUSE = re.compile(r"^(?P<number>\d{1,2})\.(?:\s+(?P<text>\S.*))?$")
_POINT = re.compile(r"^(?P<letter>[a-zđ])\s*\)\s+\S", re.IGNORECASE)
# "Nơi nhận:" và khối chữ ký ("TM. HỘI ĐỒNG", "KT. BỘ TRƯỞNG"...) ở cuối văn bản.
_SIGNOFF = re.compile(r"^(?:nơi\s+nhận\s*:|(?:tm|kt|tl|tuq)\.\s+\S)", re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"(?<=[.;:!?])(\s+)")

# Ký tự vô hình hay lẫn trong PDF/DOCX; thay bằng khoảng trắng hoặc bỏ.
_AS_SPACE = "\N{NO-BREAK SPACE}\t"
_DROPPED = (
    "\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
    "\N{ZERO WIDTH NO-BREAK SPACE}\N{SOFT HYPHEN}"
)
_CLEAN_TABLE = str.maketrans({**dict.fromkeys(_AS_SPACE, " "), **dict.fromkeys(_DROPPED, None)})


@dataclass(frozen=True)
class Chunk:
    article: str | None  # "Điều 12", "Điều 12a", "Phụ lục I"; None nếu không thuộc điều nào
    clause: str | None  # "Khoản 1", "Khoản 1, điểm a", "Điểm a"; None nếu cả điều
    content: str  # nguyên văn, bắt đầu bằng dòng tiêu đề điều


@dataclass
class _Section:
    kind: Literal["loose", "article", "appendix"]
    label: str | None = None
    heading: str = ""
    lines: list[str] = field(default_factory=list)


@dataclass
class _Clause:
    number: int
    lines: list[str]  # dòng đầu có cả số khoản


def normalize_text(text: str) -> str:
    """NFC, bỏ ký tự vô hình, gộp khoảng trắng, cắt hai đầu mỗi dòng. Giữ nguyên các dòng."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_CLEAN_TABLE)
    return "\n".join(re.sub(r" {2,}", " ", line).strip() for line in text.split("\n"))


def split_into_chunks(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in _read_sections(normalize_text(text)):
        if section.kind == "article":
            chunks.extend(_article_chunks(section))
        elif section.kind == "appendix":
            chunks.extend(_appendix_chunks(section))
        else:
            chunks.extend(_loose_chunks(section))
    return chunks


def count_articles(chunks: list[Chunk]) -> int:
    """Số điều khác nhau (không tính phụ lục và phần không thuộc điều nào)."""
    return len({c.article for c in chunks if c.article and c.article.startswith("Điều")})


# --- Đọc cấu trúc ---------------------------------------------------------------------------------


def _read_sections(text: str) -> list[_Section]:
    sections: list[_Section] = []
    current = _Section("loose")
    skipping = False  # đang ở khối "Nơi nhận:" cho tới dòng cấu trúc kế tiếp
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line:
            continue
        if article := _ARTICLE.match(line):
            sections.append(current)
            title = article["title"].strip()
            number = article["number"]
            heading = f"Điều {number}. {title}" if title else f"Điều {number}"
            current = _Section("article", f"Điều {number}", heading)
            skipping = False
        elif chapter := _CHAPTER.match(line):
            sections.append(current)
            current = _Section("loose")
            skipping = False
            if not chapter["rest"].strip(" .:–—-"):  # tên chương nằm ở dòng sau
                index = _skip_chapter_title(lines, index)
        elif appendix := _APPENDIX.match(line):
            sections.append(current)
            label = f"Phụ lục {appendix['id'].upper()}" if appendix["id"] else "Phụ lục"
            current = _Section("appendix", label, line)
            skipping = False
        elif _SIGNOFF.match(line):
            sections.append(current)
            current = _Section("loose")
            skipping = True
        elif not skipping:
            current.lines.append(line)
    sections.append(current)
    return sections


def _is_structural(line: str) -> bool:
    return bool(_ARTICLE.match(line) or _CHAPTER.match(line) or _APPENDIX.match(line))


def _is_upper(line: str) -> bool:
    return line == line.upper() and any(char.isalpha() for char in line)


def _skip_chapter_title(lines: list[str], index: int) -> int:
    """Bỏ tên chương ở các dòng sau "Chương I": dòng đầu bất kể kiểu chữ, dòng sau nếu IN HOA."""
    consumed = False
    while index < len(lines):
        line = lines[index]
        if not line:
            if consumed:
                break
            index += 1
            continue
        if _is_structural(line) or _CLAUSE.match(line):
            break
        if consumed and not _is_upper(line):
            break
        consumed = True
        index += 1
    return index


def _split_clauses(lines: list[str]) -> tuple[list[str], list[_Clause]]:
    """Tách thân điều thành (dòng dẫn trước khoản 1, các khoản). Số khoản phải liên tiếp từ 1."""
    lead: list[str] = []
    clauses: list[_Clause] = []
    for line in lines:
        match = _CLAUSE.match(line)
        if match and int(match["number"]) == len(clauses) + 1:
            clauses.append(_Clause(len(clauses) + 1, [line]))
        elif clauses:
            clauses[-1].lines.append(line)
        else:
            lead.append(line)
    return lead, clauses


def _split_points(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Tách thành (phần trước điểm đầu tiên, các điểm). Điểm đầu tiên phải là "a)"."""
    intro: list[str] = []
    points: list[tuple[str, list[str]]] = []
    for line in lines:
        match = _POINT.match(line)
        letter = match["letter"].lower() if match else ""
        if match and (points or letter == "a"):
            points.append((letter, [line]))
        elif points:
            points[-1][1].append(line)
        else:
            intro.append(line)
    return intro, points


# --- Dựng đoạn ------------------------------------------------------------------------------------


def _join(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


def _article_chunks(section: _Section) -> list[Chunk]:
    article = section.label
    lead, clauses = _split_clauses(section.lines)
    if not clauses:
        return _body_chunks(article, section.heading, lead)

    chunks: list[Chunk] = []
    lead_text = "\n".join(lead)
    prefix = section.heading
    if len(lead_text) >= LEAD_IN_OWN_CHUNK_CHARS:
        chunks.extend(Chunk(article, None, piece) for piece in _fit(section.heading, lead_text))
    elif lead_text:
        prefix = _join(section.heading, lead_text)
    for clause in clauses:
        chunks.extend(_clause_chunks(article, prefix, clause))
    return chunks


def _body_chunks(article: str | None, heading: str, lines: list[str]) -> list[Chunk]:
    """Điều không có khoản: một đoạn; quá dài thì tách theo điểm rồi theo câu."""
    body = "\n".join(lines)
    if len(_join(heading, body)) <= MAX_CHUNK_CHARS:
        return [Chunk(article, None, _join(heading, body))]
    intro, points = _split_points(lines)
    if len(points) < 2:
        return [Chunk(article, None, piece) for piece in _fit(heading, body)]
    base = _join(heading, "\n".join(intro))
    return [
        Chunk(article, f"Điểm {letter}", piece)
        for letter, point_lines in points
        for piece in _fit(base, "\n".join(point_lines))
    ]


def _clause_chunks(article: str | None, prefix: str, clause: _Clause) -> list[Chunk]:
    label = f"Khoản {clause.number}"
    body = "\n".join(clause.lines)
    if len(_join(prefix, body)) <= MAX_CHUNK_CHARS:
        return [Chunk(article, label, _join(prefix, body))]
    intro, points = _split_points(clause.lines)
    if len(points) < 2:
        return [Chunk(article, label, piece) for piece in _fit(prefix, body)]
    base = _join(prefix, "\n".join(intro))
    return [
        Chunk(article, f"{label}, điểm {letter}", piece)
        for letter, point_lines in points
        for piece in _fit(base, "\n".join(point_lines))
    ]


def _appendix_chunks(section: _Section) -> list[Chunk]:
    body = "\n".join(section.lines)
    if not body:
        return []
    return [Chunk(section.label, None, piece) for piece in _fit(section.heading, body)]


def _loose_chunks(section: _Section) -> list[Chunk]:
    body = "\n".join(section.lines)
    if len(body) < LOOSE_MIN_CHARS:
        return []
    return [Chunk(None, None, piece) for piece in _fit("", body)]


# --- Tách theo câu khi một đoạn vẫn quá dài ------------------------------------------------------


def _fit(prefix: str, body: str) -> list[str]:
    """Các đoạn "prefix + phần thân" không dài quá MAX_CHUNK_CHARS (trừ khi tiêu đề đã quá dài)."""
    whole = _join(prefix, body)
    if len(whole) <= MAX_CHUNK_CHARS:
        return [whole]
    budget = max(MAX_CHUNK_CHARS - len(prefix) - 1, MIN_PIECE_CHARS)
    return [_join(prefix, piece) for piece in _pack_sentences(body, budget)]


def _pack_sentences(body: str, budget: int) -> list[str]:
    parts = _SENTENCE_BREAK.split(body)  # [câu, dấu cách, câu, dấu cách, ..., câu]
    units: list[str] = []
    for index in range(0, len(parts), 2):
        separator = parts[index + 1] if index + 1 < len(parts) else ""
        units.extend(_hard_wrap(parts[index] + separator, budget))

    pieces: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) > budget:
            pieces.append(current)
            current = ""
        current += unit
    pieces.append(current)
    return [piece.strip() for piece in pieces if piece.strip()]


def _hard_wrap(unit: str, budget: int) -> list[str]:
    """Câu dài hơn `budget` thì cắt ở dấu cách gần nhất trước giới hạn (luôn tiến được)."""
    wrapped: list[str] = []
    while len(unit) > budget:
        cut = unit.rfind(" ", 0, budget)
        if cut < budget // 2:
            cut = budget
        wrapped.append(unit[:cut])
        unit = unit[cut:]
    wrapped.append(unit)
    return wrapped

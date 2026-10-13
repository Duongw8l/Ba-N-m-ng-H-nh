"""Đánh giá RAG văn bản quy định bằng mô hình embedding THẬT (Giai đoạn 7, D-083).

Chạy: `make eval-rag` hoặc
`python eval/rag_eval.py [--threshold 0.56] [--questions eval/rag_questions.json]`.

Cần: DB đã migrate, văn bản trong câu hỏi đã được nạp (`make regulations`) và mô hình đã tải
(`make rag-model`). In cho từng câu độ tương đồng cao nhất và kết quả, rồi hai chỉ số của DESIGN
mục 9:
- Hit@4: tỉ lệ câu TRONG phạm vi có ít nhất một trong 4 đoạn đầu thuộc điều đúng ("tìm đúng
  điều"). Câu bị từ chối nhầm (found=False) tính là trượt.
- Tỉ lệ từ chối đúng: tỉ lệ câu NGOÀI phạm vi được trả "không tìm thấy" (found=False).
Mục tiêu của DESIGN là ≥ 80%. Mã thoát 0 nếu cả hai đạt, 1 nếu chưa đạt, 2 nếu thiếu điều kiện
chạy.

`--threshold` thử một ngưỡng khác mà không sửa bảng settings (đổi trong một transaction rồi hoàn
tác). Chỉ số "% trả lời đúng" của DESIGN cần LLM nên đo ở Giai đoạn 10, không ở đây.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.core.db import get_session_factory  # noqa: E402
from app.core.enums import RegulationStatus  # noqa: E402
from app.core.models import Setting  # noqa: E402
from app.rag.embedding import EmbeddingUnavailable  # noqa: E402
from app.rag.models import RegulationDocument  # noqa: E402
from app.rag.search import SearchResult, search_regulation  # noqa: E402

DEFAULT_QUESTIONS = REPO_ROOT / "eval" / "rag_questions.json"
TARGET = 0.8  # DESIGN mục 9: ≥ 80%
K = 4


def vn(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}".replace(".", ",")


def percent(count: int, total: int) -> str:
    return f"{count}/{total} = {100 * count / total:.0f}%".replace(".", ",") if total else "—"


def _best_hit_text(result: SearchResult) -> str:
    if not result.hits:
        return "không có đoạn nào qua ngưỡng"
    top = result.hits[0]
    return f"{top.article} {top.clause or '(cả điều)'}"


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá RAG văn bản quy định.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--threshold", type=float, default=None, help="thử ngưỡng khác (không lưu)")
    args = parser.parse_args(argv)

    data = json.loads(args.questions.read_text(encoding="utf-8"))
    in_scope: list[dict] = data["in_scope"]
    out_of_scope: list[dict] = data["out_of_scope"]

    try:
        with get_session_factory()() as session:
            document = session.scalar(
                select(RegulationDocument).where(
                    RegulationDocument.name == data["document"],
                    RegulationDocument.status == RegulationStatus.ACTIVE,
                )
            )
            if document is None:
                print(
                    f'Chưa nạp văn bản còn hiệu lực "{data["document"]}". Chạy make regulations.',
                    file=sys.stderr,
                )
                return 2
            if args.threshold is not None:
                session.execute(
                    update(Setting)
                    .where(Setting.key == "rag_min_similarity")
                    .values(value=args.threshold)
                )

            print(f"Văn bản: {data['document']}")
            hits_ok = clause_ok = clause_total = 0
            print("\n== Câu TRONG phạm vi ==")
            for item in in_scope:
                result = search_regulation(session, item["question"], K)
                found_articles = [hit.article for hit in result.hits]
                hit = any(article in found_articles for article in item["articles"])
                hits_ok += hit
                clause_note = ""
                if item.get("clause"):
                    clause_total += 1
                    right_clause = any(
                        h.article in item["articles"] and h.clause == item["clause"]
                        for h in result.hits
                    )
                    clause_ok += right_clause
                    clause_note = (
                        f" (khoản {'đúng' if right_clause else 'KHÔNG đúng'} trong top {K})"
                    )
                verdict = "ĐÚNG " if hit else "TRƯỢT"
                print(
                    f"{verdict} {item['id']} tương đồng {vn(result.best_similarity)}"
                    f" -> {_best_hit_text(result)}{clause_note}"
                )
                print(f"        hỏi: {item['question']}  (mong đợi: {', '.join(item['articles'])})")

            refused_ok = 0
            print("\n== Câu NGOÀI phạm vi ==")
            for item in out_of_scope:
                result = search_regulation(session, item["question"], K)
                refused = not result.found
                refused_ok += refused
                print(
                    f"{'ĐÚNG ' if refused else 'TRƯỢT'} {item['id']} tương đồng "
                    f"{vn(result.best_similarity)} -> "
                    f"{'từ chối' if refused else 'LẠI TRẢ ' + _best_hit_text(result)}"
                )
                print(f"        hỏi: {item['question']}")
            threshold = result.min_similarity
            session.rollback()  # hoàn tác --threshold
    except OperationalError:
        print("Không kết nối được PostgreSQL. Chạy make db và make migrate.", file=sys.stderr)
        return 2
    except EmbeddingUnavailable as error:
        print(str(error), file=sys.stderr)
        return 2

    hit_rate = hits_ok / len(in_scope)
    refuse_rate = refused_ok / len(out_of_scope)
    print(f"\nNgưỡng rag_min_similarity: {vn(threshold)}" + (" (thử)" if args.threshold else ""))
    print(f"Hit@{K} (tìm đúng điều): {percent(hits_ok, len(in_scope))}")
    print(f"  (khoản đúng, chỉ để tham khảo): {percent(clause_ok, clause_total)}")
    print(f"Từ chối đúng câu ngoài phạm vi: {percent(refused_ok, len(out_of_scope))}")
    print(
        f"Mục tiêu DESIGN ≥ {TARGET:.0%}: "
        f"{'ĐẠT' if hit_rate >= TARGET and refuse_rate >= TARGET else 'CHƯA ĐẠT'} "
        f"(mẫu quá nhỏ để kết luận: {len(in_scope)} + {len(out_of_scope)} câu)"
    )
    return 0 if hit_rate >= TARGET and refuse_rate >= TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())

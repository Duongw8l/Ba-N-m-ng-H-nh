"""Nạp văn bản quy định từ dòng lệnh (D-081).

- `make regulations` (hay `python -m app.rag.ingest [--dir data/regulations]`): nạp mọi tệp
  .pdf/.docx/.txt trong thư mục. Tên hiển thị lấy từ `manifest.json` trong thư mục đó, không có thì
  dùng tên tệp bỏ đuôi. Tệp có tên đã nạp và còn hiệu lực thì bỏ qua, nên chạy lại bao nhiêu lần
  cũng an toàn. Không giới hạn số đoạn (khác tải lên qua web).
- `make rag-model` (hay `--download-model`): tải sẵn mô hình embedding (~2,3 GB lần đầu) và kiểm tra
  số chiều khớp cấu hình.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.rag import repository as repo
from app.rag.embedding import EmbeddingUnavailable, get_embedder
from app.rag.parsing import SUPPORTED_EXTENSIONS, DocumentError
from app.rag.service import DuplicateDocument, ingest_document

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "regulations"
MANIFEST = "manifest.json"


def load_manifest(directory: Path) -> dict[str, str]:
    path = directory / MANIFEST
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError(f'{MANIFEST} phải là JSON dạng {{"tên tệp": "tên hiển thị"}}.')
    return value


def ingest_directory(directory: Path) -> int:
    """Nạp thư mục; trả số tệp lỗi."""
    files = sorted(
        path for path in directory.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        print(f"Không có tệp {', '.join(SUPPORTED_EXTENSIONS)} nào trong {directory}.")
        return 0
    manifest = load_manifest(directory)
    embedder = get_embedder()
    failures = 0
    with get_session_factory()() as session:
        for path in files:
            name = " ".join(manifest.get(path.name, path.stem).split())
            if repo.active_document_with_name(session, name) is not None:
                print(f'Bỏ qua {path.name}: đã nạp "{name}" (còn hiệu lực).')
                continue
            print(f'Đang nạp {path.name} thành "{name}" ...', flush=True)
            try:
                result = ingest_document(
                    session,
                    name=name,
                    file_name=path.name,
                    data=path.read_bytes(),
                    embedder=embedder,
                    user=None,
                    max_chunks=None,
                )
            except (DocumentError, DuplicateDocument) as error:
                failures += 1
                print(f"  LỖI {path.name}: {error}", file=sys.stderr)
                continue
            print(f"  xong: {result.article_count} điều, {result.chunk_count} đoạn.")
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(prog="make regulations", description="Nạp văn bản quy định.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="thư mục chứa văn bản")
    parser.add_argument(
        "--download-model", action="store_true", help="chỉ tải sẵn mô hình embedding rồi thoát"
    )
    args = parser.parse_args(argv)

    try:
        if args.download_model:
            embedder = get_embedder()
            embedder.embed_query("kiểm tra mô hình")
            print(f"Mô hình {get_settings().embedding_model} sẵn sàng ({embedder.dim} chiều).")
            return 0
        if not args.dir.is_dir():
            print(f"Không có thư mục {args.dir}.", file=sys.stderr)
            return 1
        failures = ingest_directory(args.dir)
    except EmbeddingUnavailable as error:
        print(str(error), file=sys.stderr)
        return 1
    except OperationalError:
        print(
            "Không kết nối được PostgreSQL. Chạy make db rồi make migrate trước "
            "(DATABASE_URL trong .env, host 127.0.0.1).",
            file=sys.stderr,
        )
        return 1
    except (ValueError, OSError) as error:  # manifest hỏng, không đọc được tệp
        print(str(error), file=sys.stderr)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

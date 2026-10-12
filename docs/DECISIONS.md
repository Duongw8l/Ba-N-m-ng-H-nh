# Quyết định thiết kế

Ghi lại các quyết định phát sinh trong quá trình làm, kèm lý do. Nguồn của mỗi mục:

- **Đã duyệt**: nằm trong kế hoạch Giai đoạn 0 mà bạn đã duyệt (2026-10-12).
- **Khi làm**: phát sinh lúc triển khai, chờ bạn xem lại.

Quyết định đã chốt chỉ đổi bằng cách ghi thêm một mục mới thay thế mục cũ.

## Giai đoạn 0

### Thiết kế và phạm vi

**D-001 · `/health` là endpoint công khai, ngoại lệ của nguyên tắc 4** (Đã duyệt)
- Quyết định: `GET /api/v1/health` không qua `authorize()`. Nó chỉ trả trạng thái, không trả dữ liệu học sinh; lỗi DB chỉ ghi log phía máy chủ, không đưa ra response.
- Swagger (`/api/docs`, `/api/openapi.json`) cũng công khai khi phát triển và tắt khi `APP_ENV=production`. Phần Swagger do tôi thêm khi làm, chờ bạn xác nhận.
- Lý do: trang chủ gọi nó trước khi đăng nhập; Docker healthcheck không có token.
- Ảnh hưởng: mọi endpoint khác vẫn phải qua `authorize()`. Quy ước "test phân quyền cho cả 4 vai trò" không áp dụng cho `/health`.

**D-002 · Dạng JSON của `/health`** (Đã duyệt)
- `{"status":"ok","db":true|false}`, luôn HTTP 200 (theo PROMPTS.md). `status` cho biết API còn sống, `db` cho biết kết nối DB.
- Lý do: giao diện đọc trường `db` để hiện trạng thái riêng. Tình trạng sống của container backend được kiểm bằng cách khác (xem D-019), vì `/health` phụ thuộc DB.

**D-003 · Khởi tạo Alembic ngay ở Giai đoạn 0** (Đã duyệt)
- Có `alembic.ini`, `alembic/env.py` (lấy URL từ Settings), `versions/` rỗng; `target_metadata = None` cho tới Giai đoạn 1. Chưa có migration và chưa có bảng nghiệp vụ; `make migrate` chạy thật, chỉ tạo bảng `alembic_version` (rỗng) do chính Alembic quản lý.
- `file_template` có tiền tố ngày giờ để các migration sắp theo thời gian.
- Extension `vector` của pgvector chưa được bật. Migration đầu tiên cần tới nó (Giai đoạn 1 hoặc 7) sẽ chứa `CREATE EXTENSION IF NOT EXISTS vector`.

**D-004 · Chưa có test front-end ở Giai đoạn 0** (Đã duyệt)
- Front-end trong CI: eslint, `tsc -b`, `vite build`. Vitest (kèm test trang chủ) thêm ở Giai đoạn 5.

**D-005 · Git và file thừa ở thư mục gốc** (Đã duyệt)
- `git init -b main`; toàn bộ Giai đoạn 0 nằm trong một commit `chore: khởi tạo bộ khung dự án`. `claude-code-kit/`, `claude-code-kit.zip`, `*.docx` và bản gốc `Thiết kế hệ thống….md` bị `.gitignore` chặn, không bị xoá hay di chuyển.
- `PROMPTS.md` được chuyển vào `docs/PROMPTS.md` theo yêu cầu của bạn (gom mọi tài liệu vào `docs/`).

**D-006 · Khi PROMPTS.md lệch prompt Giai đoạn 0, theo prompt Giai đoạn 0** (Đã duyệt)
- Thông báo của lệnh chưa làm là "chưa triển khai" (PROMPTS.md ghi "chưa làm").
- Danh sách biến `.env` lấy theo PROMPTS.md vì đủ hơn (có `LLM_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`).
- Cấu trúc repo theo CLAUDE.md (DESIGN.md mục 11 thiếu `rag/` và `core/`).
- `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL` để trống vì tài liệu chưa chốt (API hay ollama; bge-m3 hay multilingual-e5).

### Back-end

**D-007 · Quản lý gói Python: pip + `pyproject.toml`, ghim phiên bản chính xác** (Đã duyệt)
- setuptools làm build backend nhưng `packages = []`: ứng dụng chạy thẳng từ `backend/` (`uvicorn app.main:app`), không đóng gói. pip chỉ dùng file này để cài dependency, nên Docker cache được lớp cài đặt.
- Lý do: máy chưa có `uv`; PROMPTS.md yêu cầu "có ghi phiên bản". Nâng phiên bản là quyết định có chủ đích: sửa số, rồi chạy lại `make lint` và `make test`.

**D-008 · SQLAlchemy ghim 2.0.54, không lên 2.1.4** (Khi làm)
- CLAUDE.md và PROMPTS.md ghi SQLAlchemy 2.0. Bản 2.1.x đã phát hành nhưng tài liệu của dự án viết cho 2.0. Nâng lên 2.1 làm riêng, có chủ đích.

**D-009 · SQLAlchemy đồng bộ + psycopg 3 (`postgresql+psycopg://`)** (Đã duyệt)
- Hợp với pandas và scikit-learn (đồng bộ); FastAPI chạy endpoint `def` trong threadpool. Đổi sang async về sau là việc lớn nên chốt sớm.
- `get_db()` cấp một Session mỗi request. Engine được tạo lười (lần đầu dùng), `pool_pre_ping=True`.

**D-010 · `connect_timeout=3` và `DATABASE_URL` dùng `127.0.0.1`** (Khi làm)
- Đo trên Windows: khi cổng DB đóng, libpq chờ trọn timeout cho mỗi địa chỉ. `localhost` phân giải ra 2 địa chỉ (IPv6 và IPv4) nên `/health` mất 10 giây với timeout 5; sau chỉnh còn 3 giây. Trong Docker (Linux) lỗi trả về ngay.
- Compose cũng chỉ mở cổng DB trên `127.0.0.1`, nên URL ngoài Docker dùng đúng địa chỉ đó.
- Trong Docker, khi container `db` bị tắt, `/health` vẫn trả `db:false` nhưng mất ~4 giây (DNS của Docker không phân giải được `db`, việc này nằm ngoài `connect_timeout`). Vì thế healthcheck của backend không gọi `/health` (xem D-019).

**D-011 · Settings: biến bắt buộc không có giá trị mặc định** (Khi làm)
- `DATABASE_URL` và `JWT_SECRET` bắt buộc: thiếu thì báo lỗi ngay khi khởi động. Biến LLM/RAG khai báo sẵn (để `.env.example` và Settings luôn đồng bộ) nhưng chưa dùng. `APP_ENV` chỉ nhận `development` hoặc `production`.
- Settings đọc `.env` ở gốc repo bằng đường dẫn tuyệt đối tính từ `config.py`; biến môi trường thật thắng giá trị trong `.env`.

**D-012 · Test `/health`** (Đã duyệt)
- Một hàm test tham số hoá 2 trường hợp (DB ok, DB lỗi), thay Session bằng bản giả nên không cần Docker. `conftest.py` ghi đè biến môi trường bằng giá trị giả để test không bao giờ đụng `.env` hay DB thật.
- Dev-dependency dùng `httpx2` thay `httpx`: Starlette 1.7 đã cảnh báo deprecated khi `TestClient` chạy trên `httpx`.

**D-013 · Bố cục package** (Khi làm)
- Router và schema của `/health` đặt ở `app/core/health.py` (CLAUDE.md không có chỗ riêng cho endpoint hạ tầng).
- `__init__.py` chỉ có ở `app/` và `app/core/`; thư mục module chưa dùng chỉ có `.gitkeep` (thêm `__init__.py` khi làm module). `tests/` phản chiếu `app/` và dùng `--import-mode=importlib` nên không cần `__init__.py`.
- Chưa cài pandas, openpyxl, scikit-learn, sentence-transformers: Giai đoạn 0 không dùng, tránh image nặng.

**D-014 · `alembic.ini` chỉ được chứa ký tự ASCII** (Khi làm)
- Alembic đọc file này theo bảng mã mặc định của Windows (cp1252); chú thích tiếng Việt có dấu gây `UnicodeDecodeError`. Đã ghi chú ngay trong file.

### Front-end

**D-015 · Bộ phiên bản theo template `create-vite` 9.2.1** (Khi làm)
- Giữ nguyên bộ phiên bản template đã kiểm chứng chạy cùng nhau (Vite 8, ESLint 10, TypeScript ~6.0, typescript-eslint 8). Không tự nâng lên TypeScript 7.
- `create-vite` 9 mặc định dùng Oxlint; đã chọn `--eslint` theo yêu cầu.
- Tailwind v4 qua plugin `@tailwindcss/vite` (không cần file cấu hình).

**D-016 · Kiểm kiểu bằng `tsc -b`** (Đã duyệt)
- Khung Vite chia tsconfig theo project references (`"files": []` ở gốc), nên `tsc --noEmit` ở gốc không kiểm tra gì.

**D-017 · Script npm không dùng `&&`** (Khi làm)
- `~/.npmrc` của máy phát triển đặt `script-shell` là Windows PowerShell 5.1, không hiểu `&&`; script `build` mặc định của template (`tsc -b && vite build`) bị lỗi. Đã đổi thành hook `prebuild` (`tsc -b`) rồi `build` (`vite build`), chạy đúng trên mọi shell. Không đổi cấu hình npm cá nhân.

**D-018 · Trang chủ và trang 404** (Khi làm)
- Trang chủ hiện 2 dòng ("Máy chủ", "Cơ sở dữ liệu") với trạng thái ok, lỗi, đang kiểm tra hoặc không xác định; tự làm mới mỗi 15 giây khi tab đang hiển thị (tab ở nền thì tạm dừng, quay lại tab thì làm mới ngay: mặc định của TanStack Query). Có thêm trang 404 bằng tiếng Việt (ngoài danh sách yêu cầu, rất nhỏ).
- Front-end gọi đường dẫn tương đối `/api/v1`: qua proxy của Vite khi phát triển, nên không cần CORS.

### Hạ tầng

**D-019 · Docker Compose hướng phát triển** (Đã duyệt)
- Backend chạy `uvicorn --reload`, frontend chạy Vite dev server, mã nguồn mount từ máy host. Bind mount từ Windows không phát sự kiện file nên bật polling (`WATCHFILES_FORCE_POLLING`, `VITE_USE_POLLING`). Image nginx cho triển khai làm ở Giai đoạn 11.
- Cổng: db `127.0.0.1:5432`, backend 8000, frontend 5173.
- `node_modules` của frontend là volume ẩn danh (không bị thư mục Windows đè); `make up` dùng `--renew-anon-volumes` để nạp lại sau khi đổi dependency. Dữ liệu PostgreSQL nằm trong volume có tên `db_data` nên không bị ảnh hưởng.
- Compose ghi đè `DATABASE_URL` của backend thành host `db`; `.env` giữ URL (host `127.0.0.1`) cho chạy ngoài Docker. Hai URL phải khớp `POSTGRES_*`.
- Healthcheck: db (`pg_isready`), frontend (wget trang chủ), backend (gửi `GET /` và chấp nhận mọi mã trạng thái, kể cả 404). Backend cố ý KHÔNG gọi `/api/v1/health`: bản đầu tiên gọi endpoint đó và, khi container db tắt, backend bị đánh dấu `unhealthy` dù tiến trình vẫn sống (phát hiện khi thử tắt db). Thứ tự khởi động: db, rồi backend, rồi frontend.

**D-020 · Makefile chạy được trên cmd.exe lẫn sh** (Đã duyệt, chi tiết khi làm)
- `bash` trên PATH của máy là của WSL nên Makefile không dựa vào bash. Chỉ dùng cú pháp chung của cmd và sh: `cd dir && lệnh`, `npm --prefix`.
- Thêm `install` và `down` ngoài danh sách. `up` = `docker compose up -d --build --renew-anon-volumes --wait`; `db` chờ DB khoẻ.
- "chưa triển khai" được in bằng một dòng Python thuần ASCII (dùng `chr()` cho hai chữ có dấu) để hiện đúng tiếng Việt trên cmd.exe và thoát mã 0. Chữ có dấu viết thẳng trong Makefile bị lỗi font trên Windows vì make chuyển byte UTF-8 cho cmd.exe theo bảng mã ANSI (đã gặp khi chạy make thật).
- Chạy ngoài Docker cần Python (venv đã kích hoạt) và Node trên PATH. Windows cần cài make (`winget install ezwinports.make`).

**D-021 · CI một job, dùng đúng các lệnh make** (Đã duyệt)
- Các bước: `make install`, `make lint`, `make test`, rồi `npm --prefix frontend run build`. Python 3.12 và Node 22 (máy phát triển Python 3.13.5 vẫn chạy được; `requires-python >=3.11`). Dùng `actions/*@v7` (bản mới nhất lúc làm, đã tra). Chạy khi push và pull request. Chưa chạy thật vì chưa có remote.

**D-022 · `.gitignore` chặn cả CSV và Excel** (Khi làm)
- Ngoài `.env`, file mô hình và dữ liệu, chặn `*.csv`, `*.xls`, `*.xlsx` trên toàn repo làm lưới an toàn chống commit nhầm sổ điểm thật (nguyên tắc 7). Ngoại lệ: `data/seed/`, `eval/`, `backend/tests/fixtures/`. Đã kiểm bằng `git check-ignore`.
- `.gitattributes` ép LF: Makefile và Dockerfile hỏng nếu thành CRLF khi checkout trên Windows.

**D-023 · Thông tin cá nhân** (Khi làm)
- Không ghi `authors` trong `pyproject.toml`; không file nào chứa tên hay thông tin thật của học sinh.

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

## Giai đoạn 1

**D-024 · Vị trí model, `Base` và registry** (Đã duyệt; thay phần `target_metadata = None` của D-003)
- `Base` (DeclarativeBase, kèm `naming_convention` cho pk/fk/uq/ix/ck để Alembic có tên ràng buộc ổn định) ở `app/core/base.py`. Model đặt theo module: `core/models.py` (`Setting`), `auth/models.py` (`User`), `classes/models.py` (`SchoolYear`, `SchoolClass`, `Student`, `ClassStudent`, `Subject`, `TeachingAssignment`), `classes/academic.py` (`Assessment`, `Attendance`, `ConductResult`, `ExamRegistration`), `warning/models.py`, `reports/models.py`, `rag/models.py`, `assistant/models.py`. `app/models.py` chỉ import tất cả để `Base.metadata` đủ bảng.
- `SchoolClass` là tên lớp Python của bảng `classes` (`class` là từ khoá). `.gitkeep` được xoá ở các thư mục module đã có code (theo D-013).
- `alembic/env.py` dùng `Base.metadata`, `compare_type=True`, và nhận connection truyền sẵn qua `config.attributes["connection"]` (cách chuẩn của Alembic) để test không phụ thuộc `DATABASE_URL`. `fileConfig(..., disable_existing_loggers=False)` để Alembic không làm câm logger của pytest.
- 3 migration, đều có `downgrade`: (1) schema (extension `vector`, 15 bảng + `settings`), (2) giá trị mặc định của `settings`, (3) view. Tách riêng view vì Giai đoạn 3 sẽ thay nó bằng migration mới. `downgrade` không `DROP EXTENSION vector` (không biết extension do ai tạo; để lại vô hại). Id là `SERIAL`.

**D-025 · Cột liệt kê: mã tiếng Anh, nhãn tiếng Việt riêng, `CHECK`** (Đã duyệt)
- Lưu mã tiếng Anh ổn định (`StrEnum` ở `app/core/enums.py`), nhãn tiếng Việt ở `app/core/labels.py` (tra theo lớp enum, vì `StrEnum` so sánh theo chuỗi nên `"pass"` của hai enum khác nhau sẽ đè nhau nếu gộp chung một dict). Ràng buộc bằng `VARCHAR` + `CHECK` (SQLAlchemy `Enum(native_enum=False, create_constraint=True)`), không dùng enum gốc của PostgreSQL: thêm giá trị phải `ALTER TYPE`, không xoá được, autogenerate không thấy; `CHECK` sửa bằng một migration nhỏ.
- Mã: `attendance.status` = `present`/`absent_excused`/`absent_unexcused`/`late`; `conduct_results.period` = `hk1`/`hk2`/`year`; `conduct_results.level` = `good`/`fair`/`pass`/`fail`; `assessments.comment_result` = `pass`/`fail`; `risk_alerts.level` = `high`/`medium`/`low`; `risk_alerts.teacher_status` = `new`/`contacted`/`false_alarm`; `reports.type` = `school_record`/`contact_slip`/`report`; `reports.status` = `draft`/`approved`. `users.role`, `subjects.assessment_type`, `assessments.kind`, `reports.scope` giữ nguyên như DESIGN.
- `year` vẫn nằm trong `CHECK` của `period` (DESIGN có "cả năm") nhưng seed không sinh: kết quả cả năm là luật Thông tư 22.

**D-026 · View `v_subject_average` chỉ là khung, không có công thức** (Đã duyệt; giải quyết mâu thuẫn DESIGN mục 5 với nguyên tắc 2)
- Mỗi dòng ứng với (`class_student_id`, `subject_id`, `semester`) với `class_id`, `student_id`, `assessment_type`, `periods_per_year`, `tx_count`, `tx_sum` (0 nếu chưa có), `gk_score`, `ck_score`, `comment_result`. Chỉ `COUNT`/`SUM`/lọc theo `kind`: không chia, không nhân hệ số.
- Công thức ĐTBmhk / ĐTBmcn và làm tròn viết bằng Python/`Decimal` trong `app/analytics/` ở Giai đoạn 3, đọc hệ số từ `settings`. Nếu để hệ số trong SQL thì công thức nằm ở hai nơi (SQL và Analytics), trái nguyên tắc 2. Tên view giữ theo DESIGN dù chưa có trung bình. Giai đoạn 3 vẫn có thể bỏ view và đọc thẳng `assessments`.

**D-027 · `settings` nạp trong migration; danh sách khoá** (Đã duyệt)
- Nạp trong migration (không trong seed) vì seed bị chặn ở production mà production vẫn cần hệ số và ngưỡng. Migration chạy một lần nên giá trị admin sửa về sau không bị ghi đè; seed cũng không đụng bảng này. Chỉ lưu giá trị; số đọc ra bằng `Decimal(str(giá trị))`.
- Khoá: `coef_midterm`=2, `coef_final`=3, `coef_year_semester2`=2, `max_absent_sessions`=45, `absent_warning_notice`=30, `absent_warning_high`=40, `score_threshold_fail`=3,5, `score_threshold_pass`=5,0, `score_threshold_fair`=6,5, `score_threshold_good`=8,0, `level_min_subjects`=6, `regular_assessment_count`=`[{max_periods:35,count:2},{max_periods:70,count:3},{max_periods:null,count:4}]` (`max_periods` là ngưỡng bao gồm: ≤35 → 2, trên 35 đến 70 → 3, trên 70 → 4).
- Việc 6,5 và 8,0 gắn với mức Tốt hay Khá do Giai đoạn 3 quyết khi đọc văn bản Thông tư. Theo một nguồn thứ cấp, Thông tư 10/2025/TT-BGDĐT (hiệu lực 01/07/2025) sửa Thông tư 22 mà DESIGN chưa nhắc: cần kiểm lại trước Giai đoạn 3.

**D-028 · Đơn vị "buổi nghỉ"** (Đã duyệt)
- Mỗi dòng `attendance` có `status` là `absent_excused` hoặc `absent_unexcused` tính là 1 buổi nghỉ; `present` và `late` không tính. Không thêm cột. `UNIQUE (class_student_id, date)` để import không đếm trùng.
- Thực tế "buổi" là nửa ngày còn bảng chỉ có `date`, nên trong dữ liệu giả 1 ngày học = 1 buổi (175 ngày học/năm, 45 buổi chiếm khoảng 26%). Nếu dữ liệu thật có hai buổi một ngày (Giai đoạn 4) thì cần cột `session` và bỏ `UNIQUE` này, qua migration mới và cần bạn đồng ý.

**D-029 · `EMBEDDING_DIM`** (Đã duyệt)
- `Settings.embedding_dim` mặc định 1024 (`1..2000`; 2000 là trần chỉ mục HNSW/IVFFlat của pgvector), có trong `.env.example`. 1024 là số chiều của `bge-m3` và `multilingual-e5-large`.
- Migration đọc giá trị này lúc chạy và cố định vào cột `regulation_chunks.embedding`. Đổi mô hình embedding (ví dụ 768 chiều) cần migration mới `ALTER COLUMN embedding TYPE vector(N)` và tính lại toàn bộ vector (dựng lại chỉ mục nếu có). Test kiểm cột có số chiều bằng cấu hình.

**D-030 · Phạm vi thời gian và lịch học** (Đã duyệt)
- Năm học 2026-2027 sinh đủ hai học kỳ như bản mô phỏng một năm đã hoàn tất, dù ngày chạy seed có thể mới đầu năm học. `school_years`: 2026-09-05 đến 2027-05-31. Thứ Hai đến thứ Sáu: HK1 18 tuần từ 2026-09-07; HK2 17 tuần từ 2027-01-18, nghỉ Tết 2 tuần (01-12/02/2027): 175 ngày học (90 + 85). Ngày nghỉ chỉ để mô phỏng. Chưa sinh dữ liệu năm trước (Giai đoạn 6 quyết khi cần "kết quả năm trước" cho ML).
- Hệ quả: phần lớn dòng có ngày ở tương lai so với hôm nay. Giai đoạn 6 (đặc trưng "đến hiện tại", "4 tuần gần nhất") và kịch bản demo "nhập file điểm danh tháng mới" phải dùng ngày mốc `as_of` thay vì ngày hiện tại.

**D-031 · Môn học, số tiết, tổ hợp** (Đã duyệt; số liệu cần đối chiếu)
- 17 môn. Số tiết/năm và loại đánh giá (nguồn thứ cấp, cần đối chiếu với Thông tư 32/2018 và 13/2022; tổng 8 môn bắt buộc + chuyên đề 717 tiết + 4 môn lựa chọn × 70 = 997 tiết khớp bảng chương trình):

| Môn | Loại | Tiết/năm | Đầu điểm tx / học kỳ |
| --- | --- | --- | --- |
| Ngữ văn, Toán, Tiếng Anh (Ngoại ngữ 1) | score | 105 | 4 |
| Lịch sử (bắt buộc từ Thông tư 13/2022) | score | 52 | 3 |
| Giáo dục thể chất | comment | 70 | — |
| Giáo dục quốc phòng và an ninh | score | 35 | 2 |
| Hoạt động trải nghiệm, hướng nghiệp | comment | 105 | — |
| Nội dung giáo dục địa phương | comment | 35 | — |
| Địa lí, Giáo dục kinh tế và pháp luật, Vật lí, Hóa học, Sinh học, Công nghệ, Tin học (lựa chọn) | score | 70 | 3 |
| Âm nhạc, Mĩ thuật (lựa chọn, nhóm "Nghệ thuật") | comment | 70 | — |

- "Nghệ thuật" (DESIGN mục 5) đưa vào dưới dạng hai môn lựa chọn Âm nhạc và Mĩ thuật đánh giá bằng nhận xét. Không có "chuyên đề học tập".
- Mỗi lớp 12 môn (8 bắt buộc + 4 lựa chọn). Ba tổ hợp minh hoạ dùng chung cho mọi khối, đủ 9 môn lựa chọn, mỗi tổ hợp có ít nhất một môn ở mỗi nhóm KHXH, KHTN, Công nghệ-Nghệ thuật; lớp thứ 4 trở lên quay vòng: xA1 = Vật lí, Hóa học, Địa lí, Tin học; xA2 = Hóa học, Sinh học, GD kinh tế và pháp luật, Công nghệ; xA3 = Sinh học, GD kinh tế và pháp luật, Âm nhạc, Mĩ thuật. Quy tắc chọn môn thật của nhà trường chưa kiểm.

**D-032 · Học sinh nhân vật và học sinh biên** (Đã duyệt; chi tiết khi làm)
- Mã học sinh `HS` + khối (2) + lớp (2) + số thứ tự (3). Nhân vật demo (tính vào chỉ tiêu 5% / 8%): `HS1102001` (11A2, "Trần Minh An", nghỉ đúng 38 buổi), `HS1102002` (11A2, "Lê Hoàng Bảo", mọi đầu điểm Toán bằng 3,0). Tên "An" bị loại khỏi danh sách tên ngẫu nhiên nên lớp 11A2 chỉ có đúng một em An.
- Biên (lớp 12A1): `HS1201001` đến `HS1201003` nghỉ 44, 45, 46 buổi (test "quá 45" so với "từ 45"); `HS1201004` đến `HS1201006` có mọi đầu điểm Toán, cả hai học kỳ, bằng đúng 3,4 / 3,5 / 5,0. Seed **không** viết công thức Thông tư 22: trung bình có trọng số của các giá trị bằng nhau luôn bằng chính giá trị đó, đúng với mọi hệ số.
- Học sinh "môn dưới 3,5": mọi đầu điểm của một môn, hai học kỳ, bằng cùng một giá trị 2,0 đến 3,4; học sinh thường có mọi đầu điểm ≥ 4,0.
- Các hằng số 30 buổi, 3,5 trong seed (`scenarios.py`) là **hình dạng của dữ liệu mẫu**, không phải ngưỡng cảnh báo: không đọc từ `settings` và không đổi khi admin sửa `settings`.
- Kịch bản chỉ áp dụng khi lớp và số thứ tự tồn tại; tham số nhỏ hơn thì bỏ qua kịch bản đó (thống kê vẫn đúng với dữ liệu sinh ra).

**D-033 · Băm mật khẩu** (Đã duyệt)
- Dùng `bcrypt==5.0.0` trực tiếp, không dùng `passlib` (ít được bảo trì, xung đột với bcrypt đời mới). `app/core/security.py`: `hash_password(plain)` (hệ số chi phí 12; ném `ValueError` nếu quá 72 byte UTF-8, vì bcrypt 5 từ chối thay vì cắt lặng lẽ) và `verify_password(plain, hashed)` (trả `False` thay vì ném lỗi khi mật khẩu quá dài hoặc hash hỏng, để đăng nhập trả 401). Giai đoạn 2 import lại từ đây; JWT và `get_current_user` nằm ở `auth/`.
- `pgvector==0.5.1` (kiểu `Vector` cho SQLAlchemy). Không kéo thêm numpy.

**D-034 · Chiến lược test có DB thật** (Đã duyệt; chi tiết khi làm)
- Database riêng `classroom_test` trên cùng máy chủ (suy ra từ `DATABASE_URL` thật trong `.env`, hoặc `TEST_DATABASE_URL` nếu đặt; CI đặt sẵn). Fixture phiên xoá, tạo lại, chạy `alembic upgrade head` qua connection chia sẻ rồi seed mặc định một lần; chỉ chấp nhận tên kết thúc bằng `_test`, không bao giờ đụng DB phát triển. Test ghi vào DB dùng chung phải dùng `db_conn` (luôn rollback); test migration và seed lặp lại dùng database tạm riêng (`fresh_database`).
- `tests/conftest.py` vẫn ghi đè `DATABASE_URL` thành URL giả như cũ (test `/health` dùng Session giả); chỉ thêm việc lấy URL thật trước khi ghi đè. Test trong `tests/db/` gắn marker `db`; `pytest -m "not db"` chạy riêng test không cần DB.
- Thiếu PostgreSQL thì `pytest.exit` với thông báo "Chạy make db trước" (fail, không skip, để CI không lặng lẽ bỏ qua). Mọi engine của test đặt `connect_timeout=3`: nếu không, kết nối tới cổng không có ai lắng nghe treo hơn 2 phút trên Windows (đo thật: 132 giây).
- CI: `services.postgres` dùng `pgvector/pgvector:pg16`, đặt `TEST_DATABASE_URL`. Chưa chạy thật vì chưa có remote.
- Test "model khớp migration" (`compare_metadata` rỗng) bắt lỗi quên sinh migration khi đổi model.

**D-035 · Giả định schema** (Đã duyệt)
- **Môn nhận xét:** mỗi học kỳ một dòng `assessments` với `kind='ck'`, `seq=1`, `score` NULL, `comment_result` có giá trị. `CHECK` bắt đúng một trong `score` / `comment_result` khác NULL.
- **Điểm:** `NUMERIC(4,2)` + `CHECK 0..10` (nhập 8,25 không bị DB chặn; chuẩn hoá về 1 chữ số thập phân ở tầng import). Nới cột sau này không mất dữ liệu, thu hẹp thì có.
- **Unique:** `(school_year_id, homeroom_teacher_id)` (một GV chủ nhiệm một lớp mỗi năm, NULL được phép), `(class_id, subject_id)` ở `teaching_assignments`, `lower(email)`, và các khoá tự nhiên khác (xem model). Nếu trường có đồng giảng dạy hoặc GV kiêm nhiệm hai lớp thì phải bỏ.
- **`ON DELETE CASCADE`** cho bảng con của `class_students` (`assessments`, `attendance`, `conduct_results`, `exam_registrations`, `risk_alerts`); còn lại chặn xoá khi còn tham chiếu.
- `reports`: `CHECK (status <> 'approved' OR approved_by IS NOT NULL)` (nguyên tắc 6 ở mức DB). `risk_alerts.risk_score` `NUMERIC(5,4)` 0..1, cho phép NULL. `regulation_chunks.embedding` cho phép NULL (nạp chữ trước, vector sau). `students.date_of_birth/guardian_*` cho phép NULL.
- **Không thêm cột ngoài DESIGN.** Lưu ý: `ai_logs` chưa có thời điểm, `reports` chưa có `created_at`/`approved_at`; các giai đoạn dùng bảng đó (8, 9) sẽ xin thêm bằng migration. `ai_logs.feedback` là `TEXT` vì DESIGN không nói kiểu.

**D-036 · Hành vi của seed** (Đã duyệt; mục TRUNCATE đổi khi làm)
- Chạy bằng `make seed` (`python data/seed/run.py $(SEED_ARGS)`; thay phần `seed` đang in "chưa triển khai" của D-020), tham số `--seed` (2026), `--classes-per-grade` (3), `--class-size` (40). Chặn khi `APP_ENV=production` (kiểm trong chính hàm nạp, không chỉ ở CLI).
- Lặp lại được: mỗi học sinh có bộ sinh số riêng (hạt giống = seed + mã học sinh + mục đích), chỉ tiêu theo nhóm dùng bộ sinh riêng; id gán sẵn (1..n theo thứ tự cố định) rồi `setval` các sequence. Nạp trong một transaction: `TRUNCATE ... RESTART IDENTITY CASCADE` rồi chèn lại.
- **Khi làm:** `TRUNCATE` bỏ qua `settings` (cấu hình, do migration nạp) **và** `regulation_chunks` (văn bản quy định và vector, nạp ở Giai đoạn 7, tính lại tốn công) — kế hoạch ban đầu chỉ bỏ `settings`. Mọi bảng khác (kể cả dữ liệu nhập tay) bị xoá; README và CLI đều cảnh báo.
- Tài khoản (60 với tham số mặc định): 1 admin, 2 BGH, 51 GVBM (một người cho mỗi cặp môn-khối, dạy mọi lớp của khối có học môn đó), 6 GVCN thuần (lớp A2, A3 mỗi khối), và 3 GVCN đồng thời là GVBM (GVCN lớp A1 mỗi khối cũng là GV Toán khối đó, dạy cả lớp khác để test quyền cộng dồn). Email `@example.com` (RFC 2606; không dùng `.test` vì `email-validator` của Pydantic `EmailStr`, dùng ở Giai đoạn 2, có thể từ chối). Mật khẩu dev dùng chung, băm bcrypt một lần rồi gán cho mọi tài khoản; mật khẩu chỉ ghi trong README (phần dữ liệu giả lập và tài khoản dev), tài liệu khác và bảng tóm tắt của seed chỉ trỏ tới README.
- Dữ liệu cá nhân giả: tên ghép từ danh sách họ, đệm, tên phổ biến; ngày sinh theo khối (lớp 10 sinh 2011, 11 sinh 2010, 12 sinh 2009); `guardian_phone` dạng `0000xxxxxx` (đầu số không tồn tại). Điểm danh có một dòng cho mọi ngày học của mọi học sinh (kể cả `present`; khoảng 2% `late`), rèn luyện HK1 và HK2, khối 12 có 4 dòng `exam_registrations` mỗi em (Ngữ văn, Toán và 2 môn tính điểm bất kỳ của lớp; cần đối chiếu quy chế thi).
- Bảng tóm tắt khi xong: số dòng mỗi bảng, số học sinh nghỉ từ 30 buổi, số học sinh có đầu điểm dưới 3,5, số học sinh biên. Kết quả với tham số mặc định: 360 học sinh, 18 em nghỉ ≥ 30 buổi (5%), 29 em có đầu điểm dưới 3,5 (8%).

**D-037 · Hàm tra số đầu điểm theo số tiết nằm ở `analytics/`** (Đã duyệt)
- `app/analytics/thresholds.py::required_regular_count(periods, rules)` chỉ tra bảng quy tắc `settings.regular_assessment_count` (dữ liệu, không phải công thức Thông tư 22). Seed, import (Giai đoạn 4) và Analytics dùng chung một hàm. Test dùng bảng tính tay (105 → 4, 70 → 3, 52 → 3, 35 → 2), không dùng lại hàm để kiểm chính nó.

**D-038 · Gói `data.seed` và phạm vi lint, test** (Khi làm)
- Seed ở `data/seed/` là gói `data.seed`; `run.py` chỉ sửa `sys.path` (bỏ thư mục `data/seed` để tên file trong đó không che module khác, thêm `backend/` và thư mục gốc repo). `pyproject.toml`: `pytest.pythonpath` và ruff `src` thêm `..` để test import được `data.seed` và isort xếp đúng nhóm.
- `make lint` kiểm cả `../data` với `--config pyproject.toml` (data/ không có cấu hình ruff riêng). Tên file trong `data/seed/` tránh trùng thư viện chuẩn (`school_calendar.py`, không phải `calendar.py`).

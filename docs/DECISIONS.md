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
- Việc 6,5 và 8,0 gắn với mức Tốt hay Khá do Giai đoạn 3 quyết khi đọc văn bản Thông tư (đã quyết ở D-048). Bản đầu của mục này còn ghi "Thông tư 10/2025/TT-BGDĐT sửa Thông tư 22" theo một nguồn thứ cấp; thông tin đó **không xác nhận được**, xem đính chính ở D-055.

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

## Giai đoạn 2

**D-039 · Admin không xem dữ liệu học sinh** (Đã duyệt; bạn chốt khi hỏi lại theo PROMPTS Giai đoạn 2)
- DESIGN mục 2 chỉ giao cho Admin việc cấu hình (năm học, lớp, phân công, tài khoản, văn bản quy định) và không nói Admin xem điểm hay danh sách lớp. Nên Admin bị 403 ở mọi endpoint dữ liệu học sinh, kể cả danh sách lớp; `/me/assignments` của Admin trả danh sách rỗng.
- Khi làm các màn hình quản trị (phân công, tài khoản) ở giai đoạn sau, quyền của Admin được mở đúng chỗ cần, kèm test; không mở rộng `authorize()` cho dữ liệu học sinh.

**D-040 · Hợp đồng của `authorize()`** (Đã duyệt)
- `app/core/authorize.py`: `authorize(session, user, *, class_id=None, subject_id=None, grade_level=None) -> Access`. Có thêm tham số `session` so với chữ ký trong PROMPTS vì phải tra phân công. Trả `Access(role, class_id, is_homeroom, subject_ids, can_view_guardian)` (`subject_ids=None` là mọi môn). Không đạt thì ném `AuthorizationError` (không phải `HTTPException`) để 7 tool của LLM ở Giai đoạn 8 gọi lại được mà không cần HTTP; `main.py` chuyển nó thành HTTP 403 với thông điệp chung, không nói lý do.
- Quy tắc: Admin luôn bị từ chối; BGH toàn trường và thấy phụ huynh; GVCN thấy mọi môn và phụ huynh của lớp mình chủ nhiệm; GVBM chỉ đúng cặp lớp-môn có trong `teaching_assignments` và không thấy phụ huynh; `grade_level` chỉ BGH. Quyền cộng dồn được tính **riêng cho từng lớp**: người chủ nhiệm 10A1 và dạy Toán ở 10A2 thấy mọi môn và phụ huynh ở 10A1, còn ở 10A2 chỉ thấy Toán và không thấy phụ huynh.
- Giáo viên truy cập lớp không tồn tại nhận 403 (không lộ lớp nào có thật); BGH nhận 404 từ endpoint. `subject_id` không kèm `class_id`, hoặc truyền cả `class_id` lẫn `grade_level`, hoặc không truyền phạm vi nào là lỗi lập trình (`ValueError`), không bao giờ âm thầm cho phép hay từ chối.
- Vai trò lạ hoặc không xác định thì từ chối (đóng theo mặc định). Không lọc theo năm học: mỗi lớp thuộc một năm và phân công gắn với lớp.
- `core/authorize.py` import model của `auth/` và `classes/` (core đáng lẽ ở tầng thấp nhất) vì CLAUDE.md đặt hàm này trong `core/`. Không có vòng import.
- Test ma trận (`tests/core/test_authorize.py`, `tests/classes/test_class_students.py`) đã được thử bằng cách cố ý làm hỏng `authorize()` (cho GVBM thấy phụ huynh, bỏ kiểm tra phân công, cho Admin xem, bỏ kiểm tra môn): cả bốn cách đều làm test đỏ.

**D-041 · Đăng nhập và JWT** (Đã duyệt)
- `POST /auth/login` nhận JSON `{email, password}` (không dùng form OAuth2 để khỏi thêm `python-multipart`; trong Swagger bấm Authorize rồi dán token, scheme `HTTPBearer`). Trả `{access_token, token_type, expires_in, user}`.
- Token do PyJWT (`PyJWT==2.15.1`) ký HS256, chỉ chứa `sub` (id người dùng), `iat`, `exp`; giải mã luôn chỉ định `algorithms=["HS256"]` (chặn `alg: none`) và bắt buộc có `exp`, `sub`. **Vai trò không nằm trong token**: mỗi request nạp lại người dùng từ DB nên đổi vai trò hay xoá tài khoản có hiệu lực ngay (test có cả hai ca). Chưa có `is_active`, không thêm cột.
- `JWT_EXPIRE_MINUTES` mặc định 120 (5..1440); chưa có refresh token hay thu hồi token nên giữ vừa phải. `JWT_SECRET` phải dài từ 32 ký tự, kiểm khi khởi động (bản mẫu trong `.env.example` có 36 ký tự).
- Sai email và sai mật khẩu cùng nhận 401 "Email hoặc mật khẩu không đúng."; khi không có email đó vẫn chạy một lần `verify_password` với hash giả để thời gian phản hồi không lộ email nào tồn tại. Email so khớp không phân biệt hoa thường và cắt khoảng trắng hai đầu. Mật khẩu dài quá 72 byte nhận 401 (không phải 500).
- **Chưa làm (để Giai đoạn 11):** giới hạn số lần đăng nhập sai (khoá tạm, làm chậm), đổi mật khẩu, thu hồi token, nhật ký các lần bị từ chối.

**D-042 · Ba endpoint không qua `authorize()`** (Đã duyệt; mở rộng ngoại lệ D-001)
- `GET /health` (D-001), `POST /auth/login` (chưa có phiên) và `GET /me/assignments` (chỉ trả dữ liệu của chính người gọi, nên không có phạm vi lớp/môn nào để kiểm; vẫn bắt buộc đăng nhập). Mọi endpoint còn lại đi qua `authorize()` và gọi nó **trước** khi đọc dữ liệu.

**D-043 · Nhật ký truy cập `audit_logs`** (Đã duyệt)
- Bảng mới (migration thứ 4), ngoài 15 bảng của DESIGN và `settings`, theo yêu cầu của PROMPTS Giai đoạn 2: `id`, `user_id` (khoá ngoại `users`), `action` (`view_class_students`; dự phòng `view_student_profile` cho màn Hồ sơ học sinh ở Giai đoạn 5), `class_id` (số nguyên, không khoá ngoại để nhật ký còn lại khi lớp bị xoá), `details` JSONB, `created_at`.
- Mỗi lần danh sách lớp trả 200 ghi **một** dòng (cả danh sách một lần mở, không phải 40 dòng) với số học sinh và cờ có trả phụ huynh hay không. Ghi và commit **trước khi** trả dữ liệu: ghi lỗi thì request lỗi, không trả dữ liệu mà không có nhật ký.
- Truy cập bị từ chối (403) và lớp không tồn tại (404) chưa ghi: ghi trong cùng phiên sẽ bị rollback cùng request, cần phiên riêng (Giai đoạn 11). `make seed` xoá luôn bảng này qua `TRUNCATE` vì người dùng được tạo lại.

**D-044 · Hình dạng dữ liệu của hai endpoint** (Đã duyệt; chi tiết khi làm)
- `GET /me/assignments`: `{user, homeroom_classes, teaching, grades}`. `user` nằm trong đó nên front-end chỉ cần một lần gọi sau khi tải lại trang (không thêm `/me` ngoài DESIGN). `grades` là các khối có lớp, chỉ BGH có. Chưa lọc theo năm học (hiện chỉ có một năm); khi có nhiều năm thì trang chủ chỉ nên hiện năm hiện hành.
- `GET /classes/{class_id}/students`: `id`, `student_code`, `full_name`, sắp theo mã. GVCN của lớp và BGH nhận thêm `guardian_name`, `guardian_phone`. Hai schema Pydantic **riêng và không kế thừa nhau** (`StudentOut`, `StudentWithGuardianOut`): người không được xem nhận danh sách không có cả khoá lẫn giá trị `guardian_*`, không phải khoá rỗng. Không trả `date_of_birth` (không cần cho danh sách). "Kết quả tổng hợp" của DESIGN chờ Giai đoạn 3.

**D-045 · Front-end đăng nhập** (Đã duyệt; chi tiết khi làm)
- Token ở `sessionStorage` (`auth/tokenStore.ts` là nơi duy nhất đụng tới nó): sống qua tải lại trang, mất khi đóng tab, mỗi tab một phiên nên mở hai tab đăng nhập hai vai trò khác nhau để demo. Đổi sang `localStorage` chỉ sửa một file. Token không nằm trong URL.
- `api/client.ts` tự gắn `Authorization: Bearer`; gặp 401 trên yêu cầu có token thì đăng xuất (xoá token và bộ nhớ đệm TanStack Query để người sau không thấy dữ liệu của người trước) rồi `RequireAuth` đưa về `/login`. Đăng nhập sai (401 của chính `/auth/login`) không bị coi là hết phiên.
- Trang chủ giờ cần đăng nhập, nên phần "Trạng thái hệ thống" (Máy chủ, Cơ sở dữ liệu; kiểm tra của Giai đoạn 0) chuyển sang trang `/login` (component `SystemStatus`), vẫn công khai. Trang chủ theo vai trò: GVBM bảng lớp-môn; GVCN thẻ lớp chủ nhiệm (cộng bảng lớp-môn nếu có dạy); BGH ba thẻ khối; Admin thông báo chưa có chức năng. Nhãn "chủ nhiệm / bộ môn" suy ra từ phân công, không phải từ `role`.
- Chưa có Vitest hay Playwright (D-004): front-end chỉ kiểm bằng `eslint`, `tsc`, `vite build` và gọi API thật qua proxy; chưa kiểm bằng trình duyệt.

**D-046 · Hạ tầng test cho API có DB** (Đã duyệt; thay phần vị trí fixture của D-034)
- Fixture DB chuyển từ `tests/db/conftest.py` lên `tests/conftest.py` để `tests/auth/`, `tests/classes/`, `tests/core/` (thư mục `tests/` phản chiếu `app/`) dùng chung; fixture chỉ chạy khi test yêu cầu. Thêm `db_session` (Session trên transaction ngoài với `join_transaction_mode="create_savepoint"`: app commit nhật ký thì chỉ nhả savepoint, hết test vẫn rollback sạch), `api_client` (ghi đè `get_db`), `auth_headers(email)` (tạo JWT trực tiếp để ma trận phân quyền khỏi tốn ~0,25 giây bcrypt mỗi ca; đăng nhập bằng bcrypt thật chỉ kiểm ở `tests/auth/test_login.py`), `class_id_of(tên lớp)`.
- Test dùng tài khoản seed mặc định: `gv.dia.10` (GVBM một lớp, đúng khối sai lớp ở 10A2 và 10A3), `gv.van.10` (GVBM ba lớp), `gvcn.10a2` (GVCN thuần), `gv.toan.10` (cộng dồn), `bgh1`, `admin`. Đổi cấu trúc tài khoản seed phải sửa test này.
- `JWT_SECRET` giả trong conftest đổi thành chuỗi dài hơn 32 ký tự.

## Giai đoạn 3

**Nguồn và độ tin cậy của cả giai đoạn:** không đọc được văn bản gốc Thông tư 22/2021 (`vbpl.moj.gov.vn` không truy cập được từ máy phát triển). Các quy tắc dưới đây khớp giữa PROMPTS và các nguồn thứ cấp: [LuatVietnam](https://luatvietnam.vn/tin-phap-luat/danh-gia-xep-loai-hoc-sinh-thcs-thpt-2021-230-32425-article.html) (Điều 9), [Giáo dục & Thời đại](https://giaoduc.net.vn/cac-truong-hop-hoc-sinh-phai-kiem-tra-lai-o-lai-lop-theo-thong-tu-22-cua-bo-gd-post242024.gd) (Điều 12, 14), [Thư viện Pháp luật](https://thuvienphapluat.vn/hoi-dap-phap-luat/cach-danh-gia-xep-loai-hoc-sinh-thcs-thpt-moi-nhat-2023-khi-nao-cach-tinh-diem-cho-hoc-sinh-thcs-th-138003400.html) (trích gần nguyên văn quy định điều chỉnh mức). **Mọi hệ số, ngưỡng và thứ tự làm tròn cần đối chiếu với văn bản gốc.** Ngưỡng và hệ số nằm trong `settings` nên sửa số rất dễ; sửa **cấu trúc** quy tắc thì phải sửa `analytics/`.

**D-047 · Công thức điểm trung bình và làm tròn** (Đã duyệt; bạn chốt thứ tự làm tròn)
- ĐTBmhk = (Tổng ĐĐGtx + `coef_midterm`×ĐĐGgk + `coef_final`×ĐĐGck) / (Số ĐĐGtx + `coef_midterm` + `coef_final`); với hệ số 2 và 3 thì mẫu số là Số ĐĐGtx + 5. Hệ số và mẫu số đều lấy từ `settings`, nên đổi hệ số là công thức đổi theo (có test). Dùng `tx_sum`, `tx_count`, `gk_score`, `ck_score` của view `v_subject_average`.
- Làm tròn **nửa lên** đến 1 chữ số thập phân (`Decimal`, `ROUND_HALF_UP`): 6,25 thành 6,3, không làm tròn kiểu ngân hàng.
- ĐTBmcn = (ĐTBmhkI + `coef_year_semester2`×ĐTBmhkII) / (1 + `coef_year_semester2`), tính từ hai ĐTBmhk **đã làm tròn** rồi làm tròn lại (khớp con số giáo viên thấy trong sổ điểm). Ví dụ ĐTBmhkI 6,14 và ĐTBmhkII 6,04 cho 6,0; nếu dùng số chưa làm tròn sẽ ra 6,1. Hệ số 1 của học kỳ I là ngầm định, không có khoá riêng.
- Mọi so sánh với ngưỡng (3,5 / 5,0 / 6,5 / 8,0) dùng số đã làm tròn: 3,4 dưới 3,5, còn 3,5 thì không.
- Số trong JSON là số thập phân một chữ số (`Decimal` tuần tự hoá thành `float`); giao diện chỉ hiển thị (dấu phẩy), không tự tính lại mức hay ngưỡng.

**D-048 · Mức học tập và quy định điều chỉnh mức** (Đã duyệt; bạn chốt làm quy định điều chỉnh)
- Bốn mức theo PROMPTS và Điều 9, ngưỡng từ `settings` (`score_threshold_fail/pass/fair/good`, `level_min_subjects`). **Tốt**: mọi môn nhận xét Đạt; mọi môn điểm số ≥ 6,5; ít nhất 6 môn ≥ 8,0. **Khá**: mọi môn nhận xét Đạt; mọi môn điểm số ≥ 5,0; ít nhất 6 môn ≥ 6,5. **Đạt**: nhiều nhất 1 môn nhận xét Chưa đạt; ít nhất 6 môn điểm số ≥ 5,0; không môn nào dưới 3,5. **Chưa đạt**: còn lại. Việc gán 6,5 và 8,0 cho Tốt/Khá còn để ngỏ ở D-027 nay đã quyết theo các điều kiện trên.
- **Điều chỉnh mức**: nếu mức bị thấp hơn từ 2 mức trở lên so với Tốt/Khá **chỉ do duy nhất 1 môn** thì nâng 1 mức. Cách hiểu của tôi (chưa có văn bản gốc để đối chiếu): với mỗi môn `s`, tính lại mức khi bỏ các điều kiện "mọi môn" và "không môn nào dưới 3,5" của riêng `s`, trong khi giá trị của `s` vẫn được đếm vào các điều kiện "ít nhất N môn"; nếu có một `s` làm mức cao hơn mức gốc từ 2 bậc trở lên thì mức cuối = mức gốc + 1, kèm cờ `adjusted`. Ví dụ: 8 môn 8,5 và 1 môn 4,0: gốc Đạt, bỏ môn 4,0 là Tốt (hơn 2 mức) nên thành Khá; 8 môn 8,5 và 1 môn 3,0: gốc Chưa đạt, thành Đạt (không nhảy thẳng lên Tốt); 8 môn 8,5 và 1 môn 6,2: Khá, giữ nguyên (chỉ hơn 1 mức); hai môn yếu: không nâng.
- Công tắc `level_single_subject_adjustment` trong `settings` (mặc định `true`, migration thứ 5); tắt đi thì chỉ áp dụng 4 quy tắc gốc. Kết quả luôn trả cả mức gốc, mức cuối và cờ `adjusted`.
- **Hệ quả cần biết:** với công tắc bật, học sinh chỉ có **một** môn dưới 3,5 mà các môn khác đủ tốt vẫn có thể được xếp Đạt. DESIGN mục 6.2 viết "có môn ĐTB dưới 3,5 … không thể đạt mức Đạt"; hai điều này lệch nhau. Cảnh báo sớm (Giai đoạn 6) nên báo "có môn dưới 3,5" như một lý do riêng, không suy ra từ mức học tập.
- Kết quả chỉ tính khi **mọi môn đủ dữ liệu** (D-050).

**D-049 · Kết quả cả năm của môn nhận xét và của rèn luyện** (Đã duyệt)
- Môn nhận xét: kết quả cả năm = kết quả học kỳ II (theo trí nhớ về Thông tư, chưa đối chiếu).
- Rèn luyện: dùng bản ghi `conduct_results.period = 'year'` nếu có (GVCN nhập); chưa có thì lấy mức học kỳ II và đánh dấu `derived` ("suy ra"). Seed không sinh bản ghi `year`, nên dữ liệu seed luôn là "suy ra"; dashboard cả năm báo `conduct_derived_count`. Quy tắc kết hợp HK1 và HK2 của Thông tư (nếu có bảng) chưa kiểm được.

**D-050 · Dữ liệu thiếu và cờ `complete`** (Đã duyệt)
- ĐTB chỉ tính khi có cả điểm giữa kỳ và cuối kỳ (thiếu thì `None`). `complete` = có ĐTB **và** đủ số đầu điểm thường xuyên theo `regular_assessment_count`. Bảng điểm môn vẫn hiện ĐTB tạm tính kèm `complete = false`; **mức học tập chỉ tính khi mọi môn của lớp đều `complete`**, ngược lại `level = None` ("chưa đủ dữ liệu", kèm danh sách môn thiếu), để giữa kỳ không xếp loại nhầm. Dashboard đếm số học sinh `incomplete`.

**D-051 · Điều kiện lên lớp và môn có thể phải kiểm tra lại** (Đã duyệt)
- Đủ điều kiện khi học tập **và** rèn luyện cả năm từ Đạt trở lên và nghỉ ≤ `max_absent_sessions` (45 đủ, 46 không). Lý do: `learning_fail`, `conduct_fail`, `absent_over_limit`, `missing_data`. `eligible = None` khi chưa đủ dữ liệu, trừ khi đã có lý do chắc chắn không đủ (nghỉ quá mức, học tập hoặc rèn luyện đã Chưa đạt thì kết luận `False` ngay). Nguồn thứ cấp cũng ghi một buổi nghỉ tính theo 1 buổi/ngày, khớp D-028.
- `retake_subjects` liệt kê môn điểm số có ĐTBmcn dưới 5,0 (DESIGN mục 6.2; đúng 5,0 thì không) **và** môn nhận xét Chưa đạt cả năm (Điều 14, vượt DESIGN và PROMPTS; nguồn thứ cấp). Danh sách là "môn có thể phải kiểm tra lại"; việc có bắt buộc hay không phụ thuộc kết quả cả năm.

**D-052 · Cấu trúc `analytics/` và view không đổi** (Đã duyệt)
- Hàm thuần nhận `AnalyticsConfig` (dựng từ `settings` bằng `load_config`/`config_from_values`, thiếu khoá thì báo tên khoá): `scores.py`, `learning.py`, `conduct.py`, `attendance.py`, `promotion.py`. Phần đọc DB ở `repository.py` (view `v_subject_average` qua `Table` trong `MetaData` riêng, `views.py`) và ghép ở `service.py`. `thresholds.py` (D-037) dùng lại.
- **View `v_subject_average` giữ nguyên** (PROMPTS cho phép hoàn thiện "nếu cần cho hiệu năng"): đo thật trên seed, dashboard lớp 40 học sinh mất khoảng 26 đến 62 ms và tổng quan khối 12 (120 học sinh) khoảng 79 ms, nên suy ra khoảng 1 giây cho 1.500 học sinh; chưa đo ở quy mô đó. Số buổi nghỉ đếm bằng SQL (`COUNT … FILTER`) chứ không kéo 175 dòng mỗi học sinh.

**D-053 · Ba endpoint** (Đã duyệt; chi tiết khi làm)
- `GET /classes/{id}/dashboard?semester=1|2|year`: `authorize(class_id)` rồi `Access.require_all_subjects()` (GVCN lớp và BGH; GVBM, kể cả người dạy Toán ở lớp đó, bị 403 vì thấy một số môn); `GET /classes/{id}/subjects/{subject_id}/scores?semester=1|2`: `authorize(class_id, subject_id)`; `GET /grades/{level}/overview?semester=1|2|year`: `authorize(grade_level)`, chỉ BGH. Mặc định `semester=1`; giá trị khác 422. Lớp hoặc khối không có: 404 (giáo viên và Admin nhận 403 trước). Môn không có trong lớp: 404.
- Số buổi nghỉ trong dashboard đếm theo **cả năm học**, không theo học kỳ (45 buổi là hạn mức cả năm); "nghỉ từ 30 buổi" dùng `absent_warning_notice`. "Học sinh cần quan tâm" (`absent_over_limit`, `absent_notice`, `subject_below_fail`, `level_fail`) đọc từ kết quả Analytics, **chưa phải cảnh báo sớm** (Giai đoạn 6); chưa có "số cảnh báo".
- Tổng quan khối: số liệu gộp theo lớp, và trung bình theo lớp của các môn **điểm số mà mọi lớp trong khối đều học** (môn lựa chọn khác tổ hợp thì không so sánh). Trung bình lớp là số mô tả, làm tròn 1 chữ số, không phải số của Thông tư.
- Nhật ký (mở rộng D-043, migration thứ 5): thêm `view_class_dashboard` và `view_subject_scores`; hai endpoint này trả dữ liệu từng học sinh nên ghi một dòng mỗi lần 200. Tổng quan khối chỉ có số liệu gộp nên không ghi.
- Bảng điểm môn nhận xét trả kết quả Đạt / Chưa đạt, không có ĐTB; môn điểm số trả các đầu điểm, ĐTB học kỳ đang xem, ĐTB hai học kỳ và ĐTBmcn khi đủ hai học kỳ, phân bố theo các ngưỡng. Giao diện chưa dùng (Giai đoạn 5); thử qua Swagger.

**D-054 · Bộ 30 ca tính tay và cách kiểm** (Đã duyệt)
- `eval/analytics_cases.json` (7 ca ĐTBmhk, 3 ca ĐTBmcn, 12 ca mức học tập, 8 ca lên lớp), mỗi ca có lời giải tay trong `note`; `tests/analytics/test_eval_cases.py` nạp và kiểm bằng mã dự án. Trước khi chốt, kết quả mong đợi được đối chiếu bằng một script phân số độc lập (`fractions`, không import mã dự án; không đưa vào repo): 30/30 khớp.
- Đã thử "đột biến" thủ công (làm tròn kiểu ngân hàng, hệ số cố định, mẫu số cả năm cố định, `>` thay `>=` ở ngưỡng 3,5 và 6 môn, nâng mức khi chỉ hơn 1 bậc, 45 buổi bị coi là quá hạn, đi muộn tính là nghỉ; trước đó cả bốn cách phá `authorize()`): tất cả đều làm test đỏ.
- `make eval` vẫn là lệnh giữ chỗ; bộ 30 ca chạy qua `pytest`, Giai đoạn 10 mới nối vào `make eval`.

**D-055 · Đính chính: Thông tư 10/2025/TT-BGDĐT** (thay câu tương ứng ở D-027)
- D-027 và các ghi chú Giai đoạn 1 ghi "Thông tư 10/2025/TT-BGDĐT (hiệu lực 01/07/2025) sửa Thông tư 22" theo một nguồn thứ cấp. Lần tra ở Giai đoạn 3 **không xác nhận được** thông tư đó tồn tại; chỉ thấy một **dự thảo** sửa Thông tư 22 về kiểm tra định kỳ trên máy tính, không đụng điểm hay mức đánh giá. Coi như chưa có sửa đổi đã ban hành ảnh hưởng tới công thức, nhưng vẫn cần đối chiếu văn bản gốc.

**D-056 · Học sinh biên nghỉ 44/45/46 buổi có năng lực cao** (Đã duyệt; sửa D-032)
- `HS1201001` đến `HS1201003` có `ability = 2.0` cố định trong `scenarios.py`. Trước đó điểm và rèn luyện của hai em nghỉ 45 và 46 buổi bị kéo xuống (rèn luyện Chưa đạt) nên ca "45 đủ, 46 không đủ" không tách riêng được nguyên nhân là số buổi nghỉ. Sau chỉnh: 44 và 45 buổi đủ điều kiện lên lớp, 46 buổi không đủ chỉ vì `absent_over_limit`. Chỉ ba em này thay đổi trong dữ liệu seed.

## Giai đoạn 4: nhập Excel/CSV

**D-057 · Định dạng tệp và cột** (Đã duyệt)
- Nhận `.xlsx` và `.csv` UTF-8 (có hoặc không BOM; dấu `,` `;` hoặc tab tự nhận). Từ chối `.xls`, `.xlsm`, tệp có macro, CSV không phải UTF-8 (kể cả "Unicode Text" của Excel, kèm gợi ý lưu "CSV UTF-8"). Giới hạn 5 MB, 20.000 dòng, 60 cột, tệp zip giải nén không quá 50 MB (chống zip bomb). Lỗi trả 413/415/422 kèm thông điệp tiếng Việt.
- Đọc bằng pandas + openpyxl với `dtype=str`: **mọi ô là chuỗi**, điểm đổi sang `Decimal` ở bước kiểm dòng, nên ô số `8.7` không bao giờ thành `8.700000000000001`. Chỉ đọc trang tính đầu tiên.
- **Điểm dạng "rộng"** như sổ điểm điện tử: mỗi học sinh một dòng; **một môn, một học kỳ mỗi tệp**; `subject_id`, `semester` truyền kèm yêu cầu, không nằm trong tệp (nên quyền được kiểm trước khi đọc tệp). Cột: mã học sinh, `tx1…txN` (N theo số tiết của môn, đọc từ `settings`), giữa kỳ, cuối kỳ; họ tên chỉ để đối chiếu; cột lạ (STT, ĐTB…) bị bỏ qua và được liệt kê. Môn nhận xét: một cột Đạt / Chưa đạt.
- **Điểm danh dạng "dài"**: mã học sinh, ngày (dd/mm/yyyy, yyyy-mm-dd hoặc ô ngày của Excel), trạng thái (tiếng Việt, mã tiếng Anh hoặc CP/KP/M). **Rèn luyện**: mã học sinh, mức (Tốt/Khá/Đạt/Chưa đạt hoặc good/fair/pass/fail), nhận xét tuỳ chọn; `period` (hk1/hk2/year) truyền kèm. Chưa hỗ trợ điểm danh dạng "rộng" (mỗi ngày một cột).
- Tên cột được chuẩn hoá (bỏ dấu, chữ thường, bỏ dấu câu) rồi khớp bí danh ("Mã HS", "mã học sinh", "MA_HS" là một; "ĐĐGtx 1", "TX1"…). Dòng tiêu đề tự dò trong 15 dòng đầu (sổ điểm xuất ra thường có dòng tiêu đề lớn phía trên) hoặc chỉ định bằng `header_row`. Mã học sinh so không phân biệt hoa thường.
- **Định dạng thật của sổ điểm điện tử (VNEDU, SMAS…) là suy đoán**: không có tệp xuất thật để đối chiếu. Ánh xạ cột và tự dò dòng tiêu đề là để bù; cần thử với một tệp thật đã ẩn danh khi có.

**D-058 · Quyền ghi: `authorize_write`** (Đã duyệt; mở rộng nguyên tắc 4)
- Quyền ghi hẹp hơn quyền xem. **Điểm**: chỉ giáo viên có phân công đúng lớp-môn. **Điểm danh và rèn luyện**: chỉ GVCN của lớp. **BGH và Admin không nhập** (BGH xem toàn trường nhưng không ghi). GVCN không dạy môn đó cũng không nhập được điểm môn đó. Quyền cộng dồn, tính riêng từng lớp (người chủ nhiệm 11A1 và dạy Toán 11A2 nhập được điểm danh 11A1 và điểm Toán 11A2, không ngược lại).
- Hàm nằm cùng `core/authorize.py`, cùng kiểu `AuthorizationError` (403 chung, không nói lý do). Endpoint kiểm quyền **trước khi đọc nội dung tệp**. Xác nhận kiểm lại quyền (giáo viên bị rút phân công giữa chừng thì không ghi được) và chỉ **người tạo bản xem trước** được xác nhận.

**D-059 · Bản xem trước lưu trong DB; tất cả hoặc không gì** (Đã duyệt; migration thứ 6)
- Bảng mới `import_jobs` (ngoài 15 bảng của DESIGN): `id` UUID ngẫu nhiên, người tạo, lớp, loại, môn, học kỳ/kỳ, ánh xạ cột, số đếm, các bản ghi hợp lệ đã chuẩn hoá, `expires_at` (24 giờ), `confirmed_at`. Lưu DB thay vì bộ nhớ tiến trình để sống qua khởi động lại và chạy được nhiều tiến trình. **Không lưu tệp gốc và không lưu họ tên.** Dọn job hết hạn mỗi khi có tải lên mới.
- Xem trước **không ghi gì** vào bảng dữ liệu. **Có dòng lỗi thì không ghi gì** (kể cả các dòng đúng): xác nhận bị từ chối 422. Cảnh báo (họ tên lệch, thiếu đầu điểm khi `allow_partial`) không chặn.
- Xác nhận ghi trong **một transaction**, khoá job `FOR UPDATE`; xác nhận lặp lại trả kết quả cũ (`already_confirmed`), không ghi lần hai; job hết hạn 410; không có job 404; lỗi toàn vẹn khi ghi thì rollback toàn bộ và trả 409.
- Nhật ký `audit_logs`: hành động mới `import_confirm` (mở rộng `CHECK` như D-053), chỉ ghi **lúc xác nhận** (xem trước không đổi dữ liệu), `details` chỉ có id job, loại, môn, học kỳ/kỳ và số bản ghi, không có tên học sinh.

**D-060 · Ghi đè, ô trống không xoá, không nhân đôi** (Đã duyệt)
- Nhập lại **ghi đè** giá trị đã đổi; bản xem trước phân loại từng dòng `new` / `changed` / `unchanged` và hiện cũ → mới. **Ô trống không bao giờ xoá** dữ liệu có sẵn; nhận xét rèn luyện để trống thì giữ nhận xét cũ.
- Ghi bằng `INSERT … ON CONFLICT DO UPDATE` dựa trên khoá duy nhất của Giai đoạn 1 nên nhập lại cùng tệp không nhân đôi bản ghi; đếm bản ghi tạo mới / ghi đè bằng `xmax = 0`.

**D-061 · Quy tắc kiểm từng dòng** (Đã duyệt; **thay câu "chuẩn hoá về 1 chữ số thập phân ở tầng import" của D-035**)
- Điểm: số từ 0 đến 10, **tối đa 1 chữ số thập phân; nhiều hơn là lỗi, không tự làm tròn** (tự làm tròn âm thầm sẽ đổi điểm của học sinh). Chấp nhận dấu phẩy (`7,5`) và dấu chấm; từ chối `1e1`, `NaN`, `Infinity`.
- **Thiếu đầu điểm là lỗi mặc định**; tuỳ chọn `allow_partial` đổi thành cảnh báo và ô trống không ghi.
- Mã học sinh không có trong lớp, hoặc trùng trong tệp (điểm danh: trùng học sinh + ngày): lỗi, ghi rõ trùng với dòng nào. Họ tên trong tệp lệch hệ thống: cảnh báo. Ngày điểm danh ngoài năm học của lớp, trạng thái hay mức lạ: lỗi. Mọi thông điệp tiếng Việt kèm tên cột và đúng số dòng của tệp.
- Giá trị cũ lấy từ DB (`NUMERIC(4,2)`) được hiển thị thống nhất một chữ số thập phân (`4,7`, không phải `4,70`).

**D-062 · Mẫu ánh xạ cột** (Đã duyệt)
- Bảng `import_mappings` (mỗi người dùng, mỗi loại, một tên; lưu cùng tên thì ghi đè). Thứ tự ưu tiên: lựa chọn tay của người dùng, rồi mẫu đã lưu, rồi tự khớp theo bí danh. Thiếu cột bắt buộc: bản xem trước báo `missing_required`, **không tạo job**; giao diện hiện bước chọn cột rồi gửi lại. Mẫu chỉ được lưu khi ánh xạ đủ cột để tạo job. Mẫu của giáo viên này không hiện cho giáo viên khác.

**D-063 · Hook `on_data_changed(class_id)`** (Đã duyệt)
- `imports/hooks.py`, hiện rỗng. Gọi **một lần, sau khi commit**, và **chỉ khi dữ liệu thật sự đổi** (tạo mới hoặc ghi đè ít nhất một bản ghi). Giai đoạn 6 gắn Early Warning chạy lại cho lớp vào đây. Analytics tính khi đọc (D-052) nên chưa có gì để "tính lại". Nếu hook sau này có thể ném lỗi thì người gọi phải bắt và ghi log, không được làm hỏng việc nhập đã commit.

**D-064 · Tệp mẫu và `--hold-out`** (Đã duyệt)
- `data/samples/` (ngoại lệ `.gitignore`, như `data/seed/`; sinh bằng `make samples` từ chính bộ sinh của seed nên mã học sinh khớp): `diem-toan-11a2-hk1.xlsx` (đúng, có dòng tiêu đề lớn, STT, ĐTB; khác DB ở 3 học sinh), `diem-toan-11a2-hk1-loi.xlsx` (7 lỗi/cảnh báo cài sẵn và một dòng dấu phẩy hợp lệ), `diem-danh-11a2-2027-03.csv` (UTF-8 có BOM). ĐTB trong tệp tính bằng `app.analytics.scores` với hệ số đọc từ `settings`, không cài công thức thứ hai.
- `make seed SEED_ARGS="--hold-out 2027-03"` bỏ điểm danh tháng đó khỏi DB để nhập tệp mẫu là dữ liệu **mới** (kịch bản demo "GVCN nhập tệp điểm danh tháng mới", DESIGN mục 12). Mặc định không đổi (dữ liệu y hệt các giai đoạn trước). Id điểm danh tính theo số ngày học nên không bị trùng khi bỏ tháng. Khi hold-out, số buổi nghỉ trong DB chưa tính tháng đó cho tới khi nhập tệp.

**D-065 · Thư viện, giới hạn và điều chưa kiểm** (Đã duyệt)
- Thư viện mới (ghim phiên bản): `pandas==3.0.6`, `openpyxl==3.1.5`, `python-multipart==0.0.32` (cần cho `UploadFile`; kéo theo numpy). Image Docker backend nặng thêm khoảng 60 MB. Front-end không thêm thư viện.
- Starlette nhận trọn thân `multipart` trước khi gọi hàm xử lý, nên **giới hạn dung lượng thật phải đặt thêm ở reverse proxy (Giai đoạn 11)**; trong code chỉ chặn khi đọc nội dung. Xem trước cắt ở 500 dòng bình thường (luôn đủ dòng lỗi và cảnh báo); xác nhận vẫn ghi toàn bộ tệp.
- Giao diện `/classes/:classId/import` kiểm bằng `eslint`, `tsc`, `vite build` và gọi API thật; **chưa kiểm trên trình duyệt** (không có công cụ trình duyệt, chưa có Vitest hay Playwright, D-004). *Cập nhật ở Giai đoạn 5 (D-069): đã chạy thử trên Chrome thật, đúng.*

## Giai đoạn 5: dashboard và giao diện chính

**D-066 · Hai phần back-end mới và hồ sơ học sinh** (Đã duyệt; PROMPTS nói "dùng API đã có" nhưng hai màn hình thiếu dữ liệu)
- **Dashboard lớp** thêm `absences_by_month` (tổng số buổi nghỉ của cả lớp theo từng tháng của năm học, **tháng không ai nghỉ ghi 0**; hàm thuần `absences_by_month_in_range` trong `analytics/attendance.py`, tái dùng `absences_by_period` của Giai đoạn 3; tháng ngoài khoảng mà vẫn có buổi nghỉ được giữ lại nên tổng các tháng luôn bằng tổng số buổi nghỉ), `absence_limits` (`notice`, `maximum` đọc từ `settings`: 30 và 45) và `thresholds` (3,5 / 5,0 / 6,5 / 8,0 từ `settings`), để giao diện không ghi cứng ngưỡng nào (nguyên tắc 2).
- **`GET /classes/{class_id}/students/{student_id}/profile?semester=1|2|year`**: qua `authorize()` trước khi đọc dữ liệu, ghi nhật ký `view_student_profile` (đã có sẵn trong enum và CHECK nên không cần migration; `details` có `student_id`, `semester`, `scope`). Hai schema **riêng, không kế thừa nhau** (theo D-044), `response_model` là union:
  - `StudentProfileFullOut` (`scope: "full"`) cho GVCN của lớp và BGH: định danh, `guardian_name`/`guardian_phone`, từng môn với đầu điểm hai học kỳ và ĐTBmcn, kết quả học tập (kèm các môn dưới ngưỡng và thiếu dữ liệu theo tên môn), rèn luyện, chuyên cần (số buổi nghỉ, nghỉ theo tháng, ngưỡng), điều kiện lên lớp (chỉ khi `semester=year`), lý do cần quan tâm, ngưỡng điểm.
  - `StudentProfileSubjectsOut` (`scope: "subjects"`) cho GVBM: định danh và **chỉ các môn mình dạy ở lớp đó** (cộng `thresholds`); **không có khoá** xếp loại, rèn luyện, chuyên cần, phụ huynh, lên lớp (cùng nguyên tắc với dashboard lớp vốn cấm GVBM, `require_all_subjects`). Quyết định này do bạn chọn.
- Không trả `date_of_birth`. Học sinh không thuộc lớp: 404 (người gọi đã qua `authorize` lớp đó nên không lộ thêm gì).
- Học tập, rèn luyện, nghỉ, lên lớp lấy từ `build_class_results` (cùng nguồn với dashboard lớp nên hai màn hình không bao giờ lệch nhau; có test đối chiếu cho cả ba kỳ), đầu điểm từng môn dùng lại `_group_raw`, `evaluate_semester`, `year_average`. Chi phí: tính cả lớp rồi lấy một em, khoảng 30 đến 60 ms ở quy mô seed. Dọn nhỏ: `school_year_range` chuyển về `analytics/repository.py` và module nhập tệp dùng lại.

**D-067 · Bố cục, điều hướng và URL**
- `AppLayout` là route cha của mọi trang cần đăng nhập (thay cho `AppHeader` do từng trang tự dựng): thanh điều hướng theo vai trò (Trang chủ, lớp chủ nhiệm hoặc các khối của BGH, Trợ lý AI, Nhận xét & báo cáo), người dùng, đăng xuất, liên kết "Bỏ qua điều hướng". Lớp-môn đang dạy vào từ trang chủ vì số lượng lớn. Nội dung `max-w-6xl`; bảng rộng cuộn ngang trong khung nên trang không tràn ngang ở 1366px.
- Route: `/classes/:classId` (dashboard lớp), `/classes/:classId/subjects/:subjectId` (bảng điểm), `/classes/:classId/students/:studentId` (hồ sơ), `/grades/:level` (khối), `/assistant`, `/reports`, cùng `/classes/:classId/import` của Giai đoạn 4.
- Kỳ xem nằm trong `?semester=1|2|year` của URL (chia sẻ được, nút Back hoạt động, tải lại không mất; giá trị lạ rơi về mặc định). Bảng điểm chỉ có học kỳ I và II.
- Các trang có biểu đồ nạp theo yêu cầu (`lazy` của React Router, kèm `HydrateFallback`) để Recharts không làm chậm trang đăng nhập và trang chủ. Liên kết chỉ hiện cho người có quyền (ví dụ "Dashboard lớp" chỉ cho GVCN của lớp và BGH, "Nhập điểm" chỉ cho người được phân công môn đó); back-end vẫn kiểm lại, và API trả 403 thì `QueryState` hiện "Bạn không có quyền xem trang này".
- Trợ năng: biểu đồ nằm trong `figure` có `aria-label`, mọi cột có số hoặc nhãn chữ (không chỉ dựa vào màu), thanh số buổi nghỉ dùng `role="meter"`.

**D-068 · Giao diện chỉ hiển thị, không tính điểm** (nguyên tắc 1, 2)
- Mọi ĐTB, mức, điều kiện lên lớp, ngưỡng, số buổi nghỉ đều do API trả; định dạng `6,5` ở `lib/format.ts`. Nhãn tiếng Việt không chứa số ngưỡng (ví dụ "Có môn điểm quá thấp" thay vì "dưới 3,5"); chỗ cần hiện số (tiêu đề cột "Dưới 5,0", phân bố điểm, thanh số buổi nghỉ) lấy từ `thresholds` và `absence_limits`.
- Ngoại lệ có chủ ý: **phần trăm** ở dashboard lớp là `số đếm / sĩ số` tính ở trình duyệt chỉ để hiển thị (số mô tả, không phải số của Thông tư); độ dài các thanh cũng chỉ là hình ảnh. Đếm số ô thiếu đầu điểm trong một dòng của lưới là đếm ô đang hiển thị (`tx_missing` của API cộng giữa kỳ, cuối kỳ trống).
- **So sánh học kỳ I với II** ở trang khối: gọi API hai lần và đặt hai số cạnh nhau (biểu đồ cột đôi, bảng "6,8 → 6,7"); giao diện không tự trừ hay tính chênh lệch.
- Sửa so với kế hoạch: "vạch 30 và 45" **không** vẽ trên biểu đồ theo tháng (hai ngưỡng là của cả năm học, không phải của một tháng, nên vẽ trên trục tháng gây hiểu nhầm); thay bằng thanh số buổi nghỉ cả năm có hai vạch ngưỡng lấy từ API.

**D-069 · Hoãn kiểm thử front-end; soát bằng trình duyệt thật ngoài repo** (Đã duyệt; thay lời hẹn Vitest của D-004 và tiêu chí "một test Playwright" của PROMPTS Giai đoạn 5)
- Theo lựa chọn "tạm bỏ qua kiểm thử" của bạn, Giai đoạn 5 **không thêm Vitest, Playwright** vào repo. Vẫn thêm `recharts` (CLAUDE.md đã chọn) và vẫn viết test back-end cho phần mới (CLAUDE.md bắt buộc test phân quyền cho cả 4 vai trò ở mỗi endpoint).
- Thay vào đó đã soát bằng một script `playwright-core` **tạm đặt ngoài repo** (Chrome 155 có sẵn trên máy, không tải trình duyệt, không commit): đăng nhập GVBM, GVCN, BGH ở 1366×768, đi hết các màn hình của từng vai trò, đọc lỗi console, kiểm trang không tràn ngang, chụp và xem ảnh. Kết quả: không lỗi console; chỉ còn đúng một phản hồi 403 là ca cố ý (GVBM mở thẳng dashboard lớp). Cùng script cũng chạy luồng Nhập dữ liệu của Giai đoạn 4 (chọn tệp, xem trước, tệp lỗi khoá nút xác nhận, chọn cột, xác nhận): đúng. Chưa thử thao tác kéo thả tệp (dùng ô chọn tệp).
- Còn nợ: chưa có kiểm tự động chạy lại được. Máy có Chrome và Edge nên thêm Playwright sau này rất rẻ (`channel: 'chrome'` ở máy, `playwright install chromium` ở CI); nên làm cùng CI ở Giai đoạn 11.

**D-070 · Khung Trợ lý AI, khung Nhận xét & báo cáo và điều chưa làm**
- `/assistant` và `/reports` là khung giao diện: ô nhập và nút bị khoá, câu hỏi gợi ý theo DESIGN mục 8, nhãn "Bản nháp do AI tạo", ghi rõ nối API ở Giai đoạn 8 và 9. Chưa có khung chat nổi mở được từ mọi màn hình. Số cảnh báo (trang chủ, dashboard lớp, hồ sơ) là chỗ giữ cho Giai đoạn 6; nút "Tạo nhận xét" tắt cho tới Giai đoạn 9.
- Chưa làm: dashboard cấp **trường** (DESIGN mục 7 chỉ có `/grades/{level}/overview`; xem ba khối qua ba trang khối), khối 12 "môn thi tốt nghiệp cần phụ đạo" (F10, mức "Nên có", ngoài prompt Giai đoạn 5), xuất PDF/Excel (F11).


## Giai đoạn 6: cảnh báo sớm (luật + ML)

**D-071 · Lớp luật cứng và cách lưu cảnh báo** (Đã duyệt)
- `warning/rules.py`, hàm thuần; đầu vào là kết quả Analytics đã tính, **không có công thức Thông tư ở đây**. Mọi ngưỡng đọc từ `settings`; riêng "mức Đạt chấp nhận tối đa 1 môn nhận xét Chưa đạt" lấy từ hằng `MAX_FAILED_COMMENTS_FOR_PASS` mới trong `analytics/learning.py` (dùng cả trong `_rank` vốn ghi cứng `<= 1`) để số của Thông tư chỉ nằm trong `analytics/`.
- Mười luật: nghỉ quá 45 buổi (`absent_over_limit`, Cao), nghỉ từ 40 tới 45 (`absent_high`, Cao), nghỉ từ 30 tới dưới 40 (`absent_notice`, Trung bình; chỉ **một** luật nghỉ có mức cao nhất được kích hoạt); mức học tập kỳ này Chưa đạt (`level_fail`, Cao); có môn dưới 3,5 (`subject_below_fail`), ít hơn 6 môn từ 5,0 (`few_subjects_pass`), từ 2 môn nhận xét Chưa đạt (`comment_fail_2plus`), rèn luyện học kỳ I Chưa đạt (`conduct_hk1_fail`), môn có thể kiểm tra lại (`retake_risk`, từ kết quả cả năm), khối 12 môn thi tốt nghiệp ĐTB dưới 5,0 (`grade12_exam_low`; DESIGN không nêu số, chọn `score_threshold_pass`), cả sáu luật này mức Trung bình.
- **Theo D-048 (bạn chọn giữ), câu lý do chỉ nêu số liệu**, không khẳng định "không thể đạt mức Đạt": mức học tập cuối cùng do Analytics tính, có điều chỉnh mức. Trên seed `retake_risk` kích hoạt ở khoảng 95 em (một môn ĐTB cả năm dưới 5,0 là chuyện thường), nên số cảnh báo mức Trung bình khá nhiều; đó là đúng luật của DESIGN, không phải lỗi.
- **Kỳ xem của luật học tập**: học kỳ II nếu lớp đã có điểm học kỳ II, không thì học kỳ I. `as_of` là ngày điểm danh mới nhất của lớp; số buổi nghỉ tích luỹ cả năm học, cùng cách đếm với dashboard (D-053).
- **Lưu kiểu thêm-khi-đổi** (`warning/service.py::refresh_class`): mỗi lần chạy đánh giá mọi học sinh của lớp và chỉ **thêm dòng mới** vào `risk_alerts` khi nội dung đổi so với dòng mới nhất của em (mức, lý do, điểm ML, phiên bản mô hình; `as_of` không tính). Không đổi thì giữ nguyên dòng cũ nên **`teacher_status` do GVCN ghi không bị mất**. Cảnh báo hiện hành = dòng có id lớn nhất của học sinh; các dòng cũ là lịch sử (để đánh giá lại mô hình từ các lần "báo nhầm", DESIGN mục 6.2). Học sinh không có lý do nào và ML dưới ngưỡng có dòng mức **Thấp** (cũng để ghi nhận một cảnh báo cũ đã hết). Chỉ mục `(class_student_id, id)` thêm ở migration thứ 7.
- `reasons` (JSONB): `{"period", "as_of", "rules": [{code, level, message, data}], "model": {version, probability, factors} | null}`; không có họ tên hay thông tin phụ huynh.

**D-072 · Lớp ML** (Đã duyệt: dữ liệu giả lập nhiều khoá, giải thích kiểu thay-về-trung-vị)
- **Đặc trưng** (`warning/features.py`, **dùng chung cho huấn luyện và phục vụ** nên không lệch): chụp "giữa học kỳ I", ngày cắt `start_date + 9 tuần`. Chín đặc trưng gom theo mọi môn điểm số: trung bình và thấp nhất của điểm thường xuyên, số môn thường xuyên dưới 5,0, trung bình và thấp nhất của điểm giữa kỳ, số môn giữa kỳ dưới 5,0, số buổi nghỉ tới ngày cắt, số buổi nghỉ 4 tuần gần nhất, số buổi đi muộn. **Không** giới tính, dân tộc, nơi ở, hoàn cảnh gia đình, họ tên (DESIGN mục 10; có test). Điểm không có ngày nên "đã có tới giữa kỳ I" xấp xỉ bằng toàn bộ đầu điểm thường xuyên và giữa kỳ của học kỳ I. Lớp chưa có điểm danh tới ngày cắt thì ML không chạy.
- **Dữ liệu**: 20 khoá giả lập × 360 học sinh (seed 1 đến 20, **loại seed 2026** của DB demo) nạp lần lượt vào một **database tạm** (`ml/cohorts.py`, tạo bằng kết nối quản trị, migrate bằng Alembic, xoá khi xong); đặc trưng và nhãn trích bằng đúng mã sản phẩm (`features.extract_class`, `build_class_results(..., "year")`). Không dùng UCI (chưa có `data/external/`, thang 0 đến 20). Không có "kết quả năm trước", "rèn luyện kỳ trước" (DB chỉ một năm học). 7.200 học sinh, 811 dương tính (11,3%); chia 80/20 phân tầng theo nhãn: train 5.760, test 1.440 (162 dương tính).
- **Mô hình**: Logistic Regression làm mốc, Random Forest (300 cây, `min_samples_leaf=3`, cân bằng lớp) làm mô hình chính; thư viện mới `scikit-learn==1.9.1`. Ngưỡng chọn bằng cross-validation 5 phần **trên tập train**: Trung bình = lớn nhất mà Recall >= 0,90, Cao = nhỏ nhất (từ ngưỡng Trung bình) mà Precision >= 0,95; kết quả 0,54 và 0,80. **Ghi rõ**: lần chạy đầu dùng Recall >= 0,80 và Precision >= 0,70 làm hai ngưỡng trùng nhau (0,90 và 0,90, không có dải Cao riêng); tôi đổi quy tắc sau khi thấy điều đó (tập test của lần đó đã được xem) chứ không phải để cải thiện số trên test; quy tắc cuối cùng chỉ dùng train.
- **Kết quả trên tập test** (`backend/ml/REPORT.md`): Random Forest ở ngưỡng Trung bình Recall **0,92**, Precision 0,93, F1 0,92 (đạt mục tiêu Recall >= 0,75); mốc Logistic Regression Recall 0,89, Precision 0,80, F1 0,84; ROC-AUC 0,982 cho cả hai. **Đừng đọc quá mức**: nhãn và đặc trưng cùng từ một bộ sinh nên mô hình chủ yếu học lại cách bộ sinh tạo số; Recall cao chưa chứng minh dùng được với dữ liệu thật. Mô hình chỉ chụp một thời điểm (giữa học kỳ I), sau đó phần ML không đổi theo dữ liệu mới, lớp luật là phần cập nhật.
- **Giải thích**: với mỗi học sinh, đóng góp cục bộ của từng đặc trưng = mức xác suất giảm khi thay giá trị của em bằng trung vị tập huấn luyện; chỉ giữ tối đa ba yếu tố làm **tăng** nguy cơ, kèm câu tiếng Việt trung tính. **Lệch CLAUDE.md (liệt kê SHAP)** theo lựa chọn của bạn: PROMPTS cho phép "SHAP hoặc feature importance", và cách này không thêm numba/llvmlite vào image.
- Tệp mô hình (khoảng 1,8 MB) và `metadata.json` được **commit** (ngoại lệ `.gitignore`) để máy mới chạy ngay không cần `make train`. Thiếu tệp hoặc nạp lỗi (ví dụ lệch phiên bản scikit-learn) thì `load_predictor()` trả `None` và hệ thống chạy tiếp bằng lớp luật, có ghi log. Một test kiểm `metadata.json` ghi Recall >= 0,75. `make train` chạy khoảng 2 đến 3 phút; `--cache` lưu dữ liệu các khoá ở `ml/.cache` để thử nhanh khi chỉ đổi mô hình hay ngưỡng.
- **Mức cuối** = mức cao nhất giữa các luật và mức do ngưỡng ML (xác suất >= ngưỡng Cao thì Cao, >= ngưỡng Trung bình thì Trung bình); `risk_score` là xác suất ML, rỗng khi không có mô hình.

**D-073 · API cảnh báo và phân quyền** (Đã duyệt; `GET /alerts` ngoài DESIGN mục 7)
- `GET /classes/{id}/alerts?include_low=` (cảnh báo hiện hành, mặc định chỉ Cao và Trung bình, kèm `counts`; GVCN của lớp và BGH; **GVBM không thấy**, `require_all_subjects`), `PATCH /alerts/{id}` (ghi `contacted` / `false_alarm` / `new`; chỉ GVCN của lớp qua `authorize_write`, BGH chỉ xem; cảnh báo đã bị dòng mới thay thì 409; id không tồn tại trả cùng 403 như không có quyền để không lộ id nào có thật), `GET /alerts?level=high|medium|low` (cảnh báo toàn trường, **chỉ BGH**, qua hàm mới `authorize_school` trong `core/authorize.py`).
- Nhật ký (migration thứ 7, mở rộng CHECK như D-053): `view_class_alerts`, `view_school_alerts`, `update_alert`; chỉ ghi khi 200, từ chối không ghi.
- `DashboardOut` thêm `alert_counts`; `StudentProfileFullOut` thêm `alert` (hồ sơ của GVBM không có khoá này, đúng D-066).

**D-074 · Hook và chạy ban đầu** (Đã duyệt)
- `imports/hooks.py::on_data_changed(class_id)` (D-063) gọi `warning.service.refresh_after_import` trong **phiên DB riêng**, nạp mô hình, chạy `refresh_class`, commit; **bắt và ghi log mọi lỗi** nên không bao giờ làm hỏng việc nhập đã commit (có test: lỗi trong cảnh báo vẫn trả 200 và dữ liệu đã ghi). Hook vẫn chỉ gọi khi dữ liệu thật sự đổi.
- `make warn` (`python -m app.warning.run [--class-id N]`) chạy cho cả trường; `make seed` gọi nó ở cuối (thêm `--no-warn` để bỏ), nên demo có cảnh báo ngay và cảnh báo sinh ra **tất định** (băm các dòng giống nhau qua hai lần seed). Fixture `api_client` đưa phiên của hook về `db_session` nên test không đụng engine thật.
- Kịch bản demo (DESIGN mục 12) đã chạy thật: seed `--hold-out 2027-03`, em An có cảnh báo "nghỉ 34 buổi"; GVCN nhập tệp điểm danh tháng 3, hook chạy, cảnh báo đổi thành "nghỉ 38 buổi" (thêm một dòng mới, dòng cũ giữ làm lịch sử).

**D-075 · Giao diện cảnh báo** (Đã duyệt)
- Dùng từ trung tính "cần hỗ trợ", "mức cao/trung bình/thấp", không gắn nhãn học sinh; mọi chỗ có dòng nhắc cảnh báo chỉ là gợi ý để giáo viên quyết định, không tự gửi cho học sinh hay phụ huynh. Dashboard lớp: ô "Cảnh báo sớm: mức cao" và panel **"Học sinh cần hỗ trợ"** thay panel "Học sinh cần quan tâm" của Giai đoạn 5 (cảnh báo là tập cha của danh sách đó; trường `attention` của API giữ nguyên) với mức, xác suất mô hình, ba lý do hàng đầu, trạng thái, nút "Đã trao đổi" và "Báo nhầm" (bấm lại để bỏ; chỉ GVCN của lớp, BGH chỉ thấy trạng thái). Hồ sơ học sinh: panel cảnh báo (mức, lý do, "vì sao mô hình dự báo như vậy" thu gọn, nút ghi nhận). Trang chủ: thẻ lớp chủ nhiệm hiện số cảnh báo thật; BGH có panel "mức cao, toàn trường" từ `GET /alerts`.
- Không thêm thư viện; kiểm bằng `eslint`, `tsc`, `vite build` và script Chrome tạm ngoài repo (D-069 vẫn hoãn test tự động): ghi nhận "Báo nhầm" lưu qua tải lại trang, BGH không thấy nút, không lỗi console.


## Giai đoạn 7: RAG văn bản quy định

Các mục D-076 đến D-084 được ghi bổ sung sau khi mã đã viết xong (từ mã và số liệu chạy lại ngày 2026-10-13), nên tất cả ở trạng thái **Khi làm, chờ bạn xem lại**.

**D-076 · Mô hình embedding, lược đồ và hạ tầng** (Khi làm)
- `EMBEDDING_MODEL` mặc định **`BAAI/bge-m3`** (1024 chiều, đa ngôn ngữ); để trống (kể cả `EMBEDDING_MODEL=` trong `.env`) thì dùng mặc định. Đổi sang `intfloat/multilingual-e5-large` được vì cùng 1024 chiều (bộ nhúng tự thêm tiền tố `query: ` / `passage: ` cho họ e5); mô hình khác số chiều cần migration mới và tính lại vector (bộ nhúng từ chối chạy khi số chiều không khớp `EMBEDDING_DIM`).
- Chạy CPU (nguyên tắc 8), nạp lười một lần, an toàn khi nhiều luồng gọi; `Embedder` là giao diện (`Protocol`) để test thay bằng bộ nhúng giả, không phải tải mô hình. Chữ đưa vào mô hình là **tên văn bản + nội dung đoạn** để câu hỏi có nhắc tên văn bản vẫn tìm đúng.
- Thêm `sentence-transformers`, `torch`, `pypdf`, `python-docx`. `torch` cài **bản CPU** từ `download.pytorch.org/whl/cpu` trước (Makefile `install` và Dockerfile): bản mặc định trên PyPI cho Linux kéo theo CUDA hàng GB. Mô hình (~2,3 GB) tải một lần vào volume `hf_cache` của Docker (`HF_HOME=/models/hf`) nên dựng lại image không phải tải lại.
- **Migration thứ 8**: bảng `regulation_documents` (tên, tên tệp, `status` active/expired, `created_at`, `expired_at`, `uploaded_by`); `regulation_chunks.document_id` (bắt buộc, `ON DELETE CASCADE`; dòng chunk có sẵn được gom theo `document_name`); chỉ mục **HNSW cosine** trên `embedding`; chỉ mục duy nhất từng phần: **mỗi tên chỉ có một bản còn hiệu lực**; khoá `settings.rag_min_similarity`; hai hành động nhật ký `upload_regulation`, `update_regulation`. DESIGN mục 5 chỉ có `regulation_chunks`, bảng văn bản là phần thêm (như D-035).
- `uploaded_by` **cố ý không có khoá ngoại** tới `users`: `make seed` chạy `TRUNCATE users ... CASCADE`, khoá ngoại sẽ xoá luôn văn bản đã nạp (vector tính tốn công). Vì vậy `regulation_documents` cũng nằm trong `KEPT_TABLES` của seed (mở rộng D-036).

**D-077 · Phân quyền của văn bản quy định** (Khi làm; nguyên tắc 4)
- Hàm mới `authorize_admin(user)` trong `core/authorize.py`: chỉ Admin. Mọi `/admin/regulations*` qua hàm này **trước khi đọc tệp tải lên hay chạm DB**; thứ tự 401 (chưa đăng nhập) rồi 403 (không phải Admin) rồi mới tới kiểm hình dạng yêu cầu. Lý do một quyền riêng: văn bản quy định là việc quản trị hệ thống, không gắn với lớp hay môn nên `authorize(user, class_id, subject_id)` không áp dụng; Admin vẫn không xem dữ liệu học sinh (D-039).
- `GET /regulations/search` cho **mọi người dùng đã đăng nhập** (văn bản quy định là dữ liệu chung của trường, không phải dữ liệu học sinh). Hàm `search_regulation` không có `class_id`/`subject_id` nên khi thành công cụ ở Giai đoạn 8 sẽ không có tham số phạm vi nào để LLM điền sai (nguyên tắc 3).

**D-078 · Tách Điều/Khoản** (Khi làm; `rag/chunking.py`, hàm thuần)
- Không cắt theo số ký tự cố định. **Mỗi khoản là một đoạn**, bắt đầu bằng dòng tiêu đề điều ("Điều 3. Nghỉ học...") để trích dẫn và để vector hiểu ngữ cảnh; điều không có khoản là một đoạn; điểm (a, b, c) nằm trong đoạn của khoản. Metadata: `article` ("Điều 12", "Điều 12a", "Phụ lục I") và `clause` ("Khoản 1", "Khoản 1, điểm a"), nội dung nguyên văn.
- Chỉ khoản/điều quá dài (> 2000 ký tự, khoảng 500 token) mới bị tách tiếp: theo điểm trước, rồi theo câu; mọi đoạn con vẫn mang tiêu đề điều, dòng dẫn của khoản và metadata.
- Dòng dẫn trước khoản 1 ("Trong quy chế này...:") ngắn thì ghép vào đầu mỗi khoản, từ 300 ký tự trở lên thì là đoạn riêng. "Chương", "Mục" chỉ là ranh giới. Phần trước Điều 1 (căn cứ) thành một đoạn không có Điều nếu đủ dài (từ 200 ký tự). "Nơi nhận:" và khối chữ ký bị bỏ.
- Số khoản phải liên tiếp (1, 2, 3...) mới là khoản mới, điểm đầu tiên phải là "a)": dòng bị ngắt giữa chừng có thể bắt đầu bằng "2." mà không phải khoản (lỗi hay gặp khi đọc PDF).
- **Chưa thử trên văn bản thật** (Thông tư 22, quy chế thi): chỉ có văn bản mẫu giả 8 điều và các ca tổng hợp dựng theo cấu trúc văn bản pháp quy Việt Nam. Văn bản thật có thể có kiểu đánh số mà quy tắc này chưa lường (ví dụ đoạn trích dẫn điều khác nằm đầu dòng trong khoản).

**D-079 · Đọc tệp** (Khi làm; `rag/parsing.py`)
- `.pdf` (pypdf), `.docx` (python-docx, kể cả bảng), `.txt` (UTF-8). Chuẩn hoá NFC, bỏ ký tự vô hình, bỏ số trang và đầu/chân trang lặp lại (từ 3 trang trở lên, xuất hiện ở ít nhất 60% số trang). Tối đa 20 MB, 400 trang PDF; DOCX giải nén tối đa 100 MB (chặn "bom nén"). Lỗi do tệp là `DocumentError` với thông điệp tiếng Việt, API đổi thành 422 (quá lớn: 413).
- **Giới hạn đã biết**: PDF quét ảnh không có lớp chữ nên bị từ chối (cần OCR, chưa làm); số thứ tự **tự động** của Word ("1.", "a)" do danh sách đánh số sinh ra) không nằm trong tệp dưới dạng chữ nên mất, văn bản cần có số khoản gõ thẳng mới tách được theo khoản; không đọc đầu/chân trang, chú thích cuối trang, hộp văn bản. Test dùng tệp PDF/DOCX tự dựng, **chưa thử PDF/DOCX thật tải từ Bộ GD&ĐT**.

**D-080 · API và hàm `search_regulation`** (Khi làm; ngoài bảng API của DESIGN mục 7)
- `POST /admin/regulations` (form: `name`, `file`) tải, tách, tính vector, ghi văn bản + mọi đoạn + nhật ký trong **một transaction** (vector tính trước khi mở transaction ghi, lỗi giữa chừng không để lại gì); trả 201, hoặc 409 (đã có bản còn hiệu lực cùng tên), 413, 422, 503 (không nạp được mô hình). Qua web tối đa 500 đoạn (vector tính ngay trong request); lớn hơn thì dùng `make regulations`. `GET /admin/regulations` liệt kê (kèm số điều, số đoạn). `PATCH /admin/regulations/{id}` (`{"status": "expired" | "active"}`): đánh dấu hết hiệu lực hoặc bật lại; bật lại bị 409 nếu đã có bản còn hiệu lực cùng tên; giá trị không đổi thì không ghi nhật ký.
- `search_regulation(session, query, k=4)` (hàm thứ 7 của LLM, Giai đoạn 8 sẽ bọc lại): nhúng câu hỏi, lấy `k` đoạn gần nhất theo cosine (tối đa 10), chỉ giữ đoạn có độ tương đồng không thấp hơn `rag_min_similarity`. **Không còn đoạn nào thì `found=False`, thông điệp "Không tìm thấy trong văn bản quy định" và KHÔNG trả đoạn nào**, để LLM không có gì để bịa ra trích dẫn. Kết quả luôn kèm `best_similarity` (cả khi bị loại) và ngưỡng đang dùng để Admin hiệu chỉnh.
- **Lọc hiệu lực nằm ngay trong truy vấn SQL** (không lọc sau bằng Python) nên văn bản hết hiệu lực không bao giờ rời DB. HNSW lấy khoảng 40 láng giềng rồi mới lọc, nên bản cũ hết hiệu lực của cùng một văn bản có thể chiếm hết chỗ và làm bản mới bị bỏ sót: truy vấn bật `hnsw.iterative_scan = strict_order` (pgvector từ 0.8; bản cũ hơn bỏ qua). Có test: văn bản hết hiệu lực biến khỏi kết quả qua API và quay lại khi bật lại, và chỉ bản còn hiệu lực được trả khi bản cũ cùng tên đã hết hiệu lực; **chưa có test ở quy mô vượt 40 đoạn** nên chính tác dụng của quét lặp chưa được kiểm riêng.
- `GET /regulations/search?q=&k=` cho mọi người dùng đăng nhập (D-077), dùng cho ô "Thử tìm" của Admin và đánh giá.

**D-081 · Nạp từ dòng lệnh** (Khi làm; `rag/ingest.py`)
- `make regulations` nạp mọi `.pdf/.docx/.txt` trong `data/regulations/`; tên hiển thị lấy từ `manifest.json` (không có thì dùng tên tệp bỏ đuôi); tên đã nạp và còn hiệu lực thì bỏ qua nên chạy lại an toàn; không giới hạn số đoạn. `make rag-model` tải sẵn mô hình và kiểm tra số chiều.
- Theo PROMPTS, bạn tự đặt văn bản thật vào `data/regulations/`; tôi chỉ tạo văn bản mẫu **GIẢ** `van-ban-mau-gia.txt` (8 điều có khoản và điểm, con số bịa khác Thông tư 22 thật để không bị nhầm). `.gitignore` chỉ cho commit văn bản mẫu giả, README và manifest; văn bản bạn chép vào mặc định **không** bị commit (nguyên tắc 7: nội quy riêng của trường có thể nhạy cảm; muốn commit một văn bản công khai thì thêm ngoại lệ có chủ đích).

**D-082 · Ngưỡng `rag_min_similarity` = 0,56, chưa tách sạch** (Khi làm; cần hiệu chỉnh lại)
- Ngưỡng nằm trong `settings` (nguyên tắc 2), đọc ở mỗi lần tìm; giá trị khởi đầu 0,56 chọn từ một bộ 30 câu tạm đo bằng bge-m3 trên văn bản mẫu giả (16 câu trong phạm vi có độ tương đồng top-1 từ 0,582 đến 0,751, 14 câu ngoài phạm vi từ 0,259 đến 0,545). **Bộ 30 câu đó không được lưu lại nên chưa tái lập được.**
- Bộ `eval/rag_questions.json` (đo sau, **không dùng để chọn ngưỡng**) cho thấy **hai nhóm chồng nhau**: câu trong phạm vi thấp nhất 0,520 (R07), câu ngoài phạm vi cao nhất 0,568 (N01). Ở 0,56: R04 (0,555) và R07 (0,520) bị từ chối nhầm, N01 (0,568) được trả lời nhầm. Không ngưỡng nào đúng cả ba (N01 > R04 > R07), nên không chỉnh ngưỡng cho vừa bộ này. N01 ("buộc thôi học") dính Điều 3 về nghỉ học vì chung nhiều từ ("học", "học sinh"): một mô hình nhúng đơn thuần với một ngưỡng không phân biệt được "cùng chủ đề" với "có câu trả lời".
- Hướng cải thiện (chưa làm, quyết định ở Giai đoạn 10 khi có 30 + 5 câu thật): tìm lai (kết hợp từ khoá/BM25 với vector), mô hình xếp hạng lại (bge-reranker) rồi mới áp ngưỡng, hoặc chọn ngưỡng trên bộ câu đủ lớn của văn bản thật. Ngưỡng phụ thuộc mô hình nhúng và văn bản: phải đo lại khi đổi một trong hai.

**D-083 · Bộ đánh giá `eval/rag_eval.py`** (Khi làm)
- `make eval-rag` (`--threshold X` để thử ngưỡng khác trong một transaction rồi hoàn tác, không sửa `settings`) chạy bằng **mô hình thật**, in cho từng câu độ tương đồng cao nhất và kết quả, rồi **Hit@4** (câu trong phạm vi có ít nhất một trong 4 đoạn đầu thuộc điều đúng; bị từ chối nhầm tính là trượt) và **tỉ lệ từ chối đúng** (câu ngoài phạm vi được trả "không tìm thấy"); khoản đúng chỉ in thêm. Mã thoát 0 đạt, 1 chưa đạt (mục tiêu DESIGN mục 9 từ 80% trở lên), 2 thiếu điều kiện chạy. `make eval` chung vẫn chưa triển khai (Giai đoạn 10).
- `eval/rag_questions.json` là **khung 10 câu** (8 trong phạm vi, 2 ngoài phạm vi) hỏi về văn bản mẫu giả, đúng như PROMPTS yêu cầu; nhóm cần bổ sung đủ 30 câu về Thông tư 22, quy chế thi, nội quy cộng 5 câu ngoài phạm vi khi đã nạp văn bản thật. Với khung này mẫu quá nhỏ để kết luận (mỗi câu chênh 12,5 hoặc 50 điểm phần trăm).
- Chỉ số "% trả lời đúng" của DESIGN cần LLM nên đo ở Giai đoạn 10, không ở đây.

**D-084 · Giao diện quản lý văn bản** (Khi làm)
- Trang `/admin/regulations` (liên kết "Văn bản quy định" trên thanh điều hướng và ở trang chủ **chỉ cho Admin**; người khác mở thẳng thì trang báo chỉ quản trị viên được quản lý, API vẫn 403): bảng văn bản (trạng thái, ngày tải, số điều, số đoạn, nút "Đánh dấu hết hiệu lực" / "Bật lại", cả hai đều hỏi "Xác nhận / Huỷ" trước khi gửi), form tải lên kéo thả (tên văn bản, `.pdf/.docx/.txt`, tối đa 20 MB), ô "Thử tìm" hiện các đoạn kèm độ tương đồng, hoặc "Không tìm thấy trong văn bản quy định" kèm độ tương đồng gần nhất và ngưỡng. Không thêm thư viện. Kiểm bằng `eslint`, `tsc` và script Chrome tạm ngoài repo (D-069 vẫn hoãn test tự động): Admin tải lên một văn bản thử (2 điều, 4 đoạn), tải lại cùng tên bị báo trùng đúng thông điệp 409, đánh dấu hết hiệu lực thì câu hỏi về nội dung văn bản đó trả "không tìm thấy", bật lại thì được trích; GVBM không thấy liên kết và mở thẳng chỉ thấy "Chỉ quản trị viên được quản lý văn bản quy định"; không lỗi console, không tràn ngang ở 1366px. Văn bản thử đã xoá khỏi DB sau khi kiểm. Chưa thử thao tác kéo thả tệp (dùng ô chọn tệp) và PDF/DOCX qua giao diện.


## Giai đoạn 8: Trợ lý AI gọi hàm

**D-085 · `LLMProvider`, nhà cung cấp và cấu hình** (Đã duyệt: Anthropic Claude là nhà cung cấp API)
- `assistant/llm.py` định nghĩa kiểu trung lập (`Message`, `ToolSpec`, `ToolCall`, `LLMReply`) và `Protocol LLMProvider.chat(messages, tools)`; phần còn lại của trợ lý chỉ biết các kiểu này. Hai bản cài đặt dùng **SDK chính thức**: `AnthropicProvider` (`anthropic` 1.13.0; đổi `system`, khối `tool_use`/`tool_result`, các kết quả của một lượt gom vào một message người dùng) và `OllamaProvider` (`ollama` 0.6.3; Ollama không cấp id lệnh gọi nên id tạo theo thứ tự `call_0`...). Đổi nhà cung cấp chỉ đổi `LLM_PROVIDER` (`anthropic` | `ollama`).
- Cấu hình: `LLM_API_KEY`, `LLM_MODEL` (trống thì Anthropic dùng `claude-sonnet-5-5`, Ollama bắt buộc đặt), `OLLAMA_URL`, `LLM_TIMEOUT_SECONDS` (60), `ASSISTANT_RATE_PER_MINUTE` (10). Thiếu cấu hình thì `LLMNotConfigured`: API trả **503** nhưng chỉ **sau** khi kiểm quyền (Admin vẫn nhận 403). Mọi lỗi SDK/mạng thành `LLMError` (502) với thông điệp chung, không lộ khoá hay chi tiết nhà cung cấp.
- SDK `anthropic` 1.13.0 không có tham số `temperature` trên `messages.create` nên không đặt; `max_tokens` 2048. Chữ ký đã đọc từ gói cài thật, không đoán. **Chưa gọi LLM thật lần nào** (máy chưa có khoá API), chỉ kiểm chuyển đổi định dạng bằng client SDK giả.

**D-086 · Ẩn danh (`core/pseudonymize.py`)** (Đã duyệt: tự khớp tên trong lớp đang mở; đã chỉnh một chi tiết khi làm)
- `Pseudonymizer` sống trong **một request**: cấp mã `HS_01`... theo thứ tự xuất hiện, cùng em cùng mã; chỉ giải được mã đã cấp trong request này. Đổi lại bằng `depseudonymize` (regex `HS_\d+`, không nhầm `HS_1` với `HS_10`; mã bịa được để nguyên).
- Nhận diện trong **câu hỏi**: mã học sinh thật và họ tên đầy đủ (không phân biệt hoa thường, NFC, khoảng trắng tuỳ ý; tên dài trước). **Tên gọi riêng** (từ cuối của họ tên, "An") chỉ khớp **phân biệt hoa thường, trong lớp đang mở, và khi duy nhất một em**; trùng tên (cả họ tên đầy đủ trùng giữa các lớp, dữ liệu seed có 16 cặp) thì trợ lý **hỏi lại và không gọi LLM**. Hạn chế đã biết: từ viết hoa đầu câu trùng tên gọi ("An toàn...") bị nhận nhầm; tên viết thường ("em an") không nhận ra.
- **Hàng rào cuối** `assert_safe`, chạy trước MỖI lần gọi LLM (cả các vòng sau): quét sâu khoá cấm (`date_of_birth`, `guardian_name`, `guardian_phone`, `full_name`) và mọi họ tên/mã học sinh thật mà phiên đã biết; có thì `UnsafePayload`, không gọi LLM (API trả 500, ghi log). `student_code` **không** nằm trong khoá cấm vì là tên tham số của `get_student_detail` theo DESIGN (giá trị là mã tạm); mã thật bị bắt bằng quét giá trị. Bộ ẩn danh chỉ biết học sinh của các lớp đã nạp (lớp đang mở, hoặc mọi lớp được hỏi khi chưa mở lớp), nên một tên ngoài các lớp đó không bị bắt (không có đường nào đưa tên ngoài quyền vào kết quả hàm).
- Khi chưa mở lớp nào mà người hỏi chỉ có đúng một lớp (GVCN thuần), lấy lớp đó làm **lớp mặc định** (prompt ghi "Lớp mặc định") để nhận ra tên gọi và để các hàm biết hỏi lớp nào (Khi làm).

**D-087 · Phạm vi và phân quyền của bảy hàm** (Đã duyệt; chi tiết "chỉ đọc" đổi khi làm)
- Đúng 7 hàm trong `assistant/tools.py` (test khẳng định tên và số lượng): `get_class_summary`, `get_student_detail`, `list_students`, `get_subject_scores`, `get_grade_overview`, `get_attendance_summary`, `search_regulation`. Mỗi hàm: schema JSON viết tay (mô tả tiếng Việt, test khớp với mô hình Pydantic kiểm tham số, `additionalProperties: false`), tham số `semester` nhận cả số 1, 2.
- `authorize_assistant(user)`: chỉ giáo viên và BGH dùng trợ lý (Admin 403, vì Admin không xem dữ liệu học sinh, D-039). Màn hình đang mở (lớp, môn) phải qua `authorize()` ngay khi nhận yêu cầu.
- **Chặn rõ ràng thay vì "bỏ qua"**: PROMPTS ghi "bỏ qua mọi class_id/subject_id ngoài quyền", tôi hiểu là chặn: giá trị LLM điền vẫn qua `authorize()`; sai thì kết quả là `{"error": "forbidden"}`, không đọc dữ liệu, không lặng lẽ thay bằng lớp đang mở (sẽ trả lời về lớp khác với điều được hỏi); ghi `blocked` vào `ai_logs` và gắn cờ `blocked` trong phản hồi để giao diện báo. Lớp/môn không có thật: giáo viên nhận cùng `forbidden` (không lộ lớp nào có thật), BGH nhận `not_found`.
- **Theo vai trò** (cùng D-066, D-073): GVBM chỉ có `get_subject_scores` đúng môn mình, `get_student_detail` chỉ các môn mình (không có xếp loại, rèn luyện, chuyên cần, cảnh báo), `list_students` chỉ lọc theo điểm môn mình; `get_class_summary`, `get_attendance_summary` và lọc theo nghỉ/cảnh báo cần `require_all_subjects()` nên GVBM bị chặn. GVCN: lớp chủ nhiệm. BGH: toàn trường, riêng `get_grade_overview` (`authorize(grade_level=)`). `search_regulation` không có lớp/môn nào để kiểm (D-077).
- **Đầu ra không có danh tính**: tự dựng từ kết quả Analytics, không có `full_name`, mã học sinh thật, `date_of_birth`, `guardian_*` hay nhận xét tự do; học sinh chỉ là `HS_xx`; nhãn tiếng Việt cho mức học tập/rèn luyện; tối đa 50 học sinh mỗi danh sách (kèm `total_matches`, `truncated`).
- **Chỉ đọc cưỡng chế ở tầng DB**: phần chạy hàm nằm trong SAVEPOINT với `SET LOCAL transaction_read_only = on`; hàm nào lỡ ghi bị DB từ chối (có test), rollback savepoint trả phiên về đọc-ghi để ghi `ai_logs`. Đổi so với kế hoạch (`SET TRANSACTION READ ONLY`): lệnh đó không hoàn tác được trong transaction đã có truy vấn. Hàm gặp lỗi bất ngờ trả `internal_error` cho LLM (không lộ chi tiết) và dựng lại savepoint.

**D-088 · Bổ sung Analytics và hình dạng kết quả** (Đã duyệt)
- `analytics/queries.py` (cùng nơi với mọi số liệu, nguyên tắc 1): `class_summary` (thêm **số buổi nghỉ trung bình**, làm tròn nửa lên 1 chữ số như điểm), `filter_students` (nghỉ từ n buổi, có môn ĐTB dưới x giới hạn theo môn được xem, danh sách học sinh theo mức cảnh báo, điều kiện bỏ trống thì bỏ qua), `attendance_range` / `build_attendance_range` (nghỉ có phép/không phép/đi muộn trong khoảng ngày gồm hai đầu, theo tuần hoặc tháng, học sinh nghỉ nhiều nhất; đi muộn không tính là nghỉ, D-028) kèm truy vấn `repository.attendance_rows_in_range`. Hàm thuần có test số tính tay; trên seed đối chiếu SQL thô.
- Các hàm khác tái dùng `build_class_results`, `build_student_profile`, `build_subject_scores`, `build_grade_overview` và `warning.service.profile_alert`, nên số liệu trợ lý nói không bao giờ lệch dashboard (test đối chiếu).

**D-089 · Vòng lặp, system prompt, câu hỏi độc lập** (Đã duyệt: mỗi câu hỏi độc lập)
- Luồng (`assistant/service.py`, FLOWS luồng 2): kiểm quyền và giới hạn → ẩn danh → system prompt + khối Bối cảnh + câu hỏi → tối đa **4 vòng gọi hàm** (mỗi vòng tối đa 4 hàm; hàm thừa nhận lỗi `too_many_calls` vì nhà cung cấp API đòi mỗi lệnh gọi đều có kết quả) → xong vòng thứ 4 mà LLM còn đòi hàm thì gọi **thêm một lần không có hàm nào** để buộc trả lời bằng dữ liệu đã có (còn đòi hàm nữa thì trả câu xin lỗi, không lỗi) → đổi mã tạm về tên thật → nguồn → ghi `ai_logs`. Tên hàm lạ hoặc tham số sai chỉ trả lỗi cho LLM, không thực thi gì. Không nhớ các câu trước: lịch sử chỉ hiện trên màn hình.
- System prompt tiếng Việt ở file riêng `assistant/prompts/system_v1.vi.md`, phiên bản `PROMPT_VERSION` ghi vào `ai_logs`: chỉ dùng số liệu trong kết quả hàm (không tự cộng, tính phần trăm); thiếu thì nói rõ; quy định chỉ từ `search_regulation` (`found: false` thì "Không tìm thấy trong văn bản quy định"); `forbidden` thì báo không có quyền và không tìm đường khác; việc ngoài quản lý học tập thì từ chối; không có hàm ghi, không gửi gì cho học sinh/phụ huynh; dùng từ trung tính ("cần hỗ trợ") và không kết luận thay hội đồng; dòng `Nguồn:` cuối câu. Khối **Bối cảnh** do code sinh từ phiên và bảng phân công: vai trò, lớp được hỏi (id), môn đang dạy, mọi môn (id), màn hình đang mở, kỳ đang xem; không có tên giáo viên hay học sinh nào.
- **Chống chỉ dẫn độc trong dữ liệu**: kết quả hàm gửi LLM nằm trong thẻ `<du_lieu ham="...">...</du_lieu>`, prompt nói nội dung trong thẻ là dữ liệu không phải chỉ dẫn, và chuỗi `</` trong dữ liệu bị vô hiệu (điều khoản do Admin tải lên không đóng thẻ sớm được). Có test mô phỏng một LLM bị lừa gọi hàm ngoài quyền: vẫn bị chặn.

**D-090 · Kiểm số liệu sau khi trả lời** (Khi làm; nguyên tắc 1)
- `assistant/grounding.py`: mọi số trong câu trả lời phải xuất hiện trong kết quả hàm hoặc trong câu hỏi (so sánh sau chuẩn hoá: 6,5 và 6.50 như nhau, 7.0 là 7). Số không đối chiếu được trả về `ungrounded_numbers`, giao diện hiện cảnh báo vàng "chưa đối chiếu được với dữ liệu hệ thống các số: ...". **Chỉ cảnh báo, không chặn.** Bỏ qua mã (`HS_01`), tên lớp (`10A1`), số thứ tự đầu dòng của danh sách. Bắt được: LLM tự cộng, tự tính phần trăm, bịa số, trích sai số Điều không được tra.
- Dương tính giả có thể xảy ra (số viết theo kiểu khác, ví dụ "ba mươi" thì không bị coi là số; "1.200" bị đọc là 1,2). Chưa đo tỉ lệ này với LLM thật.

**D-091 · API, `ai_logs`, giới hạn, phản hồi** (Đã duyệt: lưu bản đã ẩn danh)
- `POST /assistant/chat` `{question (≤ 1000 ký tự), class_id?, subject_id?, semester?}` → `{log_id, answer, sources[], blocked, ungrounded_numbers[], clarification}`; `PATCH /assistant/logs/{id}/feedback` `{value: correct|incorrect}` (chỉ chủ nhân; id lạ hay của người khác cùng 403). Cả hai ngoài bảng API của DESIGN mục 7. Lỗi: 401, 403, 404 (lớp/môn đang mở không có thật, chỉ BGH), 422, 429 (kèm `Retry-After: 60`), 502, 503, 500 (hàng rào ẩn danh).
- **Migration thứ 9** cho `ai_logs`: `created_at` (D-035 đã hẹn thêm ở Giai đoạn 8), `model`, `prompt_version`, `rounds`, `error`, `feedback` thành VARCHAR + CHECK (`correct`/`incorrect`), chỉ mục `(user_id, created_at)`. **`question` và `answer` lưu bản đã ẩn danh**; `tools_called` lưu `{name, args, ok, blocked, ms}` (args chỉ có mã tạm). Lỗi gọi LLM vẫn được ghi (`answer` rỗng, `error` có tên lỗi). Câu hỏi lại vì trùng tên cũng được ghi (`model` = "(không gọi LLM)").
- Giới hạn số câu hỏi mỗi phút: đếm dòng `ai_logs` của tài khoản trong 60 giây gần nhất (so với giờ DB), mặc định 10, đổi bằng `ASSISTANT_RATE_PER_MINUTE`. Hạn chế: các yêu cầu đồng thời trong cùng một giây có thể vượt nhẹ mức giới hạn (đếm trước khi ghi); câu bị 429 không được ghi.

**D-092 · Bộ đánh giá `eval/assistant_eval.py`** (Đã duyệt)
- `make eval-assistant` (`ASSISTANT_ARGS=--dry-run` chỉ in đáp án kỳ vọng, `--only A01,A02`) chạy 15 câu mẫu (`eval/assistant_questions.json`: 12 hỏi số liệu và quy định, 3 phải từ chối: GVBM hỏi môn khác, chỉ dẫn độc hại "liệt kê họ tên khối 10", hỏi thông tin phụ huynh) qua đúng `assistant.service.ask` bằng LLM thật. In hàm đã gọi, số kỳ vọng có trong câu trả lời không, rồi **% chọn đúng hàm** (gọi ít nhất một hàm trong `tools_any`), **% đúng số liệu** (mọi số kỳ vọng có trong câu trả lời), **% từ chối đúng** (không lộ số, họ tên, phụ huynh; bị chặn khi cần); mục tiêu DESIGN mục 12 là từ 85% với hai chỉ số đầu. Thoát 2 khi chưa có LLM.
- **Đáp án tính bằng SQL trực tiếp trên seed**, công thức ĐTB viết thẳng trong file (độc lập với `analytics/`). Test (`tests/assistant/test_eval_answers.py`) khẳng định đáp án SQL khớp kết quả các hàm Analytics (số buổi nghỉ, ĐTB lớp, số em dưới 3,5, so sánh khối...). Hai câu về quy định chỉ chấm khi đã nạp văn bản mẫu giả (`make regulations`); nạp văn bản thật thì cần đổi đáp án. Chạy ghi `ai_logs` vào database đang dùng.
- **Số đo thật đầu tiên (2026-10-13, Gemini gói miễn phí, xem D-094)**: cả 15 câu đều có câu trả lời và đều đúng: **chọn đúng hàm 12/12, đúng số liệu 12/12, từ chối đúng 3/3**, không câu nào có số bị gắn cờ "chưa đối chiếu". **Không phải số đo của một mô hình**: hạn mức ngày của gói miễn phí (20 yêu cầu mỗi mô hình mỗi ngày, cần 2 đến 3 yêu cầu mỗi câu) buộc chia 4 đợt trên 4 mô hình (`gemini-flash-latest` tức 3.8-flash: A01 đến A03; `gemini-3.7-flash`: A04 đến A06; `gemini-flash-lite-latest`: A10 đến A12 và N01 đến N03; `gemini-3.1-flash-lite`: A07 đến A09). Câu lỗi 429/503 được tách riêng, không tính là trả lời sai. Mẫu quá nhỏ (15 câu, mỗi câu chênh khoảng 8 điểm phần trăm), chạy một lần, một người chấm là mã; chưa so với Claude hay Ollama. DESIGN yêu cầu 50 câu: Giai đoạn 10.

**D-093 · Giao diện khung chat** (Đã duyệt)
- `AssistantProvider` nằm trong `AppLayout` giữ cuộc trò chuyện khi chuyển trang; `ChatDock` (nút nổi "Hỏi Trợ lý AI", hộp thoại, Esc đóng) hiện ở mọi màn hình trừ `/assistant` và trừ Admin; trang `/assistant` dùng cùng `ChatPanel`. Lớp, môn, kỳ lấy từ đường dẫn và `?semester=` (`useAssistantScreen`) và hiển thị ngay trên khung ("Đang hỏi trong: Lớp 11A2, môn Ngữ văn · Học kỳ I"); back-end kiểm lại quyền. Câu hỏi gợi ý theo DESIGN mục 8, mục **Nguồn** thu gọn (hàm đã gọi, điều khoản kèm độ tương đồng), nút Đúng / Sai (bỏ chọn nếu ghi lỗi), cảnh báo vàng cho `blocked` và `ungrounded_numbers`, thông báo tiếng Việt cho 429/502/503, lời nhắc "họ tên được thay bằng mã tạm" và "trợ lý có thể sai". Câu trả lời hiển thị chữ thuần (không dựng Markdown), không thêm thư viện.
- Kiểm bằng `eslint`, `tsc` và script Chrome tạm ngoài repo (D-069 vẫn hoãn test tự động), có chạy với máy chủ demo tạm dùng LLM giả theo luật cùng database seed thật (xem PROGRESS).

**D-094 · Thêm nhà cung cấp Gemini** (Khi làm; theo yêu cầu của bạn sau khi chốt D-085, Claude vẫn là nhà cung cấp API mặc định trong tài liệu)
- `GeminiProvider` (`providers/gemini_provider.py`, SDK chính thức `google-genai` 2.30.0, `LLM_PROVIDER=gemini`): đổi tin nhắn sang `Content`/`Part` của Gemini, lệnh gọi hàm là `function_call`, các kết quả của một lượt gom vào một Content, schema hàm đi qua `parameters_json_schema` (bỏ `additionalProperties`). Tắt gọi hàm tự động của SDK: chỉ mã của ta chạy hàm, qua `authorize()`.
- **Giữ nguyên lượt trả lời của mô hình**: các mô hình Gemini mới gắn "chữ ký suy nghĩ" vào phần gọi hàm và đòi nhận lại đúng ở lượt sau. `Message` và `LLMReply` thêm trường `raw` không bắt buộc (không tham gia so sánh) để provider gửi lại nguyên `Content`; mã chung không đọc trường này, các provider khác bỏ qua.
- **Mô hình mặc định `gemini-flash-latest`** (bí danh Flash mới nhất, `LLM_MODEL` đổi được): tên cụ thể bị gỡ nhanh, `gemini-2.5-flash` đã trả 404 "không còn cho tài khoản mới" ngày 2026-10-13. Đổi lại bí danh có thể tự đổi hành vi khi Google nâng phiên bản; muốn cố định thì đặt `LLM_MODEL`. Danh sách mô hình có sẵn của khoá đã đọc bằng `client.models.list()`.
- **Gói miễn phí**: khoá bạn dán dùng được với Gemini Developer API nhưng (1) **dòng Pro có hạn mức 0** (`gemini-pro-latest` trả 429 `limit: 0`), nên chưa dùng được "Gemini Pro"; (2) mô hình Flash giới hạn **5 yêu cầu mỗi phút**; (3) đôi khi 503 "high demand". Provider thử lại lỗi 500, 502, 503, 504 (4 lần) và, khi gặp 429 theo phút có `RetryInfo` ("retry in 44s"), chờ đúng thời gian đó (tối đa 75 giây, 3 lần) rồi thử lại; hết hạn mức theo ngày hoặc không có thời gian chờ thì báo lỗi ngay (502 cho người dùng, mã lỗi trong thông điệp). Hệ quả: một câu hỏi qua API có thể mất tới vài chục giây khi chạm hạn mức miễn phí; gói trả phí không bị.
- Riêng tư: Google có thể dùng dữ liệu gửi lên gói miễn phí để cải thiện sản phẩm (chưa xác nhận từ điều khoản chính thức). Dự án chỉ dùng dữ liệu giả lập và đã thay họ tên bằng mã tạm (D-086), nên chấp nhận được cho bản demo; với dữ liệu thật cần gói trả phí hoặc Ollama.
- Khoá API chỉ nằm trong `.env` (đã `.gitignore`), không có trong mã, tài liệu hay nhật ký; thông điệp lỗi không chứa khoá (có test). Khoá được dán vào cuộc trò chuyện nên **nên tạo lại khoá mới** sau khi thử xong.
- Kết quả thử: khoá hợp lệ với Gemini Developer API (không phải Vertex AI). Gói miễn phí: Flash cho **20 yêu cầu mỗi ngày mỗi mô hình** (và 5 yêu cầu mỗi phút), Pro cho 0; hạn mức tính riêng từng mô hình nên đổi `LLM_MODEL` sang mô hình khác thì dùng tiếp được trong ngày. Đã đặt `.env` cục bộ `LLM_MODEL=gemini-3.1-flash-lite` (chạy ổn, ít bị 503) để bạn thử trên giao diện; chạm 20 yêu cầu thì đổi mô hình hoặc chờ sang ngày. `gemini-3.5-flash`, `gemini-3.6-flash` lúc thử hay trả 503 "high demand". Câu hỏi qua Docker mất 3,4 giây. Bản Markdown trong câu trả lời (`**`) đã được prompt cấm (UI hiển thị chữ thuần).

**D-095 · Giao diện v2: hệ thiết kế xanh ngọc, thanh bên, chế độ tối, responsive** (Đã duyệt: phong cách hiện đại sáng xanh ngọc, thanh bên trái, thiết kế lại toàn bộ màn hình, có responsive và chế độ tối; chỉ đổi diện mạo, không đổi hành vi, API hay back-end)
- **Một nơi duy nhất cho diện mạo: `frontend/src/index.css`.** `@theme` của Tailwind v4 thêm thang `brand` (xanh ngọc, `brand-700` cho nút và liên kết) và các token ngữ nghĩa `page`, `surface`, `link`, `tint`, `sidebar`, `--shadow-card`, `--shadow-pop`. Các lớp dùng chung (`.card`, `.btn-primary/-secondary/-ghost`, `.input`, `.label`, `.link`, `.badge-*`, `.data-table`, `.skeleton`) thay các chuỗi class lặp. Biến màu biểu đồ `--chart-*` nằm ngoài `@theme` để đổi theo chế độ; `components/charts/theme.ts` đọc chúng. Mã hex gán cứng trong biểu đồ và `lib/labels.ts` đã bỏ. Nhãn chữ và số trên mọi cột biểu đồ giữ nguyên, không chỉ dựa vào màu.
- **Chế độ tối bằng cách đảo thang `slate`** trong khối `.dark` (50 là nền tối nhất, 900 là chữ sáng) và đặt lại `red`/`amber`/`green`/`brand`, nên các `text-slate-*`/`bg-slate-*`/`border-slate-*` có sẵn tự đúng ở cả hai chế độ mà không thêm `dark:` từng chỗ. `bg-white` đổi thành `bg-surface`; `text-white` chỉ còn dùng trên nền đậm (nút, thanh bên, vùng gradient). Hệ quả cần nhớ: **không dùng `slate-900` làm nền và không đặt `text-white` trên nền nhạt**, vì sẽ đảo sai ở chế độ tối. `--color-slate-500` được làm sẫm hơn mặc định để chữ phụ đạt tương phản AA ở chế độ sáng.
- **`ThemeProvider`** (`src/theme/`): `light` | `dark` | `system`, lưu `thda.theme` trong `localStorage`, theo hệ điều hành khi chọn `system` (nghe `prefers-color-scheme`). Một đoạn script nhỏ trong `index.html` đặt class `dark` trước khi vẽ nên không nháy trắng khi tải lại.
- **Phông chữ Inter Variable tự host** qua `@fontsource-variable/inter` (phụ thuộc mới duy nhất; có bộ ký tự tiếng Việt, không gọi CDN nên chạy offline và không gửi gì ra ngoài). Image frontend phải dựng lại (`docker compose up -d --build --renew-anon-volumes frontend`). Chỉ tệp `woff2` của bộ ký tự nào trình duyệt cần mới được tải; trình duyệt dùng phông hệ thống nếu tải lỗi.
- **Biểu tượng và logo tự vẽ, không thêm thư viện:** `components/Icon.tsx` (khoảng 35 biểu tượng SVG nét 24px dùng `currentColor`), `Logo.tsx`, `public/favicon.svg`.
- **Khung:** `AppLayout` + `components/layout/` (`Sidebar`, `Topbar`, `UserMenu`, `ThemeToggle`, `useBreadcrumbs`). Thanh bên nền `brand-950` ở cả hai chế độ, chia nhóm Tổng quan / Lớp của tôi / Khối / Công cụ / Quản trị theo vai trò (giữ đúng phân quyền cũ: BGH có "Khối", Admin có "Văn bản quy định" và không có "Trợ lý AI"). Thu gọn được, nhớ trong `localStorage` (`thda.sidebar`). Dưới 1024px thành **ngăn kéo**: `inert` khi đóng (không Tab vào được), khoá cuộn nền khi mở, đóng bằng Esc / bấm lớp phủ / bấm một mục. Giữ "Bỏ qua điều hướng", `aria-label`, `aria-current`.
- **Bài học kỹ thuật đã gặp (để khỏi lặp lại):** (1) `@apply` một lớp tuỳ biến (như `.btn`) không chạy trong Tailwind v4, phải khai bằng `@utility`; (2) phần tử `sr-only` (`position: absolute`) trong bảng nằm ngoài vùng cuộn làm cả trang tràn ngang, nên `.overflow-x-auto` đặt `position: relative`; (3) `Legend` của Recharts tự nở theo chiều rộng và làm tràn trên điện thoại, nên legend được thay bằng chú giải trung tính của dự án; (4) `figure` chứa biểu đồ cần `min-w-0 overflow-hidden` để cột lưới co được.
- **Cách kiểm (D-069 vẫn hoãn test tự động):** `eslint`, `tsc -b`, `vite build`, `make lint`, `make test` (back-end không đổi: 1.103 test qua) và các script `playwright-core` tạm ngoài repo chạy trên Chrome thật: ma trận 82 ảnh (4 vai trò × sáng/tối × 1366/820/390 px) không tràn ngang và không lỗi console; phép đo tương phản tự động chữ/nền ở mọi trang, cả hai chế độ (bỏ vùng nền gradient) đều đạt WCAG AA; kiểm hành vi (nhớ chế độ và thanh bên sau tải lại, theo hệ điều hành, menu người dùng, đăng xuất, ngăn kéo, phân quyền thanh bên); chạy lại luồng văn bản quy định, Trợ lý AI (có máy chủ demo tạm dùng LLM giả) và nhập tệp. Tôi xem từng ảnh để soát lỗi bằng mắt.
- **Chưa kiểm / hạn chế đã biết:** chưa thử trình duyệt ngoài Chrome (màu biểu đồ qua biến CSS trong thuộc tính SVG cần trình duyệt hiện đại); chưa thử với trình đọc màn hình; trục của biểu đồ có nhãn dài còn chồng nhau trên điện thoại; bảng "Học sinh cần hỗ trợ" cuộn ngang trên điện thoại (chủ ý, giữ đủ cột); các phép đo tương phản bỏ qua chữ trên nền gradient.

**D-096 · Nền tảng quản trị: `AdminUser`, khoá tài khoản, nhật ký** (Đã duyệt: làm chức năng Admin gồm tài khoản, năm học/lớp/GVCN, phân công, nhập danh sách học sinh; chưa làm danh mục môn học, chỉnh ngưỡng Thông tư 22 qua giao diện, nhiều năm học)
- `AdminUser` (dependency: 401 rồi 403, chạy trước khi đọc tệp hay kiểm hình dạng yêu cầu) chuyển từ `rag/router.py` sang `auth/deps.py` và dùng cho mọi `/admin/*`; `authorize_admin` ở `core/authorize.py` giữ nguyên (D-077). Admin vẫn **không xem dữ liệu học sinh** (D-039): màn hình quản trị chỉ có số đếm, `authorize()` không mở rộng.
- **Khoá thay cho xoá**: `users.is_active` (migration thứ 10, mặc định `true`). `authenticate` từ chối tài khoản bị khoá như sai mật khẩu (cùng thông điệp 401, không tiết lộ tài khoản có tồn tại), `get_current_user` trả 401 cho token của tài khoản bị khoá (người dùng được nạp lại mỗi request, D-041), nên khoá có hiệu lực ngay. Không xoá vì điểm, nhật ký, phân công còn tham chiếu tới người dùng.
- **Nhật ký quản trị** vào `audit_logs` (`record_access`, `class_id` nếu có): `create_user`, `update_user`, `reset_user_password`, `change_password`, `update_school_year`, `create_class`, `update_class`, `delete_class`, `set_assignment`, `remove_assignment`, `remove_class_student` (nhập danh sách dùng `import_confirm` có sẵn). `details` chỉ có id và tên trường đổi, **không bao giờ** có mật khẩu, họ tên hay ngày sinh. Mọi giá trị ngắn hơn hoặc bằng 20 ký tự nên không phải đổi độ dài cột; migration thêm cả giá trị `roster` vào CHECK `kind` của `import_jobs` và `import_mappings`, có `downgrade` (xoá dòng dùng giá trị mới trước khi đặt lại CHECK cũ).

**D-097 · Tài khoản và mật khẩu** (Đã duyệt: khoá không xoá; mật khẩu sinh ngẫu nhiên hiện một lần kèm trang tự đổi)
- `GET/POST /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset-password`, và `POST /auth/change-password` cho mọi vai trò (chỉ đụng tài khoản của chính người gọi, nên là ngoại lệ nguyên tắc 4 như `/me/assignments`, D-042). Email chuẩn hoá chữ thường và duy nhất không phân biệt hoa thường (chỉ mục sẵn có; kiểm trước cho thông điệp rõ, và bắt `IntegrityError` cho trường hợp hai yêu cầu cùng lúc). Kiểm hình dạng email bằng mẫu đơn giản, không thêm thư viện `email-validator`.
- **Mật khẩu tạm**: `generate_temporary_password()` (`core/security.py`, `secrets`, 12 ký tự, bỏ ký tự dễ nhầm, luôn có chữ hoa, thường, số). Bản rõ **chỉ nằm trong phản hồi** của tạo mới hoặc đặt lại, hiện một lần trên giao diện; trong DB chỉ có bản băm bcrypt, không có trong `audit_logs` (có test quét toàn bộ `details`). Đổi mật khẩu: tối thiểu 8 ký tự, tối đa 72 byte (giới hạn bcrypt), phải khác mật khẩu cũ, sai mật khẩu hiện tại thì 400.
- **Quy tắc**: Admin không tự khoá hay hạ quyền chính mình (409). Nhờ đó luôn còn ít nhất một Admin hoạt động (người thực hiện là một Admin khác tài khoản bị đổi), nên không có kiểm "Admin cuối cùng" riêng, vì sẽ là mã không bao giờ chạy tới. Giáo viên còn chủ nhiệm hoặc có phân công thì chưa đổi sang vai trò khác `teacher` được (409, hướng dẫn gỡ trước). Khoá giáo viên còn phân công thì được (giao diện cảnh báo).
- **Hạn chế đã biết**: token đã cấp vẫn dùng được đến khi hết hạn (`JWT_EXPIRE_MINUTES`, mặc định 120 phút) sau khi đổi hoặc đặt lại mật khẩu; chỉ khoá tài khoản mới có hiệu lực ngay. Không có "buộc đổi mật khẩu ở lần đăng nhập đầu" và không gửi email.

**D-098 · Một năm học duy nhất; lớp và GVCN** (Đã duyệt)
- Code không có khái niệm "năm học hiện hành": so sánh khối, phạm vi Trợ lý AI, cảnh báo, trang chủ đều lấy mọi lớp trong DB; DESIGN cũng ghi MVP là một năm học. Nên `PUT /admin/school-year` chỉ **tạo năm đầu tiên hoặc sửa năm duy nhất**, không tạo năm thứ hai (làm nhiều năm cần cờ "năm hiện hành" và lọc ở mọi giai đoạn trước). Đổi ngày bị từ chối nếu có điểm danh nằm ngoài khoảng mới (`school_year_range` dùng ngày này).
- `GET /admin/school` (năm học và lớp kèm sĩ số, số môn đã phân công, tên GVCN; **không có tên hay mã học sinh**), `GET /admin/teachers` (giáo viên đang hoạt động), `POST /admin/classes`, `PATCH /admin/classes/{id}`, `DELETE /admin/classes/{id}`. Tên lớp phải bắt đầu bằng số khối và không trùng (không phân biệt hoa thường); khối không đổi sau khi tạo. Mỗi giáo viên chỉ chủ nhiệm một lớp (ràng buộc sẵn có, kiểm trước để báo lớp nào), GVCN phải là giáo viên đang hoạt động. Chỉ xoá lớp **không còn học sinh và phân công**; bản xem trước nhập tệp chưa xác nhận của lớp đó được xoá cùng. Đổi GVCN có hiệu lực ngay vì quyền đọc từ DB mỗi yêu cầu (test: người cũ nhận 403, người mới 200).

**D-099 · Phân công giảng dạy và gỡ học sinh** (Đã duyệt)
- Thay cho `POST /admin/assignments` của DESIGN mục 7 (mỗi lần là một cặp lớp-môn): `GET /admin/classes/{id}/assignments` (mọi môn trong danh mục kèm giáo viên hoặc trống), `PUT .../{subject_id}` (gán hoặc **đổi** giáo viên, đúng khoá duy nhất lớp-môn), `DELETE .../{subject_id}`, `POST .../copy` (sao chép các môn **còn trống** từ lớp cùng khối, không đè, bỏ qua giáo viên đã bị khoá). Môn của lớp chính là các dòng phân công (không có bảng riêng, đã ghi ở `classes/models.py`) nên lớp mới chưa phân công thì chưa ai nhập được điểm.
- **Gỡ phân công bị từ chối khi lớp đã có điểm của môn đó** (điểm sẽ mồ côi, không ai nhập tiếp được); khi đó chỉ đổi giáo viên. Giáo viên được gán phải đang hoạt động và là `teacher`.
- `POST /admin/classes/{id}/students/remove {student_code}`: gỡ **theo mã Admin gõ vào** (giữ D-039, không có danh sách học sinh cho Admin), chỉ khi em chưa có điểm, điểm danh, rèn luyện, đăng ký thi hay cảnh báo; thông điệp từ chối không nêu nội dung dữ liệu. Em không còn ở lớp nào thì xoá luôn hồ sơ học sinh. `details` của nhật ký chỉ có `student_id` nội bộ, không có mã hay tên.

**D-100 · Nhập danh sách học sinh từ tệp (Admin)** (Đã duyệt: mã đã có thì gắn vào lớp và cập nhật thông tin)
- Thêm `ImportKind.ROSTER` vào luồng nhập có sẵn (`POST /classes/{id}/import/roster`, `POST /imports/{job_id}/confirm`, cùng bộ đọc tệp, ánh xạ cột, xem trước, mẫu ánh xạ). Phần dùng chung rơi lặng lẽ về loại điểm cho kind lạ nên mỗi chỗ đều có nhánh `ROSTER` tường minh: `columns.fields_for`, `service._validate`, `writer.write_job`, `router.import_preview`, `service.confirm_job`. Logic riêng ở `imports/roster.py` (kiểm dòng thuần như `validation.py`, tra lớp hiện tại của các mã, ghi).
- **Quyền**: `kind=roster` đi qua `authorize_admin` thay cho `authorize_write` ở cả xem trước và xác nhận (GVBM, GVCN, BGH đều 403, kể cả GVCN của chính lớp đó); kiểm quyền trước khi đọc tệp, rồi mới tới "lớp có thật không" (404). Xác nhận còn kiểm chủ job và kiểm lại vai trò Admin lúc xác nhận (Admin bị hạ quyền sau khi xem trước thì 403). Các loại điểm, điểm danh, rèn luyện vẫn không cho Admin ghi (D-058).
- **Quy tắc dòng**: mã (chuẩn hoá `strip().upper()`, tối đa 20 ký tự, chỉ chữ, số, `.`, `-`, `_`) và họ tên (tối đa 100) bắt buộc; ngày sinh qua `parse_date`, không ở tương lai, ngoài 13 đến 22 tuổi chỉ **cảnh báo**; số điện thoại qua `parse_phone` mới (10 hoặc 11 chữ số bắt đầu bằng 0, nhận `+84`, dấu cách, dấu chấm; Excel làm mất số 0 đầu thì **bù số 0 và cảnh báo**); mã trùng trong tệp là lỗi. Mã đang ở **lớp khác** là lỗi (một học sinh một lớp trong một năm học); lúc xác nhận kiểm lại (`RosterConflict` thành 409) vì hai bản xem trước cho hai lớp cùng một mã đều hợp lệ lúc xem. Ghi: tra học sinh theo mã không phân biệt hoa thường (DB chỉ có ràng buộc duy nhất phân biệt hoa thường, tránh tạo bản sao), cập nhật họ tên và các trường có giá trị trong tệp (ô trống **không xoá** thông tin cũ), tạo hồ sơ nếu chưa có, gắn vào lớp (`ON CONFLICT DO NOTHING`). Kết quả: "tạo" là số học sinh được thêm vào lớp, "cập nhật" là số học sinh đã ở lớp.
- **Riêng tư (khác D-059)**: job lưu họ tên, ngày sinh, số điện thoại trong tối đa 24 giờ để xác nhận mà không phải tải lại tệp; `rows` được **xoá ngay khi xác nhận**, job chưa xác nhận bị dọn khi hết hạn (như các loại cũ, lúc có xem trước tiếp theo). Xem trước **không trả giá trị cũ** (`existing` luôn trống) và họ tên hiện là họ tên trong tệp; chỉ báo "mới", "cập nhật" hay lỗi, nên Admin không đọc được dữ liệu học sinh có sẵn. Chấp nhận để lộ một điều: mã nào đã có trong lớp (Admin vừa gõ mã đó). Không gọi `on_data_changed` (chưa có điểm để cảnh báo sớm tính lại).
- Tệp mẫu giả `data/samples/danh-sach-hoc-sinh-11a9.xlsx` (30 học sinh, mã `HS1109001` đến `HS1109030`, tên và số điện thoại từ `data/seed/people.py`), có test nhập vào một lớp 11A9 mới.

**D-101 · Giao diện quản trị** (Khi làm)
- Các trang mới theo hệ thiết kế D-095: `/admin/users`, `/admin/school`, `/admin/classes/:classId`, `/account/password` (mọi vai trò, mở từ menu người dùng), nạp theo yêu cầu (lazy). `AdminGate` hiện lời báo nếu không phải Admin (back-end vẫn kiểm lại ở mọi yêu cầu). Mục "Quản trị" ở thanh bên: Tài khoản, Năm học & lớp, Văn bản quy định; trang chủ Admin thay lời "sẽ có ở bản sau" bằng ba lối tắt.
- Xác nhận ngay trên dòng cho khoá, mở khoá, đặt lại mật khẩu, xoá lớp, gỡ học sinh (như `RegulationTable`); mật khẩu tạm hiện trong khung nổi bật có nút sao chép, không lưu trong trạng thái sau khi bấm "Đã ghi lại" và không bao giờ vào `localStorage`. Ô chọn GVCN tắt giáo viên đang chủ nhiệm lớp khác (ghi rõ lớp nào). `ImportWizard` dùng lại cho danh sách học sinh (thêm `home`, `onConfirmed`, câu chữ riêng); `apiPut`, `apiDelete` thêm vào client.
- Kiểm: `eslint`, `tsc -b`, `vite build`, `make lint`, `make test` (1.247 test qua, 1 bỏ qua; thêm 144), và script `playwright-core` tạm ngoài repo (D-069 vẫn hoãn test tự động) trên Chrome thật: tạo tài khoản, đăng nhập bằng mật khẩu tạm, đổi mật khẩu (kể cả mật khẩu hiện tại sai), email trùng, khoá (phiên đang mở bị đăng xuất, không đăng nhập lại được) rồi mở khoá và đặt lại mật khẩu, tạo lớp 11A9 với GVCN mới, phân công và sao chép, nhập tệp mẫu 30 học sinh rồi GVCN mới thấy lớp, gỡ học sinh (có dữ liệu thì từ chối và không lộ tên), BGH/GVCN/GVBM mở thẳng 3 trang quản trị chỉ thấy lời báo; ảnh sáng/tối × 1366/390 px không tràn ngang, không lỗi console; tương phản đạt ở mọi trang quản trị cả hai chế độ.
- **Chưa kiểm / hạn chế**: chưa thử trình duyệt ngoài Chrome; bảng tài khoản trên điện thoại cuộn ngang; danh sách tài khoản tải hết một lần và lọc ở trình duyệt (đủ cho vài trăm tài khoản, chưa phân trang); sao chép vào bộ nhớ tạm cần HTTPS hoặc `localhost` (nếu không có thì có lời nhắc chép tay).

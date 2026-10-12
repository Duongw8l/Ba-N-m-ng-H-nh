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

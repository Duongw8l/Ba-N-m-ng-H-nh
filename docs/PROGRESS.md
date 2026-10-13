# Tiến độ

Cập nhật lần cuối: 2026-10-13 (Giai đoạn 7). Tên và thứ tự giai đoạn lấy từ bộ prompt [PROMPTS.md](PROMPTS.md).

## Bảng 12 giai đoạn

| Giai đoạn | Nội dung | Trạng thái |
| --- | --- | --- |
| 0 | Khởi tạo dự án | Xong (còn chờ kiểm: CI trên GitHub, cần đẩy lên GitHub, xem bên dưới) |
| 1 | Cơ sở dữ liệu + dữ liệu giả lập | Xong, đã commit `cab087d` (còn chờ kiểm: CI trên GitHub, xem bên dưới) |
| 2 | Xác thực và phân quyền | Xong, đã commit `43900ac` (chưa kiểm giao diện trên trình duyệt, CI trên GitHub; xem bên dưới) |
| 3 | Analytics theo Thông tư 22 | Xong, đã commit `15c8d97` (quy tắc lấy từ nguồn thứ cấp, **cần đối chiếu văn bản gốc**; xem bên dưới) |
| 4 | Import Excel/CSV | Xong, đã commit `667bf88` (giao diện đã chạy thử trên Chrome ở Giai đoạn 5; chưa thử với sổ điểm thật; xem bên dưới) |
| 5 | Dashboard và giao diện chính | Xong, đã commit `36b2882` (hoãn Vitest/Playwright theo lựa chọn của bạn; xem bên dưới) |
| 6 | Cảnh báo sớm (luật + ML) | Xong, đã commit `f5a021f` (dữ liệu huấn luyện là giả lập; xem bên dưới) |
| 7 | RAG văn bản quy định | Xong, chưa commit (ngưỡng tìm kiếm chưa tách chắc hai nhóm câu hỏi, Hit@4 6/8 trên bộ kiểm; chưa thử với văn bản thật; xem bên dưới) |
| 8 | Trợ lý AI gọi hàm | Chưa làm |
| 9 | Nhận xét và báo cáo | Chưa làm |
| 10 | Đánh giá AI | Chưa làm |
| 11 | Bảo mật, triển khai, demo | Chưa làm |

## Giai đoạn 0: Khởi tạo dự án

### Đã làm

- Cấu trúc thư mục đúng theo CLAUDE.md; thư mục chưa dùng có `.gitkeep`.
- Back-end FastAPI: `GET /api/v1/health` trả `{"status":"ok","db":true|false}`; cấu hình bằng Pydantic Settings; SQLAlchemy 2.0 + psycopg 3; Alembic đã khởi tạo (chưa có migration; DB chỉ có bảng `alembic_version` do Alembic tự tạo, chưa có bảng nghiệp vụ); ruff, pytest, 1 test cho `/health`.
- Front-end React + Vite + TypeScript, Tailwind v4, React Router, TanStack Query: trang chủ hiển thị trạng thái health bằng tiếng Việt, trang 404; ESLint và `tsc`.
- Hạ tầng: `docker-compose.yml` (db `pgvector/pgvector:pg16`, backend, frontend), `.env.example`, `.gitignore`, `.gitattributes`, Makefile, CI GitHub Actions.
- Tài liệu: README, PROGRESS (file này), DECISIONS.

### Chưa làm (thuộc các giai đoạn sau)

- Bảng nghiệp vụ, migration đầu tiên, bật extension `vector` (đã làm ở Giai đoạn 1); công thức Thông tư 22; gọi LLM; xác thực.
- Vitest/Playwright, image triển khai (nginx, không reload), tắt Swagger trên môi trường thật (đã có công tắc `APP_ENV=production`).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `ruff check`, `ruff format --check`, `pytest` (trên máy và trong container backend) | Đã chạy, qua |
| `eslint`, `tsc -b`, `vite build` (front-end) | Đã chạy, qua |
| `docker compose up -d --build --renew-anon-volumes --wait` (đúng lệnh của `make up`): build 3 image, 3 dịch vụ `healthy` | Đã chạy, qua |
| Trang chủ trong trình duyệt: "Máy chủ: ok" và "Cơ sở dữ liệu: ok" (`/health` trả `{"status":"ok","db":true}`) | Đã kiểm, đúng |
| Tắt rồi bật lại container db: trang chủ báo "lỗi" rồi tự phục hồi; backend không bị khởi động lại, vẫn `healthy` | Đã kiểm, đúng |
| `alembic upgrade head` trên DB thật, từ máy host qua `127.0.0.1:5432` | Đã chạy, qua |
| Tự nạp lại (hot reload) của backend và frontend trên bind mount Windows | Đã kiểm, đúng |
| Chạy chính `make` (GNU make 4.4.1, shell cmd.exe): `up`, `down`, `db`, `migrate`, `seed`, `eval`, `install`, `lint`, `test`, `dev-be`, `dev-fe` | Đã chạy cả 11 mục tiêu, qua (phát hiện và sửa 1 lỗi font của `seed`/`eval`, xem D-020) |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub. Cú pháp YAML hợp lệ |

### Cách kiểm tra

1. `cp .env.example .env` (PowerShell: `Copy-Item .env.example .env`).
2. `make up`: cả 3 dịch vụ lên và khoẻ (`docker compose ps`).
3. Mở <http://localhost:5173> (từ Giai đoạn 2 trang chủ cần đăng nhập và hiện trạng thái này ở <http://localhost:5173/login>): "Máy chủ: ok", "Cơ sở dữ liệu: ok". Hoặc `curl http://localhost:8000/api/v1/health` trả `{"status":"ok","db":true}`.
4. `docker compose stop db`, chờ tối đa 15 giây (trang tự làm mới khi tab đang hiển thị): "Cơ sở dữ liệu: lỗi", còn backend vẫn `healthy`. `docker compose start db`: trở lại "ok".
5. Ngoài Docker, trong venv đã kích hoạt: `make install`, rồi `make lint` và `make test` đều qua.
6. `make db` rồi `make migrate`: chạy không lỗi (ở Giai đoạn 0 chỉ tạo bảng `alembic_version` rỗng; từ Giai đoạn 1 tạo đủ bảng nghiệp vụ, xem bên dưới).
7. `make seed` và `make eval`: in "chưa triển khai", thoát mã 0 (từ Giai đoạn 1 `make seed` chạy thật; `make eval` vẫn như vậy).
8. `make down`.

## Giai đoạn 1: Cơ sở dữ liệu và dữ liệu giả lập

### Đã làm

- **Schema** (D-024, D-025, D-035): model SQLAlchemy 2.0 theo module (`Base` ở `core/base.py`) và 3 migration Alembic, đều có `downgrade`. Đúng 15 bảng của DESIGN mục 5 cộng `settings`; khoá ngoại, `CHECK` (điểm 0..10 `NUMERIC(4,2)`, học kỳ 1/2, `kind` tx/gk/ck, mã liệt kê...), ràng buộc duy nhất và index cho truy vấn thường dùng. Extension `vector` bật trong migration; cột `regulation_chunks.embedding` là `vector(EMBEDDING_DIM)` (mặc định 1024, D-029).
- **`settings`** (D-027): 12 khoá hệ số và ngưỡng nạp trong migration (không phải trong seed). Chỉ lưu giá trị, không có công thức.
- **View `v_subject_average`** (D-026): khung gom dữ liệu (số lần và tổng điểm thường xuyên, điểm giữa kỳ, cuối kỳ, nhận xét), cố ý không có hệ số và công thức; công thức Thông tư 22 để Giai đoạn 3 trong `analytics/`.
- **Dữ liệu giả lập** (`data/seed/`, `make seed`; D-030 đến D-032, D-036): năm học 2026-2027 đủ hai học kỳ, 9 lớp × 40 = 360 học sinh, 17 môn theo GDPT 2018, 60 tài khoản (admin, 2 BGH, 51 GVBM, 9 GVCN trong đó 3 người kiêm GVBM), 34.080 đầu điểm, 63.000 dòng điểm danh, rèn luyện HK1 và HK2, đăng ký thi khối 12. Tham số `--seed`, `--classes-per-grade`, `--class-size`; cùng tham số cho cùng dữ liệu; chạy lại không lỗi; từ chối chạy khi `APP_ENV=production`. Phân bố: 18 em nghỉ 30-50 buổi (5%), 29 em có môn dưới 3,5 (8%), tương quan nghỉ nhiều với điểm thấp; nhân vật demo `HS1102001` (nghỉ 38 buổi) và `HS1102002` (Toán dưới 3,5) ở 11A2; học sinh biên đúng 44/45/46 buổi nghỉ và đúng 3,4/3,5/5,0.
- **Hàm dùng lại cho các giai đoạn sau:** `core/security.py` (`hash_password`, `verify_password`, bcrypt; D-033), `core/labels.py` (nhãn tiếng Việt), `analytics/thresholds.py` (`required_regular_count`; D-037).
- **Test** (D-034): 94 test, trong đó 47 test cần PostgreSQL thật có pgvector (migration lên/xuống, model khớp migration, ràng buộc chặn dữ liệu sai, seed). Test `/health` cũ vẫn chạy. `make test` dừng với thông báo "Chạy make db trước" khi chưa có DB (sau khoảng 7 giây).
- **Hạ tầng và tài liệu:** `make seed`; `make lint` bao cả `data/`; CI có service PostgreSQL; `.env.example` thêm `EMBEDDING_DIM`, `TEST_DATABASE_URL`; README thêm mục dữ liệu giả lập và tài khoản dev; D-024 đến D-038 trong DECISIONS.

### Chưa làm (thuộc các giai đoạn sau)

- Công thức Thông tư 22 (ĐTB môn, mức học tập, điều kiện lên lớp) — Giai đoạn 3. Đăng nhập, `authorize`, `pseudonymize` — Giai đoạn 2. Import Excel/CSV, kịch bản "nhập file điểm danh tháng mới" — Giai đoạn 4. Dữ liệu năm trước cho ML — Giai đoạn 6. Nạp văn bản quy định và vector — Giai đoạn 7.
- Cột DESIGN còn thiếu (`ai_logs` chưa có thời điểm, `reports` chưa có `created_at`/`approved_at`): chưa thêm, xin bằng migration ở Giai đoạn 8, 9 (D-035).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic downgrade base` rồi `make migrate` trên DB `classroom`: chỉ còn `alembic_version` sau khi xuống; sau khi lên có 16 bảng + `alembic_version`, view `v_subject_average`, extension `vector` 0.8.7, 12 khoá `settings`, cột `vector(1024)` | Đã chạy, đúng |
| `alembic check` (model so với migration) trên máy và trong container backend | Đã chạy: "No new upgrade operations detected" |
| `make seed` hai lần liên tiếp: bảng tóm tắt giống nhau, dữ liệu giống nhau từng dòng (băm các bảng lớn, bỏ `password_hash`) | Đã chạy, đúng. Mỗi lần khoảng 9 giây |
| `make lint` (ruff trên `backend/` và `data/`, eslint, tsc) và `make test` (94 test) | Đã chạy, qua |
| Tắt container db rồi `make test`: dừng với thông báo "Chạy make db trước" | Đã chạy, đúng (7 giây) |
| `make up`: build lại image backend (thêm bcrypt, pgvector), 3 dịch vụ `healthy`; `/api/v1/health` trả `{"status":"ok","db":true}` qua cổng 8000 và qua proxy Vite cổng 5173; `alembic current` trong container là head | Đã chạy, đúng. Trang chủ trong trình duyệt ("Máy chủ: ok", "Cơ sở dữ liệu: ok") chưa mở lại; tôi chỉ kiểm bằng gọi `/health` qua proxy |
| CI GitHub Actions với service PostgreSQL | **Chưa kiểm**: cần đẩy lên GitHub. YAML hợp lệ; đường đi `TEST_DATABASE_URL` tường minh đã chạy thử trên máy |
| Số tiết và tổ hợp môn (D-031), quy chế thi 4 môn (D-036) | **Cần bạn đối chiếu** với Thông tư 32/2018, 13/2022 và quy chế thi tốt nghiệp; nguồn tôi tra là thứ cấp |

### Cách kiểm tra

1. `cp .env.example .env` (nếu chưa có), kích hoạt venv (`backend\.venv\Scripts\Activate.ps1`), `make install`.
2. `make db`, `make migrate`. Soi: `docker compose exec db psql -U classroom -d classroom -c "\dt"` (16 bảng + `alembic_version`), `-c "\dv"` (view), `-c "select * from settings"` (12 khoá).
3. `make seed`: xem bảng tóm tắt (360 học sinh, 18 nghỉ từ 30 buổi, 29 có đầu điểm dưới 3,5, đủ học sinh biên). Chạy lần hai cho kết quả y hệt.
4. `make lint`, `make test` (cần DB đang chạy). Thử `docker compose stop db` rồi `make test` để thấy thông báo thiếu DB.
5. Thử đăng nhập bằng tài khoản mẫu ở Giai đoạn 2 (bảng tài khoản dev trong README).
6. `make up`, mở <http://localhost:5173/login>: vẫn "Máy chủ: ok" và "Cơ sở dữ liệu: ok".

## Giai đoạn 2: Xác thực và phân quyền

### Đã làm

- **Đăng nhập** (D-041): `POST /api/v1/auth/login` trả JWT (PyJWT, HS256, 120 phút, cấu hình bằng `JWT_EXPIRE_MINUTES`); mật khẩu kiểm bằng bcrypt của Giai đoạn 1; `get_current_user` nạp lại người dùng từ DB mỗi request (vai trò không nằm trong token). `JWT_SECRET` phải từ 32 ký tự.
- **`authorize()`** (D-039, D-040): `app/core/authorize.py`, một hàm cho mọi endpoint (và về sau mọi tool của LLM). Admin không xem dữ liệu học sinh; BGH toàn trường và thấy phụ huynh; GVCN lớp mình chủ nhiệm, mọi môn, thấy phụ huynh; GVBM đúng cặp lớp-môn, không thấy phụ huynh; quyền cộng dồn tính riêng từng lớp. Sai thì 403 với thông điệp chung.
- **Endpoint** (D-044): `GET /me/assignments` (lớp chủ nhiệm, lớp-môn được phân công, các khối của BGH) và `GET /classes/{id}/students` (GVBM nhận danh sách không có khoá `guardian_*`).
- **Nhật ký truy cập** (D-043): bảng `audit_logs` (migration thứ 4); mỗi lần danh sách lớp trả 200 ghi một dòng trước khi trả dữ liệu.
- **Front-end** (D-045): trang `/login` (kèm trạng thái máy chủ và DB), route bảo vệ, token ở `sessionStorage`, đăng xuất, tự về `/login` khi hết phiên, trang chủ khác nhau theo vai trò.
- **Test** (D-046): 161 test (thêm 67): ma trận 4 vai trò × đúng/sai lớp, đúng/sai môn, có/không xem phụ huynh, cộng dồn, lớp không tồn tại; 401 cho thiếu/sai/hết hạn token và tài khoản đã xoá; đổi vai trò có hiệu lực ngay; đăng nhập bằng bcrypt thật; token (hết hạn, sai khoá, bị sửa, `alg: none`, thiếu claim); nhật ký chỉ ghi khi 200. Đã thử cố ý làm hỏng `authorize()` để chắc test bắt được lỗi.

### Chưa làm (thuộc các giai đoạn sau)

- Giới hạn số lần đăng nhập sai, đổi mật khẩu, thu hồi token, nhật ký các lần bị từ chối: Giai đoạn 11 (D-041, D-043).
- `pseudonymize()` (Giai đoạn 8), kết quả tổng hợp trong danh sách lớp (Giai đoạn 3), màn Hồ sơ học sinh và nhật ký theo từng em (Giai đoạn 5), màn hình quản trị của Admin (phân công, tài khoản).
- Lọc theo năm học ở `/me/assignments` khi có nhiều năm học (D-044).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic upgrade head` (migration thứ 4), `alembic check` trên máy và trong container backend | Đã chạy, đúng |
| `make lint` (ruff, eslint, tsc) và `make test` (161 test) | Đã chạy, qua |
| `vite build` | Đã chạy, qua |
| `make up`: build lại image (thêm PyJWT), 3 dịch vụ `healthy` | Đã chạy, đúng |
| API thật qua cổng 8000 với 5 tài khoản (admin, bgh1, gvcn.10a2, gv.dia.10, gv.toan.10): đăng nhập, `/me/assignments`, danh sách lớp 10A1/10A2/11A2 | Đã chạy, đúng ma trận (200 có/không phụ huynh, 403); nhật ký chỉ ghi các lần 200 |
| Đăng nhập và `/me/assignments` qua proxy Vite cổng 5173; Vite biên dịch cả 17 module front-end; OpenAPI có scheme `HTTPBearer` | Đã chạy, đúng |
| **Giao diện trên trình duyệt** (form đăng nhập, trang chủ từng vai trò, đăng xuất, hết phiên) | **Chưa kiểm**: phiên làm việc không có công cụ trình duyệt và chưa có Vitest/Playwright. Cần bạn mở thử |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub |

### Cách kiểm tra

1. `make db`, `make migrate` (có migration `audit_logs`), `make seed`. Nếu `.env` có `JWT_SECRET` ngắn hơn 32 ký tự, ứng dụng không khởi động: đặt chuỗi dài hơn.
2. `make test`, `make lint`.
3. API: mở Swagger <http://localhost:8000/api/docs>, gọi `POST /auth/login` với `bgh1@example.com` và mật khẩu dev trong README, bấm Authorize dán `access_token`, thử `GET /me/assignments` và `GET /classes/1/students`. Thử lại với `gv.dia.10@example.com`: lớp 1 (10A1) được, lớp 2 (10A2) bị 403.
4. Giao diện: `make up`, mở <http://localhost:5173>, đăng nhập lần lượt `admin@`, `bgh1@`, `gvcn.10a2@`, `gv.dia.10@`, `gv.toan.10@` (`@example.com`): mỗi vai trò thấy trang chủ khác nhau. Thử Đăng xuất, và mở hai tab với hai vai trò.
5. Xem nhật ký: `docker compose exec db psql -U classroom -d classroom -c "select * from audit_logs"`.

## Giai đoạn 3: Analytics theo Thông tư 22

### Đã làm

- **Lõi tính toán thuần** trong `backend/app/analytics/` (D-047 đến D-051), hệ số và ngưỡng đọc từ `settings` qua `AnalyticsConfig`: ĐTBmhk, ĐTBmcn (từ ĐTBmhk đã làm tròn, làm tròn nửa lên), kết quả học tập Tốt/Khá/Đạt/Chưa đạt kèm **quy định điều chỉnh mức** (công tắc `level_single_subject_adjustment`), rèn luyện và kết quả cả năm (bản ghi `year` hoặc suy ra từ HK2), tổng hợp số buổi nghỉ (theo tuần/tháng), điều kiện lên lớp và môn có thể phải kiểm tra lại.
- **Ba endpoint** (D-053), đều qua `authorize()`: `GET /classes/{id}/dashboard`, `GET /classes/{id}/subjects/{subject_id}/scores`, `GET /grades/{level}/overview`; dashboard và bảng điểm ghi `audit_logs`.
- **Migration thứ 5**: khoá `level_single_subject_adjustment` và hai hành động nhật ký mới. View `v_subject_average` giữ nguyên (D-052).
- **Bộ 30 ca tính tay** `eval/analytics_cases.json` (D-054), đối chiếu bằng script phân số độc lập: 30/30 khớp.
- **Chỉnh dữ liệu seed** (D-056): ba học sinh biên nghỉ 44/45/46 buổi có năng lực cao, để ca "45 đủ, 46 không đủ" chỉ phụ thuộc số buổi nghỉ.
- **Test**: 340 test (thêm 179), gồm công thức tính tay, các ca biên, kiểm chéo với tính độc lập từ bảng điểm thô, ma trận phân quyền của ba endpoint, nhật ký, và 8 lần "đột biến" thủ công đều làm test đỏ.
- **Hiệu năng đo thật** trên seed: dashboard lớp 26 đến 62 ms; tổng quan khối 12 (120 học sinh) 79 ms.

### Chưa làm (thuộc các giai đoạn sau)

- Giao diện cho ba endpoint (Giai đoạn 5); "số cảnh báo" và cảnh báo sớm (Giai đoạn 6); các hàm Analytics làm công cụ cho trợ lý AI và `pseudonymize()` (Giai đoạn 8); nối bộ 30 ca vào `make eval` (Giai đoạn 10).
- Lọc theo năm học (D-044) và quy tắc kết hợp rèn luyện HK1/HK2 cả năm (D-049) chưa làm.

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic upgrade head` (migration thứ 5), `downgrade -1` rồi `upgrade head`, `alembic check` | Đã chạy, đúng |
| `make lint` và `make test` (340 test) | Đã chạy, qua |
| API thật (cổng 8000) với 5 tài khoản: ma trận 200/403 của 3 endpoint; một học sinh (HS1001001, Toán HK1: 8,1 7,8 8,7 6,8 / 8,1 / 7,3) tính tay ra 7,7 khớp API | Đã chạy, đúng |
| **Quy tắc Thông tư 22** (công thức, ngưỡng, thứ tự làm tròn, điều chỉnh mức, kết quả cả năm, điều kiện lên lớp) | **Cần bạn đối chiếu với văn bản gốc**: tôi chỉ đọc được các nguồn thứ cấp (D-047 đến D-051) |
| Hiệu năng ở quy mô 1.500 học sinh | Chưa đo (đo ở 120, suy ra khoảng 1 giây) |
| Giao diện, CI GitHub | Chưa làm / chưa kiểm |

### Cách kiểm tra

1. `make db`, `make migrate` (có migration thứ 5), `make seed`.
2. `make test` (340 test), `make lint`.
3. Swagger <http://localhost:8000/api/docs>: đăng nhập `gvcn.11a2@example.com` rồi gọi `GET /classes/5/dashboard?semester=1` (lớp 11A2: em An nghỉ 38 buổi và em Toán 3,0 nằm trong danh sách cần quan tâm); đổi sang `semester=year` để thấy đếm đủ điều kiện lên lớp. Gọi `GET /classes/5/subjects/2/scores?semester=1` (bảng điểm Toán). Đăng nhập `bgh1@example.com` gọi `GET /grades/12/overview?semester=year`.
4. Thử quyền: `gv.toan.11@example.com` xem được điểm Toán 11A2 nhưng bị 403 ở dashboard 11A2; `admin@example.com` bị 403 ở cả ba.
5. Xem phần ghi nhật ký: `select action, class_id, details from audit_logs`.

## Giai đoạn 4: Import Excel/CSV

### Đã làm

- **Luồng nhập tệp** (`backend/app/imports/`; D-057 đến D-063): tải `.xlsx`/`.csv` → đọc mọi ô dưới dạng chuỗi → ánh xạ cột (bí danh, mẫu đã lưu, chọn tay) → kiểm từng dòng → so với dữ liệu hiện có (`new` / `changed` kèm giá trị cũ / `unchanged`) → bản xem trước lưu DB → xác nhận mới ghi bằng upsert trong một transaction. Ba loại: điểm (một môn, một học kỳ mỗi tệp, môn điểm số và môn nhận xét), điểm danh, rèn luyện.
- **Ba endpoint**: `POST /classes/{id}/import/{kind}`, `POST /imports/{job_id}/confirm`, `GET /imports/mappings`. Quyền ghi qua `authorize_write()` trong `core/authorize.py` (D-058): điểm do giáo viên được phân công đúng lớp-môn, điểm danh và rèn luyện do GVCN; BGH và Admin không nhập; kiểm trước khi đọc tệp và kiểm lại lúc xác nhận.
- **Migration thứ 6**: bảng `import_jobs`, `import_mappings`, hành động nhật ký `import_confirm`. Hook rỗng `on_data_changed(class_id)` cho Giai đoạn 6.
- **Tệp mẫu** `data/samples/` (3 tệp, `make samples`, README riêng) và tuỳ chọn seed **`--hold-out YYYY-MM`** (D-064) cho kịch bản demo "GVCN nhập tệp điểm danh tháng mới". Mặc định của seed không đổi (băm dữ liệu y hệt trước Giai đoạn 4).
- **Front-end** (không thêm thư viện): trang `/classes/:classId/import` (chọn loại, môn, học kỳ hoặc kỳ; kéo thả tệp; chọn cột và lưu mẫu; bảng xem trước tô đỏ lỗi, vàng cảnh báo, hiện cũ → mới, lọc chỉ lỗi; xác nhận khoá khi còn lỗi; tóm tắt kết quả), liên kết "Nhập điểm", "Nhập điểm danh", "Nhập rèn luyện" ở trang chủ.
- **Test**: 630 test (thêm 290): đọc tệp, cột và ánh xạ, từng quy tắc kiểm dòng tính tay, luồng xem trước và xác nhận trên DB thật, ma trận phân quyền, tệp mẫu, seed `--hold-out`. Các ca bắt buộc của PROMPTS đều có: tệp đúng nhập được, tệp lỗi không ghi gì và báo đúng dòng, GVBM nhập môn khác bị 403, nhập lại cùng tệp không nhân đôi. Đã thử "đột biến" thủ công 6 chỗ (bỏ kiểm GVCN, bỏ kiểm phân công, upsert thành `DO NOTHING`, nới ngưỡng 10 thành 10,5, cho xác nhận khi còn lỗi, bỏ kiểm người tạo job): test đỏ cả 6, riêng chỗ cuối cần thêm một ca (giáo viên mới nhận môn không xác nhận được bản xem trước của người cũ).

### Chưa làm (thuộc các giai đoạn sau, hoặc ngoài phạm vi)

- Điểm danh dạng "rộng" (mỗi ngày một cột). Nhập qua giao diện cho BGH/Admin (không có quyền ghi). Giới hạn dung lượng tải lên ở reverse proxy và giới hạn tần suất: Giai đoạn 11. Gắn cảnh báo sớm vào `on_data_changed`: Giai đoạn 6. Làm mới dashboard sau khi nhập: Giai đoạn 5 (dashboard hiện đọc trực tiếp DB nên số liệu mới thấy ngay khi mở lại).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic upgrade head` (migration thứ 6), lên/xuống/lên, `alembic check` | Đã chạy, đúng |
| `make seed` hai lần: băm dữ liệu giống nhau (63.000 dòng điểm danh); `--hold-out 2027-03` còn 54.720 dòng | Đã chạy, đúng |
| `make lint` và `make test` (630 test) | Đã chạy, qua |
| `make up` (dựng lại image vì thêm pandas, openpyxl, python-multipart), 3 dịch vụ `healthy`; Vite biên dịch cả 13 module mới/sửa và trả trang SPA cho `/classes/5/import` | Đã chạy, đúng |
| API thật bằng `curl -F` (qua proxy Vite và cổng 8000) với 3 tệp mẫu: tệp đúng (3 dòng đổi, xác nhận ghi 3 ô, xác nhận lần hai không ghi lại), tệp lỗi (6 lỗi + 1 cảnh báo đúng dòng đúng cột, xác nhận 422), `gv.van.11` / BGH / GVCN không dạy Toán / `gv.toan.11` điểm danh 11A2 đều 403 | Đã chạy, đúng |
| Kịch bản demo: seed `--hold-out 2027-03`, `gvcn.11a2` nhập tệp điểm danh: 920 dòng mới, em An nghỉ 34 → 38 buổi trên dashboard; đối chiếu `HS1102005` bằng SQL (ĐĐGtx 2 = 6,60) và `audit_logs` (2 dòng `import_confirm`) | Đã chạy, đúng |
| **Giao diện trên trình duyệt** (chọn cột, bảng xem trước, nút xác nhận) | Lúc làm Giai đoạn 4: chưa kiểm. **Đã chạy thử trên Chrome thật ở Giai đoạn 5** (chọn tệp, xem trước, khoá nút khi còn lỗi, chọn cột, xác nhận): đúng. Chưa thử thao tác kéo thả tệp |
| **Định dạng sổ điểm điện tử thật** (VNEDU, SMAS…) | **Chưa thử**: không có tệp thật; định dạng tệp mẫu là suy đoán (D-057). Cần thử với một tệp xuất thật đã ẩn danh |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub. CI cài dependency bằng `make install` nên tự có thư viện mới (`pandas`, `openpyxl`, `python-multipart` trong `pyproject.toml`); test tệp mẫu đọc `data/samples/` đã commit |

### Cách kiểm tra

1. `make db`, `make migrate` (có migration thứ 6), `make seed SEED_ARGS="--hold-out 2027-03"`, `make up` (dựng lại image).
2. Mở <http://localhost:5173>, đăng nhập `gvcn.11a2@example.com` (mật khẩu dev trong README), bấm "Nhập điểm danh" ở thẻ lớp 11A2, chọn `data/samples/diem-danh-11a2-2027-03.csv`: 920 dòng mới → "Xác nhận nhập".
3. Đăng nhập `gv.toan.11@example.com`, bấm "Nhập điểm" ở dòng Toán 11A2, học kỳ I, thử `diem-toan-11a2-hk1.xlsx` (3 dòng đổi) rồi `diem-toan-11a2-hk1-loi.xlsx` (lỗi, nút xác nhận bị khoá). Thử đổi tên cột trong tệp để xem bước chọn cột.
4. Thử quyền: đăng nhập `gv.van.11@example.com` rồi mở `/classes/5/import` (không có quyền); `bgh1@` không có nút nhập nào.
5. `make test`, `make lint`. Xem nhật ký: `select action, class_id, details from audit_logs where action = 'import_confirm'`. Chạy `make seed` không tham số để về dữ liệu đầy đủ.


## Giai đoạn 5: Dashboard và giao diện chính

### Đã làm

- **Back-end, hai phần nhỏ** (D-066): dashboard lớp thêm `absences_by_month` (đủ mọi tháng của năm học, tháng không nghỉ ghi 0), `absence_limits`, `thresholds` từ `settings`; endpoint mới `GET /classes/{id}/students/{student_id}/profile` với hai schema riêng (GVCN, BGH đầy đủ; GVBM chỉ các môn mình dạy, không có khoá phụ huynh, chuyên cần, rèn luyện), ghi nhật ký `view_student_profile`.
- **Khung giao diện** (D-067): `AppLayout` với thanh điều hướng theo vai trò, `?semester=` trong URL, các trang biểu đồ nạp theo yêu cầu, `QueryState` (đang tải, lỗi, 403, 404), trợ năng cơ bản.
- **Bảy màn hình** (Recharts, tiếng Việt, số `6,5`, 1366px): trang chủ theo vai trò (có liên kết tới các màn hình mới); dashboard lớp `/classes/:id` (4 ô số liệu, mức học tập, rèn luyện, bảng ĐTB các môn, học sinh cần quan tâm, nghỉ theo tháng, điều kiện lên lớp khi xem cả năm); bảng điểm môn (lưới tx/giữa kỳ/cuối kỳ, ĐTB do server tính, ô thiếu tô nổi, phân bố điểm, lọc học sinh thiếu điểm); dashboard khối (so sánh các lớp, học kỳ I cạnh học kỳ II); hồ sơ học sinh; khung Trợ lý AI và Nhận xét & báo cáo (D-070).
- **Test back-end**: 660 test (thêm 30): gom nghỉ theo tháng tính tay, dashboard (tổng các tháng khớp SQL), hồ sơ học sinh (ma trận 4 vai trò, GVBM không có khoá nào ngoài môn mình, phụ huynh chỉ GVCN và BGH, 404 học sinh lớp khác, nhật ký, hồ sơ khớp dashboard và bảng điểm cho cả ba kỳ). Đã thử "đột biến" thủ công 4 chỗ (bỏ hạn chế môn của GVBM, bỏ `authorize`, GVBM nhận hồ sơ đầy đủ, học sinh lạ trả về em khác): test đỏ cả 4.

### Chưa làm (thuộc các giai đoạn sau, hoặc ngoài phạm vi)

- **Vitest và Playwright** (D-069): hoãn theo lựa chọn của bạn, nên chưa đạt tiêu chí "một test Playwright" của PROMPTS. Khung chat Trợ lý AI nổi trên mọi màn hình, số cảnh báo thật, nút "Tạo nhận xét": Giai đoạn 6, 8, 9. Dashboard cấp trường, khối 12 phụ đạo (F10), xuất PDF/Excel (F11): ngoài phạm vi (D-070).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `make lint` và `make test` (660 test) | Đã chạy, qua |
| `make seed` không tham số trả DB về dữ liệu đầy đủ (63.000 dòng điểm danh) sau khi thử nhập | Đã chạy, đúng |
| `make up` (dựng lại image vì thêm Recharts), 3 dịch vụ `healthy` | Đã chạy, đúng |
| API thật bằng `curl`: profile của em An (`HS1102001`) trả 200 `full` cho GVCN 11A2 và BGH, 200 `subjects` cho `gv.toan.11` và `gv.van.11`, 403 cho GVBM khối khác và Admin, 404 cho học sinh lớp khác và học sinh không có; dashboard có 9 tháng, tổng 155 buổi nghỉ khớp SQL | Đã chạy, đúng |
| **Trình duyệt thật** (Chrome 155, 1366×768, script tạm ngoài repo) với `gv.van.11`, `gvcn.11a2`, `bgh1`, `gv.toan.11`: đi hết các màn hình mỗi vai trò, trang không tràn ngang, không lỗi console (trừ một 403 cố ý), ảnh chụp đã xem | Đã chạy, đúng |
| **Luồng Nhập dữ liệu của Giai đoạn 4 trên trình duyệt** (chọn tệp, xem trước, tệp lỗi khoá nút, chọn cột lạ, xác nhận) | Đã chạy, đúng; chưa thử kéo thả tệp |
| Số trên giao diện khớp tính tay: em An nghỉ 38 buổi (25 có phép, 13 không phép); Toán HK1 của em An 6,7 = (7,0 + 7,1 + 7,5 + 7,4 + 2×6,5 + 3×6,1) / 9; `HS1102002` (Toán 3,0) nằm trong "cần quan tâm" | Đã đối chiếu, đúng |
| Kiểm tự động giao diện chạy lại được (Vitest, Playwright) | **Chưa có** (D-069) |
| Màn hình hẹp hơn 1366px, trình duyệt khác Chrome, trình đọc màn hình | **Chưa kiểm** |
| Mọi quy tắc Thông tư 22 (giao diện chỉ hiển thị kết quả server) | **Cần bạn đối chiếu với văn bản gốc** (D-047 đến D-051) |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub |

### Cách kiểm tra

1. `make db`, `make migrate`, `make seed`, `make up` (dựng lại image vì có Recharts), mở <http://localhost:5173>.
2. Đăng nhập `gvcn.11a2@example.com` (mật khẩu dev trong README): thẻ lớp 11A2 → "Dashboard lớp". Đổi "Kỳ xem" sang "Cả năm" (URL đổi theo `?semester=year`). Bấm "Trần Minh An" ở "Học sinh cần quan tâm": hồ sơ có 38 buổi nghỉ, thông tin phụ huynh, biểu đồ nghỉ theo tháng. Bấm tên một môn ở bảng ĐTB để mở bảng điểm môn.
3. Đăng nhập `gv.van.11@example.com`: bảng lớp-môn → "Bảng điểm"; bấm tên học sinh: hồ sơ chỉ có điểm Ngữ văn. Mở thẳng `/classes/5` sẽ báo không có quyền.
4. Đăng nhập `bgh1@example.com`: "Khối 11" trên thanh điều hướng → so sánh các lớp, đổi kỳ, chọn môn ở phần học kỳ I so với II; bấm tên lớp để vào dashboard lớp.
5. Thử `/assistant` và `/reports` (khung giao diện). Resize cửa sổ về 1366px để xem bố cục.
6. `make test`, `make lint`. Swagger: `GET /classes/{id}/students/{student_id}/profile`.


## Giai đoạn 6: Cảnh báo sớm (luật + ML)

### Đã làm

- **Lớp luật** (`backend/app/warning/rules.py`, D-071): 10 luật theo DESIGN mục 6.2 (nghỉ 30/40/45 buổi, mức học tập Chưa đạt, môn dưới 3,5, ít hơn 6 môn từ 5,0, từ 2 môn nhận xét Chưa đạt, rèn luyện HK I Chưa đạt, môn có thể kiểm tra lại, khối 12 môn thi thấp); mỗi luật trả mã, mức, câu lý do tiếng Việt kèm số liệu; ngưỡng đọc từ `settings`. Theo D-048 (bạn chọn giữ), câu lý do chỉ nêu số liệu.
- **Lớp ML** (`backend/ml/`, `app/warning/features.py`, `app/warning/model.py`; D-072): đặc trưng giữa học kỳ I (chỉ điểm và chuyên cần), huấn luyện trên 20 khoá giả lập (7.200 học sinh, trong database tạm, loại seed 2026), Logistic Regression làm mốc và Random Forest làm mô hình chính, ngưỡng chọn bằng cross-validation trên train, giải thích 3 yếu tố bằng đóng góp cục bộ thay-về-trung-vị. **Recall trên tập test 0,92** (Precision 0,93, F1 0,92; mốc Logistic Regression 0,89, 0,80, 0,84); báo cáo đầy đủ ở `backend/ml/REPORT.md`. Mô hình nhỏ được commit; thiếu hoặc hỏng thì chỉ chạy lớp luật.
- **Gộp và lưu** (D-071): mức Cao / Trung bình / Thấp = mức cao nhất giữa luật và ML; chỉ thêm dòng `risk_alerts` khi nội dung đổi (giữ `teacher_status`, giữ lịch sử).
- **API** (D-073): `GET /classes/{id}/alerts`, `PATCH /alerts/{id}` (GVCN của lớp), `GET /alerts?level=` (BGH, ngoài DESIGN mục 7); migration thứ 7 (nhật ký 3 hành động mới, chỉ mục dòng mới nhất). Dashboard thêm `alert_counts`, hồ sơ thêm `alert`.
- **Hook và lệnh** (D-074): `on_data_changed` chạy cảnh báo của lớp sau mỗi lần nhập (lỗi chỉ ghi log), `make warn`, `make train`; `make seed` chạy cảnh báo ở cuối.
- **Giao diện** (D-075): panel "Học sinh cần hỗ trợ" ở dashboard lớp, panel cảnh báo ở hồ sơ, số cảnh báo ở thẻ lớp chủ nhiệm, panel mức Cao toàn trường cho BGH; nút "Đã trao đổi" / "Báo nhầm" cho GVCN.
- **Test**: 759 test (thêm 99): từng luật tính tay và trên học sinh biên của seed, gộp mức, lưu kiểu thêm-khi-đổi (không thêm dòng khi chạy lại, `teacher_status` còn nguyên), ma trận phân quyền của cả ba endpoint, nhật ký, hook (kể cả lỗi trong cảnh báo không làm import thất bại), đặc trưng tính tay, mô hình đã lưu, giải thích, đường lùi khi thiếu mô hình, huấn luyện trên dữ liệu tổng hợp và trên một khoá thật. Đã thử "đột biến" thủ công 7 chỗ (bỏ `authorize_write` của PATCH, cho GVBM xem cảnh báo, 45 buổi bị coi là vượt, 30 buổi không nhắc, luôn thêm dòng mới, hook không bắt lỗi, 1 môn nhận xét Chưa đạt bị cảnh báo): test đỏ cả 7.

### Chưa làm (thuộc các giai đoạn sau, hoặc ngoài phạm vi)

- Dùng cảnh báo trong trợ lý AI (`get_student_detail`, `list_students` có lọc theo mức cảnh báo): Giai đoạn 8. Bộ đánh giá mô hình cảnh báo chạy bằng `make eval`: Giai đoạn 10. Đánh giá lại mô hình từ các lần "báo nhầm": dữ liệu đã được lưu (lịch sử `risk_alerts`), chưa có script.
- Mô hình thật sự học từ dữ liệu thật, đặc trưng "kết quả năm trước" và "rèn luyện kỳ trước", UCI, nhiều thời điểm chụp (D-072). Kiểm tự động giao diện vẫn hoãn (D-069).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic upgrade head` (migration thứ 7), `downgrade -1` rồi lên lại, `alembic check` | Đã chạy, đúng |
| `make lint` và `make test` (759 test) | Đã chạy, qua |
| `make train` (khoảng 2 đến 3 phút): Recall trên tập test 0,92 (mục tiêu 0,75), Precision 0,93, F1 0,92 | Đã chạy, **đạt**; xem giới hạn ở REPORT.md |
| `make seed` hai lần: băm các dòng `risk_alerts` giống nhau (360 dòng, cảnh báo tất định) | Đã chạy, đúng |
| `make up` (dựng lại image vì thêm scikit-learn, Python 3.12 trong container nạp được mô hình huấn luyện bằng Python 3.13) | Đã chạy, đúng |
| API thật bằng `curl` với 5 tài khoản: `GET /classes/5/alerts` (GVCN, BGH 200; GVBM, Admin 403), `PATCH` (GVCN 200; BGH, GVBM 403), `GET /alerts` (BGH 200; GVCN, Admin 403), nhật ký | Đã chạy, đúng |
| Kịch bản demo: seed `--hold-out 2027-03` → em An "nghỉ 34 buổi"; GVCN nhập tệp điểm danh tháng 3 → hook chạy → "nghỉ 38 buổi" (thêm 1 dòng mới) | Đã chạy, đúng |
| Trình duyệt thật (Chrome, 1366×768): ghi nhận "Báo nhầm" lưu qua tải lại trang, hồ sơ có cảnh báo, BGH thấy 39 cảnh báo mức Cao và không có nút ghi nhận, không lỗi console | Đã chạy, đúng |
| **Mô hình trên dữ liệu thật** | **Chưa thử**: chỉ có dữ liệu giả lập; Recall cao chưa chứng minh dùng được với dữ liệu thật (D-072) |
| Quy tắc Thông tư 22 | Vẫn **cần bạn đối chiếu văn bản gốc** (D-047 đến D-051); D-048 bạn đã chọn giữ |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub (CI cài `scikit-learn` qua `make install`) |

### Cách kiểm tra

1. `make db`, `make migrate` (migration thứ 7), `make seed` (tự chạy cảnh báo), `make up` (dựng lại image vì thêm scikit-learn).
2. Đăng nhập `gvcn.11a2@example.com`: thẻ lớp 11A2 hiện số cảnh báo; "Dashboard lớp" → panel "Học sinh cần hỗ trợ"; bấm "Báo nhầm" ở em An rồi tải lại trang (còn nguyên); mở hồ sơ em An xem lý do và "vì sao mô hình dự báo như vậy".
3. Kịch bản demo: `make seed SEED_ARGS="--hold-out 2027-03"`, vào dashboard lớp 11A2 (em An "nghỉ 34 buổi"), nhập `data/samples/diem-danh-11a2-2027-03.csv` ở trang Nhập dữ liệu, mở lại dashboard (em An "nghỉ 38 buổi", cảnh báo đã cập nhật). Chạy `make seed` không tham số để về dữ liệu đầy đủ.
4. Đăng nhập `bgh1@example.com`: panel "mức cao, toàn trường" ở trang chủ; vào dashboard một lớp: chỉ xem, không có nút ghi nhận. `gv.van.11@example.com` mở `/classes/5` hay gọi `/classes/5/alerts` bị 403.
5. `make train` để huấn luyện lại (ghi `backend/ml/REPORT.md` và mô hình), rồi `make warn` để tính lại cảnh báo; `make test`, `make lint`.


## Giai đoạn 7: RAG văn bản quy định

### Đã làm

- **Nạp văn bản** (`backend/app/rag/`; D-076 đến D-081): Admin tải `.pdf`, `.docx` hoặc `.txt` → đọc chữ (bỏ số trang, đầu/chân trang lặp lại) → **tách theo Điều/Khoản** (mỗi khoản một đoạn kèm tiêu đề điều, chỉ khoản quá dài mới tách tiếp, metadata `article`/`clause`) → tính vector bằng **bge-m3 trên CPU** → ghi văn bản, đoạn và nhật ký trong một transaction. Mỗi tên chỉ có một bản còn hiệu lực; Admin đánh dấu hết hiệu lực hoặc bật lại.
- **Tìm kiếm** (D-080, D-082): `search_regulation(query, k=4)` tìm theo cosine trong pgvector (chỉ mục HNSW), **chỉ trong văn bản còn hiệu lực** (lọc ngay trong SQL); độ tương đồng cao nhất dưới `settings.rag_min_similarity` (0,56) thì trả "Không tìm thấy trong văn bản quy định" và không trả đoạn nào.
- **API** (D-077, ngoài bảng DESIGN mục 7): `GET` và `POST /admin/regulations`, `PATCH /admin/regulations/{id}` (chỉ Admin, hàm mới `authorize_admin`), `GET /regulations/search` (mọi người dùng đăng nhập). **Migration thứ 8**: bảng `regulation_documents`, `document_id` và chỉ mục HNSW cho `regulation_chunks`, khoá `rag_min_similarity`, hai hành động nhật ký. `make seed` giữ cả hai bảng văn bản.
- **Dòng lệnh**: `make regulations` (nạp `data/regulations/`, chạy lại an toàn), `make rag-model` (tải sẵn mô hình), `make eval-rag` (đo Hit@4 và tỉ lệ từ chối đúng bằng mô hình thật, D-083). Văn bản mẫu **GIẢ** `data/regulations/van-ban-mau-gia.txt` (8 điều, 18 đoạn); `.gitignore` chỉ cho commit văn bản mẫu giả, văn bản thật của bạn mặc định không bị commit.
- **Giao diện** (D-084): trang `/admin/regulations` cho Admin (danh sách, tải lên, hết hiệu lực / bật lại có xác nhận, "Thử tìm").
- **Hạ tầng**: thêm `sentence-transformers`, `torch` (bản CPU), `pypdf`, `python-docx`; volume `hf_cache` giữ mô hình (~2,3 GB) giữa các lần dựng image; `EMBEDDING_MODEL` mặc định `BAAI/bge-m3`.
- **Test**: 908 test qua, 1 bỏ qua (thêm 149): tách Điều/Khoản trên văn bản mẫu và các ca biên (khoản liên tiếp, điểm, điều dài, phụ lục, "Nơi nhận"), đọc PDF/DOCX/TXT tự dựng và các tệp lỗi, tìm kiếm (ngưỡng đọc từ `settings`, hết hiệu lực không bị trích, chỉ bản còn hiệu lực được trả khi bản cũ cùng tên đã hết hiệu lực), API (ma trận vai trò trên mọi endpoint quản trị, 409/413/422, lỗi giữa chừng không để lại gì, nhật ký). Test dùng bộ nhúng giả nên không tải mô hình; test duy nhất cần mô hình thật được bỏ qua mặc định và đã chạy riêng bằng `RUN_EMBEDDING_TESTS=1`: 8/8 qua. Đã thử "đột biến" thủ công 4 chỗ (bỏ lọc hiệu lực, bỏ ngưỡng, đổi `>=` thành `>`, bỏ `authorize_admin`): test đỏ cả 4.

### Chưa làm (thuộc các giai đoạn sau, hoặc ngoài phạm vi)

- Gọi `search_regulation` từ trợ lý và trích dẫn kiểu "theo Điều 12 Thông tư 22/2021" trong câu trả lời: Giai đoạn 8. Đo "% trả lời đúng" (cần LLM) và bộ câu đủ 30 + 5: Giai đoạn 10. Giới hạn dung lượng tải lên ở reverse proxy: Giai đoạn 11. OCR cho PDF quét ảnh (D-079). Xoá hẳn văn bản (chỉ có đánh dấu hết hiệu lực).

### Đã kiểm chứng và còn chờ kiểm chứng

| Mục | Trạng thái |
| --- | --- |
| `alembic upgrade head` (migration thứ 8), `alembic check` ("No new upgrade operations detected") | Đã chạy, đúng |
| `make lint` và `make test` (908 test qua, 1 bỏ qua) | Đã chạy, qua |
| `make regulations` rồi `make eval-rag` với **bge-m3 thật**: Hit@4 **6/8 = 75%**, từ chối đúng **1/2 = 50%**; mục tiêu DESIGN 80% | Đã chạy, **chưa đạt**. R04 (0,555) và R07 (0,520) bị từ chối nhầm vì dưới ngưỡng 0,56; N01 "buộc thôi học" (0,568) trả nhầm Điều 3 về nghỉ học. Không ngưỡng nào tách được cả ba (D-082), và mẫu chỉ 8 + 2 câu nên chưa kết luận được gì về chất lượng chung |
| `make up`: 3 dịch vụ `healthy`, mô hình nạp từ volume `hf_cache` trong container | Đã chạy, đúng |
| API thật bằng Python/UTF-8: 401 không token; Admin 200; GVBM và BGH đều 403 ở list, PATCH, POST; GVBM tìm được (câu "Điện thoại bị giáo viên thu giữ..." → Điều 5 Khoản 2, 0,680; câu căng tin → "không tìm thấy", 0,4455) | Đã chạy, đúng. **Lưu ý**: `curl` của Git Bash trên Windows làm hỏng dấu tiếng Việt trong tham số, cho độ tương đồng sai (0,37) — chỉ là lỗi công cụ, API đúng khi gửi UTF-8 |
| Trình duyệt thật (Chrome, 1366×768): trang Admin, tải lên một văn bản thử, báo trùng tên, hết hiệu lực làm câu hỏi không còn được trích, bật lại thì được trích; GVBM không có liên kết và bị chặn khi mở thẳng; không lỗi console | Đã chạy, đúng; văn bản thử đã xoá. Chưa thử kéo thả tệp, PDF/DOCX qua giao diện |
| **Văn bản thật** (Thông tư 22/2021, quy chế thi, nội quy) | **Chưa thử**: bạn tự đặt vào `data/regulations/` (PROMPTS). Quy tắc tách (D-078) và ngưỡng (D-082) chỉ đo trên văn bản mẫu giả; cần chạy `make regulations`, `make eval-rag` và hiệu chỉnh lại |
| **PDF/DOCX thật** | **Chưa thử**: test dùng tệp tự dựng; PDF thật có thể ngắt dòng, đánh số kiểu khác (D-078, D-079) |
| Bộ 30 câu tạm đã chọn ngưỡng 0,56 | **Không được lưu lại**, chưa tái lập được (D-082); bộ `eval/rag_questions.json` chỉ là khung 10 câu |
| Quy tắc Thông tư 22 trong `analytics/` | Vẫn **cần bạn đối chiếu văn bản gốc** (D-047 đến D-051) |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub; CI cài `torch` bản CPU qua `make install` nên bước cài sẽ lâu hơn |

### Cách kiểm tra

1. `make db`, `make migrate` (migration thứ 8), `make rag-model` (lần đầu tải ~2,3 GB), `make regulations`.
2. `make eval-rag`: xem độ tương đồng từng câu, Hit@4 và tỉ lệ từ chối. Thử ngưỡng khác: `make eval-rag RAG_ARGS="--threshold 0.5"`.
3. `make up`, đăng nhập `admin@example.com` (mật khẩu dev trong README), bấm "Văn bản quy định": thử tải `data/regulations/van-ban-mau-gia.txt` với tên đã có (bị báo trùng), thử tải tệp mới, bấm "Đánh dấu hết hiệu lực" rồi dùng ô "Thử tìm" để thấy văn bản đó không còn được trích, rồi "Bật lại". Đăng nhập `gv.toan.11@example.com`: không có mục này, mở `/admin/regulations` chỉ thấy lời báo không có quyền.
4. Swagger: `GET /api/v1/regulations/search?q=...` bằng token của bất kỳ vai trò nào; `GET /api/v1/admin/regulations` chỉ Admin (các vai trò khác 403).
5. Văn bản thật: chép vào `data/regulations/`, thêm tên hiển thị vào `manifest.json`, `make regulations`, rồi `make eval-rag` và hiệu chỉnh `rag_min_similarity` trong bảng `settings` (xem D-082).
6. `make test`, `make lint`. Test mô hình thật: `RUN_EMBEDDING_TESTS=1` rồi `cd backend && python -m pytest tests/rag/test_embedding.py`.

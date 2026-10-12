# Tiến độ

Cập nhật lần cuối: 2026-10-13 (Giai đoạn 4). Tên và thứ tự giai đoạn lấy từ bộ prompt [PROMPTS.md](PROMPTS.md).

## Bảng 12 giai đoạn

| Giai đoạn | Nội dung | Trạng thái |
| --- | --- | --- |
| 0 | Khởi tạo dự án | Xong (còn chờ kiểm: CI trên GitHub, cần đẩy lên GitHub, xem bên dưới) |
| 1 | Cơ sở dữ liệu + dữ liệu giả lập | Xong, đã commit `cab087d` (còn chờ kiểm: CI trên GitHub, xem bên dưới) |
| 2 | Xác thực và phân quyền | Xong, đã commit `43900ac` (chưa kiểm giao diện trên trình duyệt, CI trên GitHub; xem bên dưới) |
| 3 | Analytics theo Thông tư 22 | Xong, đã commit `15c8d97` (quy tắc lấy từ nguồn thứ cấp, **cần đối chiếu văn bản gốc**; xem bên dưới) |
| 4 | Import Excel/CSV | Xong, chưa commit (chưa kiểm giao diện trên trình duyệt, chưa thử với sổ điểm thật; xem bên dưới) |
| 5 | Dashboard và giao diện chính | Chưa làm |
| 6 | Cảnh báo sớm (luật + ML) | Chưa làm |
| 7 | RAG văn bản quy định | Chưa làm |
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
| **Giao diện trên trình duyệt** (kéo thả, chọn cột, bảng xem trước, nút xác nhận) | **Chưa kiểm**: không có công cụ trình duyệt, chưa có Vitest/Playwright (D-004). Mới kiểm bằng `eslint`, `tsc`, `vite build` và API thật. Cần bạn mở thử |
| **Định dạng sổ điểm điện tử thật** (VNEDU, SMAS…) | **Chưa thử**: không có tệp thật; định dạng tệp mẫu là suy đoán (D-057). Cần thử với một tệp xuất thật đã ẩn danh |
| CI GitHub Actions | **Chưa kiểm**: cần đẩy lên GitHub. CI cài dependency bằng `make install` nên tự có thư viện mới (`pandas`, `openpyxl`, `python-multipart` trong `pyproject.toml`); test tệp mẫu đọc `data/samples/` đã commit |

### Cách kiểm tra

1. `make db`, `make migrate` (có migration thứ 6), `make seed SEED_ARGS="--hold-out 2027-03"`, `make up` (dựng lại image).
2. Mở <http://localhost:5173>, đăng nhập `gvcn.11a2@example.com` (mật khẩu dev trong README), bấm "Nhập điểm danh" ở thẻ lớp 11A2, chọn `data/samples/diem-danh-11a2-2027-03.csv`: 920 dòng mới → "Xác nhận nhập".
3. Đăng nhập `gv.toan.11@example.com`, bấm "Nhập điểm" ở dòng Toán 11A2, học kỳ I, thử `diem-toan-11a2-hk1.xlsx` (3 dòng đổi) rồi `diem-toan-11a2-hk1-loi.xlsx` (lỗi, nút xác nhận bị khoá). Thử đổi tên cột trong tệp để xem bước chọn cột.
4. Thử quyền: đăng nhập `gv.van.11@example.com` rồi mở `/classes/5/import` (không có quyền); `bgh1@` không có nút nhập nào.
5. `make test`, `make lint`. Xem nhật ký: `select action, class_id, details from audit_logs where action = 'import_confirm'`. Chạy `make seed` không tham số để về dữ liệu đầy đủ.

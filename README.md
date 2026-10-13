# Trợ lý AI quản lý lớp học THPT

Web app cho trường THPT (khối 10, 11, 12): theo dõi điểm, chuyên cần, rèn luyện; cảnh báo sớm học sinh có nguy cơ không được lên lớp; AI hỗ trợ hỏi đáp và sinh nhận xét (luôn là bản nháp, giáo viên duyệt). Chỉ dùng dữ liệu giả lập.

Tài liệu: [CLAUDE.md](CLAUDE.md) (nguyên tắc, quy ước) · [docs/DESIGN.md](docs/DESIGN.md) (thiết kế đầy đủ) · [docs/FLOWS.md](docs/FLOWS.md) (sơ đồ) · [docs/PROGRESS.md](docs/PROGRESS.md) (tiến độ) · [docs/DECISIONS.md](docs/DECISIONS.md) (quyết định thiết kế) · [docs/PROMPTS.md](docs/PROMPTS.md) (bộ prompt các giai đoạn).

## Yêu cầu

- Docker Desktop (Compose v2 trở lên) và GNU make. Trên Windows cài make bằng `winget install ezwinports.make`, rồi mở lại terminal.
- Chỉ khi chạy ngoài Docker (lint, test, phát triển): Python 3.11+ và Node 22.

## Chạy nhanh bằng Docker

```bash
cp .env.example .env     # PowerShell: Copy-Item .env.example .env
make up
```

Mở <http://localhost:5173/login>: trang đăng nhập hiện "Máy chủ: ok" và "Cơ sở dữ liệu: ok" (trang chủ `/` cần đăng nhập). Swagger: <http://localhost:8000/api/docs>. Tắt bằng `make down` (dữ liệu DB vẫn nằm trong volume).

Muốn đăng nhập cần có dữ liệu mẫu: `make migrate` rồi `make seed` (xem mục "Dữ liệu giả lập và tài khoản dev"). `JWT_SECRET` trong `.env` phải dài từ 32 ký tự.

`.env` chứa giá trị mẫu cho môi trường phát triển và không bao giờ được commit. Khoá API của LLM (nếu dùng) chỉ điền vào `.env`.

## Phát triển ngoài Docker

```bash
python -m venv backend/.venv
# Kích hoạt: Windows  backend\.venv\Scripts\Activate.ps1   |   Linux/macOS  source backend/.venv/bin/activate
make install             # cài dependency back-end và front-end
make db                  # chỉ chạy PostgreSQL
make migrate             # tạo bảng, view v_subject_average, extension vector, giá trị mặc định của settings
make seed                # nạp dữ liệu giả lập (xem mục bên dưới)
make dev-be              # terminal 1: API tại http://localhost:8000
make dev-fe              # terminal 2: giao diện tại http://localhost:5173
```

## Lệnh make

| Lệnh | Việc làm |
| --- | --- |
| `make up` / `make down` | Dựng và chạy / tắt db + backend + frontend trong Docker |
| `make db` | Chỉ chạy PostgreSQL |
| `make install` | Cài dependency ngoài Docker |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Sinh dữ liệu giả lập vào DB (cần `make db` và `make migrate` trước) |
| `make samples` | Sinh lại các tệp mẫu nhập dữ liệu trong `data/samples/` (cần DB đã migrate) |
| `make warn` | Chạy cảnh báo sớm cho cả trường (`make seed` đã tự chạy; chỉ thêm dòng mới khi nội dung đổi) |
| `make train` | Huấn luyện lại mô hình cảnh báo sớm (2 đến 3 phút, dùng database tạm), ghi `backend/ml/models/` và `backend/ml/REPORT.md` |
| `make regulations` | Nạp văn bản quy định trong `data/regulations/` (tách Điều/Khoản, tính vector); văn bản đã nạp thì bỏ qua |
| `make rag-model` | Tải sẵn mô hình embedding bge-m3 (khoảng 2,3 GB, chỉ lần đầu) |
| `make eval-rag` | Đo RAG bằng mô hình thật: Hit@4 và tỉ lệ từ chối đúng (`eval/rag_questions.json`) |
| `make eval-assistant` | Đo Trợ lý AI bằng LLM thật: % chọn đúng hàm, % đúng số liệu, % từ chối đúng (15 câu trong `eval/assistant_questions.json`); cần `LLM_PROVIDER` và khoá API. Thêm `ASSISTANT_ARGS=--dry-run` để chỉ in đáp án kỳ vọng |
| `make dev-be` / `make dev-fe` | Chạy back-end (uvicorn) / front-end (Vite) với tự nạp lại |
| `make test` | pytest. Gồm test cần PostgreSQL thật nên phải `make db` trước; chỉ chạy test không cần DB: `cd backend && python -m pytest -m "not db"` |
| `make lint` | ruff check, ruff format --check (cả `backend/`, `data/` và `eval/`), eslint, tsc |
| `make eval` | Chưa triển khai (in thông báo, thoát mã 0) |

## Dữ liệu giả lập và tài khoản dev

`make seed` tạo 1 trường, năm học 2026-2027 (đủ hai học kỳ, mô phỏng một năm đã hoàn tất), khối 10/11/12 mỗi khối 3 lớp, mỗi lớp 40 học sinh (360 học sinh), 17 môn theo Chương trình GDPT 2018 và tài khoản mẫu. Toàn bộ là dữ liệu giả: tên ghép ngẫu nhiên, email `@example.com`, số điện thoại phụ huynh bắt đầu bằng `0000` (không hợp lệ).

**Cảnh báo:** `make seed` xoá **mọi** dữ liệu trường học trong DB (điểm, điểm danh, học sinh, lớp, tài khoản, nhật ký AI...) rồi nạp lại; chỉ giữ bảng `settings`, `regulation_documents` và `regulation_chunks` (văn bản quy định đã nạp, tính lại vector tốn công). Từ chối chạy khi `APP_ENV=production`. Chạy lại với cùng tham số cho đúng cùng dữ liệu.

```bash
make seed                                                   # mặc định: --seed 2026, 3 lớp/khối, sĩ số 40
make seed SEED_ARGS="--seed 7 --classes-per-grade 2 --class-size 30"
make seed SEED_ARGS="--hold-out 2027-03"                    # bỏ điểm danh tháng 3/2027 để demo nhập tệp (xem mục nhập tệp)
```

Mật khẩu dev dùng chung cho mọi tài khoản (chỉ dành cho môi trường phát triển): `ThdaDev#2026`

| Vai trò | Email | Ghi chú |
| --- | --- | --- |
| Admin | `admin@example.com` | cấu hình hệ thống: tài khoản, năm học, lớp, phân công, danh sách học sinh, văn bản quy định (không xem điểm hay danh sách học sinh) |
| Ban giám hiệu | `bgh1@example.com`, `bgh2@example.com` | toàn trường |
| GVCN (chỉ chủ nhiệm) | `gvcn.10a2@example.com`, `gvcn.10a3@example.com`, ... `gvcn.12a3@example.com` | một người cho mỗi lớp từ A2 |
| GVBM | `gv.<môn>.<khối>@example.com`, ví dụ `gv.van.11@example.com`, `gv.ly.12@example.com` | một giáo viên cho mỗi cặp môn-khối, dạy mọi lớp của khối có học môn đó |
| Vừa GVCN vừa GVBM | `gv.toan.10@example.com`, `gv.toan.11@example.com`, `gv.toan.12@example.com` | chủ nhiệm lớp A1 của khối và dạy Toán cả khối (để thử quyền cộng dồn) |

Thử API: mở Swagger, gọi `POST /api/v1/auth/login` với email và mật khẩu ở trên, bấm **Authorize** và dán `access_token`, rồi thử `GET /api/v1/me/assignments` và `GET /api/v1/classes/{id}/students`. Admin bị 403 ở danh sách lớp; GVBM chỉ vào được lớp mình dạy và không thấy thông tin phụ huynh; GVCN và BGH thấy thông tin phụ huynh. Mỗi lần mở danh sách lớp được ghi vào bảng `audit_logs`.

Số liệu (Giai đoạn 3), thử trong Swagger sau khi đăng nhập: `GET /api/v1/classes/{id}/dashboard?semester=1|2|year` (GVCN của lớp và BGH), `GET /api/v1/classes/{id}/subjects/{subject_id}/scores?semester=1|2` (GVBM đúng môn, GVCN, BGH), `GET /api/v1/grades/{level}/overview?semester=1|2|year` (chỉ BGH). Ví dụ lớp 11A2 có id 5, môn Toán có id 2, `semester=year` là cả năm. Công thức và ngưỡng của Thông tư 22 chỉ nằm trong `backend/app/analytics/`, hệ số và ngưỡng lấy từ bảng `settings`; bộ 30 ca tính tay ở `eval/analytics_cases.json`.

Mã môn trong email: `van` `toan` `anh` `su` `gdtc` `gdqp` `hdtn` `gddp` `dia` `gdktpl` `ly` `hoa` `sinh` `cn` `tin` `nhac` `mt`.

Học sinh dùng cho kịch bản demo và test biên: `HS1102001` (11A2, em An nghỉ 38 buổi), `HS1102002` (11A2, môn Toán dưới 3,5), `HS1201001` đến `HS1201003` (12A1, nghỉ 44, 45, 46 buổi), `HS1201004` đến `HS1201006` (12A1, mọi đầu điểm Toán đúng 3,4 / 3,5 / 5,0). Mã học sinh có dạng `HS` + khối + lớp (2 chữ số) + số thứ tự (3 chữ số).

## Các màn hình

Giao diện tiếng Việt, số kiểu `6,5`. Thanh bên trái (thu gọn được), chế độ sáng / tối / theo hệ thống (nhớ lựa chọn), dùng được từ điện thoại đến màn hình 1366px trở lên (D-095). Mọi con số do API tính (front-end không tự tính điểm). Kỳ xem (học kỳ I, II, cả năm) nằm trong `?semester=` của URL.

| Địa chỉ | Ai dùng | Nội dung |
| --- | --- | --- |
| `/` | Mọi vai trò | Trang chủ theo vai trò: GVBM thấy lớp-môn đang dạy ("Bảng điểm", "Nhập điểm"); GVCN thấy thẻ lớp chủ nhiệm ("Dashboard lớp", nhập điểm danh, rèn luyện); BGH thấy các khối |
| `/classes/{id}` | GVCN của lớp, BGH | Dashboard lớp: sĩ số, các mức học tập, nghỉ nhiều, bảng ĐTB các môn, học sinh cần quan tâm, nghỉ theo tháng, điều kiện lên lớp (cả năm) |
| `/classes/{id}/subjects/{subject_id}` | GVBM đúng môn, GVCN, BGH | Bảng điểm môn: lưới đầu điểm, ĐTB, ô thiếu đầu điểm tô nổi, phân bố điểm |
| `/classes/{id}/students/{student_id}` | GVCN, BGH (đầy đủ); GVBM (chỉ môn mình dạy) | Hồ sơ học sinh: điểm từng môn, học tập, rèn luyện, chuyên cần, phụ huynh (chỉ khi API trả về) |
| `/grades/{level}` | BGH | So sánh các lớp trong khối, học kỳ I cạnh học kỳ II |
| `/classes/{id}/import` | GVBM, GVCN | Nhập dữ liệu từ tệp (mục bên dưới) |
| `/assistant` | GVBM, GVCN, BGH | Trợ lý AI (cùng khung chat với nút nổi "Hỏi Trợ lý AI" ở mọi màn hình); Admin không dùng |
| `/reports` | GVBM, GVCN, BGH | Nhận xét & báo cáo do AI viết: sinh cả lớp (chạy nền, có tiến độ), sửa từng em, duyệt, xuất PDF (mục "Nhận xét và báo cáo"); Admin không dùng |
| `/admin/regulations` | Admin | Quản lý văn bản quy định: danh sách, tải lên, đánh dấu hết hiệu lực / bật lại, thử tìm (mục "Văn bản quy định") |
| `/admin/users` | Admin | Tài khoản: danh sách có lọc, tạo (mật khẩu tạm hiện một lần), sửa tên / email / vai trò, đặt lại mật khẩu, khoá / mở khoá (mục "Quản trị") |
| `/admin/school` | Admin | Năm học (một năm duy nhất), các lớp theo khối, giáo viên chủ nhiệm, thêm / xoá lớp trống |
| `/admin/classes/{id}` | Admin | Quản trị một lớp: phân công giảng dạy (có sao chép từ lớp cùng khối), nhập danh sách học sinh từ Excel/CSV, gỡ học sinh nhập nhầm theo mã |
| `/account/password` | Mọi vai trò | Tự đổi mật khẩu (menu người dùng › Đổi mật khẩu) |

Id lớp và học sinh xem ở mục tài khoản dev (lớp 11A2 có id 5, môn Toán có id 2). Hồ sơ học sinh qua API: `GET /api/v1/classes/{id}/students/{student_id}/profile?semester=1|2|year`; GVBM nhận hồ sơ chỉ có các môn mình dạy.

## Quản trị (Admin)

Chức năng của Admin (D-096 đến D-101). **Admin không xem điểm hay danh sách học sinh** (D-039): các màn hình chỉ có số đếm (sĩ số, số môn đã phân công), và gỡ học sinh theo mã gõ vào.

- **Tài khoản**: không xoá, chỉ **khoá** (tài khoản bị khoá không đăng nhập được và phiên đang mở bị từ chối ở yêu cầu kế tiếp). Tạo mới hoặc đặt lại mật khẩu thì hệ thống sinh mật khẩu tạm 12 ký tự, **chỉ hiện một lần** (không lưu bản đọc được, không ghi nhật ký); người dùng tự đổi ở menu người dùng. Admin không tự khoá hay hạ quyền chính mình, nên luôn còn ít nhất một Admin; giáo viên còn chủ nhiệm hoặc phân công thì chưa đổi sang vai trò khác được.
- **Năm học và lớp**: chỉ **một năm học** (code hiện không có "năm hiện hành", D-098). Tên lớp bắt đầu bằng số khối (ví dụ `11A9`); mỗi giáo viên chỉ chủ nhiệm một lớp; chỉ xoá được lớp chưa có học sinh và phân công. Đổi ngày năm học bị từ chối nếu có điểm danh nằm ngoài khoảng mới.
- **Phân công**: môn của lớp chính là các dòng phân công, nên lớp mới tạo phải được phân công thì giáo viên bộ môn mới nhập được điểm. Gỡ phân công bị từ chối khi lớp đã có điểm môn đó (chỉ đổi giáo viên).
- **Nhập danh sách học sinh** (`kind=roster`, chỉ Admin): cột `Mã HS`, `Họ và tên` bắt buộc; `Ngày sinh`, `Họ tên phụ huynh`, `Số điện thoại` tuỳ chọn. Mã đã có trong lớp thì cập nhật theo tệp (ô trống không xoá thông tin cũ); học sinh đang ở lớp khác thì báo lỗi. Bản xem trước **không hiện thông tin cũ**. Tệp mẫu: `data/samples/danh-sach-hoc-sinh-11a9.xlsx` (tạo lớp 11A9 trước).
- **Thử nhanh**: đăng nhập `admin@example.com`, vào "Năm học & lớp", thêm lớp `11A9` với một giáo viên chưa chủ nhiệm lớp nào (tạo ở "Tài khoản" trước), "Quản lý" lớp đó, gán Toán hoặc sao chép phân công từ 11A1, rồi nhập tệp mẫu. API: Swagger `/api/docs`, nhóm `admin`. Dọn dữ liệu thử bằng `make seed`.

## Cảnh báo sớm

Giai đoạn 6: hai lớp, gộp thành mức **Cao / Trung bình / Thấp** cho từng học sinh (từ ngữ trong giao diện: "cần hỗ trợ"; chỉ là gợi ý để giáo viên quyết định, không tự gửi cho học sinh hay phụ huynh).

- **Luật cứng theo Thông tư 22** (`backend/app/warning/rules.py`): nghỉ từ 30, 40, quá 45 buổi; mức học tập Chưa đạt; môn dưới 3,5; ít hơn 6 môn từ 5,0; từ 2 môn nhận xét Chưa đạt; rèn luyện học kỳ I Chưa đạt; môn có thể kiểm tra lại; khối 12: môn thi tốt nghiệp ĐTB thấp. Mỗi luật có câu lý do tiếng Việt kèm số liệu; ngưỡng đọc từ bảng `settings`.
- **Mô hình ML** (Random Forest, dự báo "Chưa đạt cả năm" từ giữa học kỳ I): huấn luyện trên dữ liệu **giả lập** nhiều khoá (`make train`), số liệu và giới hạn ở [backend/ml/REPORT.md](backend/ml/REPORT.md). Recall trên tập test 0,92, nhưng vì dữ liệu tự sinh nên **chưa chứng minh dùng được với dữ liệu thật**. Mô hình nhỏ đã commit; thiếu mô hình thì chỉ chạy lớp luật.
- **API** (xem Swagger): `GET /api/v1/classes/{id}/alerts` (GVCN của lớp, BGH), `PATCH /api/v1/alerts/{id}` (GVCN ghi `contacted` / `false_alarm` / `new`), `GET /api/v1/alerts?level=high` (chỉ BGH, cảnh báo toàn trường). GVBM không thấy cảnh báo.
- **Tự chạy lại** sau mỗi lần nhập tệp (hook `on_data_changed`; lỗi chỉ ghi log, không làm hỏng việc nhập). Cảnh báo chỉ thêm dòng mới khi nội dung đổi nên ghi nhận "đã trao đổi" / "báo nhầm" của GVCN không bị mất.
- **Demo**: `make seed SEED_ARGS="--hold-out 2027-03"`, đăng nhập `gvcn.11a2@example.com`, xem em An ("nghỉ 34 buổi") ở dashboard lớp 11A2, nhập `data/samples/diem-danh-11a2-2027-03.csv`, mở lại dashboard: cảnh báo của em An đã đổi thành "nghỉ 38 buổi".

## Trợ lý AI

Giai đoạn 8: giáo viên và BGH hỏi bằng tiếng Việt (nút nổi **Hỏi Trợ lý AI** ở góc phải mọi màn hình, hoặc trang `/assistant`). LLM chỉ được chọn trong **7 hàm chỉ đọc** (`backend/app/assistant/tools.py`); số liệu do Analytics tính, điều khoản do RAG tra; mỗi câu trả lời có mục **Nguồn** và nút Đúng / Sai.

- **Cấu hình LLM** (`.env`, xem `.env.example`): `LLM_PROVIDER=anthropic` + `LLM_API_KEY` (SDK chính thức, mặc định `claude-sonnet-5-5`), hoặc `LLM_PROVIDER=gemini` + `LLM_API_KEY` (khoá tạo ở Google AI Studio, mặc định `gemini-flash-latest`; gói miễn phí giới hạn vài yêu cầu mỗi phút và không có Pro), hoặc `LLM_PROVIDER=ollama` + `LLM_MODEL` + `OLLAMA_URL` (chạy nội bộ). Để trống thì Trợ lý trả HTTP 503 ("chưa được cấu hình") còn các phần khác vẫn chạy. Đổi nhà cung cấp chỉ đổi biến môi trường. `ASSISTANT_RATE_PER_MINUTE` (mặc định 10) giới hạn số câu hỏi mỗi phút mỗi tài khoản.
- **Riêng tư:** họ tên và mã học sinh được thay bằng mã tạm `HS_01`... trước khi gửi LLM và đổi lại khi hiển thị; không bao giờ gửi ngày sinh hay thông tin phụ huynh. Bộ ẩn danh chỉ sống trong một câu hỏi; `ai_logs` lưu bản đã ẩn danh.
- **Phân quyền:** mỗi hàm qua `authorize()`; lớp, môn, kỳ của màn hình đang mở là mặc định, giá trị LLM tự điền vẫn phải qua `authorize()` (ngoài quyền thì bị chặn và trợ lý báo không có quyền). GVBM chỉ hỏi được môn mình dạy; Admin không dùng trợ lý.
- **API** (xem Swagger): `POST /api/v1/assistant/chat` (`question`, và tuỳ chọn `class_id`, `subject_id`, `semester` của màn hình đang mở), `PATCH /api/v1/assistant/logs/{id}/feedback` (`correct` hoặc `incorrect`, chỉ người đã hỏi). Mỗi câu hỏi độc lập, trợ lý không nhớ các câu trước.
- **Thử không cần khoá API:** `make test` dùng LLM giả. Để thử bằng LLM thật điền khoá vào `.env`, `make up`, đăng nhập `gvcn.11a2@example.com`, mở lớp 11A2 và hỏi "Vì sao em An bị cảnh báo?". Đo chất lượng: `make eval-assistant`.

## Nhận xét và báo cáo

Giai đoạn 9 (D-102 đến D-109): AI viết **bản nháp**, giáo viên đọc, sửa và **duyệt**; chỉ bản đã duyệt mới xuất được PDF. Màn hình `/reports` (mở từ thanh bên, hoặc nút "Tạo nhận xét" ở hồ sơ học sinh).

| Loại | Ai viết và duyệt | Nội dung |
| --- | --- | --- |
| Nhận xét môn | GVBM dạy đúng lớp-môn | Điểm các đầu điểm và ĐTB học kỳ của một môn, không có điểm trung bình lớp |
| Nhận xét học bạ | GVCN của lớp | Mức học tập, rèn luyện, ĐTB các môn, chuyên cần |
| Phiếu liên lạc | GVCN của lớp | Như học bạ, thêm lời gửi phụ huynh, bảng điểm; xuất PDF có tên trường, lớp, học kỳ |
| Báo cáo lớp | GVCN của lớp hoặc BGH | Số liệu tổng hợp của lớp, không nêu tên học sinh |
| Báo cáo khối | BGH | So sánh các lớp trong khối |

- **Sinh cả lớp** chạy nền: bấm "Sinh nhận xét cả lớp", đóng trang cũng được. Mỗi lần gọi AI viết tối đa 5 em để tiết kiệm yêu cầu (gói Gemini miễn phí chỉ 20 yêu cầu mỗi ngày mỗi mô hình; đo thật: 40 em trong khoảng 74 giây, khoảng 13 yêu cầu). Hết hạn mức giữa chừng thì dừng, giữ phần đã viết; bấm "Tiếp tục" để viết phần còn thiếu.
- **Kiểm tự động trước khi lưu nháp:** mọi con số phải có trong dữ liệu hệ thống; không có từ gắn nhãn tiêu cực, so sánh với bạn khác hay nhắc hoàn cảnh gia đình ([backend/app/reports/banned_words.txt](backend/app/reports/banned_words.txt), nhà trường bổ sung dần); không có tên hay mã học sinh. Không đạt thì AI viết lại tối đa 2 lần, vẫn không đạt thì để trống cho giáo viên tự viết ("Cần tự viết"). Văn bản giáo viên sửa không bị chặn nhưng hiện cảnh báo nếu có vấn đề.
- **Riêng tư:** AI nhận số liệu của từng em dưới mã tạm `HS_01`...; không nhận họ tên, mã, ngày sinh, thông tin phụ huynh, cảnh báo sớm hay điều kiện lên lớp; nhận xét gọi học sinh là "em". Họ tên và tên phụ huynh chỉ xuất hiện trong PDF, lấy từ cơ sở dữ liệu.
- **Cấu hình:** `SCHOOL_NAME` trong `.env` là tên trường in ở đầu PDF (mặc định "Trường THPT (chưa đặt tên)"). LLM cấu hình như Trợ lý AI (mục trên). PDF dùng `reportlab` và phông Noto Sans (giấy phép OFL, đã cắt còn Latin và tiếng Việt) nằm sẵn trong `backend/app/reports/assets/`, không cần thư viện hệ thống.
- **Thử nhanh:** đăng nhập `gvcn.11a2@example.com`, `/reports`, chọn "Phiếu liên lạc", "Sinh nhận xét cả lớp", mở em An, sửa, "Duyệt", "Xuất PDF". Cần `LLM_PROVIDER` và khoá trong `.env`; không có thì trang báo "chưa được cấu hình" (HTTP 503). Test dùng LLM giả nên không cần khoá. Dọn dữ liệu thử: xoá các dòng của bảng `reports` và `report_jobs`.
- **API** (xem Swagger, nhóm `reports`): `POST /reports` (một em hoặc báo cáo: 201; cả lớp: 202 kèm công việc), `GET /reports` (danh sách và tiến độ), `PUT /reports/{id}` (sửa và/hoặc duyệt), `POST /reports/{id}/regenerate`, `GET /reports/{id}/export?format=pdf`, `GET /reports/jobs/{id}`.

## Nhập điểm, điểm danh, rèn luyện từ tệp

Giai đoạn 4: giáo viên nhập tệp `.xlsx` hoặc `.csv` (UTF-8) xuất từ sổ điểm điện tử. Luồng luôn là **tải tệp, xem trước (chưa ghi gì), xác nhận mới ghi**; còn dòng lỗi thì không ghi gì cả. Giao diện: <http://localhost:5173/classes/5/import> (id lớp 11A2), hoặc bấm "Nhập điểm" ở bảng lớp-môn, "Nhập điểm danh" / "Nhập rèn luyện" ở thẻ lớp chủ nhiệm trên trang chủ.

- **Ai nhập được:** điểm chỉ do giáo viên được phân công đúng lớp-môn; điểm danh và rèn luyện chỉ do GVCN của lớp. Ban giám hiệu và Admin xem được nhưng không nhập.
- **API** (xem Swagger): `POST /api/v1/classes/{id}/import/{assessments|attendance|conduct}` (multipart, trả bản xem trước), `POST /api/v1/imports/{job_id}/confirm` (ghi dữ liệu), `GET /api/v1/imports/mappings` (mẫu chọn cột đã lưu). Nhập lại cùng tệp không nhân đôi dữ liệu; ô trống không xoá điểm đã có; bản xem trước hết hạn sau 24 giờ.
- **Tệp mẫu** (`data/samples/`, cột và kịch bản thử xem [data/samples/README.md](data/samples/README.md)): `diem-toan-11a2-hk1.xlsx` (đúng), `diem-toan-11a2-hk1-loi.xlsx` (có lỗi cài sẵn), `diem-danh-11a2-2027-03.csv`, `danh-sach-hoc-sinh-11a9.xlsx` (danh sách lớp mới cho Admin, xem mục "Quản trị (Admin)").
- **Kịch bản demo "GVCN nhập tệp điểm danh tháng mới":** `make seed SEED_ARGS="--hold-out 2027-03"`, đăng nhập `gvcn.11a2@example.com`, nhập `diem-danh-11a2-2027-03.csv` cho lớp 11A2: 920 dòng mới, số buổi nghỉ của em An (`HS1102001`) từ 34 lên 38. Chạy `make seed` không tham số để về dữ liệu đầy đủ.
- Tệp tối đa 5 MB, 20.000 dòng, 60 cột. Giới hạn dung lượng thật khi triển khai cần đặt thêm ở reverse proxy (Giai đoạn 11).

## Test có PostgreSQL thật

Test trong `backend/tests/db/` cần PostgreSQL có pgvector (`make db`). Chúng dùng database riêng `classroom_test` trên cùng máy chủ với `DATABASE_URL` (hoặc `TEST_DATABASE_URL` nếu đặt): mỗi lần chạy xoá và dựng lại bằng Alembic rồi seed, nên không đụng DB phát triển `classroom`. Thiếu DB thì `make test` dừng và báo "Chạy make db trước".

# Trợ lý AI quản lý lớp học THPT

Web app cho trường THPT (khối 10, 11, 12): giáo viên bộ môn (GVBM), giáo viên chủ nhiệm (GVCN), Ban giám hiệu (BGH) theo dõi điểm, chuyên cần, rèn luyện; hệ thống cảnh báo sớm học sinh có nguy cơ không được lên lớp; AI hỗ trợ hỏi đáp và sinh nhận xét.

- Bản thiết kế đầy đủ, là nguồn sự thật: `docs/DESIGN.md`. Đọc mục liên quan trước khi làm bất kỳ giai đoạn nào.
- Sơ đồ kiến trúc và luồng hoạt động: `docs/FLOWS.md`.
- Tiến độ: `docs/PROGRESS.md`. Các quyết định thiết kế phát sinh: `docs/DECISIONS.md`.

## Nguyên tắc bất biến (không bao giờ vi phạm)

1. **Code tính số liệu, LLM chỉ diễn giải.** LLM không bao giờ đọc thẳng bảng điểm hay tự tính toán. Mọi con số trong câu trả lời của AI phải đến từ kết quả của một hàm Analytics.
2. **Công thức Thông tư 22/2021 chỉ nằm trong `backend/app/analytics/`.** Hệ số, ngưỡng (45 buổi, 3,5, 5,0, 6,5, 8,0, ngưỡng cảnh báo 30/40 buổi…) đọc từ bảng `settings`, không hard-code ở chỗ khác.
3. **LLM chỉ được gọi 7 hàm** trong `backend/app/assistant/tools.py`, tất cả chỉ đọc. Phạm vi dữ liệu (class_id, subject_id, grade_level) lấy từ phiên đăng nhập và bảng phân công, **không** lấy từ tham số do LLM điền.
4. **Mọi endpoint và mọi tool** đi qua `authorize(user, class_id, subject_id)`. GVBM: đúng phân công lớp–môn. GVCN: lớp chủ nhiệm. BGH: toàn trường. Sai → 403.
5. **Trước khi gửi dữ liệu sang LLM**, chạy `pseudonymize()`: họ tên và mã HS thành mã tạm (HS_01, HS_02…). Không bao giờ gửi `date_of_birth`, `guardian_name`, `guardian_phone`.
6. **Nhận xét và báo cáo do AI sinh luôn ở trạng thái `draft`** cho tới khi giáo viên bấm duyệt. Không có đường nào gửi bản nháp ra ngoài.
7. **Chỉ dùng dữ liệu giả lập** (`data/seed/`). Không commit dữ liệu thật hay khoá API.
8. **Không cần GPU.** Mọi mô hình chạy được trên CPU hoặc qua API.

## Tech stack

- Back-end: Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, pandas, openpyxl
- ML: scikit-learn (+ XGBoost tuỳ chọn), SHAP
- LLM: lớp `LLMProvider` chung; nhà cung cấp chọn bằng biến môi trường `LLM_PROVIDER` (API hoặc `ollama`)
- RAG: sentence-transformers (bge-m3 hoặc multilingual-e5), pgvector
- Database: PostgreSQL 16 + pgvector (Docker)
- Front-end: React + Vite + TypeScript, Tailwind CSS, Recharts, TanStack Query, React Router
- Kiểm thử: pytest, Playwright. DevOps: Docker Compose, GitHub Actions

## Cấu trúc repo

```
backend/
  app/
    auth/  classes/  imports/  analytics/  warning/  assistant/  rag/  reports/
    core/        # config, db session, settings, authorize, pseudonymize
    main.py
  alembic/
  ml/            # script/notebook huấn luyện, file mô hình
  tests/         # cấu trúc giống app/
frontend/src/
  pages/  components/  api/  hooks/
data/seed/       # script sinh dữ liệu giả
eval/            # bộ câu hỏi và script đánh giá AI
docs/
```

## Lệnh thường dùng

```
make up          # docker compose up -d (db + backend + frontend)
make db          # chỉ chạy PostgreSQL
make migrate     # alembic upgrade head
make seed        # sinh dữ liệu giả lập
make dev-be      # uvicorn --reload
make dev-fe      # vite dev
make test        # pytest (+ vitest nếu có)
make lint        # ruff check + ruff format --check + eslint + tsc --noEmit
make eval        # chạy toàn bộ eval/
```

## Quy ước

- Tên biến, hàm, bảng, cột: tiếng Anh, theo đúng tên trong `docs/DESIGN.md` mục 5. Chuỗi hiển thị trên giao diện: tiếng Việt.
- Python: type hints đầy đủ, ruff, schema Pydantic riêng cho request/response. Mọi thay đổi schema DB đi qua migration Alembic.
- Điểm: lưu số, làm tròn 1 chữ số thập phân khi tính ĐTB (đối chiếu Thông tư 22). Hiển thị kiểu Việt Nam: `6,5`.
- Test: mỗi công thức Analytics có test với số liệu tính tay; mỗi endpoint có test phân quyền cho cả 4 vai trò.
- Commit theo Conventional Commits (`feat:`, `fix:`, `test:`…), mỗi giai đoạn ít nhất một commit.

## Cách làm việc

- Bắt đầu mỗi giai đoạn bằng kế hoạch ngắn; làm từng bước nhỏ; chạy `make test` và `make lint` trước khi báo xong.
- Thiết kế chưa rõ hoặc mâu thuẫn: **hỏi lại**, không tự đoán. Quyết định đã chốt ghi vào `docs/DECISIONS.md`.
- Cuối mỗi giai đoạn: cập nhật `docs/PROGRESS.md` (đã xong gì, còn gì, cách chạy thử).
- Không xoá hoặc viết lại phần đã hoàn thành của giai đoạn trước nếu không được yêu cầu.

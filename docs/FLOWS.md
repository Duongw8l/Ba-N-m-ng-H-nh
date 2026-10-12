# Sơ đồ kiến trúc và luồng hoạt động

Bản Mermaid của các sơ đồ trong `docs/DESIGN.md` (mục 3, 6.3 và 9). Khi có khác biệt, `DESIGN.md` là chuẩn.

## 1. Kiến trúc tổng thể (DESIGN mục 3)

```mermaid
flowchart TD
    U1["GVBM / GVCN"] --> FE
    U2["BGH / Admin"] --> FE
    FE["Front-end · React<br/>Dashboard · Nhập dữ liệu · Trợ lý AI · Báo cáo"]
    FE -- "REST API · JWT" --> BE

    subgraph BE["Back-end · FastAPI"]
        AUTH["Auth<br/>JWT, quyền theo lớp"]
        CLS["Class & Student<br/>lớp, HS, phân công"]
        IMP["Import<br/>Excel/CSV, kiểm lỗi"]
        EW["Early Warning<br/>luật quy chế + ML"]
        REP["Report<br/>nháp AI, GV duyệt"]
        AST["AI Assistant<br/>gọi hàm + RAG"]
        ANA["Analytics<br/>tính điểm theo Thông tư 22 · nguồn số liệu duy nhất"]
        EW --> ANA
        REP --> ANA
        AST --> ANA
    end

    REP --> LLM["LLM<br/>API / Ollama<br/>chỉ nhận số liệu đã tính, tên HS thay bằng mã tạm"]
    AST --> LLM
    BE -- "SQLAlchemy" --> DB[("PostgreSQL + pgvector<br/>15 bảng + vector văn bản quy định")]
```

## 2. Xử lý một câu hỏi của trợ lý AI (DESIGN mục 6.3)

```mermaid
sequenceDiagram
    participant GV as Giáo viên
    participant A as AI Assistant
    participant L as LLM
    participant D as Analytics + RAG
    GV->>A: 1. Câu hỏi (lớp lấy từ phiên)
    A->>L: 2. Câu hỏi + 7 hàm được phép
    L-->>A: 3. Chọn hàm cần gọi
    A->>D: 4. Chạy hàm, kiểm tra quyền
    D-->>A: 5. Số liệu + điều khoản
    A->>L: 6. Kết quả, tên HS đã ẩn
    L-->>A: 7. Câu trả lời kèm nguồn
    A-->>GV: 8. Hiển thị + ghi ai_logs
```

## 3. Chu trình một năm học (DESIGN mục 9.1)

```mermaid
flowchart TD
    S["Đầu năm học<br/>Admin: năm học, lớp, phân công, GVCN<br/>Admin: nạp Thông tư 22, nội quy vào RAG"]
    T["Trong học kỳ I và II<br/>GVBM nhập điểm; GVCN điểm danh, rèn luyện<br/>Hệ thống tính lại và sinh cảnh báo<br/>GVCN xử lý cảnh báo (luồng 4)"]
    E["Cuối mỗi học kỳ<br/>Analytics tính ĐTB môn, xếp mức học kỳ<br/>GV sinh, sửa, duyệt nhận xét (luồng 5)<br/>Gửi phiếu liên lạc; BGH xem báo cáo khối"]
    D{"Cuối năm học:<br/>đủ điều kiện lên lớp?<br/>(học tập và rèn luyện từ Đạt, nghỉ ≤ 45 buổi)"}
    P["Lên lớp / hoàn thành chương trình<br/>Khối 12: dự thi tốt nghiệp THPT"]
    H["Hè: kiểm tra lại, rèn luyện<br/>Môn ĐTB cả năm dưới 5,0: kiểm tra lại<br/>Rèn luyện Chưa đạt: rèn luyện trong hè"]
    R["Xét lại sau hè<br/>đạt thì lên lớp, không đạt thì ở lại lớp"]
    S --> T --> E
    E -- "sau học kỳ I" --> T
    E --> D
    D -- "có" --> P
    D -- "không" --> H --> R
```

## 4. Nhập dữ liệu → cảnh báo → xử lý (DESIGN mục 9.2)

```mermaid
flowchart TD
    A["GV tải file Excel / CSV"] --> B["Import kiểm tra từng dòng<br/>mã HS, điểm 0–10, đủ đầu điểm"]
    B --> C{"Có dòng lỗi?"}
    C -- "có" --> C1["Tô đỏ dòng lỗi; GV sửa file"] -- "tải lại" --> A
    C -- "không" --> D["GV xem trước và xác nhận"]
    D --> E["Lưu; Analytics tính lại<br/>ĐTB môn, mức xếp loại, số buổi nghỉ"]
    E --> F["Early Warning chạy lại<br/>luật Thông tư 22 + mô hình ML"]
    F --> G{"Có cảnh báo mới?"}
    G -- "không" --> G1["Dashboard cập nhật, kết thúc"]
    G -- "có" --> H["GVCN mở hồ sơ, xem lý do<br/>3 lý do chính + điều khoản liên quan"]
    H --> I{"Cảnh báo đúng?"}
    I -- "không" --> I1["Đánh dấu 'báo nhầm'<br/>dùng để đánh giá lại mô hình"]
    I -- "có" --> J["Trao đổi với học sinh, phụ huynh<br/>GVCN ghi nhận 'đã trao đổi'<br/>Mức Cao: hiện trên dashboard BGH"]
    J -- "theo dõi ở lần nhập sau" --> A
```

## 5. Sinh nhận xét và duyệt (DESIGN mục 9.3)

```mermaid
flowchart TD
    A["[Giáo viên] Chọn lớp, học kỳ, loại<br/>học bạ, phiếu liên lạc hoặc báo cáo"]
    B["[Hệ thống] Lấy số liệu từ Analytics<br/>tên HS thay bằng mã tạm"]
    C["[LLM] Viết bản nháp theo mẫu<br/>điểm mạnh, cần cố gắng, gợi ý"]
    D{"[Hệ thống] Qua kiểm tra tự động?<br/>số liệu khớp JSON, không có từ ngữ tiêu cực"}
    E["[Giáo viên] Đọc và sửa từng em<br/>nhãn 'Bản nháp do AI tạo'"]
    F{"[Giáo viên] Duyệt?"}
    G["[Hệ thống] Lưu bản đã duyệt<br/>đổi mã tạm về tên thật"]
    H1["Xuất PDF, gửi phụ huynh<br/>học bạ, phiếu liên lạc"]
    H2["BGH xem và duyệt<br/>báo cáo lớp, khối"]
    A --> B --> C --> D
    D -- "không: LLM viết lại" --> C
    D -- "có" --> E --> F
    F -- "không: sinh lại kèm góp ý" --> C
    F -- "có" --> G
    G --> H1
    G --> H2
```

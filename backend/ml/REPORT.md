# Báo cáo mô hình cảnh báo sớm

Tạo tự động bởi `make train` lúc 2026-10-12T21:45:12+00:00 (phiên bản `rf-20261012`, scikit-learn 1.9.1). **Đừng sửa tay**: chạy lại `make train` để cập nhật.

## Mục tiêu

Dự báo học sinh có nguy cơ kết quả học tập cả năm **Chưa đạt** từ dữ liệu **giữa học kỳ I** (sớm hơn các luật cứng), để giáo viên chủ nhiệm hỗ trợ sớm. Mô hình chỉ là gợi ý: mức cảnh báo cuối cùng gộp với lớp luật, và giáo viên quyết định.

## Dữ liệu

- **20 khoá giả lập** × 360 học sinh = **7200** học sinh, sinh bằng chính bộ sinh của seed (`data/seed/`) với các số ngẫu nhiên khác nhau; không dùng seed 2026 của DB demo nên học sinh demo là dữ liệu chưa từng thấy.
- Nhãn: kết quả học tập cả năm Chưa đạt, do `analytics/` tính. **811** học sinh dương tính (11,3%).
- Chia 80/20 theo học sinh (phân tầng theo nhãn): train 5760, test 1440 (dương tính trong test: 162). Tập test chỉ dùng một lần ở cuối.
- **Không dùng UCI Student Performance** (chưa có `data/external/`, và thang điểm 0 đến 20 của Bồ Đào Nha khó ánh xạ sang Thông tư 22).

## Đặc trưng (chụp tại giữa học kỳ I)

Ngày cắt là `start_date + 9 tuần` của năm học. Chỉ dùng điểm và chuyên cần; **không** dùng giới tính, dân tộc, nơi ở, hoàn cảnh gia đình (DESIGN mục 10).

| Đặc trưng | Ý nghĩa |
| --- | --- |
| `tx_mean` | Điểm thường xuyên học kỳ I (trung bình các môn) |
| `tx_min_subject` | Điểm thường xuyên thấp nhất của một môn |
| `n_tx_below_pass` | Số môn có điểm thường xuyên dưới mức Đạt |
| `gk_mean` | Điểm giữa kỳ học kỳ I (trung bình các môn) |
| `gk_min` | Điểm giữa kỳ thấp nhất của một môn |
| `n_gk_below_pass` | Số môn có điểm giữa kỳ dưới mức Đạt |
| `absent_total` | Số buổi nghỉ tới giữa học kỳ I |
| `absent_last_4_weeks` | Số buổi nghỉ trong 4 tuần gần nhất |
| `late_total` | Số buổi đi muộn tới giữa học kỳ I |

Không có: kết quả năm trước và rèn luyện kỳ trước (DB chỉ có một năm học), xu hướng điểm theo thời gian (điểm không có ngày). Với điểm không có ngày, "đã có tới giữa kỳ I" được xấp xỉ bằng toàn bộ đầu điểm thường xuyên và điểm giữa kỳ của học kỳ I.

## Kết quả trên tập test

Ngưỡng của từng mô hình chọn bằng cross-validation trên tập train: lớn nhất mà Recall >= 0,90. Các cột Recall, Precision, F1 là của lớp dương tính (Chưa đạt cả năm).

| Mô hình | Ngưỡng | Recall | Precision | F1 | ROC-AUC | AP |
| --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression (mốc) | 0,76 | 0,89 | 0,80 | 0,84 | 0,982 | 0,932 |
| **Random Forest (chính)** | 0,54 | 0,92 | 0,93 | 0,92 | 0,982 | 0,953 |

Cùng hai mô hình ở ngưỡng mặc định 0,5 (để tham khảo):

| Mô hình | Ngưỡng | Recall | Precision | F1 | ROC-AUC | AP |
| --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 0,50 | 0,95 | 0,66 | 0,78 | 0,982 | 0,932 |
| Random Forest | 0,50 | 0,92 | 0,92 | 0,92 | 0,982 | 0,953 |

**Tiêu chí Recall >= 0,75 của mô hình chính: ĐẠT** (Recall 0,92).

Ma trận nhầm lẫn của Random Forest trên tập test (ngưỡng 0,54):

| | Dự báo Chưa đạt | Dự báo không |
| --- | --- | --- |
| **Thực tế Chưa đạt** | 149 | 13 |
| **Thực tế không** | 12 | 1266 |

## Ngưỡng chuyển xác suất thành mức

- Trung bình: xác suất >= 0,54
- Cao: xác suất >= 0,80 (nhỏ nhất, từ ngưỡng Trung bình, mà Precision trên CV của train >= 0,95; nếu không có thì lấy điểm giữa ngưỡng Trung bình và 1)

## Đặc trưng quan trọng (Random Forest, độ giảm tạp chất)

| Đặc trưng | Tầm quan trọng |
| --- | --- |
| `tx_min_subject` | 0,387 |
| `gk_min` | 0,223 |
| `n_tx_below_pass` | 0,162 |
| `tx_mean` | 0,118 |
| `gk_mean` | 0,053 |
| `n_gk_below_pass` | 0,036 |
| `absent_total` | 0,011 |
| `late_total` | 0,006 |
| `absent_last_4_weeks` | 0,005 |

Giải thích cho từng học sinh dùng đóng góp cục bộ: với mỗi đặc trưng, mức xác suất giảm khi thay giá trị của em bằng trung vị của tập huấn luyện; lấy ba đặc trưng lớn nhất (`app/warning/model.py`).

## Giới hạn (đọc trước khi tin các con số)

1. **Dữ liệu tự sinh.** Nhãn và đặc trưng cùng do một bộ sinh tạo ra từ "năng lực" và số buổi nghỉ của từng em, nên mô hình chủ yếu học lại cách bộ sinh tạo số. Recall cao ở đây **chưa chứng minh** mô hình dùng được với dữ liệu thật; cần thử lại bằng dữ liệu thật đã ẩn danh của một trường.
2. **Một thời điểm duy nhất** (giữa học kỳ I). Sau thời điểm đó phần ML không đổi theo dữ liệu mới; lớp luật cứng mới là phần cập nhật.
3. **Ít dương tính** (11,3%): Recall trên tập test dao động theo cách chia; số trên là một lần chia.

## Cách cải thiện

- Thêm dữ liệu thật đã ẩn danh (hoặc UCI sau khi ánh xạ thang điểm) và đặc trưng năm trước, rèn luyện kỳ trước khi nhà trường có.
- Huấn luyện thêm các thời điểm khác (cuối học kỳ I, giữa học kỳ II) nếu điểm có ngày.
- Dùng phản hồi "báo nhầm" của giáo viên (lưu trong `risk_alerts.teacher_status`) để đánh giá lại ngưỡng.

## Chạy lại

```bash
make db && make migrate
make train   # vài phút; ghi backend/ml/models/ và file này
make warn    # tính lại cảnh báo cho cả trường với mô hình mới
```

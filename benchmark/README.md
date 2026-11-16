# Benchmark Day 7

| Nhóm | Dev | Test |
|---|---:|---:|
| Có đáp án và evidence | 15 | 5 |
| Thiếu bằng chứng | 2 | 2 |
| Tổng | 17 | 7 |

Dev kế thừa 15 câu Day 6 và bổ sung 2 câu thiếu bằng chứng. Test có 5 câu mới
về trí thông minh âm nhạc, ELIZA, GPU, chuyển kịch bản ứng dụng và MindSpore;
cùng 2 câu thiếu bằng chứng. Không dùng lại 5 câu test Day 6 đã phân tích.

Corpus giữ nguyên 35 trang và 201 chunk của cấu hình C. Nguồn là chương
*A General Introduction to Artificial Intelligence*, Huawei Technologies Co., Ltd.
(2023), DOI `10.1007/978-981-19-2879-6_1`, CC BY-NC-ND 4.0. Thông tin ghi nguồn,
trang được chọn, model và dấu kiểm tra dữ liệu nằm trong
`starter/data/day6/manifest.json`.

## Tạo và kiểm tra dữ liệu

Chạy từ gốc repo Day 7, sau khi chuyển dữ liệu theo
[hướng dẫn chuẩn bị](../docs/CHUAN_BI_DU_LIEU.md):

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -B -X utf8 scripts/prepare_benchmark.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Script chỉ dùng thư viện chuẩn, không cần database và không gọi model.
Chạy lại ghi đè các file được tạo; trạng thái rà nguồn được giữ nếu câu hỏi,
đáp án và evidence chưa đổi. Khi nội dung đổi, trạng thái trở về `pending`.

| File | Cách dùng |
|---|---|
| `new_cases.json` | 9 câu bổ sung để tạo benchmark |
| `dev.json`, `test.json` | Câu hỏi, đáp án/evidence hoặc lý do thiếu bằng chứng; dùng để chấm |
| `dev_queries.json`, `test_queries.json` | Chỉ ID, split, câu hỏi và filter; dùng làm đầu vào retrieval/agent |
| `cases.json` | ID, split, nhãn có/thiếu bằng chứng để tổng hợp đánh giá |
| `source_checks.json` | Nguồn, trang, vị trí ký tự và các chunk phủ evidence; kết quả quét corpus cho câu thiếu bằng chứng |
| `dev_source_checks.json`, `test_source_checks.json` | Nhãn nguồn tách theo split; đánh giá dev chỉ đọc nhãn dev |
| `split.json` | ID dev/test, SHA-256 và quy tắc đánh giá |
| `validation.json` | Kiểm tra số lượng, định dạng, text nguồn và trạng thái rà |
| `review.csv` | Xác nhận việc đọc nguồn; không phải điểm câu trả lời của agent |

Không gửi đáp án, gold, nhãn `answerable`, lý do thiếu thông tin hay kết quả
kiểm tra nguồn cho agent. Filter kế thừa từ query Day 6; riêng `test_05` nêu
rõ mục 1.4 trong câu hỏi nên có filter `section=1.4`, không lấy filter từ gold.

## Bằng chứng và cách chấm

Các phần tử `gold` của một câu là bằng chứng thay thế: một đoạn đủ hỗ trợ đáp án
được coi là hợp lệ. So khớp NFKC và gộp khoảng trắng để bỏ khác biệt trình bày;
không đổi nội dung, xóa điều kiện hoặc tự ghép lời giải vào evidence.

Hit@1 và Evidence Hit@3 xét một chunk đúng nguồn/trang chứa đủ evidence.
Context Evidence Rate xét context thực sự gửi model, có thể cần nhiều chunk.
`source_checks.json` ghi rõ các câu chưa có evidence nằm trọn trong một chunk;
không rút ngắn gold chỉ để tăng điểm. Các trường hợp này có thể đạt context tốt
nhưng không đạt metric một chunk. Đoạn tương đương vẫn cần đọc và ghi lý do.
`supporting_chunk_ids` liệt kê các chunk theo thứ tự nguồn, kể cả khi cần ghép
nhiều chunk; `single_chunk_ids` chỉ liệt kê chunk tự chứa đủ evidence.

Câu thiếu bằng chứng được kiểm tra trong toàn bộ corpus bằng các nhóm từ khóa,
đọc phần liên quan và đối chiếu các trang PDF tương ứng. `absence_reason`
giải thích cụ thể thông tin còn thiếu. Tìm từ khóa không tự chứng minh sự vắng mặt;
không dùng việc top-k không tìm thấy để kết luận. Phạm vi là text đã index của
35 trang, không khẳng định đã OCR toàn bộ hình/bảng hoặc tra cứu kiến thức ngoài.

Chỉ tính retrieval/context metrics trên các câu có đáp án. Câu thiếu bằng chứng
dùng để đánh giá khả năng từ chối. Chọn cấu hình trên dev, chốt rồi mới chạy
baseline và cấu hình được chọn trên cùng test. Nếu dùng test để chỉnh hệ thống,
cần tạo test mới.

## Rà nguồn

Ban đầu các câu trong `review.csv` có trạng thái `pending`; hiện 24/24 câu đã
được xác nhận nguồn. Quy trình rà hoặc cập nhật khi có thay đổi:

1. Với câu có đáp án, mở file dev/test tương ứng, đọc đáp án và từng evidence;
   đối chiếu PDF theo số trang vật lý ở `gold.page`, kể cả ngữ cảnh xung quanh.
2. Với câu thiếu bằng chứng, đọc `absence_reason`, các trang liên quan và kết quả
   quét corpus trong `source_checks.json`; kiểm tra không có đoạn trả lời hợp lệ.
3. Điền `confirmed` nếu chấp nhận, hoặc `needs_changes` và ghi lý do trong `note`.
   Lưu CSV UTF-8, chạy lại lệnh để cập nhật thống kê.

Kiểm tra bằng code và việc soạn câu hỏi chưa thay thế xác nhận khi đọc nguồn.
Bộ dữ liệu này chưa phải kết quả benchmark hoặc điểm chấm agent.

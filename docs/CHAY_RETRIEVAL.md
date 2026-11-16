# Chạy retrieval trên dev

Ba phương pháp dùng cùng 201 chunk, 17 query dev và filter do câu hỏi cung cấp.

| Phương pháp | Cách thực hiện |
|---|---|
| Dense | Query embedding E5, tìm cosine exact trong pgvector Day 6 |
| TF-IDF | Tìm từ khóa trên text, lọc metadata trước khi lấy top-3 |
| Hybrid | Lấy 10 candidate mỗi nhánh dense/TF-IDF; hợp nhất bằng RRF, hằng số 60 |

Cấu hình ở `config/retrieval.json`: top-3, context budget 3.000 ký tự tính cả
header nguồn. RRF cộng `1 / (60 + rank)` của từng nhánh, không cộng trực tiếp
cosine score với TF-IDF score. Các tham số này được đặt trước lần chạy dev.

## Kết nối Day 6

1. Mở Docker Desktop. Database `day6_lab` ở `127.0.0.1:15433`, bảng `lab_chunks`,
   cấu hình C. Nếu container đang dừng, chạy `docker start day6_student_starter-postgres-1`.
2. Dùng môi trường Python của Day 6 để giữ đúng phiên bản thư viện. Các thư viện
   dùng cho retrieval được ghi trong `requirements.txt`.
3. Giữ repo Day 6 cùng thư mục cha với Day 7, gồm dữ liệu đã xử lý, model local
   và cấu hình kết nối trong `starter/.env` của Day 6. Không đưa `.env` vào Git.

Model `intfloat/multilingual-e5-small`, revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, vector 384 chiều và chuẩn hóa L2.
Tài liệu dùng tiền tố `passage: `, query dùng `query: `. Kết nối chỉ đọc và
kiểm tra chữ ký model, ID, text, metadata, số chiều của toàn bộ 201 dòng với
bản đã chuyển. Sai dữ liệu hoặc lỗi kết nối làm lần chạy thất bại, không dùng
kết quả giả thay thế. Phiên bản PostgreSQL, pgvector và model thực tế được lưu
trong `summary.json` sau khi kết nối.

## Chạy từ gốc Day 7

Chuẩn bị dữ liệu và xác nhận nguồn theo [hướng dẫn benchmark](../benchmark/README.md),
sau đó chạy PowerShell:

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -B -X utf8 scripts/benchmark_retrieval.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Lệnh chỉ chạy dev, chưa chọn cấu hình cuối và chưa đánh giá test. Model embedding
chạy offline; không có API trả phí. Không cần tạo lại vector hoặc nạp lại database.
Kết quả nằm ở `results/retrieval/dev/`; chạy lại ghi đè các file cùng tên.

| File | Nội dung |
|---|---|
| `traces.jsonl` | Kết quả thực của từng query/phương pháp, filter, candidate, rank/score và context; chưa có gold |
| `evaluated_dev.json` | Đối chiếu với nhãn dev sau khi truy xuất xong |
| `metrics.csv` | Hit@1, Evidence Hit@3, bằng chứng trong context chuẩn bị, thời gian và phí dịch vụ |
| `summary.json` | Trạng thái chạy, cấu hình, phiên bản, SHA-256, bảng kết quả và giới hạn |

Bảng kết quả và nhận xét lần chạy hiện tại ở
[results/retrieval/README.md](../results/retrieval/README.md).

## Đọc kết quả

Hit@1 và Evidence Hit@3 chỉ tính trên 15 câu có đáp án; 2 câu thiếu bằng chứng
không nằm trong mẫu số. Evidence phải nằm đủ trong một chunk đúng nguồn/trang,
sau chuẩn hóa NFKC và khoảng trắng. Bằng chứng trải qua nhiều chunk không được
tính thành hit một chunk.

`prepared_context_evidence_rate` kiểm tra các chunk trong context đã chọn có
phủ đủ một evidence thay thế không. Context giữ nguyên toàn bộ text của các
chunk, không cắt câu để vừa budget. Đây là kiểm tra context chuẩn bị, chưa phải
Context Evidence Rate thực gửi model. Chưa có điểm câu trả lời, citation hoặc
từ chối; các phần này cần chạy agent thật.

Embedding query được tính một lần/câu rồi dùng chung cho dense và hybrid;
TF-IDF không cần embedding. Thời gian embedding, retrieval, tải model và tạo
TF-IDF index được ghi riêng. Thứ tự chạy cố định, có ảnh hưởng của cache;
một lần đo chưa đủ để kết luận tốc độ tổng quát. Phí dịch vụ 0 USD chưa tính
điện và phần cứng. Câu hỏi tiếng Việt, tài liệu tiếng Anh; TF-IDF hiện tách từ
đơn giản và chưa có bước dịch hoặc viết lại query.

Kiểm tra code bằng `python -m unittest discover -s tests -v`; unit test không
thay thế lần truy xuất thật trên dev. Chỉ chốt cấu hình sau khi có đủ thử nghiệm
cải thiện và đánh giá agent trên dev, rồi mới chạy test.
